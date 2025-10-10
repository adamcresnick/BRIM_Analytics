# Athena Extraction & Validation Workflow

## Overview

This repository contains a comprehensive, production-ready workflow for extracting, validating, and staging clinical data from AWS HealthLake FHIR databases (accessed via Athena) for downstream analytics, reporting, and research applications.

**Project Goal**: Create clean, validated, analysis-ready staging files from complex FHIR resource tables with comprehensive metadata, temporal tracking, and quality validation.

**Key Features**:
- ✅ **Multi-table JOIN strategies** for complex FHIR resource extraction
- ✅ **Age calculation** at event dates (maintaining patient privacy)
- ✅ **Coding system validation** (ICD-10, SNOMED, RxNorm, LOINC)
- ✅ **S3 Binary file availability** checking with naming bug fixes
- ✅ **Comprehensive logging** and execution summaries
- ✅ **Privacy-first approach** (excludes MRN from outputs)
- ✅ **Encounter linkage** across all resource types

---

## 📁 Repository Structure

```
athena_extraction_validation/
├── scripts/
│   ├── extract_all_medications_metadata.py         # 1,121 medications (10 tables joined)
│   ├── filter_chemotherapy_from_medications.py     # 385 chemotherapy (5-strategy ID)
│   ├── extract_all_imaging_metadata.py             # 181 imaging (3 radiology tables)
│   ├── extract_all_measurements_metadata.py        # 1,586 measurements (observation + labs)
│   ├── extract_all_diagnoses_metadata.py           # 23 diagnoses (problem list)
│   ├── extract_all_binary_files_metadata.py        # 22,127 documents (5 tables, encounter refs)
│   └── check_binary_s3_availability.py             # S3 verification (9,137 available, 54.4%)
│
├── staging_files/
│   ├── ALL_MEDICATIONS_METADATA.csv                # 1,121 records, 29 columns
│   ├── CHEMOTHERAPY_MEDICATIONS.csv                # 385 records (275 high-confidence)
│   ├── ALL_IMAGING_METADATA.csv                    # 181 records, 31 columns
│   ├── ALL_MEASUREMENTS_METADATA.csv               # 1,586 records (289 anthro + 1,297 labs)
│   ├── ALL_DIAGNOSES_METADATA.csv                  # 23 records, 17 columns
│   ├── ALL_BINARY_FILES_METADATA.csv               # 22,127 records, 25 columns
│   └── ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv  # 22,127 records, 28 columns
│
├── documentation/
│   └── MEASUREMENTS_STAGING_FILE_ANALYSIS.md       # Detailed measurements documentation
│
└── README.md                                        # This file
```

---

## 🚀 Quick Start

### Prerequisites

1. **AWS Configuration**:
   ```bash
   # Configure AWS SSO profile
   aws sso login --profile radiant-prod
   export AWS_PROFILE=radiant-prod
   ```

2. **Python Dependencies**:
   ```bash
   pip install boto3 pandas pyarrow awswrangler
   ```

3. **Database Access**: 
   - Access to AWS Athena workgroup: `primary`
   - Read permissions for `fhir_prd_db` (primary) and `fhir_v2_prd_db` (supplementary)

### Running Extraction Scripts

```bash
cd scripts/

# Extract medications (10 tables, ~30 seconds)
python3 extract_all_medications_metadata.py

# Filter chemotherapy (5 strategies, ~5 seconds)
python3 filter_chemotherapy_from_medications.py

# Extract imaging (3 tables, ~10 seconds)
python3 extract_all_imaging_metadata.py

# Extract measurements (3 tables, ~10 seconds)
python3 extract_all_measurements_metadata.py

# Extract diagnoses (1 table, ~3 seconds)
python3 extract_all_diagnoses_metadata.py

# Extract binary files metadata (5 tables, ~10 seconds)
python3 extract_all_binary_files_metadata.py

# Check S3 availability (~10-15 minutes for 16,798 files)
python3 check_binary_s3_availability.py
```

---

## 📊 Extraction Summaries

### 1. Medications (1,121 Records)

**Script**: `extract_all_medications_metadata.py`  
**Database**: `fhir_v2_prd_db`  
**Tables Joined**: 10 (medication, medication_request, medication_dosage_instruction, etc.)  
**Output**: `ALL_MEDICATIONS_METADATA.csv` (29 columns, 458 KB)

