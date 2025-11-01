# Extent of Resection (EOR) - Dual-Priority Extraction Proposal

## Current Implementation Gap

**Currently**: Only queries operative reports (`dr_type_text = 'Operative Record'`)
**Missing**: Post-operative imaging (MRI within 24-72 hours) - the radiographic gold standard for EOR assessment

---

## Clinical Reality: Two Complementary Sources for EOR

### Source 1: Operative Report (Surgeon's Assessment)
- **What it provides**: Intraoperative assessment, surgeon's impression
- **Limitations**:
  - Subjective assessment
  - Limited visualization of residual tumor intraoperatively
  - Surgeon may overestimate resection completeness

### Source 2: Post-Operative MRI (Radiologist's Assessment)
- **What it provides**: Objective radiographic assessment of residual enhancing tumor
- **Standard timing**: Within 24-72 hours post-surgery (before contrast breakdown)
- **Gold standard**: More accurate than intraoperative assessment
- **Limitations**:
  - Requires properly timed MRI (too early or too late affects accuracy)
  - Enhancement pattern interpretation needed

---

## Proposed Dual-Priority Strategy

### Strategy A: Sequential Prioritization (RECOMMENDED)

**Priority 1: Operative Report**
- Try operative report first (as currently implemented)
- Rationale: Often available, provides surgeon's assessment
- Extraction: Verbal EOR assessment (GTR, NTR, STR, BIOPSY)

**Priority 2: Post-Operative MRI (if operative report unavailable OR incomplete)**
- Query v_imaging for MRI within surgery_date + 24-72 hours
- Extraction: Radiologist assessment of "residual enhancing tumor"
- Map to EOR categories:
  - "No residual" or "Complete resection" → GTR
  - "Minimal residual" or "Small amount of residual" → NTR
  - "Residual enhancing tumor" → STR
  - "Biopsy site only" → BIOPSY

**Why Sequential?**
- Operative report directly states EOR category
- Post-op MRI requires interpretation of residual description
- If both available, operative report + post-op MRI provide **complementary evidence**

### Strategy B: Parallel Extraction with Reconciliation

