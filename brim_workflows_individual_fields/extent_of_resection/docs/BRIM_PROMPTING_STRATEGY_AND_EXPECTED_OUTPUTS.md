# BRIM Prompting Strategy and Expected Outputs

**Date**: 2025-10-11
**Purpose**: Document BRIM variable prompting strategy, extraction logic, and expected outputs for radiology/operative note fields

---

## Overview

This document details the **9 variables** we're extracting from radiology and operative note documents, organized by:
1. **Extraction source** (STRUCTURED vs clinical notes)
2. **Prompting strategy** (how we instruct BRIM)
3. **Expected output format**
4. **Validation approach**

---

## Variable Categories

### **Category A: 100% Automated from STRUCTURED Documents** (4 variables)

These are extracted directly from the STRUCTURED_surgery_events document with near-perfect accuracy because the values are pre-computed and formatted.

| Variable | Source | Expected Accuracy |
|----------|--------|------------------|
| event_type | STRUCTURED_surgery_events | **100%** |
| age_at_event_days | STRUCTURED_surgery_events | **100%** |
| surgery | STRUCTURED_surgery_events | **100%** |
| age_at_surgery | STRUCTURED_surgery_events | **100%** |

### **Category B: LLM Extraction from Clinical Notes** (5 variables)

These require BRIM's LLM to extract from unstructured operative notes and imaging reports.

| Variable | Source | Expected Accuracy |
|----------|--------|------------------|
| extent_of_tumor_resection | Operative notes | **85-90%** |
| tumor_location | Op notes + imaging | **85-90%** |
| metastasis | Imaging reports | **75-80%** |
| metastasis_location | Imaging reports | **70-75%** |
| site_of_progression | Sequential imaging | **70-75%** |

---

## Detailed Variable Specifications

### **Variable 1: event_type** ✅ 100% Automated

**Data Dictionary Field**: `event_type` (radio button)

**Valid Values**:
- `5` = Initial CNS Tumor
- `6` = Second Malignancy
- `7` = Recurrence
- `8` = Progressive
- `9` = Unavailable
- `10` = Deceased

**BRIM Instruction**:
```
Extract event_type from STRUCTURED_surgery_events document.
Look for "Event Type: X" in each Event section.
Valid values: 5 (Initial CNS Tumor), 6 (Second Malignancy),
7 (Recurrence), 8 (Progressive), 9 (Unavailable), 10 (Deceased).
Return only the numeric code.
```

**Scope**: `many_per_note` (one per surgical event)

**Example STRUCTURED Document Content**:
```markdown
## Event 1: Initial CNS Tumor (age 4763 days)

**Event Type**: 5 (Initial CNS Tumor)
**Surgery Date**: 2018-05-28
**Age at Surgery**: 4763 days
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_surgery_events,event_type,5
STRUCTURED_surgery_events,event_type,8
```

**Validation**: Compare to gold standard event classification

---

### **Variable 2: age_at_event_days** ✅ 100% Automated

**Data Dictionary Field**: `age_at_event_days` (text, converted to days)

**Valid Values**: Numeric (days since birth)

**BRIM Instruction**:
```
Extract age_at_event_days from STRUCTURED_surgery_events document.
Look for "Age at Surgery: X days" in each Event section.
Return only the numeric value (days).
```

**Scope**: `many_per_note`

**Example STRUCTURED Document Content**:
```markdown
**Age at Surgery**: 4763 days (~13.0 years)
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_surgery_events,age_at_event_days,4763
STRUCTURED_surgery_events,age_at_event_days,5780
```

**Validation**: Compare to `Procedure.performedPeriodStart` - birthdate calculation

---

### **Variable 3: surgery** ✅ 100% Automated

**Data Dictionary Field**: `surgery` (radio button)

**Valid Values**:
- `1` = Yes
- `2` = No
- `3` = Unavailable

**BRIM Instruction**:
```
Determine if surgery was performed.
If document is STRUCTURED_surgery_events: always return 1 (Yes).
For other documents: look for surgical procedure descriptions.
Valid values: 1 (Yes), 2 (No), 3 (Unavailable).
Return only the numeric code.
```

