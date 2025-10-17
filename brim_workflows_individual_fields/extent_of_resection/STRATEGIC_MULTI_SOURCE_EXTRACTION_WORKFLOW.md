# Strategic Multi-Source Extraction Workflow for RADIANT PCA

## Executive Summary
The current BRIM extraction missed critical surgical events because it only accessed a limited subset of available data. Athena contains 85 operative reports across 6 surgical dates, but BRIM only processed 2 from one date. This proposal outlines a strategic agent-driven workflow that leverages both structured and unstructured data from multiple sources.

## Key Findings from Analysis

### Data Availability Issues
1. **BRIM Dataset**: Only 2 operative notes from 2018-05-28 (both identical)
2. **Athena Binary Files**: 85 operative documents across 6 surgery dates:
   - 2018-05-29: 20 documents
   - 2018-06-04: 1 document
   - 2021-03-10: 12 documents (MISSING IN BRIM)
   - 2021-03-15: 8 documents (MISSING IN BRIM)
   - 2021-03-16: 24 documents (MISSING IN BRIM)
   - 2021-03-19: 12 documents (MISSING IN BRIM)

### Data Source Distribution

| Data Type | Athena Structured | Athena Unstructured | Binary/Notes |
|-----------|-------------------|---------------------|--------------|
| Procedures | ✓ (72 records) | - | ✓ (85 op notes) |
| Diagnoses | ✓ (structured) | - | ✓ (in progress notes) |
| Measurements | ✓ (structured) | - | ✓ (embedded in notes) |
| Imaging | - | ✓ (result text) | ✓ (full reports) |
| Medications | ✓ (structured) | - | ✓ (in notes) |
| Progress Notes | - | - | ✓ (7,668 notes) |

## Proposed Strategic Workflow

### Phase 1: Structured Data Harvesting
**Goal**: Extract all directly available structured features from Athena

```python
class StructuredDataExtractor:
    def extract_surgical_events(self):
        # 1. Query procedures table for surgical keywords
        surgical_procs = procedures_df[procedures_df['is_surgical_keyword'] == True]

        # 2. Extract surgery dates and types
        surgery_timeline = surgical_procs.groupby('performed_date_time').agg({
            'code_text': 'first',
            'outcome_text': 'first',
            'encounter_reference': 'first'
        })

        # 3. Map to data dictionary codes
        return map_to_radiant_codes(surgery_timeline)

    def extract_measurements(self):
        # Extract tumor measurements, lab values, etc.
        return measurements_df[measurements_df['measurement_type'].isin(TARGET_MEASUREMENTS)]
```

### Phase 2: Event Timeline Construction
**Goal**: Build a comprehensive timeline of clinical events

```python
class ClinicalTimelineBuilder:
    def build_timeline(self):
        events = []

        # 1. Surgical events from procedures + binary operative notes
        surgical_events = self.identify_all_surgeries()

        # 2. Progression events from imaging
        progression_events = self.identify_progression_from_imaging()

        # 3. Treatment events from medications/radiation
        treatment_events = self.identify_treatments()

        # 4. Merge and deduplicate
        return self.merge_events(surgical_events, progression_events, treatment_events)

    def identify_all_surgeries(self):
        # Cross-reference procedures table with binary operative notes
        op_notes = binary_df[binary_df['document_type'].contains('OP Note')]
        procedures = procedures_df[procedures_df['is_surgical_keyword']]

        # Match by date and encounter
        return self.match_procedures_to_notes(procedures, op_notes)
```

### Phase 3: Intelligent Binary Selection
**Goal**: Select only necessary binary files for extraction

```python
class IntelligentBinarySelector:
    def select_binaries_for_extraction(self, timeline, required_features):
        selected_binaries = []

        for event in timeline:
            if event.type == 'surgery':
                # Get operative note for extent of resection
                op_note = self.get_operative_note(event.date, event.encounter_id)
                selected_binaries.append(op_note)

                # Get post-op imaging for validation
                post_op_imaging = self.get_post_op_imaging(event.date)
                selected_binaries.extend(post_op_imaging)

            elif event.type == 'progression':
                # Get relevant progress notes and imaging
                relevant_notes = self.get_progression_documentation(event)
                selected_binaries.extend(relevant_notes)

        return selected_binaries
```

### Phase 4: Contextual BRIM Extraction
**Goal**: Extract unstructured features with structured context

```python
class ContextualBRIMExtractor:
    def __init__(self, structured_data, timeline):
        self.structured_data = structured_data
        self.timeline = timeline

    def extract_with_context(self, binary_file, target_variable):
        # 1. Get event context
        event = self.timeline.get_event_for_document(binary_file)

        # 2. Create contextualized prompt
        prompt = f"""
        Patient Context:
        - Event Date: {event.date}
        - Event Type: {event.type}
        - Previous Surgery: {event.previous_surgery}
        - Known Measurements: {self.structured_data.get_measurements(event.date)}

        Extract: {target_variable}
        From Document: {binary_file.content}
        """

        # 3. Extract with LLM
        return self.llm_extract(prompt)
```