**Key Features**:
- RADIANT unified drug reference integration (RxNorm codes)
- Medication name, brand name, generic name
- Dosage instructions (dose quantity, dose unit, route, frequency)
- Temporal tracking (authored date, effective period, last updated)
- Age at medication order/administration
- 100% metadata coverage

**Critical Discovery**: No annotation tables exist in FHIR V2 database (validated against schema).

**Data Quality**:
- **RxNorm Coding**: 100% (1,121/1,121)
- **Temporal Coverage**: Birth to age 20.2 years (7,384 days)
- **Top Categories**: Chemotherapy (385), Antiemetics, GI medications, Procedural agents

---

### 2. Chemotherapy (385 Records)

**Script**: `filter_chemotherapy_from_medications.py`  
**Input**: `ALL_MEDICATIONS_METADATA.csv`  
**Output**: `CHEMOTHERAPY_MEDICATIONS.csv` (31 columns, 160 KB)

**5-Strategy Identification**:
1. **RxNorm Exact Match**: 100% precision (highest confidence)
2. **Generic Name Match**: High confidence (e.g., "Vincristine")
3. **Brand Name Match**: Moderate confidence (e.g., "Oncovin")
4. **Medication Name Contains**: Lower confidence (requires review)
5. **Unified Drug Reference**: Cross-validation with RADIANT reference

**Results**:
- **Total Chemotherapy**: 385 records
- **High-Confidence**: 275 (71.4%) - Strategies 1-2
- **Moderate-Confidence**: 90 (23.4%) - Strategy 3
- **Requires Review**: 20 (5.2%) - Strategy 4

**Top Agents**: Vincristine (133), Temozolomide (68), Irinotecan (32), Cyclophosphamide (28)

---

### 3. Imaging (181 Records)

**Script**: `extract_all_imaging_metadata.py`  
**Database**: `fhir_v2_prd_db`  
**Tables Joined**: 3 (diagnostic_report_imaging, imaging_study, imaging_study_series)  
**Output**: `ALL_IMAGING_METADATA.csv` (31 columns, 86 KB)

**Key Features**:
- Imaging modality (MRI, CT, X-Ray, Ultrasound)
- Body part examined
- Study date, series count, instance count
- Age at imaging (0.8-15.8 years)
- Imaging context (inpatient, outpatient, emergency)

**Data Quality**:
- **Temporal Coverage**: 5,477 days (15.0 years)
- **Modality Distribution**: MRI (68%), CT (18%), X-Ray (10%), Other (4%)
- **Primary Focus**: Neurological imaging (brain, spine) for oncology patient

---

### 4. Measurements (1,586 Records)

**Script**: `extract_all_measurements_metadata.py`  
**Database**: `fhir_v2_prd_db`  
**Tables Joined**: 3 (observation, lab_tests, lab_test_results)  
**Output**: `ALL_MEASUREMENTS_METADATA.csv` (23 columns, 640 KB)

**Data Breakdown**:
- **Anthropometric Observations**: 289 (18.2%)
  - Weight: 163 measurements
  - Height: 114 measurements
  - Head Circumference: 10 measurements
  - BMI: 2 measurements
- **Lab Test Results**: 1,297 (81.8%)
  - 421 distinct lab tests
  - 999 component results (multi-component panels)

**Critical ID Format Discovery**:
- ⚠️ **observation table**: Uses `subject_reference = 'FHIR_ID'` (NO 'Patient/' prefix)
- ✅ **All other tables**: Use standard FHIR reference format
- This discovery prevented 0-result queries and is documented for future extractions

**Data Quality**:
- **Temporal Coverage**: 7,308 days (20.0 years) - birth to present
- **Age Range**: 0.0 - 20.0 years
- **Top Lab Categories**: Hematology (CBC), Chemistry (CMP), Tumor markers

**8 Lessons Learned**: Documented in `MEASUREMENTS_STAGING_FILE_ANALYSIS.md`

---

### 5. Diagnoses (23 Records)

**Script**: `extract_all_diagnoses_metadata.py`  
**Database**: `fhir_v2_prd_db`  
**Table**: `problem_list_diagnoses`  
**Output**: `ALL_DIAGNOSES_METADATA.csv` (17 columns, 6 KB)

