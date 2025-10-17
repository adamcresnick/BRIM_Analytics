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
│   ├── extract_radiation_data.py                   # Radiation oncology (8 resources, 10 CSV outputs)
│   └── check_binary_s3_availability.py             # S3 verification (9,137 available, 54.4%)
│
├── staging_files/
│   ├── ALL_MEDICATIONS_METADATA.csv                # 1,121 records, 29 columns
│   ├── CHEMOTHERAPY_MEDICATIONS.csv                # 385 records (275 high-confidence)
│   ├── ALL_IMAGING_METADATA.csv                    # 181 records, 31 columns
│   ├── ALL_MEASUREMENTS_METADATA.csv               # 1,586 records (289 anthro + 1,297 labs)
│   ├── ALL_DIAGNOSES_METADATA.csv                  # 23 records, 17 columns
│   ├── ALL_BINARY_FILES_METADATA.csv               # 22,127 records, 25 columns
│   ├── ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv  # 22,127 records, 28 columns
│   └── patient_{id}/                               # Per-patient RT extraction (10 CSV files)
│       ├── radiation_oncology_consults.csv
│       ├── radiation_treatment_appointments.csv
│       ├── radiation_treatment_courses.csv
│       ├── radiation_care_plan_notes.csv
│       ├── radiation_care_plan_hierarchy.csv
│       ├── service_request_notes.csv
│       ├── service_request_rt_history.csv
│       ├── procedure_rt_codes.csv
│       ├── radiation_oncology_documents.csv
│       └── radiation_data_summary.csv
│
├── docs/
│   ├── MEASUREMENTS_STAGING_FILE_ANALYSIS.md       # Detailed measurements documentation
│   ├── COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md  # Complete RT extraction strategy
│   ├── DOCUMENT_RETRIEVAL_STRATEGY.md              # HTML/RTF vs PDF retrieval approach
│   ├── DOCUMENT_REFERENCE_RT_ANALYSIS.md           # DocumentReference findings
│   └── COLUMN_NAMING_CONVENTIONS.md                # Resource-prefixed column strategy
│
└── README.md                                        # This file
```

---

## 🏗️ Architecture: Config-Driven Multi-Patient Workflow

**Major Update (October 2025)**: All extraction scripts have been **refactored to use a centralized `patient_config.json`** file, enabling seamless multi-patient extraction without code changes.

### Key Benefits
- ✅ **No Code Modification**: Change patient by editing config file only
- ✅ **Reproducible**: Same config = identical extraction
- ✅ **Multi-Patient**: Process any participant by updating config
- ✅ **Standardized Outputs**: Generic filenames (`medications.csv`, `encounters.csv`) with patient-specific directories

### Config File Structure (`patient_config.json`)

```json
{
  "fhir_id": "eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3",
  "birth_date": "1988-05-13",
  "gender": "female",
  "output_dir": "staging_files/patient_eXdoUrDdY4gkdnZEs6uTeq",
  "database": "fhir_v2_prd_db",
  "aws_profile": "343218191717_AWSAdministratorAccess",
  "s3_output": "s3://aws-athena-query-results-343218191717-us-east-1/"
}
```

### Workflow Comparison

**Old Approach** (Patient-Specific Scripts):
```python
# Hardcoded in script
PATIENT_MRN = 'C1277724'
PATIENT_FHIR_ID = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
# Output: ALL_MEDICATIONS_METADATA_C1277724.csv
```

**New Approach** (Config-Driven):
```python
# Load from patient_config.json
config = json.load(open('patient_config.json'))
patient_fhir_id = config['fhir_id']
# Output: staging_files/patient_{shortid}/medications.csv
```

---

## 🚀 Quick Start

### Prerequisites

1. **AWS Configuration**:
   ```bash
   # Configure AWS SSO profile
   aws sso login --profile 343218191717_AWSAdministratorAccess
   export AWS_PROFILE=343218191717_AWSAdministratorAccess
   ```

2. **Python Dependencies**:
   ```bash
   pip install boto3 pandas pyarrow awswrangler
   ```

3. **Database Access**: 
   - Access to AWS Athena workgroup: `primary`
   - Read permissions for `fhir_prd_db` (primary) and `fhir_v2_prd_db` (supplementary)

4. **Patient Configuration**:
   - Edit `patient_config.json` with target patient details
   - Or use `patient_config_template.json` as starting point

### Running Config-Driven Extraction Scripts

**Step 1: Configure Patient**
```bash
# Edit patient_config.json with target patient
nano patient_config.json

