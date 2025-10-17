# Procedures Staging File Analysis

## Overview

Comprehensive analysis of ALL_PROCEDURES_METADATA_C1277724.csv - a complete procedures staging file extracted from FHIR v2 database before applying any filtering logic.

**File**: `ALL_PROCEDURES_METADATA_C1277724.csv`
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)
**Birth Date**: 2005-05-13
**Extraction Date**: 2024
**Total Procedures**: 72
**Total Columns**: 34
**File Size**: 77.7 KB

## Staging File Philosophy

This is a **STAGING FILE** - we extract EVERYTHING first, then filter later. This approach:
1. Preserves all data for exploratory analysis
2. Allows pattern discovery before imposing filters
3. Enables validation of filtering logic
4. Provides complete audit trail
5. Supports downstream resource linkage via procedure_fhir_id

## Column Structure (34 columns)

### Identity & Linkage (3 columns)
1. **procedure_fhir_id** - Unique FHIR resource ID (for linking to encounters, reports, etc.)
2. **subject_reference** - Patient FHIR ID (always e4BwD8ZYDBccepXcJ.Ilo3w3)
3. **encounter_reference** - Link to encounter FHIR ID (populated in 50% of procedures)

### Status & Timing (9 columns)
4. **status** - All 72 are "completed"
5. **performed_date_time** - Single datetime (sparse - 11% populated)
6. **performed_period_start** - Period start (11% populated, more reliable than date_time)
7. **performed_period_end** - Period end (11% populated)
8. **performed_string** - Free-text timing
9. **performed_age_value** - Age at procedure (numeric)
10. **performed_age_unit** - Age unit
11. **procedure_date** - Derived from performed_period_start (11% populated)
12. **age_at_procedure_days** - Calculated age in days (11% populated)

### Procedure Description (4 columns)
13. **code_text** - Human-readable procedure name from main table
14. **category_text** - Human-readable category from main table
15. **outcome_text** - Procedure outcome description (sparse)
16. **status_reason_text** - Why procedure was cancelled/not done (sparse)

### Structured Codes (4 columns)
17. **code_coding_system** - Code system URI (CPT, LOINC, Epic internal)
18. **code_coding_code** - Actual CPT/HCPCS code
19. **code_coding_display** - Structured code description (98.6% populated)
20. **is_surgical_keyword** - Boolean flag: TRUE if code contains surgical keywords

### Categories & Classification (2 columns)
21. **category_coding_display** - Structured category (100% populated)
   - "Diagnostic procedure" (62/72, 86%)
   - "Surgical procedure" (10/72, 14%)

### Anatomical & Location (3 columns)
22. **body_site_text** - Anatomical location (8.3% populated)
23. **location_reference** - Where procedure occurred (FHIR reference)
24. **location_display** - Location name

### Personnel (6 columns)
25. **performer_actor_display** - Provider name(s) (30.6% populated)
26. **performer_function_text** - Provider role(s) (30.6% populated)
27. **recorder_reference** - Who recorded the procedure
28. **recorder_display** - Recorder name
29. **asserter_reference** - Who asserted the procedure occurred
30. **asserter_display** - Asserter name

### Clinical Context (2 columns)
31. **reason_code_text** - Why procedure was performed (83.3% populated)
32. **encounter_display** - Description of associated encounter

### Documentation (2 columns)
33. **report_reference** - Link(s) to operative reports/documents (50% populated)
34. **report_display** - Report title(s) (50% populated)

## Data Distribution

### Status Breakdown
```
completed: 72/72 (100%)
```
**Observation**: All procedures in this dataset are completed. No in-progress, cancelled, or not-done procedures.

### Category Breakdown
```
Diagnostic procedure: 62/72 (86%)
Surgical procedure: 10/72 (14%)
```

**Insight**: Majority are diagnostic/screening procedures. Only 10 procedures explicitly categorized as surgical.

### Code System Breakdown
```
http://www.ama-assn.org/go/cpt: 58/72 (81%)
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580 (Epic internal): 13/72 (18%)
http://loinc.org: 1/72 (1%)
```

**Insight**: CPT codes dominate (standard billing codes). Epic internal codes likely for administrative orders.

