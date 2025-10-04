# Highest-Value Binary Document Selection Strategy

**Date**: October 4, 2025  
**Purpose**: Systematic, stepwise approach to identify the most valuable clinical documents for each patient to maximize free-text extraction accuracy while minimizing document volume  
**Patient Example**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

---

## 🎯 Core Principle: Temporal + Variable-Specific Targeting

**Strategy**: Match document types to critical temporal windows where specific variables are most likely documented.

### Variable Coverage Requirements (35 total variables)

**PRIORITY 1 Variables** (Athena CSV - NO documents needed): 11 variables
- Demographics: `patient_gender`, `date_of_birth`, `age_at_diagnosis`, `race`, `ethnicity`
- Medications: `chemotherapy_agent`, `chemo_start_date`, `chemo_end_date`, `chemotherapy_status`
- Imaging: `imaging_type`, `imaging_date`

**PRIORITY 2 Variables** (Free-text extraction REQUIRED): 24 variables
- Diagnosis: `primary_diagnosis` (1), `diagnosis_date` (1), `who_grade` (1), `tumor_location` (1)
- Molecular: `idh_mutation` (1), `mgmt_methylation` (1), `braf_status` (1)
- Surgery: `surgery_date` (1), `surgery_type` (1), `surgery_extent` (1), `surgery_location` (1)
- Chemotherapy details: `chemotherapy_line` (1), `chemotherapy_route` (1), `chemotherapy_dose` (1)
- Radiation: `radiation_therapy_yn` (1), `radiation_start_date` (1), `radiation_dose` (1), `radiation_fractions` (1)
- Clinical status: `clinical_status` (1), `progression_date` (1), `recurrence_date` (1)
- Imaging details: `tumor_size` (1), `contrast_enhancement` (1), `imaging_findings` (1)

---

## 📊 Step 1: Map Clinical Timeline for Patient

### Patient C1277724 Timeline

```
2005-05-13: Birth (calculated from age_at_diagnosis)
|
2018-05-28: First Surgery (age 4763 days = 13.0 years)
2018-06-04: Diagnosis Date (pathology result, 7 days post-surgery)
|
2018-10-01: Chemotherapy #1 START (Vinblastine) - 1st line
|
2019-05-01: Chemotherapy #1 END (Vinblastine)
2019-05-15: Progression #1 detected
2019-05-15: Chemotherapy #2 START (Bevacizumab) - 2nd line
|
2021-03-10: Second Surgery (age 5780 days = 15.8 years)
2021-04-30: Chemotherapy #2 END (Bevacizumab)
2021-05-01: Chemotherapy #3 START (Selumetinib) - 3rd line
|
2018-2025: 51 MRI Brain studies (surveillance imaging)
|
2025-Present: Ongoing follow-up
```

### Critical Temporal Windows

**Window 1: Diagnosis Period** (2018-05-27 to 2018-06-15)
- **Duration**: 3 weeks around diagnosis
- **Key Events**: First surgery, pathology diagnosis, molecular testing
- **Target Variables**: `diagnosis_date`, `primary_diagnosis`, `who_grade`, `tumor_location`, `braf_status`, `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location`

**Window 2: Treatment Initiation** (2018-10-01 ±14 days)
- **Duration**: 2 weeks before/after chemo start
- **Key Event**: Start of 1st line chemotherapy
- **Target Variables**: `chemotherapy_line`, `chemotherapy_route`, `chemotherapy_dose`

**Window 3: First Progression** (2019-05-01 to 2019-05-31)
- **Duration**: 1 month around progression
- **Key Events**: End of 1st line therapy, progression detected, start of 2nd line therapy
- **Target Variables**: `progression_date`, `clinical_status`, `tumor_size`, `contrast_enhancement`, `imaging_findings`

**Window 4: Second Surgery** (2021-03-10 ±7 days)
- **Duration**: 2 weeks around 2nd surgery
- **Key Event**: Repeat resection for progression
- **Target Variables**: `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location`, `recurrence_date`

