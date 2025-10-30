#!/bin/bash
QUERY_FILE=$1
QUERY=$(cat "$QUERY_FILE")
EXECUTION_ID=$(aws athena start-query-execution \
    --query-string "$QUERY" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-531530102581-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1 \
    --output json | jq -r '.QueryExecutionId')

echo "$EXECUTION_ID"
