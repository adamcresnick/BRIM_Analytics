# Institution/Facility Tracking for Multi-Site Care - V4 Design

**Status**: Design specification for V4.1 enhancement
**Last Updated**: 2025-11-03
**Purpose**: Track all healthcare institutions providing care across patient timeline for multi-site care coordination and data quality

---

## Executive Summary

Pediatric brain tumor patients frequently receive care at multiple institutions:
1. **Initial diagnosis** at local/regional hospital
2. **Specialty care** at tertiary center (e.g., CHOP, Penn State Hershey)
3. **Radiation therapy** at external facility
4. **Long-term follow-up** alternating between institutions
5. **Progressive disease** managed at original or new institution

**Critical Need**: Track **institution provenance** for every clinical event to:
- **EOR adjudication**: External operative notes may describe different surgery than CHOP imaging suggests
- **Date mismatch detection**: External radiation (Nov 2017 @ Penn State) vs internal placeholder (Apr 2018 @ CHOP)
- **Care coordination**: Understanding referral patterns and multi-site treatment
- **Data quality**: Flag incomplete external records requiring manual review
- **Research**: Analyze outcomes by treating institution

---

## Problem Statement

### Current Issues in V4:

1. **No institution field** in timeline events
2. **External data ambiguity**: TIFF from "Penn State Hershey" detected via date mismatch, but institution not captured
3. **EOR conflicts**: Operative note (Institution A) says "GTR" but post-op MRI (Institution B) shows residual → No way to know if imaging is from different institution
4. **Binary document metadata**: `dr_type_text = 'Outside Records'` hints at external source, but no structured institution field
5. **FHIR data model**: Organization/Location data exists but not integrated into timeline

### Real Example from Current V4 Test:

```
TIFF Document: Radiation therapy summary from Penn State Hershey
- Dates: 2017-11-02 to 2017-12-20
- Extracted via Textract: "Penn State Milton S Hershey Medical Center"
- Current V4: Creates NEW radiation event but doesn't capture institution
- Problem: Can't distinguish CHOP radiation (Apr 2018) from Penn State radiation (Nov 2017)
```

---

## Solution: Institution as FeatureObject

### Design Principle

Institution is a **FeatureObject** (like tumor_location, EOR) with multi-source support:
- **Structured source**: FHIR Organization/Location resource
- **Extracted source**: Text mention in clinical documents (e.g., "transferred from Penn State")
- **Inferred source**: Binary document metadata (`dr_type_text = 'Outside Records'`)

### Data Model (V4 Layer 2: Clinical Features)

```json
{
  "event_type": "surgery",
  "event_date": "2017-09-27",

  "clinical_features": {
    "institution": {
      "value": "Children's Hospital of Philadelphia",
      "sources": [
        {
          "source_type": "fhir_organization",
          "source_id": "Organization/chop_main",
          "extracted_value": "Children's Hospital of Philadelphia",
          "extraction_method": "structured_field",
          "confidence": "HIGH",
          "raw_text": null,
          "extracted_at": "2025-11-03T10:00:00Z"
        }
      ],
      "adjudication": null,
      "metadata": {
        "institution_type": "primary_treating",
        "npi": "1234567890",
        "external": false
      }
    }
  }
}
```

### Institution Taxonomy

#### Institution Types:
1. **primary_treating**: Primary institution (e.g., CHOP for RADIANT patients)
2. **referring**: Institution that referred patient
3. **external_specialty**: External institution providing specific service (e.g., radiation)
4. **external_diagnosis**: Institution where initial diagnosis occurred
5. **consulting**: Institution providing consultation only
6. **unknown**: Institution not specified

#### External Flag:
- `external: true` → Care provided outside primary institution
- `external: false` → Care provided at primary institution (CHOP)

---

## Data Sources for Institution

### Source 1: FHIR Structured Data (HIGH confidence)

**FHIR Resources with Institution Data**:

1. **Procedure.performer.organization** → Organization performing surgery
2. **DiagnosticReport.performer** → Organization performing imaging
3. **MedicationAdministration.performer.actor.organization** → Organization administering chemo
4. **Observation.performer** → Organization performing lab/molecular tests
5. **DocumentReference.custodian** → Organization storing external documents

