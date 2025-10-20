"""
Document Text Cache with Full Provenance

Caches extracted text from binary files (PDFs, HTML) to avoid reprocessing.
Stores complete provenance for audit trail and enables re-extraction for new variables.

Design:
- Patient-specific DuckDB table: extracted_document_text
- Stores extracted text + full metadata
- Enables future re-extraction without S3/PDF parsing
- Tracks extraction version for reproducibility

Benefits:
1. Performance: Extract once, use many times
2. Cost: Avoid repeated S3 API calls
3. Provenance: Complete audit trail
4. Flexibility: Re-extract new variables from cached text
5. Versioning: Track extraction method changes over time
"""

import duckdb
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedDocument:
    """Cached document text with full provenance"""
    # Primary identifiers
    document_id: str                    # document_reference_id or diagnostic_report_id
    patient_fhir_id: str
    binary_id: Optional[str]            # For binary files (PDF/HTML)

    # Document metadata
    document_type: str                  # imaging_report, progress_note, operative_report
    document_date: str                  # ISO format
    content_type: str                   # application/pdf, text/html, text/plain
    dr_type_text: Optional[str]         # Document type from FHIR
    dr_category_text: Optional[str]     # Document category from FHIR
    dr_description: Optional[str]       # Document description

    # Extracted text
    extracted_text: str                 # Full extracted text
    text_length: int                    # Character count
    text_hash: str                      # SHA256 hash for deduplication

    # Extraction provenance
    extraction_timestamp: str           # When extracted
    extraction_method: str              # pdf_pymupdf, html_beautifulsoup, text_direct
    extraction_version: str             # Version of extraction code (e.g., "v1.0")
    extractor_agent: str                # binary_file_agent, athena_query

    # S3 provenance (for binary files)
    s3_bucket: Optional[str]
    s3_key: Optional[str]
    s3_last_modified: Optional[str]     # S3 object last modified

    # Processing status
    extraction_success: bool
    extraction_error: Optional[str]

    # Metadata
    age_at_document_days: Optional[int]
    additional_metadata: Optional[str]  # JSON string for extensibility


