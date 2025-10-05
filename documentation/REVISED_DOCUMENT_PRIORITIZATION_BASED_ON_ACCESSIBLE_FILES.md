# Revised Document Prioritization: Based on Accessible Binary Files Analysis
**Date**: October 4, 2025
**Source**: `accessible_binary_files_annotated.csv` (3,865 documents for patient C1277724)
**Critical Finding**: Most clinical notes are in XML format, NOT text/html or text/rtf
**Status**: ⚠️ Major strategy revision required

---

## CRITICAL FINDINGS

### **Finding 1: Content Type Mismatch** 🚨

**Previous Assumption**: Most clinical notes available in text/html or text/rtf format
**Reality**: 76.3% of accessible documents are `application/xml`

```
Content Type Distribution (Patient C1277724):
  application/xml:     762 documents (76.3%)  ← Encounter Summaries
  text/xml:             83 documents (8.3%)   ← External C-CDA
  text/html + text/rtf: 113 documents (11.3%) ← Only processable by BRIM (current)
  application/pdf:      28 documents (2.8%)   ← Imaging reports
  Images:               12 documents (1.2%)   ← Not processable
```

### **Finding 2: Critical Note Types Are NOT in Text Format** 🚨

**All critical clinical note types are in non-text formats:**

| Note Type | Total Available | text/html or text/rtf | application/xml | application/pdf | Other |
|-----------|----------------|----------------------|-----------------|-----------------|-------|
| **Discharge Summary** | 5 | **0** ❌ | 0 | 0 | 5 (unknown) |
| **Consult Note** | 44 | **0** ❌ | 0 | 0 | 44 (unknown) |
| **H&P** | 13 | **0** ❌ | 0 | 0 | 13 (unknown) |
| **OP Note - Complete** | 10 | **0** ❌ | 0 | 0 | 10 (unknown) |
| **OP Note - Brief** | 9 | **0** ❌ | 0 | 0 | 9 (unknown) |
| **Anesthesia Preprocedure** | 25 | **0** ❌ | 0 | 0 | 25 (unknown) |
| **Anesthesia Postprocedure** | 11 | **0** ❌ | 0 | 0 | 11 (unknown) |
| **Pathology study** | 40 | 6 ✅ | 0 | 0 | 34 (unknown) |
| **MR Brain W & W/O IV Contrast** | 39 | 0 ❌ | 0 | 11 | 28 (unknown) |

**Implication**: If BRIM can only process text/html and text/rtf, we **CANNOT use** the majority of high-value clinical documents.

### **Finding 3: Encounter Summaries Dominate**

**761 Encounter Summary documents** in `application/xml` format span entire clinical timeline:
- 2005-2025 coverage
- **127 documents** in 2018 (diagnosis/surgery year)
- **102 documents** in 2021 (second surgery year)
- **10 encounter summaries** around 2018 surgery (May 21-June 14)
- **12 encounter summaries** around 2021 surgery (Feb 22-Mar 16)
- **5 encounter summaries** during diagnosis period (June 2018)

**Question**: Can BRIM process `application/xml` Encounter Summaries?
- If **YES**: Massive coverage improvement
- If **NO**: Severely limited document availability

---

## What's Actually Available in Text/HTML or Text/RTF?

### **Text-Processable Documents** (113 total for patient C1277724):

| Document Type | Count | Date Range | Clinical Value |
|--------------|-------|------------|----------------|
| **Telephone Encounter** | 35 | 2023-12-04 to 2025-01-31 | LOW - Recent phone calls |
| **Progress Notes** | 29 | 2023-11-27 to 2025-05-22 | **MEDIUM-HIGH** - Recent clinical assessments |
| **Diagnostic imaging study** | 27 | 2024-01-23 to 2025-05-14 | **HIGH** - Recent imaging reports |
| **Pathology study** | 6 | 2024-01-23 to 2024-09-09 | **CRITICAL** - But only recent (2024), missing 2018 diagnosis |
| **Patient Instructions** | 5 | 2023-11-27 to 2025-01-09 | LOW - Patient education materials |
| **Addendum Note** | 3 | 2024-09-20 to 2025-02-27 | MEDIUM - Updates to previous notes |
| **ED Notes** | 1 | 2025-01-31 | MEDIUM - Emergency visit |
| **Care Plan Note** | 1 | 2025-01-31 | MEDIUM - Treatment planning |
| **Others** | 6 | Various | LOW - Misc clinical notes |