**Scope**: `many_per_note`

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_surgery_events,surgery,1
STRUCTURED_surgery_events,surgery,1
```

**Validation**: Count should match number of surgical events in gold standard

---

### **Variable 4: age_at_surgery** ✅ 100% Automated

**Data Dictionary Field**: `age_at_surgery` (text, converted to days)

**Valid Values**: Numeric (days) or empty if no surgery

**BRIM Instruction**:
```
Extract age_at_surgery from STRUCTURED_surgery_events document.
Look for "Age at Surgery: X days" in each Event section.
Return only the numeric value (days).
If no surgery, return empty.
```

**Scope**: `many_per_note`

**Expected BRIM Output**: Same as age_at_event_days for surgical events

```csv
NOTE_ID,variable_name,value
STRUCTURED_surgery_events,age_at_surgery,4763
STRUCTURED_surgery_events,age_at_surgery,5780
```

**Validation**: Should match age_at_event_days for events with surgery=1

---

### **Variable 5: extent_of_tumor_resection** ⚠️ LLM Extraction (85-90% accuracy)

**Data Dictionary Field**: `extent_of_tumor_resection` (radio button)

**Valid Values**:
- `1` = Gross/Near total resection
- `2` = Partial resection
- `3` = Biopsy only
- `4` = Unavailable
- `5` = N/A

**BRIM Instruction**:
```
Extract extent of tumor resection from operative note (NOTE_TITLE contains "OP Note").
Look in sections: Procedure Performed, Post-operative Assessment, Surgeon Summary.
Keywords: GTR (gross total), NTR (near total), Partial, Subtotal (STR), Biopsy only.
Valid values: 1 (Gross/Near total resection), 2 (Partial resection),
3 (Biopsy only), 4 (Unavailable), 5 (N/A).
Return only the numeric code.
If document is not an operative note, skip.
```

**Scope**: `many_per_note` (one per operative note)

**Example Operative Note Content**:
```
PROCEDURE PERFORMED:
Suboccipital craniectomy for resection of posterior fossa tumor

POST-OPERATIVE ASSESSMENT:
Partial resection achieved due to tumor involvement of brainstem.
Residual tumor remains along floor of fourth ventricle.
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
op_note_1_2018-05-28,extent_of_tumor_resection,2
op_note_2_2021-03-10,extent_of_tumor_resection,2
```

**Validation**:
- Gold standard for C1277724: Both surgeries = Partial resection (2)
- Check for keywords: "partial", "residual", "incomplete", "debulking"

**Common Errors**:
- Confusing "near total" (NTR) with "partial" → Use strict keyword matching
- Missing extent when buried in narrative → Emphasize section headers

---

### **Variable 6: tumor_location** ⚠️ LLM Extraction (85-90% accuracy)

**Data Dictionary Field**: `tumor_location` (checkbox - can be multiple)

**Valid Values** (comma-separated numbers):
```
1=Frontal Lobe, 2=Temporal Lobe, 3=Parietal Lobe, 4=Occipital Lobe,
5=Thalamus, 6=Ventricles, 7=Suprasellar/Hypothalamic/Pituitary,
8=Cerebellum/Posterior Fossa, 9=Brain Stem-Medulla,
10=Brain Stem-Midbrain/Tectum, 11=Brain Stem-Pons,
12=Spinal Cord-Cervical, 13=Spinal Cord-Thoracic,
14=Spinal Cord-Lumbar/Thecal Sac, 15=Optic Pathway,
16=Cranial Nerves NOS, 19=Pineal Gland, 20=Basal Ganglia,
21=Hippocampus, 22=Meninges/Dura, 23=Skull, 24=Unavailable
```

**BRIM Instruction**:
```
Extract tumor anatomical location(s).
Search operative notes and imaging reports.
Valid values (return comma-separated numbers): [list above]
Return numeric codes only (e.g., "8" or "8,10").
```

**Scope**: `many_per_note`
**Aggregation**: `Combine all unique tumor locations across documents`

**Example Operative Note Content**:
```
INDICATION: Pilocytic astrocytoma of cerebellum/posterior fossa
with extension to midbrain tectum

