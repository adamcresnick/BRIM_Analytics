-- ================================================================================
-- OPHTHALMOLOGY DATA EXPLORATORY QUERIES
-- ================================================================================
-- Purpose: Discover what ophthalmology data exists in FHIR database
-- Date: 2025-10-18
-- Clinical Context: Brain tumor patients with visual deficits
--
-- Tables Explored:
--   1. Observation (structured test results)
--   2. Procedure (exams performed)
--   3. ServiceRequest (orders for ophthalmology)
--   4. DiagnosticReport (formal reports)
--   5. DocumentReference (binary files)
--   6. Encounter (ophthalmology visits)
--
-- Note: Includes main tables AND sub-schema tables
-- ================================================================================


-- ================================================================================
-- 1. OBSERVATION TABLE - OPHTHALMOLOGY OBSERVATIONS
-- ================================================================================

-- 1A. Main observation table - broad ophthalmology search
-- ================================================================================
SELECT
    'observation_main' as source_table,
    COUNT(*) as total_records,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN value_quantity_value IS NOT NULL THEN id END) as records_with_numeric_values,
    COUNT(DISTINCT CASE WHEN value_string IS NOT NULL THEN id END) as records_with_text_values,
    COUNT(DISTINCT CASE WHEN value_codeable_concept_text IS NOT NULL THEN id END) as records_with_coded_values
FROM fhir_prd_db.observation
WHERE (
    -- General ophthalmology
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%ophtha%'
    OR LOWER(code_text) LIKE '%ophtho%'
    OR LOWER(code_text) LIKE '%eye exam%'
    OR LOWER(code_text) LIKE '%neuro-ophthal%'
    OR LOWER(code_text) LIKE '%neuroophthal%'

    -- Visual acuity
    OR LOWER(code_text) LIKE '%visual%acuity%'
    OR LOWER(code_text) LIKE '%acuity%'
    OR LOWER(code_text) LIKE '%snellen%'
    OR LOWER(code_text) LIKE '%logmar%'
    OR LOWER(code_text) LIKE '%etdrs%'
    OR LOWER(code_text) LIKE '%hotv%'
    OR LOWER(code_text) LIKE '%lea%symbol%'
    OR LOWER(code_text) LIKE '%cardiff%'
    OR LOWER(code_text) LIKE '%teller%'
    OR LOWER(code_text) LIKE '%bcva%'

    -- Visual fields
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%perimetry%'
    OR LOWER(code_text) LIKE '%goldmann%'
    OR LOWER(code_text) LIKE '%humphrey%'
    OR LOWER(code_text) LIKE '%hemianopia%'
    OR LOWER(code_text) LIKE '%quadrantanopia%'
    OR LOWER(code_text) LIKE '%scotoma%'

    -- Optic disc/nerve
    OR LOWER(code_text) LIKE '%optic%disc%'
    OR LOWER(code_text) LIKE '%optic%nerve%'
    OR LOWER(code_text) LIKE '%papilledema%'
    OR LOWER(code_text) LIKE '%papilloedema%'
    OR LOWER(code_text) LIKE '%disc%edema%'
    OR LOWER(code_text) LIKE '%optic%atrophy%'
    OR LOWER(code_text) LIKE '%pallor%'
    OR LOWER(code_text) LIKE '%cup-to-disc%'
    OR LOWER(code_text) LIKE '%c/d ratio%'

    -- OCT
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optical coherence%'
    OR LOWER(code_text) LIKE '%rnfl%'
    OR LOWER(code_text) LIKE '%retinal nerve fiber%'
    OR LOWER(code_text) LIKE '%ganglion%cell%'
    OR LOWER(code_text) LIKE '%macular%thickness%'

    -- Fundoscopy
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%fundoscopy%'
    OR LOWER(code_text) LIKE '%retinal%exam%'

    -- Pupils
    OR LOWER(code_text) LIKE '%pupil%'
    OR LOWER(code_text) LIKE '%rapd%'
    OR LOWER(code_text) LIKE '%marcus gunn%'
    OR LOWER(code_text) LIKE '%afferent pupil%'
);


-- 1B. Sample ophthalmology observation records (for manual review)
-- ================================================================================
SELECT
    id as observation_fhir_id,
    subject_reference as patient_fhir_id,
    code_text,
    value_quantity_value,
    value_quantity_unit,
    value_string,
    value_codeable_concept_text,
    effective_date_time,
    status,
    category_text
