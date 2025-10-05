# CSV Variable Quick Reference Matrix

**Patient C1277724 Gold Standard Values**

---

## 📊 Variable Coverage Matrix

| # | Variable | Gold Standard Value | Extraction Source | Method | Priority | Status |
|---|----------|-------------------|-------------------|--------|----------|--------|
| **DEMOGRAPHICS (4 fields)** |
| 1 | legal_sex | Female | Patient.gender | ✅ STRUCTURED | P1 | ✅ DONE |
| 2 | date_of_birth | 2005-05-13 | Patient.birthDate | ✅ STRUCTURED | P1 | ✅ DONE |
| 3 | race | White | Patient.extension | ✅ STRUCTURED | P1 | ⏳ TODO |
| 4 | ethnicity | Not Hispanic/Latino | Patient.extension | ✅ STRUCTURED | P1 | ⏳ TODO |
| **DIAGNOSIS (3 fields)** |
| 5 | cns_integrated_diagnosis | Pilocytic astrocytoma | problem_list_diagnoses | ✅ STRUCTURED | P1 | ✅ DONE |
| 6 | diagnosis_date | 2018-06-04 | problem_list_diagnoses | ✅ STRUCTURED | P1 | ✅ DONE |
| 7 | who_grade | 1 (Grade I) | Condition.stage OR pathology | 🟡 HYBRID | P2 | ⏳ TODO |
| **SURGERY (4 fields)** |
| 8 | surgery (boolean) | Yes (2 encounters) | procedure COUNT | ✅ STRUCTURED | P1 | ⏳ TODO |
| 9 | age_at_surgery | 4763, 5780 days | procedure.performed_date_time | ✅ STRUCTURED | P1 | ✅ DONE |
| 10 | extent_of_resection | Partial resection | Operative note narrative | 🔴 NARRATIVE | P3 | ❌ BRIM |
| 11 | specimen_origin | Initial/Progressive | Timeline + context | 🟡 HYBRID | P2 | ❌ BRIM |
| **CHEMOTHERAPY (6 fields)** |
| 12 | chemotherapy (boolean) | Yes | patient_medications COUNT | ✅ STRUCTURED | P1 | ✅ DONE |
| 13 | chemotherapy_agents | vinblastine, bevacizumab, selumetinib | patient_medications | ✅ STRUCTURED | P1 | ⚠️ 1/3 |
| 14 | age_at_chemo_start | 5130, 5873 days | patient_medications.authored_on | ✅ STRUCTURED | P1 | ✅ DONE |
| 15 | age_at_chemo_stop | 5492, 7049 days | patient_medications.end_date | ✅ STRUCTURED | P1 | ⏳ TODO |
| 16 | protocol_name | N/A | CarePlan OR notes | 🔴 NARRATIVE | P3 | ❌ BRIM |
| 17 | chemotherapy_type | Standard of care | Notes | 🔴 NARRATIVE | P3 | ❌ BRIM |
| **RADIATION (2 fields)** |
| 18 | radiation (boolean) | No | procedure CPT 77xxx | ✅ STRUCTURED | P1 | ✅ DONE |
| 19 | radiation_type | N/A | procedure.code OR notes | 🟡 HYBRID | P2 | ⏳ TODO |
| **MOLECULAR (4 fields)** |
| 20 | mutation | KIAA1549-BRAF fusion | observation.value_string | ✅ STRUCTURED | P1 | ✅ DONE |
| 21 | age_at_molecular_test | 4763, 5780 days | observation.effective_datetime | ✅ STRUCTURED | P1 | ⏳ TODO |
| 22 | molecular_tests | Fusion Panel, Somatic | molecular_tests OR observation | ✅ STRUCTURED | P1 | ⏳ TODO |
| 23 | idh_mutation | Wildtype (inferred) | BRAF-only → infer wildtype | 🟡 HYBRID | P2 | ⏳ LOGIC |
| 24 | mgmt_methylation | Unknown/Not tested | observation OR N/A | 🟡 HYBRID | P2 | ⏳ TODO |
| **LOCATION/METASTASIS (3 fields)** |
| 25 | tumor_location | Cerebellum/Posterior Fossa | Condition.bodySite OR radiology | 🟡 HYBRID | P2 | ⏳ TODO |
| 26 | metastasis | Yes (Leptomeningeal, Spine) | Condition OR notes | 🟡 HYBRID | P2 | ❌ BRIM |
| 27 | metastasis_location | Leptomeningeal, Spine | Notes (radiology) | 🔴 NARRATIVE | P3 | ❌ BRIM |
| **ENCOUNTERS (3 fields)** |
| 28 | age_at_encounter | 4931, 5130, 5228... | encounter.period_start | ✅ STRUCTURED | P1 | ⏳ TODO |
| 29 | follow_up_visit_status | Visit Completed | encounter.status | ✅ STRUCTURED | P1 | ⏳ TODO |
| 30 | tumor_status | Stable/Change | Notes (oncology) | 🔴 NARRATIVE | P3 | ❌ BRIM |
| **OTHER (3 fields)** |
| 31 | shunt_required | ETV Shunt | procedure CPT 62201 | ✅ STRUCTURED | P1 | ⏳ TODO |
| 32 | clinical_status | Alive | patient.deceased | ✅ STRUCTURED | P1 | ⏳ TODO |
| 33 | conditions | Emesis, Headaches, etc. | Condition OR notes | 🟡 HYBRID | P2 | ❌ BRIM |

