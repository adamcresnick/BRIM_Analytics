# Usage Examples - Common Recipes & Use Cases

## Quick Start Examples

### Example 1: Basic Run with Defaults

**Scenario**: Match CBTN enrollment to CHOP database only.

```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/ID_Crosswalk

python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output ~/Downloads/stg_cbtn_enrollment_with_fhir_id.csv
```

**Expected Output**:
```
=== Database: chop ===
Processing database: chop
Querying CHOP (fhir_v2_prd_db.patient)...
Athena query submitted: 4bca8e3f-9d2e-4a5a-a123-456789abcdef
Query execution complete after 8.3 seconds
Query returned 245,123 rows

Processing enrollment file (6,599 records)...
Matched 1,877 records (28.4% of enrollment file)
  By MRN exact: 1,241
  By DOB + exact name: 320
  By DOB + name initial: 93
  By DOB only (single): 223 (_VERIFY)

Match summary saved to: ~/Downloads/stg_cbtn_enrollment_with_fhir_id_match_summary.txt
```

### Example 2: Multi-Database Run

**Scenario**: Match against both CHOP and UCSF databases.

```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output ~/Downloads/stg_cbtn_enrollment_with_fhir_id_multi.csv \
  --databases chop ucsf
```

**Expected Output**:
```
=== Database: chop ===
... (CHOP matching statistics)

=== Database: ucsf ===
Processing database: ucsf
Querying UCSF (fhir_v2_ucsf_prd_db.patient)...
...
Matched 149 records (2.3% of enrollment file)
  By MRN exact: 0
  By DOB + exact name: 67
  By DOB + name initial: 32
  By DOB only (single): 50 (_VERIFY)

=== TOTAL ACROSS ALL DATABASES ===
Total matched: 2,026 (30.7% of enrollment file)
Total unmatched: 4,573 (69.3% of enrollment file)
```

### Example 3: Dry Run (Test Query Only)

**Scenario**: Test Athena connection without processing enrollment file.

```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --dry-run
```

**Expected Output**:
```
DRY RUN MODE - Testing queries only

=== Database: chop ===
Querying CHOP (fhir_v2_prd_db.patient)...
Query successful: 245,123 rows returned

Database schema:
  - id: 245,123 non-null values
  - identifier_mrn: 245,089 non-null values (34 missing)
  - birth_date: 245,123 non-null values
  - given_name: 244,998 non-null values (125 missing)
  - family_name: 245,001 non-null values (122 missing)

Dry run complete. No matching performed.
```

---

## Advanced Use Cases

### Use Case 1: Incremental Updates

**Scenario**: New enrollment records added since last run. Only process new records.

**Step 1**: Identify new records
```bash
python3 -c "
import pandas as pd

# Load previous output
prev_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_2025-10-20.csv')
# Load current enrollment
curr_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_final_10262025.csv')

# Find new records
new_ids = set(curr_df['research_id']) - set(prev_df['research_id'])
new_df = curr_df[curr_df['research_id'].isin(new_ids)]

new_df.to_csv('~/Downloads/stg_cbtn_enrollment_NEW.csv', index=False)
print(f'Found {len(new_df)} new records')
"
```

**Step 2**: Process only new records
```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_NEW.csv \
  --output ~/Downloads/stg_cbtn_enrollment_NEW_with_fhir_id.csv \
  --databases chop ucsf
```

**Step 3**: Merge with previous results
```bash
python3 -c "
import pandas as pd

prev_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_2025-10-20.csv')
new_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_NEW_with_fhir_id.csv')

merged_df = pd.concat([prev_df, new_df], ignore_index=True)
merged_df.to_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_UPDATED.csv', index=False)
print(f'Merged: {len(prev_df)} previous + {len(new_df)} new = {len(merged_df)} total')
"
```

### Use Case 2: Re-run Unmatched Records

**Scenario**: Re-process only records that failed to match (maybe new data in Athena).

**Step 1**: Extract unmatched records
```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id.csv')
unmatched_df = df[df['FHIR_ID'].isna()]

unmatched_df.to_csv('~/Downloads/stg_cbtn_enrollment_UNMATCHED.csv', index=False)
print(f'Extracted {len(unmatched_df)} unmatched records ({len(unmatched_df)/len(df)*100:.1f}%)')
"
```

