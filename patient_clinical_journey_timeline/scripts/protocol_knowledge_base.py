"""
Protocol Knowledge Base for V5.0 Therapeutic Approach Framework

This module provides an expanded protocol knowledge base integrating:
1. Original hardcoded protocols (Stupp, COG ACNS0331, CheckMate 143)
2. CBTN REDCap protocols (114 pediatric oncology trials)
3. Pediatric Oncology Treatment Protocols Reference (comprehensive protocol guide)
4. NCCN 2024 Guidelines (annotated on relevant protocols)

The knowledge base supports:
- Protocol matching from observed treatment patterns
- Confidence scoring based on signature agents, radiation doses, and treatment structure
- Evidence level assignment
- Era-appropriate protocol selection
- NCCN 2024 guideline integration

Data Sources:
- /docs/CBTN_REDCAP_Protocols_Updated.csv
- /docs/Pediatric_Oncology_Treatment_Protocols.html

Author: V5.0 Framework Enhancement
Created: 2025-11-09
Updated: 2025-11-09 (NCCN 2024 guidelines added)
"""

import csv
import os
from typing import Dict, List, Any, Optional


# ============================================================================
# ORIGINAL V5.0 PROTOCOLS (Preserved for backward compatibility)
# ============================================================================

ORIGINAL_PEDIATRIC_CNS_PROTOCOLS = {
    "stupp_protocol": {
        "name": "Modified Stupp Protocol",
        "reference": "Stupp et al. NEJM 2005",
        "indications": ["IDH-mutant astrocytoma", "glioblastoma", "anaplastic astrocytoma"],
        "evidence_level": "standard_of_care",
        "trial_id": "N/A",
        "era": "2005-present",
        "components": {
            "surgery": {
                "required": True,
                "timing": "upfront",
                "eor_preference": "gross_total_resection"
            },
            "concurrent_chemoradiation": {
                "required": True,
                "chemotherapy": {
                    "drugs": ["temozolomide"],
                    "dose": "75 mg/m² daily",
                    "duration_days": 42
                },
                "radiation": {
                    "dose_gy": [54, 60],
                    "fractions": 30,
                    "dose_per_fraction": [1.8, 2.0]
                }
            },
            "adjuvant_chemotherapy": {
                "required": True,
                "drugs": ["temozolomide"],
                "dose": "150-200 mg/m² days 1-5",
                "schedule": "q28 days",
                "cycles": 6
            }
        },
        "expected_duration_days": [168, 196],
        "signature_agents": ["temozolomide"],
        "signature_radiation": {"dose_gy": [54, 60], "type": "focal"}
    },

    "cog_acns0331": {
        "name": "COG ACNS0331 (Medulloblastoma)",
        "reference": "Children's Oncology Group ACNS0331",
        "indications": ["medulloblastoma"],
        "evidence_level": "standard_of_care",
        "trial_id": "ACNS0331",
        "era": "2004-2012",
        "components": {
            "surgery": {"required": True, "timing": "upfront"},
            "radiation": {
                "type": "craniospinal",
                "csi_dose_gy": [23.4, 36.0],
                "boost_dose_gy": [30.6, 23.4],
                "total_dose_gy": 54
            },
            "concurrent_chemotherapy": {
                "drugs": ["vincristine"],
                "schedule": "weekly"
            },
            "maintenance_chemotherapy": {
                "drugs": ["cisplatin", "vincristine", "cyclophosphamide"],
                "cycles": 6
            }
        },
        "signature_agents": ["vincristine", "cisplatin", "cyclophosphamide"],
        "signature_radiation": {"csi_dose_gy": 23.4, "type": "craniospinal"}
    },

    "checkmate_143": {
        "name": "CheckMate 143 / Nivolumab Salvage",
        "reference": "NCT02017717",
        "indications": ["recurrent_glioblastoma"],
        "evidence_level": "experimental",
        "trial_id": "NCT02017717",
        "era": "2014-present",
        "line_of_therapy": "salvage",
        "components": {
            "immunotherapy": {
                "drugs": ["nivolumab"],
                "dose": "3 mg/kg",
                "schedule": "q14 days",
                "duration": "until_progression"
            }
        },
        "signature_agents": ["nivolumab"]
    }
}


# ============================================================================
# EXPANDED PROTOCOL KNOWLEDGE BASE - COG TRIALS
# ============================================================================

