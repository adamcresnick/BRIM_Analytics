# V5.0 Protocol Augmentation Documentation

**Date:** 2025-11-09
**Author:** V5.0 Framework Enhancement
**Version:** V5.0.1

## Executive Summary

The V5.0 Therapeutic Approach Framework has been augmented with a comprehensive protocol knowledge base, expanding from 3 hardcoded protocols to **42 structured pediatric oncology treatment protocols**. This enhancement enables precise protocol matching from observed treatment patterns using signature agents, radiation fingerprints, and multi-step matching algorithms.

### Key Enhancements

1. **Expanded Protocol Coverage:** 42 protocols across 6 major disease categories
2. **New Protocol Knowledge Base Module:** `protocol_knowledge_base.py` (1,800+ lines)
3. **Enhanced Protocol Matching:** 3-step algorithm with signature agent and radiation fingerprint matching
4. **Data Sources Integrated:**
   - CBTN REDCap Protocols CSV (110+ trial arms)
   - Pediatric Oncology Treatment Protocols Reference (comprehensive guide)
5. **Backward Compatible:** Graceful fallback to original 3-protocol knowledge base

---

## Protocol Knowledge Base Statistics

### Coverage Overview

| Category | Count | Examples |
|----------|-------|----------|
| **Total Protocols** | 42 | All categories below |
| Original V5.0 Protocols | 3 | Stupp, ACNS0331, CheckMate 143 |
| COG CNS Trials | 9 | ACNS0332, ACNS0334, ACNS0423, ACNS0822, ACNS0831, etc. |
| COG Leukemia/Lymphoma | 2 | AALL0434 (T-ALL), ANHL0131 (B-cell NHL) |
| COG Neuroblastoma | 2 | ANBL0532 (high-risk), ANBL0531 (intermediate-risk) |
| COG Solid Tumor | 2 | AREN0532/0533 (Wilms tumor) |
| St. Jude Institutional | 5 | SJMB12, SJMB03, SJATRT, SJ-DIPG-BATS, SJYC07 |
| Consortium (PBTC/PNOC/Head Start) | 9 | PNOC003, PNOC007, PNOC013, PBTC-026/027/030/045, Head Start II/III |
| Legacy Protocols | 5 | CCG-99701, CCG-99703, SJMB-96, CCG-A5971, CCG-A9952 |
| Salvage/Experimental | 5 | SJDAWN, GemPOx, DFMO, ETMR One, Selumetinib (NF1) |

### Evidence Level Distribution

| Evidence Level | Count | Description |
|----------------|-------|-------------|
| **Standard of Care** | 7 | Established protocols (e.g., Stupp, ACNS0331, ACNS0334) |
| **Phase 3 Trials** | 8 | Randomized trials (e.g., AALL0434, ANBL0532, ACNS0822) |
| **Phase 2/3 Trials** | 3 | ACNS0822, SJMB12, SJMB03 |
| **Phase 2 Trials** | 8 | Multiple institutional and consortium trials |
| **Phase 1/2 Trials** | 6 | PNOC/PBTC early phase trials |
| **Phase 1 Trials** | 4 | PBTC-026/027, dose-finding studies |
| **Institutional Protocols** | 2 | St. Jude protocols (SJATRT, SJMB-96) |
| **Experimental** | 3 | Novel agents and combinations |
| **Salvage Regimen** | 1 | GemPOx |

### Disease Coverage

- **CNS Tumors:** 22 protocols
  - Medulloblastoma (8 protocols)
  - High-Grade Glioma (5 protocols)
  - DIPG (7 protocols)
  - Ependymoma (2 protocols)
  - AT/RT (2 protocols)
  - Germinoma (1 protocol)
  - Infant Brain Tumors (4 protocols)

- **Leukemia/Lymphoma:** 4 protocols
  - T-cell ALL (1 protocol)
  - B-cell NHL (1 protocol)
  - Hodgkin Lymphoma (1 protocol)
  - Lymphoblastic Lymphoma (1 protocol)

- **Solid Tumors:** 5 protocols
  - Neuroblastoma (2 protocols)
  - Wilms Tumor (2 protocols)
  - NF1 Plexiform Neurofibromas (1 protocol)

- **Rare/Other:** 3 protocols
  - ETMR (1 protocol)
  - Multi-indication salvage regimens (2 protocols)

---

## Architecture

### File Structure

```
scripts/
├── protocol_knowledge_base.py           # NEW: Expanded protocol knowledge base (1,800+ lines)
├── therapeutic_approach_abstractor.py   # UPDATED: Enhanced protocol matching
└── patient_timeline_abstraction_V3.py   # No changes (imports transparently)

docs/
├── CBTN_REDCAP_Protocols.csv            # Source: 110+ trial arms
├── Pediatric Oncology Treatment Protocols Reference.html  # Source: Comprehensive guide
├── V5_0_PROTOCOL_AUGMENTATION.md        # THIS FILE
└── V4_7_COMPREHENSIVE_INVESTIGATION_ENGINE_ARCHITECTURE.md  # To be updated
```

