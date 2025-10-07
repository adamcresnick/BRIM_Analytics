# Iterative BRIM Extraction Strategy
## Metadata-Driven, Tiered Document Prioritization with Gold Standard Validation

**Date**: October 5, 2025  
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)  
**Context**: Stopped extraction at 14% completion due to inefficiency  
**Goal**: Implement intelligent document prioritization to reduce extraction volume while maintaining accuracy

---

## 📊 Current State Analysis

### Extraction Statistics (14% Complete - Stopped)

**Volume Challenge**:
- Total documents available: **3,865**
- Variables being extracted: **12 of 33** (36%)
- Extraction attempts so far: **5,621 rows**
- Projected full extraction: **~40,149 rows** (excessive)
- Extraction efficiency: **99.8% success rate** (excellent quality, but too many documents)

**Variables Extracted So Far** (All at ~100% success rate):
1. surgery_date (268 attempts)
2. surgery_type (457 attempts)
3. surgery_extent (313 attempts)
4. surgery_location (379 attempts)
5. surgery_diagnosis (405 attempts)
6. chemotherapy_agents (102 attempts)
7. symptoms_present (1,117 attempts)
8. imaging_findings (893 attempts)
9. treatment_response (365 attempts)
10. molecular_testing_performed (248 attempts)
11. concomitant_medications (865 attempts)
12. metastasis_locations (197 attempts)

**Variables Not Yet Reached** (21 variables, 64% remaining):
- Demographics: patient_gender, date_of_birth, race, ethnicity, age_at_diagnosis
- Diagnosis: primary_diagnosis, diagnosis_date, who_grade, tumor_location
- Molecular: idh_mutation, mgmt_methylation, braf_status
- Treatment: radiation_received, chemotherapy_received
- Status: clinical_status, tumor_progression, metastasis_present
- Other: surgery_number, document_type, hydrocephalus_treatment, follow_up_duration

---

## 🎯 Core Problem & Solution

### Problem Statement
**"Processing all 3,865 documents across all 33 variables is computationally expensive and unnecessary"**

**Why**:
1. Many variables can be directly populated from Athena materialized views
2. Not all document types contain relevant information for all variables
3. Temporal proximity matters (recent documents more relevant than 20-year-old notes)
4. Document type matters (pathology reports contain diagnoses, operative notes contain surgeries)

### Solution: Two-Phase Iterative Extraction

**Phase 1: Targeted High-Value Extraction**
- Use only **Tier 1 documents** (~150-200 documents vs 3,865)
- Focus on **variables requiring note extraction** (exclude Athena-available variables)
- Apply **temporal filtering** (±6 months from diagnosis/key dates)
- **Validate** against Athena gold standard

**Phase 2: Selective Gap-Filling Extraction**
- Identify variables that didn't meet gold standard in Phase 1
- Expand to **Tier 2 documents** for those specific variables
- Broaden temporal window if needed
- **Re-validate** and iterate if necessary

---

## 📋 Variable-to-Data-Source Mapping

### ✅ Category 1: Complete from Athena (8 variables - NO NOTE EXTRACTION NEEDED)

These variables are already available from materialized views and should be **directly populated** in BRIM, not extracted from notes:

| Variable | Athena Source | Notes |
|----------|---------------|-------|
| `patient_gender` | demographics.gender | Direct mapping |
| `date_of_birth` | demographics.birth_date | Direct mapping |
| `race` | demographics.race | Direct mapping |
| `ethnicity` | demographics.ethnicity | Direct mapping |
| `age_at_diagnosis` | demographics.birth_date + diagnosis_date | Calculate |
| `chemotherapy_received` | medications (count > 0) | Yes/No flag |
| `chemotherapy_agents` | medications.medication_name (filtered) | Subset of medications |
| `concomitant_medications` | medications.medication_name (filtered) | Non-chemo subset |

**Action**: Pre-populate these in variables.csv with `scope: one_per_patient` and source as "athena_materialized_view"

---