**Example Query** (to be added to Phase 1):
```sql
-- Extract institution from Procedure resources
SELECT
    p.proc_id,
    p.proc_performed_date_time,
    json_extract_scalar(performer, '$.reference') as performer_org_reference,
    org.name as organization_name,
    org.identifier as organization_npi
FROM fhir_prd_db.procedure p
CROSS JOIN UNNEST(p.performer) AS t(performer)
LEFT JOIN fhir_prd_db.organization org
    ON json_extract_scalar(performer, '$.reference') = CONCAT('Organization/', org.org_id)
WHERE p.patient_fhir_id = 'Patient/{patient_id}'
```

### Source 2: Binary Document Metadata (MEDIUM confidence)

**v_binary_files fields indicating external source**:

1. **dr_type_text = 'Outside Records'** → External institution document
2. **dr_type_text = 'ONC Outside Summaries'** → External oncology summary
3. **dr_type_text = 'External Radiology and Imaging'** → External imaging
4. **document_reference_id** → Link to FHIR DocumentReference with custodian

**Example**:
```json
{
  "binary_id": "Binary/radiation_tiff_123",
  "dr_type_text": "Outside Records",
  "dr_description": "Radiation Therapy Summary",
  "institution_inferred": "external_unknown"
}
```

### Source 3: Extracted from Clinical Text (LOW-MEDIUM confidence)

**Text patterns indicating institution**:

Common institution mentions in clinical text:
- "Patient transferred from **Penn State Hershey**"
- "Outside MRI from **St. Christopher's Hospital** shows..."
- "Diagnosis established at **Alfred I. duPont Hospital**"
- "Received radiation at **University of Pennsylvania**"
- "Followed by oncology at **Nemours**"

**MedGemma Extraction Prompt** (to be added):
```
Extract the healthcare institution(s) mentioned in this document.

INSTITUTION TYPES:
- Primary treating institution (where most care occurs)
- Referring institution (where patient came from)
- External institution (providing specific services)
- Diagnostic institution (where initial diagnosis made)

Return JSON:
{
  "institutions": [
    {
      "name": "string",
      "institution_type": "primary_treating|referring|external|diagnostic",
      "context": "string (what care/service mentioned)",
      "confidence": "HIGH|MEDIUM|LOW"
    }
  ]
}
```

### Source 4: Document Text Content (LOW confidence, last resort)

**Textract/PDF extraction** may contain institution name in:
- Document headers: "Penn State Milton S Hershey Medical Center"
- Signatures: "John Smith, MD, Children's Hospital of Philadelphia"
- Addresses: "34th Street and Civic Center Boulevard, Philadelphia, PA 19104"

**Example from current V4 test**:
```
Textract extracted from TIFF:
"Penn State Milton S Hershey Medical Center
Department of Radiation Oncology
Patient: Khan, Rayan
..."
```

---

## Integration into V4 Pipeline

### Phase 1: Load Structured Institution Data (NEW)

Add institution queries to `_load_structured_data_from_athena()`:

```python
def _load_institution_data(self):
    """
    Query FHIR Organization and extract institutions mentioned across patient's care.
    Returns dict mapping event_id → institution data
    """

    # Query 1: Get institutions from Procedure.performer
    procedure_orgs_query = f"""
    SELECT
        p.proc_id,
        json_extract_scalar(performer, '$.reference') as org_reference,
        org.name as org_name,
        org.identifier as org_npi,
        org.type as org_type
    FROM fhir_prd_db.procedure p
    CROSS JOIN UNNEST(p.performer) AS t(performer)
    LEFT JOIN fhir_prd_db.organization org
        ON json_extract_scalar(performer, '$.reference') = CONCAT('Organization/', org.org_id)
    WHERE p.patient_fhir_id = '{self.athena_patient_id}'
    """

    # Query 2: Get institutions from DiagnosticReport.performer
    imaging_orgs_query = f"""
    SELECT
        dr.diagnostic_report_id,
        json_extract_scalar(performer, '$.reference') as org_reference,
        org.name as org_name
    FROM fhir_prd_db.diagnostic_report dr
    CROSS JOIN UNNEST(dr.performer) AS t(performer)
    LEFT JOIN fhir_prd_db.organization org
        ON json_extract_scalar(performer, '$.reference') = CONCAT('Organization/', org.org_id)
    WHERE dr.patient_fhir_id = '{self.athena_patient_id}'
    """

    # Query 3: Get institutions from DocumentReference.custodian (external documents)
    external_doc_orgs_query = f"""
    SELECT
        dref.document_reference_id,
        dref.custodian as org_reference,
        org.name as org_name
    FROM fhir_prd_db.document_reference dref
    LEFT JOIN fhir_prd_db.organization org
        ON dref.custodian = CONCAT('Organization/', org.org_id)
    WHERE dref.patient_fhir_id = '{self.athena_patient_id}'
        AND dref.custodian IS NOT NULL
    """

    # Execute queries and build institution index
    procedure_orgs = self._execute_athena_query(procedure_orgs_query)
    imaging_orgs = self._execute_athena_query(imaging_orgs_query)
    external_orgs = self._execute_athena_query(external_doc_orgs_query)

    # Build institution lookup: {event_id: institution_data}
    institution_index = {}

    for row in procedure_orgs:
        institution_index[row['proc_id']] = {
            'name': row['org_name'],
            'npi': row['org_npi'],
            'type': row['org_type'],
            'source': 'fhir_organization',
            'confidence': 'HIGH'
        }

    # ... similar for imaging, external docs

    return institution_index
```

### Phase 2: Merge Institution into Timeline Events

Add institution to events during timeline construction:

```python
def _construct_timeline_from_structured_data(self):
    """Construct timeline and add institution data to each event"""

    # Load institution index
    institution_index = self._load_institution_data()

    # Merge institution into events
    for event in self.timeline_events:
        event_id = event.get('procedure_id') or event.get('diagnostic_report_id')

        if event_id and event_id in institution_index:
            inst_data = institution_index[event_id]

            # Create FeatureObject for institution
            event['institution_v4'] = {
                'value': inst_data['name'],
                'sources': [
                    {
                        'source_type': 'fhir_organization',
                        'source_id': f"Organization/{inst_data.get('npi')}",
                        'extracted_value': inst_data['name'],
                        'extraction_method': 'structured_field',
                        'confidence': inst_data['confidence'],
                        'extracted_at': datetime.utcnow().isoformat() + 'Z'
                    }
                ],
                'adjudication': None,
                'metadata': {
                    'npi': inst_data.get('npi'),
                    'institution_type': self._classify_institution_type(inst_data['name']),
                    'external': self._is_external_institution(inst_data['name'])
                }
            }

            # V3 backward compatibility
            event['institution'] = inst_data['name']
```

### Phase 3: Infer Institution from Binary Document Metadata

Add institution inference for external documents:

```python
def _phase3_identify_extraction_gaps(self):
    """Identify extraction gaps and infer institution from document metadata"""

    # ... existing gap logic ...

    # For each gap, infer institution from binary metadata
    for gap in self.extraction_gaps:
        binary_id = gap.get('medgemma_target')

        if binary_id:
            # Query binary metadata
            binary_meta = self._get_binary_metadata(binary_id)
            dr_type = binary_meta.get('dr_type_text', '').lower()

            # Infer external institution
            if 'outside' in dr_type or 'external' in dr_type:
                gap['institution_inferred'] = 'external_unknown'
                gap['external_document'] = True
            else:
                gap['institution_inferred'] = 'chop'  # Primary institution
                gap['external_document'] = False
```

### Phase 4: Extract Institution from Clinical Text

Add institution extraction to MedGemma prompts:

```python
INSTITUTION_EXTRACTION_PROMPT = """
CRITICAL: Extract the healthcare institution(s) mentioned in this document.

LOOK FOR:
- Institution names (e.g., "Children's Hospital of Philadelphia", "Penn State Hershey")
- Transfer mentions (e.g., "transferred from", "referred from")
- External care mentions (e.g., "outside MRI", "radiation at")
- Document headers (institution letterhead)
- Physician affiliations (e.g., "John Smith, MD, University of Pennsylvania")

COMMON INSTITUTIONS IN PHILADELPHIA REGION:
- Children's Hospital of Philadelphia (CHOP)
- Penn State Milton S Hershey Medical Center
- Alfred I. duPont Hospital for Children
- St. Christopher's Hospital for Children
- Nemours Children's Hospital
- Hospital of the University of Pennsylvania (HUP)
- Thomas Jefferson University Hospital

Return JSON:
{
  "institutions": [
    {
      "name": "full institution name",
      "institution_type": "primary_treating|referring|external_specialty|diagnostic|consulting",
      "context": "what service/care was provided here",
      "confidence": "HIGH|MEDIUM|LOW",
      "text_snippet": "exact text mentioning institution"
    }
  ],
  "primary_institution": "name of primary treating institution (if clear)"
}

DOCUMENT:
{document_text}
"""

# Use in MedGemma extraction
result = self.medgemma_agent.extract(
    prompt=INSTITUTION_EXTRACTION_PROMPT.format(document_text=document_text)
)

institutions = result.extracted_data.get('institutions', [])
```

### Phase 4: Integrate Institution into FeatureObject

Merge extracted institution data into timeline events:

```python
elif gap_type == 'missing_institution':
    from lib.feature_object import FeatureObject

    extracted_institutions = extraction_data.get('institutions', [])

    if not extracted_institutions:
        continue

    # Get primary institution or first mentioned
    primary_inst = extraction_data.get('primary_institution')
    if not primary_inst and extracted_institutions:
        primary_inst = extracted_institutions[0]['name']

    # Check if event already has institution (from structured data)
    existing_inst = event.get('institution_v4')

    if existing_inst and isinstance(existing_inst, dict):
        # MULTI-SOURCE: We have institution from FHIR + extracted text
        feature = FeatureObject(
            value=existing_inst['value'],
            sources=existing_inst.get('sources', [])
        )

        # Add extracted institution as additional source
        feature.add_source(
            source_type='clinical_text',
            extracted_value=primary_inst,
            extraction_method='medgemma_llm',
            confidence=extracted_institutions[0]['confidence'],
            source_id=gap.get('medgemma_target'),
            raw_text=extracted_institutions[0].get('text_snippet', '')[:200]
        )

        # Check for conflict
        if feature.has_conflict():
            # Structured FHIR data takes precedence over extracted text
            feature.adjudicate(
                final_value=existing_inst['value'],
                method='structured_data_priority',
                rationale='FHIR Organization resource more reliable than text extraction',
                adjudicated_by='institution_adjudicator_v1',
                requires_manual_review=False
            )

        event['institution_v4'] = feature.to_dict()
    else:
        # SINGLE-SOURCE: First institution mention for this event
        feature = FeatureObject.from_single_source(
            value=primary_inst,
            source_type='clinical_text',
            extracted_value=primary_inst,
            extraction_method='medgemma_llm',
            confidence=extracted_institutions[0]['confidence'],
            source_id=gap.get('medgemma_target'),
            raw_text=extracted_institutions[0].get('text_snippet', '')[:200]
        )

        event['institution_v4'] = feature.to_dict()
        event['institution_v4']['metadata'] = {
            'institution_type': extracted_institutions[0]['institution_type'],
            'external': self._is_external_institution(primary_inst),
            'all_mentioned': [inst['name'] for inst in extracted_institutions]
        }

    event['institution'] = primary_inst  # V3 backward compatibility
    logger.info(f"Merged institution for {event_date}: {primary_inst}")
```

---

## Use Cases

### Use Case 1: EOR Adjudication with Institution Context

**Scenario**: Operative note (Penn State Hershey) says "GTR", but post-op MRI (CHOP) shows residual tumor.

**Current V4**: Adjudicates based on source type (imaging > operative note) without knowing institutions differ.

**With Institution Tracking**:
```python
# EOR Orchestrator enhanced with institution awareness
def adjudicate_eor_with_institution(operative_eor, operative_inst,
                                     imaging_eor, imaging_inst):
    if operative_inst != imaging_inst:
        # Different institutions - may be imaging different surgeries!
        if imaging_inst == 'chop':  # Primary institution
            # CHOP imaging likely refers to surgery at CHOP, not Penn State
            return {
                'final_eor': imaging_eor,
                'method': 'favor_primary_institution_imaging',
                'rationale': f'Imaging at primary institution ({imaging_inst}) likely assessing local surgery, not external surgery at {operative_inst}',
                'requires_manual_review': True
            }
```

