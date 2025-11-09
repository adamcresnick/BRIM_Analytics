#!/usr/bin/env python3
"""
V5.0: Therapeutic Approach Abstractor

Transforms V4.8 timeline events into hierarchical therapeutic approaches:
- Treatment Lines
- Regimens (matched to known protocols)
- Cycles (for chemotherapy)
- Radiation Courses and Phases
- Response Assessments
- Clinical Endpoints

All V4.8 granular data is preserved as subelements.

Design document: docs/V5_0_THERAPEUTIC_APPROACH_FRAMEWORK.md
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict
import re


# ============================================================================
# PROTOCOL KNOWLEDGE BASES
# ============================================================================

PEDIATRIC_CNS_PROTOCOLS = {
    "stupp_protocol": {
        "name": "Modified Stupp Protocol",
        "reference": "Stupp et al. NEJM 2005",
        "indications": ["IDH-mutant astrocytoma", "glioblastoma", "anaplastic astrocytoma"],
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
                    "dose_gy": [54, 60],
                    "fractions": 30,
                    "dose_per_fraction": [1.8, 2.0]
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
        "expected_duration_days": [168, 196]
    },

    "cog_acns0331": {
        "name": "COG ACNS0331 (Medulloblastoma)",
        "reference": "Children's Oncology Group ACNS0331",
        "indications": ["medulloblastoma"],
        "evidence_level": "standard_of_care",
        "components": {
            "surgery": {"required": True, "timing": "upfront"},
            "radiation": {
                "type": "craniospinal",
                "csi_dose_gy": [23.4, 36.0],
                "boost_dose_gy": [30.6, 23.4],
                "total_dose_gy": 54
            },
            "concurrent_chemotherapy": {
                "drugs": ["vincristine"],
                "schedule": "weekly"
            },
            "maintenance_chemotherapy": {
                "drugs": ["cisplatin", "vincristine", "cyclophosphamide"],
                "cycles": 6
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


RADIATION_REGIMENS = {
    "pediatric_focal_definitive": {
        "name": "Pediatric focal definitive radiation",
        "indications": ["high-grade glioma", "ependymoma", "low-grade glioma"],
        "age_range": [0, 21],
        "dose_range_gy": [50.4, 59.4],
        "fractions": [28, 33],
        "dose_per_fraction_gy": 1.8,
        "target": "tumor bed + margin",
        "concurrent_chemo_common": True
    },

    "craniospinal_with_boost": {
        "name": "Craniospinal irradiation with boost",
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
                "dose_gy": [19.8, 30.6],
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
    }
}


# Drug class mapping for treatment line detection
DRUG_CLASSES = {
    "temozolomide": "alkylating_agent",
    "lomustine": "alkylating_agent",
    "carmustine": "alkylating_agent",
    "cyclophosphamide": "alkylating_agent",
    "nivolumab": "immunotherapy",
    "pembrolizumab": "immunotherapy",
    "bevacizumab": "targeted_therapy",
    "etoposide": "topoisomerase_inhibitor",
    "vincristine": "vinca_alkaloid",
    "cisplatin": "platinum_agent",
    "carboplatin": "platinum_agent"
}


# ============================================================================
# PHASE 5.0.1: TREATMENT LINE DETECTION
# ============================================================================

def detect_treatment_lines(
    timeline_events: List[Dict[str, Any]],
    diagnosis_date: str,
    diagnosis: str
) -> List[Dict[str, Any]]:
    """
    Group timeline events into treatment lines based on:
    - Temporal gaps with imaging progression
    - Drug class changes
    - Recurrence/salvage surgery
    - Treatment intent changes

    Returns list of treatment lines with events grouped.
    """
    if not timeline_events:
        return []

    # Sort events chronologically
    events = sorted(
        [e for e in timeline_events if e.get('event_date')],
        key=lambda x: x['event_date']
    )

    if not events:
        return []

    lines = []
    current_line = None

    for event in events:
        event_date = event.get('event_date')
        event_type = event.get('event_type', '')

        # First event starts Line 1
        if current_line is None:
            current_line = {
                'line_number': 1,
                'start_date': event_date,
                'events': [event],
                'drugs_used': set(),
                'drug_classes': set(),
                'reason_for_change': 'initial_diagnosis'
            }
            _add_drug_info(event, current_line)
            continue

        # Check if this event should start a new line
        if _is_new_treatment_line(event, current_line, events, timeline_events):
            # Save current line
            current_line['end_date'] = current_line['events'][-1].get('event_date')
            lines.append(current_line)

            # Start new line
            reason = _detect_line_change_reason(event, current_line, timeline_events)
            current_line = {
                'line_number': len(lines) + 1,
                'start_date': event_date,
                'events': [event],
                'drugs_used': set(),
                'drug_classes': set(),
                'reason_for_change': reason
            }
            _add_drug_info(event, current_line)
        else:
            # Add to current line
            current_line['events'].append(event)
            _add_drug_info(event, current_line)

    # Add final line
    if current_line:
        current_line['end_date'] = current_line['events'][-1].get('event_date')
        lines.append(current_line)

    # Calculate days from diagnosis for each line
    dx_date = datetime.fromisoformat(diagnosis_date.replace('Z', '+00:00'))
    for line in lines:
        line_start = datetime.fromisoformat(line['start_date'].replace('Z', '+00:00'))
        line['days_from_diagnosis'] = (line_start - dx_date).days

        if line.get('end_date'):
            line_end = datetime.fromisoformat(line['end_date'].replace('Z', '+00:00'))
            line['duration_days'] = (line_end - line_start).days
        else:
            line['duration_days'] = None

        # Convert sets to lists for JSON serialization
        line['drugs_used'] = sorted(list(line['drugs_used']))
        line['drug_classes'] = sorted(list(line['drug_classes']))

    return lines


def _add_drug_info(event: Dict[str, Any], line: Dict[str, Any]):
    """Extract drug names and classes from event and add to line."""
    if event.get('event_type', '').startswith('chemotherapy'):
        drugs = event.get('episode_drug_names', '')
        if drugs:
            for drug in str(drugs).lower().split(','):
                drug = drug.strip()
                if drug:
                    line['drugs_used'].add(drug)
                    drug_class = DRUG_CLASSES.get(drug, 'other')
                    line['drug_classes'].add(drug_class)


def _is_new_treatment_line(
    event: Dict[str, Any],
    current_line: Dict[str, Any],
    all_events: List[Dict[str, Any]],
    timeline_events: List[Dict[str, Any]]
) -> bool:
    """
    Determine if event should start a new treatment line.

    Signals for new line:
    1. Gap >30 days + imaging progression
    2. Drug class change after progression
    3. Salvage surgery
    4. Explicit line change indicators
    """
    event_date_str = event.get('event_date')
    event_type = event.get('event_type', '')

    if not event_date_str or not current_line.get('events'):
        return False

    event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
    last_event_date = datetime.fromisoformat(
        current_line['events'][-1].get('event_date').replace('Z', '+00:00')
    )

    gap_days = (event_date - last_event_date).days

    # Signal 1: Large temporal gap with progression
    if gap_days > 30:
        # Check for imaging showing progression between events
        has_progression = _has_progression_imaging_between(
            last_event_date.isoformat(),
            event_date.isoformat(),
            timeline_events
        )
        if has_progression:
            return True

    # Signal 2: Drug class change
    if event_type.startswith('chemotherapy'):
        event_drugs = set()
        drugs_str = event.get('episode_drug_names', '')
        for drug in str(drugs_str).lower().split(','):
            drug = drug.strip()
            if drug:
                event_drug_class = DRUG_CLASSES.get(drug, 'other')
                event_drugs.add(event_drug_class)

        if event_drugs and current_line['drug_classes']:
            # If completely different drug classes, likely new line
            if not event_drugs.intersection(current_line['drug_classes']):
                # But only if there's evidence of progression or gap
                if gap_days > 14 or _has_progression_imaging_between(
                    last_event_date.isoformat(),
                    event_date.isoformat(),
                    timeline_events
                ):
                    return True

    # Signal 3: Surgery after initial treatment (salvage)
    if event_type == 'surgery' and current_line['line_number'] >= 1:
        # If we've had chemo/radiation already, surgery is likely salvage
        if current_line['events']:
            prior_types = {e.get('event_type') for e in current_line['events']}
            if any(t.startswith(('chemotherapy', 'radiation')) for t in prior_types):
                # This is salvage surgery
                return True

    return False


def _has_progression_imaging_between(
    start_date: str,
    end_date: str,
    timeline_events: List[Dict[str, Any]]
) -> bool:
    """Check if there's imaging showing progression between two dates."""
    start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

    for event in timeline_events:
        if event.get('event_type') != 'imaging':
            continue

        event_date_str = event.get('event_date')
        if not event_date_str:
            continue

        event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))

        if start <= event_date <= end:
            # Check for progression indicators
            rano = event.get('rano_assessment', '').lower()
            conclusion = str(event.get('report_conclusion', '')).lower()

            if 'progressive' in rano or 'progression' in conclusion:
                return True

    return False