class DocumentTextCache:
    """
    Manages cached extracted document text with provenance

    Storage: DuckDB table in timeline database
    Benefits: SQL queryable, fast, embedded, no external dependencies
    """

    EXTRACTION_VERSION = "v1.1"  # Increment when extraction logic changes

    def __init__(self, db_path: str = "data/timeline.duckdb"):
        """
        Initialize document text cache

        Args:
            db_path: Path to DuckDB timeline database
        """
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._ensure_schema()
        logger.info(f"DocumentTextCache initialized: {db_path}")

    def _ensure_schema(self):
        """Create extracted_document_text table if not exists"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_document_text (
                -- Primary identifiers
                document_id VARCHAR PRIMARY KEY,
                patient_fhir_id VARCHAR NOT NULL,
                binary_id VARCHAR,

                -- Document metadata
                document_type VARCHAR NOT NULL,
                document_date TIMESTAMP NOT NULL,
                content_type VARCHAR NOT NULL,
                dr_type_text VARCHAR,
                dr_category_text VARCHAR,
                dr_description VARCHAR,

                -- Extracted text
                extracted_text VARCHAR NOT NULL,
                text_length INTEGER NOT NULL,
                text_hash VARCHAR NOT NULL,

                -- Extraction provenance
                extraction_timestamp TIMESTAMP NOT NULL,
                extraction_method VARCHAR NOT NULL,
                extraction_version VARCHAR NOT NULL,
                extractor_agent VARCHAR NOT NULL,

                -- S3 provenance
                s3_bucket VARCHAR,
                s3_key VARCHAR,
                s3_last_modified TIMESTAMP,

                -- Processing status
                extraction_success BOOLEAN NOT NULL,
                extraction_error VARCHAR,

                -- Metadata
                age_at_document_days INTEGER,
                additional_metadata VARCHAR,

                -- Indexes
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_extracted_text_patient
            ON extracted_document_text(patient_fhir_id)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_extracted_text_type
            ON extracted_document_text(document_type, document_date)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_extracted_text_hash
            ON extracted_document_text(text_hash)
        """)

        logger.info("Document text cache schema validated")

    def cache_document(self, doc: CachedDocument) -> bool:
        """
        Cache extracted document text

        Args:
            doc: CachedDocument with text and metadata

        Returns:
            True if cached successfully, False if already exists
        """
        try:
            # Check if document already cached
            existing = self.get_cached_document(doc.document_id)
            if existing:
                logger.info(f"Document already cached: {doc.document_id}")
                return False

            # Insert into cache
            self.conn.execute("""
                INSERT INTO extracted_document_text VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                doc.document_id,
                doc.patient_fhir_id,
                doc.binary_id,
                doc.document_type,
                doc.document_date,
                doc.content_type,
                doc.dr_type_text,
                doc.dr_category_text,
                doc.dr_description,
                doc.extracted_text,
                doc.text_length,
                doc.text_hash,
                doc.extraction_timestamp,
                doc.extraction_method,
                doc.extraction_version,
                doc.extractor_agent,
                doc.s3_bucket,
                doc.s3_key,
                doc.s3_last_modified,
                doc.extraction_success,
                doc.extraction_error,
                doc.age_at_document_days,
                doc.additional_metadata
            ])

            logger.info(f"Cached document: {doc.document_id} ({doc.text_length} chars)")
            return True

        except Exception as e:
            logger.error(f"Error caching document {doc.document_id}: {e}")
            raise

    def get_cached_document(self, document_id: str) -> Optional[CachedDocument]:
        """
        Retrieve cached document by ID

        Args:
            document_id: Document reference ID

        Returns:
            CachedDocument if found, None otherwise
        """
        result = self.conn.execute("""
            SELECT * FROM extracted_document_text
            WHERE document_id = ?
        """, [document_id]).fetchone()

        if not result:
            return None

        return CachedDocument(
            document_id=result[0],
            patient_fhir_id=result[1],
            binary_id=result[2],
            document_type=result[3],
            document_date=result[4],
            content_type=result[5],
            dr_type_text=result[6],
            dr_category_text=result[7],
            dr_description=result[8],
            extracted_text=result[9],
            text_length=result[10],
            text_hash=result[11],
            extraction_timestamp=result[12],
            extraction_method=result[13],
            extraction_version=result[14],
            extractor_agent=result[15],
            s3_bucket=result[16],
            s3_key=result[17],
            s3_last_modified=result[18],
            extraction_success=result[19],
            extraction_error=result[20],
            age_at_document_days=result[21],
            additional_metadata=result[22]
        )

    def get_patient_documents(
        self,
        patient_fhir_id: str,
        document_type: Optional[str] = None,
        successful_only: bool = True
    ) -> List[CachedDocument]:
        """
        Get all cached documents for a patient

        Args:
            patient_fhir_id: Patient FHIR ID
            document_type: Optional filter by type (imaging_report, progress_note, etc)
            successful_only: Only return successfully extracted documents

        Returns:
            List of CachedDocument objects
        """
        query = """
            SELECT * FROM extracted_document_text
            WHERE patient_fhir_id = ?
        """
        params = [patient_fhir_id]

        if document_type:
            query += " AND document_type = ?"
            params.append(document_type)

        if successful_only:
            query += " AND extraction_success = true"

        query += " ORDER BY document_date"

        results = self.conn.execute(query, params).fetchall()

        documents = []
        for row in results:
            documents.append(CachedDocument(
                document_id=row[0],
                patient_fhir_id=row[1],
                binary_id=row[2],
                document_type=row[3],
                document_date=row[4],
                content_type=row[5],
                dr_type_text=row[6],
                dr_category_text=row[7],
                dr_description=row[8],
                extracted_text=row[9],
                text_length=row[10],
                text_hash=row[11],
                extraction_timestamp=row[12],
                extraction_method=row[13],
                extraction_version=row[14],
                extractor_agent=row[15],
                s3_bucket=row[16],
                s3_key=row[17],
                s3_last_modified=row[18],
                extraction_success=row[19],
                extraction_error=row[20],
                age_at_document_days=row[21],
                additional_metadata=row[22]
            ))

        return documents

    def is_cached(self, document_id: str) -> bool:
        """Check if document is already cached"""
        result = self.conn.execute("""
            SELECT COUNT(*) FROM extracted_document_text
            WHERE document_id = ?
        """, [document_id]).fetchone()

        return result[0] > 0

    def get_cache_stats(self, patient_fhir_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache statistics

        Args:
            patient_fhir_id: Optional patient filter

        Returns:
            Dictionary with cache statistics
        """
        where_clause = ""
        params = []

        if patient_fhir_id:
            where_clause = "WHERE patient_fhir_id = ?"
            params = [patient_fhir_id]

        # Total documents
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM extracted_document_text {where_clause}",
            params
        ).fetchone()[0]

        # By document type
        by_type = self.conn.execute(f"""
            SELECT document_type, COUNT(*) as count
            FROM extracted_document_text
            {where_clause}
            GROUP BY document_type
        """, params).fetchall()

        # By content type
        by_content_type = self.conn.execute(f"""
            SELECT content_type, COUNT(*) as count
            FROM extracted_document_text
            {where_clause}
            GROUP BY content_type
        """, params).fetchall()

        # Success rate
        success_rate = self.conn.execute(f"""
            SELECT
                SUM(CASE WHEN extraction_success THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as rate
            FROM extracted_document_text
            {where_clause}
        """, params).fetchone()[0]

        # Total text
        total_chars = self.conn.execute(f"""
            SELECT SUM(text_length) FROM extracted_document_text
            {where_clause}
        """, params).fetchone()[0] or 0

        return {
            'total_documents': total,
            'total_characters': total_chars,
            'success_rate': round(success_rate, 1) if success_rate else 0,
            'by_document_type': {row[0]: row[1] for row in by_type},
            'by_content_type': {row[0]: row[1] for row in by_content_type}
        }

    def export_patient_cache(
        self,
        patient_fhir_id: str,
        output_path: Path
    ):
        """
        Export patient's cached documents to JSON

        Args:
            patient_fhir_id: Patient FHIR ID
            output_path: Output file path
        """
        documents = self.get_patient_documents(patient_fhir_id, successful_only=False)

        export_data = {
            'patient_fhir_id': patient_fhir_id,
            'export_timestamp': datetime.now().isoformat(),
            'document_count': len(documents),
            'documents': [asdict(doc) for doc in documents]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported {len(documents)} documents to {output_path}")

    def close(self):
        """Close database connection"""
        self.conn.close()


def create_cached_document_from_binary_extraction(
    extracted_content,  # ExtractedBinaryContent from BinaryFileAgent
    document_type: str,
    extractor_agent: str = "binary_file_agent"
) -> CachedDocument:
    """
    Create CachedDocument from BinaryFileAgent extraction result

    Args:
        extracted_content: ExtractedBinaryContent object
        document_type: Document type (imaging_report, progress_note, operative_report)
        extractor_agent: Name of extraction agent

    Returns:
        CachedDocument ready for caching
    """
    metadata = extracted_content.metadata

    # Determine extraction method
    if metadata.content_type == "application/pdf":
        extraction_method = "pdf_pymupdf"
    elif metadata.content_type in ["text/html", "text/rtf"]:
        extraction_method = "html_beautifulsoup"
    else:
        extraction_method = "text_direct"

    # Compute text hash for deduplication
    text_hash = hashlib.sha256(
        extracted_content.extracted_text.encode('utf-8')
    ).hexdigest()

    return CachedDocument(
        document_id=metadata.document_reference_id,
        patient_fhir_id=metadata.patient_fhir_id,
        binary_id=metadata.binary_id,
        document_type=document_type,
        document_date=metadata.dr_date or datetime.now().isoformat(),
        content_type=metadata.content_type,
        dr_type_text=metadata.dr_type_text,
        dr_category_text=metadata.dr_category_text,
        dr_description=metadata.dr_description,
        extracted_text=extracted_content.extracted_text,
        text_length=extracted_content.text_length,
        text_hash=text_hash,
        extraction_timestamp=datetime.now().isoformat(),
        extraction_method=extraction_method,
        extraction_version=DocumentTextCache.EXTRACTION_VERSION,
        extractor_agent=extractor_agent,
        s3_bucket=metadata.s3_bucket,
        s3_key=metadata.s3_key,
        s3_last_modified=None,  # Can add if needed
        extraction_success=extracted_content.extraction_success,
        extraction_error=extracted_content.extraction_error,
        age_at_document_days=metadata.age_at_document_days,
        additional_metadata=None
    )


def create_cached_document_from_imaging_text(
    imaging_record: Dict[str, Any],
    document_type: str = "imaging_report"
) -> CachedDocument:
    """
    Create CachedDocument from v_imaging text report

    Args:
        imaging_record: Record from v_imaging (with report_conclusion)
        document_type: Document type

    Returns:
        CachedDocument ready for caching
    """
    report_text = imaging_record.get('report_conclusion', '')

    text_hash = hashlib.sha256(report_text.encode('utf-8')).hexdigest()

    return CachedDocument(
        document_id=imaging_record['diagnostic_report_id'],
        patient_fhir_id=imaging_record['patient_fhir_id'],
        binary_id=None,  # Text reports don't have binary_id
        document_type=document_type,
        document_date=imaging_record.get('imaging_date', datetime.now().isoformat()),
        content_type="text/plain",
        dr_type_text=imaging_record.get('imaging_modality'),
        dr_category_text="imaging",
        dr_description=None,
        extracted_text=report_text,
        text_length=len(report_text),
        text_hash=text_hash,
        extraction_timestamp=datetime.now().isoformat(),
        extraction_method="text_direct",
        extraction_version=DocumentTextCache.EXTRACTION_VERSION,
        extractor_agent="athena_query",
        s3_bucket=None,
        s3_key=None,
        s3_last_modified=None,
        extraction_success=len(report_text) > 0,
        extraction_error=None if len(report_text) > 0 else "Empty report text",
        age_at_document_days=None,
        additional_metadata=None
    )


# CLI for testing
if __name__ == "__main__":
    import sys

    print("Document Text Cache Utility")
    print("=" * 60)
    print()
    print("This utility caches extracted text from PDFs/HTML to avoid")
    print("reprocessing. Full provenance tracked for reproducibility.")
    print()
    print("Usage:")
    print("  from utils.document_text_cache import DocumentTextCache")
    print()
    print("  cache = DocumentTextCache()")
    print("  ")
    print("  # Cache extracted document")
    print("  doc = create_cached_document_from_binary_extraction(extracted)")
    print("  cache.cache_document(doc)")
    print("  ")
    print("  # Retrieve cached documents")
    print("  docs = cache.get_patient_documents('Patient/123')")
    print("  ")
    print("  # Check if already cached")
    print("  if not cache.is_cached(document_id):")
    print("      # Extract and cache")
    print()
    print("Benefits:")
    print("  ✓ Extract once, use many times")
    print("  ✓ No repeated S3/PDF parsing")
    print("  ✓ Complete audit trail")
    print("  ✓ Version tracking")
