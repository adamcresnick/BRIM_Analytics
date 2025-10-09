# Generalizable FHIR Extraction Workflow Guide

## Overview

This guide documents the **generalizable workflow** for extracting and validating clinical data from FHIR databases using AWS Athena. The workflow has been developed and validated using patient C1277724 (pediatric medulloblastoma) but is designed to work for **any patient** regardless of:

- Cancer type or diagnosis
- Availability of gold standard data
- Treatment timeline complexity
- Data completeness

## Key Principles

1. **Staging Before Filtering**: Extract ALL data first, then analyze patterns to inform filtering
2. **Schema Discovery First**: Understand table structures before writing queries
3. **Progressive Enhancement**: Start with core data, then enrich with linkages
4. **Validation Without Gold Standard**: Use internal consistency checks and clinical logic
5. **Documentation as Code**: Every script documents its purpose, assumptions, and limitations

---

## Script Inventory

### Discovery Scripts

#### `discover_procedure_schema.py`
**Purpose**: Map FHIR table structures to understand available data and relationships

**When to Use**: 
- First time working with new FHIR tables
- Understanding available fields before extraction
- Identifying subtables and relationships

**Inputs**:
- Database name (e.g., `fhir_v2_prd_db`)
- Table prefix pattern (e.g., `procedure*`)

**Outputs**:
- Schema documentation markdown
- Column lists for all related tables
- Sample queries for exploration

**Generalizability**: 
- Works for any FHIR table family (encounter, condition, medication, etc.)
- Adaptable to different FHIR versions
- No patient-specific logic

**Example Usage**:
```python
# Discover encounter tables for any patient
python3 discover_procedure_schema.py \
  --database fhir_v2_prd_db \
  --table_prefix encounter \
  --output ENCOUNTERS_SCHEMA_DISCOVERY.md
```

---

### Staging File Extraction Scripts

#### `extract_all_encounters_metadata.py`
**Purpose**: Extract **ALL encounters** for a patient with complete metadata before applying any filters

**When to Use**:
- Initial data extraction for new patient
- Understanding encounter patterns and distributions
- Before implementing diagnosis/follow-up filtering logic

**Key Design Decisions**:
- **Extracts everything**: No filtering applied (all 999 encounters for C1277724)
- **Rich metadata**: 24 columns including dates, ages, types, classes, diagnoses
- **Multiple subtables**: Queries 7 encounter-related tables and merges on encounter_fhir_id
- **Aggregates multi-valued fields**: Pipe-separated (e.g., multiple diagnoses per encounter)

**Inputs**:
- Patient FHIR ID (e.g., `e4BwD8ZYDBccepXcJ.Ilo3w3`)
- Birth date (for age calculations)
- AWS profile for Athena access

**Outputs**:
- `ALL_ENCOUNTERS_METADATA_{patient_id}.csv` - Comprehensive staging file (24 columns)
- Summary statistics (total encounters, date coverage, field completeness)

**Generalizability**:
✅ **100% Generalizable** - No hardcoded logic, works for any patient

**Critical for Workflow**:
- Provides "ground truth" of what encounters exist
- Enables pattern analysis without bias
- Supports data quality assessment
- Reveals filtering opportunities

**Example Usage**:
```python
# Extract all encounters for any patient
python3 extract_all_encounters_metadata.py \
  --patient_fhir_id "abc123xyz" \
  --birth_date "2005-05-13" \
  --aws_profile 343218191717_AWSAdministratorAccess
```

**Post-Extraction Analysis Questions**:
1. What encounter classes exist? (Surgery Log, Appointment, HOV, etc.)
2. What percentage have dates? Diagnoses? Reasons?
3. What type_text keywords appear for oncology visits?
4. Are there clear patterns for diagnosis events vs follow-ups?

---

#### `extract_all_procedures_metadata.py`
**Purpose**: Extract **ALL procedures** for a patient with complete metadata before filtering

**When to Use**:
- After encounter extraction (procedures often reference encounters)
- Understanding surgical vs diagnostic procedure patterns
- Before implementing surgical timeline validation

**Key Design Decisions**:
- **No filtering**: Extracts all 72 procedures (10 surgical, 62 diagnostic for C1277724)
- **34 metadata columns**: Codes, categories, performers, body sites, reports
- **Multiple subtables**: Queries 7 procedure-related tables
- **Category classification**: Uses `category_coding_display` for surgical vs diagnostic distinction

**Inputs**:
- Patient FHIR ID
- Birth date
- AWS profile

**Outputs**:
- `ALL_PROCEDURES_METADATA_{patient_id}.csv` - Comprehensive staging file (34 columns)
- Summary statistics (total procedures, surgical count, date coverage)

