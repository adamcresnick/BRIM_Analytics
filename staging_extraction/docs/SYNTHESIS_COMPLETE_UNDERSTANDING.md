# Complete Understanding Synthesis - Ready for CSV Inventory

**Date**: October 7, 2025  
**Status**: ✅ FULLY REVIEWED - Ready to Execute Inventory  
**Documents Reviewed**: 12 critical files (3,500+ lines)

---

## 🎯 Complete Strategic Picture

### What You're Building: Hybrid Athena + BRIM Pipeline

**Your Strategy** (validated across all documentation):

```
┌──────────────────────────────────────────────────────────┐
│ 1. GOLD STANDARD (Validation Target)                    │
│    - 18 CSV files: demographics, diagnosis, treatments,  │
│      concomitant_medications, imaging, measurements, etc │
│    - Human-curated for 191 patients                      │
│    - Location: data/20250723_multitab_csvs/             │
└──────────────────────────────────────────────────────────┘
                           ↓ validates
┌──────────────────────────────────────────────────────────┐
│ 2. ATHENA STRUCTURED EXTRACTION (Layer 1)               │
│    - Source: fhir_v2_prd_db materialized views           │
│    - Method: Direct SQL queries                          │
│    - Coverage: 61% of variables (20/33 fully structured) │
│    - Output: Reference CSVs + STRUCTURED_* documents     │
└──────────────────────────────────────────────────────────┘
                           ↓ augments
┌──────────────────────────────────────────────────────────┐
│ 3. BRIM NARRATIVE EXTRACTION (Layer 2)                  │
│    - Source: Binary documents (operative, pathology)     │
│    - Method: LLM extraction via BRIM API                 │
│    - Coverage: 39% of variables (13/33 narrative-only)   │
│    - Output: BRIM results validated against gold std     │
└──────────────────────────────────────────────────────────┘
```

---

## 📊 33 Variables: Complete Coverage Matrix

### From CSV_VARIABLE_QUICK_REFERENCE.md

**✅ STRUCTURED (20 variables - 61%)** - Athena SQL extraction:
1. legal_sex ← `patient.gender`
2. date_of_birth ← `patient.birth_date`
3. race ← `patient_extension` (US Core)
4. ethnicity ← `patient_extension` (US Core)
5. cns_integrated_diagnosis ← `problem_list_diagnoses.diagnosis_name`
6. diagnosis_date ← `problem_list_diagnoses.onset_date_time`
7. surgery (boolean) ← `procedure` COUNT
8. age_at_surgery ← `procedure.performed_date_time`
9. chemotherapy (boolean) ← `patient_medications` COUNT
10. chemotherapy_agents ← `patient_medications.medication_name` (⚠️ FILTER TOO NARROW!)
11. age_at_chemo_start ← `patient_medications.authored_on`
12. age_at_chemo_stop ← `patient_medications.end_date`
13. radiation (boolean) ← `procedure` CPT 77xxx
14. mutation ← `observation.value_string` (BRAF fusion)
15. age_at_molecular_test ← `observation.effective_datetime`
16. molecular_tests ← `molecular_tests` OR `observation`
17. age_at_encounter ← `encounter.period_start`
18. follow_up_visit_status ← `encounter.status`
19. shunt_required ← `procedure` CPT 62201
20. clinical_status ← `patient.deceased`

**🟡 HYBRID (8 variables - 24%)** - Structured + Narrative:
21. who_grade ← `condition.stage` (partial) + pathology reports
22. specimen_origin ← Timeline + context
23. radiation_type ← `procedure.code` + notes
24. idh_mutation ← BRAF-only → infer wildtype
25. mgmt_methylation ← `observation` OR N/A
26. tumor_location ← `condition.bodySite` (generic) + radiology
27. metastasis ← `condition` OR notes
28. conditions ← `condition` OR notes

**🔴 NARRATIVE ONLY (5 variables - 15%)** - BRIM required:
29. extent_of_resection ← Operative notes ("gross total resection")
30. protocol_name ← Oncology notes (trial names)
31. chemotherapy_type ← Oncology notes (protocol vs standard)
32. metastasis_location ← Radiology reports (specific sites)
33. tumor_status ← Oncology notes (stable/change)

---

## ✅ What You've Already Built (DO NOT DUPLICATE!)

### BRIM_Analytics Repository Scripts

**1. extract_structured_data.py** (767 lines) ✅ OPERATIONAL
- **Current Extraction**:
  - ✅ diagnosis_date (from `problem_list_diagnoses`)
  - ✅ primary_diagnosis (from `problem_list_diagnoses`)
  - ✅ patient_gender (from `patient`)
  - ✅ date_of_birth (from `patient`)
  - ✅ surgeries (4 procedures from `procedure`)
  - ✅ molecular_markers (BRAF from `observation`)
  - ⚠️ treatments (48 bevacizumab, MISSING vinblastine/selumetinib)
  - ✅ radiation_therapy (boolean from `procedure` CPT codes)

