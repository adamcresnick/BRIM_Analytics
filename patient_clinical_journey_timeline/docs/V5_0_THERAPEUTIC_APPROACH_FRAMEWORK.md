# V5.0: Therapeutic Approach Framework - Design Document

**Version:** 5.0
**Date:** November 8, 2025
**Author:** Claude (Orchestrator Agent)
**Status:** Design Phase

---

## Executive Summary

V5.0 introduces a **hierarchical therapeutic approach framework** that groups individual medication administrations into clinically meaningful treatment paradigms. This enables cross-patient comparison, treatment outcome analysis, and protocol adherence assessment.

**Key Principle:** Preserve all granular detail (individual administrations) as supporting evidence underneath higher-level clinical abstractions (treatment lines, regimens, therapeutic approaches).

---

## Problem Statement

### Current State (V4.8)

The current timeline represents **medication administration events**, not **treatment paradigms**:

```json
{
  "timeline_events": [
    {"event_type": "chemotherapy_start", "drug": "temozolomide", "date": "2017-10-05"},
    {"event_type": "chemotherapy_start", "drug": "temozolomide", "date": "2017-10-05"},
    {"event_type": "chemotherapy_start", "drug": "temozolomide", "date": "2017-10-05"},
    {"event_type": "chemotherapy_start", "drug": "temozolomide", "date": "2017-10-19"},
    ...
  ]
}
```

**Problems:**
1. **No concept of "treatment line"** - Cannot distinguish first-line from salvage therapy
2. **Duplicate episodes** - Same drug/date repeated due to view design
3. **Cannot answer clinical questions:**
   - "What was the first-line regimen?" → Unknown
   - "How long was the patient on standard-of-care before progression?" → Cannot calculate
   - "Does this patient match COG ACNS0126 protocol?" → No way to assess
4. **Cannot compare across patients** - No standardized treatment paradigm classification

### What Clinical Coordinators Need

To support comparative effectiveness research, clinical trial matching, and outcomes analysis:

```
QUESTION: "Show me all IDH-mutant astrocytoma patients who received Stupp Protocol"

CURRENT V4.8: Cannot answer (no regimen grouping)

V5.0 ANSWER:
  - Patient A: Stupp Protocol, 6 cycles completed, PFS 8 months
  - Patient B: Stupp Protocol, 3 cycles completed, discontinued due to toxicity
  - Patient C: Modified Stupp (no RT), 6 cycles completed, PFS 12 months
```

---

## Design: Hierarchical Therapeutic Approach Model

### Conceptual Hierarchy

```
THERAPEUTIC APPROACH
├── Treatment Intent (curative | palliative | experimental | bridge | hospice)
├── Treatment Lines (numbered, with reason for change)
│   ├── LINE 1: Standard of Care
│   │   ├── Regimen (named protocol or drug combination)
│   │   │   ├── Regimen Components (surgery, chemo, radiation)
│   │   │   │   ├── Treatment Phases (concurrent, adjuvant, maintenance)
│   │   │   │   │   ├── Treatment Cycles
│   │   │   │   │   │   ├── Individual Administrations ← V4.8 granular data
│   │   ├── Response Assessment (imaging, clinical)
│   │   └── Reason for Change (progression, toxicity, completion)
│   ├── LINE 2: Salvage Therapy
│   └── LINE 3: Experimental Therapy
└── Clinical Endpoints
    ├── Time to Progression (per line)
    ├── Overall Survival (from diagnosis)
    └── Quality of Life metrics
```

### JSON Schema Design

#### Top-Level Artifact Structure

```json
{
  "patient_id": "eQSB0y3q...",
  "abstraction_timestamp": "2025-11-08T16:18:00Z",

  "who_2021_classification": { ... },  // Unchanged from V4.8
  "patient_demographics": { ... },     // Unchanged from V4.8

  // NEW in V5.0: High-level therapeutic approach
  "therapeutic_approach": {
    "diagnosis_date": "2017-09-27",  // Anchor date (D0)
    "treatment_intent": "curative",
    "lines_of_therapy": [
      { ... },  // Detailed below
    ],
    "clinical_endpoints": { ... }
  },

  // PRESERVED from V4.8: Granular timeline events
  "timeline_events": [
    { ... },  // All individual administrations preserved
  ],

  // PRESERVED from V4.8
  "extraction_gaps": [ ... ],
  "binary_extractions": [ ... ],
  "protocol_validations": [ ... ]
}
```

#### Treatment Line Schema

```json
{
  "line_number": 1,
  "line_name": "First-line Standard of Care (Stupp Protocol)",
  "treatment_intent": "curative",

  // Temporal anchoring
  "start_date": "2017-09-27",
  "end_date": "2018-04-05",
  "days_from_diagnosis": 0,
  "duration_days": 191,
  "status": "completed",

  // Regimen classification
  "regimen": {
    "regimen_name": "Modified Stupp Protocol (TMZ + RT)",
    "protocol_reference": "Stupp et al. NEJM 2005, adapted for pediatric",
    "match_confidence": "high",
    "deviations_from_protocol": [
      {
        "deviation": "Radiation dose 54 Gy instead of 60 Gy",
        "rationale": "Pediatric age consideration",
        "clinical_significance": "standard_variation"
      }
    ],

    // Regimen components with granular data
    "components": [
      {
        "component_id": "stupp_surgery",
        "component_type": "surgery",
        "timing": "upfront",
        "procedure_name": "Craniotomy with tumor resection",
        "date": "2017-09-27",
        "institution": "Children's Hospital of Philadelphia",
        "extent_of_resection": "partial",

        // Link to granular timeline events
        "timeline_event_refs": ["surgery_event_1"]
      },
      {
        "component_id": "stupp_concurrent",
        "component_type": "concurrent_chemoradiation",
        "timing": "adjuvant",
        "start_date": "2017-10-05",
        "end_date": "2017-11-16",
        "duration_days": 42,

        "chemotherapy": {
          "drugs": ["temozolomide"],
          "dose": "75 mg/m² daily",
          "route": "oral",
          "frequency": "daily",
          "days_administered": 42,

          // Link to all individual administrations
          "timeline_event_refs": [
            "chemo_start_2017-10-05_temo_1",
            "chemo_start_2017-10-05_temo_2",
            "chemo_start_2017-10-05_temo_3",
            ...
          ],

          // Preserved granular data from V4.8
          "individual_administrations": [
            {
              "date": "2017-10-05",
              "dose_mg": "150",
              "episode_drug_names": "temozolomide",
              "chemo_drug_category": "chemotherapy",
              "episode_care_plan_title": "Temozolomide",
              "source_event_type": "chemotherapy_start",
              "v48_adjudication_tier": "Tier 2a: raw_medication_start_date"
            },
            ...
          ]
        },

        "radiation": {
          "modality": "external_beam",
          "total_dose_gy": 54,
          "dose_per_fraction_gy": 1.8,
          "fractions": 30,
          "fields": "focal",
          "target_volume": "tumor bed + 2cm margin",
          "start_date": "2017-10-05",
          "end_date": "2017-11-16",

          // Link to granular events
          "timeline_event_refs": ["radiation_start_2017-10-05"],

          // Preserved from V4.8
          "individual_fractions_tracked": false,
          "appointment_count": 30,
          "appointment_fulfillment_rate": "100%"
        }
      },
      {
        "component_id": "stupp_adjuvant",
        "component_type": "adjuvant_chemotherapy",
        "timing": "post_radiation",
        "start_date": "2017-12-14",
        "end_date": "2018-04-05",

        "chemotherapy": {
          "drugs": ["temozolomide"],
          "dose": "150-200 mg/m² days 1-5",
          "route": "oral",
          "schedule": "q28 days",
          "cycles_planned": 6,
          "cycles_completed": 6,
          "cycles_administered": [
            {
              "cycle_number": 1,
              "start_date": "2017-12-14",
              "end_date": "2017-12-18",
              "days": "1-5",
              "dose_intensity": "100%",
              "timeline_event_refs": ["chemo_2017-12-14_c1d1", ...]
            },
            {
              "cycle_number": 2,
              "start_date": "2018-01-11",
              "end_date": "2018-01-15",
              "days": "1-5",
              "dose_intensity": "100%",
              "timeline_event_refs": ["chemo_2018-01-11_c2d1", ...]
            },
            ...
          ],

          // All individual administrations from V4.8
          "individual_administrations": [...]
        }
      }
    ]
  },

  // Response assessment
  "response_assessments": [
    {
      "assessment_date": "2017-12-15",
      "days_on_treatment": 79,
      "modality": "MRI brain",
      "rano_response": "stable_disease",
      "tumor_measurements": {
        "largest_dimension_mm": 25,
        "change_from_baseline_pct": -10
      },
      "clinical_assessment": "tolerating therapy well",
      "timeline_event_refs": ["imaging_2017-12-15"]
    },
    {
      "assessment_date": "2018-03-01",
      "days_on_treatment": 155,
      "modality": "MRI brain",
      "rano_response": "progressive_disease",
      "tumor_measurements": {
        "largest_dimension_mm": 35,
        "change_from_baseline_pct": +40
      },
      "clinical_assessment": "new enhancement, increased edema",
      "led_to_line_change": true,
      "timeline_event_refs": ["imaging_2018-03-01"]
    }
  ],

  // Reason for discontinuation
  "discontinuation": {
    "date": "2018-04-05",
    "reason": "disease_progression",
    "evidence": "MRI 2018-03-01 showed PD, started salvage therapy",
    "best_response_achieved": "stable_disease",
    "progression_free_survival_days": 155,
    "next_line_started": true
  }
}
```