FROM fhir_prd_db.observation
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%acuity%'
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optic%'
    OR LOWER(code_text) LIKE '%papilledema%'
    OR LOWER(code_text) LIKE '%fundus%'
)
ORDER BY effective_date_time DESC
LIMIT 100;


-- 1C. Observation code_text patterns (what test names exist?)
-- ================================================================================
SELECT
    code_text,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT subject_reference) as patient_count,
    COUNT(DISTINCT CASE WHEN value_quantity_value IS NOT NULL THEN id END) as numeric_results,
    COUNT(DISTINCT CASE WHEN value_string IS NOT NULL THEN id END) as text_results
FROM fhir_prd_db.observation
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optic%'
    OR LOWER(code_text) LIKE '%eye%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%pupil%'
)
GROUP BY code_text
ORDER BY occurrence_count DESC
LIMIT 50;


-- 1D. Observation sub-schema: observation_category
-- ================================================================================
SELECT
    'observation_category' as source_table,
    oc.category_text,
    COUNT(DISTINCT o.id) as observation_count,
    COUNT(DISTINCT o.subject_reference) as patient_count
FROM fhir_prd_db.observation o
JOIN fhir_prd_db.observation_category oc ON o.id = oc.observation_id
WHERE (
    LOWER(o.code_text) LIKE '%ophthal%'
    OR LOWER(o.code_text) LIKE '%visual%'
    OR LOWER(o.code_text) LIKE '%oct%'
    OR LOWER(o.code_text) LIKE '%optic%'
)
GROUP BY oc.category_text
ORDER BY observation_count DESC;


-- 1E. Observation sub-schema: observation_component (multi-part observations)
-- ================================================================================
SELECT
    'observation_component' as source_table,
    ocomp.code_text as component_name,
    COUNT(*) as component_count,
    COUNT(DISTINCT observation_id) as parent_observation_count,
    COUNT(DISTINCT CASE WHEN value_quantity_value IS NOT NULL THEN ocomp.observation_id END) as numeric_values
FROM fhir_prd_db.observation_component ocomp
JOIN fhir_prd_db.observation o ON ocomp.observation_id = o.id
WHERE (
    LOWER(o.code_text) LIKE '%ophthal%'
    OR LOWER(o.code_text) LIKE '%visual%'
    OR LOWER(o.code_text) LIKE '%oct%'
    OR LOWER(ocomp.code_text) LIKE '%ophthal%'
    OR LOWER(ocomp.code_text) LIKE '%visual%'
    OR LOWER(ocomp.code_text) LIKE '%oct%'
)
GROUP BY ocomp.code_text
ORDER BY component_count DESC
LIMIT 50;


-- ================================================================================
-- 2. PROCEDURE TABLE - OPHTHALMOLOGY PROCEDURES
-- ================================================================================

-- 2A. Main procedure table - ophthalmology procedures
-- ================================================================================
SELECT
    'procedure_main' as source_table,
    COUNT(*) as total_procedures,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN id END) as completed_procedures,
    MIN(performed_date_time) as earliest_procedure,
    MAX(performed_date_time) as latest_procedure
FROM fhir_prd_db.procedure
WHERE (
    -- General ophthalmology
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%eye%exam%'
    OR LOWER(code_text) LIKE '%eye%examination%'

    -- Specific tests
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%perimetry%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%fundoscopy%'
    OR LOWER(code_text) LIKE '%ophthalmoscopy%'

    -- Imaging
    OR LOWER(code_text) LIKE '%retinal%photo%'
    OR LOWER(code_text) LIKE '%fundus%photo%'
);


-- 2B. Sample procedure records
-- ================================================================================
SELECT
    id as procedure_fhir_id,
    subject_reference as patient_fhir_id,
    code_text,
    performed_date_time,
    status,
    outcome_text,
    note_text
FROM fhir_prd_db.procedure
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%eye%exam%'
)
ORDER BY performed_date_time DESC
LIMIT 100;


-- 2C. Procedure code_text patterns
-- ================================================================================
SELECT
    code_text,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT subject_reference) as patient_count,
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN id END) as completed_count
FROM fhir_prd_db.procedure
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%eye%'
    OR LOWER(code_text) LIKE '%fundus%'
)
GROUP BY code_text
ORDER BY occurrence_count DESC
LIMIT 50;


