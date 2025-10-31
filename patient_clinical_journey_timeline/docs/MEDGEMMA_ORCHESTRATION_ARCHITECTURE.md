# MedGemma Orchestration Architecture

**Purpose**: Comprehensive guide for Claude-orchestrated, context-aware MedGemma extraction of all free text notes and binary files in patient timeline abstraction

**Created**: 2025-10-30
**Last Updated**: 2025-10-30

---

## Core Principle

**ALL free text and binary documents should be abstracted by MedGemma using dynamically-generated, context-aware prompts from Claude.**

Claude acts as the **orchestrating agent** that:
1. Analyzes the patient timeline phase (molecular diagnosis → surgery → adjuvant therapy → surveillance)
2. Identifies which documents require extraction
3. Generates **specialized MedGemma prompts** based on:
   - WHO 2021 molecular diagnosis context
   - Timeline stage (pre-surgery, post-surgery, during treatment, surveillance)
   - Expected clinical information needs
4. Calls MedGemma iteratively
5. Integrates extractions back into timeline
6. Re-assesses for remaining gaps

---

## Two-Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLAUDE (Orchestrating Agent)                │
│                                                                   │
│  Responsibilities:                                                │
│  1. Load patient timeline from 6 Athena views                    │
│  2. Load WHO 2021 molecular classification                       │
│  3. Construct stepwise timeline (Stages 0-6)                     │
│  4. Identify extraction gaps based on timeline phase             │
│  5. Generate context-aware MedGemma prompts                      │
│  6. Call MedGemma for each document                              │
│  7. Integrate extractions into timeline                          │
│  8. Validate against WHO 2021 protocols                          │
│  9. Generate final JSON artifact                                 │
└──────────────────┬────────────────────────────────────────────────┘
                   │
                   │ Sends document + context-aware prompt
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MEDGEMMA (Extraction Agent)                 │
│                                                                   │
│  Responsibilities:                                                │
│  1. Receive binary document + specialized prompt                 │
│  2. Extract structured data (measurements, dates, findings)      │
│  3. Return JSON-formatted extraction result                      │
│  4. NO decision-making about clinical relevance                  │
└───────────────────────────────────────────────────────────────────┘
```

---

## Document Types Requiring MedGemma Extraction

### 1. Pathology Reports (v_pathology_diagnostics)

**Source**: `extraction_priority` field (1-5 tier system)

**Extraction Triggers**:
- Priority 1-2 documents (Final surgical pathology, surgical pathology)
- Documents with `extraction_priority` field populated

**Target Information**:
- Extent of resection (EOR) - GTR, STR, biopsy
- Tumor histology details
- Molecular marker confirmation
- Tumor grade
- Margins assessment

---

### 2. Surgical/Operative Notes (v_procedures_tumor)

**Source**: Procedure records where `is_tumor_surgery = true`

**Extraction Triggers**:
- ALL surgical procedures (missing EOR is a CRITICAL gap)

**Target Information**:
- **Extent of resection** (CRITICAL for prognosis)
- Surgical approach (craniotomy, endoscopic, stereotactic)
- Complications
- Estimated blood loss
- Duration of surgery
- Surgeon's assessment of resectability

---

### 3. Radiation Treatment Summaries (v_radiation_episode_enrichment)

**Source**: `extraction_priority` field for radiation documents

**Extraction Triggers**:
- Missing `total_dose_cgy`
- Priority 1-2 radiation treatment reports

**Target Information**:
- **Total dose in cGy** (CRITICAL for protocol validation)
- Radiation fields (focal, craniospinal, boost)
- Fractionation schedule (e.g., 1.8 Gy x 30 fractions)
- Start and end dates
- Treatment interruptions
- Concurrent medications (e.g., temozolomide)

---

### 4. Imaging Reports (v_imaging)

**Source**: `report_conclusion` field

**Extraction Triggers**:
- `report_conclusion` is NULL, empty, OR <50 characters (vague summary)
- ALL imaging reports benefit from full extraction

**Target Information**:
- **Tumor measurements** (bidimensional: AP x ML x SI)
- Lesion locations
- Enhancement patterns
- Comparison to prior studies
- RANO response assessment
- New lesions detection
- Perilesional edema
- Mass effect
- Corticosteroid use implications

---

### 5. Chemotherapy Notes (v_chemo_treatment_episodes)

**Source**: Episode records

**Extraction Triggers**:
- Missing drug names
- Vague episode descriptions
- Need for dosing, cycles, toxicities

**Target Information**:
- Specific drug names and doses
- Cycle numbers (e.g., "Cycle 3 of 6")
- Dose modifications and reasons
- Toxicities (grade, attribution)
- Treatment delays
- Supportive care medications

---

### 6. Clinical Notes (Future Integration)

**Source**: Encounter notes, progress notes

**Extraction Triggers**:
- Within critical timeline windows (post-surgery, during treatment)

**Target Information**:
- Performance status (Karnofsky, Lansky)
- Symptom progression
- Clinical exam findings
- Treatment response assessment
- Quality of life
- Family discussions about prognosis

---

## Claude's Context-Aware Prompt Generation

### Prompt Generation Framework

For **each document**, Claude generates a specialized prompt that includes:

1. **Patient Context**:
   - WHO 2021 molecular diagnosis
   - Current timeline phase
   - Days from surgery
   - Days from radiation (if applicable)

2. **Document Context**:
   - Document type
   - Expected information based on timeline phase
   - Known gaps from structured data

3. **Extraction Instructions**:
   - Specific fields to extract
   - Expected value formats
   - Clinical relevance guidance

4. **Output Format**:
   - JSON schema for structured extraction

---

## Example: Context-Aware Prompt for Post-Surgical Pathology Report

### Timeline Context (Input to Claude)

```json
{
  "patient_id": "e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3",
  "who_2021_diagnosis": "Pineoblastoma, CNS WHO grade 4",
  "molecular_subtype": "MYC/FOXR2-activated",
  "timeline_phase": "post_surgery",
  "surgery_date": "2023-03-15",
  "document_type": "Final surgical pathology report",
  "extraction_priority": 1,
  "current_gaps": ["extent_of_resection", "tumor_grade_confirmation"],
  "expected_molecular_markers": ["MYCN amplification", "TP53 mutation", "KRAS mutation"]
}
```

### Claude-Generated MedGemma Prompt

```
CONTEXT:
Patient with Pineoblastoma, CNS WHO grade 4 (MYC/FOXR2-activated molecular subtype).
This is a FINAL SURGICAL PATHOLOGY REPORT (Priority 1 - highest value for extraction).
Surgery date: 2023-03-15 (posterior fossa craniotomy).