FINDINGS: Tumor epicenter in right cerebellar hemisphere with
involvement of vermis and fourth ventricle floor
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
op_note_1_2018-05-28,tumor_location,8
op_note_2_2021-03-10,tumor_location,"8,10"
```

**Aggregated Output**:
```csv
patient_fhir_id,tumor_location_aggregated
e4BwD8ZYDBccepXcJ.Ilo3w3,"8,10"
```

**Validation**:
- Gold standard: Cerebellum/Posterior Fossa (8), Midbrain/Tectum (10), Temporal Lobe (2)
- Check for anatomical synonyms: "posterior fossa" = "infratentorial"

**Common Errors**:
- Missing secondary locations → Emphasize "all mentioned locations"
- Using text labels instead of numbers → Strict "numeric codes only" instruction

---

### **Variable 7: metastasis** ⚠️ LLM Extraction (75-80% accuracy)

**Data Dictionary Field**: `metastasis` (radio button)

**Valid Values**:
- `0` = Yes (metastases present)
- `1` = No (localized)
- `2` = Unavailable

**BRIM Instruction**:
```
Determine if metastatic disease was present at time of diagnosis/clinical event.
Search imaging reports (especially pre-operative) for:
CSF spread, leptomeningeal involvement, spine metastases, bone marrow involvement,
distant brain metastases.
Valid values: 0 (Yes - metastases present), 1 (No - localized), 2 (Unavailable).
Return only the numeric code.
```

**Scope**: `many_per_note`

**Example Imaging Report Content**:
```
IMPRESSION:
1. Large posterior fossa mass consistent with pilocytic astrocytoma
2. Leptomeningeal enhancement along spinal cord concerning for CSF seeding
3. Hydrocephalus requiring ventriculostomy
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_imaging,metastasis,0
imaging_preop_2018-05-27,metastasis,0
```

**Validation**:
- Gold standard for C1277724: Yes (0) at initial diagnosis - leptomeningeal + spine
- Cross-validate with shunt requirement and CSF analysis notes

**Common Errors**:
- Confusing "concerning for" vs "confirmed" metastases → Use permissive language
- Missing CSF spread when mentioned in narrative → Include synonyms

---

### **Variable 8: metastasis_location** ⚠️ LLM Extraction (70-75% accuracy)

**Data Dictionary Field**: `metastasis_location` (checkbox - conditional on metastasis=0)

**Valid Values** (comma-separated numbers):
```
0=CSF, 1=Spine, 2=Bone Marrow, 3=Other, 4=Brain, 5=Leptomeningeal, 6=Unavailable
```

**BRIM Instruction**:
```
If metastases present (metastasis=0), extract location(s).
Valid values (comma-separated numbers):
0=CSF, 1=Spine, 2=Bone Marrow, 3=Other, 4=Brain, 5=Leptomeningeal, 6=Unavailable.
Return numeric codes only. Skip if metastasis=1 (No).
```

**Scope**: `many_per_note`
**Aggregation**: `Combine all unique metastasis locations`

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
imaging_preop_2018-05-27,metastasis_location,"0,1,5"
```

**Interpretation**: CSF (0) + Spine (1) + Leptomeningeal (5)

**Validation**:
- Gold standard: Leptomeningeal (5), Spine (1)
- Note: Leptomeningeal involvement implies CSF spread

---

### **Variable 9: site_of_progression** ⚠️ LLM Extraction (70-75% accuracy)

**Data Dictionary Field**: `site_of_progression` (radio - conditional on event_type=8)

**Valid Values**:
- `1` = Local (growth at original site)
- `2` = Metastatic (new distant sites)
- `3` = Unavailable

**BRIM Instruction**:
```
For Progressive events (event_type=8), determine site of progression.
Compare current imaging to previous studies.
Look for: growth at original site (Local) vs new distant sites (Metastatic).
Valid values: 1 (Local), 2 (Metastatic), 3 (Unavailable).
Return only the numeric code. Skip if event_type != 8.
```

**Scope**: `many_per_note`

**Example STRUCTURED_imaging Content**:
```markdown
## Event 3: Surgery on 2021-03-10

### Post-operative Imaging

| Date | Days After Surgery | Findings |
|------|-------------------|----------|
| 2021-06-15 | 97 days | Interval growth of residual tumor in posterior fossa.
No new distant lesions. Stable leptomeningeal enhancement. |
```

**Expected BRIM Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_imaging,site_of_progression,1
```

**Validation**:
- Gold standard for C1277724 Event 3: Local (1) progression
- Check for keywords: "interval growth", "residual tumor", "local recurrence"

**Common Errors**:
- Confusing stable metastases with new progression → Emphasize "new" vs "stable"
- Missing temporal comparison → Link to STRUCTURED timeline

---

## BRIM Output File Formats

### **1. Variable-Level Output** (per-note extractions)

**File**: `{patient_fhir_id}_variables_output.csv`

**Format**:
```csv
NOTE_ID,variable_name,value,confidence_score
STRUCTURED_surgery_events,event_type,5,1.0
STRUCTURED_surgery_events,age_at_event_days,4763,1.0
op_note_1_2018-05-28,extent_of_tumor_resection,2,0.89
op_note_1_2018-05-28,tumor_location,8,0.92
STRUCTURED_imaging,metastasis,0,0.95
```

**Rows**: One per (NOTE_ID, variable_name) combination

### **2. Aggregated Output** (patient-level decisions)

**File**: `{patient_fhir_id}_decisions_output.csv`

**Format**:
```csv
patient_fhir_id,decision_name,value
e4BwD8ZYDBccepXcJ.Ilo3w3,event_sequence,"Event 1: event_type=5, age=4763 days; Event 2: event_type=8, age=5095 days; Event 3: event_type=8, age=5780 days"
e4BwD8ZYDBccepXcJ.Ilo3w3,total_surgical_events,2
e4BwD8ZYDBccepXcJ.Ilo3w3,progression_vs_recurrence_count,"Recurrence: 0, Progressive: 2"
e4BwD8ZYDBccepXcJ.Ilo3w3,metastatic_disease_present,"Yes - Leptomeningeal, Spine"
```

---

## Validation Strategy

### **Step 1: Automated Field Validation** (Category A variables)

Compare BRIM output to pre-computed values from staging files:

```python
def validate_automated_fields(brim_output, staging_file):
    """
    Validate that BRIM correctly extracted values from STRUCTURED documents
    """
    discrepancies = []

    # Load staging data
    staging = pd.read_csv(staging_file)

    for idx, row in staging.iterrows():
        # Check event_type
        brim_value = brim_output[
            (brim_output['NOTE_ID'] == 'STRUCTURED_surgery_events') &
            (brim_output['variable_name'] == 'event_type')
        ].iloc[idx]['value']

        if int(brim_value) != int(row['event_type']):
            discrepancies.append({
                'variable': 'event_type',
                'expected': row['event_type'],
                'actual': brim_value,
                'event': idx + 1
            })

    return discrepancies
