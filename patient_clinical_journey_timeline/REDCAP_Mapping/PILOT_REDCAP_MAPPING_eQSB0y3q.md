# REDCap Mapping Pilot: eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83

## 1. Pilot Summary

This document represents a simulated data mapping from the patient's `timeline_artifact.json` to the CBTN REDCap project. The mapping was **partially successful**. 

Key diagnostic and demographic data was mapped with high confidence. However, the pilot revealed **significant data gaps** in the source JSON artifact, primarily related to **missing event dates and failed binary extractions (e.g., Extent of Resection)**. These gaps prevent the complete population of the REDCap record and must be addressed in the underlying abstraction pipeline.

## 2. Key Findings & Challenges

*   **High-Confidence Success:** Core demographic data and the primary WHO CNS5 diagnosis, including grade and key molecular markers, were mapped successfully.
*   **Critical Gap - Event Dates:** A majority of events in the `timeline_events` array are missing `event_date`. This is the most critical issue, as it makes it impossible to populate dates for surgeries, radiation, chemo, or follow-up, and prevents chronological ordering.
*   **Critical Gap - Failed Extractions:** The pipeline identified 73 gaps but failed to fill them (e.g., `extent_of_tumor_resection`, `total_radiation_dose`). This is a primary blocker for populating treatment forms.
*   **Schema Discrepancy:** The JSON artifact appears to use an older data schema. It is missing the `v4` feature objects (like `extent_of_resection_v4`, `v41_tumor_location`) that were described in the project documentation. The mapping logic had to fall back to less structured fields.
*   **Vocabulary Mismatch:** A pathology report mentions "corpus callosum tumor," but this is not an option in the REDCap `tumor_location` dropdown. This requires a manual mapping rule.

## 3. Form-by-Form Simulated Mapping

Below is a summary of what would be populated in REDCap, instance by instance.

--- 

### **Form: `enrollment` & `demographics` (Instance 1)**

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `mrn` | `eQSB0y3q.OmvN40Yhg9.eCBk5-9c-Qp-FT3pBWoSGuL83` | **SUCCESS** |
| `dob` | `""` | **GAP - Missing Data** |
| `legal_sex` | `0` (Male) | **SUCCESS** |
| `race` | `7` (Other) | **SUCCESS** |
| `ethnicity` | `2` (Not Hispanic or Latino) | **SUCCESS** |


### **Form: `diagnosis` (Instance 1: Initial Diagnosis)**

*   **Triggering Event:** Initial diagnosis derived from the `who_2021_classification` block.

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `date_of_event` | `2017-09-27` | **SUCCESS (Inferred)**¹ |
| `event_type` | `5` (Initial CNS Tumor) | **SUCCESS** |
| `who_cns5_diagnosis` | `20` (Astrocytoma, IDH-mutant) | **SUCCESS** |
| `who_grade` | `3` (Grade 3) | **SUCCESS** |
| `tumor_location` | `17` (Other locations NOS) | **SUCCESS (Requires Rule)**² |
| `tumor_location_other`| `Corpus callosum` | **SUCCESS (Requires Rule)**² |
| `metastasis` | `1` (No) | **SUCCESS (Assumed)**³ |

¹*Note: No surgery or pathology dates were present in the JSON. This date was inferred from the text of a pathology report (`Date Reported: 09/27/2017`).*
²*Note: Inferred from pathology report text. Requires a mapping rule for "Corpus callosum" -> "Other".*
³*Note: No evidence of metastatic disease was found in the timeline; defaulted to 'No'.*

### **Form: `medical_history` (Instance 1)**

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `cancer_predisposition` | `1` (NF-1) | **SUCCESS**⁴ |
| `germline` | `0` (No) | **SUCCESS**⁵ |

⁴*Note: The `NF1` checkbox is selected based on the `p.Arg1534*` and `p.Arg1968*` variants found in the `molecular_markers` array.*
⁵*Note: Based on the direct Athena query returning no results for germline tests.*

### **Form: `treatment` (Instance 1: First Surgery)**

*   **Triggering Event:** First `surgery` event in `timeline_events`.

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `tx_dx_link` | `[Instance 1 of Diagnosis Form]` | **SUCCESS** |
| `surgery` | `1` (Yes) | **SUCCESS** |
| `date_at_surgery_start` | `2017-09-27` | **SUCCESS (Inferred)**¹ |
| `surgery_type` | `1` (Craniotomy) | **SUCCESS** |
| `extent_of_tumor_resection` | `null` | **GAP - Extraction Failed** |

### **Form: `treatment` (Instance 2: First Radiation)**

*   **Triggering Event:** First `radiation_start` event in `timeline_events`.

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `tx_dx_link` | `[Instance 1 of Diagnosis Form]` | **SUCCESS** |
| `radiation` | `0` (Yes) | **SUCCESS** |
| `date_at_radiation_start` | `""` | **GAP - Missing Data** |
| `total_radiation_dose` | `null` | **GAP - Extraction Failed** |

### **Form: `treatment` (Instance 3: First Chemotherapy)**

*   **Triggering Event:** First `chemotherapy_start` event in `timeline_events`.

| REDCap Variable | Mapped Value | Status |
| :--- | :--- | :--- |
| `tx_dx_link` | `[Instance 1 of Diagnosis Form]` | **SUCCESS** |
| `chemotherapy` | `0` (Yes) | **SUCCESS** |
| `date_at_chemotherapy_start` | `""` | **GAP - Missing Data** |
| `chemotherapy_agent_1` | `nivolumab` | **SUCCESS** |

---

## 4. Recommendations

1.  **Enhance the Pipeline:** The highest priority is to fix the core pipeline (`patient_timeline_abstraction_V3.py`) to ensure **event dates** are correctly populated from the Athena views and that the **binary extraction gap-filling process** (Phase 4) is functioning as intended. The failure to extract EOR and radiation dose is a critical limitation.

2.  **Update Data Model:** The pipeline should be updated to produce the latest JSON schema, including the `v4` feature objects, to enable more robust, provenance-tracked mapping.

3.  **Implement Mapping Rules:** The `map_to_redcap.py` script should include a small rules engine to handle vocabulary mismatches, such as mapping "Corpus callosum" to the "Other" location field.

This pilot demonstrates that the overall strategy is sound, but its success is entirely dependent on the quality and completeness of the input `timeline_artifact.json`. Addressing the data gaps in the source artifact is the necessary next step before proceeding with a live REDCap integration.