**Window 5: Ongoing Surveillance** (2022-2025)
- **Duration**: Recent 3 years
- **Key Events**: Multiple MRI follow-ups, ongoing selumetinib therapy
- **Target Variables**: `clinical_status`, `tumor_size`, `imaging_findings`, `contrast_enhancement`

---

## 📋 Step 2: Define High-Value Document Types by Variable Requirements

### Document Type Priority Matrix

| Document Type | Variables Covered (Count) | Temporal Windows | Priority | Expected Count |
|---------------|---------------------------|------------------|----------|----------------|
| **Surgical Pathology Report** | `primary_diagnosis`, `who_grade`, `tumor_location`, `braf_status`, `diagnosis_date` (5) | Window 1, Window 4 | ⭐⭐⭐ CRITICAL | 2 |
| **Molecular Testing Report** | `braf_status`, `idh_mutation`, `mgmt_methylation` (3) | Window 1 | ⭐⭐⭐ CRITICAL | 1 |
| **Complete Operative Note** | `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location`, `tumor_location` (5) | Window 1, Window 4 | ⭐⭐⭐ CRITICAL | 2 |
| **MRI Radiology Report (Diagnosis)** | `tumor_location`, `tumor_size`, `contrast_enhancement`, `imaging_findings`, `diagnosis_date` (5) | Window 1 | ⭐⭐⭐ CRITICAL | 1 |
| **MRI Radiology Report (Progression)** | `progression_date`, `clinical_status`, `tumor_size`, `contrast_enhancement`, `imaging_findings` (5) | Window 3 | ⭐⭐ HIGH | 1-2 |
| **Oncology Consultation Note** | `chemotherapy_line`, `chemotherapy_route`, `chemotherapy_dose`, `clinical_status` (4) | Window 2, Window 3 | ⭐⭐ HIGH | 2-3 |
| **MRI Radiology Report (Surveillance)** | `clinical_status`, `tumor_size`, `imaging_findings`, `contrast_enhancement` (4) | Window 5 | ⭐ MEDIUM | 3-5 |
| **Radiation Oncology Note** | `radiation_therapy_yn`, `radiation_start_date`, `radiation_dose`, `radiation_fractions` (4) | Any | ⭐ MEDIUM | 0-1 |
| **Post-Op/Pathology Addendum** | `molecular` markers, `who_grade` updates (2) | Window 1 | ⭐ MEDIUM | 0-1 |
| **Treatment Summary** | `chemotherapy_line`, timeline overview (2) | Any | ⭐ MEDIUM | 0-1 |

---

## 🔍 Step 3: Query Strategy by Document Type

### Query 1: Surgical Pathology Reports (TOP PRIORITY)

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.category_coding_display,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Pathology report type codes
    dr.type_coding_display ILIKE '%pathology%'
    OR dr.type_coding_display ILIKE '%surgical pathology%'
    OR dr.type_coding_display ILIKE '%biopsy%'
    OR dr.category_coding_display ILIKE '%pathology%'
  )
  AND (
    -- Target diagnosis period (Window 1: 2018-05-27 to 2018-06-15)
    dr.date BETWEEN '2018-05-20' AND '2018-06-20'
    OR dr.context_period_start BETWEEN '2018-05-20' AND '2018-06-20'
    
    -- OR Target 2nd surgery period (Window 4: 2021-03-03 to 2021-03-17)
    OR dr.date BETWEEN '2021-03-03' AND '2021-03-20'
    OR dr.context_period_start BETWEEN '2021-03-03' AND '2021-03-20'
  )
ORDER BY dr.date ASC
LIMIT 3;
```

**Expected Results**: 2 pathology reports (one per surgery)  
**Variables Covered**: `primary_diagnosis`, `who_grade`, `tumor_location`, `diagnosis_date`  
**S3 Availability Check**: REQUIRED before adding to project.csv

---

### Query 2: Molecular Testing Reports

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.category_coding_display
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Molecular/genetic testing type codes
    dr.type_coding_display ILIKE '%molecular%'
    OR dr.type_coding_display ILIKE '%genetic%'
    OR dr.type_coding_display ILIKE '%genomic%'
    OR dr.type_coding_display ILIKE '%NGS%'
    OR dr.type_coding_display ILIKE '%sequencing%'
    OR dr.type_coding_display ILIKE '%BRAF%'
    OR dr.category_coding_display ILIKE '%laboratory%'
  )
  AND (
    -- Target diagnosis period + 3 months for molecular results
    dr.date BETWEEN '2018-05-20' AND '2018-09-30'
  )
ORDER BY dr.date ASC
LIMIT 2;
```

