#!/usr/bin/env python3
"""
Create Source Documents Table in DuckDB Timeline Database

Purpose: Store full-text source documents (radiology reports, operative notes,
         progress notes) separately from the timeline events table.

Design Rationale:
- Timeline events table: Structured metadata + references to source documents
- Source documents table: Full text content for agent extraction
- Similar to how we wouldn't load binary files into a timeline - we store
  references and load documents on-demand for agent processing

Based on: TIMELINE_STORAGE_AND_QUERY_ARCHITECTURE.md
"""

import duckdb
from datetime import datetime

DUCKDB_PATH = "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/data/timeline.duckdb"

def create_source_documents_table(db_path):
    """
    Create source_documents table for storing full-text clinical documents

    Table design:
    - document_id: Unique identifier (e.g., 'rad_report_<imaging_procedure_id>')
    - patient_id: Links to patients table
    - document_type: 'radiology_report', 'operative_note', 'progress_note', etc.
    - document_date: When the document was created/signed
    - source_event_id: Optional link to timeline event (e.g., imaging event)
    - source_view: Which Athena view this came from (e.g., 'v_imaging')
    - source_id: Original FHIR resource ID
    - document_text: Full text content
    - metadata: JSON with document-specific metadata (e.g., modality, report_status)
    - char_count: Length of document for filtering
    - created_timestamp: When this record was created
    """

    conn = duckdb.connect(db_path)

    # Create source_documents table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS source_documents (
        document_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR NOT NULL,

        -- Document classification
        document_type VARCHAR NOT NULL,  -- 'radiology_report', 'operative_note', 'progress_note'
        document_date TIMESTAMP,

        -- Links to timeline and source systems
        source_event_id VARCHAR,  -- Optional link to events table
        source_view VARCHAR NOT NULL,  -- e.g., 'v_imaging', 'v_procedures_tumor'
        source_domain VARCHAR,  -- FHIR resource type
        source_id VARCHAR,  -- Original FHIR resource ID

        -- Document content
        document_text TEXT NOT NULL,
        char_count INTEGER,

        -- Metadata (JSON)
        -- For radiology reports: {imaging_modality, report_status, imaging_procedure}
        -- For operative notes: {procedure_type, surgeon, procedure_code}
        -- For progress notes: {note_type, provider, specialty}
        metadata JSON,

        -- Provenance
        created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        -- Indexes for efficient querying
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
        FOREIGN KEY (source_event_id) REFERENCES events(event_id)
    )
    """)

    print("✓ Created source_documents table")

    # Create indexes for common queries
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_source_docs_patient
    ON source_documents(patient_id)
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_source_docs_type
    ON source_documents(document_type)
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_source_docs_date
    ON source_documents(document_date)
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_source_docs_event
    ON source_documents(source_event_id)
    """)

    print("✓ Created indexes on source_documents")

    # Show table schema
    schema = conn.execute("DESCRIBE source_documents").fetchdf()
    print("\nSource Documents Table Schema:")
    print(schema.to_string(index=False))

    conn.close()

if __name__ == "__main__":
    print("=" * 80)
    print("CREATE SOURCE DOCUMENTS TABLE")
    print("=" * 80)
    print()

    create_source_documents_table(DUCKDB_PATH)

    print()
    print("=" * 80)
    print("✅ SOURCE DOCUMENTS TABLE CREATED SUCCESSFULLY")
    print("=" * 80)