### Protocol Knowledge Base Module

[protocol_knowledge_base.py](../scripts/protocol_knowledge_base.py) provides:

#### Protocol Dictionaries

```python
ALL_PROTOCOLS = {
    **ORIGINAL_PEDIATRIC_CNS_PROTOCOLS,    # 3 protocols
    **COG_CNS_PROTOCOLS,                   # 9 protocols
    **COG_LEUKEMIA_LYMPHOMA_PROTOCOLS,     # 2 protocols
    **COG_NEUROBLASTOMA_PROTOCOLS,         # 2 protocols
    **COG_SOLID_TUMOR_PROTOCOLS,           # 2 protocols
    **ST_JUDE_PROTOCOLS,                   # 5 protocols
    **CONSORTIUM_PROTOCOLS,                # 9 protocols
    **LEGACY_PROTOCOLS,                    # 5 protocols
    **SALVAGE_EXPERIMENTAL_PROTOCOLS       # 5 protocols
}
```

#### Query Functions

```python
get_protocols_by_indication(indication: str) -> List[Dict[str, Any]]
get_protocols_by_signature_agent(agent: str) -> List[Dict[str, Any]]
get_protocols_by_radiation_signature(dose_gy: float, type: str) -> List[Dict[str, Any]]
get_protocol_by_id(protocol_id: str) -> Optional[Dict[str, Any]]
get_protocols_by_era(start_year: int, end_year: int) -> List[Dict[str, Any]]
get_all_signature_agents() -> List[str]
get_protocol_statistics() -> Dict[str, Any]
```

#### Protocol Structure

Each protocol contains:

```python
{
    "protocol_id": "acns0332",
    "name": "COG ACNS0332 (High-Risk Medulloblastoma)",
    "reference": "JAMA Oncology 2021, NCT00392327",
    "trial_id": "ACNS0332",
    "indications": ["medulloblastoma_high_risk", "metastatic_medulloblastoma"],
    "evidence_level": "standard_of_care",
    "era": "2004-2015",
    "components": {
        "surgery": {...},
        "radiation": {...},
        "concurrent_chemotherapy": {...},
        "maintenance_chemotherapy": {...}
    },
    "signature_agents": ["carboplatin", "isotretinoin"],  # Fingerprints
    "signature_radiation": {"csi_dose_gy": 36.0, "type": "craniospinal"},
    "inference_clues": [
        "Carboplatin during radiation for medulloblastoma",
        "Isotretinoin maintenance in brain tumor",
        "CSI 36 Gy + 6 cycles platinum-based chemo"
    ]
}
```

### Enhanced Protocol Matching Algorithm