**Step 2**: Re-run matching
```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_UNMATCHED.csv \
  --output ~/Downloads/stg_cbtn_enrollment_UNMATCHED_reprocessed.csv \
  --databases chop ucsf
```

**Step 3**: Merge any new matches
```bash
python3 -c "
import pandas as pd

original_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id.csv')
reprocessed_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_UNMATCHED_reprocessed.csv')

# Update original with new matches
for idx, row in reprocessed_df[reprocessed_df['FHIR_ID'].notna()].iterrows():
    mask = original_df['research_id'] == row['research_id']
    original_df.loc[mask, 'FHIR_ID'] = row['FHIR_ID']
    original_df.loc[mask, 'match_strategy'] = row['match_strategy']
    original_df.loc[mask, 'match_database'] = row['match_database']

original_df.to_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_UPDATED.csv', index=False)
print('Updated original file with new matches')
"
```

### Use Case 3: Database-Specific Processing

**Scenario**: Process CHOP and UCSF separately, then merge.

**CHOP only**:
```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output ~/Downloads/stg_cbtn_enrollment_CHOP_only.csv \
  --databases chop
```

**UCSF only**:
```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output ~/Downloads/stg_cbtn_enrollment_UCSF_only.csv \
  --databases ucsf
```

**Merge** (CHOP takes precedence):
```bash
python3 -c "
import pandas as pd

chop_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_CHOP_only.csv')
ucsf_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_UCSF_only.csv')

# Start with CHOP
merged_df = chop_df.copy()

# Add UCSF matches for records not matched in CHOP
chop_matched_ids = set(chop_df[chop_df['FHIR_ID'].notna()]['research_id'])
ucsf_new_matches = ucsf_df[
    (ucsf_df['FHIR_ID'].notna()) & 
    (~ucsf_df['research_id'].isin(chop_matched_ids))
]

for idx, row in ucsf_new_matches.iterrows():
    mask = merged_df['research_id'] == row['research_id']
    merged_df.loc[mask, 'FHIR_ID'] = row['FHIR_ID']
    merged_df.loc[mask, 'match_strategy'] = row['match_strategy']
    merged_df.loc[mask, 'match_database'] = row['match_database']

merged_df.to_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_merged.csv', index=False)
print(f'CHOP matches: {len(chop_matched_ids)}')
print(f'UCSF new matches: {len(ucsf_new_matches)}')
print(f'Total matches: {merged_df[\"FHIR_ID\"].notna().sum()}')
"
```

---

## Analysis & Reporting Examples

### Example 4: Generate Match Statistics by Database

```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv')

print('=== MATCH STATISTICS BY DATABASE ===\n')

for db in ['chop', 'ucsf']:
    db_matches = df[df['match_database'] == db]
    print(f'{db.upper()}:')
    print(f'  Total matches: {len(db_matches)}')
    print(f'  Match strategies:')
    for strategy in db_matches['match_strategy'].value_counts().items():
        print(f'    {strategy[0]}: {strategy[1]}')
    print()

print('UNMATCHED:')
unmatched = df[df['FHIR_ID'].isna()]
print(f'  Total unmatched: {len(unmatched)} ({len(unmatched)/len(df)*100:.1f}%)')
"
```

### Example 5: Identify High-Confidence vs Needs-Verification

```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv')

# High-confidence: MRN exact or DOB + exact name match
high_conf = df[df['match_strategy'].str.contains('mrn_exact|dob_name_exact', na=False, regex=True)]
print(f'HIGH CONFIDENCE: {len(high_conf)} records ({len(high_conf)/len(df)*100:.1f}%)')
print('  Strategies:', high_conf['match_strategy'].unique())

# Needs verification: VERIFY suffix
needs_verify = df[df['match_strategy'].str.contains('VERIFY', na=False)]
print(f'\nNEEDS VERIFICATION: {len(needs_verify)} records ({len(needs_verify)/len(df)*100:.1f}%)')
print('  Strategies:', needs_verify['match_strategy'].unique())

# No match
no_match = df[df['FHIR_ID'].isna()]
print(f'\nNO MATCH: {len(no_match)} records ({len(no_match)/len(df)*100:.1f}%)')

# Save verification queue
needs_verify.to_csv('~/Downloads/verification_queue.csv', index=False)
print(f'\nVerification queue saved to: ~/Downloads/verification_queue.csv')
"
```

