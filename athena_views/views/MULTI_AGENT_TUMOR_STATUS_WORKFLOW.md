# MULTI-AGENT TUMOR STATUS ABSTRACTION WORKFLOW
**Version:** 1.0
**Date:** 2025-10-19
**Purpose:** Define longitudinal tumor status tracking using AI agents to extract from clinical narratives

---

## EXECUTIVE SUMMARY

**Problem:** Critical clinical information (extent of resection, tumor status) exists only in free text radiology reports and clinical notes, not in structured FHIR fields.

**Solution:** Two-agent workflow to:
1. **Agent 1 (Surgical Event Abstractor):** Extract extent of resection (EOR) from post-op MRI reports → Define tumor epochs
2. **Agent 2 (Tumor Status Abstractor):** Extract tumor status from surveillance imaging → Track longitudinal disease trajectory

**Key Innovation:** Provenance tracking enables cross-validation between structured data, radiology reports, and clinical notes - flagging discordance for human review.

---

## CLINICAL CONTEXT

### Tumor Management Paradigm

**Anchor Events** (Surgeries):
- Each surgical resection defines a new **diagnostic epoch**
- Epoch type determined by:
  - First surgery → `initial_diagnosis`
  - Surgery after recurrence → `recurrence_surgery`
  - Surgery after progression → `progression_surgery`

**Extent of Resection (EOR)** determines surveillance expectations:
- **GTR** (Gross Total Resection) → Expect NED or true recurrence
- **STR** (Subtotal Resection) → Stable residual disease vs. progression
- **Partial** → Significant residual disease
- **Biopsy** → Diagnostic only, no resection

**Tumor Status Evolution** within each epoch:
1. **NED** (No Evidence of Disease) - Complete response post-GTR
2. **Stable** - No change in residual/surveillance findings
3. **Increased** - Progression (size increase, new enhancement)
4. **Decreased** - Partial response (size reduction)
5. **New Malignancy** - Second primary or new lesion

### Assessment Sources
- **Post-op MRI** (within 72 hours of surgery) → EOR assessment
- **Surveillance MRI** (every 3-6 months) → Tumor status
- **Progress Notes** (at clinic visits) → Clinical assessment, plan changes
- **Operative Reports** → Surgical details, intraoperative findings

---

## DATA SOURCES

### Available Free Text Sources

| Source | Location | Volume | Content | Avg Length |
|--------|----------|--------|---------|------------|
| **Radiology Reports** | v_imaging.result_information | 72,649 | Full MRI/CT reports with findings, measurements, comparisons | 1,506 chars |
| **Progress Notes** | v_binary_files (type='Progress Notes') | 740,517 | Clinical notes from all specialties | Variable |
| **Operative Reports** | v_binary_files (description LIKE '%operative%') | ~150,000 | Surgical procedure notes | Variable |
| **Pathology Reports** | v_binary_files (type='Pathology study') | 155,044 | Histopathology findings | Variable |

### Key Views for Agents

**Created in V_AGENT_DATA_ACCESS_VIEWS.sql:**
1. `v_imaging_with_reports` - Radiology reports with full text
2. `v_postop_imaging` - Post-op MRI linked to surgeries
3. `v_progress_notes` - Clinical notes linked to visits
4. `v_operative_reports` - Operative notes linked to procedures

---

## AGENT 1: SURGICAL EVENT ABSTRACTOR

### Purpose
Extract extent of resection (EOR) from post-operative imaging reports to define tumor epochs.

### Input Data
```sql
SELECT
    patient_fhir_id,
    procedure_fhir_id,
    procedure_date,
    surgery_number,  -- 1st, 2nd, 3rd surgery
    imaging_procedure_id,
    imaging_date,
    days_post_op,
    radiology_report_text,  -- FREE TEXT TO EXTRACT FROM
    imaging_modality
FROM v_postop_imaging
WHERE patient_fhir_id = 'Patient/xyz'
ORDER BY procedure_date, imaging_date;
```

### Extraction Task

**Primary Goal:** Determine extent_of_resection from radiology report text

**Extraction Targets:**
```
Keywords for GTR:
- "gross total resection"
- "complete resection"
- "no residual enhancing tumor"
- "complete removal"
- GTR explicitly stated

Keywords for STR:
- "subtotal resection"
- "near-total resection"
- "95% resection" / "90% resection"
- "small amount of residual tumor"

Keywords for Partial:
- "partial resection"
- "debulking"
- "significant residual tumor"

Keywords for Biopsy:
- "biopsy only"
- "stereotactic biopsy"
- "no resection"
```

