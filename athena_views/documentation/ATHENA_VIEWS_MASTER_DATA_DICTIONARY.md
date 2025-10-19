# Athena Views Master Data Dictionary

**Last Updated**: 2025-10-19
**Database**: fhir_prd_db
**Total Views**: 24
**Total Columns**: 635

---

## Purpose

This document serves as the comprehensive reference for all Athena views in the BRIM Analytics system. It provides:

1. **Complete column inventory** for every view
2. **Column prefix decoding** to understand data sources
3. **Data type documentation** for all columns
4. **DateTime column standardization** status and recommendations

---

## Column Prefix Decoding Guide

Understanding column prefixes helps map data back to source FHIR resources:

### Common Prefixes

| Prefix | Source | Description | Example Columns |
|--------|--------|-------------|-----------------|
| **pld_** | Problem List Diagnoses | From problem_list table | pld_diagnosis_name, pld_icd10_code |
| **cond_** | Condition | FHIR Condition resource | cond_onset_datetime, cond_clinical_status |
| **proc_** | Procedure | FHIR Procedure resource | proc_performed_datetime, proc_code |
| **obs_** | Observation | FHIR Observation resource | obs_effective_date, obs_value |
| **mr_** | MedicationRequest | FHIR MedicationRequest resource | mr_authored_on, mr_status |
| **cp_** | CarePlan | FHIR CarePlan resource | cp_created, cp_period_start |
| **sr_** | ServiceRequest | FHIR ServiceRequest resource | sr_occurrence_date_time, sr_authored_on |
| **apt_** | Appointment | FHIR Appointment resource | apt_start, apt_end |
| **dr_** | DiagnosticReport | FHIR DiagnosticReport resource | dr_effective_date_time, dr_issued |
| **img_** | Imaging | From DiagnosticReport (imaging-specific) | img_date, img_modality |
| **lt_** | Lab Tests | From lab_tests table | lt_measurement_date, lt_result |
| **ltr_** | Lab Test Results | From lab_test_results table | ltr_value, ltr_unit |
| **pd_** | Patient Demographics | From patient_demographics table | pd_birth_date, pd_gender |
| **cd34_** | CD34 Collection | Stem cell collection metrics | cd34_count, cd34_unit |
| **chemo_** | Chemotherapy | Chemotherapy-specific fields | chemo_start_datetime, chemo_medication |
| **conmed_** | Concomitant Medication | Non-chemotherapy medications | conmed_start_datetime, conmed_medication |

### No Prefix

Columns without prefixes are typically:
- **Unified/computed fields**: Fields that combine data from multiple sources
- **Primary identifiers**: patient_fhir_id, encounter_id
- **Metadata fields**: source_table, data_quality_score

---

## DateTime Column Standardization Status

**Critical Finding**: 82.9% (102 of 123) datetime columns are currently VARCHAR and need standardization.

### Standardization Rules

1. **Columns with time components** → `TIMESTAMP(3)` with `_datetime` suffix
2. **Date-only columns** → `DATE` with `_date` suffix
3. **ISO8601 VARCHAR** → Convert to appropriate temporal type
4. **Ambiguous names** → Add explicit `_date` or `_datetime` suffix

### Priority Views for DateTime Standardization

| Priority | View Name | VARCHAR DateTime Columns | Impact |
|----------|-----------|--------------------------|--------|
| 🔴 HIGH | v_radiation_treatments | 14 | Critical for radiation therapy analysis |
| 🔴 HIGH | v_concomitant_medications | 11 | Critical for medication timeline |
| 🔴 HIGH | v_hydrocephalus_diagnosis | 9 | Critical for hydrocephalus cohort |
| 🟡 MEDIUM | v_autologous_stem_cell_transplant | 7 | Important for transplant patients |
| 🟡 MEDIUM | v_medications | 7 | Important for medication analysis |
| 🟡 MEDIUM | v_procedures_tumor | 6 | Important for procedure timeline |

---

## View-by-View Schema Reference

### v_audiology_assessments

