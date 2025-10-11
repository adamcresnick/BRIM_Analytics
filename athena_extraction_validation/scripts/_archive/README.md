# Archive: Exploratory & Test Scripts

**Date Archived:** October 11, 2025  
**Reason:** Superseded by enhanced extraction scripts with comprehensive medication_request table joins

## Archived Files

### Test Scripts (Exploratory Phase)
These scripts were created during the exploration phase to understand table schemas and JOIN patterns. Their findings have been incorporated into the main extraction scripts.

**Status:** ✅ Completed their purpose, findings documented, superseded by production scripts

#### Files:
1. **test_medication_table.py** (empty file)
   - Purpose: Initial test of medication_request table structure
   - Status: Empty, never completed
   - Superseded by: Direct queries in extract_all_medications_metadata.py

2. **test_medication_joins.py** (117 lines)
   - Purpose: Test JOIN patterns between patient_medications and medication_form_coding/medication_ingredient
   - Key Finding: medication_reference = medication_id for joins
   - Status: Findings incorporated into extract_all_medications_metadata.py
   - Superseded by: Lines 177-180 and 273-278 in extract_all_medications_metadata.py

3. **test_additional_medication_tables.py** (257 lines)
   - Purpose: Test 5 additional medication tables for data availability
   - Key Finding: medication_request_* child tables have low linkage to patient medications
   - Status: Findings documented, approach refined
   - Superseded by: CTEs in extract_all_medications_metadata.py

4. **test_patient_medications.py**
   - Purpose: Initial exploration of patient_medications view
   - Status: Completed exploration
   - Superseded by: Full schema documented in MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md

### Preliminary Analysis Scripts
These scripts were used for one-time analyses during the schema discovery phase.

5. **count_meds.py**
   - Purpose: Quick count of medications for patient C1277724
   - Result: 1,121 medications
   - Status: Finding confirmed in production script
   - Superseded by: Full extraction in extract_all_medications_metadata.py

6. **discover_medication_schema.py**
   - Purpose: Explore medication table structure
   - Status: Schema documented
   - Superseded by: Documentation in MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md

7. **list_all_medication_tables.py**
   - Purpose: List available medication-related tables in Athena
   - Status: Complete inventory created
   - Superseded by: Table list documented in COMPLETE_LANDSCAPE_ANALYSIS.md

### Investigation Scripts
These were used for specific investigation tasks and their findings are documented.

8. **investigate_care_plan_table.py**
   - Purpose: Analyze care_plan table structure and linkages
   - Key Finding: Only ~10% of medications link to care plans
   - Status: Findings incorporated into medication extraction strategy
   - Superseded by: Care plan JOINs in extract_all_medications_metadata.py

9. **analyze_based_on_references.py**
   - Purpose: Analyze medication_request_based_on linkage patterns
   - Key Finding: 276 medications (24.6%) link to care plans
   - Status: Pattern documented and implemented
   - Superseded by: medication_request_based_on CTE in extract_all_medications_metadata.py

## Why These Files Are Archived

### Rationale
- **Exploratory phase complete**: Table schemas and JOIN patterns now documented
- **Findings incorporated**: All useful patterns integrated into production scripts
- **Superseded by enhanced scripts**: extract_all_medications_metadata.py now includes:
  - Direct JOIN to medication_request table for temporal fields
  - All patient_medications view fields
  - Comprehensive CTEs for child tables
  - 44 columns of metadata (vs preliminary 10-20 columns)

### What Was Learned

From these test scripts, we discovered:
1. **patient_medications is a materialized view** with 10 fields (not a full table)
2. **medication_request table has 68 fields** including validity_period_end for stop dates
3. **JOIN pattern**: pm.medication_request_id = mr.id (not pm.id = mr.medication_request_id)
4. **medication_id join**: Used for medication_form_coding and medication_ingredient tables
5. **Care plan linkage**: Only 24.6% of medications linked via medication_request_based_on
6. **Date fields**: validity_period_end (21.5% coverage) > care_plan_period_end (0% coverage)

### Production Scripts (Not Archived)

These scripts remain active and are the current source of truth:

- ✅ **extract_all_medications_metadata.py** - Enhanced with medication_request JOIN, 44 fields
- ✅ **filter_chemotherapy_from_medications.py** - 5-strategy chemotherapy identification
- ✅ **extract_all_encounters_metadata.py** - 999 encounters extracted
- ✅ **extract_all_procedures_metadata.py** - Procedure extraction with CPT codes
- ✅ **extract_all_imaging_metadata.py** - Imaging studies with corticosteroid context
- ✅ **extract_all_measurements_metadata.py** - Vital signs and observations
- ✅ **extract_all_diagnoses_metadata.py** - ICD-9/10 diagnosis codes
- ✅ **extract_all_binary_files_metadata.py** - Document references with S3 availability

## How to Use Archived Files

### If You Need to Reference Them
```bash
# View archived test script
cat _archive/test_medication_joins.py

# Search for specific pattern
grep -n "medication_reference" _archive/test_medication_joins.py
```

### If You Need to Restore Them
```bash
# Copy back to scripts directory (not recommended)
cp _archive/test_medication_joins.py ../

# Better: Reference findings in documentation
# See: docs/MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md
```

## Documentation References

All findings from these archived scripts are documented in:

1. **MEDICATION_EXTRACTION_ENHANCEMENT_TEMPORAL_FIELDS.md**
   - Complete schema analysis
   - Field coverage statistics
   - JOIN patterns and strategies

2. **COMPLETE_LANDSCAPE_ANALYSIS.md**
   - Table inventory
   - Coverage analysis
   - Data source recommendations

3. **MATERIALIZED_VIEW_STRATEGY_VALIDATION.md**
   - patient_medications view structure
   - Comparison with underlying tables

---

**Restoration Policy**: These files are archived for reference only. Do not restore to active scripts directory unless investigating a regression or schema change.

**Deletion Policy**: Keep archived indefinitely (small file size, valuable historical context).
