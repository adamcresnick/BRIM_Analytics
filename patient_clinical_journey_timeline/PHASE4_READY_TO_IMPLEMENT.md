# Phase 4 MedGemma Integration - Ready to Implement

**Status**: All prerequisites identified, implementation plan ready
**Date**: 2025-10-30

---

## Summary

I've identified all your existing MedGemma/Ollama infrastructure from the MVP work and created a complete implementation plan for Phase 4 (binary extraction with real MedGemma).

---

## Existing Infrastructure (Reusable from MVP)

### 1. MedGemmaAgent (`mvp/agents/medgemma_agent.py`)
- **Model**: `gemma2:27b` via Ollama (http://localhost:11434)
- **Key Features**:
  - JSON format extraction with retry logic
  - Temperature control (default 0.1 for deterministic extraction)
  - Automatic prompt formatting
  - Error handling with 3 retries
  - Response parsing (handles markdown code blocks)
- **Usage**:
```python
from mvp.agents.medgemma_agent import MedGemmaAgent

agent = MedGemmaAgent(model_name="gemma2:27b")
result = agent.extract(
    prompt=context_aware_prompt,
    temperature=0.1
)
# result.extracted_data contains parsed JSON
# result.confidence contains extraction confidence
```

### 2. BinaryFileAgent (`mvp/agents/binary_file_agent.py`)
- **Purpose**: Streams binary files from S3 and extracts text
- **S3 Configuration**:
  - Bucket: `radiant-prd-343218191717-us-east-1-prd-ehr-pipeline`
  - Prefix: `prd/source/Binary/`
  - Profile: `radiant-prod`
- **Critical S3 Bug Fix**: FHIR Binary IDs use periods (.) but S3 files use underscores (_)
  - Example: `Binary/fmAXdcPPNkiCF9rr.5soVBQ` → `prd/source/Binary/fmAXdcPPNkiCF9rr_5soVBQ`
- **Text Extraction**:
  - PDF: PyMuPDF (fitz)
  - HTML: BeautifulSoup
  - Streams from S3 (no local storage)
- **Usage**:
```python
from mvp.agents.binary_file_agent import BinaryFileAgent

agent = BinaryFileAgent(aws_profile="radiant-prod")
extracted = agent.fetch_and_extract_text(binary_id="Binary/xyz...")
# extracted.extracted_text contains full document text
```

### 3. DocumentTextCache (`mvp/utils/document_text_cache.py`)
- **Purpose**: Caches extracted text to avoid re-extraction
- **Storage**: DuckDB table with full provenance
- **Benefits**: Extract once, reuse many times

---

## Implementation Plan for Phase 4

### Step 1: Create `agents/` directory in timeline framework

```bash
mkdir -p /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/agents
```

### Step 2: Copy reusable agents

```bash
# Copy MedGemma agent
cp mvp/agents/medgemma_agent.py patient_clinical_journey_timeline/agents/

# Copy Binary file agent
cp mvp/agents/binary_file_agent.py patient_clinical_journey_timeline/agents/
```

### Step 3: Create `patient_timeline_abstraction_V2.py` with Phase 4

The new script will:
1. Initialize MedGemmaAgent and BinaryFileAgent in `__init__()`
2. Implement `_phase4_extract_from_binaries()` with real extraction
3. Add context-aware prompt generation methods:
   - `_generate_imaging_prompt()` - for radiology reports
   - `_generate_operative_note_prompt()` - for EOR extraction
   - `_generate_radiation_summary_prompt()` - for dose extraction
   - `_generate_pathology_prompt()` - for molecular markers
4. Implement `_fetch_binary_document()` using BinaryFileAgent
5. Implement `_call_medgemma()` using MedGemmaAgent
6. Implement `_integrate_extraction_into_timeline()` to merge results

### Step 4: Add Ollama verification

Before running extractions:
```python
def _verify_medgemma_available(self):
    """Verify Ollama is running and gemma2:27b is available"""
    try:
        agent = MedGemmaAgent(model_name="gemma2:27b")
        logger.info("✅ MedGemma (gemma2:27b) is available via Ollama")
        return True
    except ConnectionError as e:
        logger.error(f"❌ Ollama not accessible: {e}")
        logger.error("Start Ollama with: ollama serve")
        logger.error("Pull model with: ollama pull gemma2:27b")
        return False
```

---

## Phase 4 Implementation Code Structure

### Modified `__init__()`:

```python
def __init__(self, patient_id: str, output_dir: Path):
    # ... existing init code ...

    # Initialize agents for Phase 4
    self.medgemma_agent = None
    self.binary_agent = None

    # Verify Ollama is available
    if self._verify_medgemma_available():
        from agents.medgemma_agent import MedGemmaAgent
        from agents.binary_file_agent import BinaryFileAgent

        self.medgemma_agent = MedGemmaAgent(model_name="gemma2:27b", temperature=0.1)
        self.binary_agent = BinaryFileAgent(aws_profile="radiant-prod")
        logger.info("✅ MedGemma and BinaryFile agents initialized")
    else:
        logger.warning("⚠️  Phase 4 (binary extraction) will be skipped - Ollama not available")
```

### New `_phase4_extract_from_binaries()`:

```python
def _phase4_extract_from_binaries(self):
    """
    Phase 4: Real MedGemma extraction from binary documents
    """

    if not self.medgemma_agent or not self.binary_agent:
        print("  ⚠️  Ollama/MedGemma not available - skipping binary extraction")
        return

    # Prioritize gaps
    prioritized_gaps = sorted(
        self.extraction_gaps,
        key=lambda x: {'HIGHEST': 0, 'HIGH': 1, 'MEDIUM': 2}.get(x.get('priority', 'LOW'), 3)
    )

    print(f"  Extracting from {len(prioritized_gaps)} documents using MedGemma...")

    extracted_count = 0
    failed_count = 0

    for i, gap in enumerate(prioritized_gaps, 1):
        print(f"\n  [{i}/{len(prioritized_gaps)}] Processing {gap['gap_type']} (priority: {gap.get('priority')})")

        # STEP 1: Generate context-aware prompt
        prompt = self._generate_medgemma_prompt(gap)
        print(f"    ✅ Generated context-aware prompt ({len(prompt)} chars)")

        # STEP 2: Fetch binary document
        try:
            extracted_text = self._fetch_binary_document(gap.get('medgemma_target'))
            if not extracted_text:
                print(f"    ❌ Failed to fetch document")
                failed_count += 1
                continue
            print(f"    ✅ Fetched document ({len(extracted_text)} chars)")
        except Exception as e:
            print(f"    ❌ Error fetching document: {e}")
            failed_count += 1
            continue

        # STEP 3: Call MedGemma
        try:
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT:\n{extracted_text}"
            result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

            if result.success:
                print(f"    ✅ MedGemma extraction complete ({result.confidence} confidence)")

                # STEP 4: Integrate into timeline
                self._integrate_extraction_into_timeline(gap, result.extracted_data)
                gap['status'] = 'RESOLVED'
                gap['extraction_result'] = result.extracted_data
                extracted_count += 1
            else:
                print(f"    ❌ Extraction failed: {result.error}")
                gap['status'] = 'REQUIRES_MANUAL_REVIEW'
                failed_count += 1
        except Exception as e:
            print(f"    ❌ MedGemma error: {e}")
            gap['status'] = 'REQUIRES_MANUAL_REVIEW'
            failed_count += 1

    print(f"\n  ✅ Extracted from {extracted_count} documents")
    print(f"  ❌ {failed_count} failed or require manual review")
```

### Context-Aware Prompt Generator (Example - Imaging):

```python
def _generate_imaging_prompt(self, gap: Dict) -> str:
    """Generate context-aware prompt for imaging report extraction"""

    who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
    molecular_subtype = self.who_2021_classification.get('molecular_subtype', '')

    prompt = f"""You are a medical AI extracting structured data from a radiology report.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Molecular Subtype: {molecular_subtype}
- Imaging Date: {gap.get('event_date')}
- Imaging Modality: {gap.get('imaging_modality')}

TASK:
Extract structured tumor measurements and response assessment from this radiology report.

OUTPUT FORMAT (JSON):
{{
  "lesions": [
    {{
      "location": "anatomic location",
      "current_dimensions_cm": {{"ap": float, "ml": float, "si": float}},
      "prior_dimensions_cm": {{"ap": float, "ml": float, "si": float}} or null,
      "percent_change": float or null,
      "enhancement_pattern": "description"
    }}
  ],
  "rano_assessment": {{
    "new_lesions": "yes" or "no",
    "rano_category": "CR" or "PR" or "SD" or "PD" or "INDETERMINATE"
  }},
  "radiologist_impression": "verbatim impression/conclusion",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

IMPORTANT:
- Extract bidimensional measurements (perpendicular diameters)
- If prior measurements mentioned, include them for comparison
- RANO categories: CR=complete response, PR=partial response, SD=stable disease, PD=progressive disease
"""

    return prompt
```

---

## Testing Strategy

### Test 1: Single Imaging Gap (Low Risk)
```bash
# Run on Pineoblastoma patient, extract ONE imaging report
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_single \
  --max-extractions 1  # NEW FLAG: limit to 1 extraction for testing
```

### Test 2: High-Priority Gaps Only
```bash
# Extract only HIGHEST priority gaps (e.g., missing EOR)
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_test_high_priority \
  --priority-filter HIGHEST
```

### Test 3: Full Extraction (All 153 Gaps)
```bash
# Run full Phase 4 on all gaps
python3 scripts/patient_timeline_abstraction_V2.py \
  --patient-id e8jPD8zawpt.KIpA97WuwdDCHyK.qEO5mX-6tEB7krPU3 \
  --output-dir output/phase4_full
```

---

## Prerequisites Checklist

Before implementing Phase 4:

- ✅ **Ollama running**: Verify with `ollama list`
- ✅ **gemma2:27b available**: Pull with `ollama pull gemma2:27b`
- ✅ **AWS SSO logged in**: Run `aws sso login --profile radiant-prod`
- ✅ **Existing agents copied**: Copy from mvp/agents/ to patient_clinical_journey_timeline/agents/
- ✅ **Dependencies installed**: Ensure PyMuPDF (fitz), boto3, beautifulsoup4

---

## Implementation Complexity

**Estimated Implementation Time**: 2-3 hours

**Components**:
1. Copy agents directory (5 min)
2. Add agent initialization to script (15 min)
3. Implement `_phase4_extract_from_binaries()` (30 min)
4. Implement 4 prompt generators (45 min)
5. Implement integration logic (30 min)
6. Testing (30-60 min)

---

## Next Steps

**Option A**: I can implement the full Phase 4 now
- Create patient_timeline_abstraction_V2.py with real MedGemma integration
- Copy agents from MVP
- Test on 1 imaging gap first

**Option B**: Document only for now
- You implement Phase 4 later when you're ready to run extractions

**Option C**: Implement incrementally
- Start with just imaging extraction
- Add operative note extraction later
- Add radiation/pathology extraction last

Which would you like me to do?

---

**Status**: Waiting for user decision on implementation approach