**Expected Results**: 1-2 molecular testing reports  
**Variables Covered**: `braf_status`, `idh_mutation`, `mgmt_methylation`  
**Gold Standard Value**: KIAA1549-BRAF fusion detected

---

### Query 3: Complete Operative Notes

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Operative note type codes
    dr.type_coding_display ILIKE '%operative%'
    OR dr.type_coding_display ILIKE '%surgical%'
    OR dr.type_coding_display ILIKE '%operation%'
    OR dr.type_coding_display ILIKE '%procedure%'
    OR dr.type_coding_display ILIKE '%op note%'
  )
  AND (
    dr.type_coding_display NOT ILIKE '%brief%'  -- Exclude brief op notes
    AND dr.type_coding_display NOT ILIKE '%anesthesia%'  -- Exclude anesthesia
  )
  AND (
    -- Target first surgery (Window 1: 2018-05-28)
    dr.date BETWEEN '2018-05-25' AND '2018-06-05'
    OR dr.context_period_start BETWEEN '2018-05-25' AND '2018-06-05'
    
    -- OR Target second surgery (Window 4: 2021-03-10)
    OR dr.date BETWEEN '2021-03-05' AND '2021-03-15'
    OR dr.context_period_start BETWEEN '2021-03-05' AND '2021-03-15'
  )
ORDER BY dr.date ASC
LIMIT 3;
```

**Expected Results**: 2 complete operative notes (one per surgery)  
**Variables Covered**: `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location`, `tumor_location`  
**CRITICAL**: Must be "complete" operative notes (NOT "brief" notes - brief notes lack surgical details)

---

### Query 4: MRI Radiology Reports (Diagnosis Period)

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Radiology report type codes
    dr.type_coding_display ILIKE '%radiology%'
    OR dr.type_coding_display ILIKE '%MRI%'
    OR dr.type_coding_display ILIKE '%imaging%'
    OR dr.category_coding_display ILIKE '%radiology%'
  )
  AND (
    -- Target PRE-OPERATIVE imaging (diagnosis period)
    -- Window 1: 2018-05-27 (pre-surgery scan)
    dr.date BETWEEN '2018-05-20' AND '2018-05-28'
    OR dr.context_period_start BETWEEN '2018-05-20' AND '2018-05-28'
  )
ORDER BY dr.date DESC  -- Most recent pre-op scan
LIMIT 1;
```

**Expected Results**: 1 MRI report (pre-operative, showing initial tumor)  
**Variables Covered**: `tumor_location`, `tumor_size`, `contrast_enhancement`, `imaging_findings`, `diagnosis_date`  
**Timing Logic**: Pre-operative MRI defines baseline tumor characteristics

---

### Query 5: MRI Radiology Reports (Progression Period)

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Radiology report type codes
    dr.type_coding_display ILIKE '%radiology%'
    OR dr.type_coding_display ILIKE '%MRI%'
    OR dr.type_coding_display ILIKE '%imaging%'
    OR dr.category_coding_display ILIKE '%radiology%'
  )
  AND (
    -- Target Window 3: First Progression (2019-05-01 to 2019-05-31)
    dr.date BETWEEN '2019-04-15' AND '2019-06-15'
    OR dr.context_period_start BETWEEN '2019-04-15' AND '2019-06-15'
  )
