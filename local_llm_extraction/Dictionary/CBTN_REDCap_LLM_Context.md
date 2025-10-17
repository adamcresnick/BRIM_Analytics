# CBTN REDCap → LLM Context (Structured Protocol Schema)

**Source**: CBTN REDCap Codebook / Data Dictionary (PDF).  
**Compiled**: 2025-10-15T16:26:26Z  
**Purpose**: Give an LLM agent a complete understanding of the forms, events, fields, branching logic, and key relationships in the CBTN observational registry focused on pediatric CNS tumors. This context is designed to be used for:
- reasoning about data entry consistency, QC, and lineage across events;
- mapping EHR → registry variables;
- automating extraction/validation across longitudinal updates and linked forms (diagnosis ↔ treatment ↔ updates ↔ biospecimens).

> **PII/PHI note to agent**: Variables marked *Identifier* or carrying PHI (e.g., dates of birth, names, MRNs) **must not be exposed downstream** outside compliant contexts. Treat any *_id / MRN / date* flagged as PHI with special care.

---

## 1) ARM & EVENT MODEL

**Arms/Events (unique event names & IDs)**
- Enrollment — `enrollment_arm_1` (Event ID: 476003)  
- Demographics — `demographics_arm_1` (Event ID: 476004)  
- Medical History — `medical_history_arm_1` (Event ID: 476005)  
- Diagnoses — `diagnoses_arm_1` (Event ID: 476006)  
- Disease-Related — `diseaserelated_arm_1` (Event ID: 529121)  
- Specimens — `specimens_arm_1` (Event ID: 476007)  
- Radiology Form — `radiology_form_arm_1` (Event ID: 476008)  
- Quality Control — `quality_control_arm_1` (Event ID: 522250)

**Longitudinal updates (timepoints used across multiple instruments)**  
Used to index follow-up forms (Treatment; Updates; Concomitant Meds; etc.). The canonical set:  
`3M, 6M, 12M, 18M, 24M, 30M, 36M, 42M, 48M, 60M, 10Y, 15Y, 20Y`.

---

## 2) INSTRUMENTS (FORMS) & EVENT PLACEMENT

| Instrument (Display) | Instrument (Unique) | Primary Event(s) | Notes |
|---|---|---|---|
| Enrollment | `enrollment` | Enrollment | Subject identifiers, consent metadata, DAG-based visibility, PHI flags |
| Cohort Identification | `cohort_identification` | Enrollment | Marks inclusion in cohort initiatives (e.g., CBTN_D0261; AZ HGG CBTN_0149) |
| Demographics | `demographics` | Demographics | Legal sex, race (checkbox), ethnicity |
| Medical History | `medical_history` | Medical History | Cancer predisposition, family history templates |
| Diagnosis | `diagnosis` | Diagnoses | Core clinical event; WHO CNS5 Dx; grade; tumor site; staging; testing |
| Treatment | `treatment` | Diagnoses | Linked to a specific Diagnosis instance; surgery/radiation/chemo details |
| Updates Data Form | `updates_data_form` | Diagnoses | Follow-up status, clinical/tumor status at visit; linked to Diagnosis |
| CBTN_D0261 – Additional Fields | `additional_fields` | Disease-Related | NF1, OPG, etc. |
| BRAF Alteration Details | `braf_alteration_details` | Disease-Related | BRAF/MAPK alterations & test types; methylation profiling |
| Imaging (Clinical Related) | `imaging_clinical_related` | Disease-Related | Scan date, steroid exposure, global clinical status |
| Ophthalmology Functional Assessment | `ophthalmology_functional_assessment` | Disease-Related | Visual fields, discs, acuity (multiple scales), OCT |
| Hydrocephalus Details | `hydrocephalus_details` | Disease-Related | Event date; diagnosis modality; intervention details |
| Concomitant Medications | `concomitant_medications` | Disease-Related | Linked to Diagnosis instance + timepoint; non-tumor-directed meds |
| Measurements | `measurements` | Disease-Related | Anthropometrics (Ht/Wt/HC) + percentiles |
| Specimen | `specimen` | Specimens | Surgical/non-surgical; donor role; Dx linkage; SOP compliance |
| IDs | `ids` | Enrollment | Site-specific IDs (e.g., CHOP LB ID) |
| Quality Control | `quality_control` | Quality Control | Read-only pointers and QC workflow fields |