#### Treatment Line 2 Example (Salvage)

```json
{
  "line_number": 2,
  "line_name": "Second-line Immunotherapy (Experimental)",
  "treatment_intent": "palliative",

  "start_date": "2018-02-22",
  "end_date": "2018-05-03",
  "days_from_diagnosis": 148,
  "duration_days": 70,
  "status": "completed",

  "regimen": {
    "regimen_name": "Nivolumab monotherapy",
    "protocol_reference": "CheckMate 143 (NCT02017717)",
    "match_confidence": "medium",
    "is_clinical_trial": true,
    "trial_name": "CheckMate pediatric expansion cohort",

    "components": [
      {
        "component_type": "immunotherapy",
        "drugs": ["nivolumab"],
        "dose": "3 mg/kg",
        "route": "IV",
        "schedule": "q14 days",
        "cycles_planned": null,  // Unknown
        "cycles_completed": 6,

        "individual_administrations": [
          {
            "date": "2018-02-22",
            "dose_mg": "180",  // Estimated from weight
            "infusion_duration_min": 60,
            "timeline_event_refs": ["chemo_start_2018-02-22_nivo_1"]
          },
          {
            "date": "2018-03-08",
            "dose_mg": "180",
            "timeline_event_refs": ["chemo_start_2018-03-08_nivo_1"]
          },
          ...
        ]
      }
    ]
  },

  "response_assessments": [
    {
      "assessment_date": "2018-04-15",
      "days_on_treatment": 52,
      "rano_response": "progressive_disease",
      "led_to_line_change": true
    }
  ],

  "discontinuation": {
    "date": "2018-05-03",
    "reason": "disease_progression",
    "evidence": "MRI showed continued growth despite immunotherapy",
    "best_response_achieved": "progressive_disease",
    "progression_free_survival_days": 52,
    "next_line_started": true
  }
}
```

---

## Implementation Architecture

### Phase 5.0.1: Treatment Line Detection (Claude Orchestrator)

**Goal:** Group timeline events into treatment lines

**Claude's Role:**
1. Load all V4.8 timeline events (chemotherapy_start, radiation_start, surgery)
2. Identify temporal boundaries for treatment line changes
3. Classify reason for each line change

**Generalizable Claude Prompt for Treatment Line Detection:**

```
You are analyzing a patient's cancer treatment timeline to identify distinct treatment lines.

INPUT:
- Timeline events: chemotherapy_start, radiation_start, surgery, imaging events
- Diagnosis: {who_2021_diagnosis}
- Diagnosis date: {diagnosis_date}

TASK:
Group events into treatment lines. A new treatment line begins when:

1. TEMPORAL SIGNAL: Gap >30 days between treatments of same drug class
   - AND imaging shows progression during gap
   - OR clinical note mentions "progression", "recurrence", "salvage"

2. THERAPEUTIC INTENT CHANGE:
   - Curative → Palliative (e.g., after surgical resection deemed not feasible)
   - Standard-of-care → Experimental (e.g., enrollment in clinical trial)
   - Active treatment → Hospice

3. DRUG CLASS CHANGE after imaging progression:
   - Alkylator (TMZ) → Immunotherapy (nivolumab)
   - Chemotherapy → Targeted therapy (bevacizumab)
   - Single-agent → Multi-agent combination

4. RECURRENCE TREATMENT:
   - Re-resection after initial treatment completion
   - Radiation to new site after prior focal RT
   - Salvage chemotherapy after progression on prior regimen

CLASSIFY each line's reason for change:
- "initial_diagnosis" (Line 1 only)
- "disease_progression" (most common for Line 2+)
- "toxicity_intolerance"
- "protocol_completion"
- "patient_preference"
- "clinical_trial_enrollment"

OUTPUT:
For each line, provide:
- line_number: int
- start_date: ISO date
- end_date: ISO date (or null if ongoing)
- reason_for_change: classification above
- evidence: brief clinical justification (cite imaging dates, note excerpts)
```

**Detection Algorithm:**

```python
def detect_treatment_lines(timeline_events):
    """
    Claude's reasoning process for detecting treatment lines.

    Signals for new treatment line:
    1. Temporal gap > 30 days between similar drug classes
    2. Change in drug class (alkylator → immunotherapy → topoisomerase inhibitor)
    3. Imaging showing progression followed by new therapy
    4. Clinical notes mentioning "second-line", "salvage", "progression"
    5. Surgery for recurrence
    """

    lines = []
    current_line = None

    # Sort events chronologically
    events = sorted(timeline_events, key=lambda e: e['event_date'])

    for event in events:
        # First event always starts Line 1
        if current_line is None:
            current_line = {
                'line_number': 1,
                'start_date': event['event_date'],
                'events': [event],
                'drugs_used': set()
            }
            continue

        # Check for line change signals
        if is_new_treatment_line(event, current_line, timeline_events):
            # Save current line
            lines.append(current_line)

            # Start new line
            current_line = {
                'line_number': len(lines) + 1,
                'start_date': event['event_date'],
                'events': [event],
                'drugs_used': set(),
                'reason_for_change': detect_change_reason(event, lines[-1])
            }
        else:
            # Add to current line
            current_line['events'].append(event)
            if 'drug' in event:
                current_line['drugs_used'].add(event['drug'])

    # Add final line
    if current_line:
        lines.append(current_line)

    return lines


def is_new_treatment_line(event, current_line, all_events):
    """
    Multi-signal detection for treatment line boundaries.
    """
    # Signal 1: Large temporal gap
    last_event_date = current_line['events'][-1]['event_date']
    gap_days = (parse_date(event['event_date']) - parse_date(last_event_date)).days
    if gap_days > 30:
        # Check if there's imaging showing progression in between
        progression_imaging = find_imaging_between(
            last_event_date,
            event['event_date'],
            all_events,
            response_filter='progressive_disease'
        )
        if progression_imaging:
            return True

    # Signal 2: Drug class change
    event_drug_class = get_drug_class(event.get('drug'))
    current_drug_classes = {get_drug_class(d) for d in current_line['drugs_used']}
    if event_drug_class and event_drug_class not in current_drug_classes:
        # Switching from alkylator to immunotherapy is likely a new line
        if (current_drug_classes == {'alkylating_agent'} and
            event_drug_class == 'immunotherapy'):
            return True

    # Signal 3: Surgery for recurrence
    if event['event_type'] == 'surgery':
        if current_line['line_number'] > 1:
            # Surgery after initial treatment = salvage surgery
            return True

    # Signal 4: Clinical note mentions
    # (Would query progress notes around event date)

    return False
```

### Phase 5.0.2: Regimen Grouping (Claude Orchestrator)

**Goal:** Group treatment line events into named regimens

**Generalizable Claude Prompt for Regimen Matching:**

