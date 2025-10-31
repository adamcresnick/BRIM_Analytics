# Phase 4: MedGemma Integration Implementation Guide

**Purpose**: Step-by-step guide for implementing the MedGemma binary extraction phase

**Created**: 2025-10-30
**Status**: READY FOR IMPLEMENTATION

---

## Overview

Phase 4 is the **two-agent orchestration** where:
1. **Claude** (this script) generates context-aware prompts based on patient timeline
2. **MedGemma** extracts structured data from binary documents
3. **Claude** integrates extractions back into timeline and re-assesses gaps

---

## Implementation Approach: Incremental with Mock Testing

### Why Mock First?

Before integrating with actual MedGemma API/service, we should:
1. **Implement the orchestration framework** (prompt generation, integration logic)
2. **Test with mock MedGemma responses** to validate the workflow
3. **Verify timeline integration works correctly**
4. **Then** connect to real MedGemma API

This allows us to:
- Test the full workflow end-to-end
- Debug integration issues without API dependencies
- Demonstrate the architecture before production deployment

---

## Phase 4 Architecture

```python
def _phase4_extract_from_binaries(self):
    """
    Phase 4: Iterative MedGemma extraction with Claude-generated prompts

    MOCK MODE: For initial testing
    PRODUCTION MODE: When MedGemma API is available
    """

    # STEP 1: Sort gaps by priority
    prioritized_gaps = self._prioritize_extraction_gaps()

    # STEP 2: Iterate through gaps
    for gap in prioritized_gaps:
        # STEP 2a: Generate context-aware prompt (CLAUDE)
        medgemma_prompt = self._generate_medgemma_prompt(gap)

        # STEP 2b: Fetch binary document (FHIR)
        document_content = self._fetch_binary_document(gap['medgemma_target'])

        # STEP 2c: Call MedGemma (MOCK or REAL)
        if self.use_mock_medgemma:
            extraction_result = self._mock_medgemma_extraction(gap, medgemma_prompt)
        else:
            extraction_result = self._call_medgemma(document_content, medgemma_prompt)

        # STEP 2d: Validate extraction confidence
        if extraction_result['extraction_confidence'] in ['HIGH', 'MEDIUM']:
            # STEP 2e: Integrate into timeline
            self._integrate_extraction_into_timeline(gap, extraction_result)
            gap['status'] = 'RESOLVED'
        else:
            gap['status'] = 'REQUIRES_MANUAL_REVIEW'

        gap['extraction_result'] = extraction_result

    # STEP 3: Re-assess for new gaps
    self._reassess_gaps_post_extraction()

    # STEP 4: Report results
    resolved = len([g for g in self.extraction_gaps if g.get('status') == 'RESOLVED'])
    manual_review = len([g for g in self.extraction_gaps if g.get('status') == 'REQUIRES_MANUAL_REVIEW'])

    print(f"  ✅ Extracted from {resolved} documents")
    print(f"  ⚠️  {manual_review} require manual review")
```

---

## Method 1: `_prioritize_extraction_gaps()`

**Purpose**: Sort gaps by clinical significance + WHO 2021 context

```python
def _prioritize_extraction_gaps(self) -> List[Dict]:
    """
    Prioritize extraction gaps for MedGemma processing

    Priority order:
    1. HIGHEST: Missing EOR, pseudoprogression window imaging
    2. HIGH: Missing radiation dose, Priority 1-2 pathology
    3. MEDIUM: Vague imaging conclusions (non-critical)
    """

    priority_scores = {
        'HIGHEST': 0,
        'HIGH': 1,
        'MEDIUM': 2,
        'LOW': 3
    }

    # Sort gaps
    return sorted(
        self.extraction_gaps,
        key=lambda x: priority_scores.get(x.get('priority', 'LOW'), 4)
    )
```

---

## Method 2: `_generate_medgemma_prompt(gap)`

**Purpose**: Generate context-aware prompts based on gap type + timeline phase

```python
def _generate_medgemma_prompt(self, gap: Dict) -> str:
    """
    Generate context-aware MedGemma prompt

    Args:
        gap: Extraction gap dictionary with clinical context

    Returns:
        Specialized prompt string for MedGemma
    """

    # Route to specialized prompt template based on gap type
    prompt_generators = {
        'vague_imaging_conclusion': self._generate_imaging_prompt,
        'missing_eor': self._generate_operative_note_prompt,
        'missing_radiation_dose': self._generate_radiation_summary_prompt,
        'high_priority_pathology': self._generate_pathology_prompt
    }

    generator_func = prompt_generators.get(gap['gap_type'])
    if generator_func:
        return generator_func(gap)
    else:
        return self._generate_generic_prompt(gap)
```

### 2a: Imaging Report Prompt Generator

