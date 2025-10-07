# BRIM Upload Checklist

## Pre-Upload Verification

### Files Validated
- [x] variables_PRODUCTION.csv (33 variables, 0 errors)
- [x] decisions_PRODUCTION.csv (13 dependent variables, 0 errors)
- [x] project.csv (1,472 rows, deduplicated)

### Architecture Alignment
- [x] Variables are pure extractors (Stage 1)
- [x] Dependent variables do filtering/aggregation (Stage 2)
- [x] All variable_type values are data types (text/boolean/integer/float)
- [x] All default_empty_value fields populated
- [x] All option_definitions are valid JSON

### Gold Standard Reference
- [x] Patient: C1277724
- [x] Surgery 1: 2018-05-28, Pilocytic astrocytoma, Partial Resection, Cerebellum
- [x] Surgery 2: 2021-03-10, Pilocytic astrocytoma recurrent, Partial Resection, Cerebellum
- [x] Total surgeries: 2
- [x] Chemotherapy agents: vinblastine, bevacizumab, selumetinib

---

## Upload Sequence

### Step 1: Upload Variables
- [ ] Navigate to BRIM interface
- [ ] Upload: `variables_PRODUCTION.csv`
- [ ] Verify: "0 lines skipped" message
- [ ] Confirm: 33 variables loaded

**If errors occur:**
- Check error message for specific line numbers
- Run validation script again
- Review REDESIGN_COMPARISON.md

### Step 2: Upload Decisions (Dependent Variables)
- [ ] Upload: `decisions_PRODUCTION.csv`
- [ ] Verify: "0 lines skipped" message (was 13/14 before!)
- [ ] Confirm: 13 dependent variables loaded

**Expected Success**: All 13 dependent variables should load without errors

### Step 3: Upload Project
- [ ] Upload: `project.csv`
- [ ] Verify: 1,472 rows loaded
- [ ] Confirm: No duplicate patient_id + note_id combinations

---

## Run Extraction

### Configuration
- [ ] Select all 33 variables for extraction
- [ ] Enable all 13 dependent variables
- [ ] Set extraction to run on all 1,472 project rows
- [ ] Estimate: 2-4 hours runtime

### Monitor Progress
- [ ] Check extraction logs for errors
- [ ] Monitor progress percentage
- [ ] Note any warnings or skipped documents

---

## Validation Against Gold Standard

### Patient C1277724 - Expected Values

#### Variables (Stage 1 - Extraction)
| Variable | Expected Value |
|----------|----------------|
| patient_id | C1277724 |
| primary_diagnosis | Pilocytic astrocytoma |
| surgery_number | 2 |
| surgery_date | 2018-05-28; 2021-03-10 |
| surgery_diagnosis | Pilocytic astrocytoma; Pilocytic astrocytoma, recurrent |
| surgery_extent | Partial Resection; Partial Resection |
| surgery_location | Cerebellum/Posterior Fossa; Cerebellum/Posterior Fossa |
| chemotherapy_agents | vinblastine; bevacizumab; selumetinib |
| symptoms_present | Emesis; Headaches; Hydrocephalus; Visual deficit; Posterior fossa syndrome |

#### Dependent Variables (Stage 2 - Filtering/Aggregation)
| Dependent Variable | Expected Value |
|--------------------|----------------|
| diagnosis_surgery1 | Pilocytic astrocytoma |
| extent_surgery1 | Partial Resection |
| location_surgery1 | Cerebellum/Posterior Fossa |
| diagnosis_surgery2 | Pilocytic astrocytoma, recurrent |
| extent_surgery2 | Partial Resection |
| location_surgery2 | Cerebellum/Posterior Fossa |
| total_surgeries | 2 |
| all_chemotherapy_agents | vinblastine;bevacizumab;selumetinib |
| all_symptoms | Emesis;Headaches;Hydrocephalus;Visual deficit;Posterior fossa syndrome |

---

## Accuracy Assessment

### Validation Procedure
1. [ ] Export extraction results for C1277724
2. [ ] Compare each variable to gold standard
3. [ ] Calculate accuracy percentage
4. [ ] Document discrepancies

### Success Criteria
- [ ] Variables accuracy ≥ 95%
- [ ] Dependent variables accuracy ≥ 95%
- [ ] 0 lines skipped during upload
- [ ] 0 critical errors during extraction

### Expected vs Actual
| Metric | Expected | Actual | Pass/Fail |
|--------|----------|--------|-----------|
| Variables loaded | 33 | ___ | __ |
| Decisions loaded | 13 | ___ | __ |
| Variables skipped | 0 | ___ | __ |
| Decisions skipped | 0 | ___ | __ |
| Extraction errors | 0 | ___ | __ |
| Overall accuracy | 93-98% | ___ % | __ |

---

## Troubleshooting

### If Variables Are Skipped
1. Check error message for line numbers
2. Run: `python3 scripts/validate_redesigned_csvs.py`
3. Review variable_type values (must be text/boolean/integer/float)
4. Check for empty required fields

### If Decisions Are Skipped
1. Verify input_variables reference existing variable names
2. Check default_empty_value is present for all rows
3. Validate option_definitions JSON format
4. Ensure variable_type is data type (not "filter"/"aggregation")

### If Extraction Fails
1. Check BRIM logs for specific error messages
2. Review extraction configuration
3. Verify project.csv has valid patient_id and note_id values
4. Check for document access issues

---

## Post-Upload Actions

### Immediate
- [ ] Confirm 0 lines skipped for all 3 files
- [ ] Save upload confirmation messages
- [ ] Start extraction run
- [ ] Set reminder to check extraction progress in 1 hour

### After Extraction Completes
- [ ] Download results for C1277724
- [ ] Validate against gold standard
- [ ] Document accuracy metrics
- [ ] Identify any remaining issues
- [ ] Update documentation with lessons learned

### If Accuracy < 95%
- [ ] Review extraction logs for patterns
- [ ] Check if specific document types are problematic
- [ ] Verify gold standard data sources
- [ ] Consider instruction refinements for low-accuracy variables

---

## Sign-Off

**Pre-Upload Verification Completed By**: _______________ Date: ___________

**Upload Completed By**: _______________ Date: ___________

**Extraction Validated By**: _______________ Date: ___________

**Final Accuracy**: _____ % (Target: 93-98%)

**Status**: ☐ Success  ☐ Needs Review  ☐ Failed

**Notes**:
___________________________________________________________________________
___________________________________________________________________________
___________________________________________________________________________

---

## Files Reference

### Production Files (Upload These)
- `variables_PRODUCTION.csv` - 33 variables
- `decisions_PRODUCTION.csv` - 13 dependent variables  
- `project.csv` - 1,472 patient-document rows

### Archive Files (Do Not Upload)
- `variables_archived_*.csv` - Old format (for reference)
- `decisions_archived_*.csv` - Old format (caused 13/14 skipped)

### Documentation Files
- `REDESIGN_COMPARISON.md` - Before/after comparison
- `UPLOAD_CHECKLIST.md` - This file

### Validation Scripts
- `scripts/validate_redesigned_csvs.py` - Format validation
- `scripts/analyze_variables_for_redesign.py` - Analysis tool
- `scripts/create_redesigned_variables.py` - Variable generation
- `scripts/create_redesigned_decisions.py` - Decision generation

---

**Last Updated**: 2025-10-05 07:51:13
**Version**: 2.0 (Option B - Full Redesign)
**Status**: ✅ Ready for Upload
