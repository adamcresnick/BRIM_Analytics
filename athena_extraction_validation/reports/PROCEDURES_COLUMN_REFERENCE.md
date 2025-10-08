# Procedures Column Reference Guide

Complete reference for all 34 columns in `ALL_PROCEDURES_METADATA_C1277724.csv`

## Quick Reference Table

| # | Column Name | Type | Coverage | Primary Use |
|---|-------------|------|----------|-------------|
| 1 | procedure_fhir_id | ID | 100% | Resource linkage |
| 2 | status | String | 100% | Completion status |
| 3 | performed_date_time | DateTime | 11% | Single datetime (sparse) |
| 4 | performed_period_start | DateTime | 11% | Period start (preferred) |
| 5 | performed_period_end | DateTime | 11% | Period end |
| 6 | performed_string | String | Low | Free-text timing |
| 7 | performed_age_value | Float | Low | Age at procedure |
| 8 | performed_age_unit | String | Low | Age unit |
| 9 | code_text | String | 100% | Procedure name |
| 10 | category_text | String | 100% | Category (human-readable) |
| 11 | subject_reference | ID | 100% | Patient FHIR ID |
| 12 | encounter_reference | ID | 50% | Link to encounter |
| 13 | encounter_display | String | 50% | Encounter description |
| 14 | location_reference | ID | Unknown | Location FHIR ID |
| 15 | location_display | String | Unknown | Location name |
| 16 | outcome_text | String | Low | Procedure outcome |
| 17 | recorder_reference | ID | Unknown | Who recorded |
| 18 | recorder_display | String | Unknown | Recorder name |
| 19 | asserter_reference | ID | Unknown | Who asserted |
| 20 | asserter_display | String | Unknown | Asserter name |
| 21 | status_reason_text | String | Low | Why not done |
| 22 | procedure_date | Date | 11% | Derived date |
| 23 | age_at_procedure_days | Integer | 11% | Calculated age |
| 24 | code_coding_system | URI | 98.6% | Code system |
| 25 | code_coding_code | String | 98.6% | CPT/HCPCS code |
| 26 | code_coding_display | String | 98.6% | Code description |
| 27 | is_surgical_keyword | Boolean | 100% | Surgical flag |
| 28 | category_coding_display | String | 100% | Structured category |
| 29 | body_site_text | String | 8.3% | Anatomical location |
| 30 | performer_actor_display | String | 30.6% | Provider name(s) |
| 31 | performer_function_text | String | 30.6% | Provider role(s) |
| 32 | reason_code_text | String | 83.3% | Why performed |
| 33 | report_reference | ID | 50% | Operative report ID(s) |
| 34 | report_display | String | 50% | Report title(s) |

## Detailed Column Descriptions

### Identity & Linkage Columns

#### 1. procedure_fhir_id
- **Type**: String (FHIR resource ID)
- **Coverage**: 100% (72/72)
- **Format**: Alphanumeric ID (e.g., `fSUOuC2zGppXw6ft5yRFL6idtK2kZjjV6DoTHxFsq87w4`)
- **Usage**: PRIMARY KEY for linking to other FHIR resources
- **Example**: Use to link to encounters, diagnostic reports, operative notes
- **Note**: Different from CPT procedure codes

#### 11. subject_reference
- **Type**: String (FHIR reference)
- **Coverage**: 100% (always same patient)
- **Format**: Patient FHIR ID (`e4BwD8ZYDBccepXcJ.Ilo3w3`)
- **Usage**: Verify all procedures belong to target patient
- **Filter**: Should always equal patient FHIR ID

#### 12. encounter_reference
- **Type**: String (FHIR reference)
- **Coverage**: 50% (36/72)
- **Format**: Encounter FHIR ID
- **Usage**: **CRITICAL** - Link to encounters to get dates for undated procedures
- **Merge Strategy**:
  ```python
  merged = procedures.merge(
      encounters[['encounter_fhir_id', 'encounter_date']],
      left_on='encounter_reference',
      right_on='encounter_fhir_id',
      how='left'
  )
  ```

### Status & Timing Columns

#### 2. status
- **Type**: String (FHIR status code)
- **Coverage**: 100%
- **Values**: All 72 are "completed"
- **FHIR Values**: completed | in-progress | not-done | on-hold | stopped | unknown | entered-in-error
- **Usage**: Filter for completed procedures only
- **Note**: No cancelled or not-done procedures in this dataset