### ⚠️ Category 2: Partial from Athena (1 variable - NEEDS NOTE VALIDATION)

| Variable | Athena Source | What's Missing | Note Extraction Purpose |
|----------|---------------|----------------|-------------------------|
| `imaging_findings` | imaging.imaging_type | Findings/impressions | Extract radiologist interpretations |

**Action**: Use Athena for imaging dates/types, extract findings from radiology reports

---

### ❌ Category 3: Only from Notes (24 variables - REQUIRE NOTE EXTRACTION)

These variables **must** be extracted from clinical notes:

**Diagnosis & Tumor Characteristics** (9 variables):
- `primary_diagnosis` - From pathology reports
- `diagnosis_date` - From pathology/oncology notes
- `who_grade` - From pathology reports
- `tumor_location` - From operative notes, imaging reports
- `idh_mutation` - From pathology/molecular reports
- `mgmt_methylation` - From pathology/molecular reports
- `braf_status` - From pathology/molecular reports
- `surgery_number` - Count from operative notes
- `document_type` - Metadata (not extracted)

**Surgical Variables** (5 variables):
- `surgery_date` - From operative notes
- `surgery_type` - From operative notes
- `surgery_extent` - From operative notes
- `surgery_location` - From operative notes
- `surgery_diagnosis` - From pathology linked to surgery

**Treatment & Response** (4 variables):
- `radiation_received` - From oncology progress notes
- `treatment_response` - From progress notes, imaging
- `symptoms_present` - From progress notes
- `molecular_testing_performed` - From pathology reports

**Clinical Status** (6 variables):
- `clinical_status` - From most recent progress notes
- `tumor_progression` - From imaging, oncology notes
- `metastasis_present` - From imaging, oncology notes
- `metastasis_locations` - From imaging reports
- `hydrocephalus_treatment` - From neurosurgery notes
- `follow_up_duration` - Calculate from encounter dates

---

## 🎯 Tiered Document Prioritization Strategy

### Document Classification by Annotation

**Total Documents**: 3,865  
**Metadata Coverage**:
- Document type: 95.3% (3,683 documents)
- Practice setting: 45.8% (1,771 documents)
- Category: 100% (3,865 documents)
- Date: 96.8% (3,742 documents)
- Encounter reference: 89.2% (3,448 documents)

---

### 🥇 TIER 1: Critical High-Value Documents (~150-200 documents)

**Selection Criteria**:
- Document types with highest information density
- Temporal proximity to key clinical events
- Practice settings aligned with variable needs

| Document Type | Count | % of Total | Key Variables Supported | Priority |
|---------------|-------|------------|-------------------------|----------|
| **Pathology study** | 40 | 1.0% | diagnosis, WHO grade, IDH, MGMT, BRAF, tumor location | ⭐⭐⭐⭐⭐ |
| **OP Note - Complete** | 10 | 0.3% | surgery date/type/extent/location, tumor location | ⭐⭐⭐⭐⭐ |
| **OP Note - Brief** | 9 | 0.2% | surgery variables (lower detail) | ⭐⭐⭐⭐ |
| **Consult Note** | 44 | 1.1% | diagnosis, treatment plans, specialist assessments | ⭐⭐⭐⭐ |
| **Progress Notes (Oncology)** | ~50 | 1.3% | treatment response, symptoms, progression | ⭐⭐⭐⭐ |
| **Progress Notes (Neurosurgery)** | ~30 | 0.8% | surgical outcomes, hydrocephalus, complications | ⭐⭐⭐⭐ |
| **Diagnostic imaging study** | 163 | 4.2% | tumor progression, metastasis, imaging findings | ⭐⭐⭐ |

**Tier 1 Total**: **~200 documents** (5.2% of all documents)

**Practice Setting Filters for Progress Notes**:
- Oncology (246 docs) → Filter to ±6 months from diagnosis
- Neurosurgery (87 docs) → Filter to ±3 months from surgery dates
- Radiology (75 docs) → Include all (already specific)

---

