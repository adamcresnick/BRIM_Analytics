#!/bin/bash
set -e

PROFILE="radiant-prod"
REGION="us-east-1"
DATABASE="fhir_prd_db"
S3_OUTPUT="s3://aws-athena-query-results-343218191717-us-east-1/"

deploy_large_view() {
    local SQL_FILE=$1
    local VIEW_NAME=$2

    echo "Deploying $VIEW_NAME from $SQL_FILE..."

    # Read SQL content and escape for JSON
    SQL_CONTENT=$(cat "$SQL_FILE" | jq -Rs .)

    # Create JSON input file
    cat > /tmp/athena_query.json <<EOF
{
  "QueryString": $SQL_CONTENT,
  "QueryExecutionContext": {
    "Database": "$DATABASE"
  },
  "ResultConfiguration": {
    "OutputLocation": "$S3_OUTPUT"
  }
}
EOF

    # Execute query using JSON input
    QUERY_ID=$(aws athena start-query-execution \
        --cli-input-json file:///tmp/athena_query.json \
        --profile $PROFILE \
        --region $REGION \
        --output text \
        --query 'QueryExecutionId')

    echo "  Query ID: $QUERY_ID"

    # Wait for completion
    while true; do
        STATUS=$(aws athena get-query-execution \
            --query-execution-id $QUERY_ID \
            --profile $PROFILE \
            --region $REGION \
            --output text \
            --query 'QueryExecution.Status.State')

        if [ "$STATUS" = "SUCCEEDED" ]; then
            echo "  ✅ $VIEW_NAME deployed successfully!"
            rm /tmp/athena_query.json
            return 0
        elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
            echo "  ❌ $VIEW_NAME deployment failed!"
            aws athena get-query-execution \
                --query-execution-id $QUERY_ID \
                --profile $PROFILE \
                --region $REGION \
                --query 'QueryExecution.Status.StateChangeReason'
            rm /tmp/athena_query.json
            return 1
        fi

        sleep 2
    done
}

echo "================================================================================"
echo "Deploying chemotherapy views to Athena"
echo "================================================================================"
echo ""

deploy_large_view "views/V_CHEMOTHERAPY_DRUGS.sql" "v_chemotherapy_drugs"
echo ""

deploy_large_view "views/V_CHEMO_MEDICATIONS.sql" "v_chemo_medications"
echo ""

echo "================================================================================"
echo "✅ All chemotherapy views deployed successfully!"
echo "================================================================================"
