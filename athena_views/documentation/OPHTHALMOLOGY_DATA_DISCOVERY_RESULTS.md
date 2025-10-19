# Ophthalmology Data Discovery Results

**Date**: 2025-10-18
**Database**: fhir_v2_prd_db (CBTN Production)
**Purpose**: Identify ophthalmology assessment data for brain tumor patients with visual deficits

---

## Executive Summary

Comprehensive ophthalmology data exists across **6 FHIR resource tables**, capturing assessments for **631+ unique patients** (when combining all sources). The data includes structured observations, procedure records, diagnostic reports, service orders, and binary document files spanning visual acuity, visual fields, OCT imaging, and fundus exams.

**Key Finding**: Rich longitudinal monitoring data exists, particularly for OCT optic nerve imaging (632 procedures, 187 patients) and visual field testing (629 procedures, 180 patients), critical for tracking optic pathway glioma and craniopharyngioma patients.

---

## Data Coverage by FHIR Table

### Table 1: Observation
- **Total Records**: 24,013
- **Unique Patients**: 315
- **Records with Numeric Values**: 24,013
- **Records with Text Values**: 24,013

**Top Observation Types**:
1. **Visual Acuity Workflow** (1,129 records, 177 patients)
2. **Fundus Disc Exams - Left Eye** (826 records, 172 patients)
3. **Fundus Disc Exams - Right Eye** (805 records, 169 patients)
4. **Visual Acuity Decreased** (569 records, 66 patients) ⚠️ Clinical alert finding
5. **Fundus Macula Exams** (1,137 combined left/right, 163 patients)

**Multi-Component Observations**:
- Observation_component table contains **14,839 observations** with separate "Line 1", "Line 2", etc. components (likely multi-line visual acuity charts)
- Enables capture of right/left eye separate measurements

---

### Table 2: Procedure
- **Total Procedures**: 2,345
- **Unique Patients**: 410
- **Completed Procedures**: 2,345 (100%)

**Top Procedure Types**:
1. **OCT, Optic Nerve - Both Eyes** (632 procedures, 187 patients)
2. **Visual Field, Extended - Both Eyes** (629 procedures, 180 patients)
3. **OCT, Retina - Both Eyes** (427 procedures, 118 patients)
4. **Visual Field Exam, Extended** (182 procedures, 104 patients)
5. **Fundus Photography** (71 procedures, 60 patients)

**CPT Code Coverage** (from procedure_code_coding sub-table):
- **92083** - Visual Field Extended Exam: 806 procedures, 247 patients
- **92133** - OCT Optic Nerve: 636 procedures, 187 patients
- **92134** - OCT Retina: 424 procedures, 117 patients
- **92082** - Visual Field Intermediate: 97 procedures, 61 patients
- **92250** - Fundus Photography: 72 procedures, 57 patients

**Surgical Procedures Captured**:
- Optic nerve decompression (12 procedures)
- Optic pathway glioma biopsy/resection (5 procedures)
- Exam under anesthesia (11 procedures)

---

### Table 3: ServiceRequest (Orders)
- **Total Orders**: 4,137
- **Unique Patients**: 631 ⭐ **Highest patient coverage**
- **Completed Orders**: 3,929 (95%)
- **Actual Orders (intent='order')**: 3,505 (85%)

**Top Order Types**:
1. **OCT, Optic Nerve** (612 orders, 185 patients)
2. **Visual Field, Extended** (592 orders, 166 patients)
3. **OCT, Retina** (394 orders, 110 patients)
4. **Ophthalmic Diagnostic Imaging - Optic Nerve** (209 orders, 76 patients)
5. **Visual Field Exam - Intermediate** (122 orders, 71 patients)

**Specialized Testing Orders**:
- **Neuromyelitis Optica Antibody** (47 orders, 18 patients) - Important for differential diagnosis of optic neuritis

---

### Table 4: DiagnosticReport
- **Total Reports**: 3,731
- **Unique Patients**: 637
- **Final Reports**: 3,361 (90%)

**Top Report Types**:
1. **OCT, Optic Nerve** (601 reports, 181 patients)
2. **Visual Field, Extended** (589 reports, 166 patients)
3. **OCT, Retina** (387 reports, 108 patients)
4. **Eye Chart Vision Screening** (244 reports, 153 patients) - Pediatric screening
5. **Fundus Photos - Both Eyes** (43 reports, 34 patients)

