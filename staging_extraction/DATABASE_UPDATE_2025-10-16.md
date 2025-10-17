# Database Update: fhir_v2_prd_db → fhir_prd_db

**Date**: 2025-10-16
**Change**: All staging extraction scripts updated to use `fhir_prd_db` (latest database)

---

## Changes Made

### Python Scripts Updated (7 references):

1. **extract_all_binary_files_metadata.py**
   - Line 5: Comment updated from `fhir_v2_prd_db` → `fhir_prd_db`
   - Line 14: Comment updated from `fhir_v1_prd_db` → `fhir_prd_db`

2. **extract_all_molecular_tests_metadata.py**
   - Line 305: Default database parameter changed
   ```python
   # OLD: database = config.get('database', 'fhir_v2_prd_db')
   # NEW: database = config.get('database', 'fhir_prd_db')
   ```

3. **extract_patient_demographics.py**
   - Line 17: Comment updated in TABLES USED section
   - Line 203: Hardcoded database variable changed
   ```python
   # OLD: database = 'fhir_v2_prd_db'
   # NEW: database = 'fhir_prd_db'
   ```

4. **extract_problem_list_diagnoses.py**
   - Line 17: Comment updated in TABLES USED section
   - Line 222: Hardcoded database variable changed
   ```python
   # OLD: database = 'fhir_v2_prd_db'
   # NEW: database = 'fhir_prd_db'
   ```

### Configuration Files Updated (2 references):

5. **config_driven/README.md**
   - Line 27: Example `patient_config.json` updated

6. **README.md** (parent directory)
   - Line 72: Example `patient_config.json` updated

---

## Verification

All 12 extraction scripts verified clean:
```bash
$ grep -c "fhir_v2_prd_db\|fhir_v1_prd_db" config_driven/*.py
# All return: 0
```

✅ No old database references remaining in Python code
✅ Configuration examples updated
✅ Comments and documentation strings updated

---

## Documentation Files (Informational - Left As-Is)

The following documentation files still reference `fhir_v2_prd_db` for historical context. These are **not used by code execution** and preserve the history of database evolution:

- `docs/README_ATHENA_VALIDATION_STRATEGY.md` - Historical validation strategy
- `docs/SYNTHESIS_COMPLETE_UNDERSTANDING.md` - Historical architecture notes
- `docs/IMAGING_STAGING_FILE_ANALYSIS.md` - Historical analysis
- `docs/MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md` - Historical SQL examples
- `README_ATHENA_EXTRACTION.md` - Historical lessons learned section

These documents serve as reference for understanding:
1. **Database Evolution**: `fhir_v1_prd_db` → `fhir_v2_prd_db` → `fhir_prd_db`
2. **Lessons Learned**: Why certain database choices were made
3. **Historical Context**: What worked and what didn't during development

---

## Impact

### Scripts Now Use Latest Database:
- ✅ `fhir_prd_db` contains the complete, up-to-date FHIR dataset
- ✅ All extractions will pull from the most current data
- ✅ No more references to deprecated `fhir_v2_prd_db` or `fhir_v1_prd_db`

### User Configuration:
When users run `initialize_patient_config.py` or manually create `patient_config.json`, they should use:
```json
{
  "database": "fhir_prd_db"
}
```

### Backward Compatibility:
If a user has an old `patient_config.json` with `"database": "fhir_v2_prd_db"`, the scripts will respect that setting. However, we recommend updating to `fhir_prd_db` for complete data access.

---

## Testing Recommendations

Before running extractions in production:

1. **Verify Database Access**:
   ```bash
   aws athena start-query-execution \
     --profile 343218191717_AWSAdministratorAccess \
     --query-string "SELECT COUNT(*) FROM fhir_prd_db.patient LIMIT 1" \
     --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/
   ```

2. **Test Single Extraction**:
   ```bash
   cd staging_extraction
   python3 initialize_patient_config.py <TEST_PATIENT_ID>
   cd config_driven
   python3 extract_patient_demographics.py
   ```

3. **Verify Output**:
   ```bash
   head staging_files/patient_*/demographics.csv
   ```

---

## Status

✅ **All code updated to fhir_prd_db**
✅ **Configuration templates updated**
✅ **Ready for production use**

Multi-agent branch now uses the latest FHIR database for all staging file extractions.
