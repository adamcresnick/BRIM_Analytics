# Gold Standard Data for Patient C1277724

**Patient ID**: C1277724  
**FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3  
**Subject ID (BRIM)**: 1277724

---

## Gold Standard Reference Data

### Demographics
| Field | Value |
|-------|-------|
| **Gender** | Female |
| **Race** | White |
| **Ethnicity** | Not Hispanic or Latino |

### Molecular Characterization
| Field | Value |
|-------|-------|
| **Molecular Alteration** | KIAA1549-BRAF (fusion) |

### Diagnosis Events
Patient has **3 clinical events** documented:

#### Event 1: ET_FWYP9TY0 (Initial CNS Tumor)
- **Age at Event**: 4763 days (~13.0 years)
- **Event Type**: Initial CNS Tumor
- **Diagnosis**: Pilocytic astrocytoma (Low-Grade Glioma)
- **WHO Grade**: 1
- **Tumor Locations**: Cerebellum/Posterior Fossa (multiple entries)
- **Metastasis**: Yes (Leptomeningeal, Spine)
- **Molecular Testing**: Whole Genome Sequencing
- **Shunt**: Endoscopic Third Ventriculostomy (ETV) Shunt

#### Event 2: ET_94NK0H3X (Progressive)
- **Age at Event**: 5095 days (~13.9 years)
- **Event Type**: Progressive
- **Diagnosis**: Pilocytic astrocytoma (Low-Grade Glioma)
- **WHO Grade**: 1
- **Tumor Location**: Cerebellum/Posterior Fossa
- **Site of Progression**: Local
- **Metastasis**: No

#### Event 3: ET_FRRCB155 (Progressive)
- **Age at Event**: 5780 days (~15.8 years)
- **Event Type**: Progressive
- **Diagnosis**: Pilocytic astrocytoma (Low-Grade Glioma)
- **WHO Grade**: 1
- **Tumor Locations**: 
  - Brain Stem - Midbrain/Tectum
  - Cerebellum/Posterior Fossa
  - Temporal Lobe
- **Site of Progression**: Local
- **Molecular Testing**: Specific gene mutation analysis
- **Metastasis**: No

### Treatment History

#### Treatment 1: ET_FWYP9TY0 (Age 4763 days)
- **Treatment Status**: New
- **Surgery**: Yes
- **Age at Surgery**: 4763 days
- **Extent of Resection**: Partial resection
- **Specimen Collection**: Initial CNS Tumor Surgery
- **Chemotherapy**: No
- **Radiation**: No

#### Treatment 2: ET_94NK0H3X (Age 5130 days - chemotherapy start)
- **Treatment Status**: New
- **Surgery**: No
- **Chemotherapy**: Yes
  - **Type**: Treatment follows other standard of care (not protocol-based)
  - **Agents**: vinblastine; bevacizumab
  - **Age at Start**: 5130 days (~14.0 years)
  - **Age at Stop**: 5492 days (~15.0 years)
  - **Duration**: 362 days (~1 year)
- **Radiation**: No

#### Treatment 3: ET_FRRCB155 (Age 5780 days)
- **Treatment Status**: New
- **Surgery**: Yes
- **Age at Surgery**: 5780 days (~15.8 years)
- **Extent of Resection**: Partial resection
- **Specimen Collection**: Progressive surgery
- **Chemotherapy**: Yes
  - **Type**: Treatment follows other standard of care (not protocol-based)
  - **Agents**: selumetinib
  - **Age at Start**: 5873 days (~16.1 years)
  - **Age at Stop**: 7049 days (~19.3 years)
  - **Duration**: 1176 days (~3.2 years)
- **Radiation**: No

---

## Key Facts Summary

### Timeline
- **Initial Diagnosis**: Age 4763 days (~13.0 years old)
- **First Surgery**: Age 4763 days (partial resection)
- **First Progression**: Age 5095 days (~14 months later)
- **Chemotherapy #1**: Age 5130-5492 days (vinblastine + bevacizumab)
- **Second Progression**: Age 5780 days
- **Second Surgery**: Age 5780 days (partial resection)
- **Chemotherapy #2**: Age 5873-7049 days (selumetinib, 3+ years)

### Treatment Summary
- **Total Surgeries**: 2 (both partial resections)
- **Chemotherapy Agents**: vinblastine, bevacizumab, selumetinib
- **Radiation**: None documented
- **Molecular Testing**: KIAA1549-BRAF fusion confirmed

### Clinical Course
- Low-grade pilocytic astrocytoma
- Initial presentation with metastases (leptomeningeal, spine)
- Required ETV shunt for hydrocephalus
- Two documented progressions requiring intervention
- Tumor locations: Cerebellum/posterior fossa (primary), midbrain/tectum, temporal lobe (progression sites)

---

## Age Calculation Notes

**CRITICAL**: Gold standard uses **age_in_days** format for all temporal data.

