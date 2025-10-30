SELECT
    'v_radiation_documents' as source,
    COUNT(DISTINCT patient_fhir_id) as patients,
    COUNT(DISTINCT document_id) as documents,
    COUNT(DISTINCT CASE WHEN doc_date IS NOT NULL THEN document_id END) as docs_with_dates
FROM fhir_prd_db.v_radiation_documents

UNION ALL

SELECT
    'document_reference (filtered)' as source,
    COUNT(DISTINCT subject_reference) as patients,
    COUNT(DISTINCT id) as documents,
    COUNT(DISTINCT CASE WHEN date IS NOT NULL AND LENGTH(date) > 0 THEN id END) as docs_with_dates
FROM fhir_prd_db.document_reference
WHERE (LOWER(type_text) LIKE '%rad%onc%' OR LOWER(description) LIKE '%radiation%')