---

## 🎯 Coverage Summary

### By Extraction Method:
- ✅ **STRUCTURED (Direct DB query):** 20 fields (61%)
- 🟡 **HYBRID (Structured + Narrative):** 8 fields (24%)
- 🔴 **NARRATIVE (BRIM only):** 5 fields (15%)

### By Implementation Status:
- ✅ **EXTRACTED:** 9 fields (27%)
- ⏳ **TODO (Structured):** 11 fields (33%)
- ⚠️ **PARTIAL:** 1 field (3%) - chemotherapy_agents (1/3 drugs)
- ❌ **BRIM REQUIRED:** 12 fields (36%)

### By Priority:
- **P1 (High - Fully Structured):** 21 fields (64%)
- **P2 (Medium - Hybrid):** 7 fields (21%)
- **P3 (Low - Narrative):** 5 fields (15%)

---

## 🔴 CRITICAL ISSUE: Medication Filter

### Gold Standard Expects:
```
Event 2: vinblastine + bevacizumab (ages 5130-5492 days)
Event 3: selumetinib (ages 5873-7049 days)
```

### Currently Extracting:
```
✅ bevacizumab: 48 records
❌ vinblastine: MISSING
❌ selumetinib: MISSING
```

### Root Cause:
```python
# CURRENT FILTER (TOO NARROW):
WHERE LOWER(medication_name) LIKE '%bevacizumab%'
   OR LOWER(medication_name) LIKE '%temozolomide%'
   OR LOWER(medication_name) LIKE '%chemotherapy%'

# MISSING KEYWORDS:
- vinblastine
- selumetinib/koselugo
```

### Impact:
- Chemotherapy agent extraction: **33% recall** (1/3 drugs)
- BRIM will miss structured data for vinblastine/selumetinib
- Critical clinical data loss

### Fix Required:
Expand keyword list to include:
- vinblastine, velban
- selumetinib, koselugo
- vincristine, oncovin
- carboplatin, cisplatin
- lomustine, ccnu
- cyclophosphamide, etoposide
- dabrafenib, trametinib

**Time to fix:** 10 minutes  
**Priority:** 🔴 HIGHEST

---

## 📋 Next Steps (Prioritized)

### IMMEDIATE (Phase 2):
1. **Expand medication filter** → Extract vinblastine + selumetinib (10 min)
2. **Test extraction** → Validate 3/3 agents present (5 min)

### HIGH PRIORITY (Phase 3):
3. **Add race/ethnicity extraction** → Patient.extension table (10 min)
4. **Add encounter extraction** → encounter table (10 min)
5. **Add shunt procedure extraction** → Procedure CPT 62201 (5 min)
6. **Add molecular test dates** → observation.effective_datetime (5 min)
7. **Add clinical status** → patient.deceased (5 min)
8. **Add chemo stop dates** → patient_medications.end_date (5 min)

### MEDIUM PRIORITY (Phase 4):
9. **Add surgery type classification** → CPT code logic (10 min)
10. **Add surgery body sites** → procedure.bodySite (5 min)
11. **Add WHO grade logic** → Diagnosis → Grade mapping (5 min)
12. **Add IDH wildtype inference** → BRAF-only → IDH WT (5 min)

### DOCUMENTATION (Phase 5):
13. **Update BRIM variables.csv** → Add STRUCTURED priority (20 min)
14. **Regenerate BRIM CSVs** → With enhanced structured data (5 min)
15. **Upload and test iteration 2** → BRIM platform (20 min)

**Total Time to Iteration 2:** ~2 hours

---

## 🎯 Expected Outcomes

### After Phase 2 (Medication Fix):
- Chemotherapy recall: 33% → **100%** (3/3 drugs)
- Structured field coverage: 27% → **30%**

### After Phase 3 (Structured Fields):
- Structured field coverage: 30% → **50%**
- New extractions: race, ethnicity, encounters, shunt, test dates, status

### After Phase 4 (Classification Logic):
- Structured field coverage: 50% → **58%**
- Enhanced extractions: surgery types, body sites, grade mapping, IDH inference

### After Phase 5 (BRIM Integration):
- BRIM accuracy: 50% (iteration 1) → **85-90%** (iteration 2 target)
- Variables with STRUCTURED priority: 0 → **7 variables**

---

## 📊 Variable → BRIM Mapping

### BRIM Variables That Need STRUCTURED Priority:

| BRIM Variable | STRUCTURED Document | Gold Standard Field |
|---------------|---------------------|---------------------|
| patient_gender | STRUCTURED_demographics | legal_sex |
| date_of_birth | STRUCTURED_demographics | date_of_birth |
| primary_diagnosis | STRUCTURED_diagnosis | cns_integrated_diagnosis |
| diagnosis_date | STRUCTURED_diagnosis | diagnosis_date |
| surgery_date | STRUCTURED_surgeries | age_at_surgery |
| surgery_type | STRUCTURED_surgeries | surgery type classification |
| chemotherapy_agent | STRUCTURED_treatments | chemotherapy_agents |
| radiation_therapy | STRUCTURED_radiation | radiation (boolean) |
| idh_mutation | STRUCTURED_molecular | Inferred from BRAF-only |
| mgmt_methylation | STRUCTURED_molecular | mgmt status (if tested) |

**Total:** 10 BRIM variables should check STRUCTURED documents first

---

**Ready to proceed with medication filter fix!**