### Example 6: Compare Match Rates Across Versions

```bash
python3 -c "
import pandas as pd

v1_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id.csv')  # Basic MRN-only
v3_df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv')  # Generic

print('=== VERSION COMPARISON ===\n')

v1_matches = v1_df['FHIR_ID'].notna().sum()
v3_matches = v3_df['FHIR_ID'].notna().sum()
improvement = v3_matches - v1_matches

print(f'V1 (MRN-only): {v1_matches} matches ({v1_matches/len(v1_df)*100:.1f}%)')
print(f'V3 (Generic):  {v3_matches} matches ({v3_matches/len(v3_df)*100:.1f}%)')
print(f'Improvement:   +{improvement} matches (+{improvement/v1_matches*100:.1f}%)')

# New matches by strategy
v1_matched_ids = set(v1_df[v1_df['FHIR_ID'].notna()]['research_id'])
v3_new_matches = v3_df[
    (v3_df['FHIR_ID'].notna()) & 
    (~v3_df['research_id'].isin(v1_matched_ids))
]

print(f'\nNew matches in V3: {len(v3_new_matches)}')
print('By strategy:')
for strategy, count in v3_new_matches['match_strategy'].value_counts().items():
    print(f'  {strategy}: {count}')
"
```

---

## Data Quality Checks

### Example 7: Validate MRN Format

**Check for MRNs that don't match expected format**:

```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_final_10262025.csv')

# Assuming MRN should be 8-digit numeric
invalid_mrns = df[~df['mrn'].astype(str).str.match(r'^\d{8}$')]

print(f'Total records: {len(df)}')
print(f'Invalid MRN format: {len(invalid_mrns)} ({len(invalid_mrns)/len(df)*100:.1f}%)')

if len(invalid_mrns) > 0:
    print('\nExamples (first 10):')
    print(invalid_mrns[['research_id', 'mrn']].head(10))
    
    # Save for review
    invalid_mrns.to_csv('~/Downloads/invalid_mrn_format.csv', index=False)
    print('\nFull list saved to: ~/Downloads/invalid_mrn_format.csv')
"
```

### Example 8: Check for Duplicate MRNs

**Identify potential duplicate enrollments**:

```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_final_10262025.csv')

# Find MRNs appearing multiple times
duplicates = df[df.duplicated(subset=['mrn'], keep=False)].sort_values('mrn')

print(f'Total records: {len(df)}')
print(f'Records with duplicate MRNs: {len(duplicates)}')
print(f'Unique duplicate MRNs: {duplicates[\"mrn\"].nunique()}')

if len(duplicates) > 0:
    print('\nDuplicate MRN examples:')
    for mrn in duplicates['mrn'].unique()[:5]:
        mrn_records = duplicates[duplicates['mrn'] == mrn]
        print(f'  MRN [REDACTED]: {len(mrn_records)} records')
        print(f'    Research IDs: {mrn_records[\"research_id\"].tolist()}')
    
    duplicates.to_csv('~/Downloads/duplicate_mrns.csv', index=False)
    print('\nFull list saved to: ~/Downloads/duplicate_mrns.csv')
"
```

### Example 9: Validate Date of Birth

**Check for invalid/suspicious DOBs**:

```bash
python3 -c "
import pandas as pd
from datetime import datetime, timedelta

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_final_10262025.csv')
df['dob'] = pd.to_datetime(df['dob'], errors='coerce')

# Check for future dates
future_dobs = df[df['dob'] > datetime.now()]
print(f'Future DOBs: {len(future_dobs)}')

# Check for very old dates (>100 years ago)
hundred_years_ago = datetime.now() - timedelta(days=365*100)
ancient_dobs = df[df['dob'] < hundred_years_ago]
print(f'DOBs >100 years ago: {len(ancient_dobs)}')

# Check for missing DOBs
missing_dobs = df[df['dob'].isna()]
print(f'Missing DOBs: {len(missing_dobs)}')

# Check for common placeholder dates
placeholder_dates = ['1900-01-01', '2000-01-01', '1970-01-01']
for date in placeholder_dates:
    count = (df['dob'] == pd.to_datetime(date)).sum()
    if count > 0:
        print(f'Potential placeholder date {date}: {count} records')
"
```