ORDER BY dr.date ASC
LIMIT 2;
```

**Expected Results**: 1-2 MRI reports showing progression  
**Variables Covered**: `progression_date`, `clinical_status`, `tumor_size`, `contrast_enhancement`, `imaging_findings`  
**Clinical Context**: MRI showing tumor growth triggers 2nd line therapy

---

### Query 6: Oncology Consultation Notes

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Oncology note type codes
    dr.type_coding_display ILIKE '%oncology%'
    OR dr.type_coding_display ILIKE '%hematology%'
    OR dr.type_coding_display ILIKE '%hem/onc%'
    OR dr.type_coding_display ILIKE '%consultation%'
    OR dr.type_coding_display ILIKE '%clinic%'
  )
  AND (
    -- Target Window 2: Treatment Initiation (2018-10-01 ±14 days)
    dr.date BETWEEN '2018-09-15' AND '2018-10-15'
    
    -- OR Window 3: First Progression/2nd Line Start (2019-05-15 ±14 days)
    OR dr.date BETWEEN '2019-05-01' AND '2019-06-01'
    
    -- OR 3rd Line Start (2021-05-01 ±14 days)
    OR dr.date BETWEEN '2021-04-15' AND '2021-05-15'
  )
ORDER BY dr.date ASC
LIMIT 4;
```

**Expected Results**: 2-4 oncology notes (one per treatment line initiation)  
**Variables Covered**: `chemotherapy_line`, `chemotherapy_route`, `chemotherapy_dose`, `clinical_status`  
**Critical Content**: Treatment plans, dosing, line of therapy rationale

---

### Query 7: MRI Radiology Reports (Recent Surveillance)

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date,
    dr.context_period_start
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Radiology report type codes
    dr.type_coding_display ILIKE '%radiology%'
    OR dr.type_coding_display ILIKE '%MRI%'
    OR dr.type_coding_display ILIKE '%imaging%'
    OR dr.category_coding_display ILIKE '%radiology%'
  )
  AND (
    -- Target Window 5: Recent surveillance (2022-2025)
    dr.date BETWEEN '2022-01-01' AND '2025-12-31'
  )
ORDER BY dr.date DESC  -- Most recent scans
LIMIT 5;
```

**Expected Results**: 3-5 recent MRI reports  
**Variables Covered**: `clinical_status`, `tumor_size`, `imaging_findings`, `contrast_enhancement`  
**Purpose**: Longitudinal disease status tracking (stable vs progressive)

---

### Query 8: Radiation Oncology Notes (If Applicable)

**DocumentReference Query**:
```sql
SELECT 
    dr.id AS document_reference_id,
    dr.subject_reference,
    dr.type_coding_display,
    dr.content_attachment_url,
    dr.date
FROM fhir_v1_prd_db.document_reference dr
WHERE dr.subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND dr.status = 'current'
  AND (
    -- Radiation oncology type codes
    dr.type_coding_display ILIKE '%radiation%'
    OR dr.type_coding_display ILIKE '%radiotherapy%'
    OR dr.type_coding_display ILIKE '%rad onc%'
  )
