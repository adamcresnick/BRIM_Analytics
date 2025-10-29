# Chemotherapy Treatment Episode Approach

## Document Overview

**Purpose**: Comprehensive documentation of the chemotherapy treatment episode construction methodology, including data sources, prioritization strategies, and recommendations for future enhancement through NLP/LLM-based augmentation.

**Date**: 2025-10-28
**Database**: fhir_prd_db
**Primary Views**:
- `v_medications` - All medications with standardized datetime fields
- `v_chemo_medications` - Filtered to chemotherapy/oncology medications only
- `v_chemo_treatment_episodes` - Aggregated treatment episodes with episode boundaries

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Episode Construction Methodology](#episode-construction-methodology)
3. [Data Quality Assessment](#data-quality-assessment)
4. [Note Retrieval Prioritization Framework](#note-retrieval-prioritization-framework)
5. [Recommendations for Validation](#recommendations-for-validation)
6. [NLP/LLM Augmentation Strategy](#nlpllm-augmentation-strategy)
7. [Protocol and Cycle Information](#protocol-and-cycle-information)
8. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Executive Summary

### Current State

We have successfully implemented a three-tier view architecture that constructs chemotherapy treatment episodes from FHIR medication resources:

**Data Coverage**:
- **111,638 chemotherapy medications** across **2,347 patients**
- **99.9% encounter linkage** (mr_encounter_reference) - PRIMARY grouping mechanism
- **78.5% missing structured stop dates** - KEY data quality gap
- **47.4% coverage** of medication notes
- **15.6% of medications with missing stop dates** have extractable date patterns in notes

**Episode Construction**:
- Episodes grouped by **encounter reference** (99.9% coverage)
- Date boundaries use **COALESCE logic** with fallback hierarchy
- Data quality flags enable **future prioritization** without view changes
- Prioritization logic **documented in comments only** (not in output fields)

### Key Findings

1. **Medication notes offer HIGH VALUE** for date extraction:
   - 6,470 notes contain MM/DD/YY date patterns (15.6% of missing stop dates)
   - 69.6% of medications without stop dates have cycle/course information in notes
   - Very few explicit "discontinue" or "stop" keywords (near zero)

2. **CarePlan linkage is LIMITED**:
   - Only 10.4% of medications link to CarePlans
   - CarePlan period_end fields are empty strings (not usable)
   - Encounter-based grouping is far superior

3. **Note retrieval should be prioritized** based on data quality indicators

---

## 2. Episode Construction Methodology

### 2.1 View Architecture

#### v_medications (Base View)
- **Purpose**: Standardize ALL medication datetime fields across FHIR resources
- **Sources**: MedicationAdministration, MedicationStatement, MedicationRequest
- **Key Transformations**:
  - Convert VARCHAR dates to TIMESTAMP using `date_parse()`
  - Preserve original VARCHAR fields for reference
  - Add episode linkage fields (encounter references, group identifiers)
  - Aggregate note text from multiple annotation sources

**Critical Fields**:
```sql
-- Datetime fields (TIMESTAMP)
medication_start_datetime        -- From dosageInstruction.timing.repeat.boundsPeriod.start
medication_stop_datetime         -- From dosageInstruction.timing.repeat.boundsPeriod.end
medication_authored_datetime     -- From MedicationRequest.authoredOn

-- Episode linkage fields
mr_encounter_reference          -- From MedicationRequest.encounter.reference (99.9% coverage)
mr_group_identifier_value       -- From MedicationRequest.groupIdentifier.value
mr_group_identifier_system      -- From MedicationRequest.groupIdentifier.system

-- CarePlan linkage
cp_id                          -- Joined from care_plan table (10.4% coverage)
cp_period_start                -- CarePlan.period.start
cp_period_end                  -- CarePlan.period.end (EMPTY STRINGS - NOT USABLE)

-- Clinical context
medication_notes               -- Aggregated from all annotation.note fields (pipe-delimited)
```

#### v_chemo_medications (Filtered View)
- **Purpose**: Filter to chemotherapy/oncology medications only
- **Filter Logic**:
  - ATC code starts with 'L01' (antineoplastic agents)
  - OR drug name contains chemotherapy keywords
  - OR medication category = oncology
- **Coverage**: 111,638 chemotherapy medications

#### v_chemo_treatment_episodes (Aggregation View)
- **Purpose**: Group medications into treatment episodes with temporal boundaries
- **Grouping Strategy**:
  - **PRIMARY**: `mr_encounter_reference` (99.9% coverage)
  - **FALLBACK**: `mr_group_identifier_value` (if encounter missing)
  - **LAST RESORT**: `cp_id` (if both above missing)

**Episode Fields**:
```sql
-- Episode identifiers
episode_id                          -- Generated from encounter/group/careplan reference
patient_fhir_id                     -- Patient reference
episode_encounter_reference         -- The encounter used for grouping

-- Temporal boundaries (using COALESCE fallback logic)
episode_start_datetime             -- MIN of medication start dates
episode_end_datetime               -- MAX of medication stop dates (NULL if any missing)

-- Episode composition
medication_count                   -- Total medications in episode
unique_drug_count                  -- Distinct drugs (triggers HIGH priority if >3)
medications_with_stop_date         -- Count of medications with stop dates
episode_drug_names                 -- Pipe-delimited list of unique drugs

-- Data quality indicators (for future prioritization)
has_medications_without_stop_date  -- Boolean: Any meds missing stop dates?
has_medication_notes               -- Boolean: Any meds have clinical notes?

-- Medication details (array)
medication_details                 -- All medications in episode with dates
```

### 2.2 Date Fallback Hierarchy

**Episode Start Date** (COALESCE logic):
```sql
COALESCE(
    medication_start_datetime,        -- 1st choice: Timing bounds start (39.8% coverage)
    medication_authored_datetime,     -- 2nd choice: Authored date (99.9% coverage)
    cp_period_start                   -- 3rd choice: CarePlan start (10.4% coverage)
)
```

**Episode Stop Date** (NULL preservation):
```sql
CASE
    WHEN COUNT(CASE WHEN medication_stop_datetime IS NULL THEN 1 END) > 0
    THEN NULL                         -- If ANY medication missing stop date, episode stop = NULL
    ELSE MAX(medication_stop_datetime)
END
```

**Rationale for NULL preservation**:
- Episodes with incomplete data should be flagged as ongoing/open
- Forces explicit handling of missing dates rather than computed guesses
- Enables HIGH priority flagging for note retrieval/validation

### 2.3 Episode Grouping Logic

**Primary Grouping** (99.9% coverage):
```sql
COALESCE(mr_encounter_reference, 'unknown-encounter') || '-episode'
```

**Why encounter-based grouping?**
- Encounters represent discrete care events (visits, admissions)
- Near-universal coverage (99.9%)
- Aligns with clinical workflow (medications ordered during same encounter)
- More reliable than CarePlan linkage (10.4% coverage)

**Fallback Grouping**:
```sql
COALESCE(
    mr_encounter_reference,           -- 1st: Encounter (99.9%)
    mr_group_identifier_value,        -- 2nd: Group identifier
    cp_id,                           -- 3rd: CarePlan (10.4%)
    patient_fhir_id || '-ungrouped'  -- 4th: Patient-level catch-all
)
```

---

## 3. Data Quality Assessment

### 3.1 Temporal Coverage Analysis

**Results from production data**:

| Field Name | Coverage | Source | Data Type |
|-----------|----------|--------|-----------|
| **START DATE OPTIONS** |
| medication_start_date | 39.8% | dosageInstruction.timing.repeat.boundsPeriod.start | VARCHAR |
| medication_authored_date | 99.9% | MedicationRequest.authoredOn | VARCHAR |
| mr_validity_period_start | 0.0% | dispenseRequest.validityPeriod.start | TIMESTAMP |
| cp_period_start | 10.4% | CarePlan.period.start | TIMESTAMP |
| **STOP DATE OPTIONS** |
| medication_stop_date | 21.5% | dosageInstruction.timing.repeat.boundsPeriod.end | VARCHAR |
| cp_period_end | 0.0% | CarePlan.period.end (empty strings) | TIMESTAMP |
| **EPISODE LINKAGE** |
| mr_encounter_reference | 99.9% | MedicationRequest.encounter.reference | VARCHAR |
| cp_id | 10.4% | CarePlan.id (via basedOn) | VARCHAR |

### 3.2 Missing Data Patterns

**Critical Gap: Stop Dates**
- **78.5% of medications** lack structured stop dates
- This represents **87,474 medications** across episodes
- Episodes with ANY missing stop date have `episode_end_datetime = NULL`

**Note Coverage**:
- **52,950 medications have notes** (47.4% of total)
- Of medications with notes:
  - **21.5% have structured stop dates**
  - **78.5% DO NOT have structured stop dates**
  - **15.6% contain extractable date patterns (MM/DD/YY format)**

### 3.3 CarePlan Linkage Assessment

**Coverage**:
- 111,638 chemotherapy medications have `care_plan_references` populated
- Only **10.4% successfully link** to CarePlan records
- **89.6% of references** point to non-existent or filtered CarePlans

**CarePlan Date Fields**:
- `cp_period_start`: 10.4% coverage (timestamp values)
- `cp_period_end`: **0% usable** (empty strings, not NULL)

**Conclusion**: CarePlan-based episode boundaries are NOT viable. Encounter-based grouping is superior.

---

## 4. Note Retrieval Prioritization Framework

### 4.1 Prioritization Logic

The episode view provides data quality indicators that enable **query-time prioritization** without baking priority into the view structure.

**Priority Levels**:

#### HIGH Priority
**Criteria**:
- `has_medications_without_stop_date = true` OR
- `unique_drug_count > 3`

**Rationale**:
- Missing stop dates indicate incomplete structured data
- Complex regimens (>3 drugs) require validation of drug combinations and timing
- These episodes need human review to establish temporal boundaries

**Expected Volume**: ~78% of episodes

#### MEDIUM Priority
**Criteria**:
- `has_medication_notes = true`

**Rationale**:
- Providers added clinical notes → likely contains important context
- 15.6% of these notes contain extractable date patterns
- 69.6% contain cycle/course information
- Notes provide validation context even without dates

**Expected Volume**: ~47% of episodes

#### LOW Priority
**Criteria**:
- Complete structured data (has stop dates)
- Standard regimens (≤3 drugs)
- No medication notes

**Rationale**:
- Episodes have complete temporal boundaries
- Lower risk of data quality issues
- Can be processed with lower priority

**Expected Volume**: ~22% of episodes

### 4.2 Calculating Priority in Queries

**Implementation**:
```sql
SELECT
    episode_id,
    patient_fhir_id,
    episode_start_datetime,
    episode_end_datetime,
    unique_drug_count,
    has_medications_without_stop_date,
    has_medication_notes,

    -- Calculate priority at query time
    CASE
        WHEN has_medications_without_stop_date OR unique_drug_count > 3
        THEN 'HIGH'
        WHEN has_medication_notes
        THEN 'MEDIUM'
        ELSE 'LOW'
    END AS note_retrieval_priority,

    -- Rationale for transparency
    CASE
        WHEN has_medications_without_stop_date AND unique_drug_count > 3
        THEN 'Complex regimen with missing stop dates'
        WHEN has_medications_without_stop_date
        THEN 'Missing stop dates - needs validation'
        WHEN unique_drug_count > 3
        THEN 'Complex regimen (>3 drugs) - needs validation'
        WHEN has_medication_notes
        THEN 'Has medication notes - may contain additional context'
        ELSE 'Complete structured data'
    END AS note_retrieval_rationale

FROM fhir_prd_db.v_chemo_treatment_episodes
ORDER BY
    CASE
        WHEN has_medications_without_stop_date OR unique_drug_count > 3 THEN 1
        WHEN has_medication_notes THEN 2
        ELSE 3
    END,
    episode_start_datetime
```

### 4.3 Integration with Patient Timeline

**Recommended Query Pattern**:
```sql
WITH prioritized_episodes AS (
    SELECT
        episode_id,
        patient_fhir_id,
        episode_encounter_reference,
        episode_start_datetime,
        episode_end_datetime,
        episode_drug_names,
        CASE
            WHEN has_medications_without_stop_date OR unique_drug_count > 3 THEN 'HIGH'
            WHEN has_medication_notes THEN 'MEDIUM'
            ELSE 'LOW'
        END AS priority
    FROM fhir_prd_db.v_chemo_treatment_episodes
    WHERE patient_fhir_id = 'Patient/12345'
)
SELECT
    pt.*,
    pe.priority AS episode_priority
FROM fhir_prd_db.v_patient_timeline pt
LEFT JOIN prioritized_episodes pe
    ON pt.patient_fhir_id = pe.patient_fhir_id
    AND pt.encounter_reference = pe.episode_encounter_reference
ORDER BY pt.event_datetime, pe.priority
```

---

## 5. Recommendations for Validation

### 5.1 Validation Objectives

1. **Validate Drug Regimens**: Confirm medications belong to same treatment protocol
2. **Validate Treatment Period**: Confirm episode start/stop dates align with clinical timeline
3. **Identify Protocol Names**: Extract treatment protocol identifiers from notes
4. **Extract Cycle Numbers**: Identify which cycle in a multi-cycle regimen

### 5.2 Note Types for Validation

#### Priority Order for Note Retrieval

Based on the analysis, prioritize notes in this order:

**1. Medication Notes (HIGHEST VALUE)**
- **Source**: `medication_notes` field in v_chemo_medications
- **Coverage**: 47.4% of medications
- **Content**:
  - Dosing instructions
  - Cycle/course information (69.6% of notes without stop dates)
  - Date patterns (15.6% of notes without stop dates)
  - Clinical trial protocol numbers
  - Provider instructions
- **Example**:
  ```
  "In combination with other dosage form? No
   Dose level: 0.032mg/kg/dose
   Cycle Number (s):7
   Cycle Start Date: Per roadmap
   Pickup Information Date/Time needed: 4/28/23
   Pickup Location: IDS Pharmacy"
  ```

**2. Encounter Notes (HIGH VALUE)**
- **Source**: Clinical notes associated with `mr_encounter_reference`
- **Coverage**: Available for 99.9% of medications (via encounter linkage)
- **Content**:
  - Treatment plans
  - Protocol descriptions
  - Cycle-specific assessments
  - Side effects and modifications
- **Recommended Types**:
  - Oncology progress notes
  - Chemotherapy administration notes
  - Treatment planning notes
  - Infusion center notes

**3. CarePlan Notes (MEDIUM VALUE)**
- **Source**: CarePlan.note field (if CarePlan exists)
- **Coverage**: Only 10.4% of medications link to CarePlans
- **Content**:
  - Overall treatment strategy
  - Protocol names
  - Expected duration
  - Goals of therapy
- **Limitation**: Low coverage makes this a supplementary source only

**4. Diagnostic Report Notes (SUPPLEMENTARY)**
- **Source**: DiagnosticReport notes related to treatment monitoring
- **Content**:
  - Lab results indicating treatment timing
  - Imaging reports documenting treatment response
  - Treatment-related toxicity assessments

### 5.3 Validation Workflow

#### Step 1: HIGH Priority Episodes (Missing Stop Dates or Complex Regimens)

**Objective**: Establish episode boundaries and validate drug combinations

**Note Retrieval Strategy**:
1. Retrieve medication_notes for ALL medications in episode
2. Retrieve encounter notes for episode encounter
3. Search for temporal keywords: "cycle", "course", "through", "until", date patterns
4. Search for protocol keywords: "protocol", "trial", "regimen", "plan"

**Validation Tasks**:
- [ ] Extract any date patterns (MM/DD/YY format)
- [ ] Identify cycle/course numbers
- [ ] Confirm all drugs are part of same protocol
- [ ] Identify protocol name if mentioned
- [ ] Establish episode stop date if possible
- [ ] Flag for manual review if unable to validate

**Output**:
```json
{
  "episode_id": "Encounter/12345-episode",
  "validation_status": "needs_review",
  "extracted_dates": {
    "cycle_start": "2023-04-28",
    "cycle_number": 7,
    "expected_end": null
  },
  "protocol_info": {
    "protocol_name": "Per roadmap",
    "drugs_validated": true
  },
  "notes_reviewed": ["medication_notes", "encounter_notes"]
}
```

#### Step 2: MEDIUM Priority Episodes (Has Notes but Complete Dates)

**Objective**: Enrich episode metadata with protocol and cycle information

**Note Retrieval Strategy**:
1. Retrieve medication_notes for episode
2. Extract protocol names and cycle numbers
3. Validate dates against note content

**Validation Tasks**:
- [ ] Extract protocol name/identifier
- [ ] Extract cycle numbers
- [ ] Validate stop date aligns with cycle duration
- [ ] Flag discrepancies for review

#### Step 3: LOW Priority Episodes (Complete Structured Data)

**Objective**: Spot-check for quality assurance

**Note Retrieval Strategy**:
- Sample 10% of low-priority episodes
- Quick review for obvious data quality issues

---

## 6. NLP/LLM Augmentation Strategy

### 6.1 Date Extraction from Medication Notes

#### Current Findings

**High-Value Target**:
- **6,470 medications** (15.6% of those missing stop dates) have date patterns in notes
- Common formats:
  - `4/28/23` (M/DD/YY)
  - `2/13` (M/DD)
  - `12-08-2022` (MM-DD-YYYY)

#### Recommended Approach

**Phase 1: Regex-Based Extraction**
```python
import re
from datetime import datetime

def extract_dates_from_notes(note_text, authored_date):
    """
    Extract date patterns from medication notes.

    Args:
        note_text: The medication note text
        authored_date: The medication_authored_date for context

    Returns:
        List of extracted dates with confidence scores
    """
    date_patterns = [
        # MM/DD/YYYY or M/D/YYYY
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',
        # MM/DD/YY or M/D/YY
        r'\b(\d{1,2})/(\d{1,2})/(\d{2})\b',
        # MM-DD-YYYY
        r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b',
        # Month DD, YYYY
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
    ]

    extracted_dates = []

    for pattern in date_patterns:
        matches = re.finditer(pattern, note_text, re.IGNORECASE)
        for match in matches:
            try:
                # Parse and validate date
                date_str = match.group(0)
                parsed_date = parse_flexible_date(date_str, authored_date)

                # Check if date makes clinical sense
                if is_clinically_plausible(parsed_date, authored_date):
                    extracted_dates.append({
                        'date': parsed_date,
                        'raw_text': date_str,
                        'confidence': calculate_confidence(match, note_text),
                        'context': get_surrounding_context(match, note_text, window=20)
                    })
            except ValueError:
                continue

    return extracted_dates

def calculate_confidence(match, note_text):
    """
    Calculate confidence score based on context.
    High confidence: Near keywords like "end", "stop", "through", "until"
    Medium confidence: Near "cycle", "course"
    Low confidence: Isolated date
    """
    context = note_text[max(0, match.start()-50):min(len(note_text), match.end()+50)].lower()

    high_confidence_keywords = ['end', 'stop', 'through', 'until', 'complete', 'finish', 'last']
    medium_confidence_keywords = ['cycle', 'course', 'start', 'begin']

    if any(kw in context for kw in high_confidence_keywords):
        return 0.9
    elif any(kw in context for kw in medium_confidence_keywords):
        return 0.7
    else:
        return 0.5
```

**Phase 2: LLM-Based Extraction and Validation**

Use LLM (GPT-4, Claude, or domain-specific model) for:
1. **Temporal reasoning** about extracted dates
2. **Contextual validation** of date plausibility
3. **Relationship extraction** between dates and events

**Example Prompt**:
```
You are a clinical data extraction specialist. Review the following medication note
and extract temporal information about the treatment period.

MEDICATION NOTE:
"{medication_notes}"

STRUCTURED DATA CONTEXT:
- Drug: {drug_name}
- Start Date: {medication_start_date}
- Authored Date: {medication_authored_date}
- Current Stop Date: NULL (missing)

TASK:
1. Extract any dates mentioned in the note
2. Identify the likely treatment stop date
3. Identify cycle/course numbers if mentioned
4. Assess confidence in extracted information

OUTPUT FORMAT (JSON):
{
  "stop_date": "YYYY-MM-DD or null",
  "stop_date_confidence": 0.0-1.0,
  "stop_date_source": "quote from note",
  "cycle_number": integer or null,
  "cycle_duration": "description if available",
  "additional_context": "relevant clinical notes"
}
```

### 6.2 Cycle and Protocol Extraction

#### Cycle Number Extraction

**Regex Patterns**:
```python
cycle_patterns = [
    r'Cycle\s+(?:Number|#)?\s*:?\s*(\d+)',
    r'Cycle\s+(\d+)',
    r'C(\d+)D(\d+)',  # Cycle X Day Y notation
    r'Course\s+(\d+)',
]
```

**LLM Enhancement**:
```
Extract treatment cycle information from the note:

MEDICATION NOTE:
"{medication_notes}"

Identify:
1. Cycle number (if mentioned)
2. Day within cycle (if mentioned)
3. Total planned cycles (if mentioned)
4. Cycle frequency (e.g., "every 28 days")

OUTPUT (JSON):
{
  "cycle_number": integer,
  "day_of_cycle": integer,
  "total_cycles_planned": integer,
  "cycle_frequency_days": integer,
  "cycle_frequency_description": "text"
}
```

#### Protocol Name Extraction

**Common Patterns**:
- Protocol numbers: "Protocol: PNOC017", "Protocol number: 17NO025"
- Trial names: "KEYNOTE-123", "CheckMate-456"
- Regimen acronyms: "R-CHOP", "FOLFOX", "ABVD"

**LLM Prompt**:
```
Extract treatment protocol information:

MEDICATION NOTES:
"{medication_notes}"

ENCOUNTER NOTES (if available):
"{encounter_notes}"

Identify:
1. Protocol name or identifier
2. Clinical trial identifier
3. Standard regimen name
4. Protocol-specific dosing notes

OUTPUT (JSON):
{
  "protocol_name": "string or null",
  "protocol_type": "clinical_trial|standard_regimen|custom",
  "trial_identifier": "string or null",
  "protocol_source": "quote from notes"
}
```

### 6.3 Binary Source Extraction (PDFs, Images)

#### Sources Beyond Structured Data

**High-Value Binary Sources**:
1. **Chemotherapy order sheets** (PDF)
   - Often contain complete protocol information
   - Cycle numbers and dates clearly labeled
   - Drug combinations with doses

2. **Treatment roadmaps** (PDF)
   - Multi-cycle treatment plans
   - Expected start/stop dates for each cycle
   - Protocol names

3. **Infusion records** (PDF/scanned documents)
   - Actual administration dates
   - Drug names and doses
   - Notes about treatment completion

#### OCR + LLM Pipeline

**Step 1: OCR Extraction**
```python
import pytesseract
from pdf2image import convert_from_path

def extract_text_from_pdf(pdf_path):
    """Convert PDF to images and extract text via OCR."""
    images = convert_from_path(pdf_path)
    extracted_text = []

    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        extracted_text.append({
            'page': i + 1,
            'text': text
        })

    return extracted_text
```

**Step 2: LLM-Based Structured Extraction**
```
You are analyzing a chemotherapy treatment document. Extract structured information.

DOCUMENT TEXT (OCR):
"{ocr_text}"

CONTEXT:
- Patient: {patient_id}
- Known drugs in episode: {episode_drug_names}
- Episode start date: {episode_start_datetime}

Extract:
1. Treatment protocol name
2. Cycle numbers and dates
3. All drug names and doses
4. Treatment start and end dates
5. Any notes about modifications

OUTPUT (JSON):
{
  "protocol_name": "string",
  "cycles": [
    {
      "cycle_number": 1,
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "drugs": ["drug1", "drug2"]
    }
  ],
  "treatment_period": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  },
  "modifications": "text"
}
```

### 6.4 Comprehensive Augmentation Pipeline

**Recommended Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│  1. EPISODE PRIORITIZATION (SQL Query)                      │
│     - Query v_chemo_treatment_episodes                      │
│     - Calculate priority (HIGH/MEDIUM/LOW)                  │
│     - Filter to episodes needing augmentation               │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  2. NOTE RETRIEVAL                                          │
│     - Retrieve medication_notes from v_chemo_medications    │
│     - Retrieve encounter notes (via FHIR DocumentReference) │
│     - Retrieve CarePlan notes if available                  │
│     - Identify binary attachments (PDFs, images)            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  3. REGEX-BASED EXTRACTION                                  │
│     - Extract date patterns (confidence scoring)            │
│     - Extract cycle numbers                                 │
│     - Extract protocol identifiers                          │
│     - Flag ambiguous cases for LLM review                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  4. LLM-BASED AUGMENTATION                                  │
│     - Validate extracted dates with temporal reasoning      │
│     - Extract complex protocol information                  │
│     - Resolve ambiguities in cycle/course numbering         │
│     - Provide confidence scores                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  5. BINARY SOURCE PROCESSING (if available)                 │
│     - OCR extraction from PDFs/images                       │
│     - LLM structured extraction from OCR text               │
│     - Cross-reference with structured data                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  6. VALIDATION & CONFIDENCE SCORING                         │
│     - Cross-check extracted data against structured fields  │
│     - Calculate overall confidence score                    │
│     - Flag conflicts for manual review                      │
│     - Generate validation report                            │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  7. DATABASE UPDATE                                         │
│     - Insert augmented data into episode_augmentation table │
│     - Link to source notes/documents                        │
│     - Track provenance and confidence                       │
│     - Update episode metadata                               │
└─────────────────────────────────────────────────────────────┘
```

**Proposed Database Schema for Augmented Data**:
```sql
CREATE TABLE episode_augmentation (
    augmentation_id VARCHAR PRIMARY KEY,
    episode_id VARCHAR NOT NULL,

    -- Extracted dates
    extracted_stop_date TIMESTAMP,
    stop_date_confidence DECIMAL(3,2),
    stop_date_source VARCHAR,  -- 'medication_notes', 'encounter_notes', 'pdf', etc.
    stop_date_source_quote VARCHAR,

    -- Cycle information
    cycle_number INTEGER,
    day_of_cycle INTEGER,
    total_cycles_planned INTEGER,
    cycle_frequency_days INTEGER,

    -- Protocol information
    protocol_name VARCHAR,
    protocol_identifier VARCHAR,
    protocol_type VARCHAR,  -- 'clinical_trial', 'standard_regimen', 'custom'

    -- Processing metadata
    extraction_method VARCHAR,  -- 'regex', 'llm', 'ocr_llm'
    llm_model VARCHAR,
    processing_timestamp TIMESTAMP,
    overall_confidence DECIMAL(3,2),

    -- Review flags
    requires_manual_review BOOLEAN,
    manual_review_reason VARCHAR,
    reviewed_by VARCHAR,
    review_timestamp TIMESTAMP,

    -- Source tracking
    source_note_ids VARCHAR[],  -- Array of note IDs used
    source_document_ids VARCHAR[]  -- Array of binary document IDs
);
```

---

## 7. Protocol and Cycle Information

### 7.1 Current State in Views

#### Available Fields in v_chemo_medications

**Fields containing protocol/cycle information**:
```sql
-- Notes field (primary source)
medication_notes                -- Contains protocol names, cycle numbers, trial identifiers

-- Drug identification
chemo_drug_generic_name        -- Generic drug name
chemo_drug_brand_name          -- Brand name
chemo_drug_atc_code            -- ATC classification code

-- Dosing (may contain cycle info)
dosage_text                    -- Free-text dosing instructions
dosage_patient_instruction     -- Patient-facing instructions

-- Group identifiers (potential protocol linkage)
mr_group_identifier_value      -- May contain protocol or cycle identifiers
mr_group_identifier_system     -- System/namespace for group identifier
```

#### Fields NOT Currently in Views (Potential Additions)

From source tables that could be added:

**MedicationRequest fields**:
- `reason_code`: May contain protocol or diagnosis codes
- `reason_reference`: Reference to Condition/Observation justifying medication
- `supporting_information`: May link to protocol documents or orders
- `course_of_therapy_type`: Coding for treatment course (e.g., "continuous", "seasonal")

**MedicationRequest.category field**:
- May contain oncology-specific categorization
- Currently not exposed in view

**MedicationRequest.intent field**:
- "plan", "order", "instance-order"
- Could help distinguish protocol-level plans vs. individual administrations

### 7.2 Recommendations for View Enhancement

#### Proposed New Fields for v_chemo_medications

```sql
-- Add to v_chemo_medications view:

-- Protocol/reason linkage
mr_reason_code_system          VARCHAR,  -- From MedicationRequest.reasonCode[].coding[].system
mr_reason_code_code            VARCHAR,  -- From MedicationRequest.reasonCode[].coding[].code
mr_reason_code_display         VARCHAR,  -- From MedicationRequest.reasonCode[].coding[].display
mr_reason_reference            VARCHAR,  -- From MedicationRequest.reasonReference.reference

-- Treatment course
mr_course_of_therapy_code      VARCHAR,  -- From MedicationRequest.courseOfTherapyType.coding[].code
mr_course_of_therapy_display   VARCHAR,  -- From MedicationRequest.courseOfTherapyType.coding[].display

-- Intent/category
mr_intent                      VARCHAR,  -- From MedicationRequest.intent
mr_category                    VARCHAR,  -- From MedicationRequest.category[].coding[].display

-- Supporting information (may link to protocol documents)
mr_supporting_info_references  VARCHAR,  -- Pipe-delimited MedicationRequest.supportingInformation[].reference
```

**SQL to add these fields**:
```sql
-- In the medications_base CTE, add JOINs to extract:

LEFT JOIN (
    SELECT
        medication_request_id,
        STRING_AGG(DISTINCT coding_code, ' | ') as reason_codes,
        STRING_AGG(DISTINCT coding_display, ' | ') as reason_displays
    FROM fhir_prd_db.medication_request_reason_code
    GROUP BY medication_request_id
) mr_reason ON mr.id = mr_reason.medication_request_id

LEFT JOIN (
    SELECT
        medication_request_id,
        STRING_AGG(DISTINCT reference, ' | ') as supporting_references
    FROM fhir_prd_db.medication_request_supporting_information
    GROUP BY medication_request_id
) mr_support ON mr.id = mr_support.medication_request_id
```

### 7.3 Protocol Extraction Strategy

#### Location 1: medication_notes Field

**Current Evidence**:
- "Clinical trial status: Patient enrolled on a clinical trial / ON study: Protocol number: 17NO025"
- "Patient receiving commercial supply and is enrolled on a clinical trial / ON Study. Protocol number: PNOC017"

**Extraction Pattern**:
```python
protocol_patterns = [
    r'Protocol\s+(?:number|#)?\s*:?\s*([A-Z0-9-]+)',
    r'Trial\s+(?:ID|identifier)\s*:?\s*([A-Z0-9-]+)',
    r'Study\s+(?:ID|identifier)\s*:?\s*([A-Z0-9-]+)',
]
```

#### Location 2: mr_group_identifier_value

**Purpose**: MedicationRequest.groupIdentifier is designed to link related requests
**Potential Content**: Protocol identifiers, order set IDs, cycle identifiers

**Recommended Analysis**:
```sql
-- Analyze mr_group_identifier_value for patterns
SELECT
    mr_group_identifier_system,
    mr_group_identifier_value,
    COUNT(*) as medication_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM fhir_prd_db.v_chemo_medications
WHERE mr_group_identifier_value IS NOT NULL
GROUP BY mr_group_identifier_system, mr_group_identifier_value
ORDER BY medication_count DESC
LIMIT 100;
```

#### Location 3: mr_reason_code/mr_reason_reference (Proposed)

**Purpose**: Links medication to indication (diagnosis, condition)
**Potential Content**:
- ICD-10 codes for cancer diagnosis
- References to Condition resources with protocol information
- References to CarePlans or ServiceRequests with protocol details

**Recommended Query** (after adding fields):
```sql
SELECT
    mr_reason_code_display,
    mr_reason_reference,
    COUNT(*) as medication_count
FROM fhir_prd_db.v_chemo_medications
WHERE mr_reason_code_display IS NOT NULL
   OR mr_reason_reference IS NOT NULL
GROUP BY mr_reason_code_display, mr_reason_reference
ORDER BY medication_count DESC;
```

#### Location 4: Linked ServiceRequest/ProcedureRequest

**Not currently in views but available in FHIR data**:
- MedicationRequest.basedOn may reference ServiceRequest/ProcedureRequest
- These resources may contain protocol information in:
  - `ServiceRequest.code` - Coded procedures/protocols
  - `ServiceRequest.orderDetail` - Protocol-specific details
  - `ServiceRequest.note` - Free-text protocol descriptions

**Recommended Enhancement**:
```sql
-- Add to v_chemo_medications:
LEFT JOIN (
    SELECT
        mr_id,
        STRING_AGG(sr.code_display, ' | ') as service_request_codes,
        STRING_AGG(sr.note_text, ' | ') as service_request_notes
    FROM fhir_prd_db.medication_request_based_on mrb
    INNER JOIN fhir_prd_db.service_request sr ON mrb.based_on_reference = sr.id
    GROUP BY mr_id
) sr_info ON mr.id = sr_info.mr_id
```

### 7.4 Cycle Number Extraction Strategy

#### Location 1: medication_notes Field

**Current Evidence**:
- "Cycle Number (s):7 Cycle Start Date: Per roadmap"
- "Total of 4 doses per cycle"
- "60mg every 24 hours for 5 days every 28 days" (cycle duration)

**Extraction Patterns**:
```python
def extract_cycle_info(medication_notes):
    """Extract cycle number and frequency from notes."""
    patterns = {
        'cycle_number': [
            r'Cycle\s+Number\s*\(?s?\)?\s*:?\s*(\d+)',
            r'Cycle\s+(\d+)',
            r'C(\d+)D\d+',  # Cycle X Day Y
        ],
        'cycle_frequency': [
            r'every\s+(\d+)\s+days?',
            r'(\d+)-day\s+cycle',
            r'q(\d+)d',  # Every X days
        ],
        'doses_per_cycle': [
            r'(\d+)\s+doses?\s+per\s+cycle',
            r'for\s+(\d+)\s+days\s+every',
        ]
    }

    results = {}
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, medication_notes, re.IGNORECASE)
            if match:
                results[key] = int(match.group(1))
                break

    return results
```

#### Location 2: Temporal Patterns in medication_start_date

**Strategy**: Analyze intervals between medication start dates for same patient/drug
```sql
-- Detect cycle patterns from medication intervals
WITH medication_sequence AS (
    SELECT
        patient_fhir_id,
        chemo_drug_generic_name,
        medication_start_datetime,
        LAG(medication_start_datetime) OVER (
            PARTITION BY patient_fhir_id, chemo_drug_generic_name
            ORDER BY medication_start_datetime
        ) as prev_start,
        date_diff('day',
            LAG(medication_start_datetime) OVER (
                PARTITION BY patient_fhir_id, chemo_drug_generic_name
                ORDER BY medication_start_datetime
            ),
            medication_start_datetime
        ) as days_since_previous
    FROM fhir_prd_db.v_chemo_medications
    WHERE medication_start_datetime IS NOT NULL
)
SELECT
    patient_fhir_id,
    chemo_drug_generic_name,
    days_since_previous,
    COUNT(*) as occurrence_count
FROM medication_sequence
WHERE days_since_previous BETWEEN 7 AND 90  -- Typical cycle lengths
GROUP BY patient_fhir_id, chemo_drug_generic_name, days_since_previous
HAVING COUNT(*) >= 2  -- Pattern repeated at least twice
ORDER BY occurrence_count DESC;
```

#### Location 3: dosage_text Field

**Contains**: Free-text dosing instructions that may include cycle information
**Example**: "Take 1 capsule daily for 21 days, then 7 days off (28-day cycle)"

### 7.5 Proposed episode_protocol_info Table

**Schema for extracted protocol/cycle information**:
```sql
CREATE TABLE episode_protocol_info AS (
    episode_id VARCHAR PRIMARY KEY,
    patient_fhir_id VARCHAR,

    -- Protocol identification
    protocol_name VARCHAR,
    protocol_identifier VARCHAR,
    protocol_source VARCHAR,  -- 'medication_notes', 'service_request', 'manual', etc.
    protocol_confidence DECIMAL(3,2),

    -- Trial information
    is_clinical_trial BOOLEAN,
    trial_identifier VARCHAR,
    trial_status VARCHAR,  -- 'ON study', 'OFF study'

    -- Regimen information
    regimen_name VARCHAR,  -- 'R-CHOP', 'FOLFOX', etc.
    regimen_type VARCHAR,  -- 'combination', 'monotherapy'

    -- Cycle information
    cycle_number INTEGER,
    total_cycles_planned INTEGER,
    cycle_frequency_days INTEGER,
    doses_per_cycle INTEGER,
    cycle_extraction_source VARCHAR,

    -- Inferred from patterns
    inferred_cycle_frequency INTEGER,  -- From temporal pattern analysis
    cycle_frequency_confidence DECIMAL(3,2),

    -- Metadata
    extracted_timestamp TIMESTAMP,
    extraction_method VARCHAR,
    requires_validation BOOLEAN
);
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Objectives**:
- ✅ Complete episode view deployment
- ✅ Validate data quality metrics
- Implement prioritization queries
- Create validation documentation

**Deliverables**:
- [x] v_chemo_treatment_episodes deployed to Athena
- [x] Data quality assessment complete
- [x] Prioritization logic documented in view comments
- [ ] Validation workflow documentation
- [ ] Sample queries for priority-based retrieval

### Phase 2: Note Retrieval Infrastructure (Weeks 3-4)

**Objectives**:
- Build note retrieval pipelines
- Implement encounter note linkage
- Create note sampling for manual review

**Deliverables**:
- [ ] Python scripts to retrieve medication_notes by episode
- [ ] FHIR API queries for encounter notes (DocumentReference)
- [ ] CarePlan note retrieval (where available)
- [ ] Sample dataset of high-priority episodes with notes
- [ ] Manual review template for validation

### Phase 3: Regex-Based Extraction (Weeks 5-6)

**Objectives**:
- Implement date extraction from notes
- Implement cycle number extraction
- Implement protocol identifier extraction
- Calculate confidence scores

**Deliverables**:
- [ ] Python library for regex-based extraction
- [ ] Confidence scoring algorithm
- [ ] Validation against known-complete episodes
- [ ] Performance metrics (precision, recall)
- [ ] Episode_augmentation table schema

### Phase 4: LLM-Based Augmentation (Weeks 7-10)

**Objectives**:
- Design LLM prompts for date/cycle/protocol extraction
- Implement LLM validation pipeline
- Cross-validate LLM vs. regex extraction
- Handle ambiguous cases

**Deliverables**:
- [ ] LLM prompt library (GPT-4/Claude)
- [ ] LLM extraction pipeline (with retry logic)
- [ ] Comparison of regex vs. LLM accuracy
- [ ] Cost analysis for LLM usage
- [ ] Recommendation on regex-first vs. LLM-first strategy

### Phase 5: Binary Source Processing (Weeks 11-14)

**Objectives**:
- Identify available binary sources (PDFs, images)
- Implement OCR pipeline
- Implement LLM-based structured extraction from OCR text
- Cross-reference with structured data

**Deliverables**:
- [ ] Inventory of binary documents per episode
- [ ] OCR pipeline (Tesseract/AWS Textract)
- [ ] LLM extraction from OCR text
- [ ] Structured output: dates, cycles, protocols
- [ ] Validation report comparing binary vs. structured data

### Phase 6: View Enhancement (Weeks 15-16)

**Objectives**:
- Add protocol/reason fields to v_chemo_medications
- Add ServiceRequest linkage if available
- Redeploy enhanced views

**Deliverables**:
- [ ] Enhanced v_chemo_medications with protocol fields
- [ ] Analysis of newly exposed protocol information
- [ ] Updated documentation
- [ ] Redeployment to Athena

### Phase 7: Production Deployment (Weeks 17-18)

**Objectives**:
- Deploy augmentation pipeline to production
- Populate episode_augmentation table
- Integrate with downstream analytics

**Deliverables**:
- [ ] Automated augmentation pipeline (scheduled job)
- [ ] episode_augmentation table populated
- [ ] episode_protocol_info table populated
- [ ] Dashboard for monitoring augmentation coverage
- [ ] Manual review queue for low-confidence extractions

### Phase 8: Validation & Iteration (Weeks 19-20)

**Objectives**:
- Manual review of augmented data
- Calculate accuracy metrics
- Iterate on extraction logic
- Document lessons learned

**Deliverables**:
- [ ] Manual review of 100-200 episodes (stratified sample)
- [ ] Accuracy report (precision, recall, F1)
- [ ] Updated extraction logic based on findings
- [ ] Final documentation and handoff

---

## Appendix A: Key SQL Queries

### A.1 Episode Prioritization Query

```sql
-- Retrieve episodes by priority with full context
WITH prioritized_episodes AS (
    SELECT
        episode_id,
        patient_fhir_id,
        episode_encounter_reference,
        episode_start_datetime,
        episode_end_datetime,
        medication_count,
        unique_drug_count,
        episode_drug_names,
        has_medications_without_stop_date,
        has_medication_notes,

        -- Calculate priority
        CASE
            WHEN has_medications_without_stop_date OR unique_drug_count > 3
            THEN 'HIGH'
            WHEN has_medication_notes
            THEN 'MEDIUM'
            ELSE 'LOW'
        END AS priority,

        -- Calculate rationale
        CASE
            WHEN has_medications_without_stop_date AND unique_drug_count > 3
            THEN 'Complex regimen with missing stop dates'
            WHEN has_medications_without_stop_date
            THEN 'Missing stop dates - needs validation'
            WHEN unique_drug_count > 3
            THEN 'Complex regimen (>3 drugs) - needs validation'
            WHEN has_medication_notes
            THEN 'Has medication notes - may contain additional context'
            ELSE 'Complete structured data'
        END AS rationale,

        -- Priority rank
        ROW_NUMBER() OVER (
            ORDER BY
                CASE
                    WHEN has_medications_without_stop_date OR unique_drug_count > 3 THEN 1
                    WHEN has_medication_notes THEN 2
                    ELSE 3
                END,
                episode_start_datetime DESC
        ) as priority_rank

    FROM fhir_prd_db.v_chemo_treatment_episodes
)
SELECT *
FROM prioritized_episodes
WHERE priority IN ('HIGH', 'MEDIUM')  -- Focus on actionable episodes
ORDER BY priority_rank
LIMIT 1000;
```

### A.2 Note Retrieval Query

```sql
-- Retrieve all notes for high-priority episodes
WITH high_priority_episodes AS (
    SELECT
        episode_id,
        patient_fhir_id,
        episode_encounter_reference
    FROM fhir_prd_db.v_chemo_treatment_episodes
    WHERE has_medications_without_stop_date = true
       OR unique_drug_count > 3
)
SELECT
    hpe.episode_id,
    hpe.patient_fhir_id,
    vcm.medication_request_fhir_id,
    vcm.chemo_drug_generic_name,
    vcm.medication_start_date,
    vcm.medication_stop_date,
    vcm.medication_notes,
    LENGTH(vcm.medication_notes) as note_length,

    -- Flag notes with date patterns
    CASE WHEN REGEXP_LIKE(vcm.medication_notes, '\d{1,2}/\d{1,2}/\d{2,4}')
         THEN true ELSE false END as has_date_pattern,

    -- Flag notes with cycle keywords
    CASE WHEN LOWER(vcm.medication_notes) LIKE '%cycle%'
         THEN true ELSE false END as has_cycle_keyword,

    -- Flag notes with protocol keywords
    CASE WHEN LOWER(vcm.medication_notes) LIKE '%protocol%'
          OR LOWER(vcm.medication_notes) LIKE '%trial%'
         THEN true ELSE false END as has_protocol_keyword

FROM high_priority_episodes hpe
INNER JOIN fhir_prd_db.v_chemo_medications vcm
    ON hpe.episode_encounter_reference = vcm.mr_encounter_reference
WHERE vcm.medication_notes IS NOT NULL
  AND vcm.medication_notes != ''
ORDER BY hpe.episode_id, vcm.medication_start_date;
```

### A.3 Cycle Pattern Detection Query

```sql
-- Detect cycle patterns from medication timing intervals
WITH medication_sequence AS (
    SELECT
        patient_fhir_id,
        mr_encounter_reference,
        chemo_drug_generic_name,
        medication_start_datetime,
        ROW_NUMBER() OVER (
            PARTITION BY patient_fhir_id, chemo_drug_generic_name
            ORDER BY medication_start_datetime
        ) as sequence_num,
        LAG(medication_start_datetime) OVER (
            PARTITION BY patient_fhir_id, chemo_drug_generic_name
            ORDER BY medication_start_datetime
        ) as prev_start,
        date_diff('day',
            LAG(medication_start_datetime) OVER (
                PARTITION BY patient_fhir_id, chemo_drug_generic_name
                ORDER BY medication_start_datetime
            ),
            medication_start_datetime
        ) as days_since_previous
    FROM fhir_prd_db.v_chemo_medications
    WHERE medication_start_datetime IS NOT NULL
),
cycle_patterns AS (
    SELECT
        patient_fhir_id,
        chemo_drug_generic_name,
        days_since_previous as inferred_cycle_length,
        COUNT(*) as cycle_count,
        MIN(medication_start_datetime) as first_cycle_date,
        MAX(medication_start_datetime) as last_cycle_date
    FROM medication_sequence
    WHERE days_since_previous BETWEEN 7 AND 90  -- Typical cycle lengths
    GROUP BY patient_fhir_id, chemo_drug_generic_name, days_since_previous
    HAVING COUNT(*) >= 2  -- Pattern repeated at least twice
)
SELECT
    cp.*,
    -- Calculate confidence based on consistency
    CASE
        WHEN cp.cycle_count >= 4 THEN 0.95
        WHEN cp.cycle_count = 3 THEN 0.85
        WHEN cp.cycle_count = 2 THEN 0.70
        ELSE 0.50
    END as cycle_pattern_confidence
FROM cycle_patterns cp
ORDER BY cp.patient_fhir_id, cp.chemo_drug_generic_name;
```

---

## Appendix B: Example Note Analysis

### Sample High-Priority Episode

**Episode ID**: `Encounter/12345-episode`
**Patient**: `Patient/67890`
**Priority**: HIGH (missing stop dates)

**Medications in Episode**:
1. Carboplatin - Start: 2023-04-28, Stop: NULL
2. Pemetrexed - Start: 2023-04-28, Stop: NULL
3. Pembrolizumab - Start: 2023-04-28, Stop: NULL

**Medication Notes (Carboplatin)**:
```
In combination with other dosage form? No
Dose level: 0.032mg/kg/dose
Cycle Number (s): 7
Cycle Start Date: Per roadmap
Pickup Information Date/Time needed: 4/28/23
Pickup Location: IDS Pharmacy
```

**Extracted Information**:
- Cycle Number: **7**
- Cycle Start Date: **2023-04-28** (matches medication_start_date)
- Date Pattern Confidence: **0.9** (explicit date format)
- Protocol: "Per roadmap" (needs cross-reference with CarePlan/ServiceRequest)

**Recommendations**:
1. Search for treatment roadmap document (PDF/image) via DocumentReference
2. Extract complete cycle schedule from roadmap
3. Calculate expected stop date based on cycle 7 duration (if roadmap available)
4. Validate that all three drugs are part of same protocol (likely platinum-based regimen)

---

## Appendix C: LLM Prompt Templates

### C.1 Date Extraction Prompt

```
SYSTEM: You are a clinical data extraction specialist with expertise in oncology treatment timelines.

USER:
Extract temporal information from this chemotherapy medication note.

MEDICATION CONTEXT:
Drug: {chemo_drug_generic_name}
Start Date: {medication_start_date}
Authored Date: {medication_authored_date}
Current Stop Date: {medication_stop_date or 'NULL (missing)'}

MEDICATION NOTE:
{medication_notes}

TASK:
1. Identify any dates mentioned in the note
2. Determine if any date represents a treatment stop/end date
3. Extract cycle number if mentioned
4. Extract cycle duration or frequency if mentioned

OUTPUT FORMAT (JSON only, no additional text):
{
  "extracted_dates": [
    {
      "date": "YYYY-MM-DD",
      "date_type": "cycle_start|cycle_end|pickup|other",
      "source_text": "exact quote from note",
      "confidence": 0.0-1.0
    }
  ],
  "stop_date": "YYYY-MM-DD or null",
  "stop_date_confidence": 0.0-1.0,
  "stop_date_reasoning": "explanation",
  "cycle_info": {
    "cycle_number": integer or null,
    "cycle_frequency_days": integer or null,
    "cycle_description": "text or null"
  }
}
```

### C.2 Protocol Extraction Prompt

```
SYSTEM: You are a clinical oncology data specialist.

USER:
Extract treatment protocol information from clinical notes.

MEDICATION CONTEXT:
Drugs in episode: {episode_drug_names}
Episode start: {episode_start_datetime}

MEDICATION NOTES:
{medication_notes}

ENCOUNTER NOTES (if available):
{encounter_notes}

TASK:
1. Identify any protocol name or identifier
2. Determine if this is a clinical trial
3. Extract trial identifier if mentioned
4. Identify standard regimen name if applicable (e.g., "R-CHOP", "FOLFOX")

OUTPUT FORMAT (JSON only):
{
  "protocol_name": "string or null",
  "protocol_identifier": "string or null",
  "is_clinical_trial": true|false,
  "trial_identifier": "string or null",
  "trial_status": "ON study|OFF study|null",
  "standard_regimen_name": "string or null",
  "confidence": 0.0-1.0,
  "source_quote": "exact quote from notes"
}
```

### C.3 Validation Prompt

```
SYSTEM: You are validating extracted chemotherapy data for accuracy.

USER:
Review the extracted information and assess its validity against the source notes.

STRUCTURED DATA:
{json.dumps(structured_data, indent=2)}

EXTRACTED DATA:
{json.dumps(extracted_data, indent=2)}

SOURCE NOTES:
{all_notes}

TASK:
1. Validate that extracted dates are consistent with structured data
2. Flag any conflicts or ambiguities
3. Assess overall confidence in extracted information
4. Recommend manual review if necessary

OUTPUT FORMAT (JSON only):
{
  "validation_status": "valid|needs_review|conflicting",
  "conflicts": [
    {
      "field": "field_name",
      "extracted_value": "value",
      "structured_value": "value",
      "severity": "high|medium|low",
      "recommendation": "explanation"
    }
  ],
  "overall_confidence": 0.0-1.0,
  "requires_manual_review": true|false,
  "manual_review_reason": "explanation or null"
}
```

---

## Document Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-28 | Claude Code | Initial comprehensive documentation |

---

## References

1. **FHIR R4 Specification**: https://hl7.org/fhir/R4/
2. **MedicationRequest Resource**: https://hl7.org/fhir/R4/medicationrequest.html
3. **CarePlan Resource**: https://hl7.org/fhir/R4/careplan.html
4. **ATC Classification System**: https://www.whocc.no/atc_ddd_index/
5. **BRIM Analytics Views**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_views/views/DATETIME_STANDARDIZED_VIEWS.sql`
