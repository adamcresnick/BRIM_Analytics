WITH doc_stats AS (
    SELECT
        patient_fhir_id,
        COUNT(DISTINCT document_id) as num_documents,
        MIN(doc_date) as earliest_doc_date,
        MAX(doc_date) as latest_doc_date,
        COUNT(DISTINCT CASE WHEN doc_date IS NOT NULL THEN document_id END) as docs_with_dates,
        COUNT(DISTINCT CASE WHEN extraction_priority IS NOT NULL THEN document_id END) as docs_with_priority
    FROM fhir_prd_db.v_radiation_documents
    GROUP BY patient_fhir_id
),
structured_patients AS (
    SELECT DISTINCT patient_fhir_id
    FROM fhir_prd_db.v_radiation_treatments
    WHERE course_id IS NOT NULL
)
SELECT
    COUNT(DISTINCT ds.patient_fhir_id) as total_patients_with_documents,
    SUM(ds.num_documents) as total_documents,
    ROUND(AVG(ds.num_documents), 1) as avg_docs_per_patient,
    COUNT(DISTINCT CASE WHEN ds.docs_with_dates > 0 THEN ds.patient_fhir_id END) as patients_with_dated_docs,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN ds.docs_with_dates > 0 THEN ds.patient_fhir_id END) / 
          NULLIF(COUNT(DISTINCT ds.patient_fhir_id), 0), 1) as pct_patients_with_dates,
    COUNT(DISTINCT CASE WHEN sp.patient_fhir_id IS NULL THEN ds.patient_fhir_id END) as patients_without_structured_episodes,
    COUNT(DISTINCT CASE WHEN sp.patient_fhir_id IS NULL AND ds.docs_with_dates > 0 THEN ds.patient_fhir_id END) as incremental_patients_for_strategy_d,
    COUNT(DISTINCT CASE WHEN ds.docs_with_priority > 0 THEN ds.patient_fhir_id END) as patients_with_prioritized_docs
FROM doc_stats ds
LEFT JOIN structured_patients sp ON ds.patient_fhir_id = sp.patient_fhir_id