```
You are classifying a patient's treatment regimen against known oncology protocols.

INPUT:
- Line events: surgeries, chemotherapy administrations, radiation courses
- Diagnosis: {who_2021_diagnosis} (e.g., "IDH-mutant astrocytoma grade 3", "medulloblastoma WNT-activated", "DIPG")
- Patient age: {age_years}
- Treatment line number: {line_number}

TASK:
Match observed treatment components to known protocols from the knowledge base.

MATCHING CRITERIA:
1. Diagnosis match: Does protocol indication match patient's diagnosis?
2. Age-appropriate: Is protocol designed for patient's age group (pediatric vs adult)?
3. Component match: Are surgery, chemotherapy, radiation present as expected?
4. Dose/schedule match: Do doses and schedules align with protocol specifications?
5. Temporal sequence: Are components administered in correct order?

SCORING:
- High confidence (≥90%): All major components match, minor deviations acceptable
- Medium confidence (70-89%): Core components match, notable deviations present
- Low confidence (50-69%): Partial match, significant deviations
- No match (<50%): Does not match any known protocol

DEVIATIONS TO DOCUMENT:
- Dose modifications (e.g., "Radiation 54 Gy vs protocol 60 Gy")
- Schedule changes (e.g., "q21 days vs protocol q28 days")
- Missing components (e.g., "No concurrent chemotherapy per protocol")
- Additional agents (e.g., "Added bevacizumab not in standard protocol")

For each deviation, classify clinical significance:
- "standard_variation": Acceptable modification (e.g., pediatric dose adjustment)
- "protocol_deviation": Notable change from protocol (e.g., reduced cycles due to toxicity)
- "off_protocol": Treatment does not follow standard guidelines

OUTPUT:
{
  "regimen_name": str,  // e.g., "Modified Stupp Protocol (TMZ + RT)"
  "protocol_reference": str,  // e.g., "Stupp et al. NEJM 2005"
  "match_confidence": "high" | "medium" | "low" | "no_match",
  "evidence_level": "standard_of_care" | "clinical_trial" | "experimental" | "salvage",
  "deviations_from_protocol": [
    {"deviation": str, "rationale": str, "clinical_significance": str}
  ]
}
```

**Knowledge Base:** Pediatric & Adult CNS Tumor Protocols

```python
PEDIATRIC_CNS_PROTOCOLS = {
    "stupp_protocol": {
        "name": "Modified Stupp Protocol",
        "reference": "Stupp et al. NEJM 2005",
        "indications": ["IDH-mutant astrocytoma", "glioblastoma"],
        "evidence_level": "standard_of_care",
        "components": {
            "surgery": {
                "required": True,
                "timing": "upfront",
                "eor_preference": "gross_total_resection"
            },
            "concurrent_chemoradiation": {
                "required": True,
                "chemotherapy": {
                    "drugs": ["temozolomide"],
                    "dose": "75 mg/m² daily",
                    "duration_days": 42
                },
                "radiation": {
                    "dose_gy": {"adult": 60, "pediatric": [54, 59.4]},
                    "fractions": 30,
                    "dose_per_fraction": 1.8
                }
            },
            "adjuvant_chemotherapy": {
                "required": True,
                "drugs": ["temozolomide"],
                "dose": "150-200 mg/m² days 1-5",
                "schedule": "q28 days",
                "cycles": 6
            }
        },
        "expected_duration_days": [168, 196]  // 24-28 weeks
    },

    "cog_acns0126": {
        "name": "COG ACNS0126 Protocol",
        "reference": "Children's Oncology Group",
        "indications": ["high-grade glioma"],
        "evidence_level": "clinical_trial",
        "components": {
            "surgery": {"required": True, "timing": "upfront"},
            "radiation": {
                "dose_gy": 54,
                "fractions": 30
            },
            "chemotherapy_arm_a": {
                "drugs": ["temozolomide"],
                "concurrent": True,
                "adjuvant_cycles": 10
            },
            "chemotherapy_arm_b": {
                "drugs": ["temozolomide", "lomustine"],
                "concurrent": "temozolomide",
                "adjuvant": ["temozolomide", "lomustine"]
            }
        }
    },

    "checkmate_143": {
        "name": "CheckMate 143 / Nivolumab Salvage",
        "reference": "NCT02017717",
        "indications": ["recurrent_glioblastoma"],
        "evidence_level": "experimental",
        "line_of_therapy": "salvage",
        "components": {
            "immunotherapy": {
                "drugs": ["nivolumab"],
                "dose": "3 mg/kg",
                "schedule": "q14 days",
                "duration": "until_progression"
            }
        }
    }
}


def match_regimen_to_protocol(line_events, diagnosis, knowledge_base):
    """
    Claude matches observed treatment to known protocols.

    Returns:
        regimen_match: {
            'protocol_name': str,
            'confidence': float,
            'components_matched': dict,
            'deviations': list
        }
    """
    # Extract components from events
    observed_components = extract_components_from_events(line_events)

    best_match = None
    best_score = 0

    for protocol_id, protocol in knowledge_base.items():
        # Check if diagnosis matches
        if diagnosis not in protocol['indications']:
            continue

        # Score component matching
        score, matched, deviations = score_protocol_match(
            observed_components,
            protocol['components']
        )

        if score > best_score:
            best_score = score
            best_match = {
                'protocol_id': protocol_id,
                'protocol_name': protocol['name'],
                'confidence': score,
                'components_matched': matched,
                'deviations': deviations,
                'evidence_level': protocol['evidence_level']
            }

    return best_match
```

### Phase 5.0.2b: Radiation Treatment Grouping (Claude Orchestrator)

**Goal:** Group radiation events into clinically meaningful courses and regimens

**Radiation Hierarchical Model:**

```
RADIATION TREATMENT LINE
├── Radiation Regimen (named by intent and technique)
│   ├── Treatment Intent: upfront_definitive | adjuvant | salvage | palliative | stereotactic_boost
│   ├── Treatment Phases
│   │   ├── Phase 1: Simulation & Planning
│   │   ├── Phase 2: Initial Treatment (e.g., whole brain, craniospinal)
│   │   ├── Phase 3: Boost (e.g., tumor bed boost)
│   ├── Individual Fractions ← V4.8 granular data
│   │   ├── Appointment records
│   │   ├── Dosimetry data
│   │   └── Fulfillment tracking
```

**Generalizable Claude Prompt for Radiation Grouping:**

```
You are analyzing radiation therapy events to group them into clinically meaningful treatment courses.

INPUT:
- Radiation events: radiation_start, radiation_stop dates
- Total dose (Gy), fractions, dose per fraction
- Radiation field/target (e.g., "focal tumor bed", "craniospinal axis", "whole brain")
- Care plan titles (e.g., "Brain Tumor RT", "CSI + Boost")
- Appointment records with fulfillment rates
- Patient diagnosis: {who_2021_diagnosis}
- Patient age: {age_years}

TASK:
Group radiation events into treatment courses and classify regimen type.

RADIATION COURSE DETECTION:
A new radiation course starts when:
1. Gap >60 days from prior radiation end date
2. New anatomical target (e.g., whole brain after prior focal RT)
3. Different treatment intent (e.g., salvage RT after upfront RT)
4. Re-irradiation after progression

REGIMEN CLASSIFICATION by dose/fractionation pattern:

STANDARD FRACTIONATION (1.8-2.0 Gy per fraction):
- 54-60 Gy in 30-33 fractions → "Definitive focal radiation"
- 30.6-36 Gy CSI + 19.8-23.4 Gy boost → "Craniospinal irradiation with boost"
- 50.4 Gy in 28 fractions → "Standard adult glioma radiation"

HYPOFRACTIONATION (>2.5 Gy per fraction):
- 40-42 Gy in 15 fractions → "Hypofractionated palliative radiation"
- 34 Gy in 10 fractions → "Short-course palliative RT"

STEREOTACTIC (high dose, few fractions):
- 15-24 Gy in 1 fraction → "Single-fraction SRS"
- 21-35 Gy in 3-5 fractions → "Fractionated SRS/SBRT"

PALLIATION:
- 20-30 Gy in 5-10 fractions → "Palliative radiation"
- 8 Gy in 1 fraction → "Single-fraction palliation"

PHASE DETECTION:
For multi-phase treatments (e.g., CSI + boost):
- Phase 1: Larger field, lower dose (e.g., 23.4 Gy CSI)
- Phase 2: Smaller field, higher total dose (e.g., + 30.6 Gy boost to posterior fossa)

OUTPUT:
{
  "radiation_course_number": int,
  "treatment_intent": "upfront_definitive" | "adjuvant" | "salvage" | "palliative" | "boost",
  "regimen_name": str,  // e.g., "Focal definitive radiation 54 Gy"
  "technique": "3D_conformal" | "IMRT" | "proton" | "stereotactic" | "craniospinal",
  "total_dose_gy": float,
  "fractions_planned": int,
  "fractions_delivered": int,
  "dose_per_fraction_gy": float,
  "fractionation_type": "standard" | "hypofractionated" | "stereotactic" | "palliative",
  "target_volume": str,  // e.g., "tumor bed + 2cm margin", "whole brain", "craniospinal axis"
  "phases": [
    {
      "phase_number": 1,
      "phase_name": "Initial field",
      "dose_gy": float,
      "fractions": int,
      "target": str
    }
  ],
  "timeline_event_refs": [str],  // Links to V4.8 radiation events
  "individual_appointments": [...]  // Preserved from V4.8
}
```