---

### Table 5: DocumentReference (Binary Files)
- **Total Documents**: 731
- **Unique Patients**: 185
- **File Types Available**: PDFs, images (via content_attachment_url)

**Top Document Categories**:
1. **OCT Archived Procedural Results** (15 documents)
2. **Visual Field Exam Reports** (7 documents, "Other" type)
3. **Ophthalmology Consult Notes** (10+ documents from CHOP and other institutions)
4. **Goldman Visual Field Reports** (2+ documents) - Gold standard perimetry
5. **Craniopharyngioma with Visual Field Defects** (2 documents) - Key diagnostic context

**Notable Finding**: Document descriptions include diagnoses like "Bitemporal hemianopia", "Visual field defect of both eyes" - indicates capture of clinical context.

---

### Table 6: Encounter
- **Total Encounters**: 567
- **Unique Patients**: 460
- **Encounter Type**: Ophthalmology visits (filtered via encounter_type sub-table)

---

## Clinical Data Quality Assessment

### Strengths
1. **Longitudinal Monitoring**: Patients have serial OCT and visual field exams over years
2. **Structured + Unstructured**: Combination of coded observations (CPT 92133, 92083) and free-text findings
3. **Bilateral Capture**: Most exams documented for both eyes separately (OU - both eyes)
4. **Multi-Source Validation**: Same assessment often appears in procedure, diagnostic_report, AND document_reference
5. **Component-Level Detail**: observation_component enables capture of multi-part visual acuity (e.g., Line 1: 20/20, Line 2: 20/25)

### Gaps Identified
1. **Visual Acuity Numeric Values**: While 24,013 observations exist, need to validate if Snellen/logMAR scores are in numeric_value or text_value fields
2. **Optic Disc Findings**: Observations capture "fundus disc normal" but may lack quantitative cup-to-disc ratio measurements
3. **Visual Field Defect Patterns**: Text-based findings (e.g., "hemianopia") in observation.value_string, not structured fields
4. **OCT Quantitative Data**: RNFL thickness, ganglion cell layer measurements likely in observation_component or embedded in diagnostic reports

---

## Assessment Categories Defined

The `v_ophthalmology_assessments` view organizes data into these clinical categories:

### Observation-Based Categories
1. **visual_acuity** - Snellen, logMAR, ETDRS, HOTV, Lea charts
2. **optic_disc_papilledema** - Elevated optic disc from increased ICP
3. **optic_disc_exam** - Funduscopic disc assessment
4. **fundus_macula** - Macular integrity
5. **fundus_vessels** - Retinal vessel exam
6. **fundus_vitreous** - Vitreous hemorrhage/opacities
7. **fundus_periphery** - Peripheral retina

### Procedure-Based Categories
8. **visual_field** - Perimetry testing (Goldmann, Humphrey)
9. **oct_optic_nerve** - RNFL, optic nerve head imaging
10. **oct_retina** - Retinal/macular OCT
11. **oct_macula** - Macula-specific OCT
12. **fundus_photography** - Retinal photo documentation
13. **ophthalmology_exam** - Comprehensive eye exams

### Order/Report Categories
14. **visual_field_order** / **visual_field_report**
15. **oct_optic_nerve_order** / **oct_optic_nerve_report**
16. **oct_retina_order** / **oct_retina_report**
17. **vision_screening_report** - Pediatric screening

### Document Categories
18. **oct_document** - Binary OCT files
19. **visual_field_document** - VF test printouts
20. **fundus_document** - Fundus photo files
21. **ophthalmology_consult** - Consult notes from external ophthalmology

---

## View Schema: v_ophthalmology_assessments

### Core Fields
- `record_fhir_id` - FHIR resource ID (observation, procedure, etc.)
- `patient_fhir_id` - Patient identifier
- `assessment_date` - Date of exam/order/report
- `assessment_description` - Original code_text or description
- `assessment_category` - Standardized category (see list above)
- `source_table` - Origin (observation, procedure, service_request, diagnostic_report, document_reference)
- `record_status` - Status (final, completed, active)

