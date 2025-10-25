# Agent Onboarding Guide - Update Assessment
**Date:** 2025-10-25
**Assessment Period:** October 20-25, 2025
**Current Guide Version:** v1.2.0 (Last Updated: 2025-10-20)

---

## Executive Summary

The Agent Onboarding Guide requires **SIGNIFICANT UPDATES** to reflect critical improvements made over the past 5 days:

### Critical Missing Content:
1. **Enhanced Operative Note Extraction** - Complete deduplication and datetime fixes (Oct 23-24)
2. **Automatic AWS SSO Refresh** - Auto-retry mechanism for expired tokens (Oct 24)
3. **Extraction Failure Tracking** - Failed extraction logging for quality monitoring (Oct 24)
4. **Athena View Deployment** - Timeline view rebuild procedures and prerequisites (Oct 25)
5. **ChemotherapyFilter Integration** - Automated medication categorization in timeline (Oct 25)
6. **Version Update** - Current version is now v1.3.0+ (was v1.2.0)

### Impact Level: **HIGH**
Without these updates, new Claude sessions will:
- Miss critical bug fixes implemented in the past week
- Lack guidance on timeline view deployment procedures
- Not understand automatic SSO refresh capabilities
- Miss extraction failure tracking for QA purposes

---

## Detailed Gap Analysis

### 1. Enhanced Operative Note Extraction (HIGH PRIORITY)

**What Changed (Oct 23-24):**
- Fixed datetime column handling: All `obs_*_datetime` columns now properly wrapped in `TRY_CAST(... AS TIMESTAMP(3))`
- Implemented operative note deduplication: Prevents duplicate extractions when notes appear multiple times
- Added extraction failure tracking: Logs failed operative note extractions for investigation

**Current Guide Coverage:** ❌ NOT MENTIONED

**Impact:** New sessions won't know about:
- The datetime bug fix that prevented extraction crashes
- Deduplication logic preventing redundant extractions
- Failure tracking capabilities for QA

**Recommended Addition:**

```markdown
### Enhanced Operative Note Extraction (v1.3.0)

**Bug Fixes (Oct 23-24):**

1. **Datetime Column Handling:**
   - All observation datetime columns wrapped in `TRY_CAST(... AS TIMESTAMP(3))`
   - Prevents extraction crashes from malformed datetime strings
   - Affects: operative notes, pathology reports, radiology reports

2. **Operative Note Deduplication:**
   - Prevents duplicate extractions when same note linked to multiple procedures
   - Uses `document_reference_id` for deduplication instead of `procedure_fhir_id`
   - Reduces extraction costs and improves data quality

3. **Extraction Failure Tracking:**
   - Failed operative note extractions logged to `failed_operative_extractions` list
   - Enables post-workflow QA review
   - Format: `{'document_reference_id': '...', 'error': '...', 'procedure_id': '...'}`

**Code Location:** `scripts/run_enhanced_extraction.py` lines 450-550

**Testing:** Validated on Patient/eVvGlY04JfHlbdS3NYINlRTuDlO6.uTRfPMfPRCKnEYU3
```

---

### 2. Automatic AWS SSO Token Refresh (MEDIUM-HIGH PRIORITY)

**What Changed (Oct 24):**
- Implemented automatic SSO login retry mechanism
- Detects expired token errors and triggers `aws sso login` automatically
- Continues extraction after successful re-authentication
- Eliminates manual intervention for long-running workflows

**Current Guide Coverage:** ⚠️ PARTIAL (Troubleshooting section only)

**Current Guidance (Lines 418-425):**
```markdown
### Issue: AWS SSO Token Expired
**Symptoms:** Error when retrieving token from sso: Token has expired and refresh failed
**Solution:**
```bash
aws sso login --profile radiant-prod
```
```

**Gap:** Guide shows manual fix but doesn't mention automatic retry capability

**Recommended Update:**

```markdown
### 2.5. Automatic AWS SSO Token Refresh (v1.3.0)

**Purpose:** Automatically handle expired SSO tokens during long-running extractions

**How It Works:**
1. BinaryFileAgent detects SSO token expiration errors
2. Triggers `aws sso login --profile radiant-prod` subprocess
3. Waits for user to complete browser authentication
4. Retries failed operation automatically
5. Continues extraction workflow without manual intervention

**Impact:**
- Eliminates workflow interruptions from token expiration
- Enables multi-hour extraction workflows
- Reduces manual monitoring requirements

**Code Location:** `agents/binary_file_agent.py` lines 180-220

**User Experience:**
```
⚠️  AWS SSO token expired. Initiating automatic login...
🔐 Please complete SSO login in your browser...
✓ SSO login successful! Resuming extraction...
```

**Note:** User must still complete browser authentication, but workflow resumes automatically afterward.
```