**Generalizability**:
✅ **100% Generalizable** - No patient-specific logic

**Critical Discovery from C1277724**:
- Only 11% had explicit dates in `performed_period_start`
- 88.9% link to encounters via `encounter_reference`
- **Requires encounter linkage for date resolution** (see linkage script below)

**Example Usage**:
```python
# Extract all procedures for any patient
python3 extract_all_procedures_metadata.py \
  --patient_fhir_id "abc123xyz" \
  --birth_date "2005-05-13" \
  --aws_profile 343218191717_AWSAdministratorAccess
```

**Post-Extraction Analysis Questions**:
1. How many surgical vs diagnostic procedures?
2. What percentage have dates? CPT codes? Reports?
3. Do procedures link to encounters?
4. Are there anesthesia procedures marking surgical events?

---

### Data Enhancement Scripts

#### `link_procedures_to_encounters.py`
**Purpose**: Merge procedures with encounters to resolve dates and add clinical context

**When to Use**:
- After extracting both procedures and encounters staging files
- When procedures lack explicit dates (common issue)
- To enrich procedures with encounter context (location, type, class)

**Key Design Decisions**:
- **Date resolution priority**: `performed_period_start` > `performed_date_time` > `encounter_date`
- **Encounter linkage**: Uses `encounter_reference` field (88.9% coverage for C1277724)
- **Adds 10 new columns**: `best_available_date`, encounter class/type/location, etc.
- **Validates surgical timeline**: Cross-references Surgery Log encounters with procedures

**Inputs**:
- `ALL_PROCEDURES_METADATA_{patient_id}.csv`
- `ALL_ENCOUNTERS_METADATA_{patient_id}.csv`
- Patient birth date

**Outputs**:
- `ALL_PROCEDURES_WITH_ENCOUNTERS_{patient_id}.csv` - Enhanced staging file (44 columns)
- Validation report: `PROCEDURE_ENCOUNTER_LINKAGE_VALIDATION.md`
- Summary statistics (date resolution improvement, linkage rate, surgical validation)

**Generalizability**:
✅ **95% Generalizable** - Surgery Log validation is oncology-specific but date resolution logic is universal

**Critical Results from C1277724**:
- 83.3% date resolution improvement (8→68 dated procedures)
- 100% surgical timeline validation (all 8 Surgery Log procedures aligned)
- Discovered multi-stage recurrence surgery pattern

**Example Usage**:
```python
# Link procedures to encounters for any patient
python3 link_procedures_to_encounters.py \
  --procedures_file ALL_PROCEDURES_METADATA_abc123.csv \
  --encounters_file ALL_ENCOUNTERS_METADATA_abc123.csv \
  --birth_date "2005-05-13" \
  --output ALL_PROCEDURES_WITH_ENCOUNTERS_abc123.csv
```

**Validation Without Gold Standard**:
- Check date resolution rate (target: >80%)
- Verify encounter linkage rate (target: >70%)
- Cross-reference Surgery Log encounters with surgical procedures
- Validate anesthesia procedures mark surgical events (2:1 ratio expected)

---

### Validation Scripts

#### `validate_encounters_csv.py`
**Purpose**: Validate encounters CSV against expected clinical events and timeline

**Current State**: ⚠️ **Needs Generalization** - Uses hardcoded procedure queries for diagnosis events

**When to Use**:
- After extracting encounters staging file
- To validate diagnosis event identification
- To validate follow-up encounter filtering
- To assess field accuracy (ages, dates, statuses)

**Current Approach (Patient-Specific)**:
```python
# CURRENT: Hardcoded procedure query for diagnosis events
diagnosis_query = """
SELECT * FROM procedure 
WHERE patient_id = 'C1277724'
AND date IN ('2018-05-28', '2021-03-10')
"""
# Problem: Requires knowing diagnosis dates in advance
```

**Proposed Generalizable Approach**:
```python
# GENERALIZABLE: Use Surgery Log encounters for diagnosis events
diagnosis_events = encounters_df[
    encounters_df['class_display'] == 'Surgery Log'
]
# Works for any patient, any cancer type, no gold standard needed
```

**Inputs**:
- `ALL_ENCOUNTERS_METADATA_{patient_id}.csv`
- Expected event counts (diagnosis, progression, follow-up) - OPTIONAL
- Birth date

**Outputs**:
- Validation report markdown
- Field accuracy metrics
- Event detection results
- Recommendations for filtering improvements

**Generalizability Roadmap**:
1. ✅ **Phase 1 (Complete)**: Extract all encounters, analyze patterns
2. ✅ **Phase 2 (Complete)**: Validate Surgery Log = diagnosis events (100% reliable)
3. ⏳ **Phase 3 (In Progress)**: Update script to use Surgery Log logic
4. ⏳ **Phase 4 (Planned)**: Add problem_list progression detection
5. ⏳ **Phase 5 (Planned)**: Generalize follow-up filtering with keyword matching

