# Event Type Determination Strategy for Extent of Resection

**Created**: 2025-10-11
**Purpose**: Define strategy for linking extent of resection to correct event_type based on data dictionary requirements

---

## Overview

The data dictionary defines `event_type` as a critical field that determines the clinical context for each diagnosis event:
- **5**: Initial CNS Tumor
- **6**: Second Malignancy
- **7**: Recurrence
- **8**: Progressive
- **10**: Deceased
- **9**: Unavailable

### Critical Logic Rule (from Data Dictionary)

> "Determined by extent of tumor resection; if a previous surgery is a **gross total resection** and the tumor re-grows, the next record and subsequent surgery is considered a **recurrence**; if a previous surgery is a **partial resection** and the tumor grows, the next record and subsequent surgery is considered a **progression**."

---

## Patient C1277724 Case Study

### Gold Standard Event Classification

| Event | Age (days) | Event Type | Surgery Date | Extent of Resection | Logic |
|-------|-----------|------------|--------------|---------------------|-------|
| **Event 1** | 4763 | **Initial CNS Tumor** (5) | 2018-05-28 | Partial resection | First presentation |
| **Event 2** | 5095 | **Progressive** (8) | N/A (no surgery) | N/A | Tumor growth after partial resection (Event 1) |
| **Event 3** | 5780 | **Progressive** (8) | 2021-03-10 | Partial resection | Tumor growth after partial resection (Event 1) |

### Key Insights

1. **Initial Surgery (Event 1)** = Partial Resection
   - Sets the baseline: Since NOT gross total, all subsequent growth = **Progressive**

2. **Event 2** = Progressive (NO surgery, just clinical progression documented)
   - Age 5095 days (~332 days after initial surgery)
   - Local progression in cerebellum/posterior fossa
   - Triggered chemotherapy (vinblastine + bevacizumab)

3. **Event 3** = Progressive WITH surgery
   - Age 5780 days (~685 days after Event 2, ~1017 days after initial surgery)
   - Second partial resection
   - Still classified as **Progressive** because initial surgery was partial (not GTR)

---

## Event Type Determination Algorithm

### Step 1: Identify All Surgeries and Their Extent of Resection

```python
def classify_surgeries(procedures_df, documents_df):
    """
    Link surgeries to operative notes to extract extent of resection
    """
    surgeries = []

    for idx, surgery in procedures_df.iterrows():
        surgery_date = surgery['performed_period_start'][:10]  # YYYY-MM-DD

        # Find operative note via context_period_start matching
        op_notes = documents_df[
            (documents_df['context_period_start'].str.startswith(surgery_date)) &
            (documents_df['document_type'].str.contains('OP Note'))
        ].sort_values('document_type')  # Prioritize "Complete" over "Brief"

        surgeries.append({
            'surgery_date': surgery_date,
            'age_at_surgery': surgery['age_at_procedure_days'],
            'procedure_id': surgery['procedure_fhir_id'],
            'op_note_id': op_notes.iloc[0]['document_reference_id'] if len(op_notes) > 0 else None,
            'extent_of_resection': None  # To be filled by BRIM extraction
        })

    return pd.DataFrame(surgeries)
```

### Step 2: Classify Event Type Based on Surgery Sequence

```python
def determine_event_type(surgeries_df):
    """
    Apply data dictionary logic to determine event_type for each surgery

    Rules:
    1. First surgery = Initial CNS Tumor (5)
    2. If previous surgery was GTR/NTR + tumor regrows = Recurrence (7)
    3. If previous surgery was Partial/STR/Biopsy + tumor grows = Progressive (8)
    """
    surgeries_df = surgeries_df.sort_values('age_at_surgery').reset_index(drop=True)
    event_types = []

    for idx, surgery in surgeries_df.iterrows():
        if idx == 0:
            # First surgery is always Initial CNS Tumor
            event_types.append('5')  # Initial CNS Tumor
        else:
            # Look at previous surgery extent
            previous_extent = surgeries_df.iloc[idx - 1]['extent_of_resection']

            if previous_extent in ['Gross Total Resection (GTR)', 'Near Total Resection (NTR)',
                                   'Gross/Near total resection']:
                event_types.append('7')  # Recurrence
            elif previous_extent in ['Partial resection', 'Subtotal Resection (STR)',
                                     'Biopsy Only', 'Biopsy only']:
                event_types.append('8')  # Progressive
            else:
                event_types.append('9')  # Unavailable (unknown previous extent)

    surgeries_df['event_type'] = event_types
    return surgeries_df
```

### Step 3: Handle Non-Surgical Progressive Events