# Or copy template
cp patient_config_template.json patient_config.json
```

**Step 2: Run Extractions**
```bash
cd scripts/config_driven_versions/

# Extract encounters (appointments, visits - ~10 seconds)
python3 extract_all_encounters_metadata.py
# Output: staging_files/patient_{shortid}/encounters.csv

# Extract procedures (CPT/HCPCS codes - ~10 seconds)
python3 extract_all_procedures_metadata.py
# Output: staging_files/patient_{shortid}/procedures.csv

# Extract medications (10 tables - ~30 seconds)
python3 extract_all_medications_metadata.py
# Output: staging_files/patient_{shortid}/medications.csv

# Filter chemotherapy (5 strategies - ~5 seconds)
python3 filter_chemotherapy_from_medications.py
# Output: staging_files/patient_{shortid}/chemotherapy.csv

# Extract imaging (3 radiology tables - ~10 seconds)
python3 extract_all_imaging_metadata.py
# Output: staging_files/patient_{shortid}/imaging.csv

# Extract measurements (labs + observations - ~10 seconds)
python3 extract_all_measurements_metadata.py
# Output: staging_files/patient_{shortid}/measurements.csv

# Extract diagnoses (problem list - ~3 seconds)
python3 extract_all_diagnoses_metadata.py
# Output: staging_files/patient_{shortid}/diagnoses.csv

# Extract binary files metadata (5 tables - ~10 seconds)
python3 extract_all_binary_files_metadata.py
# Output: staging_files/patient_{shortid}/binary_files.csv
```

**Step 3: Run Specialized Extractions**
```bash
cd ../  # Back to scripts/ directory

# Extract radiation oncology data (8 resources, ~60 seconds)
# Note: This still uses command-line argument approach
python3 extract_radiation_data.py PATIENT_FHIR_ID
# Output: staging_files/patient_PATIENT_FHIR_ID/ (10 CSV files)

# Check S3 availability (~10-15 minutes for 16,798 files)
python3 check_binary_s3_availability.py
```

**Complete Pipeline** (~70 seconds for standard extractions):
```bash
# Change to config-driven directory
cd scripts/config_driven_versions/

# Run all extractions in sequence
for script in extract_all_encounters_metadata.py \
              extract_all_procedures_metadata.py \
              extract_all_medications_metadata.py \
              filter_chemotherapy_from_medications.py \
              extract_all_imaging_metadata.py \
              extract_all_measurements_metadata.py \
              extract_all_diagnoses_metadata.py \
              extract_all_binary_files_metadata.py; do
    echo "Running $script..."
    python3 $script
done

echo "✅ All extractions complete!"
echo "📁 Results in: staging_files/patient_{shortid}/"
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

### 7. Radiation Oncology (8 Resource Types, 10 CSV Outputs)

**Script**: `extract_radiation_data.py`  
**Database**: `fhir_prd_db`  
**Resources Queried**: 8 (appointment, care_plan, service_request, procedure, document_reference)  
**Tables Joined**: 20+ sub-tables  
**Output**: 10 CSV files per patient in `staging_files/patient_{id}/`

**Key Features**:
- **Comprehensive RT Coverage**: Consults, appointments, treatment courses, notes, documents
- **Cross-Resource Alignment**: Consistent date fields for temporal correlation
- **Resource-Prefixed Columns**: Clear data provenance (cp_, sr_, proc_, doc_ prefixes)
- **RT-Specific Keywords**: 60+ radiation terms (radiation, radiotherapy, IMRT, proton, etc.)
- **Document Retrieval Strategy**: Flags HTML/RTF (already extracted) vs PDFs/images (need retrieval)

**Extraction Functions**:
1. **extract_radiation_oncology_consults()** - Radiation oncology consultation appointments
2. **extract_radiation_treatment_appointments()** - RT appointments with milestone detection
3. **extract_care_plan_notes()** - RT-related care plan notes with dose information
4. **extract_care_plan_hierarchy()** - Care plan parent-child relationships
5. **extract_service_request_notes()** - RT service request notes and dosage
6. **extract_service_request_reason_codes()** - RT history reason codes
7. **extract_procedure_rt_codes()** - CPT 77xxx radiation procedure codes (86 codes including proton)
8. **extract_procedure_notes()** - RT-specific procedure notes
9. **extract_radiation_oncology_documents()** - Rad Onc documents with retrieval flagging
10. **identify_treatment_courses()** - Treatment course detection from appointments