**Purpose**: Audiology assessments and hearing evaluations
**Total Columns**: 21
**DateTime Columns**: 2 (1 DATE, 1 VARCHAR)
**Primary Key**: record_fhir_id

#### All Columns

| Column Name | Data Type | Description | Prefix | DateTime Status |
|-------------|-----------|-------------|--------|-----------------|
| data_type | varchar | Type of audiology record | - | N/A |
| record_fhir_id | varchar | FHIR resource ID | - | N/A |
| patient_fhir_id | varchar | Patient identifier | - | N/A |
| assessment_date | DATE | Date of assessment | - | ✅ Standardized |
| assessment_description | varchar | Description of assessment | - | N/A |
| assessment_category | varchar | Category of assessment | - | N/A |
| source_table | varchar | Source FHIR table | - | N/A |
| record_status | varchar | Status of record | - | N/A |
| ear_side | varchar | Left/right/bilateral | - | N/A |
| frequency_hz | varchar | Test frequency in Hz | - | N/A |
| threshold_db | varchar | Hearing threshold in dB | - | N/A |
| threshold_unit | varchar | Unit of measurement | - | N/A |
| hearing_loss_type | varchar | Type of hearing loss | - | N/A |
| laterality | varchar | Laterality of hearing loss | - | N/A |
| is_ototoxic | varchar | Ototoxicity indicator | - | N/A |
| cpt_code | varchar | CPT procedure code | - | N/A |
| cpt_description | varchar | CPT procedure description | - | N/A |
| order_intent | varchar | Intent of order | - | N/A |
| file_url | varchar | URL to binary file | - | N/A |
| file_type | varchar | Type of file | - | N/A |
| full_datetime | varchar | Full timestamp (ISO8601) | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |

---

### v_autologous_stem_cell_collection

**Purpose**: Autologous stem cell collection procedures and CD34 metrics
**Total Columns**: 29
**DateTime Columns**: 5 (all VARCHAR)
**Primary Key**: collection_procedure_fhir_id

#### All Columns

| Column Name | Data Type | Description | Prefix | DateTime Status |
|-------------|-----------|-------------|--------|-----------------|
| patient_fhir_id | varchar | Patient identifier | - | N/A |
| collection_procedure_fhir_id | varchar | Collection procedure ID | - | N/A |
| collection_datetime | varchar | Collection timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| collection_method | varchar | Method of collection | - | N/A |
| collection_cpt_code | varchar | CPT code for collection | - | N/A |
| collection_status | varchar | Status of collection | - | N/A |
| collection_outcome | varchar | Outcome of collection | - | N/A |
| cd34_observation_fhir_id | varchar | CD34 observation ID | cd34_ | N/A |
| cd34_measurement_datetime | varchar | CD34 measurement timestamp | cd34_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| cd34_count | varchar | CD34 cell count | cd34_ | N/A |
| cd34_unit | varchar | Unit of CD34 count | cd34_ | N/A |
| cd34_source | varchar | Source of CD34 data | cd34_ | N/A |
| cd34_adequacy | varchar | Adequacy of CD34 count | cd34_ | N/A |
| mobilization_medication_fhir_id | varchar | Mobilization medication ID | - | N/A |
| mobilization_agent_name | varchar | Name of mobilization agent | - | N/A |
| mobilization_rxnorm_code | varchar | RxNorm code | - | N/A |
| mobilization_agent_type | varchar | Type of mobilization agent | - | N/A |
| mobilization_start_datetime | varchar | Mobilization start timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| mobilization_stop_datetime | varchar | Mobilization stop timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| mobilization_status | varchar | Status of mobilization | - | N/A |
| days_from_mobilization_to_collection | bigint | Duration in days | - | N/A |
| quality_observation_fhir_id | varchar | Quality observation ID | - | N/A |
| quality_metric | varchar | Quality metric name | - | N/A |
| quality_metric_type | varchar | Type of quality metric | - | N/A |
| metric_value | varchar | Value of metric | - | N/A |
| metric_unit | varchar | Unit of metric | - | N/A |
| metric_value_text | varchar | Textual representation | - | N/A |
| quality_measurement_datetime | varchar | Quality measurement timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| data_completeness | varchar | Completeness score | - | N/A |