**Secondary Goal:** Determine epoch_type

```python
if surgery_number == 1:
    epoch_type = "initial_diagnosis"
elif "recurrence" in (diagnosis_text or report_text):
    epoch_type = "recurrence_surgery"
elif "progression" in (diagnosis_text or report_text):
    epoch_type = "progression_surgery"
else:
    epoch_type = "unknown_indication"
```

### Output Schema

```json
{
  "surgical_event_id": "proc_12345",
  "patient_fhir_id": "Patient/xyz",
  "surgery_date": "2023-06-15",
  "surgery_number": 1,
  "epoch_number": 1,
  "epoch_type": "initial_diagnosis",

  "extent_of_resection": "GTR",
  "eor_confidence": 0.95,
  "eor_evidence": {
    "report_excerpt": "Post-operative MRI demonstrates gross total resection of the enhancing tumor with expected post-surgical changes",
    "keywords_matched": ["gross total resection", "no residual enhancing tumor"],
    "source": "post_op_mri"
  },

  "imaging_report_id": "img_67890",
  "imaging_date": "2023-06-16",
  "days_post_op": 1,

  "provenance": {
    "extraction_timestamp": "2025-10-19T14:30:00Z",
    "agent_version": "surgical_abstractor_v1.0",
    "model": "claude-3-opus-20240229",
    "source_view": "v_postop_imaging",
    "source_documents": ["img_67890"]
  }
}
```

### Agent Implementation Pattern

```python
def extract_extent_of_resection(postop_imaging_record):
    """
    Agent 1: Extract EOR from post-op MRI report
    """
    prompt = f"""
    You are a neuro-oncology data abstractor. Extract the extent of resection (EOR)
    from this post-operative MRI report.

    CLINICAL CONTEXT:
    - Patient: {postop_imaging_record.patient_fhir_id}
    - Surgery Date: {postop_imaging_record.procedure_date}
    - Post-op MRI Date: {postop_imaging_record.imaging_date} ({postop_imaging_record.days_post_op} days post-op)
    - Modality: {postop_imaging_record.imaging_modality}

    RADIOLOGY REPORT:
    {postop_imaging_record.radiology_report_text}

    TASK:
    Determine the extent of resection based on the radiologist's assessment.

    CLASSIFICATION:
    - GTR (Gross Total Resection): Complete removal, no residual enhancing tumor
    - STR (Subtotal Resection): Near-complete removal, small residual tumor (>90%)
    - Partial: Significant residual tumor remains
    - Biopsy: Diagnostic biopsy only, no resection
    - Unknown: Insufficient information to classify

    OUTPUT FORMAT (JSON):
    {{
      "extent_of_resection": "GTR|STR|Partial|Biopsy|Unknown",
      "confidence": 0.0-1.0,
      "evidence": {{
        "report_excerpt": "Relevant excerpt from report",
        "keywords_matched": ["list", "of", "keywords"],
        "reasoning": "Brief explanation of classification"
      }}
    }}
    """

    response = llm.invoke(prompt)
    extracted_data = parse_json(response)

    return {
        **extracted_data,
        "surgical_event_id": postop_imaging_record.procedure_fhir_id,
        "patient_fhir_id": postop_imaging_record.patient_fhir_id,
        "surgery_date": postop_imaging_record.procedure_date,
        "imaging_report_id": postop_imaging_record.imaging_procedure_id,
        "provenance": {
            "extraction_timestamp": datetime.now().isoformat(),
            "agent_version": "surgical_abstractor_v1.0",
            "source_view": "v_postop_imaging"
        }
    }
```

---

## AGENT 2: TUMOR STATUS ABSTRACTOR

### Purpose
Extract longitudinal tumor status from surveillance imaging reports and clinical progress notes.

### Input Data