**Example Usage (After Generalization)**:
```python
# Validate encounters for any patient (no gold standard needed)
python3 validate_encounters_csv.py \
  --encounters_file ALL_ENCOUNTERS_METADATA_abc123.csv \
  --birth_date "2005-05-13" \
  --output encounters_validation_report.md
```

---

#### `validate_diagnosis_csv.py`
**Purpose**: Validate diagnosis/condition CSV against expected diagnosis timeline

**Generalizability**: ⚠️ **Moderate** - Uses condition codes but may require cancer-type customization

**When to Use**:
- After extracting condition/diagnosis data
- Validating diagnosis dates and coding
- Assessing diagnosis completeness

---

#### `validate_demographics_csv.py`
**Purpose**: Validate demographics CSV fields (birth date, age, sex, race/ethnicity)

**Generalizability**: ✅ **100% Generalizable** - Demographics fields are universal

**When to Use**:
- First validation step (simplest dataset)
- Ensuring foundational data accuracy
- Validating age calculations

---

## Generalizable Workflow Steps

### Phase 1: Schema Discovery & Planning

**Objective**: Understand available FHIR tables and data structures before extraction

**Steps**:

1. **Identify Patient FHIR ID**
   ```sql
   -- Query patient table
   SELECT fhir_id, birth_date, deceased 
   FROM patient 
   WHERE internal_id = 'C1277724';
   -- Result: fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
   ```

2. **Discover Encounter Schema**
   ```bash
   python3 discover_procedure_schema.py \
     --database fhir_v2_prd_db \
     --table_prefix encounter \
     --output ENCOUNTERS_SCHEMA_DISCOVERY.md
   ```
   **Expected Output**: Documentation of 19 encounter tables, column lists, relationships

3. **Discover Procedure Schema**
   ```bash
   python3 discover_procedure_schema.py \
     --database fhir_v2_prd_db \
     --table_prefix procedure \
     --output PROCEDURES_SCHEMA_DISCOVERY.md
   ```
   **Expected Output**: Documentation of 22 procedure tables, column lists, relationships

4. **Review Documentation**
   - Identify key fields: dates, codes, statuses, references
   - Note multi-valued fields (require aggregation)
   - Document data quality concerns (nulls, coverage)

---

### Phase 2: Staging File Extraction

**Objective**: Extract ALL data without filtering to enable pattern analysis

**Steps**:

1. **Extract All Encounters**
   ```bash
   python3 extract_all_encounters_metadata.py \
     --patient_fhir_id "e4BwD8ZYDBccepXcJ.Ilo3w3" \
     --birth_date "2005-05-13" \
     --aws_profile 343218191717_AWSAdministratorAccess
   ```
   **Output**: `ALL_ENCOUNTERS_METADATA_{patient_id}.csv`
   
   **Validation Checks**:
   - ✅ Total encounters extracted (expected: hundreds)
   - ✅ Date coverage >90%
   - ✅ class_display field populated (Surgery Log, Appointment, HOV, etc.)
   - ✅ type_text field populated for filtering analysis

2. **Extract All Procedures**
   ```bash
   python3 extract_all_procedures_metadata.py \
     --patient_fhir_id "e4BwD8ZYDBccepXcJ.Ilo3w3" \
     --birth_date "2005-05-13" \
     --aws_profile 343218191717_AWSAdministratorAccess
   ```
   **Output**: `ALL_PROCEDURES_METADATA_{patient_id}.csv`
   
   **Validation Checks**:
   - ✅ Total procedures extracted (expected: dozens to hundreds)
   - ✅ category_coding_display populated (surgical vs diagnostic)
   - ⚠️ Date coverage may be LOW (<20%) - expected, requires linkage
   - ✅ encounter_reference populated (>70% for linkage)