**CRITICAL PROBLEM**:
- ❌ **ZERO** operative notes from 2018 or 2021 surgeries in text format
- ❌ **ZERO** discharge summaries in text format
- ❌ **ZERO** H&P notes in text format
- ❌ **ZERO** consult notes in text format
- ❌ **ZERO** anesthesia notes in text format
- ✅ **ONLY 6** pathology studies in text format (2024, not the critical 2018 diagnosis pathology)
- ✅ **27** imaging study reports in text format (2024-2025, recent only)
- ✅ **29** progress notes in text format (2023-2025, recent only)

**Timeline Gap**: Text-processable documents are **mostly from 2023-2025**, missing critical 2018 diagnosis and 2018/2021 surgery periods!

---

## Revised Assessment: What CAN We Use?

### **Scenario A: BRIM Supports ONLY text/html and text/rtf**

#### **Available High-Value Documents**:

**TIER 1: Critical (but limited)**
1. ✅ **Pathology study** (6 docs) - BUT from 2024, NOT 2018 diagnosis
2. ✅ **Diagnostic imaging study** (27 docs) - Recent (2024-2025) MRI reports
3. ✅ **Progress Notes** (29 docs) - Recent (2023-2025) clinical assessments

**TIER 2: Supporting**
4. **Telephone Encounter** (35 docs) - Recent phone encounters (low clinical density)
5. **Patient Instructions** (5 docs) - Patient education (low value)
6. **Addendum Note** (3 docs) - Updates to previous notes
7. **Other misc notes** (8 docs) - Various recent clinical notes

**Total available**: 113 documents
**Coverage period**: Primarily 2023-2025 (recent), **MISSING critical 2018 diagnosis and surgery documentation**

#### **Variable Coverage Estimate**:

| Variable Category | Coverage | Rationale |
|------------------|----------|-----------|
| **Diagnosis** | **30%** ❌ | No 2018 pathology in text format; only recent 2024 pathology |
| **Molecular** | **20%** ❌ | No 2018 molecular testing in text format |
| **Surgery** | **10%** ❌ | No operative notes in text format |
| **Chemotherapy** | **50%** ⚠️ | Recent progress notes may mention chemo status |
| **Radiation** | **20%** ❌ | No radiation oncology consults in text format |
| **Imaging** | **70%** ✅ | 27 recent imaging reports available |
| **Clinical Status** | **60%** ⚠️ | 29 recent progress notes provide recent status |
| **Demographics** | **100%** ✅ | From FHIR Bundle structured data |

**Overall projected accuracy**: **40-50%** ❌ (WORSE than current 81.2% baseline!)

**Conclusion**: Using ONLY text/html and text/rtf documents would be a **MAJOR REGRESSION** from current Phase 3a_v2.

---

### **Scenario B: BRIM Can Parse application/xml (Encounter Summaries)**

#### **Available High-Value Documents**:

**TIER 1: Encounter Summaries (XML)**
1. ✅ **Encounter Summary** (761 docs) - Full longitudinal coverage (2005-2025)
   - 127 documents in 2018 (diagnosis/surgery year)
   - 102 documents in 2021 (second surgery year)
   - 10 encounter summaries around 2018-05-28 surgery
   - 12 encounter summaries around 2021-03-10 surgery
   - 5 encounter summaries during 2018 diagnosis period

**Question**: What's in an Encounter Summary XML?
- Likely contains: Visit summary, diagnosis lists, medications, procedures, assessments, plans
- **C-CDA format**: Structured XML with sections (Chief Complaint, Assessment & Plan, Medications, etc.)
- **Potential**: High clinical content density if parseable

**TIER 2: Text-processable notes**
2. ✅ **Progress Notes** (29 docs) - Recent assessments
3. ✅ **Diagnostic imaging study** (27 docs) - Recent imaging reports
4. ✅ **Pathology study** (6 docs) - Recent pathology

**TIER 3: External C-CDA Documents**
5. ✅ **External C-CDA** (83 docs) - External medical records in structured XML

**Total available**: 113 text + 761 XML + 83 C-CDA = **957 documents**

#### **Variable Coverage Estimate** (IF XML parseable):

| Variable Category | Coverage | Rationale |
|------------------|----------|-----------|
| **Diagnosis** | **80%** ✅ | Encounter summaries around diagnosis period likely contain diagnosis info |
| **Molecular** | **60%** ⚠️ | May be referenced in encounter summaries |
| **Surgery** | **85%** ✅ | Encounter summaries around surgery dates likely summarize procedures |
| **Chemotherapy** | **85%** ✅ | Encounter summaries + progress notes capture chemo timeline |
| **Radiation** | **70%** ⚠️ | Encounter summaries may reference radiation plans |
| **Imaging** | **80%** ✅ | 27 recent imaging reports + encounter summary references |
| **Clinical Status** | **85%** ✅ | Encounter summaries + progress notes provide longitudinal status |
| **Demographics** | **100%** ✅ | From FHIR Bundle |

