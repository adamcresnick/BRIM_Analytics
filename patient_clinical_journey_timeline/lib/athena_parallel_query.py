#!/usr/bin/env python3
"""
Athena Parallel Query Executor - V5.2

Executes multiple Athena queries in parallel with rate limiting and error handling.
Reduces Phase 1 execution time from 12-60 seconds to ~10-15 seconds per patient.

Usage:
    from lib.athena_parallel_query import AthenaParallelExecutor

    executor = AthenaParallelExecutor(
        aws_profile='radiant-prod',
        database='fhir_prd_db',
        max_concurrent=5
    )

    queries = {
        'pathology': "SELECT * FROM v_pathology_diagnostics WHERE ...",
        'procedures': "SELECT * FROM v_procedures_tumor WHERE ...",
        'chemo': "SELECT * FROM v_chemo_treatment_episodes WHERE ...",
    }

    results = executor.execute_parallel(queries)
    # Returns: {'pathology': [...], 'procedures': [...], 'chemo': [...]}
"""

import boto3
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """
    Result of a single Athena query execution.

    Attributes:
        query_name: Name/identifier for the query
        success: Whether query succeeded
        data: Query result rows (if successful)
        error_message: Error message (if failed)
        execution_time_seconds: Time taken to execute
        query_execution_id: Athena query execution ID
    """
    query_name: str
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    query_execution_id: Optional[str] = None
    row_count: int = 0