**Extract from BOTH sources:**
1. Query operative report → Extract surgeon's EOR
2. Query post-op MRI → Extract radiologist's residual assessment
3. **Reconcile** if discrepant:
   - If surgeon says GTR but MRI shows residual → Use MRI (downgrade to STR/NTR)
   - If surgeon says STR and MRI confirms residual → Concordant (use surgeon's)
   - If surgeon says GTR and MRI confirms no residual → Concordant (use GTR)

**Why Parallel?**
- More accurate EOR assessment
- Captures clinically important discrepancies
- Allows for "radiographic EOR" vs "surgical EOR"

**Challenges:**
- Requires reconciliation logic
- More complex implementation
- May need to store BOTH assessments

---

## Implementation Recommendation

### **Use Strategy A (Sequential) UNLESS both sources readily available**

Implement as escalating search:

```python
def _find_eor_documents(self, surgery_date: str, patient_id: str) -> List[Dict]:
    """
    Find documents for EOR extraction in priority order:
    1. Operative Report
    2. Post-operative MRI (if operative report unavailable)
    3. Discharge summary (fallback)
    """
    candidates = []

    # Priority 1: Operative Report
    operative_reports = self._query_operative_reports(surgery_date, patient_id)
    if operative_reports:
        candidates.extend([{
            'priority': 1,
            'type': 'operative_report',
            'source': 'surgeon_assessment',
            **report
        } for report in operative_reports])

    # Priority 2: Post-Operative MRI (24-72 hours post-surgery)
    postop_mri = self._query_postop_mri(surgery_date, patient_id)
    if postop_mri:
        candidates.extend([{
            'priority': 2,
            'type': 'postop_mri',
            'source': 'radiographic_assessment',
            **mri
        } for mri in postop_mri])

    # Priority 3: Discharge Summary
    discharge = self._query_discharge_summary(surgery_date, patient_id)
    if discharge:
        candidates.extend([{
            'priority': 3,
            'type': 'discharge_summary',
            'source': 'clinical_summary',
            **ds
        } for ds in discharge])

    return candidates
```

### New Method: _query_postop_mri()

```python
def _query_postop_mri(self, surgery_date: str, patient_id: str) -> List[Dict]:
    """
    Query for post-operative MRI within 24-72 hours (up to 7 days max)

    Returns MRI reports that likely contain EOR assessment
    """
    query = f"""
    SELECT
        diagnostic_report_id as binary_id,
        imaging_date,
        imaging_modality,
        report_conclusion,
        DATE_DIFF('hour', CAST(TIMESTAMP '{surgery_date}' AS TIMESTAMP), CAST(imaging_date AS TIMESTAMP)) as hours_post_surgery
    FROM fhir_prd_db.v_imaging
    WHERE patient_fhir_id = '{patient_id}'
      AND imaging_modality = 'MR'
      AND imaging_date > CAST(TIMESTAMP '{surgery_date}' AS TIMESTAMP)
      AND imaging_date <= CAST(TIMESTAMP '{surgery_date}' AS TIMESTAMP) + INTERVAL '7' DAY
      AND (
          LOWER(report_conclusion) LIKE '%post%op%'
          OR LOWER(report_conclusion) LIKE '%post%surg%'
          OR LOWER(report_conclusion) LIKE '%resection%'
          OR LOWER(report_conclusion) LIKE '%residual%'
      )
    ORDER BY imaging_date ASC
    LIMIT 3
    """

    results = query_athena(query, suppress_output=True)

    postop_mris = []
    for r in results:
        hours_post = r['hours_post_surgery']

        # Flag optimal timing (24-72 hours)
        if 24 <= hours_post <= 72:
            timing_quality = 'optimal'
        elif hours_post < 24:
            timing_quality = 'early'  # May have surgical changes
        elif hours_post > 72:
            timing_quality = 'delayed'  # Contrast breakdown may confuse assessment
        else:
            timing_quality = 'acceptable'

        postop_mris.append({
            'binary_id': r['binary_id'],
            'imaging_date': r['imaging_date'],
            'hours_post_surgery': hours_post,
            'timing_quality': timing_quality,
            'report_conclusion': r['report_conclusion']
        })

    return postop_mris
```

### Updated MedGemma Prompt for Post-Op MRI Interpretation

```python
def _generate_postop_mri_eor_prompt(self, surgery_date: str, mri_date: str, hours_post: int) -> str:
    """
    Generate prompt for extracting EOR from post-operative MRI report
    """
    prompt = f"""You are a medical AI extracting extent of resection from a POST-OPERATIVE MRI report.

SURGICAL CONTEXT:
- Surgery Date: {surgery_date}
- MRI Date: {mri_date}
- Time since surgery: {hours_post} hours

TASK:
Extract the radiologist's assessment of residual enhancing tumor to determine extent of resection.

OUTPUT FORMAT (JSON):
{{
  "radiographic_extent_of_resection": "GTR" or "NTR" or "STR" or "UNCLEAR",
  "residual_enhancing_tumor": "yes" or "no" or "minimal" or "unclear",
  "radiologist_description": "verbatim description of residual tumor from impression",
  "resection_cavity_description": "description of post-surgical changes",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

INTERPRETATION GUIDE:
- "No residual enhancing tumor" → GTR
- "Complete resection" → GTR
- "No significant residual" → GTR
- "Minimal residual enhancement" or "Small amount of residual" → NTR
- "Residual enhancing tumor" or "Residual enhancement" → STR
- "Large residual tumor" → STR
- "Post-biopsy changes only" → BIOPSY

IMPORTANT:
- Focus on "enhancing tumor" (contrast-enhancing lesion)
- Distinguish residual tumor from post-surgical blood products (may enhance)
- If report mentions "difficult to assess" or "blood products" → set confidence to LOW
- Look in "Impression" or "Conclusion" section for radiologist's assessment

EXAMPLE:
Document: "Post-operative changes in right frontal region. No residual enhancing tumor identified. Small amount of blood products along resection margin."
Output:
{{
  "radiographic_extent_of_resection": "GTR",
  "residual_enhancing_tumor": "no",
  "radiologist_description": "No residual enhancing tumor identified",
  "resection_cavity_description": "Post-operative changes with blood products along resection margin",
  "extraction_confidence": "HIGH"
}}
"""
    return prompt
```

---

## Decision: Which Strategy?

### Recommendation: **Strategy A (Sequential) with opportunistic parallel**

**Implementation Plan:**
1. **Always try operative report first** (current behavior)
2. **If operative report not found OR extraction fails** → Query post-op MRI
3. **If BOTH available and operative report extraction successful** → Optionally query post-op MRI for validation (future enhancement)

**Advantages:**
- Maintains current workflow (operative report primary)
- Adds fallback to radiographic assessment
- Allows future enhancement for discrepancy detection
- Clear prioritization logic

**Metadata Tracking:**
- `eor_source`: "surgeon_assessment" vs "radiographic_assessment"
- `document_type`: "operative_report" vs "postop_mri"
- `timing_quality`: "optimal" (24-72hr) vs "early" vs "delayed"

---

## Example Output with Dual Sources

```json
{
  "extent_of_resection": {
    "category": "GTR",
    "percent_resection": 98,
    "surgeon_assessment": "Gross total resection achieved",
    "radiographic_assessment": "No residual enhancing tumor",
    "source": "concordant",
    "primary_document": {
      "type": "operative_report",
      "date": "2024-03-15",
      "confidence": "HIGH"
    },
    "confirmatory_document": {
      "type": "postop_mri",
      "date": "2024-03-17",
      "hours_post_surgery": 48,
      "timing_quality": "optimal",
      "confidence": "HIGH"
    }
  }
}
```

---

## Next Steps

1. ✅ Document the strategy (this file)
2. ⏳ Implement `_query_postop_mri()` method
3. ⏳ Add post-op MRI to document priority list
4. ⏳ Create `_generate_postop_mri_eor_prompt()` with interpretation guide
5. ⏳ Test with patients who have both operative reports AND post-op MRIs
6. ⏳ Validate concordance rate between surgical and radiographic EOR

---

**Clinical Note:**
In practice, neurosurgeons often use post-op MRI to refine their assessment. If MRI shows residual when surgeon reported GTR, the clinical team typically revises to STR/NTR. Therefore, radiographic assessment should be considered the **ground truth** when available and optimally timed.
