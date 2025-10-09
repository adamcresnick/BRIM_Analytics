# Procedures Schema Discovery

## Overview

Comprehensive documentation of all procedure-related tables in the FHIR v2 database (`fhir_v2_prd_db`), their structures, and relationships for patient C1277724.

**Discovery Date**: 2024
**Database**: fhir_v2_prd_db (AWS Athena)
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

## Summary Statistics

- **Total Procedure Tables**: 22
- **Main Table Columns**: 38
- **Total Procedures Found**: 72
- **Date Range**: 2005-06-03 to 2024-04-30
- **All Procedures Completed**: 100% (72/72)

## Procedure Tables Discovered

### 1. `procedure` - Main Table (38 columns)

Primary table containing core procedure information.

**Columns**:
1. `id` - Unique FHIR resource ID (procedure_fhir_id)
2. `resource_type` - Always "Procedure"
3. `status` - completed, in-progress, not-done, etc.
4. `status_reason_text` - Why procedure was cancelled/not done
5. `category_text` - Human-readable category
6. `code_text` - Human-readable procedure name
7. `subject_reference` - Patient FHIR ID
8. `subject_type` - Usually "Patient"
9. `subject_display` - Patient display name
10. `encounter_reference` - Link to encounter FHIR ID
11. `encounter_type` - Usually "Encounter"
12. `encounter_display` - Encounter description
13. `performed_date_time` - Single datetime (sparse - only 8/72)
14. `performed_period_start` - Period start datetime
15. `performed_period_end` - Period end datetime
16. `performed_string` - Free-text timing description
17-20. `performed_age_*` - Age at procedure (value, unit, system, code)
21-28. `performed_range_*` - Range of timing (low/high value, unit, system, code)
29. `recorder_reference` - Who recorded the procedure
30. `recorder_type` - Usually "Practitioner"
31. `recorder_display` - Recorder name
32. `asserter_reference` - Who asserted the procedure occurred
33. `asserter_type` - Usually "Practitioner"
34. `asserter_display` - Asserter name
35. `location_reference` - Where procedure occurred
36. `location_type` - Usually "Location"
37. `location_display` - Location name
38. `outcome_text` - Procedure outcome description

**Key Observations**:
- **performed_date_time** is sparse (only 11% populated)
- **performed_period_start/end** are more reliable for timing (100% for dated procedures)
- All 72 procedures have status = "completed"
- encounter_reference links to encounters (50% populated)

### 2. `procedure_code_coding` - CPT/HCPCS Codes (5 columns)

Contains structured procedure codes (CPT, HCPCS, LOINC, etc.)

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `code_coding_system` - Code system URI
   - `http://www.ama-assn.org/go/cpt` (CPT codes - 58/72, 81%)
   - `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580` (Epic internal - 13/72, 18%)
   - `http://loinc.org` (LOINC - 1/72, 1%)
4. `code_coding_code` - Actual code value
5. `code_coding_display` - Human-readable code description

**Sample Codes**:
- CPT codes for immunizations (IMMUNIZ,ADMIN,EACH ADDL)
- Echocardiogram codes (OP CARD ECHOCARDIOGRAM NON-SEDATED)
- Anesthesia codes (ANES PERFORM INJ ANESTHETIC AGENT FEMORAL NERVE SINGLE)
- Surgical codes (CRANIECTOMY, VENTRICULOCISTERNOSTOMY, etc.)

**Coverage**: 71/72 procedures have code_coding (98.6%)

### 3. `procedure_category_coding` - Procedure Categories (5 columns)

Classifies procedures into categories (surgical, diagnostic, therapeutic, etc.)

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `category_coding_system` - Category code system
4. `category_coding_code` - Category code
5. `category_coding_display` - Category description

**Categories Found**:
- **Diagnostic procedure**: 62/72 (86%)
- **Surgical procedure**: 10/72 (14%)

**Coverage**: 72/72 procedures have categories (100%)

### 4. `procedure_body_site` - Anatomical Locations (4 columns)

Specifies anatomical locations where procedures were performed

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `body_site_coding` - Structured body site codes (JSON)
4. `body_site_text` - Human-readable body site description

**Coverage**: 6/72 procedures have body site information (8.3%)

**Note**: Most procedures do not have explicit body site documentation, likely because location is implicit in procedure code.

### 5. `procedure_performer` - Surgeons/Providers (7 columns)

