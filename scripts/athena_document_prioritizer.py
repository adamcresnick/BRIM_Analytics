#!/usr/bin/env python3
"""
Athena Document Prioritizer for BRIM Extraction
Queries materialized views to intelligently select high-value clinical documents

Usage:
    python athena_document_prioritizer.py --patient-fhir-id e4BwD8ZYDBccepXcJ.Ilo3w3 --limit 50
"""

import boto3
import pandas as pd
import json
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ClinicalEvent:
    """Represents a key clinical event"""
    event_type: str  # DIAGNOSIS, SURGERY, CHEMOTHERAPY
    event_id: str
    event_date: str
    event_description: str
    event_code: Optional[str]
    priority_weight: int


@dataclass
class PrioritizedDocument:
    """Represents a prioritized clinical document"""
    document_id: str
    type_text: str
    document_date: str
    description: str
    s3_url: str
    file_size: int
    nearest_event_type: str
    days_from_nearest_event: int
    document_type_priority: int
    temporal_relevance_score: int
    composite_priority_score: float


class AthenaQueryEngine:
    """Execute Athena queries against FHIR databases
    
    Uses fhir_v2_prd_db for most queries (condition, procedure, medication, observation)
    Uses fhir_v1_prd_db for document_reference queries (v2 incomplete for documents)
    """
    
    def __init__(
        self, 
        aws_profile: str = '343218191717_AWSAdministratorAccess',
        database: str = 'fhir_v2_prd_db',
        document_database: str = 'fhir_v1_prd_db',
        s3_output_location: str = 's3://aws-athena-query-results-343218191717-us-east-1/'
    ):
        self.session = boto3.Session(profile_name=aws_profile)
        self.athena_client = self.session.client('athena', region_name='us-east-1')
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        self.database = database  # v2 for condition, procedure, medication, observation
        self.document_database = document_database  # v1 for document_reference
        self.s3_output_location = s3_output_location
    
    def execute_query(self, query: str, wait: bool = True) -> str:
        """Execute Athena query and return query execution ID"""
        logger.info(f"Executing Athena query:\n{query[:200]}...")
        
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.s3_output_location}
        )
        
        query_execution_id = response['QueryExecutionId']
        logger.info(f"Query execution ID: {query_execution_id}")
        
        if wait:
            self._wait_for_query(query_execution_id)
        
        return query_execution_id
    
    def _wait_for_query(self, query_execution_id: str, max_wait: int = 60):
        """Wait for query to complete"""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                raise TimeoutError(f"Query {query_execution_id} exceeded {max_wait}s timeout")
            
            response = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            
            status = response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                logger.info(f"Query {query_execution_id} succeeded")
                return
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise RuntimeError(f"Query {query_execution_id} {status}: {reason}")
            
            time.sleep(2)
    
    def get_query_results(self, query_execution_id: str) -> pd.DataFrame:
        """Retrieve query results as DataFrame"""
        results = self.athena_client.get_query_results(
            QueryExecutionId=query_execution_id,
            MaxResults=1000
        )
        
        # Parse column headers
        columns = [col['Label'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
        
        # Parse data rows (skip header row)
        rows = []
        for row in results['ResultSet']['Rows'][1:]:
            rows.append([field.get('VarCharValue', None) for field in row['Data']])
        
        df = pd.DataFrame(rows, columns=columns)
        logger.info(f"Retrieved {len(df)} rows from query {query_execution_id}")
        
        return df
    
    def query_and_fetch(self, query: str) -> pd.DataFrame:
        """Execute query and fetch results"""
        query_id = self.execute_query(query, wait=True)
        return self.get_query_results(query_id)


class ClinicalTimelineBuilder:
    """Build patient clinical timeline from materialized views"""
    
    def __init__(self, athena: AthenaQueryEngine):
        self.athena = athena
    
    def build_timeline(self, patient_fhir_id: str) -> List[ClinicalEvent]:
        """Query patient's clinical events (diagnoses, surgeries, treatments)"""
        
        query = f"""
        -- Diagnosis events
        SELECT 
            'DIAGNOSIS' as event_type,
            c.id as event_id,
            c.onset_date_time as event_date,
            c.code_text as event_description,
            ccc.code_coding_code as event_code,
            100 as priority_weight
        FROM {self.athena.database}.condition c
        LEFT JOIN {self.athena.database}.condition_code_coding ccc ON c.id = ccc.condition_id
        WHERE c.subject_reference = '{patient_fhir_id}'
            AND (
                ccc.code_coding_code LIKE 'C71%'
                OR LOWER(c.code_text) LIKE '%glioma%'
                OR LOWER(c.code_text) LIKE '%astrocytoma%'
                OR LOWER(c.code_text) LIKE '%medulloblastoma%'
                OR LOWER(c.code_text) LIKE '%ependymoma%'
                OR LOWER(c.code_text) LIKE '%craniopharyngioma%'
            )
        
        UNION ALL
        
        -- Surgery events
        SELECT
            'SURGERY' as event_type,
            p.id as event_id,
            p.performed_date_time as event_date,
            p.code_text as event_description,
            pcc.code_coding_code as event_code,
            95 as priority_weight
        FROM {self.athena.database}.procedure p
        LEFT JOIN {self.athena.database}.procedure_code_coding pcc ON p.id = pcc.procedure_id
        WHERE p.subject_reference = '{patient_fhir_id}'
            AND (
                pcc.code_coding_code IN ('61510', '61512', '61518', '61500', '61304', '61305')
                OR LOWER(p.code_text) LIKE '%craniotomy%'
                OR LOWER(p.code_text) LIKE '%resection%'
                OR LOWER(p.code_text) LIKE '%biopsy%'
            )
        
        UNION ALL
        
        -- Chemotherapy starts
        SELECT
            'CHEMOTHERAPY' as event_type,
            mr.id as event_id,
            mr.authored_on as event_date,
            mr.medication_reference_display as event_description,
            NULL as event_code,
            90 as priority_weight
        FROM {self.athena.database}.medication_request mr
        WHERE mr.subject_reference = '{patient_fhir_id}'
            AND mr.intent = 'order'
            AND (
                LOWER(mr.medication_reference_display) LIKE '%temozolomide%'
                OR LOWER(mr.medication_reference_display) LIKE '%vincristine%'
                OR LOWER(mr.medication_reference_display) LIKE '%carboplatin%'
                OR LOWER(mr.medication_reference_display) LIKE '%bevacizumab%'
                OR LOWER(mr.medication_reference_display) LIKE '%lomustine%'
                OR LOWER(mr.medication_reference_display) LIKE '%selumetinib%'
            )
        
        ORDER BY event_date
        """
        
        df = self.athena.query_and_fetch(query)
        
        events = []
        for _, row in df.iterrows():
            events.append(ClinicalEvent(
                event_type=row['event_type'],
                event_id=row['event_id'],
                event_date=row['event_date'],
                event_description=row['event_description'],
                event_code=row['event_code'],
                priority_weight=int(row['priority_weight'])
            ))
        
        logger.info(f"Built timeline with {len(events)} events")
        return events


class DocumentPrioritizer:
    """Prioritize clinical documents using temporal and type-based scoring"""
    
    def __init__(self, athena: AthenaQueryEngine):
        self.athena = athena
    
    def prioritize_documents(
        self, 
        patient_fhir_id: str,
        timeline: List[ClinicalEvent],
        limit: int = 50
    ) -> List[PrioritizedDocument]:
        """
        Query and score documents based on:
        1. Document type relevance (pathology > operative note > progress note)
        2. Temporal proximity to clinical events
        3. Composite priority score
        """
        
        # Build event date list for temporal scoring
        event_dates = [event.event_date for event in timeline if event.event_date]
        
        if not event_dates:
            logger.warning("No clinical events found - using all documents")
            event_dates_str = "'1900-01-01'"
        else:
            event_dates_str = ", ".join([f"CAST('{d}' AS DATE)" for d in event_dates])
        
        query = f"""
        SELECT
            dr.id as document_id,
            dr.type_text,
            dr.date as document_date,
            dr.description,
            drc.content_attachment_url as s3_url,
            drc.content_attachment_size as file_size,
            
            -- Document type priority
            CASE
                WHEN LOWER(dr.type_text) LIKE '%pathology%' THEN 100
                WHEN LOWER(dr.type_text) LIKE '%op note%' THEN 95
                WHEN LOWER(dr.type_text) LIKE '%operative%' THEN 95
                WHEN LOWER(dr.type_text) LIKE '%radiology%' THEN 85
                WHEN LOWER(dr.type_text) LIKE '%mri%' THEN 85
                WHEN LOWER(dr.type_text) LIKE '%ct%' THEN 85
                WHEN LOWER(dr.type_text) LIKE '%oncology%' THEN 90
                WHEN LOWER(dr.type_text) LIKE '%consult%' THEN 80
                WHEN LOWER(dr.type_text) LIKE '%h&p%' THEN 80
                WHEN LOWER(dr.type_text) LIKE '%progress%' THEN 70
                ELSE 50
            END as document_type_priority,
            
            0 as days_from_nearest_event,
            50 as temporal_relevance_score,
            
            -- Composite score (simplified - just use document type priority)
            CAST(
                CASE
                    WHEN LOWER(dr.type_text) LIKE '%pathology%' THEN 100
                    WHEN LOWER(dr.type_text) LIKE '%op note%' THEN 95
                    WHEN LOWER(dr.type_text) LIKE '%operative%' THEN 95
                    WHEN LOWER(dr.type_text) LIKE '%radiology%' THEN 85
                    WHEN LOWER(dr.type_text) LIKE '%mri%' THEN 85
                    WHEN LOWER(dr.type_text) LIKE '%ct%' THEN 85
                    WHEN LOWER(dr.type_text) LIKE '%oncology%' THEN 90
                    WHEN LOWER(dr.type_text) LIKE '%consult%' THEN 80
                    WHEN LOWER(dr.type_text) LIKE '%h&p%' THEN 80
                    WHEN LOWER(dr.type_text) LIKE '%progress%' THEN 70
                    ELSE 50
                END AS DOUBLE
            ) as composite_priority_score,
            
            'UNKNOWN' as nearest_event_type
            
        FROM {self.athena.document_database}.document_reference dr
        LEFT JOIN {self.athena.document_database}.document_reference_content drc 
            ON dr.id = drc.document_reference_id
        WHERE dr.subject_reference = '{patient_fhir_id}'
            AND dr.status = 'current'
            AND (drc.content_attachment_size IS NULL 
                 OR drc.content_attachment_size = '' 
                 OR TRY_CAST(drc.content_attachment_size AS BIGINT) < 10000000)
        ORDER BY composite_priority_score DESC, document_date DESC
        LIMIT {limit}
        """
        
        df = self.athena.query_and_fetch(query)
        
        prioritized_docs = []
        for _, row in df.iterrows():
            prioritized_docs.append(PrioritizedDocument(
                document_id=row['document_id'],
                type_text=row['type_text'],
                document_date=row['document_date'],
                description=row.get('description', ''),
                s3_url=row['s3_url'],
                file_size=int(row['file_size']) if row['file_size'] else 0,
                nearest_event_type=row.get('nearest_event_type', 'UNKNOWN'),
                days_from_nearest_event=int(row['days_from_nearest_event']) if row['days_from_nearest_event'] else 999,
                document_type_priority=int(row['document_type_priority']),
                temporal_relevance_score=int(row['temporal_relevance_score']),
                composite_priority_score=float(row['composite_priority_score'])
            ))
        
        logger.info(f"Prioritized {len(prioritized_docs)} documents")
        return prioritized_docs


class ProcedureDocumentLinker:
    """Find documents linked to procedures via procedure_report references"""
    
    def __init__(self, athena: AthenaQueryEngine):
        self.athena = athena
    
    def find_procedure_linked_documents(self, patient_fhir_id: str) -> pd.DataFrame:
        """Query procedure_report to find operative notes and pathology linked to procedures
        
        Note: procedure_report.report_reference contains document_reference.id directly (not 'DocumentReference/xxx')
        """
        
        query = f"""
        SELECT DISTINCT
            p.id as procedure_id,
            p.performed_date_time as surgery_date,
            p.code_text as procedure_name,
            pcc.code_coding_code as cpt_code,
            pcc.code_coding_display as cpt_display,
            pr.report_reference as document_id,
            dr.type_text as document_type,
            dr.date as document_date,
            drc.content_attachment_url as s3_url
        FROM fhir_v2_prd_db.procedure p
        LEFT JOIN fhir_v2_prd_db.procedure_code_coding pcc ON p.id = pcc.procedure_id
        LEFT JOIN fhir_v2_prd_db.procedure_report pr ON p.id = pr.procedure_id
        LEFT JOIN fhir_v1_prd_db.document_reference dr ON pr.report_reference = dr.id
        LEFT JOIN fhir_v1_prd_db.document_reference_content drc ON dr.id = drc.document_reference_id
        WHERE p.subject_reference = '{patient_fhir_id}'
            AND pr.report_reference IS NOT NULL
            AND dr.status = 'current'
            AND (
                -- Operative notes and pathology reports
                LOWER(dr.type_text) LIKE '%operative%'
                OR LOWER(dr.type_text) LIKE '%operation%'
                OR LOWER(dr.type_text) LIKE '%op note%'
                OR LOWER(dr.type_text) LIKE '%pathology%'
                OR LOWER(dr.type_text) LIKE '%surgical%'
                OR LOWER(dr.type_text) LIKE '%procedure%'
            )
        ORDER BY p.performed_date_time DESC
        """
        
        df = self.athena.query_and_fetch(query)
        logger.info(f"Found {len(df)} procedure-linked documents")
        
        return df


def main():
    parser = argparse.ArgumentParser(
        description='Prioritize clinical documents using Athena materialized views'
    )
    parser.add_argument(
        '--patient-fhir-id',
        required=True,
        help='FHIR Patient ID (e.g., e4BwD8ZYDBccepXcJ.Ilo3w3)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of documents to select (default: 50)'
    )
    parser.add_argument(
        '--output',
        default='prioritized_documents.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--aws-profile',
        default='343218191717_AWSAdministratorAccess',
        help='AWS profile name'
    )
    
    args = parser.parse_args()
    
    # Initialize Athena engine
    logger.info(f"Connecting to Athena with profile: {args.aws_profile}")
    athena = AthenaQueryEngine(aws_profile=args.aws_profile)
    
    # Build clinical timeline
    logger.info(f"Building clinical timeline for patient: {args.patient_fhir_id}")
    timeline_builder = ClinicalTimelineBuilder(athena)
    timeline = timeline_builder.build_timeline(args.patient_fhir_id)
    
    print(f"\n{'='*80}")
    print(f"CLINICAL TIMELINE ({len(timeline)} events)")
    print(f"{'='*80}")
    for event in timeline:
        print(f"  {event.event_date} | {event.event_type:15s} | {event.event_description[:60]}")
    
    # Prioritize documents
    logger.info(f"Prioritizing documents (limit: {args.limit})")
    prioritizer = DocumentPrioritizer(athena)
    prioritized_docs = prioritizer.prioritize_documents(
        args.patient_fhir_id,
        timeline,
        limit=args.limit
    )
    
    print(f"\n{'='*80}")
    print(f"PRIORITIZED DOCUMENTS (top {len(prioritized_docs)})")
    print(f"{'='*80}")
    print(f"{'Score':6s} | {'Type':25s} | {'Date':12s} | {'Days':5s} | {'Doc ID'}")
    print(f"{'-'*80}")
    for doc in prioritized_docs[:20]:  # Show top 20
        print(f"{doc.composite_priority_score:5.1f} | "
              f"{doc.type_text[:25]:25s} | "
              f"{doc.document_date[:10]:12s} | "
              f"{doc.days_from_nearest_event:5d} | "
              f"{doc.document_id[:40]}")
    
    # Find procedure-linked documents
    logger.info("Finding procedure-linked documents")
    linker = ProcedureDocumentLinker(athena)
    linked_docs = linker.find_procedure_linked_documents(args.patient_fhir_id)
    
    print(f"\n{'='*80}")
    print(f"PROCEDURE-LINKED DOCUMENTS ({len(linked_docs)} found)")
    print(f"{'='*80}")
    for _, row in linked_docs.iterrows():
        print(f"  {row['surgery_date'][:10] if pd.notna(row['surgery_date']) else 'Unknown'} | "
              f"{row['procedure_name'][:40]:40s} → "
              f"{row['document_type'][:30]:30s} | "
              f"{row['document_id'][:30]}")
    
    # Save results
    output = {
        'patient_fhir_id': args.patient_fhir_id,
        'timeline': [
            {
                'event_type': e.event_type,
                'event_date': e.event_date,
                'event_description': e.event_description,
                'event_code': e.event_code
            }
            for e in timeline
        ],
        'prioritized_documents': [
            {
                'document_id': d.document_id,
                'type_text': d.type_text,
                'document_date': d.document_date,
                'composite_priority_score': d.composite_priority_score,
                'days_from_nearest_event': d.days_from_nearest_event,
                's3_url': d.s3_url
            }
            for d in prioritized_docs
        ],
        'procedure_linked_documents': linked_docs if isinstance(linked_docs, list) else linked_docs.to_dict('records') if not linked_docs.empty else []
    }
    
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Results saved to {args.output}")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"  Clinical events found: {len(timeline)}")
    print(f"  Documents prioritized: {len(prioritized_docs)}")
    print(f"  Procedure-linked docs: {len(linked_docs)}")
    print(f"  Average priority score: {sum(d.composite_priority_score for d in prioritized_docs)/len(prioritized_docs):.1f}")
    print(f"  Output: {args.output}")


if __name__ == '__main__':
    main()
