-- ============================================================================
-- REFERENCE: Pathology and Molecular Testing Codes
-- ============================================================================
-- Purpose: Centralized reference for LOINC, CPT, and SNOMED codes used in
--          pathology/diagnostic workflows for pediatric brain tumors
--
-- Usage: Reference this when building pathology views or filtering queries
-- ============================================================================

-- ============================================================================
-- SECTION 1: LOINC Codes for Molecular/Genetic Testing
-- ============================================================================
-- Source: https://loinc.org and clinical pathology standards

-- IDH Mutation Testing
-- 81304-7: IDH1 R132 mutation
-- 81305-4: IDH2 R172 mutation
-- 88930-0: IDH gene targeted mutation analysis
-- 77207-2: IDH1 gene mutations found

-- MGMT Methylation
-- 71190-5: MGMT gene methylation analysis
-- 48676-1: MGMT gene promoter methylation

-- 1p/19q Codeletion (oligodendroglioma marker)
-- 81402-6: Chromosome 1p deletion
-- 81403-4: Chromosome 19q deletion
-- 93145-8: 1p19q codeletion status

-- TP53 Mutation (Li-Fraumeni, high-grade gliomas)
-- 81405-9: TP53 gene targeted mutation analysis
-- 77196-7: TP53 gene mutations found

-- BRAF Mutation (pediatric gliomas, especially pilocytic astrocytoma)
-- 81210-3: BRAF gene targeted mutation analysis
-- 81406-7: BRAF V600 mutation
-- 77198-3: BRAF gene mutations found

-- H3 K27M Mutation (diffuse midline glioma marker)
-- 88275-0: H3F3A gene targeted mutation analysis
-- 88276-8: HIST1H3B gene targeted mutation analysis

-- TERT Promoter Mutation (glioblastoma, oligodendroglioma)
-- 88277-6: TERT gene promoter mutation

-- ATRX Loss (glioma subtyping)
-- No standard LOINC yet, often reported narratively

-- Other Common Molecular Markers
-- 21902-6: Molecular pathology test (general)
-- 51969-4: Genetic analysis report
-- 51968-6: Genetic analysis master panel

-- Immunohistochemistry (IHC)
-- 33747-1: Ki-67 proliferation index
-- 85337-4: GFAP (glial fibrillary acidic protein)
-- 85319-2: Synaptophysin immunostain
-- 85335-8: NeuN neuronal marker
-- 85344-0: p53 protein expression
-- 85342-4: OLIG2 oligodendrocyte marker

-- WHO Grade (2021 Classification)
-- 59847-4: Histologic grade
-- 33732-3: Histology Cancer type

-- ============================================================================
-- SECTION 2: CPT Codes for Pathology Procedures
-- ============================================================================

-- Surgical Pathology CPT Codes
-- 88300: Surgical pathology, gross examination only
-- 88302: Surgical pathology, tissue examination by pathologist (limited)
-- 88304: Surgical pathology, Level III (e.g., skin, nasal polyp)
-- 88305: Surgical pathology, Level IV (e.g., CNS biopsies)
-- 88307: Surgical pathology, Level V (e.g., CNS tumor resection)
-- 88309: Surgical pathology, Level VI (e.g., CNS tumor with multiple specimens)

-- Frozen Section (Intraoperative Consultation)
-- 88331: Frozen section, first specimen
-- 88332: Frozen section, each additional specimen
-- 88333: Frozen section cytology, first specimen
-- 88334: Frozen section cytology, each additional

-- Immunohistochemistry
-- 88342: Immunohistochemistry (IHC), first stain
-- 88341: IHC, each additional stain

-- Molecular Pathology (Tier 1 & 2)
-- 81210: BRAF gene analysis
-- 81228: Cytogenomic microarray analysis
-- 81229: Cytogenomic microarray analysis (specific abnormality)
-- 81275: ASXL1 gene analysis
-- 81287: MGMT gene promoter methylation
-- 81304: IDH1 gene analysis
-- 81403: Molecular pathology, Level 4 (e.g., 1p/19q)

-- Tumor Biopsy CPT Codes (Brain/CNS)
-- 61140: Burr hole biopsy of brain
-- 61750: Stereotactic brain biopsy, needle
-- 61751: Stereotactic brain biopsy with CT/MRI guidance
-- 62269: Spinal cord biopsy

-- ============================================================================
-- SECTION 3: SNOMED Codes for Pathology Findings
-- ============================================================================

-- Tumor Types (SNOMED CT)
-- 443333004: Glioblastoma
-- 128700001: Astrocytoma
-- 253051006: Pilocytic astrocytoma
-- 445206008: Diffuse astrocytoma
-- 713242001: Oligodendroglioma
-- 128709000: Ependymoma
-- 734271000: Medulloblastoma
-- 723661006: Atypical teratoid/rhabdoid tumor (ATRT)
-- 733652006: Diffuse midline glioma H3 K27M-altered

-- WHO Grades (2021)
-- CNS WHO Grade 1: Low-grade, well-differentiated
-- CNS WHO Grade 2: Intermediate
-- CNS WHO Grade 3: Anaplastic/malignant
-- CNS WHO Grade 4: High-grade malignant (includes glioblastoma, DIPG)

-- Molecular Subtypes
-- 1182847007: IDH-mutant glioma
-- 1182849005: IDH-wildtype glioma
-- 1182850005: 1p/19q codeleted oligodendroglioma
-- 1182851009: MGMT methylated glioblastoma

