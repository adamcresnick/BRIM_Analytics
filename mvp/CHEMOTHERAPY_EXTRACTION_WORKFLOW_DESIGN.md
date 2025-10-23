# Chemotherapy Extraction Workflow Design

## Overview
This workflow extracts comprehensive chemotherapy treatment data using a multi-source approach that combines structured FHIR data from v_chemo_medications with binary file validation (progress notes, infusion records, treatment plans) to capture the complete picture of chemotherapy administration.

## Data Sources

### 1. Primary Structured Data: v_chemo_medications
**Source**: Athena view querying FHIR medication_request + comprehensive chemotherapy reference (3,064 drugs)

**Key Features**:
- Persistent table-based data (not local file filtering)
- ~89% date coverage using dosage_instruction_timing_repeat_bounds_period
- Both ingredient-level and product-level RxNorm matching
- Includes medication route, dosage, method, site
- Links to care plans via based_on_references

**Columns Used**:
- `patient_fhir_id` - Patient identifier
- `medication_request_fhir_id` - Unique medication order ID
- `chemo_preferred_name` - Standardized drug name from reference
- `chemo_rxnorm_ingredient` - RxNorm ingredient code
- `chemo_approval_status` - FDA approval status
- `medication_start_date` / `medication_stop_date` - Treatment period (TIMESTAMP)
- `medication_route` - Administration route (IV, PO, etc.)
- `medication_dosage_instructions` - Full dosage text
- `medication_reason_codes` - Indication/diagnosis
- `care_plan_references` - Links to treatment protocols

### 2. Concomitant Medications: v_concomitant_medications
**Source**: Temporal overlap analysis between chemotherapy and ALL other medications

**Key Features**:
- 192M+ records showing medication interactions
- Temporal overlap types: during_chemo, started_during_chemo, stopped_during_chemo, spans_chemo
- Categorizes concomitant meds: antiemetic, corticosteroid, growth_factor, anticonvulsant, etc.
- Date quality indicators (high/medium/low)

**Use Case**: Validate actual chemotherapy administration by presence of expected supportive care medications

### 3. Binary Files for Validation

#### A. Progress Notes
**Purpose**: Capture therapy changes, dose modifications, toxicity-driven adjustments

**Selection Criteria**:
- **Timing Window**: ±14 days from medication_start_date (expanded from ±7 to capture delayed documentation)
- **Additional Window**: ±7 days from medication_stop_date (to capture discontinuation reasons)
- **Types**: Progress Note, Attending MD Progress Note, Oncology Consult Note

**Rationale**: Clinicians often document chemotherapy changes, delays, or modifications in progress notes that may not be reflected in medication_request data

#### B. Infusion Records
**Purpose**: Validate actual drug administration vs ordered medications

**Selection Criteria**:
- **Timing Window**: Exact match to medication_start_date ±3 days
- **Types**:
  - Infusion Note
  - Nursing Flowsheet
  - Medication Administration Record

**Rationale**: medication_request represents ORDERS, but infusion records show what was ACTUALLY administered

#### C. Treatment Plans / Protocols
**Purpose**: Identify clinical trial enrollment, protocol-based treatment, regimen details

**Selection Criteria**:
- **Timing Window**: Within 30 days BEFORE first medication_start_date
- **Types**:
  - Treatment Plan
  - Chemotherapy Order Form
  - Clinical Trial Consent
  - Protocol Documentation

**Rationale**: Clinical trial protocols and treatment plans document intended regimens that may differ from individual medication orders

#### D. Lab Results (Ancillary Validation)
**Purpose**: Corroborate chemotherapy timing via myelosuppression markers

**Selection Criteria**:
- **Timing Window**: medication_start_date to medication_stop_date + 30 days
- **Lab Types**:
  - Complete Blood Count (CBC)
  - Absolute Neutrophil Count (ANC)
  - Platelet count

**Rationale**: Chemotherapy causes predictable lab changes; absence of expected myelosuppression may indicate medication_request data doesn't reflect actual administration

## Comprehensive JSON Structure

