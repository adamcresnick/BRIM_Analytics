#!/usr/bin/env python3
"""
Extract Comprehensive Binary Files Metadata

This script extracts ALL DocumentReference records from fhir_v2_prd_db for a specific patient,
including Binary IDs, encounter references, content types, categories, and comprehensive metadata.

Key Features:
- Queries 5 document_reference tables with LEFT JOINs
- Includes encounter reference IDs from document_reference_context_encounter
- Calculates age at document date
- Excludes MRN for privacy
- Does NOT check S3 availability (separate script: check_binary_s3_availability.py)

Adapted from BRIM workflow's comprehensive binary files strategy (originally fhir_v1_prd_db).

Author: AI Assistant
Date: 2025-01-09
"""

import os
import sys
import boto3
import pandas as pd
import logging
from datetime import datetime, timezone
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extract_binary_files.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BinaryFilesExtractor:
    """Extract binary files metadata from FHIR database."""
    
    def __init__(self):
        """Initialize extractor with patient info and AWS clients."""
        # Patient information
        self.patient_mrn = "C1277724"
        self.patient_fhir_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"
        self.birth_date = pd.Timestamp('2005-05-13')
        
        # Database configuration
        self.database = 'fhir_prd_db'
        self.output_bucket = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
        self.work_group = 'primary'
        
        # Initialize AWS clients
        self.athena_client = boto3.client('athena', region_name='us-east-1')
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        
        logger.info("=" * 100)
        logger.info("📄 BINARY FILES METADATA EXTRACTOR")
        logger.info("=" * 100)
        logger.info(f"Patient MRN: {self.patient_mrn}")
        logger.info(f"Patient FHIR ID: {self.patient_fhir_id}")
        logger.info(f"Birth Date: {self.birth_date.date()}")
        logger.info(f"Database: {self.database}")
        logger.info("=" * 100)
    
    def execute_query(self, query: str, description: str) -> pd.DataFrame:
        """
        Execute Athena query and return results as DataFrame with pagination support.
        
        Args:
            query: SQL query to execute
            description: Description of what the query does
            
        Returns:
            DataFrame with query results
        """
        logger.info(f"\n📋 {description}")
        logger.info("  Starting query execution...")
        
        try:
            # Start query execution
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={
                    'OutputLocation': f's3://{self.output_bucket}/athena-results/'
                },
                WorkGroup=self.work_group
            )
            
            query_execution_id = response['QueryExecutionId']
            
            # Wait for query to complete
            while True:
                response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                status = response['QueryExecution']['Status']['State']
                
                if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                    break
            
            if status != 'SUCCEEDED':
                error_msg = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                logger.error(f"  ❌ Query failed: {error_msg}")
                return pd.DataFrame()
            
            # Get results with pagination (MaxResults max is 1000)
            all_rows = []
            columns = None
            next_token = None
            page = 1
            
            while True:
                if next_token:
                    results = self.athena_client.get_query_results(
                        QueryExecutionId=query_execution_id,
                        MaxResults=1000,
                        NextToken=next_token
                    )
                else:
                    results = self.athena_client.get_query_results(
                        QueryExecutionId=query_execution_id,
                        MaxResults=1000
                    )
                
                # Extract column names from first page
                if page == 1:
                    columns = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
                    all_rows.extend(results['ResultSet']['Rows'][1:])  # Skip header
                else:
                    all_rows.extend(results['ResultSet']['Rows'])
                
                # Check if there are more results
                next_token = results.get('NextToken')
                if not next_token:
                    break
                
                page += 1
                if page % 5 == 0:
                    logger.info(f"  📄 Retrieved {len(all_rows)} rows so far (page {page})...")
            
            # Parse results into DataFrame
            if len(all_rows) == 0:
                logger.warning("  ⚠️  No data returned")
                return pd.DataFrame()
            
            # Extract data rows
            data = []
            for row in all_rows:
                data.append([col.get('VarCharValue', None) for col in row['Data']])
            
            df = pd.DataFrame(data, columns=columns)
            
            logger.info(f"  ✅ Returned {len(df)} rows in {response['QueryExecution']['Statistics']['TotalExecutionTimeInMillis']/1000:.1f} seconds")
            
            return df
            
        except Exception as e:
            logger.error(f"  ❌ Query execution failed: {str(e)}")
            return pd.DataFrame()
    
    def extract_binary_files_metadata(self) -> pd.DataFrame:
        """
        Extract all DocumentReference records with comprehensive metadata.
        
        Queries 5 document_reference tables:
        1. document_reference (main table)
        2. document_reference_content (Binary IDs, content types)
        3. document_reference_context_encounter (encounter references)
        4. document_reference_type_coding (type_coding_display)
        5. document_reference_category (category_text)
        
        Returns:
            DataFrame with all binary files metadata
        """
        query = f"""
        SELECT 
            -- Document Reference Info
            dr.id as document_reference_id,
            dr.type_text as document_type,
            dr.date as document_date,
            dr.description,
            dr.status,
            dr.doc_status,
            
            -- Binary Content Info
            dc.content_attachment_url as binary_id,
            dc.content_attachment_content_type as content_type,
            dc.content_attachment_size as content_size_bytes,
            dc.content_attachment_title as content_title,
            dc.content_format_display as content_format,
            
            -- Encounter Reference (USER REQUESTED)
            de.context_encounter_reference as encounter_reference,
            de.context_encounter_display as encounter_display,
            
            -- Type Coding
            dt.type_coding_system as type_coding_system,
            dt.type_coding_code as type_coding_code,
            dt.type_coding_display as type_coding_display,
            
            -- Category
            dcat.category_text,
            
            -- Context Period
            dr.context_period_start,
            dr.context_period_end,
            dr.context_facility_type_text,
            dr.context_practice_setting_text,
            
            -- Authenticator/Custodian
            dr.authenticator_display,
            dr.custodian_display
            
        FROM {self.database}.document_reference dr
        
        -- JOIN for Binary IDs (INNER JOIN - must have Binary ID)
        LEFT JOIN {self.database}.document_reference_content dc
            ON dr.id = dc.document_reference_id
        
        -- JOIN for Encounter References (LEFT JOIN - may not have encounter)
        LEFT JOIN {self.database}.document_reference_context_encounter de
            ON dr.id = de.document_reference_id
        
        -- JOIN for Type Coding (LEFT JOIN - may not have type coding)
        LEFT JOIN {self.database}.document_reference_type_coding dt
            ON dr.id = dt.document_reference_id
        
        -- JOIN for Category (LEFT JOIN - may not have category)
        LEFT JOIN {self.database}.document_reference_category dcat
            ON dr.id = dcat.document_reference_id
        
        WHERE dr.subject_reference = '{self.patient_fhir_id}'
        
        ORDER BY dr.date DESC
        """
        
        return self.execute_query(query, "Extracting all DocumentReferences with metadata")
    
    def calculate_ages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate age at document date.
        
        Args:
            df: DataFrame with document_date column
            
        Returns:
            DataFrame with added age columns
        """
        if df.empty:
            return df
        
        logger.info("\n🎂 Calculating age at document date...")
        
        # Convert document_date to datetime
        df['document_date'] = pd.to_datetime(df['document_date'], errors='coerce')
        
        # Remove timezone info for arithmetic (both should be tz-naive)
        df['document_date_naive'] = df['document_date'].dt.tz_localize(None)
        birth_date_naive = self.birth_date.tz_localize(None) if self.birth_date.tz else self.birth_date
        
        # Calculate age in days and years
        df['age_at_document_days'] = (df['document_date_naive'] - birth_date_naive).dt.days
        df['age_at_document_years'] = df['age_at_document_days'] / 365.25
        
        # Drop temporary column
        df.drop('document_date_naive', axis=1, inplace=True)
        
        # Round age_at_document_years to 1 decimal place
        df['age_at_document_years'] = df['age_at_document_years'].round(1)
        
        logger.info(f"  ✅ Age calculations complete")
        logger.info(f"  Age range: {df['age_at_document_years'].min():.1f} - {df['age_at_document_years'].max():.1f} years")
        
        return df
    
    def clean_binary_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract just the Binary ID from the full URL.
        
        Binary IDs come as: Binary/fbEmTjtK9koEXazjN4eKcmu-tRJaXuAhc7DDwchpOqfQ4
        We want just: fbEmTjtK9koEXazjN4eKcmu-tRJaXuAhc7DDwchpOqfQ4
        
        Args:
            df: DataFrame with binary_id column
            
        Returns:
            DataFrame with cleaned binary_id
        """
        if df.empty or 'binary_id' not in df.columns:
            return df
        
        logger.info("\n🧹 Cleaning Binary IDs...")
        
        # Extract Binary ID after 'Binary/' prefix
        df['binary_id'] = df['binary_id'].str.replace('Binary/', '', regex=False)
        
        logger.info(f"  ✅ Binary IDs cleaned")
        
        return df
    
    def generate_summary(self, df: pd.DataFrame) -> None:
        """
        Generate comprehensive summary statistics.
        
        Args:
            df: DataFrame with all binary files metadata
        """
        logger.info("\n" + "=" * 100)
        logger.info("📊 BINARY FILES METADATA SUMMARY")
        logger.info("=" * 100)
        
        if df.empty:
            logger.warning("⚠️  No data to summarize")
            return
        
        # Overall counts
        logger.info(f"\n📋 Overall Counts:")
        logger.info(f"  Total DocumentReferences: {len(df)}")
        logger.info(f"  DocumentReferences with Binary IDs: {df['binary_id'].notna().sum()}")
        logger.info(f"  DocumentReferences with Encounter References: {df['encounter_reference'].notna().sum()}")
        
        # Document types
        if 'document_type' in df.columns and df['document_type'].notna().any():
            logger.info(f"\n📄 Document Types (Top 10):")
            doc_types = df['document_type'].value_counts().head(10)
            for doc_type, count in doc_types.items():
                pct = count / len(df) * 100
                logger.info(f"  {doc_type}: {count} ({pct:.1f}%)")
        
        # Type coding display
        if 'type_coding_display' in df.columns and df['type_coding_display'].notna().any():
            logger.info(f"\n🏷️  Type Coding Display (Top 10):")
            type_codings = df['type_coding_display'].value_counts().head(10)
            for coding, count in type_codings.items():
                pct = count / len(df) * 100
                logger.info(f"  {coding}: {count} ({pct:.1f}%)")
        
        # Categories
        if 'category_text' in df.columns and df['category_text'].notna().any():
            logger.info(f"\n📂 Categories:")
            categories = df['category_text'].value_counts()
            for category, count in categories.items():
                pct = count / len(df) * 100
                logger.info(f"  {category}: {count} ({pct:.1f}%)")
        
        # Content types
        if 'content_type' in df.columns and df['content_type'].notna().any():
            logger.info(f"\n📎 Content Types:")
            content_types = df['content_type'].value_counts()
            for content_type, count in content_types.items():
                pct = count / len(df) * 100
                logger.info(f"  {content_type}: {count} ({pct:.1f}%)")
        
        # Status
        if 'status' in df.columns and df['status'].notna().any():
            logger.info(f"\n✅ Status:")
            statuses = df['status'].value_counts()
            for status, count in statuses.items():
                pct = count / len(df) * 100
                logger.info(f"  {status}: {count} ({pct:.1f}%)")
        
        # Temporal coverage
        if 'document_date' in df.columns and df['document_date'].notna().any():
            logger.info(f"\n📅 Temporal Coverage:")
            logger.info(f"  Earliest document: {df['document_date'].min()}")
            logger.info(f"  Latest document: {df['document_date'].max()}")
            logger.info(f"  Age range: {df['age_at_document_years'].min():.1f} - {df['age_at_document_years'].max():.1f} years")
        
        # Encounter linkage
        if 'encounter_reference' in df.columns:
            unique_encounters = df['encounter_reference'].nunique()
            logger.info(f"\n🏥 Encounter Linkage:")
            logger.info(f"  Unique encounters: {unique_encounters}")
            logger.info(f"  Documents with encounters: {df['encounter_reference'].notna().sum()} ({df['encounter_reference'].notna().sum() / len(df) * 100:.1f}%)")
        
        logger.info("\n" + "=" * 100)
    
    def save_to_csv(self, df: pd.DataFrame, filename: str) -> None:
        """
        Save DataFrame to CSV file.
        
        Args:
            df: DataFrame to save
            filename: Output filename
        """
        if df.empty:
            logger.warning(f"⚠️  No data to save to {filename}")
            return
        
        logger.info(f"\n💾 Saving to {filename}...")
        
        # Get script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, '..', 'staging_files')
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, filename)
        
        df.to_csv(output_path, index=False)
        
        logger.info(f"  ✅ Saved {len(df)} records to {output_path}")
        logger.info(f"  Columns: {len(df.columns)}")
        logger.info(f"  File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    
    def run(self) -> pd.DataFrame:
        """
        Run complete binary files metadata extraction workflow.
        
        Returns:
            DataFrame with all binary files metadata
        """
        logger.info("\n🚀 Starting binary files metadata extraction...\n")
        
        try:
            # Extract binary files metadata
            df = self.extract_binary_files_metadata()
            
            if df.empty:
                logger.error("❌ No binary files metadata found")
                return df
            
            # Clean Binary IDs
            df = self.clean_binary_id(df)
            
            # Calculate ages
            df = self.calculate_ages(df)
            
            # Generate summary
            self.generate_summary(df)
            
            # Save to CSV
            self.save_to_csv(df, 'ALL_BINARY_FILES_METADATA.csv')
            
            logger.info("\n✅ Binary files metadata extraction complete!")
            
            return df
            
        except Exception as e:
            logger.error(f"\n❌ Error during extraction: {str(e)}")
            raise


def main():
    """Main execution function."""
    extractor = BinaryFilesExtractor()
    df = extractor.run()
    return df


if __name__ == '__main__':
    main()
