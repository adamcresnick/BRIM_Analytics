# Agent Context: BRIM Analytics Athena Views Project

**Purpose**: Comprehensive onboarding document for AI agents joining this project
**Project**: RADIANT PCA - BRIM Analytics - Athena Views Development
**Last Updated**: 2025-10-30
**Git Branch**: `feature/multi-agent-framework`

---

## Table of Contents

1. [🎯 Project Overview](#-project-overview)
2. [🏗️ Technical Environment](#️-technical-environment)
3. [📂 Critical File Locations](#-critical-file-locations)
4. [🔄 Common Workflows](#-common-workflows)
5. [📚 Domain Knowledge](#-domain-knowledge)
6. [🔥 Recent Work Context](#-recent-work-context)
7. [🚀 Quick Start Checklist](#-quick-start-checklist)
8. [💡 Best Practices](#-best-practices)

---

## 🎯 Project Overview

### What This Project Does

**BRIM Analytics** is a hybrid FHIR + clinical notes extraction framework for pediatric brain tumor clinical trial data. This project specifically focuses on:

- **Athena SQL Views** - Scalable FHIR data extraction using AWS Athena
- **View Development** - Creating, testing, and deploying SQL views for clinical data
- **Data Standardization** - Normalizing FHIR resources into analyst-friendly formats
- **Quality Enhancement** - Improving data quality through classification, validation, and enrichment

### Current State

✅ **Production System** with 50+ Athena views covering:
- Patient demographics, diagnoses, procedures, medications
- Imaging studies with corticosteroid use analysis
- Radiation therapy episodes (multi-stage unified view)
- Chemotherapy regimens and medications
- Molecular/genetic testing results
- Hydrocephalus treatments and outcomes
- Surgical procedures with tumor surgery classification
- Unified patient timeline (all events)

### Project Context

**Clinical Domain**: Pediatric CNS tumors (primarily brain tumors)
**Data Source**: Epic EHR via FHIR API → AWS S3 → Athena tables
**Institution**: Children's Hospital of Philadelphia (CHOP)
**Purpose**: Enable retrospective clinical trial data extraction at scale

---

## 🏗️ Technical Environment

### AWS Infrastructure

**AWS Account**: 343218191717 (Production: `radiant-prod`)
**Region**: us-east-1
**Authentication**: AWS SSO (required for all operations)

```bash
# Login command (required before any AWS operations)
aws sso login --profile radiant-prod

# Token expires after ~8 hours
# Re-run if you see: "Error when retrieving token from sso: Token has expired"
```

### Athena Configuration

**Database**: `fhir_prd_db`
**Query Results**: `s3://aws-athena-query-results-531530102581-us-east-1/`
**Source Data**: `s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/`

**Key Tables**:
- `patient_access` - Patient demographics
- `problem_list_diagnoses` - Diagnoses with ICD-10/SNOMED
- `procedure` + 10 child tables - Surgical procedures
- `procedure_code_coding` - Procedure coding systems (CPT, EAP, LOINC, etc.)
- `medication_request` + 9 child tables - Medications
- `observation`, `lab_tests` - Lab results and measurements
- `appointment` - Treatment appointments
- `care_plan` - Treatment plans
- `document_reference` - Clinical documents
- `diagnostic_report` - Imaging reports
- `encounter` - Patient encounters

### Deployment Tools

**Primary Script**: `surgical_procedures_assessment/run_query.sh`

```bash
#!/bin/bash
QUERY_FILE=$1
QUERY=$(cat "$QUERY_FILE")
EXECUTION_ID=$(aws athena start-query-execution \
    --query-string "$QUERY" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-531530102581-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output json | jq -r '.QueryExecutionId')
echo "$EXECUTION_ID"
```

**Usage**:
```bash
# Deploy a view
./surgical_procedures_assessment/run_query.sh athena_views/views/v_oid_reference.sql

# Test a query
./surgical_procedures_assessment/run_query.sh athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql
```

### Git Configuration

**Repository**: https://github.com/adamcresnick/RADIANT_PCA
**Working Directory**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics`
**Current Branch**: `feature/multi-agent-framework`
**Remote**: `origin/feature/multi-agent-framework`

**Important Git Practices**:
- Always commit with descriptive messages
- Include "🤖 Generated with Claude Code" footer
- Use `Co-Authored-By: Claude <noreply@anthropic.com>` trailer
- Never force push to main/master
- Use `git add .` → `git commit` → `git status` workflow

### Local Development Environment

**Python**: 3.9+ (for extraction scripts, not primary focus)
**Shell**: zsh (macOS)
**Required Tools**: aws-cli, jq
**Optional**: Python venv at `BRIM_Analytics/venv/`

---

## 📂 Critical File Locations

### Project Root
```
/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/
```

### Core View Definitions

**🌟 PRIMARY VIEWS FILE (MOST IMPORTANT)** 🌟:
```
athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql
```
**This is THE main file containing 30+ production views with standardized datetime handling**

**Critical Information**:
- **Size**: ~15,000+ lines of SQL
- **Contains**: All core clinical views in ONE file
- **Purpose**: Centralized view management with consistent patterns
- **Last Major Update**: October 2025 (OID decoding added to v_procedures_tumor)
- **Pattern**: Each view is a complete CREATE OR REPLACE VIEW statement

**Key Views in This File**:
- `v_procedures_tumor` - Tumor surgery classification with OID decoding (lines ~2569-3200)
- `v_radiation_episodes` - Unified radiation treatment episodes
- `v_chemo_medications` - Chemotherapy medications with regimen classification
- `v_patient_demographics` - Core patient demographics
- `v_diagnoses` - All diagnoses with ICD-10/SNOMED codes
- `v_imaging_studies` - Imaging with corticosteroid use analysis
- `v_unified_patient_timeline` - All clinical events in timeline format

**How to Work With This File**:
1. **For small changes**: Edit specific view section using line numbers
2. **For new views**: Add at end or create separate file first
3. **Deploy entire file**: `./surgical_procedures_assessment/run_query.sh athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql`
4. **Deploy single view**: Extract view to temp file and deploy individually

**Key View Files**:
- `athena_views/views/v_oid_reference.sql` - **Central OID registry** (22 OIDs documented)
- `athena_views/views/V_PROCEDURES_TUMOR_ENHANCED.sql` - Tumor surgery classification
- `athena_views/views/V_UNIFIED_PATIENT_TIMELINE.sql` - All patient events unified
- `athena_views/views/V_CHEMO_MEDICATIONS.sql` - Chemotherapy medications
- `athena_views/views/V_RADIATION_TREATMENT_EPISODES.sql` - Radiation episodes

### Documentation Hub

**Main README**: `athena_views/README.md`

**OID Documentation** (Critical for understanding coding systems):
- `documentation/README_OID_DOCUMENTATION.md` - **Start here for OID work**
- `documentation/OID_DECODING_WORKFLOW_GUIDE.md` - Complete implementation guide (13,000 words)
- `documentation/OID_QUICK_REFERENCE.md` - One-page cheat sheet
- `documentation/OID_VALIDATION_REPORT.md` - Validation methodology

**Session Summaries** (Historical context):
- `documentation/RADIATION_EPISODE_DEPLOYMENT_SUMMARY.md`
- `athena_views/views/DATETIME_STANDARDIZATION_SUMMARY.md`
- `athena_views/COMPREHENSIVE_REVIEW_SUMMARY.md`

### Assessment Directories (Test Queries & Analysis)

**Recently Organized**:
1. **`surgical_procedures_assessment/`** - Surgical procedure validation
   - `compare_procedures_analysis.sql` - Compare v_procedures_tumor vs surgical_procedures
   - `analyze_overlap.sql` - Deep dive into shared procedures
   - `tumor_surgeries_not_in_surgical_procedures.sql` - Gap analysis
   - `GUIDE_surgical_procedures_augmentation.md` - Analyst guide

2. **`oid_validation/`** - OID decoding validation
   - `validate_procedure_oids.sql` - Discover undocumented OIDs
   - `validate_my_oid_work.sql` - Coverage validation
   - `v_procedures_tumor_original.sql` - Pre-OID baseline
   - `v_procedures_tumor_with_oid.sql` - Post-OID enhanced

3. **`radiation_episodes_assessment/`** - Radiation episode testing
   - `test_stage_1a_clean.sql` - Observations testing
   - `test_stage_1b_clean.sql` - Care plans testing
   - `test_stage_1c_*.sql` - Appointments testing (5 iterations)
   - `test_stage_1d_documents.sql` - Documents testing
   - `test_unified_episodes.sql` - Complete episode testing

### Deployment Scripts

**Utility Script**: `surgical_procedures_assessment/run_query.sh` (see above)

**Named Deployment Scripts** (in `athena_views/views/`):
- `deploy_concomitant_medications.sh`
- `deploy_enhanced_chemo_medications.sh`
- `deploy_imaging_corticosteroid.sh`
- `deploy_medication_join_fixes.sh`
- `deploy_stem_cell_collection.sh`
- `deploy_unified_timeline.sh`

### Analysis & Testing

**Analysis Queries**: `athena_views/analysis/`
- `tumor_surgeries_not_in_surgical_procedures.sql` - Identify missing surgeries
- `GUIDE_surgical_procedures_augmentation.md` - How to augment surgical_procedures

**Testing Queries**: `athena_views/views/testing/`
- `radiation_episodes_strategy_*.sql` - Episode construction strategies
- `test_stage_1a_structured_episodes.sql` - Structured episode testing

---

## 🔄 Common Workflows

### 1. Creating a New View

**Step-by-Step**:

```bash
# 1. Create SQL file with CREATE OR REPLACE VIEW
# Location: athena_views/views/v_new_view_name.sql

# 2. Test locally (optional - validate SQL syntax)
cat athena_views/views/v_new_view_name.sql

# 3. Deploy to Athena
./surgical_procedures_assessment/run_query.sh athena_views/views/v_new_view_name.sql

# 4. Validate deployment
# Run a simple SELECT query to verify view exists and returns data
# (Create a test query file or use Athena console)

# 5. Document in DATETIME_STANDARDIZED_VIEWS.sql if it's a core view
# Or keep as separate file if it's experimental/specialized
```

**View Naming Conventions**:
- Core views: `v_tablename` (lowercase, e.g., `v_patient_demographics`)
- Enhanced views: `V_DESCRIPTIVE_NAME` (uppercase, e.g., `V_PROCEDURES_TUMOR`)
- Internal CTEs: lowercase with underscores (e.g., `patient_codes`, `oid_reference`)

### 2. Adding OID Decoding to Existing View

**Pattern** (see `documentation/OID_DECODING_WORKFLOW_GUIDE.md` for full guide):

```sql
-- Step 1: Add oid_reference CTE (after view header comments)
WITH
oid_reference AS (
    SELECT * FROM fhir_prd_db.v_oid_reference
),

-- Step 2: Add 3 decoded columns to SELECT clause
-- Use consistent naming: <resource_prefix>_coding_system_{code|name|source}
SELECT
    -- Existing columns...
    code_coding_system,

    -- Add OID decoding columns
    oid_ref.masterfile_code as pcc_coding_system_code,
    oid_ref.description as pcc_coding_system_name,
    oid_ref.oid_source as pcc_coding_system_source,

    -- More columns...
FROM source_table
-- Step 3: Add LEFT JOIN to oid_reference
LEFT JOIN oid_reference oid_ref ON source_table.code_coding_system = oid_ref.oid_uri
```

**Column Naming by Resource**:
- Procedures: `pcc_coding_system_*` (procedure_code_coding)
- Medications: `medication_coding_system_*`
- Conditions: `condition_coding_system_*`
- Observations: `observation_coding_system_*`

### 3. Validating OID Coverage

```bash
# Discover all OIDs in use
./surgical_procedures_assessment/run_query.sh oid_validation/validate_procedure_oids.sql

# Check which are documented in v_oid_reference
# Output will show: DOCUMENTED ✓, UNDOCUMENTED ⚠️, NEEDS VERIFICATION ⚡
```

**If Undocumented OIDs Found**:
1. Research OID at https://oid-base.com/ or https://hl7.org/fhir/terminologies.html
2. Add to `athena_views/views/v_oid_reference.sql`
3. Redeploy v_oid_reference
4. Re-run validation query

### 4. Testing View Changes

**Iterative Testing Pattern**:

```bash
# 1. Create test query in appropriate assessment directory
# Example: oid_validation/test_my_changes.sql

# 2. Run test query
./surgical_procedures_assessment/run_query.sh oid_validation/test_my_changes.sql

# 3. Review results (query execution ID printed)
# Check AWS Athena Console or use aws athena get-query-execution

# 4. Iterate on query until working

# 5. Once validated, deploy to production view
./surgical_procedures_assessment/run_query.sh athena_views/views/v_production_view.sql
```

### 5. Git Commit Workflow

**Standard Commit**:
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

git add <files>

git commit -m "$(cat <<'EOF'
Brief summary of changes

Detailed explanation:
- What changed and why
- Key features or fixes
- Impact on existing views

Technical details:
- Specific tables/columns modified
- Performance considerations
- Breaking changes (if any)

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

git status  # Verify commit succeeded
```

**When to Commit**:
- After creating/modifying a view
- After adding documentation
- After organizing files
- Before switching tasks
- **NOT**: After every tiny change (batch related changes)

### 6. Handling AWS SSO Token Expiration

**Symptom**: `Error when retrieving token from sso: Token has expired and refresh failed`

**Fix**:
```bash
aws sso login --profile radiant-prod

# Wait for browser to open and complete authentication
# Token valid for ~8 hours
# Then retry your query
```

---

## 📚 Domain Knowledge

### FHIR Concepts

**FHIR** = Fast Healthcare Interoperability Resources (healthcare data standard)

**Key FHIR Resources**:
- **Patient** - Demographics, identifiers
- **Condition** - Diagnoses, problems
- **Procedure** - Surgical procedures, interventions
- **MedicationRequest** - Prescriptions, medication orders
- **Observation** - Lab results, vital signs, measurements
- **DiagnosticReport** - Imaging reports, pathology
- **Appointment** - Scheduled visits, treatment sessions
- **CarePlan** - Treatment plans, care protocols
- **DocumentReference** - Clinical notes, reports

**FHIR ID Pattern**: `ResourceType/UniqueID`
- Example: `Patient/eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3`
- Always includes resource type prefix

### Epic FHIR Implementation

**Epic** is the EHR system at CHOP. Epic's FHIR implementation has:

**Epic-Specific OIDs** (Object Identifiers):
```
urn:oid:1.2.840.114350.1.13.20.2.7.2.696580
                         ^^              ^^^^^^
                         20 = CHOP       696580 = ASCII encoded "EAP"
                         (site code)     (Masterfile code)
```

**ASCII Decoding**:
- 696580 = 69, 65, 80 = E, A, P = "EAP" = Epic Ambulatory Procedures
- 798268 = 79, 82, 68 = O, R, D = "ORD" = Orders
- 698288 = 69, 82, 88 = E, R, X = "ERX" = Prescriptions

**Common Epic Masterfiles at CHOP**:
- **EAP** (.1) - Procedure Masterfile ID (primary procedure identifier)
- **ORD** - Order Masterfile
- **ERX** - Medication/Prescription Masterfile
- **CSN** - Contact Serial Number (Encounter ID)
- **DEP** - Department Masterfile
- **SER** - Service/Provider Masterfile

**Standard Healthcare Coding Systems**:
- **CPT** - Current Procedural Terminology (procedures)
- **ICD-10-CM** - Diagnoses
- **SNOMED CT** - Clinical terminology
- **LOINC** - Lab tests and observations
- **RxNorm** - Medications
- **HCPCS** - Healthcare Common Procedure Coding System
- **CDT-2** - Current Dental Terminology
- **NDDF** - National Drug Data File

### Clinical Domain: Pediatric Brain Tumors

**Common Tumor Types**:
- Glioblastoma (GBM) - High-grade
- Medulloblastoma - Cerebellar
- Ependymoma - Ventricular
- ATRT (Atypical Teratoid/Rhabdoid Tumor) - Highly aggressive
- Diffuse Intrinsic Pontine Glioma (DIPG) - Brainstem

**Treatment Modalities**:
- **Surgery** - Tumor resection (GTR = Gross Total Resection, STR = Subtotal, Biopsy)
- **Radiation** - Proton therapy, photon therapy (typical: 54 Gy over 30 fractions)
- **Chemotherapy** - Temozolomide, vincristine, carboplatin, etc.
- **Molecular Testing** - IDH mutation, MGMT methylation, 1p/19q codeletion

**Key Procedures**:
- Craniotomy for tumor resection
- Ventriculoperitoneal shunt (VP shunt) for hydrocephalus
- Endoscopic third ventriculostomy (ETV)
- Biopsy (stereotactic, open)

**Complications**:
- Hydrocephalus (fluid buildup in brain)
- Seizures
- Neurological deficits
- Infection

### Datetime Handling in FHIR

**Challenge**: FHIR datetimes stored as VARCHAR in mixed formats:
- ISO 8601 with timezone: `2025-01-24T09:02:00Z`
- Date-only: `2012-10-19`
- Partial dates: `2023-10`

**Standardization Pattern**:
```sql
-- Always cast to TIMESTAMP for datetime columns
CAST(field_name AS TIMESTAMP) as field_name_datetime,

-- Extract date component
CAST(CAST(field_name AS TIMESTAMP) AS DATE) as field_name_date,

-- Handle NULLs explicitly
COALESCE(CAST(field1 AS TIMESTAMP), CAST(field2 AS TIMESTAMP)) as derived_datetime
```

**Naming Convention**:
- `*_datetime` - TIMESTAMP columns (preserves time)
- `*_date` - DATE columns (date only)
- Original field kept as `*_raw` if needed for debugging

### Data Quality Patterns

**Multi-Source Resolution**:
When data exists in multiple places, prioritize:
1. Structured coded data (procedures, observations)
2. Care plans (treatment intent)
3. Appointments (delivery confirmation)
4. Clinical notes (narrative, lower priority)

**Episode Construction**:
For treatment episodes (radiation, chemotherapy):
1. Group by patient + encounter/care plan
2. Derive start date: MIN(observation_date, appointment_date, careplan_date, document_date)
3. Derive end date: MAX(appointment_date, observation_date) or COALESCE(end_date, CURRENT_DATE)
4. Calculate duration: end_date - start_date
5. Aggregate metrics: COUNT appointments, SUM doses, ARRAY_AGG laterality

---

## 🔥 Recent Work Context

### Most Recent Session (October 29-30, 2025)

**Primary Achievement**: Organized 44 test queries into 3 assessment directories

**Work Completed**:

1. **Created `surgical_procedures_assessment/`**
   - Moved surgical procedure comparison queries from /tmp/
   - Created comprehensive README documenting gap analysis
   - Contains queries comparing v_procedures_tumor vs surgical_procedures table
   - Key finding: ~965 missing procedures, 43 high-priority cases with OR Log IDs

2. **Created `oid_validation/`**
   - Moved OID decoding validation queries from /tmp/
   - Documents OID coverage validation process
   - Contains before/after views (original vs enhanced)
   - Captures honest assessment: initial 60% accuracy → 100% after corrections

3. **Created `radiation_episodes_assessment/`**
   - Moved radiation episode development queries from /tmp/
   - 19 test queries covering all 4 stages + unified episodes
   - Documents datetime handling challenges and solutions
   - Contains deployment milestone files

4. **Key Files for Analyst**:
   - `athena_views/analysis/tumor_surgeries_not_in_surgical_procedures.sql` - Discovery query
   - `athena_views/analysis/GUIDE_surgical_procedures_augmentation.md` - Step-by-step guide

**Context for Next Agent**:
- All /tmp/ SQL files have been organized into project structure
- Each assessment directory has comprehensive README
- run_query.sh script is standardized deployment tool
- User may ask analyst for feedback on tumor surgery gap analysis

### Previous Major Work (October 29, 2025)

**OID Decoding Implementation**:

1. **Created Central OID Registry** (`v_oid_reference.sql`)
   - 22 OIDs documented (9 Epic CHOP + 13 Standard)
   - Includes technical notes, FHIR table mappings, ASCII decoding

2. **Enhanced v_procedures_tumor** with OID decoding
   - Added 3 columns: pcc_coding_system_code, pcc_coding_system_name, pcc_coding_system_source
   - Queries now self-documenting (see "EAP" instead of long URIs)
   - Deployed to production

3. **Self-Validation Process**:
   - Discovered initial 60% OID coverage (by count)
   - Missing: CDT-2 (dental), HCPCS (CMS billing)
   - Corrected to 100% coverage for procedure_code_coding

4. **Comprehensive Documentation** (9 files created):
   - `OID_DECODING_WORKFLOW_GUIDE.md` - 13,000-word implementation guide
   - `OID_QUICK_REFERENCE.md` - One-page cheat sheet
   - `OID_VALIDATION_REPORT.md` - Transparent assessment of validation process
   - `README_OID_DOCUMENTATION.md` - Navigation hub

**Pattern Established**:
```sql
-- This pattern can be extended to ANY view with coding systems
WITH
oid_reference AS (SELECT * FROM fhir_prd_db.v_oid_reference),
-- ... other CTEs

SELECT
    original_columns,
    oid.masterfile_code as coding_system_code,
    oid.description as coding_system_name,
    oid.oid_source as coding_system_source
FROM source_table
LEFT JOIN oid_reference oid ON source_table.code_coding_system = oid.oid_uri
```

### Earlier Major Work (October 2025)

**Radiation Episodes** (Multi-Stage View):
- Combined 4 data sources: observations, care plans, appointments, documents
- Datetime standardization across all stages
- Episode construction with start/end dates, duration
- Laterality tracking (left/right/bilateral)
- Dose aggregation

**Surgical Procedures Enhancement**:
- v_procedures_tumor view with tumor surgery classification
- 10 annotation columns for surgical context
- CPT code-based tumor surgery identification
- Epic OR Log linkage
- Keyword-based filtering (craniotomy, resection, etc.)

**Datetime Standardization**:
- Standardized datetime handling across 30+ views
- Pattern: CAST(field AS TIMESTAMP)
- Date extraction: CAST(CAST(field AS TIMESTAMP) AS DATE)
- NULL handling: COALESCE chains

---

## 🚀 Quick Start Checklist

### For a New Agent Joining This Project

**☐ Step 1: Authenticate AWS**
```bash
aws sso login --profile radiant-prod
```

**☐ Step 2: Verify Access**
```bash
# Test query
./surgical_procedures_assessment/run_query.sh -c "SELECT COUNT(*) FROM fhir_prd_db.patient_access"
# (Or create a simple test query file)
```

**☐ Step 3: Read Core Documentation**
- [ ] `BRIM_Analytics/README.md` - Project overview
- [ ] `athena_views/README.md` - Views overview
- [ ] `documentation/README_OID_DOCUMENTATION.md` - OID system (if working with coding systems)
- [ ] This file (`AGENT_CONTEXT.md`) - You're reading it!

**☐ Step 4: Understand Project Structure**
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Key directories
ls -la athena_views/views/          # Production views
ls -la athena_views/analysis/       # Analysis queries
ls -la surgical_procedures_assessment/  # Procedure validation
ls -la oid_validation/              # OID validation
ls -la radiation_episodes_assessment/   # Radiation testing
ls -la documentation/               # Guides and summaries
```

**☐ Step 5: Check Git Status**
```bash
git status
git branch  # Should be on feature/multi-agent-framework
git log --oneline -5  # See recent work
```

**☐ Step 6: Review Recent Work**
- Read [Recent Work Context](#recent-work-context) section above
- Check latest commit messages for context

**☐ Step 7: Identify Your Task**
- User will provide specific task or question
- If unclear, ask user to clarify
- Reference this document for context

---

## 💡 Best Practices

### SQL Development

**1. Always Use CREATE OR REPLACE VIEW**
```sql
CREATE OR REPLACE VIEW fhir_prd_db.v_view_name AS
-- Never just CREATE VIEW (will fail if exists)
```

**2. Use Descriptive CTE Names**
```sql
WITH
patient_demographics AS (...),
tumor_diagnoses AS (...),
surgical_procedures AS (...)
-- Not: cte1, temp_table, x
```

**3. Comment Complex Logic**
```sql
-- Filter to brain tumor surgeries only
-- Criteria: CPT codes 61510-61545 (craniotomy for tumor)
--           OR keyword match: 'craniotomy' + 'tumor'
--           AND status = 'completed'
WHERE ...
```

**4. Handle NULLs Explicitly**
```sql
COALESCE(field1, field2, 'UNKNOWN') as derived_field
-- Not: field1 OR field2 (doesn't work in SQL)
```

**5. Use LEFT JOIN for Optional Data**
```sql
-- Use LEFT JOIN when right table may not have matches
LEFT JOIN oid_reference ON code_system = oid_uri

-- Use INNER JOIN only when match is required
INNER JOIN patient_access ON patient_id = patient_fhir_id
```

### Testing & Validation

**1. Test Before Deploying**
- Create test query in assessment directory
- Run with small patient subset first (WHERE patient_fhir_id = 'Patient/xyz')
- Verify column names, data types, NULL handling
- Then deploy to production view

**2. Validate OID Coverage**
- After any changes to coding system fields
- Run validation queries from oid_validation/
- Add missing OIDs to v_oid_reference

**3. Check Datetime Parsing**
- Verify CAST(field AS TIMESTAMP) succeeds
- Check for NULL handling
- Test with sample data first

### Documentation

**1. Update README Files**
- When adding new views, document in athena_views/README.md
- When creating new patterns, document in relevant guides
- When fixing issues, document in troubleshooting sections

**2. Create Session Summaries**
- For significant work sessions
- Include: What changed, Why, Impact, Next steps
- Save in `documentation/` or `athena_views/`

**3. Maintain Assessment READMEs**
- When adding queries to assessment directories
- Explain purpose, expected results, how to use

### Git Practices

**1. Write Descriptive Commit Messages**
- Summary line (what changed)
- Detailed body (what, why, how, impact)
- Include file counts and key changes
- Always add Claude Code footer

**2. Commit Logical Units**
- One feature/fix per commit
- Don't commit unrelated changes together
- But don't commit every tiny change (batch related work)

**3. Never Force Push**
- Especially to main/master branches
- Use `git push` (will warn if unsafe)

### User Interaction

**1. Ask Clarifying Questions**
- If task is ambiguous, ask before proceeding
- Confirm assumptions about data or requirements
- Verify which files to modify

**2. Report Progress**
- Use TodoWrite tool for multi-step tasks
- Mark todos in_progress and completed
- Keep user informed of what's happening

**3. Be Honest About Limitations**
- If you don't know something, say so
- If a query might be slow/expensive, warn user
- If data might be incomplete, note it

### AWS & Security

**1. Never Commit Secrets**
- No AWS credentials, tokens, or passwords
- No patient identifiers or PHI
- Use .gitignore for sensitive files

**2. Use Correct AWS Profile**
- Always `--profile radiant-prod`
- Never use default profile
- Re-authenticate when tokens expire

**3. Be Mindful of Costs**
- Athena charges by data scanned
- Test with small queries first
- Use WHERE filters to limit data scanned

### Performance

**1. Filter Early**
```sql
-- Good: Filter in CTE
WITH filtered_patients AS (
    SELECT * FROM patient_access
    WHERE patient_fhir_id = 'Patient/xyz'
)

-- Bad: Filter at end
SELECT * FROM patient_access
-- ... complex joins ...
WHERE patient_fhir_id = 'Patient/xyz'
```

**2. Avoid SELECT \***
```sql
-- Good: Select only needed columns
SELECT patient_id, diagnosis_code, diagnosis_date

-- Bad: Select everything
SELECT *
```

**3. Use LIMIT for Testing**
```sql
-- When testing, limit rows
SELECT * FROM large_view LIMIT 100
```

---

## 📋 Appendix: File Path Quick Reference

### Immediate Action Files
```
surgical_procedures_assessment/run_query.sh           # Deploy queries
athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql   # Main views file
athena_views/views/v_oid_reference.sql               # OID registry
documentation/README_OID_DOCUMENTATION.md            # OID system guide
```

### When Creating New Views
```
athena_views/views/                    # Add new view SQL files here
athena_views/analysis/                 # Add analysis queries here
documentation/                         # Add documentation here
```

### When Testing/Validating
```
surgical_procedures_assessment/        # Procedure-related tests
oid_validation/                        # OID coverage validation
radiation_episodes_assessment/         # Radiation episode tests
```

### When Looking for Examples
```
oid_validation/v_procedures_tumor_with_oid.sql      # OID decoding example
radiation_episodes_assessment/test_unified_episodes.sql  # Episode construction example
athena_views/views/V_PROCEDURES_TUMOR_ENHANCED.sql  # Classification example
```

### When Troubleshooting
```
documentation/OID_DECODING_WORKFLOW_GUIDE.md        # OID issues
documentation/OID_VALIDATION_REPORT.md              # Validation methodology
surgical_procedures_assessment/README.md            # Procedure gaps
radiation_episodes_assessment/README.md             # Datetime handling
```

---

## 🎓 Learning Resources

### Understanding FHIR
- Official Spec: https://www.hl7.org/fhir/
- Epic FHIR Docs: https://fhir.epic.com/
- Specific to CHOP: See Epic Vendor Services article in `/Users/resnick/Downloads/`

### Understanding OIDs
- OID Base Registry: https://oid-base.com/
- Epic OID Structure: See `documentation/OID_DECODING_WORKFLOW_GUIDE.md`
- ASCII Encoding: See `documentation/OID_QUICK_REFERENCE.md`

### AWS Athena
- Athena SQL Reference: https://docs.aws.amazon.com/athena/latest/ug/ddl-sql-reference.html
- Presto SQL (Athena engine): https://prestodb.io/docs/current/

### Clinical Terminology
- CPT Codes: https://www.ama-assn.org/practice-management/cpt
- ICD-10-CM: https://www.cdc.gov/nchs/icd/icd-10-cm.htm
- SNOMED CT: https://www.snomed.org/
- LOINC: https://loinc.org/

---

## 🆘 Emergency Contact

**User**: Dr. Adam Cresnick (via Claude Code interface)

**When Stuck**:
1. Check this document for patterns and examples
2. Review relevant README in assessment directories
3. Check recent git commits for similar work
4. Ask user for clarification

**Common Issues & Quick Fixes**:
- AWS token expired → `aws sso login --profile radiant-prod`
- View already exists → Use `CREATE OR REPLACE VIEW`
- Column not found → Check FHIR table structure in athena_views/views/
- OID not documented → Check oid_validation/validate_procedure_oids.sql
- Test query needed → Use assessment directories (surgical_procedures_assessment/, etc.)

---

## ✅ Handoff Complete

**You now have**:
- ✅ Complete technical environment setup (AWS, Athena, Git)
- ✅ Critical file locations for all major project areas
- ✅ Common workflows for view development, testing, deployment
- ✅ Domain knowledge (FHIR, Epic, clinical concepts, OIDs)
- ✅ Recent work context (OID implementation, assessment organization)
- ✅ Best practices for SQL, testing, documentation, Git
- ✅ Quick reference for immediate action

**Next Steps**:
1. Run AWS SSO login
2. Verify access with a test query
3. Read relevant documentation based on user's task
4. Ask user what they need help with
5. Reference this document throughout your work

**Remember**: This document is your foundation. Return to it when:
- Starting a new task
- Encountering unfamiliar concepts
- Needing examples or patterns
- Troubleshooting issues
- Writing documentation

---

**Last Updated**: 2025-10-30
**Maintained By**: Claude Code Agents
**Version**: 1.0 (Initial comprehensive handoff)

---

## 📍 Patient Clinical Journey Timeline Framework

**Location**: `patient_clinical_journey_timeline/`
**Status**: Phases 1-3 COMPLETE, Phase 4 READY TO IMPLEMENT
**Next Session Start Here**: Read `patient_clinical_journey_timeline/NEW_SESSION_PROMPT.md`

### Overview

Comprehensive per-patient timeline framework combining:
1. WHO 2021 CNS tumor molecular classifications (already done for 9 patients)
2. Structured Athena data from 6 views (visits, procedures, chemo, radiation, imaging, pathology)
3. Context-aware MedGemma binary extraction for missing data
4. Protocol validation against WHO 2021 expected paradigms

### What's Complete ✅

**Phases 1-3 Working**:
- ✅ 7-stage stepwise timeline construction
- ✅ Tested on Pineoblastoma patient: 2,202 events, 153 extraction gaps identified
- ✅ Protocol validation at each stage (chemotherapy regimen, radiation dose vs expected)
- ✅ Gap identification with `medgemma_target` fields for binary extraction

**Infrastructure**:
- ✅ Agents copied from MVP: `medgemma_agent.py` (gemma2:27b), `binary_file_agent.py` (S3)
- ✅ WHO 2021 classifications embedded (DO NOT re-extract)
- ✅ 150+ pages of documentation

### What's Next 🚀

**Phase 4: MedGemma Binary Extraction** (2-3 hours to implement)

Create `scripts/patient_timeline_abstraction_V2.py` that:
1. Initializes MedGemmaAgent and BinaryFileAgent
2. Generates context-aware prompts based on WHO 2021 diagnosis + timeline phase
3. Fetches binary documents from S3
4. Calls MedGemma for structured extraction
5. Integrates extractions back into timeline events
6. Outputs enriched JSON artifacts

**Start New Session With**:
```
Read patient_clinical_journey_timeline/NEW_SESSION_PROMPT.md for complete context.

Quick summary: Implement Phase 4 (MedGemma binary extraction) in patient_timeline_abstraction_V2.py.
All infrastructure ready, agents copied, documentation complete. Just need to implement the extraction loop.
```

### Key Files

**Documentation (READ THESE FIRST)**:
- `NEW_SESSION_PROMPT.md` - ⭐ Complete prompt for new session
- `SESSION_COMPLETE_PHASE4_READY.md` - Implementation roadmap
- `PHASE4_READY_TO_IMPLEMENT.md` - Real MedGemma integration plan
- `MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md` - Two-agent architecture + 3 detailed prompt examples

**Scripts**:
- `scripts/patient_timeline_abstraction_V1.py` - Working (Phases 1-3)
- `scripts/patient_timeline_abstraction_V2.py` - TO CREATE (add Phase 4)

**Agents**:
- `agents/medgemma_agent.py` - Medical LLM (gemma2:27b via Ollama)
- `agents/binary_file_agent.py` - S3 streaming + PDF/HTML extraction

**Data**:
- `WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md` - Existing molecular classifications
- `config/patient_cohorts.json` - Patient cohort configuration

### Critical Requirements

**DO NOT**:
- ❌ Re-extract WHO 2021 classifications (already done, embedded in script)
- ❌ Create SQL view for Phase 4 (it's a per-patient Python workflow)
- ❌ Use mock MedGemma (use real gemma2:27b via Ollama)

**DO**:
- ✅ Use existing agents from `agents/`
- ✅ Generate context-aware prompts (examples in MEDGEMMA_ORCHESTRATION_ARCHITECTURE.md)
- ✅ Test incrementally: 1 extraction → high-priority → all 153

### Test Results (Pineoblastoma Patient)

```
PHASE 1: LOAD STRUCTURED DATA
  ✅ pathology: 1309 records
  ✅ procedures: 11 records
  ✅ chemotherapy: 42 records
  ✅ radiation: 2 records
  ✅ imaging: 140 records
  ✅ visits: 683 records

PHASE 2: CONSTRUCT INITIAL TIMELINE
  Stage 0: Molecular diagnosis
    ✅ WHO 2021: Pineoblastoma, CNS WHO grade 4
  Stage 1: Encounters/appointments
    ✅ Added 683 encounters/appointments
  Stage 2: Procedures (surgeries)
    ✅ Added 11 surgical procedures
  Stage 3: Chemotherapy episodes
    ✅ Added 42 chemotherapy episodes
    📋 Expected per WHO 2021: High-dose platinum-based
  Stage 4: Radiation episodes
    ✅ Added 2 radiation episodes
    📋 Expected per WHO 2021: 54 Gy craniospinal + posterior fossa boost
  Stage 5: Imaging studies
    ✅ Added 140 imaging studies
  Stage 6: Pathology events
    ✅ Added 1309 pathology records

  ✅ Timeline construction complete: 2202 total events

PHASE 3: IDENTIFY GAPS
  ✅ 153 extraction opportunities identified:
     missing_eor: 11
     missing_radiation_dose: 2
     vague_imaging_conclusion: 140
```

### Prerequisites for Phase 4

Before implementing in new session:
- ✅ Agents infrastructure: COMPLETE
- ✅ Documentation: 150+ pages
- ⬜ Ollama running: Verify `ollama list` shows `gemma2:27b`
- ⬜ AWS SSO: Login with `aws sso login --profile radiant-prod`