-- 2D. Procedure sub-schema: procedure_code_coding (CPT/SNOMED codes)
-- ================================================================================
SELECT
    'procedure_code_coding' as source_table,
    pc.code_coding_system,
    pc.code_coding_code,
    pc.code_coding_display,
    COUNT(DISTINCT p.id) as procedure_count,
    COUNT(DISTINCT p.subject_reference) as patient_count
FROM fhir_prd_db.procedure p
JOIN fhir_prd_db.procedure_code_coding pc ON p.id = pc.procedure_id
WHERE (
    LOWER(p.code_text) LIKE '%ophthal%'
    OR LOWER(p.code_text) LIKE '%visual%'
    OR LOWER(p.code_text) LIKE '%oct%'
    OR LOWER(pc.code_coding_display) LIKE '%ophthal%'
    OR LOWER(pc.code_coding_display) LIKE '%visual%'
    OR LOWER(pc.code_coding_display) LIKE '%oct%'

    -- Common ophthalmology CPT codes
    OR pc.code_coding_code IN (
        '92002', '92004',  -- Ophthalmologic exam new patient
        '92012', '92014',  -- Ophthalmologic exam established
        '92081', '92082', '92083',  -- Visual field testing
        '92133', '92134',  -- OCT imaging
        '92225', '92226',  -- Fundus photography
        '92250',  -- Fundus photography with interpretation
        '92227', '92228'  -- Remote fundus imaging
    )
)
GROUP BY pc.code_coding_system, pc.code_coding_code, pc.code_coding_display
ORDER BY procedure_count DESC;


-- 2E. Procedure sub-schema: procedure_performer (who did the exam?)
-- ================================================================================
SELECT
    'procedure_performer' as source_table,
    pp.function_text,
    pp.actor_reference,
    COUNT(DISTINCT p.id) as procedure_count
FROM fhir_prd_db.procedure p
JOIN fhir_prd_db.procedure_performer pp ON p.id = pp.procedure_id
WHERE (
    LOWER(p.code_text) LIKE '%ophthal%'
    OR LOWER(p.code_text) LIKE '%visual%'
    OR LOWER(p.code_text) LIKE '%oct%'
)
GROUP BY pp.function_text, pp.actor_reference
ORDER BY procedure_count DESC
LIMIT 50;


-- ================================================================================
-- 3. SERVICE REQUEST TABLE - OPHTHALMOLOGY ORDERS
-- ================================================================================

-- 3A. Main service_request table
-- ================================================================================
SELECT
    'service_request_main' as source_table,
    COUNT(*) as total_orders,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN id END) as completed_orders,
    COUNT(DISTINCT CASE WHEN status = 'active' THEN id END) as active_orders,
    COUNT(DISTINCT CASE WHEN intent = 'order' THEN id END) as actual_orders,
    COUNT(DISTINCT CASE WHEN intent = 'plan' THEN id END) as planned_orders
FROM fhir_prd_db.service_request
WHERE (
    -- General ophthalmology
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%eye%'
    OR LOWER(code_text) LIKE '%vision%'

    -- Specific tests
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%visual%acuity%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%optic%'

    -- Consults
    OR LOWER(code_text) LIKE '%ophthal%consult%'
    OR LOWER(code_text) LIKE '%neuro-ophthal%'
);


-- 3B. Sample service_request records
-- ================================================================================
SELECT
    id as service_request_fhir_id,
    subject_reference as patient_fhir_id,
    code_text,
    authored_on,
    occurrence_date_time,
    status,
    intent,
    priority,
    reason_code_text,
    note_text
FROM fhir_prd_db.service_request
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optic%'
    OR LOWER(code_text) LIKE '%eye%'
)
ORDER BY authored_on DESC
LIMIT 100;


-- 3C. Service request code_text patterns
-- ================================================================================
SELECT
    code_text,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT subject_reference) as patient_count,
    COUNT(DISTINCT CASE WHEN status = 'completed' THEN id END) as completed_count,
    COUNT(DISTINCT CASE WHEN intent = 'order' THEN id END) as order_count
FROM fhir_prd_db.service_request
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%optic%'
    OR LOWER(code_text) LIKE '%eye%'
)
GROUP BY code_text
ORDER BY occurrence_count DESC
LIMIT 50;