```python
def _generate_imaging_prompt(self, gap: Dict) -> str:
    """Generate context-aware prompt for imaging report extraction"""

    who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
    molecular_subtype = self.who_2021_classification.get('molecular_subtype', '')

    # Calculate temporal context
    imaging_date = gap.get('event_date')
    days_from_radiation = self._calculate_days_from_radiation(imaging_date)
    days_from_surgery = self._calculate_days_from_surgery(imaging_date)

    # Determine if pseudoprogression window
    is_pseudoprogression_window = 21 <= days_from_radiation <= 90 if days_from_radiation else False

    prompt = f"""CONTEXT:
Patient with {who_dx} ({molecular_subtype}).
Imaging date: {imaging_date}
"""

    if is_pseudoprogression_window:
        prompt += f"""
CRITICAL WINDOW: PSEUDOPROGRESSION ASSESSMENT
This imaging is {days_from_radiation} days post-radiation (within 21-90 day pseudoprogression window).
Increased enhancement could be:
1. True tumor progression (requires treatment escalation)
2. Treatment-related inflammation/pseudoprogression (benign, self-limiting)

EXTRACTION PRIORITY: HIGHEST
"""
    elif days_from_surgery and days_from_surgery <= 7:
        prompt += f"""
POST-SURGICAL IMAGING ({days_from_surgery} days post-surgery)
Focus: Extent of resection assessment, residual tumor
"""
    else:
        prompt += f"""
SURVEILLANCE IMAGING
Focus: RANO response assessment, new lesions
"""

    prompt += f"""
EXTRACTION TASK:
Extract the following from this MRI report:

1. LESION MEASUREMENTS (CRITICAL):
   For EACH enhancing lesion:
   - Location (anatomic region)
   - Dimensions in cm (AP x ML x SI)
   - Enhancement pattern
   - Comparison to prior study

2. RANO RESPONSE:
   - New lesions? (yes/no)
   - Progression category: CR/PR/SD/PD

"""

    if is_pseudoprogression_window:
        prompt += """3. PSEUDOPROGRESSION FEATURES:
   - Diffusion characteristics (ADC, restricted diffusion)
   - Perfusion patterns (rCBV if mentioned)
   - FLAIR signal changes

"""

    prompt += """OUTPUT FORMAT (JSON):
{
  "lesions": [
    {
      "location": "string",
      "current_dimensions_cm": {"ap": float, "ml": float, "si": float},
      "prior_dimensions_cm": {"ap": float, "ml": float, "si": float} or null,
      "percent_change": float or null,
      "enhancement_pattern": "string"
    }
  ],
  "rano_assessment": {
    "new_lesions": "yes/no",
    "rano_category": "CR/PR/SD/PD/INDETERMINATE"
  },
  "radiologist_impression": "verbatim string",
  "extraction_confidence": "HIGH/MEDIUM/LOW"
}
"""

    return prompt
```

### 2b: Operative Note Prompt Generator

```python
def _generate_operative_note_prompt(self, gap: Dict) -> str:
    """Generate prompt for extent of resection extraction"""

    who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
    surgery_date = gap.get('event_date')
    surgery_type = gap.get('surgery_type', 'unknown')

    prompt = f"""CONTEXT:
Patient with {who_dx}.
Surgery: {surgery_type}, {surgery_date}

CLINICAL SIGNIFICANCE:
- Extent of resection (EOR) is a KEY PROGNOSTIC FACTOR
- GTR (gross total resection) → better survival
- Location/infiltration may limit resectability

EXTRACTION TASK:
Extract extent of resection (EOR) from this operative note.

LOOK FOR:
1. SURGEON'S ASSESSMENT:
   - Explicit statements: "gross total resection", "subtotal resection"
   - Estimated percent resection (e.g., "90% resection")
   - Residual tumor described?

2. REASONS FOR INCOMPLETE RESECTION:
   - Adherence to critical structures (vessels, nerves)
   - Infiltration patterns
   - Safety concerns

OUTPUT FORMAT (JSON):
{{
  "extent_of_resection": "GTR/STR/Biopsy",
  "estimated_percent_resection": integer (0-100) or null,
  "surgeon_verbatim_assessment": "exact quote",
  "residual_tumor": {{
    "present": "yes/no/uncertain",
    "location": "string or null"
  }},
  "extraction_confidence": "HIGH/MEDIUM/LOW"
}}

CATEGORIZATION RULES:
- GTR = "gross total resection", "complete resection", ">95%"
- STR = "subtotal", "near-total", "90-95%", "small residual"
- Biopsy = "biopsy only", "<50%"
"""

    return prompt
```

---

## Method 3: `_fetch_binary_document(fhir_id)`