---

## 3) CORE ENTITIES & RELATIONSHIPS

### Entity overview
- **SUBJECT** (key: `study_id`; PHI includes `dob`, `mrn`, first/last name, consent date).  
- **DIAGNOSIS EVENT** (repeatable per subject): each has `date_of_event`, `event_type`, WHO CNS5 diagnosis, grade, tumor sites, metastasis, and clinical testing performed.  
- **TREATMENT INSTANCE**: linked to a specific Diagnosis (`tx_dx_link`) and visit/timepoint; captures surgery, extent of resection, specimen routing, radiation (sites/type/dose), chemotherapy (type/protocol/free text), and registries.  
- **FOLLOW-UP UPDATE**: linked to a specific Diagnosis (`update_dx_link`) and timepoint; visit completion, clinical/tumor status.  
- **BIOSPECIMEN EVENT**: for surgical/non-surgical samples; for surgical collections, explicitly linked to a Diagnosis (`sx_dx_link`), with SOP compliance and collection date.  
- **CONCOMITANT MEDICATIONS**: non-tumor-directed med list, linked to a Diagnosis (`conmed_dx_link`) and a timepoint.  
- **DISEASE-RELATED SUBMODULES**: BRAF Alterations; Imaging; Ophthalmology; Hydrocephalus; Measurements; Additional cohort-specific fields.  
- **QUALITY CONTROL**: system-driven references to other forms/timepoints; resolution workflow.

### Relationship map (cardinalities)
- SUBJECT 1—∞ DIAGNOSIS_EVENT  
- DIAGNOSIS_EVENT 1—∞ TREATMENT_INSTANCE  
- DIAGNOSIS_EVENT 1—∞ FOLLOW_UP_UPDATE  
- DIAGNOSIS_EVENT 1—∞ CONCOMITANT_MED_SET (each set has 1..10 meds)  
- DIAGNOSIS_EVENT 1—∞ SPECIMEN (surgery-based collections only; non-surgical collections are subject-level without Dx linkage)  
- SUBJECT 1—∞ DISEASE_RELATED_FORMS (Imaging, Ophtho, Hydrocephalus, etc. are visit- or event-anchored as noted)  
- QUALITY_CONTROL references any of the above by instrument + timepoint + event.

**Link keys (human-readable SQL pickers)**  
- `tx_dx_link` → associates a Treatment instance with a **Diagnoses**-event **instance** (shows strings composed from `date_of_event :: event_type, WHO CNS5 Dx` plus free-text Dx).  
- `update_dx_link` → associates a Follow-up Update to a **Diagnoses** instance.  
- `conmed_dx_link` → associates a ConMeds set to a **Diagnoses** instance.  
- `sx_dx_link` → associates a **surgical** Specimen set to a **Diagnoses** instance.

---

## 4) GLOBAL FIELD CONVENTIONS

- **Required**: many fields are explicitly required (e.g., `study_id`, `subject_consent_date`, `event_type`, `who_cns5_diagnosis`).  
- **Identifiers / PHI**: flagged fields include names, MRN, DOB, applicable dates (`date_ymd`) and some notes fields; some dates carry `@HIDEBUTTON`.  
- **Branching**: *“Show the field ONLY if”* conditions drive visibility; typical patterns:  
  - *_other* text fields gated on an “Other” choice flag.  
  - Detailed panels (e.g., Ophthalmology sub-sections) gated by parent exam selection.  
  - Event-dependent fields (e.g., metastasis sites only if metastasis = Yes).  
  - Site/DAG-based gating for a small number of operational fields (e.g., Return of Results).  
- **Validation**: dates `date_ymd`; numeric fields with implicit units; radio/checkbox/dropdown semantics per REDCap.  
- **Standardized dictionaries**: WHO CNS5 Dx list; tumor location; metastasis sites; radiation sites/units/types; surgery types; chemo type.  
- **None-of-the-above**: some checkbox groups use `@NONEOFTHEABOVE` (e.g., BRAF; Ophthalmology visual fields).

