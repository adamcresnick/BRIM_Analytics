SELECT 
    COUNT(DISTINCT dr.id) as total_radiation_docs,
    COUNT(DISTINCT CASE WHEN dr.date IS NOT NULL AND LENGTH(dr.date) > 0 THEN dr.id END) as has_date,
    MIN(dr.date) as earliest_date,
    MAX(dr.date) as latest_date
FROM fhir_prd_db.document_reference dr
WHERE (
    dr.type_text LIKE '%Rad%Onc%'
    OR dr.type_text LIKE '%Radiation%'
    OR LOWER(dr.description) LIKE '%radiation%'
    OR dr.type_text IN ('Rad Onc Treatment Report', 'ONC RadOnc Consult', 'ONC RadOnc End of Treatment')
)
