# Germline Variant Analysis from StarRocks Database

**Date:** October 26, 2024
**Analysis Type:** Somatic Variant Extraction from Molecular Test Reports
**Database:** StarRocks (radiant and radiant_tests schemas)

---

## Overview

This analysis extracted somatic variants from molecular test result narratives for 45 pediatric patients who have both germline variant data in the StarRocks `radiant` database and corresponding clinical molecular test reports in the `radiant_tests` database.

## Objective

Match patients with germline sequencing data to their somatic mutations found in clinical molecular test reports, enabling genotype-phenotype correlation studies and treatment response analysis.

---

## Data Sources

### 1. Germline Database (`radiant`)
- **Database:** StarRocks `radiant` schema
- **Key Tables:**
  - `germline__snv__occurrence` - 467,951,648 variant calls
  - `germline__snv__variant` - Variant-level summaries
  - `germline__snv__consequence` - Variant annotations
  - `staging_sequencing_experiment` - Sequencing metadata for 57 cases

### 2. Clinical Reports (`radiant_tests`)
- **Database:** StarRocks `radiant_tests` schema
- **Key Tables:**
  - `molecular_test_results` - Molecular pathology reports (narrative text)
  - Contains Tier 1, Tier 2, and Tier 3 variant classifications
  - Reports include gene fusions, SNVs, CNVs with clinical significance

### 3. ID Crosswalk Mapping
- **File:** `pMRN_fID_cID.csv`
- **Mappings:** pseudoMRN ↔ FHIR_ID ↔ case_id
- **Purpose:** Link germline cases to clinical FHIR data

---

## Methodology

### Step 1: Identify Patients with Both Data Types

**Query:** Found patients with:
- Germline variant data in `radiant` database (57 cases total)
- FHIR_ID mapping in crosswalk file
- Clinical molecular test reports in `radiant_tests`

**Result:** 45 patients matched all criteria (79% of germline cases)

### Step 2: Extract Somatic Variants from Molecular Reports

**Data Extraction:**
- Queried `molecular_test_results` table for 45 FHIR patient IDs
- Retrieved 191 molecular test reports
- Parsed narrative text fields (`test_result_narrative`)

**Parsing Approach:**
Used regular expressions to extract:
1. **Gene fusions:** Pattern `GENE1-GENE2` (e.g., KIAA1549-BRAF)
2. **SNVs with HGVS protein notation:** Pattern `GENE p.AminoAcidChange` (e.g., BRAF p.Val600Glu)
3. **Simple mutation notation:** Pattern `GENE MUTATION` (e.g., BRAF V600E)
4. **Histone variants:** Pattern `H3 K27M`, `H3F3A p.Lys28Met`

**Tier Classification:**
- Tier 1: Variants with strong evidence of clinical significance
- Tier 2: Variants with potential clinical significance
- Tier 3: Variants of uncertain significance (VUS)

### Step 3: Generate Output Files

Created two CSV files with different filtering criteria:
1. **All somatic variants** (any tier)
2. **Tier 1 variants only** (clinically significant)

---

## Results

### Patient Coverage

| Category | Count | Percentage |
|----------|-------|------------|
| **Total germline cases** | 57 | 100% |
| **Cases with FHIR_ID mapping** | 45 | 79% |
| **Cases with molecular reports** | 41 | 72% |
| **Cases with ANY variants identified** | 17 | 30% |
| **Cases with Tier 1 variants** | 8 | 14% |

### Variant Distribution

#### All Somatic Variants (17 patients)

**Fusions (7 patients):**
- KIAA1549-BRAF (6 patients) - Characteristic of pilocytic astrocytoma
- TRIM24-NTRK2 (1 patient) - NTRK fusion-positive tumor
- YWHAE-NUTM2B (1 patient) - Sarcoma-associated fusion

**Point Mutations/SNVs (13 patients):**
- BRAF p.Val600Glu / V600E (3 patients) - Classic oncogenic mutation
- H3F3A p.Lys28Met / H3 K27M (1 patient) - Diffuse midline glioma marker
- TP53 p.Cys275Arg (1 patient) - Tumor suppressor mutation
- CTNNB1 p.Asp32His, p.Gly34Val (2 patients) - Beta-catenin/Wnt pathway
- SMARCB1 p.Tyr248Serf (1 patient) - AT/RT tumor suppressor
- CHEK2 p.Arg145Trp (1 patient) - DNA damage checkpoint

