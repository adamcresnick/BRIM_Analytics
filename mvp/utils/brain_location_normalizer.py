import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Sequence


_DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent / "brain_tumor_location_ontology.json"


@dataclass(frozen=True)
class OntologyNode:
    source: str
    id: Optional[str]
    label: str
    needs_review: bool = False


@dataclass(frozen=True)
class NormalizedLocation:
    cbtn_code: int
    cbtn_label: str
    ontology_nodes: List[OntologyNode]
    matched_synonym: str
    confidence: float
    notes: Optional[str] = None


class BrainTumorLocationNormalizer:
    """
    Utility for normalising free-text brain tumour location mentions to
    canonical CBTN dictionary values and ontology nodes.
    """

    def __init__(self, mapping_path: Optional[Path] = None) -> None:
        path = mapping_path or _DEFAULT_MAPPING_PATH
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        self._locations: List[Dict] = payload["tumor_location"]
        self._synonym_index: Dict[str, Dict] = {}

        for location in self._locations:
            synonyms = location.get("preferred_synonyms", [])
            # include canonical label
            synonyms.append(location["cbtn_label"])
            normalised_syns = {self._normalise_text(s) for s in synonyms if s}
            location["__canonical_synonyms"] = normalised_syns

            for syn in normalised_syns:
                # keep first occurrence if duplicates show up; they refer to the same label
                self._synonym_index.setdefault(syn, location)

    @staticmethod
    def _normalise_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s/+-]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def normalise_label(self, label: str) -> Optional[NormalizedLocation]:
        """Normalise a single structured label (exact match against canonical/synonyms)."""
        if not label:
            return None

        key = self._normalise_text(label)
        location = self._synonym_index.get(key)
        if not location:
            return None

        return self._build_result(location, matched_synonym=label, confidence=1.0)

    def normalise_text(
        self,
        text: str,
        min_confidence: float = 0.55,
        top_n: int = 5
    ) -> List[NormalizedLocation]:
        """
        Extract likely tumour locations from free text.

        Args:
            text: Raw note/paragraph.
            min_confidence: Minimum ratio to include in result list.
            top_n: Maximum number of candidates to return (sorted by confidence).
        """
        if not text:
            return []

        clean_text = self._normalise_text(text)
        if not clean_text:
            return []

        matches: List[NormalizedLocation] = []

        for location in self._locations:
            best_syn = ""
            best_score = 0.0

            for synonym in location["__canonical_synonyms"]:
                if not synonym:
                    continue

                if re.search(rf"\b{re.escape(synonym)}\b", clean_text):
                    score = 1.0
                else:
                    score = SequenceMatcher(None, synonym, clean_text).ratio()

                if score > best_score:
                    best_score = score
                    best_syn = synonym

            if best_score >= min_confidence:
                matches.append(self._build_result(location, best_syn, best_score))

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:top_n]

    def normalise_many(
        self,
        tokens: Sequence[str],
        min_confidence: float = 0.55
    ) -> List[NormalizedLocation]:
        """
        Convenience wrapper for structured lists (e.g., extracted spans).
        """
        results: List[NormalizedLocation] = []
        seen = set()

        for token in tokens:
            match = self.normalise_label(token)
            if not match:
                # fall back to free-text check for partial tokens
                candidates = self.normalise_text(token, min_confidence=min_confidence, top_n=1)
                match = candidates[0] if candidates else None

            if match and (match.cbtn_code, match.matched_synonym.lower()) not in seen:
                results.append(match)
                seen.add((match.cbtn_code, match.matched_synonym.lower()))

        return results

    def _build_result(self, location: Dict, matched_synonym: str, confidence: float) -> NormalizedLocation:
        nodes: List[OntologyNode] = []
        for node in location.get("ontology_nodes", []):
            nodes.append(
                OntologyNode(
                    source=node.get("id", "").split(":")[0] if node.get("id") else location.get("ontology_source", "UBERON"),
                    id=node.get("id"),
                    label=node.get("label"),
                    needs_review=node.get("needs_review", False)
                )
            )

        return NormalizedLocation(
            cbtn_code=location["cbtn_code"],
            cbtn_label=location["cbtn_label"],
            ontology_nodes=nodes,
            matched_synonym=matched_synonym,
            confidence=round(confidence, 4),
            notes=location.get("notes")
        )


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Normalise brain tumour location text.")
    parser.add_argument("text", nargs="*", help="Free-text snippet(s) to normalise.")
    parser.add_argument("--min-confidence", type=float, default=0.6, help="Minimum match confidence.")
    args = parser.parse_args()

    normaliser = BrainTumorLocationNormalizer()

    if not args.text:
        sys.exit("Provide text fragments to normalise.")

    for fragment in args.text:
        matches = normaliser.normalise_text(fragment, min_confidence=args.min_confidence)
        print(f"\nInput: {fragment}")
        if not matches:
            print("  No matches found.")
            continue
        for idx, match in enumerate(matches, start=1):
            nodes = ", ".join(f"{node.id or 'unknown'} ({node.label})" for node in match.ontology_nodes) or "n/a"
            print(f"  [{idx}] {match.cbtn_label} (code {match.cbtn_code}) | confidence={match.confidence} | nodes={nodes}")
