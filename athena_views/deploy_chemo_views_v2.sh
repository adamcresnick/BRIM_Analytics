#!/bin/bash

# Deploy chemotherapy views to Athena using S3 upload method
echo "Deploying chemotherapy views to Athena..."

# Upload SQL files to S3
echo "Uploading SQL files to S3..."
aws s3 cp views/V_CHEMOTHERAPY_DRUGS.sql s3://aws-athena-query-results-343218191717-us-east-1/sql-scripts/V_CHEMOTHERAPY_DRUGS.sql --profile radiant-prod
aws s3 cp views/V_CHEMO_MEDICATIONS.sql s3://aws-athena-query-results-343218191717-us-east-1/sql-scripts/V_CHEMO_MEDICATIONS.sql --profile radiant-prod

# Deploy V_CHEMOTHERAPY_DRUGS view
echo "Deploying V_CHEMOTHERAPY_DRUGS..."
QUERY_ID_1=$(aws athena start-query-execution \
    --query-string "CREATE OR REPLACE VIEW fhir_prd_db.v_chemotherapy_drugs AS $(cat views/V_CHEMOTHERAPY_DRUGS.sql | sed '1d' | head -c 250000)" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output text --query 'QueryExecutionId')

echo "V_CHEMOTHERAPY_DRUGS query ID: $QUERY_ID_1"

# Wait for first query to complete
echo "Waiting for V_CHEMOTHERAPY_DRUGS to complete..."
for i in {1..60}; do
    STATUS=$(aws athena get-query-execution \
        --query-execution-id $QUERY_ID_1 \
        --profile radiant-prod \
        --region us-east-1 \
        --output text --query 'QueryExecution.Status.State' 2>/dev/null)

    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo "V_CHEMOTHERAPY_DRUGS deployed successfully!"
        break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
        echo "V_CHEMOTHERAPY_DRUGS deployment failed with status: $STATUS"
        aws athena get-query-execution \
            --query-execution-id $QUERY_ID_1 \
            --profile radiant-prod \
            --region us-east-1 \
            --output json --query 'QueryExecution.Status'
        exit 1
    else
        echo "Status: $STATUS - waiting..."
        sleep 5
    fi
done

# Deploy V_CHEMO_MEDICATIONS view
echo "Deploying V_CHEMO_MEDICATIONS..."
QUERY_ID_2=$(aws athena start-query-execution \
    --query-string "file://views/V_CHEMO_MEDICATIONS.sql" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output text --query 'QueryExecutionId')

echo "V_CHEMO_MEDICATIONS query ID: $QUERY_ID_2"

# Wait for second query to complete
echo "Waiting for V_CHEMO_MEDICATIONS to complete..."
for i in {1..60}; do
    STATUS=$(aws athena get-query-execution \
        --query-execution-id $QUERY_ID_2 \
        --profile radiant-prod \
        --region us-east-1 \
        --output text --query 'QueryExecution.Status.State' 2>/dev/null)

    if [ "$STATUS" = "SUCCEEDED" ]; then
        echo "V_CHEMO_MEDICATIONS deployed successfully!"
        break
    elif [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "CANCELLED" ]; then
        echo "V_CHEMO_MEDICATIONS deployment failed with status: $STATUS"
        aws athena get-query-execution \
            --query-execution-id $QUERY_ID_2 \
            --profile radiant-prod \
            --region us-east-1 \
            --output json --query 'QueryExecution.Status'
        exit 1
    else
        echo "Status: $STATUS - waiting..."
        sleep 5
    fi
done

echo "All chemotherapy views deployed successfully!"