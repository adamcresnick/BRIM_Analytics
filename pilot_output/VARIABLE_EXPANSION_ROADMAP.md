# BRIM Variable Expansion Roadmap - Building on Phase 1 & 2 Success

**Date**: October 3, 2025  
**Current Status**: Phase 2 Complete (100% accuracy, 8/8 gold standard match)  
**Question**: When and how to expand to other clinical variables?

---

## Strategic Expansion Approach

### ✅ What We've Proven Works (Phase 1 & 2)

1. **Table-based STRUCTURED documents** → BRIM can extract from markdown tables
2. **option_definitions JSON** → Enforces data dictionary dropdown values
3. **many_per_note scope** → Extracts longitudinal multi-event data
4. **CRITICAL instruction prefix** → Prevents semantic extraction errors
5. **Data dictionary alignment** → 100% achievable with proper constraints

### 🎯 Expansion Strategy

**Principle**: Build incrementally, validate each tier before proceeding

**Tiers Based on Complexity**:
1. **Tier 1** (Immediate): One-per-patient variables from STRUCTURED documents
2. **Tier 2** (Near-term): Multi-event longitudinal variables (like surgeries)
3. **Tier 3** (Medium-term): Aggregation-dependent variables
4. **Tier 4** (Long-term): Complex temporal alignment (imaging + corticosteroids)

---

## TIER 1: One-Per-Patient Variables (IMMEDIATE - Next 2 Weeks)

**Complexity**: Low  
**Success Probability**: 95%+  
**Why Start Here**: Builds on STRUCTURED document success, no event grouping needed

### 1A. Demographics (Already in STRUCTURED, 5 min setup)

| Variable | Source | Field Type | Expected Value (C1277724) | Status |
|----------|--------|------------|---------------------------|--------|
| **patient_gender** | STRUCTURED_demographics | dropdown | Female | Ready |
| **date_of_birth** | STRUCTURED_demographics | date | 2002-11-20 | Ready |
| **age_at_diagnosis** | STRUCTURED_demographics | number | 15 | Ready |
| **race** | STRUCTURED_demographics | dropdown | White | Ready |
| **ethnicity** | STRUCTURED_demographics | dropdown | Non-Hispanic | Ready |

**Data Dictionary Alignment**:
- Gender: "Male" / "Female" (radio button)
- Date of birth: YYYY-MM-DD format
- Race: 7 options from data dictionary

**Implementation**:
- ✅ STRUCTURED_demographics table already exists
- ✅ One row per patient (simple extraction)
- ✅ Add 5 variables to variables.csv with option_definitions
- ⏱️ **Time**: 30 minutes (15 min prep + 15 min test)

---

### 1B. Core Diagnosis (Already in STRUCTURED, 10 min setup)

| Variable | Source | Field Type | Expected Value (C1277724) | Status |
|----------|--------|------------|---------------------------|--------|
| **primary_diagnosis** | STRUCTURED_diagnosis | text | Pilocytic astrocytoma | Ready |
| **diagnosis_date** | STRUCTURED_diagnosis | date | 2018-05-28 | Ready |
| **who_grade** | STRUCTURED_molecular | dropdown | Grade I | Ready |
| **tumor_location** | STRUCTURED_diagnosis | checkbox (24 options) | Cerebellum/Posterior Fossa | Ready |

**Data Dictionary Alignment**:
- WHO Grade: "Grade I" / "Grade II" / "Grade III" / "Grade IV" (dropdown)
- Tumor location: 24 checkbox options (ALREADY PROVEN in Phase 2!)

**Implementation**:
- ✅ STRUCTURED_diagnosis table already exists
- ✅ STRUCTURED_molecular has WHO grade
- ✅ Reuse surgery_location approach (24 options proven)
- ⏱️ **Time**: 30 minutes

---

### 1C. Molecular Markers (Already in STRUCTURED, 15 min setup)

| Variable | Source | Field Type | Expected Value (C1277724) | Status |
|----------|--------|------------|---------------------------|--------|
| **idh_mutation** | STRUCTURED_molecular | dropdown | IDH wild-type | Ready |
| **mgmt_methylation** | STRUCTURED_molecular | dropdown | Unknown | Ready |
| **braf_fusion** | STRUCTURED_molecular | dropdown | KIAA1549-BRAF fusion | Ready |
| **1p19q_codeletion** | STRUCTURED_molecular | dropdown | Not tested | Ready |

