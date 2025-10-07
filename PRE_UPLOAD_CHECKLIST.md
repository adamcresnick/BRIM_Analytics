# Pre-Upload Project CSV Checklist

**Use this checklist before EVERY BRIM upload to ensure data quality**

---

## Quick Validation (1 minute)

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run automated validator
python3 scripts/project_csv_validator.py \
  --input pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv \
  --check-only
```

**✅ Expected Output**:
```
✅ PROJECT.CSV IS READY FOR BRIM UPLOAD
   - X rows
   - X unique documents
   - 1 patient: C1277724
```

**❌ If Validation Fails**: Fix automatically
```bash
python3 scripts/project_csv_validator.py \
  --input pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv
```

---

## Manual Spot Checks (30 seconds)

### 1. Check Row Count
```bash
wc -l pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv
```
**Expected**: 1472 (1 header + 1471 data rows)

### 2. Verify Single Patient ID
```bash
tail -n +2 pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv | \
  cut -d',' -f2 | sort -u
```
**Expected**: `C1277724` (only one line of output)

### 3. Check for Duplicates
```bash
tail -n +2 pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv | \
  cut -d',' -f1 | sort | uniq -d
```
**Expected**: (empty - no output)

---

## Upload Verification Checklist

- [ ] Automated validation passed (no errors)
- [ ] Row count matches expectations
- [ ] Single patient ID confirmed
- [ ] No duplicate NOTE_IDs
- [ ] File size reasonable (~8.2 MB for current data)
- [ ] Backup exists (validator creates automatically)

---

## BRIM Upload Steps

1. **Navigate to BRIM interface**
2. **Upload** `project.csv`
3. **Verify confirmation messages**:
   - [ ] "0 lines skipped" ✅
   - [ ] "1 patient in project" ✅
   - [ ] Row count matches file
4. **If issues occur**: Review validator output, fix, re-upload

---

## Files Ready for Upload

| File | Location | Size | Status |
|------|----------|------|--------|
| project.csv | `pilot_output/brim_csvs_iteration_3c_phase3a_v2/` | 8.2 MB | ✅ Validated |
| variables_PRODUCTION.csv | `pilot_output/brim_csvs_iteration_3c_phase3a_v2/` | 33 KB | ✅ Ready |
| decisions_PRODUCTION.csv | `pilot_output/brim_csvs_iteration_3c_phase3a_v2/` | 8 KB | ✅ Ready |

---

## Troubleshooting

### Problem: "2 patients in project"
```bash
# Check patient IDs
tail -n +2 project.csv | cut -d',' -f2 | sort -u

# Fix automatically
python3 scripts/project_csv_validator.py --input project.csv
```

### Problem: "X duplicate rows"
```bash
# Find duplicates
tail -n +2 project.csv | cut -d',' -f1 | sort | uniq -d

# Fix automatically
python3 scripts/project_csv_validator.py --input project.csv
```

### Problem: Upload validation error
```bash
# Full diagnostic
python3 scripts/project_csv_validator.py --input project.csv --check-only

# Review error messages and fix source data
```

---

## Post-Upload Verification

After successful upload to BRIM:

- [ ] Extraction started successfully
- [ ] No errors in BRIM logs
- [ ] Expected patient count (1)
- [ ] Expected document count (1471)
- [ ] Sample extraction results look correct

---

## Documentation References

- **Workflow Guide**: `docs/PROJECT_CSV_WORKFLOW.md`
- **QA Guide**: `docs/PROJECT_CSV_QUALITY_ASSURANCE.md`
- **Implementation Summary**: `docs/PROJECT_CSV_IMPLEMENTATION_SUMMARY.md`
- **Validator Source**: `scripts/project_csv_validator.py`

---

**Last Validated**: [Fill in date/time]
**Validated By**: [Fill in name]
**Upload Date**: [Fill in when uploaded]
**BRIM Session**: [Fill in session ID after upload]

---

## Quick Command Reference

```bash
# Full path aliases for convenience
PROJECT_CSV="pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv"
VALIDATOR="scripts/project_csv_validator.py"

# Check only (no modifications)
python3 $VALIDATOR --input $PROJECT_CSV --check-only

# Validate and fix (creates backup)
python3 $VALIDATOR --input $PROJECT_CSV

# Manual checks
wc -l $PROJECT_CSV
tail -n +2 $PROJECT_CSV | cut -d',' -f2 | sort -u
tail -n +2 $PROJECT_CSV | cut -d',' -f1 | sort | uniq -d
```

---

**Status**: ✅ Ready for validation and upload
**Version**: 1.0 (October 5, 2025)