```sql
-- For each patient, get imaging within their current epoch
SELECT
    e.epoch_number,
    e.surgery_date as epoch_start_date,
    e.extent_of_resection,

    i.imaging_procedure_id,
    i.imaging_date,
    i.radiology_report_text,  -- FREE TEXT TO EXTRACT FROM
    i.imaging_modality,
    i.age_at_imaging_days,

    DATE_DIFF('day', e.surgery_date, i.imaging_date) as days_from_surgery,

    v.visit_date,
    v.visit_type,
    v.appointment_type_text

FROM tumor_epochs e  -- Output from Agent 1
JOIN v_imaging_with_reports i
    ON e.patient_fhir_id = i.patient_fhir_id
    AND i.imaging_date >= e.surgery_date
    AND (i.imaging_date < LEAD(e.surgery_date) OR next_surgery IS NULL)
LEFT JOIN v_visits_unified v
    ON i.patient_fhir_id = v.patient_fhir_id
    AND DATE(i.imaging_date) = v.visit_date

WHERE e.patient_fhir_id = 'Patient/xyz'
ORDER BY e.epoch_number, i.imaging_date;
```

### Extraction Task

**Primary Goal:** Determine tumor_status from surveillance imaging

**Extraction Targets:**
```
Keywords for NED:
- "no evidence of disease"
- "no evidence of recurrence"
- "no residual tumor"
- "complete response"
- "resolved"

Keywords for Stable:
- "stable"
- "unchanged"
- "no significant change"
- "similar to prior"

Keywords for Increased:
- "progression"
- "increased size"
- "new enhancement"
- "enlarging"
- "worse than prior"

Keywords for Decreased:
- "improvement"
- "decreased size"
- "partial response"
- "smaller than prior"
- "regression"

Keywords for New Malignancy:
- "new lesion"
- "second primary"
- "new mass"
- "additional tumor"
```

**Secondary Goal:** Extract quantitative measurements

```
Patterns:
- "tumor measures X.X x Y.Y cm" (current size)
- "previously measured A.A x B.B cm" (prior size)
- "increased from X to Y cm"
```

**Contextual Interpretation:**
- If EOR = GTR and report says "stable post-surgical changes" → NED (not stable disease)
- If EOR = STR and report says "stable" → Stable residual disease
- Always consider comparison to prior imaging

### Output Schema

```json
{
  "assessment_id": "assess_98765",
  "patient_fhir_id": "Patient/xyz",
  "assessment_date": "2023-09-20",
  "epoch_number": 1,
  "days_from_surgery": 97,

  "tumor_status": "stable",
  "status_confidence": 0.88,
  "status_evidence": {
    "report_excerpt": "Stable appearance of post-surgical changes with no evidence of recurrent tumor. No new enhancing lesions identified",
    "keywords_matched": ["stable", "no evidence of recurrent tumor"],
    "comparison_to_prior": "No change since prior study 3 months ago",
    "source": "radiology_report"
  },

  "measurements": {
    "current_size_cm": null,
    "prior_size_cm": null,
    "size_change_percent": null,
    "measurement_method": null
  },

  "clinical_significance": "stable_surveillance",

  "imaging_event_id": "img_11223",
  "linked_visit_id": "visit_44556",
  "visit_type": "Completed Visit",

  "eor_context": "GTR",
  "interpretation_note": "Given GTR status, stable post-surgical changes interpreted as NED",

  "provenance": {
    "extraction_timestamp": "2025-10-19T14:35:00Z",
    "agent_version": "status_abstractor_v1.0",
    "model": "claude-3-opus-20240229",
    "source_view": "v_imaging_with_reports",
    "source_documents": ["img_11223"],
    "eor_source": "surgical_abstractor_v1.0"
  }
}
```

### Agent Implementation Pattern

