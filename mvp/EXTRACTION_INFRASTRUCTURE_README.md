# RADIANT Clinical Data Extraction Infrastructure

**Last Updated**: 2025-10-23

## Overview

This document describes the complete clinical data extraction infrastructure for RADIANT PCA, including the multi-source abstraction workflow that extracts and integrates data from imaging, surgeries, radiation, chemotherapy, and progress notes.

## Quick Start

```bash
# Navigate to project
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp

# Run extraction for a patient
python3 scripts/run_full_multi_source_abstraction.py \
    --patient-id Patient/YOUR_PATIENT_ID

# Output location
data/patient_abstractions/<timestamp>/Patient_<id>_comprehensive.json
```

## Architecture

###  Workflow Phases

The extraction workflow consists of 7 phases:

#### PHASE 1-PRE: Radiation & Chemotherapy Extraction
- Queries v_radiation_summary, v_chemo_medications
- Extracts complete radiation treatment history (courses, modality, site, dose)
- Extracts chemotherapy regimens (medications, dates, schedules)
- **Output**: Top-level `radiation` and `chemotherapy` keys in comprehensive JSON

#### PHASE 1: Data Querying (Athena)
- **1A**: Imaging text reports (v_imaging)
- **1B**: Imaging PDFs (v_binary_files, content_type='application/pdf')
- **1C**: Tumor surgeries (v_procedures_tumor)
- **1C-DOCUMENTS**: Operative note documents (v_binary_files, all formats: PDF/HTML/text)
- **1D**: Progress notes (v_binary_files, prioritized using temporal matching)

**Progress Note Prioritization Strategy**:
- Post-surgery notes (±7 days from surgery)
- Post-imaging notes (±7 days from imaging)
- Post-medication change notes (±7 days from chemo start/stop)
- Final progress note (most recent)

#### PHASE 2: Agent 2 (MedGemma) Extraction
- **2A**: Imaging → tumor_status, imaging_type
- **2B**: Imaging PDFs → tumor_status, imaging_type
- **2C**: Operative notes → extent_of_resection, tumor_location
- **2D**: Progress notes → disease_state

**Content Type Handling**: BinaryFileAgent automatically routes extraction:
- `application/pdf` → PyMuPDF
- `text/html`, `text/plain`, `text/rtf` → BeautifulSoup

#### PHASE 3: Temporal Inconsistency Detection (Agent 1)
- Analyzes tumor status timeline from imaging
- Detects suspicious patterns (rapid improvement without surgery, unexpected progression)
- Marks high-severity inconsistencies for review

#### PHASE 4: Agent 1 ↔ Agent 2 Clarification
- Queries Agent 2 for clarification on high-severity inconsistencies
- Builds structured prompts with timeline context
- Returns action recommendations (keep_both, keep_first, keep_second)

#### PHASE 5: EOR Adjudication (Agent 1)
- Compares operative report EOR with post-op imaging (within 72h)
- Uses EORAdjudicator to reconcile discrepancies
- Returns final EOR with confidence score

#### PHASE 6: Event Classification (Agent 1)
- Classifies events as: Initial CNS Tumor, Recurrence, Progressive, Second Malignancy
- Uses EventTypeClassifier with timeline context
- Returns classification with confidence score

#### PHASE 7: Quality Review (Planned)
- Post-extraction quality analysis using ExtractionQualityReviewer
- Generates process summaries with successes/failures
- Deep log analysis to identify failure patterns
- Gap analysis comparing Phase 1 queries vs successful extractions
- *Status: Code ready in [agents/extraction_quality_reviewer.py](agents/extraction_quality_reviewer.py), integration pending*

## Key Components

### Agents

- **[agents/medgemma_agent.py](agents/medgemma_agent.py)**: Agent 2 - MedGemma extraction for clinical variables
- **[agents/binary_file_agent.py](agents/binary_file_agent.py)**: Streams and extracts text from S3 binary files (PDF/HTML)
  - **Features**: Automatic content type routing, AWS SSO token refresh, period-to-underscore S3 path conversion
- **[agents/radiation_extractor.py](agents/radiation_extractor.py)**: Extracts radiation treatment history
- **[agents/chemo_extractor.py](agents/chemo_extractor.py)**: Extracts chemotherapy regimens
- **[agents/enhanced_master_agent.py](agents/enhanced_master_agent.py)**: Agent 1 - Temporal inconsistency detection
- **[agents/eor_adjudicator.py](agents/eor_adjudicator.py)**: Agent 1 - EOR adjudication logic
- **[agents/event_type_classifier.py](agents/event_type_classifier.py)**: Agent 1 - Event classification logic
- **[agents/extraction_quality_reviewer.py](agents/extraction_quality_reviewer.py)**: Agent 1 - Post-extraction quality review

### Utilities

- **[utils/progress_note_prioritization.py](utils/progress_note_prioritization.py)**: Temporal matching for progress note selection
- **[utils/athena_query.py](utils/athena_query.py)**: AWS Athena query utilities

