# Local LLM Extraction Pipeline (BRIM Mimic)

## Overview

This pipeline mimics BRIM's extraction workflow using either Claude API or **free local models via Ollama**. It processes the same 3 CSV input files that BRIM uses and produces similar output format.

**Two Options:**
1. **Claude API** (Anthropic) - Cloud-based, fast, costs ~$8-10 per patient
2. **Ollama** (Local) - FREE, runs on your machine, no API key needed!

**Use cases:**
- BRIM is down/unavailable
- Need faster turnaround than BRIM's processing time
- Want more control over extraction prompts and logic
- Testing extraction strategies before uploading to BRIM
- **Want to avoid API costs** (use Ollama for FREE inference!)

## Architecture

The pipeline follows BRIM's two-stage approach:

### Stage 1: Variable Extraction
- Reads `project.csv` (documents) and `variables.csv` (extraction instructions)
- For each (variable, document) pair:
  - Sends document text + extraction instruction to Claude
  - Stores extracted value
- **Output**: `extraction_results_{FHIR_ID}.csv` (long format)

### Stage 2: Decision Adjudication
- Reads `decisions.csv` (adjudication instructions) and extracted variables
- For each decision:
  - Identifies relevant variables (mentioned in instruction)
  - Sends all extracted values + adjudication logic to Claude
  - Stores adjudicated value
- **Output**: `adjudication_results_{FHIR_ID}.csv`

### Stage 3: Summary Output
- Creates wide-format summary table
- One row per patient, one column per decision
- **Output**: `extraction_summary_{FHIR_ID}.csv`

## Quick Start

### Option A: FREE Local Model (Ollama) - Recommended!

```bash
# 1. Install Ollama (see OLLAMA_SETUP.md for details)
# macOS: Download from https://ollama.ai/download
# Linux: curl -fsSL https://ollama.ai/install.sh | sh

# 2. Start Ollama
ollama serve

# 3. Pull a model (one-time download)
ollama pull llama3.1:70b    # 70B model, excellent quality
# OR
ollama pull llama3.1:8b     # 8B model, faster but lower quality

# 4. Install Python package
pip install ollama pandas pyyaml

# 5. Run extraction (NO API KEY NEEDED!)
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction
python3 local_llm_extraction_pipeline_with_ollama.py \
    ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml \
    --model ollama \
    --ollama-model llama3.1:70b
```

**See [OLLAMA_SETUP.md](OLLAMA_SETUP.md) for complete Ollama installation and configuration guide.**

### Option B: Claude API (Paid)

```bash
# 1. Install Python packages
pip install anthropic pandas pyyaml

# 2. Get API key from https://console.anthropic.com/

# 3. Set API key

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 3. Input Files

You need the 3 BRIM input files already generated:
- `project_{FHIR_ID}.csv` - Documents with NOTE_ID, PERSON_ID, NOTE_TEXT, NOTE_TITLE
- `variables_{FHIR_ID}.csv` - Extraction instructions
- `decisions_{FHIR_ID}.csv` - Adjudication instructions

## Usage

### Basic Usage

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/local_llm_extraction

python3 local_llm_extraction_pipeline.py ../brim_workflows_individual_fields/extent_of_resection/patient_config_e4BwD8ZYDBccepXcJ.Ilo3w3.yaml
```

### Expected Output