**2. pilot_generate_brim_csvs.py** ✅ OPERATIONAL
- Creates project.csv with:
  - Row 1: FHIR_BUNDLE (complete FHIR resources)
  - Rows 2-5: STRUCTURED_* documents (from Athena queries)
  - Rows 6+: Binary documents (operative, pathology, etc.)
- Creates variables.csv (35 variables)
- Creates decisions.csv (14 rules)

**3. athena_document_prioritizer.py** ✅ OPERATIONAL
- Queries `document_reference` for high-value notes
- Tiered selection: Pathology > Operative > Oncology

**4. retrieve_binary_documents.py** ✅ OPERATIONAL
- Downloads Binary content from S3 for BRIM

### fhir_athena_crosswalk Repository Scripts

**5. map_demographics.py** ✅ COMPLETED & VALIDATED
- Source: `patient_access` table
- Coverage: 100% for gender, race, ethnicity
- **Action Required**: Test on BRIM_Analytics patient C1277724

**6. complete_medication_crosswalk.py** ✅ COMPLETED & VALIDATED
- Source: `patient_medications` table
- Coverage: 85-90% with comprehensive RxNorm mapping
- **Action Required**: Review RxNorm list, ensure vinblastine/selumetinib included

**7. map_diagnosis.py** ✅ COMPLETED & VALIDATED
- Source: `problem_list_diagnoses`
- Coverage: 100% for diagnosis name, date, ICD-10

**8. map_imaging_clinical_related_v4.py** 🔄 IN PROGRESS
- Source: `radiology_imaging_mri`, `radiology_imaging_mri_results`, `medication_request`
- Coverage: 90%+ (missing only clinical status interpretation)

**9. map_measurements.py** 🔄 IN PROGRESS
- Source: `observation` (vital signs)
- Coverage: 95%+ (missing percentile calculations)

**10. corticosteroid_reference.py** ✅ COMPLETED
- 53 RxNorm codes for 10 corticosteroid drug families

---

## ⚠️ Critical Gaps Identified (HIGH PRIORITY)

### Gap 1: Chemotherapy Filter Too Narrow ❌ BLOCKING

**Problem** (from CSV_VARIABLE_QUICK_REFERENCE.md):
```python
# CURRENT FILTER:
WHERE LOWER(medication_name) LIKE '%bevacizumab%'
   OR LOWER(medication_name) LIKE '%temozolomide%'
   OR LOWER(medication_name) LIKE '%chemotherapy%'

# GOLD STANDARD C1277724 EXPECTS:
- vinblastine (Event 2: ages 5130-5492)
- bevacizumab (Event 2: ages 5130-5492) ✅ FOUND
- selumetinib (Event 3: ages 5873-7049)

# RESULT:
✅ bevacizumab: 48 records extracted
❌ vinblastine: MISSING
❌ selumetinib: MISSING
```

**Impact**: 1/3 chemotherapy agents detected (33% accuracy)

**Fix Required**:
```python
CHEMO_KEYWORDS = [
    'temozolomide', 'temodar', 'bevacizumab', 'avastin',
    'vincristine', 'vinblastine', 'vinorelbine',  # ← ADD THESE
    'selumetinib', 'koselugo',                    # ← ADD THESE
    'carboplatin', 'cisplatin', 'lomustine', 'ccnu',
    'cyclophosphamide', 'etoposide', 'irinotecan',
    'procarbazine', 'methotrexate', 'dabrafenib', 'trametinib'
]
```

### Gap 2: Race/Ethnicity Not Extracted ⏳ EASY WIN

**Status**: 100% structured in `patient_access` but not extracted yet
**Gold Standard**: C1277724 = "White", "Not Hispanic or Latino"
**Fix**: Add 2 queries to `extract_structured_data.py`

### Gap 3: Surgery Body Site Not Extracted ⏳ EASY WIN

**Status**: Partially structured in `procedure_body_site` table
**Note**: Often generic ("Brain"), narrative provides specifics
**Fix**: Add LEFT JOIN to surgery extraction query

### Gap 4: Radiation Type Not Extracted ⏳ MEDIUM

**Status**: Boolean extracted (radiation=No for C1277724), but not type
**Source**: `procedure.code` OR narrative
**Fix**: Add radiation_type extraction if radiation=Yes

### Gap 5: Molecular Test Ages Not Extracted ⏳ EASY WIN

**Status**: Markers found (BRAF fusion), but ages not saved
**Source**: `observation.effective_datetime`
**Fix**: Save age_at_molecular_test alongside marker