```python
def extract_tumor_status(imaging_record, epoch_context):
    """
    Agent 2: Extract tumor status from surveillance MRI report
    """
    prompt = f"""
    You are a neuro-oncology data abstractor. Extract the tumor status assessment
    from this surveillance MRI report.

    CLINICAL CONTEXT:
    - Patient: {imaging_record.patient_fhir_id}
    - Current Epoch: {epoch_context.epoch_number} ({epoch_context.epoch_type})
    - Surgery Date: {epoch_context.surgery_date}
    - Extent of Resection: {epoch_context.extent_of_resection}
    - Days Since Surgery: {imaging_record.days_from_surgery}
    - MRI Date: {imaging_record.imaging_date}
    - Modality: {imaging_record.imaging_modality}

    RADIOLOGY REPORT:
    {imaging_record.radiology_report_text}

    TASK:
    Determine the current tumor status based on the radiologist's findings.

    IMPORTANT CONTEXT:
    - If EOR was GTR and report shows "stable post-surgical changes", classify as NED
    - If EOR was STR and report shows "stable", classify as Stable (residual disease)
    - Always note comparison to prior studies if mentioned
    - Extract quantitative measurements if provided

    CLASSIFICATION:
    - NED: No evidence of disease (post-GTR with no recurrence)
    - Stable: Unchanged findings (stable residual or stable surveillance)
    - Increased: Progression, growth, new enhancement
    - Decreased: Improvement, size reduction, partial response
    - New_Malignancy: New distinct lesion, second primary
    - Uncertain: Ambiguous or insufficient information

    OUTPUT FORMAT (JSON):
    {{
      "tumor_status": "NED|Stable|Increased|Decreased|New_Malignancy|Uncertain",
      "confidence": 0.0-1.0,
      "evidence": {{
        "report_excerpt": "Relevant excerpt",
        "keywords_matched": ["keywords"],
        "comparison_to_prior": "What report says about comparison",
        "reasoning": "Explanation considering EOR context"
      }},
      "measurements": {{
        "current_size_cm": "X.X x Y.Y" or null,
        "prior_size_cm": "A.A x B.B" or null,
        "size_change_percent": numeric or null
      }}
    }}
    """

    response = llm.invoke(prompt)
    extracted_data = parse_json(response)

    return {
        **extracted_data,
        "assessment_id": f"assess_{imaging_record.imaging_procedure_id}",
        "patient_fhir_id": imaging_record.patient_fhir_id,
        "assessment_date": imaging_record.imaging_date,
        "epoch_number": epoch_context.epoch_number,
        "days_from_surgery": imaging_record.days_from_surgery,
        "eor_context": epoch_context.extent_of_resection,
        "imaging_event_id": imaging_record.imaging_procedure_id,
        "provenance": {
            "extraction_timestamp": datetime.now().isoformat(),
            "agent_version": "status_abstractor_v1.0",
            "source_view": "v_imaging_with_reports"
        }
    }
```

---

## CROSS-VALIDATION WITH PROGRESS NOTES

### Purpose
Validate/augment imaging-based tumor status with clinical assessments from progress notes.

### Implementation

```python
def cross_validate_with_progress_notes(imaging_assessment, progress_notes):
    """
    Cross-validate imaging findings with clinical progress notes
    """
    # Get progress notes from same visit
    visit_notes = [n for n in progress_notes
                   if n.note_date == imaging_assessment.assessment_date]

    if not visit_notes:
        return {
            "concordance_status": "no_clinical_note",
            "validation_performed": False
        }

    prompt = f"""
    You are validating tumor status assessments by comparing radiology findings
    with clinical progress notes.

    RADIOLOGY ASSESSMENT (from MRI report):
    - Tumor Status: {imaging_assessment.tumor_status}
    - Evidence: {imaging_assessment.status_evidence.report_excerpt}
    - Date: {imaging_assessment.assessment_date}

    CLINICAL PROGRESS NOTE (from same visit):
    {visit_notes[0].note_text[:2000]}  # First 2000 chars

    TASK:
    1. Identify any mentions of tumor status, disease progression, or treatment response
    2. Determine if clinical assessment agrees with radiology findings
    3. Flag any discordance

    OUTPUT FORMAT (JSON):
    {{
      "clinical_status_mentioned": true/false,
      "clinical_assessment": "What clinician says about disease status",
      "concordance": "concordant|discordant|ambiguous|not_mentioned",
      "discordance_details": "If discordant, explain the difference",
      "additional_context": "Any relevant clinical context not in imaging"
    }}
    """

    response = llm.invoke(prompt)
    validation_result = parse_json(response)

    return {
        **validation_result,
        "validation_date": datetime.now().isoformat(),
        "clinical_note_id": visit_notes[0].document_reference_id,
        "source_provenance": "progress_note_cross_validation"
    }
```

---

## OUTPUT TABLES

### tumor_epochs (Agent 1 Output)