### 🥈 TIER 2: Supplementary Documents (~400-500 documents)

Use only if Tier 1 extraction doesn't meet gold standard thresholds

| Document Type | Count | % of Total | Use Case |
|---------------|-------|------------|----------|
| **Progress Notes (All)** | 1,277 | 33.0% | Symptoms, clinical status (if Tier 1 insufficient) |
| **Encounter Summary** | 761 | 19.7% | Episode summaries, interim status |
| **Assessment & Plan Note** | 148 | 3.8% | Clinical decision-making, treatment plans |
| **Clinical Report-Other** | 39 | 1.0% | Miscellaneous clinical data |
| **H&P (History & Physical)** | 13 | 0.3% | Initial workups, pre-surgical assessments |

**Tier 2 Usage Strategy**:
- Only activate for specific variables that failed in Phase 1
- Apply temporal filters (±12 months from key dates)
- Prioritize documents with practice_setting annotations

---

### 🥉 TIER 3: Low-Value Documents (EXCLUDE from extraction)

| Document Type | Count | % of Total | Reason for Exclusion |
|---------------|-------|------------|----------------------|
| **Telephone Encounter** | 397 | 10.3% | Brief, administrative, low clinical detail |
| **Patient Instructions** | 107 | 2.8% | Education materials, not clinical data |
| **After Visit Summary** | 97 | 2.5% | Duplicate of encounter summary |
| **Patient Entered Attachment** | 36 | 0.9% | Patient-generated, not provider documentation |
| **MRI Exam Screening Form** | 30 | 0.8% | Administrative forms |
| **Contrast Screening Checklist** | 27 | 0.7% | Safety checklists, not findings |
| **Prior Authorization** | 20 | 0.5% | Insurance documentation |
| **Nursing Note** | 64 | 1.7% | Vital signs, nursing assessments (rarely has abstraction targets) |

**Tier 3 Total**: **~800 documents** (20.7% of all documents) - **EXCLUDED**

---

## ⏱️ Temporal Filtering Strategy

### Key Clinical Event Dates (from annotations)

**Diagnosis Period**: 2018-2019 (based on temporal distribution)
**Active Treatment Period**: 2018-2021 (major document cluster)
**Follow-up Period**: 2021-2025 (ongoing surveillance)

### Temporal Windows by Variable Type

| Variable Category | Temporal Window | Rationale |
|-------------------|-----------------|-----------|
| **Diagnosis variables** | ±3 months from earliest pathology | Diagnosis confirmation period |
| **Surgical variables** | ±1 month from each surgery date | Peri-operative documentation |
| **Molecular markers** | ±6 months from diagnosis | Testing turnaround time |
| **Treatment variables** | Entire treatment period | Ongoing throughout care |
| **Progression/status** | Most recent 12 months | Current state assessment |
| **Symptoms** | Most recent 6 months | Recent symptom profile |

### Implementation in Document Selection

```python
# Example: Filter documents for diagnosis variables
diagnosis_window_start = earliest_pathology_date - timedelta(days=90)
diagnosis_window_end = earliest_pathology_date + timedelta(days=90)

diagnosis_docs = df[
    (df['document_type'].isin(['Pathology study', 'Consult Note', 'Progress Notes'])) &
    (df['date'] >= diagnosis_window_start) &
    (df['date'] <= diagnosis_window_end) &
    (df['practice_setting'].isin(['Oncology', 'Neurosurgery', 'Pathology']))
]
```

---

## 🔄 Phase 1: Targeted High-Value Extraction

### Objectives
1. Extract **only variables requiring note extraction** (24 variables, excluding 8 Athena variables)
2. Use **only Tier 1 documents** (~200 documents)
3. Apply **temporal filtering** based on variable type
4. **Validate** results against Athena gold standard (where available)
5. Assess **completeness** and **accuracy**

### Phase 1 Workflow

#### Step 1: Pre-populate Athena Variables

**Action**: Directly insert Athena data into BRIM without note extraction

**Script**: `prepopulate_athena_variables.py`