To convert BRIM dates to age_in_days for comparison:
```python
from datetime import datetime

# Patient birth date (need to calculate from FHIR data)
# If diagnosis was at age 4763 days and diagnosis date was 2018-06-04:
diagnosis_date = datetime(2018, 6, 4)
age_at_diagnosis_days = 4763

# Calculate birth date
birth_date = diagnosis_date - timedelta(days=age_at_diagnosis_days)
# birth_date ≈ 2005-05-27

# Convert any BRIM date to age_in_days
def date_to_age_days(event_date, birth_date):
    return (event_date - birth_date).days

# Example:
# Surgery on 2018-06-04 → age_in_days = 4763
# Chemo start on 2019-01-15 → age_in_days = (2019-01-15 - 2005-05-27).days
```

### Key Age Milestones
| Event | Age (days) | Age (years) | Approximate Date |
|-------|-----------|-------------|------------------|
| Initial Diagnosis/Surgery 1 | 4763 | 13.0 | 2018-06-04 |
| First Progression | 5095 | 13.9 | 2019-05-02 |
| Chemo #1 Start | 5130 | 14.0 | 2019-06-06 |
| Chemo #1 Stop | 5492 | 15.0 | 2020-06-02 |
| Second Progression/Surgery 2 | 5780 | 15.8 | 2021-03-16 |
| Chemo #2 Start | 5873 | 16.1 | 2021-06-17 |
| Chemo #2 Stop | 7049 | 19.3 | 2024-08-15 |

---

## Validation Comparison Targets

### Critical Variables to Match

| Variable | Gold Standard Value | Source | Notes |
|----------|-------------------|--------|-------|
| **Gender** | Female | demographics.csv | Should be 100% match |
| **Primary Diagnosis** | Pilocytic astrocytoma | diagnosis.csv | Should match |
| **WHO Grade** | 1 (Grade I) | diagnosis.csv | Should match |
| **Molecular Marker** | KIAA1549-BRAF fusion | molecular_characterization.csv | Critical - must detect |
| **Initial Diagnosis Date** | Age 4763 days (~2018-06-04) | diagnosis.csv: age_at_event_days | Critical temporal anchor |
| **Surgery Count** | 2 surgeries | treatments.csv: surgery=Yes count | Must be exact |
| **Surgery 1 Date** | Age 4763 days | treatments.csv: age_at_surgery | ~2018-06-04 |
| **Surgery 1 Extent** | Partial resection | treatments.csv: extent_of_tumor_resection | Important |
| **Surgery 2 Date** | Age 5780 days | treatments.csv: age_at_surgery | ~2021-03-16 |
| **Surgery 2 Extent** | Partial resection | treatments.csv: extent_of_tumor_resection | Important |
| **Chemotherapy Agents** | vinblastine, bevacizumab, selumetinib | treatments.csv: chemotherapy_agents | Must detect all 3 |
| **Radiation Therapy** | No | treatments.csv: radiation=No | Should match |
| **Metastasis at Diagnosis** | Yes (Leptomeningeal, Spine) | diagnosis.csv: metastasis=Yes | Important staging |
| **Tumor Location (Primary)** | Cerebellum/Posterior Fossa | diagnosis.csv: tumor_location | Should match |

### Calculated/Derived Variables

| Variable | Expected Automated Value | Calculation Method |
|----------|------------------------|-------------------|
| **Total Surgeries** | 2 | Count surgery=Yes entries |
| **Best Resection** | Partial resection | Max extent across surgeries |
| **Chemotherapy Regimen** | "vinblastine, bevacizumab, selumetinib" | Aggregate all agents |
| **Progression Events** | 2 | Count event_type=Progressive |
| **Treatment Duration** | Multiple periods | Age ranges from treatments |

---

## Expected Accuracy by Variable

| Variable | Baseline (Bundle Only) | Enhanced (w/ Structured Findings) | Confidence |
|----------|----------------------|----------------------------------|------------|
| Gender | 100% | 100% | Very High |
| Primary Diagnosis | 90% | 95% | High |
| WHO Grade | 70% | 90% | High |
| Molecular Marker | 0% | **95%** | Very High (explicitly in structured finding) |
| Diagnosis Date | 60% | **98%** | Very High (explicitly in structured finding) |
| Surgery Count | 40% | **100%** | Very High (explicitly in structured finding) |
| Surgery Dates | 50% | **95%** | Very High (explicitly in structured finding) |
| Extent of Resection | 60% | 85% | Medium |
| Chemotherapy Agents | 70% | **95%** | Very High (explicitly in structured finding) |
| Radiation Therapy | 80% | 95% | High |
| Metastasis | 50% | 75% | Medium |
| Tumor Location | 70% | 90% | High |

**Overall Baseline Accuracy**: ~65%  
**Overall Enhanced Accuracy**: **~92%** (projected)

---

## Next Steps

1. ✅ Complete gold standard data extraction (DONE)
2. ⏳ Upload BRIM CSVs to platform
3. ⏳ Run BRIM extraction job
4. ⏳ Download BRIM results
5. ⏳ Convert BRIM dates to age_in_days format
6. ⏳ Execute validation comparison script
7. ⏳ Generate accuracy report

---

## Files Reference

- **Gold Standard**: `data/20250723_multitab_csvs/*.csv`
- **Automated Input**: `pilot_output/brim_csvs_final/*.csv`
- **Structured Findings**: `pilot_output/structured_data_enhanced.json`
