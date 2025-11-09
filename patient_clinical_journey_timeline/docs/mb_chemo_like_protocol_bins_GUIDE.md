# Medulloblastoma “Like-Protocol” Binning by Chemotherapy (RxNorm) — Coordinator Agent Guide

## Purpose
This guide instructs an LLM clinical-coordinator agent to abstract FHIR Medication* records (MedicationRequest/Administration/Statement) and **bin patients into treatment categories** that approximate well-known medulloblastoma protocols **based on chemotherapy exposure patterns alone**. Radiation dose/fields and exact dosing are not required, but **timing/sequence** cues are used when necessary.

---

## Data Inputs
- **FHIR resources:** MedicationRequest, MedicationAdministration, MedicationStatement (optionally Procedure for apheresis/ASCR surrogates; Radiotherapy events if available).
- **Normalization:** Map all medications to **RxNorm ingredients (IN)**. Ignore brand names and forms.
- **Time anchors:** Diagnosis date, RT start/stop dates (if available), transplant/ASCR dates (from Procedure/Encounter if present).

---

## Binning Table
Refer to the CSV: **mb_chemo_like_protocol_bins.csv** (columns: protocol_or_context, setting_intent, age_eligibility, defining_agents_rxnorm_ingredients, sequencing_or_timing_cues, alignment_rules_for_LLM, key_sources).

### Age Cues
- **ACNS0331 (average-risk):** 3–21 years.
- **ACNS0332 (high-risk):** pediatric/AYA (~3–21 years).
- **ACNS0334 (young children):** **<36 months.**
- **Head Start III:** **<10 years.**
- **Head Start IV:** **≤10 years** (selected strata, e.g., localized SHH).
- **WNT de-intensification trials:** ACNS1422 (children/AYA), FOR-WNT2 **3–16 years.**
- **Relapse contexts (ACNS0821, MEMMAT):** children and young adults.

### Standard-of-Care Backbones (non-protocol label but widely practiced)
- **Average-risk adjuvant backbone:** cisplatin + lomustine (CCNU) + vincristine **alternating** with cyclophosphamide + vincristine.
- **High-risk radiosensitization practice:** **concurrent carboplatin** during CSI for selected high-risk (particularly Group 3) patients.
- **Infant/young-child RT-avoidant approach:** HD-MTX–containing induction → myeloablative **carboplatin + thiotepa** (± etoposide) with ASCR.
- **Relapse:** temozolomide + irinotecan (± bevacizumab); **MEMMAT** metronomic regimen.

---

## Decision Rules (pseudocode)

1. **Normalize drugs:** to RxNorm IN; create patient-level time series of administrations/requests.
2. **Windowing:**
   - **Induction:** cluster within 6–14 weeks post-op.
   - **Consolidation/HDCT:** detect co-administration of **carboplatin + thiotepa** (± etoposide) with ASCR within 2–6 weeks cycles.
   - **Concurrent-RT check:** any **carboplatin** on days overlapping RT fractions ⇒ flag as “concurrent carboplatin.”
3. **Match Patterns:**
   - **ACNS0331-like:** alternating `(cisplatin + lomustine + vincristine)` with `(cyclophosphamide + vincristine)` within first 6–9 months after RT.
   - **ACNS0332-like:** concurrent carboplatin during RT (ignore isotretinoin).
   - **ACNS0334-like:** 3 cycles induction (cisplatin/cyclophosphamide/vincristine/etoposide ± **HD-MTX**) ⇒ 3 cycles **carboplatin + thiotepa** (± etoposide) with ASCR.
   - **Head Start III/IV-like:** multiple induction cycles containing **HD-MTX** + backbone agents ⇒ single **TICE** (thiotepa+carboplatin+etoposide) consolidation with ASCR (HS-III: ~5 cycles; HS-IV: ~3 cycles).
   - **ACNS1422-like (WNT):** RT present; **no vincristine during RT**; adjuvant maintenance otherwise typical but fewer cycles.
   - **FOR-WNT2-like (WNT):** WNT; reduced-dose CSI + focal RT; maintenance reduced (agents typical of average-risk).
   - **ACNS0821-like (relapse):** **temozolomide + irinotecan**; add “+bev” modifier if bevacizumab also present.
   - **MEMMAT-like (relapse):** **bevacizumab** + {**thalidomide**, **celecoxib**, **fenofibrate**} + alternating **low-dose oral etoposide/cyclophosphamide**, plus **intrathecal etoposide/cytarabine**.