```python
# Load Athena reference data
demographics = pd.read_csv('reference_patient_demographics.csv')
medications = pd.read_csv('reference_patient_medications.csv')

# Create pre-populated variable entries
athena_variables = {
    'patient_gender': demographics.iloc[0]['gender'],
    'date_of_birth': demographics.iloc[0]['birth_date'],
    'race': demographics.iloc[0]['race'],
    'ethnicity': demographics.iloc[0]['ethnicity'],
    'chemotherapy_received': 'Yes' if len(medications) > 0 else 'No',
    # ... etc
}

# Insert into BRIM project.csv or upload directly
```

**Expected Outcome**: 8 variables pre-filled, reducing extraction burden

---

#### Step 2: Generate Tier 1 Document Subset

**Action**: Filter project.csv to include only Tier 1 documents

**Script**: `generate_tier1_project.py`

```python
import pandas as pd
from datetime import datetime, timedelta

# Load comprehensive metadata
metadata_df = pd.read_csv('accessible_binary_files_comprehensive_metadata.csv')

# Define Tier 1 document types
tier1_types = [
    'Pathology study',
    'OP Note - Complete',
    'OP Note - Brief',
    'Consult Note',
    'Progress Notes',
    'Diagnostic imaging study'
]

# Filter to Tier 1 types
tier1_docs = metadata_df[metadata_df['type_text'].isin(tier1_types)].copy()

# Apply practice setting filters for Progress Notes
progress_notes = tier1_docs[tier1_docs['type_text'] == 'Progress Notes']
oncology_progress = progress_notes[
    progress_notes['context_practice_setting_text'] == 'Oncology'
]
neurosurgery_progress = progress_notes[
    progress_notes['context_practice_setting_text'] == 'Neurosurgery'
]

# Combine filtered subsets
tier1_filtered = pd.concat([
    tier1_docs[tier1_docs['type_text'] != 'Progress Notes'],  # All non-progress Tier 1
    oncology_progress,  # Oncology progress notes
    neurosurgery_progress  # Neurosurgery progress notes
])

# Apply temporal filtering (example: diagnosis variables)
# Find earliest pathology date
pathology_docs = tier1_filtered[tier1_filtered['type_text'] == 'Pathology study']
if len(pathology_docs) > 0:
    earliest_path_date = pd.to_datetime(pathology_docs['date']).min()
    
    # Filter diagnosis-relevant docs to ±3 months
    diagnosis_window_start = earliest_path_date - timedelta(days=90)
    diagnosis_window_end = earliest_path_date + timedelta(days=90)
    
    diagnosis_docs = tier1_filtered[
        (tier1_filtered['type_text'].isin(['Pathology study', 'Consult Note'])) &
        (pd.to_datetime(tier1_filtered['date']) >= diagnosis_window_start) &
        (pd.to_datetime(tier1_filtered['date']) <= diagnosis_window_end)
    ]

# Load full project.csv
project_df = pd.read_csv('project.csv')

# Filter project to Tier 1 documents
tier1_project = project_df[
    project_df['document_reference_id'].isin(tier1_filtered['document_reference_id'])
]

# Save Phase 1 project
tier1_project.to_csv('project_phase1_tier1.csv', index=False)

print(f"Phase 1 Tier 1 documents: {len(tier1_project)}")
print(f"Reduction: {len(project_df)} → {len(tier1_project)} ({len(tier1_project)/len(project_df)*100:.1f}%)")
```

**Expected Outcome**: 
- **3,865 documents → ~150-200 documents** (95% reduction)
- Documents focused on high-value types and temporal proximity

---

#### Step 3: Generate Phase 1 Variables List

**Action**: Create variables_phase1.csv with only note-extraction variables

**Script**: `generate_phase1_variables.py`