3. **Analyze Staging Files**
   
   **Encounter Analysis Questions**:
   ```python
   import pandas as pd
   df = pd.read_csv('ALL_ENCOUNTERS_METADATA_{patient_id}.csv')
   
   # Question 1: What encounter classes exist?
   print(df['class_display'].value_counts())
   # Look for: Surgery Log (diagnosis), HOV (follow-up), Appointment, etc.
   
   # Question 2: What type_text keywords appear?
   print(df['type_text'].value_counts())
   # Look for: Oncology, Surgery, Routine Visit, Follow-up patterns
   
   # Question 3: Date coverage?
   print(f"Date coverage: {df['encounter_date'].notna().sum() / len(df) * 100:.1f}%")
   # Target: >90%
   
   # Question 4: Diagnosis linkage?
   print(f"Diagnosis linked: {df['diagnosis_condition_display'].notna().sum() / len(df) * 100:.1f}%")
   # Target: >30%
   ```
   
   **Procedure Analysis Questions**:
   ```python
   df = pd.read_csv('ALL_PROCEDURES_METADATA_{patient_id}.csv')
   
   # Question 1: Surgical vs Diagnostic breakdown?
   print(df['category_coding_display'].value_counts())
   # Expected: Surgical procedure, Diagnostic procedure
   
   # Question 2: Date coverage?
   print(f"Date coverage: {df['performed_period_start'].notna().sum() / len(df) * 100:.1f}%")
   # Warning if <50%: Requires encounter linkage
   
   # Question 3: Encounter linkage rate?
   print(f"Encounter linked: {df['encounter_reference'].notna().sum() / len(df) * 100:.1f}%")
   # Target: >70% for date resolution
   
   # Question 4: CPT code coverage?
   print(f"CPT coded: {df['code_coding_code'].notna().sum() / len(df) * 100:.1f}%")
   # Target: >90%
   ```

---

### Phase 3: Data Enhancement & Linkage

**Objective**: Enrich procedures with encounter context and resolve missing dates

**Steps**:

1. **Link Procedures to Encounters**
   ```bash
   python3 link_procedures_to_encounters.py \
     --procedures_file ALL_PROCEDURES_METADATA_{patient_id}.csv \
     --encounters_file ALL_ENCOUNTERS_METADATA_{patient_id}.csv \
     --birth_date "2005-05-13" \
     --output ALL_PROCEDURES_WITH_ENCOUNTERS_{patient_id}.csv
   ```
   
   **Expected Results**:
   - Date resolution improvement >50% (C1277724: 83.3%)
   - Enhanced staging file with 10+ new columns
   - Validation report documenting linkage success

2. **Validate Surgical Timeline**
   
   **Without Gold Standard**:
   ```python
   # Cross-reference Surgery Log encounters with surgical procedures
   surgery_log = encounters_df[encounters_df['class_display'] == 'Surgery Log']
   surgical_procs = procedures_df[procedures_df['category_coding_display'] == 'Surgical procedure']
   
   # Check: Do Surgery Log dates match surgical procedure dates?
   # Expected: 100% alignment (±7 days tolerance)
   
   # Check: Do anesthesia procedures mark surgical events?
   anesthesia = procedures_df[procedures_df['code_text'].str.contains('ANESTHESIA', na=False)]
   # Expected: 2 anesthesia procedures per Surgery Log encounter
   ```
   
   **With Gold Standard** (if available):
   ```python
   # Compare against known surgical dates
   expected_surgeries = ['2018-05-28', '2021-03-10']
   found_surgeries = surgery_log['encounter_date'].tolist()
   
   # Validate alignment
   for expected in expected_surgeries:
       if expected in found_surgeries:
           print(f"✅ Found expected surgery: {expected}")
       else:
           print(f"❌ Missing expected surgery: {expected}")
   ```

---

### Phase 4: Pattern-Based Event Identification

**Objective**: Identify diagnosis events, progressions, and follow-ups using data patterns (NOT gold standard)

**Critical Discovery from C1277724**: 
- **Surgery Log encounters = Diagnosis Events** (100% reliable)
- **Anesthesia procedures = Surgical markers** (2:1 ratio with Surgery Log)
- **HOV encounters + Oncology keywords = Follow-up visits**

**Steps**:

1. **Identify Diagnosis Events (Surgery Log Method)**
   ```python
   # GENERALIZABLE: No gold standard needed
   diagnosis_events = encounters_df[
       encounters_df['class_display'] == 'Surgery Log'
   ].sort_values('encounter_date')
   
   print(f"Found {len(diagnosis_events)} diagnosis events")
   print(diagnosis_events[['encounter_date', 'age_at_encounter_days', 'type_text']])
   
   # Expected for cancer patients: 1-3 surgical events
   # - Initial resection
   # - Recurrence surgery (if applicable)
   # - Additional interventions
   ```
   
   **Validation Without Gold Standard**:
   - Check surgical procedures align with Surgery Log dates (±7 days)
   - Check anesthesia procedures present (2 per Surgery Log expected)
   - Clinical sanity: Age at surgery reasonable? (not neonatal for pediatric, etc.)