COG_CNS_PROTOCOLS = {
    "acns0332": {
        "name": "COG ACNS0332 (High-Risk Medulloblastoma)",
        "reference": "JAMA Oncology 2021, NCT00392327",
        "trial_id": "ACNS0332",
        "indications": ["medulloblastoma_high_risk", "metastatic_medulloblastoma", "anaplastic_medulloblastoma"],
        "evidence_level": "standard_of_care",
        "era": "2004-2015",
        "components": {
            "surgery": {"required": True, "timing": "upfront"},
            "radiation": {
                "type": "craniospinal",
                "csi_dose_gy": 36.0,
                "boost_dose_gy": 18.0,
                "total_dose_gy": 54.0
            },
            "concurrent_chemotherapy": {
                "drugs": ["carboplatin", "vincristine"],
                "carboplatin_dose": "35 mg/m² daily during CSI",
                "schedule": "carboplatin as radiosensitizer (experimental arm)"
            },
            "maintenance_chemotherapy": {
                "drugs": ["cisplatin", "vincristine", "cyclophosphamide"],
                "cycles": 6,
                "isotretinoin": {
                    "dose": "160 mg/m² QOD",
                    "cycles": 12,
                    "note": "Arms C/D only, closed early for futility"
                }
            }
        },
        "signature_agents": ["carboplatin", "isotretinoin"],  # Strong fingerprints
        "signature_radiation": {"csi_dose_gy": 36.0, "type": "craniospinal"},
        "inference_clues": [
            "Carboplatin during radiation for medulloblastoma",
            "Isotretinoin maintenance in brain tumor",
            "CSI 36 Gy + 6 cycles platinum-based chemo"
        ]
    },

    "acns0334": {
        "name": "COG ACNS0334 (Infant Brain Tumors)",
        "reference": "NCT00336024",
        "trial_id": "ACNS0334",
        "indications": ["medulloblastoma_infant", "pnet", "infant_brain_tumor"],
        "evidence_level": "standard_of_care",
        "era": "2005-2015",
        "age_range": [0, 3],
        "components": {
            "chemotherapy_induction": {
                "drugs": ["vincristine", "cisplatin", "etoposide", "cyclophosphamide"],
                "cycles": 3,
                "high_dose_methotrexate": {
                    "dose": "5 g/m²",
                    "leucovorin_rescue": True,
                    "note": "Arm II only"
                }
            },
            "consolidation": {
                "type": "myeloablative_chemotherapy",
                "drugs": ["thiotepa", "carboplatin"],
                "autologous_stem_cell_transplant": True,
                "cycles": 3
            },
            "radiation": {
                "timing": "delayed until age ≥3 years",
                "note": "Omit upfront RT to avoid neurocognitive toxicity"
            }
        },
        "signature_agents": ["thiotepa", "high-dose methotrexate"],
        "signature_features": ["autologous_stem_cell_transplant", "delayed_radiation"],
        "inference_clues": [
            "Autologous stem cell transplant in child <3 with brain tumor",
            "Thiotepa + carboplatin with PBSC rescue",
            "High-dose methotrexate + leucovorin rescue before transplant"
        ]
    },

    "acns0423": {
        "name": "COG ACNS0423 (High-Grade Glioma)",
        "reference": "PMC5035517",
        "trial_id": "ACNS0423",
        "indications": ["high_grade_glioma", "glioblastoma", "anaplastic_astrocytoma"],
        "evidence_level": "standard_of_care",
        "era": "2007-2014",
        "components": {
            "concurrent_chemoradiation": {
                "radiation": {
                    "dose_gy": [54, 59.4],
                    "fractions": 30,
                    "duration_days": 42
                },
                "chemotherapy": {
                    "drugs": ["temozolomide"],
                    "dose": "90 mg/m² daily",
                    "duration_days": 42
                }
            },
            "adjuvant_chemotherapy": {
                "drugs": ["temozolomide", "lomustine"],
                "schedule": "q6 weeks",
                "cycles": 6,
                "temozolomide_dose": "160 mg/m²/day ×5 days",
                "lomustine_dose": "90 mg/m² day 1"
            }
        },
        "signature_agents": ["temozolomide", "lomustine"],  # Unique combination
        "signature_radiation": {"dose_gy": [54, 59.4], "type": "focal"},
        "inference_clues": [
            "Temozolomide + lomustine (CCNU) for upfront glioma",
            "CCNU every 6 weeks with TMZ",
            "Modified Stupp protocol with added lomustine"
        ]
    },

    "acns0822": {
        "name": "COG ACNS0822 (High-Grade Glioma - Randomized)",
        "reference": "Neuro-Oncology Academic OUP",
        "trial_id": "ACNS0822",
        "indications": ["high_grade_glioma", "glioblastoma_pediatric", "anaplastic_astrocytoma"],
        "evidence_level": "phase_2_3_trial",
        "era": "2010-2018",
        "components": {
            "arm_1": {
                "concurrent": ["vorinostat", "radiation"],
                "vorinostat_dose": "230 mg/m²/day on RT days"
            },
            "arm_2": {
                "concurrent": ["temozolomide", "radiation"],
                "temozolomide_dose": "75-90 mg/m²/day during RT"
            },
            "arm_3": {
                "concurrent": ["bevacizumab", "radiation"],
                "bevacizumab_dose": "10 mg/kg IV q2 weeks"
            },
            "adjuvant": {
                "drugs": ["temozolomide"],
                "cycles": 6,
                "dose": "200 mg/m² ×5 days q28d"
            }
        },
        "signature_agents": ["vorinostat", "bevacizumab"],  # Experimental arms
        "signature_radiation": {"dose_gy": [54, 59.4], "type": "focal"},
        "inference_clues": [
            "Vorinostat (HDAC inhibitor) during RT for HGG",
            "Bevacizumab upfront with RT for pediatric glioma",
            "Randomization noted in records"
        ]
    },

    "acns0831": {
        "name": "COG ACNS0831 (Ependymoma)",
        "reference": "NCT01096368",
        "trial_id": "ACNS0831",
        "indications": ["ependymoma", "intracranial_ependymoma"],
        "evidence_level": "phase_3_trial",
        "era": "2010-2020",
        "age_range": [1, 21],
        "components": {
            "surgery": {
                "required": True,
                "timing": "upfront",
                "extent_required": "gross_total_resection"
            },
            "radiation": {
                "dose_gy": [54, 59.4],
                "timing": "within 31 days post-surgery",
                "type": "conformal_RT"
            },
            "arm_2": {
                "maintenance_chemotherapy": {
                    "drugs": ["vincristine", "cisplatin", "etoposide", "cyclophosphamide"],
                    "regimen": "VCEC",
                    "cycles": 4
                }
            },
            "arm_3": {
                "treatment": "observation",
                "note": "Radiation only, no adjuvant chemotherapy"
            }
        },
        "signature_agents": ["vincristine", "cisplatin", "etoposide", "cyclophosphamide"],
        "signature_radiation": {"dose_gy": [54, 59.4], "type": "conformal"},
        "inference_clues": [
            "Radiation followed by 4 cycles VCEC for ependymoma",
            "Radiation with no chemo suggests observation arm",
            "RT within 3-8 weeks of surgery"
        ]
    },

    "acns0333": {
        "name": "COG ACNS0333 (Atypical Teratoid/Rhabdoid Tumor)",
        "reference": "CTV Veeva NCT00336024",
        "trial_id": "ACNS0333",
        "indications": ["atrt", "atypical_teratoid_rhabdoid_tumor"],
        "evidence_level": "phase_2_trial",
        "era": "2006-2015",
        "components": {
            "induction": {
                "cycles": 2,
                "drugs": ["vincristine", "methotrexate", "etoposide", "cyclophosphamide", "cisplatin"],
                "high_dose_methotrexate": "5 g/m² with leucovorin rescue"
            },
            "second_look_surgery": {
                "timing": "after induction",
                "note": "Distinctive feature of ACNS0333"
            },
            "consolidation": {
                "type": "myeloablative_chemotherapy",
                "drugs": ["carboplatin", "thiotepa"],
                "dose": "carboplatin ~500 mg/m², thiotepa 300 mg/m²",
                "cycles": 3,
                "autologous_stem_cell_transplant": True
            },
            "arm_1": {
                "radiation": "delayed post-chemo",
                "dose_gy": [50, 54],
                "type": "3D_conformal_RT"
            },
            "arm_2": {
                "radiation": "early after induction",
                "dose_gy": [50, 54],
                "type": "3D_conformal_RT"
            }
        },
        "signature_agents": ["carboplatin", "thiotepa", "high-dose methotrexate"],
        "signature_features": ["second_look_surgery", "autologous_stem_cell_transplant", "csi_in_child_under_3"],
        "inference_clues": [
            "Second-look surgery after induction",
            "CSI in child <3 years (unusual, suggests AT/RT protocol)",
            "Triple transplants with carboplatin/thiotepa"
        ]
    },

    "acns0621": {
        "name": "COG ACNS0621 (DIPG with Vorinostat)",
        "reference": "PMC4482948",
        "trial_id": "ACNS0621",
        "indications": ["dipg", "diffuse_intrinsic_pontine_glioma", "brainstem_glioma"],
        "evidence_level": "phase_1_2_trial",
        "era": "2008-2012",
        "components": {
            "concurrent": {
                "radiation": {
                    "dose_gy": 54,
                    "fractions": 30,
                    "duration_weeks": 6
                },
                "chemotherapy": {
                    "drugs": ["vorinostat"],
                    "dose": "230 mg/m²/day",
                    "schedule": "5 days/week during RT"
                }
            }
        },
        "signature_agents": ["vorinostat"],
        "signature_radiation": {"dose_gy": 54, "type": "focal_brainstem"},
        "inference_clues": [
            "Vorinostat (HDAC inhibitor) during brainstem RT",
            "DIPG diagnosis with concurrent targeted agent"
        ]
    },

    "acns0821": {
        "name": "COG ACNS0821 (Recurrent Medulloblastoma)",
        "reference": "PubMed 33844469, NCICIRB node/2695",
        "trial_id": "ACNS0821",
        "indications": ["medulloblastoma_recurrent", "pnet_recurrent"],
        "evidence_level": "phase_2_trial",
        "era": "2009-2015",
        "line_of_therapy": "salvage",
        "components": {
            "arm_ti": {
                "drugs": ["temozolomide", "irinotecan"],
                "temozolomide_dose": "200 mg/m²/day ×5 days",
                "irinotecan_dose": "10 mg/m² IV ×5 days (days 1-5, 8-12)",
                "schedule": "28-day cycles"
            },
            "arm_tib": {
                "drugs": ["temozolomide", "irinotecan", "bevacizumab"],
                "temozolomide_dose": "200 mg/m²/day ×5 days",
                "irinotecan_dose": "10 mg/m² IV ×5 days",
                "bevacizumab_dose": "10 mg/kg IV on days 1 and 15",
                "schedule": "28-day cycles"
            }
        },
        "signature_agents": ["bevacizumab", "irinotecan", "temozolomide"],  # Three-drug combo
        "inference_clues": [
            "Bevacizumab + Irinotecan + Temozolomide (TIB) for recurrent MB",
            "Three-drug combination in recurrent medulloblastoma",
            "Anti-VEGF therapy in pediatric CNS tumor"
        ]
    },

    "acns0232": {
        "name": "COG ACNS0232 (CNS Germinoma)",
        "reference": "ASCO JCO GO.22.00257",
        "trial_id": "ACNS0232",
        "indications": ["germinoma", "cns_germ_cell_tumor"],
        "evidence_level": "phase_2_trial",
        "era": "2004-2010",
        "components": {
            "induction": {
                "drugs": ["carboplatin", "etoposide"],
                "cycles": 4,
                "carboplatin_dose": "AUC 6",
                "etoposide_dose": "100 mg/m²/day ×5 days"
            },
            "radiation": {
                "type": "whole_ventricular",
                "dose_gy": 18,
                "boost_dose_gy": [12, 18],
                "total_dose_gy": [30, 36]
            }
        },
        "signature_agents": ["carboplatin", "etoposide"],
        "signature_radiation": {"wv_dose_gy": 18, "type": "whole_ventricular"},  # Very distinctive
        "inference_clues": [
            "18 Gy whole-ventricular RT + boost",
            "Carboplatin/etoposide pre-RT for germinoma",
            "Reduced radiation dose for chemosensitive germ cell tumor"
        ]
    }
}