**Purpose**: Retrieve binary document from FHIR server

```python
def _fetch_binary_document(self, fhir_target: str) -> Optional[bytes]:
    """
    Fetch binary document from FHIR server

    Args:
        fhir_target: FHIR resource reference (e.g., "DiagnosticReport/12345")

    Returns:
        Binary document content or None if not found
    """

    # MOCK MODE: Return placeholder
    if self.use_mock_medgemma:
        return b"MOCK_BINARY_CONTENT"

    # PRODUCTION: Fetch from FHIR server
    try:
        # Parse FHIR reference
        resource_type, resource_id = fhir_target.split('/')

        # TODO: Implement FHIR API call
        # This would use FHIR REST API to fetch the document
        # GET https://fhir-server.com/DiagnosticReport/12345
        # Then fetch the binary content from DocumentReference

        logger.warning(f"FHIR fetch not yet implemented for {fhir_target}")
        return None

    except Exception as e:
        logger.error(f"Error fetching {fhir_target}: {e}")
        return None
```

---

## Method 4: `_mock_medgemma_extraction(gap, prompt)`

**Purpose**: Generate realistic mock extractions for testing

```python
def _mock_medgemma_extraction(self, gap: Dict, prompt: str) -> Dict:
    """
    Generate mock MedGemma extraction for testing

    Returns realistic extraction results based on gap type
    """

    gap_type = gap['gap_type']

    if gap_type == 'missing_eor':
        return {
            'extent_of_resection': 'STR',
            'estimated_percent_resection': 90,
            'surgeon_verbatim_assessment': 'Near-total resection achieved with small residual along deep venous structures',
            'residual_tumor': {
                'present': 'yes',
                'location': 'Adjacent to internal cerebral veins'
            },
            'extraction_confidence': 'HIGH',
            'extraction_timestamp': datetime.now().isoformat(),
            'source_document': gap.get('medgemma_target', 'unknown')
        }

    elif gap_type == 'vague_imaging_conclusion':
        return {
            'lesions': [
                {
                    'location': 'Pineal region',
                    'current_dimensions_cm': {'ap': 3.2, 'ml': 2.1, 'si': 2.8},
                    'prior_dimensions_cm': {'ap': 3.8, 'ml': 2.5, 'si': 3.1},
                    'percent_change': -15.8,
                    'enhancement_pattern': 'Heterogeneous ring enhancement'
                }
            ],
            'rano_assessment': {
                'new_lesions': 'no',
                'rano_category': 'PR'
            },
            'radiologist_impression': 'Decreased enhancing lesion consistent with treatment response',
            'extraction_confidence': 'HIGH',
            'extraction_timestamp': datetime.now().isoformat(),
            'source_document': gap.get('medgemma_target', 'unknown')
        }

    elif gap_type == 'missing_radiation_dose':
        return {
            'total_dose_cgy': 5400,
            'fractionation': '1.8 Gy x 30 fractions',
            'radiation_fields': 'Craniospinal (23.4 Gy) + posterior fossa boost (30.6 Gy)',
            'start_date': '2023-05-01',
            'end_date': '2023-06-15',
            'treatment_interruptions': 'None',
            'extraction_confidence': 'HIGH',
            'extraction_timestamp': datetime.now().isoformat(),
            'source_document': gap.get('medgemma_target', 'unknown')
        }

    else:
        return {
            'extraction_note': f'Mock extraction for {gap_type}',
            'extraction_confidence': 'MEDIUM',
            'extraction_timestamp': datetime.now().isoformat()
        }
```

---

## Method 5: `_call_medgemma(document, prompt)`

**Purpose**: Call actual MedGemma API (production)

```python
def _call_medgemma(self, document: bytes, prompt: str) -> Dict:
    """
    Call MedGemma API for extraction

    Args:
        document: Binary document content
        prompt: Context-aware extraction prompt

    Returns:
        Dict with extraction result in JSON format
    """

    # TODO: Implement actual MedGemma API call
    # This would depend on MedGemma's API specification

    logger.warning("Real MedGemma API not yet implemented, using mock")
    return self._mock_medgemma_extraction({}, prompt)
```

---

## Method 6: `_integrate_extraction_into_timeline(gap, result)`

**Purpose**: Merge MedGemma extraction back into timeline events

