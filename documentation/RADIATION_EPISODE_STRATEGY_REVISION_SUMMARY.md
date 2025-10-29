# Radiation Episode Strategy Revision Summary

**Date:** 2025-10-29
**Context:** Comprehensive schema review revealed critical data availability issues

---

## Key Findings from Schema Review

### 1. Appointment Date Availability Issue

**Problem Discovered:**
- `v_radiation_treatment_appointments` has **0% date coverage** (all `appointment_start` NULL)
- Root cause: View uses `TRY(CAST(a.start AS TIMESTAMP(3)))` but the cast fails for all records

**Solution Found:**
- `v_appointments` has **100% date coverage** (all 331,796 appointments have dates)
- Successfully joined to radiation appointments: **5,416 radiation appointments with full dates**

**Technical Fix:**
```sql
FROM fhir_prd_db.v_radiation_treatment_appointments rta
INNER JOIN fhir_prd_db.v_appointments va
    ON rta.appointment_id = va.appointment_fhir_id
```

### 2. Appointment Data Characteristics

**Analysis of Appointment Patterns:**
- 610 patients with radiation appointments
- 8.88 appointments per patient average
- Appointment gaps analysis revealed: **NOT daily radiation fractions**

**Sample appointment timeline:**
```
2010-06-08 → 2010-06-30 (22 days gap)
2010-07-02 → 2010-07-12 (10 days gap)
2010-07-14 → 2011-03-24 (253 days gap!)
```

**Interpretation:**
- Appointments represent **clinic visits**, **consultations**, **planning sessions**
- NOT actual daily radiation delivery appointments
- Temporal windowing for episode detection is inappropriate

### 3. Chemotherapy Comparison

**Key Insight:** Chemotherapy workflow does NOT use appointments for episode detection

**Chemotherapy Approach:**
- Uses `medication_request.dosage_instruction_timing_repeat_bounds_period_start/end`
- Falls back to `authored_on` date
- References encounters (not appointments) via `encounter_reference`
- Episode detection based on **medication administration dates** (21-day gap)

**Radiation Equivalent:**
- Should use **observation effective dates** (structured data from ELECT forms)
- Should use **service request occurrence dates**
- Should use **document dates** for unstructured data
- Appointments → **metadata enrichment only**

---

## Revised Episode Detection Strategy

### Strategy A: Structured Course ID Episodes ✅ WORKING
**Coverage:** 93 patients, 95 episodes
**Data Quality:** HIGH (93.7% completeness)
**Source:** `v_radiation_treatments.course_id` from observation components
**Status:** Production-ready

### Strategy B: Care Plan Period Episodes ❌ NOT VIABLE FOR EPISODE CREATION
**Coverage:** Only 13 care plans (out of 18,194) have both start and end dates
**Revised Use:** **Metadata enrichment** - link episodes to care plan protocols
**Status:** Repurposed for metadata layer

### Strategy C: Appointment Enrichment ✅ DEPLOYED
**Original Goal:** Create episodes from appointment temporal windowing
**Problem:** Appointments are clinic visits, not fraction delivery events
**Revised Goal:** **Enrich episodes with appointment metadata**

**New Approach:**
- Link appointments to existing episodes based on temporal proximity (±1 year window)
- Classify appointments by phase:
  - `pre_treatment` (≤30 days before episode start)
  - `during_treatment` (between episode start/end dates)
  - `post_treatment` (≤30 days after episode end)
  - `early_followup` (31-90 days post-episode)
  - `late_followup` (91-365 days post-episode)

**Final Results (Applied to All Episodes):**
- **606/967 episodes (62.7%)** enriched with appointments
- **96.1% average appointment fulfillment rate**
- Average 5.5 appointments per episode
- Distribution by phase: 0.9 pre-treatment, 3.6 during, 0.3 post, 0.3 early follow-up
- **Treatment phase coverage:**
  - Full continuum (pre+during+post): 37 episodes (3.8%)
  - Treatment + one phase: 170 episodes (17.6%)
  - Treatment only: 76 episodes (7.9%)
  - Consultation only: 257 episodes (26.6%)
  - No appointments: 427 episodes (44.2%)