---

## 5) FORM-BY-FORM SCHEMA (SELECTED FIELDS, LOGIC, SEMANTICS)

> The lists below prioritize *relationships, branching logic, and clinically material variables*. Repetitive sub-templates (e.g., Family History and Ophthalmology per-eye/per-method measurements) are summarized with rules.

### A) Enrollment (`enrollment`, Event: Enrollment)
- `study_id` *(Required, Identifier)* — Subject ID.  
- `subject_consent_date` *(Required, Identifier, date_ymd)*.  
- `enrollment_status` *(radio)* — Transfer/Existing vs Prospective.  
- `subject_results_return` *(yesno)* — **Visible only** if site/user DAG in an allowlist (DAG-based logic).  
- `frontier` *(yesno)* — CHOP-only gating via DAG.  
- `phi` *(yesno)* — Whether PHI is included for this subject.  
- `subject_deidentified` *(radio, Required)* — Permanently de-identified vs identifiable.  
- Name/MRN/DOB (Identifiers; several `@READONLY`/`@HIDEBUTTON` annotations).  
- `language` (+ `language_other` if code = “Other”).  
- `autopsy_institution` — Large, enumerated set including U.S. and international centers; default “Not Applicable”.  
- **Form status**: `enrollment_complete`.

### B) Cohort Identification (`cohort_identification`, Event: Enrollment)
- Flags for **CBTN_D0261 Day One LGG** and **CBTN_0149 AZ HGG** including “Removed after data entered” with date & reason fields gated accordingly.  
- **Form status**: `cohort_identification_complete`.

### C) Demographics (`demographics`, Event: Demographics)
- `legal_sex` *(radio, Required)* — Male/Female/Not Available.  
- `race` *(checkbox, Required)* — White, Black, Asian, NH/PI, AI/AN, Other/Unavailable.  
- `ethnicity` *(radio, Required)* — Hispanic/Latino, Not Hispanic/Latino, Unavailable.  
- **Form status**: `demographics_complete`.

### D) Medical History (`medical_history`, Event: Medical History)
- **Cancer Predisposition** (`cancer_predisposition` + optional `cancer_predisposition_other`).  
- `germline` *(yesno)* visible if predisposition group selected; `results_available` *(yesno)* likewise.  
- Family History scaffold:  
  - `family_history` *(radio, Required)* — Yes/No/Unavailable.  
  - If Yes: `family_member` *(checkbox)* to select relatives, with per-relative **cancer type** checkbox panels + free-text “other” when applicable.  
  - Pattern repeats for mother/father/siblings (ordered), grandparents, cousins, “Other 1”, unspecified relation.  
- **Form status**: `medical_history_complete`.

### E) Diagnosis (`diagnosis`, Event: Diagnoses) — **Core clinical event**
- `diagnosis_id` *(Identifier, @HIDDEN)* — warehouse key.  
- `clinical_status_at_event` *(dropdown, Required)* — Alive vs various deceased states; **“Alive” for all surgeries** (autopsy-only deceased).  
- If deceased: `cause_of_death` (free text), `autopsy_performed` (Yes/No), with Gift from a Child referral flag.  
- `event_type` *(radio, Required)* — Initial, Second Malignancy, Recurrence, Progressive, Deceased, Unavailable.  
- If Alive: `medical_conditions_present_at_event` *(checkbox)* with sub-logic (e.g., shunt details, “Other” notes).  
- `date_of_event` *(Required, Identifier, date_ymd)* — must match Specimen form if surgery; autopsy date if deceased without autopsy → date of death.  
- **Diagnosis labels**:  
  - `free_text_diagnosis` *(Required)* — path Dx from referring site.  
  - `who_cns5_diagnosis` *(dropdown, Required)* — **see full list below**.  
  - `who_cns5_diagnosis_other` if “Other/Not primary CNS” is chosen.  
  - Legacy `diagnosis` *(checkbox)* retained/read-only for reference to historical categories + `diagnosis_other` if applicable.  
