# Medulloblastoma Protocol Mapping Pilot

This workspace packages the Athena extracts, tooling, and outputs for classifying CBCT medulloblastoma patients into ACNS/NCCN-aligned chemotherapy regimens. Data was generated on 2025‑11‑09 using the `343218191717_AWSAdministratorAccess` SSO profile and the pediatric CNS SNOMED cohort (`peds_cns_codeset_unique3.csv`).

## Directory Layout
```
medulloblastoma_protocol_mapping/
├── data/
├── outputs/
│   └── latest/
└── scripts/
```

### Data Assets (`./data`)
| File | Description | Athena View / Script |
| --- | --- | --- |
| `medulloblastoma_patient_ids.csv` | 167 FHIR patient IDs pulled from the pediatric CNS SNOMED enrichment. | `snomed_peds_cns_enrichment.py`
| `mb_chemo_medications.csv` | Chemotherapy administrations with ingredient mapping, care-plan context, and RxNorm provenance. | `fhir_prd_db.v_chemo_medications`
| `mb_radiation_episodes_athena.csv` | CSI dose, boost details, appointment/care-plan enrichment. | `fhir_prd_db.v_radiation_episode_enrichment`
| `mb_procedures_athena.csv` | Procedure catalog for ASCR/pheresis detection. | `fhir_prd_db.v_procedures_tumor`
| `mb_demographics_athena.csv` | Patient ages/sex/race for age gating. | `fhir_prd_db.v_patient_demographics`
| `v_chemotherapy_drugs.csv` | Reference ingredient dictionary. | `fhir_prd_db.v_chemotherapy_drugs`
| `v_chemotherapy_rxnorm_codes.csv` | Product→ingredient RxNorm mapping. | `fhir_prd_db.v_chemotherapy_rxnorm_codes`

### Script (`./scripts`)
`prototype_mb_protocol_mapper.py` performs all rule-based classification. It:
1. Normalizes chemo agents using both RxNorm codes and the `chemo_preferred_name` annotations from `v_chemo_medications`.
2. Pulls radiation, procedure, and demographic context to detect CSI dose brackets, carboplatin overlap, ASCR evidence, and age-appropriate protocol windows.
3. Emits both definitive labels (`ACNS0821-like`, `ACNS0331-like`, `NCCN Group 3/4 High-Risk`, etc.) and “potential” cohorts listing missing evidence (e.g., `POTENTIAL_NEEDS_RADIATION_METADATA`).

Run from the repo root:
```bash
python RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/scripts/prototype_mb_protocol_mapper.py \
  --meds RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/mb_chemo_medications.csv \
  --chemo-drugs RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/v_chemotherapy_drugs.csv \
  --chemo-map RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/v_chemotherapy_rxnorm_codes.csv \
  --radiation RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/mb_radiation_episodes_athena.csv \
  --procedures RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/mb_procedures_athena.csv \
  --demographics RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/data/mb_demographics_athena.csv \
  --output-dir RADIANT_PCA/BRIM_Analytics/patient_clinical_journey_timeline/medulloblastoma_protocol_mapping/outputs/latest
```

### Outputs (`./outputs/latest`)
The latest run produces:
- `mb_protocol_assignments.csv` – patient-level classifications with confidence, rationale, supporting events, and potential-match metadata.
- `mb_protocol_assignment_summary.json` – aggregate counts (`POTENTIAL_ACNS0331-like`, `ACNS0821-like (+bevacizumab)`, etc.) plus timestamp.

### Process Summary
1. **Cohort ID** – derived from the pediatric CNS SNOMED enrichment (`medulloblastoma_patient_ids.csv`).
2. **Athena Extractions** – run via AWS CLI to pull chemo, radiation, procedure, and demographics into `./data`.
3. **Classification Script** – executed as shown above to produce the current `outputs/latest` files.
4. **Iteration** – the script was updated to surface potential cohorts (missing radiation, alternating cycle evidence, carboplatin CSI overlap) and age-gated logic following NCCN guidance.

### Next Steps
- Backfill radiation metadata for the `POTENTIAL_NEEDS_RADIATION_METADATA` group so they can move into ACNS0331/0332 categories.
- Implement alternating-cycle detection / CSI dose thresholds inside the script to graduate `POTENTIAL_ACNS0331-like` patients into confident bins.
- Continue improving ASCR detection and HD-MTX consolidation timing for younger patients.