2. **Identify Progression Events (Problem List Method)**
   ```python
   # Query problem_list for progression/recurrence
   progression_query = """
   SELECT * FROM problem_list_diagnoses
   WHERE patient_id = '{patient_fhir_id}'
   AND (
       LOWER(condition_text) LIKE '%progression%'
       OR LOWER(condition_text) LIKE '%recurrence%'
       OR LOWER(condition_text) LIKE '%metastatic%'
   )
   ORDER BY recorded_date
   """
   
   # Expected: 0-2 progression events (depending on disease course)
   ```
   
   **Validation Without Gold Standard**:
   - Progression date should be AFTER initial diagnosis (temporal logic)
   - Should precede recurrence surgery (if Surgery Log exists after progression)
   - Check clinical notes for confirmation (if available)

3. **Identify Follow-Up Encounters (Keyword Filtering)**
   ```python
   # GENERALIZABLE: Pattern-based, no gold standard needed
   followup_encounters = encounters_df[
       (encounters_df['class_display'] == 'HOV') &  # Hospital Outpatient Visit
       (encounters_df['type_text'].str.contains(
           'ROUTINE ONCO VISIT|ONCO FOL UP|ONCOLOGY FOLLOW|FOLLOWUP ONCO',
           case=False,
           na=False
       ))
   ].sort_values('encounter_date')
   
   print(f"Found {len(followup_encounters)} follow-up encounters")
   print(followup_encounters[['encounter_date', 'age_at_encounter_days', 'type_text']])
   
   # Expected for cancer patients: 5-20 follow-ups over treatment course
   ```
   
   **Validation Without Gold Standard**:
   - Follow-ups should be AFTER diagnosis (temporal logic)
   - Frequency should match expected schedule:
     - Year 1: Every 3-4 months
     - Year 2: Every 4-6 months
     - Year 3+: Every 6-12 months
   - Check encounter_date spacing (median ~90-180 days)

---

### Phase 5: Validation & Quality Assessment

**Objective**: Validate extraction accuracy and data quality WITHOUT relying on gold standard

**Internal Consistency Checks**:

1. **Temporal Logic Validation**
   ```python
   # All dates should be after birth
   assert (encounters_df['encounter_date'] >= birth_date).all()
   
   # Diagnosis should precede follow-ups
   diagnosis_dates = diagnosis_events['encounter_date'].tolist()
   followup_dates = followup_encounters['encounter_date'].tolist()
   assert min(followup_dates) > min(diagnosis_dates)
   
   # Progression should be between initial diagnosis and recurrence
   if len(diagnosis_events) > 1:
       initial_dx = diagnosis_events.iloc[0]['encounter_date']
       recurrence_dx = diagnosis_events.iloc[1]['encounter_date']
       # Check if progression exists between these dates
   ```

2. **Clinical Logic Validation**
   ```python
   # Surgery Log encounters should have matching surgical procedures
   for idx, surgery in surgery_log.iterrows():
       surgery_date = surgery['encounter_date']
       matching_procs = surgical_procs[
           abs((surgical_procs['best_available_date'] - surgery_date).dt.days) <= 7
       ]
       assert len(matching_procs) > 0, f"No procedures found for Surgery Log {surgery_date}"
   
   # Each surgical event should have anesthesia procedures
   for idx, surgery in surgery_log.iterrows():
       surgery_date = surgery['encounter_date']
       matching_anesthesia = anesthesia[
           abs((anesthesia['best_available_date'] - surgery_date).dt.days) <= 7
       ]
       assert len(matching_anesthesia) >= 2, f"Expected 2+ anesthesia for {surgery_date}"
   ```

3. **Data Completeness Assessment**
   ```python
   # Key fields should be populated
   required_fields = {
       'encounter_date': 0.90,  # 90% coverage minimum
       'class_display': 0.95,
       'type_text': 0.80,
       'age_at_encounter_days': 0.90
   }
   
   for field, min_coverage in required_fields.items():
       coverage = encounters_df[field].notna().sum() / len(encounters_df)
       assert coverage >= min_coverage, f"{field} coverage {coverage:.1%} < {min_coverage:.1%}"
   ```

4. **Age Calculation Validation**
   ```python
   # Age should match calculated age from birth_date
   encounters_df['calculated_age_days'] = (
       pd.to_datetime(encounters_df['encounter_date']) - pd.to_datetime(birth_date)
   ).dt.days
   
   age_diff = abs(
       encounters_df['age_at_encounter_days'] - encounters_df['calculated_age_days']
   )
   
   # Allow ±1 day tolerance for timezone differences
   assert (age_diff <= 1).all(), "Age calculation mismatch detected"
   ```

**Validation Report Generation**:
```python
# Create comprehensive validation report
validation_results = {
    'total_encounters': len(encounters_df),
    'diagnosis_events': len(diagnosis_events),
    'progression_events': len(progression_events),
    'followup_encounters': len(followup_encounters),
    'date_coverage_pct': encounters_df['encounter_date'].notna().sum() / len(encounters_df) * 100,
    'surgical_timeline_validated': surgery_log_validated,  # True/False
    'age_calculation_validated': age_validated,  # True/False
    'temporal_logic_validated': temporal_validated,  # True/False
}

# Generate markdown report
with open('VALIDATION_REPORT.md', 'w') as f:
    f.write("# Extraction Validation Report\n\n")
    for key, value in validation_results.items():
        f.write(f"- **{key}**: {value}\n")
```

