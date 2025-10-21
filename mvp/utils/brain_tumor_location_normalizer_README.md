# Brain Tumor Location Normalization Utilities

This directory contains the scaffolding for normalising free-text or semi-structured tumour location mentions to the canonical CBTN dictionary values and a supporting anatomy ontology.

## Files

### `brain_tumor_location_ontology.json`
- JSON mapping of each CBTN tumour location code/label to one or more ontology concepts (primarily UBERON, with fallbacks when necessary).
- Each entry includes:
  - `ontology_nodes`: list of `{id, label, needs_review}` objects.
  - `preferred_synonyms`: curated phrases expected in imaging/operative/progress notes.
  - `notes`: guidance on substructures or special considerations.
- Synonym coverage reflects language from the CBTN data dictionary, sample charts, and the neuro-anatomy hierarchy described in the reference paper (`s41597-023-02389-4`).
- Ontology gaps are flagged with `needs_review`. Currently none remain after the latest pass.

### `brain_location_normalizer.py`
- Lightweight utility that loads the JSON mapping and resolves raw spans to canonical locations.
- Public API:
  - `normalise_label(text)` – exact/near-exact match for structured values (returns `NormalizedLocation` or `None`).
  - `normalise_text(text, min_confidence=0.55, top_n=5)` – fuzzy matching against longer free text (returns ranked candidates).
  - `normalise_many(tokens)` – convenience wrapper for lists of candidate spans.
- Confidence heuristic: exact synonym match = `1.0`; otherwise falls back to `difflib.SequenceMatcher` ratio.
- CLI helper: `python -m mvp.utils.brain_location_normalizer "text ..."`.

## Next Steps (pending integration)

1. **Synonym Tuning & QA**
   - Run the normaliser against a sample of imaging/operative notes; update synonyms/ontology IDs if any mentions fall through.
   - Add unit tests (e.g., `tests/test_brain_location_normalizer.py`) to lock in expected mappings.

2. **Workflow Integration**
   - Hook the normaliser into the Agent 2 extraction pipeline (after raw spans are identified).
   - Persist the normalised label + ontology IDs in timeline event metadata (`event_metadata.location`).
   - Compare outputs with REDCap `tumor_location` fields for consistency; surface conflicts to Agent 1.

3. **Documentation Updates**
   - Incorporate the normalisation flow into `COMPREHENSIVE_SYSTEM_DOCUMENTATION.md`.
   - Document how to extend the ontology mapping (synonyms, new regions) and how to run the CLI/tests.

4. **Potential Enhancements (post-MVP)**
   - Introduce embedding-based matching for rare phrases.
   - Produce JSON arrays of matched regions when multiple locations are mentioned in a single span.
   - Add tooling to round-trip updates with an external ontology service if we adopt one.
