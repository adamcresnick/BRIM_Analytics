#!/bin/bash

# Deploy chemotherapy views to Athena
echo "Deploying chemotherapy views to Athena..."

# Deploy V_CHEMOTHERAPY_DRUGS view
echo "Deploying V_CHEMOTHERAPY_DRUGS..."
QUERY_ID_1=$(aws athena start-query-execution \
    --query-string "$(sed '/^--/d; /^\/\*/d; /^\*\//d' views/V_CHEMOTHERAPY_DRUGS.sql)" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output text --query 'QueryExecutionId')

echo "V_CHEMOTHERAPY_DRUGS query ID: $QUERY_ID_1"

# Wait for first query to complete
echo "Waiting for V_CHEMOTHERAPY_DRUGS to complete..."
while true; do
    STATUS=$(aws athena get-query-execution \
        --query-execution-id $QUERY_ID_1 \
        --profile radiant-prod \
        --region us-east-1 \
        --output text --query 'QueryExecution.Status.State')

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
    --query-string "$(sed '/^--/d; /^\/\*/d; /^\*\//d' views/V_CHEMO_MEDICATIONS.sql)" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output text --query 'QueryExecutionId')

echo "V_CHEMO_MEDICATIONS query ID: $QUERY_ID_2"

# Wait for second query to complete
echo "Waiting for V_CHEMO_MEDICATIONS to complete..."
while true; do
    STATUS=$(aws athena get-query-execution \
        --query-execution-id $QUERY_ID_2 \
        --profile radiant-prod \
        --region us-east-1 \
        --output text --query 'QueryExecution.Status.State')

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