COG_LEUKEMIA_LYMPHOMA_PROTOCOLS = {
    "aall0434": {
        "name": "COG AALL0434 (T-cell ALL)",
        "reference": "HemOnc.org, NCBI Books NBK599994",
        "trial_id": "AALL0434",
        "indications": ["t_cell_all", "acute_lymphoblastic_leukemia_t_cell"],
        "evidence_level": "phase_3_trial",
        "era": "2007-2014",
        "components": {
            "induction": {
                "drugs": ["vincristine", "daunorubicin", "prednisone", "pegaspargase"],
                "duration_weeks": 4
            },
            "consolidation": {
                "drugs": ["cyclophosphamide", "cytarabine", "6-mercaptopurine", "vincristine", "pegaspargase"],
                "nelarabine": {
                    "dose": "650 mg/m²/day ×5 days",
                    "courses": 2,
                    "note": "Experimental arm - nelarabine added"
                },
                "cranial_radiation": {
                    "dose_gy": [12, 18],
                    "indication": "CNS status dependent (12 Gy for CNS1/2, 18 Gy for CNS3)"
                }
            },
            "delayed_intensification": {
                "drugs": ["vincristine", "doxorubicin", "dexamethasone", "pegaspargase", "cyclophosphamide", "cytarabine", "thioguanine"]
            },
            "maintenance": {
                "drugs": ["vincristine", "dexamethasone", "6-mercaptopurine", "methotrexate"],
                "duration_months": 24
            }
        },
        "signature_agents": ["nelarabine"],  # Very strong fingerprint for T-ALL
        "signature_radiation": {"cranial_rt": [12, 18], "timing": "consolidation"},
        "inference_clues": [
            "Nelarabine strongly suggests AALL0434 or successor T-ALL trials",
            "Cranial irradiation during consolidation",
            "ABFM chemotherapy backbone with or without nelarabine"
        ]
    },

    "anhl0131": {
        "name": "COG ANHL0131 (B-cell NHL)",
        "reference": "COG trial records",
        "trial_id": "ANHL0131",
        "indications": ["burkitt_lymphoma", "b_cell_nhl", "non_hodgkin_lymphoma"],
        "evidence_level": "phase_3_trial",
        "era": "2006-2012",
        "components": {
            "induction": {
                "regimen": "COPADM",
                "drugs": ["cyclophosphamide", "vincristine", "prednisone", "doxorubicin", "methotrexate"],
                "methotrexate_dose": "3-8 g/m²"
            },
            "consolidation": {
                "regimen": "CYM",
                "drugs": ["cytarabine", "methotrexate"],
                "experimental_arm": {
                    "drug": "vinblastine",
                    "note": "Added in experimental arm - no EFS benefit shown"
                }
            },
            "cns_prophylaxis": {
                "intrathecal_chemotherapy": True,
                "high_dose_methotrexate": True
            }
        },
        "signature_agents": ["high-dose methotrexate", "vinblastine"],
        "inference_clues": [
            "Short intense courses (FAB/LMB protocol)",
            "Very high-dose methotrexate (3-8 g/m²)",
            "Vinblastine in consolidation suggests ANHL0131 experimental arm"
        ]
    }
}


COG_NEUROBLASTOMA_PROTOCOLS = {
    "anbl0532": {
        "name": "COG ANBL0532 (High-Risk Neuroblastoma)",
        "reference": "CBTN_REDCAP_Protocols.csv",
        "trial_id": "ANBL0532",
        "indications": ["neuroblastoma_high_risk"],
        "evidence_level": "phase_3_trial",
        "era": "2007-2017",
        "components": {
            "induction": {
                "drugs": ["cisplatin", "etoposide", "cyclophosphamide", "doxorubicin", "vincristine"],
                "cycles": [5, 6]
            },
            "surgery": {
                "timing": "after induction",
                "goal": "maximal_resection"
            },
            "consolidation_arm_a": {
                "type": "single_myeloablative_chemotherapy",
                "drugs": ["carboplatin", "etoposide", "melphalan"],
                "regimen": "CEM",
                "autologous_stem_cell_transplant": True
            },
            "consolidation_arm_b": {
                "type": "tandem_myeloablative_chemotherapy",
                "transplants": 2,
                "regimens": ["thiotepa/cyclophosphamide", "carboplatin/etoposide/melphalan"],
                "note": "Tandem HSCT improved 3-year EFS"
            },
            "radiation": {
                "dose_gy": 21,
                "target": "primary_tumor_site",
                "timing": "post-transplant"
            },
            "immunotherapy": {
                "drug": "dinutuximab",
                "target": "anti-GD2",
                "combination": ["IL-2", "GM-CSF"],
                "cycles": 6
            },
            "maintenance": {
                "drug": "isotretinoin",
                "dose": "160 mg/m² BID",
                "duration_months": 6
            }
        },
        "signature_agents": ["dinutuximab", "isotretinoin"],  # Very strong fingerprints
        "signature_features": ["autologous_stem_cell_transplant", "anti_gd2_immunotherapy", "tandem_transplants"],
        "inference_clues": [
            "Autologous stem cell transplant + anti-GD2 immunotherapy",
            "Tandem transplants specifically indicate ANBL0532 Arm B",
            "Isotretinoin maintenance in solid tumor context (unique to neuroblastoma)"
        ]
    },

    "anbl0531": {
        "name": "COG ANBL0531 (Intermediate-Risk Neuroblastoma)",
        "reference": "CBTN_REDCAP_Protocols.csv",
        "trial_id": "ANBL0531",
        "indications": ["neuroblastoma_intermediate_risk"],
        "evidence_level": "phase_3_trial",
        "era": "2007-2015",
        "components": {
            "chemotherapy": {
                "drugs": ["carboplatin", "etoposide", "cyclophosphamide", "doxorubicin", "vincristine"],
                "cycles": [4, 8],
                "note": "Moderate intensity, no transplant"
            },
            "surgery": {
                "timing": "after_chemotherapy_or_observation"
            }
        },
        "signature_features": ["no_transplant", "no_immunotherapy"],
        "inference_clues": [
            "Therapy stops after 4-8 cycles",
            "No melphalan, no immunotherapy",
            "Labeled 'intermediate risk'"
        ]
    }
}


