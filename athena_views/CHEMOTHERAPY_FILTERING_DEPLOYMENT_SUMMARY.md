# Chemotherapy Drug Filtering - Deployment Summary

## Date: October 26, 2025

## Objective
Filter out supportive care medications (~800K+ orders) from the v_chemo_medications view to focus on therapeutic chemotherapy drugs only.

## Problem Statement
The v_chemo_medications view was including ALL medications from investigational drug trials, including:
- Pain medications (morphine, fentanyl, acetaminophen)
- Antiemetics (ondansetron, granisetron)
- Anesthetics (propofol, midazolam, lidocaine)
- Antibiotics and other supportive care

This inflated the dataset from ~250K therapeutic orders to 1.27M total orders.

## Solution Implementation

### 1. Drug Categorization
Added `drug_category` column to drugs.csv with 8 categories:

| Category | Count | Description | Action |
|----------|-------|-------------|--------|
| investigational_other | 1,240 | Non-therapeutic investigational drugs | **KEEP** |
| chemotherapy | 851 | Traditional chemotherapy agents | **KEEP** |
| targeted_therapy | 499 | Targeted cancer therapies | **KEEP** |
| supportive_care | 222 | Pain, nausea, anesthesia, etc. | **EXCLUDE** |
| investigational_therapy | 103 | Investigational cancer therapies | **KEEP** |
| immunotherapy | 91 | Immunotherapy agents | **KEEP** |
| hormone_therapy | 61 | Hormone therapies | **KEEP** |
| uncategorized | 3 | Unclassified drugs | **KEEP** |

**Total Drugs**: 3,070

### 2. Infrastructure Changes

#### Problem: AWS Athena Query String Limit
- Original approach: Inline VALUES in SQL view (worked at 309KB)
- After adding drug_category: 372KB (exceeds 256KB AWS limit)
- **Solution**: Migrate to S3-backed external table

#### New Architecture
```
┌──────────────────────────────────────┐
│  S3 Bucket                           │
│  chemotherapy-reference-data/        │
│  └── drugs.csv (292 KB)              │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  External Table                      │
│  fhir_prd_db.chemotherapy_drugs      │
│  (OpenCSVSerde)                      │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  View                                │
│  fhir_prd_db.v_chemotherapy_drugs    │
│  SELECT * FROM chemotherapy_drugs    │
└──────────────────────────────────────┘
```

### 3. SQL View Filter
Updated `v_chemo_medications` WHERE clause:
```sql
WHERE mr.status IN ('active', 'completed', 'stopped', 'on-hold')
    AND (
        cmm.chemo_drug_category NOT IN ('supportive_care')
        OR cmm.chemo_drug_category IS NULL
    )
```

## Deployment Steps

1. **Upload drugs.csv to S3**:
   ```bash
   aws s3 cp data_dictionary/chemo_reference/drugs.csv \
       s3://aws-athena-query-results-343218191717-us-east-1/chemotherapy-reference-data/drugs.csv \
       --profile radiant-prod
   ```

2. **Create External Table**:
   ```sql
   CREATE EXTERNAL TABLE fhir_prd_db.chemotherapy_drugs (
       drug_id STRING,
       preferred_name STRING,
       approval_status STRING,
       is_supportive_care STRING,
       rxnorm_in STRING,
       ncit_code STRING,
       normalized_key STRING,
       sources STRING,
       drug_category STRING
   )
   ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
   LOCATION 's3://aws-athena-query-results-343218191717-us-east-1/chemotherapy-reference-data/'
   TBLPROPERTIES ('skip.header.line.count'='1');
   ```

3. **Create View on Table**:
   ```sql
   CREATE OR REPLACE VIEW fhir_prd_db.v_chemotherapy_drugs AS
   SELECT drug_id, preferred_name, approval_status, rxnorm_in,
          ncit_code, normalized_key, sources, drug_category
   FROM fhir_prd_db.chemotherapy_drugs;
   ```

4. **Update v_chemo_medications View**:
   - Deployed updated view with supportive_care filter
   - Query ID: 49c2ca98-4dae-4fe8-a623-f768ddbdd95f

## Validation Results

### ✅ Drug Category Distribution
```
investigational_other: 1,240
chemotherapy:         851
targeted_therapy:     499
supportive_care:      222  (EXCLUDED)
investigational_therapy: 103
immunotherapy:        91
hormone_therapy:      61
uncategorized:        3
```

### ✅ Supportive Care Exclusion
```sql
SELECT COUNT(*) FROM v_chemo_medications
WHERE chemo_drug_category = 'supportive_care';
-- Result: 0 ✓
```

### Impact on Data (Estimated from Local Analysis)
- **BEFORE**: 1,278,298 medication orders
- **AFTER**: ~227,506 therapeutic orders (17.8%)
- **EXCLUDED**: ~1,027,787 supportive care orders (80.4%)

Top Excluded Drugs:
1. Dextrose: ~143K orders
2. Ondansetron: ~117K orders
3. Diphenhydramine: ~111K orders
4. Propofol: ~86K orders
5. Acetaminophen: ~71K orders

## Next Steps

1. **Validate Patient Coverage**: Check how many patients have zero chemotherapy orders after filtering
2. **Rebuild Timelines**: Update timeline.duckdb with filtered medication data
3. **Re-run Paradigm Analysis**: Execute treatment paradigm analysis with clean data
4. **Production Deployment**: Push changes to production branch

## Files Modified

### New Files
- `views/CREATE_CHEMOTHERAPY_DRUGS_TABLE.sql` - External table definition
- `views/V_CHEMOTHERAPY_DRUGS_NEW.sql` - View on external table
- `deploy_large_view.sh` - Deployment script for large SQL files

### Modified Files
- `data_dictionary/chemo_reference/drugs.csv` - Added drug_category column
- `views/V_CHEMO_MEDICATIONS.sql` - Added supportive_care filter

### Backup Files
- `views/V_CHEMOTHERAPY_DRUGS.sql.bak` - Original inline VALUES approach (309KB)

## Lessons Learned

1. **AWS Athena Limits**: Query string limited to 256KB - must use external tables for large reference data
2. **Schema Validation**: Always verify CSV schema matches table definition (learned: is_supportive_care column)
3. **Incremental Testing**: Validate at each step (drug categories → exclusion → patient impact)

## Contacts
- **Deployed By**: Claude Code
- **Reviewed By**: Adam Resnick
- **Date**: October 26, 2025