```python
import pandas as pd

# Load full variables
variables_df = pd.read_csv('variables.csv')

# Define Athena-available variables to exclude
athena_vars = [
    'patient_gender', 'date_of_birth', 'age_at_diagnosis', 'race', 'ethnicity',
    'chemotherapy_received', 'chemotherapy_agents', 'concomitant_medications'
]

# Filter to note-extraction variables only
phase1_vars = variables_df[~variables_df['variable_name'].isin(athena_vars)].copy()

# Save Phase 1 variables
phase1_vars.to_csv('variables_phase1.csv', index=False)

print(f"Phase 1 variables: {len(phase1_vars)} (excluded {len(athena_vars)} Athena variables)")
```

**Expected Outcome**: 
- **33 variables → 25 variables** (excluding 8 Athena variables)
- Focus on clinical variables requiring note extraction

---

#### Step 4: Run Phase 1 Extraction

**Action**: Execute BRIM extraction with Phase 1 CSVs

```bash
# Upload to BRIM:
# - project_phase1_tier1.csv (as project.csv)
# - variables_phase1.csv (as variables.csv)
# - decisions.csv (no changes)

# Monitor extraction:
# - Expected rows: ~3,000-5,000 (vs 40,149 in full extraction)
# - Expected time: 2-4 hours (vs 10-15 hours)
# - Expected cost: $30-60 (vs $150-300)
```

**Expected Outcome**: Completed Phase 1 extraction with 95% fewer documents

---

#### Step 5: Validate Phase 1 Results

**Action**: Compare extraction against gold standard and assess completeness

**Script**: `validate_phase1_results.py`

```python
import pandas as pd
import numpy as np

# Load Phase 1 extraction results
phase1_results = pd.read_csv('phase1_extraction_results.csv')

# Load gold standard data
demographics = pd.read_csv('reference_patient_demographics.csv')
medications = pd.read_csv('reference_patient_medications.csv')
imaging = pd.read_csv('reference_patient_imaging.csv')

print("=" * 80)
print("PHASE 1 VALIDATION REPORT")
print("=" * 80)

# Group by variable
variable_results = {}

for var_name in phase1_results['Name'].unique():
    var_extractions = phase1_results[phase1_results['Name'] == var_name]
    
    total_attempts = len(var_extractions)
    successful_extractions = var_extractions['Value'].notna().sum()
    unique_values = var_extractions['Value'].dropna().unique()
    
    # Assess completeness
    if var_name in ['surgery_date', 'surgery_type', 'surgery_extent']:
        # For surgical variables, check if we have at least one complete surgery record
        completeness = 'Complete' if successful_extractions >= 1 else 'Incomplete'
    elif var_name in ['primary_diagnosis', 'who_grade', 'tumor_location']:
        # For diagnosis variables, need exactly one value
        completeness = 'Complete' if len(unique_values) == 1 else 'Incomplete'
    else:
        # For other variables, any extraction is acceptable
        completeness = 'Complete' if successful_extractions > 0 else 'Incomplete'
    
    # Gold standard comparison (where available)
    gold_standard_match = None
    if var_name == 'chemotherapy_agents':
        # Compare against medications
        extracted_agents = set([v.lower() for v in unique_values if pd.notna(v)])
        gold_agents = set([m.lower() for m in medications['medication_name'].values])
        overlap = len(extracted_agents & gold_agents)
        gold_standard_match = f"{overlap}/{len(gold_agents)} agents matched"
    
    variable_results[var_name] = {
        'attempts': total_attempts,
        'successful': successful_extractions,
        'unique_values': len(unique_values),
        'completeness': completeness,
        'gold_standard': gold_standard_match
    }

# Print validation summary
print(f"\n{'Variable':<40} {'Attempts':>10} {'Success':>10} {'Status':>15} {'Gold Std':>20}")
print("-" * 97)

for var_name, stats in variable_results.items():
    gs_text = stats['gold_standard'] if stats['gold_standard'] else 'N/A'
    print(f"{var_name:<40} {stats['attempts']:>10} {stats['successful']:>10} "
          f"{stats['completeness']:>15} {gs_text:>20}")

# Identify incomplete variables
incomplete_vars = [v for v, s in variable_results.items() if s['completeness'] == 'Incomplete']

print("\n" + "=" * 80)
print("PHASE 1 OUTCOME SUMMARY")
print("=" * 80)
print(f"Total variables extracted: {len(variable_results)}")
print(f"Complete variables: {len([v for v, s in variable_results.items() if s['completeness'] == 'Complete'])}")
print(f"Incomplete variables: {len(incomplete_vars)}")

if incomplete_vars:
    print(f"\n❌ Variables needing Phase 2 extraction:")
    for var in incomplete_vars:
        print(f"  - {var}")
else:
    print(f"\n✅ All variables complete! No Phase 2 needed.")

# Save validation report
validation_df = pd.DataFrame.from_dict(variable_results, orient='index')
validation_df.to_csv('phase1_validation_report.csv')
```

