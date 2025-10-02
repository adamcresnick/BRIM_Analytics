# BRIM Analytics

**Hybrid FHIR + BRIM Extraction Framework for Clinical Trial Data**

BRIM Analytics combines structured FHIR data extraction with unstructured clinical note analysis via BRIM Health's NLP platform for pediatric brain tumor research.

## 🚀 Quick Start (Production Pilot)

### 1. Setup Environment

```bash
cd RADIANT_PCA/BRIM_Analytics

# Run setup script
chmod +x setup.sh
./setup.sh

# Activate virtual environment
source venv/bin/activate
```

### 2. Login to AWS

```bash
aws sso login --profile 343218191717_AWSAdministratorAccess
```

### 3. Explore Available Patients

```bash
python pilot_workflow.py --explore-only
```

### 4. Run Pilot Extraction

```bash
python pilot_workflow.py \
    --patient-id "Patient/abc123" \
    --research-id "TEST001"
```

## 📊 What Gets Extracted

### From FHIR (Structured)
- Demographics, surgical procedures, diagnoses (ICD-10), medications (RxNorm), encounters

### From Clinical Notes (via BRIM)
- Pathologic diagnoses, WHO grades, extent of resection, tumor characteristics, complications

### HINT Columns (Hybrid Validation)
- Pre-populated from FHIR for validation and gap-filling

## 📁 Project Structure

```
BRIM_Analytics/
├── src/                  # Core extraction modules
├── docs/                 # Strategy and API documentation  
├── pilot_workflow.py     # Production pilot script
├── setup.sh              # Quick setup
├── requirements.txt      # Dependencies
└── .env                  # Configuration
```

## 📚 Documentation

- [Hybrid Strategy Guide](docs/HYBRID_FHIR_BRIM_EXTRACTION_STRATEGY.md)
- [BRIM Best Practices](../../Downloads/fhir_athena_crosswalk/documentation/)

## ⚙️ Requirements

- Python 3.8+, AWS CLI with SSO, Athena FHIR access, BRIM API key

See `.env` for configuration.

