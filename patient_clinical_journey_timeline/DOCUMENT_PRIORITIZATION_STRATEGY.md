# Document Prioritization Strategy for MedGemma Extraction

**Purpose**: Define prioritized document search strategy for extracting clinical variables when not found in primary documents
**Key Principle**: **Patient-specific temporal proximity** - prioritize documents closest to the treatment timepoint with patient-specific availability

---

## Core Strategy: Adaptive Patient-Specific Prioritization

**The agent should:**
1. **Query available documents** for this specific patient around the timepoint
2. **Rank by temporal proximity** and document type relevance
3. **Try highest-ranked documents** first
4. **Escalate through alternatives** until variables found or exhausted

---

## 1. SURGERY - Extent of Resection (EOR)

### Primary Source
```sql
dr_type_text IN ('Operative Record', 'External Operative Note', 'OP Note')
temporal_window: surgery_date ±7 days
```

### Alternative Document Search Priority

**Tier 1: Surgical Documentation (±14 days)**
1. **Discharge Summary**
   - `dr_type_text = 'Discharge Summary'`
   - Keywords: resection, craniotomy, surgery, EOR, gross total, subtotal
   - Rationale: Often contains operative summary and post-op assessment

2. **Post-operative Progress Notes**
   - `dr_type_text = 'Progress Notes'`
   - Keywords: post-op, surgery, resection, residual
   - Temporal: surgery_date to surgery_date + 14 days

**Tier 2: Diagnostic Documents (±30 days)**
3. **Post-operative MRI Report**
   - `dr_type_text = 'Diagnostic imaging study'`
   - Imaging modality: MRI
   - Keywords: post-operative, resection cavity, residual tumor
   - Temporal: surgery_date to surgery_date + 72 hours (typical post-op MRI window)
   - Rationale: Radiologist assessment of resection completeness

4. **Pathology Report**
   - `dr_type_text = 'Pathology report'`
   - Keywords: specimen, resection, tissue
   - Rationale: May note "extensive tissue" (STR) vs "limited biopsy tissue" (BIOPSY)

**Tier 3: Clinical Notes (±30 days)**
5. **Neurosurgery Clinic Notes**
   - `dr_type_text = 'Outpatient Note' OR 'Consultation Note'`
   - Keywords: neurosurgery, post-op visit, resection
   - Temporal: surgery_date to surgery_date + 30 days

6. **Oncology Consultation Notes**
   - `dr_type_text = 'Consultation Note'`
   - Keywords: oncology, treatment planning, resection status
   - Rationale: Discusses EOR when planning adjuvant therapy

**Tier 4: Structured Data Inference**
7. **Infer from imaging timeline**
   - If post-op MRI shows "no residual" → likely GTR
   - If post-op MRI shows "residual enhancing tumor" → likely STR
   - Mark as INFERRED, confidence: LOW

### Query Template
```python
def _find_alternative_operative_documents(self, surgery_date: str, patient_id: str) -> List[Dict]:
    """
    Search for alternative documents containing EOR information
    Returns list ordered by priority
    """
    alternatives = []

    # Tier 1: Discharge summaries
    query = f"""
    SELECT
        binary_id,
        dr_type_text,
        dr_date,
        dr_description,
        ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE))) as days_from_surgery
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
      AND dr_type_text = 'Discharge Summary'
      AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE))) <= 14
      AND (
          LOWER(dr_description) LIKE '%resection%'
          OR LOWER(dr_description) LIKE '%surgery%'
          OR LOWER(dr_description) LIKE '%craniotomy%'
          OR LOWER(dr_description) LIKE '%biopsy%'
      )
    ORDER BY days_from_surgery ASC
    LIMIT 3
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 1,
            'type': 'discharge_summary',
            'binary_id': r['binary_id'],
            'date': r['dr_date'],
            'days_from_surgery': r['days_from_surgery']
        })

    # Tier 2: Post-op MRI
    query = f"""
    SELECT
        diagnostic_report_id as binary_id,
        'Diagnostic imaging study' as dr_type_text,
        imaging_date as dr_date,
        report_conclusion as dr_description,
        DATE_DIFF('day', CAST(imaging_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE)) as days_from_surgery
    FROM fhir_prd_db.v_imaging
    WHERE patient_fhir_id = '{patient_id}'
      AND imaging_modality = 'MR'
      AND imaging_date >= CAST(TIMESTAMP '{surgery_date}' AS DATE)
      AND imaging_date <= CAST(TIMESTAMP '{surgery_date}' AS DATE) + INTERVAL '7' DAY
      AND (
          LOWER(report_conclusion) LIKE '%post%op%'
          OR LOWER(report_conclusion) LIKE '%resection%'
          OR LOWER(report_conclusion) LIKE '%residual%'
      )
    ORDER BY imaging_date ASC
    LIMIT 2
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 2,
            'type': 'postop_imaging',
            'binary_id': r['binary_id'],
            'date': r['dr_date'],
            'days_from_surgery': r['days_from_surgery']
        })

    # Sort by priority, then by temporal proximity
    alternatives.sort(key=lambda x: (x['priority'], abs(x['days_from_surgery'])))

    return alternatives
```