**Radiation Knowledge Base:**

```python
RADIATION_REGIMENS = {
    "pediatric_focal_definitive": {
        "name": "Pediatric focal definitive radiation",
        "indications": ["high-grade glioma", "ependymoma", "low-grade glioma (progressive)"],
        "age_range": [0, 21],
        "dose_range_gy": [50.4, 59.4],
        "fractions": [28, 33],
        "dose_per_fraction_gy": 1.8,
        "target": "tumor bed + margin",
        "concurrent_chemo_common": True
    },

    "craniospinal_with_boost": {
        "name": "Craniospinal irradiation with posterior fossa boost",
        "indications": ["medulloblastoma", "high-risk ependymoma", "germ cell tumors"],
        "age_range": [3, 21],
        "phases": [
            {
                "phase": 1,
                "name": "Craniospinal axis",
                "dose_gy": [23.4, 36.0],
                "target": "entire craniospinal axis"
            },
            {
                "phase": 2,
                "name": "Posterior fossa boost",
                "dose_gy": [30.6, 23.4],  # To reach total 54-55.8 Gy
                "target": "posterior fossa or tumor bed"
            }
        ],
        "technique_preference": "proton"
    },

    "adult_glioma_standard": {
        "name": "Adult high-grade glioma radiation",
        "indications": ["glioblastoma", "anaplastic astrocytoma", "IDH-mutant grade 3/4"],
        "age_range": [18, 100],
        "dose_gy": 60,
        "fractions": 30,
        "dose_per_fraction_gy": 2.0,
        "target": "T1+T2/FLAIR + 2cm margin",
        "concurrent_chemo": "temozolomide 75 mg/m² daily"
    },

    "hypofractionated_elderly": {
        "name": "Hypofractionated radiation for elderly GBM",
        "indications": ["glioblastoma age >65", "poor performance status"],
        "age_range": [65, 100],
        "dose_gy": 40,
        "fractions": 15,
        "dose_per_fraction_gy": 2.67,
        "reference": "Perry et al. NEJM 2017"
    },

    "srs_salvage": {
        "name": "Stereotactic radiosurgery for recurrence",
        "indications": ["recurrent glioma", "small volume recurrence"],
        "technique": "stereotactic",
        "dose_range_gy": [15, 24],
        "fractions": 1,
        "max_target_volume_cc": 40,
        "timing": "salvage"
    }
}
```

**Example: Classifying Multi-Phase Radiation (Medulloblastoma)**

```
INPUT EVENTS:
- radiation_start: 2018-01-10, total_dose_gy: 23.4, fractions: 13, target: "craniospinal axis"
- radiation_start: 2018-02-05, total_dose_gy: 30.6, fractions: 17, target: "posterior fossa"

CLAUDE ANALYSIS:
1. Both events have gap <30 days → Same treatment course
2. Total dose 23.4 + 30.6 = 54 Gy → Matches medulloblastoma standard-risk protocol
3. Dose/fractionation: 1.8 Gy per fraction (both phases) → Standard fractionation
4. Sequential phases: CSI → boost → Matches two-phase CSI protocol

OUTPUT:
{
  "radiation_course_number": 1,
  "regimen_name": "Craniospinal irradiation with posterior fossa boost",
  "protocol_reference": "COG ACNS0331 standard-risk medulloblastoma",
  "match_confidence": "high",
  "treatment_intent": "adjuvant",
  "technique": "craniospinal",
  "total_dose_gy": 54.0,
  "fractions_planned": 30,
  "fractions_delivered": 30,
  "fractionation_type": "standard",

  "phases": [
    {
      "phase_number": 1,
      "phase_name": "Craniospinal axis",
      "dose_gy": 23.4,
      "fractions": 13,
      "target": "entire craniospinal axis",
      "start_date": "2018-01-10",
      "end_date": "2018-01-29",
      "timeline_event_refs": ["radiation_start_2018-01-10"]
    },
    {
      "phase_number": 2,
      "phase_name": "Posterior fossa boost",
      "dose_gy": 30.6,
      "fractions": 17,
      "target": "posterior fossa",
      "start_date": "2018-02-05",
      "end_date": "2018-03-01",
      "timeline_event_refs": ["radiation_start_2018-02-05"]
    }
  ],

  "individual_appointments": [
    // All V4.8 appointment-level data preserved
    {"date": "2018-01-10", "dose_gy": 1.8, "target": "CSI", "fulfilled": true},
    {"date": "2018-01-11", "dose_gy": 1.8, "target": "CSI", "fulfilled": true},
    ...
  ]
}
```

### Phase 5.0.3: Cycle Detection (Claude Orchestrator)

**Goal:** Group individual chemotherapy administrations into cycles

```python
def detect_cycles(administrations, regimen_schedule):
    """
    Group individual administrations into treatment cycles.

    For temozolomide "days 1-5 q28 days":
      - Days 1-5: Single cycle
      - Gap of ~23 days
      - Next days 1-5: Next cycle
    """

    cycles = []
    current_cycle = None

    for admin in sorted(administrations, key=lambda a: a['date']):
        if current_cycle is None:
            # Start first cycle
            current_cycle = {
                'cycle_number': 1,
                'start_date': admin['date'],
                'administrations': [admin]
            }
            continue

        # Check if this admin belongs to current cycle or starts new cycle
        days_since_cycle_start = (
            parse_date(admin['date']) -
            parse_date(current_cycle['start_date'])
        ).days

        if days_since_cycle_start <= 7:  # Within treatment week
            current_cycle['administrations'].append(admin)
        else:  # New cycle started
            # Finalize current cycle
            current_cycle['end_date'] = current_cycle['administrations'][-1]['date']
            current_cycle['days_administered'] = len(current_cycle['administrations'])
            cycles.append(current_cycle)

            # Start new cycle
            current_cycle = {
                'cycle_number': len(cycles) + 1,
                'start_date': admin['date'],
                'administrations': [admin]
            }

    # Add final cycle
    if current_cycle:
        current_cycle['end_date'] = current_cycle['administrations'][-1]['date']
        current_cycle['days_administered'] = len(current_cycle['administrations'])
        cycles.append(current_cycle)

    return cycles
```

### Phase 5.0.4: Response Assessment Integration

**Goal:** Link imaging assessments to treatment lines

```python
def integrate_response_assessments(treatment_line, imaging_events):
    """
    Find imaging studies during treatment line and classify response.
    """
    line_start = parse_date(treatment_line['start_date'])
    line_end = parse_date(treatment_line['end_date']) if treatment_line.get('end_date') else datetime.now()

    assessments = []

    for imaging in imaging_events:
        img_date = parse_date(imaging['event_date'])

        if line_start <= img_date <= line_end:
            days_on_treatment = (img_date - line_start).days

            assessment = {
                'assessment_date': imaging['event_date'],
                'days_on_treatment': days_on_treatment,
                'modality': imaging.get('imaging_type'),
                'rano_response': imaging.get('rano_assessment'),
                'report_conclusion': imaging.get('report_conclusion'),
                'timeline_event_ref': imaging['event_id']
            }

            # Check if this led to line change
            if imaging.get('rano_assessment') == 'progressive_disease':
                # Look for new treatment line starting within 60 days
                next_treatment = find_next_treatment_after(
                    img_date,
                    within_days=60
                )
                if next_treatment:
                    assessment['led_to_line_change'] = True

            assessments.append(assessment)

    return sorted(assessments, key=lambda a: a['assessment_date'])
```