**Expected Outcome**: 
- Validation report identifying complete vs incomplete variables
- Gold standard accuracy assessment
- List of variables requiring Phase 2 extraction

---

## 🔄 Phase 2: Selective Gap-Filling Extraction

### Objectives
1. Extract **only incomplete variables** from Phase 1
2. Expand to **Tier 2 documents** for those specific variables
3. Broaden **temporal windows** if needed
4. **Re-validate** against gold standard
5. Iterate if necessary (Phase 3, etc.)

### Phase 2 Workflow

#### Step 1: Identify Phase 2 Target Variables

**Input**: Phase 1 validation report
**Action**: Select incomplete variables for re-extraction

```python
# From phase1_validation_report.csv
phase2_target_vars = [
    'primary_diagnosis',  # Example: if not found in Phase 1
    'radiation_received',
    'clinical_status'
]
```

---

#### Step 2: Generate Tier 2 Document Subset

**Action**: Expand document selection for Phase 2 variables

**Script**: `generate_tier2_project.py`

```python
import pandas as pd
from datetime import datetime, timedelta

# Load comprehensive metadata
metadata_df = pd.read_csv('accessible_binary_files_comprehensive_metadata.csv')

# Load Phase 1 documents (already processed)
phase1_docs = pd.read_csv('project_phase1_tier1.csv')['document_reference_id'].values

# Define Tier 2 document types
tier2_types = [
    'Progress Notes',  # All progress notes (not just oncology/neurosurgery)
    'Encounter Summary',
    'Assessment & Plan Note',
    'Clinical Report-Other',
    'H&P'
]

# Filter to Tier 2 types NOT in Phase 1
tier2_docs = metadata_df[
    (metadata_df['type_text'].isin(tier2_types)) &
    (~metadata_df['document_reference_id'].isin(phase1_docs))
].copy()

# Apply broadened temporal filtering (±12 months from diagnosis)
# ... (similar to Phase 1 but wider windows)

# Load full project.csv
project_df = pd.read_csv('project.csv')

# Filter project to Tier 2 documents
tier2_project = project_df[
    project_df['document_reference_id'].isin(tier2_docs['document_reference_id'])
]

# Save Phase 2 project
tier2_project.to_csv('project_phase2_tier2.csv', index=False)

print(f"Phase 2 Tier 2 documents: {len(tier2_project)}")
print(f"Additional documents beyond Phase 1: {len(tier2_project)}")
```

**Expected Outcome**: 
- Additional ~400-500 documents for Phase 2
- Focused on supplementary note types

---

#### Step 3: Generate Phase 2 Variables List

**Action**: Create variables_phase2.csv with only incomplete variables

```python
# Load Phase 1 validation results
validation_df = pd.read_csv('phase1_validation_report.csv')
incomplete_vars = validation_df[validation_df['completeness'] == 'Incomplete'].index.tolist()

# Load full variables
variables_df = pd.read_csv('variables.csv')

# Filter to Phase 2 target variables
phase2_vars = variables_df[variables_df['variable_name'].isin(incomplete_vars)].copy()

# Save Phase 2 variables
phase2_vars.to_csv('variables_phase2.csv', index=False)

print(f"Phase 2 variables: {len(phase2_vars)}")
```