ORDER BY dr.date ASC
LIMIT 2;
```

**Expected Results**: 0 for C1277724 (no radiation documented)  
**Variables Covered**: `radiation_therapy_yn`, `radiation_start_date`, `radiation_dose`, `radiation_fractions`  
**Note**: For C1277724, absence of results confirms `radiation_therapy_yn='No'`

---

## 📊 Step 4: Document Selection Matrix for C1277724

### Recommended Document Package

| Priority | Document Type | Temporal Window | Expected Count | Variables Covered (Primary) | S3 Check Required |
|----------|---------------|-----------------|----------------|----------------------------|-------------------|
| 1 | Surgical Pathology Report #1 | 2018-05-28 ±7 days | 1 | `primary_diagnosis`, `who_grade`, `tumor_location`, `diagnosis_date`, `braf_status` | ✅ |
| 2 | Molecular Testing Report | 2018-06-04 +90 days | 1 | `braf_status` (confirmation), `idh_mutation`, `mgmt_methylation` | ✅ |
| 3 | Complete Operative Note #1 | 2018-05-28 ±3 days | 1 | `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location` | ✅ |
| 4 | MRI Report (Pre-Op) | 2018-05-27 | 1 | `tumor_location`, `tumor_size`, `contrast_enhancement`, `imaging_findings` | ✅ |
| 5 | Oncology Note (1st Line Start) | 2018-10-01 ±14 days | 1 | `chemotherapy_line`, `chemotherapy_route`, `chemotherapy_dose` | ✅ |
| 6 | MRI Report (Progression #1) | 2019-05-15 ±30 days | 1-2 | `progression_date`, `clinical_status`, `tumor_size`, `imaging_findings` | ✅ |
| 7 | Oncology Note (2nd Line Start) | 2019-05-15 ±14 days | 1 | `chemotherapy_line` (2nd), dose, route | ✅ |
| 8 | Complete Operative Note #2 | 2021-03-10 ±3 days | 1 | `surgery_date`, `surgery_type`, `surgery_extent`, `surgery_location` | ✅ |
| 9 | Surgical Pathology Report #2 | 2021-03-10 ±7 days | 1 | `recurrence_date`, `who_grade` (confirm), `tumor_location` | ✅ |
| 10 | Oncology Note (3rd Line Start) | 2021-05-01 ±14 days | 1 | `chemotherapy_line` (3rd), dose, route | ✅ |
| 11 | MRI Reports (Recent Surveillance) | 2022-2025 (latest 3-5) | 3-5 | `clinical_status`, `tumor_size`, `imaging_findings` (longitudinal) | ✅ |

**Total Targeted Documents**: 15-18 high-value documents  
**Total Variables Covered**: All 24 free-text variables  
**Coverage**: ~100% of required free-text extraction needs

---

## 🔧 Step 5: S3 Availability Verification Strategy

### Before Adding Document to project.csv

**Python Code for S3 Check**:
```python
import boto3

def verify_binary_availability(binary_id, s3_bucket='healthlake-fhir-data-343218191717-us-east-1'):
    """
    Check if Binary document exists in S3 before adding to project.csv.
    
    Args:
        binary_id: FHIR Binary ID from DocumentReference.content_attachment_url
        s3_bucket: S3 bucket name
    
    Returns:
        bool: True if Binary exists in S3, False otherwise
    """
    s3_client = boto3.client('s3', region_name='us-east-1')
    
    # Apply period → underscore transformation due to S3 naming bug
    s3_filename = binary_id.replace('.', '_')
    s3_key = f"prd/source/Binary/{s3_filename}"
    
    try:
        # Use head_object (faster than get_object, doesn't download content)
        s3_client.head_object(Bucket=s3_bucket, Key=s3_key)
        print(f"✅ AVAILABLE: {binary_id}")
        return True
    except s3_client.exceptions.NoSuchKey:
        print(f"❌ MISSING: {binary_id} (not in S3)")
        return False
    except Exception as e:
        print(f"⚠️ ERROR: {binary_id} - {str(e)}")
        return False

# Example usage
document_references = [
    ('doc_ref_1', 'Binary/e.ABC123'),
    ('doc_ref_2', 'Binary/e.DEF456'),
    # ... from Athena queries
]

available_documents = []
for doc_ref_id, binary_url in document_references:
    binary_id = binary_url.split('/')[-1]  # Extract Binary ID from URL
    if verify_binary_availability(binary_id):
        available_documents.append((doc_ref_id, binary_url))

