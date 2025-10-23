# Radiation & Chemotherapy Integration Plan

## Current Status Summary

### ✅ COMPLETED:

**Chemotherapy (Today's Work):**
- Deployed v_chemo_medications (116,903+ medication orders)
- Deployed v_concomitant_medications (192M+ temporal overlap records)
- Deployed v_chemotherapy_drugs (3,064 comprehensive drug reference)
- Deployed v_chemotherapy_rxnorm_codes (2,804 product→ingredient mappings)
- Created comprehensive design document: [CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md](CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md)
- Fixed RxNorm code matching issues
- All views using `patient_fhir_id` column consistently

**Radiation (Earlier This Evening):**
- Deployed radiation views in Athena:
  - v_radiation_summary
  - v_radiation_treatments
  - v_radiation_care_plan_hierarchy
  - v_radiation_treatment_appointments
  - v_radiation_documents
- Created radiation therapy analyzer: [multi_source_extraction_framework/radiation_therapy_analyzer.py](../multi_source_extraction_framework/radiation_therapy_analyzer.py)
- All views using `patient_fhir_id` column consistently

### ⏸️ NOT YET DONE:

**For Both Radiation & Chemotherapy:**
1. Create JSON builder scripts that query Athena views (not CSVs)
2. Integrate into run_full_multi_source_abstraction.py
3. Rebuild DuckDB timeline database with new views
4. Test end-to-end extraction on pilot patients

## File Locations

### Radiation Files:
- **Analyzer script**: `multi_source_extraction_framework/radiation_therapy_analyzer.py`
  - Currently reads from CSV staging files
  - **NEEDS UPDATE**: Should query Athena views instead

- **Athena Views**:
  - `v_radiation_summary` - High-level radiation summary
  - `v_radiation_treatments` - Individual treatment records
  - `v_radiation_care_plan_hierarchy` - Care plan linkages
  - `v_radiation_treatment_appointments` - Treatment appointments
  - `v_radiation_documents` - Related documents

- **Test Data**: CSVs in `athena_extraction_validation/staging_files/patient_e4BwD8ZYDBccepXcJ.Ilo3w3/`

### Chemotherapy Files:
- **Design Document**: `mvp/CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md`
  - Complete specification
  - JSON structure defined
  - Binary file selection logic
  - CBTN field mapping (51 fields identified)

- **Athena Views**:
  - `v_chemo_medications` - All chemotherapy medications
  - `v_concomitant_medications` - Temporal overlap analysis
  - `v_chemotherapy_drugs` - Comprehensive drug reference (3,064 drugs)
  - `v_chemotherapy_rxnorm_codes` - RxNorm mappings (2,804)
  - `v_chemotherapy_regimens` - Standard regimen definitions
  - `v_chemotherapy_regimen_components` - Regimen drug components

- **Test Patient**: `Patient/eLiG6.0hbwU-5ljD0B4hUh5heq3ipPk3TILjYLt4l6P43`
  - 1,827 chemotherapy orders
  - 14 unique drugs

## Integration Tasks

### Task 1: Create Radiation JSON Builder
**File to create**: `mvp/scripts/build_radiation_json.py`

**What it should do**:
1. Query `v_radiation_summary` for patient
2. Query `v_radiation_treatments` for treatment details
3. Query `v_radiation_care_plan_hierarchy` for care plan linkages
4. Query `v_radiation_treatment_appointments` for appointment details
5. Assemble comprehensive JSON with:
   - Treatment courses (site, dose, fractions, dates)
   - Treatment intent (curative/palliative)
   - Technique (IMRT, SRS, conventional, etc.)
   - Appointment history
   - Related documents for validation

**Pattern**: Similar to existing extraction modules in `run_full_multi_source_abstraction.py`

### Task 2: Create Chemotherapy JSON Builder
**File to create**: `mvp/scripts/build_chemotherapy_json.py`

**What it should do**:
1. Query `v_chemo_medications` for patient
2. Query `v_concomitant_medications` for supportive care validation
3. Query `v_chemotherapy_regimens` for regimen matching
4. Group medications into courses (±90 day rule)
5. Match to defined regimens
6. Select relevant binary files using timing windows
7. Assemble comprehensive JSON per design document

**Pattern**: Follow [CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md](CHEMOTHERAPY_EXTRACTION_WORKFLOW_DESIGN.md)

### Task 3: Update radiation_therapy_analyzer.py
**File to update**: `multi_source_extraction_framework/radiation_therapy_analyzer.py`

**Changes needed**:
- Replace CSV file reading with Athena queries
- Use boto3 to query views instead of pd.read_csv()
- Update to use `patient_fhir_id` column name
- Maintain same output JSON structure

### Task 4: Integrate into Main Workflow
**File to update**: `mvp/scripts/run_full_multi_source_abstraction.py`

**Integration points**:
1. Import radiation and chemotherapy JSON builders
2. Add radiation extraction phase (PHASE 1C or separate)
3. Add chemotherapy extraction phase (PHASE 1D or separate)
4. Pass JSONs to Agent 2 alongside existing data
5. Update Agent 2 prompts to handle radiation/chemotherapy data

**Suggested workflow order**:
```
PHASE 1A: Timeline Database Query
PHASE 1B: Imaging & Surgery Extraction (existing)
PHASE 1C: Radiation Therapy Extraction (NEW)
PHASE 1D: Chemotherapy Extraction (NEW)
PHASE 2:  Agent 2 Multi-Source Abstraction
PHASE 3:  Agent 1 Review & Adjudication
```

### Task 5: Rebuild DuckDB Timeline Database
**File to update**: `mvp/scripts/build_timeline_database.py`

**Changes needed**:
1. Add v_chemo_medications to timeline events
2. Add v_radiation_summary to timeline events
3. Add v_concomitant_medications (optional - may be too large)
4. Update schema to include medication and radiation columns
5. Re-run database build with new Athena views

### Task 6: Update Agent 2 Prompts
**File to update**: `mvp/agents/extraction_prompts.py`

**New prompts needed**:
1. `build_radiation_therapy_extraction_prompt(radiation_json, binary_files)`
   - Extract dose, fractions, treatment site
   - Identify treatment intent
   - Map to CBTN fields

2. `build_chemotherapy_extraction_prompt(chemotherapy_json, binary_files)`
   - Extract drug names, doses, routes
   - Identify protocol enrollment
   - Validate against infusion records
   - Map to CBTN fields (51 identified fields)

## Testing Plan

### Test Patient Requirements:
- **Radiation**: `Patient/e4BwD8ZYDBccepXcJ.Ilo3w3` (confirmed has radiation data)
- **Chemotherapy**: `Patient/eLiG6.0hbwU-5ljD0B4hUh5heq3ipPk3TILjYLt4l6P43` (1,827 orders)

### Testing Sequence:
1. Test radiation JSON builder standalone
2. Test chemotherapy JSON builder standalone
3. Test integrated workflow with both modules
4. Verify Agent 2 handles both data types
5. Validate CBTN field population

## CBTN Data Dictionary Fields

### Radiation Fields (from CBTN dictionary):
- Radiation Therapy? (Yes/No)
- Start date of radiation therapy
- Stop date of radiation therapy
- Radiation treatment site
- Radiation dose (Gy)
- Number of fractions
- Radiation technique (IMRT, SRS, conventional, etc.)

### Chemotherapy Fields (51 total):
**Clinical Trial**:
- Protocol Number and Treatment Arm
- Description of Chemotherapy Treatment
- Non-intervention trial enrollment
- Trial/registry name

**Chemotherapy Details**:
- Chemotherapy? (Yes/No)
- Chemotherapy Type (protocol vs SOC)
- Start date of chemotherapy
- Stop date of chemotherapy
- Chemotherapy Agent 1-5
- Drug 1-5 name + dose/route/frequency
- Medication 1-10 (reconciliation)

## Implementation Priority

**Recommended order**:
1. ✅ Update todos to track integration tasks
2. Create radiation JSON builder (simpler - views already working)
3. Create chemotherapy JSON builder (following design doc)
4. Test both standalone
5. Integrate into main workflow
6. Rebuild DuckDB timeline database
7. End-to-end testing

## Next Session Plan

Given the late hour and amount of work accomplished today:

**Option A (Recommended)**: Document completion and resume in next session
- Create summary of today's accomplishments
- Update project documentation
- Start fresh next session with integration

**Option B**: Begin implementation now
- Start with radiation JSON builder (simpler)
- Continue with chemotherapy JSON builder
- May take 2-3 hours total

## Success Criteria

Integration is complete when:
- ✅ Both radiation and chemotherapy JSON builders query Athena (not CSVs)
- ✅ Both modules integrated into run_full_multi_source_abstraction.py
- ✅ DuckDB timeline database includes medication and radiation events
- ✅ Agent 2 successfully extracts from both data types
- ✅ CBTN fields populated from multi-source abstraction
- ✅ End-to-end test passes on pilot patients
