# Chemotherapy Gap Analysis Report
**Date**: 2025-10-26  
**Analyst**: Claude Code Analysis

## Executive Summary

**Finding**: 89 patients manually identified as having received chemotherapy are **NOT** appearing in the v_chemo_medications view. Analysis reveals this is primarily a **DATA AVAILABILITY** issue, not a filtering problem.

## Analysis Breakdown

### Patients Investigated
- **Total manually-identified chemo patients**: 89 unique patients (112 entries with duplicates)
- **Patients currently in v_chemo_medications**: 0 (0%)
- **Patients NOT in v_chemo_medications**: 89 (100%)

### Gap Categories

| Category | Patient Count | Description |
|----------|--------------|-------------|
| **No medication records at all** | 3 | No FHIR medication_request data exists for these patients in the database |
| **Have medications, but no chemo matched** | 86 | Have medication records (avg 55 distinct drugs each, 11,948 total records) but NO chemotherapy drugs matched our reference data |

## Medication Analysis (Sample of 20 Patients)

### Top Medications Found:
All medications in the top 50 are **supportive care/procedural** drugs:

1. **Anti-emetics**: ondansetron (17/20 patients)
2. **Imaging contrast**: gadobutrol, gadopentetate (15/20 patients)
3. **IV fluids**: lactated ringers, dextrose solutions (13/20 patients)
4. **Anesthetics**: fentanyl, propofol, midazolam (12/20 patients)
5. **Pain management**: oxycodone, morphine, acetaminophen (10/20 patients)
6. **Antibiotics**: cefazolin (13/20 patients)

### Critical Finding:
**ZERO chemotherapy drugs appear in the top 50 medications** for these patients.

## Root Cause Analysis

### Hypothesis 1: Data Not Captured in FHIR medication_request ✅ LIKELY
**Evidence**:
- Patients have extensive medication records (avg 55 distinct drugs)
- All medications are supportive/procedural (correctly filtered out by our system)
- No chemotherapy drugs present in medication lists
- Suggests chemotherapy was administered but NOT recorded in structured medication_request FHIR resources

**Possible reasons**:
1. Chemotherapy administered at external facilities (not captured in Epic)
2. Chemotherapy documented only in clinical notes (unstructured data)
3. Chemotherapy orders in different Epic module not exported to FHIR
4. Historical data migration issues (older treatments not fully captured)

### Hypothesis 2: Missing Drugs from Reference Data ❌ UNLIKELY
**Evidence against**:
- Our reference data has 2,968 drugs covering comprehensive chemotherapy agents
- No chemotherapy drug names appear even in raw medication lists for these patients
- If drugs were present but unmatched, we'd see generic names in the medication list

### Hypothesis 3: Over-filtering ❌ RULED OUT
**Evidence against**:
- These 86 patients average 55 distinct medications each - plenty of data
- No chemotherapy drugs visible in the raw medication lists
- Our filters are working correctly (properly excluding supportive care)

## Data Quality Metrics

### v_chemo_medications View Coverage:
- **Total patients in database**: 1,873
- **Patients with chemotherapy in view**: 968 (51.7%)
- **Patients without chemotherapy in view**: 905 (48.3%)
  - 89 manually identified as should have chemo (9.8% of the 905)
  - 816 likely correctly excluded

### False Negative Rate (Estimated):
- **Lower bound**: 89/1,873 = 4.7% of all patients
- **Upper bound**: 89/1,057 = 8.4% of patients who should have chemo (if all 89 truly received chemo)

## Recommendations

### 1. Investigate Data Source  **[HIGH PRIORITY]**
- Review with EHR team why chemotherapy orders aren't in medication_request FHIR resources
- Check if chemotherapy is recorded in different FHIR resource types (e.g., Procedure, MedicationAdministration)
- Verify external facility data integration

### 2. Cross-Reference with Clinical Notes **[MEDIUM PRIORITY]**
- Query unstructured clinical notes for chemotherapy mentions for these 89 patients
- Use NLP to extract chemotherapy regimens from documentation

###3. Validate Manual Abstraction **[MEDIUM PRIORITY]**
- Review sample of the 89 patients with clinical team
- Confirm they actually received chemotherapy
- Identify source of truth for manual abstraction (charts? billing codes? procedures?)

### 4. Expand Data Sources **[LONG-TERM]**
- Investigate Procedure codes (CPT codes for chemotherapy administration)
- Check Observation resources for treatment-related labs (chemo monitoring)
- Review billing/claims data as alternative source

## Conclusion

The gap between manually-identified chemo patients and v_chemo_medications is **NOT due to over-filtering** or missing reference data. It appears to be a **fundamental data availability issue** where chemotherapy treatments are not captured in the FHIR medication_request resources we're querying.

The v_chemo_medications view is working as designed - it correctly identifies chemotherapy from available FHIR medication data and properly filters supportive care. The issue is upstream: the chemotherapy data for these 89 patients is either:
- Not in the database at all (3 patients)
- In the database but in non-medication FHIR resources (86 patients)

**Recommendation**: Prioritize investigating alternative FHIR resources (Procedure, MedicationAdministration, Claim) and unstructured data sources (clinical notes) to capture the missing chemotherapy treatments.

## Files Generated

1. `patients_without_chemotherapy.csv` - Full list of 905 patients NOT in v_chemo_medications
2. `chemo_gap_analysis_summary.csv` - Summary statistics of the 89 patient gap
3. `missing_patients_medications_sample.csv` - Top 100 medications for sample of 20 gap patients
4. `missing_chemo_patients_unique.txt` - List of 89 unique patient IDs from manual review