#### 3. performed_date_time
- **Type**: DateTime (ISO 8601)
- **Coverage**: 11% (8/72) ⚠️ SPARSE
- **Format**: `YYYY-MM-DDTHH:MM:SSZ`
- **Usage**: Single datetime for procedure
- **Note**: **DO NOT RELY ON THIS FIELD** - Use performed_period_start instead

#### 4. performed_period_start ⭐ PREFERRED
- **Type**: DateTime (ISO 8601)
- **Coverage**: 11% (8/72) ⚠️ SPARSE BUT MORE RELIABLE
- **Format**: `YYYY-MM-DDTHH:MM:SSZ`
- **Usage**: **PRIMARY DATETIME FIELD** - Start of procedure period
- **Date Range**: 2018-05-28 to 2021-03-16
- **Strategy**: Use this field, then fallback to encounter_reference linkage

#### 5. performed_period_end
- **Type**: DateTime (ISO 8601)
- **Coverage**: 11% (8/72)
- **Format**: `YYYY-MM-DDTHH:MM:SSZ`
- **Usage**: End of procedure period (useful for calculating duration)
- **Example**: Surgery duration = period_end - period_start

#### 22. procedure_date
- **Type**: Date (YYYY-MM-DD)
- **Coverage**: 11%
- **Derivation**: Extracted from `performed_period_start` (date only, no time)
- **Usage**: Simplified date for timeline creation

#### 23. age_at_procedure_days
- **Type**: Integer (days)
- **Coverage**: 11% (only calculated for dated procedures)
- **Calculation**: `procedure_date - birth_date (2005-05-13)`
- **Usage**: Age calculations, developmental milestones
- **Example**: `4749 days = 13.0 years`

### Procedure Description Columns

#### 9. code_text
- **Type**: String (human-readable)
- **Coverage**: 100%
- **Format**: Free text from main procedure table
- **Usage**: Quick procedure identification
- **Example**: `"STRTCTC CPTR ASSTD PX CRANIAL INTRADURAL"`
- **Note**: Less structured than code_coding_display

#### 10. category_text
- **Type**: String (human-readable)
- **Coverage**: 100%
- **Format**: Free text category
- **Usage**: Informal categorization
- **Note**: Use `category_coding_display` for reliable filtering

### Structured Code Columns ⭐ CRITICAL FOR FILTERING

#### 24. code_coding_system
- **Type**: URI (code system identifier)
- **Coverage**: 98.6% (71/72)
- **Values**:
  - `http://www.ama-assn.org/go/cpt` (58/72, 81%) - CPT codes
  - `urn:oid:1.2.840.114350.1.13.20.2.7.2.696580` (13/72, 18%) - Epic internal
  - `http://loinc.org` (1/72, 1%) - LOINC codes
- **Usage**: Identify code type for interpretation

#### 25. code_coding_code
- **Type**: String (alphanumeric code)
- **Coverage**: 98.6%
- **Format**: CPT/HCPCS code (e.g., `90471`, `93303`)
- **Usage**: Precise procedure identification, billing
- **Example**: Multiple codes separated by ` | ` if procedure has multiple codes

#### 26. code_coding_display ⭐ PRIMARY DESCRIPTOR
- **Type**: String (structured description)
- **Coverage**: 98.6% (71/72)
- **Format**: Standardized code description
- **Usage**: **PRIMARY FIELD** for identifying procedure types
- **Examples**:
  - `"CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION"`
  - `"ANES PERFORM INJ ANESTHETIC AGENT FEMORAL NERVE SINGLE"`
  - `"IMMUNIZ,ADMIN,EACH ADDL"`
- **Multi-value Format**: Separated by ` | ` if multiple codes

#### 27. is_surgical_keyword ⭐ SURGICAL FLAG
- **Type**: Boolean (True/False)
- **Coverage**: 100% (calculated field)
- **Calculation**: Searches `code_coding_display` for keywords:
  - craniotomy, craniectomy, resection, excision, biopsy
  - surgery, surgical, anesthesia, anes, oper
- **Values**: 
  - `True`: 11/72 (15%) - Contains surgical keyword
  - `False` or `NaN`: 61/72 (85%) - No surgical keywords
- **Usage**: Quick surgical procedure filter
- **Note**: Includes anesthesia procedures - validate with `category_coding_display`

### Category & Classification Columns ⭐ GOLD STANDARD

#### 28. category_coding_display
- **Type**: String (FHIR category)
- **Coverage**: 100% (72/72) ✅ EXCELLENT
- **Values**:
  - `"Surgical procedure"` (10/72, 14%)
  - `"Diagnostic procedure"` (62/72, 86%)