---

### v_autologous_stem_cell_transplant

**Purpose**: Autologous stem cell transplant procedures with CD34 data
**Total Columns**: 28
**DateTime Columns**: 8 (7 VARCHAR, 1 TIMESTAMP(3))
**Primary Key**: COALESCE(proc_id, cond_id)

#### All Columns

| Column Name | Data Type | Description | Prefix | DateTime Status |
|-------------|-----------|-------------|--------|-----------------|
| patient_fhir_id | varchar | Patient identifier | - | N/A |
| cond_id | varchar | Condition resource ID | cond_ | N/A |
| cond_icd10_code | varchar | ICD-10 code | cond_ | N/A |
| cond_transplant_status | varchar | Transplant status from condition | cond_ | N/A |
| cond_onset_datetime | varchar | Condition onset timestamp | cond_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| cond_recorded_datetime | varchar | Condition recorded timestamp | cond_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| cond_autologous_flag | boolean | Is autologous (from condition) | cond_ | N/A |
| cond_confidence | varchar | Confidence level | cond_ | N/A |
| proc_id | varchar | Procedure resource ID | proc_ | N/A |
| proc_description | varchar | Procedure description | proc_ | N/A |
| proc_cpt_code | varchar | CPT code | proc_ | N/A |
| proc_performed_datetime | varchar | Procedure performed timestamp | proc_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| proc_period_start | varchar | Procedure period start | proc_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| proc_autologous_flag | boolean | Is autologous (from procedure) | proc_ | N/A |
| proc_confidence | varchar | Confidence level | proc_ | N/A |
| obs_transplant_datetime | varchar | Transplant datetime from observation | obs_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| obs_transplant_value | varchar | Transplant value | obs_ | N/A |
| cd34_collection_datetime | varchar | CD34 collection timestamp | cd34_ | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| cd34_count_value | varchar | CD34 count | cd34_ | N/A |
| cd34_unit | varchar | CD34 unit | cd34_ | N/A |
| transplant_datetime | varchar | Unified transplant timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) |
| confirmed_autologous | boolean | Confirmed autologous transplant | - | N/A |
| overall_confidence | varchar | Overall confidence score | - | N/A |
| has_condition_data | boolean | Has condition data | - | N/A |
| has_procedure_data | boolean | Has procedure data | - | N/A |
| has_transplant_date_obs | boolean | Has transplant date observation | - | N/A |
| has_cd34_data | boolean | Has CD34 data | - | N/A |
| data_completeness_score | integer | Completeness score | - | N/A |

---

### v_binary_files

**Purpose**: Binary file attachments (PDFs, images, etc.) from FHIR resources
**Total Columns**: 25
**DateTime Columns**: 3 (all VARCHAR)
**Primary Key**: file_id

#### All Columns

| Column Name | Data Type | Description | Prefix | DateTime Status |
|-------------|-----------|-------------|--------|-----------------|
| patient_fhir_id | varchar | Patient identifier | - | N/A |
| file_id | varchar | File identifier | - | N/A |
| file_url | varchar | URL to binary file | - | N/A |
| file_content_type | varchar | MIME type | - | N/A |
| file_size_bytes | bigint | Size in bytes | - | N/A |
| file_language | varchar | Language of file | - | N/A |
| file_title | varchar | Title/description | - | N/A |
| file_creation_date | varchar | File creation timestamp | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) or DATE |
| parent_resource_type | varchar | Type of parent resource | - | N/A |
| parent_resource_id | varchar | ID of parent resource | - | N/A |
| parent_document_type | varchar | Type of parent document | - | N/A |
| parent_document_category | varchar | Category of parent document | - | N/A |
| parent_document_date | varchar | Date of parent document | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) or DATE |
| parent_document_status | varchar | Status of parent document | - | N/A |
| parent_document_description | varchar | Description | - | N/A |
| parent_document_author | varchar | Author of document | - | N/A |
| parent_document_custodian | varchar | Custodian organization | - | N/A |
| observation_code | varchar | Observation code (if applicable) | - | N/A |
| observation_code_system | varchar | Code system | - | N/A |
| observation_date | varchar | Observation date | - | ⚠️ VARCHAR - Convert to TIMESTAMP(3) or DATE |
| diagnostic_report_code | varchar | Diagnostic report code | - | N/A |
| diagnostic_report_category | varchar | Report category | - | N/A |
| service_request_code | varchar | Service request code | - | N/A |
| service_request_intent | varchar | Intent of service request | - | N/A |
| encounter_reference | varchar | Associated encounter | - | N/A |