### Scripts

- **[scripts/run_full_multi_source_abstraction.py](scripts/run_full_multi_source_abstraction.py)**: Main extraction workflow

## Data Sources (AWS Athena Views)

| View | Purpose | Key Fields |
|------|---------|-----------|
| `v_imaging` | Imaging text reports | imaging_date, tumor_status, imaging_type |
| `v_binary_files` | Binary documents (PDF/HTML/text) | content_type, dr_type_text, binary_id |
| `v_procedures_tumor` | Tumor surgeries | procedure_date, is_tumor_surgery |
| `v_radiation_summary` | Radiation courses | modality, site, total_dose_gy |
| `v_chemo_medications` | Chemotherapy medications | medication_name, start_date, stop_date |

## Output Format

The comprehensive JSON output contains:

```json
{
  "patient_id": "Patient/...",
  "timestamp": "...",
  "radiation": {
    "courses": [...],
    "completeness_percent": 100.0
  },
  "chemotherapy": {
    "medications": [...],
    "regimens": [...]
  },
  "imaging": [...],
  "surgeries": [...],
  "progress_notes": [...],
  "phases": {
    "data_query": {...},
    "imaging_text": {...},
    "imaging_pdfs": {...},
    "operative_reports": {...},
    "progress_notes": {...},
    "temporal_detection": {...},
    "clarification": {...},
    "eor_adjudication": {...},
    "event_classification": {...}
  }
}
```

## Recent Fixes (2025-10-23 Session)

### Completed
1. **Radiation/Chemotherapy Integration** - Added top-level keys to comprehensive JSON ([scripts/run_full_multi_source_abstraction.py:403-405](scripts/run_full_multi_source_abstraction.py#L403-L405))
2. **Operative Note Multi-Format Support** - Updated queries to support PDF/HTML/text formats ([scripts/run_full_multi_source_abstraction.py:477-567](scripts/run_full_multi_source_abstraction.py#L477-L567))
3. **AWS SSO Token Refresh** - Added automatic token refresh to BinaryFileAgent for long-running extractions ([agents/binary_file_agent.py:124-220](agents/binary_file_agent.py#L124-L220))
4. **ExtractionQualityReviewer Agent** - Created comprehensive quality review framework ([agents/extraction_quality_reviewer.py](agents/extraction_quality_reviewer.py))
5. **Data Query Phase Tracking** - Added operative_note_documents_count to phase summary ([scripts/run_full_multi_source_abstraction.py:721](scripts/run_full_multi_source_abstraction.py#L721))

### Pending
- PHASE 7 quality review integration
- `all_locations_mentioned_normalized` field for tumor locations

## Key Features

### AWS SSO Token Refresh
The BinaryFileAgent now automatically refreshes AWS SSO tokens when they expire (typically after 2.5 hours), preventing extraction failures in long-running workflows.

```python
# Automatic token refresh in stream_binary_from_s3()
if 'TokenRetrievalError' in error_str:
    self._refresh_s3_client()
    continue  # Retry with fresh token
```

### Multi-Format Document Handling
Operative notes are now extracted from ALL formats:
- PDF documents → PyMuPDF extraction
- HTML documents → BeautifulSoup extraction
- Plain text documents → Direct text extraction

### Progress Note Prioritization
Intelligently selects a subset of progress notes based on clinical event proximity, reducing extraction volume while capturing critical disease state assessments.

## Testing

**Test Patient**: `Patient/eXnzuKb7m14U1tcLfICwETX7Gs0ok.FRxG4QodMdhoPg3`
- Has complete radiation and chemotherapy data
- Multiple imaging events
- Suitable for end-to-end workflow testing

## Common Issues

### Token Expiration
**Symptom**: Extractions fail after ~2.5 hours with S3 errors

**Solution**: AWS SSO token refresh is now automatic. If manual refresh needed:
```bash
aws sso login --profile radiant-prod
```

### S3 404 Errors
**Symptom**: Files in v_binary_files metadata don't exist in S3

**Solution**: This is a data integrity issue. The workflow logs these as errors and continues.

## Documentation Files

- [FINAL_SESSION_STATUS.md](FINAL_SESSION_STATUS.md) - Latest session status (2025-10-23)
- [WORK_COMPLETION_SUMMARY.md](WORK_COMPLETION_SUMMARY.md) - Detailed work summary
- [README_AGENT_1_COMPLETE.md](README_AGENT_1_COMPLETE.md) - Agent 1 implementation guide

## Next Steps

1. Integrate PHASE 7 quality review into workflow
2. Add `all_locations_mentioned_normalized` field
3. Test end-to-end workflow with multiple patients
4. Monitor token refresh effectiveness in production

## Contact

For questions or issues with the extraction infrastructure, refer to:
- Code documentation in agent files
- Session status files in mvp directory
- Git commit history for implementation details