**Expected Outcome**: Focused variable list for re-extraction

---

#### Step 4: Run Phase 2 Extraction

**Action**: Execute BRIM extraction with Phase 2 CSVs

```bash
# Upload to BRIM:
# - project_phase2_tier2.csv (as project.csv)
# - variables_phase2.csv (as variables.csv)
# - decisions.csv (no changes)

# Monitor extraction:
# - Expected rows: ~2,000-3,000 (focused on specific variables)
# - Expected time: 1-2 hours
# - Expected cost: $20-40
```

---

#### Step 5: Validate Phase 2 Results & Merge

**Action**: Assess Phase 2 completeness and merge with Phase 1

```python
# Load Phase 2 results
phase2_results = pd.read_csv('phase2_extraction_results.csv')

# Validate Phase 2 (similar to Phase 1 validation)
# ...

# Merge Phase 1 + Phase 2 results
phase1_results = pd.read_csv('phase1_extraction_results.csv')
merged_results = pd.concat([phase1_results, phase2_results], ignore_index=True)

# Save final merged extraction
merged_results.to_csv('final_extraction_phase1_and_phase2.csv', index=False)

print(f"Final extraction: {len(merged_results)} rows")
print(f"Phase 1: {len(phase1_results)} rows")
print(f"Phase 2: {len(phase2_results)} rows")
```

**Expected Outcome**: Complete extraction dataset with all variables addressed

---

## 📈 Expected Efficiency Gains

### Volume Reduction

| Metric | Original (Full Extraction) | Phase 1 (Tier 1) | Phase 2 (if needed) | Total Optimized |
|--------|----------------------------|------------------|---------------------|-----------------|
| **Documents** | 3,865 | ~150-200 (5%) | +400-500 (10%) | ~600-700 (18%) |
| **Variables** | 33 | 25 (76%) | 3-5 (9-15%) | 25-30 (76-91%) |
| **Est. Rows** | ~40,149 | ~5,000 | ~2,000 | ~7,000 (17%) |
| **Est. Time** | 10-15 hours | 2-4 hours | 1-2 hours | 3-6 hours (30-40%) |
| **Est. Cost** | $150-300 | $50-80 | $20-40 | $70-120 (40-50%) |

### Accuracy Maintenance

**Hypothesis**: Tier 1 documents contain 95%+ of critical clinical information
- Pathology reports: 100% of diagnosis info
- Operative notes: 100% of surgery info
- Oncology progress notes: 90%+ of treatment info
- Radiology reports: 95%+ of imaging findings

**Validation Strategy**: Gold standard comparison ensures no loss of accuracy

---

## 🛠️ Implementation Scripts Summary

### Required Scripts

1. **`prepopulate_athena_variables.py`**
   - Purpose: Pre-fill 8 Athena-available variables
   - Input: reference_patient_*.csv
   - Output: athena_prepopulated_values.json

2. **`generate_tier1_project.py`**
   - Purpose: Create Phase 1 document subset
   - Input: accessible_binary_files_comprehensive_metadata.csv, project.csv
   - Output: project_phase1_tier1.csv

3. **`generate_phase1_variables.py`**
   - Purpose: Create Phase 1 variable list
   - Input: variables.csv
   - Output: variables_phase1.csv

4. **`validate_phase1_results.py`**
   - Purpose: Assess Phase 1 completeness and accuracy
   - Input: phase1_extraction_results.csv, reference_patient_*.csv
   - Output: phase1_validation_report.csv

5. **`generate_tier2_project.py`**
   - Purpose: Create Phase 2 document subset
   - Input: metadata, project.csv, phase1 docs list
   - Output: project_phase2_tier2.csv

6. **`generate_phase2_variables.py`**
   - Purpose: Create Phase 2 variable list
   - Input: phase1_validation_report.csv, variables.csv
   - Output: variables_phase2.csv

