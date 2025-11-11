#!/usr/bin/env python3
"""
Data Fingerprint Manager for Cache Invalidation

This module implements comprehensive cache invalidation based on:
1. Infrastructure version (e.g., view schema changes)
2. Data fingerprint (e.g., new patient data arrival, data corrections)
3. Time-based expiry (safety net for stale caches)

Key Features:
- Compute data fingerprint across multiple Athena views for a patient
- Hash based on (record_count + latest_date + key_ids) per view
- Three-tier cache validation: Version + Fingerprint + Age
- Automatic cache invalidation when any tier triggers

Usage:
    from lib.data_fingerprint_manager import DataFingerprintManager

    manager = DataFingerprintManager(
        athena_client=athena_client,
        patient_id='eEJcrpDHtP...',
        aws_profile='radiant-prod'
    )

    # Compute current fingerprint
    fingerprint = manager.compute_fingerprint(
        views=['v_pathology_diagnostics', 'v_procedures_tumor', 'v_chemo_treatment_episodes']
    )

    # Validate cache entry
    is_valid = manager.validate_cache_entry(
        cached_data={
            'fingerprint': '8a3f2b...',
            'cache_version': 'v5.0.2',
            'timestamp': '2025-11-10'
        },
        current_version='v5.0.2',
        max_age_days=30
    )
"""

