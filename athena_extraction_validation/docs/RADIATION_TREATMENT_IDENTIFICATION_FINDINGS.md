# Radiation Treatment Identification in Athena FHIR Database

**Investigation Date:** 2025-10-11  
**Patients Analyzed:** 
- C1277724 (e4BwD8ZYDBccepXcJ.Ilo3w3) - Original patient with pilocytic astrocytoma
- eXdoUrDdY4gkdnZEs6uTeq-MEZEFJsVmSduLKRoTdXmE3 - New patient with brainstem glioma

## Executive Summary

**Key Finding:** ✅ **Oncology appointments CAN be identified** in the Athena FHIR database through the `appointment_service_type` subtable, but **radiation therapy procedures are NOT directly captured** in standard FHIR resource types.

### What We Found

| Data Source | Radiation/Oncology Data | Patient C1277724 | New Patient |
|------------|------------------------|------------------|-------------|
| **Appointment Service Types** | ✅ **YES** | **25 oncology appointments** | 0 |
| Appointment Text Fields | Partial (imaging-related) | 67 mentions | 4 mentions |
| Procedure Table | ❌ NO | 0 | 0 |
| Service Request Table | ❌ NO | 0 | 0 |
| Document Reference | Not tested (schema issues) | - | - |

## Detailed Findings

### 1. ✅ Appointment Service Type Coding (PRIMARY SOURCE)

**Location:** `appointment_service_type` subtable  
**Field:** `service_type_coding` (JSON array with display values)

**Found for C1277724:**
- **25 oncology-related appointments** (June 2019 - May 2021)
- **22 fulfilled, 3 cancelled**

**Appointment Types Identified:**
- `FOLLOW U/EST(ONCOLOGY)` - 21 appointments (84%)
- `NON-PROVIDER VISIT (ONCOLOGY)` - 2 appointments (8%)
- `ONCOLOGY ECHO` - 1 appointment (4%)
- `SICK(ONCOLOGY)` - 1 appointment (4%)

**Temporal Pattern:**
```
2019-06-04 to 2019-08-20: ~Weekly oncology follow-ups (likely active treatment period)
2019-09-17 to 2020-05-26: Monthly oncology follow-ups (surveillance/maintenance)
2021-05-03: Single oncology echo (cardiac monitoring)
```

**Clinical Interpretation:**
- Weekly visits during June-August 2019 suggest **active oncology treatment phase**
- Could represent chemotherapy administration, treatment monitoring, or radiation therapy follow-ups
- Monthly visits 2019-2020 suggest **surveillance phase**
- Gap from May 2020 to May 2021, then single cardiac echo (treatment-related cardiac monitoring)

### 2. Appointment Text Fields (SECONDARY SOURCE)

**Fields Searched:** `appointment_type_text`, `description`, `comment`, `patient_instruction`

**Findings:**
- **C1277724:** 67 appointments with "radiology" mentions (mostly MRI instructions)
- **New Patient:** 4 appointments with "radiology" mentions (MRI instructions)

**Assessment:** These are **diagnostic radiology** (imaging) appointments, NOT radiation therapy appointments.

### 3. ❌ Procedure Table

**Query:** Searched for radiation/radiotherapy/proton/photon/beam/brachytherapy/IMRT terms

**Result:** **0 procedures found** for both patients

**Conclusion:** Radiation therapy procedures are NOT coded as FHIR `Procedure` resources in this database.

### 4. ❌ Service Request Table

**Query:** Searched for radiation therapy orders/referrals

**Result:** **0 service requests found** for both patients

**Conclusion:** Radiation therapy orders are NOT captured as FHIR `ServiceRequest` resources.

### 5. Document Reference Table

**Status:** Schema validation incomplete (column name mismatches)

**Next Steps:** Would need to search clinical notes text for radiation therapy mentions, but requires:
- Correct schema mapping for document_reference table
- Access to document binary content (stored in S3)
- Text extraction and NLP processing

## Recommended Identification Strategy

### Primary Method: Appointment Service Type Coding