```json
{
  "patient_fhir_id": "Patient/xxx",
  "extraction_timestamp": "2025-01-22T12:00:00Z",

  "chemotherapy_courses": [
    {
      "course_id": 1,
      "course_start_date": "2024-01-15",
      "course_end_date": "2024-06-30",
      "course_duration_days": 167,

      "medications": [
        {
          "medication_request_fhir_id": "MedicationRequest/xxx",
          "drug_name": "temozolomide",
          "rxnorm_code": "38461",
          "approval_status": "FDA_approved",

          "start_date": "2024-01-15",
          "start_date_source": "infusion_record",
          "start_date_medication_request": "2024-01-14",

          "stop_date": "2024-06-30",
          "stop_date_source": "medication_request",

          "route": "Oral",
          "dosage_instructions": "150 mg/m2 PO daily x 5 days, repeat q28 days",
          "indication": "Glioblastoma multiforme",
          "care_plan_reference": "CarePlan/protocol-xyz",

          "data_source": "v_chemo_medications",
          "binary_file_confirmation": {
            "infusion_records": 6,
            "progress_notes_mentions": 12,
            "confirmed": true
          }
        }
      ],

      "concomitant_medications": [
        {
          "drug_name": "ondansetron",
          "category": "antiemetic",
          "overlap_type": "during_chemo",
          "start_date": "2024-01-15",
          "stop_date": "2024-06-30"
        }
      ],

      "clinical_trial_info": {
        "protocol_status": "like_protocol",
        "protocol_number": "ACNS0334",
        "protocol_number_cbtn_match": "ACNS0334",
        "treatment_arm": "Arm A - TMZ + RT",
        "source": "progress_note_mention",
        "source_binary_id": "DocumentReference/xyz",
        "confidence": "high"
      },

      "regimen_match": {
        "match_type": "like_regimen",
        "regimen_name": "TMZ-RT (Stupp Protocol)",
        "regimen_id": "regimen_12",
        "match_reason": "drugs match exactly, schedule modified (21-day vs 28-day cycles)",
        "source": "v_chemotherapy_regimens"
      },

      "validation_sources": {
        "infusion_records": 6,
        "progress_notes": 12,
        "treatment_plans": 1,
        "lab_confirmations": 18
      },

      "therapy_modifications": [
        {
          "date": "2024-03-10",
          "type": "dose_reduction",
          "reason": "Grade 3 thrombocytopenia",
          "new_dose": "100 mg/m2",
          "source": "progress_note_binary_id_xxx"
        }
      ]
    }
  ],

  "cbtn_abstraction_targets": {
    "protocol_number": "ACNS0334",
    "chemotherapy_agents": ["temozolomide"],
    "start_date_chemotherapy": "2024-01-15",
    "stop_date_chemotherapy": "2024-06-30",
    "chemotherapy_type": "Treatment follows a protocol and subject is enrolled on a protocol",
    "medication_reconciliation_date": "2024-01-15",
    "drug_1_name": "temozolomide",
    "drug_1_dose_route_frequency": "150 mg/m2 PO daily x 5 days, q28 days"
  }
}
```

## Workflow Implementation Steps

### Phase 1: Data Assembly (Agent 1)

1. **Query v_chemo_medications** for patient
   - Extract all chemotherapy orders with dates, drugs, routes, dosages
   - Group into logical "courses" based on temporal proximity and regimen similarity

2. **Query v_concomitant_medications** for validation
   - Identify supportive care meds that corroborate chemotherapy administration
   - Flag missing expected concomitants (e.g., no antiemetics during highly emetogenic chemo)

3. **Match to defined regimens** (v_chemotherapy_regimens)
   - Compare drug combinations + timing to standard regimens
   - Assign regimen_name if match found

4. **Select relevant binary files**:
   - Progress notes: ±14 days from med start, ±7 days from med stop
   - Infusion records: ±3 days from med start
   - Treatment plans: 30 days before first medication
   - Labs: During treatment + 30 days after

5. **Assemble comprehensive JSON**
   - Structure all data logically by course/cycle
   - Include validation source counts
   - Pre-populate CBTN target fields from structured data

### Phase 2: Binary Validation & Abstraction (Agent 2)

1. **Receive comprehensive JSON** + selected binary files

2. **Validate structured data against binaries**:
   - Confirm medication_request drugs match infusion record drugs
   - Verify dates align between orders and administration
   - Identify discrepancies (ordered but not given, given but not ordered)

3. **Extract binary-only information**:
   - Clinical trial protocol details (protocol number, treatment arm)
   - Dose modifications and reasons
   - Therapy delays or interruptions
   - Toxicities leading to changes
   - Patient-reported outcomes affecting treatment

4. **Abstract CBTN fields**:
   - Protocol Number and Treatment Arm → from treatment plans/consent forms
   - Description of Chemotherapy Treatment → comprehensive narrative from progress notes
   - Chemotherapy Type → determine if protocol-based, SOC, or investigational
   - Drug names + doses + routes + frequencies → validate/enhance from infusion records

5. **Return enhanced JSON** with:
   - Validated medication list
   - Clinical trial details
   - Therapy modifications timeline
   - Populated CBTN data dictionary fields

### Phase 3: Quality Assurance

1. **Consistency checks**:
   - Do infusion records match medication_request data?
   - Are expected supportive care meds present?
   - Do lab timelines align with myelosuppressive chemotherapy?

2. **Completeness checks**:
   - All CBTN required fields populated?
   - All treatment courses have validation sources?
   - Clinical trial enrollment status resolved?

3. **Confidence scoring**:
   - High: Structured data + infusion records + progress notes all agree
   - Medium: Structured data + one validation source
   - Low: Structured data only, no binary validation

## Binary File Type Priorities

### Critical (Always Include):
1. **Progress Notes** - Capture therapy changes, clinician decision-making
2. **Infusion Records** - Validate actual administration vs orders
3. **Treatment Plans** - Identify protocols and regimens

