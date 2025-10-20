"""
Master Agent - Orchestrates Multi-Agent Extraction Workflow

This agent coordinates between Claude (planning/orchestration) and MedGemma (medical extraction).
Manages the timeline query interface, extraction task delegation, and provenance tracking.

Architecture:
- Master Agent (Claude Sonnet 4.5) - This class - orchestrates workflow
- Medical Agent (MedGemma 27B) - Extracts from clinical text
- Timeline Interface - Queries DuckDB for events and documents
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from .medgemma_agent import MedGemmaAgent, ExtractionResult
from .extraction_prompts import (
    build_imaging_classification_prompt,
    build_eor_extraction_prompt,
    build_tumor_status_extraction_prompt
)
from timeline_query_interface import TimelineQueryInterface

logger = logging.getLogger(__name__)


class MasterAgent:
    """
    Master orchestration agent for clinical data extraction workflow.

    Responsibilities:
    - Query timeline for events needing extraction
    - Retrieve clinical documents (radiology reports, notes)
    - Build temporal context for medical agent
    - Delegate extraction to MedGemma agent
    - Store results with full provenance tracking
    - Coordinate multi-step extraction workflows
    """

    def __init__(
        self,
        timeline_db_path: str,
        medgemma_agent: Optional[MedGemmaAgent] = None,
        dry_run: bool = False
    ):
        """
        Initialize Master Agent.

        Args:
            timeline_db_path: Path to DuckDB timeline database
            medgemma_agent: Optional MedGemma agent instance (creates default if None)
            dry_run: If True, don't write extractions to database
        """
        self.timeline = TimelineQueryInterface(timeline_db_path)
        self.medgemma = medgemma_agent or MedGemmaAgent()
        self.dry_run = dry_run

        logger.info(f"Master Agent initialized (dry_run={dry_run})")

    def orchestrate_imaging_extraction(
        self,
        patient_id: str,
        extraction_type: str = "all"
    ) -> Dict[str, Any]:
        """
        Orchestrate extraction workflow for imaging events.

        Args:
            patient_id: Patient FHIR ID
            extraction_type: Type of extraction:
                - "imaging_classification": Classify as pre-op/post-op/surveillance
                - "extent_of_resection": Extract EOR from post-op imaging
                - "tumor_status": Extract tumor status from surveillance imaging
                - "all": All of the above

        Returns:
            Summary of extraction results
        """
        logger.info(f"Starting imaging extraction for patient {patient_id}")
        logger.info(f"Extraction type: {extraction_type}")

        summary = {
            "patient_id": patient_id,
            "extraction_type": extraction_type,
            "start_time": datetime.now().isoformat(),
            "imaging_events_processed": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "results": []
        }

        # Step 1: Get imaging events needing extraction
        imaging_events = self.timeline.get_imaging_events_needing_extraction(patient_id)

        if imaging_events.empty:
            logger.info("No imaging events found needing extraction")
            summary["end_time"] = datetime.now().isoformat()
            return summary

        logger.info(f"Found {len(imaging_events)} imaging events to process")
        summary["imaging_events_processed"] = len(imaging_events)

        # Step 2: Process each imaging event
        for idx, event in imaging_events.iterrows():
            event_id = event['event_id']
            imaging_date = event['event_date']

            logger.info(f"Processing imaging event {idx + 1}/{len(imaging_events)}: {event_id}")

            try:
                # Get radiology report
                report = self.timeline.get_radiology_report(event_id)

                if not report:
                    logger.warning(f"No radiology report found for {event_id}")
                    summary["failed_extractions"] += 1
                    summary["results"].append({
                        "event_id": event_id,
                        "success": False,
                        "error": "No radiology report"
                    })
                    continue

                # Get temporal context (events ±30 days)
                context = self.timeline.get_event_context_window(
                    event_id=event_id,
                    days_before=30,
                    days_after=30
                )

                # Determine which extraction(s) to run
                if extraction_type == "all":
                    # Run all three extractions
                    results = self._extract_all_from_imaging(
                        event_id, report, context, patient_id
                    )
                elif extraction_type == "imaging_classification":
                    results = [self._extract_imaging_classification(
                        event_id, report, context, patient_id
                    )]
                elif extraction_type == "extent_of_resection":
                    results = [self._extract_extent_of_resection(
                        event_id, report, context, patient_id
                    )]
                elif extraction_type == "tumor_status":
                    results = [self._extract_tumor_status(
                        event_id, report, context, patient_id
                    )]
                else:
                    raise ValueError(f"Unknown extraction_type: {extraction_type}")

                # Track results
                for result in results:
                    if result['success']:
                        summary["successful_extractions"] += 1
                    else:
                        summary["failed_extractions"] += 1

                    summary["results"].append(result)

            except Exception as e:
                logger.error(f"Error processing {event_id}: {e}", exc_info=True)
                summary["failed_extractions"] += 1
                summary["results"].append({
                    "event_id": event_id,
                    "success": False,
                    "error": str(e)
                })

        summary["end_time"] = datetime.now().isoformat()
        logger.info(f"Imaging extraction complete: "
                   f"{summary['successful_extractions']} successful, "
                   f"{summary['failed_extractions']} failed")

        return summary

    def _extract_all_from_imaging(
        self,
        event_id: str,
        report: Dict[str, Any],
        context: Dict[str, Any],
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """Run all three extraction types on an imaging event"""
        return [
            self._extract_imaging_classification(event_id, report, context, patient_id),
            self._extract_extent_of_resection(event_id, report, context, patient_id),
            self._extract_tumor_status(event_id, report, context, patient_id)
        ]

    def _extract_imaging_classification(
        self,
        event_id: str,
        report: Dict[str, Any],
        context: Dict[str, Any],
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Classify imaging as pre-operative, post-operative, or surveillance.

        Uses temporal context (procedures within ±7 days) and report keywords.
        """
        logger.info(f"Classifying imaging: {event_id}")

        # Build extraction prompt
        prompt = self._build_imaging_classification_prompt(report, context)

        # Call MedGemma
        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are a medical AI assistant specializing in radiology report analysis.",
            expected_schema={
                "required": ["imaging_classification", "confidence", "reasoning"]
            }
        )

        # Store result if successful and not dry_run
        if result.success and not self.dry_run:
            variable_id = self.timeline.store_extracted_variable(
                patient_id=patient_id,
                source_event_id=event_id,
                variable_name="imaging_classification",
                variable_value=result.extracted_data.get('imaging_classification'),
                variable_confidence=result.confidence,
                extraction_method="medgemma_27b",
                source_text=result.raw_response[:1000],
                prompt_version="v1.0"
            )
            logger.info(f"Stored imaging_classification: {variable_id}")

        return {
            "event_id": event_id,
            "extraction_type": "imaging_classification",
            "success": result.success,
            "value": result.extracted_data.get('imaging_classification') if result.success else None,
            "confidence": result.confidence,
            "error": result.error
        }

    def _extract_extent_of_resection(
        self,
        event_id: str,
        report: Dict[str, Any],
        context: Dict[str, Any],
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Extract extent of resection (GTR/STR/Partial/Biopsy) from post-op imaging.

        Only runs if imaging is within 14 days after a tumor surgery procedure.
        """
        logger.info(f"Extracting extent of resection: {event_id}")

        # Check if this is post-operative imaging
        is_postop = self._is_postoperative_imaging(context)

        if not is_postop:
            logger.info(f"Skipping EOR extraction - not post-operative imaging")
            return {
                "event_id": event_id,
                "extraction_type": "extent_of_resection",
                "success": False,
                "value": None,
                "confidence": 0.0,
                "error": "Not post-operative imaging"
            }

        # Build extraction prompt
        prompt = self._build_eor_extraction_prompt(report, context)

        # Call MedGemma
        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are a neurosurgical AI assistant specializing in post-operative MRI interpretation.",
            expected_schema={
                "required": ["extent_of_resection", "confidence", "evidence"]
            }
        )

        # Store result if successful and not dry_run
        if result.success and not self.dry_run:
            variable_id = self.timeline.store_extracted_variable(
                patient_id=patient_id,
                source_event_id=event_id,
                variable_name="extent_of_resection",
                variable_value=result.extracted_data.get('extent_of_resection'),
                variable_confidence=result.confidence,
                extraction_method="medgemma_27b",
                source_text=result.raw_response[:1000],
                prompt_version="v1.0"
            )
            logger.info(f"Stored extent_of_resection: {variable_id}")

        return {
            "event_id": event_id,
            "extraction_type": "extent_of_resection",
            "success": result.success,
            "value": result.extracted_data.get('extent_of_resection') if result.success else None,
            "confidence": result.confidence,
            "error": result.error
        }

    def _extract_tumor_status(
        self,
        event_id: str,
        report: Dict[str, Any],
        context: Dict[str, Any],
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Extract tumor status (NED/Stable/Increased/Decreased/New_Malignancy).

        Requires comparison to prior imaging - uses context to find prior scans.
        """
        logger.info(f"Extracting tumor status: {event_id}")

        # Build extraction prompt with comparison context
        prompt = self._build_tumor_status_extraction_prompt(report, context)

        # Call MedGemma
        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are a neuro-oncology AI assistant specializing in longitudinal tumor assessment.",
            expected_schema={
                "required": ["tumor_status", "confidence", "comparison_findings"]
            }
        )

        # Store result if successful and not dry_run
        if result.success and not self.dry_run:
            variable_id = self.timeline.store_extracted_variable(
                patient_id=patient_id,
                source_event_id=event_id,
                variable_name="tumor_status",
                variable_value=result.extracted_data.get('tumor_status'),
                variable_confidence=result.confidence,
                extraction_method="medgemma_27b",
                source_text=result.raw_response[:1000],
                prompt_version="v1.0"
            )
            logger.info(f"Stored tumor_status: {variable_id}")

        return {
            "event_id": event_id,
            "extraction_type": "tumor_status",
            "success": result.success,
            "value": result.extracted_data.get('tumor_status') if result.success else None,
            "confidence": result.confidence,
            "error": result.error
        }

    # Helper methods for building prompts
    def _build_imaging_classification_prompt(self, report: Dict, context: Dict) -> str:
        """Build prompt for imaging classification extraction"""
        return build_imaging_classification_prompt(report, context)

    def _build_eor_extraction_prompt(self, report: Dict, context: Dict) -> str:
        """Build prompt for extent of resection extraction"""
        return build_eor_extraction_prompt(report, context)

    def _build_tumor_status_extraction_prompt(self, report: Dict, context: Dict) -> str:
        """Build prompt for tumor status extraction"""
        return build_tumor_status_extraction_prompt(report, context)

    def _is_postoperative_imaging(self, context: Dict[str, Any]) -> bool:
        """Check if imaging is within 14 days after tumor surgery"""
        procedures_before = context.get('events_before', [])

        for proc in procedures_before:
            if proc.get('event_type') == 'Procedure':
                # Check if tumor surgery (from event_category or description)
                category = proc.get('event_category', '')
                if 'Tumor Surgery' in category or 'tumor' in category.lower():
                    # Check if within 14 days
                    days_diff = proc.get('days_diff', 999)
                    if abs(days_diff) <= 14:
                        return True

        return False
