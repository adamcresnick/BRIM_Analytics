# STRUCTURED Surgery Events with Event Type Classification

**Patient FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
**Patient FHIR ID**: e4BwD8ZYDBccepXcJ.Ilo3w3
**Birth Date**: 2005-05-13
**Generated**: 2025-10-11 21:01:36

---

## Summary

| Event | Age (days) | Surgery Date | Event Type | Operative Note Status |
|-------|-----------|--------------|------------|----------------------|
| Event 1 | 4763 | 2018-05-28 | 5 (Initial CNS Tumor) | ✓ Linked |
| Event 2 | 4763 | 2018-05-28 | 8 (Progressive) | ✓ Linked |

---

## Event 1: Initial CNS Tumor (age 4763 days)

**Event Number**: 1
**Event Type**: 5 (Initial CNS Tumor)
**Surgery Date**: 2018-05-28
**Age at Surgery**: 4763 days (~13.0 years)
**Surgery Type**: CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION
**Procedure FHIR ID**: `fSUOuC2zGppXw6ft5yRFL6idtK2kZjjV6DoTHxFsq87w4`
**Performer**: Phillip Storm, MD
**Indication**: Brain tumor

### Linked Operative Note

- **Document Type**: OP Note - Complete (Template or Full Dictation)
- **Document Date**: 2018-05-29 13:39:15+00:00
- **Context Period Start**: 2018-05-28T13:57:00Z ✓ (matches surgery date)
- **S3 Available**: Yes
- **Document FHIR ID**: `eurQFNx9i3htV0u0-bYDhm3Fq0UjBMQZ0Eew-0eJgIEw3`
- **S3 Key**: `prd/source/Binary/eADaCVEBCzyLvONCZYztXwh9vRcAhhSaUx_7EISWwBIg3`

### Extent of Resection

**BRIM Extraction Target**: Extract extent from operative note sections:
- Procedure performed
- Post-operative impression
- Surgeon's assessment

**Expected Values** (Data Dictionary):
- `1` = Gross/Near total resection
- `2` = Partial resection
- `3` = Biopsy only
- `4` = Unavailable

### Event Type Determination Logic

**Logic**: First surgery → Always event_type = 5 (Initial CNS Tumor)

---

## Event 2: Progressive (age 4763 days)

**Event Number**: 2
**Event Type**: 8 (Progressive)
**Surgery Date**: 2018-05-28
**Age at Surgery**: 4763 days (~13.0 years)
**Surgery Type**: ENDOSCOPIC THIRD VENTRICULOSTOMY
**Procedure FHIR ID**: `fiej.qAjQP4JthnNG9OC17XpWAgClD979toiL7tTFaX44`
**Performer**: Phillip Storm, MD
**Indication**: Brain tumor

### Linked Operative Note

- **Document Type**: OP Note - Complete (Template or Full Dictation)
- **Document Date**: 2018-05-29 13:39:15+00:00
- **Context Period Start**: 2018-05-28T13:57:00Z ✓ (matches surgery date)
- **S3 Available**: Yes
- **Document FHIR ID**: `eurQFNx9i3htV0u0-bYDhm3Fq0UjBMQZ0Eew-0eJgIEw3`
- **S3 Key**: `prd/source/Binary/eADaCVEBCzyLvONCZYztXwh9vRcAhhSaUx_7EISWwBIg3`

### Extent of Resection

**BRIM Extraction Target**: Extract extent from operative note sections:
- Procedure performed
- Post-operative impression
- Surgeon's assessment

**Expected Values** (Data Dictionary):
- `1` = Gross/Near total resection
- `2` = Partial resection
- `3` = Biopsy only
- `4` = Unavailable

### Event Type Determination Logic

**Logic**: Subsequent surgery → event_type = 8 (Progressive) [default assumption]

⚠️ **Note**: In production, event type would be determined by:
- If previous surgery was GTR/NTR → event_type = 7 (Recurrence)
- If previous surgery was Partial/STR/Biopsy → event_type = 8 (Progressive)

---

## Data Dictionary Field Mapping

| Event | event_type | age_at_event_days | surgery | age_at_surgery | extent_of_tumor_resection |
|-------|-----------|------------------|---------|----------------|---------------------------|
| Event 1 | 5 | 4763 | 1 (Yes) | 4763 | [EXTRACT FROM OP NOTE] |
| Event 2 | 8 | 4763 | 1 (Yes) | 4763 | [EXTRACT FROM OP NOTE] |

---

## Instructions for BRIM Upload

1. Upload this STRUCTURED document as `NOTE_ID='STRUCTURED_surgery_events'`
2. Upload linked operative notes (S3 documents) for extent of resection extraction
3. Update BRIM variables.csv to prioritize this STRUCTURED document
4. Run BRIM extraction job
5. Validate extracted extent values against data dictionary codes
