-- ================================================================================
-- Create chemotherapy_drugs table from CSV in S3
-- ================================================================================
-- This table replaces the inline VALUES approach in v_chemotherapy_drugs view
-- The data is stored in S3 and queried via external table

CREATE EXTERNAL TABLE IF NOT EXISTS fhir_prd_db.chemotherapy_drugs (
    drug_id STRING,
    preferred_name STRING,
    approval_status STRING,
    is_supportive_care STRING,
    rxnorm_in STRING,
    ncit_code STRING,
    normalized_key STRING,
    sources STRING,
    drug_category STRING,
    drug_type STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
   'separatorChar' = ',',
   'quoteChar' = '"',
   'escapeChar' = '\\'
)
LOCATION 's3://aws-athena-query-results-343218191717-us-east-1/chemotherapy-reference-data/'
TBLPROPERTIES ('skip.header.line.count'='1');
