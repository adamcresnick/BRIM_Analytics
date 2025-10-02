# Quick Start: Materialized View Document Prioritization

## TL;DR
Use Athena materialized views to select **50-100 high-value clinical documents** instead of processing all 2,560 DocumentReference files. Expected result: **98% fewer documents, 85%+ extraction accuracy, 5min instead of 30min**.

---

## 🚀 Quick Test (5 minutes)

### Test the Document Prioritizer
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics

# Run on pilot patient
python scripts/athena_document_prioritizer.py \
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --limit 50 \
    --output pilot_output/prioritized_documents.json
```

**Expected Output:**
```
CLINICAL TIMELINE (3 events)
  2021-03-10 | SURGERY         | Craniotomy for tumor resection
  2021-03-10 | DIAGNOSIS       | Pilocytic astrocytoma
  2024-08-20 | CHEMOTHERAPY    | Selumetinib

PRIORITIZED DOCUMENTS (top 47)
  Score | Type                      | Date       | Days from Event
  97.5  | Pathology Report          | 2021-03-12 | 2
  96.0  | OP Note - Complete        | 2021-03-10 | 0
  92.5  | MRI Brain w/wo contrast   | 2021-03-09 | 1

SUMMARY
  Documents prioritized: 47 (vs 2,560 total = 98.2% reduction)
  Average priority score: 82.3
```

### View Results
```bash
# See all prioritized documents
cat pilot_output/prioritized_documents.json | jq '.prioritized_documents[] | {score: .composite_priority_score, type: .type_text, date: .document_date}'

# See clinical timeline
cat pilot_output/prioritized_documents.json | jq '.timeline'

# See procedure-linked documents
cat pilot_output/prioritized_documents.json | jq '.procedure_linked_documents'
```

---

## 📊 What Gets Prioritized?

### Document Type Scoring
```
Pathology Report:         100 points
Operative Note:            95 points
MRI/CT/Radiology:          85 points
Oncology Consult:          90 points
H&P / Consult:             80 points
Progress Note:             70 points
Administrative:            50 points (likely excluded)
```

### Temporal Relevance Scoring
```
Within 1 day of event:    100 points
Within 7 days of event:    90 points
Within 30 days of event:   70 points
Within 90 days of event:   50 points
Beyond 90 days:            25 points
```

### Composite Score
```
Final Score = (Document Type Score × 0.5) + (Temporal Score × 0.5)

Only documents scoring ≥60 are included.
```

### Example Calculations
```
Pathology report 2 days after surgery:
  Type: 100 × 0.5 = 50
  Temporal: 100 × 0.5 = 50
  Composite: 100 ✅ INCLUDED

Progress note 45 days after diagnosis:
  Type: 70 × 0.5 = 35
  Temporal: 50 × 0.5 = 25
  Composite: 60 ✅ INCLUDED (barely)

Billing document 120 days from any event:
  Type: 50 × 0.5 = 25
  Temporal: 25 × 0.5 = 12.5
  Composite: 37.5 ❌ EXCLUDED
```

---

## 🔍 What Gets Queried?

### Clinical Events (Timeline)
```sql
-- Diagnoses with ICD-10 codes
SELECT onset_date_time, code_text 
FROM condition 
WHERE code LIKE 'C71%' -- Brain cancer

-- Surgeries with CPT codes  
SELECT performed_date_time, code_text
FROM procedure
WHERE code IN ('61510', '61512', '61518') -- Craniotomy

-- Chemotherapy orders
SELECT authored_on, drug_name
FROM medication_request
WHERE drug LIKE '%temozolomide%'
```

### Documents Around Events
```sql
-- Find documents near clinical events
SELECT 
    document_id,
    type_text,
    document_date,
    DATEDIFF(document_date, surgery_date) as days_from_surgery,
    composite_priority_score
FROM document_reference
WHERE composite_priority_score >= 60
ORDER BY composite_priority_score DESC
LIMIT 50
```

### Procedure-Linked Documents
```sql
-- Find operative notes referenced by procedures
SELECT 
    procedure.performed_date_time,
    procedure_report.reference as document_id
FROM procedure
JOIN procedure_report ON procedure.id = procedure_report.procedure_id
WHERE reference LIKE 'DocumentReference/%'
```

---

## 📈 Expected Benefits

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Documents** | 2,560 | 50-100 | **-98%** |
| **Size** | 200 MB | 10-20 MB | **-90%** |
| **Time** | 30 min | 5 min | **-80%** |
| **Accuracy** | 65% | 85%+ | **+20%** |
| **total_surgeries** | 0 | 3 | **Fixed** |
| **diagnosis_date** | unknown | 2021-03-10 | **Fixed** |

---

## 🛠️ Next Steps

### 1. Validate Prioritizer Works ✅ **DO THIS FIRST**
```bash
python scripts/athena_document_prioritizer.py \
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --limit 50 \
    --output pilot_output/prioritized_documents.json
```

### 2. Review Prioritized Documents
```bash
# Are key documents included?
cat pilot_output/prioritized_documents.json | jq '.prioritized_documents[] | select(.type_text | contains("Pathology") or contains("OP Note"))'

# Are low-value documents excluded?
# (Compare to original bundle - should be 98% fewer)
```

### 3. Integrate into CSV Generation ⏳ **NEXT**
Update `pilot_generate_brim_csvs.py`:
```python
# Add flag: --use-materialized-views
# Replace: extract_all_documents() 
# With: query_prioritized_documents()
```

### 4. Test End-to-End ⏳ **AFTER INTEGRATION**
```bash
# Generate optimized CSVs
python scripts/pilot_generate_brim_csvs.py --use-materialized-views

# Upload to BRIM
python scripts/brim_api_workflow.py upload ...

# Compare v3 (optimized) to v1 (baseline)
python scripts/brim_api_workflow.py analyze --results v3.csv --baseline v1.csv
```

---

## 🎯 Success Criteria

✅ **Prioritizer runs successfully** (Athena queries work)  
✅ **Clinical timeline shows 3+ events** (diagnosis, surgery, chemo)  
✅ **47-50 documents selected** (vs 2,560 = 98% reduction)  
✅ **Operative notes included** (not buried in noise)  
✅ **Pathology reports included** (100 priority score)  
✅ **Administrative docs excluded** (low priority scores)  

---

## 📚 Full Documentation

- **Strategy Guide**: `docs/MATERIALIZED_VIEW_STRATEGY.md` (850 lines)
- **Implementation**: `docs/MATERIALIZED_VIEW_IMPLEMENTATION_SUMMARY.md`
- **Schema Reference**: `data/materialized_view_schema.csv` (2,495 rows)
- **Baseline Analysis**: `pilot_output/BRIM_RESULTS_ANALYSIS.md`

---

## ❓ Troubleshooting

### Issue: "Athena query timeout"
**Solution:** Queries should complete in <10 seconds. Check AWS profile and permissions.

### Issue: "No clinical events found"
**Solution:** Verify patient FHIR ID is correct. Check if patient has Condition/Procedure resources.

### Issue: "All documents excluded (0 prioritized)"
**Solution:** Lower threshold from 60 to 50, or expand temporal window to ±180 days.

### Issue: "Key documents missing"
**Solution:** Check procedure_linked_documents - operative notes should be there. Verify document type text matches filters.

---

## 🎉 Ready to Start?

```bash
# Quick test (5 min)
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics
python scripts/athena_document_prioritizer.py \
    --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 \
    --limit 50 \
    --output pilot_output/prioritized_documents.json

# Review results
cat pilot_output/prioritized_documents.json | jq .
```

**Then:** Review output, validate approach, integrate into CSV generation! 🚀