---

## Integration Examples

### Example 10: Export for BRIM Workflow

**Prepare matched data for BRIM Analytics extraction**:

```bash
python3 -c "
import pandas as pd

# Load matched enrollment
df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv')

# Only high-confidence matches (exclude VERIFY)
high_conf_df = df[
    (df['FHIR_ID'].notna()) & 
    (~df['match_strategy'].str.contains('VERIFY', na=False))
]

print(f'Total enrollment records: {len(df)}')
print(f'High-confidence matches: {len(high_conf_df)} ({len(high_conf_df)/len(df)*100:.1f}%)')

# Create patient list for BRIM extraction
patient_list = high_conf_df[['research_id', 'FHIR_ID', 'match_database']].copy()
patient_list.rename(columns={'FHIR_ID': 'fhir_patient_id'}, inplace=True)

patient_list.to_csv('~/Downloads/brim_extraction_patient_list.csv', index=False)
print('\nPatient list for BRIM saved to: ~/Downloads/brim_extraction_patient_list.csv')

# Summary by database
print('\nBy database:')
for db in patient_list['match_database'].unique():
    count = (patient_list['match_database'] == db).sum()
    print(f'  {db.upper()}: {count}')
"
```

### Example 11: Create Athena Query for Downstream Analysis

**Generate SQL to use matched FHIR IDs in Athena**:

```bash
python3 -c "
import pandas as pd

df = pd.read_csv('~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv')

# Only high-confidence matches
high_conf_df = df[
    (df['FHIR_ID'].notna()) & 
    (~df['match_strategy'].str.contains('VERIFY', na=False))
]

# Generate SQL IN clause for CHOP
chop_ids = high_conf_df[high_conf_df['match_database'] == 'chop']['FHIR_ID'].tolist()
chop_sql = 'SELECT * FROM fhir_v2_prd_db.medication WHERE patient_id IN (\n  '
chop_sql += ',\n  '.join([f\"'{id}'\" for id in chop_ids[:50]])  # First 50 for example
chop_sql += '\n);'

# Save to file
with open('~/Downloads/athena_query_chop_patients.sql', 'w') as f:
    f.write(chop_sql)

print(f'Generated SQL for {len(chop_ids)} CHOP patients')
print(f'SQL saved to: ~/Downloads/athena_query_chop_patients.sql')
print('\nExample (first 10 IDs):')
print(chop_sql.split('\n')[:12])
"
```

---

## Troubleshooting Examples

### Example 12: Debug Missing Matches

**For a specific research_id, check why it didn't match**:

```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output /dev/null \
  --debug \
  --research-id CBT12345  # Replace with actual research_id
```

**Expected debug output**:
```
=== DEBUG MODE: Research ID CBT12345 ===

Enrollment record:
  MRN: [REDACTED]
  DOB: [REDACTED]
  Name: [REDACTED]

=== CHOP Database ===
  Step 1: MRN exact match
    Query: SELECT id FROM patient WHERE identifier_mrn = '[REDACTED]'
    Result: 0 matches
  
  Step 2: DOB + exact name match
    Query: SELECT id, given_name, family_name FROM patient WHERE birth_date = '[REDACTED]'
    Result: 3 candidates
    Candidate 1: Name similarity = 0.42 (below threshold 0.80)
    Candidate 2: Name similarity = 0.51 (below threshold 0.80)
    Candidate 3: Name similarity = 0.33 (below threshold 0.80)
    No matches
  
  Step 3: DOB + name initial match
    Result: 0 matches (no candidates with matching first initial)

=== UCSF Database ===
  ... (same steps)

FINAL RESULT: No match found
```

### Example 13: Test Athena Connection

**Verify AWS credentials and database access**:

```bash
python3 scripts/list_athena_databases.py
```