-- 3D. Service request sub-schema: service_request_code_coding
-- ================================================================================
SELECT
    'service_request_code_coding' as source_table,
    src.code_coding_system,
    src.code_coding_code,
    src.code_coding_display,
    COUNT(DISTINCT sr.id) as request_count,
    COUNT(DISTINCT sr.subject_reference) as patient_count
FROM fhir_prd_db.service_request sr
JOIN fhir_prd_db.service_request_code_coding src ON sr.id = src.service_request_id
WHERE (
    LOWER(sr.code_text) LIKE '%ophthal%'
    OR LOWER(sr.code_text) LIKE '%visual%'
    OR LOWER(sr.code_text) LIKE '%oct%'
    OR LOWER(src.code_coding_display) LIKE '%ophthal%'
    OR LOWER(src.code_coding_display) LIKE '%visual%'
    OR LOWER(src.code_coding_display) LIKE '%oct%'
)
GROUP BY src.code_coding_system, src.code_coding_code, src.code_coding_display
ORDER BY request_count DESC
LIMIT 50;


-- 3E. Service request sub-schema: service_request_reason_code
-- ================================================================================
SELECT
    'service_request_reason_code' as source_table,
    srrc.reason_code_text,
    COUNT(DISTINCT sr.id) as request_count,
    COUNT(DISTINCT sr.subject_reference) as patient_count
FROM fhir_prd_db.service_request sr
JOIN fhir_prd_db.service_request_reason_code srrc ON sr.id = srrc.service_request_id
WHERE (
    LOWER(sr.code_text) LIKE '%ophthal%'
    OR LOWER(sr.code_text) LIKE '%visual%'
    OR LOWER(sr.code_text) LIKE '%oct%'
)
GROUP BY srrc.reason_code_text
ORDER BY request_count DESC
LIMIT 50;


-- ================================================================================
-- 4. DIAGNOSTIC REPORT TABLE - OPHTHALMOLOGY REPORTS
-- ================================================================================

-- 4A. Main diagnostic_report table
-- ================================================================================
SELECT
    'diagnostic_report_main' as source_table,
    COUNT(*) as total_reports,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN status = 'final' THEN id END) as final_reports,
    COUNT(DISTINCT CASE WHEN conclusion IS NOT NULL THEN id END) as reports_with_conclusion
FROM fhir_prd_db.diagnostic_report
WHERE (
    -- Search in code_text
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%field%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%eye%'

    -- Search in conclusion
    OR LOWER(conclusion) LIKE '%ophthal%'
    OR LOWER(conclusion) LIKE '%visual%'
    OR LOWER(conclusion) LIKE '%optic%disc%'
    OR LOWER(conclusion) LIKE '%papilledema%'
    OR LOWER(conclusion) LIKE '%optic%atrophy%'
    OR LOWER(conclusion) LIKE '%visual%field%'
);


-- 4B. Sample diagnostic_report records
-- ================================================================================
SELECT
    id as diagnostic_report_fhir_id,
    subject_reference as patient_fhir_id,
    code_text,
    effective_date_time,
    issued,
    status,
    conclusion,
    conclusion_code_text
FROM fhir_prd_db.diagnostic_report
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(conclusion) LIKE '%ophthal%'
    OR LOWER(conclusion) LIKE '%optic%'
    OR LOWER(conclusion) LIKE '%visual%'
)
ORDER BY issued DESC
LIMIT 100;


-- 4C. Diagnostic report code_text patterns
-- ================================================================================
SELECT
    code_text,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT subject_reference) as patient_count,
    COUNT(DISTINCT CASE WHEN conclusion IS NOT NULL THEN id END) as with_conclusion
FROM fhir_prd_db.diagnostic_report
WHERE (
    LOWER(code_text) LIKE '%ophthal%'
    OR LOWER(code_text) LIKE '%visual%'
    OR LOWER(code_text) LIKE '%oct%'
    OR LOWER(code_text) LIKE '%fundus%'
    OR LOWER(code_text) LIKE '%eye%'
)
GROUP BY code_text
ORDER BY occurrence_count DESC
LIMIT 50;


