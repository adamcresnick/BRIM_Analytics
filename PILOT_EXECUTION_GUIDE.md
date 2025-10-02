# PILOT EXECUTION GUIDE
## Extract FHIR Bundle for Patient e4BwD8ZYDBccepXcJ.Ilo3w3

**Date:** October 2, 2025  
**Status:** Ready to Execute

---

## ✅ CONFIRMED CONFIGURATION

### Data Sources
- **Athena Database:** `radiant_prd_343218191717_us_east_1_prd_fhir_datastore_90d6a59616343629b26cd05c6686f0e8_healthlake_view`
- **Schema:** Raw FHIR tables from `e934bc57-fb76-433f-8fa5-4ccd3bffb0c2.csv`
- **Binary Links:** `s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/binary_resource_download_links.json`
- **S3 NDJSON:** `s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/ndjson/`

### Patient
- **ID:** `e4BwD8ZYDBccepXcJ.Ilo3w3`
- **Manual CSVs:** `/Users/resnick/Downloads/fhir_athena_crosswalk/20250723_multitab_csvs/`

---

## 🚀 QUICK START

### Step 1: Extract FHIR Bundle
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Activate environment (if using venv)
source venv/bin/activate

# Run extraction
python scripts/pilot_extract_patient.py
```

**Expected Output:**
- `pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json`
- Bundle with Patient, Conditions, Procedures, Medications, Observations, Encounters

### Step 2: Generate BRIM CSVs (Next)
```bash
python scripts/pilot_generate_brim_csvs.py \
  --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json \
  --output-dir pilot_output/brim_csvs
```

**Expected Output:**
- `pilot_output/brim_csvs/project.csv` (FHIR bundle + clinical notes)
- `pilot_output/brim_csvs/variables.csv` (extraction rules)
- `pilot_output/brim_csvs/decisions.csv` (aggregation rules)

---

## 📊 WHAT THE EXTRACTION DOES

### Phase 1: Query Raw Athena Tables

```sql
-- Patient demographics
SELECT id, identifier, name, birthDate, gender, deceasedBoolean
FROM patient WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'

-- All diagnoses (nested JSON preserved)
SELECT id, code, bodySite, clinicalStatus, recordedDate
FROM condition WHERE subject LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All surgeries (nested JSON preserved)
SELECT id, code, performedDateTime, bodySite, performer
FROM procedure WHERE subject LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- All medications (nested JSON preserved)
SELECT id, medicationCodeableConcept, authoredOn, dosageInstruction
FROM medicationrequest WHERE subject LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- Labs and molecular tests
SELECT id, code, effectiveDateTime, valueQuantity, valueString
FROM observation WHERE subject LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'

-- Encounters
SELECT id, class, type, period, reasonCode
FROM encounter WHERE subject LIKE '%e4BwD8ZYDBccepXcJ.Ilo3w3%'
```

### Phase 2: Assemble FHIR Bundle

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "e4BwD8ZYDBccepXcJ.Ilo3w3",
        "birthDate": "YYYY-MM-DD",
        "gender": "...",
        ...
      }
    },
    {
      "resource": {
        "resourceType": "Condition",
        "code": {
          "coding": [{
            "system": "http://hl7.org/fhir/sid/icd-10",
            "code": "C71.6",
            "display": "Malignant neoplasm of cerebellum"
          }],
          "text": "Pilocytic astrocytoma"
        },
        ...
      }
    },
    ... (more resources)
  ]
}
```

---

## 🔍 TROUBLESHOOTING

### Error: "Cannot connect to Athena"
```bash
# Test AWS connection
aws sts get-caller-identity --profile 343218191717_AWSAdministratorAccess

# Test Athena access
aws athena list-databases \
  --profile 343218191717_AWSAdministratorAccess \
  --catalog-name AwsDataCatalog \
  | grep "radiant_prd"
```

### Error: "Patient not found"
```bash
# Verify patient exists in Athena
python -c "
from pyathena import connect
conn = connect(
    s3_staging_dir='s3://aws-athena-query-results-343218191717-us-east-1/',
    region_name='us-east-1',
    profile_name='343218191717_AWSAdministratorAccess'
)
cursor = conn.cursor()
cursor.execute('''
    SELECT id FROM radiant_prd_343218191717_us_east_1_prd_fhir_datastore_90d6a59616343629b26cd05c6686f0e8_healthlake_view.patient
    WHERE id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
''')
print(cursor.fetchall())
"
```

### Error: "Binary links not found"
```bash
# Test S3 access
aws s3 ls s3://radiant-prd-343218191717-us-east-1-prd-ehr-pipeline/prd/ \
  --profile 343218191717_AWSAdministratorAccess
```

---

## 📋 VALIDATION CHECKLIST

After extraction completes:

- [ ] Bundle JSON file created
- [ ] Patient resource included
- [ ] Conditions (diagnoses) included
- [ ] Procedures (surgeries) included  
- [ ] MedicationRequests included
- [ ] Observations included
- [ ] Encounters included
- [ ] File size < 5 MB
- [ ] Estimated tokens < 50,000

---

## ➡️ NEXT STEPS

Once bundle extraction succeeds:

1. **Review the bundle JSON** - Check data quality
2. **Extract clinical notes** from DocumentReference + Binary
3. **Generate BRIM CSVs** combining bundle + notes
4. **Upload to BRIM UI** for testing
5. **Validate against manual CSVs**

---

## 📞 NEED HELP?

If extraction fails:
1. Check the error message carefully
2. Verify AWS credentials are valid
3. Confirm Athena database name is correct
4. Test individual queries in Athena console
5. Review logs in `pilot_output/` directory

---

**Ready to run?** Execute `python scripts/pilot_extract_patient.py` 🚀