### Surgical Keyword Detection
```
is_surgical_keyword = TRUE: 11/72 (15%)
```

**Keywords Searched**:
- craniotomy, craniectomy, resection, excision, biopsy
- surgery, surgical, anesthesia, anes, oper

**Discrepancy**: 11 flagged by keywords vs 10 categorized as "Surgical procedure"
- Likely due to anesthesia procedures (6 found) which are markers but not primary surgical procedures

## Top 15 Procedures by Frequency

| Procedure | Count | Category |
|-----------|-------|----------|
| IMMUNIZ,ADMIN,EACH ADDL | 10 | Diagnostic |
| OP CARD ECHOCARDIOGRAM NON-SEDATED | 9 | Diagnostic |
| ANES PERFORM INJ ANESTHETIC AGENT FEMORAL NERVE SINGLE | 6 | Surgical marker |
| IMMUNIZ, ADMIN,SINGLE | 6 | Diagnostic |
| BRIEF EMOTIONAL/BEHAVIORAL ASSESSMENT | 5 | Diagnostic |
| SURGICAL CASE REQUEST ORDER | 4 | Administrative |
| SCREENING TEST VISUAL ACUITY QUANTITATIVE BILAT | 4 | Diagnostic |
| STRTCTC CPTR ASSTD PX CRANIAL INTRADURAL | 2 | Surgical |
| VENTRICULOCISTERNOSTOMY 3RD VNTRC * | 2 | Surgical |
| SCREENING TEST PURE TONE AIR ONLY | 2 | Diagnostic |
| ECG ROUTINE ECG W/LEAST 12 LDS W/I* | 1 | Diagnostic |
| CAPILLARY, BLOOD COLLECTION | 1 | Diagnostic |
| UNLIST MODALITY SPEC TYPE&TIME CONSTANT ATTENDCE | 1 | Unknown |
| VISUAL FIELD XM UNI/BI W/INTERP EXTENDED EXAM | 1 | Diagnostic |
| EEG: CONTINUOUS MONITORING 12-24 HOURS | 1 | Diagnostic |

### Key Observations:
1. **Immunizations dominate** (16 total)
2. **Echocardiograms are frequent** (9 total) - likely cardiac monitoring
3. **Anesthesia procedures = 6** - markers of 3 probable surgical events
4. **True surgical procedures = 4** (STRTCTC CPTR, VENTRICULOCISTERNOSTOMY x2, CRANIECTOMY)
5. **Routine screenings** (vision, hearing, behavioral) are common

## Surgical Procedure Deep Dive

### Surgical Procedures (category_coding_display = "Surgical procedure")

**Total**: 10 procedures categorized as surgical

**Limitations**: Most lack explicit dates in performed_period_start field
- Only 8/72 total procedures have dates
- Cannot determine which 8 dated procedures are surgical without manual inspection

### Anesthesia Procedures (Surgical Markers)

**Total**: 6 procedures with "ANES" in code_coding_display

| Procedure | Count |
|-----------|-------|
| ANES PERFORM INJ ANESTHETIC AGENT FEMORAL NERVE SINGLE | 6 |

**Interpretation**: 
- Anesthesia procedures occur alongside surgeries
- 6 anesthesia procedures likely mark 3 surgical events (pre + post anesthesia per surgery)

### Expected Surgical Events

Based on patient's oncology history (medulloblastoma):
1. **Initial tumor resection** (2018)
2. **Recurrence resection** (2021)
3. **Possible additional procedures** (shunt placement, biopsies, etc.)

**Validation Needed**: Cross-reference with:
- "Surgery Log" encounters (4 found in encounters staging file)
- Operative report dates
- Diagnosis dates (2018-03-26 initial, 2021-01-13 recurrence)

### True Surgical Procedures by Code

| Code Description | Type |
|------------------|------|
| STRTCTC CPTR ASSTD PX CRANIAL INTRADURAL (x2) | Intracranial surgery |
| VENTRICULOCISTERNOSTOMY 3RD VNTRC * (x2) | Shunt/CSF diversion |
| CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION | Tumor resection |
| CRANIECTOMY W/EXCISION TUMOR/LESION SKULL | Tumor excision |
| SURGICAL CASE REQUEST ORDER (x4) | Administrative |

