# Radiation Dosage and Fraction Data - Analysis

**Question:** Does the radiation extraction script capture actual dosage (Gy) and fraction information?

**Short Answer:** ❌ **NO** - The appointment table does NOT contain radiation dose or fraction count data.

## What "Daily Fractions" Means

### Clinical Context

In radiation therapy:
- **Fraction** = One daily treatment session
- **Total Dose** = Sum of all fractions (measured in Gray, Gy)
- **Dose per Fraction** = Typical 1.8-2.0 Gy per fraction
- **Course** = Series of fractions (e.g., 30 fractions = 6 weeks)

**Example Treatment Course:**
```
Total Dose: 54 Gy
Fractions: 30
Dose per Fraction: 1.8 Gy
Schedule: Monday-Friday for 6 weeks
```

### What the Script Currently Captures

**Patient 2 (Milestone Pattern):**
```
Appointment Type: Milestone
Comment: "Start IMRT - DONE"
         "End of Radiation Treatment"
Duration: 6 weeks (inferred from dates)
Fractions: NOT CAPTURED (must infer ~30 from 6-week duration)
Dose: NOT CAPTURED
```

**Patient 4 (Daily Session Pattern):**
```
Appointment Type: Individual Treatment Session
Comment: "IMRT" or "IMRT (LINAC 3)"
Count: 12 appointments documented
Actual Fractions Delivered: 12 (can be counted)
Dose: NOT CAPTURED
```

## What IS Captured in Appointment Data

### Appointment Table Fields

```
Available in appointment table:
✓ id                        - Appointment ID
✓ start/end                 - Date and time
✓ status                    - fulfilled, cancelled, etc.
✓ comment                   - Free text (technique, milestones)
✓ patient_instruction       - Patient-facing instructions
✓ minutes_duration          - Appointment length
✗ dose                      - NOT PRESENT
✗ fraction_number           - NOT PRESENT
✗ total_fractions           - NOT PRESENT
✗ dose_per_fraction         - NOT PRESENT
```

### What We CAN Infer

**From Milestone Pattern (Patient 2):**
- Treatment start date: 2023-09-14
- Treatment end date: 2023-10-25
- Duration: 41 days = ~6 weeks
- **Inferred fractions**: 30 (typical 6-week course, 5 days/week)
- **Estimated total dose**: 54-60 Gy (typical for 30 fractions)

**From Daily Session Pattern (Patient 4):**
- Treatment sessions documented: 12
- Fulfilled sessions: 6-8 (rest cancelled)
- **Actual fractions delivered**: 6-8 (can count fulfilled appointments)
- **Estimated total dose**: 12-16 Gy (if 2 Gy per fraction)

### What We CANNOT Determine

❌ **Exact Total Dose (Gy)** - Not in appointment data
❌ **Dose per Fraction** - Not in appointment data
❌ **Planned vs. Delivered Fractions** - Only for milestone pattern
❌ **Treatment Target/Site** - Not in appointment data
❌ **Concurrent Chemotherapy** - Requires medication data

## Where Radiation Dose Data Might Be Found

### 1. Procedure Table ❌ (Already Checked)
**Status:** No radiation therapy procedures found for any test patient

**Query Already Run:**
```python
# From previous search_radiation_procedures.py
# Result: 0 procedures found
```

### 2. Service Request Table ❌ (Already Checked)
**Status:** No radiation therapy orders found

**Query Already Run:**
```python
# From previous search_radiation_service_requests.py
# Result: 0 service requests found
```

### 3. Observation Table ⚠️ (Not Yet Checked)
**Potential:** Might contain radiation dose observations

**Hypothesis:**
- Radiation dose might be recorded as clinical observation
- Could be in `observation_value_quantity` or similar fields
- Would need to search for radiation-related observation codes

**Need to Query:**
```sql
SELECT *
FROM observation o
JOIN observation_code_coding occ ON o.id = occ.observation_id
WHERE occ.code IN (
  -- LOINC codes for radiation dose
  'XXXXX-X'  -- Need to find correct codes
)
```

### 4. Diagnostic Report Table ⚠️ (Not Yet Checked)
**Potential:** Radiation oncology treatment summaries

**Hypothesis:**
- Radiation oncology reports might contain dose summaries
- Could be in `diagnostic_report_presented_form` (documents)
- Would be in text format, requiring parsing

**Need to Query:**
```sql
SELECT *
FROM diagnostic_report dr
JOIN diagnostic_report_code_coding drc ON dr.id = drc.diagnostic_report_id
WHERE LOWER(drc.display) LIKE '%radiation%'
```

### 5. Clinical Notes (Binary Documents) ⚠️ (Not Yet Checked)
**Potential:** Radiation oncology consult notes and treatment summaries

**Hypothesis:**
- Radiation oncology notes would contain:
  - Total dose prescribed
  - Fractionation scheme
  - Treatment technique
  - Target volumes