print(f"\nAvailable documents: {len(available_documents)}/{len(document_references)}")
```

### Fallback Strategy if S3 Unavailable

**If target document NOT in S3**:
1. Query for ALTERNATIVE documents in same temporal window
2. Expand date range by ±7 days
3. Accept related document types (e.g., "brief operative note" if "complete operative note" missing)
4. Document substitution in project.csv metadata

**Example**:
```python
# If "Surgical Pathology Report #1" missing (2018-05-28)
# Fallback: Query for ANY pathology report 2018-05-20 to 2018-06-15
# Accept: "Biopsy report", "Frozen section report", "Pathology consult"
```

---

## 📈 Step 6: Longitudinal Data Requirements

### Variables Requiring Longitudinal Tracking

**many_per_note scope variables** (require MULTIPLE documents over time):

1. **Surgery Variables** (longitudinal: 2 surgeries for C1277724)
   - `surgery_date`: 2018-05-28, 2021-03-10
   - `surgery_type`: Both "Tumor Resection"
   - `surgery_extent`: Both "Partial Resection"
   - `surgery_location`: Both "Cerebellum/Posterior Fossa"
   - **Document Need**: 2 operative notes (one per surgery)

2. **Chemotherapy Variables** (longitudinal: 3 treatment lines for C1277724)
   - `chemotherapy_agent`: Vinblastine, Bevacizumab, Selumetinib
   - `chemo_start_date`: 2018-10-01, 2019-05-15, 2021-05-01
   - `chemo_end_date`: 2019-05-01, 2021-04-30, (ongoing)
   - `chemotherapy_status`: completed, completed, active
   - `chemotherapy_line`: 1st line, 2nd line, 3rd line
   - `chemotherapy_route`: Intravenous, Intravenous, Oral
   - `chemotherapy_dose`: 6 mg/m2, 10 mg/kg, 25 mg/m2
   - **Document Need**: 3 oncology notes (one per treatment initiation)

3. **Clinical Status** (longitudinal: multiple assessments over 7 years)
   - `clinical_status`: Stable, Progressive, Stable, Progressive, Stable...
   - **Document Need**: 5-10 MRI reports across timeline

4. **Imaging Findings** (longitudinal: 51 MRI studies for C1277724)
   - `imaging_type`: Mostly "MRI Brain" (from patient_imaging.csv - PRIORITY 1)
   - `imaging_date`: 51 dates from patient_imaging.csv - PRIORITY 1)
   - `tumor_size`: Changes over time (growth/shrinkage)
   - `contrast_enhancement`: May change with treatment
   - `imaging_findings`: Impression at each timepoint
   - **Document Need**: 3-8 representative MRI reports (diagnosis, progression, recent surveillance)

5. **Tumor Location** (potentially longitudinal: multifocal or progression to new sites)
   - C1277724: Cerebellum/Posterior Fossa (primary) → +Brain Stem-Midbrain/Tectum, +Temporal Lobe (progression)
   - **Document Need**: MRI reports showing location changes over time

---

## ⚡ Step 7: Query Execution Priority Order

### Execution Sequence (Optimize for Critical Variables First)

**Phase 1: Diagnosis Core Variables** (Execute First)
```
Query 1: Surgical Pathology Report #1 → diagnosis_date, primary_diagnosis, who_grade
Query 2: Molecular Testing Report → braf_status, idh_mutation, mgmt_methylation
Query 3: Complete Operative Note #1 → surgery_date, surgery_type, surgery_extent, surgery_location
Query 4: MRI Report (Pre-Op) → tumor_location, tumor_size, baseline imaging_findings
```
**Expected: 4 documents | Variables: 14 | S3 Check: REQUIRED**

**Phase 2: Treatment Variables** (Execute Second)
```
Query 5: Oncology Note (1st Line) → chemotherapy_line, chemotherapy_route, chemotherapy_dose
Query 7: Oncology Note (2nd Line) → chemotherapy_line (2nd), dose, route
Query 10: Oncology Note (3rd Line) → chemotherapy_line (3rd), dose, route
```
**Expected: 3 documents | Variables: 3 (with multiple instances) | S3 Check: REQUIRED**

**Phase 3: Longitudinal Surgical/Progression** (Execute Third)
```
Query 8: Complete Operative Note #2 → surgery_date (2nd), surgery_type, surgery_extent, surgery_location
Query 9: Surgical Pathology Report #2 → recurrence_date, who_grade (confirm), tumor_location (progression)
Query 6: MRI Report (Progression) → progression_date, clinical_status, tumor_size, imaging_findings
```
**Expected: 3-4 documents | Variables: 6 | S3 Check: REQUIRED**

**Phase 4: Surveillance Status** (Execute Fourth)
```
Query 11: MRI Reports (Recent) → clinical_status (longitudinal), tumor_size (current), imaging_findings (stable vs progressive)
```
**Expected: 3-5 documents | Variables: 4 (longitudinal tracking) | S3 Check: REQUIRED**

**Phase 5: Radiation Check** (Execute Last - Often N/A)
```
Query 8: Radiation Oncology Notes → radiation_therapy_yn, radiation_start_date, radiation_dose, radiation_fractions
```
**Expected: 0 for C1277724 | Variables: 4 | S3 Check: REQUIRED if found**

---

## 🎯 Step 8: Quality Metrics for Document Selection

### Success Criteria

**Variable Coverage**:
- ✅ **100% of free-text variables** have at least 1 targeted document
- ✅ **Longitudinal variables** have multiple documents spanning timeline
- ✅ **Critical temporal windows** (diagnosis, progression, surgery) each have 2-3 documents

**Document Efficiency**:
- ✅ **<20 documents total** (vs 84 in enhanced workflow or 9,348 available)
- ✅ **<1% of available documents** used (highly selective)
- ✅ **Each document covers 3-5 variables** (high variable density)

**Temporal Coverage**:
- ✅ **Diagnosis period** (2018-05-27 to 2018-06-15): 4 documents
- ✅ **Treatment initiation** (2018-10-01): 1 document
- ✅ **First progression** (2019-05-15): 2 documents
- ✅ **Second surgery** (2021-03-10): 2 documents
- ✅ **Recent surveillance** (2022-2025): 3-5 documents

**S3 Availability**:
- ✅ **100% of selected documents verified in S3** before adding to project.csv
- ⚠️ **Fallback documents identified** for high-priority missing items
- ✅ **Substitution strategy documented** if target document unavailable

---

## 📝 Step 9: Implementation Pseudocode

```python
def select_highest_value_documents(patient_fhir_id, s3_bucket, max_documents=20):
    """
    Select highest-value Binary documents for a patient.
    
    Returns:
        List of (document_reference_id, binary_id, document_type, temporal_window, variables_covered)
    """
    
    # Step 1: Extract patient timeline from Athena structured data
    timeline = extract_patient_timeline(patient_fhir_id)
    # Returns: {
    #   'diagnosis_date': '2018-06-04',
    #   'surgery_dates': ['2018-05-28', '2021-03-10'],
    #   'chemo_start_dates': ['2018-10-01', '2019-05-15', '2021-05-01'],
    #   'imaging_dates': [... 51 dates ...],
    #   'progression_periods': ['2019-05-15', ...]
    # }
    
    # Step 2: Define temporal windows based on timeline
    windows = define_temporal_windows(timeline)
    # Returns: [
    #   {'name': 'Diagnosis', 'start': '2018-05-20', 'end': '2018-06-20', 'priority': 1},
    #   {'name': 'Treatment_Init_1', 'start': '2018-09-15', 'end': '2018-10-15', 'priority': 2},
    #   ...
    # ]
    
    # Step 3: Execute queries in priority order
    selected_documents = []
    
    for priority_level in [1, 2, 3, 4, 5]:
        queries = get_queries_for_priority(priority_level, windows, patient_fhir_id)
        
        for query_name, sql_query, expected_count, variables in queries:
            # Execute Athena query
            results = execute_athena_query(sql_query)
            
            # Verify S3 availability for each result
            for doc_ref_id, binary_url in results:
                binary_id = extract_binary_id(binary_url)
                
                if verify_binary_availability(binary_id, s3_bucket):
                    selected_documents.append({
                        'document_reference_id': doc_ref_id,
                        'binary_id': binary_id,
                        'document_type': query_name,
                        'variables_covered': variables,
                        'priority': priority_level
                    })
                    
                    # Stop if reached expected count for this query
                    if len([d for d in selected_documents if d['document_type'] == query_name]) >= expected_count:
                        break
            
            # Stop if reached max documents
            if len(selected_documents) >= max_documents:
                break
        
        if len(selected_documents) >= max_documents:
            break
    
    # Step 4: Validate variable coverage
    coverage = validate_variable_coverage(selected_documents)
    
    if coverage['uncovered_variables']:
        print(f"⚠️ WARNING: {len(coverage['uncovered_variables'])} variables not covered:")
        for var in coverage['uncovered_variables']:
            print(f"  - {var}")
        
        # Attempt to add fallback documents for uncovered variables
        fallback_docs = query_fallback_documents(coverage['uncovered_variables'], patient_fhir_id)
        selected_documents.extend(fallback_docs)
    
    # Step 5: Generate project.csv rows
    project_csv_rows = []
    for doc in selected_documents:
        binary_content = fetch_binary_content(doc['binary_id'], s3_bucket)
        
        project_csv_rows.append({
            'NOTE_ID': doc['document_reference_id'],
            'PERSON_ID': patient_fhir_id,
            'NOTE_DATETIME': doc.get('date', ''),
            'NOTE_TEXT': binary_content,
            'NOTE_TITLE': doc['document_type']
        })
    
    return project_csv_rows, coverage