---

## 2. RADIATION - Comprehensive Dose Details

### Primary Sources

**Option A: v_radiation_documents (PREFERRED)**
```sql
FROM fhir_prd_db.v_radiation_documents
WHERE patient_fhir_id = '{patient_id}'
  AND radiation_episode_start_date ± 30 days
```

**Option B: v_binary_files**
```sql
dr_type_text IN ('Radiation Therapy Treatment Summary', 'Radiation Oncology Note')
temporal_window: radiation_start_date ±30 days
```

### Alternative Document Search Priority

**Tier 1: Radiation-Specific Documents (±60 days)**
1. **Radiation Treatment Planning Documents**
   - `dr_type_text = 'Radiation Treatment Plan'`
   - Keywords: treatment plan, dose, fractions, target volumes
   - Rationale: Prospective plan may differ from actual, but contains intended doses

2. **Radiation Oncology Progress Notes**
   - `dr_type_text = 'Progress Notes'`
   - Author/specialty: Radiation Oncology
   - Keywords: radiation, dose, treatment, completion
   - Temporal: radiation_start_date to radiation_stop_date + 30 days

3. **Radiation Completion Summary**
   - `dr_type_text = 'Discharge Summary' OR 'Summary Note'`
   - Keywords: radiation, completed, total dose, fractions
   - Temporal: radiation_stop_date ±14 days

**Tier 2: Multi-Disciplinary Notes (±60 days)**
4. **Neuro-Oncology Clinic Notes**
   - `dr_type_text = 'Outpatient Note' OR 'Consultation Note'`
   - Keywords: radiation, dose, treatment completed
   - Temporal: radiation_stop_date to radiation_stop_date + 60 days
   - Rationale: Often summarizes completed treatment

5. **Discharge Summary (if inpatient radiation)**
   - `dr_type_text = 'Discharge Summary'`
   - Keywords: radiation, proton, photon, dose
   - Temporal: radiation_stop_date ±30 days

**Tier 3: Billing/Administrative Documents (±90 days)**
6. **Charge/Billing Documents with CPT codes**
   - CPT codes: 77385-77386 (IMRT), 77261-77263 (treatment planning), 77520-77525 (proton)
   - Rationale: Billing codes may indicate craniospinal vs focal, proton vs photon
   - NOTE: Unlikely to have dose details, but confirms treatment occurred

**Tier 4: Structured Data from v_radiation_episode_enrichment**
7. **Fallback to structured view**
   ```sql
   SELECT total_dose_cgy, radiation_fields
   FROM fhir_prd_db.v_radiation_episode_enrichment
   WHERE patient_fhir_id = '{patient_id}'
     AND episode_start_date = '{radiation_start_date}'
   ```
   - Mark as INFERRED if only total_dose_cgy available
   - Missing: fractions, dose per fraction, craniospinal vs focal breakdown