- **Grading**: `who_grade` *(dropdown)* — 1, 2, 3, 4, 1/2, 3/4, or “No grade specified”.  
- **Anatomy**: `tumor_location` *(checkbox, Required)* + `tumor_location_other`; `metastasis` / `metastasis_location` (+ “Other” notes); `tumor_staging_eval` (+ “Other”).  
- **Progression**: if `event_type = Progressive` → `site_of_progression` (Local/Metastatic/Both/Unavailable).  
- **Molecular/Testing**: `tumor_or_molecular_tests_performed` *(checkbox)* → FISH/ISH, IHC, WES/WGS, panels, fusion panels, etc.; `molecular_test_report_available`; site-only `molecular_sequencing_id` (DGD IDs).  
- `diagnosis_comments` (no PHI).  
- **Form status**: `diagnosis_complete`.

### F) Treatment (`treatment`, Event: Diagnoses) — **Linked to a Diagnosis**
- `treatment_updated` *(Required)* — New/Ongoing/Modified/No treatment/Unavailable.  
- `tx_dx_link` *(SQL pick list, Required)* — **links this Treatment to a Diagnosis**.  
- `treatment_which_visit` — which update visit for the selected Diagnosis (Event, 3M, …, 20Y).  
- If `Modified`, capture `reason_for_treatment_change` (Toxicities/Unspecified/Progression/Recurrence/Second malignancy).  
- **Surgery block**: `surgery` → `surgery_type` (+ `surgery_type_other`); `extent_of_tumor_resection`; `specimen_to_cbtn`; `specimen_collection_origin` (Initial/Repeat/Second look/Recurrence/Progressive/Second malignancy/Autopsy/Unavailable).  
- **Radiation block** (if `radiation = Yes`): start/stop dates (with “unavailable” toggles), `radiation_site` (Focal, CSI+boost, WV+boost, Other), dose & unit logic for CSI/WV vs focal/boost, `radiation_type` (Protons/Photons/Combo/Gamma Knife/Other) + `additional_radiation_description`.  
- **Chemotherapy block** (if `chemotherapy = Yes`):  
  - `chemotherapy_type` (Protocol—enrolled vs not; Other SOC; Unavailable).  
  - If protocol-based → `protocol_name` **(very large enumerated list; see §7)**.  
  - If not protocol-based → list up to 5 `chemotherapy_agent_*` (RxNorm), free-text regimen description; start/stop dates (+ “unavailable” toggles).  
  - `autologous_stem_cell_transplant` flag.  
- **Registries**: enrollment on non-interventional trials (e.g., DIPG Registry) + free text which.  
- **Form status**: `treatment_complete`.

### G) Updates Data Form (`updates_data_form`, Event: Diagnoses) — **Linked to a Diagnosis**
- `update_timepoint` (3M … 20Y).  
- `update_dx_link` *(SQL)* — **links this Update to a Diagnosis**.  
- Visit status (`follow_up_visit_status`), reason not completed, and **Clinical Status** if completed or if known deceased.  
- If alive: `tumor_status` (NED/Stable/Change/Decrease size/Not evaluated by imaging).  
- `coordinator_notes` (site-use-only).  
- **Form status**: `updates_data_form_complete`.

### H) Additional Fields: CBTN_D0261 (`additional_fields`, Event: Disease-Related)
- OPG (optic pathway glioma) & NF1 modules:  
  - `opg` *(Yes/No/Unknown)*; `nf1_yn` w/ diagnosis date (clinical), germline confirmation flag/date, variant found flag, and whether report submitted to CBTN.  
- **Form status**: `additional_fields_complete`.

### I) BRAF Alteration Details (`braf_alteration_details`, Event: Disease-Related)
- `date_specimen_collected`; `braf_alterations` (V600E/V600K, KIAA1549-BRAF, RAF1, Other, None) + “Other” notes, type of tumor characterization test(s) (FISH/Panel/Fusion/WES-WGS/IHC/Microarray/Other), methylation profiling status & result, report submission flag.  
- **Form status**: `braf_alteration_details_complete`.