**Note**: "SURGICAL CASE REQUEST ORDER" appears to be an administrative order type, not a procedure itself.

## Metadata Coverage Analysis

### High Coverage Fields (>80%)
- **category_coding_display**: 100% - Excellent for surgical filtering
- **code_coding_display**: 98.6% - Excellent for procedure identification
- **reason_code_text**: 83.3% - Good for understanding clinical context

### Moderate Coverage (30-80%)
- **report_reference**: 50% - Half of procedures have linked documentation
- **encounter_reference**: 50% - Half link to encounters
- **performer_actor_display**: 30.6% - Provider info for major procedures only

### Sparse Coverage (<30%)
- **performed_period_start**: 11% - **MAJOR GAP**: Most procedures lack dates
- **body_site_text**: 8.3% - Anatomical location rarely documented
- **performed_date_time**: 11% - Sparse, use period_start instead

### Critical Issue: Missing Dates

**Only 8/72 procedures (11%) have dates** in performed_period_start field.

**Implications**:
- Cannot create timeline for 89% of procedures
- Cannot calculate age_at_procedure for 89% of procedures
- Must rely on encounter linkage for timing of undated procedures

**Workaround Strategies**:
1. **Use encounter_reference** to link to encounters with dates
2. **Use report dates** from procedure_report linkages
3. **Use DiagnosticReport.effective dates** for diagnostic procedures
4. **Manual review** of specific surgical procedures

## Downstream Linkage Opportunities

### 1. Link to Encounters (50% have encounter_reference)
```python
# Merge with encounters to get dates for undated procedures
procedures_with_encounter_dates = pd.merge(
    procedures_df,
    encounters_df[['encounter_fhir_id', 'encounter_date']],
    left_on='encounter_reference',
    right_on='encounter_fhir_id',
    how='left'
)
```

### 2. Link to Operative Reports (50% have report_reference)
```python
# Extract DocumentReference IDs
procedure_reports = procedures_df[procedures_df['report_reference'].notna()]
report_ids = procedure_reports['report_reference'].str.split(' | ').explode()

# Query DocumentReference table for report dates and content
```

### 3. Link to DiagnosticReport (for diagnostic procedures)
```sql
SELECT p.procedure_fhir_id, dr.effective_date_time, dr.code_text
FROM procedure p
JOIN diagnostic_report dr ON p.encounter_reference = dr.encounter_reference
WHERE p.category_coding_display = 'Diagnostic procedure'
```

## Filtering Recommendations

### For Surgical Analysis

**Include**:
```python
surgical_procedures = df[
    (df['category_coding_display'] == 'Surgical procedure') |
    (df['code_coding_display'].str.contains('CRANIOTOMY|CRANIECTOMY|RESECTION', case=False, na=False))
]
```

**Exclude**:
- SURGICAL CASE REQUEST ORDER (administrative, not procedures)
- Pure anesthesia procedures (markers only, not primary procedures)

**Expected Result**: 6-8 true surgical procedures

### For Diagnostic Analysis

**Include**:
```python
diagnostic_procedures = df[
    df['category_coding_display'] == 'Diagnostic procedure'
]
```

**Result**: 62 procedures

### For Anesthesia Markers

**Include**:
```python
anesthesia_procedures = df[
    df['code_coding_display'].str.contains('ANES', case=False, na=False)
]
```

**Use Case**: Identify surgical events even when primary procedure lacks date

## Date Resolution Strategy

### Priority Order for Dating Procedures:

1. **performed_period_start** (if not NULL)
2. **performed_date_time** (if period_start NULL)
3. **Encounter date** (via encounter_reference linkage)
4. **Report date** (via report_reference → DocumentReference.date)
5. **DiagnosticReport effective date** (for diagnostic procedures)
6. **Inferred from clinical timeline** (last resort)