```

**Expected Result**: 100% match for Category A variables

### **Step 2: Gold Standard Comparison** (Category B variables)

```python
def validate_extraction_fields(brim_output, gold_standard):
    """
    Compare BRIM LLM extractions to gold standard
    """
    results = {
        'extent_of_tumor_resection': {
            'expected': [2, 2],  # Both partial
            'actual': brim_output[
                brim_output['variable_name'] == 'extent_of_tumor_resection'
            ]['value'].tolist(),
            'match': False
        },
        # ... other fields
    }

    for field, data in results.items():
        data['match'] = data['expected'] == data['actual']
        data['accuracy'] = sum(e == a for e, a in zip(
            data['expected'], data['actual']
        )) / len(data['expected'])

    return results
```

### **Step 3: Cross-Field Consistency Checks**

```python
def check_consistency(brim_output):
    """
    Validate logical consistency across fields
    """
    checks = []

    # Check 1: age_at_surgery should equal age_at_event_days when surgery=1
    surgery_events = brim_output[brim_output['variable_name'] == 'surgery']
    for idx, row in surgery_events[surgery_events['value'] == '1'].iterrows():
        age_at_event = brim_output[
            (brim_output['NOTE_ID'] == row['NOTE_ID']) &
            (brim_output['variable_name'] == 'age_at_event_days')
        ]['value'].values[0]

        age_at_surgery = brim_output[
            (brim_output['NOTE_ID'] == row['NOTE_ID']) &
            (brim_output['variable_name'] == 'age_at_surgery')
        ]['value'].values[0]

        if age_at_event != age_at_surgery:
            checks.append({
                'check': 'age_consistency',
                'failed': True,
                'note': row['NOTE_ID']
            })

    # Check 2: metastasis_location should only exist when metastasis=0
    # ... etc

    return checks
```

---

## Expected Accuracy Summary

| Variable | Extraction Type | Expected Accuracy | Validation Method |
|----------|----------------|-------------------|-------------------|
| event_type | Structured | **100%** | Exact match to staging file |
| age_at_event_days | Structured | **100%** | Exact match to staging file |
| surgery | Structured | **100%** | Exact match to staging file |
| age_at_surgery | Structured | **100%** | Exact match to staging file |
| extent_of_tumor_resection | LLM | **85-90%** | Gold standard comparison |
| tumor_location | LLM | **85-90%** | Gold standard comparison |
| metastasis | LLM | **75-80%** | Gold standard comparison |
| metastasis_location | LLM | **70-75%** | Gold standard comparison |
| site_of_progression | LLM | **70-75%** | Gold standard comparison |

**Overall Expected Accuracy**: **~88%** across all 9 variables

---

## Next Steps

1. **Generate BRIM CSVs** for patient e4BwD8ZYDBccepXcJ.Ilo3w3
2. **Upload to BRIM platform**
3. **Run extraction job**
4. **Download results**
5. **Execute validation scripts** (automated + gold standard)
6. **Analyze discrepancies** and refine prompts if needed
7. **Document actual accuracy** vs expected

---

## References

- **Data Dictionary**: `radiology_op_note_data_dictionary.csv`
- **Gold Standard**: `GOLD_STANDARD_C1277724.md`
- **BRIM CSV Generator**: `generate_radiology_opnote_brim_csvs.py`
- **Validation Patient**: e4BwD8ZYDBccepXcJ.Ilo3w3