**Query Pattern:**
```sql
SELECT DISTINCT
    ap.participant_actor_reference as patient_id,
    a.id as appointment_id,
    a.start,
    a.status,
    CAST(ast.service_type_coding AS VARCHAR) as service_type_coding_str,
    ast.service_type_text
FROM fhir_v2_prd_db.appointment a
JOIN fhir_v2_prd_db.appointment_participant ap ON a.id = ap.appointment_id
LEFT JOIN fhir_v2_prd_db.appointment_service_type ast ON a.id = ast.appointment_id
WHERE ap.participant_actor_reference = 'Patient/{fhir_id}'
  AND (
    LOWER(CAST(ast.service_type_coding AS VARCHAR)) LIKE '%radiation%'
    OR LOWER(CAST(ast.service_type_coding AS VARCHAR)) LIKE '%oncolog%'
    OR LOWER(CAST(ast.service_type_coding AS VARCHAR)) LIKE '%rad onc%'
    OR LOWER(ast.service_type_text) LIKE '%radiation%'
    OR LOWER(ast.service_type_text) LIKE '%oncolog%'
  )
ORDER BY a.start
```

**Expected Service Types:**
- `FOLLOW U/EST(ONCOLOGY)` - Oncology follow-up visits
- `NON-PROVIDER VISIT (ONCOLOGY)` - Oncology procedures/infusions without provider
- `ONCOLOGY ECHO` - Oncology-related cardiac monitoring
- `SICK(ONCOLOGY)` - Acute oncology sick visits
- Potentially: `RADIATION ONCOLOGY`, `RAD ONC FOLLOW UP`, `SIMULATION`, etc.

### Secondary Method: Appointment Specialty Coding

**Table:** `appointment_specialty`  
**Field:** `specialty_coding` (JSON array)

**Note:** In our sample, specialty fields were empty, but may contain:
- Radiation Oncology specialty codes
- Medical Oncology specialty codes
- Hematology/Oncology specialty codes

### Tertiary Method: Clinical Notes

**Requires:**
1. Query `document_reference` for oncology-related document types
2. Retrieve document binary content from S3 (via `content_attachment_url`)
3. Extract text and search for:
   - "radiation therapy"
   - "radiotherapy"
   - "XRT"
   - "IMRT"
   - "proton therapy"
   - "Gray" or "Gy" (radiation dose units)
   - "fractions"
   - Treatment field descriptions
   - Radiation oncology provider names

## Limitations and Gaps

### 1. **Radiation Procedures Not Captured**
- Individual radiation therapy sessions/fractions are NOT in the procedure table
- This is likely because:
  - Radiation therapy is delivered outside the Epic EHR system
  - External radiation oncology systems don't feed back to FHIR
  - Billing/procedural codes for radiation may be in claims data, not clinical FHIR

### 2. **Appointment Type Ambiguity**
- "ONCOLOGY" appointments could be:
  - Medical oncology (chemotherapy)
  - Radiation oncology
  - Combined care
- Cannot distinguish radiation vs. medical oncology without:
  - Provider specialty information
  - Location/department data
  - Clinical note content

### 3. **Treatment Details Missing**
Even if radiation appointments are identified, we lack:
- Radiation dose (Gray/Gy)
- Number of fractions
- Treatment fields/sites
- Technique (IMRT, proton, 3D-conformal, etc.)
- Treatment intent (curative vs. palliative)
- Completion status

## Clinical Research Implications

### For BRIM Trial Data

**What We Can Extract:**
- ✅ **Oncology appointment schedule** (dates, frequency, status)
- ✅ **Treatment phase identification** (intensive vs. surveillance)
- ✅ **Oncology visit types** (follow-up, sick visit, non-provider visit)
- ⚠️ **Possible radiation treatment period** (inferred from weekly oncology visits)

**What We CANNOT Extract:**
- ❌ Confirmation that radiation therapy was delivered
- ❌ Radiation dose and fractionation
- ❌ Radiation treatment fields/sites
- ❌ Radiation technique
- ❌ Radiation completion vs. discontinuation

**Workaround Options:**
1. **Clinical Notes Mining:** Extract radiation therapy details from progress notes
2. **External Data Integration:** Link to radiation oncology system (e.g., ARIA, Varian)
3. **Manual Chart Review:** For trial patients, manually abstract radiation data
4. **Claims Data:** Use billing codes (CPT 77xxx) to identify radiation procedures

## Implementation for BRIM Extraction Scripts

### Add Oncology Appointments Extraction

**New Script:** `extract_oncology_appointments.py`

