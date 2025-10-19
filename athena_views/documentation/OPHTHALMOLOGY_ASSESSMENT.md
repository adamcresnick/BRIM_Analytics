# Ophthalmology Assessment Data Strategy for Brain Tumor Patients

**Date**: 2025-10-18
**Clinical Context**: Brain tumor patients often suffer visual deficits due to:
- Optic pathway involvement (optic nerve, chiasm, radiation)
- Increased intracranial pressure → papilledema
- Treatment-related toxicity (radiation, chemotherapy)
- Tumor compression of visual structures

---

## Clinical Requirements

### Key Ophthalmology Assessments Needed

1. **Visual Acuity Testing**
   - Quantitative scores (Snellen, logMAR, ETDRS)
   - Age-appropriate methods (HOTV, Lea, Cardiff, Teller for pediatrics)
   - Distance and near vision

2. **Visual Field Testing**
   - Perimetry results
   - Field defects (hemianopia, quadrantanopia, scotomas)
   - Goldmann vs automated perimetry

3. **Optic Disc Examination**
   - Papilledema (optic disc swelling)
   - Optic atrophy (pallor)
   - Cup-to-disc ratio
   - Hemorrhages or exudates

4. **Optical Coherence Tomography (OCT)**
   - Retinal nerve fiber layer (RNFL) thickness
   - Ganglion cell layer analysis
   - Optic disc imaging
   - Macular thickness

5. **Ophthalmology Encounters/Exams**
   - Exam dates
   - Provider type (ophthalmology, neuro-ophthalmology)
   - Exam type (screening vs comprehensive)

---

## FHIR Data Sources Analysis

### Source 1: **Observation** (Structured Test Results)

**Expected Data**:
- Visual acuity measurements with scores
- Visual field test results
- OCT measurements (RNFL thickness, etc.)
- Optic disc findings

**Key Fields**:
- `code_text` - Test name
- `value_quantity_value` + `value_quantity_unit` - Numeric results
- `value_string` - Text results
- `value_codeable_concept_text` - Categorical results
- `effective_date_time` - Test date

**Search Strategy**:
```sql
WHERE LOWER(o.code_text) LIKE '%visual%acuity%'
   OR LOWER(o.code_text) LIKE '%visual%field%'
   OR LOWER(o.code_text) LIKE '%oct%'
   OR LOWER(o.code_text) LIKE '%optic%disc%'
   OR LOWER(o.code_text) LIKE '%papilledema%'
   OR LOWER(o.code_text) LIKE '%rnfl%'  -- retinal nerve fiber layer
```

---

### Source 2: **Procedure** (Ophthalmology Exams Performed)

**Expected Data**:
- Eye exams documented as procedures
- OCT imaging procedures
- Visual field testing procedures
- Fundoscopy/ophthalmoscopy

**Key Fields**:
- `code_text` - Procedure name
- `performed_date_time` - Exam date
- `status` - completed, in-progress
- `outcome_text` - Procedure outcome

**CPT Codes** (if available):
- 92002/92004 - Ophthalmologic examination (new patient)
- 92012/92014 - Ophthalmologic examination (established)
- 92081-92083 - Visual field testing
- 92133-92134 - OCT imaging
- 92225-92226 - Fundus photography

**Search Strategy**:
```sql
WHERE LOWER(p.code_text) LIKE '%ophthalmolog%'
   OR LOWER(p.code_text) LIKE '%visual%field%'
   OR LOWER(p.code_text) LIKE '%oct%'
   OR LOWER(p.code_text) LIKE '%fundus%'
   OR LOWER(p.code_text) LIKE '%eye%exam%'
```

---

### Source 3: **ServiceRequest** (Orders for Ophthalmology)

**Expected Data**:
- Orders for ophthalmology consults
- Orders for visual field tests
- Orders for OCT
- Referrals to ophthalmology

**Key Fields**:
- `code_text` - Test/service ordered
- `authored_on` - Order date
- `occurrence_date_time` - Scheduled date
- `status` - active, completed, cancelled
- `intent` - order, plan

**Search Strategy**:
```sql
WHERE LOWER(sr.code_text) LIKE '%ophthalmolog%'
   OR LOWER(sr.code_text) LIKE '%visual%'
   OR LOWER(sr.code_text) LIKE '%oct%'
   OR LOWER(sr.code_text) LIKE '%optic%'
   OR LOWER(sr.code_text) LIKE '%eye%'
```

---

### Source 4: **DiagnosticReport** (Formal Test Reports)

**Expected Data**:
- OCT reports
- Visual field test reports
- Ophthalmology consultation reports

**Key Fields**:
- `code_text` - Report type
- `conclusion` - Report findings/impressions
- `effective_date_time` - Report date
- `status` - final, preliminary

