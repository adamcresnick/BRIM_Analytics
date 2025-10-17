# REVISED BRIM Strategy: Event-Linked Multi-Source Extraction

**Date**: 2025-10-11
**Purpose**: Address event-linkage and multi-source extraction for radiology/operative note fields

---

## Key Revisions

### 1. **Event Linkage Problem**
Current approach extracts variables per-note but doesn't explicitly link them to specific clinical events (Event 1, Event 2, etc.).

**Solution**: Add event_number as a linking variable

### 2. **Multi-Source Extraction Problem**
- `extent_of_tumor_resection` should be extracted from BOTH operative notes AND post-op imaging
- `tumor_location` may appear in multiple documents per event

**Solution**: Extract from all sources, then use decisions.csv to adjudicate

### 3. **Aggregation Problem**
Multiple tumor locations and metastasis sites need proper per-event aggregation

**Solution**: Event-scoped aggregation decisions

---

## Revised Variable Structure

### **Added Variable: event_number** (Linking Variable)

**Purpose**: Link all extracted variables to specific clinical events

**BRIM Instruction**:
```
Extract the event number from STRUCTURED_surgery_events document.
Look for "## Event N:" headers (e.g., "## Event 1:", "## Event 2:").
Return only the numeric event number.
For non-STRUCTURED documents, extract event number from NOTE_ID
(e.g., "op_note_1_2018-05-28" → return "1").
```

**Scope**: `many_per_note`

**Example Output**:
```csv
NOTE_ID,variable_name,value
STRUCTURED_surgery_events,event_number,1
STRUCTURED_surgery_events,event_number,2
op_note_1_2018-05-28,event_number,1
op_note_2_2021-03-10,event_number,2
imaging_postop_event1_2018-06-01,event_number,1
```

**Critical**: This enables grouping all variables by event

---

## Revised Multi-Source Extraction

### **extent_of_tumor_resection** (Extract from 2 sources)

#### **Variable A: extent_from_operative_note**

**BRIM Instruction**:
```
Extract extent of tumor resection from operative note (NOTE_TITLE contains "OP Note").
Look in sections: Procedure Performed, Post-operative Assessment, Surgeon Summary.
Keywords: GTR (gross total), NTR (near total), Partial, Subtotal (STR), Biopsy only.
Valid values: 1 (Gross/Near total resection), 2 (Partial resection),
3 (Biopsy only), 4 (Unavailable), 5 (N/A).
Return only the numeric code.
IMPORTANT: Extract the surgeon's intraoperative assessment.
```

**Example Operative Note**:
```
POST-OPERATIVE ASSESSMENT:
Subtotal resection achieved. Residual tumor along brainstem could not be safely removed.
Estimated 70% of tumor resected.
```

**Output**: `2` (Partial resection)

#### **Variable B: extent_from_postop_imaging**

**BRIM Instruction**:
```
Extract extent of tumor resection from post-operative imaging report.
Look for radiologist's assessment of residual tumor.
Keywords:
- GTR/Complete: "no residual enhancement", "complete resection", "no residual tumor"
- Partial: "residual tumor", "incomplete resection", "residual enhancement"
- Unavailable: no clear assessment
Valid values: 1 (Gross/Near total resection), 2 (Partial resection),
3 (Biopsy only), 4 (Unavailable), 5 (N/A).
Return only the numeric code.
IMPORTANT: Extract the radiologist's assessment 24-72 hours post-op.
Only extract from imaging within 7 days of surgery date found in STRUCTURED document.
```

**Example Post-Op Imaging**:
```
IMPRESSION:
1. Status post posterior fossa craniotomy for tumor resection
2. Residual enhancing tumor measuring 2.1 x 1.8 cm along floor of fourth ventricle
3. Decreased mass effect compared to pre-operative study
```

**Output**: `2` (Partial resection - residual tumor present)

#### **Decision: extent_of_tumor_resection_adjudicated**

**Purpose**: Adjudicate between operative note and imaging assessments

**Decision Instruction**:
```
Adjudicate extent of tumor resection using both operative note and post-operative imaging.

RULES:
1. If BOTH sources agree → return agreed value
2. If operative note says GTR/NTR BUT imaging shows residual → return imaging value (more objective)
3. If operative note says Partial BUT imaging shows no residual → return imaging value
4. If only ONE source available → return that value
5. If BOTH unavailable → return "4" (Unavailable)

Prioritize imaging assessment as it is more objective than surgeon's intraoperative impression.

Return format: "extent_value|confidence|source"
Example: "2|high|imaging_confirms_operative" or "2|medium|imaging_only"
```