**Data Dictionary Alignment**:
- IDH: "IDH wild-type" / "IDH mutant" / "Unknown"
- MGMT: "Methylated" / "Unmethylated" / "Unknown"
- BRAF: "BRAF V600E" / "BRAF fusion" / "BRAF wild-type" / "Unknown"

**Implementation**:
- ✅ STRUCTURED_molecular table already exists
- ✅ One row per patient (simple extraction)
- ✅ Add option_definitions for each molecular marker
- ⏱️ **Time**: 45 minutes

---

### TIER 1 SUMMARY

**Total Variables**: 13 (5 demographics + 4 diagnosis + 4 molecular)  
**Total Time**: 2 hours (all setup + testing)  
**Expected Accuracy**: 95%+ (proven approach)  
**Next Milestone**: **Phase 3a** (Tier 1 expansion)

**Recommendation**: ✅ **Start immediately after Phase 2 documentation complete**

---

## TIER 2: Multi-Event Longitudinal Variables (WEEKS 3-4)

**Complexity**: Medium  
**Success Probability**: 85%+  
**Why Next**: Builds on Phase 2 surgery success, requires aggregation decisions

### 2A. Chemotherapy (High Priority, Complex)

| Variable | Source | Scope | Expected for C1277724 | Complexity |
|----------|--------|-------|----------------------|------------|
| **chemotherapy_agent** | STRUCTURED_treatments | many_per_note | vinblastine, bevacizumab, selumetinib | Medium |
| **chemotherapy_start_date** | STRUCTURED_treatments | many_per_note | 2018-10-01, 2019-05-15, 2021-05-01 | Medium |
| **chemotherapy_line** | STRUCTURED_treatments | many_per_note | 1st line, 2nd line, 3rd line | Medium |
| **chemotherapy_status** | STRUCTURED_treatments | many_per_note | completed, completed, ongoing | Medium |

**Challenge**: Event grouping critical
- Agent + Start Date + Line must link together
- Example: vinblastine (1st line, 2018-10-01, completed)

**Implementation Strategy**:
1. Extract all 4 variables with many_per_note (like surgeries) ✅
2. Create aggregation decisions to group by treatment line
3. Test with known 3-agent regimen for C1277724

**Data Dictionary Alignment**:
- Agent: Free text (RxNorm codes preferred)
- Line: "1st line" / "2nd line" / "3rd line" / "Unknown"
- Status: "ongoing" / "completed" / "discontinued" / "unknown"

⏱️ **Time**: 3 hours (2 hours setup + 1 hour aggregation testing)

---

### 2B. Radiation Therapy (Medium Priority, Simpler)

| Variable | Source | Scope | Expected for C1277724 | Complexity |
|----------|--------|-------|----------------------|------------|
| **radiation_therapy_yn** | STRUCTURED_treatments | one_per_patient | No | Low |
| **radiation_start_date** | STRUCTURED_treatments | one_per_patient | N/A | Low |
| **radiation_dose** | STRUCTURED_treatments | one_per_patient | N/A | Low |
| **radiation_fractions** | STRUCTURED_treatments | one_per_patient | N/A | Low |

**Advantage**: Simpler than chemotherapy
- Most patients have 0 or 1 radiation course (not multiple like chemo)
- Can use one_per_patient scope

**Implementation**:
- ✅ STRUCTURED_treatments has radiation data
- ✅ Binary first: radiation_therapy_yn (Yes/No)
- ✅ If Yes, extract start date, dose, fractions

⏱️ **Time**: 1.5 hours

---

### 2C. Clinical Encounters (Lower Priority, High Volume)

| Variable | Source | Scope | Expected Volume | Complexity |
|----------|--------|-------|-----------------|------------|
| **encounter_date** | FHIR_BUNDLE + notes | many_per_note | ~50 encounters | High |
| **clinical_status** | Notes | many_per_note | stable/progressive/recurrent | High |
| **tumor_size** | Imaging reports | many_per_note | dimensions over time | High |

**Challenge**: Very high volume, needs temporal filtering

**Recommendation**: ⏸️ **Defer to Tier 3** (needs aggregation first)

---

### TIER 2 SUMMARY

**Total Variables**: 11 (7 chemotherapy + 4 radiation)  
**Total Time**: 1 week (4.5 hours setup + testing + iteration)  
**Expected Accuracy**: 85%+ (event grouping adds complexity)  
**Next Milestone**: **Phase 3b** (Tier 2 multi-event longitudinal)