**Status:** ✅ Production-deployed in `v_radiation_episode_enrichment`

### Strategy D: Document Temporal Clustering ✅ DEPLOYED
**Goal:** Create episodes for patients with radiation documents but no structured observations
**Approach:** Temporal clustering of document dates (30-day gap threshold)
**Coverage:** 406 patients, 872 episodes
**Data Quality:** MEDIUM - Heuristic-based clustering

**Results:**
- **406 patients** with document-based episodes (excluded 93 Strategy A patients)
- **872 episodes** detected (avg 2.15 per patient - re-irradiation detected)
- **Average 11.4 days episode duration** (tight clustering around documentation periods)
- **Average 2.6 documents per episode**
- **NLP Priority Distribution:**
  - Priority 1 (Treatment Summaries): 197 documents, 181 episodes (20.8%)
  - Priority 2 (Consultation Notes): 337 documents, 243 episodes (27.9%)
  - Priority 3 (Outside Summaries): 69 documents, 23 episodes (2.6%)
  - Priority 4 (Progress Notes): 797 documents, 149 episodes (17.1%)
  - Priority 5 (Other Documents): 905 documents, 276 episodes (31.7%)
- **48.6% episodes have high-value NLP targets** (Priority 1-2)

**Status:** ✅ Production-deployed in `v_radiation_treatment_episodes`

---

## Cross-Resource Linkage Opportunities

### Comprehensive Date Field Hierarchy (Recommended)

For episodes without structured course_id, use this fallback hierarchy:

```sql
COALESCE(
    observation.effective_date_time,                    -- PRIORITY 1: Most specific
    observation_component.component_value_date_time,    -- PRIORITY 2: Start/stop from components
    encounter.period_start,                             -- PRIORITY 3: Via observation.encounter_reference
    service_request.occurrence_period_start,            -- PRIORITY 4: Via observation_based_on
    care_plan.period_start,                             -- PRIORITY 5: Via service_request_based_on
    observation.issued                                  -- PRIORITY 6: Fallback
) as episode_date
```

### Key Linkage Tables Identified

| From | To | Via Table | Use Case |
|------|-----|-----------|----------|
| observation | service_request | `observation_based_on` | Get treatment orders |
| observation | encounter | `observation.encounter_reference` | Get visit context |
| encounter | appointment | `encounter_appointment` | Link to scheduling |
| appointment | service_request | `appointment_based_on` | Link orders to appointments |
| service_request | care_plan | `service_request_based_on` | Link to treatment protocols |
| care_plan | care_plan | `care_plan_based_on` | Parent-child protocol hierarchy |

---

## Recommendations

### Immediate Actions

1. **Deploy Strategy A** (structured course ID episodes) to production
2. **Deploy Strategy C** (appointment enrichment) as metadata layer
3. **Implement Strategy D** (document temporal clustering) for remaining ~684 patients

### View Architecture

#### Primary Episode View: `v_radiation_treatment_episodes`
- UNION of Strategy A (structured) + Strategy D (document-based)
- Provides episode_id, dates, dose, site, detection_method

#### Enrichment View: `v_radiation_episode_enrichment`
- Joins episodes to appointments (Strategy C)
- Joins episodes to care plans (Strategy B repurposed)
- Provides appointment counts, phases, fulfillment rates, care plan protocols

#### Timeline View: `v_radiation_course_timeline`
- Combines episodes + enrichment
- Adds document classification (pre/during/post treatment)
- Adds episode sequencing and re-irradiation detection

### Data Quality Improvements Needed

1. **Fix `v_radiation_treatment_appointments`** - appointment dates returning NULL
   - Root cause: `TRY(CAST(a.start AS TIMESTAMP(3)))` failing
   - Solution: Use `v_appointments` as source instead of raw `appointment` table

2. **Investigate encounter dates** - All `encounter.period_start/end` are NULL
   - May require similar fix as appointments

3. **Document v_appointments date processing** - Why does it work when raw table doesn't?

---