CLINICAL SIGNIFICANCE:
- Pineoblastoma is a high-risk embryonal tumor requiring aggressive multimodal therapy
- MYCN amplification status CRITICAL for risk stratification
- Extent of resection impacts survival (GTR > STR > biopsy)
- This document should contain DEFINITIVE molecular findings

EXTRACTION TASK:
Extract the following structured information from this surgical pathology report:

1. TUMOR CHARACTERISTICS:
   - Tumor type/histology (confirm "Pineoblastoma")
   - WHO grade (confirm grade 4)
   - Mitotic activity (mitoses per 10 HPF)
   - Necrosis (present/absent)
   - Vascular proliferation (present/absent)

2. MOLECULAR FINDINGS (HIGH PRIORITY):
   - MYCN amplification status (PRESENT/ABSENT/NOT TESTED)
   - TP53 mutation status (if reported)
   - KRAS mutation status (if reported)
   - Any other molecular markers mentioned

3. EXTENT OF RESECTION (CRITICAL):
   - Surgical margins (negative/positive/close)
   - Estimated percent resection if mentioned
   - Residual tumor assessment
   - Categorize as: GTR (gross total resection), STR (subtotal resection), or Biopsy

4. STAGING INFORMATION:
   - CSF involvement mentioned? (yes/no)
   - Leptomeningeal spread mentioned? (yes/no)

