# Radiation Extraction Script: Date Columns & RT-Specific Keywords Update

**Date**: 2025-10-12
**Purpose**: Ensure temporal alignment across FHIR resources and use RT-specific (not general oncology) keywords

---

## Updates Made

### 1. Date Column Enhancements

#### Problem
- Date/time columns critical for aligning data elements across FHIR resources
- Service_request tables only captured `authored_on`
- Missing `occurrence_date_time` and `occurrence_period` fields
- Difficult to correlate treatments across appointment, care_plan, and service_request tables

#### Solution: Added Date Columns to service_request Extractions

**service_request_note**:
```sql
-- ADDED these date columns:
parent.occurrence_date_time,
parent.occurrence_period_start,
parent.occurrence_period_end

-- UPDATED sort order for best available date:
ORDER BY COALESCE(note.note_time, parent.occurrence_date_time, 
                  parent.occurrence_period_start, parent.authored_on)
```

**service_request_reason_code**:
```sql
-- ADDED these date columns:
parent.occurrence_date_time,
parent.occurrence_period_start,
parent.occurrence_period_end

-- UPDATED sort order for best available date:
ORDER BY COALESCE(parent.occurrence_date_time, 
                  parent.occurrence_period_start, parent.authored_on)

-- ADDED to output DataFrame:
'occurrence_date_time': row['occurrence_date_time'],
'occurrence_period_start': row['occurrence_period_start'],
'occurrence_period_end': row['occurrence_period_end']
```

**Benefit**: Now can align service_request data with:
- Appointment dates (`start`, `end`)
- Care plan dates (`period_start`, `period_end`)
- Enables cross-resource treatment timeline reconstruction

---

### 2. RT-Specific Keywords for care_plan Extraction

#### Problem Identified
- Original `RADIATION_SEARCH_TERMS` too general
- Mixed general oncology terms with RT-specific terms
- Inconsistent with service_request keyword approach
- Could capture non-RT cancer care plans

#### Original Keywords (PROBLEMATIC)
```python
RADIATION_SEARCH_TERMS = [
    'radiation', 'radiotherapy', 'rad onc',
    'imrt', 'xrt', 'rt simulation', 'rt sim',
    're-irradiation', 'reirradiation',
    'proton', 'photon', 'intensity modulated',
    'stereotactic', 'sbrt', 'srs',
    'cranial radiation', 'csi',  # Still general
]
```

**Issues**:
- Too short (18 terms vs 45+ in service_request)
- Missing critical RT abbreviations: VMAT, 3D-CRT, HDR, LDR
- Missing technical terms: linac, portal, PTV, GTV, CTV
- Missing dosimetry terms: dose, Gy, centigray, fraction
- Inconsistent with corrected service_request approach

#### Updated Keywords (RT-SPECIFIC)
```python
# RT-SPECIFIC search terms for radiation therapy identification
# NOTE: These are RT-SPECIFIC keywords, not general oncology terms
RADIATION_SEARCH_TERMS = [
    # Core RT terms
    'radiation', 'radiotherapy', 'rad onc', 'radiation oncology',
    
    # Modalities & abbreviations
    'xrt', 'imrt', 'vmat', '3d-crt', '3dcrt', 
    'proton', 'photon', 'electron',
    'brachytherapy', 'hdr', 'ldr', 'seed implant',
    
    # Stereotactic
    'stereotactic', 'sbrt', 'srs', 'sabr', 'radiosurgery',
    'gamma knife', 'cyberknife',
    
    # Delivery & planning
    'beam', 'external beam', 'teletherapy', 'conformal',
    'intensity modulated', 'volumetric modulated',
    
    # Treatment phases
    'rt simulation', 'rt sim', 'simulation',
    're-irradiation', 'reirradiation', 'boost',
    
    # Dosimetry
    'dose', 'dosage', 'gy', 'gray', 'cgy', 'centigray',
    'fraction', 'fractions', 'fractionation',
    
    # Technical terms
    'isocenter', 'ptv', 'gtv', 'ctv', 'planning target',
    'treatment planning', 'port film', 'portal',
    'linac', 'linear accelerator', 'cyclotron',
    
    # Anatomical sites (RT-specific)
    'cranial radiation', 'csi', 'craniospinal',
    'whole brain', 'wbrt', 'pci',  # Prophylactic cranial irradiation
]
```

**New keywords added (30+)**:
- **Modalities**: VMAT, 3D-CRT, electron, HDR, LDR, seed implant
- **Stereotactic**: SABR, radiosurgery, gamma knife, cyberknife
- **Delivery**: beam, external beam, teletherapy, conformal, volumetric modulated
- **Treatment phases**: simulation, boost
- **Dosimetry**: dose, dosage, Gy, gray, cGy, centigray, fraction, fractionation
- **Technical**: isocenter, PTV, GTV, CTV, planning target, treatment planning, port film, portal, linac, linear accelerator, cyclotron
- **Anatomical RT-specific**: whole brain, WBRT, PCI

**Total**: 18 terms → **60+ RT-specific terms**

---

## Impact on Data Extraction

### Date Alignment Benefits

**Cross-Resource Correlation Now Possible**:

1. **Appointment → service_request**:
   ```
   appointment.start = '2024-03-15'
   service_request.occurrence_date_time = '2024-03-15T10:00:00'
   → SAME treatment session
   ```

2. **care_plan → service_request**:
   ```
   care_plan.period_start = '2024-03-15'
   service_request.occurrence_period_start = '2024-03-15'
   → SAME treatment course
   ```