**Output Files** (per patient):
```
radiation_oncology_consults.csv          # Rad Onc consultation appointments
radiation_treatment_appointments.csv     # RT treatment appointments & milestones
radiation_treatment_courses.csv          # Identified treatment courses (start/end dates)
radiation_care_plan_notes.csv           # Care plan notes (cp_/cpn_ prefixes)
radiation_care_plan_hierarchy.csv       # Care plan relationships (cp_/cppo_ prefixes)
service_request_notes.csv               # Service request notes (sr_/srn_ prefixes)
service_request_rt_history.csv          # RT history codes (sr_/srrc_ prefixes)
procedure_rt_codes.csv                  # RT procedure codes (proc_/pcc_ prefixes)
radiation_oncology_documents.csv        # Rad Onc documents (doc_* prefixes)
radiation_data_summary.csv              # Extraction summary statistics
```

**Column Naming Convention**:
- **cp_** = care_plan main table
- **cpn_** = care_plan_note
- **cppo_** = care_plan_part_of (hierarchy)
- **sr_** = service_request main table
- **srn_** = service_request_note
- **srrc_** = service_request_reason_code
- **proc_** = procedure main table
- **pcc_** = procedure_code_coding
- **pn_** = procedure_note
- **doc_** = document_reference tables

**Example Results** (Patient eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3):
- **Rad Onc Consults**: 2 (initial + follow-up)
- **RT Appointments**: 50 (simulations, treatments, re-irradiation)
- **Treatment Courses**: 6 identified (with start/end dates, duration)
- **Care Plan Notes**: 23 (with dose information flags)
- **Care Plan Hierarchy**: 182 relationships (80 parents, 182 children)
- **Service Request Notes**: 167 (dosage information, general notes)
- **RT History Codes**: 14 (external beam radiation therapy history)
- **Procedure RT Codes**: 1 (CPT 77xxx)
- **Rad Onc Documents**: 140 (48 need retrieval, 92 already extracted)

**Data Quality**:
- **Temporal Alignment**: All resources include date fields for cross-referencing
- **Dose Detection**: Flags notes containing "Gy" for dose information
- **Re-irradiation Detection**: Identifies multiple treatment courses
- **Treatment Techniques**: Extracted from appointments (IMRT, proton, etc.)
- **Document Retrieval**: Distinguishes HTML/RTF (extracted) from PDFs (need retrieval)

**RT-Specific Keywords** (60+ terms):
```
radiation, radiotherapy, rad onc, xrt, sbrt, srs, imrt, vmat, igrt, proton,
brachytherapy, stereotactic, external beam, beam, dose, gy, gray, fraction,
treatment planning, simulation, isocenter, field, port, boost, re-irradiation
```

**Critical Discoveries**:
1. **DocumentReference Dual Strategy**: HTML/RTF docs already extracted via separate workflow; only PDFs/images need retrieval in RT workflow
2. **Practice Setting Filter**: `context_practice_setting_coding_display = 'Radiation Oncology'` is most reliable filter for RT documents
3. **CPT 77xxx Coverage**: 86 unique RT procedure codes including proton therapy (CPT 77525)
4. **Care Plan Hit Rate**: 27.5% of care plan notes contain RT keywords (high signal-to-noise)
5. **External Institution Records**: PDFs and TIFFs often contain external treatment summaries

**Documentation**:
- [`COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md`](docs/COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md): Complete strategy, resource coverage, validation
- [`DOCUMENT_RETRIEVAL_STRATEGY.md`](docs/DOCUMENT_RETRIEVAL_STRATEGY.md): HTML/RTF vs PDF/image retrieval approach
- [`DOCUMENT_REFERENCE_RT_ANALYSIS.md`](docs/DOCUMENT_REFERENCE_RT_ANALYSIS.md): DocumentReference analysis and findings
- [`COLUMN_NAMING_CONVENTIONS.md`](docs/COLUMN_NAMING_CONVENTIONS.md): Resource prefix strategy

---

### 8. S3 Binary Availability (9,137 Available)

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

### Architecture Evolution

1. **Config-Driven Refactoring (October 2025)**:
   - **Motivation**: Enable multi-patient extraction without code changes
   - **Implementation**: Centralized `patient_config.json` with standard schema
   - **Testing**: Validated with patient `eXdoUrDdY4gkdnZEs6uTeq` (1,377 records across 7 files)
   - **Performance**: ~70 seconds for complete extraction pipeline
   - **Location**: Config-driven scripts in `scripts/config_driven_versions/`
   - **Status**: ✅ All 7 extraction types tested and working
   - **Documentation**: See [`scripts/config_driven_versions/README.md`](scripts/config_driven_versions/README.md) and [`TEST_RESULTS_SUMMARY.md`](scripts/config_driven_versions/TEST_RESULTS_SUMMARY.md)