OUTPUT FORMAT (JSON):
{
  "tumor_histology": "string",
  "who_grade": "integer (1-4)",
  "mitoses_per_10_hpf": "integer or null",
  "necrosis_present": "boolean",
  "molecular_findings": {
    "mycn_amplification": "PRESENT/ABSENT/NOT_TESTED",
    "tp53_mutation": "string or null",
    "kras_mutation": "string or null",
    "other_markers": ["list of strings"]
  },
  "extent_of_resection": "GTR/STR/Biopsy",
  "surgical_margins": "negative/positive/close/not_reported",
  "csf_staging": {
    "csf_involvement": "yes/no/not_mentioned",
    "leptomeningeal_spread": "yes/no/not_mentioned"
  },
  "extraction_confidence": "HIGH/MEDIUM/LOW",
  "extraction_notes": "Any ambiguities or missing expected information"
}

IMPORTANT:
- If a field is not mentioned in the report, use null or "not_reported"
- If molecular testing was not performed, explicitly state "NOT_TESTED"
- Extent of resection is CRITICAL - extract any language about completeness of resection
```

---

## Example: Context-Aware Prompt for Post-Radiation MRI Report

### Timeline Context (Input to Claude)

```json
{
  "patient_id": "e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3",
  "who_2021_diagnosis": "Pineoblastoma, CNS WHO grade 4",
  "timeline_phase": "post_radiation_surveillance",
  "radiation_end_date": "2023-07-01",
  "imaging_date": "2023-08-15",
  "days_from_radiation_end": 45,
  "is_pseudoprogression_window": true,
  "document_type": "MRI Brain and Spine with contrast",
  "report_conclusion": "Increased enhancement in tumor bed",
  "current_gaps": ["tumor_measurements", "rano_assessment", "pseudoprogression_features"]
}
```

### Claude-Generated MedGemma Prompt

```
CONTEXT:
Patient with Pineoblastoma, CNS WHO grade 4, post-radiation surveillance.
Radiation completed: 2023-07-01 (54 Gy craniospinal + posterior fossa boost).
Current imaging: 2023-08-15 (45 days post-radiation).

CRITICAL WINDOW:
This imaging is within the PSEUDOPROGRESSION WINDOW (21-90 days post-radiation).
Increased enhancement could be:
1. True tumor progression (requires treatment escalation)
2. Treatment-related inflammation/pseudoprogression (benign, self-limiting)

CLINICAL DECISION POINT:
Detailed measurements and imaging characteristics CRITICAL to avoid:
- Over-treatment (if pseudoprogression)
- Under-treatment (if true progression)

EXTRACTION TASK:
Extract the following information from this MRI report:

1. LESION MEASUREMENTS (CRITICAL):
   For EACH enhancing lesion:
   - Location (anatomic region)
   - Dimensions in cm (AP x ML x SI)
   - Enhancement pattern (solid, ring-like, heterogeneous)
   - Comparison to PRIOR study (include prior measurements if mentioned)

2. PSEUDOPROGRESSION FEATURES (HIGH PRIORITY):
   - Diffusion characteristics (ADC values, restricted diffusion)
   - Perfusion patterns (rCBV if mentioned)
   - Pattern of enhancement (solid vs feathery/flame-like)
   - Surrounding FLAIR signal changes

3. RANO RESPONSE ASSESSMENT:
   - New lesions? (yes/no)
   - Progression of existing lesions? (yes/no with percent change)
   - Overall RANO category: CR/PR/SD/PD (if mentioned)

4. ADDITIONAL FINDINGS:
   - CSF dissemination/leptomeningeal enhancement
   - Hydrocephalus
   - Mass effect
   - Hemorrhage
   - Corticosteroid use mentioned?

5. RADIOLOGIST IMPRESSION:
   - Verbatim conclusion
   - Differential diagnosis if provided
   - Recommendation for follow-up