**Example Decision**:
```csv
patient_fhir_id,event_number,extent_of_tumor_resection_adjudicated,confidence,primary_source
e4BwD8ZYDBccepXcJ.Ilo3w3,1,2,high,imaging_confirms_operative
e4BwD8ZYDBccepXcJ.Ilo3w3,2,2,high,imaging_confirms_operative
```

---

## Revised Event-Linked Aggregation

### **tumor_location** (Multiple per Event)

#### **Variable: tumor_location_per_document**

**BRIM Instruction**:
```
Extract ALL tumor anatomical locations mentioned in this document.
Search operative notes, pre-operative imaging, and post-operative imaging.
Return ALL locations as comma-separated numeric codes.

Valid values (can be multiple):
1=Frontal Lobe, 2=Temporal Lobe, 3=Parietal Lobe, 4=Occipital Lobe,
5=Thalamus, 6=Ventricles, 7=Suprasellar/Hypothalamic/Pituitary,
8=Cerebellum/Posterior Fossa, 9=Brain Stem-Medulla,
10=Brain Stem-Midbrain/Tectum, 11=Brain Stem-Pons,
12=Spinal Cord-Cervical, 13=Spinal Cord-Thoracic,
14=Spinal Cord-Lumbar/Thecal Sac, 15=Optic Pathway,
16=Cranial Nerves NOS, 19=Pineal Gland, 20=Basal Ganglia,
21=Hippocampus, 22=Meninges/Dura, 23=Skull, 24=Unavailable

IMPORTANT: Include ALL locations mentioned, not just primary site.
Example: "Tumor epicenter in cerebellum with extension to midbrain" → return "8,10"
```

**Example Outputs**:
```csv
NOTE_ID,event_number,variable_name,value
op_note_1_2018-05-28,1,tumor_location_per_document,8
imaging_preop_event1_2018-05-27,1,tumor_location_per_document,"8,6"
imaging_postop_event1_2018-06-01,1,tumor_location_per_document,8
op_note_2_2021-03-10,2,tumor_location_per_document,"8,10,2"
```

#### **Decision: tumor_location_by_event**

**Purpose**: Aggregate all tumor locations for each event

**Decision Instruction**:
```
For each event (event_number), combine ALL unique tumor locations mentioned across:
- Pre-operative imaging for that event
- Operative note for that event
- Post-operative imaging for that event

Remove duplicates and return comma-separated numeric codes sorted ascending.

RULES:
1. Combine locations from all sources for the same event
2. Remove duplicate codes
3. Sort numerically ascending
4. Return as comma-separated string

Example: If event 1 has:
- Preop imaging: "8,6"
- Op note: "8"
- Postop imaging: "8"
→ Return: "6,8"
```

**Example Output**:
```csv
patient_fhir_id,event_number,tumor_location_by_event
e4BwD8ZYDBccepXcJ.Ilo3w3,1,"6,8"
e4BwD8ZYDBccepXcJ.Ilo3w3,2,"2,8,10"
```

**Interpretation**:
- Event 1: Ventricles (6) + Cerebellum/Posterior Fossa (8)
- Event 2: Temporal Lobe (2) + Cerebellum (8) + Midbrain/Tectum (10)

---

## Revised project.csv Structure with Event Linkage

### **NOTE_ID Naming Convention**

To enable automatic event_number extraction, use consistent naming:

| Document Type | NOTE_ID Format | Example |
|---------------|----------------|---------|
| STRUCTURED surgery events | `STRUCTURED_surgery_events` | `STRUCTURED_surgery_events` |
| STRUCTURED imaging | `STRUCTURED_imaging` | `STRUCTURED_imaging` |
| Operative note | `op_note_{event_num}_{date}` | `op_note_1_2018-05-28` |
| Pre-op imaging | `imaging_preop_event{num}_{date}` | `imaging_preop_event1_2018-05-27` |
| Post-op imaging | `imaging_postop_event{num}_{date}` | `imaging_postop_event1_2018-06-01` |
| Surveillance imaging | `imaging_surveillance_event{num}_{date}` | `imaging_surveillance_event2_2019-08-15` |

**Key**: Event number embedded in NOTE_ID enables linking

---

## Revised variables.csv (13 variables)

### **Category A: Event Metadata** (5 variables)
1. `event_number` - Link to specific clinical event
2. `event_type` - 5/6/7/8/9/10
3. `age_at_event_days` - Numeric days
4. `surgery` - 1/2/3
5. `age_at_surgery` - Numeric days

### **Category B: Operative Note Extraction** (1 variable)
6. `extent_from_operative_note` - 1/2/3/4/5

