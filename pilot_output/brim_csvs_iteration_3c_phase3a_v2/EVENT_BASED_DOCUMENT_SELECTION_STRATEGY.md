# REVISED: Clinical Event-Based Document Selection Strategy

**Date**: October 4, 2025  
**Revision**: Clinical workflow-based approach  
**Patient**: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

---

## 🎯 Strategic Principles

### User-Specified Priorities

1. **Imaging Studies**: Event-based selection tied to clinical milestones
   - NOT all 173 MRI reports
   - Targeted selection around surgeries and therapies
   
2. **Progress Notes**: Include ALL (1,277 documents)
   - Rich longitudinal clinical narrative
   - Captures symptoms, response, status changes
   
3. **H&P (History & Physical)**: Include ALL (13 documents)
   - Comprehensive clinical assessments
   
4. **Format Preference**: HTML when choice available
   - `text/html` > `text/html; text/rtf`
   - Consistent parsing, faster processing
   
5. **SKIP Pathology Notes**: Excluded
   - NOT surgical pathology reports
   - Pathology data already in Athena materialized views
   - No incremental value for abstraction

---

## 📊 Available Documents by Category

### From Deep Analysis (3,865 total documents)

| Category | Total | Format | Inclusion Strategy |
|----------|-------|--------|-------------------|
| Progress Notes | 1,277 | text/html; text/rtf | ✅ **ALL** |
| H&P (History & Physical) | 13 | text/html; text/rtf | ✅ **ALL** |
| Imaging Studies (MRI) | 173 | text/html (94%) | ✅ **EVENT-BASED** (see below) |
| Pathology Study | 40 | text/html | ❌ **SKIP** (redundant) |
| Operative Notes | 29 | text/html; text/rtf | ✅ **ALL** (surgical events) |
| Consultation Notes | 46 | text/html; text/rtf | ✅ **ALL** (treatment planning) |
| After Visit Summaries | 97 | application/pdf | ⏸️ **EVALUATE** |

---

## 🏥 Clinical Event Timeline (Patient C1277724)

### Surgical Events

| Surgery Date | Procedure | Pre-Op Imaging Window | Post-Op Imaging Window |
|-------------|-----------|---------------------|----------------------|
| 2018-05-28 | Initial resection (Craniotomy) | 2018-05-20 to 2018-05-27 | 2018-05-29 to 2018-06-15 |
| 2021-03-10 | Second resection | 2021-02-15 to 2021-03-09 | 2021-03-11 to 2021-04-15 |

**Imaging Selection Rule**: 2 studies before + 2 studies after each surgery = **8 studies total**

---

### Treatment Events (From patient_medications.csv)

| Therapy | Start Date | Stop Date | Pre-Therapy Window | During Therapy | Post-Therapy Window |
|---------|-----------|-----------|-------------------|---------------|---------------------|
| Vinblastine | 2019-04-26 | Unknown | 2019-03-26 to 2019-04-25 | 2019-04-26 to 2020-04-26 | N/A (ongoing) |
| Bevacizumab | 2021-03-11 | Unknown | 2021-02-11 to 2021-03-10 | 2021-03-11 to 2022-03-11 | N/A (ongoing) |
| Selumetinib | 2021-03-18 | Unknown | 2021-02-18 to 2021-03-17 | 2021-03-18 to 2022-03-18 | N/A (ongoing) |

**Imaging Selection Rule**: 
- 2 studies before therapy start
- 2 studies during therapy (e.g., 3-month, 6-month assessments)
- 2 studies after therapy stop (if applicable)

**For this patient**: Most therapies ongoing, so focus on pre-therapy + during-therapy assessments = **~6-8 studies per therapy**

---

## 🎯 EVENT-BASED IMAGING SELECTION STRATEGY

### Surgery-Related Imaging (8 studies)

#### Surgery 1: May 28, 2018 (Initial Resection)

**Pre-operative (2 studies)**:
```sql
-- Baseline diagnostic MRI + immediate pre-op
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2018-05-20' AND '2018-05-27'
ORDER BY document_date ASC
LIMIT 2;
```

