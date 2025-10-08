# Gold Standard CSV Inventory

**Generation Date**: 2025-10-07T08:03:08.524257
**CSV Directory**: `data/20250723_multitab_csvs`
**Total CSV Files**: 18

---

## Summary Table

| CSV Name | Rows | Columns | Size (MB) | Completeness | Status |
|----------|------|---------|-----------|--------------|--------|
| `additional_fields` | 189 | 8 | 0.02 | 100.0% | ✅ Analyzed |
| `braf_alteration_details` | 232 | 10 | 0.03 | 99.7% | ✅ Analyzed |
| `concomitant_medications` | 9,548 | 8 | 0.92 | 100.0% | ✅ Analyzed |
| `conditions_predispositions` | 1,064 | 6 | 0.09 | 100.0% | ✅ Analyzed |
| `data_dictionary` | 67 | 13 | 0.03 | 60.16% | ✅ Analyzed |
| `data_dictionary_custom_forms` | 111 | 12 | 0.03 | 62.92% | ✅ Analyzed |
| `demographics` | 189 | 4 | 0.01 | 100.0% | ✅ Analyzed |
| `diagnosis` | 1,689 | 20 | 0.43 | 97.85% | ✅ Analyzed |
| `encounters` | 1,717 | 8 | 0.16 | 97.75% | ✅ Analyzed |
| `family_cancer_history` | 242 | 6 | 0.02 | 100.0% | ✅ Analyzed |
| `hydrocephalus_details` | 277 | 10 | 0.04 | 99.8% | ✅ Analyzed |
| `imaging_clinical_related` | 4,035 | 21 | 1.17 | 100.0% | ✅ Analyzed |
| `measurements` | 7,814 | 9 | 0.7 | 100.0% | ✅ Analyzed |
| `molecular_characterization` | 52 | 2 | 0.0 | 100.0% | ✅ Analyzed |
| `molecular_tests_performed` | 131 | 3 | 0.0 | 100.0% | ✅ Analyzed |
| `ophthalmology_functional_asses` | 1,258 | 57 | 1.09 | 100.0% | ✅ Analyzed |
| `survival` | 189 | 6 | 0.0 | 100.0% | ✅ Analyzed |
| `treatments` | 695 | 27 | 0.25 | 100.0% | ✅ Analyzed |

---

## Detailed Analysis


### additional_fields.csv

**File**: `20250723_multitab__additional_fields.csv`  
**Rows**: 189  
**Columns**: 8  
**Size**: 0.02 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 100 | C1264809, C16974 |
| `optic_pathway_glioma` | object | 0.0% | 2 | No, No |
| `nf1_yn` | object | 0.0% | 2 | No, No |
| `age_at_nf1_diagnosis_date_clinical` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `nf1_germline_genetic_testing` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `age_at_nf1_diagnosis_date_germline` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `pathogenic_nf1_variant` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `nf1_germline_report_submitted` | object | 0.0% | 1 | Not Applicable, Not Applicable |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_nf1_diagnosis_date_clinical`, `age_at_nf1_diagnosis_date_germline`

#### Categorical Fields

**`optic_pathway_glioma`** (2 unique values):
  - `Yes`: 56
  - `No`: 44
**`nf1_yn`** (2 unique values):
  - `No`: 99
  - `Not Reported`: 1
**`age_at_nf1_diagnosis_date_clinical`** (1 unique values):
  - `Not Applicable`: 100
**`nf1_germline_genetic_testing`** (1 unique values):
  - `Not Applicable`: 100
**`age_at_nf1_diagnosis_date_germline`** (1 unique values):
  - `Not Applicable`: 100
**`pathogenic_nf1_variant`** (1 unique values):
  - `Not Applicable`: 100
**`nf1_germline_report_submitted`** (1 unique values):
  - `Not Applicable`: 100

---


### braf_alteration_details.csv

**File**: `20250723_multitab__braf_alteration_details.csv`  
**Rows**: 232  
**Columns**: 10  
**Size**: 0.03 MB  
**Completeness**: 99.7%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 89 | C73062, C107625 |
| `age_at_specimen_collection` | float64 | 0.0% | 99 | 1083.0, 5859.0 |
| `braf_alteration_list` | object | 0.0% | 7 | BRAF V600E Mutation, BRAF V600E Mutation |
| `braf_fusion_other` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `braf_alterations_other` | object | 0.0% | 7 | Not Applicable, Not Applicable |
| `tumor_char_test_list` | object | 3.0% | 16 | Microarray, FISH/ISH;IHC (Immunohistochemistry) |
| `tumor_char_test_other` | object | 0.0% | 5 | Not Applicable, Not Applicable |
| `methyl_profiling_yn` | object | 0.0% | 3 | No, No |
| `methyl_profiling_detail` | object | 0.0% | 8 | Not Applicable, Not Applicable |
| `braf_reports_submitted_to_cbtn` | object | 0.0% | 2 | Yes, Yes |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_specimen_collection`

#### Categorical Fields

**`braf_alteration_list`** (7 unique values):
  - `KIAA1549-BRAF fusion`: 43
  - `BRAF V600E Mutation`: 33
  - `None identified`: 13
  - `Other`: 6
  - `Other BRAF Fusion`: 2
**`braf_fusion_other`** (3 unique values):
  - `Not Applicable`: 98
  - `ANTXR1 - BRAF fusion`: 1
  - `GTF2I - BRAF fusion`: 1
**`braf_alterations_other`** (7 unique values):
  - `Not Applicable`: 93
  - `BRAF duplication`: 2
  - `BRAF p.A598_T599insV`: 1
  - `KRAS c.198_227dup \r\n(p.Met67_Glu76dup) mutation \r\n`: 1
  - `BRAF duplication - BRAF (NM_004333.5), c.1794_1796dup (p.Thr599dup)\r\n\r\nfrom 11/26/2019 path report`: 1
**`tumor_char_test_list`** (16 unique values):
  - `Fusion Panel;Somatic Tumor Panel`: 41
  - `Somatic Tumor Panel`: 16
  - `FISH/ISH`: 7
  - `Whole Exome/Whole Genome`: 7
  - `Other`: 6
**`tumor_char_test_other`** (5 unique values):
  - `Not Applicable`: 93
  - `SNP`: 3
  - `NGS`: 2
  - `The BRAF Mutation Testing assay utilizes real-time PCR amplification of  a portion of exon 15 of the BRAF gene using specific PCR primers`: 1
  - `spinal cord biopsy`: 1
**`methyl_profiling_yn`** (3 unique values):
  - `No`: 86
  - `Yes`: 7
  - `Unknown`: 7