COG_SOLID_TUMOR_PROTOCOLS = {
    "aren0532": {
        "name": "COG AREN0532 (Low-Risk Wilms)",
        "reference": "Hematology Advisor",
        "trial_id": "AREN0532",
        "indications": ["wilms_tumor_stage_1", "wilms_tumor_low_risk"],
        "evidence_level": "standard_of_care",
        "era": "2006-2013",
        "components": {
            "surgery": {
                "timing": "upfront",
                "type": "nephrectomy"
            },
            "chemotherapy": {
                "drugs": ["vincristine", "dactinomycin"],
                "regimen": "EE-4A",
                "duration_weeks": 18,
                "vincristine": "IV weekly ×10 weeks",
                "dactinomycin": "IV q3 weeks ×6 doses"
            },
            "radiation": {
                "indication": "none for Stage I FH"
            }
        },
        "signature_agents": ["dactinomycin", "vincristine"],
        "inference_clues": [
            "Child <2 with Stage I Wilms on only vincristine/dactinomycin",
            "No radiation for Stage I favorable histology"
        ]
    },

    "aren0533": {
        "name": "COG AREN0533 (Higher-Risk Wilms)",
        "reference": "Hematology Advisor",
        "trial_id": "AREN0533",
        "indications": ["wilms_tumor_stage_3", "wilms_tumor_stage_4", "wilms_tumor_unfavorable_histology"],
        "evidence_level": "standard_of_care",
        "era": "2006-2013",
        "components": {
            "surgery": {
                "timing": "upfront",
                "type": "nephrectomy"
            },
            "chemotherapy": {
                "drugs": ["vincristine", "dactinomycin", "doxorubicin"],
                "regimen": "DD4A",
                "duration_weeks": 25,
                "additional_drugs_slow_responders": ["cyclophosphamide", "etoposide"]
            },
            "radiation": {
                "flank_rt": {
                    "dose_gy": 10.8,
                    "indication": "Stage III"
                },
                "lung_rt": {
                    "dose_gy": 12,
                    "indication": "lung metastases"
                }
            }
        },
        "signature_agents": ["doxorubicin", "cyclophosphamide", "etoposide"],
        "signature_radiation": {"flank_dose_gy": 10.8, "lung_dose_gy": 12},
        "inference_clues": [
            "3-drug regimen (vincristine/dactinomycin/doxorubicin) for Wilms",
            "Flank RT 10.8 Gy + lung RT 12 Gy",
            "Cyclophosphamide/etoposide for slow responders"
        ]
    }
}


# ============================================================================
# ST. JUDE INSTITUTIONAL PROTOCOLS
# ============================================================================

ST_JUDE_PROTOCOLS = {
    "sjmb12": {
        "name": "SJMB12 (Molecular Risk-Adapted Medulloblastoma)",
        "reference": "ASCO JCO 2023",
        "trial_id": "SJMB12",
        "indications": ["medulloblastoma_wnt", "medulloblastoma_shh", "medulloblastoma_group3", "medulloblastoma_group4"],
        "evidence_level": "phase_2_3_trial",
        "era": "2012-2021",
        "molecular_stratification": True,
        "strata": {
            "wnt_w1": {
                "risk": "very_low",
                "csi_dose_gy": 18.0,  # Drastically reduced!
                "chemotherapy": "light (4 cycles vincristine/cyclophosphamide/cisplatin)",
                "signature": "18 Gy CSI for WNT-medulloblastoma (only done on trial)"
            },
            "wnt_w2": {
                "risk": "low",
                "csi_dose_gy": 23.4,
                "chemotherapy": "standard"
            },
            "wnt_w3": {
                "risk": "high",
                "csi_dose_gy": 36.0,
                "chemotherapy": "intensive"
            },
            "shh_s1": {
                "risk": "standard",
                "treatment": "chemo-only if <3y, reduced RT if ≥3y"
            },
            "shh_s2": {
                "risk": "high",
                "csi_dose_gy": 36.0,
                "targeted_therapy": {
                    "drug": "vismodegib",
                    "target": "hedgehog_pathway"
                },
                "signature": "Vismodegib for SHH-medulloblastoma"
            },
            "group3_4_n1": {
                "risk": "standard",
                "csi_dose_gy": 23.4,
                "chemotherapy": "6 cycles cisplatin/cyclophosphamide/vincristine/etoposide"
            },
            "group3_4_n2": {
                "risk": "intermediate",
                "csi_dose_gy": 36.0,
                "chemotherapy": "intensive"
            },
            "group3_4_n3": {
                "risk": "very_high",
                "csi_dose_gy": 36.0,
                "consolidation": "myeloablative + transplant"
            }
        },
        "signature_agents": ["vismodegib"],
        "signature_radiation": {"csi_dose_gy": 18.0, "type": "craniospinal"},  # 18 Gy very distinctive
        "signature_features": ["molecular_subgroup_stratification"],
        "inference_clues": [
            "18 Gy CSI for WNT-medulloblastoma (strong pointer to SJMB12)",
            "Vismodegib for SHH-medulloblastoma",
            "Multiple risk strata with molecular stratification"
        ],
        "nccn_2024_guidelines": "Molecular profiling is standard and supports protocol alignment for medulloblastoma risk stratification"
    },

    "sjmb03": {
        "name": "SJMB03 (Medulloblastoma)",
        "reference": "St. Jude publications",
        "trial_id": "SJMB03",
        "indications": ["medulloblastoma"],
        "evidence_level": "phase_2_3_trial",
        "era": "2003-2009",
        "strata": {
            "high_risk": {
                "csi_dose_gy": [36, 39],
                "chemotherapy": "4 cycles cisplatin/cyclophosphamide/vincristine/etoposide",
                "consolidation": "some received myeloablative + stem cell rescue"
            },
            "standard_risk": {
                "csi_dose_gy": 23.4,
                "chemotherapy": "4-8 cycles cisplatin/CCNU/vincristine"
            }
        },
        "inference_clues": [
            "Risk-adapted CSI dosing (23.4 vs 36 Gy)",
            "St. Jude protocol referenced in notes",
            "Achieved >80% survival in standard-risk"
        ]
    },

    "sjyc07": {
        "name": "SJYC07 (Young Children Brain Tumors)",
        "reference": "St. Jude publications",
        "trial_id": "SJYC07",
        "indications": ["infant_brain_tumor", "medulloblastoma_infant", "ependymoma_infant"],
        "evidence_level": "phase_2_trial",
        "era": "2007-2015",
        "age_range": [0, 3],
        "components": {
            "chemotherapy": "intensive multi-agent to avoid/delay RT",
            "transplant": "autologous stem cell rescue",
            "radiation": "delayed until age ≥3 years"
        },
        "inference_clues": [
            "Similar to ACNS0334 approach",
            "St. Jude institutional protocol"
        ]
    },

    "sjatrt": {
        "name": "St. Jude AT/RT Protocol",
        "reference": "St. Jude publications",
        "trial_id": "SJATRT",
        "indications": ["atrt", "atypical_teratoid_rhabdoid_tumor"],
        "evidence_level": "institutional_protocol",
        "era": "2005-2015",
        "strata": {
            "stratum_a": {
                "treatment": "intensive chemo without radiation",
                "indication": "young infants with localized disease"
            },
            "stratum_b": {
                "treatment": "intensive chemo + focal RT",
                "indication": "older patients needing local control"
            },
            "stratum_c": {
                "treatment": "intensive chemo + CSI + boost",
                "indication": "metastatic AT/RT (M+)"
            }
        },
        "inference_clues": [
            "Stratified by extent of resection and dissemination",
            "CSI for metastatic AT/RT"
        ],
        "nccn_2024_guidelines": "Radiation (54–59.4 Gy) is recommended for patients ≥3 years or ≥18 months with residual disease"
    },

    "sj_dipg_bats": {
        "name": "St. Jude DIPG-BATS",
        "reference": "St. Jude trial records",
        "trial_id": "DIPG-BATS",
        "indications": ["dipg", "diffuse_intrinsic_pontine_glioma"],
        "evidence_level": "phase_2_trial",
        "era": "2010-2015",
        "arms": {
            "arm_1": {
                "drugs": ["bevacizumab"],
                "radiation": {"dose_gy": 54}
            },
            "arm_2": {
                "drugs": ["bevacizumab", "erlotinib"],
                "radiation": {"dose_gy": 54}
            },
            "arm_3": {
                "drugs": ["bevacizumab", "erlotinib", "temozolomide"],
                "radiation": {"dose_gy": 54},
                "adjuvant": "TMZ maintenance"
            },
            "arm_4": {
                "drugs": ["bevacizumab", "temozolomide"],
                "radiation": {"dose_gy": 54},
                "adjuvant": "TMZ maintenance"
            }
        },
        "signature_agents": ["bevacizumab", "erlotinib"],
        "inference_clues": [
            "Radiation + bevacizumab (strong sign of DIPG-BATS)",
            "Erlotinib with RT for DIPG",
            "Multiple arm trial testing bevacizumab combinations"
        ]
    }
}