### Phase 5.0.5: Clinical Endpoints Calculation

**Goal:** Calculate standardized metrics for cross-patient comparison

```python
def calculate_clinical_endpoints(therapeutic_approach, diagnosis_date, last_contact_date):
    """
    Calculate standard oncology endpoints.
    """
    d0 = parse_date(diagnosis_date)

    endpoints = {
        'diagnosis_date': diagnosis_date,
        'follow_up_duration_days': (parse_date(last_contact_date) - d0).days,

        'per_line_metrics': [],

        'overall_metrics': {
            'overall_survival_days': None,  # Requires vital status
            'overall_survival_status': 'alive',  # Or 'deceased'
            'time_to_first_progression_days': None,
            'number_of_treatment_lines': len(therapeutic_approach['lines_of_therapy'])
        }
    }

    for line in therapeutic_approach['lines_of_therapy']:
        # Progression-free survival for this line
        pfs = None
        if line.get('discontinuation', {}).get('reason') == 'disease_progression':
            pfs = line['discontinuation'].get('progression_free_survival_days')
        elif line.get('response_assessments'):
            # Find first PD assessment
            for assessment in line['response_assessments']:
                if assessment.get('rano_response') == 'progressive_disease':
                    pfs = assessment['days_on_treatment']
                    break

        endpoints['per_line_metrics'].append({
            'line_number': line['line_number'],
            'regimen_name': line['regimen']['regimen_name'],
            'start_days_from_diagnosis': line['days_from_diagnosis'],
            'duration_days': line['duration_days'],
            'progression_free_survival_days': pfs,
            'best_response': get_best_response(line['response_assessments']),
            'reason_for_discontinuation': line.get('discontinuation', {}).get('reason')
        })

        # Track first progression
        if pfs and endpoints['overall_metrics']['time_to_first_progression_days'] is None:
            endpoints['overall_metrics']['time_to_first_progression_days'] = (
                line['days_from_diagnosis'] + pfs
            )

    return endpoints
```

---

## Data Preservation Principle

### Critical: All V4.8 Granular Data Preserved

The V5.0 framework **ADDS** higher-level abstractions but **NEVER REMOVES** granular detail:

```json
{
  "therapeutic_approach": {
    // NEW V5.0 abstraction
    "lines_of_therapy": [
      {
        "line_number": 1,
        "regimen": {
          "components": [
            {
              "chemotherapy": {
                // Link to V4.8 events
                "timeline_event_refs": ["chemo_2017-10-05_1", "chemo_2017-10-05_2"],

                // PRESERVED: All V4.8 individual administrations
                "individual_administrations": [
                  {
                    "date": "2017-10-05",
                    "dose_mg": "150",
                    "episode_drug_names": "temozolomide",
                    "chemo_drug_category": "chemotherapy",
                    "episode_care_plan_title": "Temozolomide",
                    "episode_start_datetime": "2017-10-05",
                    "episode_end_datetime": "2017-10-19",
                    "v48_adjudication_tier": "Tier 2a",
                    "v46_therapy_end_date": null,
                    "source_view": "v_chemo_treatment_episodes",
                    "athena_row_id": "12345"
                  },
                  ...
                ]
              }
            }
          ]
        }
      }
    ]
  },

  // PRESERVED: Original V4.8 timeline_events array
  "timeline_events": [
    {
      "event_id": "chemo_2017-10-05_1",
      "event_type": "chemotherapy_start",
      "event_date": "2017-10-05",
      "episode_drug_names": "temozolomide",
      ...
    },
    ...
  ],

  // PRESERVED: All V4.8 metadata
  "extraction_gaps": [...],
  "binary_extractions": [...],
  "timeline_construction_metadata": {...}
}
```

**Rationale:**
1. **Auditability:** Can trace high-level abstractions back to source data
2. **Debugging:** If regimen matching is wrong, can review raw events
3. **Re-analysis:** Future research may need granular data V5.0 abstracted away
4. **Regulatory compliance:** FDA/sponsor audits require source data

---

## Cross-Patient Comparison Examples

### Use Case 1: Cohort Building

**Query:** "Find all IDH-mutant astrocytoma grade 3 patients who received Stupp Protocol as first-line"

```python
cohort = []

for patient in patient_database:
    if (patient['who_2021_classification']['who_2021_diagnosis'].contains('IDH-mutant') and
        patient['who_2021_classification']['grade'] == 3):

        # Check first-line treatment
        line1 = patient['therapeutic_approach']['lines_of_therapy'][0]

        if line1['regimen']['protocol_reference'].contains('Stupp'):
            cohort.append({
                'patient_id': patient['patient_id'],
                'age_at_diagnosis': patient['patient_demographics']['pd_age_years'],
                'regimen_name': line1['regimen']['regimen_name'],
                'cycles_completed': len(line1['regimen']['components'][1]['chemotherapy']['cycles_administered']),
                'pfs_days': line1['discontinuation']['progression_free_survival_days'],
                'best_response': get_best_response(line1['response_assessments'])
            })

# Result:
# cohort = [
#   {'patient_id': 'eQSB0y3q...', 'age': 20, 'cycles': 6, 'pfs_days': 155, 'response': 'SD'},
#   {'patient_id': 'fXYZ123...', 'age': 18, 'cycles': 3, 'pfs_days': 42, 'response': 'PD'},
#   ...
# ]
```

### Use Case 2: Protocol Adherence Analysis

**Query:** "How many patients completed all 6 cycles of adjuvant TMZ per Stupp protocol?"

```python
completed_full_protocol = 0
early_discontinuation = 0

for patient in stupp_cohort:
    line1 = patient['therapeutic_approach']['lines_of_therapy'][0]
    adjuvant = [c for c in line1['regimen']['components'] if c['component_type'] == 'adjuvant_chemotherapy'][0]

    if adjuvant['chemotherapy']['cycles_completed'] >= 6:
        completed_full_protocol += 1
    else:
        early_discontinuation += 1
        print(f"Patient {patient['patient_id']}: Only {adjuvant['chemotherapy']['cycles_completed']} cycles")
        print(f"  Reason: {line1['discontinuation']['reason']}")

# Output:
# Patient eQSB0y3q...: Only 6 cycles  ✓ Completed
# Patient fXYZ123...: Only 3 cycles
#   Reason: disease_progression
```

### Use Case 3: Salvage Therapy Patterns

**Query:** "What salvage therapies are used after Stupp failure?"

```python
salvage_regimens = defaultdict(int)

for patient in stupp_cohort:
    lines = patient['therapeutic_approach']['lines_of_therapy']

    if len(lines) >= 2:  # Has salvage therapy
        line2_regimen = lines[1]['regimen']['regimen_name']
        salvage_regimens[line2_regimen] += 1

# Result:
# salvage_regimens = {
#   'Nivolumab monotherapy': 15,
#   'Bevacizumab': 8,
#   'Etoposide': 5,
#   'Re-resection only': 3,
#   ...
# }
```

---

## Generalizable Examples Across Tumor Types

### Example 1: Pediatric Medulloblastoma (WNT-activated)

**INPUT Timeline:**
- Surgery: 2023-05-15, extent_of_resection: "gross_total_resection"
- Radiation: 2023-06-20 to 2023-07-15, CSI 23.4 Gy (13 fractions)
- Radiation: 2023-07-18 to 2023-08-10, Posterior fossa boost 30.6 Gy (17 fractions)
- Chemotherapy: vincristine weekly during radiation (8 doses)
- Chemotherapy: 2023-08-20 to 2024-02-15, maintenance (cisplatin, vincristine, cyclophosphamide)

**CLAUDE V5.0 ABSTRACTION:**