def _detect_line_change_reason(
    event: Dict[str, Any],
    prior_line: Dict[str, Any],
    timeline_events: List[Dict[str, Any]]
) -> str:
    """Classify reason for treatment line change."""
    event_type = event.get('event_type', '')

    # Check for progression imaging
    if prior_line.get('end_date'):
        has_progression = _has_progression_imaging_between(
            prior_line['start_date'],
            event.get('event_date'),
            timeline_events
        )
        if has_progression:
            return "disease_progression"

    # Check for surgery (salvage)
    if event_type == 'surgery' and prior_line['line_number'] > 1:
        return "disease_progression"

    # Check for drug class change (often indicates progression)
    if event_type.startswith('chemotherapy'):
        return "disease_progression"  # Conservative assumption

    return "protocol_completion"


# ============================================================================
# PHASE 5.0.2: REGIMEN MATCHING (CHEMOTHERAPY)
# ============================================================================

def match_regimen_to_protocol(
    line_events: List[Dict[str, Any]],
    diagnosis: str,
    patient_age: int
) -> Dict[str, Any]:
    """
    Match observed treatment components to known protocols.

    Returns regimen match with confidence score and deviations.
    """
    # Extract components from events
    components = _extract_treatment_components(line_events)

    # Try to match against known protocols
    best_match = None
    best_score = 0.0

    for protocol_id, protocol in PEDIATRIC_CNS_PROTOCOLS.items():
        # Check diagnosis match
        indication_match = any(
            ind.lower() in diagnosis.lower()
            for ind in protocol.get('indications', [])
        )

        if not indication_match:
            continue

        # Score component matching
        score, deviations = _score_protocol_match(components, protocol)

        if score > best_score:
            best_score = score
            best_match = {
                'protocol_id': protocol_id,
                'regimen_name': protocol['name'],
                'protocol_reference': protocol.get('reference', ''),
                'match_confidence': _confidence_from_score(score),
                'evidence_level': protocol.get('evidence_level', 'unknown'),
                'deviations_from_protocol': deviations
            }

    if not best_match:
        # No protocol match - describe observed regimen
        best_match = {
            'protocol_id': None,
            'regimen_name': _describe_observed_regimen(components),
            'protocol_reference': 'No standard protocol match',
            'match_confidence': 'no_match',
            'evidence_level': 'unknown',
            'deviations_from_protocol': []
        }

    return best_match