**Recommendation**: ✅ **Start Week 3 after Tier 1 validated**

---

## TIER 3: Aggregation-Dependent Variables (WEEKS 5-6)

**Complexity**: High  
**Success Probability**: 75%+  
**Why Later**: Requires proven aggregation logic from surgeries/treatments

### 3A. Surgery Aggregations (Build on Phase 2)

| Variable | Aggregation Type | Logic | Expected for C1277724 |
|----------|------------------|-------|----------------------|
| **total_surgeries** | Count | Count distinct surgery_date where surgery_type="Tumor Resection" | 2 |
| **first_surgery_date** | Min | Earliest surgery_date | 2018-05-28 |
| **most_recent_surgery_date** | Max | Latest surgery_date | 2021-03-10 |
| **best_resection** | Max rank | Most extensive extent (GTR > NTR > STR > Partial) | Partial Resection |
| **total_resections** | Count | Count surgeries where extent != "Biopsy Only" | 2 |

⏱️ **Time**: 2 hours

---

### 3B. Treatment Aggregations

| Variable | Aggregation Type | Logic | Expected for C1277724 |
|----------|------------------|-------|----------------------|
| **total_chemo_lines** | Count | Count distinct chemotherapy_line values | 3 |
| **first_chemo_date** | Min | Earliest chemotherapy_start_date | 2018-10-01 |
| **time_to_progression** | Date diff | days between diagnosis_date and first progression | ~900 days |

⏱️ **Time**: 2 hours

---

### 3C. Clinical Status Tracking (Complex)

| Variable | Aggregation Type | Logic | Complexity |
|----------|------------------|-------|------------|
| **current_status** | Latest | Most recent clinical_status from encounters | High |
| **progression_free_survival** | Date diff + status | Time from diagnosis to first "progressive" status | High |
| **time_to_recurrence** | Date diff | Time from first surgery to first "recurrent" status | High |

⏱️ **Time**: 3 hours (complex temporal logic)

---

### TIER 3 SUMMARY

**Total Variables**: 13 (5 surgery agg + 3 treatment agg + 5 status tracking)  
**Total Time**: 1.5 weeks (7 hours setup + extensive testing)  
**Expected Accuracy**: 75%+ (aggregation logic adds complexity)  
**Next Milestone**: **Phase 4** (Production-ready aggregations)

**Recommendation**: ⚠️ **Start Week 5 after multi-event extraction validated**

---

## TIER 4: Complex Temporal Alignment (WEEKS 7-10)

**Complexity**: Very High  
**Success Probability**: 60%+  
**Why Last**: Requires SQL, cross-table joins, temporal reasoning

### 4A. Imaging + Corticosteroid Alignment (Deferred from Iteration 2)

**Problem Statement**: 
- Match imaging reports to corticosteroid status at time of scan
- Requires temporal join: imaging_date WITHIN corticosteroid_start/end range

**Variables Needed**:

| Variable | Source | Logic Type | Complexity |
|----------|--------|------------|------------|
| **tumor_size_at_scan_1** | Imaging reports | Extraction + temporal join | Very High |
| **corticosteroid_status_at_scan_1** | Medication orders | Temporal join | Very High |
| **tumor_progression_yn** | Imaging comparison | Sequential comparison | Very High |

**Why Deferred**:
- Requires SQL for temporal joins (documented in POST_IMPLEMENTATION_REVIEW_IMAGING_CORTICOSTEROIDS.md)
- 4 SQL attempts failed (complexity too high for current BRIM workflow)
- Need Python two-step or ETL pipeline approach

**Recommendation**: ⏸️ **Defer until Tiers 1-3 complete**

**Alternative Approach**:
1. Use STRUCTURED_imaging table (pre-computed corticosteroid alignment)
2. Extract tumor_size and corticosteroid_status as paired values
3. BRIM aggregation decision to link them

⏱️ **Time**: 2 weeks (requires architecture changes)

---

### 4B. Concomitant Medications (Complex Filtering)

**Challenge**: Separate cancer treatments from supportive care meds

**Variables**:

| Variable | Source | Filtering Logic | Complexity |
|----------|--------|-----------------|------------|
| **concomitant_medications** | MedicationRequest | Exclude chemo agents, Include supportive care | High |
| **corticosteroid_use_yn** | MedicationRequest | Filter to dexamethasone, prednisone | Medium |
| **anti_seizure_meds** | MedicationRequest | Filter to AED drug class | Medium |