- **Usage**: **AUTHORITATIVE FILTER** for surgical vs diagnostic
- **Recommended Filter**:
  ```python
  surgical = df[df['category_coding_display'] == 'Surgical procedure']
  diagnostic = df[df['category_coding_display'] == 'Diagnostic procedure']
  ```
- **Note**: **USE THIS FIELD** instead of keyword detection for reliable filtering

### Anatomical & Location Columns

#### 29. body_site_text
- **Type**: String (anatomical description)
- **Coverage**: 8.3% (6/72) ⚠️ SPARSE
- **Format**: Human-readable body site
- **Usage**: Anatomical location documentation
- **Note**: Low coverage because location often implicit in procedure code

#### 14. location_reference
- **Type**: String (FHIR reference)
- **Coverage**: Unknown (not analyzed)
- **Format**: Location FHIR ID
- **Usage**: Link to location resource for facility information

#### 15. location_display
- **Type**: String (location name)
- **Coverage**: Unknown (not analyzed)
- **Format**: Hospital/facility name
- **Usage**: Identify where procedure occurred

### Personnel Columns

#### 30. performer_actor_display
- **Type**: String (provider name)
- **Coverage**: 30.6% (22/72)
- **Format**: Practitioner name(s)
- **Usage**: Identify surgeons/providers
- **Multi-value Format**: Separated by ` | ` if multiple performers
- **Note**: Better coverage for surgical procedures

#### 31. performer_function_text
- **Type**: String (role description)
- **Coverage**: 30.6% (22/72)
- **Format**: Free text role (e.g., "Surgeon", "Anesthesiologist")
- **Usage**: Understand provider responsibilities
- **Multi-value Format**: Separated by ` | ` if multiple performers

#### 17. recorder_reference / 18. recorder_display
- **Type**: String (FHIR reference / name)
- **Coverage**: Unknown (not analyzed)
- **Usage**: Who documented the procedure

#### 19. asserter_reference / 20. asserter_display
- **Type**: String (FHIR reference / name)
- **Coverage**: Unknown (not analyzed)
- **Usage**: Who confirmed the procedure occurred

### Clinical Context Columns

#### 32. reason_code_text ⭐ HIGH COVERAGE
- **Type**: String (clinical indication)
- **Coverage**: 83.3% (60/72) ✅ EXCELLENT
- **Format**: Human-readable reason/indication
- **Usage**: Understand clinical context and decision-making
- **Examples**: Diagnosis, symptoms, preventive care
- **Multi-value Format**: Separated by ` | ` if multiple reasons

#### 13. encounter_display
- **Type**: String (encounter description)
- **Coverage**: 50% (36/72)
- **Format**: Human-readable encounter summary
- **Usage**: Context about the visit/encounter

#### 16. outcome_text
- **Type**: String (outcome description)
- **Coverage**: Low (not analyzed)
- **Usage**: Document procedure results

#### 21. status_reason_text
- **Type**: String (explanation)
- **Coverage**: Low (only if status ≠ completed)
- **Usage**: Why procedure was cancelled or not done
- **Note**: No procedures in this dataset have this populated (all completed)

### Documentation Columns ⭐ HIGH VALUE

#### 33. report_reference
- **Type**: String (FHIR reference)
- **Coverage**: 50% (36/72) ✅ GOOD
- **Format**: DocumentReference FHIR ID(s)
- **Usage**: **CRITICAL** - Link to operative reports and procedure documentation
- **Multi-value Format**: Separated by ` | ` (many procedures have 20+ reports)
- **Next Step**: Query DocumentReference table to get report dates and content
- **Note**: 998 total report linkages for 36 procedures = avg 27.7 reports per procedure

#### 34. report_display
- **Type**: String (report title)
- **Coverage**: 50% (36/72)
- **Format**: Human-readable report titles
- **Usage**: Identify type of documentation available
- **Multi-value Format**: Separated by ` | `
- **Examples**: Operative notes, anesthesia records, pathology reports

## Multi-Value Field Handling

Several columns can contain multiple values for a single procedure, separated by ` | `:

### Example: Multiple Procedure Codes
```csv
procedure_fhir_id,code_coding_display
ABC123,"IMMUNIZ, ADMIN,SINGLE | VACCINE ADMIN"
```

### Parsing Multi-Value Fields
```python
# Split pipe-separated values
df['code_list'] = df['code_coding_display'].str.split(' | ')

# Count codes per procedure
df['num_codes'] = df['code_list'].apply(lambda x: len(x) if isinstance(x, list) else 0)

# Check for specific code
df['has_cpt_90471'] = df['code_coding_code'].str.contains('90471', na=False)
```