- Would be in DocumentReference table → S3 binaries

**Need to Query:**
```sql
SELECT *
FROM document_reference dr
WHERE dr.type LIKE '%Radiation Oncology%'
  OR dr.type LIKE '%Oncology Consult%'
```

### 6. External Radiation Oncology System ❌ (Outside FHIR)
**Most Likely Location:** Radiation dose data typically stored in:
- **ARIA** (Varian Eclipse)
- **MOSAIQ** (Elekta)
- **RayStation**
- Other radiation therapy information systems (RTIS)

**Status:** These systems typically do NOT integrate with FHIR EHR data

## Summary: What the Script Captures

### Currently Extracted ✓

1. **Radiation Therapy Presence:** Yes/No
2. **Radiation Oncology Consults:** Count and dates
3. **Treatment Technique:** IMRT, Proton, etc. (from comment text)
4. **Treatment Timeline:**
   - Start date (milestone pattern)
   - End date (milestone pattern)
   - Duration in weeks
5. **Re-irradiation:** Yes/No
6. **Treatment Sessions Count:** For daily session pattern

### NOT Extracted (Not Available in Appointment Data) ✗

1. **Total Radiation Dose (Gy)** ❌
2. **Dose per Fraction (Gy)** ❌
3. **Number of Fractions Planned** ❌
4. **Number of Fractions Delivered** ❌ (except for daily session pattern where we can count)
5. **Treatment Target/Site** ❌
6. **Beam Energy (MV)** ❌
7. **Treatment Technique Details** ❌ (beyond name like "IMRT")

## Recommendations

### For BRIM Trial Data Extraction

**Use Current Script to Extract:**
✓ Radiation therapy received (Yes/No)
✓ Rad onc consult dates
✓ Treatment start/end dates (when available)
✓ Treatment duration (weeks)
✓ Re-irradiation status
✓ Treatment technique (IMRT, proton, etc.)

**For Dosage Information, Need to:**

**Option 1: Search Additional FHIR Tables** (RECOMMENDED FIRST STEP)
```python
# 1. Check observation table for dose observations
# 2. Check diagnostic_report for radiation oncology reports
# 3. Check document_reference for rad onc notes
```

**Option 2: Extract from Clinical Notes** (LABOR INTENSIVE)
- Use existing S3 clinical notes extraction
- Search for radiation oncology notes
- Parse text for dose information
- Pattern: "prescribed dose: 54 Gy in 30 fractions"

**Option 3: Manual Chart Review** (GOLD STANDARD)
- Manually review radiation oncology records
- Extract dose from treatment summaries
- Most accurate but time-consuming

**Option 4: Contact Radiation Oncology Department** (IDEAL)
- Request data export from ARIA/MOSAIQ system
- Contains precise dose, fraction, and technique data
- Requires separate IRB approval and data sharing agreement

### Priority Actions

**HIGH PRIORITY:**
1. ✅ Use current script for timeline and technique extraction
2. 🔍 Check `observation` table for radiation dose observations
3. 🔍 Check `diagnostic_report` table for rad onc summaries

**MEDIUM PRIORITY:**
4. 🔍 Extract radiation oncology notes from S3 clinical notes
5. 📊 Parse notes for dose information (NLP/regex)

**LOW PRIORITY:**
6. 📞 Contact rad onc department for ARIA/MOSAIQ data access
7. 🔄 Set up ongoing data feed from radiation oncology systems

## Current Script Status

**What "Daily Fractions" Means in Script Context:**

When I said "daily fractions" in the documentation, I meant:
- **Individual treatment appointment records** (one per day)
- **NOT the actual fraction count or dose**
- Each appointment represents ONE treatment session
- Can COUNT appointments to estimate fractions delivered
- But dose per fraction is NOT captured

**Example:**
```
Patient 4 has 12 IMRT appointment records:
  - 6 fulfilled appointments
  - 6 cancelled appointments

Can infer: Patient received ~6 fractions of IMRT
Cannot determine: Total dose or dose per fraction
```

## Conclusion

**Current Script:**
- ✅ Excellent for identifying radiation therapy presence
- ✅ Good for treatment timeline extraction
- ✅ Captures treatment technique
- ❌ Does NOT capture radiation dose information
- ❌ Does NOT capture fraction counts (except by counting daily appointments)

**Dosage Data:**
- ❌ NOT in appointment table
- ⚠️ Might be in observation, diagnostic_report, or clinical notes
- 🎯 Most likely in external radiation oncology systems (ARIA/MOSAIQ)

**For BRIM Trial:**
- Use current script for timeline and technique
- If dose data is required, need to:
  1. Check observation/diagnostic_report tables
  2. Extract from clinical notes (S3)
  3. Or request data from radiation oncology systems

---

**Created:** 2025-10-12  
**Script:** `extract_radiation_data.py`  
**Status:** Production-ready for timeline/technique extraction  
**Limitation:** Does not capture radiation dose or exact fraction counts