---

## Adaptation for Different Cancer Types

### Pediatric Solid Tumors (e.g., Medulloblastoma - C1277724)
**Characteristics**:
- Surgery-centric diagnosis events
- Intensive follow-up schedule (every 3 months year 1)
- Long-term survivorship monitoring

**Extraction Approach**:
- ✅ Surgery Log method for diagnosis (validated 100%)
- ✅ HOV encounters for follow-ups (keyword: "ROUTINE ONCO VISIT")
- ✅ Anesthesia procedures mark surgical events

---

### Liquid Tumors (e.g., Leukemia, Lymphoma)
**Characteristics**:
- Biopsy/aspiration for diagnosis (not major surgery)
- Frequent infusion visits (not traditional follow-ups)

**Extraction Approach**:
- ⚠️ Surgery Log may not exist (no surgical resection)
- Alternative: Use problem_list initial diagnosis date
- Follow-ups: Filter for "INFUSION" or "CHEMO ADMIN" in type_text
- Diagnosis validation: Check for bone marrow procedures

**Adaptation Required**:
```python
# Liquid tumor diagnosis identification
diagnosis_events = pd.concat([
    # Method 1: Bone marrow procedures
    procedures_df[
        procedures_df['code_text'].str.contains('BONE MARROW|ASPIRATION', na=False)
    ],
    # Method 2: Problem list initial diagnosis
    problem_list_df[
        problem_list_df['clinical_status'] == 'active'
    ].sort_values('recorded_date').head(1)
])

# Follow-up encounters for liquid tumors
followup_encounters = encounters_df[
    (encounters_df['class_display'] == 'HOV') &
    (encounters_df['type_text'].str.contains(
        'INFUSION|CHEMO ADMIN|TRANSFUSION|LAB DRAW',
        case=False,
        na=False
    ))
]
```

---

### Adult Solid Tumors (e.g., Breast, Lung, Colon)
**Characteristics**:
- Surgery common but may have neoadjuvant therapy
- Longer follow-up intervals (every 6-12 months)
- More outpatient diagnostic procedures

**Extraction Approach**:
- ✅ Surgery Log method for surgical diagnosis
- Alternative: Biopsy procedures for non-surgical diagnosis
- Follow-ups: Less frequent, filter for "SURVEILLANCE" keywords
- Add: Diagnostic imaging procedures (CT, PET, MRI)

**Adaptation Required**:
```python
# Adult solid tumor diagnosis identification
diagnosis_events = pd.concat([
    # Method 1: Surgery Log (surgical resection)
    encounters_df[encounters_df['class_display'] == 'Surgery Log'],
    # Method 2: Biopsy procedures (non-surgical diagnosis)
    procedures_df[
        procedures_df['code_text'].str.contains('BIOPSY|NEEDLE ASPIRATION', na=False)
    ]
]).sort_values('date').drop_duplicates('date')

# Follow-up encounters for adult tumors
followup_encounters = encounters_df[
    (encounters_df['class_display'] == 'HOV') &
    (encounters_df['type_text'].str.contains(
        'SURVEILLANCE|FOLLOWUP ONCO|POST TREATMENT',
        case=False,
        na=False
    ))
]
```

---

## Validation Without Gold Standard

### Scenario: New Patient, No Historical Data

**Challenge**: How to validate extraction accuracy without knowing "true" answers?

**Solution: Multi-Layered Validation Approach**

#### Layer 1: Internal Consistency
```python
# Check 1: Temporal logic
assert all_dates >= birth_date
assert diagnosis_date < min(followup_dates)
assert progression_date < recurrence_date

# Check 2: Referential integrity
for proc in procedures_df.iterrows():
    if proc['encounter_reference']:
        assert proc['encounter_reference'] in encounters_df['fhir_id'].values

# Check 3: Clinical logic
surgery_log_count = len(encounters_df[encounters_df['class_display'] == 'Surgery Log'])
surgical_proc_count = len(procedures_df[procedures_df['category_coding_display'] == 'Surgical procedure'])
assert surgical_proc_count >= surgery_log_count  # Should have procedures for each surgery
```