### J) Imaging (Clinical Related) (`imaging_clinical_related`, Event: Disease-Related)
- `date_scan`; steroid exposure (`cortico_yn`) with up to 5 drugs (RxNorm) and dose/frequency details; keyed overall clinical status (Stable/Improved/Deteriorating/Not Reporting vs prior).  
- Hidden bridge fields to Ophthalmology (“Was assessment completed?”).  
- **Form status**: `imaging_clinical_related_complete`.

### K) Ophthalmology Functional Assessment (`ophthalmology_functional_assessment`, Event: Disease-Related)
- `ophtho_date`; exams performed (Visual Fields, Optic Disc, Visual Acuity, OCT).  
- Visual Fields (per-eye): Normal vs quadrants; `@NONEOFTHEABOVE` used.  
- Optic Disc: Pallor/Edema per eye.  
- **Visual Acuity**: method(s) Teller / Snellen / HOTV / ETDRS / Cardiff / LEA / Other / logMAR.  
  - For each selected method → panel of Left/Right/Both **Dist cc** and **Dist ph cc** values with “Not reported” toggles.  
  - logMAR captured as numeric per eye.  
- OCT: Left/Right in microns (with “Not reported” toggles).  
- **Form status**: `ophthalmology_functional_assessment_complete`.

### L) Hydrocephalus Details (`hydrocephalus_details`, Event: Disease-Related)
- `hydro_yn` + event date; diagnosis method (Clinical / CT / MRI); interventions (Surgical / Medical / Hospitalization / None).  
- **If Surgical**: EVD; ETV; VPS (new or revision); Other + programmable valve flag.  
- **If Medical**: Steroid; Shunt reprogramming; Other.  
- **Form status**: `hydrocephalus_details_complete`.

### M) Concomitant Medications (`concomitant_medications`, Event: Disease-Related)
- `conmed_date` (reconciliation date); `conmed_dx_link` *(SQL)* to Diagnosis; `conmed_timepoint`.  
- `conmed_total` (1..10, “More than 10”, or “None noted”).  
- For each of up to 10 meds: *Medication name only* (RxNorm-guided) + Schedule Category (Scheduled / PRN / Unknown).  
- **Form status**: `concomitant_medications_complete`.

### N) Measurements (`measurements`, Event: Disease-Related)
- `measurement_date` (if any of Ht/Wt/HC available).  
- Checkboxes for which measures are available (Height/Weight/Head Circumference/None).  
- Values (with units) + percentiles.  
- **Form status**: `measurements_complete`.

### O) Specimen (`specimen`, Event: Specimens)
- **Donor**: Subject, Mother, Father, specific sibling order, grandparents, uncles/aunts, Other.  
- If `Other` → `other_donor` free text.  
- If `Subject` → `sample_type` (Surgical vs Non-surgical).  
  - If Surgical → `sx_dx_link` *(SQL)* to Diagnosis instance.  
- `specimen_collection_date` (must align with Diagnosis event date when surgery-derived).  
- Optional `only_specimen_id`; SOP compliance (`specimen_collection_standards` Yes/No/Unavailable).  
- **Form status**: `specimen_complete`.

### P) IDs (`ids`, Event: Enrollment)
- Site-specific IDs (e.g., Seattle COG; CHOP Liquid Biopsy ID with placeholder pattern).  
- **Form status**: `ids_complete`.

### Q) Quality Control (`quality_control`, Event: Quality Control)
- Read-only category (Clinical/Biospecimen/Imaging/Reports), instrument(s) implicated, timepoint, and event type; date of event; direct links to form/subject; query name/description; query status (Unresolved → Resolved) with resolution detail & date (auto @TODAY on resolve), verification note, reviewer comments.  
- **Form status**: `quality_control_complete`.

---

## 6) BRANCHING LOGIC — **Canonical Patterns & Examples**

1) **Alive vs Deceased paths** (Diagnosis):  
   - `clinical_status_at_event = Alive` ⇒ show Medical Conditions (e.g., shunt flags).  
   - Deceased variants ⇒ autopsy flags; Gift from a Child referral; use autopsy/death dates for event date rules.

2) **Event subtype** drives progression site:  
   - If `event_type = Progressive` ⇒ `site_of_progression` required.

