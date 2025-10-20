"""
Binary Extraction Interface - Bridges BinaryFileAgent with MasterAgent

This module provides integration between binary file extraction and the
existing MasterAgent extraction pipeline, ensuring consistent metadata
tracking and timeline intersection.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from binary_file_agent import BinaryFileAgent, BinaryFileMetadata, ExtractedBinaryContent

logger = logging.getLogger(__name__)


@dataclass
class BinaryExtractionEvent:
    """
    Unified event structure for binary-sourced documents
    Mirrors the structure used for v_imaging events
    """
    event_id: str  # Uses document_reference_id
    event_type: str  # "binary_imaging_report"
    event_date: Optional[datetime]
    patient_id: str
    document_text: str
    document_description: Optional[str]
    document_category: Optional[str]
    binary_id: str
    content_type: str
    age_at_document_days: Optional[int]
    source_view: str  # "v_binary_files"
    extraction_metadata: Dict


class BinaryExtractionInterface:
    """
    Interface for extracting clinical data from binary files with timeline integration
    """

    def __init__(
        self,
        binary_agent: BinaryFileAgent,
        timeline_interface,
        athena_client
    ):
        """
        Initialize Binary Extraction Interface

        Args:
            binary_agent: BinaryFileAgent instance
            timeline_interface: TimelineQueryInterface instance (DuckDB)
            athena_client: Boto3 Athena client
        """
        self.binary_agent = binary_agent
        self.timeline = timeline_interface
        self.athena_client = athena_client

    def get_binary_imaging_events(
        self,
        patient_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[BinaryExtractionEvent]:
        """
        Get all binary imaging events for a patient, optionally filtered by date

        Args:
            patient_id: Patient FHIR ID
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of BinaryExtractionEvent
        """
        # Query v_binary_files for imaging documents
        metadata_list = self.binary_agent.get_imaging_binary_files(
            self.athena_client,
            patient_id
        )

        logger.info(f"Retrieved {len(metadata_list)} binary imaging files for patient {patient_id}")

        # Convert to extraction events
        events = []
        for metadata in metadata_list:
            # Parse date if available
            event_date = None
            if metadata.dr_date:
                try:
                    event_date = datetime.fromisoformat(metadata.dr_date.replace('Z', '+00:00'))
                except:
                    pass

            # Apply date filters
            if start_date and event_date and event_date < start_date:
                continue
            if end_date and event_date and event_date > end_date:
                continue

            # Create event (without extracting text yet - lazy loading)
            event = BinaryExtractionEvent(
                event_id=metadata.document_reference_id,
                event_type="binary_imaging_report",
                event_date=event_date,
                patient_id=metadata.patient_fhir_id,
                document_text="",  # Will be populated on demand
                document_description=metadata.dr_description,
                document_category=metadata.dr_category_text,
                binary_id=metadata.binary_id,
                content_type=metadata.content_type,
                age_at_document_days=metadata.age_at_document_days,
                source_view="v_binary_files",
                extraction_metadata={
                    "dr_type_text": metadata.dr_type_text,
                    "s3_bucket": metadata.s3_bucket,
                    "s3_key": metadata.s3_key
                }
            )
            events.append(event)

        logger.info(f"Created {len(events)} binary extraction events")
        return events

    def extract_text_for_event(
        self,
        event: BinaryExtractionEvent
    ) -> BinaryExtractionEvent:
        """
        Extract text content for a binary extraction event (on-demand)

        Args:
            event: BinaryExtractionEvent

        Returns:
            Updated event with document_text populated
        """
        if event.document_text:
            # Already extracted
            return event

        # Reconstruct metadata for extraction
        metadata = BinaryFileMetadata(
            binary_id=event.binary_id,
            document_reference_id=event.event_id,
            patient_fhir_id=event.patient_id,
            content_type=event.content_type,
            dr_type_text=event.extraction_metadata.get("dr_type_text"),
            dr_category_text=event.document_category,
            dr_description=event.document_description,
            dr_date=event.event_date.isoformat() if event.event_date else None,
            age_at_document_days=event.age_at_document_days,
            s3_bucket=event.extraction_metadata["s3_bucket"],
            s3_key=event.extraction_metadata["s3_key"]
        )

        # Extract content
        result = self.binary_agent.extract_binary_content(metadata)

        if result.extraction_success:
            event.document_text = result.extracted_text
            logger.info(f"Extracted {result.text_length} chars from {event.event_id}")
        else:
            logger.warning(f"Failed to extract text from {event.event_id}: {result.extraction_error}")
            event.document_text = ""

        return event

    def build_temporal_context_for_binary_event(
        self,
        event: BinaryExtractionEvent,
        window_days: int = 30
    ) -> Dict:
        """
        Build temporal context for a binary event using timeline data

        This queries the timeline database for events around the binary document's date
        to provide context for extraction (e.g., nearby surgeries, other imaging)

        Args:
            event: BinaryExtractionEvent
            window_days: Days before/after to include in context

        Returns:
            Context dictionary with nearby events
        """
        if not event.event_date:
            return {
                "has_temporal_context": False,
                "reason": "No event date available"
            }

        # Query timeline for events in window
        start_date = event.event_date - timedelta(days=window_days)
        end_date = event.event_date + timedelta(days=window_days)

        # Get surgeries in window
        surgeries = self.timeline.query_events_by_type(
            patient_id=event.patient_id,
            event_types=['tumor_surgery'],
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        # Get other imaging in window
        imaging = self.timeline.query_events_by_type(
            patient_id=event.patient_id,
            event_types=['imaging'],
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        )

        # Calculate days from surgeries
        surgery_context = []
        for surgery in surgeries:
            surgery_date = datetime.fromisoformat(surgery['event_date'])
            days_diff = (event.event_date - surgery_date).days

            surgery_context.append({
                "event_id": surgery['event_id'],
                "event_date": surgery['event_date'],
                "days_from_imaging": days_diff,
                "procedure": surgery.get('procedure_code', 'Unknown')
            })

        context = {
            "has_temporal_context": True,
            "event_date": event.event_date.isoformat(),
            "window_days": window_days,
            "surgeries_in_window": surgery_context,
            "num_surgeries": len(surgery_context),
            "num_other_imaging": len([i for i in imaging if i['event_id'] != event.event_id]),
            "closest_surgery_days": min([abs(s['days_from_imaging']) for s in surgery_context]) if surgery_context else None
        }

        return context

    def store_binary_extraction_result(
        self,
        event: BinaryExtractionEvent,
        variable_name: str,
        variable_value: str,
        variable_confidence: float,
        extraction_method: str = "medgemma_27b",
        prompt_version: str = "v1.0"
    ) -> str:
        """
        Store extraction result from binary file in timeline database

        Args:
            event: BinaryExtractionEvent
            variable_name: Name of extracted variable
            variable_value: Value of extracted variable
            variable_confidence: Confidence score
            extraction_method: Method used for extraction
            prompt_version: Version of prompt used

        Returns:
            Variable ID from database
        """
        # Store in extracted_variables table with binary source metadata
        variable_id = self.timeline.store_extracted_variable(
            patient_id=event.patient_id,
            source_event_id=event.event_id,
            variable_name=variable_name,
            variable_value=variable_value,
            variable_confidence=variable_confidence,
            extraction_method=extraction_method,
            source_document_type=f"binary_{event.content_type}",
            source_text=event.document_text[:1000] if event.document_text else None,
            prompt_version=prompt_version
        )

        logger.info(f"Stored {variable_name} from binary {event.event_id}: {variable_id}")
        return variable_id


if __name__ == "__main__":
    """
    Test the Binary Extraction Interface
    """
    import boto3
    import sys
    sys.path.append('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp')

    from database.timeline_query_interface import TimelineQueryInterface

    # Initialize components
    session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
    athena_client = session.client('athena')

    binary_agent = BinaryFileAgent()
    timeline = TimelineQueryInterface(db_path='data/timeline.duckdb')

    interface = BinaryExtractionInterface(
        binary_agent=binary_agent,
        timeline_interface=timeline,
        athena_client=athena_client
    )

    # Test patient
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Get binary imaging events
    print(f"\nQuerying binary imaging events for {patient_id}...")
    events = interface.get_binary_imaging_events(patient_id)

    print(f"\nFound {len(events)} binary imaging events")

    if events:
        # Test extraction on first event
        print(f"\nTesting extraction on: {events[0].event_id}")
        print(f"  Binary ID: {events[0].binary_id}")
        print(f"  Content Type: {events[0].content_type}")
        print(f"  Date: {events[0].event_date}")

        # Extract text
        events[0] = interface.extract_text_for_event(events[0])

        print(f"\n  Extracted text length: {len(events[0].document_text)}")
        print(f"  First 300 chars: {events[0].document_text[:300]}")

        # Get temporal context
        context = interface.build_temporal_context_for_binary_event(events[0])
        print(f"\n  Temporal context:")
        print(f"    Surgeries in window: {context.get('num_surgeries', 0)}")
        print(f"    Closest surgery: {context.get('closest_surgery_days')} days")