**Key Features**:
- Clinical status (Active, Resolved, Inactive)
- ICD-10 and SNOMED coding (100% coverage)
- Onset, abatement, recording dates
- Age at diagnosis (1.0-15.9 years)

**Clinical Summary**:
- **Active Diagnoses**: 13 (56.5%)
- **Resolved Diagnoses**: 10 (43.5%)
- **Primary Diagnosis**: Pilocytic astrocytoma of cerebellum (age 1.0 years)
- **Treatment-Related**: 
  - Chemotherapy-induced nausea/vomiting (2 records)
  - Dysphagia (2 records)
  - Nystagmus (2 records)

**Data Quality**:
- **ICD-10 Coding**: 100% (23/23)
- **SNOMED Coding**: 100% (23/23)
- **Temporal Coverage**: 5,421 days (14.9 years)

---

### 6. Binary Files & Documents (22,127 Records)

**Script**: `extract_all_binary_files_metadata.py`  
**Database**: `fhir_prd_db` (⚠️ NOT fhir_v2_prd_db - see lessons learned)  
**Tables Joined**: 5 (document_reference + 4 related tables)  
**Output**: `ALL_BINARY_FILES_METADATA.csv` (25 columns, 8.0 MB)

**Key Features**:
- Comprehensive document metadata (type, category, content type)
- **Encounter linkage**: 97.5% of documents linked to 914 unique encounters
- Age at document date
- Binary IDs for S3 retrieval
- Pagination support (handles 9,364+ base records with JOIN multiplication)

**Document Distribution**:
- **Progress Notes**: 7,668 (34.7%)
- **Telephone Encounters**: 3,176 (14.4%)
- **Assessment & Plan**: 1,184 (5.4%)
- **Patient Instructions**: 856 (3.9%)
- **Encounter Summaries**: 762 (3.4%)
- **Other Types**: 8,481 (38.3%)

**Content Types**:
- **HTML**: 7,604 (34.4%)
- **RTF**: 7,372 (33.3%)
- **XML**: 1,086 (4.9%)
- **PDF**: 511 (2.3%)
- **Images**: 223 (1.0%)

**Data Quality**:
- **With Binary IDs**: 16,798 (75.9%)
- **Encounter Linkage**: 21,563 (97.5%)
- **Temporal Coverage**: Age 0.0 - 20.2 years (complete patient history)

---

### 7. S3 Binary Availability (9,137 Available)

**Script**: `check_binary_s3_availability.py`  
**Input**: `ALL_BINARY_FILES_METADATA.csv`  
**Output**: `ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv` (28 columns, 9.7 MB)

**Critical S3 Naming Bug Fix**:
- **Issue**: FHIR Binary IDs contain periods (.), but S3 files use underscores (_)
- **Solution**: `binary_id.replace('.', '_')` before S3 lookup
- **Impact**: Without this fix, 0% S3 availability for IDs with periods

**S3 Configuration**:
- **Bucket**: `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`
- **Prefix**: `prd/source/Binary/`
- **Verification Method**: S3 `head_object` (fast, no download)

**Results**:
- **Total Binary IDs Checked**: 16,798
- **Available in S3**: 9,137 (54.4%)
- **Not Available**: 7,661 (45.6%)
- **Execution Time**: ~10 minutes (0.036 seconds per check)

**S3 Availability by Document Type**:
- Progress Notes: 3,834 (42.0% of available)
- Telephone Encounters: 1,588 (17.4%)
- Encounter Summaries: 762 (8.3%)
- Assessment & Plan: 592 (6.5%)
- Imaging: 163 (1.8%)

**S3 Availability by Content Type**:
- HTML: 7,604 (83.2% of available)
- XML: 1,079 (11.8%)
- PDF: 229 (2.5%)
- Images (TIFF/JPEG/PNG): 223 (2.4%)

---

## 🔑 Key Technical Discoveries

### Database Architecture Lessons

1. **fhir_prd_db vs fhir_v2_prd_db**:
   - `fhir_prd_db`: Complete dataset (9,364 DocumentReferences)
   - `fhir_v2_prd_db`: Partial/test dataset (76 DocumentReferences - only 0.8%!)
   - **Rule**: Use `fhir_prd_db` for Binary/DocumentReference, `fhir_v2_prd_db` for clinical resources

