# Human Abstraction Examples - Training Data for MedGemma

**Source**: Human-abstracted data from RADIANT PCA clinical abstraction team (`/Users/resnick/Downloads/example extraction.csv`)
**Purpose**: Provide gold-standard examples for MedGemma prompt engineering and validation

---

## ⚠️ IMPORTANT: Use of This Data

**This is VALIDATED CLINICAL DATA - the target view for abstraction**

**How to use this data:**
1. ✅ **For examples**: Use to create training examples for MedGemma prompts
2. ✅ **For validation**: Compare MedGemma extraction results against these gold-standard values AFTER extraction
3. ✅ **For prompt engineering**: Understand expected output format and field values
4. ❌ **NOT as source data**: Do NOT use this as input to the extraction pipeline
5. ❌ **NOT for pre-population**: Do NOT use to pre-fill extraction results

**Workflow:**
```
Binary Documents (PDF/XML)
  → MedGemma Extraction
    → Extracted Results
      → VALIDATE against Human Abstraction Examples ✅
```

**NOT:**
```
Human Abstraction Examples → Copy to Results ❌
```

---

## Table of Contents
1. [Surgery Examples](#surgery-examples)
2. [Chemotherapy Examples](#chemotherapy-examples)
3. [Radiation Examples](#radiation-examples)
4. [Combined Treatment Examples](#combined-treatment-examples)
5. [Edge Cases](#edge-cases)

---

## Surgery Examples

### Example S1: Biopsy Only (Initial CNS Tumor Surgery)
**Patient**: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
**Timeline Date**: Day 4545

```csv
surgery: Yes
age_at_surgery: 4545
extent_of_tumor_resection: Biopsy only
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Key Learning Points:**
- **Extent of Resection (EOR)**: "Biopsy only" = no resection performed
- **Specimen origin**: Initial CNS Tumor Surgery (primary diagnostic procedure)
- Maps to MedGemma category: "BIOPSY"
- This is definitive treatment followed by chemoradiation (see combined examples)

**MedGemma Expected Output:**
```json
{
  "surgery_performed": true,
  "surgery_date": "<convert age 4545 days to date>",
  "extent_of_resection": "BIOPSY",
  "percent_resection": 0,
  "surgeon_assessment": "Biopsy only",
  "residual_tumor": "yes",
  "specimen_collection_origin": "initial_cns_tumor_surgery",
  "extraction_confidence": "HIGH"
}
```

---

### Example S2: Gross/Near Total Resection
**Patient**: e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3
**Timeline Date**: Day 6421

```csv
surgery: Yes
age_at_surgery: 6421
extent_of_tumor_resection: Gross/Near total resection
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Key Learning Points:**
- **EOR**: "Gross/Near total resection" = GTR or NTR (>90% removed)
- **Human abstraction combines GTR and NTR** - MedGemma should distinguish if possible
- Standard for medulloblastoma (this patient)
- Followed by craniospinal radiation + temozolomide

**MedGemma Expected Output:**
```json
{
  "surgery_performed": true,
  "surgery_date": "<date>",
  "extent_of_resection": "GTR",
  "percent_resection": 95,
  "surgeon_assessment": "Gross total resection achieved",
  "residual_tumor": "no",
  "specimen_collection_origin": "initial_cns_tumor_surgery",
  "extraction_confidence": "HIGH"
}
```

**Alternative if NTR:**
```json
{
  "extent_of_resection": "NTR",
  "percent_resection": 92,
  "surgeon_assessment": "Near-total resection, minimal residual",
  "residual_tumor": "yes"
}
```

---

### Example S3: Partial Resection
**Patient**: eXdEVvOs091o4-RCug2.5hA3
**Timeline Date**: Day 4851

```csv
surgery: Yes
age_at_surgery: 4851
extent_of_tumor_resection: Partial resection
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Key Learning Points:**
- **EOR**: "Partial resection" = STR (Subtotal Resection, <90%)
- Maps to MedGemma category: "STR"
- Common for infiltrative tumors (e.g., diffuse gliomas)
- Typically followed by adjuvant therapy

**MedGemma Expected Output:**
```json
{
  "surgery_performed": true,
  "surgery_date": "<date>",
  "extent_of_resection": "STR",
  "percent_resection": 75,
  "surgeon_assessment": "Partial resection performed",
  "residual_tumor": "yes",
  "specimen_collection_origin": "initial_cns_tumor_surgery",
  "extraction_confidence": "MEDIUM"
}
```

---

### Example S4: Multiple Surgeries - Biopsy Then Resection
**Patient**: eUFS4hKO-grXh72WvK-5l0TFbD0sV2SMysYY5JpxOR-A3

**Surgery 1 (Day 5844):**
```csv
surgery: Yes
age_at_surgery: 5844
extent_of_tumor_resection: Biopsy only
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Surgery 2 (Day 5847 - 3 days later):**
```csv
surgery: Yes
age_at_surgery: 5847
extent_of_tumor_resection: Gross/Near total resection
specimen_collection_origin: Repeat resection
```

**Key Learning Points:**
- **Two-stage surgical approach**: Diagnostic biopsy → Definitive resection
- **Specimen origin changes**: "Initial CNS Tumor Surgery" → "Repeat resection"
- 3-day interval suggests: Biopsy → Frozen section/molecular testing → Resection
- **Most recent surgery determines current EOR status**

**MedGemma Expected Output for Surgery 1:**
```json
{
  "surgery_performed": true,
  "surgery_date": "<date day 5844>",
  "extent_of_resection": "BIOPSY",
  "specimen_collection_origin": "initial_cns_tumor_surgery",
  "extraction_confidence": "HIGH"
}
```

**MedGemma Expected Output for Surgery 2:**
```json
{
  "surgery_performed": true,
  "surgery_date": "<date day 5847>",
  "extent_of_resection": "GTR",
  "specimen_collection_origin": "repeat_resection",
  "temporal_relationship": "definitive_resection_following_biopsy",
  "prior_surgery_date": "<date day 5844>",
  "extraction_confidence": "HIGH"
}
```

---

### Example S5: Two Separate Surgical Procedures (Different Lesions)
**Patient**: ekrJf9m27ER1umcVah.rRqC.9hDY9ch91PfbuGjUHko03

**Surgery 1 (Day 7117):**
```csv
surgery: Yes
age_at_surgery: 7117
extent_of_tumor_resection: Partial resection
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Surgery 2 (Day 7143 - 26 days later):**
```csv
surgery: Yes
age_at_surgery: 7143
extent_of_resection: Biopsy only
specimen_collection_origin: Initial CNS Tumor Surgery
```

**Key Learning Points:**
- **Both marked as "Initial CNS Tumor Surgery"** - suggests different lesions or sites
- 26-day interval suggests separate procedures (not immediate re-operation)
- First: Partial resection (likely primary lesion)
- Second: Biopsy only (likely additional/metastatic lesion)
- Both followed by same radiation course (day 7174-7224)

**MedGemma Expected Output:**
```json
{
  "surgical_procedures": [
    {
      "surgery_date": "<date day 7117>",
      "extent_of_resection": "STR",
      "percent_resection": 70,
      "specimen_collection_origin": "initial_cns_tumor_surgery",
      "lesion_number": 1
    },
    {
      "surgery_date": "<date day 7143>",
      "extent_of_resection": "BIOPSY",
      "specimen_collection_origin": "initial_cns_tumor_surgery",
      "lesion_number": 2,
      "extraction_note": "Separate biopsy procedure, likely additional lesion"
    }
  ],
  "extraction_confidence": "HIGH"
}
```

---

### Summary: Extent of Resection Mapping

| Human Abstraction Term | MedGemma Category | Percent Resection | Residual Tumor |
|------------------------|-------------------|-------------------|----------------|
| Biopsy only | BIOPSY | 0% | Yes |
| Partial resection | STR | <90% | Yes |
| Gross/Near total resection | GTR or NTR | ≥90% | GTR: No, NTR: Minimal |
| (Not specified) | UNCLEAR | N/A | Unclear |

**Key Distinction:**
- **GTR (Gross Total Resection)**: >95%, no visible residual
- **NTR (Near Total Resection)**: 90-95%, minimal residual
- Human abstractors combine these as "Gross/Near total resection"
- MedGemma should distinguish if operative note provides details

---

### Specimen Collection Origin Values

| Value | Meaning | MedGemma Interpretation |
|-------|---------|-------------------------|
| Initial CNS Tumor Surgery | First surgery for this tumor | primary_cns_tumor_surgery |
| Repeat resection | Re-operation on same tumor | repeat_resection |
| (Not in data) External Operative Note | Surgery at outside institution | external_surgery |
| (Not in data) Autopsy | Post-mortem tissue | autopsy |

---

## Chemotherapy Examples

### Example 1: Temozolomide + Nivolumab (Concurrent with Radiation)
**Patient**: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
**Timeline Date**: Day 4545

```csv
chemotherapy: Yes
chemotherapy_type: Treatment follows other standard of care not associated with a current or past protocol
protocol_name: Not Applicable
chemotherapy_agents: temozolomide;nivolumab
age_at_chemo_start: 4581
age_at_chemo_stop: 4735
```

**Key Learning Points:**
- Multiple agents separated by semicolon: `temozolomide;nivolumab`
- Duration: 154 days (4735 - 4581)
- No formal protocol, but standard of care
- Concurrent with proton radiation (same patient, day 4545)

**MedGemma Expected Output:**
```json
{
  "chemotherapy_agents": ["temozolomide", "nivolumab"],
  "protocol_name": null,
  "treatment_type": "standard_of_care",
  "date_at_chemo_start": "<convert age 4581 days to date>",
  "date_at_chemo_stop": "<convert age 4735 days to date>",
  "concurrent_with_radiation": true
}
```

---

### Example 2: Single Agent - Etoposide
**Patient**: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
**Timeline Date**: Day 4754

```csv
chemotherapy: Yes
chemotherapy_type: Treatment follows other standard of care not associated with a current or past protocol
protocol_name: Not Applicable
chemotherapy_agents: etoposide
age_at_chemo_start: 4754
age_at_chemo_stop: Not Available
```

**Key Learning Points:**
- Single agent (no semicolon separator)
- Stop date unavailable (ongoing treatment at time of abstraction)
- Use "Not Available" vs null

**MedGemma Expected Output:**
```json
{
  "chemotherapy_agents": ["etoposide"],
  "protocol_name": null,
  "treatment_type": "standard_of_care",
  "date_at_chemo_start": "<date>",
  "date_at_chemo_stop": null,
  "extraction_note": "Stop date not available in document"
}
```

---

### Example 3: Protocol-Based - ACNS0423
**Patient**: eXdEVvOs091o4-RCug2.5hA3
**Timeline Date**: Day 4851

```csv
chemotherapy: Yes
chemotherapy_type: Treatment follows a protocol but subject is not enrolled
protocol_name: ACNS0423
chemotherapy_agents: temozolomide;lomustine
age_at_chemo_start: 4878
age_at_chemo_stop: 5298
```

**Key Learning Points:**
- Formal protocol: ACNS0423 (Children's Oncology Group protocol)
- Two-agent regimen: temozolomide + lomustine
- Long duration: 420 days (5298 - 4878)
- Patient follows protocol but not formally enrolled

**MedGemma Expected Output:**
```json
{
  "chemotherapy_agents": ["temozolomide", "lomustine"],
  "protocol_name": "ACNS0423",
  "treatment_type": "protocol_based_not_enrolled",
  "date_at_chemo_start": "<date>",
  "date_at_chemo_stop": "<date>",
  "duration_days": 420,
  "concurrent_with_radiation": true
}
```

---

### Example 4: Treatment Modification Due to Toxicity
**Patient**: eXdEVvOs091o4-RCug2.5hA3
**Timeline Date**: Day 5305

```csv
treatment_status: Modified Treatment
reason_for_treatment_change: Toxicities
chemotherapy: Yes
chemotherapy_agents: procarbazine
age_at_chemo_start: 5305
age_at_chemo_stop: 5399
```

**Key Learning Points:**
- Treatment modified due to toxicities (not disease progression)
- Single-agent salvage: procarbazine
- Duration: 94 days
- Important to capture reason for change

**MedGemma Expected Output:**
```json
{
  "chemotherapy_agents": ["procarbazine"],
  "protocol_name": null,
  "treatment_status": "modified",
  "reason_for_change": "toxicities",
  "date_at_chemo_start": "<date>",
  "date_at_chemo_stop": "<date>"
}
```

---

### Example 5: Agents Not Available
**Patient**: eiZ8gIQ.xVzYybDaR2sW5E0z9yI5BQjDeWulBFer5T4g3
**Timeline Date**: Day 3473

```csv
chemotherapy: Yes
chemotherapy_type: Treatment follows a protocol but subject is not enrolled
protocol_name: Not Available
chemotherapy_agents: Not Available
age_at_chemo_start: 3473
age_at_chemo_stop: 3565
```

**Key Learning Points:**
- Dates available but agents unknown (incomplete documentation)
- Protocol mentioned but not identified
- Use "Not Available" when information exists but is not accessible

**MedGemma Expected Output:**
```json
{
  "chemotherapy_agents": null,
  "protocol_name": null,
  "date_at_chemo_start": "<date>",
  "date_at_chemo_stop": "<date>",
  "extraction_confidence": "LOW",
  "extraction_note": "Agent names not available in document"
}
```

---

## Radiation Examples

### Example 6: Focal Proton Radiation
**Patient**: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
**Timeline Date**: Day 4545

```csv
radiation: Yes
radiation_type: Protons
radiation_site: Focal/Tumor bed
total_radiation_dose: Not Applicable
total_radiation_dose_focal: 5940
total_radiation_dose_focal_unit: cGy
age_at_radiation_start: 4581
age_at_radiation_stop: 4629
```

**Key Learning Points:**
- **Focal-only radiation**: `total_radiation_dose` = "Not Applicable", `total_radiation_dose_focal` = 5940 cGy
- Proton therapy
- Duration: 48 days (typical ~6-7 weeks)
- Dose: 5940 cGy = 59.4 Gy (standard for high-grade glioma)

**MedGemma Expected Output:**
```json
{
  "radiation_type": "focal",
  "radiation_modality": "protons",
  "radiation_site": "focal_tumor_bed",
  "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
  "radiation_focal_or_boost_dose": 5940,
  "completed_radiation_focal_or_boost_dose_unit": "cGy",
  "total_dose_cgy": 5940,
  "date_at_radiation_start": "<date>",
  "date_at_radiation_stop": "<date>",
  "duration_days": 48,
  "fractions": 33,
  "dose_per_fraction_cgy": 180
}
```

---

### Example 7: CRITICAL - Craniospinal + Focal Boost
**Patient**: e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3
**Timeline Date**: Day 6454

```csv
radiation: Yes
radiation_type: Protons
radiation_site: Craniospinal with focal boost
total_radiation_dose: 4140
total_radiation_dose_unit: cGy
total_radiation_dose_focal: 5400
total_radiation_dose_focal_unit: cGy
age_at_radiation_start: 6457
age_at_radiation_stop: 6504
```

**Key Learning Points:**
- **BOTH fields populated**: craniospinal dose = 4140 cGy, focal dose = 5400 cGy
- This is the pattern from previous test failure!
- Total treatment dose = 5400 cGy (focal includes craniospinal + boost)
- Duration: 47 days
- Concurrent with temozolomide chemotherapy

**MedGemma Expected Output:**
```json
{
  "radiation_type": "focal_with_boost",
  "radiation_modality": "protons",
  "radiation_site": "craniospinal_with_focal_boost",
  "completed_craniospinal_or_whole_ventricular_radiation_dose": 4140,
  "completed_craniospinal_or_whole_ventricular_radiation_dose_unit": "cGy",
  "radiation_focal_or_boost_dose": 5400,
  "completed_radiation_focal_or_boost_dose_unit": "cGy",
  "total_dose_cgy": 5400,
  "date_at_radiation_start": "<date>",
  "date_at_radiation_stop": "<date>",
  "duration_days": 47,
  "fractions": 30,
  "any_other_radiation_treatments_not_captured": "Sequential craniospinal irradiation followed by focal boost to tumor bed"
}
```

**CRITICAL INTERPRETATION:**
- The focal dose (5400 cGy) represents the CUMULATIVE dose to the tumor bed
- Craniospinal dose (4140 cGy) represents dose to brain/spine
- Tumor bed receives: 4140 cGy (craniospinal) + 1260 cGy (boost) = 5400 cGy total

---

### Example 8: Photon Radiation
**Patient**: eDe7IanglsmBppe3htvO-QdYT26-v54aUqFAeTPQSJ6w3
**Timeline Date**: Day 1422

```csv
radiation: Yes
radiation_type: Photons
radiation_site: Focal/Tumor bed
total_radiation_dose_focal: 5400
total_radiation_dose_focal_unit: cGy
age_at_radiation_start: 1430
age_at_radiation_stop: 1471
```

**Key Learning Points:**
- Photon (not proton) therapy
- Standard focal dose: 5400 cGy = 54 Gy
- Duration: 41 days (typical 5.5-6 weeks)

**MedGemma Expected Output:**
```json
{
  "radiation_type": "focal",
  "radiation_modality": "photons",
  "radiation_site": "focal_tumor_bed",
  "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
  "radiation_focal_or_boost_dose": 5400,
  "total_dose_cgy": 5400,
  "date_at_radiation_start": "<date>",
  "date_at_radiation_stop": "<date>",
  "fractions": 30
}
```

---

### Example 9: Re-irradiation (Second Course)
**Patient**: eiZ8gIQ.xVzYybDaR2sW5E0z9yI5BQjDeWulBFer5T4g3
**Timeline Date**: Day 3473

```csv
treatment_status: New
radiation: Yes
radiation_type: Protons
radiation_site: Focal/Tumor bed
total_radiation_dose_focal: 3500
age_at_radiation_start: 3530
age_at_radiation_stop: 3545
```

**Key Learning Points:**
- Second radiation course (patient had prior radiation at day 3363)
- Lower dose: 3500 cGy (reduced for re-irradiation)
- Shorter course: 15 days
- Concurrent with chemotherapy (agents not available)

**MedGemma Expected Output:**
```json
{
  "radiation_type": "focal",
  "radiation_modality": "protons",
  "radiation_site": "focal_tumor_bed",
  "radiation_focal_or_boost_dose": 3500,
  "total_dose_cgy": 3500,
  "date_at_radiation_start": "<date>",
  "date_at_radiation_stop": "<date>",
  "treatment_course": "re_irradiation",
  "extraction_note": "Reduced dose consistent with re-irradiation"
}
```

---

### Example 10: Unavailable Radiation Details
**Patient**: eIkYtPKrgCyQIt1zJXMux2cWyHHSSFeZg6zKSznsH7WM3
**Timeline Date**: Day 4837

```csv
radiation: Unavailable
radiation_type: Unavailable
total_radiation_dose: Unavailable
total_radiation_dose_unit: Not Reported
radiation_site: Unavailable
age_at_radiation_start: 4841
age_at_radiation_stop: 4881
```

**Key Learning Points:**
- Dates available but all other details unavailable
- Use "Unavailable" vs "Not Applicable" vs null
- Duration: 40 days suggests standard fractionation

**MedGemma Expected Output:**
```json
{
  "radiation_type": null,
  "radiation_modality": null,
  "total_dose_cgy": null,
  "date_at_radiation_start": "<date>",
  "date_at_radiation_stop": "<date>",
  "extraction_confidence": "LOW",
  "extraction_note": "Radiation confirmed but details unavailable in document"
}
```

---

## Combined Treatment Examples

### Example 11: Concurrent Chemoradiation (Standard Stupp Protocol)
**Patient**: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83
**Timeline Date**: Day 4545

**Combined Treatment:**
```csv
# Chemotherapy
chemotherapy_agents: temozolomide;nivolumab
age_at_chemo_start: 4581
age_at_chemo_stop: 4735

# Radiation
radiation_type: Protons
radiation_site: Focal/Tumor bed
total_radiation_dose_focal: 5940 cGy
age_at_radiation_start: 4581
age_at_radiation_stop: 4629
```

**Key Learning Points:**
- Chemo and radiation START on same day: 4581
- Radiation completes first: 4629 (48 days)
- Chemo continues after radiation: stops 4735 (154 days total)
- Pattern: Concurrent temozolomide during RT, then adjuvant temozolomide + nivolumab

**MedGemma Expected Output:**
```json
{
  "treatment_paradigm": "concurrent_chemoradiation",
  "chemotherapy": {
    "agents": ["temozolomide", "nivolumab"],
    "date_at_chemo_start": "<date>",
    "date_at_chemo_stop": "<date>"
  },
  "radiation": {
    "radiation_type": "focal",
    "total_dose_cgy": 5940,
    "date_at_radiation_start": "<date>",
    "date_at_radiation_stop": "<date>"
  },
  "temporal_relationship": "concurrent_then_adjuvant",
  "extraction_note": "Standard Stupp-like regimen: concurrent TMZ during RT, followed by adjuvant chemotherapy"
}
```

---

### Example 12: CRITICAL - Craniospinal RT + Concurrent TMZ (ACNS0126 Protocol)
**Patient**: e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3
**Timeline Date**: Day 6454

**Combined Treatment:**
```csv
# Chemotherapy
protocol_name: ACNS0126
chemotherapy_agents: temozolomide
age_at_chemo_start: 6454
age_at_chemo_stop: 6626

# Radiation
radiation_type: Protons
radiation_site: Craniospinal with focal boost
total_radiation_dose: 4140 cGy
total_radiation_dose_focal: 5400 cGy
age_at_radiation_start: 6457
age_at_radiation_stop: 6504
```

**Key Learning Points:**
- **HIGH-RISK MEDULLOBLASTOMA PARADIGM**
- Protocol: ACNS0126 (COG high-risk medulloblastoma)
- Craniospinal: 4140 cGy (23 Gy reduced dose per protocol)
- Focal boost: 5400 cGy total to posterior fossa
- Concurrent temozolomide during and after RT
- Chemo starts 3 days before RT: 6454 vs 6457
- Chemo continues 122 days after RT ends: 6626 vs 6504

**MedGemma Expected Output:**
```json
{
  "treatment_paradigm": "high_risk_medulloblastoma_protocol",
  "protocol": "ACNS0126",
  "chemotherapy": {
    "agents": ["temozolomide"],
    "date_at_chemo_start": "<date>",
    "date_at_chemo_stop": "<date>",
    "duration_days": 172
  },
  "radiation": {
    "radiation_type": "focal_with_boost",
    "radiation_site": "craniospinal_with_focal_boost",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": 4140,
    "radiation_focal_or_boost_dose": 5400,
    "total_dose_cgy": 5400,
    "date_at_radiation_start": "<date>",
    "date_at_radiation_stop": "<date>",
    "duration_days": 47,
    "fractions": 30
  },
  "temporal_relationship": "concurrent_and_adjuvant",
  "any_other_radiation_treatments_not_captured": "Sequential craniospinal irradiation (4140 cGy) followed by posterior fossa boost to total 5400 cGy per ACNS0126 protocol"
}
```

---

## Edge Cases

### Edge Case 1: Multiple Surgeries, No Chemo/RT
**Patient**: eUFS4hKO-grXh72WvK-5l0TFbD0sV2SMysYY5JpxOR-A3
**Timeline Dates**: Day 5844 (biopsy), Day 5847 (resection)

```csv
# Day 5844
surgery: Yes
extent_of_tumor_resection: Biopsy only
specimen_collection_origin: Initial CNS Tumor Surgery

# Day 5847 (3 days later)
surgery: Yes
extent_of_tumor_resection: Gross/Near total resection
specimen_collection_origin: Repeat resection
```

**Key Learning Points:**
- Two surgeries 3 days apart
- First: Biopsy only
- Second: Definitive resection
- Pattern: Diagnostic biopsy → awaiting pathology → definitive surgery

---

### Edge Case 2: Treatment Change Due to Progression
**Patient**: eXdEVvOs091o4-RCug2.5hA3
**Timeline**: Multiple treatment lines

```csv
# Line 1 (Day 4851): Initial treatment
protocol_name: ACNS0423
chemotherapy_agents: temozolomide;lomustine
radiation: Yes (5940 cGy focal proton)

# Line 2 (Day 5305): Modified due to toxicity
treatment_status: Modified Treatment
reason_for_treatment_change: Toxicities
chemotherapy_agents: procarbazine

# Line 3 (Day 5490): New treatment line
treatment_status: New
chemotherapy_agents: avastin

# Line 4 (Day 5591): Off treatment
treatment_status: No treatment
```

**Key Learning Points:**
- Capture treatment trajectory
- Distinguish "Modified Treatment" vs "New" treatment line
- Reason for change: Toxicities vs Progression vs Other

---

## Summary Statistics from Human Abstraction

**Radiation Dose Patterns:**
| Dose (cGy) | Gy Equivalent | Pattern | Count |
|------------|---------------|---------|-------|
| 5940 | 59.4 Gy | Standard high-grade focal | 4 |
| 5400 | 54.0 Gy | Standard focal | 3 |
| 5570 | 55.7 Gy | Slightly reduced focal | 1 |
| 5490 | 54.9 Gy | Standard focal | 1 |
| 4140 | 41.4 Gy | Craniospinal (reduced dose) | 1 |
| 3500 | 35.0 Gy | Re-irradiation | 1 |

**Chemotherapy Agent Frequency:**
| Agent | Count | Notes |
|-------|-------|-------|
| temozolomide | 6 | Standard alkylator |
| lomustine | 3 | CCNU, nitrosourea |
| nivolumab | 1 | PD-1 inhibitor |
| etoposide | 1 | Topoisomerase inhibitor |
| procarbazine | 1 | Alkylator |
| bevacizumab/avastin | 2 | VEGF inhibitor |
| pazopanib | 1 | Multi-kinase inhibitor |
| everolimus | 1 | mTOR inhibitor |
| dasatinib | 1 | Tyrosine kinase inhibitor |

**Protocol Frequency:**
| Protocol | Count | Disease |
|----------|-------|---------|
| ACNS0423 | 1 | High-grade glioma |
| ACNS0126 | 1 | High-risk medulloblastoma |

---

## Validation Rules Based on Human Abstraction

### Required Fields for Complete Extraction:

**Chemotherapy:**
- ✅ chemotherapy_agents (can be null if truly unavailable)
- ✅ date_at_chemo_start
- ⚠️ date_at_chemo_stop (can be null if ongoing)
- ⚠️ protocol_name (can be null)

**Radiation:**
- ✅ radiation_type (focal, craniospinal, focal_with_boost)
- ✅ date_at_radiation_start
- ✅ date_at_radiation_stop
- ✅ total_dose_cgy (REQUIRED - sum of all radiation)
- ⚠️ completed_craniospinal_or_whole_ventricular_radiation_dose (null if focal-only)
- ⚠️ radiation_focal_or_boost_dose (null if craniospinal-only without boost)
- ✅ At least ONE dose field must be populated

---

**Generated**: 2025-10-31
**Purpose**: Training examples for MedGemma prompt engineering and Agent 1↔2 negotiation
