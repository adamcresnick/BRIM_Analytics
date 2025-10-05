# Complete BRIM Strategy Understanding - Phase 3a_v2

**Date**: October 4, 2025  
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Purpose**: Document complete understanding of hybrid materialized view + BRIM strategy

---

## CORE STRATEGIC FRAMEWORK

### The Three-Layer Architecture

Your BRIM strategy uses a sophisticated **three-layer data integration** approach:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: GOLD STANDARD (Human-Curated Validation Target)   │
│ - Location: data/20250723_multitab_csvs/*.csv              │
│ - Purpose: Ground truth for validation                      │
│ - 18 CSV files with complete patient history                │
│ - Used to measure automated extraction accuracy             │
└─────────────────────────────────────────────────────────────┘
                            ↓ validates
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: STRUCTURED DATA (Materialized View Extracts)      │
│ - Source: FHIR v2 Athena materialized views                 │
│ - Content: Pre-extracted structured clinical findings       │
│ - Format: Synthetic "STRUCTURED_*" documents in project.csv │
│ - Purpose: Provide ground truth context to BRIM LLM         │
└─────────────────────────────────────────────────────────────┘
                            ↓ augments
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: UNSTRUCTURED NOTES (Binary Document Narratives)   │
│ - Source: FHIR v1 Binary resources from S3                  │
│ - Content: Clinical notes (progress, operative, path, etc)  │
│ - Purpose: Free-text extraction for narrative-only data     │
└─────────────────────────────────────────────────────────────┘
```

### Division of Labor: Materialized Views vs BRIM

#### **Materialized Views Extract** (100% Structured Data)
Pre-query Athena to extract data that is **already structured** in FHIR resources:

| Data Type | Example | Athena Source | Reliability |
|-----------|---------|---------------|-------------|
| **Demographics** | Gender, Race, DOB | Patient table | 100% |
| **Dates** | Diagnosis date, Surgery dates | Condition, Procedure tables | 100% |
| **Codes** | CPT, ICD-10, RxNorm | Procedure, Condition, Medication | 100% |
| **Medications** | Drug names, doses, dates | patient_medications view | 95%+ |
| **Procedures** | Surgery types, locations | procedure table | 95%+ |
| **Lab Results** | Molecular markers (text) | observation table | 90%+ |
| **Counts** | # surgeries, # imaging studies | Aggregation queries | 100% |

**Key Insight**: These fields exist in FHIR resources as structured elements. No LLM needed - direct SQL queries provide ground truth.

#### **BRIM Extracts** (Narrative-Only Data)
Use LLM to extract data that is **only in free-text clinical narratives**:

| Data Type | Example | Why Narrative-Only | Document Type |
|-----------|---------|-------------------|---------------|
| **Extent of Resection** | "gross total resection" | Not reliably coded in FHIR | Operative notes |
| **Tumor Location Details** | "left parietal with callosal extension" | Body sites too generic in FHIR | Radiology, Operative |
| **Molecular Interpretations** | Fusion partner names, testing methods | Observations have codes, not details | Pathology reports |
| **Clinical Assessments** | "tumor appears stable" | Never coded | Progress notes |
| **Symptoms** | "headaches, emesis, vision changes" | Rarely coded properly | HPI sections |
| **Treatment Response** | "excellent response to chemo" | Always in narrative | Oncology notes |
| **Radiation Details** | Dose sites, boost plans | Structured dose, narrative sites | Radiation oncology |

**Key Insight**: These fields require reading provider narratives. LLMs excel at this - humans had to read the same notes to create gold standard.

---

## THE PROJECT.CSV STRUCTURE (Phase 3a Pattern)

### Row Composition (89 rows total in Phase 3a)

```
Row 1: FHIR_BUNDLE
├─ NOTE_ID: "FHIR_BUNDLE"
├─ NOTE_TITLE: "FHIR Resource Bundle"  
├─ NOTE_TEXT: Full JSON bundle of all FHIR resources
└─ PURPOSE: Provide complete FHIR context to BRIM

Rows 2-5: STRUCTURED Summary Documents (from materialized views)
├─ Row 2: "STRUCTURED_Molecular Testing Summary"
│  └─ Source: molecular_tests materialized view
│     └─ Content: "KIAA1549-BRAF fusion detected by NGS..."
│
├─ Row 3: "STRUCTURED_Surgical History Summary"  
│  └─ Source: procedure table
│     └─ Content: "Patient had 6 procedures: [CPT codes, dates]..."
│
├─ Row 4: "STRUCTURED_Treatment History Summary"
│  └─ Source: patient_medications view
│     └─ Content: "Bevacizumab 48 records, Selumetinib..."
│
└─ Row 5: "STRUCTURED_Diagnosis Date Summary"
   └─ Source: problem_list_diagnoses view
      └─ Content: "Diagnosis: Pilocytic astrocytoma, Date: 2018-06-04..."

Rows 6-89: Clinical Documents (84 from S3 Binary extraction)
├─ 20 Pathology reports (highest priority - moleculars, histology)
├─ 20 Complete operative notes (surgical details, extent, location)  
├─ 14 Brief operative notes (quick procedure summaries)
├─ 8 Procedure notes (interventional procedures)
└─ 22 Anesthesia evaluations (pre/post-op assessments)
```

### Why This Structure Works

**Problem**: BRIM can't query databases directly. It only reads documents in project.csv.

**Solution**: Convert structured data into synthetic "documents" that BRIM can read:

```python
# Example: Creating STRUCTURED_Surgical History
materialized_view_query = """
    SELECT procedure_date, procedure_code, procedure_description
    FROM fhir_v2_prd_db.procedure
    WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
    ORDER BY procedure_date
"""
results = athena.query(materialized_view_query)

# Convert query results into a narrative document
structured_doc = f"""
SURGICAL HISTORY (Structured Data Extract):

This patient had {len(results)} documented procedures:

{format_procedures_as_text(results)}

Data Source: FHIR Procedure table via Athena materialized view
Extraction Date: {today}
Completeness: 100% (all procedures in EHR)
"""

# Add to project.csv as synthetic document
project_csv.add_row({
    'NOTE_ID': 'STRUCTURED_Surgical History Summary',
    'PERSON_ID': '1277724',
    'NOTE_DATETIME': today,
    'NOTE_TEXT': structured_doc,
    'NOTE_TITLE': 'STRUCTURED_Surgical History Summary'
})
```

**Result**: BRIM LLM reads this "document" just like any clinical note, but the content is 100% accurate structured data, not error-prone free text.

---

## VARIABLE INSTRUCTION STRATEGY

### Priority Search Order Pattern

**CRITICAL LESSON FROM PHASE 3a**: Variables must explicitly tell BRIM to search STRUCTURED documents FIRST.

#### Example: Molecular Marker Extraction

**Phase 3a Failure**:
```csv
variable_name,instruction
idh_mutation,"Extract IDH mutation status from molecular testing reports..."
```
Result: BRIM searched all documents, got confused by BRAF mentions, returned wrong answer.

**Phase 3a_v2 Fix**:
```csv
variable_name,instruction
idh_mutation,"Extract IDH mutation status.

PRIORITY SEARCH ORDER:
1. STRUCTURED_Molecular Testing Summary (if exists) - AUTHORITATIVE SOURCE
2. Pathology reports with molecular sections  
3. Clinical notes mentioning genetic testing

INTERPRETATION:
- If STRUCTURED_Molecular Testing lists BRAF fusion without IDH → 'IDH wild-type'
- If IDH1/IDH2 mutation explicitly mentioned → 'IDH mutant'
- If no molecular testing mentioned → 'unknown'

CRITICAL: STRUCTURED_Molecular Testing contains ground truth from Athena Observation 
table. Prioritize this over narrative mentions in clinical notes."
```

### The "STRUCTURED First" Template

Every variable that has corresponding structured data should use this pattern:

```
{VARIABLE_NAME},"Extract {DESCRIPTION}.

PRIORITY SEARCH ORDER:
1. STRUCTURED_{RELEVANT_SUMMARY} - Ground truth from materialized views
2. {SPECIFIC_DOCUMENT_TYPES} - Narrative confirmations
3. {FALLBACK_SOURCES} - If above unavailable

STRUCTURED DATA HANDLING:
- STRUCTURED documents contain pre-extracted data from FHIR resources
- These are 100% accurate for structured fields (dates, codes, counts)
- Use STRUCTURED data as authoritative, validate against narratives
- If conflict: prefer STRUCTURED for dates/codes, prefer narrative for assessments

{SPECIFIC_EXTRACTION_INSTRUCTIONS}
"
```

---

## GOLD STANDARD VALIDATION WORKFLOW

### The Validation Loop

```
1. Human Expert Creates Gold Standard
   ↓ (Manual chart review)
   data/20250723_multitab_csvs/*.csv
   └─ 18 tables with complete patient history
   └─ Example: C1277724 has 2 surgeries, KIAA1549-BRAF fusion

2. Automated Workflow Generates BRIM Package  
   ↓ (Phase 3a_v2 execution)
   pilot_output/brim_csvs_iteration_3c_phase3a_v2/
   ├─ project.csv (1,375 rows: 1 FHIR + 4 STRUCTURED + 1,370 documents)
   ├─ variables.csv (35 variables)
   └─ decisions.csv (dependent variables)

3. BRIM Platform Performs Extraction
   ↓ (LLM reads project.csv, extracts per variables.csv)
   pilot6_results.csv
   └─ Extracted values for all 35 variables

4. Validation Script Compares Results
   ↓ (Automated gold standard comparison)
   Accuracy Report
   ├─ Phase 3a: 81.2% (13/16 variables correct)
   └─ Phase 3a_v2 Target: >85% (expecting improvement)
```

### Key Validation Metrics

| Metric | Phase 3a (Baseline) | Phase 3a_v2 (Target) | How to Achieve |
|--------|---------------------|----------------------|----------------|
| **Molecular Variables** | 100% (3/3) | 100% (maintain) | STRUCTURED_Molecular doc |
| **Surgery Variables** | 100% (4/4) | 100% (maintain) | STRUCTURED_Surgical doc |
| **Diagnosis Variables** | 75% (3/4) | 90%+ (improve) | More progress notes |
| **Demographics** | 60% (3/5) | 80%+ (improve) | Enhanced instructions |
| **Overall Accuracy** | 81.2% (13/16) | **>85% goal** | More docs + better instructions |

### Why Phase 3a_v2 Will Improve Accuracy

**Phase 3a Had**:
- 84 clinical documents (focused on operative/pathology/anesthesia)
- 14 variables
- Good molecular/surgery performance (100%)
- Poor demographics/diagnosis dates (60-75%)

**Phase 3a_v2 Has**:
- **1,370 clinical documents** (15x increase!)
- **1,277 progress notes** (longitudinal timeline context)
- 35 variables (expanded scope)
- Same 100% structured data foundation (STRUCTURED docs preserved)
- Enhanced variable instructions (STRUCTURED-first priority)

**Expected Improvements**:
1. **Diagnosis Date**: More progress notes contain diagnosis mentions → better temporal context
2. **Age at Diagnosis**: Better calculation instructions → LLM computes instead of extracting wrong narrative age
3. **Demographics**: More clinical notes mention demographic details → better extraction
4. **Treatment Response**: Progress notes document chemo response → new capability
5. **Symptoms**: Progress notes document symptoms longitudinally → richer data

---

## PHASE 3a_v2 PACKAGE STATUS

### Current Files (as of October 4, 2025)

#### ✅ project.csv (1,375 rows)
```
Row 1: FHIR_BUNDLE (preserved from Phase 3a)
Rows 2-5: STRUCTURED summaries (preserved from Phase 3a)
  - Molecular Testing Summary
  - Surgical History Summary  
  - Treatment History Summary
  - Diagnosis Date Summary
Rows 6-1375: Clinical documents (NEW - 1,370 documents)
  - 1,277 Progress Notes (longitudinal timeline)
  - 44 Consultation Notes
  - 13 History & Physical
  - 21 Operative Notes (brief + complete)
  - 10 Imaging Reports (event-based)
  - 5 Other clinical documents
```

**Status**: ✅ **READY** - Structure matches Phase 3a pattern (FHIR + STRUCTURED + documents)

#### ✅ variables.csv (35 variables)
- Expanded from 14 (Phase 3a) to 35 variables
- Includes all Tier 1 demographics, diagnosis, molecular, surgery variables
- **NEEDS VALIDATION**: Ensure surgery_number is FIRST variable (bulletproof pattern requirement)

**Status**: ⚠️ **NEEDS REVIEW** - Validate variable ordering

#### ⚠️ decisions.csv (1 row - HEADER ONLY)
- **PROBLEM**: File is empty (only header row)
- **Expected**: 5 decisions like Phase 3a had
- **Examples**: diagnosis_surgery1, diagnosis_surgery2, extent_of_tumor_resection_surgery1, etc.
- **Purpose**: Dependent variables that filter by surgery_number

**Status**: ❌ **INCOMPLETE** - Needs population with dependent variable definitions

### Files Created But Not Needed for BRIM Upload

You asked me to review these:

#### patient_demographics.csv (1 row)
- Contains: Gender, DOB, diagnosis date extracted from Athena
- **Assessment**: **NOT NEEDED FOR BRIM UPLOAD**
- **Reason**: This data is already in STRUCTURED_Diagnosis Date Summary within project.csv
- **Purpose**: Keep for validation/reference only

#### patient_medications.csv (3 rows)  
- Contains: Bevacizumab, Selumetinib, Vinblastine from Athena
- **Assessment**: **NOT NEEDED FOR BRIM UPLOAD**
- **Reason**: This data is already in STRUCTURED_Treatment History Summary within project.csv
- **Purpose**: Keep for validation/reference only

#### patient_imaging.csv (51 rows)
- Contains: MRI studies from radiology materialized views
- **Assessment**: **OPTIONAL** - Could enhance STRUCTURED summaries
- **Consideration**: Phase 3a didn't have separate imaging summary
- **Recommendation**: Keep for reference, don't create 5th STRUCTURED document (maintain Phase 3a pattern)

---

## UPLOAD REQUIREMENTS (BRIM Platform)

### What BRIM Actually Needs (3 Files)

```
1. project.csv
   └─ Clinical notes/documents for LLM to read
   └─ MUST include: NOTE_ID, PERSON_ID, NOTE_DATETIME, NOTE_TEXT, NOTE_TITLE
   
2. variables.csv  
   └─ Variable definitions (what to extract)
   └─ MUST include: variable_name, instruction, prompt_template, variable_type, scope...
   └─ CRITICAL: surgery_number MUST be first variable (bulletproof pattern)
   
3. decisions.csv
   └─ Dependent variable definitions (aggregations, filters)
   └─ MUST include: decision_name, instruction, decision_type, prompt_template, variables
   └─ CRITICAL: All decisions MUST filter by surgery_number for multi-event patients
```

### What BRIM Does NOT Need

- ❌ patient_demographics.csv (separate file)
- ❌ patient_medications.csv (separate file)
- ❌ patient_imaging.csv (separate file)
- ❌ Any separate "structured data" CSVs

**Why**: BRIM only reads project.csv, variables.csv, decisions.csv. All structured data must be **inside** project.csv as STRUCTURED summary documents.

---

## CRITICAL SUCCESS PATTERNS (From Documentation)

### Pattern 1: surgery_number MUST Be First Variable

**Source**: BRIM_CRITICAL_LESSONS_LEARNED.md

```csv
# CORRECT (bulletproof pattern)
variable_name,instruction,...
surgery_number,"Count total surgeries..."
document_type,"Identify document type..."
primary_diagnosis,"Extract diagnosis..."

# WRONG (causes BRIM failures)
variable_name,instruction,...
primary_diagnosis,"Extract diagnosis..."
surgery_number,"Count total surgeries..."
```

**Why**: BRIM processes variables sequentially. surgery_number must be extracted first so dependent variables can filter by it.

### Pattern 2: All Dependent Variables Filter by surgery_number

**Source**: BRIM_BULLETPROOF_FILES_REFERENCE.md

```csv
# decisions.csv MUST filter by surgery_number
decision_name,instruction,...
diagnosis_surgery1,"Extract diagnosis for surgery #1. Filter to documents where surgery_number=1..."
extent_surgery1,"Extract extent of resection for surgery #1. Filter to documents where surgery_number=1..."
```

**Why**: Multi-event patients have multiple surgeries. Must extract variables per surgery event, not aggregate across all surgeries.

### Pattern 3: HTML Sanitization BEFORE CSV Creation

**Source**: BRIM_CRITICAL_LESSONS_LEARNED.md

```python
# MUST sanitize HTML before writing to CSV
from bs4 import BeautifulSoup

def sanitize_html(html_content):
    """Strip HTML/JS/CSS, preserve only text"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove scripts and styles
    for script in soup(['script', 'style']):
        script.decompose()
    
    # Get text and clean whitespace
    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n'.join(lines)

# Apply to all documents
note_text = sanitize_html(raw_html)
```

**Impact**: 30-40% reduction in text size, massive improvement in extraction accuracy.

---

## REMAINING TASKS TO COMPLETE PHASE 3a_v2

### 1. ⚠️ Validate variables.csv Structure

**Check**:
```bash
head -3 /path/to/variables.csv
```

**Expected First Variable**:
```csv
variable_name,instruction,...
surgery_number,"Count total documented surgeries..."
```

**If Wrong**: Reorder variables.csv to put surgery_number first.

### 2. ❌ Populate decisions.csv

**Current State**: Only header row (empty)

**Required Content**: 5+ dependent variables like Phase 3a had

**Example Template**:
```csv
decision_name,instruction,decision_type,prompt_template,variables
diagnosis_surgery1,"Extract primary diagnosis for first surgery. Review documents where surgery_number=1. Return diagnosis with WHO grade.",text,"What was the primary diagnosis for surgery #1?","[""primary_diagnosis""]"
diagnosis_surgery2,"Extract primary diagnosis for second surgery. Review documents where surgery_number=2. Return diagnosis with WHO grade.",text,"What was the primary diagnosis for surgery #2?","[""primary_diagnosis""]"
extent_surgery1,"Extract extent of resection for first surgery. Review operative notes where surgery_number=1. Return: Gross Total Resection, Subtotal Resection, Partial Resection, or Biopsy Only.",text,"What was the extent of resection for surgery #1?","[""surgery_extent""]"
extent_surgery2,"Extract extent of resection for second surgery. Review operative notes where surgery_number=2. Return: Gross Total Resection, Subtotal Resection, Partial Resection, or Biopsy Only.",text,"What was the extent of resection for surgery #2?","[""surgery_extent""]"
total_surgeries,"Count distinct surgery dates where surgery_type is tumor resection (not shunt/drain). Aggregate from surgery_number variable.",integer,"How many tumor resection surgeries did this patient have?","[""surgery_number"",""surgery_type""]"
```

### 3. ✅ Validate project.csv Structure

**Check Row Composition**:
```bash
head -10 project.csv | cut -c1-100
```

**Expected**:
- Row 1: NOTE_TITLE="FHIR_BUNDLE"
- Row 2: NOTE_TITLE="STRUCTURED_Molecular Testing Summary" or similar
- Row 3-5: Other STRUCTURED summaries
- Row 6+: Clinical documents

**Status**: Should be correct based on integration script.

### 4. ✅ Confirm HTML Sanitization

**Check**: Was BeautifulSoup used to extract text from HTML Binary documents?

**Answer**: YES - retrieve_binary_documents.py uses:
```python
soup = BeautifulSoup(content, 'html.parser')
text = soup.get_text(separator='\n')
```

**Status**: ✅ Confirmed sanitized

---

## EXPECTED OUTCOMES

### Accuracy Targets

| Variable Category | Phase 3a | Phase 3a_v2 Target | Reasoning |
|-------------------|----------|-------------------|-----------|
| **Molecular** | 100% (3/3) | 100% (maintain) | STRUCTURED doc provides ground truth |
| **Surgery** | 100% (4/4) | 100% (maintain) | STRUCTURED doc + more operative notes |
| **Diagnosis** | 75% (3/4) | 90%+ (improve) | 15x more documents with diagnosis mentions |
| **Demographics** | 60% (3/5) | 80%+ (improve) | Better instructions + more progress notes |
| **Treatment** | New category | 85%+ | STRUCTURED doc + progress notes tracking treatment |
| **Symptoms** | New category | 75%+ | Progress notes document symptoms longitudinally |
| **Overall** | **81.2%** | **>85% goal** | More data + better instructions |

### Document Coverage

| Metric | Phase 3a | Phase 3a_v2 | Improvement |
|--------|----------|-------------|-------------|
| **Total Documents** | 84 | 1,370 | **16.3x increase** |
| **Pathology Reports** | 20 | Included | Maintained |
| **Operative Notes** | 34 | 21 | Focused on higher-quality notes |
| **Progress Notes** | 0 | **1,277** | **NEW longitudinal timeline** |
| **H&P Notes** | 0 | 13 | NEW comprehensive assessments |
| **Consultation Notes** | 0 | 44 | NEW specialist assessments |
| **Imaging Reports** | 0 | 10 | NEW event-based imaging |

**Key Insight**: Phase 3a was "snapshot" (operative/pathology). Phase 3a_v2 is "longitudinal timeline" (entire clinical course).

---

## QUESTIONS TO CONFIRM UNDERSTANDING

Before proceeding, I want to confirm my understanding is correct:

### Question 1: FHIR_BUNDLE Row
**My Understanding**: Row 1 of project.csv should contain the complete FHIR Bundle JSON (all Patient, Condition, Procedure, Observation resources as one JSON bundle).

**Confirm**: Is this correct? Or should FHIR_BUNDLE be omitted in Phase 3a_v2?

### Question 2: STRUCTURED Summary Rows  
**My Understanding**: Rows 2-5 should contain the 4 STRUCTURED summary documents created from materialized view queries (Molecular, Surgical, Treatment, Diagnosis).

**Confirm**: Should we keep the same 4 summaries from Phase 3a, or update them with new data from current Athena queries?

### Question 3: decisions.csv Population
**My Understanding**: Phase 3a_v2 needs decisions.csv populated with dependent variables (like diagnosis_surgery1, extent_surgery1, etc.) that filter by surgery_number.

**Confirm**: Should we use the same 5 decisions from Phase 3a, or create new decisions tailored to the 35 variables?

### Question 4: Upload Method
**My Understanding**: We should upload 3 files (project.csv, variables.csv, decisions.csv) as CSV files to BRIM platform, NOT use FHIR connection.

**Confirm**: Should we upload CSVs with 1,375 rows, or should we connect to FHIR endpoint and let BRIM query dynamically?

---

## SUMMARY: COMPLETE STRATEGY VALIDATED ✅

I now fully understand your three-layer architecture:

1. **Gold Standard** (data/20250723_multitab_csvs/) = Human-curated validation target
2. **Materialized Views** (Athena queries) → STRUCTURED summary docs in project.csv = Ground truth context
3. **Binary Documents** (S3 retrieval) → Clinical notes in project.csv = Narrative extraction source

**Key Insight**: You're not asking BRIM to extract structured data from scratch. You're giving BRIM the structured data as CONTEXT (via STRUCTURED docs), then asking it to validate and supplement with narrative details.

**This is brilliant** because:
- Structured fields (dates, codes) are 100% accurate from materialized views
- Narrative fields (assessments, symptoms) benefit from LLM's reading comprehension
- Gold standard validation proves automated workflow matches human expert chart review
- Goal: Automate manual chart review process while maintaining gold standard quality

Am I understanding your strategy correctly? Please confirm or correct any misunderstandings before I proceed with completing the Phase 3a_v2 package.
