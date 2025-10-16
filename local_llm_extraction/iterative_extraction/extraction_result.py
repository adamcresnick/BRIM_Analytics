"""
Data structures for multi-pass iterative extraction with clinical reasoning
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class Candidate:
    """A candidate value from a specific source"""
    value: str
    confidence: float
    source: str
    source_type: str  # 'document', 'structured_data', 'timeline', 'inference'
    supporting_text: str = ""
    date_extracted: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PassResult:
    """Result from a single extraction pass"""
    pass_number: int
    method: str  # 'document', 'structured_query', 'cross_validation', 'temporal'
    value: Optional[str] = None
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    candidates: List[Candidate] = field(default_factory=list)
    confidence_adjustment: float = 1.0
    notes: List[str] = field(default_factory=list)

    def add_candidate(self, value: str, confidence: float, source: str,
                     source_type: str = 'unknown', supporting_text: str = ""):
        """Add a candidate value"""
        self.candidates.append(Candidate(
            value=value,
            confidence=confidence,
            source=source,
            source_type=source_type,
            supporting_text=supporting_text,
            date_extracted=datetime.now()
        ))

    def add_flag(self, flag_name: str, flag_value: Any):
        """Add a clinical flag"""
        self.flags[flag_name] = flag_value

    def add_note(self, note: str):
        """Add a clinical note"""
        self.notes.append(note)

    def add_recommendation(self, recommendation: str):
        """Add a recommendation"""
        self.recommendations.append(recommendation)

@dataclass
class ExtractionResult:
    """Complete multi-pass extraction result with clinical reasoning"""
    variable: str
    patient_id: str
    event_date: str
    passes: List[PassResult] = field(default_factory=list)
    final_value: Optional[str] = None
    final_confidence: float = 0.0
    clinical_flags: List[str] = field(default_factory=list)
    needs_manual_review: bool = False
    all_candidates: List[Candidate] = field(default_factory=list)
    reasoning_chain: List[str] = field(default_factory=list)

    def add_pass(self, pass_num: int, result: PassResult):
        """Add a pass result"""
        self.passes.append(result)
        # Collect all candidates
        self.all_candidates.extend(result.candidates)

    def get_all_candidates(self) -> List[Candidate]:
        """Get all candidate values from all passes"""
        return self.all_candidates

    def merge_passes(self, pass_results: List[PassResult]):
        """Merge results from multiple passes"""
        # Collect unique values
        value_groups: Dict[str, List[Candidate]] = {}

        for pass_result in pass_results:
            for candidate in pass_result.candidates:
                if candidate.value not in value_groups:
                    value_groups[candidate.value] = []
                value_groups[candidate.value].append(candidate)

        # Update all_candidates
        for candidates in value_groups.values():
            self.all_candidates.extend(candidates)

    def finalize(self):
        """Aggregate all passes into final result with clinical reasoning"""
        if not self.passes:
            self.needs_manual_review = True
            self.reasoning_chain.append("No extraction passes completed")
            return

        # Get latest pass with a value
        valid_passes = [p for p in self.passes if p.value and p.value != "Not found"]

        if not valid_passes:
            # No valid extractions - check if we have candidates
            if self.all_candidates:
                # Use highest confidence candidate
                best_candidate = max(self.all_candidates, key=lambda c: c.confidence)
                if best_candidate.confidence >= 0.5:
                    self.final_value = best_candidate.value
                    self.final_confidence = best_candidate.confidence
                    self.reasoning_chain.append(f"Selected best candidate: {best_candidate.value} from {best_candidate.source}")
                else:
                    self.final_value = "No confident extractions"
                    self.final_confidence = 0.0
                    self.reasoning_chain.append("All candidates below confidence threshold (0.5)")
                    self.needs_manual_review = True
            else:
                self.final_value = "No confident extractions"
                self.final_confidence = 0.0
                self.reasoning_chain.append("No candidates extracted from any pass")
                self.needs_manual_review = True
            return

        # Use latest valid pass
        latest = valid_passes[-1]
        self.final_value = latest.value

        # Apply confidence adjustments from validation passes
        adjusted_conf = latest.confidence
        self.reasoning_chain.append(f"Pass {latest.pass_number} ({latest.method}): {latest.value} (confidence: {latest.confidence:.2f})")

        for p in self.passes[1:]:  # Skip first pass, apply adjustments from later passes
            if p.confidence_adjustment != 1.0:
                adjusted_conf *= p.confidence_adjustment
                self.reasoning_chain.append(f"Pass {p.pass_number} adjustment: {p.confidence_adjustment:.2f}x → {adjusted_conf:.2f}")

        self.final_confidence = max(0.0, min(1.0, adjusted_conf))

        # Collect all clinical flags
        for p in self.passes:
            for flag_name, flag_value in p.flags.items():
                flag_str = f"{flag_name}: {flag_value}"
                self.clinical_flags.append(flag_str)
                self.reasoning_chain.append(f"Clinical flag: {flag_str}")

        # Determine if manual review needed
        if self.final_confidence < 0.6:
            self.needs_manual_review = True
            self.reasoning_chain.append(f"Manual review: Low confidence ({self.final_confidence:.2f})")

        if any('discordance' in f.lower() or 'conflict' in f.lower() for f in self.clinical_flags):
            self.needs_manual_review = True
            self.reasoning_chain.append("Manual review: Conflicting sources detected")

        if any('unlikely' in f.lower() or 'warning' in f.lower() for f in self.clinical_flags):
            self.needs_manual_review = True
            self.reasoning_chain.append("Manual review: Clinical plausibility concerns")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'variable': self.variable,
            'patient_id': self.patient_id,
            'event_date': self.event_date,
            'final_value': self.final_value,
            'final_confidence': self.final_confidence,
            'needs_manual_review': self.needs_manual_review,
            'clinical_flags': self.clinical_flags,
            'reasoning_chain': self.reasoning_chain,
            'all_candidates': [
                {
                    'value': c.value,
                    'confidence': c.confidence,
                    'source': c.source,
                    'source_type': c.source_type,
                    'supporting_text': c.supporting_text[:500] if c.supporting_text else ""
                }
                for c in self.all_candidates
            ],
            'passes': [
                {
                    'pass_number': p.pass_number,
                    'method': p.method,
                    'value': p.value,
                    'confidence': p.confidence,
                    'flags': p.flags,
                    'notes': p.notes,
                    'recommendations': p.recommendations
                }
                for p in self.passes
            ]
        }