OUTPUT FORMAT (JSON):
{
  "imaging_date": "2023-08-15",
  "lesions": [
    {
      "location": "Pineal region/posterior fossa",
      "current_dimensions_cm": {"ap": float, "ml": float, "si": float},
      "prior_dimensions_cm": {"ap": float, "ml": float, "si": float} or null,
      "percent_change": float or null,
      "enhancement_pattern": "string"
    }
  ],
  "pseudoprogression_features": {
    "diffusion_restricted": "yes/no/not_reported",
    "adc_values": "string or null",
    "perfusion_pattern": "string or null",
    "flair_signal": "increased/stable/decreased/not_reported"
  },
  "rano_assessment": {
    "new_lesions": "yes/no",
    "lesion_progression": "yes/no",
    "rano_category": "CR/PR/SD/PD/INDETERMINATE",
    "assessment_rationale": "string"
  },
  "csf_spine_findings": {
    "leptomeningeal_enhancement": "yes/no/not_reported",
    "spinal_lesions": "yes/no/not_reported"
  },
  "radiologist_impression": "verbatim string",
  "differential_diagnosis": ["list of strings"],
  "pseudoprogression_likelihood": "HIGH/MODERATE/LOW/INDETERMINATE",
  "extraction_confidence": "HIGH/MEDIUM/LOW"
}

IMPORTANT:
- Bidimensional measurements (AP x ML OR two perpendicular diameters) are CRITICAL
- If prior measurements mentioned, extract them for comparison
- Pseudoprogression features help distinguish treatment effect from progression
```

---

## Example: Context-Aware Prompt for Operative Note (EOR Extraction)

### Timeline Context (Input to Claude)

```json
{
  "patient_id": "e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3",
  "who_2021_diagnosis": "Pineoblastoma, CNS WHO grade 4",
  "timeline_phase": "initial_surgery",
  "surgery_date": "2023-03-15",
  "surgery_type": "craniotomy",
  "document_type": "Operative note",
  "current_gaps": ["extent_of_resection"],
  "clinical_significance": "EOR is prognostic factor for pineoblastoma"
}
```

### Claude-Generated MedGemma Prompt

```
CONTEXT:
Patient with Pineoblastoma, CNS WHO grade 4.
Surgery: Posterior fossa craniotomy, 2023-03-15.

CLINICAL SIGNIFICANCE:
- Pineoblastoma is an embryonal tumor arising in pineal region
- Extent of resection is a KEY PROGNOSTIC FACTOR
- GTR (gross total resection) associated with better survival vs STR/biopsy
- Location near deep venous structures makes complete resection challenging

EXTRACTION TASK:
Extract extent of resection (EOR) assessment from this operative note.

LOOK FOR:
1. SURGEON'S ASSESSMENT OF RESECTION:
   - Explicit statements like "gross total resection achieved"
   - Qualitative descriptions: "near-total", "subtotal", "partial", "biopsy only"
   - Estimated percent resection (e.g., "90% resection")
   - Residual tumor described? (yes/no, location if yes)

2. INTRAOPERATIVE FINDINGS:
   - Tumor size/dimensions
   - Tumor consistency (soft, firm, vascular)
   - Adherence to critical structures
   - Reasons for incomplete resection (if applicable)

3. SURGICAL COMPLICATIONS:
   - Blood loss
   - Venous injury
   - Neurological concerns

OUTPUT FORMAT (JSON):
{
  "extent_of_resection": "GTR/STR/Biopsy",
  "estimated_percent_resection": integer (0-100) or null,
  "surgeon_verbatim_assessment": "exact quote from note",
  "residual_tumor": {
    "present": "yes/no/uncertain",
    "location": "string or null",
    "reason_for_residual": "string or null"
  },
  "intraoperative_findings": {
    "tumor_size_cm": "string or null",
    "tumor_consistency": "string",
    "vascular_involvement": "yes/no/not_mentioned"
  },
  "complications": ["list of strings"],
  "extraction_confidence": "HIGH/MEDIUM/LOW",
  "extraction_rationale": "How EOR was determined from note"
}

CATEGORIZATION RULES:
- GTR = "gross total resection", "complete resection", ">95% resection"
- STR = "subtotal resection", "near-total", "90-95% resection", "small residual"
- Biopsy = "biopsy only", "<50% resection", "debulking not attempted"

