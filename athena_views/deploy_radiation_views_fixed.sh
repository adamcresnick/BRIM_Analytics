#!/bin/bash
set -e

PROFILE="radiant-prod"
REGION="us-east-1"
DATABASE="fhir_prd_db"
S3_OUTPUT="s3://aws-athena-query-results-343218191717-us-east-1/"

deploy_view() {
    local SQL_FILE=$1
    local VIEW_NAME=$2

    echo "Deploying $VIEW_NAME from $SQL_FILE..."
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
echo "DEPLOYING FIXED RADIATION VIEWS TO ATHENA"
echo "================================================================================"
echo "Fixes applied:"
echo "  1. v_radiation_summary: Fixed patient ID extraction (CRITICAL)"
echo "  2. v_radiation_documents: Improved content selection with ROW_NUMBER"
echo "  3. v_radiation_treatments: Performance optimization for appointment filtering"
echo "================================================================================"
echo ""

# Deploy in dependency order (dependencies first)
deploy_view "views/V_RADIATION_CARE_PLAN_HIERARCHY.sql" "v_radiation_care_plan_hierarchy"
echo ""

deploy_view "views/V_RADIATION_DOCUMENTS.sql" "v_radiation_documents"
echo ""

deploy_view "views/V_RADIATION_TREATMENT_APPOINTMENTS.sql" "v_radiation_treatment_appointments"
echo ""

deploy_view "views/V_RADIATION_TREATMENTS.sql" "v_radiation_treatments"
echo ""

# Deploy v_radiation_summary last (depends on other views)
deploy_view "views/V_RADIATION_SUMMARY.sql" "v_radiation_summary"
echo ""

echo "================================================================================"
echo "✅ ALL RADIATION VIEWS DEPLOYED SUCCESSFULLY!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Run validation queries (see RADIATION_VIEWS_CRITICAL_FIXES.sql)"
echo "  2. Verify patient ID lengths are correct (should be 45 characters)"
echo "  3. Test radiation JSON builder on sample patients"
echo "================================================================================"