# Example execution
patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
s3_bucket = 'healthlake-fhir-data-343218191717-us-east-1'

rows, coverage = select_highest_value_documents(patient_fhir_id, s3_bucket, max_documents=18)

print(f"✅ Selected {len(rows)} documents")
print(f"✅ Variable coverage: {coverage['coverage_percent']}%")
print(f"✅ Variables covered: {len(coverage['covered_variables'])}/24")
```

---

## 📊 Expected Outcome for C1277724

### Document Selection Summary

**Total Documents**: 15-18 high-value documents  
**Total Variables Covered**: 24/24 free-text variables (100%)  
**Document Types**:
- 2 Surgical pathology reports
- 1 Molecular testing report
- 2 Complete operative notes
- 1 Pre-operative MRI
- 1-2 Progression MRI reports
- 3 Oncology consultation notes
- 3-5 Recent surveillance MRI reports
- 0 Radiation oncology notes (N/A for this patient)

**Temporal Coverage**:
- Diagnosis period (2018-05): 4 documents
- Treatment initiation (2018-10): 1 document
- First progression (2019-05): 2 documents
- Second surgery (2021-03): 2 documents
- Surveillance (2022-2025): 4 documents

**Expected Accuracy**:
- Structured data variables (Athena CSV): 95-100% (11/11 variables)
- Free-text variables: 90-95% (24/24 variables with high-quality targeted documents)
- **Overall: 92-97% expected accuracy** 🎯

---

## 🔄 Generalization to Other Patients

### Adaptable Framework

**Step 1**: Extract patient timeline from Athena structured data
- Surgery dates from `patient_procedures` or FHIR Procedure
- Medication start dates from `patient_medications`
- Imaging dates from `patient_imaging`

**Step 2**: Identify critical temporal windows
- Diagnosis: First surgery date ±14 days
- Each treatment line: Medication start date ±14 days
- Progression: Imaging dates where tumor_size increased
- Surveillance: Most recent 3-5 imaging dates

**Step 3**: Query documents matching temporal windows + document type
- Use same SQL templates with patient-specific dates
- Adjust expected counts based on patient complexity (1 surgery vs 5 surgeries)

**Step 4**: Verify S3 availability before adding
- Always check S3 before adding to project.csv (57% availability rate)
- Use fallback queries for missing documents

**Step 5**: Validate variable coverage
- Ensure all 24 free-text variables have at least 1 targeted document
- Add fallback documents if coverage <100%

---

## ✅ Summary: Highest-Value Document Selection Principles

1. **Temporal Targeting**: Match documents to critical clinical events (diagnosis, surgery, treatment changes, progression)
2. **Variable Density**: Prioritize documents covering 3-5 variables each (pathology, operative notes, MRI reports)
3. **Longitudinal Capture**: Include multiple documents for `many_per_note` variables (surgeries, chemotherapy lines, clinical status)
4. **S3 Verification**: Always check Binary availability before adding to project.csv (avoid 43% failure rate)
5. **Fallback Strategy**: Define alternative documents for each temporal window in case of S3 unavailability
6. **Quality Over Quantity**: 15-20 targeted documents >> 84 random documents >> 9,348 total available
7. **100% Variable Coverage**: Every free-text variable must have at least 1 high-quality document in its optimal temporal window

**Result**: Surgical precision in document selection → Maximum accuracy with minimum document volume → Scalable to any patient timeline
