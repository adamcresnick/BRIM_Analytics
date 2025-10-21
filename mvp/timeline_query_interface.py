"""
Timeline Query Interface

Purpose: Abstraction layer for querying timeline database and source documents.
         Provides clean API for agent-based extraction workflows.

Design:
- Encapsulates all DuckDB queries
- Returns structured data for agent consumption
- Handles temporal context calculations
- Links timeline events to source documents

Based on: TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md
"""

import duckdb
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json


class TimelineQueryInterface:
    """
    Query interface for timeline database

    Provides methods for:
    - Retrieving events by type, date range, or patient
    - Getting temporal context windows around events
    - Accessing source documents (radiology reports, operative notes)
    - Finding events needing agent extraction
    - Storing extracted variables
    """

    def __init__(self, db_path: str):
        """
        Initialize query interface

        Args:
            db_path: Path to DuckDB timeline database
        """
        self.db_path = db_path
        self._conn = None

    @property
    def conn(self):
        """
        Lazy connection - only connect when needed

        Note: For DuckDB, we create a fresh connection each time to avoid
        lock conflicts when the same database is accessed from multiple
        parts of the code. DuckDB connections are lightweight.
        """
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path, read_only=False)
        return self._conn

    def get_connection(self):
        """
        Get a fresh connection for a single query operation

        This method creates a new connection that should be closed after use.
        Use this for one-off queries to avoid lock conflicts.

        Returns:
            DuckDB connection object
        """
        return duckdb.connect(self.db_path, read_only=False)

    def close(self):
        """Close database connection"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    # ========================================================================
    # EVENT QUERIES
    # ========================================================================

    def get_patient_timeline(self, patient_id: str,
                            event_type: Optional[str] = None,
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Get timeline events for a patient

        Args:
            patient_id: Patient FHIR ID
            event_type: Optional filter by event type ('Imaging', 'Medication', etc.)
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            DataFrame with timeline events
        """
        query = """
        SELECT
            event_id,
            patient_id,
            event_date,
            age_at_event_days,
            age_at_event_years,
            event_type,
            event_category,
            event_subtype,
            description,
            event_status,
            source_view,
            source_domain,
            source_id,
            days_since_diagnosis,
            days_since_surgery,
            days_since_treatment_start,
            disease_phase,
            treatment_status
        FROM events
        WHERE patient_id = ?
        """

        params = [patient_id]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if start_date:
            query += " AND event_date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND event_date <= ?"
            params.append(end_date)

        query += " ORDER BY event_date"

        return self.conn.execute(query, params).fetchdf()

    def get_imaging_events_needing_extraction(self, patient_id: str) -> pd.DataFrame:
        """
        Get imaging events that need agent-based extraction

        Returns imaging events that don't have extracted variables yet.

        Args:
            patient_id: Patient FHIR ID

        Returns:
            DataFrame with imaging events needing extraction:
            - event_id, event_date, description
            - source_event_id (for document lookup)
            - has_report (whether radiology report exists)
        """
        query = """
        SELECT
            e.event_id,
            e.event_date,
            e.age_at_event_days,
            e.description,
            e.source_id,
            e.days_since_diagnosis,
            e.days_since_surgery,
            e.disease_phase,
            e.treatment_status,
            -- Check if radiology report exists
            CASE WHEN sd.document_id IS NOT NULL THEN true ELSE false END as has_report,
            sd.document_id,
            sd.char_count as report_length,
            -- Check if already extracted
            CASE WHEN ev.extraction_id IS NOT NULL THEN true ELSE false END as already_extracted
        FROM events e
        LEFT JOIN source_documents sd
            ON e.event_id = sd.source_event_id
            AND sd.document_type = 'radiology_report'
        LEFT JOIN extracted_variables ev
            ON e.event_id = ev.source_event_id
            AND ev.variable_name IN ('imaging_classification', 'extent_of_resection', 'tumor_status')
        WHERE e.patient_id = ?
        AND e.event_type = 'Imaging'
        AND sd.document_id IS NOT NULL  -- Only imaging with reports
        AND ev.extraction_id IS NULL  -- Not yet extracted
        ORDER BY e.event_date
        """

        return self.conn.execute(query, [patient_id]).fetchdf()

    def get_event_context_window(self, event_id: str,
                                 days_before: int = 30,
                                 days_after: int = 30) -> Dict[str, Any]:
        """
        Get temporal context around a specific event

        Returns events and context information within a time window around
        the specified event.

        Args:
            event_id: Event ID to get context for
            days_before: Number of days before event to include
            days_after: Number of days after event to include

        Returns:
            Dictionary with:
            - target_event: The event being queried
            - context_events: Events in the time window
            - active_medications: Medications active during event
            - recent_procedures: Procedures in prior 90 days
        """
        # Get target event
        target_event = self.conn.execute("""
            SELECT * FROM events WHERE event_id = ?
        """, [event_id]).fetchdf()

        if target_event.empty:
            raise ValueError(f"Event {event_id} not found")

        target_event = target_event.iloc[0]
        event_date = pd.to_datetime(target_event['event_date'])
        patient_id = target_event['patient_id']

        # Get events in context window
        context_events = self.conn.execute("""
            SELECT * FROM events
            WHERE patient_id = ?
            AND event_date BETWEEN ? AND ?
            AND event_id != ?
            ORDER BY event_date
        """, [
            patient_id,
            event_date - timedelta(days=days_before),
            event_date + timedelta(days=days_after),
            event_id
        ]).fetchdf()

        # Get active medications at event date
        active_medications = self.conn.execute("""
            SELECT * FROM events
            WHERE patient_id = ?
            AND event_type = 'Medication'
            AND event_date <= ?
            ORDER BY event_date DESC
            LIMIT 10
        """, [patient_id, event_date]).fetchdf()

        # Get recent procedures (within 90 days before event)
        recent_procedures = self.conn.execute("""
            SELECT * FROM events
            WHERE patient_id = ?
            AND event_type = 'Procedure'
            AND event_date BETWEEN ? AND ?
            ORDER BY event_date DESC
        """, [
            patient_id,
            event_date - timedelta(days=90),
            event_date
        ]).fetchdf()

        return {
            'target_event': target_event.to_dict(),
            'context_events': context_events,
            'active_medications': active_medications,
            'recent_procedures': recent_procedures,
            'patient_id': patient_id,
            'event_date': event_date
        }

    def get_active_treatments_at_date(self, patient_id: str, date: datetime) -> pd.DataFrame:
        """
        Get treatments active at a specific date

        Args:
            patient_id: Patient FHIR ID
            date: Date to check for active treatments

        Returns:
            DataFrame with active medication events
        """
        query = """
        SELECT * FROM events
        WHERE patient_id = ?
        AND event_type = 'Medication'
        AND event_date <= ?
        ORDER BY event_date DESC
        LIMIT 20
        """

        return self.conn.execute(query, [patient_id, date]).fetchdf()

    # ========================================================================
    # DOCUMENT QUERIES
    # ========================================================================

    def get_radiology_report(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get radiology report for an imaging event

        Args:
            event_id: Imaging event ID

        Returns:
            Dictionary with report information:
            - document_id, document_text, char_count
            - metadata (imaging_modality, etc.)
            - None if no report found
        """
        result = self.conn.execute("""
            SELECT
                sd.document_id,
                sd.document_text,
                sd.char_count,
                sd.metadata,
                sd.document_date,
                e.description as imaging_description,
                e.event_date,
                e.days_since_diagnosis,
                e.days_since_surgery,
                e.disease_phase
            FROM source_documents sd
            JOIN events e ON sd.source_event_id = e.event_id
            WHERE sd.source_event_id = ?
            AND sd.document_type = 'radiology_report'
        """, [event_id]).fetchdf()

        if result.empty:
            return None

        row = result.iloc[0]

        # Parse metadata JSON
        metadata = json.loads(row['metadata']) if pd.notna(row['metadata']) else {}

        return {
            'document_id': row['document_id'],
            'document_text': row['document_text'],
            'char_count': int(row['char_count']),
            'metadata': metadata,
            'document_date': row['document_date'],
            'imaging_description': row['imaging_description'],
            'event_date': row['event_date'],
            'days_since_diagnosis': int(row['days_since_diagnosis']) if pd.notna(row['days_since_diagnosis']) else None,
            'days_since_surgery': int(row['days_since_surgery']) if pd.notna(row['days_since_surgery']) else None,
            'disease_phase': row['disease_phase']
        }

    def get_all_radiology_reports(self, patient_id: str) -> pd.DataFrame:
        """
        Get all radiology reports for a patient

        Args:
            patient_id: Patient FHIR ID

        Returns:
            DataFrame with all radiology reports and metadata
        """
        query = """
        SELECT
            sd.document_id,
            sd.document_date,
            sd.char_count,
            sd.source_event_id,
            sd.metadata,
            e.description as imaging_description,
            e.disease_phase,
            e.days_since_diagnosis,
            e.days_since_surgery
        FROM source_documents sd
        LEFT JOIN events e ON sd.source_event_id = e.event_id
        WHERE sd.patient_id = ?
        AND sd.document_type = 'radiology_report'
        ORDER BY sd.document_date DESC
        """

        return self.conn.execute(query, [patient_id]).fetchdf()

    # ========================================================================
    # EXTRACTED VARIABLES - READ
    # ========================================================================

    def get_extracted_variables(self, patient_id: str,
                               variable_name: Optional[str] = None) -> pd.DataFrame:
        """
        Get extracted variables for a patient

        Args:
            patient_id: Patient FHIR ID
            variable_name: Optional filter by variable name

        Returns:
            DataFrame with extracted variables
        """
        query = """
        SELECT * FROM extracted_variables
        WHERE patient_id = ?
        """

        params = [patient_id]

        if variable_name:
            query += " AND variable_name = ?"
            params.append(variable_name)

        query += " ORDER BY event_date DESC"

        return self.conn.execute(query, params).fetchdf()

    def has_extraction(self, event_id: str, variable_name: str) -> bool:
        """
        Check if an event already has an extracted variable

        Args:
            event_id: Event ID
            variable_name: Variable name to check

        Returns:
            True if extraction exists
        """
        result = self.conn.execute("""
            SELECT COUNT(*) as count
            FROM extracted_variables
            WHERE source_event_id = ?
            AND variable_name = ?
        """, [event_id, variable_name]).fetchone()

        return result[0] > 0

    # ========================================================================
    # EXTRACTED VARIABLES - WRITE
    # ========================================================================

    def store_extracted_variable(self,
                                 patient_id: str,
                                 source_event_id: str,
                                 variable_name: str,
                                 variable_value: str,
                                 variable_confidence: float,
                                 extraction_method: str,
                                 source_document_type: Optional[str] = None,
                                 source_text: Optional[str] = None,
                                 model_version: Optional[str] = None,
                                 prompt_version: Optional[str] = None) -> str:
        """
        Store an extracted variable from agent processing

        Args:
            patient_id: Patient FHIR ID
            source_event_id: Event ID this extraction relates to
            variable_name: Name of extracted variable (e.g., 'tumor_status', 'extent_of_resection')
            variable_value: Extracted value
            variable_confidence: Confidence score (0.0-1.0)
            extraction_method: Method used ('medgemma', 'claude', 'manual')
            source_document_type: Type of source document
            source_text: Relevant excerpt from source
            model_version: Model version used for extraction
            prompt_version: Prompt version used

        Returns:
            extraction_id (generated)
        """
        # Generate extraction ID
        extraction_id = f"ext_{variable_name}_{source_event_id}_{int(datetime.now().timestamp())}"

        # Get event date and temporal context from source event
        event_info = self.conn.execute("""
            SELECT event_date, days_since_diagnosis, disease_phase, treatment_status
            FROM events
            WHERE event_id = ?
        """, [source_event_id]).fetchone()

        if not event_info:
            raise ValueError(f"Source event {source_event_id} not found")

        event_date, days_since_diagnosis, disease_phase, treatment_status = event_info

        # Insert extraction
        self.conn.execute("""
            INSERT INTO extracted_variables (
                extraction_id,
                patient_id,
                source_event_id,
                source_document_type,
                source_text,
                variable_name,
                variable_value,
                variable_confidence,
                event_date,
                days_since_diagnosis,
                disease_phase,
                treatment_status,
                extraction_method,
                extraction_timestamp,
                model_version,
                prompt_version,
                validated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            extraction_id,
            patient_id,
            source_event_id,
            source_document_type,
            source_text,
            variable_name,
            variable_value,
            variable_confidence,
            event_date,
            days_since_diagnosis,
            disease_phase,
            treatment_status,
            extraction_method,
            datetime.now(),
            model_version,
            prompt_version,
            False  # validated
        ])

        return extraction_id

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def get_patient_info(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get patient information and milestones

        Args:
            patient_id: Patient FHIR ID

        Returns:
            Dictionary with patient info or None if not found
        """
        result = self.conn.execute("""
            SELECT * FROM patients WHERE patient_id = ?
        """, [patient_id]).fetchdf()

        if result.empty:
            return None

        return result.iloc[0].to_dict()

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the timeline database

        Returns:
            Dictionary with database statistics
        """
        stats = {}

        # Patient count
        stats['patient_count'] = self.conn.execute(
            "SELECT COUNT(*) FROM patients"
        ).fetchone()[0]

        # Event counts by type
        event_counts = self.conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM events
            GROUP BY event_type
            ORDER BY count DESC
        """).fetchdf()
        stats['event_counts'] = event_counts.to_dict('records')

        # Document counts
        doc_counts = self.conn.execute("""
            SELECT document_type, COUNT(*) as count
            FROM source_documents
            GROUP BY document_type
        """).fetchdf()
        stats['document_counts'] = doc_counts.to_dict('records')

        # Extraction counts
        extraction_counts = self.conn.execute("""
            SELECT variable_name, COUNT(*) as count
            FROM extracted_variables
            GROUP BY variable_name
        """).fetchdf()
        stats['extraction_counts'] = extraction_counts.to_dict('records')

        return stats