Documents who performed the procedure

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `performer_function_text` - Role description
4. `performer_actor_reference` - Provider FHIR reference
5. `performer_actor_type` - Always "Practitioner"
6. `performer_actor_display` - Provider name
7. `performer_on_behalf_of_reference` - Organization reference
8. `performer_on_behalf_of_display` - Organization name

**Coverage**: 22/72 procedures have performer information (30.6%)

**Note**: Performer data appears primarily for surgical procedures and major interventions. Most routine procedures (immunizations, screenings) lack performer documentation.

### 6. `procedure_reason_code` - Indications (3 columns)

Captures why the procedure was performed

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `reason_code_coding` - Structured reason codes (JSON)
4. `reason_code_text` - Human-readable reason

**Coverage**: 60/72 procedures have reason documentation (83.3%)

**Note**: High coverage rate suggests reason is well-documented in this patient's records.

### 7. `procedure_report` - Operative Reports (4 columns)

Links procedures to operative reports and documentation

**Columns**:
1. `id` - Unique row ID
2. `procedure_id` - Foreign key to procedure.id
3. `report_reference` - DocumentReference FHIR ID
4. `report_type` - Usually "DocumentReference"
5. `report_display` - Report title/description

**Coverage**: 36/72 procedures have linked reports (50%)

**Note**: High coverage suggests many procedures have associated documentation. The 998 report linkages for 36 procedures indicates many procedures have multiple related documents.

### 8-22. Additional Subtables (Sparse)

**procedure_based_on** (5 columns):
- Links procedures to care plans or service requests
- Foreign key: based_on_reference

**procedure_complication** (4 columns):
- Documents procedure complications
- Fields: complication_coding, complication_text

**procedure_complication_detail** (structure unknown - no data):
- Detailed complication information

**procedure_focal_device** (7 columns):
- Devices used during procedure
- Fields: focal_device_action_*, focal_device_manipulated_*

**procedure_follow_up** (structure unknown - no data):
- Follow-up procedures or actions

**procedure_identifier** (8 columns):
- Additional identifiers for procedures
- Fields: identifier_use, identifier_type_text, identifier_system, identifier_value, identifier_period_*

**procedure_instantiates_canonical** (structure unknown):
- Links to protocol definitions

**procedure_instantiates_uri** (structure unknown):
- External protocol URIs

**procedure_note** (structure unknown):
- Procedure notes and comments

**procedure_outcome_coding** (structure unknown):
- Structured procedure outcomes

**procedure_part_of** (structure unknown):
- Links to parent procedures

**procedure_reason_reference** (structure unknown):
- Links reasons to other resources

**procedure_status_reason_coding** (structure unknown):
- Structured status reasons

**procedure_used_code** (structure unknown):
- Codes for items used during procedure

**procedure_used_reference** (structure unknown):
- References to items used during procedure

## Key Relationships

### Procedure → Encounter
```sql
SELECT p.*, e.class_display, e.period_start
FROM procedure p
LEFT JOIN encounter e ON p.encounter_reference = e.id
WHERE p.subject_reference = 'PATIENT_FHIR_ID'
```
- 50% of procedures link to encounters

### Procedure → Codes
```sql
SELECT p.*, pcc.code_coding_code, pcc.code_coding_display
FROM procedure p
JOIN procedure_code_coding pcc ON p.id = pcc.procedure_id
WHERE p.subject_reference = 'PATIENT_FHIR_ID'
```
- 98.6% of procedures have CPT/HCPCS codes

### Procedure → Reports
```sql
SELECT p.*, pr.report_reference, pr.report_display
FROM procedure p
JOIN procedure_report pr ON p.id = pr.procedure_id
WHERE p.subject_reference = 'PATIENT_FHIR_ID'
```
- 50% of procedures have linked documentation

## Surgical Procedure Identification

### Method 1: Category Coding
```sql
SELECT p.*
FROM procedure p
JOIN procedure_category_coding pcat ON p.id = pcat.procedure_id
WHERE pcat.category_coding_display = 'Surgical procedure'
```
**Result**: 10 surgical procedures

### Method 2: Keyword Detection
Search code_coding_display for surgical keywords:
- craniotomy, craniectomy, resection, excision, biopsy
- surgery, surgical, anesthesia, anes, oper

**Result**: 11 procedures with surgical keywords (includes anesthesia procedures)

### Method 3: Anesthesia as Marker
Anesthesia procedures often indicate surgical events:
```sql
SELECT p.*
FROM procedure p
JOIN procedure_code_coding pcc ON p.id = pcc.procedure_id
WHERE pcc.code_coding_display LIKE '%ANES%'
```
**Result**: 6 anesthesia procedures (likely markers of 3 surgical events based on dates)