```python
def identify_clinical_progression_events(imaging_df, surgeries_df):
    """
    Identify progressive events documented in imaging/clinical notes
    WITHOUT associated surgery

    These would be Event 2 type scenarios (age 5095 for C1277724)
    """
    progression_events = []

    # Look for imaging reports with keywords indicating progression
    progression_keywords = [
        'progression', 'progressive disease', 'tumor growth',
        'increased size', 'new enhancement', 'worsening'
    ]

    for idx, img in imaging_df.iterrows():
        if any(keyword in img['result_information'].lower()
               for keyword in progression_keywords):

            # Check if this is NOT associated with a surgery date
            img_date = img['imaging_date'][:10]
            if img_date not in surgeries_df['surgery_date'].values:
                progression_events.append({
                    'event_date': img_date,
                    'age_at_event': img['age_at_imaging_days'],
                    'event_type': '8',  # Progressive
                    'surgery': 'No',
                    'evidence': 'Imaging progression documented'
                })

    return pd.DataFrame(progression_events)
```

---

## Implementation for C1277724

### Expected Output Table

| event_type | age_at_event_days | surgery | age_at_surgery | extent_of_tumor_resection | Evidence Source |
|-----------|------------------|---------|----------------|---------------------------|-----------------|
| **5** (Initial CNS Tumor) | 4763 | Yes | 4763 | Partial resection | OP Note 2018-05-28 |
| **8** (Progressive) | 5095 | No | N/A | N/A | Imaging + chemotherapy initiation |
| **8** (Progressive) | 5780 | Yes | 5780 | Partial resection | OP Note 2021-03-10 |

### Mapping to Data Dictionary Fields

| Variable / Field Name | Value for Event 1 | Value for Event 2 | Value for Event 3 |
|----------------------|-------------------|-------------------|-------------------|
| **event_type** | 5 (Initial CNS Tumor) | 8 (Progressive) | 8 (Progressive) |
| **age_at_event_days** | 4763 | 5095 | 5780 |
| **surgery** | 1 (Yes) | 2 (No) | 1 (Yes) |
| **age_at_surgery** | 4763 | N/A | 5780 |
| **extent_of_tumor_resection** | 2 (Partial resection) | 5 (N/A) | 2 (Partial resection) |

---

## STRUCTURED Document Design

### STRUCTURED_surgery_events.md Format

```markdown
# Surgery Events with Event Type Classification
Patient: C1277724 (FHIR: e4BwD8ZYDBccepXcJ.Ilo3w3)

## Event 1: Initial CNS Tumor (age 4763 days)

**Event Type**: 5 (Initial CNS Tumor)
**Surgery Date**: 2018-05-28
**Age at Surgery**: 4763 days
**Surgery Type**: CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION
**Procedure FHIR ID**: fSUOuC2zGppXw6ft5yRFL6idtK2kZjjV6DoTHxFsq87w4

### Linked Operative Note
- **Document Type**: OP Note - Complete (Template or Full Dictation)
- **Document Date**: 2018-05-29 13:39:00
- **Context Period Start**: 2018-05-28 13:57:00 ✅ (matches surgery date)
- **S3 Available**: Yes
- **Document ID**: fJh9zEOHdPgUlvOZvGDNO9.fOIE1nJGqJvTNNhPR.klI4

### Extent of Resection
**Gold Standard**: Partial resection
**BRIM Extraction Target**: Extract from OP Note sections:
- Procedure performed
- Post-operative impression
- Surgeon's assessment

---

## Event 2: Progressive Disease (age 5095 days)

**Event Type**: 8 (Progressive)
**Surgery**: No
**Clinical Evidence**: Imaging progression + chemotherapy initiation
**Age at Event**: 5095 days (~332 days after initial surgery)
**Site of Progression**: Local (Cerebellum/Posterior Fossa)

### Evidence Sources
- Imaging studies showing tumor growth
- Initiation of chemotherapy (vinblastine + bevacizumab) at age 5130 days
- Clinical assessment notes

**Logic**: Tumor growth after partial resection (Event 1) = Progressive per data dictionary

---

## Event 3: Progressive Disease with Surgery (age 5780 days)

**Event Type**: 8 (Progressive)
**Surgery Date**: 2021-03-10
**Age at Surgery**: 5780 days
**Surgery Type**: STRTCTC CPTR ASSTD PX CRANIAL INTRADURAL
**Procedure FHIR ID**: fL.qXzge9F8KQEloCTo66Ux8WQfYzyLTz5GZECIaYXCo4

### Linked Operative Note
- **Document Type**: OP Note - Complete (Template or Full Dictation)
- **Document Date**: 2021-03-16 14:08:00
- **Context Period Start**: 2021-03-10 14:46:00 ✅ (matches surgery date)
- **S3 Available**: Yes
- **Document ID**: fSFJXFYBhCHXTg8EyDGnJDL89xUzQZaLVmDzk2wZL4lk4

### Extent of Resection
**Gold Standard**: Partial resection
**BRIM Extraction Target**: Extract from OP Note sections

**Logic**: Tumor growth after partial resection (Event 1) = Progressive per data dictionary
```

