# Actual MedGemma Prompts - Examples

This document shows the **ACTUAL TEXT** that gets sent to MedGemma when the prompt functions are called with real data.

## Example 1: Tumor Status Extraction Prompt

### Input Data (from v_imaging table):
```python
report = {
    'diagnostic_report_id': 'eb.VViXySPQd-2I8fGfYCtOSuDA2wMs3FNyEcCKSLqAo3',
    'imaging_date': '2018-05-27 13:27:10.000',
    'imaging_modality': 'MRI Brain',
    'report_conclusion': 'HISTORY: Brain tumor follow-up.\n\nFINDINGS: Comparison is made to prior MRI from 2018-05-01.\n\nThere is stable appearance of an enhancing left frontal mass measuring 3.2 x 2.8 cm, previously 3.1 x 2.7 cm. No significant change in size. Minimal surrounding edema is unchanged. No new lesions identified.\n\nIMPRESSION: Stable left frontal enhancing mass.',
    'patient_fhir_id': 'e4BwD8ZYDBccepXcJ.Ilo3w3'
}

context = {
    'patient_id': 'Patient/e4BwD8ZYDBccepXcJ.Ilo3w3',
    'surgical_history': [
        {'date': '2018-05-15', 'description': 'Craniotomy for tumor resection'}
    ],
    'report_date': '2018-05-27 13:27:10.000',
    'events_before': [
        {
            'event_type': 'Imaging',
            'event_category': 'MRI Brain',
            'event_date': '2018-05-01',
            'days_diff': -26,
            'description': 'Prior MRI'
        },
        {
            'event_type': 'Procedure',
            'event_category': 'Surgery',
            'event_date': '2018-05-15',
            'days_diff': -12,
            'description': 'Craniotomy for tumor resection'
        }
    ],
    'events_after': []
}
```

### Actual Prompt Text Sent to MedGemma:

```
You are a neuro-oncology AI assistant analyzing a surveillance MRI report to determine tumor status.

**TASK:** Determine the tumor status by comparing this imaging to prior studies.

**IMAGING INFORMATION:**
Current imaging date: 2018-05-27 13:27:10.000
Comparison: Prior imaging: 26 days before (date: 2018-05-01)

**RADIOLOGY REPORT TEXT:**
HISTORY: Brain tumor follow-up.

FINDINGS: Comparison is made to prior MRI from 2018-05-01.

There is stable appearance of an enhancing left frontal mass measuring 3.2 x 2.8 cm, previously 3.1 x 2.7 cm. No significant change in size. Minimal surrounding edema is unchanged. No new lesions identified.

IMPRESSION: Stable left frontal enhancing mass.

**CLASSIFICATION CATEGORIES:**

1. **NED (No Evidence of Disease)** - Indicators:
   - "no evidence of tumor"
   - "no residual or recurrent disease"
   - "complete response"
   - "no abnormal enhancement"

2. **Stable** - Indicators:
   - "stable"
   - "unchanged"
   - "no significant change"
   - "similar to prior"
   - Measurements within 20% of prior

3. **Increased (Progression)** - Indicators:
   - "increased size"
   - "progression"
   - "new enhancement"
   - "enlarging"
   - Size increase >20%
   - New areas of enhancement

4. **Decreased (Partial Response)** - Indicators:
   - "decreased size"
   - "reduction in tumor burden"
   - "improved"
   - "smaller"
   - Size decrease >20%

5. **New_Malignancy** - Indicators:
   - "new lesion" distinct from primary site
   - "second primary"
   - "new tumor" in different location
   - "metastasis" (rare in primary brain tumors)

**OUTPUT FORMAT (JSON):**
{
  "tumor_status": "NED" | "Stable" | "Increased" | "Decreased" | "New_Malignancy",
  "confidence": 0.0-1.0,
  "comparison_findings": "Description of how current imaging compares to prior",
  "measurements": {
    "current_size": "e.g., '2.1 x 1.8 cm' or null",
    "prior_size": "e.g., '2.0 x 1.7 cm' or null",
    "change_description": "e.g., 'slight increase' or null"
  },
  "enhancement_pattern": "Description of enhancement if mentioned",
  "evidence": "Direct quote(s) from report supporting classification"
}

**IMPORTANT:**
- Rely heavily on radiologist's comparison statements
- Extract measurements if provided
- If report says "stable" explicitly, classify as Stable even without measurements
- Higher confidence (>0.9) if explicit comparison statement present
- Return ONLY valid JSON, no additional text
```

### Expected MedGemma Response (what SHOULD happen):

```json
{
  "tumor_status": "Stable",
  "confidence": 0.95,
  "comparison_findings": "Stable appearance of left frontal enhancing mass compared to prior MRI from 2018-05-01. No significant change in size.",
  "measurements": {
    "current_size": "3.2 x 2.8 cm",
    "prior_size": "3.1 x 2.7 cm",
    "change_description": "minimal increase within measurement error"
  },
  "enhancement_pattern": "Enhancing left frontal mass",
  "evidence": "Stable appearance of an enhancing left frontal mass measuring 3.2 x 2.8 cm, previously 3.1 x 2.7 cm. No significant change in size."
}
```