**`methyl_profiling_detail`** (8 unique values):
  - `Not Applicable`: 93
  - `Inconclusive`: 1
  - `"The methylation profile did not show a consistent match across the versions 11b6, 12b6 of the Heidelberg classifier or the NCI classifier. In the v11b6 classifier, Diffuse leptomeningeal glioneuronal tumor was given a suggestive score (<0.84). However, the tumor does not have chromosome 1p loss, which would be expected for this tumor type. In support of DLGNT is the presence of a BRAF fusion, although this is not specific for this tumor type. Given the lack of a specific methylation class in this case, diagnostic considerations include a variant of DLGNT versus another histologically low-grade glial or glioneuronal tumor type."\r\n \r\n \r\nWhile this tumor with radiographic evidence of dissemination shows both histologic and immunohistochemical features of a diffuse leptomeningeal glioneuronal tumor (DLGNT) as well as a MAPK pathway alteration, the tumor does not have chromosome 1p loss. 1p loss is currently considered to be an essential diagnostic criteria for DLGNT (WHO 5th edition). Therefore, this histologically low-grade disseminated neoplasm is best classified as a glial/glioneuronal tumor, NEC (Not Elsewhere Classified). This neoplasm may represent a variant of DLGNT versus another histologically low-grade glial/glioneuronal tumor type with dissemination. \r\n`: 1
  - `DNA methylation array analysis of this tumor, using v12.8 of the Heidelberg Classifier, did not find a match with established calibration score cutoff. The closest match of this tumor is low-grade glial/glioneuronal/neuroepithelial tumors super family with a score of 0.60 and pilocytic astrocytoma family with a score of 0.55.`: 1
  - `DNA methylation array analysis of this tumor, using v12.8 of the Heidelberg classifier, matched this tumor to the family pilocytic astrocytoma with a score >0.99 and the subclass pilocytic astrocytoma, infratentorial with a score of 0.99. These results are consistent with the histological diagnosis of Pilocytic Astrocytoma.`: 1
**`braf_reports_submitted_to_cbtn`** (2 unique values):
  - `Yes`: 89
  - `No`: 11

---


### concomitant_medications.csv

**File**: `20250723_multitab__concomitant_medications.csv`  
**Rows**: 9,548  
**Columns**: 8  
**Size**: 0.92 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `event_id` | object | 0.0% | 5 | ET_7DK4B210, ET_7DK4B210 |
| `conmed_timepoint` | object | 0.0% | 7 | Event Diagnosis, Event Diagnosis |
| `research_id` | object | 0.0% | 3 | C1003557, C1003557 |
| `form_conmed_number` | object | 0.0% | 8 | conmed_1, conmed_2 |
| `age_at_conmed_date` | int64 | 0.0% | 21 | 2321, 2321 |
| `rxnorm_cui` | int64 | 0.0% | 25 | 1116927, 203171 |
| `medication_name` | object | 0.0% | 25 | dexamethasone phosphate 4 MG/ML Injectable Solu... |
| `conmed_routine` | object | 0.0% | 3 | Scheduled, Scheduled |

**Identifier Fields**: `event_id`, `research_id`
**Date Fields**: `conmed_timepoint`, `age_at_conmed_date`

#### Categorical Fields

**`event_id`** (5 unique values):
  - `ET_48S336XH`: 41
  - `ET_7DK4B210`: 31
  - `ET_DRY10WQM`: 16
  - `ET_44SR1SDC`: 11
  - `ET_66WQ2FWX`: 1
**`conmed_timepoint`** (7 unique values):
  - `6 Month Update`: 23
  - `Event Diagnosis`: 20
  - `12 Month Update`: 17
  - `18 Month Update`: 16
  - `24 Month Update`: 16
**`research_id`** (3 unique values):
  - `C1003557`: 58
  - `C1003680`: 41
  - `C102459`: 1
**`form_conmed_number`** (8 unique values):
  - `conmed_1`: 21
  - `conmed_2`: 15
  - `conmed_3`: 14
  - `conmed_4`: 11
  - `conmed_5`: 11
**`conmed_routine`** (3 unique values):
  - `Scheduled`: 47
  - `As needed (PRN)`: 42
  - `Unknown`: 11

---


### conditions_predispositions.csv

**File**: `20250723_multitab__conditions_predispositions.csv`  
**Rows**: 1,064  
**Columns**: 6  
**Size**: 0.09 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 17 | C1003557, C1003557 |
| `event_id` | object | 0.0% | 57 | ET_7DK4B210, ET_7DK4B210 |
| `age_at_event_days` | int64 | 0.0% | 57 | 2321, 2321 |
| `cancer_predisposition` | object | 0.0% | 1 | None documented, None documented |
| `medical_conditions_present_at_event` | object | 0.0% | 13 | Developmental delay, Focal neurological deficit... |
| `medical_conditions_present_at_event_other` | object | 0.0% | 13 | Not Applicable, Not Applicable |

**Identifier Fields**: `research_id`, `event_id`
**Date Fields**: `age_at_event_days`

#### Categorical Fields

**`research_id`** (17 unique values):
  - `C1254354`: 25
  - `C111807`: 10
  - `C107625`: 8
  - `C1046730`: 8
  - `C1031970`: 7
**`cancer_predisposition`** (1 unique values):
  - `None documented`: 100
**`medical_conditions_present_at_event`** (13 unique values):
  - `Focal neurological deficit (cranial nerve palsies, motor deficits, sensory deficits)`: 20
  - `Visual deficit (acuity or fields)`: 15
  - `Hydrocephalus`: 14
  - `Developmental delay`: 12
  - `Other medical conditions NOS`: 12
**`medical_conditions_present_at_event_other`** (13 unique values):
  - `Not Applicable`: 88
  - `Had a fall where he struck his head, which brought him to the hospital. Hearing loss (unilateral left) worsened after fall.`: 1
  - `minimal/no hearing from left ear.`: 1
  - `Ehlers Danlos Syndrome`: 1
  - `Small weight gain`: 1

---


### data_dictionary.csv

**File**: `20250723_multitab__data_dictionary.csv`  
**Rows**: 67  
**Columns**: 13  
**Size**: 0.03 MB  
**Completeness**: 60.16%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `Variable / Field Name` | object | 0.0% | 66 | research_id, legal_sex |
| `Tab` | object | 1.49% | 9 | demographics, demographics |
| `CollectionForm Name` | object | 2.99% | 8 | all, demographics |
| `Field Type` | object | 8.96% | 5 | text, dropdown |
| `Field Label` | object | 10.45% | 58 | Study Subject ID, Gender (Legal Sex) |
| `Choices, Calculations, OR Slider Labels` | object | 41.79% | 34 | 0, Male | 1, Female | 2, Unavailable, 1, White ... |
| `Field Note` | object | 65.67% | 15 | Clinical status should be marked "Alive" for al... |
| `Branching Logic (Show field only if...)` | object | 38.81% | 28 | [formstatus_demo] = '1' or [formstatus_demo] = ... |
| `Required Field?` | object | 52.24% | 1 | y, y |
| `post-data entry coding logic` | object | 95.52% | 3 | when medical_conditions_present_at_event_other ... |
| `Field Description` | object | 13.43% | 57 | The CBTN unique research id for the subject., R... |
| `Comments` | object | 89.55% | 6 | Transformed into age in days, The value selecti... |
| `Unnamed: 12` | object | 97.01% | 1 | y, y |

**Identifier Fields**: `Choices, Calculations, OR Slider Labels`

#### Categorical Fields

**`Tab`** (9 unique values):
  - `treatment`: 26
  - `diagnosis`: 15
  - `encounters`: 7
  - `family_cancer_history`: 5
  - `survival`: 5