def _extract_treatment_components(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract surgery, chemo, radiation components from events."""
    components = {
        'has_surgery': False,
        'has_chemotherapy': False,
        'has_radiation': False,
        'chemo_drugs': set(),
        'radiation_dose_gy': None,
        'concurrent_chemoradiation': False
    }

    chemo_dates = []
    radiation_dates = []

    for event in events:
        event_type = event.get('event_type', '')
        event_date = event.get('event_date')

        if event_type == 'surgery':
            components['has_surgery'] = True

        elif event_type.startswith('chemotherapy'):
            components['has_chemotherapy'] = True
            drugs = str(event.get('episode_drug_names', '')).lower()
            for drug in drugs.split(','):
                drug = drug.strip()
                if drug:
                    components['chemo_drugs'].add(drug)
            if event_date:
                chemo_dates.append(event_date)

        elif event_type.startswith('radiation'):
            components['has_radiation'] = True
            dose = event.get('total_dose_cgy')
            if dose:
                components['radiation_dose_gy'] = float(dose) / 100.0
            if event_date:
                radiation_dates.append(event_date)

    # Check for concurrent chemoradiation (dates overlap)
    if chemo_dates and radiation_dates:
        chemo_start = min(chemo_dates)
        chemo_end = max(chemo_dates)
        rad_start = min(radiation_dates)
        rad_end = max(radiation_dates)

        # If they overlap, likely concurrent
        if not (chemo_end < rad_start or rad_end < chemo_start):
            components['concurrent_chemoradiation'] = True

    components['chemo_drugs'] = sorted(list(components['chemo_drugs']))
    return components


def _score_protocol_match(
    components: Dict[str, Any],
    protocol: Dict[str, Any]
) -> Tuple[float, List[Dict[str, str]]]:
    """Score how well observed components match protocol. Returns (score, deviations)."""
    score = 0.0
    deviations = []
    protocol_components = protocol.get('components', {})

    # Surgery match (20 points)
    if protocol_components.get('surgery', {}).get('required'):
        if components['has_surgery']:
            score += 20
        else:
            deviations.append({
                'deviation': 'No surgery documented',
                'rationale': 'Protocol requires surgery',
                'clinical_significance': 'protocol_deviation'
            })

    # Chemotherapy match (30 points)
    protocol_drugs = set()
    for comp_name, comp_spec in protocol_components.items():
        if 'chemotherapy' in comp_name.lower():
            drugs = comp_spec.get('drugs', [])
            protocol_drugs.update([d.lower() for d in drugs])

    if protocol_drugs:
        observed_drugs = set(components['chemo_drugs'])
        if observed_drugs.intersection(protocol_drugs):
            score += 30
        else:
            deviations.append({
                'deviation': f"Drugs used: {', '.join(observed_drugs)} vs protocol: {', '.join(protocol_drugs)}",
                'rationale': 'Different chemotherapy agents',
                'clinical_significance': 'protocol_deviation'
            })

    # Radiation match (30 points)
    if protocol_components.get('concurrent_chemoradiation', {}).get('required') or \
       protocol_components.get('radiation'):
        if components['has_radiation']:
            score += 30

            # Check dose match
            protocol_radiation = protocol_components.get('concurrent_chemoradiation', {}).get('radiation', {})
            if not protocol_radiation:
                protocol_radiation = protocol_components.get('radiation', {})

            expected_dose = protocol_radiation.get('dose_gy')
            if expected_dose and components['radiation_dose_gy']:
                if isinstance(expected_dose, list):
                    dose_min, dose_max = expected_dose
                else:
                    dose_min = dose_max = expected_dose

                actual_dose = components['radiation_dose_gy']
                if dose_min <= actual_dose <= dose_max:
                    score += 20  # Bonus for dose match
                else:
                    deviations.append({
                        'deviation': f"Radiation {actual_dose} Gy vs protocol {dose_min}-{dose_max} Gy",
                        'rationale': 'Dose modification',
                        'clinical_significance': 'standard_variation'
                    })
        else:
            deviations.append({
                'deviation': 'No radiation documented',
                'rationale': 'Protocol includes radiation',
                'clinical_significance': 'protocol_deviation'
            })

    return score, deviations


def _confidence_from_score(score: float) -> str:
    """Convert numeric score to confidence level."""
    if score >= 90:
        return "high"
    elif score >= 70:
        return "medium"
    elif score >= 50:
        return "low"
    else:
        return "no_match"


def _describe_observed_regimen(components: Dict[str, Any]) -> str:
    """Generate descriptive name for observed regimen."""
    parts = []

    if components['has_surgery']:
        parts.append("Surgery")

    if components['chemo_drugs']:
        drugs_str = " + ".join(sorted(components['chemo_drugs'])[:3])  # Limit to 3 drugs
        if components['concurrent_chemoradiation']:
            parts.append(f"{drugs_str} + RT (concurrent)")
        else:
            parts.append(drugs_str)

    if components['has_radiation'] and not components['concurrent_chemoradiation']:
        if components['radiation_dose_gy']:
            parts.append(f"RT {components['radiation_dose_gy']:.1f} Gy")
        else:
            parts.append("RT")

    if not parts:
        return "Unknown regimen"

    return " → ".join(parts)


# ============================================================================
# PHASE 5.0.2b: RADIATION TREATMENT GROUPING
# ============================================================================

def group_radiation_treatments(
    line_events: List[Dict[str, Any]],
    diagnosis: str,
    patient_age: int
) -> List[Dict[str, Any]]:
    """
    Group radiation events into courses and phases.

    Returns list of radiation courses with phase detection.
    """
    radiation_events = [
        e for e in line_events
        if e.get('event_type', '').startswith('radiation')
    ]

    if not radiation_events:
        return []

    # Sort by date
    radiation_events = sorted(radiation_events, key=lambda e: e.get('event_date', ''))

    courses = []
    current_course = None

    for event in radiation_events:
        event_date = event.get('event_date')

        if current_course is None:
            # Start first course
            current_course = {
                'course_number': 1,
                'events': [event],
                'start_date': event_date
            }
        else:
            # Check if this starts a new course (gap >60 days)
            last_date = parse_date(current_course['events'][-1].get('event_date'))
            this_date = parse_date(event_date)

            if last_date and this_date and (this_date - last_date).days > 60:
                # Save current course
                courses.append(_finalize_radiation_course(current_course, diagnosis, patient_age))

                # Start new course
                current_course = {
                    'course_number': len(courses) + 1,
                    'events': [event],
                    'start_date': event_date
                }
            else:
                # Add to current course
                current_course['events'].append(event)

    # Finalize last course
    if current_course:
        courses.append(_finalize_radiation_course(current_course, diagnosis, patient_age))

    return courses


def _finalize_radiation_course(
    course: Dict[str, Any],
    diagnosis: str,
    patient_age: int
) -> Dict[str, Any]:
    """Finalize radiation course with regimen matching and phase detection."""
    events = course['events']

    # Calculate total dose
    total_dose_gy = 0.0
    total_fractions = 0

    for event in events:
        dose_cgy = event.get('total_dose_cgy', 0) or 0
        total_dose_gy += float(dose_cgy) / 100.0

        fractions = event.get('fractions', 0) or 0
        total_fractions += int(fractions) if fractions else 0

    dose_per_fraction = total_dose_gy / total_fractions if total_fractions > 0 else None

    # Classify fractionation type
    if dose_per_fraction:
        if dose_per_fraction >= 5.0:
            fractionation_type = "stereotactic"
        elif dose_per_fraction >= 2.5:
            fractionation_type = "hypofractionated"
        elif 1.8 <= dose_per_fraction <= 2.0:
            fractionation_type = "standard"
        else:
            fractionation_type = "unknown"
    else:
        fractionation_type = "unknown"

    # Match to radiation regimen
    regimen_match = _match_radiation_regimen(
        total_dose_gy,
        total_fractions,
        dose_per_fraction,
        diagnosis,
        patient_age
    )

    return {
        'radiation_course_number': course['course_number'],
        'regimen_name': regimen_match.get('regimen_name', 'Radiation therapy'),
        'treatment_intent': 'adjuvant',  # Would need more logic to determine
        'total_dose_gy': total_dose_gy,
        'fractions_delivered': total_fractions,
        'dose_per_fraction_gy': dose_per_fraction,
        'fractionation_type': fractionation_type,
        'start_date': course['start_date'],
        'end_date': events[-1].get('event_date') if events else None,
        'protocol_reference': regimen_match.get('protocol_reference', ''),
        'match_confidence': regimen_match.get('match_confidence', 'low'),
        'timeline_event_refs': [e.get('event_id', '') for e in events],
        'individual_events': events
    }


def _match_radiation_regimen(
    total_dose_gy: float,
    fractions: int,
    dose_per_fraction: Optional[float],
    diagnosis: str,
    patient_age: int
) -> Dict[str, str]:
    """Match radiation parameters to known regimens."""
    for regimen_id, regimen in RADIATION_REGIMENS.items():
        # Check age range
        age_range = regimen.get('age_range', [0, 100])
        if not (age_range[0] <= patient_age <= age_range[1]):
            continue

        # Check indication
        indications = regimen.get('indications', [])
        if not any(ind.lower() in diagnosis.lower() for ind in indications):
            continue

        # Check dose match
        dose_range = regimen.get('dose_range_gy')
        target_dose = regimen.get('dose_gy')

        if dose_range:
            if dose_range[0] <= total_dose_gy <= dose_range[1]:
                return {
                    'regimen_name': regimen['name'],
                    'protocol_reference': regimen.get('name', ''),
                    'match_confidence': 'high'
                }
        elif target_dose:
            if abs(total_dose_gy - target_dose) < 5:  # Within 5 Gy
                return {
                    'regimen_name': regimen['name'],
                    'protocol_reference': regimen.get('name', ''),
                    'match_confidence': 'high'
                }

    # No match
    return {
        'regimen_name': f"Radiation {total_dose_gy:.1f} Gy in {fractions} fractions",
        'protocol_reference': 'No standard regimen match',
        'match_confidence': 'low'
    }


# ============================================================================
# PHASE 5.0.3: CYCLE DETECTION
# ============================================================================

def detect_chemotherapy_cycles(
    chemo_events: List[Dict[str, Any]],
    expected_schedule: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Group individual chemotherapy administrations into cycles.

    For example, temozolomide "days 1-5 q28 days" groups into distinct cycles.
    """
    if not chemo_events:
        return []

    # Sort by date
    chemo_events = sorted(chemo_events, key=lambda e: e.get('event_date', ''))

    cycles = []
    current_cycle = None

    for event in chemo_events:
        event_date = event.get('event_date')

        if current_cycle is None:
            # Start first cycle
            current_cycle = {
                'cycle_number': 1,
                'start_date': event_date,
                'administrations': [event]
            }
            continue

        # Check if this belongs to current cycle or starts new one
        last_date = parse_date(current_cycle['administrations'][-1].get('event_date'))
        this_date = parse_date(event_date)

        if not last_date or not this_date:
            current_cycle['administrations'].append(event)
            continue

        days_since_cycle_start = (this_date - parse_date(current_cycle['start_date'])).days

        # If within 7 days of cycle start, same cycle
        # If >7 days, new cycle
        if days_since_cycle_start <= 7:
            current_cycle['administrations'].append(event)
        else:
            # Finalize current cycle
            current_cycle['end_date'] = current_cycle['administrations'][-1].get('event_date')
            current_cycle['days_administered'] = len(current_cycle['administrations'])
            cycles.append(current_cycle)

            # Start new cycle
            current_cycle = {
                'cycle_number': len(cycles) + 1,
                'start_date': event_date,
                'administrations': [event]
            }

    # Finalize last cycle
    if current_cycle:
        current_cycle['end_date'] = current_cycle['administrations'][-1].get('event_date')
        current_cycle['days_administered'] = len(current_cycle['administrations'])
        cycles.append(current_cycle)

    return cycles


# ============================================================================
# PHASE 5.0.4: RESPONSE ASSESSMENT INTEGRATION
# ============================================================================

def integrate_response_assessments(
    line_start_date: str,
    line_end_date: Optional[str],
    timeline_events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Find imaging assessments during treatment line and extract RANO responses.
    """
    start = parse_date(line_start_date)
    end = parse_date(line_end_date) if line_end_date else datetime.now()

    if not start:
        return []

    assessments = []

    for event in timeline_events:
        if event.get('event_type') != 'imaging':
            continue

        event_date = parse_date(event.get('event_date'))
        if not event_date:
            continue

        if start <= event_date <= end:
            days_on_treatment = (event_date - start).days

            assessment = {
                'assessment_date': event.get('event_date'),
                'days_on_treatment': days_on_treatment,
                'modality': event.get('imaging_type', 'MRI'),
                'rano_response': event.get('rano_assessment'),
                'report_conclusion': event.get('report_conclusion'),
                'timeline_event_ref': event.get('event_id')
            }

            # Check if this led to line change
            if event.get('rano_assessment', '').lower() in ['progressive_disease', 'progressive disease']:
                assessment['led_to_line_change'] = True
            else:
                assessment['led_to_line_change'] = False

            assessments.append(assessment)

    return sorted(assessments, key=lambda a: a['assessment_date'])


# ============================================================================
# PHASE 5.0.5: CLINICAL ENDPOINTS CALCULATION
# ============================================================================

def calculate_clinical_endpoints(
    lines_of_therapy: List[Dict[str, Any]],
    diagnosis_date: str
) -> Dict[str, Any]:
    """
    Calculate standard oncology endpoints: PFS, TTP, OS per line and overall.
    """
    dx_date = parse_date(diagnosis_date)
    if not dx_date:
        return {}

    per_line_metrics = []
    time_to_first_progression = None

    for line in lines_of_therapy:
        line_num = line.get('line_number')
        regimen_name = line.get('regimen', {}).get('regimen_name', 'Unknown')
        start_date = parse_date(line.get('start_date'))
        duration_days = line.get('duration_days')

        # Calculate PFS for this line
        pfs_days = None
        best_response = None
        reason_for_discontinuation = line.get('discontinuation', {}).get('reason')

        if line.get('discontinuation'):
            pfs_days = line['discontinuation'].get('progression_free_survival_days')

        # Get best response from assessments
        if line.get('response_assessments'):
            responses = [a.get('rano_response') for a in line['response_assessments'] if a.get('rano_response')]
            if responses:
                # Best response: CR > PR > SD > PD
                if any('complete' in r.lower() for r in responses):
                    best_response = 'complete_response'
                elif any('partial' in r.lower() for r in responses):
                    best_response = 'partial_response'
                elif any('stable' in r.lower() for r in responses):
                    best_response = 'stable_disease'
                else:
                    best_response = 'progressive_disease'

        per_line_metrics.append({
            'line_number': line_num,
            'regimen_name': regimen_name,
            'start_days_from_diagnosis': line.get('days_from_diagnosis'),
            'duration_days': duration_days,
            'progression_free_survival_days': pfs_days,
            'best_response': best_response,
            'reason_for_discontinuation': reason_for_discontinuation
        })

        # Track first progression
        if pfs_days and time_to_first_progression is None:
            time_to_first_progression = line.get('days_from_diagnosis', 0) + pfs_days

    return {
        'diagnosis_date': diagnosis_date,
        'overall_metrics': {
            'number_of_treatment_lines': len(lines_of_therapy),
            'time_to_first_progression_days': time_to_first_progression,
            'overall_survival_days': None,  # Would need vital status
            'overall_survival_status': 'unknown'
        },
        'per_line_metrics': per_line_metrics
    }


# ============================================================================
# MAIN ORCHESTRATOR: BUILD THERAPEUTIC APPROACH
# ============================================================================

def build_therapeutic_approach(
    artifact: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main orchestrator function that builds the complete therapeutic approach
    from V4.8 timeline events.

    This is the entry point called from patient_timeline_abstraction_V3.py
    """
    timeline_events = artifact.get('timeline_events', [])
    who_classification = artifact.get('who_2021_classification', {})
    demographics = artifact.get('patient_demographics', {})

    diagnosis = who_classification.get('who_2021_diagnosis', 'Unknown')
    diagnosis_date = who_classification.get('classification_date')
    patient_age = int(demographics.get('pd_age_years', 0)) if demographics.get('pd_age_years') else 0

    if not timeline_events or not diagnosis_date:
        return None

    # Phase 5.0.1: Detect treatment lines
    lines = detect_treatment_lines(timeline_events, diagnosis_date, diagnosis)

    # Process each line
    lines_of_therapy = []

    for line in lines:
        line_events = line.get('events', [])

        # Phase 5.0.2: Match regimen
        regimen_match = match_regimen_to_protocol(line_events, diagnosis, patient_age)

        # Phase 5.0.2b: Group radiation
        radiation_courses = group_radiation_treatments(line_events, diagnosis, patient_age)

        # Phase 5.0.3: Detect cycles for chemotherapy
        chemo_events = [e for e in line_events if e.get('event_type', '').startswith('chemotherapy')]
        cycles = detect_chemotherapy_cycles(chemo_events)

        # Phase 5.0.4: Integrate response assessments
        response_assessments = integrate_response_assessments(
            line.get('start_date'),
            line.get('end_date'),
            timeline_events
        )

        # Build line structure
        line_of_therapy = {
            'line_number': line.get('line_number'),
            'line_name': f"Line {line.get('line_number')}: {regimen_match.get('regimen_name')}",
            'treatment_intent': 'curative' if line.get('line_number') == 1 else 'palliative',
            'start_date': line.get('start_date'),
            'end_date': line.get('end_date'),
            'days_from_diagnosis': line.get('days_from_diagnosis'),
            'duration_days': line.get('duration_days'),
            'status': 'completed' if line.get('end_date') else 'ongoing',
            'reason_for_change': line.get('reason_for_change'),
            'regimen': regimen_match,
            'chemotherapy_cycles': cycles if cycles else [],
            'radiation_courses': radiation_courses if radiation_courses else [],
            'response_assessments': response_assessments,
            'timeline_event_refs': [e.get('event_id', '') for e in line_events if e.get('event_id')]
        }

        lines_of_therapy.append(line_of_therapy)

    # Phase 5.0.5: Calculate clinical endpoints
    clinical_endpoints = calculate_clinical_endpoints(lines_of_therapy, diagnosis_date)

    # Build therapeutic approach
    therapeutic_approach = {
        'diagnosis_date': diagnosis_date,
        'treatment_intent_overall': 'curative',  # Could be refined based on line progression
        'lines_of_therapy': lines_of_therapy,
        'clinical_endpoints': clinical_endpoints
    }

    return therapeutic_approach


# ============================================================================
# Helper function
# ============================================================================

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return None