3) **Metastasis** gates site checklist and “Other” notes:  
   - `metastasis = Yes` ⇒ `metastasis_location` (CSF/Spine/BM/Brain/Lepto/Other/Unavailable) and, if Other, free-text notes.

4) **Testing performed** gates report availability and sequencing ID:  
   - Panels/WES/WGS/fusion etc. ⇒ `molecular_test_report_available = Yes/No`.  
   - CHOP-only `molecular_sequencing_id` exposed by DAG rule.

5) **Treatment modules** expand based on toggles:  
   - `surgery = Yes` ⇒ surgery type (+ other), extent of resection, specimen routing, collection origin.  
   - `radiation = Yes` ⇒ radiation site(s) + dose fields with “unavailable” toggles and units; radiation type; optional free-text details.  
   - `chemotherapy = Yes` ⇒ chemo **type**: protocol (with or without subject enrollment) or other SOC; if not protocol → up to 5 agents (RxNorm) + regimen narrative; start/stop date capture with “unavailable” toggles.

6) **Linked forms** must point to a **Diagnosis instance** using the SQL pickers:  
   - `tx_dx_link`, `update_dx_link`, `conmed_dx_link`, and `sx_dx_link` present the latest instance labels composed from `date_of_event :: event_type, WHO CNS5 Dx / legacy Dx` to disambiguate repeats.

7) **Family History**:  
   - Selecting a relative in `family_member` opens a per-relative cancer-type checklist including “Other” → description.  
   - Siblings captured in birth order with “(Second)/(Third)” explicit labels to align with biospecimen sibling order rules.

8) **Ophthalmology**:  
   - Selecting a method (e.g., Snellen) opens a panel of Left/Right/Both, each with cc and ph cc; each value is either a free-text string (e.g., `20/40`) or toggled “Not reported”.  
   - logMAR recorded numerically per eye.  
   - OCT recorded in microns per eye.

9) **Hydrocephalus**:  
   - If intervention includes Surgical, show surgical management (EVD/ETV/VPS new or revision/Other) and programmable valve flag.  
   - If intervention includes Medical, show medical management (Steroid/Reprogramming/Other).

10) **DAG-based gating**:  
   - A small number of fields (e.g., Return of Results, CHOP Ops Pathology Review, DGD sequencing ID) restrict visibility to specific site DAGs.

---

## 7) CONTROLLED VOCABULARIES (SELECTED)

> The following are the clinically material enumerations frequently referenced by logic or cross-form relationships. Code → Label format used where codes are meaningful.

### 7.1 Event Type (`event_type`)
- Initial CNS Tumor; Second Malignancy; Recurrence; Progressive; Deceased; Unavailable.

### 7.2 WHO CNS5 Diagnosis (`who_cns5_diagnosis`) — **Abbreviated structure**  
> Full list in the source includes: HGG (IDH-mutant, GBM IDH-wildtype, piloid features…), DMG (H3 K27-altered, H3 G34-mutant…), LGG (pilocytic, MAPK-altered, MYB/MYBL1-altered, SEGA…), Ependymoma (PFA/PFB/ZFTA/YAP1), Medulloblastoma (WNT/SHH TP53-wildtype/TP53-mutant/non-WNT/non-SHH/Groups 3/4), ATRT subgroups, Embryonal tumors (ETMR, FOXR2-activated, BCOR-ITD, pineoblastoma, cribriform neuroepithelial, NOS/NEC), Germ cell (germinoma, NGGCT), Glioneuronal/neuronal (GG, DNET, DLGNT, MVNT, etc.), Craniopharyngioma (adamantinomatous, papillary), Choroid plexus, CNS sarcomas (FET-CREB, CIC, DICER1, Ewing, mesenchymal), and numerous “Other” primary/non-primary CNS entities.  
- Includes options for **NOS/NEC** within each family and **Other/Not a primary CNS tumor** with free-text `who_cns5_diagnosis_other`.