4. **Age sanity-check (non-exclusionary):**
   - If patient age at start of treatment is **<3 years**, favor ACNS0334/Head Start-like bins.
   - If **3–21 years**, favor ACNS0331/0332/WNT trial–like bins based on radiation/sequence.
   - If **>16 years** and WNT de-intensification, likely **not** FOR-WNT2; consider ACNS1422-like if other cues fit.
5. **Confidence scores:**
   - Start at 1.0; subtract 0.2 if RT dates absent but needed for ACNS0332/ACNS1422 calls; subtract 0.2 if ASCR/pheresis surrogate missing for HDCT calls; subtract 0.1 if only one cycle observed for multi-cycle patterns.
6. **Validation prompts (for human coordinator):**
   - Confirm RT dates and whether vincristine was given during RT.
   - Confirm any stem cell collection/ASCR procedures around consolidation.
   - Verify WNT molecular status if de-intensification bin is assigned.

---

## Output Schema (per patient)
- `patient_id`
- `bin_protocol_like` (e.g., “ACNS0331-like”, “ACNS0332-like”, “HeadStart-III-like”, “MEMMAT-like”)
- `rationale` (detected agents + sequence cues + age cue)
- `confidence` (0–1)
- `supporting_medication_events` (list of [ingredient, date])
- `supporting_procedure_events` (ASCR, apheresis, intrathecal ports if present)
- `rt_overlap_flag` (true/false)
- `wnt_status_known` (true/false/unknown)

---

## Caveats
- Dose **intensity** is not encoded by ingredients; “high-dose methotrexate” vs low-dose requires administration dose extraction where available.
- **Cellular therapies** and oncolytic viruses will not be captured by Medication* resources.
- Some protocols (e.g., SJMB03) are **not** chemo-definable from this paper alone (no agent list).

---

## Sources
- ACNS0331 (NCT00085735), average-risk MB: randomized RT fields; adjuvant agents: cisplatin, lomustine, vincristine, cyclophosphamide; age 3–21.  
- ACNS0332 (NCT00392327) high-risk MB: carboplatin concurrent with RT; isotretinoin maintenance tested; pediatric/AYA.  
- ACNS0334: randomized **HD-MTX** in **<36 months**; induction (cisplatin/cyclophosphamide/vincristine/etoposide ± HD-MTX) → myeloablative **carboplatin + thiotepa** with ASCR.  
- Head Start III: young children **<10 y**; induction ×5 with **HD-MTX** backbone → **TICE** (thiotepa+carboplatin+etoposide) with ASCR.  
- Head Start IV (NCT02875314): children **≤10 y**; induction ×3 with HD-MTX backbone → single **TICE**.  
- ACNS1422 (NCT02724579) WNT: reduced CSI (18 Gy), **omit vincristine during RT**.  
- FOR-WNT2 (NCT04474964): **3–16 y**; low-dose CSI + focal RT; fewer maintenance cycles.  
- ACNS0821 (NCT01217437): **temozolomide + irinotecan ± bevacizumab** for recurrent MB/PNET.  
- MEMMAT: bevacizumab + oral **thalidomide/celecoxib/fenofibrate** with alternating low-dose **etoposide/cyclophosphamide** and alternating intrathecal **etoposide/cytarabine**.

---

## Coordinator Checklist
- [ ] Verify age at therapy start; compare with age cues.
- [ ] Confirm RT overlaps (or absence of vincristine during RT for ACNS1422-like).
- [ ] Confirm presence of ASCR/pheresis around consolidation cycles (ACNS0334 / HS-like).
- [ ] Confirm WNT pathway status for de-intensification bins.
- [ ] For relapse, ensure the bin is applied to **post-progression** window.