```sql
CREATE TABLE fhir_prd_db.tumor_epochs (
    epoch_id VARCHAR,  -- Primary key
    patient_fhir_id VARCHAR,
    surgery_date DATE,
    surgical_event_id VARCHAR,  -- Links to v_procedures_tumor
    epoch_number INT,  -- 1, 2, 3...
    epoch_type VARCHAR,  -- initial_diagnosis, recurrence_surgery, progression_surgery

    -- AGENT-EXTRACTED FIELDS
    extent_of_resection VARCHAR,  -- GTR, STR, Partial, Biopsy, Unknown
    eor_confidence DOUBLE,
    eor_evidence_excerpt VARCHAR,
    eor_keywords_matched ARRAY<VARCHAR>,

    -- Source provenance
    imaging_report_id VARCHAR,
    imaging_date DATE,
    days_post_op INT,
    operative_report_id VARCHAR,

    -- Agent metadata
    extraction_timestamp TIMESTAMP,
    agent_version VARCHAR,
    agent_model VARCHAR,
    source_view VARCHAR
);
```

### tumor_status_assessments (Agent 2 Output)

```sql
CREATE TABLE fhir_prd_db.tumor_status_assessments (
    assessment_id VARCHAR,  -- Primary key
    patient_fhir_id VARCHAR,
    assessment_date DATE,
    epoch_number INT,  -- Links to tumor_epochs
    days_from_surgery INT,

    -- AGENT-EXTRACTED FIELDS
    tumor_status VARCHAR,  -- NED, Stable, Increased, Decreased, New_Malignancy, Uncertain
    status_confidence DOUBLE,
    status_evidence_excerpt VARCHAR,
    keywords_matched ARRAY<VARCHAR>,
    comparison_to_prior VARCHAR,

    -- Measurements (if available)
    current_size_cm VARCHAR,
    prior_size_cm VARCHAR,
    size_change_percent DOUBLE,

    -- Clinical context
    eor_context VARCHAR,  -- From epoch
    clinical_significance VARCHAR,
    interpretation_note VARCHAR,

    -- Cross-validation with progress notes
    clinical_note_concordance VARCHAR,  -- concordant, discordant, not_available
    discordance_details VARCHAR,

    -- Source provenance
    imaging_event_id VARCHAR,
    linked_visit_id VARCHAR,
    clinical_note_id VARCHAR,

    -- Agent metadata
    extraction_timestamp TIMESTAMP,
    agent_version VARCHAR,
    agent_model VARCHAR,
    source_view VARCHAR
);
```

---

## ORCHESTRATION WORKFLOW

### End-to-End Process