### Query Template with v_radiation_documents Integration
```python
def _find_alternative_radiation_documents(self, radiation_date: str, patient_id: str) -> List[Dict]:
    """
    Search for alternative radiation documents
    **START WITH v_radiation_documents before v_binary_files**
    """
    alternatives = []

    # TIER 0: v_radiation_documents (specialized view)
    query = f"""
    SELECT
        document_reference_id,
        'Radiation Treatment Document' as dr_type_text,
        radiation_episode_start_date,
        radiation_episode_end_date,
        ABS(DATE_DIFF('day', radiation_episode_start_date, CAST(TIMESTAMP '{radiation_date}' AS DATE))) as days_from_radiation
    FROM fhir_prd_db.v_radiation_documents
    WHERE patient_fhir_id = '{patient_id}'
      AND ABS(DATE_DIFF('day', radiation_episode_start_date, CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 30
    ORDER BY days_from_radiation ASC
    LIMIT 5
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 0,  # HIGHEST
            'type': 'radiation_document',
            'document_reference_id': r['document_reference_id'],
            'date': r['radiation_episode_start_date'],
            'days_from_radiation': r['days_from_radiation']
        })

    # TIER 1: Progress notes from radiation oncology
    query = f"""
    SELECT
        binary_id,
        dr_type_text,
        dr_date,
        dr_description,
        ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) as days_from_radiation
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
      AND dr_type_text = 'Progress Notes'
      AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 60
      AND (
          LOWER(dr_description) LIKE '%radiation%'
          OR LOWER(dr_description) LIKE '%proton%'
          OR LOWER(dr_description) LIKE '%dose%'
          OR LOWER(dr_description) LIKE '%treatment%'
      )
    ORDER BY days_from_radiation ASC
    LIMIT 5
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 1,
            'type': 'radiation_progress_note',
            'binary_id': r['binary_id'],
            'date': r['dr_date'],
            'days_from_radiation': r['days_from_radiation']
        })

    # Sort by priority, then temporal proximity
    alternatives.sort(key=lambda x: (x['priority'], x['days_from_radiation']))

    return alternatives
```

---

## 3. CHEMOTHERAPY - Agent Names, Dates, Protocols

### Primary Source
```sql
FROM fhir_prd_db.v_chemo_treatment_episodes
-- Already structured, but may be incomplete
```

### Alternative Document Search Priority

**Tier 1: Oncology Treatment Notes (±30 days)**
1. **Oncology Progress Notes**
   - `dr_type_text = 'Progress Notes'`
   - Author/specialty: Medical Oncology, Neuro-Oncology
   - Keywords: chemotherapy, temozolomide, protocol, cycle, treatment
   - Temporal: episode_start_date to episode_end_date

2. **Chemotherapy Treatment Plans**
   - `dr_type_text = 'Treatment Plan' OR 'Chemotherapy Order'`
   - Keywords: protocol, regimen, agents, dosing
   - Temporal: episode_start_date ±7 days

3. **Infusion Records**
   - `dr_type_text = 'Infusion Record' OR 'Medication Administration Record'`
   - Keywords: chemotherapy, infusion, administered
   - Temporal: episode_start_date to episode_end_date
   - Rationale: Documents what was actually given (vs ordered)

**Tier 2: Multi-Disciplinary Notes (±60 days)**
4. **Neuro-Oncology Clinic Notes**
   - `dr_type_text = 'Outpatient Note' OR 'Consultation Note'`
   - Keywords: chemotherapy, protocol, cycle, treatment regimen
   - Temporal: episode_start_date ±60 days

5. **Discharge Summary (if admitted during chemo)**
   - `dr_type_text = 'Discharge Summary'`
   - Keywords: chemotherapy, protocol, agents
   - Temporal: episode_start_date to episode_end_date

**Tier 3: Protocol Documentation**
6. **Protocol Enrollment Documents**
   - `dr_type_text = 'Consent Form' OR 'Protocol Document'`
   - Keywords: protocol name (ACNS0423, ACNS0126, etc.), enrollment
   - Rationale: Identifies formal protocol, may list planned agents

7. **Clinical Trial Documents**
   - `dr_type_text = 'Clinical Trial Document'`
   - Keywords: protocol, randomization, treatment arm

**Tier 4: Pharmacy Records (if available)**
8. **Pharmacy Dispensing Records**
   - May not be in v_binary_files, but check MedicationRequest/MedicationAdministration resources
   - Rationale: Ground truth of what was actually dispensed