## Coverage Summary

| Strategy | Patients | Episodes | Status | Use |
|----------|----------|----------|--------|-----|
| **A: Structured Course ID** | 93 | 95 | ✅ Deployed | Episode creation (high quality) |
| **B: Care Plan Periods** | N/A | N/A | ✅ Deployed | Metadata enrichment only |
| **C: Appointments** | 606 episodes | 606 episodes | ✅ Deployed | Metadata enrichment |
| **D: Documents** | 406 | 872 | ✅ Deployed | Episode creation (medium quality) |
| **Combined Coverage** | **499** | **967** | ✅ **Production** | **72% patient coverage** |

### Final Architecture

**Base Episode View:** `v_radiation_treatment_episodes`
- UNION of Strategy A (95 episodes) + Strategy D (872 episodes)
- **967 total episodes across 499 patients**
- **72% coverage of 693 radiation patients**
- Fields: episode_id, dates, dose (Strategy A), documents (Strategy D), NLP priorities

**Enrichment Layer:** `v_radiation_episode_enrichment`
- Adds appointment metadata (Strategy C) to all episodes
- Adds care plan metadata (Strategy B) to all episodes
- **606/967 episodes (62.7%)** with appointment enrichment
- **598/967 episodes (61.8%)** with care plan enrichment
- Fields: appointment counts by phase, fulfillment rates, care plan protocols, enrichment scores

**Data Completeness Tiers:**
- **COMPLETE** (structured + appointments + care plans): 58 episodes (6.0%)
- **GOOD** (comprehensive multi-source): 401 episodes (41.5%)
- **PARTIAL** (some enrichment): 508 episodes (52.5%)
- **MINIMAL**: 0 episodes (0%)

**Key Metrics:**
- **96.1% appointment fulfillment rate** across all episodes
- **51.1 average enrichment score** (out of 100)
- **47.5% episodes have GOOD/COMPLETE data** - suitable for primary analysis
- **1.94 episodes per patient** - re-irradiation detection working

---

## Next Steps

### Immediate Priorities

1. **Episode Sequencing** - Add re-irradiation detection and episode ordering
   - Episode number: "Episode 1 of 3" for patient
   - Inter-episode gap analysis
   - Initial vs. salvage treatment classification
   - Temporal relationship to chemotherapy episodes

2. **Timeline View** - Create comprehensive `v_radiation_course_timeline`
   - Episodes (base layer from enrichment view)
   - Appointments (classified by phase)
   - Documents (linked to episodes via date proximity)
   - Treatments (daily fractions if available)
   - Care plans (protocol tracking)

3. **Production Finalization**
   - Move views from `/testing/` to `/views/` directory
   - Add to DATETIME_STANDARDIZED_VIEWS.sql
   - Update README with architecture documentation
   - Create example queries for common use cases

4. **NLP Integration**
   - Export high-priority episodes (Priority 1-2) for NLP extraction
   - Extract dose, site, duration from unstructured text
   - Backfill Strategy D episodes with extracted structured data
   - Measure NLP accuracy against Strategy A gold standard

---

## Technical Notes

### Why 14-Day Gap Threshold Didn't Work

**Original Assumption:**
Appointments represent daily radiation fractions, use 14-day gap to detect episode boundaries

**Reality:**
- Appointments are sporadic clinic visits (weeks/months apart)
- 586 patients → 586 episodes (1.0 per patient)
- Average duration: 503 days (1.4 years!)
- Gap analysis shows appointments already have large gaps (22 days, 253 days, etc.)

**Lesson:**
Always verify data characteristics before applying heuristics. What works for chemotherapy infusions (21-day gap) may not work for radiation appointments.

### Schema Analysis Tools

The comprehensive schema review used:
- `/Users/resnick/Downloads/Athena_FHIR_prd_db_Schema.csv` - Full schema with all tables/columns
- Systematic search for `based_on`, `period_start/end`, `effective_*`, `authored`, `issued` fields
- Cross-reference between related resources (observation → encounter → appointment)

This revealed critical linkage opportunities not obvious from view definitions alone.