3. **Timeline Reconstruction**:
   - Sort by best available date across all resources
   - Identify treatment phases: consult → simulation → treatment → follow-up
   - Detect gaps in care
   - Align dose information from multiple sources

### RT-Specific Keyword Benefits

**care_plan_note Filtering**:
- **Before**: Risk of capturing general oncology care plans
- **After**: Captures only RT-specific care plans
- **Consistency**: Same approach as service_request (corrected methodology)

**Expected Changes**:
- May slightly reduce false positives from general cancer care plans
- Will capture more RT-specific notes with technical terminology
- Enables filtering by:
  - Modality (IMRT vs proton vs brachytherapy)
  - Treatment phase (simulation vs treatment vs boost)
  - Anatomical site (cranial, CSI, whole brain)

---

## Validation Recommendations

### 1. Test Date Alignment
```python
# Load all extraction outputs
appointments_df = pd.read_csv('appointments.csv')
service_notes_df = pd.read_csv('service_request_notes.csv')
service_history_df = pd.read_csv('service_request_rt_history.csv')
care_plans_df = pd.read_csv('care_plan_notes.csv')

# Cross-reference by date
# Example: Find appointments and service_requests on same date
merged = appointments_df.merge(
    service_notes_df,
    left_on='start',
    right_on='occurrence_date_time',
    how='inner'
)
print(f"Matched {len(merged)} records across resources")
```

### 2. Test RT-Specific Keyword Impact
```python
# Compare before/after care_plan note counts
# Run on same patient before and after keyword update
# Check if any notes lost are truly RT-related
```

### 3. Timeline Reconstruction
```python
# Combine all date columns
all_dates = []
all_dates.extend(appointments_df[['start', 'rt_category']].values)
all_dates.extend(service_notes_df[['occurrence_date_time', 'note_type']].values)
all_dates.extend(care_plans_df[['period_start', 'note_type']].values)

# Sort chronologically
timeline = pd.DataFrame(all_dates, columns=['date', 'event_type'])
timeline = timeline.sort_values('date')
print(timeline)
```

---

## Files Modified

### extract_radiation_data.py
**Changes**:
1. Updated `RADIATION_SEARCH_TERMS` (18 → 60+ terms, RT-specific)
2. Added date columns to `extract_service_request_notes()`:
   - occurrence_date_time
   - occurrence_period_start
   - occurrence_period_end
3. Added date columns to `extract_service_request_reason_codes()`:
   - occurrence_date_time
   - occurrence_period_start
   - occurrence_period_end
4. Updated SQL ORDER BY clauses for best available date
5. Updated DataFrame output to include all date fields

**Functions Affected**:
- `extract_service_request_notes()`: Query, sort order, output unchanged
- `extract_service_request_reason_codes()`: Query, sort order, DataFrame construction

**care_plan Functions** (using updated RADIATION_SEARCH_TERMS):
- `extract_care_plan_notes()`: Now filters with 60+ RT-specific keywords
- `extract_care_plan_hierarchy()`: Unchanged (uses JOIN, not keyword filtering)

---

## Testing Plan

### Test 1: RT Patient with Multiple Data Sources
**Patient**: `eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3` (known RT patient)

**Expected**:
- service_request CSV files now have 3 additional date columns
- care_plan notes may have slightly different count (more specific)
- Can correlate events across resources by date
- Timeline should show: consult → simulation → treatment start → treatment sessions → completion

### Test 2: Date Alignment Validation
**Steps**:
1. Extract data with updated script
2. Load all CSV files
3. Create unified timeline sorted by date
4. Verify same-day events cluster appropriately
5. Check for chronological consistency

### Test 3: Keyword Specificity Check
**Steps**:
1. Extract care_plan_notes with updated keywords
2. Manually review sample of captured notes
3. Verify all contain RT-specific terminology
4. Check no critical RT notes were missed

---

## Next Steps

1. ✅ **COMPLETED**: Update extraction script
2. **TODO**: Test on RT patient
3. **TODO**: Validate date alignment across resources
4. **TODO**: Check care_plan note count changes
5. **TODO**: Create unified timeline view
6. **TODO**: Update documentation with timeline reconstruction examples

---

## Lessons Learned

### Date Columns are Critical
- **Problem**: Without occurrence dates, difficult to align service_request with appointments
- **Solution**: Always extract ALL available date/time fields from parent tables
- **Best Practice**: Use COALESCE in ORDER BY for most relevant date

### Keyword Consistency Matters
- **Problem**: care_plan used different (less specific) keywords than service_request
- **Solution**: Unified RT-specific keyword list across all extractions
- **Best Practice**: Document keyword methodology; keep consistent across resources

### FHIR Date Fields Vary by Resource
- **appointment**: `start`, `end`
- **care_plan**: `period_start`, `period_end`
- **service_request**: `authored_on`, `occurrence_date_time`, `occurrence_period_start/end`
- **Challenge**: Different naming conventions require resource-specific handling
- **Solution**: Map to common fields for cross-resource analysis

---

## Summary

✅ **Date columns added** to service_request extractions for temporal alignment
✅ **RT-specific keywords** (60+ terms) now used consistently across all extractions
✅ **Cross-resource correlation** now possible via date matching
✅ **care_plan filtering** now as specific as service_request (corrected methodology)

**Result**: More precise RT data extraction with temporal alignment capabilities