### Phase 5: Cross-Source Validation
**Goal**: Validate extracted data across sources

```python
class CrossSourceValidator:
    def validate_extraction(self, extracted_data):
        validations = []

        # 1. Validate surgery dates against procedures table
        surgery_validation = self.validate_surgeries(
            extracted_data.surgeries,
            self.structured_data.procedures
        )

        # 2. Validate progression against imaging timeline
        progression_validation = self.validate_progression(
            extracted_data.progression_events,
            self.imaging_timeline
        )

        # 3. Check for consistency across redundant sources
        consistency_check = self.check_redundancy_consistency(extracted_data)

        return ValidationReport(surgery_validation, progression_validation, consistency_check)
```

## Implementation Strategy

### Stage 1: Data Aggregation Pipeline
1. Create unified patient data model combining all Athena sources
2. Build comprehensive event timeline from structured data
3. Map all binary files to their clinical context

### Stage 2: Intelligent Extraction
1. Use structured data to pre-populate known values
2. Select minimal set of binary files needed for remaining features
3. Extract with contextual prompts including known information

### Stage 3: Validation & Reconciliation
1. Cross-validate extracted values against structured sources
2. Resolve conflicts using confidence scoring
3. Flag discrepancies for manual review

## Specific Improvements for This Patient

### Immediate Actions:
1. **Retrieve Missing Operative Reports**: Extract the 83 missing operative reports from Athena binary files
2. **Build Complete Surgical Timeline**:
   - 2018-05-28: Initial surgery (partial resection + ETV)
   - 2021-03-10-19: Progressive surgeries (4 separate events)
3. **Link Imaging to Events**: Map each imaging study to its clinical context
4. **Extract Event-Specific Variables**: Calculate extent of resection for each surgery

### Workflow Benefits:
- **Completeness**: Access all 85 operative reports vs just 2
- **Accuracy**: Cross-validate across multiple sources
- **Efficiency**: Only extract from necessary binaries
- **Context**: Use structured data to inform extraction

## Agent-Driven Process

```python
class MultiSourceExtractionAgent:
    """
    Autonomous agent for coordinating multi-source extraction
    """

    def execute_extraction(self, patient_id):
        # Phase 1: Aggregate all available data
        self.log("Loading Athena staging files...")
        athena_data = self.load_athena_data(patient_id)

        # Phase 2: Build clinical timeline
        self.log("Constructing clinical event timeline...")
        timeline = self.build_timeline(athena_data)

        # Phase 3: Extract structured features
        self.log("Extracting structured features...")
        structured_features = self.extract_structured(athena_data)

        # Phase 4: Identify extraction gaps
        self.log("Identifying data gaps...")
        gaps = self.identify_gaps(structured_features, REQUIRED_FEATURES)

        # Phase 5: Select binaries for gap filling
        self.log("Selecting binary files for extraction...")
        selected_binaries = self.select_binaries(gaps, timeline, athena_data.binary_files)

        # Phase 6: Contextual extraction
        self.log(f"Extracting from {len(selected_binaries)} binary files...")
        unstructured_features = self.extract_unstructured(selected_binaries, gaps, timeline)

        # Phase 7: Merge and validate
        self.log("Merging and validating results...")
        final_data = self.merge_validate(structured_features, unstructured_features)

        # Phase 8: Generate event-based output
        self.log("Generating event-based data dictionary...")
        return self.format_output(final_data, timeline)
```

## Expected Outcomes

1. **Complete Surgical History**: All 6 surgical dates with proper event classification
2. **Accurate Progression Timeline**: Validated against imaging and clinical notes
3. **Reduced Extraction Load**: Only process necessary binaries (est. 100 vs 22,000)
4. **Higher Quality Data**: Cross-validated across multiple sources
5. **Event-Level Granularity**: Separate records for each clinical event

## Next Steps

1. Implement data aggregation pipeline for Athena sources
2. Develop event timeline construction algorithm
3. Create intelligent binary selection logic
4. Modify BRIM extraction to accept contextual prompts
5. Build cross-source validation framework
6. Test on patient e4BwD8ZYDBccepXcJ.Ilo3w3
7. Generalize to full patient cohort

## Conclusion

This strategic workflow addresses the fundamental limitation of the current approach: incomplete data access. By leveraging the full breadth of available data in Athena and using intelligent selection and contextual extraction, we can achieve more complete and accurate results while reducing computational load.