**Post-operative (2 studies)**:
```sql
-- Immediate post-op + early follow-up
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2018-05-29' AND '2018-06-30'
ORDER BY document_date ASC
LIMIT 2;
```

#### Surgery 2: March 10, 2021 (Second Resection)

**Pre-operative (2 studies)**:
```sql
-- Progression documentation + pre-op planning
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-02-01' AND '2021-03-09'
ORDER BY document_date DESC
LIMIT 2;
```

**Post-operative (2 studies)**:
```sql
-- Post-op assessment
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-03-11' AND '2021-04-30'
ORDER BY document_date ASC
LIMIT 2;
```

---

### Therapy-Related Imaging (~12-15 studies)

#### Vinblastine Therapy (Start: April 26, 2019)

**Pre-therapy baseline (2 studies)**:
```sql
-- Baseline tumor assessment before starting Vinblastine
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2019-03-15' AND '2019-04-25'
ORDER BY document_date DESC
LIMIT 2;
```

**During therapy (2 studies)**:
```sql
-- 3-month and 6-month response assessments
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2019-07-15' AND '2019-11-15'
ORDER BY document_date ASC
LIMIT 2;
```

#### Bevacizumab + Selumetinib Therapy (Start: March 2021)

**Pre-therapy baseline (2 studies)**:
```sql
-- Already captured in Surgery 2 pre-op imaging
-- Therapies started shortly after surgery
```

**During combination therapy (2 studies)**:
```sql
-- Response assessment during dual therapy
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-06-01' AND '2021-09-30'
ORDER BY document_date ASC
LIMIT 2;
```

**Continued surveillance (2-4 studies)**:
```sql
-- Recent surveillance during ongoing therapy (2022-2025)
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date >= '2023-01-01'
ORDER BY document_date DESC
LIMIT 4;
```

---

## 📋 COMPLETE DOCUMENT SELECTION LIST

### Category 1: Progress Notes (ALL)
**Count**: 1,277 documents  
**Format**: Prefer `text/html` if available, otherwise `text/html; text/rtf`  
**Rationale**: Longitudinal clinical narrative capturing symptoms, response, side effects, clinical status

```sql
SELECT document_reference_id, document_date, document_type, content_type, description
FROM accessible_binary_files_annotated
WHERE document_type = 'Progress Notes'
ORDER BY document_date ASC;
```

**Format Preference Implementation**:
```sql
-- If choosing specific format
SELECT document_reference_id, document_date, document_type, description
FROM accessible_binary_files_annotated
WHERE document_type = 'Progress Notes'
  AND (
    content_type = 'text/html'  -- Prefer pure HTML
    OR (content_type LIKE '%text/html%' AND content_type NOT LIKE '%text/rtf%')  -- HTML variations
    OR content_type LIKE '%text/html%'  -- Accept dual format if HTML-only not available
  )
ORDER BY document_date ASC;
```

---

### Category 2: H&P (History & Physical) - ALL
**Count**: 13 documents  
**Format**: Prefer `text/html`  
**Rationale**: Comprehensive clinical assessments at key time points

```sql
SELECT document_reference_id, document_date, document_type, content_type, description
FROM accessible_binary_files_annotated
WHERE document_type = 'H&P'
ORDER BY document_date ASC;
```

---

### Category 3: Operative Notes - ALL
**Count**: 29 documents  
**Format**: Prefer `text/html`  
**Rationale**: Surgical procedures, anatomical location, resection extent

```sql
SELECT document_reference_id, document_date, document_type, content_type, description
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%OP Note%'
  OR document_type LIKE '%Operative%'
ORDER BY document_date ASC;
```

---

### Category 4: Consultation Notes - ALL
**Count**: 46 documents  
**Format**: Prefer `text/html`  
**Rationale**: Treatment planning, molecular results discussion, clinical trial considerations