```python
class TumorStatusAbstractionWorkflow:
    """
    Orchestrates two-agent workflow for tumor status abstraction
    """

    def __init__(self):
        self.agent1 = SurgicalEventAbstractor()
        self.agent2 = TumorStatusAbstractor()
        self.validator = CrossValidator()

    def process_patient(self, patient_id):
        """
        Process complete tumor status timeline for a patient
        """
        # STEP 1: Extract surgical epochs (Agent 1)
        print(f"Processing surgical epochs for {patient_id}...")
        postop_imaging = query_athena("SELECT * FROM v_postop_imaging WHERE patient_fhir_id = ?", patient_id)

        epochs = []
        for record in postop_imaging:
            epoch = self.agent1.extract_extent_of_resection(record)
            epochs.append(epoch)

        # Store epochs
        insert_into_table("tumor_epochs", epochs)
        print(f"  → Identified {len(epochs)} surgical epochs")

        # STEP 2: Extract tumor status assessments (Agent 2)
        print(f"Processing surveillance imaging...")
        surveillance_imaging = query_athena("""
            SELECT i.*, e.epoch_number, e.extent_of_resection, e.surgery_date
            FROM v_imaging_with_reports i
            JOIN tumor_epochs e ON i.patient_fhir_id = e.patient_fhir_id
            WHERE i.patient_fhir_id = ?
              AND i.imaging_date >= e.surgery_date
            ORDER BY i.imaging_date
        """, patient_id)

        assessments = []
        for record in surveillance_imaging:
            epoch_context = get_epoch_context(record.epoch_number)
            assessment = self.agent2.extract_tumor_status(record, epoch_context)
            assessments.append(assessment)

        print(f"  → Extracted {len(assessments)} tumor status assessments")

        # STEP 3: Cross-validate with progress notes
        print(f"Cross-validating with clinical notes...")
        progress_notes = query_athena("SELECT * FROM v_progress_notes WHERE patient_fhir_id = ?", patient_id)

        for assessment in assessments:
            validation = self.validator.cross_validate_with_progress_notes(
                assessment, progress_notes
            )
            assessment['clinical_validation'] = validation

        # Store assessments
        insert_into_table("tumor_status_assessments", assessments)

        # STEP 4: Update unified timeline with status events
        self.update_unified_timeline(patient_id, epochs, assessments)

        return {
            "patient_id": patient_id,
            "epochs": len(epochs),
            "assessments": len(assessments),
            "status": "complete"
        }

    def update_unified_timeline(self, patient_id, epochs, assessments):
        """
        Add tumor status change events to v_unified_patient_timeline
        """
        # Identify status changes (where tumor_status differs from prior)
        status_changes = []
        for i, assessment in enumerate(assessments[1:], 1):
            prior = assessments[i-1]
            if assessment['tumor_status'] != prior['tumor_status']:
                status_changes.append({
                    'event_type': 'Tumor Status Change',
                    'event_category': f"{prior['tumor_status']} → {assessment['tumor_status']}",
                    'event_date': assessment['assessment_date'],
                    'event_metadata': assessment,
                    'provenance': 'agent_extracted'
                })

        # Insert into timeline
        for event in status_changes:
            insert_timeline_event(patient_id, event)
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1)
- [ ] Deploy V_AGENT_DATA_ACCESS_VIEWS.sql to Athena
- [ ] Create tumor_epochs and tumor_status_assessments tables in Athena
- [ ] Test sample radiology report extraction manually
- [ ] Validate view queries return expected data

### Phase 2: Agent Development (Week 2)
- [ ] Develop Agent 1 (Surgical Event Abstractor)
  - [ ] Define prompt template
  - [ ] Test on 10 sample post-op MRI reports
  - [ ] Refine classification logic based on results
  - [ ] Achieve >90% accuracy on validation set
- [ ] Develop Agent 2 (Tumor Status Abstractor)
  - [ ] Define prompt template with EOR context
  - [ ] Test on 20 sample surveillance MRI reports
  - [ ] Refine status classification logic
  - [ ] Achieve >85% accuracy on validation set

### Phase 3: Orchestration (Week 3)
- [ ] Build orchestration workflow
- [ ] Implement cross-validation logic
- [ ] Create batch processing pipeline
- [ ] Test on 5 complete patient timelines
- [ ] Manual review of all extractions for accuracy

### Phase 4: Integration (Week 4)
- [ ] Integrate with v_unified_patient_timeline
- [ ] Add status_change events to timeline
- [ ] Create visualization/dashboard
- [ ] Document agent behavior and edge cases
- [ ] Deploy to production

---

## VALIDATION STRATEGY

### Ground Truth Dataset
Create validation set of 50 patients with manual chart review:
- 10 with GTR + NED trajectory
- 10 with STR + stable residual disease
- 10 with progression events
- 10 with mixed/complex trajectories
- 10 with limited/ambiguous documentation

### Accuracy Metrics
- **Agent 1 (EOR):** Agreement with neurosurgeon chart review (target: >90%)
- **Agent 2 (Status):** Agreement with neuro-oncologist assessment (target: >85%)
- **Concordance Detection:** Sensitivity for identifying discordant imaging/clinical findings (target: >95%)

### Error Analysis
- Categorize extraction errors (ambiguous text, missing context, etc.)
- Iterate on prompts based on error patterns
- Flag low-confidence extractions for human review

---

## QUESTIONS FOR USER

1. **Agent Framework Preference:**
   - Do you have a preferred multi-agent framework (LangGraph, CrewAI, custom)?
   - What LLM should agents use (Claude 3.5 Sonnet, GPT-4, etc.)?

2. **Document Text Retrieval:**
   - How do we retrieve actual text from v_binary_files.binary_id?
   - Is there an S3 bucket with document content we can access?
   - Or should we focus only on embedded text in v_imaging.result_information?

3. **Table Creation:**
   - Can I create tumor_epochs and tumor_status_assessments tables in Athena now?
   - Or should these be external tables (e.g., in S3 as parquet)?

4. **Validation:**
   - Can you identify 5-10 sample patients for initial testing?
   - Do you have access to clinical experts for validation review?

---

## NEXT IMMEDIATE STEPS

1. **Deploy agent data access views** (V_AGENT_DATA_ACCESS_VIEWS.sql)
2. **Sample data testing** - Pull 5 example post-op MRI reports to test Agent 1 prompt
3. **Create output tables** - Define tumor_epochs and tumor_status_assessments schemas
4. **Agent 1 prototype** - Build first version of surgical event abstractor
5. **Test and iterate** - Validate on sample patients, refine prompts

**Should I proceed with Step 1 (deploying the views)?**