### Recommended Approach
**Combine all three methods**:
1. Start with category_coding_display = 'Surgical procedure' (authoritative)
2. Add anesthesia procedures as surgical markers
3. Manual review of procedures with surgical keywords but not categorized as surgical

## Sample Queries

### All Procedures for Patient
```sql
SELECT 
    p.id as procedure_fhir_id,
    p.status,
    p.performed_period_start,
    p.performed_period_end,
    p.code_text,
    p.category_text,
    p.encounter_reference
FROM fhir_v2_prd_db.procedure p
WHERE p.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
ORDER BY p.performed_period_start
```

### Surgical Procedures with Codes
```sql
SELECT 
    p.id,
    p.performed_period_start,
    p.code_text,
    pcc.code_coding_code,
    pcc.code_coding_display,
    pcat.category_coding_display
FROM fhir_v2_prd_db.procedure p
JOIN fhir_v2_prd_db.procedure_code_coding pcc ON p.id = pcc.procedure_id
JOIN fhir_v2_prd_db.procedure_category_coding pcat ON p.id = pcat.procedure_id
WHERE p.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND pcat.category_coding_display = 'Surgical procedure'
ORDER BY p.performed_period_start
```

### Procedures with Operative Reports
```sql
SELECT 
    p.id,
    p.performed_period_start,
    p.code_text,
    pr.report_reference,
    pr.report_display
FROM fhir_v2_prd_db.procedure p
JOIN fhir_v2_prd_db.procedure_report pr ON p.id = pr.procedure_id
WHERE p.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    AND pr.report_reference IS NOT NULL
ORDER BY p.performed_period_start
```

## Data Quality Notes

### Well-Populated Fields (>80%)
- `procedure_fhir_id` - 100%
- `status` - 100%
- `category_coding_display` - 100%
- `code_coding_display` - 98.6%
- `reason_code_text` - 83.3%

### Moderately Populated (30-80%)
- `report_reference` - 50%
- `encounter_reference` - 50%
- `performer_actor_display` - 30.6%

### Sparse Fields (<30%)
- `performed_date_time` - 11%
- `body_site_text` - 8.3%
- `location_display` - Unknown (not analyzed)
- `outcome_text` - Unknown (not analyzed)

### Timing Data Strategy
- **Primary**: Use `performed_period_start` and `performed_period_end`
- **Fallback**: Use `performed_date_time` if period fields are NULL
- **Note**: Some procedures may only have encounter-based timing

## Important Findings

### 1. Procedure Date Coverage
- Only 8/72 procedures have explicit dates in performed_period_start (11%)
- Most procedures appear to be documentation artifacts without explicit timing
- Surgical procedures (category = 'Surgical procedure') have better date coverage

### 2. Surgical Procedures
- **10 categorized as "Surgical procedure"**
- **6 anesthesia procedures** (markers of surgical events)
- **Key surgical codes**: CRANIECTOMY, VENTRICULOCISTERNOSTOMY, STRTCTC CPTR ASSTD PX

### 3. Diagnostic Dominance
- 86% of procedures are categorized as "Diagnostic procedure"
- Includes: immunizations, screenings, echocardiograms, assessments

### 4. Operative Reports
- 50% of procedures have linked reports (good coverage)
- 998 report linkages for 36 procedures = avg 27.7 reports per procedure
- Suggests extensive documentation for major procedures

### 5. Reason Documentation
- 83.3% coverage for procedure reasons
- Indicates high data quality for clinical decision-making documentation

## Next Steps

1. **Cross-reference with Encounters**: Match surgical procedures to "Surgery Log" encounters
2. **Extract Operative Reports**: Use procedure_report.report_reference to get DocumentReference IDs
3. **Age Calculations**: Compute age_at_procedure_days for all dated procedures
4. **Validation**: Compare surgical procedure dates against known diagnosis dates (2018-03-26 initial, 2021-01-13 recurrence)
5. **Filter for Analysis**: Create filtered datasets for surgical vs diagnostic procedures

## Related Documentation

- `ENCOUNTERS_SCHEMA_DISCOVERY.md` - For encounter linkage patterns
- `COMPLETE_CHEMOTHERAPY_DETECTION_ACROSS_TABLES.md` - For treatment detection strategies
- `COMPREHENSIVE_SURGICAL_CAPTURE_GUIDE.md` - For surgical documentation patterns
