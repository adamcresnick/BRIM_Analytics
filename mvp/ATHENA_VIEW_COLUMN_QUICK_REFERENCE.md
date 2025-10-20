# Athena View Column Quick Reference

**Always check this BEFORE writing queries!**

---

## v_procedures_tumor

### Core Columns
```sql
procedure_fhir_id              -- FHIR resource ID
patient_fhir_id                -- Patient ID
proc_status                    -- Procedure status
proc_performed_date_time       -- ⚠️ NOT procedure_date (timestamp)
proc_code_text                 -- ⚠️ NOT procedure_code_text
proc_outcome_text              -- ⚠️ NOT procedure_outcome_text
pbs_body_site_text             -- ⚠️ NOT procedure_bodySite_text
```

### Tumor Surgery Filters
```sql
is_tumor_surgery               -- boolean
surgery_type                   -- 'craniotomy', 'csf_management', etc.
is_surgical_keyword            -- boolean
```

### Example Query
```sql
SELECT
    procedure_fhir_id,
    proc_performed_date_time,
    proc_code_text,
    proc_outcome_text,
    surgery_type
FROM v_procedures_tumor
WHERE patient_fhir_id = 'xxx'
  AND is_tumor_surgery = true
```

---

## v_binary_files

### Core Columns
```sql
document_reference_id          -- DocumentReference FHIR ID
binary_id                      -- ⚠️ NOT file_id
patient_fhir_id                -- Patient ID
content_type                   -- ⚠️ NOT file_content_type
content_size_bytes             -- ⚠️ NOT file_size_bytes
content_title                  -- ⚠️ NOT file_title
dr_date                        -- ⚠️ NOT parent_document_date (timestamp)
dr_category_text               -- ⚠️ NOT parent_document_category
dr_type_text                   -- Document type
dr_description                 -- Description
```

### Date Fields (all timestamp(3))
```sql
dr_date                        -- Document date
dr_context_period_start        -- Context start
dr_context_period_end          -- Context end
```

### Example Query
```sql
SELECT
    binary_id,
    dr_date,
    dr_category_text,
    content_title,
    content_size_bytes
FROM v_binary_files
WHERE patient_fhir_id = 'xxx'
  AND content_type = 'application/pdf'
  AND dr_category_text = 'Imaging Result'
  AND dr_date >= TIMESTAMP '2018-05-01'
```

---

## v_imaging

### Core Columns
```sql
patient_fhir_id                -- Patient ID
imaging_procedure_id           -- Procedure ID
imaging_date                   -- Imaging date (timestamp)
imaging_modality               -- MRI, CT, etc.
diagnostic_report_id           -- DiagnosticReport FHIR ID
report_conclusion              -- Report text
report_issued                  -- Report issued date
```

### Example Query
```sql
SELECT
    imaging_procedure_id,
    imaging_date,
    imaging_modality,
    report_conclusion
FROM v_imaging
WHERE patient_fhir_id = 'xxx'
  AND imaging_modality = 'MRI'
ORDER BY imaging_date
```

---

## v_medications

### Core Columns
```sql
medication_request_fhir_id     -- MedicationRequest ID
patient_fhir_id                -- Patient ID
mr_status                      -- ⚠️ Uses 'mr_' prefix
mr_intent                      -- order, plan, etc.
mr_authored_on                 -- ⚠️ NOT medication_date (timestamp)
medication_code_text           -- Medication name
```

### Example Query
```sql
SELECT
    medication_request_fhir_id,
    mr_authored_on,
    medication_code_text,
    mr_status
FROM v_medications
WHERE patient_fhir_id = 'xxx'
  AND mr_status = 'active'
```

---

## v_patient_demographics

### Core Columns
```sql
patient_fhir_id                -- Patient ID
pd_birth_date                  -- Birth date
pd_gender                      -- Gender
pd_deceased                    -- Deceased flag
pd_deceased_date_time          -- Death date
```

---

## Naming Convention Patterns

### Prefixes by Resource Type
| Prefix | FHIR Resource | Example |
|--------|---------------|---------|
| `proc_*` | Procedure | `proc_code_text` |
| `dr_*` | DocumentReference | `dr_date` |
| `pbs_*` | Procedure.bodySite | `pbs_body_site_text` |
| `pcc_*` | Procedure.code.coding | `pcc_code_coding_code` |
| `mr_*` | MedicationRequest | `mr_status` |
| `obs_*` | Observation | `obs_value` |
| `pd_*` | Patient (demographics) | `pd_birth_date` |

### Common Suffixes
| Suffix | Meaning |
|--------|---------|
| `_text` | Human-readable text |
| `_coding_code` | Coded value |
| `_coding_system` | Code system (e.g., SNOMED, LOINC) |
| `_display` | Display name |
| `_reference` | FHIR reference (e.g., `Patient/xxx`) |
| `_fhir_id` | FHIR resource ID |
| `_date_time` | Timestamp field |

---

## ⚠️ Common Mistakes

### DON'T Use These (They Don't Exist):
```sql
-- v_procedures_tumor
procedure_code_text            -- ❌ Use: proc_code_text
procedure_outcome_text         -- ❌ Use: proc_outcome_text
procedure_bodySite_text        -- ❌ Use: pbs_body_site_text
procedure_date                 -- ❌ Use: proc_performed_date_time

-- v_binary_files
file_id                        -- ❌ Use: binary_id
file_content_type              -- ❌ Use: content_type
parent_document_date           -- ❌ Use: dr_date
parent_document_category       -- ❌ Use: dr_category_text

-- v_medications
medication_date                -- ❌ Use: mr_authored_on
medication_status              -- ❌ Use: mr_status
```

---

## Validation Workflow

### BEFORE Writing ANY Query:

1. **Check this quick reference** ⬆️

2. **Run SHOW COLUMNS in Athena**:
   ```sql
   SHOW COLUMNS FROM fhir_prd_db.v_procedures_tumor;
   ```

3. **Use schema registry CLI**:
   ```bash
   python utils/athena_schema_registry.py v_procedures_tumor
   ```

4. **Test query in Athena console FIRST**

5. **Then add to Python code**

---

## Full Schema Documentation

For complete column lists, see:
- [ATHENA_VIEWS_MASTER_DATA_DICTIONARY.md](../../athena_views/documentation/ATHENA_VIEWS_MASTER_DATA_DICTIONARY.md)
- Run: `python utils/athena_schema_registry.py <view_name>`

---

**Last Updated**: 2025-10-19
**Maintained By**: Development Team
**Update When**: Any view schema changes