```json
{
  "therapeutic_approach": {
    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "First-line standard-risk medulloblastoma therapy",
        "treatment_intent": "curative",
        "regimen": {
          "regimen_name": "COG ACNS0331 Arm A (average-risk medulloblastoma)",
          "protocol_reference": "COG ACNS0331",
          "match_confidence": "high",
          "evidence_level": "standard_of_care",
          "components": [
            {
              "component_type": "surgery",
              "timing": "upfront",
              "date": "2023-05-15",
              "extent_of_resection": "gross_total_resection"
            },
            {
              "component_type": "radiation",
              "timing": "adjuvant",
              "regimen_name": "Craniospinal irradiation with posterior fossa boost",
              "total_dose_gy": 54.0,
              "phases": [
                {"phase": 1, "target": "CSI", "dose_gy": 23.4},
                {"phase": 2, "target": "posterior fossa", "dose_gy": 30.6}
              ]
            },
            {
              "component_type": "concurrent_chemotherapy",
              "timing": "during_radiation",
              "drugs": ["vincristine"],
              "schedule": "weekly",
              "administrations": 8
            },
            {
              "component_type": "maintenance_chemotherapy",
              "timing": "post_radiation",
              "drugs": ["cisplatin", "vincristine", "cyclophosphamide"],
              "cycles_planned": 6,
              "cycles_completed": 6
            }
          ]
        }
      }
    ]
  }
}
```

### Example 2: Adult Glioblastoma (IDH-wildtype)

**INPUT Timeline:**
- Surgery: 2024-01-10, extent_of_resection: "subtotal_resection"
- Radiation: 2024-02-15 to 2024-03-25, 60 Gy in 30 fractions, concurrent TMZ
- Chemotherapy: TMZ 75 mg/m² daily during RT (42 days)
- Chemotherapy: 2024-04-20 to 2024-09-15, TMZ 150-200 mg/m² days 1-5 q28d (6 cycles)
- Imaging: 2024-07-10, RANO: progressive_disease
- Surgery: 2024-08-05, re-resection
- Chemotherapy: 2024-09-01, bevacizumab + lomustine (salvage)

**CLAUDE V5.0 ABSTRACTION:**

```json
{
  "therapeutic_approach": {
    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "First-line Stupp Protocol",
        "treatment_intent": "curative",
        "regimen": {
          "regimen_name": "Stupp Protocol (TMZ + RT → adjuvant TMZ)",
          "protocol_reference": "Stupp et al. NEJM 2005",
          "match_confidence": "high",
          "components": [
            {"component_type": "surgery", "eor": "subtotal_resection"},
            {"component_type": "concurrent_chemoradiation", "rt_dose": 60, "tmo": "75 mg/m² daily"},
            {"component_type": "adjuvant_chemotherapy", "drug": "temozolomide", "cycles": 6}
          ]
        },
        "discontinuation": {
          "reason": "disease_progression",
          "evidence": "MRI 2024-07-10 showed new enhancement",
          "pfs_days": 116
        }
      },
      {
        "line_number": 2,
        "line_name": "Second-line salvage therapy",
        "treatment_intent": "palliative",
        "regimen": {
          "regimen_name": "Re-resection + bevacizumab/lomustine",
          "protocol_reference": "EORTC 26101 salvage regimen",
          "match_confidence": "medium",
          "components": [
            {"component_type": "surgery", "timing": "salvage", "date": "2024-08-05"},
            {"component_type": "chemotherapy", "drugs": ["bevacizumab", "lomustine"]}
          ]
        }
      }
    ]
  }
}
```

### Example 3: Pediatric DIPG (Diffuse Intrinsic Pontine Glioma)

**INPUT Timeline:**
- NO surgery (unresectable)
- Radiation: 2023-03-01 to 2023-03-30, 54 Gy in 30 fractions
- Clinical trial: 2023-04-15 to 2023-08-20, panobinostat (HDAC inhibitor)
- Imaging: 2023-09-01, RANO: progressive_disease
- Hospice: 2023-09-15

**CLAUDE V5.0 ABSTRACTION:**

```json
{
  "therapeutic_approach": {
    "treatment_intent_overall": "palliative_converted_to_hospice",
    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "Upfront radiation therapy",
        "treatment_intent": "palliative",
        "regimen": {
          "regimen_name": "Focal brainstem radiation 54 Gy",
          "protocol_reference": "DIPG standard-of-care",
          "match_confidence": "high",
          "components": [
            {
              "component_type": "radiation",
              "total_dose_gy": 54,
              "fractions": 30,
              "target": "pontine lesion + margin"
            }
          ]
        },
        "response_assessments": [
          {"date": "2023-05-01", "rano": "stable_disease", "clinical": "symptom improvement"}
        ]
      },
      {
        "line_number": 2,
        "line_name": "Experimental HDAC inhibitor therapy",
        "treatment_intent": "experimental",
        "regimen": {
          "regimen_name": "Panobinostat monotherapy",
          "is_clinical_trial": true,
          "trial_name": "BIOMEDE trial",
          "match_confidence": "high",
          "components": [
            {"component_type": "targeted_therapy", "drug": "panobinostat", "duration_days": 127}
          ]
        },
        "discontinuation": {
          "reason": "disease_progression",
          "evidence": "MRI 2023-09-01 showed increased lesion size",
          "next_line_started": false
        }
      },
      {
        "line_number": 3,
        "line_name": "Hospice care",
        "treatment_intent": "hospice",
        "start_date": "2023-09-15",
        "regimen": {
          "regimen_name": "Comfort care",
          "components": []
        }
      }
    ]
  }
}
```

### Example 4: Pediatric Ependymoma (Posterior Fossa)

**INPUT Timeline:**
- Surgery: 2022-11-20, extent_of_resection: "gross_total_resection"
- Radiation: 2023-01-10 to 2023-02-20, 59.4 Gy in 33 fractions (focal posterior fossa)
- Imaging: Follow-up MRIs every 3 months, all stable
- NO chemotherapy (per protocol for GTR ependymoma)

**CLAUDE V5.0 ABSTRACTION:**

```json
{
  "therapeutic_approach": {
    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "Surgery + adjuvant radiation (no chemo)",
        "treatment_intent": "curative",
        "regimen": {
          "regimen_name": "Ependymoma GTR + focal RT",
          "protocol_reference": "COG ACNS0831",
          "match_confidence": "high",
          "components": [
            {
              "component_type": "surgery",
              "date": "2022-11-20",
              "extent_of_resection": "gross_total_resection",
              "location": "posterior fossa"
            },
            {
              "component_type": "radiation",
              "timing": "adjuvant",
              "total_dose_gy": 59.4,
              "fractions": 33,
              "target": "tumor bed + 1cm margin",
              "note": "No chemotherapy per protocol for GTR disease"
            }
          ]
        },
        "status": "completed",
        "response_assessments": [
          {"date": "2023-05-15", "rano": "complete_response"},
          {"date": "2023-08-15", "rano": "complete_response"},
          {"date": "2023-11-15", "rano": "complete_response"}
        ]
      }
    ],
    "clinical_endpoints": {
      "pfs_days": 730,
      "status": "no_evidence_of_disease"
    }
  }
}
```

### Example 5: Surgery-Only Low-Grade Glioma (Pediatric)

**INPUT Timeline:**
- Surgery: 2024-06-10, extent_of_resection: "gross_total_resection"
- Pathology: Pilocytic astrocytoma, WHO grade 1
- NO chemotherapy, NO radiation (per observation protocol)
- Imaging: Serial MRIs every 3-6 months, all showing no residual disease

**CLAUDE V5.0 ABSTRACTION:**

```json
{
  "therapeutic_approach": {
    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "Surgical resection only (observation protocol)",
        "treatment_intent": "curative",
        "regimen": {
          "regimen_name": "Surgery alone with surveillance",
          "protocol_reference": "COG ACNS0221 observation arm",
          "match_confidence": "high",
          "components": [
            {
              "component_type": "surgery",
              "date": "2024-06-10",
              "extent_of_resection": "gross_total_resection",
              "pathology": "pilocytic astrocytoma grade 1",
              "note": "No adjuvant therapy per protocol for completely resected grade 1 LGG"
            }
          ]
        },
        "status": "surveillance",
        "response_assessments": [
          {"date": "2024-09-10", "rano": "complete_response", "residual": "none"},
          {"date": "2024-12-10", "rano": "complete_response", "residual": "none"}
        ]
      }
    ]
  }
}
```