### Use Case 2: Date Mismatch with Institution

**Current V4**: TIFF with Nov 2017 dates creates NEW event but institution not captured.

**With Institution Tracking**:
```json
{
  "event_type": "radiation_start",
  "event_date": "2017-11-02",
  "source": "medgemma_extracted_from_binary",
  "description": "Radiation started (external institution)",

  "institution_v4": {
    "value": "Penn State Milton S Hershey Medical Center",
    "sources": [
      {
        "source_type": "document_header",
        "extracted_value": "Penn State Milton S Hershey Medical Center",
        "extraction_method": "textract_ocr",
        "confidence": "HIGH",
        "source_id": "Binary/radiation_tiff_123"
      }
    ],
    "metadata": {
      "institution_type": "external_specialty",
      "external": true,
      "service": "radiation_therapy"
    }
  }
}
```

### Use Case 3: Care Continuity Visualization

**Timeline with Institution**:
```
2017-09-27: Diagnosis @ Children's Hospital of Philadelphia
2017-11-02: Radiation Start @ Penn State Hershey Medical Center (EXTERNAL)
2017-12-20: Radiation End @ Penn State Hershey Medical Center (EXTERNAL)
2018-04-25: Follow-up MRI @ Children's Hospital of Philadelphia
2018-08-09: Re-irradiation @ Children's Hospital of Philadelphia
```

**Research Questions Enabled**:
- What % of patients receive radiation at external facilities?
- How does EOR differ between CHOP surgeries vs external surgeries?
- What is median time to return to primary institution after external treatment?

---

## Patient-Level Institution Summary

### New Timeline Root-Level Field: `institutions_involved`

Track all institutions mentioned across patient timeline:

```json
{
  "patient_id": "eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83",

  "institutions_involved": {
    "primary_institution": {
      "name": "Children's Hospital of Philadelphia",
      "npi": "1234567890",
      "first_event_date": "2017-09-27",
      "last_event_date": "2018-08-24",
      "event_count": 42,
      "services": ["diagnosis", "surgery", "chemotherapy", "imaging", "radiation"]
    },

    "external_institutions": [
      {
        "name": "Penn State Milton S Hershey Medical Center",
        "npi": "9876543210",
        "first_event_date": "2017-11-02",
        "last_event_date": "2017-12-20",
        "event_count": 2,
        "services": ["radiation"],
        "institution_type": "external_specialty"
      }
    ],

    "total_institutions": 2,
    "multi_site_care": true
  }
}
```

---

## Institution Normalization

### Institution Name Standardization

Create institution normalizer (similar to brain_location_normalizer):

```python
class InstitutionNormalizer:
    """Normalize institution names to canonical forms"""

    INSTITUTION_SYNONYMS = {
        "Children's Hospital of Philadelphia": [
            "CHOP",
            "Children's Hospital Philadelphia",
            "Childrens Hospital of Philadelphia",
            "The Children's Hospital of Philadelphia"
        ],
        "Penn State Milton S Hershey Medical Center": [
            "Penn State Hershey",
            "Hershey Medical Center",
            "Penn State Hershey Medical Center",
            "Milton S Hershey Medical Center"
        ],
        "Alfred I. duPont Hospital for Children": [
            "duPont Hospital",
            "AI duPont",
            "Nemours duPont"
        ],
        # ... add more institutions
    }

    def normalize(self, institution_name: str) -> str:
        """Normalize institution name to canonical form"""
        name_lower = institution_name.lower().strip()

        for canonical, synonyms in self.INSTITUTION_SYNONYMS.items():
            if name_lower == canonical.lower():
                return canonical
            for synonym in synonyms:
                if name_lower == synonym.lower():
                    return canonical

        return institution_name  # Return original if no match
```

---

## Implementation Plan

### Phase 1: Data Source Investigation (2-3 hours)
1. Query FHIR Organization/Location resources
2. Identify which events have performer/custodian data
3. Analyze binary metadata (dr_type_text patterns)
4. Sample text extraction for institution mentions