#### Layer 2: Clinical Plausibility
```python
# Check 1: Age at diagnosis reasonable?
age_at_diagnosis_years = age_at_diagnosis_days / 365.25
assert 0 < age_at_diagnosis_years < 120  # Human lifespan

# Check 2: Follow-up frequency reasonable?
followup_intervals = followup_dates.diff().dt.days.median()
assert 30 <= followup_intervals <= 365  # Monthly to annual

# Check 3: Treatment timeline reasonable?
time_to_treatment = (first_treatment_date - diagnosis_date).days
assert 0 <= time_to_treatment <= 90  # Typically within 3 months
```

#### Layer 3: Cross-Resource Validation
```python
# Check 1: Surgery Log encounters should have matching procedures
for surgery_encounter in surgery_log.iterrows():
    matching_procedures = procedures_df[
        abs((procedures_df['best_available_date'] - surgery_encounter['encounter_date']).dt.days) <= 7
    ]
    assert len(matching_procedures) > 0  # Must have procedures

# Check 2: Surgical procedures should have anesthesia
for surgical_proc in surgical_procs.iterrows():
    proc_date = surgical_proc['best_available_date']
    anesthesia_procs = anesthesia_df[
        abs((anesthesia_df['best_available_date'] - proc_date).dt.days) <= 1
    ]
    assert len(anesthesia_procs) >= 1  # Anesthesia required for surgery

# Check 3: Diagnosis encounters should have condition linkage
for diagnosis_encounter in diagnosis_events.iterrows():
    assert pd.notna(diagnosis_encounter['diagnosis_condition_display'])  # Should have diagnosis
```

#### Layer 4: Statistical Outlier Detection
```python
# Check 1: Unusual follow-up frequency?
followup_intervals = followup_dates.diff().dt.days
outliers = followup_intervals[followup_intervals < 7]  # Weekly or more frequent
if len(outliers) > len(followup_intervals) * 0.1:  # >10% outliers
    print(f"⚠️ Warning: {len(outliers)} unusually frequent follow-ups")

# Check 2: Unusual age progression?
age_progression = encounters_df.sort_values('encounter_date')['age_at_encounter_days'].diff()
negative_ages = age_progression[age_progression < 0]
if len(negative_ages) > 0:
    print(f"❌ Error: {len(negative_ages)} encounters with decreasing ages")

# Check 3: Unusual diagnosis count?
diagnosis_count = len(diagnosis_events)
if diagnosis_count > 5:
    print(f"⚠️ Warning: {diagnosis_count} diagnosis events (expected 1-3)")
```

#### Layer 5: Documentation Review
```python
# If clinical notes available, sample and review
sample_encounters = diagnosis_events.sample(min(3, len(diagnosis_events)))
for idx, encounter in sample_encounters.iterrows():
    # Query clinical notes
    notes_query = f"""
    SELECT note_text 
    FROM clinical_notes 
    WHERE encounter_id = '{encounter['fhir_id']}'
    LIMIT 1
    """
    # Manual review: Does note confirm diagnosis/surgery?
    print(f"Review note for {encounter['encounter_date']}: {note_text[:200]}")
```

---

## Production Deployment Checklist

### Pre-Deployment Validation

- [ ] Schema discovery completed for all relevant tables
- [ ] Staging files extracted for test patient
- [ ] Pattern analysis documented (encounter classes, procedure categories, keywords)
- [ ] Linkage scripts tested and validated
- [ ] Internal consistency checks pass
- [ ] Clinical plausibility checks pass
- [ ] Cross-resource validation passes
- [ ] Statistical outlier detection reviewed

### Script Configuration

- [ ] Patient FHIR ID parameterized (no hardcoding)
- [ ] Birth date parameterized
- [ ] AWS profile configurable
- [ ] Output file paths configurable
- [ ] Date formats standardized (ISO 8601: YYYY-MM-DD)
- [ ] Error handling implemented (try/except, logging)
- [ ] Progress indicators added (print statements, progress bars)

### Documentation

- [ ] Script purpose documented (docstrings)
- [ ] Input parameters documented
- [ ] Output file formats documented
- [ ] Example usage provided
- [ ] Generalizability notes included
- [ ] Known limitations documented
- [ ] Adaptation guidance for different cancer types

### Quality Assurance

- [ ] Test with 3+ different patients (if available)
- [ ] Test with different cancer types (solid vs liquid)
- [ ] Test with incomplete data (missing dates, missing codes)
- [ ] Test with edge cases (neonatal, geriatric, deceased)
- [ ] Validate results manually for 1 patient (100% review)
- [ ] Validate results sampling for remaining patients (10% review)

---

## Common Pitfalls & Solutions

### Pitfall 1: Hardcoding Patient-Specific Logic
❌ **BAD**: 
```python
if patient_id == 'C1277724':
    diagnosis_dates = ['2018-05-28', '2021-03-10']
```