**`CollectionForm Name`** (8 unique values):
  - `treatment`: 25
  - `diagnosis`: 19
  - `updates`: 6
  - `family_cancer_history`: 5
  - `survival`: 5
**`Field Type`** (5 unique values):
  - `text`: 21
  - `radio`: 18
  - `checkbox`: 10
  - `dropdown`: 9
  - `notes`: 3
**`Field Note`** (15 unique values):
  - `Entered as yyyy-mm-dd. Converted to age in days`: 6
  - `No PHI should be listed here (including dates)`: 3
  - `Mother`: 2
  - `Clinical status should be marked "Alive" for all surgeries; only use "Deceased" choices for the deceased record (i.e., autopsy collection). `: 1
  - `Not all tests are always listed within the path report. Please check other areas of the subject's EMR.`: 1
**`Required Field?`** (1 unique values):
  - `y`: 32
**`post-data entry coding logic`** (3 unique values):
  - `when medical_conditions_present_at_event_other is null then 'Not Applicable'
else medical_conditions_present_at_event_other`: 1
  - `Events relevant to EFS calculation include the following:
	- Progressive/Progression
	- Recurrence
	- Secondary malignancy
	- Deceased (event type) + Death due to disease (clinical_status_at_event)

EFS is calculated as: 
	The difference between the age at initial diagnosis and either:
	- the earliest event (as listed above)
- if no event is recorded, then the last known survival

All fields needed to validate/"self calculate" this are present in the data `: 1
  - `when clinical_status is null then 'Not Applicable'
else clinical_status`: 1
**`Comments`** (6 unique values):
  - `Transformed into age in days`: 2
  - `The value selection in this field is also used to populate cns_integrated_category`: 1
  - `This field is not independently collected. It is a derived field, based on the selection made for cns_integrated_diagnosis.  See cell E13 for selection values.`: 1
  - `This field is provided solely for row ordering purposes, so that information can be sorted and displayed in a more logical order for participants who have multiple treatment records. This field is not intended for analysis uses.`: 1
  - `this indicates which CBTN follow up timepoint the visit is closest to, relative to the event shown in the event_id column.  A participant may have multiple follow up time points for their initial diagnosis event, such as 6 months, 12 months, 24 months. If they then have a progression event, the follow up time points will "start over" and will be relative to the progression event. The value in the event_id column will change to indicate we are now tracking a new event, and the follow up time points will start over. Note that the value in this column does not indicate the exact date of the follow up, but rather it is the update descriptor selected during data entry for record keeping purposes.`: 1
**`Unnamed: 12`** (1 unique values):
  - `y`: 2

---


### data_dictionary_custom_forms.csv