**Expected output**:
```
=== Athena Databases ===

Using AWS profile: radiant-prod
Region: us-east-1

Available databases:
  1. fhir_v2_prd_db (Tables: 47)
  2. fhir_v2_ucsf_prd_db (Tables: 45)
  3. fhir_prd_db (Tables: 38)
  4. athena_logs (Tables: 2)
  ... (more databases)

Test query successful!
```

### Example 14: Estimate Query Cost

**Check Athena data scanned before running full query**:

```bash
python3 -c "
import boto3
import time

session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
athena = session.client('athena')

# Test query
query = '''
SELECT COUNT(*) as row_count
FROM fhir_v2_prd_db.patient
'''

response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': 'fhir_v2_prd_db'},
    ResultConfiguration={'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'}
)

query_id = response['QueryExecutionId']

# Wait for completion
while True:
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status['QueryExecution']['Status']['State']
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    time.sleep(1)

if state == 'SUCCEEDED':
    stats = status['QueryExecution']['Statistics']
    data_scanned = stats.get('DataScannedInBytes', 0) / (1024**3)  # Convert to GB
    cost_estimate = data_scanned * 5.00  # \$5 per TB scanned
    
    print(f'Data scanned: {data_scanned:.2f} GB')
    print(f'Estimated cost: \${cost_estimate:.4f}')
    print(f'Query runtime: {stats.get(\"EngineExecutionTimeInMillis\", 0)/1000:.1f} seconds')
else:
    print(f'Query failed: {status[\"QueryExecution\"][\"Status\"][\"StateChangeReason\"]}')
"
```

---

## Automation Examples

### Example 15: Scheduled Daily Updates

**Cron job to run daily incremental matching**:

```bash
# Add to crontab: crontab -e
0 2 * * * /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/ID_Crosswalk/scripts/daily_update.sh
```

**Create `daily_update.sh`**:
```bash
#!/bin/bash

set -e  # Exit on error

SCRIPT_DIR="/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/ID_Crosswalk"
OUTPUT_DIR="$HOME/Downloads"
DATE=$(date +%Y%m%d)

# Log file
LOG="$SCRIPT_DIR/logs/daily_update_$DATE.log"
mkdir -p "$SCRIPT_DIR/logs"

echo "=== Daily Update Started: $(date) ===" | tee -a "$LOG"

# Activate AWS session (requires manual SSO login in previous session)
export AWS_PROFILE=radiant-prod

# Run matching
python3 "$SCRIPT_DIR/scripts/match_cbtn_multi_database.py" \
  --input "$OUTPUT_DIR/stg_cbtn_enrollment_latest.csv" \
  --output "$OUTPUT_DIR/stg_cbtn_enrollment_with_fhir_id_$DATE.csv" \
  --databases chop ucsf \
  2>&1 | tee -a "$LOG"

echo "=== Daily Update Completed: $(date) ===" | tee -a "$LOG"

# Optional: Email notification
# mail -s "CBTN ID Crosswalk Daily Update - $DATE" user@example.com < "$LOG"
```

### Example 16: Batch Processing Multiple Enrollment Files

**Process multiple cohorts/studies at once**:

```bash
#!/bin/bash

for cohort in CBTN PNOC INSTRuCT; do
  echo "Processing cohort: $cohort"
  
  python3 scripts/match_cbtn_multi_database.py \
    --input ~/Downloads/stg_${cohort}_enrollment.csv \
    --output ~/Downloads/stg_${cohort}_enrollment_with_fhir_id.csv \
    --databases chop ucsf
  
  echo "Completed: $cohort"
  echo "---"
done
```

---

## Best Practices Summary

1. **Always use --dry-run first** to test queries and validate connection
2. **Process incrementally** when possible (new records only)
3. **Save intermediate outputs** with timestamps for version control
4. **Review VERIFY records** before using in downstream analysis
5. **Monitor query costs** using test queries before full runs
6. **Use database-specific processing** if different strategies needed
7. **Document all parameter choices** in run logs
8. **Keep outputs secure** (PHI data - encrypt, restrict access, delete when done)

---

**Document Version**: 1.0  
**Last Updated**: October 26, 2025  
**Classification**: Internal Use Only  
**Author**: RADIANT/BRIM Analytics Team