---

### 3. Extraction Failure Tracking (MEDIUM PRIORITY)

**What Changed (Oct 24):**
- Added `failed_operative_extractions` tracking list
- Logs document_reference_id, error message, and procedure_id for failed extractions
- Enables post-workflow QA and debugging
- Saved in comprehensive abstraction JSON

**Current Guide Coverage:** ❌ NOT MENTIONED

**Impact:** New sessions won't know to:
- Check `failed_operative_extractions` for QA purposes
- Investigate why certain operative notes failed to extract
- Report extraction quality metrics

**Recommended Addition:**

```markdown
### Quality Assurance: Extraction Failure Tracking

**Location in Output JSON:**
```json
{
  "comprehensive_summary": {
    "failed_operative_extractions": [
      {
        "document_reference_id": "DocumentReference/xyz",
        "error": "Text extraction failed: PDF corrupted",
        "procedure_id": "Procedure/abc"
      }
    ]
  }
}
```

**Post-Workflow QA Checklist:**
1. Check `failed_operative_extractions` list
2. Investigate errors (missing PDFs, corrupted files, extraction timeouts)
3. Manually review failed documents if critical
4. Track failure patterns for system improvements

**Common Failure Reasons:**
- Binary file not found in S3 (404 errors)
- PDF corruption or unsupported format
- Text extraction timeout (large PDFs)
- SSO token expiration (now auto-retried)
```

---

### 4. Athena View Deployment Procedures (HIGH PRIORITY)

**What Changed (Oct 25):**
- Deployed updated `v_unified_patient_timeline` with prerequisite views
- Created deployment automation scripts (`deploy_unified_timeline.sh`)
- Documented prerequisite views: `v_diagnoses`, `v_radiation_summary`
- Rebuilt DuckDB timeline database with updated views
- Fixed column name standardization (patient_id → patient_fhir_id)

**Current Guide Coverage:** ❌ NOT MENTIONED AT ALL

**Impact:** New sessions won't know:
- How to deploy updated Athena timeline views
- That prerequisite views must be deployed first
- Timeline rebuild procedures after view updates
- Recent timeline view changes (v_visits_unified v2.2, datetime fixes)

**Recommended Addition (New Section):**

```markdown
## Athena View Deployment and Timeline Rebuild

### When to Rebuild Timeline Views

Rebuild Athena timeline views when:
1. Source FHIR views change (v_medications, v_imaging, v_procedures_tumor, etc.)
2. Timeline view logic updated (new event types, column changes)
3. Temporal context calculations modified
4. Column name standardization applied

**Recent Updates (Oct 25):**
- Column standardization: `patient_id` → `patient_fhir_id` across all views
- Datetime standardization: `VARCHAR` → `TIMESTAMP(3)` for all datetime columns
- New data source: `v_visits_unified` v2.2 (unified encounters + appointments)

### Prerequisite Views (MUST DEPLOY FIRST)

The unified timeline depends on two prerequisite views:

1. **v_diagnoses** - Normalizes `v_problem_list_diagnoses`
   - Removes `pld_` column prefixes
   - Standardizes diagnosis data structure
   - File: `athena_views/views/V_DIAGNOSES.sql`

2. **v_radiation_summary** - Aggregates `v_radiation_treatments`
   - Course-level radiation summaries
   - Uses `patient_fhir_id` (not `patient_id`)
   - File: `athena_views/views/V_RADIATION_SUMMARY.sql`

### Deployment Procedure

```bash
# Navigate to athena_views directory
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views

# Deploy all timeline views (prerequisites + main view)
./deploy_unified_timeline.sh

# Output:
# ✅ v_diagnoses deployed successfully!
# ✅ v_radiation_summary deployed successfully!
# ✅ v_unified_patient_timeline deployed successfully!
```

**Deployment Script:** `athena_views/deploy_unified_timeline.sh`
- Deploys views in correct order (prerequisites first)
- Handles Athena's single-statement limitation
- Polls for query completion
- Reports deployment status

### Rebuild DuckDB Timeline After Athena Updates

**CRITICAL:** After deploying updated Athena views, rebuild local DuckDB timeline:

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp
python3 scripts/build_timeline_database.py
```