### **Category C: Imaging Extraction** (5 variables)
7. `extent_from_postop_imaging` - 1/2/3/4/5
8. `tumor_location_per_document` - Comma-separated codes
9. `metastasis` - 0/1/2
10. `metastasis_location` - Comma-separated codes
11. `site_of_progression` - 1/2/3 (conditional)

### **Category D: Cross-Document Variables** (2 variables - from decisions.csv)
12. `extent_of_tumor_resection_adjudicated` - Final extent per event
13. `tumor_location_by_event` - All locations per event

---

## Revised decisions.csv (6 decisions)

### **Decision 1: extent_of_tumor_resection_adjudicated**

**Variables**: `["event_number", "extent_from_operative_note", "extent_from_postop_imaging"]`

**Instruction**:
```
For each event_number, adjudicate extent of tumor resection.
If operative note and imaging agree → return value with confidence=high
If they disagree → prioritize imaging (more objective) with confidence=medium
If only one source → return that value with confidence=low
Return format: numeric_code (1-5)
```

### **Decision 2: tumor_location_by_event**

**Variables**: `["event_number", "tumor_location_per_document"]`

**Instruction**:
```
For each event_number, combine all unique tumor locations from all documents.
Remove duplicates, sort ascending, return comma-separated.
```

### **Decision 3: metastasis_location_by_event**

**Variables**: `["event_number", "metastasis", "metastasis_location"]`

**Instruction**:
```
For each event_number where metastasis=0, combine all unique metastasis locations.
If metastasis=1 (No), return empty.
```

### **Decision 4: event_sequence**

**Variables**: `["event_number", "event_type", "age_at_event_days", "surgery"]`

**Instruction**:
```
Create chronological timeline of all clinical events sorted by age_at_event_days.
Return format: "Event N: type=X, age=Y, surgery=Z" separated by semicolons
```

### **Decision 5: extent_progression_analysis**

**Variables**: `["event_number", "extent_of_tumor_resection_adjudicated", "event_type"]`

**Instruction**:
```
Analyze extent of resection across events to validate event_type classification.
If event N has GTR/NTR and event N+1 has tumor → should be Recurrence (7)
If event N has Partial and event N+1 has tumor → should be Progressive (8)
Flag any inconsistencies.
```

### **Decision 6: site_of_progression_by_event**

**Variables**: `["event_number", "event_type", "tumor_location_by_event"]`

**Instruction**:
```
For Progressive events (event_type=8), determine if progression is:
- Local (1): Tumor locations overlap with previous event
- Metastatic (2): New locations not present in previous event
Compare tumor_location_by_event across sequential events.
```

---

## Example Expected Output

### **Variable-Level Output**

```csv
NOTE_ID,event_number,variable_name,value
STRUCTURED_surgery_events,1,event_type,5
STRUCTURED_surgery_events,1,age_at_event_days,4763
STRUCTURED_surgery_events,1,surgery,1
op_note_1_2018-05-28,1,event_number,1
op_note_1_2018-05-28,1,extent_from_operative_note,2
op_note_1_2018-05-28,1,tumor_location_per_document,8
imaging_postop_event1_2018-06-01,1,event_number,1
imaging_postop_event1_2018-06-01,1,extent_from_postop_imaging,2
imaging_postop_event1_2018-06-01,1,tumor_location_per_document,"6,8"
STRUCTURED_surgery_events,2,event_type,8
STRUCTURED_surgery_events,2,age_at_event_days,5780
STRUCTURED_surgery_events,2,surgery,1
op_note_2_2021-03-10,2,event_number,2
op_note_2_2021-03-10,2,extent_from_operative_note,2
op_note_2_2021-03-10,2,tumor_location_per_document,"8,10,2"
imaging_postop_event2_2021-03-17,2,event_number,2
imaging_postop_event2_2021-03-17,2,extent_from_postop_imaging,2
imaging_postop_event2_2021-03-17,2,tumor_location_per_document,"8,10"
```

### **Decision-Level Output**

```csv
patient_fhir_id,event_number,decision_name,value
e4BwD8ZYDBccepXcJ.Ilo3w3,1,extent_of_tumor_resection_adjudicated,2
e4BwD8ZYDBccepXcJ.Ilo3w3,1,tumor_location_by_event,"6,8"
e4BwD8ZYDBccepXcJ.Ilo3w3,2,extent_of_tumor_resection_adjudicated,2
e4BwD8ZYDBccepXcJ.Ilo3w3,2,tumor_location_by_event,"2,8,10"
e4BwD8ZYDBccepXcJ.Ilo3w3,2,site_of_progression_by_event,1
e4BwD8ZYDBccepXcJ.Ilo3w3,,event_sequence,"Event 1: type=5, age=4763, surgery=1; Event 2: type=8, age=5780, surgery=1"
```

---

## Implementation Changes Required