**Search Strategy**:
```sql
WHERE LOWER(dr.code_text) LIKE '%ophthalmolog%'
   OR LOWER(dr.code_text) LIKE '%oct%'
   OR LOWER(dr.code_text) LIKE '%visual%field%'
   OR LOWER(dr.conclusion) LIKE '%optic%disc%'
   OR LOWER(dr.conclusion) LIKE '%papilledema%'
```

---

### Source 5: **DocumentReference** (Binary Files/Images)

**Expected Data**:
- OCT images
- Fundus photographs
- Visual field printouts
- Scanned ophthalmology reports

**Key Fields**:
- `description` - Document description
- `content_attachment_url` - S3 URL to binary file
- `content_attachment_content_type` - MIME type (PDF, JPEG, DICOM)
- `type_text` - Document type

**Search Strategy**:
```sql
WHERE LOWER(dr.description) LIKE '%oct%'
   OR LOWER(dr.description) LIKE '%fundus%'
   OR LOWER(dr.description) LIKE '%visual%field%'
   OR LOWER(dr.description) LIKE '%ophthalmolog%'
   OR LOWER(dr.type_text) LIKE '%eye%'
```

---

### Source 6: **Encounter** (Ophthalmology Visits)

**Expected Data**:
- Ophthalmology clinic visits
- Eye exam encounters

**Key Fields**:
- `service_type_text` - Ophthalmology
- `type_text` - Encounter type
- `period_start` - Visit date

**Search Strategy**:
```sql
WHERE LOWER(e.service_type_text) LIKE '%ophthalmolog%'
   OR LOWER(et.type_text) LIKE '%eye%'
   OR LOWER(et.type_text) LIKE '%vision%'
```

---

## Improved Search Term Taxonomy

### Your Original Terms (Good Foundation)
```python
terms = [
    "ophthal",    # Ophthalmology/ophthalmic
    "ophtha",     # Variant
    "ophtho",     # Variant
    "optic",      # Optic nerve/disc
    "visual",     # Visual acuity/fields
    "acuity",     # Visual acuity
    "logmar",     # LogMAR scoring
    "snellen",    # Snellen chart
    "hotv",       # HOTV test (pediatric)
    "etdrs",      # ETDRS chart
    "lea",        # Lea symbols (pediatric)
    "cardiff",    # Cardiff acuity cards
    "teller",     # Teller acuity cards
    "pallor",     # Optic disc pallor
    "edema",      # Papilledema
    "oct",        # Optical coherence tomography
    "disc"        # Optic disc
]
```

### Enhanced Taxonomy (Organized by Clinical Concept)

```python
ophthalmology_terms = {
    # General ophthalmology
    "general": [
        "ophthal", "ophtha", "ophtho",  # Ophthalmology variants
        "eye exam", "eye examination",
        "neuro-ophthal", "neuroophthal"  # Neuro-ophthalmology
    ],

    # Visual acuity testing
    "visual_acuity": [
        "visual acuity", "acuity",
        "va score", "bcva",  # best corrected visual acuity
        "logmar", "snellen", "etdrs",
        "hotv", "lea", "cardiff", "teller",  # Pediatric methods
        "20/", "6/",  # Snellen notation (20/20, 6/6)
        "counting fingers", "hand motion", "light perception",  # Low vision
        "near vision", "distance vision"
    ],

    # Visual field testing
    "visual_fields": [
        "visual field", "vf", "perimetry",
        "goldmann", "humphrey",  # Common perimeter types
        "hemianopia", "quadrantanopia", "scotoma",  # Field defects
        "field defect", "field loss",
        "confrontation", "tangent screen",
        "30-2", "24-2", "10-2"  # Test patterns
    ],

    # Optic disc/nerve
    "optic_disc": [
        "optic disc", "optic nerve", "optic disk",
        "papilledema", "papilloedema",
        "disc edema", "disc swelling",
        "optic atrophy", "pallor",
        "cup-to-disc", "c/d ratio",
        "optic neuritis", "optic neuropathy",
        "disc hemorrhage", "disc drusen"
    ],

    # OCT imaging
    "oct": [
        "oct", "optical coherence",
        "rnfl", "retinal nerve fiber",
        "ganglion cell", "gca", "gcc",  # ganglion cell analysis/complex
        "macular thickness", "optic nerve head",
        "peripapillary", "macula oct"
    ],

    # Fundoscopy/imaging
    "fundus": [
        "fundus", "fundoscopy", "ophthalmoscopy",
        "fundus photo", "fundus image",
        "retinal exam", "retina",
        "red reflex"
    ],

    # Pupil assessment
    "pupils": [
        "pupil", "pupils", "rapd",  # relative afferent pupillary defect
        "marcus gunn", "afferent pupillary",
        "pupillary response", "pupil reactivity"
    ],

    # Extraocular movements
    "eom": [
        "extraocular", "eom", "eye movement",
        "diplopia", "double vision",
        "strabismus", "gaze palsy",
        "nystagmus"
    ],

    # Color vision
    "color_vision": [
        "color vision", "colour vision",
        "ishihara", "color blind",
        "dyschromatopsia"
    ]
}
```