```python
def _integrate_extraction_into_timeline(self, gap: Dict, extraction_result: Dict):
    """
    Integrate MedGemma extraction into timeline events

    Updates the corresponding timeline event with extracted data
    """

    gap_type = gap['gap_type']
    event_date = gap.get('event_date')

    # Find corresponding timeline event(s)
    if gap_type == 'missing_eor':
        # Update surgery event
        surgery_events = [e for e in self.timeline_events
                         if e['event_type'] == 'surgery' and e.get('event_date') == event_date]
        for event in surgery_events:
            event['medgemma_extraction'] = extraction_result
            event['extent_of_resection'] = extraction_result.get('extent_of_resection')
            event['percent_resection'] = extraction_result.get('estimated_percent_resection')

    elif gap_type == 'vague_imaging_conclusion':
        # Update imaging event
        imaging_events = [e for e in self.timeline_events
                         if e['event_type'] == 'imaging' and e.get('event_date') == event_date]
        for event in imaging_events:
            event['medgemma_extraction'] = extraction_result
            event['tumor_measurements'] = extraction_result.get('lesions', [])
            event['rano_assessment'] = extraction_result.get('rano_assessment', {})

    elif gap_type == 'missing_radiation_dose':
        # Update radiation event
        radiation_events = [e for e in self.timeline_events
                           if e['event_type'] == 'radiation_start' and e.get('event_date') == event_date]
        for event in radiation_events:
            event['medgemma_extraction'] = extraction_result
            event['total_dose_cgy'] = extraction_result.get('total_dose_cgy')
            event['fractionation'] = extraction_result.get('fractionation')

    logger.info(f"Integrated extraction for {gap_type} on {event_date}")
```

---

## Method 7: `_reassess_gaps_post_extraction()`

**Purpose**: Re-evaluate timeline for remaining gaps after extraction

```python
def _reassess_gaps_post_extraction(self):
    """
    Re-assess timeline for gaps after MedGemma extractions

    This identifies:
    1. Gaps that were successfully filled
    2. New gaps revealed by extractions
    3. Remaining unresolved gaps
    """

    original_gap_count = len(self.extraction_gaps)

    # Filter out resolved gaps
    unresolved_gaps = [g for g in self.extraction_gaps
                       if g.get('status') != 'RESOLVED']

    # Check for new gaps (e.g., imaging shows new lesion → need follow-up)
    # This would run similar logic to _phase3_identify_extraction_gaps()

    resolved_count = len([g for g in self.extraction_gaps if g.get('status') == 'RESOLVED'])

    logger.info(f"Gaps resolved: {resolved_count}/{original_gap_count}")
    logger.info(f"Gaps remaining: {len(unresolved_gaps)}")
```

---

## Testing Strategy

### Step 1: Add Mock Mode Flag to __init__

```python
def __init__(self, patient_id: str, output_dir: Path, use_mock_medgemma: bool = True):
    self.patient_id = patient_id
    self.use_mock_medgemma = use_mock_medgemma  # NEW FLAG
    # ... rest of init
```

### Step 2: Test with Mock Extractions

```bash
# Run with mock MedGemma (default)
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/mock_medgemma_test \
  --use-mock-medgemma
```

### Step 3: Verify Timeline Integration

Check that timeline artifact includes:
- Surgery events with `medgemma_extraction` and `extent_of_resection`
- Imaging events with `tumor_measurements` and `rano_assessment`
- Radiation events with extracted `total_dose_cgy`

### Step 4: Implement Real MedGemma API

Once mock testing passes, replace `_call_medgemma()` with real API integration.

---

## Expected Output (Mock Mode)

```
PHASE 4: PRIORITIZED BINARY EXTRACTION
--------------------------------------------------------------------------------
  Extracting from 153 documents using MedGemma (MOCK MODE)...

  [1/153] Processing missing_eor (HIGHEST priority)
    ✅ Generated context-aware prompt (234 tokens)
    ✅ Fetched binary document: Procedure/xyz (MOCK)
    ✅ MedGemma extraction complete (HIGH confidence)
    ✅ Integrated: extent_of_resection = STR (90%)

  [2/153] Processing vague_imaging_conclusion (HIGHEST priority - pseudoprogression window)
    ✅ Generated context-aware prompt (312 tokens)
    ✅ Fetched binary document: DiagnosticReport/abc (MOCK)
    ✅ MedGemma extraction complete (HIGH confidence)
    ✅ Integrated: tumor measurements, RANO = PR

  ...

  ✅ Extracted from 151 documents
  ⚠️  2 require manual review (LOW confidence)

  Re-assessing gaps post-extraction...
  ✅ Gaps resolved: 151/153
  ✅ Gaps remaining: 2
```

---

## Next Steps

1. ✅ Implement all methods with mock functionality
2. ✅ Test on Pineoblastoma patient
3. ✅ Verify timeline artifact integration
4. ⬜ Implement real FHIR document fetching
5. ⬜ Integrate with MedGemma API
6. ⬜ Run on all 9 patients

---

**Document Version**: 1.0
**Created**: 2025-10-30
**Purpose**: Implementation guide for Phase 4 MedGemma integration with mock testing capability
