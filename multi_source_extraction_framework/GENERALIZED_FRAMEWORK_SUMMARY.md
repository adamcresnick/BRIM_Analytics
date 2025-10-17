# Generalized Multi-Source Extraction Framework
## Patient-Agnostic Chemotherapy Identification and Treatment Period Extraction

### Overview
Successfully implemented a comprehensive, generalizable framework for identifying chemotherapy medications and extracting standardized treatment periods from RADIANT PCA data. The framework is fully patient-agnostic and can be applied to any patient in the cohort without modifications.

### Key Achievements

#### 1. Comprehensive 5-Strategy Chemotherapy Identification
Implemented all five strategies from the RADIANT methodology:
- **Strategy 1: RxNorm Ingredient Matching** - 265 medications identified
- **Strategy 2: Product-to-Ingredient Mapping** - 155 medications identified
- **Strategy 3: Medication Name Pattern Matching** - 172 medications identified
- **Strategy 4: Care Plan ONCOLOGY Category** - 120 medications identified
- **Strategy 5: Reason Code Indicators** - 240 medications identified

**Total Result**: 409 chemotherapy medications identified (36.5% of 1,121 total medications)

#### 2. Robust Date Handling
The framework checks multiple date sources in priority order:
1. `medication_start_date` / `medication_end_date`
2. `med_date_given_start` / `med_date_given_end`
3. `cp_period_start` / `cp_period_end` (care plan periods)
4. `mr_validity_period_start` / `mr_validity_period_end`

This ensures treatment periods can be extracted even when primary date columns are missing.

#### 3. Treatment Period Results
Successfully extracted treatment periods for all major chemotherapy agents:

| Drug | Records | Treatment Period | Duration |
|------|---------|------------------|----------|
| **Bevacizumab** | 166 | 2019-05-30 to 2019-12-26 | 210 days |
| **Vinblastine** | 170 | 2019-05-30 to 2019-12-26 | 210 days |
| **Selumetinib** | 22 | 2021-05-20 to 2021-09-24 | 127 days |

### Technical Innovations

#### 1. Semicolon-Separated RxNorm Code Parsing
```python
def parse_rxnorm_codes(self, rx_norm_codes_str: str) -> List[str]:
    """Parse semicolon-separated RxNorm codes"""
    codes = [c.strip() for c in str(rx_norm_codes_str).split(';') if c.strip()]
```

#### 2. Pipe-Separated Drug Combination Handling
```python
# Extract individual drugs from combinations like "vinblastine|bevacizumab"
drugs = [d.strip() for d in drug_list.split('|') if d.strip()]
```

#### 3. Missing RxNorm Code Coverage
- Bevacizumab has NO RxNorm codes but is caught by name matching
- Vinblastine (RxNorm: 11198, 11199) caught by RxNorm matching
- Selumetinib (RxNorm: 2289380, 2361596) caught by RxNorm matching

### Files Created

1. **comprehensive_chemotherapy_identifier.py** - Core identification engine
2. **test_comprehensive_treatment_periods.py** - Testing and validation
3. **debug_date_availability.py** - Date column diagnostic tool
4. **outputs/**
   - comprehensive_chemotherapy_e4BwD8ZYDBccepXcJ.Ilo3w3.csv (409 records)
   - treatment_periods_e4BwD8ZYDBccepXcJ.Ilo3w3.csv (8 periods)
   - treatment_timeline_e4BwD8ZYDBccepXcJ.Ilo3w3.json (chronological events)

### Generalizability Features

1. **Configuration-Driven**: All paths and parameters are configurable
2. **Patient-Agnostic**: No hardcoded patient-specific logic
3. **Reference Database Integration**: Uses RADIANT unified drug reference system
4. **Flexible Date Handling**: Adapts to available date columns
5. **UTC Timezone Standardization**: Prevents timezone comparison errors
6. **Comprehensive Error Handling**: Graceful handling of missing data

### Usage for Cohort Processing

```python
# For any patient in the cohort:
identifier = ComprehensiveChemotherapyIdentifier()

# Load patient medications
patient_id = "any_patient_id_from_cohort"
patient_path = staging_path / f"patient_{patient_id}"
meds_df = pd.read_csv(patient_path / "medications.csv")

# Identify chemotherapy
chemo_df, summary = identifier.identify_chemotherapy(meds_df)

# Extract treatment periods
periods_df = identifier.extract_treatment_periods(chemo_df)

# Create timeline
timeline = identifier.create_treatment_timeline(periods_df)
```

### Validation Completed

- ✅ iloc vs loc indexing fixed (preserves all columns)
- ✅ Multiple date source handling implemented
- ✅ Missing end date handling (uses max start date)
- ✅ Pipe-separated drug combinations parsed correctly
- ✅ All three primary chemotherapy agents have treatment periods
- ✅ Framework tested and working on patient e4BwD8ZYDBccepXcJ.Ilo3w3

### Next Steps for Full Pipeline

1. **Phase 3**: Intelligent Binary Selection (select ~100 relevant documents from 22,127)
2. **Phase 4**: Contextual BRIM Extraction (use timeline as LLM context)
3. **Phase 5**: Cross-Source Validation
4. **Cohort Automation**: Script to process all patients in batch

This framework represents a significant advancement in standardized chemotherapy identification and treatment period extraction for the RADIANT PCA project, providing a robust foundation for cohort-wide analysis.