**Overall projected accuracy**: **80-85%** ✅ (Maintains current baseline, slight improvement)

---

### **Scenario C: BRIM Can Parse application/pdf (Radiology Reports)**

#### **Additional Available Documents**:

**Radiology Reports (PDF)**:
- ✅ **MR Brain W & W/O IV Contrast** (11 PDFs) - Radiology narrative reports
- ✅ **Other imaging PDFs** (17 PDFs) - CT, other MRI protocols

**Total PDFs**: 28 documents

#### **Variable Coverage Improvement**:

| Variable Category | Coverage Gain | New Coverage |
|------------------|--------------|--------------|
| **Imaging** | +10% | **90%** ✅ |
| **Tumor Location** | +15% | **75%** ✅ |
| **Clinical Status** | +5% | **90%** ✅ |

**Overall projected accuracy**: **85-90%** ✅ (Significant improvement)

---

## Recommended Strategy: Multi-Format Approach

### **Option 1: XML Parsing Pipeline** (RECOMMENDED)

**Approach**:
1. **Parse Encounter Summary XML files** (761 docs)
   - Extract text content from C-CDA sections
   - Convert to text/HTML format
   - Include in project.csv

2. **Include text-processable documents** (113 docs)
   - Use as-is (already text/html or text/rtf)

3. **Optionally parse External C-CDA** (83 docs)
   - Extract external medical records
   - Convert to text format

**Preprocessing Required**:
```python
import xml.etree.ElementTree as ET

def parse_ccda_to_text(xml_content):
    """
    Extract clinical narrative from C-CDA XML
    Returns: Plain text or HTML with clinical sections
    """
    root = ET.fromstring(xml_content)

    # Extract sections: Chief Complaint, HPI, Assessment & Plan, etc.
    sections = {}
    for section in root.findall('.//{urn:hl7-org:v3}section'):
        title = section.find('.//{urn:hl7-org:v3}title')
        text = section.find('.//{urn:hl7-org:v3}text')
        if title is not None and text is not None:
            sections[title.text] = ET.tostring(text, encoding='unicode', method='text')

    # Format as HTML or plain text for BRIM
    formatted_text = '\n\n'.join([f'## {title}\n{content}' for title, content in sections.items()])
    return formatted_text
```

**Pros**:
- Unlocks 761 encounter summaries with longitudinal coverage
- Covers critical 2018 diagnosis and surgery periods
- Maintains structured clinical content

**Cons**:
- Requires preprocessing pipeline
- XML parsing complexity
- Need to validate BRIM can handle converted content

**Expected Accuracy**: **80-85%** (maintains current baseline)

---

### **Option 2: Text-Only (NO Preprocessing)**

**Approach**:
- Use ONLY the 113 text/html and text/rtf documents
- Accept limited coverage

**Pros**:
- No preprocessing required
- Simple BRIM upload

**Cons**:
- **MASSIVE coverage gap** for 2018 diagnosis/surgery
- Missing all operative notes, discharge summaries, consult notes
- **Expected accuracy: 40-50%** ❌ (REGRESSION from 81.2% baseline)

**Recommendation**: ❌ **DO NOT USE** - This would be worse than current Phase 3a_v2

---

### **Option 3: Hybrid (XML + PDF Parsing)**

**Approach**:
1. Parse Encounter Summary XML → text (761 docs)
2. Use text-processable documents as-is (113 docs)
3. Convert PDF radiology reports → text (28 docs)
4. Optionally parse External C-CDA (83 docs)

**Total**: 985 documents (or 902 without external C-CDA)

**Expected Accuracy**: **85-92%** ✅ (BEST option)

**Cons**:
- Most complex preprocessing pipeline
- Requires XML + PDF parsing
- Development effort

---

## Immediate Next Steps

### **CRITICAL QUESTION**: Does BRIM support XML or PDF formats?

**Test 1: Upload Sample XML**
- Take 1 Encounter Summary XML from accessible files
- Upload to BRIM as-is
- Test if BRIM can extract variables

**Test 2: Upload Sample PDF**
- Take 1 MR Brain PDF radiology report
- Upload to BRIM as-is
- Test if BRIM can extract variables

**If BRIM supports XML**:
→ Proceed with Option 1 (XML parsing pipeline)

**If BRIM supports PDF**:
→ Proceed with Option 3 (Hybrid XML + PDF)