2. **Script Organization**:
   - **Original Scripts** (`scripts/`): Patient-specific, hardcoded IDs (maintained for backward compatibility)
   - **Config-Driven Scripts** (`scripts/config_driven_versions/`): JSON-based configuration (recommended)
   - **Radiation Therapy** (`scripts/extract_radiation_data.py`): Command-line argument approach (will migrate to config)

### Database Architecture Lessons

1. **fhir_prd_db vs fhir_v2_prd_db**:
   - `fhir_prd_db`: Complete dataset (9,364 DocumentReferences)
   - `fhir_v2_prd_db`: Partial/test dataset (76 DocumentReferences - only 0.8%!)
   - **Rule**: Use `fhir_prd_db` for Binary/DocumentReference, `fhir_v2_prd_db` for clinical resources
   - **Config Setting**: Specify database per resource type if needed

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
| **Radiation Therapy** | 444+ rows | Treatment courses | 86 CPT 77xxx codes | 8 resources, 10 CSV outputs |
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

### Config-Driven Design Pattern

**Architecture**: All extraction scripts inherit from a common pattern:
```python
class ResourceExtractor:
    def __init__(self, patient_config: dict):
        self.patient_fhir_id = patient_config['fhir_id']
        self.output_dir = Path(patient_config['output_dir'])
        self.database = patient_config['database']
        self.birth_date = patient_config.get('birth_date')
        
        # AWS initialization from config
        aws_profile = patient_config['aws_profile']
        session = boto3.Session(profile_name=aws_profile)
        self.athena = session.client('athena')
        self.s3 = session.client('s3')

def main():
    # Load config from standard location
    config_file = Path(__file__).parent.parent / 'patient_config.json'
    with open(config_file) as f:
        config = json.load(f)
    
    # Initialize and run
    extractor = ResourceExtractor(patient_config=config)
    extractor.extract()
```

**Benefits**:
- **Separation of Concerns**: Config (data) separate from logic (code)
- **Version Control Safe**: Config excluded from git via .gitignore
- **Testing**: Easy to swap configs for different test patients
- **Production Ready**: Same code runs in dev/test/prod with different configs

**Standardized Output Structure**:
```
staging_files/
└── patient_{shortid}/          # e.g., patient_eXdoUrDdY4gkdnZEs6uTeq/
    ├── encounters.csv          # Appointments, visits
    ├── procedures.csv          # CPT/HCPCS codes
    ├── medications.csv         # RxNorm medications
    ├── chemotherapy.csv        # Filtered chemo agents
    ├── imaging.csv             # Radiology studies
    ├── measurements.csv        # Labs + observations
    ├── diagnoses.csv           # ICD-10/SNOMED
    └── binary_files.csv        # DocumentReference metadata
```

### AWS Services
- **Athena**: SQL queries against FHIR HealthLake data
- **S3**: Binary file storage and query results
- **SSO**: Secure authentication via AWS profiles (configurable)
- **Workgroup**: `primary` (configured for result location)

### Python Stack
- **boto3**: AWS SDK (Athena, S3 clients)
- **pandas**: DataFrame operations, CSV I/O
- **json**: Config file parsing
- **pathlib**: Cross-platform path handling
- **pyarrow**: Parquet support (optional)
- **awswrangler**: Athena query simplification (optional)

### Logging Strategy
- **Dual Output**: Console + log files
- **Progress Tracking**: Every 100 records for long-running operations
- **Execution Summaries**: Counts, percentages, temporal coverage
- **Error Handling**: Graceful failures with detailed error messages
- **Patient Privacy**: Patient identifiers only in logs (not CSV outputs)

---

## 📝 Future Enhancements

### Completed Features ✅
1. **Radiation Therapy Extraction**: 8 FHIR resources, 10 CSV outputs per patient
   - Consults, appointments, treatment courses
   - Care plan notes and hierarchy
   - Service request notes and history codes
   - Procedure RT codes (CPT 77xxx)
   - Radiation oncology documents with retrieval flags