### Key Generalizable Patterns

**Pattern 1: No Surgery (Unresectable)**
```python
if no_surgery_events and diagnosis in ["DIPG", "brainstem_glioma"]:
    regimen_components = [radiation, chemotherapy]  # Surgery omitted, not failed
    note = "Unresectable tumor, no surgical intervention attempted per standard-of-care"
```

**Pattern 2: Surgery-Only (Complete Resection of Benign)**
```python
if surgery_eor == "gross_total_resection" and grade == 1 and no_chemo_radiation:
    regimen_name = "Surgery alone with surveillance"
    treatment_intent = "curative"
    note = "No adjuvant therapy per protocol"
```

**Pattern 3: Multi-Modal Therapy (Standard)**
```python
if surgery and radiation and chemotherapy:
    # Determine timing relationships
    if chemo_concurrent_with_radiation:
        components = ["surgery", "concurrent_chemoradiation", "adjuvant_chemotherapy"]
    else:
        components = ["surgery", "radiation", "chemotherapy"]
```

**Pattern 4: Clinical Trial Enrollment**
```python
if "clinical trial" in care_plan_title or medication_name not in standard_drugs:
    is_clinical_trial = True
    evidence_level = "experimental"
    # Still preserve all individual administrations
```

**Pattern 5: Treatment Intent Transitions**
```python
intent_trajectory = {
    "curative → palliative": "Disease progression",
    "curative → hospice": "End-of-life transition",
    "palliative → experimental": "Clinical trial enrollment after standard failure",
    "experimental → standard_of_care": "Trial discontinuation, return to standard therapy"
}
```

---

## Implementation Phases

### Phase 5.0.1: Treatment Line Detection
**Timeline:** Week 1-2
**Deliverable:** Claude algorithm to detect treatment line boundaries
**Testing:** Validate on 10 patients with known treatment histories

### Phase 5.0.2: Regimen Matching (Chemotherapy)
**Timeline:** Week 3
**Deliverable:** Knowledge base of pediatric CNS chemotherapy protocols + matching algorithm
**Testing:** Compare Claude's regimen classification to clinical coordinator's manual review

### Phase 5.0.2b: Radiation Regimen Grouping
**Timeline:** Week 4
**Deliverable:** Knowledge base of radiation regimens + phase detection algorithm
**Testing:** Validate multi-phase radiation grouping (e.g., CSI + boost) against radiation oncology documentation
**Special Cases:**
- Craniospinal irradiation with boost (medulloblastoma)
- Focal definitive radiation (glioma)
- Stereotactic radiosurgery (SRS/SBRT)
- Re-irradiation for recurrence

### Phase 5.0.3: Cycle Grouping
**Timeline:** Week 5
**Deliverable:** Cycle detection for common chemotherapy schedules (q21, q28, weekly, daily)
**Testing:** Verify cycle counts match care plan documentation

### Phase 5.0.4: Response Integration
**Timeline:** Week 6
**Deliverable:** Link imaging assessments to treatment lines
**Testing:** Validate PFS calculations against chart review

### Phase 5.0.5: Endpoint Calculation
**Timeline:** Week 7
**Deliverable:** Standardized metrics (PFS, TTP, OS)
**Testing:** Compare to existing clinical trial datasets

### Phase 5.0.6: Clinical Summary V2
**Timeline:** Week 8
**Deliverable:** New clinical summary showing therapeutic approaches
**Testing:** Present to clinical coordinators for usability feedback

---

## Success Metrics

### Primary Metrics

1. **Regimen Classification Accuracy:** >90% agreement with clinical coordinator manual review
2. **Treatment Line Detection:** >95% accuracy identifying line boundaries
3. **Cycle Count Accuracy:** 100% match to protocol documentation
4. **Cross-Patient Comparability:** Ability to build cohorts matching ≥3 clinical criteria

### Secondary Metrics

1. **Data Preservation:** 100% of V4.8 granular data retained in V5.0 artifact
2. **Performance:** V5.0 abstraction adds <10% to total runtime
3. **Usability:** Clinical coordinators can answer comparative queries without SQL knowledge

---

## V5.0 Artifact Example: Complete Patient

See Appendix A for full JSON example of patient eQSB0y3q... with:
- 3 treatment lines (Stupp → Nivolumab → Etoposide)
- 26 individual chemotherapy administrations
- Response assessments linked to each line
- Clinical endpoints calculated
- All V4.8 granular data preserved

---

## Appendix A: Full V5.0 Artifact Example

