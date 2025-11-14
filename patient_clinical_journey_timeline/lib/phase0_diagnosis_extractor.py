#!/usr/bin/env python3
"""
Phase 0.2: Primary Diagnosis Extractor

Extracts the most authoritative clinical diagnosis from multi-source diagnostic evidence.
This is NOT re-classification - it's finding what clinicians documented.

Part of Phase 0 WHO 2021 Nomenclature Standardization redesign.

Usage:
    from lib.phase0_diagnosis_extractor import DiagnosisExtractor

    extractor = DiagnosisExtractor(medgemma_agent)
    primary_diagnosis = extractor.extract_primary_diagnosis(
        diagnostic_evidence=evidence_list,
        pathology_data=pathology_records
    )
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DiagnosisExtractor:
    """
    Phase 0.2: Extract primary diagnosis from multi-source evidence.

    Prioritizes:
    1. Genomics/molecular reports (definitive pathology)
    2. Surgical pathology final diagnoses
    3. Clinical notes with diagnostic statements
    4. Problem list entries

    Handles:
    - Missing pathology (uses clinical documentation)
    - Conflicting sources (flags for review)
    - Minimal evidence (documents limitations)
    """

    def __init__(self, medgemma_agent):
        """
        Initialize diagnosis extractor.

        Args:
            medgemma_agent: MedGemma agent for extraction tasks
        """
        self.medgemma_agent = medgemma_agent
        logger.info("✅ V5.6: Phase 0.2 Diagnosis Extractor initialized")

    def extract_primary_diagnosis(
        self,
        diagnostic_evidence: List[Any],
        pathology_data: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Extract the most authoritative diagnosis from all available evidence.

        Args:
            diagnostic_evidence: List of DiagnosisEvidence objects from Phase 0.1
            pathology_data: Optional raw pathology records from v_pathology_diagnostics / molecular_test_results
                          (V5.6+: Phase 0.1 already provides comprehensive pathology evidence, so this is optional)

        Returns:
            Dict with:
                - primary_diagnosis: The diagnosis string
                - diagnosis_source: Where it came from
                - supporting_evidence: List of molecular/histologic details
                - concordance: Agreement across sources
                - evidence_quality: complete / partial / minimal / conflicting
                - confidence: Extraction confidence
                - raw_extraction: Full extraction details for audit
        """
        logger.info("   [Phase 0.2] Extracting primary diagnosis from multi-source evidence...")

        # Format diagnostic evidence summary
        evidence_summary = self._format_diagnostic_evidence(diagnostic_evidence)

        # Format pathology data (priority records only to avoid document too large)
        # V5.6+: This is optional since Phase 0.1 already provides comprehensive evidence
        pathology_summary = self._format_pathology_data(pathology_data) if pathology_data else "All pathology evidence already included in diagnostic_evidence from Phase 0.1"

        # Build extraction prompt
        extraction_prompt = f"""You are a medical data extraction specialist. Your task is to identify the PRIMARY INITIAL diagnosis AND detect any temporal diagnostic changes (recurrence, progression, second primary).

**CRITICAL INSTRUCTIONS:**
1. DO NOT create a new diagnosis - find what clinicians documented
2. Identify PRIMARY INITIAL DIAGNOSIS:
   - The EARLIEST authoritative diagnosis (genomics/surgical pathology)
   - This anchors the treatment timeline
   - Prioritize molecular/pathology over clinical notes
3. Detect TEMPORAL DIAGNOSTIC EVENTS:
   - Look for dated diagnoses that suggest: recurrence, progression, transformation, second primary
   - Flag if later diagnoses differ from initial (e.g., "anaplastic astrocytoma" 2016 → "glioblastoma" 2023)
   - Note if multiple distinct tumors mentioned
4. Extract VERBATIM - do not paraphrase or interpret
5. Source priority for PRIMARY diagnosis:
   a. Genomics/molecular reports with diagnostic summaries (earliest)
   b. Surgical pathology final diagnoses (earliest)
   c. Clinical oncology notes with diagnostic statements
   d. Radiology reports with diagnostic impressions
   e. Problem list entries

**DIAGNOSTIC EVIDENCE COLLECTED (Phase 0.1):**
{evidence_summary}

**PATHOLOGY/MOLECULAR DATA:**
{pathology_summary}

**YOUR TASK:**
Return this JSON structure:

{{
  "primary_initial_diagnosis": "Exact diagnosis text from EARLIEST authoritative source",
  "primary_diagnosis_source": "genomics_report / surgical_pathology / clinical_note / radiology / problem_list",
  "primary_source_text_quote": "Exact quote showing where you found the initial diagnosis",
  "primary_diagnosis_date": "YYYY-MM-DD or null (date of initial diagnosis)",

  "supporting_evidence": [
    "PTCH1 c.260_279del mutation",
    "TP53-wildtype",
    "Any molecular or histologic details mentioned in initial diagnosis"
  ],

  "temporal_diagnostic_events_detected": true/false,
  "temporal_diagnostic_events": [
    {{
      "event_type": "recurrence / progression / transformation / second_primary / diagnostic_revision",
      "diagnosis": "Exact diagnosis text",
      "date": "YYYY-MM-DD or null",
      "source": "genomics_report / surgical_pathology / clinical_note / radiology",
      "source_quote": "Exact quote",
      "relationship_to_primary": "Brief explanation of how this relates to initial diagnosis"
    }}
  ],

  "source_concordance": {{
    "all_sources_agree": true/false,
    "primary_sources_agree": true/false,
    "contradictions_noted": ["List any contradictions between sources"],
    "concordance_notes": "Brief explanation of agreement/disagreement"
  }},

  "evidence_quality": "complete / partial / minimal / conflicting",
  "evidence_quality_rationale": "Why this quality rating - what's available vs missing",

  "confidence": "high / moderate / low",
  "confidence_rationale": "Why this confidence level",

  "extraction_notes": "Any important caveats, ambiguities, or concerns"
}}

**EXAMPLES OF GOOD EXTRACTION:**

Example 1 - Single Diagnosis (No Temporal Changes):
{{
  "primary_initial_diagnosis": "medulloblastoma, SHH-activated and TP53-wildtype",
  "primary_diagnosis_source": "genomics_report",
  "primary_source_text_quote": "the findings described above are characteristic of a medulloblastoma, SHH-activated and TP53-wildtype [WHO Paediatric Tumours, 5th ed]",
  "primary_diagnosis_date": "2020-03-15",
  "temporal_diagnostic_events_detected": false,
  "temporal_diagnostic_events": [],
  "evidence_quality": "complete",
  "confidence": "high"
}}

Example 2 - Tumor Progression Detected:
{{
  "primary_initial_diagnosis": "anaplastic astrocytoma, IDH-mutant",
  "primary_diagnosis_source": "surgical_pathology",
  "primary_source_text_quote": "Pathology consistent with anaplastic astrocytoma, IDH1-mutant",
  "primary_diagnosis_date": "2016-03-20",
  "temporal_diagnostic_events_detected": true,
  "temporal_diagnostic_events": [
    {{
      "event_type": "progression",
      "diagnosis": "glioblastoma",
      "date": "2023-08-15",
      "source": "surgical_pathology",
      "source_quote": "Recurrent tumor shows features of glioblastoma",
      "relationship_to_primary": "Progression from initial anaplastic astrocytoma to glioblastoma at recurrence"
    }}
  ],
  "evidence_quality": "complete",
  "confidence": "high"
}}

Example 3 - Second Primary Malignancy:
{{
  "primary_initial_diagnosis": "pilocytic astrocytoma",
  "primary_diagnosis_source": "surgical_pathology",
  "primary_source_text_quote": "Low-grade pilocytic astrocytoma",
  "primary_diagnosis_date": "2015-06-10",
  "temporal_diagnostic_events_detected": true,
  "temporal_diagnostic_events": [
    {{
      "event_type": "second_primary",
      "diagnosis": "ependymoma, grade 2",
      "date": "2022-11-03",
      "source": "surgical_pathology",
      "source_quote": "Separate ependymoma identified in posterior fossa, distinct from prior pilocytic astrocytoma",
      "relationship_to_primary": "New distinct primary tumor, anatomically separate from initial pilocytic astrocytoma"
    }}
  ],
  "evidence_quality": "complete",
  "confidence": "high"
}}

**IMPORTANT:** Return ONLY the JSON object, no additional text.
"""

        try:
            # Use MedGemma to extract diagnosis
            # Temperature 0.0 for consistent extraction
            result = self.medgemma_agent.extract(extraction_prompt, temperature=0.0)

            # Parse JSON response
            extraction = json.loads(result.raw_response)

            # V5.6: Log result with new schema (primary_initial_diagnosis)
            # Backward compatible: also check old field name
            diagnosis = extraction.get('primary_initial_diagnosis') or extraction.get('primary_diagnosis', 'Unknown')
            source = extraction.get('primary_diagnosis_source') or extraction.get('diagnosis_source', 'unknown')
            diagnosis_date = extraction.get('primary_diagnosis_date', 'Unknown')
            quality = extraction.get('evidence_quality', 'unknown')
            confidence = extraction.get('confidence', 'unknown')
            temporal_events = extraction.get('temporal_diagnostic_events_detected', False)

            logger.info(f"      Primary initial diagnosis: {diagnosis}")
            logger.info(f"      Diagnosis date: {diagnosis_date}")
            logger.info(f"      Source: {source}")
            logger.info(f"      Evidence quality: {quality}")
            logger.info(f"      Confidence: {confidence}")

            if temporal_events:
                num_events = len(extraction.get('temporal_diagnostic_events', []))
                logger.info(f"      ⚠️  Temporal diagnostic events detected: {num_events}")
                for i, event in enumerate(extraction.get('temporal_diagnostic_events', [])[:3], 1):  # Log first 3
                    logger.info(f"         Event {i}: {event.get('event_type', 'unknown')} - {event.get('diagnosis', 'unknown')} ({event.get('date', 'unknown')})")

            # Add raw extraction for audit trail
            extraction['raw_extraction'] = result.raw_response
            extraction['extraction_timestamp'] = datetime.now().isoformat()

            return extraction

        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Phase 0.2 JSON parse error: {e}")
            logger.error(f"      Response preview: {result.raw_response[:500]}")
            return {
                "primary_diagnosis": "Extraction failed: JSON parse error",
                "diagnosis_source": "error",
                "evidence_quality": "error",
                "confidence": "low",
                "error": str(e),
                "raw_response": result.raw_response[:1000]
            }
        except Exception as e:
            logger.error(f"   ❌ Phase 0.2 extraction error: {e}")
            return {
                "primary_diagnosis": "Extraction failed: Exception",
                "diagnosis_source": "error",
                "evidence_quality": "error",
                "confidence": "low",
                "error": str(e)
            }

    def _format_diagnostic_evidence(self, evidence_list: List[Any]) -> str:
        """
        Format Phase 0.1 diagnostic evidence for prompt.

        Args:
            evidence_list: List of DiagnosisEvidence objects

        Returns:
            Formatted string
        """
        if not evidence_list:
            return "No diagnostic evidence collected from Phase 0.1"

        output = []
        output.append(f"Total evidence items: {len(evidence_list)}")
        output.append("")

        for i, evidence in enumerate(evidence_list[:20], 1):  # Limit to top 20
            output.append(f"Evidence #{i}:")
            output.append(f"  Diagnosis: {evidence.diagnosis}")
            output.append(f"  Source: {evidence.source.name}")
            output.append(f"  Confidence: {evidence.confidence:.2f}")
            output.append(f"  Date: {evidence.date.strftime('%Y-%m-%d') if evidence.date else 'Unknown'}")
            output.append(f"  Extraction method: {evidence.extraction_method}")
            output.append("")

        if len(evidence_list) > 20:
            output.append(f"... and {len(evidence_list) - 20} more evidence items")

        return "\n".join(output)

    def _format_pathology_data(self, pathology_data: List[Dict[str, str]]) -> str:
        """
        Format pathology data for extraction prompt.

        Prioritizes genomics_interpretation and final_diagnosis records.
        Limits to avoid excessive context usage.

        Args:
            pathology_data: Raw pathology records

        Returns:
            Formatted string
        """
        if not pathology_data:
            return "No pathology/molecular data available"

        # Prioritize records by category
        priority_categories = [
            'Genomics_Interpretation',
            'Final_Diagnosis',
            'Genomics_Method',
            'Molecular_Results'
        ]

        priority_records = []
        other_records = []

        for record in pathology_data:
            category = record.get('diagnostic_category', '')
            if category in priority_categories:
                priority_records.append(record)
            else:
                other_records.append(record)

        # Take top 10 priority + top 5 other
        selected_records = priority_records[:10] + other_records[:5]

        output = []
        output.append(f"Pathology/Molecular Records ({len(selected_records)} of {len(pathology_data)} shown):")
        output.append("")

        for i, record in enumerate(selected_records, 1):
            output.append(f"[Record {i}]")
            output.append(f"Source: {record.get('diagnostic_source', 'Unknown')}")
            output.append(f"Category: {record.get('diagnostic_category', 'Unknown')}")
            output.append(f"Date: {record.get('diagnostic_date', 'Unknown')}")
            output.append(f"Name: {record.get('diagnostic_name', 'Unknown')}")

            # Include result_value but limit to 1000 chars per record
            result = record.get('result_value', '')
            if result:
                if len(result) > 1000:
                    output.append(f"Result: {result[:1000]}... [truncated]")
                else:
                    output.append(f"Result: {result}")

            output.append("")

        return "\n".join(output)
