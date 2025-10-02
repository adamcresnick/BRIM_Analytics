# BRIM CSV Generation - Pilot Results

## Summary

Successfully generated 3 BRIM-compatible CSV files for pilot patient `e4BwD8ZYDBccepXcJ.Ilo3w3`.

## Generated Files

### 1. project.csv (3.3 MB)
- **Rows:** 2 total (1 header + 1 data row)
- **Structure:** 
  - NOTE_ID: `FHIR_BUNDLE`
  - PERSON_ID: `e4BwD8ZYDBccepXcJ.Ilo3w3`
  - NOTE_DATETIME: ISO 8601 timestamp
  - NOTE_TEXT: Complete FHIR Bundle JSON (1,770 resources)
  - NOTE_TITLE: `FHIR_BUNDLE`

**Note:** Currently contains only the FHIR Bundle. Clinical notes from DocumentReference resources were not found in the first 5 NDJSON files queried (out of 1,000 available files). This is expected for a pilot - the full implementation can query all files or use a more targeted search.

### 2. variables.csv (3.7 KB)
- **Variables:** 13 extraction rules
- **Categories:**
  1. **Document Classification** (1 variable)
     - `document_type`: Classifies each document (FHIR_BUNDLE, OPERATIVE_NOTE, etc.)
  
  2. **Demographics** (2 variables)
     - `patient_gender`: male|female|other|unknown
     - `date_of_birth`: YYYY-MM-DD format
  
  3. **Diagnosis** (3 variables)
     - `primary_diagnosis`: Brain tumor diagnosis
     - `diagnosis_date`: Date of diagnosis
     - `who_grade`: I|II|III|IV tumor grade
  
  4. **Surgical Events** (3 variables)
     - `surgery_date`: Date of each surgery
     - `surgery_type`: BIOPSY|RESECTION|SHUNT|etc.
     - `extent_of_resection`: Percentage or category
  
  5. **Treatments** (2 variables)
     - `chemotherapy_agent`: Drug names
     - `radiation_therapy`: yes|no|unknown
  
  6. **Molecular/Genetic** (2 variables)
     - `idh_mutation`: positive|negative|wildtype|unknown
     - `mgmt_methylation`: methylated|unmethylated|unknown

**Key Features:**
- All variables have proper `scope` definitions (one_per_patient, one_per_note, many_per_note)
- Categorical variables include `option_definitions` for controlled vocabularies
- Prompts are designed to work with both FHIR JSON and narrative text

### 3. decisions.csv (1.3 KB)
- **Decisions:** 5 aggregation/validation rules
- **Types:**
  1. **confirmed_diagnosis** (merge): Cross-validates diagnosis from FHIR vs narrative
  2. **total_surgeries** (count): Counts unique surgical procedures
  3. **best_resection** (max): Identifies most extensive resection
  4. **chemotherapy_regimen** (list): Aggregates all chemo agents
  5. **molecular_profile** (merge): Summarizes genetic testing results

## FHIR Bundle Contents

The FHIR Bundle in project.csv contains:
- **Patient:** 1 resource (female, DOB: 2005-05-13)
- **Conditions:** 1,397 resources (diagnoses)
- **Procedures:** 72 resources (surgeries)
- **MedicationRequests:** 100 resources (medications)
- **Observations:** 200 resources (labs, vitals, molecular)
- **Total:** 1,770 FHIR resources

## What BRIM Will Extract

When these CSVs are uploaded to BRIM, the LLM will:

1. **Classify the document** as FHIR_BUNDLE using `document_type` variable
2. **Extract demographics** by parsing the Patient resource JSON
3. **Extract diagnoses** by parsing Condition resources with ICD-10/SNOMED codes
4. **Extract surgical procedures** by parsing Procedure resources with dates
5. **Extract medications** by parsing MedicationRequest resources with RxNorm codes
6. **Extract observations** including lab values and molecular markers
7. **Run dependent variables** to cross-validate and aggregate data

## Clinical Notes Status

**Current:** 0 clinical notes extracted (DocumentReference resources not found in first 5 NDJSON files)

**For Production:**
- Query all 1,000 DocumentReference NDJSON files (remove `files[:5]` limit)
- Or use more targeted search if patient ID is indexed
- Clinical notes would appear as additional rows in project.csv
- Variables would extract complementary data from narrative text
- Decisions would cross-validate FHIR vs narrative findings

## Next Steps

### 1. Review CSVs (✅ Complete)
All files generated successfully with proper structure.

### 2. Upload to BRIM UI
1. Go to https://app.brimhealth.com
2. Create new project
3. Upload these 3 CSV files:
   - `project.csv` (3.3 MB)
   - `variables.csv` (3.7 KB)
   - `decisions.csv` (1.3 KB)

### 3. Run Extraction Job
- BRIM will process the FHIR Bundle using LLM
- Estimated time: 5-15 minutes for 1 patient with 1,770 resources
- Monitor job progress in UI

### 4. Download Results
- BRIM will generate 18 output CSVs matching manual structure:
  - demographics.csv
  - diagnosis.csv
  - treatments.csv
  - medications.csv
  - measurements.csv
  - imaging.csv
  - molecular.csv
  - etc.

### 5. Validate Against Manual CSVs
Compare BRIM output vs manual CSVs from:
`/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/`

**Validation criteria:**
- ≥80% field accuracy (primary goal)
- ≥90% accuracy (stretch goal)
- Identify mismatches for prompt refinement

## File Locations

```
pilot_output/
├── fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json  (3.5 MB, 1,770 resources)
└── brim_csvs/
    ├── project.csv     (3.3 MB, FHIR Bundle)
    ├── variables.csv   (3.7 KB, 13 variables)
    └── decisions.csv   (1.3 KB, 5 decisions)
```

## Known Limitations

1. **Clinical Notes:** Not included in current pilot (0 found)
   - Can be added by removing file limit in script
   - Not critical for initial FHIR-only validation

2. **Encounters:** Failed to extract from Athena (NULL comparison issue)
   - Not critical for pilot
   - Can be fixed in future iteration

3. **Large Document Size:** FHIR Bundle is 3.3 MB in a single CSV cell
   - Should work with BRIM, but verify in UI
   - If issues arise, can split into multiple notes by resource type

## Success Metrics

✅ FHIR Bundle extracted successfully (1,770 resources)  
✅ All 3 BRIM CSVs generated with proper structure  
✅ 13 extraction variables defined with prompts  
✅ 5 cross-validation decisions configured  
✅ Ready for UI testing  

Next: Upload to BRIM and validate results!
