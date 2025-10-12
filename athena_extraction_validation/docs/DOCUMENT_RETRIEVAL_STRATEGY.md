# Document Retrieval Strategy for Radiation Oncology

## Overview

The radiation therapy extraction workflow captures **all** radiation oncology documents from DocumentReference resources but distinguishes between documents that are already extracted elsewhere vs. those that need binary content retrieval in this workflow.

## Document Categories

### Already Extracted (HTML/RTF)
- **Formats**: `text/html`, `text/rtf`
- **Extraction**: These documents are already extracted via the existing comprehensive DocumentReference workflow
- **In This Workflow**: Listed in `radiation_oncology_documents.csv` for completeness but marked with `doc_needs_retrieval = False`
- **Priority**: `LOW` (comprehensive listing, no additional action needed)

### Needs Retrieval (PDFs/Images)
- **Formats**: `application/pdf`, `image/tiff`, `image/jpeg`, `image/png`, and others
- **Extraction**: NOT extracted in existing workflows - need binary content retrieval
- **In This Workflow**: Marked with `doc_needs_retrieval = True` for processing
- **Priority**: 
  - `HIGH` = PDFs or TIFFs from "Radiation Oncology" practice setting (external treatment summaries)
  - `MEDIUM` = Images from Rad Onc, or PDFs/images from related specialties
  - `LOW` = HTML/RTF (already extracted)

## Column Schema

### Key Columns in `radiation_oncology_documents.csv`

| Column | Description | Values |
|--------|-------------|--------|
| `doc_format_category` | Document format | PDF, TIFF Image, JPEG Image, PNG Image, HTML, RTF, Other |
| `doc_is_likely_external` | Likely from external institution | True for PDFs/images, False for HTML/RTF |
| `doc_needs_retrieval` | **NEW** - Needs binary retrieval in THIS workflow | True for non-HTML/RTF, False for HTML/RTF |
| `doc_priority` | Processing priority | HIGH (PDFs from Rad Onc), MEDIUM (images/related PDFs), LOW (HTML/RTF) |

## Workflow Integration

### Current State (Comprehensive Listing)
```python
documents_df = extract_radiation_oncology_documents(athena, patient_id)
# Returns DataFrame with ALL Radiation Oncology documents
# Columns include: doc_needs_retrieval, doc_priority, doc_binary_id, etc.
```

### Future Enhancement (Binary Retrieval)
```python
# Filter for documents needing retrieval
docs_to_retrieve = documents_df[documents_df['doc_needs_retrieval'] == True]

# Prioritize by priority level
high_priority = docs_to_retrieve[docs_to_retrieve['doc_priority'] == 'HIGH']

# Retrieve binary content from S3
for _, doc in high_priority.iterrows():
    binary_id = doc['doc_binary_id']
    content = retrieve_binary_content(binary_id)
    # Process PDF content (text extraction, OCR, etc.)
```

## Rationale

### Why List HTML/RTF if Already Extracted?

1. **Comprehensive Documentation**: Provides complete picture of all radiation oncology documentation
2. **Cross-Reference**: Links between RT appointments/treatments and their associated notes
3. **Audit Trail**: Verifies that all Rad Onc documents are accounted for across workflows
4. **Future Analysis**: Enables correlation analysis between structured data and unstructured notes

### Why Only Retrieve PDFs/Images Here?

1. **Avoid Duplication**: HTML/RTF extraction already handled by existing workflow
2. **Resource Optimization**: Don't waste processing time on already-extracted content
3. **Focus on Gaps**: PDFs and images often contain external institution records not captured elsewhere
4. **Specialty-Specific Context**: RT-specific PDFs require domain expertise to interpret (dose, technique, etc.)

## Example Output

### Test Patient: `eoA0IUD9yNPeuxPPiUouATJ9GJXsLuc.V.jCILPjXR9I3`

```
RT-Related Documents:          140
PDFs (likely external):        0
Likely External Docs:          0
High Priority Docs:            0
Needs Retrieval (non-HTML/RTF): 48
Note: HTML/RTF docs are already extracted via separate workflow
```

**Breakdown:**
- 140 total Radiation Oncology documents
- 48 documents (34.3%) need retrieval (format = "Other" - likely XML/structured)
- 92 documents (65.7%) already extracted (46 HTML + 46 RTF)
- 0 PDFs for this patient (all treatment was internal)

### Expected for Patients with External Treatment

```
RT-Related Documents:          56
PDFs (likely external):        10
Likely External Docs:          17
High Priority Docs:            10
Needs Retrieval (non-HTML/RTF): 17
```

**Breakdown:**
- 56 total Radiation Oncology documents
- 10 PDFs (HIGH priority - likely external treatment summaries)
- 7 images (4 TIFF + 3 JPEG - MEDIUM priority)
- 39 HTML/RTF (LOW priority - already extracted)

## Next Steps

### Phase 1: Comprehensive Listing ✅ COMPLETE
- [x] Query all Radiation Oncology documents
- [x] Categorize by format
- [x] Flag external vs. internal
- [x] Add retrieval flag
- [x] Assign priority scores
- [x] Save to CSV for review

### Phase 2: Binary Content Retrieval (FUTURE)
- [ ] Implement S3 binary content retrieval for PDFs
- [ ] Extract text from PDFs (pypdf2, pdfplumber)
- [ ] OCR for scanned images (Tesseract, AWS Textract)
- [ ] Parse dose/technique information from external summaries
- [ ] Link documents to treatment courses by date

### Phase 3: Advanced Analysis (FUTURE)
- [ ] NLP extraction of treatment parameters from PDFs
- [ ] External institution name database
- [ ] Automatic categorization (treatment summary, planning, consultation)
- [ ] Quality scoring for manual abstraction prioritization
- [ ] Integration with structured RT data for validation

## References

- **Existing DocumentReference Workflow**: `extract_all_binary_files_metadata_newpatient.py`
- **RT Extraction Main Script**: `scripts/extract_radiation_data.py`
- **DocumentReference Analysis**: `docs/DOCUMENT_REFERENCE_RT_ANALYSIS.md`
- **Complete RT Strategy**: `docs/COMPREHENSIVE_RADIATION_EXTRACTION_STRATEGY.md`

---
**Last Updated**: October 12, 2025  
**Status**: Phase 1 Complete - Comprehensive listing with retrieval flags