IMPORTANT:
- Extract surgeon's exact language about completeness
- If percent resection mentioned, capture it
- EOR assessment is CRITICAL for prognosis - high confidence required
```

---

## Iterative Extraction Workflow (Phase 4)

### Current Status: PLACEHOLDER

When implemented, Phase 4 will execute this workflow:

```python
def _phase4_extract_from_binaries(self):
    """
    Phase 4: Iterative MedGemma extraction with Claude-generated prompts

    This is the TWO-AGENT orchestration:
    - Claude (this script) generates context-aware prompts
    - MedGemma performs extraction
    - Claude integrates results and re-assesses
    """

    # Sort gaps by priority (HIGHEST → HIGH → MEDIUM)
    prioritized_gaps = sorted(
        self.extraction_gaps,
        key=lambda x: {'HIGHEST': 0, 'HIGH': 1, 'MEDIUM': 2}.get(x['priority'], 3)
    )

    for gap in prioritized_gaps:
        # STEP 1: Generate context-aware prompt (Claude)
        medgemma_prompt = self._generate_medgemma_prompt(gap)

        # STEP 2: Fetch binary document
        document_content = self._fetch_binary_document(gap['medgemma_target'])

        # STEP 3: Call MedGemma
        extraction_result = self._call_medgemma(
            document=document_content,
            prompt=medgemma_prompt
        )

        # STEP 4: Validate extraction
        if extraction_result['extraction_confidence'] in ['HIGH', 'MEDIUM']:
            # STEP 5: Integrate into timeline
            self._integrate_extraction_into_timeline(gap, extraction_result)

            # STEP 6: Mark gap as resolved
            gap['status'] = 'RESOLVED'
            gap['extraction_result'] = extraction_result
        else:
            # Low confidence - flag for manual review
            gap['status'] = 'REQUIRES_MANUAL_REVIEW'
            gap['extraction_result'] = extraction_result

    # STEP 7: Re-assess for new gaps after integration
    self._reassess_gaps_post_extraction()

    print(f"  ✅ Extracted from {len([g for g in self.extraction_gaps if g.get('status') == 'RESOLVED'])} documents")
    print(f"  ⚠️  {len([g for g in self.extraction_gaps if g.get('status') == 'REQUIRES_MANUAL_REVIEW'])} require manual review")
```

### Key Methods

#### `_generate_medgemma_prompt(gap)`

```python
def _generate_medgemma_prompt(self, gap: Dict) -> str:
    """
    Generate context-aware MedGemma prompt based on:
    - WHO 2021 diagnosis
    - Timeline phase
    - Gap type
    - Clinical significance
    """

    prompt_templates = {
        'vague_imaging_conclusion': self._imaging_prompt_template,
        'missing_eor': self._operative_note_prompt_template,
        'missing_radiation_dose': self._radiation_summary_prompt_template,
        'high_priority_pathology': self._pathology_prompt_template
    }

    template_func = prompt_templates.get(gap['gap_type'])
    if template_func:
        return template_func(gap, self.who_2021_classification, self.timeline_events)
    else:
        return self._generic_prompt_template(gap)
```

#### `_call_medgemma(document, prompt)`

```python
def _call_medgemma(self, document: bytes, prompt: str) -> Dict:
    """
    Call MedGemma API with document + context-aware prompt

    Returns:
        Dict with extraction result in standardized JSON format
    """
    # PLACEHOLDER - actual MedGemma integration needed
    # This would call MedGemma API/service

    response = medgemma_api.extract(
        document=document,
        prompt=prompt,
        output_format='json'
    )

    return response