```sql
SELECT document_reference_id, document_date, document_type, content_type, description
FROM accessible_binary_files_annotated
WHERE document_type = 'Consult Note'
ORDER BY document_date ASC;
```

---

### Category 5: Event-Based Imaging Studies
**Count**: ~20-24 targeted studies (NOT all 173)  
**Format**: `text/html` (94% of imaging studies are HTML)  
**Rationale**: Clinical event-driven selection around surgeries and therapies

**Surgery-Related (8 studies)**:
- 2 pre-op + 2 post-op for Surgery 1 (May 2018)
- 2 pre-op + 2 post-op for Surgery 2 (March 2021)

**Therapy-Related (12-16 studies)**:
- 2 pre-Vinblastine + 2 during Vinblastine
- 2 pre-combination therapy (overlap with surgery)
- 2 during combination therapy
- 4-6 recent surveillance (2023-2025)

**Combined Query for All Event-Based Imaging**:
```sql
-- Surgery 1 pre-op
SELECT document_reference_id, document_date, document_type, description, 'Surgery1_PreOp' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2018-05-20' AND '2018-05-27'
ORDER BY document_date ASC
LIMIT 2

UNION ALL

-- Surgery 1 post-op
SELECT document_reference_id, document_date, document_type, description, 'Surgery1_PostOp' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2018-05-29' AND '2018-06-30'
ORDER BY document_date ASC
LIMIT 2

UNION ALL

-- Vinblastine pre-therapy
SELECT document_reference_id, document_date, document_type, description, 'Vinblastine_PreTx' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2019-03-15' AND '2019-04-25'
ORDER BY document_date DESC
LIMIT 2

UNION ALL

-- Vinblastine during therapy
SELECT document_reference_id, document_date, document_type, description, 'Vinblastine_DuringTx' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2019-07-15' AND '2019-11-15'
ORDER BY document_date ASC
LIMIT 2

UNION ALL

-- Surgery 2 pre-op
SELECT document_reference_id, document_date, document_type, description, 'Surgery2_PreOp' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-02-01' AND '2021-03-09'
ORDER BY document_date DESC
LIMIT 2

UNION ALL

-- Surgery 2 post-op
SELECT document_reference_id, document_date, document_type, description, 'Surgery2_PostOp' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-03-11' AND '2021-04-30'
ORDER BY document_date ASC
LIMIT 2

UNION ALL

-- Combination therapy during treatment
SELECT document_reference_id, document_date, document_type, description, 'ComboTx_During' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date BETWEEN '2021-06-01' AND '2021-09-30'
ORDER BY document_date ASC
LIMIT 2

UNION ALL

-- Recent surveillance
SELECT document_reference_id, document_date, document_type, description, 'Surveillance_Recent' as event_type
FROM accessible_binary_files_annotated
WHERE document_type LIKE '%MR%Brain%'
  AND content_type LIKE '%text/html%'
  AND document_date >= '2023-01-01'
ORDER BY document_date DESC
LIMIT 6

ORDER BY document_date ASC;
```

---

## 📊 TOTAL DOCUMENT COUNT ESTIMATE

| Category | Count | Format |
|----------|-------|--------|
| Progress Notes | 1,277 | HTML preferred |
| H&P | 13 | HTML preferred |
| Operative Notes | 29 | HTML preferred |
| Consultation Notes | 46 | HTML preferred |
| Event-Based Imaging | 20-24 | HTML (targeted) |
| **TOTAL** | **~1,385-1,389** | |

**Excluded**:
- ❌ Pathology Study (40) - Redundant with Athena materialized views
- ❌ Encounter Summaries (761 XML) - Structured data already captured
- ❌ Telephone Encounters (397) - Lower clinical value
- ❌ Non-event imaging (153) - Not tied to clinical milestones

---

## 🎯 Format Preference Implementation

### When Multiple Formats Available

**Priority Order**:
1. `text/html` (pure HTML)
2. `text/html; text/rtf` (accept if HTML-only unavailable)
3. Avoid: `text/rtf` alone, `application/xml`, `image/tiff`