## Filtering Strategies

### Filter 1: Surgical Procedures Only (RECOMMENDED)
```python
surgical = df[df['category_coding_display'] == 'Surgical procedure']
# Result: 10 procedures
```

### Filter 2: Exclude Administrative Orders
```python
non_admin = df[~df['code_coding_display'].str.contains('SURGICAL CASE REQUEST ORDER', na=False)]
# Removes 4 administrative orders
```

### Filter 3: Dated Procedures Only
```python
dated = df[df['performed_period_start'].notna()]
# Result: 8 procedures with explicit dates
```

### Filter 4: Procedures with Operative Reports
```python
with_reports = df[df['report_reference'].notna()]
# Result: 36 procedures (good for detailed analysis)
```

### Filter 5: Anesthesia Procedures (Surgical Markers)
```python
anesthesia = df[df['code_coding_display'].str.contains('ANES', case=False, na=False)]
# Result: 6 procedures (markers of 3 probable surgical events)
```

## Date Resolution Strategy

### Priority Order for Dating:
```python
def resolve_procedure_date(row):
    """Priority order for dating procedures"""
    if pd.notna(row['performed_period_start']):
        return row['performed_period_start']
    elif pd.notna(row['performed_date_time']):
        return row['performed_date_time']
    elif pd.notna(row['encounter_reference']):
        # Merge with encounters to get encounter_date
        return row['encounter_date']  # from merge
    elif pd.notna(row['report_reference']):
        # Query DocumentReference to get report date
        return row['report_date']  # from DocumentReference query
    else:
        return None

df['best_available_date'] = df.apply(resolve_procedure_date, axis=1)
```

## Common Analysis Patterns

### Pattern 1: Surgical Timeline
```python
surgical = df[df['category_coding_display'] == 'Surgical procedure'].copy()
surgical['procedure_date'] = pd.to_datetime(surgical['performed_period_start'])
surgical_timeline = surgical.sort_values('procedure_date')[
    ['procedure_date', 'code_coding_display', 'age_at_procedure_days', 'performer_actor_display']
]
```

### Pattern 2: Frequency Analysis
```python
top_procedures = df['code_coding_display'].value_counts().head(15)
print("Most common procedures:")
print(top_procedures)
```

### Pattern 3: Metadata Completeness
```python
completeness = pd.DataFrame({
    'column': df.columns,
    'coverage_pct': (df.notna().sum() / len(df) * 100).values
}).sort_values('coverage_pct', ascending=False)
```

### Pattern 4: Link to Encounters
```python
# Merge with encounters staging file
encounters = pd.read_csv('ALL_ENCOUNTERS_METADATA_C1277724.csv')
procedures_with_encounters = procedures.merge(
    encounters[['encounter_fhir_id', 'encounter_date', 'class_display']],
    left_on='encounter_reference',
    right_on='encounter_fhir_id',
    how='left'
)

# Filter for Surgery Log encounters
surgical_encounters = procedures_with_encounters[
    procedures_with_encounters['class_display'] == 'Surgery Log'
]
```

## Data Quality Issues

### Issue 1: Sparse Date Coverage (CRITICAL)
- **Field**: performed_period_start
- **Coverage**: 11% (8/72)
- **Impact**: Cannot create timeline for 89% of procedures
- **Solution**: Merge with encounters on encounter_reference (50% coverage)

### Issue 2: Body Site Sparse
- **Field**: body_site_text
- **Coverage**: 8.3% (6/72)
- **Impact**: Limited anatomical documentation
- **Mitigation**: Anatomical location often implicit in procedure code

### Issue 3: Performer Info Limited
- **Field**: performer_actor_display
- **Coverage**: 30.6% (22/72)
- **Impact**: Missing surgeon information for some procedures
- **Note**: Better coverage for surgical procedures

## Next Steps

1. **Merge with Encounters**: Use encounter_reference to get dates
2. **Query DocumentReference**: Use report_reference to access operative notes
3. **Validate Surgical Dates**: Cross-reference with diagnosis timeline
4. **Calculate Ages**: Use best_available_date for age calculations
5. **Filter Datasets**: Create surgical-only and diagnostic-only subsets

## Related Documentation

- `PROCEDURES_SCHEMA_DISCOVERY.md` - Database table structures
- `PROCEDURES_STAGING_FILE_ANALYSIS.md` - Comprehensive data analysis
- `ENCOUNTERS_COLUMN_REFERENCE.md` - Encounter columns for merging
- `SESSION_SUMMARY_PROCEDURES_STAGING.md` - This session's accomplishments