**What This Does:**
1. Queries updated `v_unified_patient_timeline` from Athena
2. Applies ChemotherapyFilter to medication categorization
3. Computes temporal context (disease phases, milestones)
4. Loads data into `data/timeline.duckdb`
5. Creates indexes for fast queries

**Output:**
```
✅ TIMELINE DATABASE CREATED SUCCESSFULLY
Database location: /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb

Event counts by type:
  Visit                1007
  Measurement           438
  Medication            281
  Imaging                82
  Procedure               9
  Molecular Test          3
```

**Validation:**
```python
import duckdb
conn = duckdb.connect('data/timeline.duckdb')
conn.execute('SELECT event_type, COUNT(*) FROM events GROUP BY event_type').fetchdf()
```

### Timeline View Files

- `athena_views/views/V_DIAGNOSES.sql` - Diagnosis normalization view
- `athena_views/views/V_RADIATION_SUMMARY.sql` - Radiation course summaries
- `athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql` - Main timeline view (with comments)
- `athena_views/views/V_UNIFIED_PATIENT_TIMELINE_DEPLOY.sql` - Clean deployment version (no comments)
- `athena_views/deploy_unified_timeline.sh` - Automated deployment script

### Troubleshooting Timeline Deployment

**Error: "Only one sql statement is allowed"**
- Cause: SQL file contains comments or multiple statements
- Solution: Use `V_UNIFIED_PATIENT_TIMELINE_DEPLOY.sql` (clean version)

**Error: "Column 'patient_id' cannot be resolved"**
- Cause: View uses old column name
- Solution: Update to `patient_fhir_id` everywhere

**Timeline has no events after rebuild:**
- Check SSO token: `aws sso login --profile radiant-prod`
- Verify Athena views deployed successfully
- Check test patient ID matches: `e4BwD8ZYDBccepXcJ.Ilo3w3`
```

---

### 5. ChemotherapyFilter Integration in Timeline (MEDIUM PRIORITY)

**What Changed (Oct 25):**
- Timeline build process now applies ChemotherapyFilter automatically
- Medications correctly categorized as Chemotherapy vs Targeted Therapy
- Drug aliases and RxNorm codes used for classification
- Timeline database includes corrected medication categories

**Current Guide Coverage:** ❌ NOT MENTIONED (ChemotherapyFilter exists but timeline integration not documented)

**Impact:** New sessions won't know:
- Timeline build includes automatic medication categorization
- How ChemotherapyFilter improves medication event categorization
- Where to find chemotherapy reference files

**Recommended Addition:**

```markdown
### ChemotherapyFilter Integration in Timeline Build

**Automatic Medication Categorization:**

When building the timeline database (`build_timeline_database.py`), medications are automatically categorized using ChemotherapyFilter:

**Process:**
1. Query medications from `v_medications` (includes RxNorm codes)
2. Apply ChemotherapyFilter to each medication
3. Classify as: Chemotherapy, Targeted Therapy, or Other Medication
4. Update `event_category` in timeline database

**Example Output:**
```
Applying ChemotherapyFilter to medications
ChemotherapyFilter loaded:
  total_drugs: 3067
  chemotherapy_drugs: 3064
  rxnorm_ingredient_codes: 803

  ✓ vinBLAStine inj 10 mg → Chemotherapy (rxnorm_ingredient, high confidence)
  ✓ selumetinib capsule → Targeted Therapy (drug_name_alias, medium confidence)
  ✓ bevacizumab 575 mg → Chemotherapy (rxnorm_ingredient, high confidence)

✓ Updated 110 medication categories using ChemotherapyFilter

Event type distribution (AFTER ChemotherapyFilter):
  Other Medication    749
  Chemotherapy        110
  Targeted Therapy     12
```

**Reference Files Location:**
`athena_views/data_dictionary/chemo_reference/`
- `chemotherapy_drugs.csv` - Drug names and classifications
- `chemotherapy_drug_aliases.csv` - Name variations
- `chemotherapy_rxnorm_mappings.csv` - RxNorm code mappings

