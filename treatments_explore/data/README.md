# Treatment Data Directory

## Current Files (Clean Filtered Data)

### chemotherapy_all_patients_filtered_therapeutic.csv (30M)
**Source**: AWS Athena `v_chemo_medications` view with supportive care filtering  
**Date**: October 26, 2025  
**Rows**: 196,001 medication orders  
**Patients**: 1,032 unique patients  
**Drugs**: 350 unique therapeutic drugs  

**Contents**: Therapeutic chemotherapy data only
- ✅ Chemotherapy (traditional cytotoxic agents)
- ✅ Targeted therapy (molecularly targeted agents)
- ✅ Immunotherapy (checkpoint inhibitors, CAR-T, etc.)
- ✅ Hormone therapy (endocrine therapies)
- ✅ Investigational therapies (experimental therapeutics)
- ❌ Supportive care drugs EXCLUDED (pain meds, antiemetics, G-CSF, etc.)

**Drug Categories**:
- chemotherapy: 83,723 orders
- targeted_therapy: 48,996 orders
- investigational_therapy: 26,325 orders
- immunotherapy: 21,478 orders
- investigational_other: 11,844 orders
- hormone_therapy: 2,630 orders
- uncategorized: 1,005 orders

**Top Drugs**:
1. vincristine (3,851 orders)
2. carboplatin (3,402 orders)
3. bevacizumab (1,935 orders)
4. mesna (1,481 orders) - chemoprotectant
5. filgrastim (1,343 orders) - growth factor support
6. pegfilgrastim (1,032 orders) - growth factor support
7. Cyclophosphamide (916 orders)
8. etoposide (898 orders)
9. temozolomide (672 orders)

**Use this file for**:
- Treatment paradigm analysis
- Chemotherapy regimen discovery
- Drug combination patterns
- Clinical outcomes research

---

## Archived Files (Old Unfiltered Data)

### OLD_UNFILTERED_DATA_20251026/
**Contains**: Previous unfiltered medication data from October 25, 2025

#### chemotherapy_all_patients_final.csv (853M) - ARCHIVED
- Contained pain medications (morphine, fentanyl, oxycodone)
- Contained sedatives (propofol, midazolam, ketamine)
- Contained antiemetics (ondansetron, granisetron)
- Contained general supportive care drugs
- **Do not use for treatment analysis** - data is contaminated

**Size comparison**:
- Old unfiltered: 853M
- New filtered: 30M
- **96.5% reduction** (28x smaller)

#### Other archived files:
- `chemotherapy_all_patients.csv` (199M)
- `chemotherapy_all_patients_corrected.csv` (121M)
- `chemotherapy_all_patients_raw.tsv` (223M)

---

## Data Quality Notes

### Fixed Issues
1. ✅ Supportive care drugs filtered out
2. ✅ Only therapeutic anticancer drugs included
3. ✅ Methotrexate sodium correctly categorized as chemotherapy
4. ✅ Drug categories validated against reference data

### Known Issues (Future Work)
1. **Drug name variants**: Same drug appears with multiple names
   - filgrastim / G-CSF (same drug)
   - Cyclophosphamide / Cyclophosphamid (spelling variants)
   - Vinblastin / vinblastine (case sensitivity)
   - See `treatment_paradigms/ANALYSIS_SUMMARY_AND_RECOMMENDATIONS.md`

2. **Growth factor support drugs**: Still included (filgrastim, pegfilgrastim)
   - These ARE part of chemotherapy protocols (enable dose intensification)
   - Can be filtered in downstream analysis if needed

3. **Combination regimens**: Present but labeled as drug_type=combination_regimen
   - Not used in EHR matching (only single agents matched)
   - Kept for reference/documentation purposes

---

## Related Files

- **Drug reference**: `../../athena_views/data_dictionary/chemo_reference/drugs.csv`
- **Paradigm analysis**: `treatment_paradigms/`
- **Analysis summary**: `treatment_paradigms/ANALYSIS_SUMMARY_AND_RECOMMENDATIONS.md`

---

## Version History

- **v3 (2025-10-26)**: Clean therapeutic-only data with supportive care filtering
- **v2 (2025-10-25)**: Unfiltered data with drug categorization (ARCHIVED)
- **v1 (2025-10-25)**: Raw extraction from v_medications (ARCHIVED)

---

**Last Updated**: October 26, 2025  
**Athena Query ID**: ef8b3cb6-5836-4c50-a727-c2e75c6e39d3  
**S3 Location**: s3://aws-athena-query-results-343218191717-us-east-1/filtered-chemo-final/