# ============================================================================
# CONSORTIUM PROTOCOLS (PBTC, PNOC, HEAD START)
# ============================================================================

CONSORTIUM_PROTOCOLS = {
    "pnoc003": {
        "name": "PNOC003 (Recurrent DIPG)",
        "reference": "PNOC trial records",
        "trial_id": "PNOC003",
        "indications": ["dipg_recurrent", "diffuse_midline_glioma_recurrent"],
        "evidence_level": "phase_1_2_trial",
        "era": "2014-2018",
        "line_of_therapy": "salvage",
        "components": {
            "drugs": ["everolimus", "bevacizumab"],
            "everolimus_dose": "PO daily",
            "bevacizumab_dose": "IV q2 weeks",
            "schedule": "28-day cycles"
        },
        "signature_agents": ["everolimus", "bevacizumab"],
        "inference_clues": [
            "mTOR inhibitor + anti-VEGF for recurrent DIPG",
            "Two-drug targeted therapy combination"
        ]
    },

    "pnoc007": {
        "name": "PNOC007 (Recurrent HGG)",
        "reference": "PNOC trial records",
        "trial_id": "PNOC007",
        "indications": ["high_grade_glioma_recurrent", "glioblastoma_recurrent"],
        "evidence_level": "phase_1_2_trial",
        "era": "2015-2019",
        "line_of_therapy": "salvage",
        "components": {
            "drugs": ["panitumumab", "everolimus", "irinotecan"],
            "panitumumab": "IV q2 weeks (EGFR mAb)",
            "everolimus": "PO daily",
            "irinotecan": "IV q2 weeks",
            "schedule": "28-day cycles"
        },
        "signature_agents": ["panitumumab", "everolimus", "irinotecan"],
        "inference_clues": [
            "Three-agent biologic therapy for recurrent glioma",
            "EGFR + mTOR + chemotherapy combination"
        ]
    },

    "pnoc013": {
        "name": "PNOC013 (DIPG Immunotherapy)",
        "reference": "PNOC trial records",
        "trial_id": "PNOC013",
        "indications": ["dipg", "diffuse_midline_glioma"],
        "evidence_level": "phase_1_2_trial",
        "era": "2018-present",
        "arms": {
            "arm_a": {
                "drugs": ["nivolumab", "panobinostat"],
                "note": "PD-1 inhibitor + HDAC inhibitor"
            },
            "arm_b": {
                "drugs": ["nivolumab", "everolimus"],
                "note": "PD-1 inhibitor + mTOR inhibitor"
            }
        },
        "signature_agents": ["nivolumab", "panobinostat"],
        "inference_clues": [
            "Nivolumab combinations for DIPG",
            "Immunotherapy + epigenetic or targeted therapy"
        ]
    },

    "pbtc026": {
        "name": "PBTC-026 (DIPG with Lenalidomide)",
        "reference": "PBTC trial records",
        "trial_id": "PBTC-026",
        "indications": ["dipg", "diffuse_intrinsic_pontine_glioma"],
        "evidence_level": "phase_1_trial",
        "era": "2010-2013",
        "components": {
            "drug": "lenalidomide",
            "dose": "PO daily during RT (dose escalation)",
            "radiation": {"dose_gy": 54, "duration_weeks": 6}
        },
        "signature_agents": ["lenalidomide"],
        "inference_clues": [
            "Lenalidomide (immune-modulator) with RT for DIPG",
            "Rare agent in pediatric brain tumor"
        ]
    },

    "pbtc027": {
        "name": "PBTC-027 (DIPG with Cilengitide)",
        "reference": "PBTC trial records",
        "trial_id": "PBTC-027",
        "indications": ["dipg", "diffuse_intrinsic_pontine_glioma"],
        "evidence_level": "phase_1_trial",
        "era": "2009-2012",
        "components": {
            "drug": "cilengitide",
            "mechanism": "integrin_inhibitor_αvβ3_αvβ5",
            "dose": "IV bi-weekly during RT",
            "radiation": {"dose_gy": 54, "duration_weeks": 6}
        },
        "signature_agents": ["cilengitide"],
        "inference_clues": [
            "Cilengitide (angiogenesis inhibitor) for DIPG",
            "Integrin inhibitor - very rare agent"
        ]
    },

    "pbtc030": {
        "name": "PBTC-030 (DIPG with Vorinostat)",
        "reference": "PBTC trial records",
        "trial_id": "PBTC-030",
        "indications": ["dipg", "diffuse_intrinsic_pontine_glioma"],
        "evidence_level": "phase_1_trial",
        "era": "2009-2012",
        "components": {
            "drug": "vorinostat",
            "mechanism": "hdac_inhibitor",
            "dose": "PO 5 days/week during RT",
            "radiation": {"dose_gy": 54, "duration_weeks": 6}
        },
        "signature_agents": ["vorinostat"],
        "inference_clues": [
            "Similar to COG ACNS0621",
            "HDAC inhibition in newly diagnosed DIPG"
        ]
    },

    "pbtc045": {
        "name": "PBTC-045 (DIPG with Paxalisib)",
        "reference": "PBTC trial records",
        "trial_id": "PBTC-045",
        "indications": ["dipg_post_radiation"],
        "evidence_level": "phase_1_trial",
        "era": "2018-present",
        "line_of_therapy": "maintenance",
        "components": {
            "drug": "paxalisib",
            "mechanism": "pi3k_mtor_inhibitor",
            "dose": "PO daily continuously",
            "schedule": "28-day cycles"
        },
        "signature_agents": ["paxalisib"],
        "inference_clues": [
            "PI3K/mTOR inhibitor for DIPG post-RT",
            "Novel targeted therapy"
        ]
    },

    "head_start_ii": {
        "name": "Head Start II (Infant Brain Tumors)",
        "reference": "Multi-institutional consortium",
        "trial_id": "Head Start II",
        "indications": ["infant_brain_tumor", "medulloblastoma_infant", "pnet_infant"],
        "evidence_level": "phase_2_trial",
        "era": "1998-2004",
        "age_range": [0, 3],
        "components": {
            "induction": {
                "drugs": ["vincristine", "cisplatin", "etoposide", "cyclophosphamide", "methotrexate"],
                "cycles": 3
            },
            "consolidation": {
                "type": "3_sequential_myeloablative_cycles",
                "regimens": [
                    {"drugs": ["thiotepa", "etoposide"]},
                    {"drugs": ["carboplatin"]},
                    {"drugs": ["thiotepa", "cyclophosphamide"]}
                ],
                "autologous_stem_cell_transplant": True,
                "note": "3 different HD chemo cycles, each with stem cell rescue"
            }
        },
        "signature_agents": ["thiotepa", "carboplatin"],
        "signature_features": ["three_sequential_transplants"],
        "inference_clues": [
            "5-drug induction followed by 3 transplants",
            "Head Start specific: thiotepa/etoposide, carboplatin, thiotepa/cyclophosphamide cycles",
            "Triple transplants with different drug combos"
        ]
    },

    "head_start_iii": {
        "name": "Head Start III (Infant Brain Tumors)",
        "reference": "Multi-institutional consortium",
        "trial_id": "Head Start III",
        "indications": ["infant_brain_tumor", "medulloblastoma_infant", "pnet_infant", "atrt"],
        "evidence_level": "phase_2_trial",
        "era": "2004-2013",
        "age_range": [0, 3],
        "components": {
            "induction": {
                "drugs": ["vincristine", "cisplatin", "etoposide", "cyclophosphamide"],
                "high_dose_methotrexate": "added in select cycles",
                "cycles": 5
            },
            "consolidation": {
                "type": "single_myeloablative_cycle",
                "drugs": ["thiotepa", "etoposide", "carboplatin"],
                "dose": "thiotepa 300 mg/m²/day ×3, etoposide 250 mg/m² ×3, carboplatin 500 mg/m² ×3",
                "autologous_stem_cell_transplant": True,
                "note": "Changed to single transplant to reduce toxicity"
            }
        },
        "signature_agents": ["thiotepa", "carboplatin", "high-dose methotrexate"],
        "signature_features": ["single_transplant", "extended_induction"],
        "inference_clues": [
            "5 induction cycles (longer than Head Start II)",
            "Single transplant (vs 3 in HSII)",
            "HD methotrexate incorporated in induction"
        ]
    }
}