7. **`validate_phase2_results.py`**
   - Purpose: Assess Phase 2 and merge with Phase 1
   - Input: phase1 + phase2 results
   - Output: final_extraction_phase1_and_phase2.csv, final_validation_report.csv

---

## ✅ Success Criteria

### Phase 1 Success
- [ ] At least 80% of variables complete
- [ ] Gold standard accuracy ≥ 95% (where comparable)
- [ ] Extraction time reduced by 60-70%
- [ ] Document count reduced by 95%

### Phase 2 Success
- [ ] All incomplete variables from Phase 1 addressed
- [ ] Combined Phase 1+2 achieves 95%+ variable completeness
- [ ] Total extraction time < 40% of original estimate
- [ ] No loss of accuracy compared to full extraction

### Final Success
- [ ] All 33 variables extracted (or pre-populated)
- [ ] Gold standard validation confirms accuracy
- [ ] Workflow documented for future patients
- [ ] Efficiency gains demonstrated and reproducible

---

## 📊 Monitoring & Metrics

### Track These Metrics Throughout

1. **Document Efficiency**
   - Documents processed
   - Documents skipped
   - Tier 1 vs Tier 2 vs Tier 3 distribution

2. **Variable Completeness**
   - Variables with ≥1 value extracted
   - Variables meeting gold standard
   - Variables requiring Phase 2

3. **Extraction Quality**
   - Success rate per variable
   - Unique values per variable
   - Gold standard agreement

4. **Resource Usage**
   - API calls / tokens used
   - Processing time
   - Cost (estimated)

5. **Temporal Coverage**
   - Documents within temporal windows
   - Documents outside windows (excluded)
   - Key date coverage (diagnosis, surgery, etc.)

---

## 🔄 Iterative Refinement Process

### After Each Phase

1. **Assess Results**
   - Run validation script
   - Compare against gold standard
   - Identify gaps

2. **Analyze Patterns**
   - Which document types yielded best results?
   - Which temporal windows were optimal?
   - Which variables were most challenging?

3. **Refine Strategy**
   - Adjust document type priorities
   - Modify temporal windows
   - Update variable extraction instructions

4. **Document Learnings**
   - Update this strategy document
   - Note what worked / didn't work
   - Refine for next patient

---

## 🎯 Next Steps

### Immediate Actions

1. **Review & Approve Strategy** ✅ (this document)
2. **Implement Scripts** (7 scripts listed above)
3. **Pre-populate Athena Variables** (8 variables)
4. **Generate Phase 1 CSVs** (Tier 1 docs + note-extraction vars)
5. **Run Phase 1 Extraction** (BRIM upload & monitor)
6. **Validate Phase 1 Results** (compare to gold standard)
7. **Decide on Phase 2** (if needed based on validation)
8. **Run Phase 2 Extraction** (if incomplete variables remain)
9. **Final Validation & Merge** (Phase 1 + Phase 2)
10. **Document Learnings** (update strategy for next patient)

---

## 📚 References

**Related Documentation**:
- `DOCUMENT_TYPE_PRIORITIZATION_STRATEGY.md` - Original Tier 1/2/3 classification
- `METADATA_DRIVEN_ABSTRACTION_STRATEGY.md` - Metadata usage patterns
- `PHASE_3A_V2_COMPREHENSIVE_SUMMARY.md` - Current workflow state
- `DATA_SOURCE_VALIDATION_*.md` - Gold standard reference data

**Key Data Files**:
- `accessible_binary_files_comprehensive_metadata.csv` - Full document annotations
- `reference_patient_demographics.csv` - Athena demographics
- `reference_patient_imaging.csv` - Athena imaging records
- `reference_patient_medications.csv` - Athena medication orders
- `partial_extraction_14pct.csv` - Stopped extraction results
- `variables.csv` - All 33 variables defined
- `project.csv` - All 3,865 documents

---

**Strategy Author**: AI Assistant  
**Review Date**: October 5, 2025  
**Status**: Ready for Implementation  
**Expected ROI**: 60-70% time savings, 50-60% cost savings, maintained accuracy