```python
def extract_oncology_appointments(self) -> pd.DataFrame:
    """Extract oncology-related appointments via service_type coding"""
    
    query = f"""
    SELECT DISTINCT
        ap.participant_actor_reference as patient_id,
        a.id as appointment_fhir_id,
        a.start as appointment_start,
        a.end as appointment_end,
        a.status as appointment_status,
        a.minutes_duration,
        a.description,
        a.comment,
        CAST(ast.service_type_coding AS VARCHAR) as service_type_coding,
        ast.service_type_text,
        CAST(asp.specialty_coding AS VARCHAR) as specialty_coding,
        asp.specialty_text
    FROM {self.database}.appointment a
    JOIN {self.database}.appointment_participant ap ON a.id = ap.appointment_id
    LEFT JOIN {self.database}.appointment_service_type ast ON a.id = ast.appointment_id
    LEFT JOIN {self.database}.appointment_specialty asp ON a.id = asp.appointment_id
    WHERE ap.participant_actor_reference = 'Patient/{self.patient_fhir_id}'
      AND (
        LOWER(CAST(ast.service_type_coding AS VARCHAR)) LIKE '%oncolog%'
        OR LOWER(CAST(ast.service_type_coding AS VARCHAR)) LIKE '%radiation%'
        OR LOWER(ast.service_type_text) LIKE '%oncolog%'
        OR LOWER(ast.service_type_text) LIKE '%radiation%'
      )
    ORDER BY a.start
    """
    
    results = self.execute_query(query, "Query oncology appointments")
    
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame(results)
    
    # Parse JSON service_type_coding to extract display value
    def extract_display(json_str):
        if pd.isna(json_str) or json_str == '':
            return ''
        try:
            data = json.loads(json_str)
            if isinstance(data, list) and len(data) > 0:
                return data[0].get('display', '')
        except:
            import re
            match = re.search(r"'display':\s*'([^']+)'", json_str)
            if match:
                return match.group(1)
        return ''
    
    df['service_type_display'] = df['service_type_coding'].apply(extract_display)
    df['specialty_display'] = df['specialty_coding'].apply(extract_display)
    
    # Calculate age
    df['age_at_appointment_days'] = df['appointment_start'].apply(self.calculate_age_days)
    df['appointment_date'] = df['appointment_start'].str[:10]
    
    return df
```

### BRIM CSV Output

**Filename:** `oncology_appointments.csv`

**Columns:**
- `appointment_fhir_id`
- `appointment_date`
- `age_at_appointment_days`
- `appointment_start`
- `appointment_end`
- `appointment_status`
- `minutes_duration`
- `service_type_display` (e.g., "FOLLOW U/EST(ONCOLOGY)")
- `specialty_display`
- `description`
- `comment`

**BRIM Variable Mapping:**
- `ONCOLOGY_APPOINTMENT_DATE` ← `appointment_date`
- `ONCOLOGY_APPOINTMENT_TYPE` ← `service_type_display`
- `ONCOLOGY_APPOINTMENT_STATUS` ← `appointment_status`

## Next Steps

1. ✅ **Implemented:** Query appointment_service_type for oncology appointments
2. ⏳ **Pending:** Add oncology appointment extraction to BRIM scripts
3. ⏳ **Pending:** Test with additional patients to validate pattern
4. ⏳ **Recommended:** Investigate clinical notes for radiation therapy details
5. ⏳ **Recommended:** Explore encounter table for oncology encounter types
6. ⏳ **Recommended:** Check observation table for radiation-related observations (e.g., skin reactions)

## Validation

**Test Case:** Patient C1277724
- **Expected:** Oncology appointments during known treatment period
- **Result:** ✅ **25 oncology appointments identified** (June 2019 - May 2021)
- **Pattern:** Weekly visits → Monthly visits → Single followup
- **Clinical Fit:** Consistent with active treatment followed by surveillance

## Conclusion

**Radiation treatment identification in Athena FHIR database:**

✅ **Possible via appointment service types** - Can identify oncology appointments which may include radiation visits

❌ **NOT possible via procedure resources** - Individual radiation therapy sessions not captured

⚠️ **Requires clinical notes for confirmation** - Need to parse free-text documentation to confirm radiation vs. chemotherapy

**Recommendation:** Use appointment service types as primary source for oncology encounter dates, then supplement with clinical notes extraction for treatment type confirmation and details.

---

**Files Created:**
- `scripts/search_radiation_procedures.py` - ❌ No results
- `scripts/search_radiation_service_requests.py` - ❌ No results
- `scripts/search_radiation_appointment_service_types.py` - ✅ 25 results
- `reports/radiation_oncology_appointments.csv` - ✅ Saved

**Git Status:** Ready to commit radiation identification investigation findings
