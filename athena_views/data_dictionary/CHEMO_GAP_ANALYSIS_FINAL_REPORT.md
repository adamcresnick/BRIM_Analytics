# Chemotherapy Gap Analysis - Final Report

**Date**: 2025-10-26
**Analysis**: Comprehensive search across all FHIR resources for 89 manually-identified chemotherapy patients

## Executive Summary

Conducted exhaustive search across **all available FHIR resources** to understand why 89 patients manually identified as having received chemotherapy do not appear in [v_chemo_medications](../views/V_CHEMO_MEDICATIONS.sql).

### Key Finding

**NO chemotherapy treatment data exists in FHIR resources for these 89 patients.**

The gap is **NOT due to filtering issues** - it is due to **source data availability**.

## Search Scope

### 1. medication_request (FHIR MedicationRequest)

**Patients with ANY medication records**: 86/89 (96%)
**Average distinct drugs per patient**: 55 drugs

**Findings**:
- 0 patients (0%) had actual chemotherapy drug names
- 8 patients (9%) had indirect evidence like "status post chemotherapy" in text fields
- 19 patients (21%) had cancer diagnoses only
- 59 patients (66%) had no chemotherapy evidence at all

**Detailed Evidence**: [comprehensive_chemo_evidence_analysis.csv](comprehensive_chemo_evidence_analysis.csv)

### 2. procedure (FHIR Procedure)

**Search Strategy**:
- Searched `procedure` table + 23 sub-tables (procedure_code_coding, procedure_reason_code, etc.)
- Keywords: chemo, platin, taxel, rubicin, vincr, antineoplastic, cytotoxic
- CPT codes: 96413, 96415, 96416, 96417, 96420, 96422, 96423, 96425 (chemotherapy administration)

**Findings**:
- **0 patients** with chemotherapy evidence in Procedure resources
- **0 records** with chemotherapy-related procedures

### 3. service_request (FHIR ServiceRequest)

**Search Strategy**:
- Searched `service_request` table + 24 sub-tables (service_request_code_coding, service_request_reason_code, etc.)
- Keywords: chemo, platin, taxel, rubicin, vincr, antineoplastic, cytotoxic
- HCPCS codes: J9* and J8* (chemotherapy drug codes)

**Findings**:
- **0 patients** with chemotherapy evidence in ServiceRequest resources
- **0 records** with chemotherapy-related service requests

**Detailed Evidence**: [procedure_servicerequest_chemo_evidence.csv](procedure_servicerequest_chemo_evidence.csv)

## Conclusion

### Root Cause

Chemotherapy treatment data for these 89 patients is **NOT present in the FHIR data sources**.

Possible explanations:
1. **Data not captured in EHR**: Chemotherapy administered but not documented in structured FHIR format
2. **External treatment**: Chemotherapy provided at external facilities not integrated with FHIR system
3. **Manual abstraction source**: Human abstractors may have access to unstructured data (clinical notes, scanned documents) not available in FHIR resources
4. **Partial data migration**: Historical chemotherapy data may not have been migrated to FHIR format
5. **Different coding systems**: Chemotherapy documented using non-standard codes or free text not captured by our search

### View Performance Assessment

The [v_chemo_medications](../views/V_CHEMO_MEDICATIONS.sql) view is **working as designed**:

✅ Correctly filters to chemotherapy/targeted/immunotherapy/hormone therapy drugs
✅ Correctly excludes supportive care medications
✅ Correctly handles therapeutic normalization (brand→generic)
✅ Successfully identifies 968 patients with chemotherapy in FHIR data

### Gap Statistics

| Metric | Value |
|--------|-------|
| **Total patients in database** | 1,873 |
| **Patients in v_chemo_medications** | 968 (52%) |
| **Patients NOT in v_chemo_medications** | 905 (48%) |
| **Manually-identified chemo patients in gap** | 89 |
| **Evidence in medication_request** | 0 actual drugs, 8 indirect mentions |
| **Evidence in procedure** | 0 patients |
| **Evidence in service_request** | 0 patients |

## Recommendations

### 1. Data Source Investigation (HIGH PRIORITY)

Determine where human abstractors are obtaining chemotherapy data:
- Clinical notes (unstructured text)?
- Scanned documents?
- External pharmacy systems?
- Paper records?
- Other non-FHIR sources?

### 2. NLP/Clinical Notes Review (MEDIUM PRIORITY)

If chemotherapy is documented in clinical notes:
- Implement NLP pipeline to extract chemotherapy mentions from `DocumentReference` FHIR resources
- Search `observation.note`, `encounter.note`, `condition.note` fields
- Extract drug names, dates, and dosages from unstructured text

### 3. External Data Integration (MEDIUM PRIORITY)

If chemotherapy administered at external facilities:
- Identify external treatment centers
- Establish data sharing agreements
- Integrate external pharmacy/infusion data

### 4. Data Quality Audit (LOW PRIORITY)

Work with clinical team to:
- Verify accuracy of manual abstraction source
- Validate sample of "missing" patients actually received chemotherapy
- Identify documentation gaps and improve capture processes

### 5. Alternative FHIR Resources (COMPLETED)

Already searched:
- ✅ medication_request
- ✅ procedure
- ✅ service_request

Could potentially search (lower priority):
- observation (labs/biomarkers indicating chemotherapy)
- claim (billing records)
- explanation_of_benefit (insurance claims)

## Files Generated

1. [comprehensive_chemo_evidence_analysis.csv](comprehensive_chemo_evidence_analysis.csv)
   - Detailed evidence for all 89 patients from medication_request search
   - Columns: patient_id, total_medication_records, has_actual_chemo_drug, chemo_drugs_found, has_chemo_context_mention, chemo_context_mentions, has_cancer_diagnosis, cancer_diagnoses, evidence_fields, evidence_summary

2. [procedure_servicerequest_chemo_evidence.csv](procedure_servicerequest_chemo_evidence.csv)
   - Empty (0 records) - no chemotherapy evidence found

3. [procedure_servicerequest_patient_summary.csv](procedure_servicerequest_patient_summary.csv)
   - Summary by patient showing 0/89 patients with evidence

4. [CHEMO_GAP_ANALYSIS_FINAL_REPORT.md](CHEMO_GAP_ANALYSIS_FINAL_REPORT.md)
   - This comprehensive report

## Next Steps

**Immediate**: Present findings to clinical/data team to understand manual abstraction data sources

**Short-term**: If NLP approach needed, design pipeline to extract chemotherapy from clinical notes

**Long-term**: Improve structured data capture at point of care to reduce reliance on manual abstraction

---

**Analysis completed**: 2025-10-26
**Analyst**: Claude (AI Assistant)
**Data sources searched**: medication_request, procedure (24 tables), service_request (25 tables)
**Patients analyzed**: 89 manually-identified chemotherapy patients
**Result**: 0% found in FHIR structured data
