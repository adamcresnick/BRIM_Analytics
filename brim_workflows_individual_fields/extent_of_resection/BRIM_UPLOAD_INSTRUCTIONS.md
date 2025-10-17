# BRIM Upload Instructions - Patient e4BwD8ZYDBccepXcJ.Ilo3w3

**Generated**: 2025-10-11
**Patient**: e4BwD8ZYDBccepXcJ.Ilo3w3 (MRN: C1277724)

---

## Files to Upload to BRIM

Upload these 3 CSV files to the BRIM platform:

### 1. project_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/brim_workflows_individual_fields/extent_of_resection/staging_files/e4BwD8ZYDBccepXcJ.Ilo3w3/project_e4BwD8ZYDBccepXcJ.Ilo3w3.csv`

**Contents**:
- 1 document (STRUCTURED_surgery_events)
- Contains algorithmically-generated surgery event timeline
- Includes event type classification based on temporal logic

**NOTE**: Operative notes were not available in S3, so only the STRUCTURED document is included. BRIM will extract what it can from this synthetic document.

### 2. variables_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/brim_workflows_individual_fields/extent_of_resection/staging_files/e4BwD8ZYDBccepXcJ.Ilo3w3/variables_e4BwD8ZYDBccepXcJ.Ilo3w3.csv`

**Contents**: 13 variables
1. event_number (linking variable)
2. event_type_structured (temporal baseline)
3. age_at_event_days
4. surgery
5. age_at_surgery
6. progression_recurrence_indicator_operative_note (clinical validation)
7. progression_recurrence_indicator_imaging (clinical validation)
8. extent_from_operative_note
9. extent_from_postop_imaging
10. tumor_location_per_document
11. metastasis
12. metastasis_location
13. site_of_progression

**All variables return TEXT labels** (not numeric codes)

### 3. decisions_e4BwD8ZYDBccepXcJ.Ilo3w3.csv
**Location**: `/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/brim_workflows_individual_fields/extent_of_resection/staging_files/e4BwD8ZYDBccepXcJ.Ilo3w3/decisions_e4BwD8ZYDBccepXcJ.Ilo3w3.csv`

**Contents**: 10 decisions
1. **event_type_adjudicated** - Adjudicates temporal baseline vs clinical evidence
2. **extent_of_tumor_resection_adjudicated** - Adjudicates op note vs imaging
3. tumor_location_by_event - Per-event aggregation
4. metastasis_location_by_event - Per-event aggregation
5. event_sequence - Chronological timeline
6. total_surgical_events - Count
7. progression_vs_recurrence_count - Categorization
8. **extent_progression_validation** - Validation check
9. site_of_progression_by_event - Per-event determination
10. metastatic_disease_summary - Overall summary

---

## Patient Summary

### Surgeries Identified
- **Event 1** (2018-05-28): CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION
- **Event 2** (2018-05-28): ENDOSCOPIC THIRD VENTRICULOSTOMY

**Note**: Both surgeries occurred on the same date. Event 1 is classified as "Initial CNS Tumor", Event 2 as "Progressive" (default).

### Documents Available
- STRUCTURED document: ✓ Generated
- Operative notes: ✗ Not available in S3
- Imaging reports: ✗ No imaging timeline available

---

## What BRIM Will Extract

### From STRUCTURED Document Only:

**Automated Fields (100% accuracy expected):**
- event_number: 1, 2
- event_type_structured: "Initial CNS Tumor", "Progressive"
- age_at_event_days: 0, 0 (NOTE: Age calculation failed - both show 0)
- surgery: "Yes", "Yes"
- age_at_surgery: 0, 0

**LLM Extraction Fields (limited extraction from STRUCTURED doc):**
- progression_recurrence_indicator_operative_note: "Unavailable" (no op notes)
- progression_recurrence_indicator_imaging: "Unavailable" (no imaging)
- extent_from_operative_note: "Unavailable" (no op notes)
- extent_from_postop_imaging: "Unavailable" (no imaging)
- tumor_location_per_document: May extract "Cerebellum/Posterior Fossa" from STRUCTURED doc text
- metastasis: "Unavailable"
- site_of_progression: "Unavailable"

### Adjudication Results Expected:

**event_type_adjudicated:**
- Since no clinical notes available, will use event_type_structured
- Expected: "Event 1: Initial CNS Tumor | Event 2: Progressive"

**extent_of_tumor_resection_adjudicated:**
- No operative notes or imaging available
- Expected: "Unavailable" for both events

---

## Known Issues

### 1. Age Calculation Error
Both events show age = 0 days instead of actual ages. This needs investigation in the `create_structured_surgery_events.py` script.

**Root cause**: `age_at_procedure_days` field is likely NaN or missing in the procedures CSV.

**Impact**: Age-based variables will be incorrect.

### 2. Missing Operative Notes
The operative notes are linked in the metadata but marked as "S3 Available: No". This means:
- No extent of resection extraction possible
- No clinical validation of progression/recurrence possible
- Limited tumor location extraction

**Document IDs**:
- fCI9ykSUqvPIb6HYPRpYtMuXym7Dx3v7ae-pJQsf.Elc4 (both surgeries linked to same note)

### 3. No Imaging Timeline
No imaging data was available for this patient in the staging files.

**Impact**:
- No post-op imaging extent validation
- No progression/recurrence indicators from imaging
- No metastasis detection

---

## Testing Goals

Despite limited data availability, this upload will test:

### ✓ Successfully Testable:
1. **Text output format** - Verify BRIM accepts text labels vs numeric codes
2. **event_number extraction** - From STRUCTURED document "Event N:" headers
3. **event_type_structured extraction** - From STRUCTURED document
4. **Event linkage** - Verify grouping by event_number works
5. **Adjudication logic** - event_type_adjudicated should fall back to event_type_structured
6. **Decision execution** - All 10 decisions should run (even if returning "Unavailable")

### ⚠️ Limited Testing:
1. **Clinical validation workflow** - No clinical notes to validate against
2. **Multi-source adjudication** - No imaging to compare with op notes
3. **Extent extraction** - No operative notes available
4. **Per-event aggregation** - Limited data per event

---

## Expected BRIM Output

### Variables Table (predicted):

| NOTE_ID | event_number | event_type_structured | age_at_event_days | surgery | extent_from_operative_note | tumor_location_per_document |
|---------|-------------|----------------------|------------------|---------|---------------------------|----------------------------|
| STRUCTURED_surgery_events | 1 | Initial CNS Tumor | 0 | Yes | Unavailable | Cerebellum/Posterior Fossa |
| STRUCTURED_surgery_events | 2 | Progressive | 0 | Yes | Unavailable | Unavailable |

### Decisions Table (predicted):

| Decision | Value |
|----------|-------|
| event_type_adjudicated | Event 1: Initial CNS Tumor (temporal: Initial, clinical: Unavailable) \| Event 2: Progressive (temporal: Progressive, clinical: Unavailable) |
| extent_of_tumor_resection_adjudicated | Event 1: Unavailable \| Event 2: Unavailable |
| tumor_location_by_event | Event 1: Cerebellum/Posterior Fossa \| Event 2: Unavailable |
| event_sequence | Event 1: event_type=Initial CNS Tumor, age=0 days, surgery=Yes \| Event 2: event_type=Progressive, age=0 days, surgery=Yes |
| total_surgical_events | 2 |
| progression_vs_recurrence_count | Recurrence: 0, Progressive: 1 |

---

## Next Steps After Upload

1. **Upload the 3 CSV files to BRIM**
2. **Run BRIM extraction job**
3. **Download results**
4. **Share with me for evaluation**:
   - Variables output CSV
   - Decisions output CSV
   - Any error logs

5. **Focus evaluation on**:
   - Text format acceptance
   - event_number linking working
   - Adjudication logic executing
   - Decision dependencies resolving

6. **Fix for next iteration**:
   - Age calculation issue
   - Operative note S3 availability
   - Add imaging timeline

---

## Alternative: Use Pilot Data

If you want more robust testing with actual operative notes and imaging, consider using the pilot data from:

`/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/pilot_output/brim_csvs_iteration_3c_phase3a_v2/`

This would give BRIM actual clinical notes to extract from, enabling full testing of:
- Multi-source extent adjudication
- Clinical progression/recurrence indicators
- Tumor location extraction
- Per-event aggregation with multiple documents

---

**Questions or issues? Share the BRIM output and I'll help debug!**