#### Tier 1 Variants Only (8 patients)

| case_id | FHIR_ID | Tier 1 Mutations |
|---------|---------|------------------|
| 1000012 | eHmvUFS6s7OBGee-DdUhKxXnvS5b8zfrsi.ezHzyKckI3 | KIAA1549-BRAF |
| 1000027 | emB6TYGnmgMFuUJBdehn3M969UP2rlq77IhVV2e.rFtE3 | KIAA1549-BRAF |
| 1000231 | e2TQGdOX6ADUEI1m8YdkZVlfn6tQTt4b7D7qSwcUTvVM3 | TRIM24-NTRK2 |
| 1000238 | efzecnwnkpCKBiMcVxuF..q5XTxbH9QAjtbsVHUi7N783 | KIAA1549-BRAF |
| 1000488 | e8XUZfL9-sgUQ.zzbFSKP4mLw891dPo2zOFvUlc1TcQc3 | MYB-FOXO3 |
| 1000567 | e9928Ob8xk5xOoc-dCvSKUB4uu0qun3mruwy-KFg89Q3 | BRAF V600E |
| 1000671 | eTsTC65b18h50a948z714Fw3 | KIAA1549-BRAF |
| 1000715 | edPKBgqZsNo.zm56tbK4x3w3 | KIAA1549-BRAF |

---

## Output Files

### 1. germline_somatic_variants.csv
**Description:** Complete list of all somatic variants (any tier) for 45 germline cases

**Columns:**
- `case_id` - StarRocks case identifier
- `FHIR_ID` - Patient FHIR identifier (hashed)
- `somatic_variants` - Semicolon-separated list of variants

**Statistics:**
- Total rows: 45
- Patients with variants: 17 (37.8%)
- Patients without variants: 24 (53.3%)
- Patients without reports: 4 (8.9%)

**File size:** 2.8 KB

### 2. germline_tier1_variants.csv
**Description:** Filtered list containing only Tier 1 (clinically significant) variants

**Columns:**
- `case_id` - StarRocks case identifier
- `FHIR_ID` - Patient FHIR identifier (hashed)
- `tier1_mutations` - Tier 1 variants only

**Statistics:**
- Total rows: 45
- Patients with Tier 1 variants: 8 (17.8%)
- Most common: KIAA1549-BRAF fusion (5/8 patients, 62.5%)

**File size:** 2.7 KB

---

## Key Findings

### 1. Data Completeness
- **Germline variant data:** Available for 57 cases in `radiant` database (467M variants)
- **Somatic variant data:** Only 1 case in `radiant_tests.somatic_snv_occurrence` (case_id 1000001)
- **Molecular reports:** Available for 41/45 matched cases (91%)
- **Structured vs. Narrative:** Variant data primarily exists as narrative text in reports, not structured database tables

### 2. Common Variant Patterns
- **Pediatric low-grade gliomas:** KIAA1549-BRAF fusion dominant (35% of patients with variants)
- **BRAF pathway mutations:** Present in 53% of patients with variants (fusions + V600E)
- **Histone mutations:** H3 K27M present, indicating diffuse midline glioma
- **Targetable alterations:** NTRK fusions (TRIM24-NTRK2) identified

### 3. Clinical Implications
- **Tier 1 variants:** All 8 patients with Tier 1 findings have actionable or diagnostically significant alterations
- **Treatment relevance:** BRAF V600E and NTRK fusions are FDA-approved drug targets
- **Prognostic markers:** KIAA1549-BRAF associated with favorable prognosis in pilocytic astrocytoma

---

## Technical Challenges & Limitations

### Challenges Addressed
1. **Unstructured data:** Molecular reports stored as narrative text requiring NLP/regex parsing
2. **Gene nomenclature:** Handled variations (H3F3A vs H3-3A, BRAF V600E vs p.Val600Glu)
3. **Multiple report formats:** Different institutions use varying Tier classification formats
4. **ID mapping:** Required crosswalk between germline case_ids, FHIR_IDs, and pseudoMRNs