import hashlib
import json
import logging
import time
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DataFingerprintManager:
    """
    Manages data fingerprinting for cache invalidation across Athena views.
    """

    def __init__(
        self,
        athena_client: Optional[Any] = None,
        patient_id: Optional[str] = None,
        aws_profile: str = 'radiant-prod',
        athena_output_bucket: str = 's3://radiant-prd-343218191717-us-east-1-prd-athena-output/'
    ):
        """
        Initialize DataFingerprintManager.

        Args:
            athena_client: Boto3 Athena client (if None, will create new session)
            patient_id: FHIR patient ID to compute fingerprint for
            aws_profile: AWS profile name for boto3 session
            athena_output_bucket: S3 bucket for Athena query results
        """
        self.patient_id = patient_id
        self.aws_profile = aws_profile
        self.athena_output_bucket = athena_output_bucket

        # Initialize Athena client
        if athena_client:
            self.athena_client = athena_client
        else:
            session = boto3.Session(profile_name=aws_profile, region_name='us-east-1')
            self.athena_client = session.client('athena')

    def _execute_athena_query(self, query: str, database: str = 'fhir_prd_db') -> List[Dict[str, Any]]:
        """
        Execute an Athena query and return results.

        Args:
            query: SQL query string
            database: Athena database name

        Returns:
            List of result rows as dictionaries
        """
        try:
            # Start query execution
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': database},
                ResultConfiguration={'OutputLocation': self.athena_output_bucket}
            )

            query_execution_id = response['QueryExecutionId']

            # Wait for query to complete
            max_attempts = 60  # 60 attempts * 1 second = 1 minute timeout
            attempt = 0

            while attempt < max_attempts:
                status_response = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )

                state = status_response['QueryExecution']['Status']['State']

                if state == 'SUCCEEDED':
                    break
                elif state in ['FAILED', 'CANCELLED']:
                    reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                    logger.error(f"Query {state}: {reason}")
                    return []

                time.sleep(1)
                attempt += 1

            if attempt >= max_attempts:
                logger.error("Query timeout after 60 seconds")
                return []

            # Get query results
            results = self.athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )

            rows = results['ResultSet']['Rows']

            if len(rows) <= 1:
                return []  # No data rows (only header or empty)

            # Parse header and data
            headers = [col['VarCharValue'] for col in rows[0]['Data']]
            data_rows = []

            for row in rows[1:]:
                row_dict = {}
                for i, col in enumerate(row['Data']):
                    row_dict[headers[i]] = col.get('VarCharValue', None)
                data_rows.append(row_dict)

            return data_rows

        except Exception as e:
            logger.error(f"Athena query execution error: {e}")
            return []

    def compute_view_fingerprint(self, view_name: str, patient_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute fingerprint for a single Athena view.

        Args:
            view_name: Name of Athena view (e.g., 'v_pathology_diagnostics')
            patient_id: FHIR patient ID (defaults to self.patient_id)

        Returns:
            Dictionary with fingerprint metadata:
            {
                'view_name': str,
                'record_count': int,
                'latest_date': str,
                'id_checksum': str,
                'computed_at': str
            }
        """
        if not patient_id:
            patient_id = self.patient_id

        if not patient_id:
            logger.error("No patient_id provided for fingerprint computation")
            return {}

        logger.info(f"Computing fingerprint for {view_name} (patient: {patient_id})")

        # Construct query to get record count, latest date, and ID checksum
        # Note: Different views have different date columns and ID columns
        # We'll use a flexible approach that works across views

        query = f"""
        SELECT
            COUNT(*) as record_count,
            MAX(
                COALESCE(
                    diagnostic_date,
                    surgery_date,
                    episode_start_date,
                    treatment_start_date,
                    exam_date,
                    encounter_start_datetime,
                    recorded_date,
                    onset_date_time,
                    effective_date_time,
                    issued_date
                )
            ) as latest_date,
            APPROX_SET(
                COALESCE(
                    diagnostic_id,
                    procedure_id,
                    episode_id,
                    treatment_id,
                    exam_id,
                    encounter_id,
                    observation_id,
                    condition_id,
                    id
                )
            ) as id_set_size
        FROM fhir_prd_db.{view_name}
        WHERE patient_fhir_id = '{patient_id}'
           OR patient_id = '{patient_id}'
           OR subject_reference LIKE '%{patient_id}%'
        """

        results = self._execute_athena_query(query)

        if not results:
            logger.warning(f"No results from {view_name} for patient {patient_id}")
            return {
                'view_name': view_name,
                'record_count': 0,
                'latest_date': None,
                'id_set_size': 0,
                'computed_at': datetime.now().isoformat()
            }

        row = results[0]

        return {
            'view_name': view_name,
            'record_count': int(row.get('record_count', 0)),
            'latest_date': row.get('latest_date'),
            'id_set_size': int(row.get('id_set_size', 0)),
            'computed_at': datetime.now().isoformat()
        }

    def compute_fingerprint(
        self,
        views: List[str],
        patient_id: Optional[str] = None
    ) -> str:
        """
        Compute comprehensive fingerprint across multiple Athena views.

        Args:
            views: List of view names to include in fingerprint
            patient_id: FHIR patient ID (defaults to self.patient_id)

        Returns:
            MD5 hash string representing the data fingerprint
        """
        if not patient_id:
            patient_id = self.patient_id

        logger.info(f"Computing comprehensive fingerprint for patient {patient_id}")
        logger.info(f"  Views: {', '.join(views)}")

        fingerprint_data = {}

        for view_name in views:
            view_fingerprint = self.compute_view_fingerprint(view_name, patient_id)
            fingerprint_data[view_name] = view_fingerprint

        # Compute MD5 hash of the entire fingerprint data structure
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.md5(fingerprint_json.encode()).hexdigest()

        logger.info(f"✅ Fingerprint computed: {fingerprint_hash}")
        logger.info(f"   Based on {len(views)} views")

        # Log summary statistics
        total_records = sum(v['record_count'] for v in fingerprint_data.values())
        logger.info(f"   Total records: {total_records}")

        return fingerprint_hash

    def compute_detailed_fingerprint(
        self,
        views: List[str],
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compute detailed fingerprint with metadata for debugging.

        Args:
            views: List of view names to include in fingerprint
            patient_id: FHIR patient ID (defaults to self.patient_id)

        Returns:
            Dictionary with:
            {
                'fingerprint_hash': str,
                'fingerprint_data': dict,
                'summary': dict
            }
        """
        if not patient_id:
            patient_id = self.patient_id

        fingerprint_data = {}

        for view_name in views:
            view_fingerprint = self.compute_view_fingerprint(view_name, patient_id)
            fingerprint_data[view_name] = view_fingerprint

        # Compute hash
        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint_hash = hashlib.md5(fingerprint_json.encode()).hexdigest()

        # Compute summary statistics
        total_records = sum(v['record_count'] for v in fingerprint_data.values())
        latest_dates = [v['latest_date'] for v in fingerprint_data.values() if v['latest_date']]
        most_recent_date = max(latest_dates) if latest_dates else None

        return {
            'fingerprint_hash': fingerprint_hash,
            'fingerprint_data': fingerprint_data,
            'summary': {
                'total_records': total_records,
                'most_recent_date': most_recent_date,
                'views_included': len(views),
                'computed_at': datetime.now().isoformat()
            }
        }

    def validate_cache_entry(
        self,
        cached_data: Dict[str, Any],
        current_version: str,
        current_fingerprint: Optional[str] = None,
        max_age_days: int = 30
    ) -> Dict[str, Any]:
        """
        Validate cache entry using three-tier validation.

        Tier 1: Infrastructure version check
        Tier 2: Data fingerprint check
        Tier 3: Age-based expiry check

        Args:
            cached_data: Dictionary containing cached entry with keys:
                - 'cache_version': Infrastructure version string
                - 'fingerprint': Data fingerprint hash
                - 'timestamp': ISO format timestamp string
            current_version: Current infrastructure version
            current_fingerprint: Current data fingerprint (optional)
            max_age_days: Maximum cache age in days

        Returns:
            Dictionary with validation results:
            {
                'is_valid': bool,
                'reason': str,
                'details': dict
            }
        """
        cached_version = cached_data.get('cache_version', 'unknown')
        cached_fingerprint = cached_data.get('fingerprint')
        cached_timestamp = cached_data.get('timestamp')

        # TIER 1: Infrastructure version check
        if cached_version != current_version:
            return {
                'is_valid': False,
                'reason': 'infrastructure_version_mismatch',
                'details': {
                    'cached_version': cached_version,
                    'current_version': current_version,
                    'message': 'Infrastructure changed - cache invalidated'
                }
            }

        # TIER 2: Data fingerprint check (if provided)
        if current_fingerprint and cached_fingerprint:
            if cached_fingerprint != current_fingerprint:
                return {
                    'is_valid': False,
                    'reason': 'data_fingerprint_mismatch',
                    'details': {
                        'cached_fingerprint': cached_fingerprint,
                        'current_fingerprint': current_fingerprint,
                        'message': 'Patient data changed - cache invalidated'
                    }
                }

        # TIER 3: Age-based expiry check
        if cached_timestamp:
            try:
                cached_date = datetime.fromisoformat(cached_timestamp)
                age_days = (datetime.now() - cached_date).days

                if age_days > max_age_days:
                    return {
                        'is_valid': False,
                        'reason': 'cache_expired',
                        'details': {
                            'cached_date': cached_timestamp,
                            'age_days': age_days,
                            'max_age_days': max_age_days,
                            'message': f'Cache expired (age: {age_days} days > max: {max_age_days} days)'
                        }
                    }
            except ValueError:
                logger.warning(f"Invalid timestamp format in cached data: {cached_timestamp}")

        # All validation tiers passed
        return {
            'is_valid': True,
            'reason': 'valid',
            'details': {
                'message': 'Cache entry is valid'
            }
        }

    def get_cache_metadata(
        self,
        cache_version: str,
        fingerprint: str,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate standardized cache metadata dictionary.

        Args:
            cache_version: Infrastructure version string
            fingerprint: Data fingerprint hash
            additional_metadata: Optional additional metadata to include

        Returns:
            Dictionary with standardized cache metadata
        """
        metadata = {
            'cache_version': cache_version,
            'fingerprint': fingerprint,
            'timestamp': datetime.now().isoformat(),
            'patient_id': self.patient_id
        }

        if additional_metadata:
            metadata.update(additional_metadata)

        return metadata
