# BRIM Analytics

**Hybrid FHIR + Clinical Notes Extraction Framework**

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 Overview

BRIM Analytics combines **structured FHIR data** with **unstructured clinical notes** for comprehensive clinical trial data extraction using BRIM Health's NLP platform.

### Key Innovation

Instead of processing only FHIR OR only clinical notes, this framework:
- Packages entire FHIR Bundle as ONE document
- Extracts clinical notes from S3 Binary resources
- Uses single-pass LLM extraction across both data types

### Current Status

✅ **Production Ready** - Pilot validated and tested  
✅ **188 clinical notes** extracted from 388 DocumentReferences  
✅ **1,770 FHIR resources** in Bundle  
✅ **13 variables + 5 decisions** defined and validated  

---

## 🚀 Quick Start

### Prerequisites

- **AWS CLI** with SSO configured
- **Python 3.9+**
- **Access** to radiant-prd-343218191717-us-east-1-prd-ehr-pipeline S3 bucket

### Installation

```bash
# Clone repository
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate environment
source venv/bin/activate

# Login to AWS
aws sso login --profile 343218191717_AWSAdministratorAccess
```

### Generate BRIM CSVs

```bash
# Run pilot extraction
python scripts/pilot_generate_brim_csvs.py \
    --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
```

**Output:**
- pilot_output/brim_csvs/project.csv (189 documents)
- pilot_output/brim_csvs/variables.csv (13 extraction rules)
- pilot_output/brim_csvs/decisions.csv (5 aggregation rules)

### Upload to BRIM

1. Login: https://app.brimhealth.com
2. Upload variables.csv and decisions.csv
3. Upload project.csv
4. Run extraction job
5. Download results (18 CSVs)

---

## 📚 Documentation

### **→ [Complete BRIM Workflow Guide](docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md) ← START HERE**

This comprehensive guide contains everything needed to understand and work with BRIM Analytics:

- **Architecture** - System components and data flow
- **Data Sources** - S3 bucket structure and FHIR resources
- **CSV Format Specifications** - Exact format requirements for BRIM platform
- **Script Documentation** - API reference and usage examples
- **Workflow Steps** - End-to-end process from extraction to results
- **Troubleshooting** - Common errors and solutions

### Additional Documentation

- [Pilot Execution Guide](PILOT_EXECUTION_GUIDE.md) - Step-by-step pilot instructions
- [Hybrid FHIR-BRIM Strategy](docs/HYBRID_FHIR_BRIM_EXTRACTION_STRATEGY.md) - Design rationale
- [Archived Docs](docs/archive/) - Historical documentation (superseded)

---

## 📊 What Gets Extracted

### Variables (13 total)

| Category | Variables | Type |
|----------|-----------|------|
| **Demographics** | patient_gender, date_of_birth | text |
| **Diagnosis** | primary_diagnosis, diagnosis_date, who_grade | text |
| **Surgeries** | surgery_date, surgery_type, extent_of_resection | text |
| **Treatments** | chemotherapy_agent, radiation_therapy | text, boolean |
| **Molecular** | idh_mutation, mgmt_methylation | text |
| **Document** | document_type | text |

### Decisions (5 total)

- confirmed_diagnosis - Cross-validate diagnosis from multiple sources
- total_surgeries - Count unique surgical procedures
- best_resection - Determine most extensive resection
- chemotherapy_regimen - Aggregate chemotherapy agents
- molecular_profile - Summarize IDH/MGMT results

---

## 🛠️ Key Files

| File | Purpose |
|------|---------|
| scripts/pilot_generate_brim_csvs.py | **Main script** - Generate BRIM CSVs |
| docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md | **Master documentation** - Everything you need |
| pilot_output/brim_csvs/ | **Output directory** - Generated CSVs |
| requirements.txt | **Dependencies** - boto3, beautifulsoup4, etc. |
| setup.sh | **Environment setup** - Automated installation |

---

## 🔍 Critical Format Requirements

### BRIM Only Supports 2 Data Types

- ✅ **text** - For all text, dates, numbers, categorical data
- ✅ **boolean** - For true/false values ONLY
- ❌ **date** - NOT SUPPORTED (use text with YYYY-MM-DD)
- ❌ **integer** - NOT SUPPORTED (use text with numeric string)

### Empty Field Rules

- **prompt_template** - MUST be empty (BRIM uses instruction instead)
- **aggregation_instruction** - Empty unless specific aggregation needed
- **only_use_true_value_in_aggregation** - Empty for non-boolean types

**See:** [CSV Format Specifications](docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md#csv-format-specifications)

---

## 🐛 Troubleshooting

### "Skipped X variable lines due to incomplete info!"

**Cause:** Wrong data type (date/integer) or filled prompt_template

**See:** [Complete Troubleshooting Guide](docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md#troubleshooting)

---

## 📝 References

- **Repository:** https://github.com/adamcresnick/RADIANT_PCA/tree/main/BRIM_Analytics
- **BRIM Platform:** https://app.brimhealth.com
- **FHIR Specification:** https://www.hl7.org/fhir/

---

**For complete documentation, see [docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md](docs/COMPLETE_BRIM_WORKFLOW_GUIDE.md)**
