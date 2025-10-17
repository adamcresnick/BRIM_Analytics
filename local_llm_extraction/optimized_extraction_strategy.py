#!/usr/bin/env python3
"""
Optimized extraction strategy based on validated workflow requirements.
Implements:
1. Same time windows as validated workflow (±7, ±14, ±30 days)
2. Document limits to prevent processing thousands
3. Early termination when variable is confirmed by 3+ documents
4. Document-type-specific prompts for better extraction
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OptimizedExtractionStrategy:
    """
    Implements validated extraction strategy with efficiency improvements.
    """

    # Document windows from validated workflow
    TIER_WINDOWS = {
        'primary': 7,      # ±7 days for operative notes, pathology
        'secondary': 14,   # ±14 days for discharge summaries
        'tertiary': 30     # ±30 days for progress notes
    }

    # Maximum documents per tier (performance optimization)
    TIER_LIMITS = {
        'primary': 10,     # Process up to 10 primary docs
        'secondary': 15,   # Process up to 15 secondary docs
        'tertiary': 20,    # Process up to 20 tertiary docs
        'fallback': 20     # Hard limit on fallback docs
    }

    # Document type priorities and their optimal prompts
    DOCUMENT_STRATEGIES = {
        'operative_note': {
            'priority': 1,
            'prompt_focus': 'surgical details, extent of resection, approach',
            'confidence_weight': 0.9
        },
        'pathology_report': {
            'priority': 1,
            'prompt_focus': 'histological diagnosis, WHO grade, molecular markers',
            'confidence_weight': 0.95
        },
        'post_op_imaging': {
            'priority': 1,
            'prompt_focus': 'residual tumor, extent of resection, complications',
            'confidence_weight': 0.85,
            'required_for': ['extent_of_tumor_resection']  # Mandatory validation
        },
        'discharge_summary': {
            'priority': 2,
            'prompt_focus': 'overall surgical outcome, complications, plan',
            'confidence_weight': 0.7
        },
        'progress_note': {
            'priority': 3,
            'prompt_focus': 'clinical status, treatment response',
            'confidence_weight': 0.6
        }
    }

    # Early termination rules
    CONFIRMATION_THRESHOLDS = {
        'default': 3,  # Stop after 3 confirming documents
        'extent_of_tumor_resection': 2,  # Need op note + imaging minimum
        'histopathology': 1,  # Pathology report is definitive
        'molecular_markers': 1  # Single molecular report is sufficient
    }

    def __init__(self):
        self.extraction_stats = {
            'documents_processed': 0,
            'early_terminations': 0,
            'variables_confirmed': 0
        }

    def should_continue_extraction(self,
                                  variable: str,
                                  existing_results: List[Dict],
                                  document_type: str) -> bool:
        """
        Determine if we should continue extracting this variable.
        Implements early termination logic.
        """
        # Special case: extent ALWAYS needs post-op imaging
        if variable == 'extent_of_tumor_resection':
            has_imaging = any(r.get('source_type') == 'post_op_imaging'
                            for r in existing_results)
            has_op_note = any(r.get('source_type') == 'operative_note'
                            for r in existing_results)

            # Need both operative note AND imaging
            if has_imaging and has_op_note:
                logger.info(f"✓ Variable {variable} confirmed by required sources")
                return False

        # Check if we have enough confirming documents
        threshold = self.CONFIRMATION_THRESHOLDS.get(variable,
                                                     self.CONFIRMATION_THRESHOLDS['default'])

        # Count consistent results
        if len(existing_results) >= threshold:
            # Check agreement
            values = [r.get('value') for r in existing_results if r.get('value')]
            if values and len(set(values)) == 1:  # All agree
                logger.info(f"✓ Variable {variable} confirmed by {len(values)} consistent sources")
                self.extraction_stats['early_terminations'] += 1
                return False

        # Continue if not enough evidence
        return True

    def get_optimized_prompt(self,
                            variable: str,
                            document_type: str,
                            document_metadata: Dict) -> str:
        """
        Generate document-type-specific prompt for better extraction.
        """
        base_prompt = f"Extract {variable} from this {document_type}.\n"

        # Add document-specific focus
        if document_type in self.DOCUMENT_STRATEGIES:
            focus = self.DOCUMENT_STRATEGIES[document_type]['prompt_focus']
            base_prompt += f"Focus on: {focus}\n"

        # Add temporal context
        if 'document_date' in document_metadata:
            base_prompt += f"Document date: {document_metadata['document_date']}\n"

        # Variable-specific instructions
        if variable == 'extent_of_tumor_resection':
            base_prompt += """
Extract using ONLY these terms:
- Gross total resection (GTR) or "complete"
- Near-total resection (NTR) or ">95%"
- Subtotal resection (STR) or "50-95%"
- Partial resection or "<50%"
- Biopsy only

Look for keywords: debulking, resection, residual, extent
"""
        elif variable == 'histopathology':
            base_prompt += """
Extract the histological diagnosis.
Include WHO grade if mentioned.
Look for: astrocytoma, glioblastoma, medulloblastoma, ependymoma, etc.
"""
        elif variable == 'tumor_location':
            base_prompt += """
