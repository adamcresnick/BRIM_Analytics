# Migration from MRN to FHIR ID Only

**Date**: 2025-10-11
**Status**: ✅ Complete

---

## Summary

All scripts and configuration files have been updated to use **patient FHIR ID as the primary and only identifier**. MRN references have been completely removed.

---

## Changes Made

### Configuration Files

**`patient_config_template.yaml`**
- ✅ Removed `patient_mrn` field
- ✅ Made `patient_fhir_id` the primary identifier
- ✅ Updated all file path examples to use FHIR ID
- ✅ Updated comments and documentation

**Example config naming:**
- Old: `patient_config_C1277724.yaml`
- **New**: `patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml`

### Python Scripts

All 5 scripts updated:
1. ✅ `create_structured_surgery_events.py`
2. ✅ `create_structured_imaging_timeline.py`
3. ✅ `extract_data_dictionary_fields.py`
4. ✅ `generate_brim_inputs.py`
5. ✅ `generate_radiology_opnote_brim_csvs.py`

**Changes in each script:**
- Variable: `self.patient_mrn` → `self.patient_fhir_id`
- Config key: `config['patient_mrn']` → `config['patient_fhir_id']`
- File naming: `*_{MRN}.csv` → `*_{FHIR_ID}.csv`
- Display text: "Patient MRN" → "Patient FHIR ID"
- BRIM PERSON_ID: Now uses FHIR ID instead of MRN

### Output Files

**File naming convention changed:**

| Old Naming | New Naming |
|------------|------------|
| `STRUCTURED_surgery_events_C1277724.md` | `STRUCTURED_surgery_events_e4BwD8ZYDBccepXcJ.Ilo3w3.md` |
| `surgery_events_staging_C1277724.csv` | `surgery_events_staging_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |
| `STRUCTURED_imaging_timeline_C1277724.md` | `STRUCTURED_imaging_timeline_e4BwD8ZYDBccepXcJ.Ilo3w3.md` |
| `imaging_timeline_staging_C1277724.csv` | `imaging_timeline_staging_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |
| `data_dictionary_fields_C1277724.csv` | `data_dictionary_fields_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |
| `project_C1277724.csv` | `project_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |
| `variables_C1277724.csv` | `variables_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |
| `decisions_C1277724.csv` | `decisions_e4BwD8ZYDBccepXcJ.Ilo3w3.csv` |

### BRIM CSV Format

**project.csv PERSON_ID field:**
- Old: Used MRN (`C1277724`)
- **New**: Uses FHIR ID (`e4BwD8ZYDBccepXcJ.Ilo3w3`)

This ensures consistent identification across all systems using FHIR standard.

---

## Verification

To verify the migration was successful:

```bash
# Check no MRN references remain in scripts
grep -r "patient_mrn\|MRN" scripts/*.py

# Should only find comments/documentation, not variable usage
```

**Expected output**: Only template comments, no actual variable usage

---

## Usage Examples

### Old Workflow (MRN-based)
```bash
# ❌ OLD - NO LONGER VALID
cp patient_config_template.yaml patient_config_C1277724.yaml
python scripts/generate_brim_inputs.py patient_config_C1277724.yaml
```

### New Workflow (FHIR ID-based)
```bash
# ✅ NEW - CURRENT STANDARD
cp patient_config_template.yaml patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml
python scripts/generate_brim_inputs.py patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml
```

---

## Rationale

1. **FHIR Standard**: FHIR ID is the primary identifier in AWS HealthLake
2. **Consistency**: All downstream processes use FHIR ID
3. **Deidentification**: FHIR IDs are already pseudonymized
4. **No MRN Dependency**: Eliminates need for MRN mapping tables
5. **Portability**: Works across all FHIR-compliant systems

---

## Impact on Existing Patients

**Patient e4BwD8ZYDBccepXcJ.Ilo3w3 (formerly C1277724):**
- ✅ All documentation uses FHIR ID
- ✅ All scripts accept FHIR ID in config
- ✅ All output files named with FHIR ID
- ✅ BRIM CSVs use FHIR ID as PERSON_ID

**Future patients:**
- Must provide FHIR ID in config file
- MRN is no longer required or used
- All staging file paths should reference FHIR ID

---

## Backwards Compatibility

⚠️ **BREAKING CHANGE**: Old config files using `patient_mrn` will fail.

**Migration path for old configs:**
1. Replace `patient_mrn: "C1277724"` with `patient_fhir_id: "e4BwD8ZYDBccepXcJ.Ilo3w3"`
2. Update `output_directory` path to use FHIR ID
3. Update `staging_files` paths to use FHIR ID

---

## Testing Checklist

- [ ] Config template uses only FHIR ID
- [ ] All scripts load `patient_fhir_id` from config
- [ ] Output files named with FHIR ID
- [ ] BRIM project.csv uses FHIR ID as PERSON_ID
- [ ] No `patient_mrn` variable usage in scripts
- [ ] Documentation updated with FHIR ID examples
- [ ] README reflects FHIR ID-only approach

---

## References

- **Config Template**: `patient_config_template.yaml`
- **Test Patient FHIR ID**: `e4BwD8ZYDBccepXcJ.Ilo3w3`
- **Gold Standard File**: `GOLD_STANDARD_C1277724.md` (legacy filename, content uses FHIR ID)