### Query Template
```python
def _find_alternative_chemotherapy_documents(self, chemo_start_date: str, chemo_end_date: str, patient_id: str) -> List[Dict]:
    """
    Search for chemotherapy agent details in alternative documents
    """
    alternatives = []

    # Tier 1: Oncology progress notes
    query = f"""
    SELECT
        binary_id,
        dr_type_text,
        dr_date,
        dr_description,
        ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{chemo_start_date}' AS DATE))) as days_from_chemo_start
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
      AND dr_type_text IN ('Progress Notes', 'Outpatient Note', 'Consultation Note')
      AND dr_date >= CAST(TIMESTAMP '{chemo_start_date}' AS DATE) - INTERVAL '7' DAY
      AND dr_date <= CAST(TIMESTAMP '{chemo_end_date}' AS DATE) + INTERVAL '30' DAY
      AND (
          LOWER(dr_description) LIKE '%chemotherapy%'
          OR LOWER(dr_description) LIKE '%temozolomide%'
          OR LOWER(dr_description) LIKE '%protocol%'
          OR LOWER(dr_description) LIKE '%cycle%'
          OR LOWER(dr_description) LIKE '%treatment%'
      )
    ORDER BY dr_date ASC
    LIMIT 10
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 1,
            'type': 'oncology_progress_note',
            'binary_id': r['binary_id'],
            'date': r['dr_date'],
            'days_from_chemo_start': r['days_from_chemo_start']
        })

    # Tier 2: Treatment plans
    query = f"""
    SELECT
        binary_id,
        dr_type_text,
        dr_date,
        ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{chemo_start_date}' AS DATE))) as days_from_chemo_start
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
      AND dr_type_text LIKE '%Treatment Plan%'
      AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{chemo_start_date}' AS DATE))) <= 30
    ORDER BY days_from_chemo_start ASC
    LIMIT 3
    """
    results = query_athena(query, suppress_output=True)
    for r in results:
        alternatives.append({
            'priority': 2,
            'type': 'treatment_plan',
            'binary_id': r['binary_id'],
            'date': r['dr_date'],
            'days_from_chemo_start': r['days_from_chemo_start']
        })

    alternatives.sort(key=lambda x: (x['priority'], x['days_from_chemo_start']))

    return alternatives
```

---

## 4. IMAGING - Tumor Measurements and RANO Assessment

### Primary Source
```sql
FROM fhir_prd_db.v_imaging
WHERE imaging_modality = 'MR' AND report_conclusion IS NOT NULL
-- BUT report_conclusion often vague, needs binary extraction
```

### Alternative Document Search Priority

**Tier 1: Prior Imaging for Comparison (if missing prior measurements)**
1. **Most recent prior MRI**
   - Same imaging modality
   - Temporal: Any scan before current_imaging_date
   - Order by: Most recent first
   - Rationale: Need prior measurements to calculate percent change

2. **Baseline imaging (first scan after diagnosis)**
   - Temporal: Closest to diagnosis date
   - Rationale: Reference for overall response assessment

**Tier 2: Clinical Notes Referencing Imaging (±30 days)**
3. **Neuro-Oncology Clinic Notes**
   - `dr_type_text = 'Outpatient Note' OR 'Progress Notes'`
   - Keywords: MRI, imaging, response, progression, stable
   - Temporal: imaging_date ±30 days
   - Rationale: Clinician interpretation of imaging

4. **Tumor Board Notes**
   - `dr_type_text = 'Tumor Board Note' OR 'Multidisciplinary Conference'`
   - Keywords: imaging review, response assessment
   - Temporal: imaging_date ±30 days
   - Rationale: Multi-disciplinary interpretation

**Tier 3: Structured Imaging Data**
5. **Fallback to v_imaging.report_conclusion**
   - Use qualitative descriptors if measurements unavailable
   - "Stable" → SD, "Decreased" → PR (if ≥50%), "Increased" → PD (if ≥25%)
   - Mark as INFERRED, confidence: MEDIUM

---

## Implementation Strategy

### 1. Patient-Specific Document Inventory
```python
def _build_patient_document_inventory(self, patient_id: str) -> Dict:
    """
    Build inventory of ALL available documents for this patient
    Allows agent to make informed prioritization decisions
    """
    query = f"""
    SELECT
        binary_id,
        dr_type_text,
        dr_date,
        dr_description,
        content_type
    FROM fhir_prd_db.v_binary_files
    WHERE patient_fhir_id = '{patient_id}'
    ORDER BY dr_date DESC
    """
    results = query_athena(query, suppress_output=True)

    inventory = {
        'operative_records': [],
        'discharge_summaries': [],
        'progress_notes': [],
        'imaging_reports': [],
        'pathology_reports': [],
        'consultation_notes': [],
        'treatment_plans': [],
        'other': []
    }

    for doc in results:
        doc_type = doc['dr_type_text'].lower()
        if 'operative' in doc_type or 'op note' in doc_type:
            inventory['operative_records'].append(doc)
        elif 'discharge' in doc_type:
            inventory['discharge_summaries'].append(doc)
        elif 'progress' in doc_type:
            inventory['progress_notes'].append(doc)
        elif 'imaging' in doc_type or 'radiology' in doc_type:
            inventory['imaging_reports'].append(doc)
        elif 'pathology' in doc_type:
            inventory['pathology_reports'].append(doc)
        elif 'consultation' in doc_type:
            inventory['consultation_notes'].append(doc)
        elif 'treatment plan' in doc_type:
            inventory['treatment_plans'].append(doc)
        else:
            inventory['other'].append(doc)

    return inventory
```