### Implementation:
```python
# Create best_available_date column
df['best_available_date'] = df['performed_period_start'].fillna(
    df['performed_date_time']
).fillna(
    df['encounter_date']  # from encounter linkage
).fillna(
    df['report_date']  # from report linkage
)

# Calculate age
df['age_at_procedure_days'] = (
    pd.to_datetime(df['best_available_date']) - 
    pd.to_datetime('2005-05-13')
).dt.days
```

## Known Issues & Limitations

### Issue 1: Sparse Date Coverage
- **Impact**: Cannot create accurate procedure timeline for most procedures
- **Severity**: HIGH
- **Mitigation**: Use encounter linkage + report linkage

### Issue 2: Anesthesia as Separate Procedures
- **Impact**: Anesthesia procedures counted separately from primary surgical procedures
- **Severity**: MEDIUM
- **Mitigation**: Use anesthesia as marker, manually link to primary procedure

### Issue 3: Administrative Orders Included
- **Impact**: "SURGICAL CASE REQUEST ORDER" is not a procedure itself
- **Severity**: LOW
- **Mitigation**: Filter by category or exclude by code

### Issue 4: Duplicate Procedures
- **Impact**: Some procedures appear twice (STRTCTC CPTR, VENTRICULOCISTERNOSTOMY)
- **Severity**: MEDIUM
- **Interpretation**: May represent staged procedures or separate events
- **Action**: Investigate dates (if available) to determine if duplicates or separate events

### Issue 5: Body Site Sparseness
- **Impact**: Only 8.3% have anatomical location documentation
- **Severity**: LOW
- **Mitigation**: Anatomical location is implicit in many procedure codes (e.g., "CRANIOTOMY" = cranial)

## Validation Against Clinical Timeline

### Known Patient History:
- **Initial Diagnosis**: 2018-03-26 (medulloblastoma)
- **Expected Initial Surgery**: ~May 2018
- **Recurrence Diagnosis**: 2021-01-13
- **Expected Recurrence Surgery**: ~March 2021

### Dated Procedures (8 total):
- **Date range**: 2018-05-28 to 2021-03-16
- **Aligns with**: Expected surgical timeframes

**Hypothesis**: The 8 dated procedures likely include:
1. Initial tumor resection (May 2018)
2. Recurrence resection (March 2021)
3. Associated procedures (shunt placement, etc.)

**Validation Needed**: Cross-reference with:
1. Encounters staging file (4 "Surgery Log" encounters found)
2. Operative reports (via report_reference)
3. Chemotherapy start dates (typically 2-4 weeks post-surgery)

## Next Steps

### Immediate Actions:
1. **Link to Encounters**: Merge with ALL_ENCOUNTERS_METADATA_C1277724.csv on encounter_reference
2. **Extract Report Dates**: Query DocumentReference table using report_reference
3. **Cross-validate Surgical Events**: Compare surgical procedures to "Surgery Log" encounters
4. **Manual Review**: Inspect the 8 dated procedures to identify primary surgical events

### Analysis Workflow:
```python
# 1. Load staging files
procedures = pd.read_csv('ALL_PROCEDURES_METADATA_C1277724.csv')
encounters = pd.read_csv('ALL_ENCOUNTERS_METADATA_C1277724.csv')

# 2. Link procedures to encounters
merged = procedures.merge(
    encounters[['encounter_fhir_id', 'encounter_date', 'class_display']],
    left_on='encounter_reference',
    right_on='encounter_fhir_id',
    how='left'
)

# 3. Filter for surgical events
surgical = merged[
    (merged['category_coding_display'] == 'Surgical procedure') &
    (merged['class_display'] == 'Surgery Log')
]

# 4. Identify primary surgical dates
surgical_dates = surgical['encounter_date'].dropna().unique()
```

### Documentation Updates:
1. Create PROCEDURES_COLUMN_REFERENCE.md (detailed column guide)
2. Update SESSION_SUMMARY with procedures findings
3. Document surgical procedure validation results

## Related Documentation

- `PROCEDURES_SCHEMA_DISCOVERY.md` - Complete table structures
- `ENCOUNTERS_STAGING_FILE_ANALYSIS.md` - For encounter linkage
- `COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md` - Surgical documentation patterns
- `PROCEDURES_COLUMN_REFERENCE.md` - Detailed column definitions (next)