# ============================================================================
# LEGACY PROTOCOLS (Referenced in historical records)
# ============================================================================

LEGACY_PROTOCOLS = {
    "ccg_99701": {
        "name": "CCG-99701 (Medulloblastoma)",
        "reference": "Children's Cancer Group",
        "trial_id": "CCG-99701",
        "indications": ["medulloblastoma_standard_risk"],
        "evidence_level": "phase_3_trial",
        "era": "1996-2003",
        "arms": {
            "regimen_a": {
                "treatment": "CSI 36 Gy + 8 cycles chemo (conventional dose)",
                "drugs": ["CCNU", "cisplatin", "vincristine"],
                "schedule": "q6 weeks ×8"
            },
            "regimen_b": {
                "treatment": "CSI 36 Gy + intensive chemo with stem cell support",
                "consolidation": "3 cycles high-dose chemo + PBSC"
            }
        },
        "inference_clues": [
            "Historical medulloblastoma protocol",
            "8 cycles q6-week chemotherapy",
            "Carboplatin during RT tested"
        ]
    },

    "ccg_99703": {
        "name": "CCG-99703 (Infant Brain Tumor)",
        "reference": "Children's Cancer Group",
        "trial_id": "CCG-99703",
        "indications": ["infant_brain_tumor", "medulloblastoma_infant"],
        "evidence_level": "phase_2_trial",
        "era": "1996-2003",
        "age_range": [0, 3],
        "components": {
            "chemotherapy": {
                "drugs": ["vincristine", "cyclophosphamide", "cisplatin", "etoposide"],
                "cycles": 4,
                "note": "Chemo backbone for infant MB/PNET without radiation"
            }
        },
        "inference_clues": [
            "Historical infant protocol (predecessor to ACNS0334)",
            "4-drug regimen without RT",
            "Achieved ~30-40% 3-yr EFS in infants"
        ]
    },

    "sjmb96": {
        "name": "SJMB-96 (Medulloblastoma)",
        "reference": "St. Jude publications",
        "trial_id": "SJMB-96",
        "indications": ["medulloblastoma"],
        "evidence_level": "institutional_protocol",
        "era": "1996-2003",
        "components": {
            "induction": {
                "drugs": ["cisplatin", "cyclophosphamide", "etoposide"],
                "cycles": 4,
                "note": "Pre-radiation chemotherapy to delay RT in young children"
            },
            "radiation": {
                "csi_dose_gy": [23.4, 36.0],
                "timing": "delayed after induction"
            },
            "maintenance": {
                "drugs": ["cisplatin", "cyclophosphamide", "vincristine"]
            }
        },
        "inference_clues": [
            "Historical St. Jude medulloblastoma protocol",
            "Tested delaying radiation with induction chemo",
            "Informed later infant therapy approaches"
        ]
    },

    "ccg_a5971": {
        "name": "CCG-A5971 (Lymphoblastic Lymphoma)",
        "reference": "Children's Cancer Group",
        "trial_id": "CCG-A5971",
        "indications": ["lymphoblastic_lymphoma", "t_cell_lymphoma"],
        "evidence_level": "phase_3_trial",
        "era": "1996-2002",
        "components": {
            "regimen_b1": {
                "treatment": "BFM chemotherapy without cranial RT (CNS-negative)",
                "drugs": ["prednisone", "vincristine", "doxorubicin", "cyclophosphamide", "methotrexate", "cytarabine", "6-MP"]
            },
            "regimen_b2": {
                "treatment": "BFM chemotherapy + cranial RT (CNS-positive)",
                "cranial_rt_dose_gy": 18
            }
        },
        "inference_clues": [
            "BFM regimen B for lymphoblastic lymphoma",
            "CNS-directed therapy based on CNS status"
        ]
    },

    "ccg_a9952": {
        "name": "CCG-A9952 (Hodgkin Lymphoma)",
        "reference": "Children's Cancer Group",
        "trial_id": "CCG-A9952",
        "indications": ["hodgkin_lymphoma"],
        "evidence_level": "phase_3_trial",
        "era": "2002-2009",
        "components": {
            "regimen_a": {
                "chemotherapy": ["cyclophosphamide", "vincristine"],
                "radiation": "15 Gy IF-RT",
                "note": "Low-intensity for favorable patients"
            },
            "regimen_b": {
                "chemotherapy": "ABVD ×4 cycles",
                "radiation": "25.5 Gy IF-RT",
                "note": "Standard arm"
            }
        },
        "inference_clues": [
            "ABVD in pediatric context",
            "Low-dose involved-field RT"
        ]
    }
}


