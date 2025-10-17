#!/usr/bin/env python3
"""
Context-Aware LLM Extractor for Phase 4
This extractor actively queries and uses outputs from Phases 1-3 to guide extraction.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ContextAwareLLMExtractor:
    """
    Enhanced Phase 4 extractor that leverages all previous phase outputs.
    """

    def __init__(self, ollama_model: str = "gemma2:27b"):
        self.ollama_model = ollama_model
        self.phase1_data = {}  # Structured data from Phase 1
        self.phase2_timeline = []  # Clinical timeline from Phase 2
        self.phase3_documents = {}  # Document selection metadata from Phase 3

    def set_context(self,
                   phase1_structured: Dict,
                   phase2_timeline: List[Dict],
                   phase3_docs: Dict):
        """
        Receive and store outputs from previous phases.
        """
        self.phase1_data = phase1_structured
        self.phase2_timeline = phase2_timeline
        self.phase3_documents = phase3_docs

        logger.info(f"Context loaded:")
        logger.info(f"  Phase 1: {len(self.phase1_data)} structured features")
        logger.info(f"  Phase 2: {len(self.phase2_timeline)} timeline events")
        logger.info(f"  Phase 3: {len(self.phase3_documents)} documents selected")

    def query_structured_data(self, query_type: str, params: Dict = None) -> Any:
        """
        Allow LLM to query structured data to inform extraction.
        """
        queries = {
            # Phase 1 queries
            'surgery_dates': lambda: self.phase1_data.get('surgical_events', []),
            'has_chemotherapy': lambda: self.phase1_data.get('has_chemotherapy', False),
            'has_radiation': lambda: self.phase1_data.get('has_radiation_therapy', False),
            'diagnosis_date': lambda: self.phase1_data.get('first_diagnosis_date'),
            'tumor_diagnosis': lambda: self.phase1_data.get('brain_tumor_diagnoses', []),

            # Phase 2 timeline queries
            'events_around_date': lambda: self._get_events_around_date(
                params.get('date'), params.get('window_days', 7)
            ),
            'event_sequence': lambda: self._get_event_sequence(
                params.get('event_type')
            ),
            'time_between_events': lambda: self._calculate_time_between_events(
                params.get('event1'), params.get('event2')
            ),

            # Phase 3 document queries
            'document_types_available': lambda: self._get_document_types(),
            'documents_for_event': lambda: self._get_documents_for_event(
                params.get('event_date')
            ),
            'imaging_reports': lambda: self._get_imaging_reports(
                params.get('date_range')
            )
        }

        if query_type in queries:
            return queries[query_type]()
        return None

    def _get_events_around_date(self, target_date: str, window_days: int) -> List[Dict]:
        """Get all events within window of target date."""
        target = datetime.fromisoformat(target_date)
        window = timedelta(days=window_days)

        nearby_events = []
        for event in self.phase2_timeline:
            event_date = datetime.fromisoformat(event['event_date'])
            if abs((event_date - target).days) <= window_days:
                nearby_events.append({
                    'event_type': event['event_type'],
                    'event_date': event['event_date'],
                    'days_from_target': (event_date - target).days
                })

        return sorted(nearby_events, key=lambda x: abs(x['days_from_target']))

    def _get_event_sequence(self, event_type: str = None) -> List[Dict]:
        """Get chronological sequence of events."""
        if event_type:
            events = [e for e in self.phase2_timeline if e['event_type'] == event_type]
        else:
            events = self.phase2_timeline

        return sorted(events, key=lambda x: x['event_date'])

    def _get_document_types(self) -> Dict[str, int]:
        """Get count of each document type available."""
        doc_types = {}
        for doc in self.phase3_documents.values():
            doc_type = doc.get('document_type', 'unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        return doc_types

    def create_context_aware_prompt(self,
                                   variable: str,
                                   document_text: str,
                                   document_metadata: Dict) -> str:
        """
        Create a prompt that actively uses context from all phases.
        """
        prompt_parts = []

        # 1. Start with system instruction
        prompt_parts.append("""You are extracting clinical data with access to VERIFIED STRUCTURED DATA.
