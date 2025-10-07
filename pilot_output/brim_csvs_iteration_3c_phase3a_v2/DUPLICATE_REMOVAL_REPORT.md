# Duplicate NOTE_ID Removal Report
**Date:** October 5, 2025  
**Project:** Phase 3a_v2 BRIM Package

## Issue Discovered
During BRIM upload, the platform detected duplicate Document IDs (NOTE_IDs) and stopped the upload:
- Error: "Document ID 'f67tpbiiD.SjSxpi2c8vjZ2dc9B1lPNl81xbr8-kMwa04' for patient MRN 'C1277724' appears multiple times in the file"

## Investigation Results

### Duplicate Detection Script
Created `/scripts/find_duplicate_document_ids.py` to safely identify duplicates without displaying MRN in terminal output.

### Duplicates Found
**Total Duplicate NOTE_IDs:** 2

#### Duplicate 1: f67tpbiiD.SjSxpi2c8vjZ2dc9B1lPNl81xbr8-kMwa04
- **Occurrences:** 2 times (lines 1308 and 1366)
- **NOTE_DATETIME:** 2021-03-10T17:17:00Z
- **NOTE_TITLE:** OP Note - Brief (Needs Dictation)

#### Duplicate 2: fGzsvbcHmFDA7iyi1SZ5K7LPo-8nWTYcz6hi8PUT.psY4
- **Occurrences:** 2 times (lines 1309 and 1367)
- **NOTE_DATETIME:** 2021-03-10T17:17:00Z
- **NOTE_TITLE:** OP Note - Brief (Needs Dictation)

### Root Cause Analysis
Both duplicates are the same type of document from the same date/time, suggesting they were retrieved twice during the Binary document integration process. This likely occurred during the annotation or retrieval scripts when processing the 1,371 S3-available documents.

## Resolution

### Deduplication Process
1. Created `/scripts/remove_duplicate_note_ids.py` to remove duplicates
2. Script keeps first occurrence of each NOTE_ID, removes subsequent duplicates
3. Automatic backup created before modification

### Files Created
- **Backup:** `project_backup_20251005_072419.csv` (8.2 MB, 1,474 rows)
- **Original with duplicates:** `project_with_duplicates.csv` (8.2 MB, 1,474 rows)
- **Cleaned file:** `project.csv` (8.2 MB, 1,472 rows)

### Changes Made
- **Rows removed:** 2 duplicate document entries
- **Original row count:** 1,474 rows (including header)
- **Final row count:** 1,472 rows (including header)
- **Unique documents:** 1,373 (1 FHIR_BUNDLE + 4 STRUCTURED + 1,368 clinical documents)

## Verification

### Final Validation
```bash
python3 scripts/check_csv_duplicates.py project.csv
```

**Result:**
- Total unique NOTE_IDs: 1,373
- Duplicate NOTE_IDs: 0
- ✅ **NO DUPLICATES FOUND**

## Impact Assessment

### Data Integrity
- ✅ No data loss - only duplicate entries removed
- ✅ First occurrence retained for both duplicate documents
- ✅ All other 1,371 documents unchanged

### BRIM Upload Readiness
- ✅ project.csv now has unique NOTE_IDs only (1,472 rows)
- ✅ variables.csv unchanged (35 variables)
- ✅ decisions.csv unchanged (14 decisions)
- ✅ Package ready for upload

### Expected Accuracy
- **Unchanged:** Still expecting 91.4% accuracy (32/35 variables)
- Removal of 2 duplicate documents does not affect variable extraction accuracy

## Prevention Strategy

### For Future Iterations
1. **Annotation Script Enhancement:**
   - Add duplicate detection before writing to CSV
   - Log duplicate Binary IDs encountered
   - Skip re-annotation of already processed documents

2. **Retrieval Script Enhancement:**
   - Check existing project.csv for NOTE_IDs before adding
   - Prevent re-retrieval of already downloaded documents
   - Add deduplication step at end of retrieval process

3. **Integration Script Enhancement:**
   - Run deduplication check before final CSV write
   - Report duplicate count in summary statistics
   - Automatic removal of duplicates during integration

### Recommended Script Updates
```python
# Add to annotation/retrieval/integration scripts:
def check_for_duplicates(note_ids: set) -> int:
    """Check if NOTE_ID already exists in project.csv"""
    existing_ids = set()
    with open('project.csv', 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            existing_ids.add(row[0])
    
    duplicates = note_ids & existing_ids
    if duplicates:
        print(f"⚠️  Found {len(duplicates)} duplicate NOTE_IDs - skipping")
    
    return len(duplicates)
```

## Files for Reference

### Scripts Created
1. `scripts/find_duplicate_document_ids.py` - Safe duplicate detection (no MRN output)
2. `scripts/remove_duplicate_note_ids.py` - Automated deduplication with backup
3. `scripts/check_csv_duplicates.py` - Quick CSV duplicate checker

### Backup Files
1. `project_backup_20251005_072419.csv` - Automatic backup from deduplication script
2. `project_with_duplicates.csv` - Original file with duplicates (renamed for reference)

### Production File
- `project.csv` - Cleaned, deduplicated, ready for BRIM upload ✅

## Next Steps

1. ✅ Upload cleaned package to BRIM (project.csv, variables.csv, decisions.csv)
2. Monitor extraction progress (2-4 hours expected)
3. Download results and compare to gold standard
4. Update annotation/retrieval scripts with duplicate prevention logic
5. Document lessons learned in BRIM_CRITICAL_LESSONS_LEARNED.md

## Summary

**Status:** ✅ **RESOLVED**

Successfully identified and removed 2 duplicate NOTE_IDs from project.csv. The deduplicated file is verified clean and ready for BRIM upload. Future iterations will include duplicate prevention logic in annotation and retrieval scripts to avoid this issue.

**Cleaned Package Ready for Upload:**
- project.csv: 8.2 MB, 1,472 rows, 1,373 unique documents ✅
- variables.csv: 31 KB, 35 variables ✅
- decisions.csv: 5.9 KB, 14 decisions ✅
