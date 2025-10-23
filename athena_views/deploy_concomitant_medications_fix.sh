#!/bin/bash

# Deploy fixed v_concomitant_medications view to Athena
# Fix: Remove dependency on v_medications.medication_start_date which is always NULL
# Pull directly from medication_request table with proper date computation

echo "================================================================================"
echo "DEPLOYING FIXED v_concomitant_medications VIEW"
echo "================================================================================"
echo ""
echo "This fix addresses the critical bug where v_concomitant_medications was empty"
echo "because it depended on v_medications.medication_start_date which is always NULL."
echo ""
echo "The fix:"
echo "  - Pulls directly from medication_request table"
echo "  - Computes dates using the same logic as all_medications CTE"
echo "  - Filters to chemotherapy using RxNorm codes"
echo ""

# Extract just the v_concomitant_medications view definition from the file
echo "Step 1: Extracting view definition..."

# Find the line numbers for the view
START_LINE=$(grep -n "^CREATE OR REPLACE VIEW fhir_prd_db.v_concomitant_medications AS" views/DATETIME_STANDARDIZED_VIEWS.sql | cut -d: -f1)

if [ -z "$START_LINE" ]; then
    echo "ERROR: Could not find v_concomitant_medications view in DATETIME_STANDARDIZED_VIEWS.sql"
    exit 1
fi

# Find the end of the view (next CREATE OR REPLACE VIEW or end of file)
TOTAL_LINES=$(wc -l < views/DATETIME_STANDARDIZED_VIEWS.sql)
NEXT_VIEW_LINE=$(tail -n +$((START_LINE + 1)) views/DATETIME_STANDARDIZED_VIEWS.sql | grep -n "^CREATE OR REPLACE VIEW" | head -1 | cut -d: -f1)

if [ -z "$NEXT_VIEW_LINE" ]; then
    END_LINE=$TOTAL_LINES
else
    END_LINE=$((START_LINE + NEXT_VIEW_LINE - 1))
fi

echo "  View found at lines $START_LINE to $END_LINE"

# Extract the view definition
sed -n "${START_LINE},${END_LINE}p" views/DATETIME_STANDARDIZED_VIEWS.sql > /tmp/v_concomitant_medications_fix.sql

echo "  View definition extracted to /tmp/v_concomitant_medications_fix.sql"
echo ""

echo "Step 2: Deploying to Athena..."
echo "  Database: fhir_prd_db"
echo "  View: v_concomitant_medications"
echo ""

# Deploy using AWS CLI
aws athena start-query-execution \
    --profile radiant-prod \
    --query-string "$(cat /tmp/v_concomitant_medications_fix.sql)" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://radiant-prd-343218191717-us-east-1-prd-athena-results/ \
    --region us-east-1

if [ $? -eq 0 ]; then
    echo "✅ View deployment initiated successfully"
    echo ""
    echo "Next steps:"
    echo "  1. Wait 30-60 seconds for Athena to process the view"
    echo "  2. Test the view with: SELECT COUNT(*) FROM fhir_prd_db.v_concomitant_medications"
    echo "  3. Expected result: > 0 records (previously was 0)"
else
    echo "❌ View deployment failed"
    exit 1
fi

echo ""
echo "================================================================================"
