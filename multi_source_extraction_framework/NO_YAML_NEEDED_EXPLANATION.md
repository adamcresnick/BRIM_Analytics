# Automated Cohort Processing: No Individual YAMLs Needed

## The Answer: NO, You Don't Need Individual YAML Files

The framework I've created **automatically processes all patients** without requiring individual configuration files for each patient.

## How It Works

### 1. Automatic Patient Discovery
```python
# The system automatically finds all patients
processor = CohortProcessor(staging_path, output_path)
patients = processor.discover_patients()
# Found: 7 patients automatically
```

The system:
- Scans the staging directory for all `patient_*` folders
- Extracts patient IDs automatically
- No manual patient list needed

### 2. Single Configuration for Entire Cohort

Instead of individual YAMLs per patient, we have **ONE configuration** that applies to all:

```yaml
# cohort_processing_config.yaml (ONE FILE FOR ALL PATIENTS)
framework_version: '2.0'
imaging_prioritization:
  pre_surgery_days: 30
  post_surgery_days: 90
  chemo_change_window_days: 30
modules:
  surgery_classification: true
  chemotherapy_identification: true
  radiation_analysis: true
```

### 3. Processing Options

#### Process Entire Cohort:
```bash
python cohort_processor.py /path/to/staging /path/to/output
```

#### Process Specific Patients:
```bash
python cohort_processor.py /path/to/staging /path/to/output --patients patient1 patient2
```

#### Test Mode (First 3 Patients):
```bash
python cohort_processor.py /path/to/staging /path/to/output --test
```

#### Parallel Processing:
```bash
python cohort_processor.py /path/to/staging /path/to/output --parallel
```

## Comparison: Old vs New Approach

### Old Approach (Individual YAMLs):
```
❌ patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml
❌ patient_config_patient2.yaml
❌ patient_config_patient3.yaml
... (one YAML per patient)
```

**Problems:**
- Manual creation for each patient
- Maintenance nightmare for large cohorts
- Inconsistent configurations
- Error-prone

### New Approach (Automated):
```
✅ cohort_processing_config.yaml (ONE FILE)
```

**Benefits:**
- Automatic patient discovery
- Consistent processing
- Scalable to thousands of patients
- Single point of configuration

## What Gets Processed Automatically

For **EACH** patient discovered, the system automatically:

1. **Classifies tumor surgeries** (from 72+ procedures)
2. **Identifies chemotherapy** (5-strategy approach)
3. **Analyzes radiation therapy** (from 7 tables)
4. **Prioritizes imaging** (with treatment change windows)
5. **Extracts survival endpoints** (last contact, vital status)
6. **Creates standardized outputs** (CSV, JSON)

## Output Structure (Automatic)

```
outputs/
├── cohort_summaries/
│   ├── cohort_summary_20251013_014212.csv
│   ├── cohort_report.json
│   └── checkpoint_latest.json
├── patient_results/
│   ├── patient_e4BwD8ZYDBccepXcJ.Ilo3w3/
│   │   ├── tumor_surgeries_*.csv
│   │   ├── imaging_enhanced_priority_*.csv
│   │   ├── survival_endpoints_*.json
│   │   └── processing_summary_*.json
│   ├── patient_2/
│   │   └── ... (same structure)
│   └── patient_3/
│       └── ... (same structure)
```

## Example: Processing 1000 Patients

```python
# No YAMLs needed!
processor = CohortProcessor(staging_path, output_path)

# Process all 1000 patients with parallel processing
cohort_summary = processor.process_cohort(parallel=True)

# Results:
# - 1000 patient folders processed
# - 1 configuration file used
# - 0 individual YAMLs created
```

## Configuration Customization

If you need to adjust parameters, edit the **single** configuration:

```python
# Custom configuration for specific needs
config = {
    'imaging_prioritization': {
        'pre_surgery_days': 45,  # Wider window
        'chemo_change_window_days': 45
    },
    'processing': {
        'parallel': True,
        'max_workers': 8  # More parallel workers
    }
}

processor = CohortProcessor(staging_path, output_path, config)
```

## The Key Innovation

The framework uses **data-driven discovery** instead of configuration files:

1. **Discovers patients** from directory structure
2. **Identifies events** from data content (surgeries, treatments)
3. **Applies rules** uniformly across cohort
4. **Adapts to available data** (handles missing tables gracefully)

## Summary

**Question:** "Would we have to set up a new yaml for each patient?"

**Answer:** **NO** - The code automatically:
- Discovers all patients
- Processes them with consistent rules
- Uses one optional configuration for the entire cohort
- Scales from 1 to 10,000+ patients without changes

This is a **major improvement** over systems that require individual patient configurations, making it practical for large cohort studies like RADIANT PCA.