-- 4D. Diagnostic report sub-schema: diagnostic_report_category
-- ================================================================================
SELECT
    'diagnostic_report_category' as source_table,
    drc.category_text,
    COUNT(DISTINCT dr.id) as report_count,
    COUNT(DISTINCT dr.subject_reference) as patient_count
FROM fhir_prd_db.diagnostic_report dr
JOIN fhir_prd_db.diagnostic_report_category drc ON dr.id = drc.diagnostic_report_id
WHERE (
    LOWER(dr.code_text) LIKE '%ophthal%'
    OR LOWER(dr.code_text) LIKE '%visual%'
    OR LOWER(dr.code_text) LIKE '%oct%'
)
GROUP BY drc.category_text
ORDER BY report_count DESC;


-- 4E. Diagnostic report sub-schema: diagnostic_report_media (images/attachments)
-- ================================================================================
SELECT
    'diagnostic_report_media' as source_table,
    drm.link_reference,
    COUNT(DISTINCT dr.id) as report_count
FROM fhir_prd_db.diagnostic_report dr
JOIN fhir_prd_db.diagnostic_report_media drm ON dr.id = drm.diagnostic_report_id
WHERE (
    LOWER(dr.code_text) LIKE '%ophthal%'
    OR LOWER(dr.code_text) LIKE '%visual%'
    OR LOWER(dr.code_text) LIKE '%oct%'
    OR LOWER(dr.code_text) LIKE '%fundus%'
)
GROUP BY drm.link_reference
LIMIT 50;


-- ================================================================================
-- 5. DOCUMENT REFERENCE TABLE - BINARY FILES
-- ================================================================================

-- 5A. Main document_reference table
-- ================================================================================
SELECT
    'document_reference_main' as source_table,
    COUNT(*) as total_documents,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN status = 'current' THEN id END) as current_documents,
    COUNT(DISTINCT type_text) as unique_document_types
FROM fhir_prd_db.document_reference
WHERE (
    -- Search in description
    LOWER(description) LIKE '%ophthal%'
    OR LOWER(description) LIKE '%visual%field%'
    OR LOWER(description) LIKE '%oct%'
    OR LOWER(description) LIKE '%fundus%'
    OR LOWER(description) LIKE '%eye%'
    OR LOWER(description) LIKE '%retina%'

    -- Search in type_text
    OR LOWER(type_text) LIKE '%ophthal%'
    OR LOWER(type_text) LIKE '%visual%'
    OR LOWER(type_text) LIKE '%oct%'
    OR LOWER(type_text) LIKE '%eye%'
);


-- 5B. Sample document_reference records
-- ================================================================================
SELECT
    id as document_reference_fhir_id,
    subject_reference as patient_fhir_id,
    description,
    type_text,
    date as document_date,
    status,
    content_attachment_url,
    content_attachment_content_type
FROM fhir_prd_db.document_reference
WHERE (
    LOWER(description) LIKE '%ophthal%'
    OR LOWER(description) LIKE '%visual%'
    OR LOWER(description) LIKE '%oct%'
    OR LOWER(description) LIKE '%fundus%'
    OR LOWER(type_text) LIKE '%ophthal%'
    OR LOWER(type_text) LIKE '%eye%'
)
ORDER BY date DESC
LIMIT 100;


-- 5C. Document description patterns
-- ================================================================================
SELECT
    description,
    type_text,
    content_attachment_content_type,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT subject_reference) as patient_count
FROM fhir_prd_db.document_reference
WHERE (
    LOWER(description) LIKE '%ophthal%'
    OR LOWER(description) LIKE '%visual%'
    OR LOWER(description) LIKE '%oct%'
    OR LOWER(description) LIKE '%fundus%'
    OR LOWER(type_text) LIKE '%ophthal%'
)
GROUP BY description, type_text, content_attachment_content_type
ORDER BY occurrence_count DESC
LIMIT 50;


-- 5D. Document reference sub-schema: document_reference_content (multiple attachments)
-- ================================================================================
SELECT
    'document_reference_content' as source_table,
    drc.attachment_content_type,
    COUNT(DISTINCT dr.id) as document_count,
    COUNT(DISTINCT dr.subject_reference) as patient_count