---

## Key Linkage Fields

### From Procedure Resource to Operative Note

1. **Primary Linkage**: `context_period_start` matching surgery date
   ```python
   documents_df[
       documents_df['context_period_start'].str.startswith(surgery_date)
   ]
   ```

2. **Document Type Priority**:
   - OP Note - Complete (Template or Full Dictation) [PRIORITY 1]
   - OP Note - Brief (Needs Dictation) [PRIORITY 2]
   - Operative Record [PRIORITY 3]
   - Anesthesia Postprocedure Evaluation [PRIORITY 4]

3. **S3 Availability**: Filter for `s3_available = 'Yes'` to ensure document can be retrieved

---

## BRIM Variable Instructions Update

### Updated surgery_extent Variable Instructions

```csv
surgery_extent,"Extract extent of tumor resection for each surgery.

EVENT TYPE DETERMINATION:
- First surgery is ALWAYS event_type = 5 (Initial CNS Tumor)
- If PREVIOUS surgery was GTR/NTR and tumor regrows → event_type = 7 (Recurrence)
- If PREVIOUS surgery was Partial/STR/Biopsy and tumor grows → event_type = 8 (Progressive)

PRIORITY SEARCH ORDER:
1. STRUCTURED_surgery_events.md - Pre-linked operative notes by surgery date
2. Documents with context_period_start matching surgery date
3. Post-operative imaging reports (same date or within 7 days)

VALID VALUES (Data Dictionary Mapping):
- 1, Gross/Near total resection (includes GTR >95% OR NTR 90-95%)
- 2, Partial resection (includes STR 50-90% OR <50% debulking)
- 3, Biopsy only (diagnostic only, no resection)
- 4, Unavailable
- 5, N/A (for non-surgical events)

EXTRACTION KEYWORDS:
- GTR/NTR: 'gross total', 'near total', 'complete resection', '>90%', 'no residual'
- Partial: 'partial', 'subtotal', 'STR', 'debulking', '<90%', 'residual tumor'
- Biopsy: 'biopsy only', 'diagnostic biopsy', 'no resection performed'

CRITICAL: Match extent values EXACTLY with data dictionary format

Gold Standard for C1277724:
- Event 1 (age 4763, 2018-05-28): event_type=5, extent=2 (Partial resection)
- Event 3 (age 5780, 2021-03-10): event_type=8, extent=2 (Partial resection)
```

---

## Validation Checklist

### For Each Surgery Event:

- [ ] Surgery date extracted from Procedure.performedPeriodStart
- [ ] Age at surgery calculated from birth date
- [ ] Operative note linked via context_period_start matching
- [ ] Extent of resection extracted from operative note
- [ ] Event type determined based on previous surgery extent
- [ ] Data dictionary value mappings applied correctly
- [ ] Event sequence validated against gold standard

### For Patient C1277724 Specifically:

- [ ] 2 surgeries identified (2018-05-28, 2021-03-10)
- [ ] 1 non-surgical progressive event identified (age 5095)
- [ ] Event 1 classified as Initial CNS Tumor (5)
- [ ] Event 2 classified as Progressive (8) - no surgery
- [ ] Event 3 classified as Progressive (8) - with surgery
- [ ] Both surgical extents = Partial resection (value 2)
- [ ] Event type logic: Partial → Progressive (not Recurrence)

---

## Next Steps

1. ✅ Document event_type determination strategy
2. ⏳ Create Python script to generate STRUCTURED_surgery_events.md
3. ⏳ Update BRIM variables.csv with event_type instructions
4. ⏳ Create validation script comparing BRIM output to gold standard
5. ⏳ Test on C1277724 pilot patient
6. ⏳ Validate event_type classification accuracy

---

## References

- **Data Dictionary**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/brim_workflows_individual_fields/radiology_op_note_data_dictionary.csv`
- **Gold Standard**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/GOLD_STANDARD_C1277724.md`
- **Linkage Strategy**: `IMAGING_AND_OPERATIVE_NOTE_LINKAGE_STRATEGY.md`
- **Procedures CSV**: `athena_extraction_validation/staging_files/ALL_PROCEDURES_WITH_ENCOUNTERS_C1277724.csv`
- **Documents CSV**: `athena_extraction_validation/staging_files/ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv`