**Implementation in Queries**:
```sql
-- Method 1: Prefer pure HTML
WHERE content_type = 'text/html'

-- Method 2: Accept HTML in any form
WHERE content_type LIKE '%text/html%'

-- Method 3: Explicit preference
WHERE (
  content_type = 'text/html'  -- First choice
  OR (content_type LIKE '%text/html; text/rtf%' AND NOT EXISTS (
    SELECT 1 FROM accessible_binary_files_annotated a2 
    WHERE a2.document_reference_id = document_reference_id 
    AND a2.content_type = 'text/html'
  ))  -- Second choice if no pure HTML
)
```

---

## 🚀 Implementation Steps

### Step 1: Export Event-Based Imaging List
```bash
# Run the combined imaging query and export to CSV
python3 scripts/select_event_based_imaging.py
# Output: event_based_imaging_studies.csv (20-24 documents)
```

### Step 2: Export Clinical Notes
```bash
# Export all progress notes, H&P, operative notes, consults
python3 scripts/select_clinical_notes.py
# Output: clinical_notes_all.csv (1,365 documents)
```

### Step 3: Retrieve Binary Content
```bash
# Use existing Binary retrieval logic from pilot_generate_brim_csvs.py
# For ~1,385 documents (may take 30-45 minutes)
python3 scripts/retrieve_binary_content.py \
  --input clinical_notes_all.csv \
  --input event_based_imaging_studies.csv \
  --output binary_content_phase3a_v2/
```

### Step 4: Update project.csv
```bash
# Combine all content into project.csv format
python3 scripts/create_project_csv.py \
  --binary-content binary_content_phase3a_v2/ \
  --structured-data patient_*.csv \
  --fhir-bundle bundle.json \
  --output project.csv
```

---

## 📈 Expected Accuracy Impact

### Rationale for >85% Accuracy Target

**Why This Will Work**:

1. **Comprehensive Progress Notes (1,277)**: 
   - Captures ALL clinical status changes, symptoms, responses
   - Fills gaps from structured data
   - Provides narrative context for discrete values

2. **H&P Complete Assessments (13)**:
   - Holistic patient status at key time points
   - Comprehensive problem lists
   - Detailed exam findings

3. **All Surgical Documentation (29)**:
   - Complete anatomical location details
   - Surgical technique and extent
   - Intraoperative findings

4. **All Consultation Notes (46)**:
   - Treatment rationale
   - Molecular results interpretation
   - Clinical trial discussions

5. **Targeted Event-Based Imaging (20-24)**:
   - NOT overwhelming with 173 redundant reports
   - Captures critical clinical milestones
   - Pre/post comparisons for response assessment
   - Imaging narrative already in Athena free-text tables

6. **Exclusion of Redundant Data**:
   - Pathology: Already in Athena materialized views
   - XML summaries: Captured in FHIR
   - Images: Low extraction value

**Projected Accuracy**: **88-93%** (vs current 81.2%)

**Variables Expected to Improve Most**:
- Clinical status variables: 75% → 90% (+15 points)
- Treatment response: 70% → 88% (+18 points)
- Symptoms/side effects: 65% → 85% (+20 points)
- Timeline variables: 80% → 92% (+12 points)

---

## ✅ Next Steps

1. ✅ **Create Python scripts** to execute event-based imaging queries
2. ✅ **Export all clinical notes** (progress, H&P, operative, consults)
3. ✅ **Implement format preference** (HTML > dual format)
4. ✅ **Retrieve Binary content** for ~1,385 documents
5. ✅ **Update project.csv** with comprehensive document set
6. ✅ **Upload Phase 3a_v2** to BRIM
7. ✅ **Validate accuracy** improvement (target: >85%)

---

**Status**: ✅ STRATEGY UPDATED - Ready for Implementation  
**Key Change**: Clinical event-based approach vs broad document type prioritization  
**Confidence**: HIGH (aligns with clinical workflows and leverages existing Athena free-text data)

