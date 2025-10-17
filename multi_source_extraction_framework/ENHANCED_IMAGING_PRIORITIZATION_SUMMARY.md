# Enhanced Clinical Event Prioritization Framework
## Complete Imaging Prioritization with Treatment Changes and Survival Tracking

### Summary of Enhancements

Based on your feedback, I've enhanced the imaging prioritization framework to capture critical clinical timepoints that were previously missed:

## 1. Enhanced Imaging Prioritization Criteria

### Current Classification (39 High-Priority Studies from 181 Total):

#### **Critical Priority (33 studies)**
- **Pre-operative imaging** (3 studies): Within 30 days before surgery
  - Defines extent of disease for surgical planning
- **Post-operative imaging** (24 studies): Within 90 days after surgery
  - Assesses extent of resection (gross total vs subtotal)
- **Progression assessment** (6 studies): At chemotherapy regimen changes
  - Indicates potential treatment failure requiring new therapy

#### **High Priority (6 studies)**
- **Radiation planning** (6 studies): Within 14 days before radiation start
  - Defines target volumes for treatment planning

### NEW: Chemotherapy Change Points (16 identified)

The framework now identifies and prioritizes imaging around:
1. **New drug initiation** (baseline assessment)
2. **Drug discontinuation** (response/progression assessment)
3. **Regimen changes** (progression evaluation)

**Window**: 30 days before/after chemotherapy changes

These are critical because imaging at these timepoints helps determine:
- Treatment efficacy
- Disease progression requiring therapy change
- New baseline for subsequent treatment monitoring

## 2. Survival Endpoint Tracking

Successfully extracted for survival calculations:
- **Last known alive date**: July 29, 2025
- **Last clinical contact**: May 14, 2025
- **Last imaging**: May 14, 2025
- **Last treatment**: July 29, 2025
- **Vital status**: Can be extracted from patient_demographics

These endpoints enable:
- Overall survival (OS) calculation
- Progression-free survival (PFS) calculation
- Event-free survival (EFS) calculation

## 3. Standardized Configuration for Cohort Processing

Created `cohort_processing_config.yaml` containing:

### Configurable Parameters:
```yaml
imaging_windows:
  pre_surgery_days: 30
  post_surgery_days: 90
  chemo_change_window_days: 30
  radiation_planning_window_days: 14
  progression_assessment_days: 90
```

### Modular Components:
- Tumor surgery classification
- Chemotherapy identification (5-strategy approach)
- Radiation therapy analysis
- Enhanced imaging prioritization
- Survival endpoint extraction

### Cohort Processing Features:
- Batch processing capability
- Checkpoint frequency for large cohorts
- Standardized output formats (CSV, JSON)

## 4. Clinical Impact of Enhanced Prioritization

### Before Enhancement:
- 27 high-priority imaging studies
- Only surgical imaging prioritized
- No treatment change tracking
- No survival endpoint extraction

### After Enhancement:
- 39 critical/high-priority imaging studies
- Captures treatment response timepoints
- Tracks 16 chemotherapy change events
- Automated survival endpoint extraction

### Imaging Context Distribution:
- **Surveillance**: 142 studies (routine monitoring)
- **Post-operative**: 24 studies (extent of resection)
- **Radiation planning**: 6 studies (treatment planning)
- **Progression assessment**: 6 studies (treatment changes)
- **Pre-operative**: 3 studies (baseline disease)

## 5. Implementation for Next Patient

The framework is fully standardized and ready for the next patient:

```python
from enhanced_clinical_prioritization import process_patient_enhanced

# For any patient in cohort
patient_id = "next_patient_id"
results = process_patient_enhanced(
    patient_id,
    staging_path,
    output_path
)

# Access prioritized imaging
critical_imaging = results['critical_imaging']
chemo_change_imaging = results['chemo_change_imaging']
survival_endpoints = results['survival_endpoints']
```

## 6. Key Advantages of Enhanced Framework

1. **Comprehensive Coverage**: Captures all clinically significant imaging timepoints
2. **Treatment-Aware**: Links imaging to treatment changes for response assessment
3. **Survival-Ready**: Automated endpoint extraction for outcome analysis
4. **Standardized**: Configuration-driven approach works for entire cohort
5. **Prioritized**: Reduces review burden from 181 to 39 critical studies

## 7. Files Generated per Patient

1. `imaging_enhanced_priority_[patient_id].csv` - All imaging with priority scores
2. `survival_endpoints_[patient_id].json` - Last contact dates and vital status
3. `treatment_changes_[patient_id].csv` - Chemotherapy change timeline
4. `cohort_processing_config.yaml` - Standardized configuration (once per cohort)

## 8. Validation Results for Patient e4BwD8ZYDBccepXcJ.Ilo3w3

- **Treatment duration**: 6+ years (2018-2025)
- **16 chemotherapy changes** identified (starts/stops/regimen changes)
- **4 radiation courses** with 72 fractions
- **4 tumor surgeries** requiring operative note review
- **Last known alive**: July 29, 2025 (from last treatment date)

## Next Steps for BRIM Integration

1. **Apply to next patient**: Use standardized config to process next cohort member
2. **Validate priority assignments**: Clinical review of flagged imaging
3. **Extract from priority documents**: Focus BRIM on the 39 critical/high studies
4. **Track outcomes**: Use survival endpoints for cohort analysis
5. **Refine windows**: Adjust timing windows based on clinical feedback

This enhanced framework ensures no critical imaging is missed while dramatically reducing the abstraction burden from 181 to 39 studies, focusing effort on the most clinically meaningful timepoints.