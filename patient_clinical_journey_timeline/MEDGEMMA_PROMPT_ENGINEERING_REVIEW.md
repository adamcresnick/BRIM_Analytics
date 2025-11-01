# MedGemma Prompt Engineering Review & Improvements

**Date**: 2025-10-31
**Status**: Completed - All prompts improved with examples, field-specific instructions, and validation criteria

---

## Summary of Improvements

All three main extraction prompts have been significantly enhanced with:
1. **Field-specific instructions** - Detailed guidance for each output field
2. **Concrete examples** - Real-world scenarios showing expected input → output
3. **Ambiguous language handling** - Explicit rules for interpreting common clinical phrases
4. **Extraction confidence criteria** - Clear definitions of HIGH/MEDIUM/LOW confidence
5. **Critical validation notes** - Emphasis on required fields that must not be null
6. **Re-extraction guidance** - Specific field-level instructions for clarification prompts

---

## 1. Radiation Summary Prompt Improvements

### Issues Fixed:
- ❌ No examples provided for complex scenarios (craniospinal + boost)
- ❌ Unclear confidence criteria
- ❌ No guidance on unit conversion edge cases
- ❌ Missing validation emphasis on required fields

### New Additions:
✅ **Field-Specific Instructions** (lines 1100-1113)
- Detailed explanation of each field with data types and formats
- Clear distinction between craniospinal, focal, and boost doses
- Explicit null handling rules

✅ **Unit Conversion Rules** (lines 1115-1117)
- Formula: 1 Gy = 100 cGy
- Example: "54 Gy in 30 fractions" = 5400 cGy total, 180 cGy per fraction

✅ **Common Scenarios with Examples** (lines 1119-1141)
```
Example 1 - Focal only:
  Document: "Patient received 54 Gy to tumor bed in 30 fractions from 2024-01-15 to 2024-03-01"
  Output: {
    "date_at_radiation_start": "2024-01-15",
    "date_at_radiation_stop": "2024-03-01",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
    "radiation_focal_or_boost_dose": 5400,
    "radiation_type": "focal",
    "total_dose_cgy": 5400
  }

Example 2 - Craniospinal + Focal Boost:
  Document: "Craniospinal 36 Gy in 20 fractions, followed by focal boost 18 Gy in 10 fractions"
  Output: {
    "completed_craniospinal_or_whole_ventricular_radiation_dose": 3600,
    "radiation_focal_or_boost_dose": 1800,
    "radiation_type": "focal_with_boost",
    "total_dose_cgy": 5400
  }
```

✅ **Extraction Confidence Criteria** (lines 1143-1146)
- HIGH: All dates and doses explicitly stated, no ambiguity
- MEDIUM: Most fields present but some require inference
- LOW: Missing critical fields or document quality poor

✅ **Critical Validation** (lines 1148-1152)
- Emphasizes `total_dose_cgy` and `date_at_radiation_start` are REQUIRED
- Instructs to set confidence to LOW if required fields missing
- Clarifies difference between null (truly absent) vs uncertain

---

## 2. Operative Note Prompt Improvements

### Issues Fixed:
- ❌ No guidance on ambiguous surgical language
- ❌ Unclear confidence criteria
- ❌ No examples showing edge cases
- ❌ Missing validation emphasis

### New Additions:
✅ **Field-Specific Instructions** (lines 1057-1072)
- Definitions of GTR/NTR/STR/BIOPSY with percentages
- Guidance on where to find surgeon assessment text
- Residual tumor determination logic

✅ **Interpretation Guide for Ambiguous Language** (lines 1074-1083)
```
- "Complete resection" → GTR
- "Gross total resection" → GTR
- "Near-complete resection" → NTR
- "Near-total resection" → NTR
- "Maximal safe resection" → Check percentage; >95% → GTR, 90-95% → NTR, <90% → STR
- "Subtotal resection" → STR
- "Debulking" → STR
- "Biopsy only" → BIOPSY
```

✅ **Extraction Confidence Criteria** (lines 1085-1088)
- HIGH: Surgeon explicitly states EOR category or percentage
- MEDIUM: EOR inferred from descriptive language
- LOW: Minimal description or conflicting information

✅ **Concrete Examples** (lines 1090-1109)
```
Example 1: GTR with explicit statement
Example 2: STR with residual tumor on eloquent cortex
```

✅ **Critical Validation** (lines 1111-1114)
- `extent_of_resection` is REQUIRED
- `surgeon_assessment` is REQUIRED (verbatim text)
- If unclear, use "UNCLEAR" category with LOW confidence

### Validation Update:
- Added `surgeon_assessment` to required fields for `missing_eor` gaps (line 1444)

---

## 3. Imaging Prompt Improvements

### Issues Fixed:
- ❌ Nested JSON structure potentially confusing
- ❌ No guidance on "stable" reports without measurements
- ❌ Unclear when to use empty lesions array
- ❌ No examples for different RANO categories

### New Additions:
✅ **Field-Specific Instructions** (lines 1024-1058)
- When to use empty lesions array `[]`
- Explanation of bidimensional measurements (ap, ml, si)
- Percent change calculation formula
- RANO category definitions with thresholds

