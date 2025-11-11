#!/usr/bin/env python3
"""
Prototype rule-based medulloblastoma treatment classifier.

Inputs:
  --meds CSV of v_medications cohort (mb_medications_athena.csv)
  --chemo-drugs CSV dump of fhir_prd_db.v_chemotherapy_drugs
  --chemo-map  CSV dump of fhir_prd_db.v_chemotherapy_rxnorm_codes
  --radiation CSV from v_radiation_episode_enrichment
  --procedures CSV from v_procedures_tumor
  --demographics CSV from v_patient_demographics
  --output-dir directory for classifier outputs

Outputs:
  {output-dir}/mb_protocol_assignments.csv
  {output-dir}/mb_protocol_assignment_summary.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

DATE_COLS = (
    "medication_start_date",
    "mr_validity_period_start",
    "mr_authored_on",
    "cp_period_start",
)

# keywords that imply stem-cell collection or transplant
ASCR_KEYWORDS = (
    "stem cell",
    "ascr",
    "autologous transplant",
    "bone marrow transplant",
    "pheresis",
    "apheresis",
    "tice",
    "hematopoietic",
)

CANONICAL_OVERRIDES = {
    "lomustine (ccnu)": "lomustine",
    "vincristine sulfate": "vincristine",
    "methotrexate (antineoplastic)": "methotrexate",
    "carboplatin (antineoplastic)": "carboplatin",
    "cisplatin (antineoplastic)": "cisplatin",
    "cyclophosphamide (antineoplastic)": "cyclophosphamide",
}

KEY_AGENTS = {
    "cisplatin",
    "carboplatin",
    "vincristine",
    "lomustine",
    "cyclophosphamide",
    "thiotepa",
    "etoposide",
    "methotrexate",
    "temozolomide",
    "irinotecan",
    "bevacizumab",
    "thalidomide",
    "celecoxib",
    "fenofibrate",
}

SUPPORTIVE_CODE_OVERRIDES = {
    "celecoxib": {"140587", "205322"},
    "fenofibrate": {"8703", "477560", "349287"},
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meds", required=True)
    ap.add_argument("--chemo-drugs", required=True)
    ap.add_argument("--chemo-map", required=True)
    ap.add_argument("--radiation", required=True)
    ap.add_argument("--procedures", required=True)
    ap.add_argument("--demographics", required=True)
    ap.add_argument("--output-dir", required=True)
    return ap.parse_args()


def normalize_code(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    if s.endswith(".0"):
        s = s[:-2]
    return s


def parse_date(row: pd.Series) -> Optional[datetime]:
    for col in DATE_COLS:
        val = row.get(col)
        if pd.isna(val):
            continue
        if isinstance(val, str) and not val.strip():
            continue
        try:
            ts = pd.to_datetime(val)
            if isinstance(ts, pd.Timestamp):
                if ts.tzinfo is not None:
                    ts = ts.tz_convert(None)
                return ts.to_pydatetime()
            return ts
        except Exception:
            continue
    return None


def canonical_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    core = name.lower().strip()
    if not core or core == "nan":
        return ""
    return CANONICAL_OVERRIDES.get(core, core)


@dataclass
class PatientRecord:
    patient_id: str
    age_years: Optional[float] = None
    exposures: Dict[str, List[datetime]] = field(default_factory=lambda: defaultdict(list))
    exposure_events: List[Tuple[str, Optional[str], Optional[datetime]]] = field(default_factory=list)
    has_ascr: bool = False
    radiation_courses: List[Tuple[datetime, datetime, Optional[float]]] = field(default_factory=list)

    def add_exposure(self, agent: str, date: Optional[datetime], source: Optional[str]) -> None:
        self.exposures[agent].append(date)
        self.exposure_events.append((agent, source, date))

    def has_agents(self, agents: Iterable[str]) -> bool:
        for agent in agents:
            if not self.exposures.get(agent):
                return False
        return True

    def first_radiation_course(self) -> Optional[Tuple[datetime, datetime, Optional[float]]]:
        if not self.radiation_courses:
            return None
        return sorted(self.radiation_courses, key=lambda x: x[0] or datetime.max)[0]

    def max_total_dose(self) -> Optional[float]:
        if not self.radiation_courses:
            return None
        doses = [dose for _, _, dose in self.radiation_courses if dose]
        return max(doses) if doses else None


def build_reference_maps(drugs_path: str, map_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    drugs = pd.read_csv(drugs_path)
    chemo_map = pd.read_csv(map_path)

    ingred_lookup: Dict[str, str] = {}
    for _, row in drugs.iterrows():
        code = normalize_code(row.get("rxnorm_in"))
        if not code:
            continue
        ingred_lookup[code] = canonical_name(str(row.get("preferred_name", "")))

    product_lookup: Dict[str, str] = {}
    for _, row in chemo_map.iterrows():
        product = normalize_code(row.get("product_rxnorm_code"))
        ingredient = normalize_code(row.get("ingredient_rxnorm_code"))
        if product and ingredient:
            product_lookup[product] = ingredient

    # add manual overrides for supportive agents
    for agent, codes in SUPPORTIVE_CODE_OVERRIDES.items():
        for code in codes:
            ingred_lookup[code] = agent
            product_lookup[code] = code

    return ingred_lookup, product_lookup


def ingest_patients(args: argparse.Namespace) -> Dict[str, PatientRecord]:
    ingred_lookup, product_lookup = build_reference_maps(args.chemo_drugs, args.chemo_map)
    patients: Dict[str, PatientRecord] = {}

    def get_patient(pid: str) -> PatientRecord:
        if pid not in patients:
            patients[pid] = PatientRecord(patient_id=pid)
        return patients[pid]

    # Demographics
    demo = pd.read_csv(args.demographics)
    for _, row in demo.iterrows():
        pid = row["patient_fhir_id"]
        rec = get_patient(pid)
        rec.age_years = row.get("pd_age_years")

    # Procedures for ASCR flags
    procedures = pd.read_csv(args.procedures)
    procedures.fillna("", inplace=True)
    for _, row in procedures.iterrows():
        pid = row["patient_fhir_id"]
        text = " ".join(
            str(row.get(col, "")) for col in ("proc_code_text", "procedure_classification", "surgery_type")
        ).lower()
        if any(keyword in text for keyword in ASCR_KEYWORDS):
            get_patient(pid).has_ascr = True

    # Radiation
    radiation = pd.read_csv(args.radiation)
    for _, row in radiation.iterrows():
        pid = row["patient_fhir_id"]
        start = row.get("episode_start_date")
        end = row.get("episode_end_date")
        dose = row.get("total_dose_cgy")
        try:
            start_dt = pd.to_datetime(start) if pd.notna(start) else None
            end_dt = pd.to_datetime(end) if pd.notna(end) else None
        except Exception:
            start_dt = end_dt = None
        if start_dt or end_dt:
            get_patient(pid).radiation_courses.append((start_dt, end_dt, dose))

    # Medications
    meds = pd.read_csv(args.meds)
    if "rx_norm_codes" in meds.columns:
        code_col = "rx_norm_codes"
    elif "medication_rxnorm_code" in meds.columns:
        code_col = "medication_rxnorm_code"
    else:
        raise KeyError("Unable to locate RxNorm code column in meds file.")
    meds[code_col] = meds[code_col].fillna("").astype(str)
    has_chemo_name = "chemo_preferred_name" in meds.columns

    for _, row in meds.iterrows():
        pid = row["patient_fhir_id"]
        date = parse_date(row)
        source = row.get("source_table")

        if has_chemo_name:
            label = canonical_name(row.get("chemo_preferred_name", ""))
            if label and label in KEY_AGENTS:
                get_patient(pid).add_exposure(label, date, source)
                continue

        codes = [
            normalize_code(code)
            for code in row[code_col].replace(";", ",").split(",")
            if normalize_code(code)
        ]
        if not codes:
            continue
        for code in codes:
            ingredient_code = None
            if code in ingred_lookup:
                ingredient_code = code
            elif code in product_lookup:
                ingredient_code = product_lookup[code]
            if not ingredient_code:
                continue
            agent = ingred_lookup.get(ingredient_code)
            if not agent or agent not in KEY_AGENTS:
                continue
            get_patient(pid).add_exposure(agent, date, source)

    return patients


def overlap_with_radiation(rec: PatientRecord, agent: str) -> bool:
    if not rec.radiation_courses:
        return False
    agent_dates = [dt for dt in rec.exposures.get(agent, []) if dt]
    if not agent_dates:
        return False
    for start, end, _ in rec.radiation_courses:
        if not start or not end:
            continue
        for dt in agent_dates:
            if start <= dt <= end:
                return True
    return False


def age_within(rec: PatientRecord, min_age: Optional[float], max_age: Optional[float]) -> bool:
    if rec.age_years is None:
        return True
    if min_age is not None and rec.age_years < min_age:
        return False
    if max_age is not None and rec.age_years > max_age:
        return False
    return True


def classify_patient(rec: PatientRecord) -> Tuple[str, float, List[str], List[Tuple[str, Optional[str], Optional[str]]], List[Dict[str, object]]]:
    rationale: List[str] = []
    support_events: List[Tuple[str, Optional[str], Optional[str]]] = []
    confidence = 0.4

    def record_support(agents: Iterable[str]) -> None:
        for agent in agents:
            for ev in rec.exposure_events:
                if ev[0] == agent:
                    support_events.append(
                        (
                            agent,
                            ev[1],
                            ev[2].strftime("%Y-%m-%d") if isinstance(ev[2], datetime) else None,
                        )
                    )

    # Rule order matters
    if rec.has_agents(["temozolomide", "irinotecan"]):
        label = "ACNS0821-like"
        rationale.append("Temozolomide + irinotecan exposures detected.")
        if rec.exposures.get("bevacizumab"):
            label = "ACNS0821-like (+bevacizumab)"
            rationale.append("Bevacizumab present.")
            confidence += 0.1
        record_support(["temozolomide", "irinotecan", "bevacizumab"])
        confidence += 0.2
        return label, min(confidence, 0.95), rationale, support_events, []

    if rec.has_agents(["bevacizumab", "thalidomide", "celecoxib", "fenofibrate"]) and (
        rec.exposures.get("etoposide") or rec.exposures.get("cyclophosphamide")
    ):
        label = "MEMMAT-like"
        rationale.append("Bevacizumab + oral metronomic backbone detected.")
        record_support(["bevacizumab", "thalidomide", "celecoxib", "fenofibrate"])
        confidence += 0.25
        return label, min(confidence, 0.9), rationale, support_events, []

    if rec.has_agents(["cisplatin", "lomustine", "vincristine", "cyclophosphamide"]):
        if rec.age_years is not None and not age_within(rec, 3, 21):
            potentials = [
                {
                    "candidate": "ACNS0331-like",
                    "reason": f"Average-risk backbone detected but age {rec.age_years}y outside 3–21y window.",
                    "missing_data": ["confirm age / non-standard protocol usage"],
                }
            ]
            return "POTENTIAL_ACNS0331-like", confidence, rationale, support_events, potentials
        if rec.max_total_dose() and rec.max_total_dose() <= 2500:
            label = "NCCN WNT/SHH SOC"
            rationale.append("Low-dose CSI with classical average-risk maintenance backbone.")
        else:
            label = "ACNS0331-like"
            rationale.append("Average-risk backbone (cis+CCNU+vin alternating cyclophosphamide).")
        record_support(["cisplatin", "lomustine", "vincristine", "cyclophosphamide"])
        confidence += 0.3
        return label, min(confidence, 0.85), rationale, support_events, []

    if rec.exposures.get("carboplatin"):
        concurrent = overlap_with_radiation(rec, "carboplatin")
        max_dose = rec.max_total_dose() or 0
        if concurrent and max_dose >= 3000:
            if rec.age_years is not None and not age_within(rec, 3, 21):
                potentials = [
                    {
                        "candidate": "ACNS0332-like",
                        "reason": f"Carboplatin overlaps CSI but age {rec.age_years}y outside 3–21y range.",
                        "missing_data": ["confirm age or nonstandard high-risk protocol"],
                    }
                ]
                return "POTENTIAL_ACNS0332-like", confidence, rationale, support_events, potentials
            label = "ACNS0332-like"
            rationale.append("Carboplatin overlaps CSI course (>=30 Gy).")
            record_support(["carboplatin"])
            confidence += 0.25
            return label, min(confidence, 0.85), rationale, support_events, []
        elif max_dose >= 3600:
            label = "NCCN Group 3/4 High-Risk"
            rationale.append("High-dose CSI (>=36 Gy) with carboplatin exposure.")
            record_support(["carboplatin"])
            confidence += 0.2
            return label, min(confidence, 0.8), rationale, support_events, []

    if rec.has_agents(["methotrexate"]) and rec.has_ascr and rec.exposures.get("thiotepa"):
        if rec.age_years is not None and rec.age_years > 10:
            potentials = [
                {
                    "candidate": "ACNS0334/HeadStart",
                    "reason": f"HD-MTX + thiotepa exposures detected but age {rec.age_years}y exceeds pediatric thresholds.",
                    "missing_data": ["validate age / confirm non-infant HDCT use"],
                }
            ]
            return "POTENTIAL_ACNS0334/HeadStart", confidence, rationale, support_events, potentials
        label = "ACNS0334/HeadStart-like"
        rationale.append("HD-MTX + thiotepa + ASCR signals infant protocol.")
        record_support(["methotrexate", "thiotepa"])
        confidence += 0.3
        return label, min(confidence, 0.85), rationale, support_events, []

    if rec.has_agents(["lomustine"]) and rec.exposures.get("etoposide"):
        label = "NCCN Recurrent Disease Option"
        rationale.append("Lomustine + etoposide exposures indicative of salvage therapy.")
        record_support(["lomustine", "etoposide"])
        confidence += 0.15
        return label, min(confidence, 0.75), rationale, support_events, []

    potentials = suggest_potentials(rec)
    if potentials:
        top = potentials[0]
        rationale.append(top["reason"])
        label = f"POTENTIAL_{top['candidate']}"
        confidence = min(confidence + 0.05, 0.5)
        return label, confidence, rationale, support_events, potentials

    return "UNCLASSIFIED", confidence, rationale, support_events, potentials


def suggest_potentials(rec: PatientRecord) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []

    patient_agents = set(rec.exposures.keys())

    if not rec.radiation_courses and any(agent in patient_agents for agent in KEY_AGENTS):
        out.append(
            {
                "candidate": "NEEDS_RADIATION_METADATA",
                "reason": "Chemotherapy exposures detected but no radiation record available.",
                "missing_data": ["CSI dose/dates to differentiate ACNS/NCCN regimens"],
            }
        )

    if rec.exposures.get("cisplatin") and rec.exposures.get("vincristine"):
        if rec.exposures.get("lomustine") or rec.exposures.get("cyclophosphamide"):
            missing = []
            if not rec.exposures.get("lomustine"):
                missing.append("lomustine exposure evidence")
            if not rec.exposures.get("cyclophosphamide"):
                missing.append("cyclophosphamide exposure evidence")
            if not rec.radiation_courses:
                missing.append("CSI dose/dates")
            else:
                missing.extend(
                    [
                        "alternating-cycle detection (cis/CCNU/vin vs cyclophosphamide/vin)",
                        "CSI dose confirmation (≤23.4 Gy vs ≥36 Gy)",
                    ]
                )
            out.append(
                {
                    "candidate": "ACNS0331-like",
                    "reason": "Cisplatin + vincristine backbone detected but alternating cycles/CSI context missing.",
                    "missing_data": missing,
                }
            )

    if rec.exposures.get("carboplatin"):
        missing = []
        if not rec.radiation_courses:
            missing.append("CSI dose/date data")
        elif not overlap_with_radiation(rec, "carboplatin"):
            missing.append("proof of real-time overlap with CSI fractions")
        out.append(
            {
                "candidate": "ACNS0332-like",
                "reason": "Carboplatin present without verified CSI concurrency.",
                "missing_data": missing,
            }
        )

    if rec.exposures.get("methotrexate") and not rec.exposures.get("thiotepa"):
        missing = []
        if not rec.has_ascr:
            missing.append("ASCR/pheresis procedure")
        missing.append("thiotepa ± carboplatin consolidation cycle")
        out.append(
            {
                "candidate": "ACNS0334/HeadStart",
                "reason": "HD-MTX noted but consolidation evidence is incomplete.",
                "missing_data": missing,
            }
        )

    if rec.exposures.get("bevacizumab") and (
        rec.exposures.get("thalidomide") or rec.exposures.get("celecoxib") or rec.exposures.get("fenofibrate")
    ):
        missing = []
        if not rec.exposures.get("etoposide"):
            missing.append("oral etoposide schedule")
        if not rec.exposures.get("cyclophosphamide"):
            missing.append("oral cyclophosphamide schedule")
        out.append(
            {
                "candidate": "MEMMAT-like",
                "reason": "Bevacizumab + partial metronomic backbone detected.",
                "missing_data": missing,
            }
        )

    return out


def main() -> None:
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    patients = ingest_patients(args)

    records: List[Dict[str, object]] = []
    label_counts = Counter()

    for pid, rec in patients.items():
        label, conf, rationale, support, potentials = classify_patient(rec)
        label_counts[label] += 1
        records.append(
            {
                "patient_id": pid,
                "classification": label,
                "confidence": round(conf, 3),
                "rationale": " | ".join(rationale) if rationale else "",
                "supporting_events": json.dumps(support),
                "potential_matches": json.dumps(potentials),
                "has_ascr": rec.has_ascr,
                "max_total_dose_cgy": rec.max_total_dose(),
                "age_years": rec.age_years,
            }
        )

    out_csv = os.path.join(args.output_dir, "mb_protocol_assignments.csv")
    pd.DataFrame(records).to_csv(out_csv, index=False)

    summary = {
        "total_patients": len(patients),
        "classification_counts": label_counts,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    out_summary = os.path.join(args.output_dir, "mb_protocol_assignment_summary.json")
    with open(out_summary, "w") as fh:
        json.dump(summary, fh, indent=2, default=lambda x: int(x) if isinstance(x, (int,)) else x)

    print(f"Wrote {out_csv} and {out_summary}")
    print("Top classifications:", label_counts.most_common())


if __name__ == "__main__":
    main()