**Code Location:** `scripts/build_timeline_database.py` lines 120-180
```

---

### 6. Version Update Required (HIGH PRIORITY)

**Current Guide Version:** v1.2.0 (2025-10-20)
**Actual System Version:** v1.3.0+ (2025-10-25)

**Recommended Version Update:**

```markdown
### v1.3.0 (2025-10-25) - Current Version
- ✅ Enhanced operative note extraction with deduplication
- ✅ Automatic AWS SSO token refresh for long-running workflows
- ✅ Extraction failure tracking for QA
- ✅ Athena timeline view deployment automation
- ✅ DuckDB timeline rebuild procedures documented
- ✅ ChemotherapyFilter integration in timeline build
- ✅ Column name standardization: patient_id → patient_fhir_id
- ✅ Datetime standardization: VARCHAR → TIMESTAMP(3)
- ✅ v_visits_unified v2.2 integration

### v1.2.0 (2025-10-20)
- ✅ All 4 components fully integrated (WorkflowMonitoring, DocumentTextCache, BinaryFileAgent, ProgressNotePrioritizer)
- ✅ Phases 2B, 2C, 2D fully functional (imaging PDFs, operative reports, progress notes)
- ✅ Complete end-to-end multi-source workflow operational
```

---

## Additional Missing Context

### 7. New Documentation Files (LOW-MEDIUM PRIORITY)

**Created Since Oct 20:**
- `V_UNIFIED_TIMELINE_REBUILD_ASSESSMENT.md` - Timeline rebuild rationale and deployment log
- `TIMELINE_CONSTRUCTION_DEEP_DIVE.md` - Detailed timeline view construction analysis
- `V_UNIFIED_PATIENT_TIMELINE_CONSTRUCTION.md` - Timeline architecture documentation

**Recommendation:** Add these to "Essential Context Documents" section if they contain critical information for new sessions.

### 8. AWS Profile Update (LOW PRIORITY)

**Note:** Timeline rebuild script uses AWS profile `343218191717_AWSAdministratorAccess`, but other scripts use `radiant-prod`. This inconsistency should be noted:

```markdown
### AWS Profile Configuration

**Profiles in Use:**
- `radiant-prod` - Primary production access (most scripts)
- `343218191717_AWSAdministratorAccess` - Administrator access (timeline build)

Both profiles access the same account (343218191717) but use different SSO sessions.

**Check Available Profiles:**
```bash
cat ~/.aws/config | grep -A 2 "\[profile"
```
```

---

## Priority Ranking for Updates

### CRITICAL (Update Immediately):
1. ✅ Version update to v1.3.0
2. ✅ Athena view deployment procedures
3. ✅ Enhanced operative note extraction bug fixes

### HIGH (Update Soon):
4. ✅ Automatic SSO refresh capabilities
5. ✅ Timeline rebuild procedures

### MEDIUM (Update When Convenient):
6. ✅ Extraction failure tracking for QA
7. ✅ ChemotherapyFilter timeline integration
8. ✅ New documentation file references

### LOW (Optional):
9. AWS profile configuration notes
10. Additional troubleshooting scenarios

---

## Recommended Structure Changes

### New Sections to Add:

1. **"Athena View Deployment and Maintenance"** (after "Main Workflow Script")
   - Prerequisite views
   - Deployment procedures
   - Timeline rebuild process
   - Validation steps

2. **"Quality Assurance and Monitoring"** (after "Main Workflow Script")
   - Extraction failure tracking
   - Post-workflow QA checklist
   - Common failure patterns

### Sections to Enhance:

1. **"Key Capabilities"** - Add v1.3.0 features
2. **"Version History"** - Add v1.3.0 entry
3. **"Troubleshooting"** - Add automatic SSO refresh note
4. **"File Structure Reference"** - Add athena_views deployment scripts

---

## Conclusion

The Agent Onboarding Guide is **significantly outdated** and requires immediate updates to reflect 5 days of critical improvements:

**Must Update:**
- Version: v1.2.0 → v1.3.0
- Add Athena deployment procedures (NEW section)
- Add operative note extraction bug fixes
- Add automatic SSO refresh documentation
- Add timeline rebuild procedures

**Impact if Not Updated:**
- New Claude sessions lack critical bug fix knowledge
- No guidance on timeline deployment (high-risk operation)
- Missing QA capabilities (extraction failure tracking)
- Outdated system capabilities description

**Estimated Update Time:** 45-60 minutes for comprehensive update

**Recommended Next Steps:**
1. Update version to v1.3.0
2. Add "Athena View Deployment" section
3. Update "Key Capabilities" with v1.3.0 features
4. Add "Quality Assurance" section
5. Update version history
6. Update "Last Updated" date to 2025-10-25