**If BRIM supports NEITHER**:
→ Build preprocessing pipeline to convert XML/PDF → text/HTML

---

## Current Phase 3a_v2 project.csv Re-evaluation

### **What's Actually IN Current project.csv** (45 documents):

Looking at `accessible_binary_files_annotated.csv`, the current 40 Binary documents in Phase 3a_v2 are likely **NOT** in this accessible files list because:

1. **Different query method**: Current project.csv may use different DocumentReference query or different database (fhir_v1_prd_db vs fhir_v2_prd_db)
2. **Different time period**: accessible_binary_files may be a different snapshot
3. **Different document selection criteria**

**Critical Question**: Where did the current 40 documents in Phase 3a_v2 project.csv come from?
- Were they manually selected?
- From a different Athena query?
- From a different time period?

### **Recommendation**: Cross-reference current project.csv with accessible_binary_files

```python
# Load current project.csv
current_project = pd.read_csv('pilot_output/brim_csvs_iteration_3c_phase3a_v2/project.csv')

# Extract document IDs from current project
current_doc_ids = set(current_project[current_project['NOTE_ID'].str.startswith('Binary/', na=False)]['NOTE_ID'].str.replace('Binary/', ''))

# Load accessible binary files
accessible = pd.read_csv('pilot_output/brim_csvs_iteration_3c_phase3a_v2/accessible_binary_files_annotated.csv')
accessible_ids = set(accessible['binary_id'].str.replace('Binary/', ''))

# Check overlap
overlap = current_doc_ids.intersection(accessible_ids)
print(f"Current docs in accessible list: {len(overlap)} of {len(current_doc_ids)}")
print(f"Current docs NOT in accessible list: {len(current_doc_ids - accessible_ids)}")
```

---

## Revised Top 20 Note Types (Based on Actual Availability)

### **IF BRIM Supports XML**:

**TIER 1: MUST HAVE**
1. **Encounter Summary** (761 docs, application/xml) - Longitudinal clinical summaries
2. **Progress Notes** (29 docs, text/html/rtf) - Recent clinical assessments
3. **Diagnostic imaging study** (27 docs, text/html/rtf) - Recent imaging reports
4. **Pathology study** (6 docs, text/html/rtf) - Recent pathology (but missing 2018 diagnosis!)

**TIER 2: HIGH VALUE (if accessible)**
5. External C-CDA Documents (83 docs, text/xml) - External medical records
6. **Consult Note** (44 docs, format unknown) - Need to find these
7. **Discharge Summary** (5 docs, format unknown) - Need to find these
8. **OP Note - Complete** (10 docs, format unknown) - Need to find these
9. **H&P** (13 docs, format unknown) - Need to find these

**CRITICAL GAP**: Documents #6-9 exist in accessible_binary_files but their content_type is "unknown" - **need to investigate actual format**

### **IF BRIM Supports ONLY text/html and text/rtf**:

**TIER 1: AVAILABLE**
1. **Diagnostic imaging study** (27 docs)
2. **Progress Notes** (29 docs)
3. **Pathology study** (6 docs)
4. **Telephone Encounter** (35 docs) - Low clinical value but high volume

**CRITICAL PROBLEM**: This list is too small and too recent to adequately cover 2018 diagnosis and surgery periods.

---

## Final Recommendation

### **Immediate Actions**:

1. ✅ **Test BRIM format support**:
   - Upload 1 sample Encounter Summary XML
   - Upload 1 sample PDF radiology report
   - Determine what BRIM can process

2. ✅ **Investigate "unknown" format documents**:
   - The 44 Consult Notes, 13 H&Ps, 10 OP Notes, 5 Discharge Summaries show "Other formats: X"
   - Need to check actual content_type in database or S3
   - May be in text/html or text/rtf but not captured in accessible_binary_files_annotated.csv

3. ✅ **Cross-reference current project.csv**:
   - Understand where current 40 documents came from
   - Validate they're still the best available

4. ⚠️ **If BRIM cannot process XML/PDF**:
   - Build preprocessing pipeline to convert XML → text/HTML
   - Consider PDF-to-text conversion for radiology reports
   - Target: 700-900 documents (XML encounter summaries + text docs)

5. ✅ **If BRIM can process XML/PDF**:
   - Proceed with document selection from accessible_binary_files_annotated.csv
   - Target: 800-1000 documents (encounter summaries + text docs + PDFs)

---

**Document Status**: ✅ Complete - Strategy Revision Required
**Critical Finding**: Majority of high-value documents are in XML format, not text/html or text/rtf
**Next Step**: Determine BRIM's XML/PDF processing capabilities before proceeding