### Value Fields (Observations)
- `numeric_value` - Quantitative measurements
- `value_unit` - Units (e.g., "logMAR", "mmHg")
- `text_value` - Free-text findings
- `component_name` - Multi-part observation component name
- `component_numeric_value` - Component-level values
- `component_unit` - Component units

### Procedure Fields
- `cpt_code` - CPT code (92133, 92083, etc.)
- `cpt_description` - CPT code description

### Order Fields
- `order_intent` - order vs proposal

### Document Fields
- `file_url` - Binary file location (S3, FHIR server)
- `file_type` - MIME type (application/pdf, image/png)

### Temporal
- `full_datetime` - Complete timestamp with time

---

## Sample Patient Coverage Analysis

**Example High-Utilization Patient** (validation query needed):
- Likely has 10+ OCT exams over 3+ years
- Serial visual field testing (quarterly or biannual)
- Visual acuity documented at each visit
- Fundus photography for progression monitoring
- Consult notes from neuro-ophthalmology

**Expected Clinical Scenario**: Optic pathway glioma patient on chemotherapy with serial monitoring for:
1. Visual acuity decline (treatment effect vs tumor progression)
2. Visual field defects (bitemporal hemianopia from chiasm compression)
3. Optic disc changes (papilledema from hydrocephalus, optic atrophy from tumor/radiation)
4. OCT RNFL thinning (quantitative axonal loss measurement)

---

## Recommended Next Steps

### Immediate (Pre-Analysis)
1. ✅ **Execute view creation** - Run SECTION 7 SQL in Athena
2. **Run validation queries** - Verify patient counts, date ranges, category distribution
3. **Sample data inspection** - Pull 5-10 patients with complete longitudinal data

### Data Quality Enhancement
4. **Visual acuity parsing** - Extract numeric Snellen (20/X) and logMAR values from text_value
5. **Visual field defect extraction** - NLP or regex to identify hemianopia, quadrantanopia, scotoma patterns
6. **OCT metric extraction** - Parse RNFL thickness from diagnostic_report text or observation_component

### Clinical Analysis
7. **Temporal analysis** - Identify patients with ≥3 OCT exams to calculate RNFL change rate
8. **Treatment correlation** - Join with chemotherapy/radiation views to assess visual toxicity
9. **Tumor-vision correlation** - Join with imaging (MRI) to correlate tumor size with visual deficits
10. **Risk stratification** - Identify patients with declining vision requiring intervention

### Documentation
11. **Data dictionary** - Document all assessment_category definitions for analysts
12. **Clinical use cases** - Create example queries for common research questions
13. **Binary file access** - Document how to retrieve and view OCT/VF files from file_url

---

## Files Created/Updated

1. **ATHENA_VIEW_CREATION_QUERIES.sql** (Section 7 added)
   - Lines 4903-5612: v_ophthalmology_assessments view definition
   - 700+ lines of SQL with 13 CTEs
   - 5 validation queries included

2. **OPHTHALMOLOGY_EXPLORATORY_QUERIES.sql** (Previously created)
   - 30+ exploratory queries used for data discovery
   - Location: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/queries/`

3. **OPHTHALMOLOGY_ASSESSMENT.md** (Previously created)
   - Clinical background and taxonomy
   - Location: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/documentation/`

4. **OPHTHALMOLOGY_DATA_DISCOVERY_RESULTS.md** (This document)
   - Summary of findings from exploratory queries
   - Location: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/documentation/`

---

## Query Execution Summary

**Queries Run**: 10+ exploratory queries
**Execution Time**: ~30 seconds total
**Database**: fhir_v2_prd_db (Athena)
**AWS Profile**: radiant-prod

**Tables Analyzed**:
- ✅ observation (main + observation_component sub-table)
- ✅ procedure (main + procedure_code_coding sub-table)
- ✅ service_request
- ✅ diagnostic_report
- ✅ document_reference (main + document_reference_content sub-table)
- ✅ encounter (main + encounter_type sub-table)

**Schema Discoveries**:
- observation_component uses `component_code_text` (not `code_text`)
- procedure_code_coding captures CPT codes separately from procedure.code_text
- document_reference_content stores binary file URLs

---

## Contact for Questions

**Analyst**: Claude Code
**Session Date**: 2025-10-18
**Data Source**: Children's Brain Tumor Network (CBTN) FHIR bulk export v2