### **1. Update create_structured_surgery_events.py**

Add event number explicitly to STRUCTURED document:

```markdown
## Event 1: Initial CNS Tumor (age 4763 days)

**Event Number**: 1
**Event Type**: 5 (Initial CNS Tumor)
...
```

### **2. Update generate_radiology_opnote_brim_csvs.py**

**Change NOTE_ID naming**:
```python
# Old
row = {
    'NOTE_ID': f"op_note_{idx+1}_{surgery['surgery_date']}",
    ...
}

# New - explicitly include event number
row = {
    'NOTE_ID': f"op_note_{event_num}_{surgery['surgery_date']}",
    ...
}
```

**Add imaging reports with event linkage**:
```python
# For each surgery event, fetch:
# 1. Pre-op imaging (within 30 days before)
# 2. Post-op imaging (within 7 days after)
# 3. Surveillance imaging (categorized by event)

for idx, surgery in self.surgery_df.iterrows():
    event_num = idx + 1
    surgery_date = pd.to_datetime(surgery['surgery_date'])

    # Pre-op imaging
    preop_window = (surgery_date - timedelta(days=30), surgery_date)
    preop_imaging = self.imaging_df[
        (self.imaging_df['imaging_date'] >= preop_window[0]) &
        (self.imaging_df['imaging_date'] < preop_window[1])
    ]

    for img_idx, img in preop_imaging.iterrows():
        note_id = f"imaging_preop_event{event_num}_{img['imaging_date']}"
        # Fetch and add to project_rows

    # Post-op imaging
    postop_window = (surgery_date, surgery_date + timedelta(days=7))
    # ... similar logic
```

### **3. Update variables.csv generation**

Add the new variables and update instructions to reference event_number

### **4. Update decisions.csv generation**

Add the new adjudication and aggregation decisions

---

## Validation Strategy

### **Event Linkage Validation**

```python
def validate_event_linkage(brim_output):
    """Ensure all variables are properly linked to events"""

    # Check 1: All documents have event_number
    missing_event_num = brim_output[
        brim_output['event_number'].isna()
    ]
    assert len(missing_event_num) == 0, "All documents must have event_number"

    # Check 2: Event numbers are consistent per NOTE_ID
    for note_id in brim_output['NOTE_ID'].unique():
        event_nums = brim_output[
            brim_output['NOTE_ID'] == note_id
        ]['event_number'].unique()
        assert len(event_nums) == 1, f"{note_id} has multiple event numbers"

    # Check 3: Each event has expected documents
    for event_num in brim_output['event_number'].unique():
        event_docs = brim_output[
            brim_output['event_number'] == event_num
        ]['NOTE_ID'].unique()

        # Should have at least: STRUCTURED + op_note
        assert any('STRUCTURED' in doc for doc in event_docs)
        assert any('op_note' in doc for doc in event_docs)
```

### **Multi-Source Adjudication Validation**

```python
def validate_extent_adjudication(brim_output, decisions_output):
    """Validate extent adjudication logic"""

    for event_num in brim_output['event_number'].unique():
        # Get both sources
        op_note_extent = brim_output[
            (brim_output['event_number'] == event_num) &
            (brim_output['variable_name'] == 'extent_from_operative_note')
        ]['value'].values[0]

        imaging_extent = brim_output[
            (brim_output['event_number'] == event_num) &
            (brim_output['variable_name'] == 'extent_from_postop_imaging')
        ]['value'].values

        adjudicated_extent = decisions_output[
            (decisions_output['event_number'] == event_num) &
            (decisions_output['decision_name'] == 'extent_of_tumor_resection_adjudicated')
        ]['value'].values[0]

        # Validate adjudication logic
        if len(imaging_extent) > 0:
            # If imaging available, should match imaging (prioritized)
            assert adjudicated_extent == imaging_extent[0]
        else:
            # Otherwise should match op note
            assert adjudicated_extent == op_note_extent
```

---

## Summary of Key Changes

1. ✅ **Event linkage**: All variables tied to event_number
2. ✅ **Multi-source extraction**: extent from both op notes AND imaging
3. ✅ **Adjudication decision**: extent_of_tumor_resection_adjudicated combines sources
4. ✅ **Per-event aggregation**: tumor_location_by_event combines all mentions
5. ✅ **Consistent NOTE_ID naming**: Embeds event number for automatic linking
6. ✅ **Validation**: Cross-checks ensure proper linkage and adjudication

**Next Steps**:
1. Update scripts with new NOTE_ID conventions
2. Add event_number variable
3. Split extent into two extraction variables
4. Add adjudication decisions
5. Test on patient e4BwD8ZYDBccepXcJ.Ilo3w3
