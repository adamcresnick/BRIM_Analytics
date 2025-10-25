#!/bin/bash
set -e

PROFILE="radiant-prod"
REGION="us-east-1"
DATABASE="fhir_prd_db"
S3_OUTPUT="s3://aws-athena-query-results-343218191717-us-east-1/"

deploy_view() {
    local SQL_FILE=$1
    local VIEW_NAME=$2
    
    echo "Deploying $VIEW_NAME..."
    QUERY_ID=$(aws athena start-query-execution \
        --query-string "$(cat $SQL_FILE)" \
        --query-execution-context Database=$DATABASE \
        --result-configuration OutputLocation=$S3_OUTPUT \
        --profile $PROFILE \
        --region $REGION \
        --output text \
        --query 'QueryExecutionId')
    
    echo "  Query ID: $QUERY_ID"
    
    while true; do
        STATUS=$(aws athena get-query-execution \
            --query-execution-id $QUERY_ID \
            --profile $PROFILE \
            --region $REGION \
            --output text \
            --query 'QueryExecution.Status.State')
        
        if [ "$STATUS" = "SUCCEEDED" ]; then
            echo "  ✅ $VIEW_NAME deployed successfully!"
            return 0
        elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
            echo "  ❌ $VIEW_NAME deployment failed!"
            aws athena get-query-execution \
                --query-execution-id $QUERY_ID \
                --profile $PROFILE \
                --region $REGION \
                --query 'QueryExecution.Status.StateChangeReason'
            return 1
        fi
        
        sleep 2
    done
}

echo "================================================================================"
echo "Deploying v_unified_patient_timeline to Athena"
echo "================================================================================"
echo ""

deploy_view "views/V_DIAGNOSES.sql" "v_diagnoses"
echo ""

deploy_view "views/V_RADIATION_SUMMARY.sql" "v_radiation_summary"
echo ""

deploy_view "views/V_UNIFIED_PATIENT_TIMELINE.sql" "v_unified_patient_timeline"
echo ""

echo "================================================================================"
echo "✅ All views deployed successfully!"
echo "================================================================================"
