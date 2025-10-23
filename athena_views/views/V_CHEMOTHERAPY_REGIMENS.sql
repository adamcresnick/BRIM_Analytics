-- Comprehensive Chemotherapy Regimen Reference View
-- Generated from RADIANT Unified Chemotherapy Index
-- Total regimens: 22
-- Source: /Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index/regimens.csv

CREATE OR REPLACE VIEW fhir_prd_db.v_chemotherapy_regimens AS
SELECT regimen_id, acronym, label, approval_status, notes
FROM (
  VALUES
    ('regimen:pcv', 'PCV', 'Procarbazine + Lomustine (CCNU) + Vincristine', 'regimen', NULL),
    ('regimen:abvd', 'ABVD', 'Doxorubicin + Bleomycin + Vinblastine + Dacarbazine', 'regimen', NULL),
    ('regimen:chop', 'CHOP', 'Cyclophosphamide + Doxorubicin + Vincristine + Prednisone', 'regimen', NULL),
    ('regimen:rchop', 'R-CHOP', 'Rituximab + CHOP', 'regimen', NULL),
    ('regimen:bep', 'BEP', 'Bleomycin + Etoposide + Cisplatin', 'regimen', NULL),
    ('regimen:folfirinox', 'FOLFIRINOX', 'Leucovorin + Fluorouracil + Irinotecan + Oxaliplatin', 'regimen', NULL),
    ('regimen:folfox', 'FOLFOX', 'Leucovorin + Fluorouracil + Oxaliplatin', 'regimen', NULL),
    ('regimen:folfiri', 'FOLFIRI', 'Leucovorin + Fluorouracil + Irinotecan', 'regimen', NULL),
    ('regimen:capox', 'CAPOX', 'Capecitabine + Oxaliplatin', 'regimen', NULL),
    ('regimen:ac', 'AC', 'Doxorubicin + Cyclophosphamide', 'regimen', NULL),
    ('regimen:tchp', 'TCHP', 'Docetaxel + Carboplatin + Trastuzumab + Pertuzumab', 'regimen', NULL),
    ('regimen:tip', 'TIP', 'Paclitaxel + Ifosfamide + Cisplatin', 'regimen', NULL),
    ('regimen:ice', 'ICE', 'Ifosfamide + Carboplatin + Etoposide', 'regimen', NULL),
    ('regimen:dhap', 'DHAP', 'Dexamethasone + High-dose Cytarabine + Cisplatin', 'regimen', NULL),
    ('regimen:epochr', 'EPOCH-R', 'Etoposide + Prednisone + Vincristine + Cyclophosphamide + Doxorubicin + Rituximab', 'regimen', NULL),
    ('regimen:hypercvad', 'Hyper-CVAD', 'Cyclophosphamide + Vincristine + Doxorubicin + Dexamethasone alternating with High-dose Methotrexate/Cytarabine', 'regimen', NULL),
    ('regimen:flagida', 'FLAG-IDA', 'Fludarabine + Cytarabine + G-CSF + Idarubicin', 'regimen', NULL),
    ('regimen:atraato', 'ATRA/ATO', 'All-trans Retinoic Acid + Arsenic Trioxide', 'regimen', NULL),
    ('regimen:tc', 'TC', 'Docetaxel + Cyclophosphamide', 'regimen', NULL),
    ('regimen:cmf', 'CMF', 'Cyclophosphamide + Methotrexate + Fluorouracil', 'regimen', NULL),
    ('regimen:captem', 'CAPTEM', 'Capecitabine + Temozolomide', 'regimen', NULL),
    ('regimen:rice', 'R-ICE', 'Rituximab + Ifosfamide + Carboplatin + Etoposide', 'regimen', NULL)
) AS regimens(regimen_id, acronym, label, approval_status, notes);