**File**: `20250723_multitab__data_dictionary_custom_forms.csv`  
**Rows**: 111  
**Columns**: 12  
**Size**: 0.03 MB  
**Completeness**: 62.92%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `Variable / Field Name` | object | 0.0% | 100 | optic_pathway_glioma, nf1_yn |
| `Tab` | object | 0.0% | 6 | additional_fields, additional_fields |
| `CollectionForm Name` | object | 0.0% | 5 | additional_fields, additional_fields |
| `Field Type` | object | 0.0% | 5 | radio, radio |
| `Field Label` | object | 5.0% | 95 | Does the patient have Optic Pathway Glioma or a... |
| `Choices, Calculations, OR Slider Labels` | object | 69.0% | 16 | 1, Yes | 2, No | 3, Unknown, 1, Yes | 2, No | 3... |
| `Field Note` | object | 95.0% | 3 | (NF1 is often diagnosed by clinical features, n... |
| `Branching Logic (Show field only if...)` | object | 28.0% | 60 | [cortico_yn] = '1', [cortico_number] = '1' or [... |
| `Required Field?` | object | 98.0% | 1 | y, y |
| `post-data entry coding logic` | object | 51.0% | 2 | Convert date to age in days, Convert date to ag... |
| `Field Description` | object | 1.0% | 87 | Confirmation of Optic Pathway Glioma, Confirmat... |
| `Comments` | object | 98.0% | 2 | Defaulted to 0 if subject is confirmed to not b... |

**Identifier Fields**: `Choices, Calculations, OR Slider Labels`

#### Categorical Fields

**`Tab`** (6 unique values):
  - `ophthalmology_functional_assessment`: 42
  - `imaging_clinical_related`: 20
  - `ophthalmology_functional_assessment	`: 14
  - `braf_alteration_details`: 9
  - `hydrocephalus_details`: 8
**`CollectionForm Name`** (5 unique values):
  - `ophthalmology_functional_assessment	`: 56
  - `imaging_clinical_related`: 20
  - `braf_alteration_details`: 9
  - `hydrocephalus_details`: 8
  - `additional_fields`: 7
**`Field Type`** (5 unique values):
  - `text`: 70
  - `radio`: 15
  - `checkbox`: 10
  - `notes`: 3
  - `dropdown`: 2
**`Choices, Calculations, OR Slider Labels`** (16 unique values):
  - `1, Yes | 2, No | 3, Unknown`: 7
  - `BIOPORTAL:RXNORM`: 5
  - `1, Present | 2, Absent | 3, Not Evaluated`: 4
  - `1, Yes | 0, No`: 2
  - `1, Normal | 2, quadrant 1/Inferior Temporal | 3, quadrant 2/Inferior Nasal | 4, quadrant 3/Superior Temporal | 5, quadrant 4/Superior Nasal | 6, Not evaluated`: 2
**`Field Note`** (3 unique values):
  - `Fixed Unit: logMAR. Typically between -10 and +10`: 2
  - `microns`: 2
  - `(NF1 is often diagnosed by clinical features, not germline testing)`: 1
**`Required Field?`** (1 unique values):
  - `y`: 2
**`post-data entry coding logic`** (2 unique values):
  - `When "Not Reported" option is selected during data entry, new value "Confirmed Not Reported" appears`: 44
  - `Convert date to age in days`: 5
**`Comments`** (2 unique values):
  - `Defaulted to 0 if subject is confirmed to not be on corticosteroids`: 1
  - `This field is logically derived based on the presence of ophthalmology functional assessment forms.  If there is a form dated within the 90 days prior to the imaging date, this field is "yes" otherwise this field is "no"`: 1

---


### demographics.csv

**File**: `20250723_multitab__demographics.csv`  
**Rows**: 189  
**Columns**: 4  
**Size**: 0.01 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 100 | C1003557, C1003680 |
| `legal_sex` | object | 0.0% | 2 | Male, Female |
| `race` | object | 0.0% | 5 | White, White |
| `ethnicity` | object | 0.0% | 3 | Not Hispanic or Latino, Not Hispanic or Latino |

**Identifier Fields**: `research_id`

#### Categorical Fields

**`legal_sex`** (2 unique values):
  - `Male`: 55
  - `Female`: 45
**`race`** (5 unique values):
  - `White`: 70
  - `Other/Unavailable/Not Reported`: 20
  - `Black or African American`: 4
  - `Asian`: 4
  - `American Indian or Alaska Native`: 2
**`ethnicity`** (3 unique values):
  - `Not Hispanic or Latino`: 79
  - `Hispanic or Latino`: 19
  - `Unavailable`: 2

---


### diagnosis.csv

**File**: `20250723_multitab__diagnosis.csv`  
**Rows**: 1,689  
**Columns**: 20  
**Size**: 0.43 MB  
**Completeness**: 97.85%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 16 | C1003557, C1003557 |
| `event_id` | object | 0.0% | 50 | ET_7DK4B210, ET_DRY10WQM |
| `autopsy_performed` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `clinical_status_at_event` | object | 0.0% | 2 | Alive, Alive |
| `cause_of_death` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `event_type` | object | 0.0% | 5 | Initial CNS Tumor, Progressive |
| `age_at_event_days` | int64 | 0.0% | 50 | 2321, 3177 |
| `cns_integrated_category` | object | 0.0% | 3 | Low-Grade Glioma, Low-Grade Glioma |
| `cns_integrated_diagnosis` | object | 0.0% | 4 | Pilocytic astrocytoma, Pilocytic astrocytoma |
| `who_grade` | object | 0.0% | 4 | 1, 1 |
| `metastasis` | object | 0.0% | 3 | No, No |
| `metastasis_location` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `metastasis_location_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `site_of_progression` | object | 0.0% | 3 | Not Applicable, Local |
| `tumor_or_molecular_tests_performed` | object | 43.0% | 6 | Specific gene mutation analysis, SNP array |
| `tumor_or_molecular_tests_performed_other` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `tumor_location` | object | 0.0% | 12 | Brain Stem-Medulla, Brain Stem-Medulla |
| `tumor_location_other` | object | 0.0% | 4 | Not Applicable, Not Applicable |
| `shunt_required` | object | 0.0% | 4 | Not Applicable, Not Applicable |
| `shunt_required_other` | object | 0.0% | 2 | Not Applicable, Not Applicable |

**Identifier Fields**: `research_id`, `event_id`
**Date Fields**: `age_at_event_days`

#### Categorical Fields

**`research_id`** (16 unique values):
  - `C107625`: 17
  - `C102459`: 9
  - `C1031970`: 9
  - `C114759`: 9
  - `C1026189`: 7
**`autopsy_performed`** (2 unique values):
  - `Not Applicable`: 97
  - `No`: 3
**`clinical_status_at_event`** (2 unique values):
  - `Alive`: 97
  - `Deceased-due to disease`: 3
**`cause_of_death`** (1 unique values):
  - `Not Applicable`: 100
**`event_type`** (5 unique values):
  - `Progressive`: 42
  - `Initial CNS Tumor`: 41
  - `Recurrence`: 12
  - `Deceased`: 3
  - `Second Malignancy`: 2
**`cns_integrated_category`** (3 unique values):
  - `Low-Grade Glioma`: 81
  - `High-Grade Glioma`: 10
  - `Glioneuronal and neuronal tumors`: 9
**`cns_integrated_diagnosis`** (4 unique values):
  - `Pilocytic astrocytoma`: 63
  - `Pleomorphic xanthoastrocytoma`: 17
  - `Low-Grade Glioma, NOS or NEC`: 11
  - `Ganglioglioma`: 9
**`who_grade`** (4 unique values):
  - `1`: 76
  - `2`: 8
  - `No grade specified`: 8
  - `3`: 8
**`metastasis`** (3 unique values):
  - `No`: 89
  - `Yes`: 9
  - `Unavailable`: 2
**`metastasis_location`** (3 unique values):
  - `Not Applicable`: 91
  - `Leptomeningeal`: 5
  - `Brain`: 4
**`metastasis_location_other`** (1 unique values):
  - `Not Applicable`: 100
**`site_of_progression`** (3 unique values):
  - `Not Applicable`: 58
  - `Local`: 41
  - `Both local and metastatic`: 1
**`tumor_or_molecular_tests_performed`** (6 unique values):
  - `Specific gene mutation analysis`: 30
  - `FISH`: 12
  - `SNP array`: 10
  - `Whole Genome Sequencing`: 2
  - `Other NOS`: 2
**`tumor_or_molecular_tests_performed_other`** (3 unique values):
  - `Not Applicable`: 98
  - `GFAP is strongly expressed, Ki67 expression is low.`: 1
  - `IHC`: 1
**`tumor_location`** (12 unique values):
  - `Temporal Lobe`: 23
  - `Suprasellar/Hypothalamic/Pituitary`: 20
  - `Cerebellum/Posterior Fossa`: 18
  - `Ventricles`: 10
  - `Brain Stem-Medulla`: 7
**`tumor_location_other`** (4 unique values):
  - `Not Applicable`: 95
  - `Cerebellar Peduncle`: 2
  - `Left hemisphere`: 2
  - `Cerebellar peduncle, Medullary Cistern`: 1
**`shunt_required`** (4 unique values):
  - `Not Applicable`: 89
  - `Ventriculo-Peritoneal Shunt (VPS)`: 4
  - `Not Done`: 4
  - `Other`: 3
**`shunt_required_other`** (2 unique values):
  - `Not Applicable`: 94
  - `EVD`: 6

---


### encounters.csv

**File**: `20250723_multitab__encounters.csv`  
**Rows**: 1,717  
**Columns**: 8  
**Size**: 0.16 MB  
**Completeness**: 97.75%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 10 | C1003557, C1003557 |
| `event_id` | object | 0.0% | 27 | ET_7DK4B210, ET_7DK4B210 |
| `age_at_encounter` | float64 | 18.0% | 82 | 2491.0, 2645.0 |
| `clinical_status` | object | 0.0% | 3 | Alive, Alive |
| `follow_up_visit_status` | object | 0.0% | 2 | Visit Completed, Visit Completed |
| `update_which_visit` | object | 0.0% | 9 | 6 Month Update, 12 Month Update |
| `tumor_status` | object | 0.0% | 4 | Stable Disease, Decrease in tumor size |
| `orig_event_date_for_update_ordering_only` | float64 | 0.0% | 27 | 2321.0, 2321.0 |

**Identifier Fields**: `research_id`, `event_id`
**Date Fields**: `age_at_encounter`, `update_which_visit`, `orig_event_date_for_update_ordering_only`

#### Categorical Fields

**`research_id`** (10 unique values):
  - `C102459`: 14
  - `C107625`: 13
  - `C1003557`: 11
  - `C1031970`: 11
  - `C1046730`: 11
**`clinical_status`** (3 unique values):
  - `Alive`: 82
  - `Not Applicable`: 17
  - `Deceased-due to disease`: 1
**`follow_up_visit_status`** (2 unique values):
  - `Visit Completed`: 82
  - `Subject not seen or followed by another institution for treatment`: 18
**`update_which_visit`** (9 unique values):
  - `6 Month Update`: 27
  - `12 Month Update`: 21
  - `18 Month Update`: 16
  - `24 Month Update`: 12
  - `36 Month Update`: 10
**`tumor_status`** (4 unique values):
  - `Stable Disease`: 65
  - `Not Applicable`: 18
  - `Decrease in tumor size`: 14
  - `Change in tumor status or 2nd malignancy`: 3

---


### family_cancer_history.csv

**File**: `20250723_multitab__family_cancer_history.csv`  
**Rows**: 242  
**Columns**: 6  
**Size**: 0.02 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 79 | C1003557, C1003680 |
| `family_history` | object | 0.0% | 3 | Yes, Yes |
| `family_member` | object | 0.0% | 9 | Other, Unspecified relation |
| `other_family_description` | object | 0.0% | 13 | Paternal great grandmother, Not Applicable |
| `cancer_type` | object | 0.0% | 12 | CNS, Unavailable/Not Specified |
| `other_cancer_description` | object | 0.0% | 13 | Not Applicable, Not Applicable |

**Identifier Fields**: `research_id`

#### Categorical Fields

**`family_history`** (3 unique values):
  - `Yes`: 53
  - `No`: 43
  - `Not Available`: 4
**`family_member`** (9 unique values):
  - `Not Applicable`: 47
  - `Other`: 17
  - `Maternal Grandmother`: 10
  - `Paternal Grandmother`: 7
  - `Unspecified relation`: 6
**`other_family_description`** (13 unique values):
  - `Not Applicable`: 83
  - `Paternal aunt (breast) and Paternal uncle (spine)`: 2
  - `Maternal Great Aunt (Breast); Parental Great Grandfather (Prostate)`: 2
  - `Several Grandparents and uncles`: 2
  - `Maternal Aunt 1 Maternal 2`: 2
**`cancer_type`** (12 unique values):
  - `Not Applicable`: 47
  - `Other`: 14
  - `CNS`: 8
  - `Breast`: 8
  - `Unavailable/Not Specified`: 5
**`other_cancer_description`** (13 unique values):
  - `Not Applicable`: 86
  - `Leukemia`: 2
  - `Not Reported`: 2
  - `Pituitary cyst`: 1
  - `Testicular (Paternal Uncle)`: 1

---


### hydrocephalus_details.csv

**File**: `20250723_multitab__hydrocephalus_details.csv`  
**Rows**: 277  
**Columns**: 10  
**Size**: 0.04 MB  
**Completeness**: 99.8%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 70 | C1003557, C102459 |
| `hydro_yn` | object | 0.0% | 3 | No, Yes |
| `age_at_hydro_event_date` | object | 0.0% | 60 | Not Applicable, 1984 |
| `hydro_method_diagnosed` | object | 0.0% | 9 | Not Applicable, Diagnostic imaging MRI |
| `hydro_intervention` | object | 2.0% | 7 | Not Applicable, Hospitalization;Surgical |
| `hydro_surgical_management` | object | 0.0% | 12 | Not Applicable, Other, specify |
| `hydro_surgical_management_other` | object | 0.0% | 12 | Not Applicable, Tumor Resection |
| `hydro_shunt_programmable` | object | 0.0% | 5 | Not Applicable, Not applicable, no shunt |
| `hydro_nonsurg_management` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `hydro_nonsurg_management_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_hydro_event_date`

#### Categorical Fields

**`hydro_yn`** (3 unique values):
  - `Yes`: 59
  - `No`: 40
  - `Unknown`: 1
**`hydro_method_diagnosed`** (9 unique values):
  - `Not Applicable`: 41
  - `Diagnostic imaging MRI`: 27
  - `Clinical`: 9
  - `Clinical;Diagnostic imaging CT`: 7
  - `Clinical;Diagnostic imaging MRI`: 6
**`hydro_intervention`** (7 unique values):
  - `Not Applicable`: 41
  - `Hospitalization;Surgical`: 31
  - `Surgical`: 15
  - `Hospitalization;Medical;Surgical`: 8
  - `Hospitalization;Medical`: 1
**`hydro_surgical_management`** (12 unique values):
  - `Not Applicable`: 45
  - `Ventriculoperitoneal Shunt (VPS) placement`: 18
  - `Temporary External Ventricular Drain (EVD) removed without need for permanent shunt`: 10
  - `Ventriculoperitoneal Shunt (VPS) revision`: 10
  - `Other, specify`: 6
**`hydro_surgical_management_other`** (12 unique values):
  - `Not Applicable`: 89
  - `Tumor Resection`: 1
  - `urgent tumor debulking`: 1
  - `s/p R occipital EVD removal (2/3)`: 1
  - `s/p EVD replacement in OR (2/8)`: 1
**`hydro_shunt_programmable`** (5 unique values):
  - `Not Applicable`: 59
  - `Unknown`: 15
  - `No`: 15
  - `Yes`: 7
  - `Not applicable, no shunt`: 4
**`hydro_nonsurg_management`** (2 unique values):
  - `Not Applicable`: 90
  - `Steroid`: 10
**`hydro_nonsurg_management_other`** (1 unique values):
  - `Not Applicable`: 100

---


### imaging_clinical_related.csv

**File**: `20250723_multitab__imaging_clinical_related.csv`  
**Rows**: 4,035  
**Columns**: 21  
**Size**: 1.17 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 5 | C1003557, C1003557 |
| `age_at_date_scan` | float64 | 0.0% | 100 | 2317.0, 2334.0 |
| `cortico_yn` | object | 0.0% | 2 | No, No |
| `cortico_number` | int64 | 0.0% | 3 | 0, 0 |
| `cortico_1_rxnorm_cui` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `cortico_1_name` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `cortico_1_dose` | object | 0.0% | 5 | Not Applicable, Not Applicable |
| `cortico_2_rxnorm_cui` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `cortico_2_name` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `cortico_2_dose` | object | 0.0% | 5 | Not Applicable, Not Applicable |
| `cortico_3_rxnorm_cui` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_3_name` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_3_dose` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_4_rxnorm_cui` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_4_name` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_4_dose` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_5_rxnorm_cui` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_5_name` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `cortico_5_dose` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_imaging_yn` | object | 0.0% | 2 | No, No |
| `imaging_clinical_status` | object | 0.0% | 4 | Stable, Improved |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_date_scan`

#### Categorical Fields

**`research_id`** (5 unique values):
  - `C102459`: 32
  - `C1026189`: 23
  - `C1003557`: 22
  - `C1003680`: 13
  - `C1031970`: 10
**`cortico_yn`** (2 unique values):
  - `No`: 86
  - `Yes`: 14
**`cortico_1_rxnorm_cui`** (3 unique values):
  - `Not Applicable`: 86
  - `1116927`: 8
  - `197782`: 6
**`cortico_1_name`** (3 unique values):
  - `Not Applicable`: 86
  - `dexamethasone phosphate 4 MG/ML Injectable Solution`: 8
  - `hydrocortisone 10 MG Oral Tablet`: 6
**`cortico_1_dose`** (5 unique values):
  - `Not Applicable`: 86
  - `10 mg TAB; Stress / Sick Dose as needed: Morning 2 1/2 tablet(s) = 25 mg. Afternoon 2 1/2 tablet(s) = 25 mg. Evening 2 1/2 tablet(s) = 25 mg.`: 6
  - `4 mg/mL SOLUTION; 0 INVALID ONCE PRN`: 5
  - `4 mg/mL SOLUTION; 4 mg EVERY 6 HOURS`: 2
  - `20 mg/5mL SOLUTION; 10 mg ONCE`: 1
**`cortico_2_rxnorm_cui`** (3 unique values):
  - `Not Applicable`: 88
  - `238755`: 6
  - `1116927`: 6
**`cortico_2_name`** (3 unique values):
  - `Not Applicable`: 88
  - `hydrocortisone 100 MG Injection`: 6
  - `dexamethasone phosphate 4 MG/ML Injectable Solution`: 6
**`cortico_2_dose`** (5 unique values):
  - `Not Applicable`: 88
  - `100mg/2mL RECON SOLN; Inject 2 mL (100 mg total) into muscle once as needed for Other (vomiting or severe stress).`: 6
  - `4 mg/mL SOLUTION; 4 mg EVERY 6 HOURS`: 3
  - `4 mg/mL SOLUTION; 4 mg ONCE`: 2
  - `4 mg/mL SOLUTION; 0 INVALID ONCE PRN`: 1
**`cortico_3_rxnorm_cui`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_3_name`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_3_dose`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_4_rxnorm_cui`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_4_name`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_4_dose`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_5_rxnorm_cui`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_5_name`** (1 unique values):
  - `Not Applicable`: 100
**`cortico_5_dose`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_imaging_yn`** (2 unique values):
  - `No`: 90
  - `Yes`: 10
**`imaging_clinical_status`** (4 unique values):
  - `Stable`: 58
  - `Not Reporting compared to prior scan visit`: 33
  - `Improved`: 5
  - `Deteriorating`: 4

---


### measurements.csv

**File**: `20250723_multitab__measurements.csv`  
**Rows**: 7,814  
**Columns**: 9  
**Size**: 0.7 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 1 | C1003557, C1003557 |
| `age_at_measurement_date` | float64 | 0.0% | 99 | 2309.0, 2317.0 |
| `measurement_available` | object | 0.0% | 1 | Not Reported, Not Reported |
| `height_cm` | object | 0.0% | 67 | 115.2, 116.2 |
| `height_percentile` | object | 0.0% | 1 | Not Reported, Not Reported |
| `weight_kg` | float64 | 0.0% | 49 | 18.1, 18.5 |
| `weight_percentile` | object | 0.0% | 1 | Not Reported, Not Reported |
| `head_circumference_cm` | object | 0.0% | 2 | Not Reported, Not Reported |
| `head_circumference_percentile` | object | 0.0% | 1 | Not Reported, Not Reported |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_measurement_date`

#### Categorical Fields

**`research_id`** (1 unique values):
  - `C1003557`: 100
**`measurement_available`** (1 unique values):
  - `Not Reported`: 100
**`height_percentile`** (1 unique values):
  - `Not Reported`: 100
**`weight_percentile`** (1 unique values):
  - `Not Reported`: 100
**`head_circumference_cm`** (2 unique values):
  - `Not Reported`: 99
  - `51`: 1
**`head_circumference_percentile`** (1 unique values):
  - `Not Reported`: 100

---


### molecular_characterization.csv

**File**: `20250723_multitab__molecular_characterization.csv`  
**Rows**: 52  
**Columns**: 2  
**Size**: 0.0 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 52 | C3418293, C2647698 |
| `mutation` | object | 0.0% | 14 | CRKL-RAF1 Fusion,  BRAF V600E |

**Identifier Fields**: `research_id`

#### Categorical Fields

**`mutation`** (14 unique values):
  - ` KIAA1549-BRAF`: 22
  - ` BRAF V600E`: 10
  - `KIAA1549-BRAF`: 6
  - `V600E`: 4
  - `CRKL-RAF1 Fusion`: 1

---


### molecular_tests_performed.csv

**File**: `20250723_multitab__molecular_tests_performed.csv`  
**Rows**: 131  
**Columns**: 3  
**Size**: 0.0 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 50 | C1003557, C1003680 |
| `assay` | object | 0.0% | 7 | Comprehensive Solid Tumor Panel, Comprehensive ... |
| `assay_type` | object | 0.0% | 2 | clinical, clinical |

**Identifier Fields**: `research_id`

#### Categorical Fields

**`assay`** (7 unique values):
  - `WGS`: 25
  - `Comprehensive Solid Tumor Panel T/N Pair`: 22
  - `Comprehensive Solid Tumor Panel`: 20
  - `RNA-Seq`: 20
  - `Methylation`: 9
**`assay_type`** (2 unique values):
  - `research`: 57
  - `clinical`: 43

---


### ophthalmology_functional_asses.csv

**File**: `20250723_multitab__ophthalmology_functional_asses.csv`  
**Rows**: 1,258  
**Columns**: 57  
**Size**: 1.09 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 9 | C1003680, C1003680 |
| `age_at_ophtho_date` | int64 | 0.0% | 100 | 3407, 3449 |
| `ophtho_exams` | object | 0.0% | 9 | Optical Coherence Tomography (OCT);Visual Acuit... |
| `ophtho_field_left` | object | 0.0% | 5 | Normal, Normal |
| `ophtho_field_right` | object | 0.0% | 3 | Normal, Normal |
| `ophtho_pallor_left` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_edema_left` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_pallor_right` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_edema_right` | object | 0.0% | 4 | Not Applicable, Not Applicable |
| `ophtho_assessment` | object | 0.0% | 12 | Snellen, Snellen |
| `ophtho_assessment_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_teller` | object | 0.0% | 15 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_teller` | object | 0.0% | 4 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_teller` | object | 0.0% | 13 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_teller` | object | 0.0% | 4 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_teller` | object | 0.0% | 9 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_teller` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_snellen` | object | 0.0% | 32 | 20/30, 20/40 |
| `ophtho_acuity_left_ph_cc_snellen` | object | 0.0% | 16 | NI, 20/25 +2 |
| `ophtho_acuity_right_cc_snellen` | object | 0.0% | 44 | 20/80, 20/50 -1 |
| `ophtho_acuity_right_ph_cc_snellen` | object | 0.0% | 20 | 20/70, NI |
| `ophtho_acuity_both_cc_snellen` | object | 0.0% | 6 | Confirmed Not Reported, Confirmed Not Reported |
| `ophtho_acuity_both_ph_cc_snellen` | object | 0.0% | 4 | Confirmed Not Reported, Confirmed Not Reported |
| `ophtho_acuity_left_cc_hotv` | object | 0.0% | 10 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_hotv` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_hotv` | object | 0.0% | 12 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_hotv` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_hotv` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_hotv` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_etdrs` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_etdrs` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_etdrs` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_etdrs` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_etdrs` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_etdrs` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_cardiff` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_lea` | object | 0.0% | 6 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_lea` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_lea` | object | 0.0% | 6 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_lea` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_lea` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_lea` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_left_ph_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_right_ph_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_acuity_both_ph_cc_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_logmar_left` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_logmar_right` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `ophtho_oct_left` | object | 0.0% | 16 | 96, Not Applicable |
| `ophtho_oct_right` | object | 0.0% | 16 | 67, Not Applicable |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_ophtho_date`

#### Categorical Fields

**`research_id`** (9 unique values):
  - `C116850`: 26
  - `C1152018`: 21
  - `C114759`: 18
  - `C1003680`: 12
  - `C1072314`: 11
**`ophtho_exams`** (9 unique values):
  - `Visual Acuity Exam (Scores)`: 35
  - `Optic Disc Exam;Visual Acuity Exam (Scores);Visual Fields Exam (Deficits)`: 22
  - `Optical Coherence Tomography (OCT);Visual Acuity Exam (Scores)`: 10
  - `Optical Coherence Tomography (OCT);Optic Disc Exam;Visual Acuity Exam (Scores);Visual Fields Exam (Deficits)`: 10
  - `Optical Coherence Tomography (OCT);Visual Acuity Exam (Scores);Visual Fields Exam (Deficits)`: 7
**`ophtho_field_left`** (5 unique values):
  - `Not Applicable`: 56
  - `Normal`: 38
  - `quadrant 1/Inferior Temporal`: 4
  - `quadrant 1/Inferior Temporal;quadrant 3/Superior Temporal`: 1
  - `quadrant 1/Inferior Temporal;quadrant 2/Inferior Nasal`: 1
**`ophtho_field_right`** (3 unique values):
  - `Not Applicable`: 56
  - `Normal`: 40
  - `Not evaluated`: 4
**`ophtho_pallor_left`** (3 unique values):
  - `Not Applicable`: 57
  - `Present`: 41
  - `Not Evaluated`: 2
**`ophtho_edema_left`** (3 unique values):
  - `Not Applicable`: 57
  - `Not Evaluated`: 32
  - `Absent`: 11
**`ophtho_pallor_right`** (3 unique values):
  - `Not Applicable`: 57
  - `Present`: 41
  - `Not Evaluated`: 2
**`ophtho_edema_right`** (4 unique values):
  - `Not Applicable`: 57
  - `Not Evaluated`: 32
  - `Absent`: 10
  - `Present`: 1
**`ophtho_assessment`** (12 unique values):
  - `Snellen`: 47
  - `HOTV;Snellen`: 16
  - `Teller`: 12
  - `HOTV`: 6
  - `HOTV;Teller`: 5
**`ophtho_assessment_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_left_cc_teller`** (15 unique values):
  - `Not Applicable`: 78
  - `20/24`: 4
  - `20/16`: 3
  - `Confirmed Not Reported`: 3
  - `20/94`: 2
**`ophtho_acuity_left_ph_cc_teller`** (4 unique values):
  - `Not Applicable`: 78
  - `Confirmed Not Reported`: 20
  - `20/30`: 1
  - `20/40 -2`: 1
**`ophtho_acuity_right_cc_teller`** (13 unique values):
  - `Not Applicable`: 78
  - `20/16`: 4
  - `Confirmed Not Reported`: 4
  - `20/24`: 3
  - `13.0 cy/cm_20/47`: 2
**`ophtho_acuity_right_ph_cc_teller`** (4 unique values):
  - `Not Applicable`: 78
  - `Confirmed Not Reported`: 20
  - `20/30`: 1
  - `20/30 -2`: 1
**`ophtho_acuity_both_cc_teller`** (9 unique values):
  - `Not Applicable`: 78
  - `Confirmed Not Reported`: 8
  - `20/16`: 4
  - `20/63`: 4
  - `20/130`: 2
**`ophtho_acuity_both_ph_cc_teller`** (2 unique values):
  - `Not Applicable`: 78
  - `Confirmed Not Reported`: 22
**`ophtho_acuity_left_ph_cc_snellen`** (16 unique values):
  - `Confirmed Not Reported`: 35
  - `Not Applicable`: 32
  - `NI`: 11
  - `20/25 +2`: 2
  - `20/30`: 2
**`ophtho_acuity_both_cc_snellen`** (6 unique values):
  - `Confirmed Not Reported`: 63
  - `Not Applicable`: 32
  - `Not Reported`: 2
  - `NI`: 1
  - `6/19`: 1
**`ophtho_acuity_both_ph_cc_snellen`** (4 unique values):
  - `Confirmed Not Reported`: 66
  - `Not Applicable`: 32
  - `NI`: 1
  - `Not Reported`: 1
**`ophtho_acuity_left_cc_hotv`** (10 unique values):
  - `Not Applicable`: 70
  - `20/25`: 6
  - `20/20`: 6
  - `20/50`: 6
  - `20/32`: 3
**`ophtho_acuity_left_ph_cc_hotv`** (2 unique values):
  - `Not Applicable`: 70
  - `Confirmed Not Reported`: 30
**`ophtho_acuity_right_cc_hotv`** (12 unique values):
  - `Not Applicable`: 70
  - `20/63`: 8
  - `20/50`: 7
  - `20/32`: 4
  - `20/80`: 2
**`ophtho_acuity_right_ph_cc_hotv`** (2 unique values):
  - `Not Applicable`: 70
  - `Confirmed Not Reported`: 30
**`ophtho_acuity_both_cc_hotv`** (2 unique values):
  - `Not Applicable`: 70
  - `Confirmed Not Reported`: 30
**`ophtho_acuity_both_ph_cc_hotv`** (2 unique values):
  - `Not Applicable`: 70
  - `Confirmed Not Reported`: 30
**`ophtho_acuity_left_cc_etdrs`** (3 unique values):
  - `Not Applicable`: 98
  - `20/32`: 1
  - `20/20`: 1
**`ophtho_acuity_left_ph_cc_etdrs`** (2 unique values):
  - `Not Applicable`: 98
  - `Confirmed Not Reported`: 2
**`ophtho_acuity_right_cc_etdrs`** (3 unique values):
  - `Not Applicable`: 98
  - `20/100`: 1
  - `20/63`: 1
**`ophtho_acuity_right_ph_cc_etdrs`** (2 unique values):
  - `Not Applicable`: 98
  - `Confirmed Not Reported`: 2
**`ophtho_acuity_both_cc_etdrs`** (2 unique values):
  - `Not Applicable`: 98
  - `Confirmed Not Reported`: 2
**`ophtho_acuity_both_ph_cc_etdrs`** (2 unique values):
  - `Not Applicable`: 98
  - `Confirmed Not Reported`: 2
**`ophtho_acuity_left_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_left_ph_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_right_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_right_ph_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_both_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_both_ph_cc_cardiff`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_left_cc_lea`** (6 unique values):
  - `Not Applicable`: 94
  - `20/25`: 2
  - `20/20`: 1
  - `20/30`: 1
  - `20/30 + 1`: 1
**`ophtho_acuity_left_ph_cc_lea`** (2 unique values):
  - `Not Applicable`: 94
  - `Confirmed Not Reported`: 6
**`ophtho_acuity_right_cc_lea`** (6 unique values):
  - `Not Applicable`: 94
  - `20/25`: 2
  - `20/30`: 1
  - `20/30 + 1`: 1
  - `Confirmed Not Reported`: 1
**`ophtho_acuity_right_ph_cc_lea`** (2 unique values):
  - `Not Applicable`: 94
  - `Confirmed Not Reported`: 6
**`ophtho_acuity_both_cc_lea`** (3 unique values):
  - `Not Applicable`: 94
  - `Confirmed Not Reported`: 5
  - `20/25`: 1
**`ophtho_acuity_both_ph_cc_lea`** (2 unique values):
  - `Not Applicable`: 94
  - `Confirmed Not Reported`: 6
**`ophtho_acuity_left_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_left_ph_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_right_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_right_ph_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_both_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_acuity_both_ph_cc_other`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_logmar_left`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_logmar_right`** (1 unique values):
  - `Not Applicable`: 100
**`ophtho_oct_left`** (16 unique values):
  - `Not Applicable`: 72
  - `60`: 4
  - `96`: 3
  - `95`: 3
  - `58`: 3
**`ophtho_oct_right`** (16 unique values):
  - `Not Applicable`: 72
  - `54`: 5
  - `67`: 3
  - `65`: 3
  - `55`: 3

---


### survival.csv

**File**: `20250723_multitab__survival.csv`  
**Rows**: 189  
**Columns**: 6  
**Size**: 0.0 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 100 | C1003557, C1003680 |
| `age_at_last_known_status` | int64 | 0.0% | 100 | 4934, 4921 |
| `os_days` | int64 | 0.0% | 99 | 2613, 1471 |
| `os_censoring_status` | int64 | 0.0% | 2 | 0, 0 |
| `efs_days` | int64 | 0.0% | 100 | 856, 1471 |
| `efs_censoring_status` | int64 | 0.0% | 1 | 1, 1 |

**Identifier Fields**: `research_id`
**Date Fields**: `age_at_last_known_status`

---


### treatments.csv

**File**: `20250723_multitab__treatments.csv`  
**Rows**: 695  
**Columns**: 27  
**Size**: 0.25 MB  
**Completeness**: 100.0%

#### Columns

| Column Name | Type | Null % | Unique Values | Sample |
|-------------|------|--------|---------------|--------|
| `research_id` | object | 0.0% | 22 | C1003557, C1003557 |
| `event_id` | object | 0.0% | 85 | ET_7DK4B210, ET_DRY10WQM |
| `treatment_status` | object | 0.0% | 3 | New, New |
| `reason_for_treatment_change` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `surgery` | object | 0.0% | 3 | Yes, No |
| `age_at_surgery` | object | 0.0% | 45 | 2321, Not Applicable |
| `extent_of_tumor_resection` | object | 0.0% | 4 | Biopsy only, Not Applicable |
| `specimen_collection_origin` | object | 0.0% | 5 | Initial CNS Tumor Surgery, Not Applicable |
| `chemotherapy` | object | 0.0% | 3 | Yes, Yes |
| `chemotherapy_type` | object | 0.0% | 4 | Treatment follows a protocol but subject is not... |
| `protocol_name` | object | 0.0% | 8 | CCG-A9952: Regimen A (CV Chemotherapy), Not App... |
| `chemotherapy_agents` | object | 0.0% | 27 | carboplatin;vincristine sulfate, temodar;avastin |
| `age_at_chemo_start` | object | 0.0% | 76 | 2344, 3232 |
| `age_at_chemo_stop` | object | 0.0% | 65 | 2890, 3511 |
| `autologous_stem_cell_transplant` | object | 0.0% | 4 | No, No |
| `radiation` | object | 0.0% | 3 | No, No |
| `radiation_type` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `radiation_type_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `radiation_site` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `radiation_site_other` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `total_radiation_dose` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `total_radiation_dose_unit` | object | 0.0% | 1 | Not Applicable, Not Applicable |
| `total_radiation_dose_focal` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `total_radiation_dose_focal_unit` | object | 0.0% | 2 | Not Applicable, Not Applicable |
| `age_at_radiation_start` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `age_at_radiation_stop` | object | 0.0% | 3 | Not Applicable, Not Applicable |
| `date_for_treatment_ordering_only` | int64 | 0.0% | 100 | 2321, 3232 |

**Identifier Fields**: `research_id`, `event_id`
**Date Fields**: `age_at_surgery`, `age_at_chemo_start`, `age_at_chemo_stop`, `age_at_radiation_start`, `age_at_radiation_stop`, `date_for_treatment_ordering_only`

#### Categorical Fields

**`treatment_status`** (3 unique values):
  - `New`: 88
  - `Modified Treatment`: 10
  - `No treatment`: 2
**`reason_for_treatment_change`** (3 unique values):
  - `Not Applicable`: 90
  - `Unspecified reasons`: 8
  - `Toxicities`: 2
**`surgery`** (3 unique values):
  - `No`: 54
  - `Yes`: 44
  - `Not Applicable`: 2
**`extent_of_tumor_resection`** (4 unique values):
  - `Not Applicable`: 56
  - `Partial resection`: 31
  - `Biopsy only`: 10
  - `Gross/Near total resection`: 3
**`specimen_collection_origin`** (5 unique values):
  - `Not Applicable`: 56
  - `Initial CNS Tumor Surgery`: 22
  - `Progressive surgery`: 17
  - `Recurrence surgery`: 3
  - `Repeat resection`: 2
**`chemotherapy`** (3 unique values):
  - `Yes`: 78
  - `No`: 20
  - `Not Applicable`: 2
**`chemotherapy_type`** (4 unique values):
  - `Treatment follows other standard of care not associated with a current or past protocol`: 48
  - `Not Applicable`: 22
  - `Treatment follows a protocol but subject is not enrolled`: 19
  - `Treatment follows a protocol and subject is enrolled on a protocol`: 11
**`protocol_name`** (8 unique values):
  - `Not Applicable`: 70
  - `CCG-A9952: Regimen A (CV Chemotherapy)`: 13
  - `Not Available`: 12
  - `OZM-063: ARM A`: 1
  - `PBTC022`: 1
**`autologous_stem_cell_transplant`** (4 unique values):
  - `No`: 76
  - `Not Applicable`: 21
  - `Unavailable`: 2
  - `Yes`: 1
**`radiation`** (3 unique values):
  - `No`: 96
  - `Yes`: 2
  - `Not Applicable`: 2
**`radiation_type`** (2 unique values):
  - `Not Applicable`: 98
  - `Photons`: 2
**`radiation_type_other`** (1 unique values):
  - `Not Applicable`: 100
**`radiation_site`** (2 unique values):
  - `Not Applicable`: 98
  - `Focal/Tumor bed`: 2
**`radiation_site_other`** (1 unique values):
  - `Not Applicable`: 100
**`total_radiation_dose`** (1 unique values):
  - `Not Applicable`: 100
**`total_radiation_dose_unit`** (1 unique values):
  - `Not Applicable`: 100
**`total_radiation_dose_focal`** (3 unique values):
  - `Not Applicable`: 98
  - `59.40`: 1
  - `35`: 1
**`total_radiation_dose_focal_unit`** (2 unique values):
  - `Not Applicable`: 98
  - `Gy`: 2
**`age_at_radiation_start`** (3 unique values):
  - `Not Applicable`: 98
  - `5235`: 1
  - `5879`: 1
**`age_at_radiation_stop`** (3 unique values):
  - `Not Applicable`: 98
  - `5278`: 1
  - `5893`: 1

---