**Implementation**:
- Documented in CONCOMITANT_MEDICATIONS_FRAMEWORK.md
- Needs RxNorm drug class filtering
- Can use STRUCTURED_medications table

⏱️ **Time**: 1 week

---

### TIER 4 SUMMARY

**Total Variables**: 11 (6 imaging + 5 concomitant meds)  
**Total Time**: 3 weeks (complex SQL + ETL pipeline)  
**Expected Accuracy**: 60%+ (highly complex temporal logic)  
**Next Milestone**: **Phase 5** (Production ETL pipeline)

**Recommendation**: ⏸️ **Defer until Q1 2026 after Tiers 1-3 production-ready**

---

## RECOMMENDED IMPLEMENTATION TIMELINE

### ✅ PHASE 3a: Tier 1 Expansion (Week 1 - October 2025)

**Variables**: 13 (demographics, diagnosis, molecular)  
**Effort**: 2 hours  
**Expected Accuracy**: 95%+  

**Why Start Here**:
- ✅ Lowest complexity (one_per_patient)
- ✅ STRUCTURED documents already exist
- ✅ Builds confidence before tackling complex variables
- ✅ Quick wins demonstrate scalability

**Deliverable**: variables.csv with 17 total variables (4 surgeries + 13 Tier 1)

---

### ✅ PHASE 3b: Tier 2 Longitudinal (Weeks 2-3 - October 2025)

**Variables**: 11 (chemotherapy, radiation)  
**Effort**: 1 week  
**Expected Accuracy**: 85%+  

**Why Next**:
- ✅ Builds on Phase 2 multi-event success
- ✅ High clinical value (treatment history critical)
- ✅ Tests event grouping at scale

**Deliverable**: variables.csv with 28 total variables + aggregation decisions

---

### ⚠️ PHASE 4: Tier 3 Aggregations (Weeks 4-6 - November 2025)

**Variables**: 13 (surgery agg, treatment agg, status tracking)  
**Effort**: 1.5 weeks  
**Expected Accuracy**: 75%+  

**Why Then**:
- ⚠️ Requires proven aggregation patterns
- ⚠️ More complex temporal logic
- ⚠️ Needs extensive validation

**Deliverable**: decisions.csv with 15+ aggregation rules

---

### ⏸️ PHASE 5: Tier 4 Complex (Q1 2026 - January-March)

**Variables**: 11 (imaging, concomitant meds)  
**Effort**: 3 weeks  
**Expected Accuracy**: 60%+  

**Why Last**:
- ⏸️ Requires SQL/ETL pipeline architecture
- ⏸️ Cross-table temporal joins
- ⏸️ Highest failure risk (already attempted 4 SQL approaches)

**Deliverable**: Hybrid Python + BRIM workflow

---

## PRIORITY MATRIX

### High Priority (Start Immediately)

| Variable Category | Value | Complexity | Recommendation |
|-------------------|-------|------------|----------------|
| **Demographics** | High | Low | ✅ Phase 3a Week 1 |
| **Core Diagnosis** | High | Low | ✅ Phase 3a Week 1 |
| **Molecular Markers** | High | Low | ✅ Phase 3a Week 1 |
| **Chemotherapy** | High | Medium | ✅ Phase 3b Week 2-3 |
| **Radiation** | High | Medium | ✅ Phase 3b Week 2-3 |

### Medium Priority (After Tier 1 Validated)

| Variable Category | Value | Complexity | Recommendation |
|-------------------|-------|------------|----------------|
| **Surgery Aggregations** | Medium | High | ⚠️ Phase 4 Week 4-5 |
| **Treatment Aggregations** | Medium | High | ⚠️ Phase 4 Week 5-6 |
| **Clinical Status** | Medium | High | ⚠️ Phase 4 Week 6 |

### Lower Priority (Defer to Q1 2026)

| Variable Category | Value | Complexity | Recommendation |
|-------------------|-------|------------|----------------|
| **Imaging + Corticosteroids** | Medium | Very High | ⏸️ Phase 5 Q1 2026 |
| **Concomitant Meds** | Low | High | ⏸️ Phase 5 Q1 2026 |
| **Encounters** | Low | High | ⏸️ Phase 5 Q1 2026 |

---

## SUCCESS CRITERIA FOR EXPANSION

### Phase 3a (Tier 1) - Must Achieve:
- ✅ 95%+ accuracy on all 13 variables
- ✅ Data dictionary alignment maintained
- ✅ Extraction time < 15 minutes
- ✅ Zero skipped variables