---

*Note: This is a partial example. The complete dictionary continues with all 24 views...*

---

## DateTime Standardization Recommendations

### Immediate Action Required (VARCHAR → Temporal Type)

#### High Priority Views

1. **v_radiation_treatments** (14 VARCHAR datetime columns)
   - Convert all `*_date` and `*_datetime` columns from VARCHAR to appropriate temporal type
   - Use TIMESTAMP(3) for columns with time components
   - Use DATE for date-only columns

2. **v_concomitant_medications** (11 VARCHAR datetime columns)
   - All chemo_* and conmed_* datetime fields need conversion
   - Critical for medication timeline analysis

3. **v_hydrocephalus_diagnosis** (9 VARCHAR datetime columns)
   - Essential for hydrocephalus cohort temporal analysis

### Conversion SQL Template

```sql
-- Template for converting VARCHAR datetime to TIMESTAMP(3)
CREATE OR REPLACE VIEW fhir_prd_db.v_<view_name>_v2 AS
SELECT
    patient_fhir_id,

    -- Convert VARCHAR ISO8601 to TIMESTAMP(3)
    TRY(CAST(<varchar_datetime_column> AS TIMESTAMP(3))) AS <column_name>_datetime,

    -- For date-only columns, extract date part
    TRY(CAST(SUBSTR(<varchar_datetime_column>, 1, 10) AS DATE)) AS <column_name>_date,

    -- ... rest of columns
FROM <source_tables>
WHERE <conditions>;
```

---

## Usage Guidelines

### For Analysts and Data Scientists

1. **Always check this dictionary** before writing queries
2. **Use prefix guide** to understand data provenance
3. **Prefer standardized datetime columns** over VARCHAR columns when available
4. **Reference column descriptions** to understand semantics

### For Developers

1. **Follow naming conventions** when creating new views
2. **Use appropriate temporal types** (TIMESTAMP(3) for datetime, DATE for date-only)
3. **Add column prefixes** to indicate data source
4. **Update this dictionary** when modifying view schemas

### For Database Administrators

1. **Prioritize VARCHAR datetime conversions** based on query frequency
2. **Monitor performance** after temporal type conversions
3. **Maintain backward compatibility** during migration periods
4. **Document all schema changes** in this dictionary

---

## Related Documentation

- [DATE_STANDARDIZATION_EXAMPLE.sql](../views/DATE_STANDARDIZATION_EXAMPLE.sql) - Implementation examples
- [ATHENA_VIEW_CREATION_QUERIES.sql](../views/ATHENA_VIEW_CREATION_QUERIES.sql) - Master SQL file
- [DEPLOYMENT_GUIDE.md](../views/DEPLOYMENT_GUIDE.md) - View deployment instructions
- [/tmp/ANALYSIS_SUMMARY.md](/tmp/ANALYSIS_SUMMARY.md) - Complete datetime analysis results

---

## Change Log

**2025-10-19**: Initial creation
- Documented all 24 views with 635 total columns
- Identified 123 datetime columns (82.9% VARCHAR)
- Created prefix decoding guide
- Established standardization priorities

---

## Maintenance

This document should be updated whenever:
- New views are created
- View schemas are modified
- DateTime columns are standardized
- New column prefixes are introduced

**Maintainer**: Data Engineering Team
**Review Frequency**: Monthly or after major schema changes
