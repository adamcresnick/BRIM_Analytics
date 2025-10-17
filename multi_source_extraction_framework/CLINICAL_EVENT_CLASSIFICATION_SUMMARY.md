# Clinical Event Classification and Prioritization Framework

## Overview
Successfully developed a comprehensive framework for classifying tumor-specific surgeries, mapping imaging events, analyzing radiation therapy data, and creating an integrated clinical timeline for BRIM extraction prioritization.

## Key Achievements

### 1. Tumor-Specific Surgery Classification
**File:** `tumor_surgery_classifier.py`

#### Identified 4 Tumor Surgeries from 72 Total Procedures:
- **Initial Surgery (2018-05-28):** CRANIECTOMY W/EXCISION TUMOR/LESION SKULL
- **3 Additional Procedures:** Requiring operative note review for classification as progressive vs recurrence surgeries

#### Classification Criteria:
- **Tumor Surgery Indicators:** resection, excision, craniotomy, tumor removal, biopsy
- **Excluded Procedures:** shunt placements, EVD, wound care, angiography
- **Surgery Types:** biopsy_only, resection, tumor_procedure

### 2. Imaging Event Mapping to Surgical Timeline
**File:** `tumor_surgery_classifier.py`

#### 181 Total Imaging Studies Classified:
- **27 High-Priority Studies:**
  - 3 Pre-operative (within 30 days before surgery)
  - 24 Post-operative (within 90 days after surgery)
- **154 Surveillance Studies**

#### Priority Levels:
- **High:** Pre/post-operative imaging for extent of disease/resection
- **Medium:** MRI surveillance studies
- **Low:** Routine surveillance imaging

### 3. Radiation Therapy Data Analysis
**File:** `radiation_therapy_analyzer.py`

#### Comprehensive Radiation Data Processing:
- **4 Radiation Courses** identified (2021-2024)
- **72 Treatment Fractions** delivered
- **205 Priority Notes** for abstraction (170 medium, 35 low priority)

#### Data Sources Integrated:
- radiation_care_plan_hierarchy (200 records)
- radiation_care_plan_notes (35 records)
- radiation_treatment_courses (4 records)
- radiation_treatment_appointments (72 records)
- radiation_service_request_notes (170 records)

### 4. Integrated Clinical Timeline
**File:** `integrated_clinical_timeline.py`

#### Complete Treatment History (2018-2024):
- **48 Total Clinical Events** over 2,276 days
- **13 Treatment Phases** identified and classified

#### Event Distribution:
- 4 Tumor surgeries
- 8 Chemotherapy courses (bevacizumab, vinblastine, selumetinib)
- 4 Radiation courses (72 fractions)
- 27 Priority imaging studies

#### Priority Documents for BRIM Abstraction:
- **3 Operative Notes** (critical priority for extent of resection)
- **10 Imaging Reports** (high priority for disease assessment)
- **205 Radiation Notes** (treatment planning and toxicity)

## Generalized Framework Features

### 1. Patient-Agnostic Design
- All classifiers work with any patient ID
- No hardcoded patient-specific logic
- Configuration-driven approach

### 2. Comprehensive Date Handling
- UTC timezone standardization throughout
- Multiple date source fallback logic
- Handles missing end dates gracefully

### 3. Multi-Source Integration
- Combines structured data from multiple Athena tables
- Links events across different data sources
- Creates unified timeline for analysis

### 4. Priority-Based Document Selection
- Automatically identifies high-value documents
- Prioritizes based on clinical context
- Reduces manual review burden

## Clinical Insights from Patient Analysis

### Treatment Pattern:
1. **Initial Phase (2018):** Surgical resection
2. **Chemotherapy Phase (2019-2021):** Bevacizumab + Vinblastine, later Selumetinib
3. **Radiation Phases (2021, 2024):** Multiple courses suggesting recurrence/progression

### Key Findings:
- **Long treatment duration:** 6+ years of active treatment
- **Multi-modal therapy:** Surgery + Chemotherapy + Radiation
- **Multiple treatment phases:** Suggesting recurrent/progressive disease

## Files Created

### Core Modules:
1. `tumor_surgery_classifier.py` - Surgical event classification
2. `radiation_therapy_analyzer.py` - Radiation data processing
3. `integrated_clinical_timeline.py` - Timeline builder

### Output Files:
1. `tumor_surgeries_*.csv` - Classified surgical procedures
2. `imaging_with_context_*.csv` - Prioritized imaging studies
3. `radiation_courses_*.csv` - Radiation treatment courses
4. `radiation_priority_notes_*.csv` - Priority radiation documents
5. `integrated_timeline_*.json` - Complete clinical timeline
6. `clinical_events_*.csv` - Chronological event list

## Usage for BRIM Extraction

```python
# For any patient in the cohort
from integrated_clinical_timeline import IntegratedClinicalTimeline

builder = IntegratedClinicalTimeline(staging_path)
timeline = builder.build_timeline(patient_id)

# Access priority documents for BRIM extraction
operative_notes = timeline['priority_documents']['operative_notes']
imaging_reports = timeline['priority_documents']['imaging_reports']
radiation_plans = timeline['priority_documents']['radiation_plans']

# Use treatment phases for context
for phase in timeline['treatment_phases']:
    print(f"{phase['phase']}: {phase['start_date']} - {phase['description']}")
```

## Next Steps for BRIM Integration

1. **Operative Note Extraction:** Use the 3 identified operative notes to extract extent of resection
2. **Imaging Report Analysis:** Process 10 high-priority imaging reports for disease progression
3. **Radiation Documentation:** Extract dose, fractionation, and toxicity from radiation notes
4. **Treatment Response Assessment:** Link imaging findings to treatment phases
5. **Cohort-Wide Processing:** Apply framework to all patients systematically

This framework provides the foundation for systematic, prioritized extraction of clinical information from the RADIANT PCA cohort, significantly reducing the manual effort required while ensuring comprehensive coverage of key clinical events.