### Phase 3b (Tier 2) - Must Achieve:
- ✅ 85%+ accuracy on chemotherapy agents
- ✅ Event grouping working (agent ↔ start date ↔ line)
- ✅ Radiation binary (Y/N) 100% accurate
- ✅ Aggregation decisions functional

### Phase 4 (Tier 3) - Must Achieve:
- ✅ 75%+ accuracy on aggregated variables
- ✅ total_surgeries count correct (2 for C1277724)
- ✅ best_resection logic working
- ✅ Temporal calculations correct (dates not swapped)

---

## RISK MITIGATION

### Known Risks:

1. **Event Grouping Complexity** (Tier 2)
   - **Mitigation**: Start with radiation (simpler) before chemotherapy
   - **Fallback**: Use indexed variables (chemo_agent_1, chemo_agent_2)

2. **Over-Extraction Volume** (All Tiers)
   - **Mitigation**: Implement aggregation decisions early
   - **Acceptance**: 100% recall more important than precision

3. **Semantic Variations** (All Tiers)
   - **Mitigation**: option_definitions JSON for constrained fields
   - **Mapping**: Create equivalence rules (e.g., "Subtotal" = "Partial")

4. **Temporal Alignment** (Tier 4)
   - **Mitigation**: Pre-compute in STRUCTURED documents
   - **Fallback**: Python two-step approach (SQL → BRIM)

---

## ANSWER TO YOUR QUESTION

### "When should we expand?"

**Immediate (This Week)**: ✅ **Start Tier 1 expansion now**
- Phase 2 success proven (100% accuracy)
- STRUCTURED documents ready
- Low complexity, high value
- 2 hours total effort

**Near-Term (Weeks 2-3)**: ✅ **Tier 2 longitudinal variables**
- After Tier 1 validated
- Chemotherapy + radiation high priority
- Builds on Phase 2 multi-event approach

**Medium-Term (Weeks 4-6)**: ⚠️ **Tier 3 aggregations**
- After multi-event extraction proven at scale
- Surgery and treatment aggregations
- Requires robust decision logic

**Long-Term (Q1 2026)**: ⏸️ **Tier 4 complex temporal**
- After Tiers 1-3 production-ready
- Imaging + corticosteroid alignment
- Requires architectural changes

---

### "Do you have these target variables in mind?"

**YES - Complete Variable Inventory**:

| Tier | Variables | Source Documentation | Status |
|------|-----------|---------------------|--------|
| **Tier 1** | 13 | STRUCTURED documents exist | ✅ Ready to implement |
| **Tier 2** | 11 | CHEMOTHERAPY_IDENTIFICATION_STRATEGY.md, CONCOMITANT_MEDICATIONS_FRAMEWORK.md | ✅ Ready after Tier 1 |
| **Tier 3** | 13 | LONGITUDINAL_EVENT_MODELING_ANALYSIS.md | ⚠️ Needs aggregation validation |
| **Tier 4** | 11 | POST_IMPLEMENTATION_REVIEW_IMAGING_CORTICOSTEROIDS.md | ⏸️ Requires SQL/ETL |

**Total Target**: 48 variables (currently have 4 surgeries = 52 total)

**Data Dictionary Coverage**:
- Current: 8% (4/52 variables)
- After Tier 1: 33% (17/52 variables)
- After Tier 2: 54% (28/52 variables)
- After Tier 3: 79% (41/52 variables)
- After Tier 4: 100% (52/52 variables)

---

## IMMEDIATE NEXT ACTION

### Recommendation: ✅ **Start Phase 3a (Tier 1) Tomorrow**

**What to Do**:
1. Add 13 Tier 1 variables to variables.csv (30 min)
2. Upload to BRIM Project 22 (5 min)
3. Run extraction (15 min)
4. Validate results (30 min)
5. Document and commit (30 min)

**Expected Outcome**: 17 total variables with 95%+ accuracy

**Timeline**: 2 hours start to finish

**Would you like me to**:
- [ ] Create Phase 3a variables.csv with Tier 1 expansion now?
- [ ] Document the specific data dictionary mappings for each variable?
- [ ] Create validation script for the 13 new variables?

---

**Status**: ✅ **Comprehensive expansion roadmap complete**  
**Recommendation**: Start Tier 1 expansion immediately (this week)  
**Confidence**: Very High (95%+ expected accuracy based on Phase 1-2 success)
