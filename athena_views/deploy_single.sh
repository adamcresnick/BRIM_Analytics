#!/bin/bash
aws athena start-query-execution \
    --query-string "$(sed '/^--/d; /^\/\*/d; /^\*\//d' views/V_UNIFIED_PATIENT_TIMELINE.sql)" \
    --query-execution-context Database=fhir_prd_db \
    --result-configuration OutputLocation=s3://aws-athena-query-results-343218191717-us-east-1/ \
    --profile radiant-prod \
    --region us-east-1