### Important (Include if Available):
4. **Lab Results** - Corroborate chemotherapy via myelosuppression
5. **Clinical Trial Documentation** - Protocol numbers, treatment arms
6. **Chemotherapy Order Forms** - Detailed dosing calculations

### Supplementary:
7. **Nursing Flowsheets** - Administration times, pre-medications
8. **Pharmacy Records** - Drug preparation and dispensing
9. **Patient Education Materials** - Confirm drug names and regimens

## Timing Adjustments for Progress Note Selection

### Standard Window:
- **Start-focused**: medication_start_date ± 14 days
- **Stop-focused**: medication_stop_date ± 7 days

### Expanded Window for Therapy Changes:
When detecting potential therapy modifications (based on gaps in medication timeline or changes in drugs), expand window to:
- ±30 days from gap/change point

### Rationale:
- Clinicians may document planned changes before they occur
- Treatment delays may be documented days before missed doses
- Toxicity-driven modifications may be discussed in notes before formal orders change

## CBTN Data Dictionary Field Mapping

### Direct Extraction from v_chemo_medications:
- `Chemotherapy?` → YES (if any records exist)
- `Start date of chemotherapy?` → MIN(medication_start_date)
- `Stop date of chemotherapy?` → MAX(medication_stop_date)
- `Chemotherapy Agent 1-5` → chemo_preferred_name (top 5 by duration)
- `Drug 1-5 name` → chemo_preferred_name
- `Drug 1-5 Dose, Route and Frequency` → medication_dosage_instructions

### Binary-Required Extraction:
- `Protocol Number and Treatment Arm` → Treatment plans, consent forms
- `Description of Chemotherapy Treatment` → Progress notes narrative
- `Chemotherapy Type` → Determine from treatment plans:
  - "Treatment follows a protocol and subject is enrolled" → if clinical trial docs present
  - "Treatment follows a protocol but subject is not enrolled" → if standard protocol used
  - "Treatment follows standard of care" → otherwise

### Medication Reconciliation Fields:
- `Date of medication reconciliation` → medication_start_date of first course
- `Medication 1-10` → All current medications from v_concomitant_medications
- `Medication 1-10 Schedule Category` → Infer from dosage_instructions (scheduled vs PRN)

## Regimen Matching Strategy

1. **Check v_chemotherapy_regimens** for exact match:
   - Compare drug combination (all drugs in course)
   - Verify timing pattern matches regimen schedule

2. **Fallback to partial match**:
   - Match on primary drug + 1-2 supporting drugs
   - Flag as "probable regimen X" with lower confidence

3. **Use protocol information**:
   - If protocol number extracted from binaries, lookup known protocol→regimen mappings

4. **Document novel combinations**:
   - If no regimen match, flag as "investigational" or "off-protocol"
   - Extract detailed description from progress notes

## Implementation Decisions (CONFIRMED)

1. **Timing sensitivity**: ✅ Use infusion/administration dates when available, fall back to medication_request dates
   - Reflects actual administration reality
   - JSON will include both dates with source annotation

2. **Missing data handling**: ✅ Include all chemotherapy courses, clearly identify data source and binary confirmation status
   - All courses included in output
   - JSON includes `data_source` and `binary_file_confirmation` fields
   - Enables downstream quality filtering

3. **Clinical trial enrollment**: ✅ Accept documentation in notes, care plans, or other documents
   - Mark as "protocol" or "like protocol" based on documentation strength
   - Match to CBTN data dictionary protocol choices when possible
   - Use confidence levels: "confirmed_enrollment" vs "likely_protocol_based"

4. **Regimen assignment**: ✅ Use "like regimen" nomenclature when drugs match but timing differs
   - Analogous to "like protocol" approach
   - JSON includes `regimen_match_type`: "exact", "like_regimen", "partial", "novel"
   - Preserves clinical insight about modified schedules

5. **Multiple courses**: ✅ Separate course_ids unless documented as defined sequential regimen
   - Default: separate courses if >90 day gap OR different drug combinations
   - Exception: if documentation explicitly describes sequential protocol (e.g., "per protocol, moving to maintenance phase")
   - JSON includes `sequential_regimen_flag` if applicable

## Implementation Priority

1. ✅ Deploy v_chemo_medications (COMPLETE)
2. ✅ Deploy v_concomitant_medications (COMPLETE)
3. Design and implement JSON assembly script (Phase 1 Agent)
4. Implement binary file selection logic with expanded timing windows
5. Enhance Agent 2 prompt to handle comprehensive JSON + multiple binary types
6. Test on pilot patients with known clinical trial enrollment
7. Validate against ground truth CBTN abstracted data

## Success Metrics

- **Coverage**: % of chemotherapy courses with at least one validation source
- **Accuracy**: Agreement between structured data and binary-validated data
- **Completeness**: % of CBTN chemotherapy fields successfully populated
- **Clinical trial detection**: % of known trial participants correctly identified
- **Regimen identification**: % of chemotherapy courses matched to standard regimens