FROM fhir_prd_db.document_reference dr
JOIN fhir_prd_db.document_reference_content drc ON dr.id = drc.document_reference_id
WHERE (
    LOWER(dr.description) LIKE '%ophthal%'
    OR LOWER(dr.description) LIKE '%visual%'
    OR LOWER(dr.description) LIKE '%oct%'
    OR LOWER(dr.description) LIKE '%fundus%'
)
GROUP BY drc.attachment_content_type
ORDER BY document_count DESC;


-- ================================================================================
-- 6. ENCOUNTER TABLE - OPHTHALMOLOGY VISITS
-- ================================================================================

-- 6A. Main encounter table
-- ================================================================================
SELECT
    'encounter_main' as source_table,
    COUNT(*) as total_encounters,
    COUNT(DISTINCT subject_reference) as unique_patients,
    COUNT(DISTINCT CASE WHEN status = 'finished' THEN id END) as finished_encounters,
    MIN(period_start) as earliest_encounter,
    MAX(period_start) as latest_encounter
FROM fhir_prd_db.encounter
WHERE (
    LOWER(service_type_text) LIKE '%ophthal%'
    OR LOWER(service_type_text) LIKE '%eye%'
    OR LOWER(service_type_text) LIKE '%vision%'
);


-- 6B. Encounter sub-schema: encounter_type
-- ================================================================================
SELECT
    'encounter_type' as source_table,
    et.type_text,
    COUNT(DISTINCT e.id) as encounter_count,
    COUNT(DISTINCT e.subject_reference) as patient_count
FROM fhir_prd_db.encounter e
JOIN fhir_prd_db.encounter_type et ON e.id = et.encounter_id
WHERE (
    LOWER(e.service_type_text) LIKE '%ophthal%'
    OR LOWER(et.type_text) LIKE '%ophthal%'
    OR LOWER(et.type_text) LIKE '%eye%'
    OR LOWER(et.type_text) LIKE '%vision%'
)
GROUP BY et.type_text
ORDER BY encounter_count DESC
LIMIT 50;


-- 6C. Encounter sub-schema: encounter_service_type_coding
-- ================================================================================
SELECT
    'encounter_service_type_coding' as source_table,
    estc.service_type_coding_display,
    COUNT(DISTINCT e.id) as encounter_count,
    COUNT(DISTINCT e.subject_reference) as patient_count
FROM fhir_prd_db.encounter e
JOIN fhir_prd_db.encounter_service_type_coding estc ON e.id = estc.encounter_id
WHERE (
    LOWER(e.service_type_text) LIKE '%ophthal%'
    OR LOWER(estc.service_type_coding_display) LIKE '%ophthal%'
    OR LOWER(estc.service_type_coding_display) LIKE '%eye%'
)
GROUP BY estc.service_type_coding_display
ORDER BY encounter_count DESC;


-- ================================================================================
-- 7. CROSS-TABLE SUMMARY
-- ================================================================================

-- Summary of ophthalmology data across all tables
-- ================================================================================
SELECT
    'SUMMARY' as analysis_type,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.observation WHERE LOWER(code_text) LIKE '%ophthal%' OR LOWER(code_text) LIKE '%visual%' OR LOWER(code_text) LIKE '%oct%') as patients_with_observations,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.procedure WHERE LOWER(code_text) LIKE '%ophthal%' OR LOWER(code_text) LIKE '%visual%field%' OR LOWER(code_text) LIKE '%oct%') as patients_with_procedures,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.service_request WHERE LOWER(code_text) LIKE '%ophthal%' OR LOWER(code_text) LIKE '%visual%' OR LOWER(code_text) LIKE '%oct%') as patients_with_service_requests,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.diagnostic_report WHERE LOWER(code_text) LIKE '%ophthal%' OR LOWER(code_text) LIKE '%visual%' OR LOWER(code_text) LIKE '%oct%' OR LOWER(conclusion) LIKE '%ophthal%') as patients_with_diagnostic_reports,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.document_reference WHERE LOWER(description) LIKE '%ophthal%' OR LOWER(description) LIKE '%visual%' OR LOWER(description) LIKE '%oct%' OR LOWER(description) LIKE '%fundus%') as patients_with_documents,
    (SELECT COUNT(DISTINCT subject_reference) FROM fhir_prd_db.encounter WHERE LOWER(service_type_text) LIKE '%ophthal%') as patients_with_encounters;


-- ================================================================================
-- END OF EXPLORATORY QUERIES
-- ================================================================================