```
================================================================================
LOCAL LLM EXTRACTION PIPELINE (BRIM Mimic)
================================================================================
Patient FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3
Person ID: 1277724
Model: claude-sonnet-4-20250514
================================================================================

Loading BRIM input files...
  Loaded project.csv: 100 documents
  Loaded variables.csv: 13 variables
  Loaded decisions.csv: 10 decisions

================================================================================
STEP 1: VARIABLE EXTRACTION
================================================================================

Total extractions to perform: 1300
  (13 variables × 100 documents)

Variable 1/13: event_number (scope: one_per_note)
  Progress: 10/1300 extractions completed
  ...
  Completed event_number across 100 documents

✓ Variable extraction completed: 1300 total extractions

================================================================================
STEP 2: DECISION ADJUDICATION
================================================================================

Total decisions to adjudicate: 10

Decision 1/10: event_type_adjudicated
  Depends on 3 variables: event_type_structured, progression_recurrence_indicator_operative_note, progression_recurrence_indicator_imaging
  Result: Initial CNS Tumor (based on operative note indicating "newly diagnosed"...)

✓ Decision adjudication completed: 10 decisions

================================================================================
STEP 3: SAVING RESULTS
================================================================================

  Saved variable extraction results: extraction_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
    (1300 rows)
  Saved decision adjudication results: adjudication_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
    (10 rows)

  Creating summary pivot table...
  Saved extraction summary: extraction_summary_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
    (11 columns)

================================================================================
✓ EXTRACTION PIPELINE COMPLETED
================================================================================
Total execution time: 245.3 seconds

Output files:
  1. Variable extractions: extraction_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
  2. Decision adjudications: adjudication_results_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
  3. Summary (wide format): extraction_summary_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
================================================================================
```

## Output Files

### 1. `extraction_results_{FHIR_ID}.csv` (Long Format)

Contains one row per (variable, document) extraction.

Columns:
- `PERSON_ID` - Patient identifier (pseudoMRN)
- `NOTE_ID` - Document identifier
- `NOTE_TITLE` - Document type
- `variable_name` - Name of extracted variable
- `extracted_value` - Value extracted by Claude
- `extraction_timestamp` - ISO timestamp

Example:
```csv
PERSON_ID,NOTE_ID,NOTE_TITLE,variable_name,extracted_value,extraction_timestamp
1277724,op_note_1_2018-05-28,OP Note - Complete,extent_from_operative_note,Gross/Near total resection,2025-10-11T21:45:23.123456
1277724,imaging_2018-05-29_1,MRI Report - Impression,extent_from_postop_imaging,Gross/Near total resection,2025-10-11T21:45:24.234567
```

### 2. `adjudication_results_{FHIR_ID}.csv`

Contains one row per adjudicated decision.

Columns:
- `PERSON_ID` - Patient identifier
- `decision_name` - Name of decision variable
- `adjudicated_value` - Final adjudicated value
- `adjudication_timestamp` - ISO timestamp

Example:
```csv
PERSON_ID,decision_name,adjudicated_value,adjudication_timestamp
1277724,event_type_adjudicated,Initial CNS Tumor (operative note indicates newly diagnosed tumor),2025-10-11T21:50:15.345678
1277724,extent_of_resection_adjudicated,Gross/Near total resection (operative note and post-op imaging agree),2025-10-11T21:50:16.456789
```

### 3. `extraction_summary_{FHIR_ID}.csv` (Wide Format)

One row per patient, one column per decision. Easy to import into analysis tools.

Example:
```csv
PERSON_ID,event_type_adjudicated,extent_of_resection_adjudicated,tumor_location_adjudicated,...
1277724,Initial CNS Tumor,Gross/Near total resection,Cerebellum/Posterior Fossa,...
```

## Performance

### Extraction Speed

**For patient C1277724 (100 documents, 13 variables, 10 decisions):**

- **Variable extractions**: 1,300 total (13 × 100)
  - Estimated time: ~3-4 minutes (with Claude API rate limits)
  - ~0.15 seconds per extraction

- **Decision adjudications**: 10 total
  - Estimated time: ~10-20 seconds
  - ~1-2 seconds per decision

**Total estimated time**: ~4-5 minutes

### Cost Estimation

Using Claude Sonnet 4:
- Input: $3 per million tokens
- Output: $15 per million tokens

**Approximate cost per patient** (100 documents):
- Variable extraction: ~1,300 API calls × ~2,000 input tokens = ~2.6M input tokens = ~$8
- Decision adjudication: ~10 API calls × ~5,000 input tokens = ~50K input tokens = ~$0.15
- **Total**: ~$8-10 per patient

Compare to BRIM:
- BRIM: Free (but slower, requires upload/download, subject to availability)
- Local: ~$8-10 (but faster, runs locally, always available)

## Comparison to BRIM