### 2. Adaptive Prioritization Based on Availability
```python
def _prioritize_documents_for_gap(self, gap: Dict, inventory: Dict) -> List[Dict]:
    """
    Prioritize documents based on:
    1. Gap type
    2. Temporal proximity to event
    3. Patient-specific document availability
    """
    gap_type = gap['gap_type']
    event_date = gap['event_date']

    if gap_type == 'missing_eor':
        # Check if operative records exist
        if inventory['operative_records']:
            candidates = inventory['operative_records']
        else:
            # Escalate to discharge summaries
            candidates = inventory['discharge_summaries']

    elif gap_type == 'missing_radiation_details':
        # Check v_radiation_documents first (not in inventory, special query)
        radiation_docs = self._query_radiation_documents(event_date)
        if radiation_docs:
            return radiation_docs

        # Fallback to progress notes
        candidates = inventory['progress_notes']

    # Filter by temporal proximity
    candidates_with_distance = []
    for doc in candidates:
        days_diff = abs((parse(doc['dr_date']) - parse(event_date)).days)
        candidates_with_distance.append({
            **doc,
            'days_from_event': days_diff
        })

    # Sort by temporal proximity
    candidates_with_distance.sort(key=lambda x: x['days_from_event'])

    return candidates_with_distance[:5]  # Top 5 candidates
```

### 3. Escalating Search Loop
```python
def _extract_with_escalation(self, gap: Dict) -> bool:
    """
    Escalate through alternative documents until variables found
    Returns True if extraction successful, False otherwise
    """
    # Build patient document inventory
    inventory = self._build_patient_document_inventory(self.athena_patient_id)

    # Get prioritized candidates
    candidates = self._prioritize_documents_for_gap(gap, inventory)

    for i, candidate in enumerate(candidates):
        print(f"    📄 Attempt {i+1}/{len(candidates)}: {candidate['dr_type_text']} from {candidate['dr_date']} ({candidate['days_from_event']} days from event)")

        # Fetch document
        doc_text = self._fetch_binary_document(f"Binary/{candidate['binary_id']}")
        if not doc_text:
            continue

        # Validate content
        is_valid, reason = self._validate_document_content(doc_text, gap['gap_type'])
        if not is_valid:
            print(f"       ⚠️  Invalid: {reason}")
            continue

        # Extract
        prompt = self._generate_medgemma_prompt(gap)
        full_prompt = f"{prompt}\n\nDOCUMENT TEXT:\n{doc_text}"
        result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

        if result.success:
            is_complete, missing = self._validate_extraction_result(result.extracted_data, gap['gap_type'])
            if is_complete:
                print(f"       ✅ Extraction successful from alternative document!")
                gap['status'] = 'RESOLVED'
                gap['extraction_source'] = candidate['dr_type_text']
                gap['extraction_document_date'] = candidate['dr_date']
                self._integrate_extraction_into_timeline(gap, result.extracted_data)
                return True
            else:
                print(f"       ⚠️  Incomplete: missing {missing}")

    # All alternatives exhausted
    print(f"    ❌ Exhausted {len(candidates)} alternative documents")
    gap['status'] = 'UNAVAILABLE_IN_RECORDS'
    return False
```

---

## Summary: Key Principles

1. **Patient-Specific**: Query actual available documents for THIS patient
2. **Temporal Proximity**: Prioritize documents closest to the treatment timepoint
3. **Escalating Search**: Try alternatives in priority order until found
4. **Adaptive**: If primary doc type unavailable, skip to next tier
5. **Transparent**: Log which document type ultimately yielded the data
6. **Graceful Degradation**: Accept UNAVAILABLE_IN_RECORDS only after exhaustive search

---

**Next Steps for Implementation:**
1. Implement `_build_patient_document_inventory()` to assess availability
2. Implement `_prioritize_documents_for_gap()` with temporal ranking
3. Integrate escalating search into Phase 4 extraction loop
4. Add metadata tracking: which doc type/date yielded successful extraction