### Known Limitations
1. **Text parsing accuracy:** Regex-based extraction may miss variants with non-standard descriptions
2. **Tier classification:** Not all reports explicitly state tier levels
3. **VCF data unavailable:** Structured variant call format (VCF) data only available for 1 patient
4. **CNV detection:** Copy number variants not reliably extracted from narrative text
5. **Fusion breakpoints:** Exact fusion breakpoint information not captured

### Data Quality Issues
- 12 germline cases (21%) lack FHIR_ID mapping in crosswalk
- 4 patients (9%) have no molecular test reports despite having case_ids
- radiant_tests database appears to be test/development environment (synthetic sequencing metadata)

---

## Usage Recommendations

### For Clinical Research
1. **Genotype-Phenotype Correlation:**
   - Link somatic variants (this file) to germline variants in `radiant.germline__snv__occurrence`
   - Correlate with phenotype codes in `radiant_tests.observation_coding` (HPO terms)

2. **Treatment Response Analysis:**
   - Cross-reference BRAF V600E patients with BRAF inhibitor treatments
   - Identify NTRK fusion patients for targeted therapy studies

3. **Cohort Definition:**
   - Use Tier 1 file for high-confidence variant-based cohorts
   - Use all variants file for exploratory/hypothesis-generating analyses

### For Data Integration
1. **Join Keys:**
   - Use `case_id` to join with `radiant_tests` tables
   - Use `FHIR_ID` to join with clinical FHIR data
   - Reference `pMRN_fID_cID.csv` for pseudoMRN mapping

2. **Validation Steps:**
   - For critical analyses, manually review molecular test reports
   - Confirm variant calls against structured data when available (case 1000001)
   - Verify tier classifications in original reports

---

## Database Schema Reference

### Germline Tables (radiant schema)

```sql
-- Germline variant occurrences
radiant.germline__snv__occurrence
  - task_id, seq_id, locus_id
  - ad_ratio, gq, dp, zygosity
  - father/mother genotypes (trio analysis)
  - exomiser scores

-- Variant annotations
radiant.germline__snv__consequence
  - symbol, consequences, vep_impact
  - hgvsc, hgvsp (HGVS notation)
  - mane_select, is_canonical

-- Sequencing metadata
radiant.staging_sequencing_experiment
  - case_id, patient_id, seq_id, task_id
  - experimental_strategy (wgs, wxs)
```

### Clinical Tables (radiant_tests schema)

```sql
-- Molecular test reports
radiant_tests.molecular_test_results
  - patient_id (FHIR_ID)
  - test_result_narrative (text)
  - observation_id, test_id

-- Patient demographics
radiant_tests.patient
  - id (patient_internal_id)
  - mrn (pseudoMRN)

-- Genomic cases
radiant_tests.cases
  - id (case_id)
  - proband_id (links to patient.id)
```

---

## Next Steps & Future Enhancements

### Short-term
1. **Manual validation:** Review molecular reports for top 10 patients with variants
2. **Expand to CNVs:** Develop parsing for copy number alterations in reports
3. **Add MAF/VAF:** Extract variant allele frequencies when reported

### Medium-term
1. **NLP enhancement:** Use LLM-based extraction for improved accuracy
2. **Structured data integration:** Link to VCF files when available
3. **Fusion breakpoint extraction:** Parse detailed fusion junction information

### Long-term
1. **Real-time updates:** Automate variant extraction as new reports arrive
2. **Variant annotation:** Enhance with ClinVar, COSMIC, OncoKB annotations
3. **Treatment correlation:** Link variants to actual treatments from EHR data

---

## Contact & Support

**Analysis performed by:** Claude (AI Assistant)
**Date:** October 26, 2024
**Data Source:** StarRocks database (radiant, radiant_tests)
**Project:** RADIANT_PCA/BRIM_Analytics/ID_Crosswalk

**Related Files:**
- `pMRN_fID_cID.csv` - ID crosswalk mapping
- `germline_somatic_variants.csv` - All variants (this analysis)
- `germline_tier1_variants.csv` - Tier 1 variants only

**For questions or issues:**
- Review molecular test reports directly in StarRocks
- Consult clinical geneticists for variant interpretation
- Validate critical findings against original pathology reports