Use this structured data to guide and validate your extraction.
""")

        # 2. Add Phase 1 structured data context
        prompt_parts.append("\n=== PHASE 1: STRUCTURED DATA (VERIFIED) ===")

        if variable == "extent_of_tumor_resection":
            # Query structured data for surgery context
            surgeries = self.query_structured_data('surgery_dates')
            if surgeries:
                prompt_parts.append(f"Known Surgeries: {len(surgeries)} total")
                for i, surgery in enumerate(surgeries[:3], 1):  # Show first 3
                    prompt_parts.append(f"  Surgery {i}: {surgery.get('surgery_date')} - {surgery.get('code_text', 'Unknown type')}")

            # Check if this document is from around a surgery date
            doc_date = document_metadata.get('document_date', '')
            if doc_date and surgeries:
                for surgery in surgeries:
                    surgery_date = surgery.get('surgery_date', '')
                    if surgery_date:
                        days_diff = self._calculate_days_between(doc_date, surgery_date)
                        if abs(days_diff) <= 30:
                            prompt_parts.append(f"\n⚠️ This document is {days_diff} days from surgery on {surgery_date}")
                            prompt_parts.append(f"   Surgery type: {surgery.get('code_text', 'Unknown')}")
                            break

        # 3. Add Phase 2 timeline context
        prompt_parts.append("\n=== PHASE 2: CLINICAL TIMELINE ===")

        # Get events around document date
        if document_metadata.get('document_date'):
            nearby_events = self.query_structured_data(
                'events_around_date',
                {'date': document_metadata['document_date'], 'window_days': 14}
            )
            if nearby_events:
                prompt_parts.append(f"Events near this document date:")
                for event in nearby_events[:5]:  # Show first 5
                    prompt_parts.append(f"  • {event['event_type']} ({event['days_from_target']:+d} days): {event['event_date']}")

        # 4. Add Phase 3 document selection context
        prompt_parts.append("\n=== PHASE 3: DOCUMENT CONTEXT ===")
        prompt_parts.append(f"Document Type: {document_metadata.get('document_type', 'Unknown')}")
        prompt_parts.append(f"Document Date: {document_metadata.get('document_date', 'Unknown')}")

        # Check why this document was selected
        if 'tier' in document_metadata:
            tier_explanations = {
                1: "Primary source (±7 days from event) - HIGHEST PRIORITY",
                2: "Secondary source (±14 days from event) - MEDIUM PRIORITY",
                3: "Tertiary source (±30 days from event) - LOWER PRIORITY"
            }
            prompt_parts.append(f"Selection Tier: {tier_explanations.get(document_metadata['tier'], 'Unknown')}")

        # 5. Variable-specific extraction instructions
        prompt_parts.append(f"\n=== EXTRACTION TASK: {variable.upper()} ===")

        if variable == "extent_of_tumor_resection":
            prompt_parts.append("""
Extract the extent of resection using ONLY these terms:
- Gross total resection (GTR) or "complete resection"
- Near-total resection (NTR) or "near total debulking" or ">95%"
- Subtotal resection (STR) or "subtotal debulking" or "50-95%"
- Partial resection or "partial debulking" or "<50%"
- Biopsy only

IMPORTANT CONTEXT RULES:
1. The surgery date in the document MUST match or be within 30 days of a known surgery
2. Post-operative imaging (1-30 days after surgery) is MORE RELIABLE than operative notes
3. Look for keywords: debulking, resection, residual tumor, extent
4. If this is an imaging report, prioritize statements about residual tumor

Common phrases to look for:
- "near total debulking" → Near-total resection
- "gross total resection achieved" → Gross total resection
- "substantial debulking" → Likely subtotal or near-total
- "residual tumor" → Indicates incomplete resection
""")

        elif variable == "tumor_histology":
            # Query diagnosis from Phase 1
            known_diagnosis = self.query_structured_data('tumor_diagnosis')
            if known_diagnosis:
                prompt_parts.append(f"Known diagnosis from structured data: {known_diagnosis}")

            prompt_parts.append("""
Extract the histological diagnosis and WHO grade.
Look for: pilocytic astrocytoma, glioblastoma, medulloblastoma, ependymoma, etc.
Include WHO grade if mentioned (I-IV).
""")

        elif variable == "tumor_location":
            prompt_parts.append("""
Extract the anatomical location of the tumor.
Be specific: cerebellar, brainstem, frontal lobe, temporal lobe, etc.
Look for: posterior fossa, supratentorial, infratentorial, ventricle
""")

        # 6. Add the actual document text
        prompt_parts.append("\n=== DOCUMENT TEXT TO ANALYZE ===")
        # Limit text to avoid token limits
        max_chars = 4000
        if len(document_text) > max_chars:
            prompt_parts.append(f"[Document truncated to {max_chars} characters]")
            prompt_parts.append(document_text[:max_chars])
        else:
            prompt_parts.append(document_text)

        # 7. Final extraction instruction
        prompt_parts.append(f"""