---

## Recommended Search Strategy

### Multi-Source Hierarchical Approach

**Priority 1: Structured Observations** (Most valuable)
```sql
-- Numeric/quantitative results with units
SELECT * FROM observation
WHERE (
    -- Visual acuity
    LOWER(code_text) LIKE '%visual%acuity%'
    OR LOWER(code_text) LIKE '%snellen%'
    OR LOWER(code_text) LIKE '%logmar%'
    OR LOWER(code_text) LIKE '%etdrs%'

    -- Visual fields
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%perimetry%'

    -- OCT measurements
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%rnfl%'
    OR LOWER(code_text) LIKE '%ganglion%cell%'

    -- Optic disc findings
    OR LOWER(code_text) LIKE '%optic%disc%'
    OR LOWER(code_text) LIKE '%papilledema%'
    OR LOWER(code_text) LIKE '%optic%atrophy%'
)
AND value_quantity_value IS NOT NULL;  -- Structured data
```

**Priority 2: Procedures Performed**
```sql
-- Actual exams/tests done
SELECT * FROM procedure
WHERE (
    LOWER(code_text) LIKE '%ophthalmolog%'
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%eye%exam%'
)
AND status = 'completed';
```

**Priority 3: Service Requests (Orders)**
```sql
-- Orders for ophthalmology services
SELECT * FROM service_request
WHERE (
    LOWER(code_text) LIKE '%ophthalmolog%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optic%'
)
AND status IN ('active', 'completed');
```

**Priority 4: Diagnostic Reports**
```sql
-- Formal test reports
SELECT * FROM diagnostic_report
WHERE (
    LOWER(code_text) LIKE '%ophthalmolog%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(conclusion) LIKE '%optic%'
    OR LOWER(conclusion) LIKE '%papilledema%'
);
```

**Priority 5: Document References (Binary Files)**
```sql
-- Images and scanned reports
SELECT * FROM document_reference
WHERE (
    LOWER(description) LIKE '%oct%'
    OR LOWER(description) LIKE '%fundus%'
    OR LOWER(description) LIKE '%visual%field%'
    OR LOWER(description) LIKE '%ophthalmolog%'
);
```

---

## Specific Clinical Scenarios

### Scenario 1: Papilledema Detection (ICP Monitoring)

**Search Terms**:
```sql
WHERE (
    LOWER(code_text) LIKE '%papilledema%'
    OR LOWER(code_text) LIKE '%papilloedema%'
    OR LOWER(code_text) LIKE '%disc%edema%'
    OR LOWER(code_text) LIKE '%disc%swelling%'
    OR LOWER(value_string) LIKE '%papilledema%'
    OR LOWER(conclusion) LIKE '%papilledema%'
)
```

### Scenario 2: Optic Pathway Glioma Monitoring

**Search Terms**:
```sql
WHERE (
    -- Visual acuity decline
    LOWER(code_text) LIKE '%visual%acuity%'

    -- Optic atrophy
    OR LOWER(code_text) LIKE '%optic%atrophy%'
    OR LOWER(code_text) LIKE '%pallor%'

    -- RNFL thinning on OCT
    OR (LOWER(code_text) LIKE '%rnfl%' AND LOWER(code_text) LIKE '%thickness%')
)
```

### Scenario 3: Radiation Optic Neuropathy

**Search Terms**:
```sql
WHERE (
    LOWER(code_text) LIKE '%optic%neuropathy%'
    OR LOWER(code_text) LIKE '%radiation%optic%'
    OR LOWER(conclusion) LIKE '%radiation%neuropathy%'
)
```

---

## Proposed Athena View Structure

### v_ophthalmology_assessments

**Grain**: One row per ophthalmology test/exam/finding

**Data Sources**:
1. Observation (structured results)
2. Procedure (exams performed)
3. ServiceRequest (orders)
4. DiagnosticReport (reports)
5. DocumentReference (binary files)
6. Encounter (visits)

**Key Columns**:
- `patient_fhir_id`
- `assessment_date`
- `assessment_type` (visual_acuity, visual_field, oct, optic_disc_exam, ophthalmology_encounter)
- `source_table` (observation, procedure, service_request, etc.)
- `source_fhir_id`
- `test_name`
- `result_value` (numeric if available)
- `result_unit`
- `result_text` (free text)
- `laterality` (OD, OS, OU - right/left/both eyes)
- `binary_file_url` (if document available)
- `age_at_assessment_days`

---

## Recommended Next Steps

1. **Exploratory Analysis**: Query each FHIR table with broad ophthalmology terms to see what data exists
2. **Refine Taxonomy**: Based on actual data, refine search terms
3. **Create View**: Build multi-source ophthalmology view
4. **Validate**: Clinical review of captured vs missed assessments
5. **Iterate**: Add additional terms as needed

Would you like me to:
1. Create exploratory queries for each FHIR table?
2. Build the comprehensive `v_ophthalmology_assessments` view?
3. Both?