### 7.3 Tumor Location (`tumor_location`)
- Frontal, Temporal, Parietal, Occipital Lobes; Thalamus; Ventricles; Suprasellar/Hypothalamus; Cerebellum/Posterior Fossa; Brainstem (Medulla/Midbrain/Thalamus/Pons); Cervical/Thoracic/Lumbar-Thecal Spinal Cord; Optic Pathway; Cranial Nerves NOS; Other NOS; Spine NOS; Pineal; Basal Ganglia; Hippocampus; Meninges/Dura; Skull; Unavailable.

### 7.4 Metastasis Location (`metastasis_location`)
- CSF, Spine, Bone Marrow, Brain, Leptomeningeal, Other, Unavailable.

### 7.5 Tumor Staging Evaluation (`tumor_staging_eval`)
- MR Brain; MR Spine; CSF Cytology; Other (specify).

### 7.6 Surgery Type (`surgery_type`)
- Craniotomy; Spinal laminectomy; Endoscopic endonasal; Stereotactic guided biopsy; LITT; Other (specify).

### 7.7 Extent of Resection (`extent_of_tumor_resection`)
- Gross/Near total; Partial; Biopsy only; Unavailable; N/A.

### 7.8 Specimen Collection Origin (`specimen_collection_origin`)
- Initial CNS Tumor Surgery; Repeat resection; Second look surgery; Recurrence surgery; Progressive surgery; Second malignancy; Autopsy; Unavailable.

### 7.9 Radiation Sites & Units
- **Sites**: Focal/Tumor bed; Craniospinal with focal boost; Whole Ventricular with focal boost; Other; Unavailable.  
- **Dose units**: cGy; Gy; CGE.  
- **Type**: Protons; Photons; Combination; Gamma Knife; Other.

### 7.10 Chemotherapy Type (`chemotherapy_type`)
- Protocol follows but *not enrolled*; Protocol follows and *enrolled*; Other SOC (non-protocol); Unavailable.  
- **If protocol**: `protocol_name` is a very large dropdown (hundreds of named trials/arms across COG/ACNS/PNOC/PBTC/SJ/etc.). *This context intentionally omits the exhaustive list to preserve prompt budget; treat as a coded label.*

### 7.11 Update Timepoints (`update_timepoint` et al.)
- 3M, 6M, 12M, 18M, 24M, 30M, 36M, 42M, 48M, 60M, 10Y, 15Y, 20Y (some forms hide or limit certain options contextually).

### 7.12 BRAF Alterations (`braf_alterations`) & Test Types (`tumor_char_test`)
- BRAF: V600E; V600K; KIAA1549-BRAF fusion; other BRAF fusion; RAF1 fusion; Other; None.  
- Test Types: FISH/ISH; Somatic Tumor Panel; Fusion Panel; WES/WGS; IHC; Microarray; Other.

### 7.13 Ophthalmology Methods & Findings
- **Methods**: Visual Fields; Optic Disc; Visual Acuity (Teller/Snellen/HOTV/ETDRS/Cardiff/LEA/Other/logMAR); OCT.  
- **Visual Fields (per eye)**: Normal; Quadrant 1–4; Not evaluated; `@NONEOFTHEABOVE` applies.  
- **Optic Disc (per eye)**: Pallor (Present/Absent/Not Evaluated); Edema (Present/Absent/Not Evaluated).  
- **Acuity values**: strings per method and eye (e.g., `20/40`) with “Not reported” toggles; `logMAR` numeric.  
- **OCT**: Left/Right microns with “Not reported” toggles.

### 7.14 Hydrocephalus
- **Diagnosis method**: Clinical; CT; MRI.  
- **Interventions**: Surgical (EVD; ETV; VPS—new/revision; Other) with programmable-valve flag; Medical (Steroid; Shunt reprogramming; Other); Hospitalization; None.

### 7.15 Concomitant Medications
- Up to 10 meds per reconciliation, **RxNorm-coded name only** + schedule (Scheduled/PRN/Unknown).

### 7.16 Measurements
- Height (cm) + percentile; Weight (kg) + percentile; Head Circumference (cm) + percentile; “None available” toggle.

### 7.17 Specimen Donor Categories
- Subject; Mother; Father; Sister/Sister (Second)/Sister (Third); Brother/Brother (Second)/Brother (Third); Maternal/Paternal Grandparents; Maternal/Paternal Aunt/Uncle; Other.