---

## 📂 Gold Standard CSV Structure (From Actual Files)

### demographics.csv (191 rows, 4 columns)
```csv
research_id,legal_sex,race,ethnicity
C1277724,Female,White,Not Hispanic or Latino
```
**Athena Coverage**: 100% from `patient_access` table

### diagnosis.csv (1,691 rows, 19 columns)
```csv
research_id,event_id,autopsy_performed,clinical_status_at_event,cause_of_death,
event_type,age_at_event_days,cns_integrated_category,cns_integrated_diagnosis,
who_grade,metastasis,metastasis_location,metastasis_location_other,
site_of_progression,tumor_or_molecular_tests_performed,
tumor_or_molecular_tests_performed_other,tumor_location,tumor_location_other,
shunt_required,shunt_required_other
```
**Athena Coverage**: ~60% (diagnosis, date structured; WHO grade, metastasis location narrative)

### treatments.csv (697 rows, 26 columns)
```csv
research_id,event_id,treatment_status,reason_for_treatment_change,surgery,
age_at_surgery,extent_of_tumor_resection,specimen_collection_origin,
chemotherapy,chemotherapy_type,protocol_name,chemotherapy_agents,
age_at_chemo_start,age_at_chemo_stop,autologous_stem_cell_transplant,
radiation,radiation_type,radiation_type_other,radiation_site,
radiation_site_other,total_radiation_dose,total_radiation_dose_unit,
total_radiation_dose_focal,total_radiation_dose_focal_unit,
age_at_radiation_start,age_at_radiation_stop,date_for_treatment_ordering_only
```
**Athena Coverage**: ~70% (dates, agents structured; extent, protocol narrative)

### concomitant_medications.csv (9,550 rows, 8 columns)
```csv
event_id,conmed_timepoint,research_id,form_conmed_number,age_at_conmed_date,
rxnorm_cui,medication_name,conmed_routine
```
**Athena Coverage**: 85-90% from `patient_medications` (per fhir_athena_crosswalk validation)

### imaging_clinical_related.csv (4,037 rows, 21 columns)
```csv
research_id,age_at_date_scan,cortico_yn,cortico_number,
cortico_1_rxnorm_cui,cortico_1_name,cortico_1_dose,
[repeated for cortico_2-5],
ophtho_imaging_yn,imaging_clinical_status
```
**Athena Coverage**: 90%+ (dates, RxNorm structured; clinical status narrative)

### measurements.csv (7,816 rows, 9 columns)
```csv
research_id,age_at_measurement_date,measurement_available,
height_cm,height_percentile,weight_kg,weight_percentile,
head_circumference_cm,head_circumference_percentile
```
**Athena Coverage**: 95%+ from `observation` (missing percentile calculations)

---

## 🎯 Next Steps: CSV Inventory Execution

### Step 1: Run Inventory Script ✅ READY

**Execute**:
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics
python3 athena_extraction_validation/scripts/inventory_gold_standard_csvs.py \
  --csv-dir /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/data/20250723_multitab_csvs \
  --output-dir athena_extraction_validation/inventory