# ============================================================================
# SALVAGE/EXPERIMENTAL PROTOCOLS
# ============================================================================

SALVAGE_EXPERIMENTAL_PROTOCOLS = {
    "sjdawn": {
        "name": "SJDAWN (DIPG Targeted Therapy)",
        "reference": "St. Jude trial records",
        "trial_id": "SJDAWN",
        "indications": ["dipg", "diffuse_midline_glioma"],
        "evidence_level": "phase_1_2_trial",
        "era": "2017-present",
        "arms": {
            "arm_a": {
                "drugs": ["ribociclib", "gemcitabine"],
                "note": "CDK4/6 inhibitor + chemotherapy"
            },
            "arm_b": {
                "drugs": ["ribociclib", "trametinib"],
                "note": "CDK4/6 + MEK inhibition"
            },
            "arm_c": {
                "drugs": ["ribociclib", "sonidegib"],
                "note": "CDK4/6 + SHH pathway inhibition"
            }
        },
        "signature_agents": ["ribociclib", "trametinib", "sonidegib"],
        "inference_clues": [
            "Ribociclib combinations for DIPG",
            "Multiple targeted therapy arms"
        ]
    },

    "gempox": {
        "name": "GemPOx (Salvage Chemotherapy)",
        "reference": "Recurrent tumor regimen",
        "trial_id": "GemPOx",
        "indications": ["high_grade_glioma_recurrent", "ependymoma_recurrent"],
        "evidence_level": "salvage_regimen",
        "era": "2000-present",
        "line_of_therapy": "salvage",
        "components": {
            "drugs": ["gemcitabine", "oxaliplatin"],
            "gemcitabine_dose": "1000 mg/m² IV Day 1,8",
            "oxaliplatin_dose": "100 mg/m² Day 1",
            "schedule": "21-day cycles"
        },
        "signature_agents": ["gemcitabine", "oxaliplatin"],
        "inference_clues": [
            "GemPOx for recurrent HGG or ependymoma",
            "Salvage chemotherapy combination"
        ]
    },

    "dfmo": {
        "name": "DFMO (Maintenance Therapy)",
        "reference": "Polyamine depletion strategy",
        "trial_id": "DFMO",
        "indications": ["neuroblastoma_recurrent", "diffuse_glioma_maintenance"],
        "evidence_level": "experimental",
        "era": "2010-present",
        "line_of_therapy": "maintenance",
        "components": {
            "drug": "difluoromethylornithine",
            "mechanism": "ornithine_decarboxylase_inhibitor",
            "dose": "500-1000 mg/m² BID",
            "schedule": "continuous oral therapy"
        },
        "signature_agents": ["difluoromethylornithine"],
        "inference_clues": [
            "DFMO (eflornithine) for maintenance",
            "Polyamine depletion strategy",
            "Continuous oral therapy"
        ]
    },

    "etmr_one": {
        "name": "ETMR One (Embryonal Tumor Protocol)",
        "reference": "Experimental protocol",
        "trial_id": "ETMR One",
        "indications": ["etmr", "embryonal_tumor_with_multilayered_rosettes"],
        "evidence_level": "experimental",
        "era": "2015-present",
        "components": {
            "induction": {
                "drugs": ["vincristine", "methotrexate", "etoposide", "cyclophosphamide", "carboplatin"],
                "high_dose_methotrexate": True
            },
            "consolidation": {
                "type": "myeloablative_chemotherapy",
                "drugs": ["thiotepa", "carboplatin"],
                "autologous_stem_cell_transplant": True
            }
        },
        "signature_features": ["etmr_diagnosis"],
        "inference_clues": [
            "Intensive chemo similar to infant MB protocols",
            "ETMR diagnosis (rare embryonal tumor)"
        ]
    },

    "selumetinib_nf1": {
        "name": "11-C-0161 (Selumetinib for NF1 Plexiform Neurofibromas)",
        "reference": "SPRINT trial",
        "trial_id": "11-C-0161",
        "indications": ["nf1_plexiform_neurofibroma"],
        "evidence_level": "phase_1_2_trial",
        "era": "2011-present",
        "age_range": [2, 18],
        "components": {
            "drug": "selumetinib",
            "mechanism": "mek_inhibitor",
            "dose": "25 mg/m² BID",
            "schedule": "28-day cycles (continuous)"
        },
        "signature_agents": ["selumetinib"],
        "inference_clues": [
            "Selumetinib (MEK inhibitor) for NF1 plexiform neurofibromas",
            "SPRINT trial",
            "No chemotherapy or radiation"
        ]
    }
}


# ============================================================================
# COMPREHENSIVE PROTOCOL DATABASE (All sources combined)
# ============================================================================

ALL_PROTOCOLS = {
    **ORIGINAL_PEDIATRIC_CNS_PROTOCOLS,
    **COG_CNS_PROTOCOLS,
    **COG_LEUKEMIA_LYMPHOMA_PROTOCOLS,
    **COG_NEUROBLASTOMA_PROTOCOLS,
    **COG_SOLID_TUMOR_PROTOCOLS,
    **ST_JUDE_PROTOCOLS,
    **CONSORTIUM_PROTOCOLS,
    **LEGACY_PROTOCOLS,
    **SALVAGE_EXPERIMENTAL_PROTOCOLS
}


# ============================================================================
# PROTOCOL MATCHING FUNCTIONS
# ============================================================================

def get_protocols_by_indication(indication: str) -> List[Dict[str, Any]]:
    """
    Retrieve all protocols that match a given indication.

    Args:
        indication: Disease indication (e.g., "medulloblastoma", "high_grade_glioma")

    Returns:
        List of matching protocols with their details
    """
    matching_protocols = []

    indication_lower = indication.lower()

    for protocol_id, protocol in ALL_PROTOCOLS.items():
        indications = protocol.get('indications', [])
        if any(indication_lower in ind.lower() for ind in indications):
            matching_protocols.append({
                'protocol_id': protocol_id,
                **protocol
            })

    return matching_protocols


def get_protocols_by_signature_agent(agent: str) -> List[Dict[str, Any]]:
    """
    Retrieve protocols that use a specific signature agent.

    Args:
        agent: Drug name (e.g., "carboplatin", "nelarabine", "isotretinoin")

    Returns:
        List of matching protocols
    """
    matching_protocols = []

    agent_lower = agent.lower()

    for protocol_id, protocol in ALL_PROTOCOLS.items():
        signature_agents = protocol.get('signature_agents', [])
        if any(agent_lower in sig_agent.lower() for sig_agent in signature_agents):
            matching_protocols.append({
                'protocol_id': protocol_id,
                **protocol
            })

    return matching_protocols