[therapeutic_approach_abstractor.py:437-573](../scripts/therapeutic_approach_abstractor.py#L437-L573)

The `match_regimen_to_protocol()` function now uses a **3-step matching algorithm**:

#### Step 1: Signature Agent Matching (Most Specific)

```python
# If patient received nelarabine → strongly suggests AALL0434 (T-ALL protocol)
# If patient received carboplatin during RT → suggests ACNS0332
# If patient received isotretinoin for brain tumor → suggests ACNS0332
# Score bonus: +20 points
```

**Signature Agents (34 unique):**
- `nelarabine` → T-ALL trials (AALL0434)
- `carboplatin` (during RT) → High-risk medulloblastoma (ACNS0332)
- `isotretinoin` (brain tumor) → ACNS0332
- `isotretinoin` (solid tumor) → Neuroblastoma
- `dinutuximab` → High-risk neuroblastoma (ANBL0532)
- `vorinostat` → DIPG trials (ACNS0621, PBTC-030)
- `bevacizumab` (DIPG) → SJ-DIPG-BATS
- `temozolomide` + `lomustine` → ACNS0423
- `vismodegib` → SHH-medulloblastoma (SJMB12)
- `thiotepa` + `carboplatin` → Infant brain tumor protocols (ACNS0334, Head Start)
- And 24 more...

#### Step 2: Radiation Signature Matching

```python
# CSI 23.4 Gy → Standard-risk medulloblastoma (ACNS0331)
# CSI 36 Gy → High-risk medulloblastoma (ACNS0332)
# CSI 18 Gy → WNT-medulloblastoma (SJMB12) - only done on trial!
# Whole-ventricular 18 Gy → Germinoma (ACNS0232)
# Score bonus: +15 points
```

**Radiation Fingerprints:**
- **CSI 18.0 Gy** → SJMB12 WNT stratum (very distinctive)
- **CSI 23.4 Gy** → ACNS0331 (standard-risk MB)
- **CSI 36.0 Gy** → ACNS0332 (high-risk MB)
- **Whole-ventricular 18 Gy** → ACNS0232 (germinoma)
- **Focal 54-59.4 Gy** → High-grade glioma protocols
- **Flank RT 10.8 Gy** → Wilms tumor (AREN0533)

#### Step 3: Indication-Based Matching (Comprehensive)

```python
# Check all protocols for diagnosis match
# Score based on component matching (surgery, chemo, radiation)
# No bonus points
```

#### Confidence Scoring

```python
def _confidence_from_score(score: float) -> str:
    if score >= 90:
        return "high"      # ≥90% match
    elif score >= 70:
        return "medium"    # 70-89% match
    elif score >= 50:
        return "low"       # 50-69% match
    else:
        return "no_match"  # <50% match
```

#### Output Enhancement

Protocol match now returns:

```python
{
    'protocol_id': 'acns0332',
    'regimen_name': 'COG ACNS0332 (High-Risk Medulloblastoma)',
    'protocol_reference': 'JAMA Oncology 2021, NCT00392327',
    'match_confidence': 'high',  # high/medium/low/no_match
    'evidence_level': 'standard_of_care',
    'trial_id': 'ACNS0332',
    'era': '2004-2015',
    'deviations_from_protocol': [...],
    'matching_method': 'signature_agent'  # NEW: signature_agent/radiation_signature/indication_based/no_match
}
```

---

## Example Protocol Matching Scenarios

### Scenario 1: High-Risk Medulloblastoma (ACNS0332)

**Patient Treatment Pattern:**
- Diagnosis: Metastatic medulloblastoma
- Surgery: Subtotal resection
- Radiation: CSI 36 Gy + posterior fossa boost
- **Carboplatin given during radiation** ← Signature agent
- Chemotherapy: 6 cycles cisplatin/vincristine/cyclophosphamide
- **Isotretinoin maintenance for 12 months** ← Signature agent

**Matching Result:**
```python
{
    'protocol_id': 'acns0332',
    'regimen_name': 'COG ACNS0332 (High-Risk Medulloblastoma)',
    'protocol_reference': 'JAMA Oncology 2021, NCT00392327',
    'match_confidence': 'high',  # Score: 95+ (signature agent bonus)
    'evidence_level': 'standard_of_care',
    'trial_id': 'ACNS0332',
    'era': '2004-2015',
    'matching_method': 'signature_agent',  # Carboplatin + isotretinoin
    'deviations_from_protocol': []  # Perfect match
}
```

**Why This Works:**
- **Step 1:** Carboplatin during RT → +20 bonus → signature_protocols = [ACNS0332]
- **Step 1:** Isotretinoin for brain tumor → +20 bonus → confirms ACNS0332
- **Step 2:** CSI 36 Gy → +15 bonus → confirms high-risk protocol
- **Diagnosis match:** medulloblastoma ✓
- **Component match:** Surgery + RT + chemo + isotretinoin ✓

---

### Scenario 2: WNT-Subgroup Medulloblastoma (SJMB12)

**Patient Treatment Pattern:**
- Diagnosis: Medulloblastoma, WNT-subgroup
- Molecular testing: WNT-pathway activated
- Surgery: Gross total resection
- **Radiation: CSI 18 Gy** ← Signature radiation (only done on trial!)
- Chemotherapy: 4 cycles vincristine/cyclophosphamide/cisplatin

**Matching Result:**
```python
{
    'protocol_id': 'sjmb12',
    'regimen_name': 'SJMB12 (Molecular Risk-Adapted Medulloblastoma)',
    'protocol_reference': 'ASCO JCO 2023',
    'match_confidence': 'high',  # Score: 90+ (radiation signature bonus)
    'evidence_level': 'phase_2_3_trial',
    'trial_id': 'SJMB12',
    'era': '2012-2021',
    'matching_method': 'radiation_signature',  # CSI 18 Gy is unique!
    'deviations_from_protocol': []
}
```

**Why This Works:**
- **Step 2:** CSI 18 Gy → +15 bonus → radiation_protocols = [SJMB12 WNT stratum]
- **Diagnosis match:** medulloblastoma + "WNT" ✓
- **Signature feature:** CSI 18 Gy is only used in SJMB12 for WNT-MB
- **This is a very high-confidence match due to unique radiation dose**

---

### Scenario 3: T-cell ALL with Nelarabine (AALL0434)

**Patient Treatment Pattern:**
- Diagnosis: T-cell acute lymphoblastic leukemia
- Induction: Vincristine, daunorubicin, prednisone, pegaspargase
- Consolidation: Cyclophosphamide, cytarabine, 6-MP, **nelarabine** ← Signature agent
- Cranial radiation: 12 Gy
- Maintenance: Vincristine, dexamethasone, 6-MP, methotrexate

**Matching Result:**
```python
{
    'protocol_id': 'aall0434',
    'regimen_name': 'COG AALL0434 (T-cell ALL)',
    'protocol_reference': 'HemOnc.org, NCBI Books NBK599994',
    'match_confidence': 'high',  # Score: 95+ (signature agent bonus)
    'evidence_level': 'phase_3_trial',
    'trial_id': 'AALL0434',
    'era': '2007-2014',
    'matching_method': 'signature_agent',  # Nelarabine is highly specific
    'deviations_from_protocol': []
}
```

**Why This Works:**
- **Step 1:** Nelarabine → +20 bonus → signature_protocols = [AALL0434]
- **Nelarabine is only used for T-cell ALL (not B-cell ALL)**
- **Diagnosis match:** T-cell ALL ✓
- **Component match:** ABFM backbone + nelarabine ✓

---

### Scenario 4: Infant Brain Tumor (ACNS0334 vs Head Start II)

**Patient Treatment Pattern:**
- Diagnosis: Medulloblastoma, age 18 months
- Induction: Vincristine, cisplatin, etoposide, cyclophosphamide, **high-dose methotrexate** ← Signature agent
- Consolidation: **Thiotepa + carboplatin with autologous stem cell transplant (×1)** ← Signature feature
- Radiation: Delayed until age 3

**Matching Result:**
```python
{
    'protocol_id': 'acns0334',
    'regimen_name': 'COG ACNS0334 (Infant Brain Tumors)',
    'protocol_reference': 'NCT00336024',
    'match_confidence': 'high',  # Score: 90+
    'evidence_level': 'standard_of_care',
    'trial_id': 'ACNS0334',
    'era': '2005-2015',
    'matching_method': 'signature_agent',  # HD-MTX + thiotepa/carboplatin
    'deviations_from_protocol': []
}
```

**Why ACNS0334 (not Head Start II):**
- **High-dose methotrexate:** Present in ACNS0334 Arm II
- **Single transplant:** ACNS0334 uses 3 cycles of HD chemo with PBSC
- **Head Start II:** Uses 3 *sequential* transplants (different regimens)
- **Era match:** 2005-2015 ✓

---

## Integration with V5.0 Pipeline

### Import and Use

[therapeutic_approach_abstractor.py:28-44](../scripts/therapeutic_approach_abstractor.py#L28-L44)

```python
# Import expanded protocol knowledge base
try:
    from protocol_knowledge_base import (
        ALL_PROTOCOLS,
        get_protocols_by_indication,
        get_protocols_by_signature_agent,
        get_protocols_by_radiation_signature,
        get_protocol_by_id,
        get_all_signature_agents,
        ORIGINAL_PEDIATRIC_CNS_PROTOCOLS
    )
    EXPANDED_PROTOCOLS_AVAILABLE = True
    print("  ✅ V5.0: Loaded expanded protocol knowledge base (42 protocols)")
except ImportError:
    EXPANDED_PROTOCOLS_AVAILABLE = False
    print("  ⚠️  V5.0: Using original protocol knowledge base (3 protocols)")
    ALL_PROTOCOLS = {}
```

### Backward Compatibility

- **If `protocol_knowledge_base.py` is available:** Uses expanded 42-protocol knowledge base
- **If import fails:** Gracefully falls back to original 3-protocol knowledge base
- **No breaking changes:** Existing V5.0 functionality preserved

### Execution Flow

1. **User runs patient_timeline_abstraction_V3.py**
2. **V5.0 Phase 5.0.1:** Detect treatment lines
3. **V5.0 Phase 5.0.2:** Match regimen to protocol
   - **Step 1:** Try signature agent matching (if expanded KB available)
   - **Step 2:** Try radiation signature matching (if expanded KB available)
   - **Step 3:** Try indication-based matching
   - **Result:** Best match with confidence score
4. **V5.0 Phase 5.0.3:** Detect chemotherapy cycles
5. **V5.0 Phase 5.0.4:** Integrate response assessments
6. **V5.0 Phase 5.0.5:** Calculate clinical endpoints
7. **Output:** `therapeutic_approach` added to artifact

---

## Data Sources

### 1. CBTN REDCap Protocols CSV

**File:** [docs/CBTN_REDCAP_Protocols.csv](CBTN_REDCAP_Protocols.csv)

**Content:** 110+ trial arms from Children's Brain Tumor Network protocols
- Detailed drug regimens, dosing, and timing
- Radiation protocols and doses
- CNS prophylaxis strategies
- Signature agents and deviations
- References and citations

**Example Entry:**

```csv
Trial ID,Arm,Drug/Radiation Modality,Sequence,Dose/Timing,Notes
ACNS0332,Regimen B,CSI + concurrent carboplatin radiosensitizer + maintenance chemo,Post-op RT + carboplatin → Maintenance chemo x6,Carboplatin 35 mg/m² daily during CSI; standard maintenance chemo,Experimental arm testing carboplatin during radiation. Result: Carboplatin during RT improved 5-yr EFS in Group 3 MB
```

**Coverage:**
- COG trials: 25+
- St. Jude trials: 10+
- PBTC trials: 7
- PNOC trials: 5
- Legacy trials (CCG, POG): 10+

### 2. Pediatric Oncology Treatment Protocols Reference

**File:** [docs/Pediatric Oncology Treatment Protocols Reference.html](Pediatric%20Oncology%20Treatment%20Protocols%20Reference.html)

**Content:** Comprehensive protocol guide (10 pages, 7,695 words)
- Protocol descriptions and indications
- Inference guidelines ("protocol fingerprints")
- Signature agents and radiation doses
- Treatment structure patterns
- Evidence levels and references
- Era-based protocol selection

**Generated by:** ChatGPT Deep Research (2025-11-09)

**Example Section:**

```markdown
### Inference Clues for Protocol Identification

#### Key Signature Agents (Protocol Fingerprints)

1. **Nelarabine** → T-ALL trials (AALL0434)
2. **Carboplatin during radiation** → High-risk MB (ACNS0332)
3. **Isotretinoin in brain tumor** → ACNS0332 (medulloblastoma)
4. **Isotretinoin in solid tumor** → Neuroblastoma maintenance
5. **Anti-GD2 antibody** → Neuroblastoma high-risk (modern era)
...
```

---

## Testing and Validation

### Test 1: Protocol Statistics

```bash
$ cd scripts
$ python3 protocol_knowledge_base.py
```

**Output:**
```
================================================================================
PROTOCOL KNOWLEDGE BASE STATISTICS
================================================================================
Total Protocols: 42

Protocol Categories:
  - Original V5.0: 3
  - COG CNS: 9
  - COG Leukemia/Lymphoma: 2
  - COG Neuroblastoma: 2
  - COG Solid Tumor: 2
  - St. Jude: 5
  - Consortium (PBTC/PNOC/Head Start): 9
  - Legacy: 5
  - Salvage/Experimental: 5

Unique Indications Covered: 59
Unique Signature Agents: 34

Evidence Levels:
  - standard_of_care: 7
  - phase_3_trial: 8
  - phase_2_3_trial: 3
  - phase_2_trial: 8
  - phase_1_2_trial: 6
  - phase_1_trial: 4
  - institutional_protocol: 2
  - experimental: 3
  - salvage_regimen: 1
================================================================================
```

### Test 2: Import Test

```bash
$ cd scripts
$ python3 -c "from therapeutic_approach_abstractor import match_regimen_to_protocol; print('Import successful')"
```

**Output:**
```
  ✅ V5.0: Loaded expanded protocol knowledge base (42 protocols)
Import successful
```

### Test 3: Query Function Tests

```python
# Query by indication
protocols = get_protocols_by_indication("medulloblastoma")
# Returns: ACNS0331, ACNS0332, ACNS0334, SJMB12, SJMB03, etc.

# Query by signature agent
protocols = get_protocols_by_signature_agent("nelarabine")
# Returns: [AALL0434]  # Only protocol using nelarabine

# Query by radiation signature
protocols = get_protocols_by_radiation_signature(dose_gy=18.0)
# Returns: [SJMB12 (WNT stratum), ACNS0232 (germinoma)]

# Query by protocol ID
protocol = get_protocol_by_id("acns0332")
# Returns: Full ACNS0332 protocol details

# Query by era
protocols = get_protocols_by_era(2010, 2015)
# Returns: All protocols active between 2010-2015
```

---

## Clinical Use Cases

### Use Case 1: Protocol-Aware Clinical Summary

**Goal:** Generate clinical summary that identifies likely protocol enrollment

**Input:** Patient with medulloblastoma who received:
- Surgery
- CSI 36 Gy
- Carboplatin during RT
- 6 cycles cisplatin/vincristine/cyclophosphamide
- Isotretinoin maintenance

**Output:**

```markdown
## Treatment Summary (V5.0 Therapeutic Approach)

### Line 1: COG ACNS0332 (High-Risk Medulloblastoma)
- **Protocol Match Confidence:** High (95%)
- **Evidence Level:** Standard of Care
- **Trial ID:** ACNS0332
- **Era:** 2004-2015
- **Matching Method:** Signature Agent (carboplatin + isotretinoin)
- **Regimen:** COG ACNS0332 (High-Risk Medulloblastoma)
- **Reference:** JAMA Oncology 2021, NCT00392327
- **Treatment Intent:** Curative
- **Duration:** 196 days
- **Status:** Completed

**Treatment Components:**
- Surgery: Subtotal resection
- Radiation: CSI 36 Gy + posterior fossa boost (total 54 Gy)
- Chemotherapy: 6 cycles cisplatin/vincristine/cyclophosphamide
- Maintenance: Isotretinoin 160 mg/m² ×12 months

**Best Response:** Stable disease
```

### Use Case 2: Protocol-Based Survival Analysis

**Goal:** Stratify patients by protocol for outcome analysis

**Code:**

```python
import pandas as pd
from protocol_knowledge_base import get_protocol_by_id

# Load patient cohort
patients = pd.read_json('patient_artifacts.json')

# Extract protocol matches
for idx, patient in patients.iterrows():
    therapeutic_approach = patient['therapeutic_approach']
    line_1 = therapeutic_approach['lines_of_therapy'][0]
    protocol_id = line_1['regimen']['protocol_id']

    if protocol_id:
        protocol = get_protocol_by_id(protocol_id)
        patient['protocol_name'] = protocol['name']
        patient['evidence_level'] = protocol['evidence_level']
        patient['era'] = protocol['era']
    else:
        patient['protocol_name'] = 'Unknown'

# Survival analysis by protocol
survival_by_protocol = patients.groupby('protocol_name').agg({
    'overall_survival_days': 'median',
    'progression_free_survival_days': 'median',
    'patient_id': 'count'
})

print(survival_by_protocol)
```

**Output:**

```
Protocol Name                              OS (days)  PFS (days)  N
COG ACNS0331 (Medulloblastoma)             1825       1460        45
COG ACNS0332 (High-Risk Medulloblastoma)   1095       730         32
Modified Stupp Protocol                    548        365         28
SJMB12 (Molecular Risk-Adapted MB)         2190       1825        15
Unknown                                    912        547         12
```

### Use Case 3: Protocol Deviation Detection

**Goal:** Identify patients with protocol deviations for quality review

**Code:**

```python
# Find patients with protocol deviations
for idx, patient in patients.iterrows():
    therapeutic_approach = patient['therapeutic_approach']
    line_1 = therapeutic_approach['lines_of_therapy'][0]
    deviations = line_1['regimen']['deviations_from_protocol']

    if deviations:
        print(f"Patient {patient['patient_id']}:")
        print(f"  Protocol: {line_1['regimen']['regimen_name']}")
        print(f"  Deviations: {', '.join(deviations)}")
        print()
```

**Output:**

```
Patient CBTN-001:
  Protocol: COG ACNS0331 (Medulloblastoma)
  Deviations: CSI dose 30 Gy (expected 23.4 Gy), Only 4 chemo cycles (expected 6)

Patient CBTN-045:
  Protocol: Modified Stupp Protocol
  Deviations: No adjuvant temozolomide (stopped after concurrent phase)
```

---

## Limitations and Future Enhancements

### Current Limitations

1. **Hardcoded Protocol Knowledge Base**
   - All 42 protocols are hardcoded in `protocol_knowledge_base.py`
   - Updates require code changes
   - No dynamic protocol loading from external databases

2. **Limited to Pediatric Oncology**
   - Current protocols focus on pediatric CNS tumors, leukemia, and solid tumors
   - Adult protocols not yet included
   - Rare tumor protocols may be missing

3. **No Temporal Evolution Tracking**
   - Protocols may have amendments over time (not captured)
   - Dosing modifications not tracked
   - Trial arm closures/openings not modeled

4. **Matching Algorithm Simplicity**
   - Component matching uses simple scoring (not ML-based)
   - No Bayesian inference
   - No uncertainty quantification

5. **No Multi-Institution Variability**
   - Assumes standard protocol implementation
   - Institutional variations not modeled
   - Off-protocol use not flagged

### Future Enhancements (V5.1 - V5.5)

#### V5.1: Dynamic Protocol Loading

**Goal:** Load protocols from external databases/APIs

```python
from protocol_knowledge_base import load_protocols_from_api

# Load from ClinicalTrials.gov API
protocols = load_protocols_from_api(
    source='clinicaltrials.gov',
    disease='medulloblastoma',
    status='recruiting'
)

# Load from institutional databases
protocols = load_protocols_from_database(
    connection_string='postgresql://...',
    table='cog_protocols'
)
```

**Benefits:**
- Always up-to-date protocol information
- No code changes required for new protocols
- Institutional customization

#### V5.2: Machine Learning-Based Protocol Matching

**Goal:** Train ML model on labeled protocol enrollments

```python
from protocol_matcher import ProtocolMatcherML

# Train on labeled data
matcher = ProtocolMatcherML()
matcher.train(
    training_data='labeled_protocol_enrollments.csv',
    features=['drugs', 'radiation_dose', 'diagnosis', 'age', 'era']
)

# Predict protocol
prediction = matcher.predict(patient_features)
# Returns: {'protocol': 'acns0332', 'confidence': 0.92, 'explanation': '...'}
```

**Benefits:**
- Higher accuracy (learns from data)
- Uncertainty quantification
- Explainable predictions

#### V5.3: Temporal Protocol Evolution

**Goal:** Track protocol amendments and era-specific variations

```python
protocol = get_protocol_by_id_and_date(
    protocol_id='acns0332',
    treatment_date='2008-03-15'
)
# Returns: ACNS0332 protocol as it existed on 2008-03-15
# (e.g., before isotretinoin arms closed in 2015)
```

**Benefits:**
- Accurate historical protocol matching
- Amendment tracking
- Trial phase transitions

#### V5.4: Adult Oncology Protocol Integration

**Goal:** Expand to adult protocols (RTOG, ECOG, etc.)

```python
# Adult GBM protocols
adult_protocols = get_protocols_by_indication("glioblastoma", age_group="adult")
# Returns: [Stupp Protocol, RTOG 0525, RTOG 0825, CheckMate 143, etc.]
```

**Benefits:**
- Cross-age comparisons
- Pediatric → adult transition patients
- Comprehensive coverage

#### V5.5: Protocol-Guided Treatment Recommendations

**Goal:** Use protocol knowledge to suggest next-line therapies

```python
from protocol_recommender import recommend_next_line

# Patient just progressed on Line 1 (ACNS0331)
recommendations = recommend_next_line(
    patient=patient,
    prior_lines=['acns0331'],
    progression_pattern='distant_mets',
    molecular_features={'tp53_mutant': True}
)

# Returns ranked recommendations
# 1. ACNS0821 TIB arm (bevacizumab/irinotecan/TMZ for recurrent MB)
# 2. PNOC013 (immunotherapy trial)
# 3. GemPOx (salvage chemotherapy)
```

**Benefits:**
- Clinical decision support
- Evidence-based recommendations
- Trial matching for recurrent disease

---

## Maintenance and Updates

### Adding New Protocols

To add a new protocol to the knowledge base:

1. **Edit `protocol_knowledge_base.py`**

2. **Add to appropriate category dictionary:**

```python
NEW_PROTOCOL_CATEGORY = {
    "protocol_key": {
        "name": "Protocol Full Name",
        "reference": "Publication reference",
        "trial_id": "NCT ID or COG ID",
        "indications": ["indication_1", "indication_2"],
        "evidence_level": "phase_3_trial",
        "era": "2020-present",
        "components": {
            # Treatment components
        },
        "signature_agents": ["drug1", "drug2"],
        "signature_radiation": {"dose_gy": 60, "type": "focal"},
        "inference_clues": [
            "Clue 1 for identifying this protocol",
            "Clue 2 for identifying this protocol"
        ]
    }
}
```

3. **Add to ALL_PROTOCOLS dictionary:**

```python
ALL_PROTOCOLS = {
    **ORIGINAL_PEDIATRIC_CNS_PROTOCOLS,
    **COG_CNS_PROTOCOLS,
    **NEW_PROTOCOL_CATEGORY,  # Add here
    # ...
}
```

4. **Test:**

```bash
$ python3 protocol_knowledge_base.py
# Verify new protocol appears in statistics

$ python3 -c "from protocol_knowledge_base import get_protocol_by_id; print(get_protocol_by_id('protocol_key'))"
# Verify new protocol can be queried
```

5. **Document in this file** (V5_0_PROTOCOL_AUGMENTATION.md)

### Updating Existing Protocols

**To update protocol details:**

1. Edit `protocol_knowledge_base.py`
2. Find the protocol dictionary
3. Update fields as needed
4. Test import and queries
5. Document changes in this file

**Example:**

```python
# Update ACNS0332 with new reference
"acns0332": {
    "name": "COG ACNS0332 (High-Risk Medulloblastoma)",
    "reference": "JAMA Oncology 2021, NCT00392327, Updated analysis 2023",  # NEW
    # ...
}
```

### Version Control

**All protocol changes should be:**
- Committed to git with descriptive messages
- Documented in this file
- Tested before pushing to production

**Example commit message:**

```
Add ACNS1422 protocol (successor to ACNS0331)

- Added ACNS1422 to COG_CNS_PROTOCOLS
- Signature agents: vincristine, cisplatin, lomustine
- Molecular risk stratification (SHH, WNT, Group 3/4)
- Era: 2016-present
- References: ClinicalTrials.gov NCT02724579
```

---

## References

### Primary Data Sources

1. **CBTN REDCap Protocols CSV**
   - Children's Brain Tumor Network protocol database
   - 110+ trial arms with detailed regimen information
   - File: `docs/CBTN_REDCAP_Protocols.csv`

2. **Pediatric Oncology Treatment Protocols Reference**
   - Comprehensive protocol guide generated by ChatGPT Deep Research
   - 10 pages, 7,695 words
   - Inference guidelines and protocol fingerprints
   - File: `docs/Pediatric Oncology Treatment Protocols Reference.html`

### Clinical Trial Registries

- **ClinicalTrials.gov** - https://clinicaltrials.gov/
- **NCI PDQ (Physician Data Query)** - https://www.cancer.gov/publications/pdq
- **Children's Oncology Group (COG)** - https://childrensoncologygroup.org/
- **St. Jude Children's Research Hospital** - https://www.stjude.org/research.html
- **HemOnc.org** - https://hemonc.org/

### Key Publications

1. **ACNS0331:** Gajjar A, et al. JAMA Oncol. 2021. PubMed 34110925
2. **ACNS0332:** Gajjar A, et al. JAMA Oncol. 2021. NCT00392327
3. **ACNS0334:** Dhall G, et al. NCT00336024
4. **ACNS0423:** Cohen KJ, et al. PMC5035517
5. **SJMB12:** Robinson GW, et al. JCO. 2023
6. **ANBL0532:** Park JR, et al. (COG high-risk neuroblastoma)
7. **AALL0434:** Dunsmore KP, et al. NBK599994

---

## Appendix: Complete Protocol List

### Original V5.0 Protocols (3)

1. **stupp_protocol** - Modified Stupp Protocol (Stupp et al. NEJM 2005)
2. **cog_acns0331** - COG ACNS0331 (Medulloblastoma)
3. **checkmate_143** - CheckMate 143 / Nivolumab Salvage (NCT02017717)

### COG CNS Protocols (9)

4. **acns0332** - COG ACNS0332 (High-Risk Medulloblastoma)
5. **acns0334** - COG ACNS0334 (Infant Brain Tumors)
6. **acns0423** - COG ACNS0423 (High-Grade Glioma)
7. **acns0822** - COG ACNS0822 (High-Grade Glioma - Randomized)
8. **acns0831** - COG ACNS0831 (Ependymoma)
9. **acns0333** - COG ACNS0333 (Atypical Teratoid/Rhabdoid Tumor)
10. **acns0621** - COG ACNS0621 (DIPG with Vorinostat)
11. **acns0821** - COG ACNS0821 (Recurrent Medulloblastoma)
12. **acns0232** - COG ACNS0232 (CNS Germinoma)

### COG Leukemia/Lymphoma Protocols (2)

13. **aall0434** - COG AALL0434 (T-cell ALL)
14. **anhl0131** - COG ANHL0131 (B-cell NHL)

### COG Neuroblastoma Protocols (2)

15. **anbl0532** - COG ANBL0532 (High-Risk Neuroblastoma)
16. **anbl0531** - COG ANBL0531 (Intermediate-Risk Neuroblastoma)

### COG Solid Tumor Protocols (2)

17. **aren0532** - COG AREN0532 (Low-Risk Wilms)
18. **aren0533** - COG AREN0533 (Higher-Risk Wilms)

### St. Jude Protocols (5)

19. **sjmb12** - SJMB12 (Molecular Risk-Adapted Medulloblastoma)
20. **sjmb03** - SJMB03 (Medulloblastoma)
21. **sjyc07** - SJYC07 (Young Children Brain Tumors)
22. **sjatrt** - St. Jude AT/RT Protocol
23. **sj_dipg_bats** - St. Jude DIPG-BATS

### Consortium Protocols (9)

24. **pnoc003** - PNOC003 (Recurrent DIPG)
25. **pnoc007** - PNOC007 (Recurrent HGG)
26. **pnoc013** - PNOC013 (DIPG Immunotherapy)
27. **pbtc026** - PBTC-026 (DIPG with Lenalidomide)
28. **pbtc027** - PBTC-027 (DIPG with Cilengitide)
29. **pbtc030** - PBTC-030 (DIPG with Vorinostat)
30. **pbtc045** - PBTC-045 (DIPG with Paxalisib)
31. **head_start_ii** - Head Start II (Infant Brain Tumors)
32. **head_start_iii** - Head Start III (Infant Brain Tumors)

### Legacy Protocols (5)

33. **ccg_99701** - CCG-99701 (Medulloblastoma)
34. **ccg_99703** - CCG-99703 (Infant Brain Tumor)
35. **sjmb96** - SJMB-96 (Medulloblastoma)
36. **ccg_a5971** - CCG-A5971 (Lymphoblastic Lymphoma)
37. **ccg_a9952** - CCG-A9952 (Hodgkin Lymphoma)

### Salvage/Experimental Protocols (5)

38. **sjdawn** - SJDAWN (DIPG Targeted Therapy)
39. **gempox** - GemPOx (Salvage Chemotherapy)
40. **dfmo** - DFMO (Maintenance Therapy)
41. **etmr_one** - ETMR One (Embryonal Tumor Protocol)
42. **selumetinib_nf1** - 11-C-0161 (Selumetinib for NF1 Plexiform Neurofibromas)

---

## Changelog

### 2025-11-09: V5.0 Protocol Augmentation (Initial Release)

**Added:**
- `protocol_knowledge_base.py` (1,800+ lines)
  - 42 structured protocols
  - Query functions for indication, signature agent, radiation signature, era
  - Protocol statistics and reporting
- Enhanced `therapeutic_approach_abstractor.py`
  - 3-step protocol matching algorithm
  - Signature agent matching with +20 bonus
  - Radiation signature matching with +15 bonus
  - Expanded protocol match output (trial_id, era, matching_method)
- Documentation: `V5_0_PROTOCOL_AUGMENTATION.md` (this file)

**Modified:**
- `match_regimen_to_protocol()` function
  - Now uses expanded protocol knowledge base
  - Multi-step matching with fingerprint detection
  - Backward compatible with original 3-protocol KB

**Data Sources Integrated:**
- CBTN REDCap Protocols CSV (110+ trial arms)
- Pediatric Oncology Treatment Protocols Reference HTML (comprehensive guide)

**Testing:**
- Module import test: ✅ Pass
- Protocol statistics test: ✅ Pass (42 protocols loaded)
- Query function tests: ✅ Pass

---

## Contact and Support

For questions, issues, or feature requests related to the V5.0 Protocol Augmentation:

1. **GitHub Issues:** Open issue in BRIM_Analytics repository
2. **Documentation:** Refer to this file and source code comments
3. **Testing:** Run `python3 protocol_knowledge_base.py` for self-test

**Future Agents:** This document provides complete context for continuing V5.0 development. All protocol definitions, matching algorithms, and data sources are documented here.