2. **ID Format Variations**:
   - `observation` table: `subject_reference = 'FHIR_ID'` (NO 'Patient/' prefix)
   - All other tables: `patient_id = 'FHIR_ID'` OR `subject_reference = 'Patient/FHIR_ID'`
   - Always test ID format before assuming standard FHIR references

3. **Annotation Tables**:
   - **BRIM Workflow Assumption**: medication_annotation tables exist
   - **Reality**: NO annotation tables in fhir_v2_prd_db (validated via schema query)
   - Workaround: Use RADIANT unified drug reference for RxNorm lookups

### Performance Optimizations

1. **Athena Pagination**:
   - Max results per query: 1,000 rows
   - Use `NextToken` for pagination with large result sets
   - 22,127 documents required 23 pages (handled automatically)

2. **JOIN Strategy**:
   - Query base table first, then annotate with LEFT JOINs
   - Avoids timeout on large multi-table JOINs
   - Python-side merging for complex relationships

3. **S3 Checking**:
   - Use `head_object` not `get_object` (no download needed)
   - Progress logging every 100 records for user feedback
   - Expected rate: ~0.04 seconds per check (3 minutes per 5,000 files)

### Privacy & Compliance

1. **MRN Exclusion**: All scripts exclude `patient_mrn` from CSV outputs
2. **Age-Based Tracking**: Use age at event (days/years) instead of absolute dates where possible
3. **Encounter References**: Maintain for clinical context without exposing identifiers
4. **Logging**: Patient MRN displayed in console logs only (not in CSV files)

---

## 📈 Data Quality Metrics

| Resource | Records | Temporal Coverage | Coding Completeness | Key Metric |
|----------|---------|-------------------|---------------------|------------|
| **Medications** | 1,121 | Birth to 20.2 yrs | 100% RxNorm | 385 chemotherapy (34.3%) |
| **Imaging** | 181 | 0.8 - 15.8 yrs | 100% modality | 68% MRI (neuro focus) |
| **Measurements** | 1,586 | Birth to 20.0 yrs | 100% LOINC | 289 anthropometric, 1,297 labs |
| **Diagnoses** | 23 | 1.0 - 15.9 yrs | 100% ICD-10/SNOMED | 13 Active, 10 Resolved |
| **Documents** | 22,127 | Birth to 20.2 yrs | 97.5% encounter-linked | 54.4% S3-available |

**Overall Assessment**: High-quality, comprehensive clinical data extraction with excellent coding coverage and temporal completeness.

---

## 🎯 Use Cases

### Clinical Research
- **Oncology Studies**: Chemotherapy regimen analysis, treatment outcomes
- **Growth Monitoring**: Anthropometric measurements over 20 years
- **Diagnostic Imaging**: Longitudinal neuro-imaging for tumor surveillance
- **Treatment Toxicity**: Lab results correlated with chemotherapy cycles

### Quality Improvement
- **Documentation Completeness**: 97.5% encounter linkage
- **Coding Accuracy**: 100% ICD-10/SNOMED coverage for diagnoses
- **Data Availability**: 54.4% binary file accessibility in S3

### Data Analytics
- **Temporal Trends**: Medication changes over treatment course
- **Resource Utilization**: Imaging frequency, lab ordering patterns
- **Clinical Decision Support**: Problem list maintenance, active vs resolved diagnoses

### Downstream Integration
- **BRIM Analytics**: Standardized staging files for regulatory reporting
- **Machine Learning**: Feature engineering from FHIR resources
- **Dashboard Development**: Pre-aggregated metrics for visualization tools

---

## 🛠️ Technical Architecture

### AWS Services
- **Athena**: SQL queries against FHIR HealthLake data
- **S3**: Binary file storage and query results
- **SSO**: Secure authentication via `radiant-prod` profile
- **Workgroup**: `primary` (configured for result location)

### Python Stack
- **boto3**: AWS SDK (Athena, S3 clients)
- **pandas**: DataFrame operations, CSV I/O
- **pyarrow**: Parquet support (optional)
- **awswrangler**: Athena query simplification (optional)

### Logging Strategy
- **Dual Output**: Console + log files
- **Progress Tracking**: Every 100 records for long-running operations
- **Execution Summaries**: Counts, percentages, temporal coverage
- **Error Handling**: Graceful failures with detailed error messages

---

## 📝 Future Enhancements