=== EXTRACTION INSTRUCTIONS ===
Based on the structured context above and the document text:
1. Extract {variable}
2. Verify it aligns with the known structured data
3. If there's a discrepancy, trust post-operative imaging over operative notes
4. Return your answer in this JSON format:
{{
  "value": "extracted value or 'Not found'",
  "confidence": 0.0 to 1.0,
  "supporting_text": "relevant quote from document",
  "date_extracted": "date mentioned in document if any",
  "aligns_with_structured": true/false,
  "notes": "any important context or discrepancies"
}}
""")

        return '\n'.join(prompt_parts)

    def _calculate_days_between(self, date1_str: str, date2_str: str) -> int:
        """Calculate days between two date strings."""
        try:
            date1 = datetime.fromisoformat(date1_str.replace('Z', '+00:00'))
            date2 = datetime.fromisoformat(date2_str.replace('Z', '+00:00'))
            return (date1 - date2).days
        except:
            return 999  # Large number if can't calculate

    def extract_with_full_context(self,
                                 variable: str,
                                 document: Dict) -> Dict:
        """
        Perform extraction using all available context.
        """
        # Get document metadata
        doc_metadata = {
            'document_id': document.get('document_id', 'unknown'),
            'document_type': document.get('document_type', document.get('type', 'unknown')),
            'document_date': document.get('document_date', document.get('date', 'unknown')),
            'tier': document.get('tier', 0),
            's3_key': document.get('s3_key', '')
        }

        # Get document text (check multiple possible fields)
        doc_text = (document.get('content', '') or
                   document.get('text', '') or
                   document.get('result_information', ''))

        if not doc_text:
            logger.warning(f"No content for document {doc_metadata['document_id']}")
            return {'value': 'No content', 'confidence': 0.0}

        # Create context-aware prompt
        prompt = self.create_context_aware_prompt(
            variable,
            doc_text,
            doc_metadata
        )

        # Here you would call Ollama with the prompt
        # For now, return a structured response showing the context was used
        return {
            'value': 'Would extract with context',
            'confidence': 0.95,
            'supporting_text': 'Context-aware extraction',
            'used_phase1': True,
            'used_phase2': True,
            'used_phase3': True,
            'prompt_length': len(prompt)
        }


# Example usage showing the context-aware approach
def demonstrate_context_aware_extraction():
    """Show how the context-aware extractor works."""

    print("\n" + "="*80)
    print("CONTEXT-AWARE LLM EXTRACTION DEMONSTRATION")
    print("="*80)

    extractor = ContextAwareLLMExtractor()

    # Simulate Phase 1 structured data
    phase1_data = {
        'has_surgery': 'Yes',
        'surgical_events': [
            {
                'surgery_date': '2018-05-28T00:00:00+00:00',
                'code_text': 'CRANIOTOMY POSTERIOR FOSSA TUMOR RESECTION',
                'event_type': 'Initial CNS Tumor'
            }
        ],
        'has_chemotherapy': 'Yes',
        'has_radiation_therapy': 'No',
        'brain_tumor_diagnoses': ['Pilocytic astrocytoma']
    }

    # Simulate Phase 2 timeline
    phase2_timeline = [
        {
            'event_type': 'Initial Surgery',
            'event_date': '2018-05-28T00:00:00+00:00',
            'age_at_event': 4763
        },
        {
            'event_type': 'Post-op Imaging',
            'event_date': '2018-05-29T00:00:00+00:00',
            'age_at_event': 4764
        }
    ]

    # Simulate Phase 3 document selection
    phase3_docs = {
        'doc_001': {
            'document_id': 'doc_001',
            'document_type': 'post_op_imaging',
            'document_date': '2018-05-29T00:00:00+00:00',
            'tier': 1,
            'content': 'There has been near total debulking of the tumor...'
        }
    }

    # Load context from all phases
    extractor.set_context(phase1_data, phase2_timeline, phase3_docs)

    # Demonstrate querying structured data
    print("\n1. LLM can query structured data:")

    surgeries = extractor.query_structured_data('surgery_dates')
    print(f"   Query: 'surgery_dates' → Found {len(surgeries)} surgeries")

    nearby_events = extractor.query_structured_data(
        'events_around_date',
        {'date': '2018-05-29T00:00:00+00:00', 'window_days': 7}
    )
    print(f"   Query: 'events_around_date' → Found {len(nearby_events)} nearby events")

    # Show context-aware prompt
    print("\n2. Context-aware prompt includes:")

    test_doc = phase3_docs['doc_001']
    prompt = extractor.create_context_aware_prompt(
        'extent_of_tumor_resection',
        test_doc['content'],
        test_doc
    )

    # Count context elements
    phase1_refs = prompt.count('PHASE 1')
    phase2_refs = prompt.count('PHASE 2')
    phase3_refs = prompt.count('PHASE 3')

    print(f"   • Phase 1 structured data: {phase1_refs} reference(s)")
    print(f"   • Phase 2 timeline context: {phase2_refs} reference(s)")
    print(f"   • Phase 3 document metadata: {phase3_refs} reference(s)")
    print(f"   • Total prompt length: {len(prompt)} characters")

    # Show key context being used
    print("\n3. Key context being leveraged:")
    print("   • Document is 1 day after known surgery")
    print("   • Document type is 'post_op_imaging' (Tier 1 - highest priority)")
    print("   • Known surgery type: CRANIOTOMY POSTERIOR FOSSA")
    print("   • Timeline shows this is immediately post-operative")

    print("\n" + "="*80)
    print("This approach allows the LLM to:")
    print("• Query structured data to validate extractions")
    print("• Understand temporal relationships from timeline")
    print("• Know why each document was selected")
    print("• Make context-informed extraction decisions")
    print("="*80)

if __name__ == "__main__":
    demonstrate_context_aware_extraction()