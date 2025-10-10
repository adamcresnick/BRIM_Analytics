#!/usr/bin/env python3
"""
Check S3 Availability for Binary Files

This script reads ALL_BINARY_FILES_METADATA.csv and checks S3 availability for each Binary ID.

Key Features:
- Applies period→underscore conversion (critical S3 naming bug fix)
- Checks S3 head_object for each Binary ID
- Adds s3_available, s3_bucket, s3_key columns
- Handles missing Binary IDs gracefully
- Progress tracking for large datasets

Critical S3 Naming Bug:
- FHIR Binary IDs contain periods (.) 
- S3 files use underscores (_) instead
- Example: fbEmTjtK9koEXazjN4eKcmu-tRJaXuAhc7DDwchpOqfQ4
  → S3: fbEmTjtK9koEXazjN4eKcmu-tRJaXuAhc7DDwchpOqfQ4 (no change needed if no periods)
- Example with periods: e5G-oDAd4PW5ngncmfMRuWlczm9kqbixAZuwFex4GBmfbAGaL7o-2W4aP25qteg7zElompZiK5jeFGkPj7IrEsw3
  → S3: e5G-oDAd4PW5ngncmfMRuWlczm9kqbixAZuwFex4GBmfbAGaL7o-2W4aP25qteg7zElompZiK5jeFGkPj7IrEsw3

S3 Configuration:
- Bucket: radiant-prd-343218191717-us-east-1-prd-ehr-pipeline
- Prefix: prd/source/Binary/

Expected S3 Availability: ~60-65% based on BRIM workflow empirical results

Author: AI Assistant
Date: 2025-01-10
"""