### Planned Features
1. **Encounters Extraction**: Comprehensive encounter staging with diagnosis linkage
2. **Procedures Extraction**: Surgical procedures, therapeutic procedures (schema discovered)
3. **Immunizations**: Vaccine history with CVX codes
4. **Vital Signs**: Temperature, blood pressure, pulse, respiration
5. **Allergies**: Allergy/intolerance list with severity
6. **Family History**: Hereditary conditions, genetic risk factors
7. **Social History**: Smoking, alcohol, occupation

### Technical Improvements
1. **Incremental Updates**: Delta extraction for new/modified records
2. **Data Validation**: Automated checks against gold standard
3. **Schema Evolution**: Detect and adapt to FHIR schema changes
4. **Parallel Processing**: Multi-threaded S3 availability checks
5. **Documentation Generation**: Auto-generate analysis reports
6. **Radiation Binary Retrieval**: Implement S3 binary content retrieval for RT PDFs/images
7. **RT Document OCR**: Text extraction from scanned external treatment summaries
8. **Dose Information Extraction**: NLP parsing of dose, fractionation, technique from notes

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
- [`MEASUREMENTS_STAGING_FILE_ANALYSIS.md`](docs/MEASUREMENTS_STAGING_FILE_ANALYSIS.md): 450+ lines documenting measurements extraction strategy, ID format discovery, query approach, clinical context, and 8 critical lessons learned
- [`COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md`](docs/COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md): Complete radiation oncology extraction strategy covering 8 FHIR resources, column naming conventions, RT-specific keywords, cross-resource validation
- [`DOCUMENT_RETRIEVAL_STRATEGY.md`](docs/DOCUMENT_RETRIEVAL_STRATEGY.md): Dual approach for radiation oncology documents - HTML/RTF already extracted vs PDFs/images needing retrieval
- [`DOCUMENT_REFERENCE_RT_ANALYSIS.md`](docs/DOCUMENT_REFERENCE_RT_ANALYSIS.md): DocumentReference analysis findings, MIME type distribution, practice setting filters, external institution identification
- [`COLUMN_NAMING_CONVENTIONS.md`](docs/COLUMN_NAMING_CONVENTIONS.md): Resource-prefixed column naming strategy for clear data provenance

### Coming Soon
- `ENCOUNTERS_STAGING_FILE_COMPLETE.md`: Comprehensive encounter extraction with diagnosis linkage
- `PROCEDURES_STAGING_FILE_COMPLETE.md`: Surgical and therapeutic procedures staging file
- `DIAGNOSES_STAGING_FILE_ANALYSIS.md`: Comprehensive diagnoses documentation
- `BINARY_FILES_STAGING_FILE_ANALYSIS.md`: Complete DocumentReference extraction strategy
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

**Total Extraction Results**:

**Patient C1277724** (Original hardcoded scripts):
- **Medications**: 1,121 records (385 chemotherapy)
- **Imaging**: 181 studies (68% MRI)
- **Measurements**: 1,586 (289 anthropometric + 1,297 labs)
- **Diagnoses**: 23 problems (13 Active, 10 Resolved)
- **Radiation Therapy**: 444+ rows across 10 CSV files (consults, appointments, notes, documents)
- **Documents**: 22,127 references (9,137 S3-available, 54.4%)

**Patient eXdoUrDdY4gkdnZEs6uTeq** (Config-driven scripts validation):
- **Encounters**: 70 records (appointments, visits)
- **Procedures**: 15 records (CPT/HCPCS codes)
- **Medications**: 156 records (14 chemotherapy)
- **Imaging**: 56 studies (MRI, CT, X-ray)
- **Measurements**: 1,058 records (labs + observations)
- **Diagnoses**: 8 problems (ICD-10/SNOMED)
- **Total**: 1,377 records across 7 files in ~70 seconds

**Temporal Coverage**: Birth (2005-05-13) to present (2025-08-01) = **20.2 years of complete clinical data**

**Data Quality**:
- ✅ 100% RxNorm coding (medications)
- ✅ 100% ICD-10/SNOMED coding (diagnoses)
- ✅ 100% LOINC coding (lab tests)
- ✅ 97.5% encounter linkage (documents)
- ✅ 54.4% S3 availability (binary files)
- ✅ 100% date field capture (radiation therapy - cross-resource alignment)
- ✅ 86 RT procedure codes (CPT 77xxx including proton therapy)
- ✅ 60+ RT-specific keywords for high signal-to-noise filtering

**Execution Time**: ~50 minutes total (including 10 minutes for S3 checks, 1 minute for radiation extraction)

---

**Last Updated**: 2025-01-10  
**Version**: 1.0  
**Status**: Production-Ready ✅
