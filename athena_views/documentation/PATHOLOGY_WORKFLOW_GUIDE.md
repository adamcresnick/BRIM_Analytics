# Pathology Diagnostics Workflow Guide

**Purpose**: Complete guide to pathology and diagnostic data extraction for tumor characterization
**Audience**: Data analysts, clinicians, researchers
**Last Updated**: 2025-10-30

---

## Table of Contents

1. [Overview](#overview)
2. [Data Sources](#data-sources)
3. [View Architecture](#view-architecture)
4. [Diagnostic Categories](#diagnostic-categories)
5. [Molecular Marker Extraction](#molecular-marker-extraction)
6. [Usage Examples](#usage-examples)
7. [Validation & Testing](#validation--testing)
8. [Clinical Context](#clinical-context)

---

## Overview

### What is v_pathology_diagnostics?

**v_pathology_diagnostics** is a comprehensive view that combines ALL pathology and diagnostic information for tumor assessment, going beyond diagnosis codes to include:

- ✅ Molecular testing results (IDH, MGMT, 1p/19q, BRAF, etc.)
- ✅ Surgical pathology observations (histology, grade, IHC)
- ✅ Procedure-linked pathology (frozen sections, biopsies)
- ✅ Free-text pathology narratives from diagnostic reports
- ✅ Care plan pathology notes
- ✅ Procedure notes with pathology content

### Why This View Matters

**Problem**: Diagnosis codes (ICD-10, SNOMED) alone are insufficient for comprehensive tumor characterization. Critical molecular and histologic details are scattered across:
- Molecular testing databases (molecular_tests, molecular_test_results)
- Clinical observations (observation table)
- Procedure records (procedure table)
- Narrative reports (diagnostic_report.conclusion)
- Care plan notes (care_plan.description)
- Procedure notes (procedure.note)

**Solution**: v_pathology_diagnostics unifies ALL pathology data into a single queryable view with:
- Standardized structure across all sources
- Automatic molecular marker extraction
- Specimen and procedure linkage
- Age-at-diagnostic calculations

### Key Features

1. **Multi-Source Integration** - 6 different data sources unified
2. **Narrative Text Extraction** - Captures free-text pathology embedded in FHIR resources
3. **Molecular Marker Flags** - Automatic extraction of IDH, MGMT, 1p/19q status
4. **Datetime Standardization** - All dates cast to TIMESTAMP(3)
5. **OID Decoding** - Human-readable coding system labels
6. **Procedure Linkage** - Links diagnostics to surgical procedures
7. **Specimen Tracking** - Links to specimen collection information

---

## Data Sources

### Source 1: Molecular Testing (molecular_test)

**From**: Materialized tables `molecular_tests` and `molecular_test_results`
**Contains**: DGD (Division of Genomic Diagnostics) molecular panels

**Key Fields**:
- `test_identifier`: DGD ID (e.g., %-GD-% pattern)
- `component_name`: Individual test components (e.g., "IDH1 R132 mutation")
- `result_value`: Test result narrative
- `specimen_types`: Tissue specimen types
- `linked_procedure`: Associated surgical procedure

**Example Data**:
```
Test: Solid Tumor Panel
Component: IDH1 R132 mutation
Result: Positive for IDH1 R132H mutation
```

**Typical Volume**: ~2,800 molecular tests per cohort

### Source 2: Pathology Observations (pathology_observation)

**From**: `observation` table filtered to pathology-related observations
**Contains**: Structured lab results, IHC, histology, molecular markers

**Key Fields**:
- `loinc_code`: Standard LOINC code for test
- `result_value`: Observation value (string, coded, or interpretation)
- `specimen_sites`: Where specimen was collected (e.g., "Brain")

**Common LOINC Codes**:
- 71190-5: MGMT gene methylation analysis
- 33747-1: Ki-67 proliferation index
- 59847-4: Histologic grade
- 88930-0: IDH gene targeted mutation analysis

**Example Data**:
```
Test: Ki-67 proliferation index
Result: 15%
```

**Typical Volume**: Variable, depends on structured lab data availability

### Source 3: Pathology Procedures (pathology_procedure)

**From**: `procedure` table filtered to pathology-related procedures
**Contains**: Biopsies, frozen sections, specimen processing

**Key Fields**:
- `cpt_code`: Procedure CPT code (88000-88399 pathology range)
- `diagnostic_name`: Procedure description
- `result_value`: Procedure outcome

**Common CPT Codes**:
- 61750: Stereotactic brain biopsy
- 88305: Surgical pathology Level IV (CNS biopsies)
- 88307: Surgical pathology Level V (CNS tumor resection)
- 88331: Frozen section, first specimen
- 88342: Immunohistochemistry, first stain

**Example Data**:
```
Procedure: Frozen section analysis
CPT: 88331
Result: High-grade glioma confirmed
```

**Typical Volume**: ~500-1,000 pathology procedures per cohort

### Source 4: Pathology Narrative Reports (pathology_narrative)

**From**: `diagnostic_report.conclusion` and `diagnostic_report.presented_form_data`
**Contains**: **Free-text pathology report summaries and full report text**

**Key Fields**:
- `diagnostic_name`: Report type (e.g., "Surgical Pathology Report")
- `result_value`: **Full narrative text from conclusion or report body**
- `test_identifier`: Service request identifier linking to order

**Narrative Text Fields Captured**:
- `diagnostic_report.conclusion` - Summary conclusion paragraph
- `diagnostic_report.presented_form_data` - Full report text if available

**Example Data**:
```
Report: Surgical Pathology Report
Narrative: "Tumor consistent with diffuse astrocytoma, IDH-mutant, CNS WHO Grade 2.
            Immunohistochemistry shows GFAP positive, IDH1 R132H mutant positive,
            p53 overexpression (70% of cells), ATRX loss, Ki-67 proliferation
            index approximately 5%."
```

**Pattern Matching**: Automatically extracts molecular markers from narrative:
- IDH mutation status
- MGMT methylation status
- 1p/19q codeletion status
- WHO grade
- Histologic type

**Exclusion**: Reports already captured in molecular_tests table (to avoid duplication)

**Typical Volume**: ~800-1,200 pathology reports per cohort

### Source 5: Care Plan Pathology Notes (care_plan_pathology_note)

**From**: `care_plan.description`
**Contains**: **Treatment planning notes that reference pathology findings**

**Key Fields**:
- `diagnostic_name`: Care plan title
- `result_value`: **Care plan description text**

**Example Data**:
```
Care Plan: Chemotherapy Protocol
Description: "Patient with newly diagnosed glioblastoma, IDH-wildtype, MGMT unmethylated.
              Plan to proceed with standard Stupp protocol (radiation + temozolomide)."
```

**Why Important**: Clinicians often summarize key pathology findings in care plans when documenting treatment decisions. This captures diagnoses and molecular status even if original pathology reports are in binary documents.

**Typical Volume**: ~100-300 care plans with pathology references per cohort

### Source 6: Procedure Pathology Notes (procedure_pathology_note)

**From**: `procedure.note` and `procedure.outcome_text`
**Contains**: **Intraoperative and postoperative notes with pathology findings**

**Key Fields**:
- `diagnostic_name`: Procedure name (e.g., "Craniotomy for tumor resection")
- `result_value`: **Procedure note or outcome text**

**Example Data**:
```
Procedure: Craniotomy for tumor resection
Note: "Frozen section analysis showed high-grade astrocytoma. Gross total resection
       achieved. Final pathology pending."
```

**Why Important**: Frozen section results during surgery are often documented in procedure notes. These provide early diagnostic information before final pathology reports.

**Typical Volume**: ~200-400 procedures with pathology notes per cohort

---

## View Architecture

### CTE Structure

```
v_pathology_diagnostics
├── CTE 1: oid_reference (OID decoding)
├── CTE 2: molecular_diagnostics (from molecular_tests)
├── CTE 3: pathology_observations (from observation)
├── CTE 4: pathology_procedures (from procedure)
├── CTE 5: pathology_narratives (from diagnostic_report) ⭐ FREE TEXT
├── CTE 6: care_plan_pathology_notes (from care_plan) ⭐ FREE TEXT
├── CTE 7: procedure_pathology_notes (from procedure) ⭐ FREE TEXT
└── CTE 8: unified_diagnostics (UNION ALL of 2-7)
    └── FINAL SELECT: Enriched with patient demographics and linkages
```

### Common Schema Across All Sources

Every diagnostic record includes:

| Column | Type | Description |
|--------|------|-------------|
| patient_fhir_id | VARCHAR | Patient identifier |
| diagnostic_source | VARCHAR | Source type (6 possible values) |
| source_id | VARCHAR | Original resource ID |
| diagnostic_datetime | TIMESTAMP(3) | When diagnostic was performed |
| diagnostic_date | DATE | Date only |
| age_at_diagnostic_days | INT | Age at diagnostic (days) |
| age_at_diagnostic_years | INT | Age at diagnostic (years) |
| diagnostic_name | VARCHAR | Test/procedure name |
| component_name | VARCHAR | Test component (if part of panel) |
| result_value | VARCHAR | **Result text (may be narrative)** |
| diagnostic_category | VARCHAR | Classified category |
| coding_system_code | VARCHAR | OID decoded code (CPT, LOINC, etc.) |
| coding_system_name | VARCHAR | OID decoded name |
| is_idh_mutant | BOOLEAN | IDH mutation status (auto-extracted) |
| is_mgmt_methylated | BOOLEAN | MGMT methylation status (auto-extracted) |
| is_1p19q_codeleted | BOOLEAN | 1p/19q codeletion status (auto-extracted) |
| specimen_types | VARCHAR | Specimen type(s) |
| specimen_sites | VARCHAR | Specimen collection site(s) |
| specimen_collection_datetime | TIMESTAMP(3) | When specimen collected |
| test_identifier | VARCHAR | Test accession number |
| test_lab | VARCHAR | Lab that performed test |
| test_status | VARCHAR | Status (completed, preliminary, etc.) |
| test_orderer | VARCHAR | Ordering provider |
| component_count | INT | Number of components in panel |
| linked_procedure_id | VARCHAR | Associated procedure ID |
| linked_procedure_name | VARCHAR | Associated procedure name |
| linked_procedure_datetime | TIMESTAMP(3) | Procedure date |
| days_from_procedure | INT | Days between procedure and diagnostic |
| encounter_id | VARCHAR | Encounter ID |
| patient_mrn | VARCHAR | Medical record number |
| patient_birth_date | DATE | Birth date |
| patient_gender | VARCHAR | Gender |

---

## Diagnostic Categories

### Molecular/Genetic Categories

| Category | Description | Common Sources |
|----------|-------------|----------------|
| IDH_Mutation | IDH1/IDH2 mutation analysis | molecular_test, observation, narrative |
| MGMT_Methylation | MGMT promoter methylation | molecular_test, observation, narrative |
| 1p19q_Codeletion | Chromosome 1p/19q codeletion | molecular_test, observation, narrative |
| BRAF_Mutation | BRAF V600E or other mutations | molecular_test, observation |
| TP53_Mutation | TP53 gene mutations | molecular_test, observation |
| H3_K27M_Mutation | H3 K27M mutation (DIPG marker) | molecular_test, observation |
| TERT_Promoter | TERT promoter mutation | molecular_test |
| ATRX_Loss | ATRX protein loss | observation, narrative |
| EGFR_Mutation | EGFR amplification/mutation | molecular_test |
| Other_Molecular | Other molecular tests | all sources |

### Histology/Pathology Categories

| Category | Description | Common Sources |
|----------|-------------|----------------|
| WHO_Grade | WHO CNS tumor grade (1-4) | observation, narrative |
| Histology | Histologic type determination | observation, narrative |
| Ki67_Proliferation | Ki-67 proliferation index | observation |
| IHC_GFAP | GFAP immunostain (astrocytoma marker) | observation |
| IHC_OLIG2 | OLIG2 immunostain (oligodendroglioma) | observation |
| IHC_Synaptophysin | Synaptophysin (neuronal marker) | observation |
| IHC_NeuN | NeuN (neuronal marker) | observation |
| IHC_Other | Other immunohistochemistry | observation, narrative |

### Procedure Categories

| Category | Description | Common Sources |
|----------|-------------|----------------|
| Frozen_Section | Intraoperative frozen section | procedure, procedure_note |
| Brain_Biopsy | Brain biopsy procedures | procedure |
| Biopsy_Other | Non-brain biopsies | procedure |
| Surgical_Pathology | Surgical pathology examination | procedure, narrative |
| Specimen_Processing | Specimen handling/processing | procedure |
| CNS_Biopsy | CNS-specific biopsy (by CPT) | procedure |

### Narrative Report Categories

| Category | Description | Common Sources |
|----------|-------------|----------------|
| Surgical_Pathology_Report | Final surgical pathology report | narrative |
| Frozen_Section_Report | Intraoperative frozen section report | narrative |
| Cytology_Report | Cytology/cell analysis report | narrative |
| Molecular_Report | Molecular pathology report | narrative |
| IHC_Report | Immunohistochemistry report | narrative |
| Care_Plan_Pathology | Pathology summary in care plan | care_plan_note |
| Procedure_Pathology_Note | Pathology findings in procedure note | procedure_note |

---

## Molecular Marker Extraction

### Automatic Pattern Matching

The view automatically extracts molecular marker status from **both structured and narrative fields** using pattern matching:

#### IDH Mutation Status

```sql
CASE
    WHEN LOWER(result_value) LIKE '%idh%mutant%'
         OR LOWER(result_value) LIKE '%idh1%mutation%'
         OR LOWER(result_value) LIKE '%idh2%mutation%'
        THEN TRUE  -- IDH-mutant
    WHEN LOWER(result_value) LIKE '%idh%wildtype%'
         OR LOWER(result_value) LIKE '%idh%wild%type%'
        THEN FALSE  -- IDH-wildtype
    ELSE NULL
END as is_idh_mutant
```

**Recognized Patterns**:
- Positive: "IDH mutant", "IDH1 mutation detected", "IDH2 mutation"
- Negative: "IDH wildtype", "IDH wild type", "no IDH mutation"

#### MGMT Methylation Status

```sql
CASE
    WHEN LOWER(result_value) LIKE '%mgmt%methylated%'
         OR LOWER(result_value) LIKE '%mgmt%positive%'
        THEN TRUE  -- MGMT-methylated
    WHEN LOWER(result_value) LIKE '%mgmt%unmethylated%'
         OR LOWER(result_value) LIKE '%mgmt%negative%'
        THEN FALSE  -- MGMT-unmethylated
    ELSE NULL
END as is_mgmt_methylated
```

**Recognized Patterns**:
- Positive: "MGMT methylated", "MGMT positive", "MGMT promoter methylation detected"
- Negative: "MGMT unmethylated", "MGMT negative", "no MGMT methylation"

#### 1p/19q Codeletion Status

```sql
CASE
    WHEN LOWER(result_value) LIKE '%1p%19q%codeleted%'
         OR LOWER(result_value) LIKE '%1p/19q%codeleted%'
        THEN TRUE  -- 1p/19q codeleted
    WHEN LOWER(result_value) LIKE '%1p%19q%intact%'
         OR LOWER(result_value) LIKE '%1p/19q%intact%'
        THEN FALSE  -- 1p/19q intact
    ELSE NULL
END as is_1p19q_codeleted
```

**Recognized Patterns**:
- Positive: "1p/19q codeleted", "1p 19q codeletion", "loss of 1p and 19q"
- Negative: "1p/19q intact", "no 1p/19q codeletion"

### Usage Notes

1. **NULL values** indicate no information found (not necessarily negative)
2. **TRUE** indicates positive/present status
3. **FALSE** indicates negative/absent status
4. Pattern matching is case-insensitive
5. Works across structured fields (from observations) AND narrative text (from reports)

---

## Usage Examples

### Example 1: Get all pathology diagnostics for a patient

```sql
SELECT
    diagnostic_date,
    diagnostic_source,
    diagnostic_category,
    diagnostic_name,
    result_value,
    is_idh_mutant,
    is_mgmt_methylated,
    is_1p19q_codeleted
FROM fhir_prd_db.v_pathology_diagnostics
WHERE patient_fhir_id = 'Patient/xyz'
ORDER BY diagnostic_date;
```

### Example 2: Find patients with IDH-mutant gliomas

```sql
SELECT DISTINCT
    patient_fhir_id,
    patient_mrn,
    MIN(diagnostic_date) as first_idh_test_date,
    LISTAGG(DISTINCT diagnostic_name, '; ') as idh_tests_performed
FROM fhir_prd_db.v_pathology_diagnostics
WHERE is_idh_mutant = TRUE
GROUP BY patient_fhir_id, patient_mrn;
```

### Example 3: Molecular profile summary per patient

```sql
SELECT
    patient_fhir_id,
    patient_mrn,
    MAX(CASE WHEN is_idh_mutant = TRUE THEN 'IDH-mutant'
             WHEN is_idh_mutant = FALSE THEN 'IDH-wildtype'
             ELSE 'Unknown' END) as idh_status,
    MAX(CASE WHEN is_mgmt_methylated = TRUE THEN 'MGMT-methylated'
             WHEN is_mgmt_methylated = FALSE THEN 'MGMT-unmethylated'
             ELSE 'Unknown' END) as mgmt_status,
    MAX(CASE WHEN is_1p19q_codeleted = TRUE THEN '1p/19q-codeleted'
             WHEN is_1p19q_codeleted = FALSE THEN '1p/19q-intact'
             ELSE 'Unknown' END) as codeletion_status
FROM fhir_prd_db.v_pathology_diagnostics
GROUP BY patient_fhir_id, patient_mrn;
```

### Example 4: Link pathology to surgical procedures

```sql
SELECT
    pd.patient_fhir_id,
    pd.diagnostic_date,
    pd.diagnostic_category,
    pd.result_value,
    pd.linked_procedure_name,
    pd.linked_procedure_datetime,
    pd.days_from_procedure
FROM fhir_prd_db.v_pathology_diagnostics pd
WHERE pd.linked_procedure_id IS NOT NULL
  AND pd.diagnostic_category IN ('IDH_Mutation', 'MGMT_Methylation', 'Histology')
ORDER BY pd.diagnostic_date;
```

### Example 5: Find frozen section results during surgery

```sql
SELECT
    patient_fhir_id,
    diagnostic_datetime,
    diagnostic_name,
    result_value,
    linked_procedure_name
FROM fhir_prd_db.v_pathology_diagnostics
WHERE diagnostic_category = 'Frozen_Section'
   OR diagnostic_category = 'Frozen_Section_Report'
ORDER BY diagnostic_datetime;
```

### Example 6: Extract narrative pathology reports

```sql
SELECT
    patient_fhir_id,
    diagnostic_date,
    diagnostic_name,
    result_value as narrative_text,
    is_idh_mutant,
    is_mgmt_methylated
FROM fhir_prd_db.v_pathology_diagnostics
WHERE diagnostic_source IN ('pathology_narrative', 'care_plan_pathology_note', 'procedure_pathology_note')
  AND LENGTH(result_value) > 100  -- Substantial narrative
ORDER BY diagnostic_date;
```

### Example 7: Compare molecular testing sources

```sql
SELECT
    diagnostic_source,
    diagnostic_category,
    COUNT(*) as test_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count,
    COUNT(CASE WHEN is_idh_mutant IS NOT NULL THEN 1 END) as has_idh_info,
    COUNT(CASE WHEN is_mgmt_methylated IS NOT NULL THEN 1 END) as has_mgmt_info
FROM fhir_prd_db.v_pathology_diagnostics
WHERE diagnostic_category IN ('IDH_Mutation', 'MGMT_Methylation', 'Other_Molecular')
GROUP BY diagnostic_source, diagnostic_category
ORDER BY test_count DESC;
```

---

## Validation & Testing

### Test Suite

A comprehensive test suite is available in:
```
athena_views/analysis/test_v_pathology_diagnostics.sql
```

**12 validation queries included**:
1. Count by diagnostic source
2. Count by diagnostic category
3. Molecular marker extraction validation
4. Specimen linkage validation
5. Procedure linkage validation
6. Narrative text capture validation
7. Date coverage analysis
8. Sample records from each source
9. Compare with molecular_tests table
10. Patient-level summary
11. Narrative extraction effectiveness
12. Age at diagnostic validation

### Running Tests

```bash
# Deploy the view first
./surgical_procedures_assessment/run_query.sh athena_views/views/v_pathology_diagnostics.sql

# Run validation tests
./surgical_procedures_assessment/run_query.sh athena_views/analysis/test_v_pathology_diagnostics.sql
```

### Expected Results

**Source Distribution** (approximate):
- molecular_test: ~2,800 tests
- pathology_observation: Variable (depends on structured lab data)
- pathology_procedure: ~500-1,000 procedures
- pathology_narrative: ~800-1,200 reports
- care_plan_pathology_note: ~100-300 care plans
- procedure_pathology_note: ~200-400 procedures

**Molecular Marker Coverage** (typical):
- IDH status: 70-80% of patients with molecular testing
- MGMT status: 60-70% of patients with molecular testing
- 1p/19q status: 40-50% of patients with molecular testing

---

## Clinical Context

### WHO 2021 CNS Tumor Classification

The WHO 2021 classification **integrates molecular AND histologic features**:

**Gliomas**:
- **Glioblastoma, IDH-wildtype** (Grade 4): Most aggressive, poorest prognosis
- **Astrocytoma, IDH-mutant** (Grade 2-4): Better prognosis than IDH-wildtype
- **Oligodendroglioma, IDH-mutant and 1p/19q-codeleted** (Grade 2-3): Best prognosis among adult diffuse gliomas

**Pediatric-Specific**:
- **Diffuse midline glioma, H3 K27M-altered** (Grade 4): DIPG, very poor prognosis
- **Pilocytic astrocytoma** (Grade 1): BRAF-altered, excellent prognosis

### Key Molecular Markers

| Marker | Clinical Significance | Detection Methods |
|--------|----------------------|-------------------|
| **IDH mutation** | Defines glioma subtype; better prognosis | Sequencing, IHC (R132H) |
| **MGMT methylation** | Predicts temozolomide response in GBM | Methylation analysis |
| **1p/19q codeletion** | Defines oligodendroglioma; chemo-sensitive | FISH, CGH array |
| **BRAF V600E** | Common in pilocytic astrocytoma; targetable | Sequencing, IHC |
| **H3 K27M** | Defines diffuse midline glioma (DIPG) | Sequencing, IHC |
| **TP53 mutation** | Li-Fraumeni syndrome; high-grade gliomas | Sequencing |
| **TERT promoter** | Prognostic in GBM and oligodendroglioma | Sequencing |
| **ATRX loss** | Alternative telomere lengthening pathway | IHC |
| **Ki-67** | Proliferation index; correlates with grade | IHC |

### Treatment Implications

**IDH-wildtype Glioblastoma**:
- Standard: Maximal safe resection → radiation + temozolomide (Stupp protocol)
- MGMT-methylated: Better response to chemotherapy

**IDH-mutant Astrocytoma**:
- Grade 2: Observation vs. radiation ± chemotherapy
- Grade 3-4: Radiation + chemotherapy (PCV or temozolomide)

**1p/19q-codeleted Oligodendroglioma**:
- Highly responsive to chemotherapy (PCV, temozolomide)
- Often defer radiation until progression

**BRAF-altered Pilocytic Astrocytoma**:
- Grade 1: Observation after resection if complete
- Targetable with MEK inhibitors if unresectable/progressive

**H3 K27M-altered DIPG**:
- Radiation is mainstay (chemotherapy ineffective)
- Clinical trials for targeted therapies

---

## Discovery Queries

### Finding Additional Pathology Data Sources

Use these queries to discover pathology-related data in your FHIR database:

**1. Discover pathology observations**:
```bash
./surgical_procedures_assessment/run_query.sh athena_views/analysis/discover_pathology_observations.sql
```

**2. Discover pathology procedures**:
```bash
./surgical_procedures_assessment/run_query.sh athena_views/analysis/discover_pathology_procedures.sql
```

**3. Reference of pathology codes**:
```bash
./surgical_procedures_assessment/run_query.sh athena_views/analysis/pathology_codes_reference.sql
```

---

## Extending the View

### Adding New Molecular Markers

To add extraction for new markers (e.g., EGFR amplification):

```sql
-- In molecular_diagnostics CTE
CASE
    WHEN LOWER(mtr.test_component) LIKE '%egfr%' THEN 'EGFR_Amplification'
    ...
END as diagnostic_category,

-- Add flag column
CASE
    WHEN LOWER(mtr.test_component) LIKE '%egfr%'
         AND LOWER(mtr.test_result_narrative) LIKE '%amplif%' THEN TRUE
    WHEN LOWER(mtr.test_component) LIKE '%egfr%'
         AND LOWER(mtr.test_result_narrative) LIKE '%normal%' THEN FALSE
    ELSE NULL
END as is_egfr_amplified,
```

### Adding New Data Sources

To add additional FHIR resources (e.g., genomic reports):

1. Create new CTE following existing pattern
2. Ensure same column structure
3. Add to unified_diagnostics UNION ALL
4. Update documentation

---

## Troubleshooting

### Common Issues

**Issue**: No data from narrative sources
**Solution**: Check that `diagnostic_report.conclusion` or `diagnostic_report.presented_form_data` fields exist and contain data

**Issue**: Molecular markers not being extracted
**Solution**: Review actual result_value text patterns in your data; may need to adjust LIKE patterns

**Issue**: Specimen linkage missing
**Solution**: Specimen-to-diagnostic linking is approximate via encounter; may need institution-specific logic

**Issue**: Performance slow
**Solution**: Add WHERE filter on patient_fhir_id or date range; consider materialized table for large cohorts

### Getting Help

**Questions about**:
- Clinical interpretation → Consult pathologist or neuro-oncologist
- FHIR data structure → See FHIR specification at https://www.hl7.org/fhir/
- Epic-specific logic → Contact Epic Clarity team or Analyst Services
- View modifications → See AGENT_CONTEXT.md for development patterns

---

**Last Updated**: 2025-10-30
**Version**: 1.0
**Maintained By**: Data Analytics Team