| Feature | BRIM | Local Pipeline |
|---------|------|----------------|
| **Speed** | Hours to days | ~5 minutes |
| **Cost** | Free | ~$8-10 per patient |
| **Availability** | Requires internet, subject to downtime | Local, always available |
| **Model** | GPT-4 (OpenAI) | Claude Sonnet 4 (Anthropic) |
| **Customization** | Limited | Full control over prompts |
| **Results format** | BRIM-specific | CSV (customizable) |
| **Debugging** | Black box | Full visibility |

## Customization

### Using Different Models

Edit `local_llm_extraction_pipeline.py`:

```python
# Line 59
self.model = "claude-sonnet-4-20250514"  # Change to desired model
```

Available Claude models:
- `claude-sonnet-4-20250514` - Latest Sonnet (recommended)
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet
- `claude-opus-4-20250514` - Opus (slower but more accurate)

### Adjusting Temperature

For more deterministic extractions, temperature is set to 0 (line 134, 197).

For more creative/flexible extractions, increase temperature:

```python
temperature=0.3,  # Slight variation allowed
```

### Parallel Processing

For faster extraction, you can modify the pipeline to process multiple documents in parallel:

1. Use `concurrent.futures.ThreadPoolExecutor`
2. Respect Anthropic API rate limits (default: 50 requests/minute for Tier 1)

## Troubleshooting

### Error: `ANTHROPIC_API_KEY environment variable not set`

**Solution**: Set your API key:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

### Error: `Rate limit exceeded`

**Solution**: The script uses sequential processing to avoid rate limits. If you modified it to use parallel processing, add rate limiting logic.

### Error: `Input too long`

**Solution**: Some imaging reports are very long. You can:
1. Truncate NOTE_TEXT to first N characters
2. Use Claude's extended context (200K tokens for Sonnet 4)
3. Split long documents into chunks

### Poor Extraction Quality

**Solution**:
1. Check the extraction instructions in `variables.csv` - may need refinement
2. Try a more powerful model (Claude Opus)
3. Add few-shot examples to the extraction prompt

## Integration with Existing Workflows

### After Running Pipeline

The output files can be used for:

1. **Validation**: Compare with BRIM results when it comes back online
2. **Analysis**: Import `extraction_summary_{FHIR_ID}.csv` into R/Python for analysis
3. **Quality Control**: Review `extraction_results_{FHIR_ID}.csv` to audit individual extractions
4. **Iteration**: Refine extraction instructions and re-run

### Example: Loading Results in Python

```python
import pandas as pd

# Load summary (wide format - easiest for analysis)
summary_df = pd.read_csv('extraction_summary_e4BwD8ZYDBccepXcJ.Ilo3w3.csv')

# Access extracted values
extent = summary_df.loc[0, 'extent_of_resection_adjudicated']
event_type = summary_df.loc[0, 'event_type_adjudicated']

print(f"Extent of resection: {extent}")
print(f"Event type: {event_type}")
```

### Example: Loading Results in R

```r
library(tidyverse)

# Load summary
summary_df <- read_csv('extraction_summary_e4BwD8ZYDBccepXcJ.Ilo3w3.csv')

# View results
summary_df %>%
  select(PERSON_ID, extent_of_resection_adjudicated, event_type_adjudicated) %>%
  print()
```

## Future Enhancements

Potential improvements to the pipeline:

1. **Batch Processing**: Process multiple patients in one run
2. **Parallel Execution**: Use threading for faster extraction (with rate limiting)
3. **Caching**: Cache extraction results to avoid re-processing unchanged documents
4. **Streaming**: Use Claude's streaming API for real-time progress
5. **Confidence Scores**: Extract confidence/uncertainty for each extraction
6. **Structured Output**: Use Claude's JSON mode for more reliable structured extraction
7. **Error Recovery**: Automatic retry with backoff for failed extractions

## License & Citation

This pipeline is part of the RADIANT PCA BRIM Analytics project.

If you use this pipeline in research, please cite:
- BRIM Analytics platform
- Claude API (Anthropic)
- This repository

## Support

For questions or issues:
1. Check this README
2. Review the script comments in `local_llm_extraction_pipeline.py`
3. Contact the RADIANT PCA team