```

**Expected Output**:
1. `gold_standard_inventory.json` - Complete metadata for all 18 CSVs
2. `gold_standard_summary.md` - Human-readable summary with:
   - Row counts per CSV
   - Column names and data types
   - Sample values
   - Identifier fields (research_id, event_id)
   - Date fields
   - Categorical fields with value distributions

### Step 2: Create Variable-to-CSV Mapping

**After inventory completes**, map each of 33 variables to:
- Gold standard CSV(s) containing the variable
- Specific column name
- Athena table/column (if structured)
- Extractability: 100% / Partial / 0% (BRIM needed)
- Existing script reference (if any)

### Step 3: Validate Existing Scripts

**Priority order**:
1. Test `map_demographics.py` on C1277724
2. Test `complete_medication_crosswalk.py` on C1277724 (check vinblastine/selumetinib)
3. Test `map_diagnosis.py` on C1277724
4. Complete `map_imaging_clinical_related_v4.py`
5. Complete `map_measurements.py`

### Step 4: Close Known Gaps

**Enhance `extract_structured_data.py`**:
1. Add race/ethnicity queries
2. Expand chemotherapy filter (comprehensive agent list)
3. Add surgery_body_site extraction
4. Add molecular_test_ages
5. Test on C1277724, compare to gold standard

### Step 5: Define BRIM Scope

**Create BRIM variable specifications** for 13 narrative-only variables:
- extent_of_resection
- protocol_name
- chemotherapy_type
- metastasis_location
- tumor_status
- who_grade (supplement structured)
- Others as needed

---

## 🔑 Key Insights From Documentation Review

### From PHASE_1_COMPLETE.md

**Achievements**:
- ✅ patient_gender extracted (100% structured)
- ✅ date_of_birth extracted (100% structured)
- ✅ primary_diagnosis extracted (100% structured)
- ✅ radiation_therapy extracted (boolean, 100% structured)
- **Before Phase 1**: 4/14 variables (29%)
- **After Phase 1**: 7/14 variables (50%)
- **Improvement**: +3 variables (+21%)

### From PHASE_1_QUICK_SUMMARY.md

**BRIM Pilot Results**:
- **Accuracy**: 87.5% (3.5/4 correct) for surgical variables
- **Success**: STRUCTURED documents prioritized correctly
- **Lesson**: Table-based extraction (STRUCTURED_Surgical History) works better than free text

### From ATHENA_ARCHITECTURE_CLARIFICATION.md

**Two Database Layers**:
1. **HealthLake Raw FHIR** (primary source):
   - Database: `radiant_prd_343218191717_us_east_1_prd_fhir_datastore_*_healthlake_view`
   - Complete FHIR Patient JSON with US Core extensions
2. **Materialized Views** (convenience layer):
   - Database: `fhir_v2_prd_db`
   - Pre-flattened for easy querying (use this!)
   - Validated: `patient_access` contains race/ethnicity already extracted

### From COMPREHENSIVE_VARIABLE_STRATEGY_REVIEW.md

**Three-Layer Architecture**:
- **Layer 1**: Athena structured metadata (CSV pre-population)
- **Layer 2**: Athena narrative text (Binary documents)
- **Layer 3**: FHIR JSON cast (complete Bundle)

**Key Pattern**:
```
PRIORITY SEARCH ORDER:
1. STRUCTURED_{SUMMARY} - Ground truth from materialized views
2. {DOCUMENT_TYPES} - Narrative confirmations
3. {FALLBACK} - If above unavailable
```

### From COMPLETE_STRATEGY_UNDERSTANDING.md

**Division of Labor**:
- **Materialized Views**: Dates, codes, counts, structured values (100% reliable)
- **BRIM**: Surgeon assessments, radiologist impressions, clinical judgments

**Project.csv Pattern**:
- Row 1: FHIR_BUNDLE
- Rows 2-5: STRUCTURED_* summaries (from Athena)
- Rows 6+: Binary documents (from S3)

### From METADATA_DRIVEN_ABSTRACTION_STRATEGY.md

**Specialty-Based Prioritization**:
- Ophthalmology: 18 documents (0.5% of 3,865)
- Oncology: 246 documents (6.4%)
- Neurosurgery: 87 documents (2.3%)
- **Strategy**: Route variables to relevant specialty documents

**Document Type Routing**:
- Operative Notes → surgical variables
- Pathology Reports → diagnostic variables
- Progress Notes → status variables
- Radiology Reports → imaging variables

### From MASTER_DOCUMENTATION_REVIEW.md

**fhir_athena_crosswalk Achievements**:
- ✅ Cancer Therapy: 100% (100+ orders, correct dosing)
- ✅ Concomitant Meds: 85-90% (high-priority 95-100%)
- ✅ Encounters: 100% (1,000+ encounters categorized)
- ✅ Conditions: 95% (18 conditions mapped to ICD-10)
- ✅ Clinical Notes: Strategy complete (75 priority docs from 1,000+)

---

## ✅ Validation Checklist

**Before Running CSV Inventory**:
- [x] Reviewed all 33 variables and their sources
- [x] Understood existing extraction scripts (BRIM_Analytics + fhir_athena_crosswalk)
- [x] Identified critical gaps (chemo filter, race/ethnicity, body site)
- [x] Reviewed gold standard CSV structures (sample rows read)
- [x] Understood Athena materialized views (20+ tables documented)
- [x] Validated three-layer architecture (gold standard → Athena → BRIM)
- [x] Confirmed test patient details (C1277724, FHIR ID, clinical events)
- [x] Reviewed BRIM pilot results (87.5% accuracy with STRUCTURED docs)
- [x] Understood specialty/document type routing strategies
- [x] Reviewed comprehensive documentation (40+ files from fhir_athena_crosswalk)

**Ready to Execute**: ✅ YES

---

## 🚀 Execute Now

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run CSV inventory
python3 athena_extraction_validation/scripts/inventory_gold_standard_csvs.py \
  --csv-dir data/20250723_multitab_csvs \
  --output-dir athena_extraction_validation/inventory
```

**Expected Runtime**: ~2-5 minutes (18 CSVs, 23,000+ total rows)

---

*Complete understanding synthesized from 12 documentation files*  
*Ready for systematic CSV-by-CSV validation*  
*Next: Execute inventory → Map variables → Validate scripts → Close gaps*