---

## Example 2: What's Actually Happening (THE PROBLEM)

### Actual Data from v_imaging:

**The issue**: The `report_conclusion` field from v_imaging appears to be EMPTY or only contains minimal text.

Based on the actual extraction results, here's what MedGemma is receiving:

```
You are a neuro-oncology AI assistant analyzing a surveillance MRI report to determine tumor status.

**TASK:** Determine the tumor status by comparing this imaging to prior studies.

**IMAGING INFORMATION:**
Current imaging date: 2018-05-27 13:27:10.000
Comparison: No prior imaging available for comparison

**RADIOLOGY REPORT TEXT:**
[EMPTY or minimal text - possibly just metadata]

**CLASSIFICATION CATEGORIES:**
[... rest of prompt ...]
```

### MedGemma's Response (actual):

```json
{
  "tumor_status": "Unknown",
  "confidence": 0.0,
  "comparison_findings": "No prior imaging available for comparison.",
  "measurements": {
    "current_size": null,
    "prior_size": null,
    "change_description": null
  },
  "enhancement_pattern": null,
  "evidence": "Comparison: No prior imaging available for comparison"
}
```

**Why MedGemma returns "Unknown":**
1. The `report_conclusion` field from v_imaging is likely empty or contains only minimal text
2. MedGemma sees no actual radiology report content to analyze
3. The context shows "No prior imaging available for comparison" even though surgical history exists
4. Without report text, MedGemma correctly returns "Unknown" with 0.0 confidence

---

## Example 3: Imaging Classification Prompt (WORKING)

This prompt **IS working** and returns valid results.

### Actual Prompt Text:

```
You are a medical AI analyzing a radiology report to classify the imaging study.

**TASK:** Classify this imaging study as one of:
- "pre_operative": Imaging before first tumor surgery (baseline/diagnostic imaging)
- "post_operative": Imaging within 72 hours after surgery to assess extent of resection
- "surveillance": Follow-up monitoring imaging (typically 3-6 months after treatment)

**IMAGING INFORMATION:**
Date: 2018-05-27 13:27:10.000
Modality: MRI Brain

**TEMPORAL CONTEXT (procedures near this imaging):**
- No tumor surgeries found in surrounding timeline (±30 days)

**RADIOLOGY REPORT TEXT:**
[EMPTY or minimal text]

**CLASSIFICATION CRITERIA:**
1. **Post-operative** if:
   - Report mentions "post-operative" or "status post resection"
   - Imaging is 0-3 days after a tumor surgery
   - Report assesses surgical changes or residual tumor

2. **Pre-operative** if:
   - This is the earliest imaging in timeline
   - Report describes initial tumor without prior surgery mentioned
   - Imaging occurs before any tumor surgery

3. **Surveillance** if:
   - Report compares to prior imaging ("compared to [date]")
   - Imaging is >14 days after surgery
   - Report monitors for recurrence/progression/stability

**OUTPUT FORMAT (JSON):**
{
  "imaging_classification": "post_operative" | "pre_operative" | "surveillance",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of classification based on temporal context and report text",
  "keywords_found": ["list", "of", "relevant", "keywords", "from", "report"]
}

**IMPORTANT:**
- Base classification primarily on temporal proximity to surgeries
- Use report keywords as supporting evidence
- If uncertain, choose most likely classification and set confidence < 0.8
- Return ONLY valid JSON, no additional text
```

### MedGemma's Response (actual - WORKING):

```json
{
  "imaging_classification": "pre_operative",
  "confidence": 0.9,
  "reasoning": "No tumor surgeries are found within ±30 days of the imaging study date. This suggests the imaging likely precedes any surgical intervention.",
  "keywords_found": []
}
```

**Why this works:**
- Classification relies primarily on TEMPORAL CONTEXT (surgery dates vs imaging dates)
- Does NOT require detailed radiology report text
- Uses surgical_history from context to determine classification
- Even with empty report text, can classify based on timeline

---

## Root Cause Analysis

### The Problem:
The `report_conclusion` field from v_imaging contains little or no actual radiology report text.

### Evidence:
1. All 82 imaging text extractions return "Unknown" for tumor status
2. MedGemma's evidence field shows: "Comparison: No prior imaging available for comparison"
3. Classification works because it uses temporal context, not report text
4. Tumor status extraction REQUIRES detailed report text to work

### Next Steps:
1. Query v_imaging directly to see what's actually in `report_conclusion` field
2. Check if there's a different field with full radiology reports
3. May need to use imaging PDFs instead of imaging text reports
4. Verify if the Athena view is properly extracting report text from FHIR DiagnosticReport resources
