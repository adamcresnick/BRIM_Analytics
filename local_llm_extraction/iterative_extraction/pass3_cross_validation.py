"""
Pass 3: Cross-Source Validation
Compare and validate results from multiple sources
"""
import logging
from typing import Dict, List, Any
from collections import Counter
from .extraction_result import PassResult, Candidate, ExtractionResult

logger = logging.getLogger(__name__)

class CrossSourceValidator:
    """Validate extraction results across multiple sources"""

    def __init__(self):
        pass

    def validate(self, variable: str, extraction_result: ExtractionResult) -> PassResult:
        """
        Validate consistency across sources
        """
        result = PassResult(pass_number=3, method='cross_validation')

        # Collect all candidate values from Pass 1 and Pass 2
        candidates = extraction_result.get_all_candidates()

        if len(candidates) == 0:
            result.add_note("No candidates to validate")
            result.confidence_adjustment = 1.0
            return result

        # Group by value
        value_groups: Dict[str, List[Candidate]] = {}
        for candidate in candidates:
            val = candidate.value
            if val not in value_groups:
                value_groups[val] = []
            value_groups[val].append(candidate)

        logger.info(f"Cross-validation for {variable}: {len(value_groups)} unique values from {len(candidates)} candidates")

        # Apply consensus logic
        if len(value_groups) == 1:
            # Perfect agreement across all sources
            result = self._handle_perfect_consensus(value_groups, result)

        elif len(value_groups) == 2:
            # Two different values - need clinical reasoning
            result = self._handle_two_value_conflict(variable, value_groups, result)

        else:
            # Three or more conflicting values - high discordance
            result = self._handle_high_discordance(value_groups, result)

        # Apply variable-specific validation rules
        result = self._apply_variable_specific_rules(variable, result, value_groups)

        return result

    def _handle_perfect_consensus(self, value_groups: Dict[str, List[Candidate]], result: PassResult) -> PassResult:
        """Handle case where all sources agree"""
        consensus_value = list(value_groups.keys())[0]
        sources = value_groups[consensus_value]

        result.value = consensus_value

        # Boost confidence for multi-source agreement
        avg_confidence = sum(s.confidence for s in sources) / len(sources)

        if len(sources) >= 3:
            # 3+ sources agreeing - high confidence boost
            result.confidence = min(0.95, avg_confidence * 1.3)
            result.add_flag('strong_consensus', f'{len(sources)} sources agree')
        elif len(sources) == 2:
            # 2 sources agreeing - moderate boost
            result.confidence = min(0.90, avg_confidence * 1.15)
            result.add_flag('consensus', f'{len(sources)} sources agree')
        else:
            # Single source - use as-is
            result.confidence = avg_confidence
            result.add_note('Single source only - no cross-validation possible')

        result.sources = [s.source for s in sources]
        result.add_note(f"All {len(sources)} sources agree on: {consensus_value}")

        return result

    def _handle_two_value_conflict(self, variable: str, value_groups: Dict[str, List[Candidate]],
                                   result: PassResult) -> PassResult:
        """Handle case where two different values are found"""
        values = list(value_groups.keys())

        logger.warning(f"Conflict detected for {variable}: {values[0]} vs {values[1]}")

        result.add_flag('two_value_conflict', f'{values[0]} vs {values[1]}')

        # Variable-specific conflict resolution
        if variable == 'extent_of_tumor_resection':
            result = self._resolve_extent_conflict(value_groups, result)

        elif variable == 'tumor_location':
            result = self._resolve_location_conflict(value_groups, result)

        elif variable == 'histopathology':
            result = self._resolve_histology_conflict(value_groups, result)

        else:
            # Generic conflict resolution: use most confident source
            all_candidates = []
            for candidates in value_groups.values():
                all_candidates.extend(candidates)

            best = max(all_candidates, key=lambda c: c.confidence)
            result.value = best.value
            result.confidence = best.confidence * 0.7  # Reduce confidence due to conflict
            result.add_note(f"Conflict resolved using highest confidence source: {best.source}")

        return result

    def _resolve_extent_conflict(self, value_groups: Dict[str, List[Candidate]],
                                 result: PassResult) -> PassResult:
        """Resolve conflicts for extent of resection - operative note > imaging > clinical notes"""

        # Source priority hierarchy
        source_priority = {
            'operative_note': 3,
            'imaging': 2,
            'pathology': 2,
            'discharge_summary': 1,
            'clinical_note': 1,
            'structured_data': 1,
            'inference': 0
        }

        best_candidate = None
        best_priority = -1

        for candidates in value_groups.values():
            for candidate in candidates:
                # Determine source type priority
                priority = 0
                source_lower = candidate.source.lower()

                for source_type, prio in source_priority.items():
                    if source_type in source_lower or source_type in candidate.source_type:
                        priority = max(priority, prio)

                # Select based on priority, then confidence
                if priority > best_priority or (priority == best_priority and
                                                (not best_candidate or candidate.confidence > best_candidate.confidence)):
                    best_candidate = candidate
                    best_priority = priority

        if best_candidate:
            result.value = best_candidate.value
            result.confidence = best_candidate.confidence * 0.9  # Slight reduction for conflict
            result.add_note(f"Extent conflict resolved: {best_candidate.source} (priority level {best_priority}) overrides other sources")

            if best_priority == 3:
                result.add_flag('operative_note_authority', 'Operative note takes precedence')
            elif best_priority == 2:
                result.add_flag('imaging_authority', 'Imaging/pathology takes precedence')

        return result

    def _resolve_location_conflict(self, value_groups: Dict[str, List[Candidate]],
                                   result: PassResult) -> PassResult:
        """Resolve conflicts for tumor location - imaging > operative note > diagnoses"""

        source_priority = {
            'imaging': 3,
            'operative_note': 2,
            'pathology': 2,
            'diagnosis': 1,
            'structured_data': 1
        }

        best_candidate = None
        best_priority = -1

        for candidates in value_groups.values():
            for candidate in candidates:
                priority = 0
                source_lower = candidate.source.lower()

                for source_type, prio in source_priority.items():
                    if source_type in source_lower or source_type in candidate.source_type:
                        priority = max(priority, prio)

                if priority > best_priority or (priority == best_priority and
                                                (not best_candidate or candidate.confidence > best_candidate.confidence)):
                    best_candidate = candidate
                    best_priority = priority

        if best_candidate:
            result.value = best_candidate.value
            result.confidence = best_candidate.confidence
            result.add_note(f"Location conflict resolved: {best_candidate.source} takes precedence")

        return result

    def _resolve_histology_conflict(self, value_groups: Dict[str, List[Candidate]],
                                   result: PassResult) -> PassResult:
        """Resolve conflicts for histopathology - pathology report > all others"""

        # Pathology report is definitive
        pathology_candidates = []
        other_candidates = []

        for candidates in value_groups.values():
            for candidate in candidates:
                if 'pathology' in candidate.source.lower() or 'pathology' in candidate.source_type:
                    pathology_candidates.append(candidate)
                else:
                    other_candidates.append(candidate)

        if pathology_candidates:
            best = max(pathology_candidates, key=lambda c: c.confidence)
            result.value = best.value
            result.confidence = best.confidence
            result.add_flag('pathology_definitive', 'Pathology report is definitive for histology')
            result.add_note("Pathology report overrides all other sources for histology")
        else:
            # No pathology - use highest confidence
            all_candidates = other_candidates
            if all_candidates:
                best = max(all_candidates, key=lambda c: c.confidence)
                result.value = best.value
                result.confidence = best.confidence * 0.7
                result.add_note("No pathology report - using clinical diagnosis with reduced confidence")

        return result

    def _handle_high_discordance(self, value_groups: Dict[str, List[Candidate]],
                                 result: PassResult) -> PassResult:
        """Handle case with 3+ conflicting values"""

        result.add_flag('high_discordance', f'{len(value_groups)} different values found')

        # Count total sources per value
        value_counts = {val: len(candidates) for val, candidates in value_groups.items()}

        # Choose most frequent value, or highest confidence if tied
        most_common_value = max(value_counts.keys(), key=lambda v: (
            value_counts[v],  # Number of sources
            max(c.confidence for c in value_groups[v])  # Max confidence
        ))

        best_candidate = max(value_groups[most_common_value], key=lambda c: c.confidence)

        result.value = most_common_value
        result.confidence = best_candidate.confidence * 0.5  # Heavily reduce confidence
        result.add_note(f"High discordance: {len(value_groups)} different values. Selected most common/confident.")
        result.add_recommendation('Manual review required - conflicting sources')

        return result

    def _apply_variable_specific_rules(self, variable: str, result: PassResult,
                                       value_groups: Dict[str, List[Candidate]]) -> PassResult:
        """Apply variable-specific validation rules"""

        if variable == 'extent_of_tumor_resection' and result.value:
            # Check for anatomically impossible values
            if result.value == 'GTR' and 'multiple_surgeries' in str(result.flags):
                result.add_flag('plausibility_warning', 'GTR unlikely with multiple surgeries')
                result.confidence_adjustment = 0.7

        elif variable == 'tumor_location' and result.value:
            # Check for specific location mismatches
            if result.value and any('cerebellum' in val.lower() or 'posterior fossa' in val.lower()
                                   for val in value_groups.keys()):
                # If one source says cerebellum and another says different supratentorial location, flag it
                if any('frontal' in val.lower() or 'temporal' in val.lower()
                      for val in value_groups.keys()):
                    result.add_flag('location_mismatch', 'Posterior fossa vs supratentorial conflict')
                    result.confidence_adjustment = 0.6

        elif variable == 'histopathology' and result.value:
            # Check for grade consistency with histology
            if 'glioblastoma' in result.value.lower() or 'gbm' in result.value.lower():
                result.add_note("Glioblastoma is WHO Grade IV by definition")
            elif 'pilocytic' in result.value.lower():
                result.add_note("Pilocytic astrocytoma is WHO Grade I by definition")

        return result