### Planned Features
1. **Procedures Extraction**: Surgical procedures, therapeutic procedures
2. **Immunizations**: Vaccine history with CVX codes
3. **Vital Signs**: Temperature, blood pressure, pulse, respiration
4. **Allergies**: Allergy/intolerance list with severity
5. **Family History**: Hereditary conditions, genetic risk factors
6. **Social History**: Smoking, alcohol, occupation

### Technical Improvements
1. **Incremental Updates**: Delta extraction for new/modified records
2. **Data Validation**: Automated checks against gold standard
3. **Schema Evolution**: Detect and adapt to FHIR schema changes
4. **Parallel Processing**: Multi-threaded S3 availability checks
5. **Documentation Generation**: Auto-generate analysis reports

### Integration Goals
1. **BRIM Workflow**: Seamless handoff to downstream BRIM analytics
2. **API Development**: REST endpoints for staging file access
3. **Dashboard Integration**: Real-time data refresh for visualizations
4. **ETL Pipeline**: Automated daily/weekly extraction schedules

---

## 🤝 Contributing

This workflow is designed for:
- **Clinical Informaticists**: Understanding FHIR resource extraction patterns
- **Data Engineers**: Building production ETL pipelines
- **Researchers**: Generating analysis-ready datasets
- **Analysts**: Downstream consumption of staging files

**Key Principles**:
1. **Privacy First**: Never expose patient identifiers in outputs
2. **Validate Early**: Check ID formats, table existence, coding completeness
3. **Document Everything**: Lessons learned, edge cases, workarounds
4. **Reproducibility**: Scripts should produce identical results given same inputs

---

## 📚 Documentation

### Detailed Guides
- [`MEASUREMENTS_STAGING_FILE_ANALYSIS.md`](documentation/MEASUREMENTS_STAGING_FILE_ANALYSIS.md): 450+ lines documenting measurements extraction strategy, ID format discovery, query approach, clinical context, and 8 critical lessons learned

### Coming Soon
- `DIAGNOSES_STAGING_FILE_ANALYSIS.md`: Comprehensive diagnoses documentation
- `BINARY_FILES_STAGING_FILE_ANALYSIS.md`: DocumentReference extraction strategy
- `MEDICATIONS_STAGING_FILE_ANALYSIS.md`: Multi-table JOIN approach for medications
- `CHEMOTHERAPY_VALIDATION_REPORT.md`: 5-strategy identification methodology

---

## 📞 Support

For questions, issues, or contributions:
- **Repository**: adamcresnick/RADIANT_PCA
- **Branch**: fix/ci-pipeline-issues
- **Path**: BRIM_Analytics/athena_extraction_validation/

---

## 🏆 Acknowledgments

This workflow builds upon lessons learned from the **BRIM (Brain Immunotherapy) clinical trial** data pipeline, adapting comprehensive strategies for:
- Binary file discovery and annotation
- Multi-strategy chemotherapy identification
- FHIR resource validation
- S3 availability verification

**Key References**:
- BINARY_DOCUMENT_DISCOVERY_WORKFLOW.md (BRIM workflow)
- COMPREHENSIVE_CLINICAL_NOTES_ANALYSIS.md (documentation framework)
- BRIM_COMPLETE_WORKFLOW_GUIDE.md (end-to-end approach)

---

## 📊 Summary Statistics

**Total Extraction Results** (Single Patient: C1277724):
- **Medications**: 1,121 records (385 chemotherapy)
- **Imaging**: 181 studies (68% MRI)
- **Measurements**: 1,586 (289 anthropometric + 1,297 labs)
- **Diagnoses**: 23 problems (13 Active, 10 Resolved)
- **Documents**: 22,127 references (9,137 S3-available, 54.4%)

**Temporal Coverage**: Birth (2005-05-13) to present (2025-08-01) = **20.2 years of complete clinical data**

**Data Quality**:
- ✅ 100% RxNorm coding (medications)
- ✅ 100% ICD-10/SNOMED coding (diagnoses)
- ✅ 100% LOINC coding (lab tests)
- ✅ 97.5% encounter linkage (documents)
- ✅ 54.4% S3 availability (binary files)

**Execution Time**: ~45 minutes total (including 10 minutes for S3 checks)

---

**Last Updated**: 2025-01-10  
**Version**: 1.0  
**Status**: Production-Ready ✅
