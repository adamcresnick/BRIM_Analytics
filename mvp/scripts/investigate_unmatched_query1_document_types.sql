-- ============================================================================
-- QUERY 1: What surgery-related document types exist for unmatched patients?
-- ============================================================================
-- Run this first to see if we're missing any document types

WITH unmatched_patients AS (
    SELECT patient_fhir_id
    FROM (VALUES
        ('e.u8g4EJNAShGUUdoFgPeGw3'),
        ('eK2Z1RSypbow3fhoTE3E71ZhCZl8-5wZg.SjeET5hLtU3'),
        ('eSUS-B1Z41pxEXmotq3GFmqDANZ8eVhzdmXBA01di6uQ3'),
        ('eanWIqDZkP.H1u1CHeBJdjyJPyQ6iMl0yUlhB5UP4V.o3'),
        ('etepqT7yXbLK-aquYCBV4GA3'),
        ('e-RTlNNtrnYfazO7K4JGWzQUSogJpql1w3CHWg1pCsnk3'),
        ('e5LM3CPQRqE51Fdp0-dPYmma8.Dxy9w8JXzs2UvNf.NM3'),
        ('e7APWcUaHic4VtkXSiJZeWb67lac-XpY3JhyT8i4KT303'),
        ('e7eUuihzR-QXNWXWAL4ZZkmbb4G-lsl3E-agtWjmLsvA3'),
        ('e7ub34.Cr3WdyZNzAIa8AjPWZJAntNGTQH1rhX8MRDWQ3'),
        ('eESojeYjHTp7U0.DgACDrCpGkcV4Zd5pYdUbAh3LkJcs3'),
        ('eGfXrPPBIeR5nxK0ZZWWbFQI1knfyqPiaSNc4.ZIJYZU3'),
        ('eHCMXPCPWwcQp4AZOEuQ4dZzE-dWH2Pxv35cVZ020yXc3'),
        ('eRuN5rqbt2Jn2i5jHOr2A0jHxezV7qiJWvG72ctE1.U03'),
        ('eUHHjV1mcn0-lDxFMjnaynHOq1T7PzQEApMvApSBnkW43'),
        ('eUmlh.9Ww5TZa5ROkB1cOae2bljKXqIgZjKPBhpte6vw3'),
        ('ea3PAYRaZFoU1AWI5w-Jl4UcKDziyjOy0.NEHlehEt7M3'),
        ('edRPyBsaGmJR9jFr0Nk8rAYINhDgc.4EUNjW0jzUMeW43'),
        ('effWARcP1du0rqxqna1OTSa8SmkJ7IoWhXAxLc780IkQ3'),
        ('epTUzZ7zFp2hkPuR8TTmNuUqzPKrYVO--HEAphz-Mmwo3'),
        ('esHxnae2Zch3KsQezaJE5oe7XNGgPSM1F5cI6LAa.SQA3'),
        ('esJnYCGRlrAFNm2-gC5y.ad--Ug4ZyOJid2Zgrk1Djt83'),
        ('euP7Qw30mvNN1saM0PuCvgFxRzsFbRHYJsoboCznz.H03'),
        ('extmfQ6mBcT7sAj5oBvPQ25LE60xDCvAacYjyBhB7GHU3'),
        ('eynMz8inQbUnQEHMU761-PwA4yKzGFlBmjy9qvL2VFGk3'),
        ('ezbY9f2Dv.vWLMADPFoNFdz90uKb52yD-CT.XYqH6Cmg3'),
        ('e4aSm7E4S6gSgeONTvIB.MODbZP.ZJGa4x6PkQFLOjNc3'),
        ('ebwk2qY9jpSnhW1IFx22mvYjRYXK50LulvkIZgNi-Knc3')
    ) AS t(patient_fhir_id)
),

all_documents AS (
    SELECT
        d.patient_fhir_id,
        d.dr_type_text,
        d.dr_category_text
    FROM fhir_prd_db.v_binary_files d
    INNER JOIN unmatched_patients u
        ON d.patient_fhir_id = u.patient_fhir_id
    WHERE
        -- Look for anything that might be surgery-related
        (
            LOWER(d.dr_type_text) LIKE '%operat%'
            OR LOWER(d.dr_type_text) LIKE '%surg%'
            OR LOWER(d.dr_type_text) LIKE '%procedure%'
            OR LOWER(d.dr_category_text) LIKE '%operat%'
            OR LOWER(d.dr_category_text) LIKE '%surg%'
            OR LOWER(d.dr_category_text) LIKE '%procedure%'
        )
)

SELECT
    dr_type_text,
    dr_category_text,
    COUNT(*) as document_count,
    COUNT(DISTINCT patient_fhir_id) as patient_count
FROM all_documents
GROUP BY dr_type_text, dr_category_text
ORDER BY document_count DESC;