```

---

## Prompt Template Library

Claude maintains a library of specialized prompt templates:

### 1. Imaging Report Prompts

- **Baseline imaging**: Focus on tumor measurements, location, enhancement
- **Post-surgical imaging**: Focus on extent of resection, residual tumor
- **Post-radiation imaging (pseudoprogression window)**: Focus on pseudoprogression features
- **Surveillance imaging**: Focus on RANO response, new lesions
- **Progression imaging**: Focus on detailed measurements, new lesions, SPD calculation

### 2. Pathology Report Prompts

- **Final surgical pathology**: Focus on histology, grade, molecular markers, EOR
- **Biopsy pathology**: Focus on diagnostic adequacy, preliminary findings
- **Molecular pathology supplements**: Focus on specific marker results (MYCN, TP53, etc.)

### 3. Operative Note Prompts

- **Initial tumor resection**: Focus on EOR, complications
- **Re-resection**: Focus on extent of re-resection, comparison to prior
- **CSF diversion (VP shunt, ETV)**: Focus on hydrocephalus management

### 4. Radiation Treatment Prompts

- **Treatment planning**: Focus on target volumes, dose prescription
- **End-of-treatment summary**: Focus on total dose, fractionation, interruptions
- **On-treatment visits**: Focus on acute toxicities

### 5. Chemotherapy Prompts

- **Cycle documentation**: Focus on drugs, doses, toxicities
- **Response assessment**: Focus on clinical response, imaging correlation
- **Dose modification rationale**: Focus on toxicity-driven changes

---

## Integration with Timeline Artifact

### Before MedGemma

Timeline events have only structured data from Athena views:

```json
{
  "event_type": "surgery",
  "event_date": "2023-03-15",
  "surgery_type": "craniotomy",
  "description": "CRNEC EXC BRAIN TUMOR INFRATENTORIAL/POST FOSSA"
  // NO extent_of_resection
}
```

### After MedGemma

Timeline events are enriched with extracted data:

```json
{
  "event_type": "surgery",
  "event_date": "2023-03-15",
  "surgery_type": "craniotomy",
  "description": "CRNEC EXC BRAIN TUMOR INFRATENTORIAL/POST FOSSA",

  // ADDED BY MEDGEMMA
  "medgemma_extraction": {
    "extraction_id": "ext_2025_001",
    "extraction_timestamp": "2025-10-30T23:00:00Z",
    "extraction_confidence": "HIGH",
    "extent_of_resection": "STR",  // CRITICAL GAP FILLED
    "estimated_percent_resection": 90,
    "surgeon_assessment": "Near-total resection achieved with small residual along deep venous structures",
    "residual_tumor_location": "Adjacent to internal cerebral veins",
    "intraoperative_findings": {
      "tumor_size_cm": "3.5 x 3.2 x 3.0",
      "tumor_consistency": "Soft, friable, moderately vascular"
    },
    "source_document": "Operative Note 2023-03-15"
  }
}
```

---

## Summary

### Key Points

1. **ALL free text and binary files** are candidates for MedGemma extraction
2. **Claude orchestrates** by generating context-aware prompts based on patient timeline phase
3. **MedGemma extracts** structured data using these specialized prompts
4. **Prompts are dynamic** - tailored to WHO 2021 diagnosis, timeline stage, and clinical information needs
5. **Extraction is iterative** - gaps are re-assessed after each extraction batch
6. **Integration is seamless** - extracted data populates timeline events as `medgemma_extraction` objects

### Benefits

- **Context-aware**: Prompts reflect clinical significance based on molecular diagnosis
- **Timeline-aware**: Extraction priorities change based on treatment phase
- **Comprehensive**: No valuable clinical information is left unextracted
- **Structured**: All extractions follow standardized JSON schemas
- **Auditable**: Extraction confidence and rationale are captured
- **Scalable**: Works for any WHO 2021 molecular diagnosis, any timeline phase

---

## References

- **Two-agent architecture**: patient_timeline_abstraction_V1.py (`_phase4_extract_from_binaries_placeholder()`)
- **Gap identification**: patient_timeline_abstraction_V1.py (`_phase3_identify_extraction_gaps()`)
- **Stepwise timeline**: STEPWISE_TIMELINE_CONSTRUCTION.md
- **Imaging extraction**: IMAGING_REPORT_EXTRACTION_STRATEGY.md
- **Document prioritization**: DOCUMENT_PRIORITIZATION_STRATEGY.md

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Define the Claude-orchestrated, MedGemma-powered extraction architecture for patient timeline abstraction