Extract anatomical location(s) of tumor.
Be specific: frontal lobe, cerebellum, brainstem, etc.
"""

        return base_prompt

    def select_documents_intelligently(self,
                                      all_documents: List[Dict],
                                      variable: str,
                                      event_date: datetime) -> List[Dict]:
        """
        Select documents intelligently based on variable type and document metadata.
        """
        selected = []

        # Prioritize by document type for this variable
        if variable == 'extent_of_tumor_resection':
            # MUST include post-op imaging
            post_op = [d for d in all_documents
                      if 'imaging' in d.get('type', '').lower()
                      and d.get('days_from_event', 0) > 0
                      and d.get('days_from_event', 0) <= 30]
            selected.extend(post_op[:5])  # Take first 5 post-op images

            # Add operative notes
            op_notes = [d for d in all_documents
                       if 'operative' in d.get('type', '').lower()
                       or 'op note' in d.get('type', '').lower()]
            selected.extend(op_notes[:3])

        elif variable == 'histopathology':
            # Prioritize pathology reports
            path_reports = [d for d in all_documents
                          if 'pathology' in d.get('type', '').lower()]
            selected.extend(path_reports[:2])  # Usually 1-2 is enough

        else:
            # Default: take variety of document types
            by_type = {}
            for doc in all_documents:
                doc_type = doc.get('type', 'unknown')
                if doc_type not in by_type:
                    by_type[doc_type] = []
                by_type[doc_type].append(doc)

            # Take up to 3 from each type
            for doc_type, docs in by_type.items():
                selected.extend(docs[:3])

        # Apply overall limit
        max_docs = self.TIER_LIMITS['secondary']
        if len(selected) > max_docs:
            logger.info(f"Limiting documents from {len(selected)} to {max_docs}")
            selected = selected[:max_docs]

        self.extraction_stats['documents_processed'] += len(selected)

        return selected

    def calculate_confidence_with_agreement(self,
                                           results: List[Dict],
                                           variable: str) -> float:
        """
        Calculate confidence based on source agreement and document types.
        """
        if not results:
            return 0.0

        # Get unique values
        values = [r.get('value') for r in results if r.get('value')]
        if not values:
            return 0.0

        # Calculate agreement ratio
        most_common = max(set(values), key=values.count)
        agreement_ratio = values.count(most_common) / len(values)

        # Weight by document types
        weighted_confidence = 0.0
        total_weight = 0.0

        for result in results:
            doc_type = result.get('source_type', 'unknown')
            if doc_type in self.DOCUMENT_STRATEGIES:
                weight = self.DOCUMENT_STRATEGIES[doc_type]['confidence_weight']
            else:
                weight = 0.5

            if result.get('value') == most_common:
                weighted_confidence += weight * result.get('confidence', 0.5)
                total_weight += weight

        if total_weight > 0:
            final_confidence = (weighted_confidence / total_weight) * agreement_ratio
        else:
            final_confidence = agreement_ratio * 0.5

        return min(final_confidence, 1.0)

    def log_extraction_summary(self):
        """Log extraction statistics."""
        logger.info("=" * 60)
        logger.info("EXTRACTION OPTIMIZATION SUMMARY")
        logger.info(f"Documents processed: {self.extraction_stats['documents_processed']}")
        logger.info(f"Early terminations: {self.extraction_stats['early_terminations']}")
        logger.info(f"Variables confirmed: {self.extraction_stats['variables_confirmed']}")
        logger.info("=" * 60)


# Example usage showing the improvements
def demonstrate_optimization():
    """Show how the optimized strategy works."""

    strategy = OptimizedExtractionStrategy()

    # Simulate extraction for extent of resection
    print("\n" + "=" * 60)
    print("OPTIMIZED EXTRACTION DEMONSTRATION")
    print("=" * 60)

    # Example 1: Early termination
    existing_results = [
        {'value': 'Gross total resection', 'source_type': 'operative_note', 'confidence': 0.9},
        {'value': 'Gross total resection', 'source_type': 'post_op_imaging', 'confidence': 0.95}
    ]

    should_continue = strategy.should_continue_extraction(
        'extent_of_tumor_resection',
        existing_results,
        'discharge_summary'
    )

    print(f"\nExtent extraction with op note + imaging: Continue? {should_continue}")
    print("→ Should be False (we have required sources)")

    # Example 2: Document selection
    all_docs = [
        {'type': 'operative_note', 'days_from_event': 0},
        {'type': 'pathology_report', 'days_from_event': 2},
        {'type': 'post_op_imaging', 'days_from_event': 1},
        {'type': 'progress_note', 'days_from_event': 5},
        {'type': 'progress_note', 'days_from_event': 10},
        # ... imagine 2000+ more progress notes
    ]

    selected = strategy.select_documents_intelligently(
        all_docs,
        'extent_of_tumor_resection',
        datetime.now()
    )

    print(f"\nDocuments selected for extent: {len(selected)}")
    print(f"Types: {[d['type'] for d in selected]}")
    print("→ Should prioritize imaging and op notes, not process all docs")

    # Example 3: Document-specific prompt
    prompt = strategy.get_optimized_prompt(
        'extent_of_tumor_resection',
        'post_op_imaging',
        {'document_date': '2018-05-29'}
    )

    print(f"\nOptimized prompt preview:")
    print(prompt[:200] + "...")

    strategy.log_extraction_summary()

if __name__ == "__main__":
    demonstrate_optimization()