```json
{
  "patient_id": "eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83",
  "abstraction_timestamp": "2025-11-08T16:18:00Z",

  "who_2021_classification": {
    "who_2021_diagnosis": "Astrocytoma, IDH-mutant, CNS WHO grade 3",
    "grade": 3,
    "molecular_subtype": "IDH-mutant astrocytoma",
    "key_markers": "IDH1 mutation (R132H)",
    "confidence": "high",
    "classification_date": "2025-11-03"
  },

  "patient_demographics": {
    "pd_age_years": "20",
    "pd_gender": "male",
    "pd_birth_date": "2005-04-18"
  },

  "therapeutic_approach": {
    "diagnosis_date": "2017-09-27",
    "treatment_intent_overall": "curative_converted_to_palliative",

    "lines_of_therapy": [
      {
        "line_number": 1,
        "line_name": "First-line Standard of Care (Modified Stupp Protocol)",
        "treatment_intent": "curative",
        "start_date": "2017-09-27",
        "end_date": "2018-04-05",
        "days_from_diagnosis": 0,
        "duration_days": 191,
        "status": "completed",

        "regimen": {
          "regimen_name": "Modified Stupp Protocol (TMZ + RT)",
          "protocol_reference": "Stupp et al. NEJM 2005",
          "match_confidence": "high",
          "evidence_level": "standard_of_care",
          "deviations_from_protocol": [
            {
              "deviation": "Radiation dose 54 Gy vs standard 60 Gy",
              "rationale": "Pediatric age consideration",
              "clinical_significance": "acceptable_variation"
            }
          ],

          "components": [
            {
              "component_id": "stupp_surgery",
              "component_type": "surgery",
              "timing": "upfront",
              "date": "2017-09-27",
              "procedure_name": "Craniotomy with tumor resection",
              "extent_of_resection": "partial",
              "institution": "Children's Hospital of Philadelphia",
              "timeline_event_refs": ["surgery_2017-09-27_1"]
            },
            {
              "component_id": "stupp_concurrent",
              "component_type": "concurrent_chemoradiation",
              "timing": "adjuvant",
              "start_date": "2017-10-05",
              "end_date": "2017-11-16",
              "duration_days": 42,

              "chemotherapy": {
                "drugs": ["temozolomide"],
                "dose": "75 mg/m² daily",
                "route": "oral",
                "frequency": "daily",
                "days_administered": 42,
                "timeline_event_refs": [
                  "chemo_start_2017-10-05_temo_1",
                  "chemo_start_2017-10-05_temo_2",
                  "chemo_start_2017-10-05_temo_3"
                ],
                "individual_administrations": [
                  {
                    "date": "2017-10-05",
                    "episode_drug_names": "temozolomide",
                    "episode_start_datetime": "2017-10-05",
                    "episode_end_datetime": "2017-10-19",
                    "chemo_drug_category": "chemotherapy",
                    "episode_care_plan_title": "Temozolomide",
                    "v48_adjudication_tier": "Tier 2a: raw_medication_start_date"
                  }
                ]
              },

              "radiation": {
                "radiation_course_number": 1,
                "regimen_name": "Focal definitive radiation 54 Gy",
                "treatment_intent": "adjuvant",
                "technique": "3D_conformal",
                "modality": "external_beam",
                "total_dose_gy": 54,
                "fractions_planned": 30,
                "fractions_delivered": 30,
                "dose_per_fraction_gy": 1.8,
                "fractionation_type": "standard",
                "target_volume": "tumor bed + 2cm margin",
                "fields": "focal",
                "start_date": "2017-10-05",
                "end_date": "2017-11-16",
                "timeline_event_refs": ["radiation_start_2017-10-05"],
                "protocol_reference": "Adult glioma standard fractionation",
                "match_confidence": "high",
                "deviations_from_protocol": [
                  {
                    "deviation": "54 Gy vs standard adult 60 Gy",
                    "rationale": "Pediatric age consideration (20 years old)",
                    "clinical_significance": "standard_variation"
                  }
                ],
                "individual_appointments": [
                  {"date": "2017-10-05", "dose_gy": 1.8, "fulfilled": true},
                  {"date": "2017-10-06", "dose_gy": 1.8, "fulfilled": true}
                ]
              }
            },
            {
              "component_id": "stupp_adjuvant",
              "component_type": "adjuvant_chemotherapy",
              "timing": "post_radiation",
              "start_date": "2017-12-14",
              "end_date": "2018-04-05",

              "chemotherapy": {
                "drugs": ["temozolomide"],
                "dose": "150-200 mg/m² days 1-5",
                "schedule": "q28 days",
                "cycles_planned": 6,
                "cycles_completed": 6,
                "cycles_administered": [
                  {
                    "cycle_number": 1,
                    "start_date": "2017-12-14",
                    "end_date": "2017-12-18",
                    "days": "1-5",
                    "timeline_event_refs": ["chemo_2017-12-14"]
                  },
                  {
                    "cycle_number": 2,
                    "start_date": "2018-01-11",
                    "end_date": "2018-01-15",
                    "days": "1-5",
                    "timeline_event_refs": ["chemo_2018-01-11"]
                  }
                ]
              }
            }
          ]
        },

        "response_assessments": [
          {
            "assessment_date": "2017-12-15",
            "days_on_treatment": 79,
            "modality": "MRI brain",
            "rano_response": "stable_disease",
            "timeline_event_refs": ["imaging_2017-12-15"]
          },
          {
            "assessment_date": "2018-03-01",
            "days_on_treatment": 155,
            "modality": "MRI brain",
            "rano_response": "progressive_disease",
            "led_to_line_change": true,
            "timeline_event_refs": ["imaging_2018-03-01"]
          }
        ],

        "discontinuation": {
          "date": "2018-04-05",
          "reason": "disease_progression",
          "evidence": "MRI 2018-03-01 showed progressive disease",
          "best_response_achieved": "stable_disease",
          "progression_free_survival_days": 155,
          "next_line_started": true
        }
      },

      {
        "line_number": 2,
        "line_name": "Second-line Immunotherapy (Experimental)",
        "treatment_intent": "palliative",
        "start_date": "2018-02-22",
        "end_date": "2018-05-03",
        "days_from_diagnosis": 148,
        "duration_days": 70,
        "status": "completed",

        "regimen": {
          "regimen_name": "Nivolumab monotherapy",
          "protocol_reference": "CheckMate 143 pediatric cohort",
          "match_confidence": "medium",
          "evidence_level": "experimental",
          "is_clinical_trial": true,

          "components": [
            {
              "component_type": "immunotherapy",
              "drugs": ["nivolumab"],
              "dose": "3 mg/kg",
              "schedule": "q14 days",
              "cycles_completed": 6,
              "timeline_event_refs": [
                "chemo_start_2018-02-22_nivo_1",
                "chemo_start_2018-03-08_nivo_1"
              ],
              "individual_administrations": [
                {
                  "date": "2018-02-22",
                  "episode_drug_names": "nivolumab",
                  "episode_start_datetime": "2018-02-22",
                  "episode_end_datetime": "2018-02-22",
                  "therapy_end_date": "2018-05-03",
                  "chemo_drug_category": "immunotherapy"
                }
              ]
            }
          ]
        },

        "response_assessments": [
          {
            "assessment_date": "2018-04-15",
            "days_on_treatment": 52,
            "rano_response": "progressive_disease",
            "led_to_line_change": true
          }
        ],

        "discontinuation": {
          "date": "2018-05-03",
          "reason": "disease_progression",
          "progression_free_survival_days": 52,
          "next_line_started": true
        }
      },

      {
        "line_number": 3,
        "line_name": "Third-line Cytotoxic Chemotherapy (Salvage)",
        "treatment_intent": "palliative",
        "start_date": "2018-04-05",
        "end_date": "2018-04-26",
        "days_from_diagnosis": 191,
        "duration_days": 21,
        "status": "completed",

        "regimen": {
          "regimen_name": "Etoposide",
          "protocol_reference": "HGG salvage regimen",
          "match_confidence": "low",
          "evidence_level": "salvage",

          "components": [
            {
              "component_type": "chemotherapy",
              "drugs": ["etoposide"],
              "dose": "100 mg/m² days 1-5",
              "schedule": "q21 days",
              "cycles_planned": null,
              "cycles_completed": 1,
              "cycles_administered": [
                {
                  "cycle_number": 1,
                  "start_date": "2018-04-05",
                  "end_date": "2018-04-10",
                  "timeline_event_refs": ["chemo_2018-04-05_etop"]
                }
              ]
            }
          ]
        },

        "discontinuation": {
          "date": "2018-04-26",
          "reason": "unknown",
          "evidence": "Only 1 cycle documented, no further treatment",
          "next_line_started": false
        }
      }
    ],

    "clinical_endpoints": {
      "diagnosis_date": "2017-09-27",
      "follow_up_duration_days": 400,

      "overall_metrics": {
        "number_of_treatment_lines": 3,
        "time_to_first_progression_days": 155,
        "overall_survival_days": null,
        "overall_survival_status": "unknown"
      },

      "per_line_metrics": [
        {
          "line_number": 1,
          "regimen_name": "Modified Stupp Protocol",
          "start_days_from_diagnosis": 0,
          "duration_days": 191,
          "progression_free_survival_days": 155,
          "best_response": "stable_disease",
          "reason_for_discontinuation": "disease_progression"
        },
        {
          "line_number": 2,
          "regimen_name": "Nivolumab monotherapy",
          "start_days_from_diagnosis": 148,
          "duration_days": 70,
          "progression_free_survival_days": 52,
          "best_response": "progressive_disease",
          "reason_for_discontinuation": "disease_progression"
        },
        {
          "line_number": 3,
          "regimen_name": "Etoposide",
          "start_days_from_diagnosis": 191,
          "duration_days": 21,
          "progression_free_survival_days": null,
          "best_response": "unknown",
          "reason_for_discontinuation": "unknown"
        }
      ]
    }
  },

  "timeline_events": [
    {
      "event_id": "surgery_2017-09-27_1",
      "event_type": "surgery",
      "event_date": "2017-09-27",
      "extent_of_resection": "partial"
    },
    {
      "event_id": "chemo_start_2017-10-05_temo_1",
      "event_type": "chemotherapy_start",
      "event_date": "2017-10-05",
      "episode_drug_names": "temozolomide",
      "episode_start_datetime": "2017-10-05",
      "episode_end_datetime": "2017-10-19"
    }
  ],

  "extraction_gaps": [],
  "binary_extractions": [],
  "timeline_construction_metadata": {}
}
```

---

## Questions for Clinical Coordinators

Before implementation, we need clinical coordinator input on:

1. **Regimen Naming:** How should we name regimens that don't match standard protocols?
2. **Line Change Detection:** What temporal gap justifies a new treatment line? (We proposed 30 days)
3. **Cycle Definition:** For oral agents like TMZ, how do you define a "cycle"?
4. **Response Assessment:** Should we use RANO, RECIST, clinical judgment, or combination?
5. **Incomplete Data:** How should we handle patients with partial treatment documentation?

---

**Document Version:** 1.1
**Last Updated:** November 9, 2025
**Changes in v1.1:**
- Added explicit radiation treatment grouping framework (Phase 5.0.2b)
- Added generalizable Claude prompts for treatment line detection and regimen matching
- Added 5 complete cross-tumor-type examples (medulloblastoma, glioblastoma, DIPG, ependymoma, low-grade glioma)
- Added radiation knowledge base with dose/fractionation patterns
- Added key generalizable patterns for edge cases (no surgery, surgery-only, clinical trials)
- Enhanced radiation schema in Appendix A with full regimen details

**Next Review:** After clinical coordinator feedback