---

## 8) DATA QUALITY & OPERATIONAL ANNOTATIONS

- Many date fields use `@HIDEBUTTON` to discourage UI date-picker; still persist `date_ymd` ISO.  
- Some fields use `@READONLY` (e.g., Ops Pathology review; QC system fields).  
- Some checkbox groups enforce `@NONEOFTHEABOVE`.  
- SQL pickers (`*_dx_link`) are the *authoritative keys* for joining repeat instances across forms.  
- **Specimen↔Diagnosis date consistency**: Surgical specimen collection date must match Diagnosis event date.  
- **Alive-at-surgery rule**: Clinical status for surgery events should be “Alive”; only the deceased record (autopsy) uses deceased statuses.

---

## 9) ER GUIDE (JOIN KEYS & PSEUDO-SQL)

```text
SUBJECT(study_id) 
  ├─< DIAGNOSIS_EVENT(instance_id, study_id, date_of_event, event_type, who_cns5_diagnosis, who_grade, tumor_location, metastasis, ...)
  │     ├─< TREATMENT(instance_id, study_id, tx_dx_link → DIAGNOSIS_EVENT.instance_id, treatment_which_visit, surgery/radiation/chemo fields...)
  │     ├─< UPDATE(instance_id, study_id, update_dx_link → DIAGNOSIS_EVENT.instance_id, update_timepoint, follow_up_visit_status, clinical_status, tumor_status)
  │     ├─< CONMED_SET(instance_id, study_id, conmed_dx_link → DIAGNOSIS_EVENT.instance_id, conmed_timepoint, meds[1..10])
  │     └─< SPECIMEN(instance_id, study_id, sx_dx_link → DIAGNOSIS_EVENT.instance_id when sample_type = Surgical)
  └─< DISEASE_RELATED_FORMS (BRAF / Imaging / Ophtho / Hydro / Measurements / Additional Fields) [subject/timepoint anchored as indicated]
```

Join hint for links (conceptually):
```sql
-- Treatment → Diagnosis
SELECT t.*
FROM treatment t
JOIN diagnosis d
  ON t.tx_dx_link_instance = d.instance_id
 AND t.study_id = d.study_id;
```

---

## 10) VALIDATION & BUSINESS RULE HIGHLIGHTS

- **If `event_type = Initial CNS Tumor`** and `surgery = Yes` → `specimen_collection_origin` should be “Initial CNS Tumor Surgery”.  
- **Dose units** must be provided when CSI/WV doses are captured; focal/boost dose likewise with its own unit.  
- **Protocol vs agents** are mutually informative: if not protocol-based, at least one `chemotherapy_agent_*` should be present when `chemotherapy = Yes` (site coverage allowing).  
- **Update timepoint order** is monotonic per Diagnosis; avoid duplicate timepoints per Diagnosis.  
- **Hydrocephalus**: Surgical implies hospitalization; programmable valve not applicable if no shunt.  
- **Ophthalmology**: A method must be selected to expose its corresponding measurement fields; avoid leaving all values empty without “Not reported” toggles when method selected.

---

## 11) APPENDIX — NOTES ON LARGE ENUMERATIONS

- **`protocol_name`**: very large curated list (hundreds) spanning COG/ACNS/PNOC/PBTC/SJ/INDIGO/NCI-MATCH and others, often with arms/strata. Preserve as a *code → label* dictionary in implementation. For LLM use, treat as a categorical label and do not reason on pharmacologic content unless additionally provided.

---

## 12) QUICK START PROMPTS (FOR AGENTS)

- *“Given a Treatment record, find the linked diagnosis and return the triad {date_of_event, event_type, who_cns5_diagnosis}.”*  
- *“Validate a surgical Specimen: ensure `sx_dx_link` exists and `specimen_collection_date == diagnosis.date_of_event`.”*  
- *“List all Updates for a Diagnosis in chronological timepoint order, with clinical and tumor status summaries.”*  
- *“For a subject with OPG and NF1, summarize ophthalmology results across all methods as of latest visit.”*

---

**End of context.**