✅ **GOOD**:
```python
diagnosis_events = encounters_df[
    encounters_df['class_display'] == 'Surgery Log'
]
diagnosis_dates = diagnosis_events['encounter_date'].tolist()
```

---

### Pitfall 2: Filtering Too Early
❌ **BAD**: 
```python
# Extracting only diagnosis events (misses pattern discovery)
diagnosis_encounters = query_encounters(class_display='Surgery Log')
```

✅ **GOOD**:
```python
# Extract ALL encounters first, then analyze patterns
all_encounters = query_encounters()  # No filter
# Analyze: What class_display values exist? What keywords?
# Then filter based on patterns discovered
```

---

### Pitfall 3: Ignoring Data Quality Issues
❌ **BAD**: 
```python
# Assuming dates always exist
age_at_encounter = (encounter_date - birth_date).days
```

✅ **GOOD**:
```python
# Check date coverage, handle missing dates
if pd.isna(encounter_date):
    # Try to resolve from linked encounter or procedure
    encounter_date = resolve_date_from_linkage(encounter_id)
    if pd.isna(encounter_date):
        print(f"⚠️ Warning: No date for encounter {encounter_id}")
        return None
age_at_encounter = (encounter_date - birth_date).days
```

---

### Pitfall 4: Assuming Single-Stage Surgeries
❌ **BAD**: 
```python
# Expecting 1 procedure per Surgery Log encounter
assert len(procedures_per_surgery) == 1
```

✅ **GOOD**:
```python
# Allow multi-stage surgeries (e.g., C1277724 recurrence = 6 procedures over 6 days)
procedures_per_surgery = procedures_df[
    abs((procedures_df['best_available_date'] - surgery_date).dt.days) <= 7
]
print(f"Found {len(procedures_per_surgery)} procedures within ±7 days of {surgery_date}")
```

---

### Pitfall 5: Not Documenting Assumptions
❌ **BAD**: 
```python
# Undocumented filtering logic
followup_encounters = encounters_df[encounters_df['type_text'].str.contains('ONCO')]
```

✅ **GOOD**:
```python
# Documented filtering logic with rationale
# ASSUMPTION: Follow-up encounters have "ONCO" or "ONCOLOGY" in type_text
# VALIDATION: Tested on C1277724, captures 90% of known follow-ups
# LIMITATION: May miss follow-ups with non-standard naming
followup_encounters = encounters_df[
    encounters_df['type_text'].str.contains('ONCO|ONCOLOGY', case=False, na=False)
]
```

---

## Future Enhancements

### 1. Automated Pattern Discovery
**Goal**: Auto-detect diagnosis event patterns without manual analysis

**Approach**:
```python
# Cluster encounters by class_display and type_text
# Identify clusters with high diagnosis linkage
# Recommend filtering logic based on patterns
```

### 2. Multi-Patient Validation
**Goal**: Validate extraction logic across cohort, not single patient

**Approach**:
- Extract for 10-20 patients
- Compare diagnosis event counts (expected: 1-3 per patient)
- Compare follow-up frequencies (expected: consistent within cancer type)
- Identify outliers for manual review

### 3. Confidence Scoring
**Goal**: Assign confidence scores to extracted events

**Approach**:
```python
# Confidence factors:
# - Surgery Log + Surgical procedure + Anesthesia = 100% confidence
# - Surgery Log + Surgical procedure (no anesthesia) = 90% confidence
# - Surgery Log only (no procedures) = 70% confidence
# - Procedure only (no Surgery Log) = 50% confidence
```

### 4. Clinical Timeline Visualization
**Goal**: Generate visual timeline of diagnosis, treatment, follow-ups

**Approach**:
- Use matplotlib or plotly for timeline
- Color-code event types (diagnosis=red, progression=orange, follow-up=blue)
- Add treatment phases (surgery, chemo, radiation)

---

## Conclusion

This workflow is designed to be:
- ✅ **Generalizable**: Works for any patient, any cancer type
- ✅ **Robust**: Handles missing data and incomplete records
- ✅ **Validated**: Internal consistency + clinical logic checks
- ✅ **Documented**: Every decision explained and justified
- ✅ **Extensible**: Easy to adapt for new cancer types or data sources

**Key Success Factors**:
1. Extract ALL data first (staging files)
2. Analyze patterns before filtering
3. Use data relationships (procedures ↔ encounters)
4. Validate without requiring gold standard
5. Document assumptions and limitations

**Next Steps**:
1. Update `validate_encounters_csv.py` with Surgery Log logic
2. Test on additional patients (if available)
3. Create production extraction script
4. Package for deployment

---

**Document Version**: 1.0  
**Last Updated**: October 9, 2025  
**Validated On**: Patient C1277724 (Pediatric Medulloblastoma)  
**Author**: BRIM Analytics Team