-- ============================================================================
-- SECTION 4: Epic/CHOP Specific Identifiers
-- ============================================================================

-- DGD (Division of Genomic Diagnostics) Identifiers
-- Pattern: %-GD-% or DGD%
-- System: 'https://open.epic.com/FHIR/20/order-accession-number/Beaker'
-- System: 'urn:oid:1.2.840.114350.1.13.20.2.7.3.798268.800'

-- Beaker (Epic Lab System) Identifiers
-- System: 'https://open.epic.com/FHIR/20/order-accession-number/Beaker'

-- ============================================================================
-- SECTION 5: Query to Extract All Pathology Codes from Production
-- ============================================================================

-- Run this to discover what's actually in your database
WITH pathology_observations AS (
    SELECT
        'observation' as source_table,
        code_coding_code as code,
        code_coding_system as code_system,
        code_text as code_description,
        COUNT(DISTINCT subject_reference) as patient_count,
        COUNT(*) as record_count
    FROM fhir_prd_db.observation
    WHERE
        (LOWER(code_text) LIKE '%idh%'
        OR LOWER(code_text) LIKE '%mgmt%'
        OR LOWER(code_text) LIKE '%1p%19q%'
        OR LOWER(code_text) LIKE '%braf%'
        OR LOWER(code_text) LIKE '%tp53%'
        OR LOWER(code_text) LIKE '%h3%'
        OR LOWER(code_text) LIKE '%k27%'
        OR LOWER(code_text) LIKE '%ki-67%'
        OR LOWER(code_text) LIKE '%ki67%'
        OR LOWER(code_text) LIKE '%molecular%'
        OR LOWER(code_text) LIKE '%genetic%'
        OR LOWER(code_text) LIKE '%mutation%'
        OR LOWER(code_text) LIKE '%methylation%'
        OR LOWER(code_text) LIKE '%histology%'
        OR LOWER(code_text) LIKE '%grade%'
        OR LOWER(code_text) LIKE '%pathology%')
    GROUP BY 1,2,3,4
),
pathology_procedures AS (
    SELECT
        'procedure' as source_table,
        pcc.code_coding_code as code,
        pcc.code_coding_system as code_system,
        p.code_text as code_description,
        COUNT(DISTINCT p.subject_reference) as patient_count,
        COUNT(*) as record_count
    FROM fhir_prd_db.procedure p
    INNER JOIN fhir_prd_db.procedure_code_coding pcc ON p.id = pcc.procedure_id
    WHERE
        (LOWER(p.code_text) LIKE '%biopsy%'
        OR LOWER(p.code_text) LIKE '%pathology%'
        OR LOWER(p.code_text) LIKE '%frozen%'
        OR LOWER(p.code_text) LIKE '%specimen%'
        OR pcc.code_coding_code BETWEEN '88000' AND '88399')
    GROUP BY 1,2,3,4
)

SELECT * FROM pathology_observations
UNION ALL
SELECT * FROM pathology_procedures
ORDER BY source_table, record_count DESC;


-- ============================================================================
-- SECTION 6: Common Pathology Test Panels at CHOP
-- ============================================================================

-- These are typical molecular test panels ordered for pediatric brain tumors:

-- 1. CHOP Division of Genomic Diagnostics (DGD) Panels:
--    - Solid Tumor Panel (comprehensive genomic profiling)
--    - CNS Tumor Panel (targeted CNS-specific genes)
--    - Leukemia/Lymphoma Panel
--    - Custom panels for specific diagnoses

-- 2. Send-Out Testing (External Labs):
--    - Caris Molecular Intelligence
--    - Foundation Medicine
--    - Tempus xT
--    - NeoGenomics

-- 3. Standard Clinical Tests:
--    - IDH1/IDH2 mutation
--    - MGMT promoter methylation
--    - 1p/19q codeletion
--    - BRAF V600E mutation
--    - H3 K27M mutation (DIPG)
--    - TP53 sequencing
--    - TERT promoter mutation

-- ============================================================================
-- SECTION 7: Pathology Terminology Notes
-- ============================================================================

-- WHO 2021 Classification Changes:
-- - Integrated molecular AND histologic features
-- - IDH mutation status is KEY for glioma classification
-- - H3 K27M-altered tumors are CNS WHO Grade 4
-- - 1p/19q codeleted tumors are oligodendrogliomas
-- - Glioblastoma, IDH-wildtype is now "Glioblastoma"
-- - Diffuse astrocytoma, IDH-mutant is separate entity

-- Key Molecular Markers by Tumor Type:
-- Glioblastoma: IDH-wildtype, MGMT methylation (prognostic)
-- Oligodendroglioma: IDH-mutant, 1p/19q codeleted
-- Diffuse astrocytoma: IDH-mutant, 1p/19q intact
-- Pilocytic astrocytoma: BRAF fusion or V600E mutation
-- Medulloblastoma: Molecular subgroups (WNT, SHH, Group 3/4)
-- DIPG: H3 K27M-altered diffuse midline glioma

-- Common IHC Markers:
-- GFAP: Glial cell marker (astrocytomas)
-- OLIG2: Oligodendrocyte marker (oligodendrogliomas, gliomas)
-- Ki-67: Proliferation index (higher = more aggressive)
-- p53: Tumor suppressor (TP53 mutation surrogate)
-- ATRX: Loss indicates alternative lengthening of telomeres
-- IDH1 R132H: Specific antibody for most common IDH1 mutation
-- H3 K27M: Specific antibody for H3 K27M-altered tumors