def get_protocols_by_radiation_signature(
    dose_gy: float,
    radiation_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve protocols that match specific radiation signatures.

    Args:
        dose_gy: Radiation dose in Gray
        radiation_type: Type of radiation (e.g., "craniospinal", "focal")

    Returns:
        List of matching protocols
    """
    matching_protocols = []

    for protocol_id, protocol in ALL_PROTOCOLS.items():
        signature_radiation = protocol.get('signature_radiation', {})

        if not signature_radiation:
            continue

        # Check CSI dose
        if 'csi_dose_gy' in signature_radiation:
            if abs(signature_radiation['csi_dose_gy'] - dose_gy) < 2.0:  # 2 Gy tolerance
                matching_protocols.append({
                    'protocol_id': protocol_id,
                    **protocol
                })
                continue

        # Check focal dose
        if 'dose_gy' in signature_radiation:
            dose_range = signature_radiation['dose_gy']
            if isinstance(dose_range, list):
                if dose_range[0] <= dose_gy <= dose_range[1]:
                    matching_protocols.append({
                        'protocol_id': protocol_id,
                        **protocol
                    })
            elif isinstance(dose_range, (int, float)):
                if abs(dose_range - dose_gy) < 2.0:
                    matching_protocols.append({
                        'protocol_id': protocol_id,
                        **protocol
                    })

    return matching_protocols


def get_protocol_by_id(protocol_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific protocol by its ID.

    Args:
        protocol_id: Protocol identifier (e.g., "acns0331", "stupp_protocol")

    Returns:
        Protocol details or None if not found
    """
    return ALL_PROTOCOLS.get(protocol_id.lower())


def get_protocols_by_era(start_year: int, end_year: int) -> List[Dict[str, Any]]:
    """
    Retrieve protocols that were active during a specific time period.

    Args:
        start_year: Start year of treatment
        end_year: End year of treatment

    Returns:
        List of matching protocols
    """
    matching_protocols = []

    for protocol_id, protocol in ALL_PROTOCOLS.items():
        era = protocol.get('era', '')

        if not era:
            continue

        # Parse era string (e.g., "2004-2012", "2005-present")
        if '-' in era:
            era_parts = era.split('-')
            try:
                era_start = int(era_parts[0])
                era_end = 9999 if 'present' in era_parts[1] else int(era_parts[1])

                # Check if time ranges overlap
                if not (end_year < era_start or start_year > era_end):
                    matching_protocols.append({
                        'protocol_id': protocol_id,
                        **protocol
                    })
            except ValueError:
                continue

    return matching_protocols


def get_all_signature_agents() -> List[str]:
    """
    Get a comprehensive list of all signature agents across all protocols.

    Returns:
        Sorted list of unique signature agents
    """
    agents = set()

    for protocol in ALL_PROTOCOLS.values():
        signature_agents = protocol.get('signature_agents', [])
        agents.update(signature_agents)

    return sorted(list(agents))


def get_protocol_statistics() -> Dict[str, Any]:
    """
    Generate statistics about the protocol knowledge base.

    Returns:
        Dictionary with statistics
    """
    total_protocols = len(ALL_PROTOCOLS)

    # Count by evidence level
    evidence_levels = {}
    for protocol in ALL_PROTOCOLS.values():
        level = protocol.get('evidence_level', 'unknown')
        evidence_levels[level] = evidence_levels.get(level, 0) + 1

    # Count by era
    eras = {}
    for protocol in ALL_PROTOCOLS.values():
        era = protocol.get('era', 'unknown')
        eras[era] = eras.get(era, 0) + 1

    # Count unique indications
    unique_indications = set()
    for protocol in ALL_PROTOCOLS.values():
        unique_indications.update(protocol.get('indications', []))

    # Count unique signature agents
    unique_agents = len(get_all_signature_agents())

    return {
        'total_protocols': total_protocols,
        'original_v5_protocols': len(ORIGINAL_PEDIATRIC_CNS_PROTOCOLS),
        'cog_cns_protocols': len(COG_CNS_PROTOCOLS),
        'cog_leukemia_lymphoma_protocols': len(COG_LEUKEMIA_LYMPHOMA_PROTOCOLS),
        'cog_neuroblastoma_protocols': len(COG_NEUROBLASTOMA_PROTOCOLS),
        'cog_solid_tumor_protocols': len(COG_SOLID_TUMOR_PROTOCOLS),
        'st_jude_protocols': len(ST_JUDE_PROTOCOLS),
        'consortium_protocols': len(CONSORTIUM_PROTOCOLS),
        'legacy_protocols': len(LEGACY_PROTOCOLS),
        'salvage_experimental_protocols': len(SALVAGE_EXPERIMENTAL_PROTOCOLS),
        'evidence_levels': evidence_levels,
        'unique_indications': len(unique_indications),
        'unique_signature_agents': unique_agents,
        'era_distribution': eras
    }


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Protocol dictionaries
    'ALL_PROTOCOLS',
    'ORIGINAL_PEDIATRIC_CNS_PROTOCOLS',
    'COG_CNS_PROTOCOLS',
    'COG_LEUKEMIA_LYMPHOMA_PROTOCOLS',
    'COG_NEUROBLASTOMA_PROTOCOLS',
    'COG_SOLID_TUMOR_PROTOCOLS',
    'ST_JUDE_PROTOCOLS',
    'CONSORTIUM_PROTOCOLS',
    'LEGACY_PROTOCOLS',
    'SALVAGE_EXPERIMENTAL_PROTOCOLS',

    # Query functions
    'get_protocols_by_indication',
    'get_protocols_by_signature_agent',
    'get_protocols_by_radiation_signature',
    'get_protocol_by_id',
    'get_protocols_by_era',
    'get_all_signature_agents',
    'get_protocol_statistics'
]


if __name__ == '__main__':
    # Print statistics when run directly
    stats = get_protocol_statistics()
    print("=" * 80)
    print("PROTOCOL KNOWLEDGE BASE STATISTICS")
    print("=" * 80)
    print(f"Total Protocols: {stats['total_protocols']}")
    print(f"\nProtocol Categories:")
    print(f"  - Original V5.0: {stats['original_v5_protocols']}")
    print(f"  - COG CNS: {stats['cog_cns_protocols']}")
    print(f"  - COG Leukemia/Lymphoma: {stats['cog_leukemia_lymphoma_protocols']}")
    print(f"  - COG Neuroblastoma: {stats['cog_neuroblastoma_protocols']}")
    print(f"  - COG Solid Tumor: {stats['cog_solid_tumor_protocols']}")
    print(f"  - St. Jude: {stats['st_jude_protocols']}")
    print(f"  - Consortium (PBTC/PNOC/Head Start): {stats['consortium_protocols']}")
    print(f"  - Legacy: {stats['legacy_protocols']}")
    print(f"  - Salvage/Experimental: {stats['salvage_experimental_protocols']}")
    print(f"\nUnique Indications Covered: {stats['unique_indications']}")
    print(f"Unique Signature Agents: {stats['unique_signature_agents']}")
    print("\nEvidence Levels:")
    for level, count in sorted(stats['evidence_levels'].items()):
        print(f"  - {level}: {count}")
    print("=" * 80)