### Phase 2: Institution Normalizer (2-3 hours)
1. Create `lib/institution_normalizer.py`
2. Build synonym dictionary (CHOP, Penn State, etc.)
3. Add NPI lookup support
4. Test with sample institution names

### Phase 3: V4 Integration (6-8 hours)
1. Add institution queries to Phase 1 (structured data)
2. Create institution inference from binary metadata (Phase 3)
3. Add institution extraction prompts (Phase 4)
4. Implement FeatureObject integration (Phase 4)
5. Add institution adjudication logic

### Phase 4: Testing & Validation (3-4 hours)
1. Test with patient eQSB0y3q (Penn State Hershey TIFF)
2. Verify institution extracted from Textract
3. Test multi-site care scenarios
4. Validate external flag accuracy

### Phase 5: Patient-Level Summary (2-3 hours)
1. Generate `institutions_involved` summary
2. Count events per institution
3. Identify primary vs external institutions
4. Add to Phase 6 artifact generation

---

## Example Output Artifacts

### Surgery Event with Institution
```json
{
  "event_id": "evt_20170927_surgery_001",
  "event_type": "surgery",
  "event_date": "2017-09-27",

  "clinical_features": {
    "institution": {
      "value": "Children's Hospital of Philadelphia",
      "sources": [
        {
          "source_type": "fhir_organization",
          "source_id": "Organization/chop_main",
          "extracted_value": "Children's Hospital of Philadelphia",
          "extraction_method": "structured_field",
          "confidence": "HIGH",
          "extracted_at": "2025-11-03T10:00:00Z"
        }
      ],
      "adjudication": null,
      "metadata": {
        "npi": "1234567890",
        "institution_type": "primary_treating",
        "external": false
      }
    },

    "extent_of_resection": {
      "value": "STR",
      "sources": [ /* ... */ ]
    }
  }
}
```

### External Radiation Event
```json
{
  "event_id": "evt_20171102_radiation_001",
  "event_type": "radiation_start",
  "event_date": "2017-11-02",
  "source": "medgemma_extracted_from_binary",

  "clinical_features": {
    "institution": {
      "value": "Penn State Milton S Hershey Medical Center",
      "sources": [
        {
          "source_type": "document_header",
          "source_id": "Binary/radiation_tiff_123",
          "extracted_value": "Penn State Milton S Hershey Medical Center",
          "extraction_method": "textract_ocr",
          "confidence": "HIGH",
          "raw_text": "Penn State Milton S Hershey Medical Center\nDepartment of Radiation Oncology",
          "extracted_at": "2025-11-03T14:40:23Z"
        }
      ],
      "adjudication": null,
      "metadata": {
        "institution_type": "external_specialty",
        "external": true,
        "service": "radiation_therapy"
      }
    },

    "total_dose_cgy": {
      "value": 5400,
      "sources": [ /* ... */ ]
    }
  },

  "description": "Radiation started at Penn State Hershey (external institution)"
}
```

---

## Benefits

1. **EOR Adjudication Quality**: Avoid comparing surgeries at different institutions
2. **Date Mismatch Context**: Know which institution provided external care
3. **Care Continuity**: Visualize patient journey across institutions
4. **Data Quality**: Flag external records needing manual review
5. **Research**: Analyze outcomes by treating institution
6. **Referral Patterns**: Understand which institutions refer to CHOP
7. **Multi-Site Coordination**: Identify patients receiving care elsewhere

---

## Next Steps

1. Investigate FHIR Organization data availability in current dataset
2. Analyze binary metadata patterns (dr_type_text = 'Outside Records')
3. Build institution normalizer with Philadelphia-area hospitals
4. Integrate into V4 pipeline (Phase 1, 3, 4)
5. Test with patient eQSB0y3q (Penn State Hershey radiation)
6. Document institution-aware EOR adjudication rules

---

**Status**: Design specification ready for implementation
**Estimated Implementation Time**: 15-20 hours
**Dependencies**: V4 FeatureObject pattern (already implemented)
**Priority**: HIGH (critical for EOR adjudication and multi-site care tracking)