class AthenaParallelExecutor:
    """
    Executes multiple Athena queries in parallel with rate limiting.

    Athena supports up to 25 concurrent queries per account by default.
    This executor manages concurrent execution with rate limiting to avoid
    hitting AWS limits.
    """

    def __init__(
        self,
        aws_profile: str,
        database: str,
        aws_region: str = 'us-east-1',
        output_location: Optional[str] = None,
        max_concurrent: int = 5,
        query_timeout_seconds: int = 300
    ):
        """
        Initialize Athena parallel executor.

        Args:
            aws_profile: AWS profile name
            database: Athena database name
            aws_region: AWS region
            output_location: S3 output location (optional, uses account default if None)
            max_concurrent: Maximum concurrent queries (default: 5, AWS limit: 25)
            query_timeout_seconds: Timeout for each query (default: 300s / 5 min)
        """
        self.aws_profile = aws_profile
        self.database = database
        self.aws_region = aws_region
        self.max_concurrent = max_concurrent
        self.query_timeout_seconds = query_timeout_seconds

        # Initialize AWS session and client
        self.session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.athena_client = self.session.client('athena')

        # Determine output location
        if output_location:
            self.output_location = output_location
        else:
            # Use default: s3://radiant-prd-{account_id}-{region}-prd-athena-output/
            sts = self.session.client('sts')
            account_id = sts.get_caller_identity()['Account']
            self.output_location = f's3://radiant-prd-{account_id}-{aws_region}-prd-athena-output/'

        logger.info(f"Initialized AthenaParallelExecutor: database={database}, max_concurrent={max_concurrent}")

    def execute_single(
        self,
        query_name: str,
        query_string: str
    ) -> QueryResult:
        """
        Execute a single Athena query.

        Args:
            query_name: Name/identifier for the query
            query_string: SQL query string

        Returns:
            QueryResult with data or error
        """
        start_time = time.time()

        try:
            # Start query execution
            response = self.athena_client.start_query_execution(
                QueryString=query_string,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )

            query_execution_id = response['QueryExecutionId']
            logger.debug(f"[{query_name}] Started query: {query_execution_id}")

            # Wait for query to complete
            status = self._wait_for_query_completion(query_execution_id, query_name)

            if status != 'SUCCEEDED':
                # Query failed
                execution_details = self.athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                error_message = execution_details['QueryExecution']['Status'].get(
                    'StateChangeReason',
                    f'Query failed with status: {status}'
                )

                execution_time = time.time() - start_time
                logger.warning(f"[{query_name}] Query failed after {execution_time:.2f}s: {error_message}")

                return QueryResult(
                    query_name=query_name,
                    success=False,
                    error_message=error_message,
                    execution_time_seconds=execution_time,
                    query_execution_id=query_execution_id
                )

            # Query succeeded - fetch results
            results = self._fetch_query_results(query_execution_id)
            execution_time = time.time() - start_time

            logger.info(f"[{query_name}] Query succeeded: {len(results)} rows in {execution_time:.2f}s")

            return QueryResult(
                query_name=query_name,
                success=True,
                data=results,
                execution_time_seconds=execution_time,
                query_execution_id=query_execution_id,
                row_count=len(results)
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[{query_name}] Exception after {execution_time:.2f}s: {error_message}")

            return QueryResult(
                query_name=query_name,
                success=False,
                error_message=error_message,
                execution_time_seconds=execution_time
            )

    def _wait_for_query_completion(
        self,
        query_execution_id: str,
        query_name: str
    ) -> str:
        """
        Wait for Athena query to complete.

        Args:
            query_execution_id: Athena query execution ID
            query_name: Name for logging

        Returns:
            Final status ('SUCCEEDED', 'FAILED', 'CANCELLED', or 'TIMED_OUT')
        """
        start_time = time.time()
        poll_interval = 1.0  # Start with 1 second

        while True:
            response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            status = response['QueryExecution']['Status']['State']

            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                return status

            # Check timeout
            if time.time() - start_time > self.query_timeout_seconds:
                logger.warning(f"[{query_name}] Query timeout after {self.query_timeout_seconds}s")
                return 'TIMED_OUT'

            # Exponential backoff for polling (1s -> 2s -> 4s, max 5s)
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 5.0)

    def _fetch_query_results(self, query_execution_id: str) -> List[Dict[str, Any]]:
        """
        Fetch query results from Athena.

        Args:
            query_execution_id: Athena query execution ID

        Returns:
            List of result rows as dictionaries
        """
        results = []
        next_token = None

        while True:
            if next_token:
                response = self.athena_client.get_query_results(
                    QueryExecutionId=query_execution_id,
                    NextToken=next_token
                )
            else:
                response = self.athena_client.get_query_results(
                    QueryExecutionId=query_execution_id
                )

            # Extract column names from first page
            if not results:
                column_info = response['ResultSet']['ResultSetMetadata']['ColumnInfo']
                column_names = [col['Name'] for col in column_info]

                # Skip header row
                rows = response['ResultSet']['Rows'][1:]
            else:
                rows = response['ResultSet']['Rows']

            # Convert rows to dictionaries
            for row in rows:
                row_data = {}
                for i, col_name in enumerate(column_names):
                    if i < len(row['Data']):
                        row_data[col_name] = row['Data'][i].get('VarCharValue', None)
                    else:
                        row_data[col_name] = None
                results.append(row_data)

            # Check for more pages
            next_token = response.get('NextToken')
            if not next_token:
                break

        return results

    def execute_parallel(
        self,
        queries: Dict[str, str],
        on_query_complete: Optional[Callable[[QueryResult], None]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute multiple queries in parallel.

        Args:
            queries: Dict of {query_name: query_string}
            on_query_complete: Optional callback called when each query completes

        Returns:
            Dict of {query_name: result_rows}

        Raises:
            Exception: If any query fails (can be changed to return errors in dict)
        """
        logger.info(f"Executing {len(queries)} queries in parallel (max_concurrent={self.max_concurrent})")

        results_dict = {}
        failed_queries = []

        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            # Submit all queries
            future_to_query = {
                executor.submit(self.execute_single, query_name, query_string): query_name
                for query_name, query_string in queries.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_query):
                query_result = future.result()

                # Call callback if provided
                if on_query_complete:
                    on_query_complete(query_result)

                # Store results
                if query_result.success:
                    results_dict[query_result.query_name] = query_result.data
                else:
                    failed_queries.append(query_result)
                    logger.warning(
                        f"Query '{query_result.query_name}' failed: {query_result.error_message}"
                    )

        # Log summary
        total_time = sum(q.execution_time_seconds for q in [
            future.result() for future in future_to_query
        ])
        avg_time = total_time / len(queries) if queries else 0
        logger.info(
            f"Parallel execution complete: {len(results_dict)}/{len(queries)} succeeded, "
            f"avg time {avg_time:.2f}s per query"
        )

        # Handle failures (option 1: raise exception, option 2: return with empty lists)
        if failed_queries:
            # Option 1: Raise exception for any failure
            error_summary = "; ".join([f"{q.query_name}: {q.error_message}" for q in failed_queries])
            raise Exception(f"{len(failed_queries)} queries failed: {error_summary}")

            # Option 2: Return empty lists for failed queries (comment out raise above, uncomment below)
            # for failed_query in failed_queries:
            #     results_dict[failed_query.query_name] = []

        return results_dict

    def execute_sequential(
        self,
        queries: Dict[str, str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Execute queries sequentially (for comparison/fallback).

        Args:
            queries: Dict of {query_name: query_string}

        Returns:
            Dict of {query_name: result_rows}
        """
        logger.info(f"Executing {len(queries)} queries sequentially")

        results_dict = {}

        for query_name, query_string in queries.items():
            query_result = self.execute_single(query_name, query_string)

            if query_result.success:
                results_dict[query_name] = query_result.data
            else:
                raise Exception(f"Query '{query_name}' failed: {query_result.error_message}")

        return results_dict