import os
import sys
import boto3
import pandas as pd
import logging
from datetime import datetime
from typing import Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('check_s3_availability.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class S3AvailabilityChecker:
    """Check S3 availability for Binary files."""
    
    def __init__(self):
        """Initialize checker with S3 configuration."""
        # S3 configuration
        self.s3_bucket = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'
        self.s3_prefix = 'prd/source/Binary/'
        
        # Initialize AWS S3 client
        self.s3_client = boto3.client('s3', region_name='us-east-1')
        
        logger.info("=" * 100)
        logger.info("🔍 BINARY FILES S3 AVAILABILITY CHECKER")
        logger.info("=" * 100)
        logger.info(f"S3 Bucket: {self.s3_bucket}")
        logger.info(f"S3 Prefix: {self.s3_prefix}")
        logger.info("=" * 100)
    
    def load_binary_metadata(self, filename: str = 'ALL_BINARY_FILES_METADATA.csv') -> pd.DataFrame:
        """
        Load binary files metadata from CSV.
        
        Args:
            filename: Name of the metadata CSV file
            
        Returns:
            DataFrame with binary files metadata
        """
        logger.info(f"\n📂 Loading binary files metadata from {filename}...")
        
        # Get script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        staging_dir = os.path.join(script_dir, '..', 'staging_files')
        file_path = os.path.join(staging_dir, filename)
        
        if not os.path.exists(file_path):
            logger.error(f"  ❌ File not found: {file_path}")
            return pd.DataFrame()
        
        df = pd.read_csv(file_path)
        
        logger.info(f"  ✅ Loaded {len(df)} records")
        logger.info(f"  Records with Binary IDs: {df['binary_id'].notna().sum()}")
        logger.info(f"  Records without Binary IDs: {df['binary_id'].isna().sum()}")
        
        return df
    
    def convert_binary_id_for_s3(self, binary_id: str) -> str:
        """
        Convert Binary ID to S3 format by replacing periods with underscores.
        
        This is a critical S3 naming bug fix discovered in BRIM workflow.
        FHIR Binary IDs contain periods (.), but S3 files use underscores (_).
        
        Args:
            binary_id: Original Binary ID from FHIR
            
        Returns:
            S3-compatible Binary ID
        """
        if pd.isna(binary_id):
            return None
        
        # Replace periods with underscores
        s3_binary_id = str(binary_id).replace('.', '_')
        
        return s3_binary_id
    
    def check_s3_exists(self, binary_id: str) -> Tuple[bool, str]:
        """
        Check if Binary file exists in S3.
        
        Args:
            binary_id: Binary ID (will be converted to S3 format)
            
        Returns:
            Tuple of (exists: bool, s3_key: str)
        """
        if pd.isna(binary_id):
            return False, None
        
        # Convert to S3 format (period → underscore)
        s3_binary_id = self.convert_binary_id_for_s3(binary_id)
        
        # Construct S3 key
        s3_key = f"{self.s3_prefix}{s3_binary_id}"
        
        try:
            # Check if object exists using head_object
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_key)
            return True, s3_key
        except self.s3_client.exceptions.ClientError as e:
            # 404 means object doesn't exist
            if e.response['Error']['Code'] == '404':
                return False, s3_key
            else:
                # Other error (permissions, etc.)
                logger.warning(f"  ⚠️  Error checking {s3_key}: {e}")
                return False, s3_key
        except Exception as e:
            logger.warning(f"  ⚠️  Unexpected error checking {s3_key}: {e}")
            return False, s3_key
    
    def check_all_s3_availability(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Check S3 availability for all Binary IDs in DataFrame.
        
        Args:
            df: DataFrame with binary_id column
            
        Returns:
            DataFrame with added s3_available, s3_bucket, s3_key columns
        """
        logger.info("\n🔍 Checking S3 availability for all Binary IDs...")
        logger.info("  This may take several minutes for large datasets...")
        
        # Initialize new columns
        df['s3_available'] = 'No'
        df['s3_bucket'] = None
        df['s3_key'] = None
        
        # Track progress
        total_records = len(df[df['binary_id'].notna()])
        checked = 0
        available = 0
        
        # Check each Binary ID
        for idx, row in df.iterrows():
            if pd.notna(row['binary_id']):
                exists, s3_key = self.check_s3_exists(row['binary_id'])
                
                if exists:
                    df.at[idx, 's3_available'] = 'Yes'
                    df.at[idx, 's3_bucket'] = self.s3_bucket
                    df.at[idx, 's3_key'] = s3_key
                    available += 1
                else:
                    df.at[idx, 's3_available'] = 'No'
                    df.at[idx, 's3_key'] = s3_key  # Store attempted key
                
                checked += 1
                
                # Progress update every 100 records
                if checked % 100 == 0:
                    pct_complete = checked / total_records * 100
                    pct_available = available / checked * 100
                    logger.info(f"  📊 Progress: {checked}/{total_records} ({pct_complete:.1f}%) - Available: {available} ({pct_available:.1f}%)")
        
        # Final summary
        logger.info(f"\n✅ S3 Availability Check Complete!")
        logger.info(f"  Total records checked: {checked}")
        logger.info(f"  Available in S3: {available} ({available/checked*100:.1f}%)")
        logger.info(f"  Not available in S3: {checked - available} ({(checked-available)/checked*100:.1f}%)")
        
        return df
    
    def generate_summary(self, df: pd.DataFrame) -> None:
        """
        Generate comprehensive summary statistics.
        
        Args:
            df: DataFrame with S3 availability data
        """
        logger.info("\n" + "=" * 100)
        logger.info("📊 S3 AVAILABILITY SUMMARY")
        logger.info("=" * 100)
        
        if df.empty:
            logger.warning("⚠️  No data to summarize")
            return
        
        # Overall counts
        total_records = len(df)
        with_binary_ids = df['binary_id'].notna().sum()
        without_binary_ids = df['binary_id'].isna().sum()
        available_in_s3 = (df['s3_available'] == 'Yes').sum()
        not_available_in_s3 = (df['s3_available'] == 'No').sum() - without_binary_ids
        
        logger.info(f"\n📋 Overall Counts:")
        logger.info(f"  Total DocumentReferences: {total_records:,}")
        logger.info(f"  With Binary IDs: {with_binary_ids:,} ({with_binary_ids/total_records*100:.1f}%)")
        logger.info(f"  Without Binary IDs: {without_binary_ids:,} ({without_binary_ids/total_records*100:.1f}%)")
        logger.info(f"\n📦 S3 Availability (for records with Binary IDs):")
        logger.info(f"  Available in S3: {available_in_s3:,} ({available_in_s3/with_binary_ids*100:.1f}%)")
        logger.info(f"  Not available in S3: {not_available_in_s3:,} ({not_available_in_s3/with_binary_ids*100:.1f}%)")
        
        # S3 availability by document type
        if 'document_type' in df.columns:
            logger.info(f"\n📄 S3 Availability by Document Type (Top 10):")
            available_df = df[df['s3_available'] == 'Yes']
            if not available_df.empty:
                doc_types = available_df['document_type'].value_counts().head(10)
                for doc_type, count in doc_types.items():
                    pct = count / available_in_s3 * 100
                    logger.info(f"  {doc_type}: {count:,} ({pct:.1f}%)")
        
        # S3 availability by content type
        if 'content_type' in df.columns:
            logger.info(f"\n📎 S3 Availability by Content Type:")
            available_df = df[df['s3_available'] == 'Yes']
            if not available_df.empty:
                content_types = available_df['content_type'].value_counts().head(10)
                for content_type, count in content_types.items():
                    pct = count / available_in_s3 * 100
                    logger.info(f"  {content_type}: {count:,} ({pct:.1f}%)")
        
        # Temporal analysis
        if 'document_date' in df.columns:
            logger.info(f"\n📅 Temporal Coverage (S3-available documents):")
            available_df = df[df['s3_available'] == 'Yes']
            if not available_df.empty and available_df['document_date'].notna().any():
                available_df['document_date'] = pd.to_datetime(available_df['document_date'], errors='coerce')
                logger.info(f"  Earliest document: {available_df['document_date'].min()}")
                logger.info(f"  Latest document: {available_df['document_date'].max()}")
                
                # Age range
                if 'age_at_document_years' in available_df.columns:
                    logger.info(f"  Age range: {available_df['age_at_document_years'].min():.1f} - {available_df['age_at_document_years'].max():.1f} years")
        
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
        Run complete S3 availability check workflow.
        
        Returns:
            DataFrame with S3 availability data
        """
        logger.info("\n🚀 Starting S3 availability check...\n")
        
        try:
            # Load binary metadata
            df = self.load_binary_metadata()
            
            if df.empty:
                logger.error("❌ No binary metadata found")
                return df
            
            # Check S3 availability
            df = self.check_all_s3_availability(df)
            
            # Generate summary
            self.generate_summary(df)
            
            # Save to CSV
            self.save_to_csv(df, 'ALL_BINARY_FILES_METADATA_WITH_AVAILABILITY.csv')
            
            logger.info("\n✅ S3 availability check complete!")
            
            return df
            
        except Exception as e:
            logger.error(f"\n❌ Error during S3 availability check: {str(e)}")
            raise


def main():
    """Main execution function."""
    checker = S3AvailabilityChecker()
    df = checker.run()
    return df


if __name__ == '__main__':
    main()