✅ **Handling Ambiguous Language** (lines 1060-1065)
```
- "Stable compared to prior" → RANO: "SD"
- "Slight interval increase" → Check if ≥25% (may be SD or PD)
- "Decreased size" → If ≥50% → PR, else SD
- "No significant change" → RANO: "SD"
- "No evidence of tumor" → RANO: "CR", lesions: []
```

✅ **Extraction Confidence Criteria** (lines 1067-1070)
- HIGH: Explicit measurements + clear RANO category
- MEDIUM: Qualitative descriptions only
- LOW: Minimal or conflicting information

✅ **Examples Covering Multiple Scenarios** (lines 1072-1099)
```
Example 1 - Measurable disease with prior comparison:
  Shows bidimensional measurements, percent change calculation, RANO SD

Example 2 - Complete response:
  Shows empty lesions array, RANO CR

(Example 3 would show progressive disease with new lesions)
```

✅ **Critical Validation** (lines 1101-1104)
- `lesions` and `rano_assessment` are REQUIRED (cannot be null)
- `lesions` can be empty `[]` but not null
- `radiologist_impression` should contain verbatim text

---

## 4. Re-Extraction Clarification Improvements

### Issue Fixed:
- ❌ Generic placeholder instructions: `"- {field}: <specific instruction for this field>"`

### New Addition:
✅ **Field-Specific Guidance Dictionary** (lines 1480-1489)
```python
field_guidance = {
    'extent_of_resection': 'Look for phrases like "gross total resection", "subtotal resection", "biopsy only" in operative note',
    'surgeon_assessment': 'Extract verbatim text from surgeon describing the resection outcome',
    'date_at_radiation_start': 'Find the first date radiation was delivered (YYYY-MM-DD). May be in "Treatment Start" section',
    'date_at_radiation_stop': 'Find the last date radiation was delivered (YYYY-MM-DD). May be calculated from start + duration',
    'total_dose_cgy': 'Find total cumulative dose in cGy or Gy (convert: 1 Gy = 100 cGy)',
    'radiation_type': 'Determine if focal, craniospinal, whole_ventricular, or focal_with_boost',
    'lesions': 'Extract array of tumor lesions with measurements. Use [] if no tumor present',
    'rano_assessment': 'Assess response using RANO criteria based on size change and new lesions'
}
```

Now when MedGemma fails to extract a field, Agent 1 provides **specific, actionable guidance** for that field in the re-extraction prompt.

---

## Validation Updates

Updated required fields to match prompt expectations:

| Gap Type | Required Fields |
|----------|----------------|
| `missing_eor` | `extent_of_resection`, `surgeon_assessment` |
| `missing_radiation_details` | `date_at_radiation_start`, `total_dose_cgy`, `radiation_type` |
| `vague_imaging_conclusion` | `lesions`, `rano_assessment` |

---

## Impact on Agent 1 ↔ Agent 2 Negotiation

These improvements strengthen the negotiation loop by:

1. **First Extraction**: MedGemma receives detailed prompts with examples and field instructions
2. **Agent 1 Validation**: Checks for required fields based on aligned validation rules
3. **Re-Extraction**: If incomplete, Agent 1 provides field-specific guidance to MedGemma
4. **Success Criteria**: Extraction only marked RESOLVED if all required fields present

This reduces:
- Incomplete extractions requiring manual review
- Ambiguous interpretations of clinical language
- Mismatched field names between prompts and validation

---

## Testing Recommendations

1. **Test with ambiguous operative notes** to validate EOR interpretation guide
2. **Test with craniospinal + boost radiation docs** to validate dose field extraction
3. **Test with qualitative imaging reports** ("stable", "decreased") to validate RANO inference
4. **Test re-extraction loop** by intentionally using incomplete documents

---

## Files Modified

| File | Lines Modified | Description |
|------|---------------|-------------|
| [patient_timeline_abstraction_V2.py:1119-1155](patient_timeline_abstraction_V2.py#L1119-L1155) | Radiation prompt | Added examples, field instructions, confidence criteria |
| [patient_timeline_abstraction_V2.py:1109-1117](patient_timeline_abstraction_V2.py#L1109-L1117) | Operative note prompt | Added interpretation guide, examples, validation notes |
| [patient_timeline_abstraction_V2.py:988-1107](patient_timeline_abstraction_V2.py#L988-L1107) | Imaging prompt | Added field instructions, ambiguous language handling, examples |
| [patient_timeline_abstraction_V2.py:1463-1528](patient_timeline_abstraction_V2.py#L1463-L1528) | Re-extraction method | Added field-specific guidance dictionary |
| [patient_timeline_abstraction_V2.py:1444](patient_timeline_abstraction_V2.py#L1444) | Validation | Added `surgeon_assessment` to required fields |

---

## Next Steps

1. ✅ Prompt engineering improvements complete
2. ⏳ Test validation and negotiation loop with real patient data
3. ⏳ Fix `medgemma_target` population for surgery/radiation gaps
4. ⏳ Implement `_find_operative_note_binary()` and `_find_radiation_document()` integration
5. ⏳ Address empty dates issue in timeline events

---

**Status**: Ready for testing with improved prompts
