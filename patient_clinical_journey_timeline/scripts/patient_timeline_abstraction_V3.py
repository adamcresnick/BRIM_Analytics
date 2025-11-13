#!/usr/bin/env python3
"""
Patient Clinical Journey Timeline Abstraction - VERSION 3 (WITH CARE PLAN VALIDATION)

This script implements the TWO-AGENT ITERATIVE WORKFLOW for patient timeline abstraction:

Claude (this script):
  - Queries 6 Athena views for structured data
  - Loads WHO 2021 molecular classifications (from previous work)
  - Constructs initial timeline from structured data
  - Identifies GAPS requiring binary extraction
  - PRIORITIZES extraction based on clinical significance
  - Validates protocols against WHO 2021 treatment paradigms
  - Generates final patient timeline artifact (JSON)

MedGemma (called when needed):
  - Extracts from binary documents (operative notes, radiation summaries, etc.)
  - Returns structured data to Claude for integration

Architecture:
  - NO SQL VIEWS CREATED (uses existing 6 Athena views)
  - Per-patient iterative workflow
  - Output: JSON artifact per patient

Data Sources:
  1. v_pathology_diagnostics (molecular markers, diagnoses)
  2. v_procedures_tumor (surgeries)
  3. v_chemo_treatment_episodes (chemotherapy episodes)
  4. v_radiation_episode_enrichment (radiation episodes with appointment metadata)
  5. v_imaging (imaging studies with free text report conclusions)
  6. v_visits_unified (clinical visits)

Reference Materials:
  - WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md (existing molecular classifications)
  - WHO 2021 Treatment Guide PDF (protocol validation)
"""

import sys
import os
import argparse
import logging
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import boto3
import time
from typing import Dict, List, Any, Optional, Tuple

# V5.0: Import therapeutic approach abstractor
try:
    from therapeutic_approach_abstractor import build_therapeutic_approach
except ImportError:
    # If import fails, V5.0 will be skipped
    build_therapeutic_approach = None

# V5.0.1: Import protocol knowledge base for binary extraction enhancement
try:
    from protocol_knowledge_base import (
        ALL_PROTOCOLS,
        get_all_signature_agents,
        get_protocol_statistics
    )
    PROTOCOL_KB_AVAILABLE = True
except ImportError:
    PROTOCOL_KB_AVAILABLE = False
    ALL_PROTOCOLS = {}

# Add parent directory to path for agent imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import agents for Phase 4
try:
    from agents import MedGemmaAgent, BinaryFileAgent, ExtractionResult
    AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import agents: {e}")
    AGENTS_AVAILABLE = False

# V4.8: Import chemotherapy date adjudication module
from orchestration.chemotherapy_date_adjudication import adjudicate_chemotherapy_dates, parse_dosage_duration

# V4.1: Import tumor location and institution tracking
try:
    from lib.tumor_location_extractor import TumorLocationExtractor
    from lib.institution_tracker import InstitutionTracker
    V41_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import V4.1 features: {e}")
    V41_FEATURES_AVAILABLE = False

# V4.2: Import tumor measurement and treatment response extractors
try:
    from lib.tumor_measurement_extractor import TumorMeasurementExtractor
    from lib.treatment_response_extractor import TreatmentResponseExtractor
    V42_MEASUREMENT_EXTRACTION_AVAILABLE = True
    V42_RESPONSE_EXTRACTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import V4.2 extractors: {e}")
    V42_MEASUREMENT_EXTRACTION_AVAILABLE = False
    V42_RESPONSE_EXTRACTION_AVAILABLE = False

# Import custom JSON encoder for safe serialization of dataclasses
try:
    from lib.checkpoint_manager import DataclassJSONEncoder, CheckpointManager, Phase
    CHECKPOINT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import checkpoint modules: {e}")
    DataclassJSONEncoder = None  # Fallback to default str encoder
    CheckpointManager = None
    Phase = None
    CHECKPOINT_AVAILABLE = False

# V5.0.3: Import data fingerprint manager for comprehensive cache invalidation
try:
    from lib.data_fingerprint_manager import DataFingerprintManager
    DATA_FINGERPRINT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import data fingerprint manager: {e}")
    DataFingerprintManager = None
    DATA_FINGERPRINT_AVAILABLE = False

# V5.2: Import production optimizations
try:
    from lib.structured_logging import get_logger, StructuredLoggerAdapter
    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import structured logging: {e}")
    get_logger = None
    StructuredLoggerAdapter = None
    STRUCTURED_LOGGING_AVAILABLE = False

try:
    from lib.exception_handling import (
        FatalError, RecoverableError, CompletenessTracker,
        handle_error, ErrorSeverity
    )
    EXCEPTION_HANDLING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import exception handling: {e}")
    FatalError = None
    RecoverableError = None
    CompletenessTracker = None
    handle_error = None
    ErrorSeverity = None
    EXCEPTION_HANDLING_AVAILABLE = False

try:
    from lib.athena_parallel_query import AthenaParallelExecutor, QueryResult
    ATHENA_PARALLEL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import athena parallel query: {e}")
    AthenaParallelExecutor = None
    QueryResult = None
    ATHENA_PARALLEL_AVAILABLE = False

# WHO 2021 CLASSIFICATION CACHE PATH
# Cache file stores all WHO 2021 classifications to avoid expensive re-computation
WHO_2021_CACHE_PATH = Path(__file__).parent.parent / 'data' / 'who_2021_classification_cache.json'

# WHO 2021 CACHE VERSION
# Increment this version whenever v_pathology_diagnostics or underlying data infrastructure changes
# This ensures old cached classifications are invalidated when data quality improves
WHO_2021_CACHE_VERSION = "v5.0.3_data_fingerprinting"  # Updated 2025-11-11: Added comprehensive data fingerprinting for cache invalidation

# WHO 2021 CACHE EXPIRY (days)
# Maximum age for cache entries - safety net for stale caches
WHO_2021_CACHE_MAX_AGE_DAYS = 30

# WHO 2021 DATA FINGERPRINT VIEWS
# List of Athena views to include in data fingerprint computation
WHO_2021_FINGERPRINT_VIEWS = [
    'v_pathology_diagnostics',
    'v_procedures_tumor',
    'v_chemo_treatment_episodes',
    'v_radiation_episode_enrichment',
    'v_imaging'
]

# V3: WHO 2021 CNS TUMOR CLASSIFICATION REFERENCE FILES
# These markdown files contain comprehensive WHO CNS5 classification information for LLM consumption

# WHO 2021 Diagnostic Agent Prompt: Instructions for HOW to analyze episodic data and generate WHO diagnoses
WHO_2021_DIAGNOSTIC_AGENT_PROMPT_PATH = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md")

# WHO 2021 CNS Tumor Classification: Reference knowledge base with classification criteria, treatment protocols, molecular markers
WHO_2021_REFERENCE_PATH = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md")

# WHO 2021 MOLECULAR CLASSIFICATIONS (DEPRECATED - migrated to cache file)
# Source: WHO_2021_INTEGRATED_DIAGNOSES_9_PATIENTS.md
# NOTE: This hardcoded dictionary is kept for backward compatibility only.
# New classifications are loaded from and saved to who_2021_classification_cache.json
# DEPRECATED: Hardcoded WHO_2021_CLASSIFICATIONS dictionary removed in favor of dynamic classification
#
# The system now uses a multi-tier dynamic classification approach:
#   - Tier 1: Structured data from v_pathology_diagnostics
#   - Tier 2: Binary pathology documents if Tier 1 confidence is low/insufficient
#   - Reference: WHO Classification of Tumours of the CNS, 5th Edition (2021) PDF
#
# This ensures classifications are:
#   1. Not patient-specific (applicable to any patient)
#   2. Based on actual available data (structured + binary)
#   3. Referencing authoritative WHO 2021 standards
#   4. Cacheable for performance (see who_2021_classification_cache.json)
#
# Implementation: See _generate_who_classification() method (lines 461-642)
# Enhancement: See _enhance_classification_with_binary_pathology() method (lines 722-892)


class SSOTokenManager:
    """
    V4.6.1: Manages AWS SSO token lifecycle with automatic refresh.

    Prevents long-running processes from crashing due to token expiration.
    """
    def __init__(self, profile_name: str = 'radiant-prod'):
        self.profile_name = profile_name
        self.last_check_time = None
        self.check_interval = 300  # Check every 5 minutes

    def is_token_valid(self) -> bool:
        """Check if current SSO token is valid"""
        try:
            session = boto3.Session(profile_name=self.profile_name)
            sts = session.client('sts')
            sts.get_caller_identity()
            self.last_check_time = time.time()
            return True
        except Exception as e:
            error_str = str(e)
            if 'expired' in error_str.lower() or 'TokenRetrievalError' in error_str:
                logger.warning(f"⚠️  AWS SSO token expired: {e}")
                return False
            else:
                logger.error(f"AWS SSO token validation error: {e}")
                return False

    def refresh_token(self) -> bool:
        """
        Trigger AWS SSO login to refresh token.

        Returns:
            True if refresh successful, False otherwise
        """
        logger.warning("🔄 AWS SSO token expired. Attempting automatic refresh...")
        logger.warning(f"   Running: aws sso login --profile {self.profile_name}")

        try:
            # Trigger SSO login
            result = subprocess.run(
                ['aws', 'sso', 'login', '--profile', self.profile_name],
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout for login
            )

            if result.returncode == 0:
                logger.info("✅ AWS SSO token refreshed successfully")
                self.last_check_time = time.time()
                return True
            else:
                logger.error(f"❌ SSO login failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("❌ SSO login timed out after 60 seconds")
            return False
        except Exception as e:
            logger.error(f"❌ SSO login failed: {e}")
            return False

    def ensure_valid_token(self) -> bool:
        """
        Ensure token is valid, refreshing if necessary.

        Returns:
            True if token is valid (or successfully refreshed), False otherwise
        """
        # Periodic check (every 5 minutes during long-running operations)
        if self.last_check_time and (time.time() - self.last_check_time) < self.check_interval:
            return True  # Assume valid if checked recently

        if self.is_token_valid():
            return True

        # Token invalid - attempt refresh
        return self.refresh_token()

# Global SSO token manager instance
_sso_manager = None

def get_sso_manager(profile_name: str = 'radiant-prod') -> SSOTokenManager:
    """Get global SSO token manager instance"""
    global _sso_manager
    if _sso_manager is None:
        _sso_manager = SSOTokenManager(profile_name)
    return _sso_manager

def check_aws_sso_token(profile_name: str = 'radiant-prod') -> bool:
    """
    Check if AWS SSO token is valid (legacy function for backward compatibility).

    V4.6.1: Now uses SSOTokenManager for better error handling.
    """
    manager = get_sso_manager(profile_name)
    return manager.is_token_valid()


def query_athena(query: str, description: str = None, profile: str = 'radiant-prod', suppress_output: bool = False, investigation_engine = None, schema_loader = None, retry_count: int = 0) -> List[Dict[str, Any]]:
    """Execute Athena query and return results as list of dicts

    Args:
        query: SQL query string
        description: Human-readable description for logging
        profile: AWS profile name
        suppress_output: Whether to suppress console output
        investigation_engine: V4.6: Optional investigation engine for auto-fixing failures
        schema_loader: V4.6: Optional schema loader for investigation
        retry_count: V4.6: Number of retry attempts (prevents infinite loops)

    V4.6.1: Now includes automatic SSO token refresh on expiration.
    """
    if description and not suppress_output:
        print(f"  {description}...", end='', flush=True)

    # V4.6.1: Ensure SSO token is valid before query
    sso_manager = get_sso_manager(profile)
    if not sso_manager.ensure_valid_token():
        error_msg = "AWS SSO token invalid and refresh failed. Run: aws sso login --profile {profile}"
        logger.error(error_msg)
        if description and not suppress_output:
            print(f" ❌ FAILED: {error_msg}")
        raise RuntimeError(error_msg)

    try:
        session = boto3.Session(profile_name=profile)
        client = session.client('athena', region_name='us-east-1')

        response = client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': 'fhir_prd_db'},
            ResultConfiguration={
                'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
            }
        )
    except Exception as e:
        # V4.6.1: Detect token expiration errors and retry once
        error_str = str(e)
        if 'expired' in error_str.lower() or 'TokenRetrievalError' in error_str:
            logger.warning("⚠️  Token expiration detected during query execution. Attempting refresh...")
            if sso_manager.refresh_token():
                logger.info("🔄 Retrying query after token refresh...")
                # Retry with fresh session
                session = boto3.Session(profile_name=profile)
                client = session.client('athena', region_name='us-east-1')
                response = client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': 'fhir_prd_db'},
                    ResultConfiguration={
                        'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
                    }
                )
            else:
                raise
        else:
            raise

    query_id = response['QueryExecutionId']

    # Wait for completion
    while True:
        status_response = client.get_query_execution(QueryExecutionId=query_id)
        status = status_response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            break
        elif status in ['FAILED', 'CANCELLED']:
            reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
            if description and not suppress_output:
                print(f" ❌ FAILED: {reason}")
                logger.error(f"Query failed for '{description}': {reason}")
                # Log the query that failed for debugging
                logger.error(f"Failed query ID: {query_id}")

            # V4.6: AUTOMATIC INVESTIGATION
            if investigation_engine and retry_count < 3:
                logger.info(f"🔍 V4.6: Investigating failure (attempt {retry_count + 1}/3)...")

                try:
                    investigation = investigation_engine.investigate_query_failure(
                        query_id=query_id,
                        query_string=query,
                        error_message=reason
                    )

                    logger.info(f"  Error type: {investigation.get('error_type', 'unknown')}")

                    # Check for auto-fix
                    if 'suggested_fix' in investigation:
                        confidence = investigation.get('fix_confidence', 0.0)
                        logger.info(f"  Fix confidence: {confidence:.1%}")

                        if confidence > 0.9 and retry_count < 2:
                            logger.info(f"  ✅ High confidence - auto-applying fix")
                            # Retry with fixed query
                            return query_athena(
                                query=investigation['suggested_fix'],
                                description=f"{description} (auto-fixed)",
                                profile=profile,
                                suppress_output=suppress_output,
                                investigation_engine=investigation_engine,
                                schema_loader=schema_loader,
                                retry_count=retry_count + 1
                            )
                        else:
                            logger.warning(f"  ⚠️  Medium confidence or max retries - manual review needed")
                            # Save investigation report for manual review
                            import json
                            from pathlib import Path
                            report_dir = Path("/tmp/investigation_reports")
                            report_dir.mkdir(parents=True, exist_ok=True)
                            report_path = report_dir / f"{query_id}.json"
                            with open(report_path, 'w') as f:
                                json.dump(investigation, f, indent=2)
                            logger.info(f"  📋 V4.6: Investigation report saved: {report_path}")
                except Exception as e:
                    logger.warning(f"  ⚠️  Investigation failed: {e}")

            return []
        time.sleep(1)

    # Get results with pagination
    rows = []
    next_token = None
    header = None

    while True:
        if next_token:
            results = client.get_query_results(
                QueryExecutionId=query_id,
                NextToken=next_token,
                MaxResults=1000
            )
        else:
            results = client.get_query_results(
                QueryExecutionId=query_id,
                MaxResults=1000
            )

        # Parse header from first page
        if header is None:
            if len(results['ResultSet']['Rows']) <= 1:
                if description and not suppress_output:
                    print(f" ✅ 0 records")

                # V4.6 BUG FIX #1: Investigation Engine - Trigger on empty results for document lookups
                if investigation_engine and ('DocumentReference' in query or 'Binary' in query or 'v_binary_files' in query):
                    logger.info(f"🔍 V4.6: Investigating empty result set for document query...")
                    try:
                        investigation = investigation_engine.investigate_query_failure(
                            query_id=query_id,
                            query_string=query,
                            error_message="Query succeeded but returned 0 rows (no documents found)"
                        )

                        logger.info(f"  Investigation type: {investigation.get('error_type', 'empty_result_set')}")

                        # Check for suggested alternative query
                        if 'suggested_fix' in investigation:
                            confidence = investigation.get('fix_confidence', 0.0)
                            logger.info(f"  Suggested alternative query (confidence: {confidence:.1%})")

                            # Log suggestion but don't auto-retry on empty results (only on failures)
                            # This prevents infinite loops and gives visibility into why no documents exist
                            if confidence > 0.7:
                                logger.info(f"  💡 Suggestion: {investigation.get('explanation', 'Try alternative document sources')}")

                            # Save investigation report for analysis
                            if hasattr(investigation_engine, 'save_report'):
                                investigation_engine.save_report(query_id, investigation)

                    except Exception as e:
                        logger.debug(f"  Investigation of empty result skipped: {e}")

                return []
            header = [col['VarCharValue'] for col in results['ResultSet']['Rows'][0]['Data']]
            result_rows = results['ResultSet']['Rows'][1:]
        else:
            result_rows = results['ResultSet']['Rows']

        # Parse rows
        for row in result_rows:
            row_dict = {}
            for i, col in enumerate(row['Data']):
                row_dict[header[i]] = col.get('VarCharValue', '')
            rows.append(row_dict)

        # Check for more pages
        next_token = results.get('NextToken')
        if not next_token:
            break

    if description and not suppress_output:
        print(f" ✅ {len(rows)} records")
    return rows


class PatientTimelineAbstractor:
    """
    Implements the TWO-AGENT ITERATIVE workflow for patient timeline abstraction.

    This is NOT a SQL view - it's a per-patient orchestration framework that:
    1. Loads structured data from 6 Athena views
    2. Loads WHO 2021 molecular classification (from previous work)
    3. Constructs initial timeline
    4. Identifies gaps → prioritizes binary extraction
    5. Calls MedGemma for extraction (REAL IMPLEMENTATION IN V2)
    6. Integrates extractions into timeline
    7. Validates protocols against WHO 2021 treatment paradigms
    8. Generates final JSON artifact
    """

    def __init__(self, patient_id: str, output_dir: Path, max_extractions: Optional[int] = None, force_reclassify: bool = False):
        self.patient_id = patient_id
        self.athena_patient_id = patient_id.replace('Patient/', '')
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Max extractions limit for testing
        self.max_extractions = max_extractions
        self.force_reclassify = force_reclassify

        # V4.2+ Enhancement #2: Batch extraction mode
        self.use_batch_extraction = True  # Default to batch mode for efficiency

        # Data structures
        self.timeline_events = []
        self.extraction_gaps = []
        self.binary_extractions = []  # MedGemma results
        self.protocol_validations = []
        self.completeness_assessment = {}  # Phase 4.5 assessment

        # V3 enhancements
        self.patient_demographics = {}  # V3: Patient demographics for age-appropriate protocols
        self.protocol_considerations = []  # V3: Age/syndrome-specific considerations
        self.extraction_tracker = self._init_extraction_tracker()  # V3: Track all data extractions

        # V4.2: Document discovery performance tracking
        self.v2_document_discovery_stats = {}  # V4.2: Track Tier 1 vs Tier 2/3 usage

        # V4.2+ Enhancement #1: Validation tracking
        self.validation_stats = {}  # Track document type validation, extraction validation
        self.failed_extractions = []  # Log failed extractions for review

        # Initialize agents for Phase 4 (BEFORE WHO classification)
        self.medgemma_agent = None
        self.binary_agent = None

        if AGENTS_AVAILABLE and self._verify_medgemma_available():
            try:
                self.medgemma_agent = MedGemmaAgent(model_name="gemma2:27b", temperature=0.1)
                self.binary_agent = BinaryFileAgent(aws_profile="radiant-prod")
                logger.info("✅ MedGemma and BinaryFile agents initialized")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize agents: {e}")
                self.medgemma_agent = None
                self.binary_agent = None
        else:
            logger.warning("⚠️  Phase 4 (binary extraction) will be skipped - Ollama not available")

        # V4.1: Initialize location and institution extractors
        self.location_extractor = None
        self.institution_tracker = None
        if V41_FEATURES_AVAILABLE:
            try:
                self.location_extractor = TumorLocationExtractor()
                self.institution_tracker = InstitutionTracker(primary_institution="Children's Hospital of Philadelphia")
                logger.info("✅ V4.1 features initialized (location + institution tracking)")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize V4.1 features: {e}")
                self.location_extractor = None
                self.institution_tracker = None

        # V4.2: Initialize tumor measurement extractor
        self.measurement_extractor = None
        if V42_MEASUREMENT_EXTRACTION_AVAILABLE and self.medgemma_agent:
            try:
                self.measurement_extractor = TumorMeasurementExtractor(medgemma_agent=self.medgemma_agent)
                logger.info("✅ V4.2 measurement extractor initialized")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize V4.2 measurement extractor: {e}")
                self.measurement_extractor = None

        # V4.2: Initialize treatment response extractor
        self.response_extractor = None
        if V42_RESPONSE_EXTRACTION_AVAILABLE and self.medgemma_agent:
            try:
                self.response_extractor = TreatmentResponseExtractor(medgemma_agent=self.medgemma_agent)
                logger.info("✅ V4.2 treatment response extractor initialized")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize V4.2 response extractor: {e}")
                self.response_extractor = None

        # V4.6: Initialize Active Reasoning Orchestrator components
        self.schema_loader = None
        self.investigation_engine = None  # Initialized later in run() after Athena client setup
        self.who_kb = None

        # Checkpoint manager for phase-level resumption
        self.checkpoint_manager = None
        if CHECKPOINT_AVAILABLE:
            self.checkpoint_manager = CheckpointManager(self.athena_patient_id, str(self.output_dir))
            logger.info("✅ Checkpoint manager initialized")

        # V5.0.3: Data fingerprint manager for cache invalidation
        self.fingerprint_manager = None  # Initialized later in run() after Athena client setup

        # V5.2: Initialize production optimizations
        # Structured logging with patient/phase context
        self.structured_logger = None
        if STRUCTURED_LOGGING_AVAILABLE:
            self.structured_logger = get_logger(
                __name__,
                patient_id=self.athena_patient_id,
                phase='INIT',
                aws_profile='radiant-prod'
            )
            self.structured_logger.info("Initializing PatientTimelineAbstractor with V5.2 features")

        # Completeness tracker for data source extraction tracking
        self.completeness_tracker = None
        if EXCEPTION_HANDLING_AVAILABLE:
            self.completeness_tracker = CompletenessTracker()
            if self.structured_logger:
                self.structured_logger.info("Completeness tracker initialized")
            else:
                logger.info("✅ V5.2: Completeness tracker initialized")

        # Athena parallel query executor for Phase 1 optimization
        self.athena_parallel_executor = None
        if ATHENA_PARALLEL_AVAILABLE:
            try:
                self.athena_parallel_executor = AthenaParallelExecutor(
                    aws_profile='radiant-prod',
                    database='fhir_prd_db',
                    max_concurrent=5,
                    query_timeout_seconds=300
                )
                if self.structured_logger:
                    self.structured_logger.info("Athena parallel executor initialized (max_concurrent=5)")
                else:
                    logger.info("✅ V5.2: Athena parallel executor initialized")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize Athena parallel executor: {e}")
                self.athena_parallel_executor = None

        try:
            from orchestration.schema_loader import AthenaSchemaLoader
            from orchestration.who_cns_knowledge_base import WHOCNSKnowledgeBase

            # Schema awareness
            schema_csv_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv')

            if schema_csv_path.exists():
                self.schema_loader = AthenaSchemaLoader(str(schema_csv_path))
                logger.info("✅ V4.6: Schema loader initialized")

                # WHO CNS knowledge base
                who_ref_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md')
                if who_ref_path.exists():
                    self.who_kb = WHOCNSKnowledgeBase(who_md_path=str(who_ref_path))
                    logger.info("✅ V4.6: WHO CNS knowledge base initialized")
            else:
                logger.warning("⚠️  V4.6: Schema CSV not found, orchestrator features disabled")

        except Exception as e:
            logger.warning(f"⚠️  V4.6: Could not initialize orchestrator components: {e}")

        # Load WHO 2021 classification AFTER agents are initialized (needed for dynamic classification)
        self.who_2021_classification = self._load_who_classification()

        logger.info(f"Initialized abstractor for {patient_id}")
        if self.who_2021_classification.get('who_2021_diagnosis'):
            logger.info(f"  WHO 2021: {self.who_2021_classification['who_2021_diagnosis']}")

    def _load_who_classification(self) -> Dict[str, Any]:
        """
        Load WHO 2021 classification from cache, or generate if not cached.

        Returns:
            Dict with WHO 2021 classification fields
        """
        # Check if cache file exists
        if not WHO_2021_CACHE_PATH.exists():
            logger.warning(f"WHO classification cache not found at {WHO_2021_CACHE_PATH}")
            logger.info("Creating empty cache file (will populate with dynamic classifications)")
            self._initialize_empty_cache()

        # Load cache
        try:
            with open(WHO_2021_CACHE_PATH, 'r') as f:
                cache_data = json.load(f)

            classifications = cache_data.get('classifications', {})

            # Check if patient has cached classification
            if self.athena_patient_id in classifications and not self.force_reclassify:
                cached = classifications[self.athena_patient_id]

                # V5.0.3: Three-tier cache validation
                # Tier 1: Infrastructure version check
                # Tier 2: Data fingerprint check (requires fingerprint manager)
                # Tier 3: Age-based expiry check

                should_use_cache = True
                invalidation_reason = None

                # Compute current fingerprint if fingerprint manager is available
                current_fingerprint = None
                if DATA_FINGERPRINT_AVAILABLE and self.fingerprint_manager:
                    try:
                        current_fingerprint = self.fingerprint_manager.compute_fingerprint(
                            views=WHO_2021_FINGERPRINT_VIEWS,
                            patient_id=self.athena_patient_id
                        )
                        logger.info(f"📊 Computed data fingerprint: {current_fingerprint}")
                    except Exception as e:
                        logger.warning(f"⚠️  Could not compute data fingerprint: {e}")
                        current_fingerprint = None

                # Validate cache entry using three-tier system
                if DATA_FINGERPRINT_AVAILABLE and self.fingerprint_manager:
                    validation_result = self.fingerprint_manager.validate_cache_entry(
                        cached_data=cached,
                        current_version=WHO_2021_CACHE_VERSION,
                        current_fingerprint=current_fingerprint,
                        max_age_days=WHO_2021_CACHE_MAX_AGE_DAYS
                    )

                    should_use_cache = validation_result['is_valid']
                    invalidation_reason = validation_result['reason']

                    if not should_use_cache:
                        logger.warning(f"⚠️  Cache invalidation triggered for {self.athena_patient_id}")
                        logger.warning(f"   Reason: {invalidation_reason}")
                        for key, value in validation_result['details'].items():
                            logger.warning(f"   {key}: {value}")
                else:
                    # Fallback: Basic version check only
                    cached_version = cached.get('cache_version', 'unknown')
                    if cached_version != WHO_2021_CACHE_VERSION:
                        should_use_cache = False
                        invalidation_reason = 'infrastructure_version_mismatch'
                        logger.warning(f"⚠️  Cache version mismatch for {self.athena_patient_id}")
                        logger.warning(f"   Cached version: {cached_version}")
                        logger.warning(f"   Current version: {WHO_2021_CACHE_VERSION}")
                        logger.warning(f"   Data infrastructure changed - regenerating WHO classification")

                if should_use_cache:
                    logger.info(f"✅ Loaded WHO classification from cache for {self.athena_patient_id}")
                    logger.info(f"   Diagnosis: {cached.get('who_2021_diagnosis', 'Unknown')}")
                    logger.info(f"   Classification date: {cached.get('classification_date', 'Unknown')}")
                    logger.info(f"   Method: {cached.get('classification_method', 'Unknown')}")
                    logger.info(f"   Cache version: {cached.get('cache_version', 'Unknown')}")
                    if current_fingerprint:
                        logger.info(f"   Data fingerprint: {current_fingerprint}")
                    return cached
                # Otherwise fall through to generate new classification

            # Need to generate classification
            if self.force_reclassify:
                logger.info(f"🔄 --force-reclassify flag set, regenerating WHO classification for {self.athena_patient_id}")
            else:
                logger.info(f"⚠️  No cached WHO classification found for {self.athena_patient_id}")
                logger.info("   Will attempt to generate classification from pathology data")

            # Generate new classification
            new_classification = self._generate_who_classification()

            # Save to cache
            self._save_who_classification(new_classification)

            return new_classification

        except Exception as e:
            logger.error(f"Error loading WHO classification cache: {e}")
            logger.error("   Cannot generate classification, returning empty result")
            return {
                "who_2021_diagnosis": f"Classification failed: {str(e)}",
                "molecular_subtype": "Unknown",
                "grade": None,
                "key_markers": "Error loading cache",
                "clinical_significance": "Cache error",
                "expected_prognosis": "Cannot determine",
                "recommended_protocols": {},
                "classification_date": datetime.now().strftime('%Y-%m-%d'),
                "classification_method": "failed_cache_error"
            }

    def _initialize_empty_cache(self):
        """Initialize empty cache file for dynamic WHO 2021 classifications"""
        cache_data = {
            "_metadata": {
                "description": "WHO 2021 CNS Tumor Classification Cache for RADIANT PCA",
                "schema_version": "2.0",
                "last_updated": datetime.now().strftime('%Y-%m-%d'),
                "source": "Dynamic multi-tier classification (Tier 1: structured data, Tier 2: binary pathology)",
                "workflow_prompt": "WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md",
                "reference_document": "/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO_2021s.pdf",
                "notes": "Classifications are dynamically generated from available data and cached for performance. Use --force-reclassify flag to regenerate."
            },
            "classifications": {}
        }

        # Ensure cache directory exists
        WHO_2021_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Write empty cache file
        with open(WHO_2021_CACHE_PATH, 'w') as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"✅ Initialized empty WHO classification cache (will populate dynamically)")

    def _save_who_classification(self, classification: Dict[str, Any]):
        """
        Save WHO 2021 classification to cache

        Args:
            classification: WHO classification dict to save
        """
        try:
            # Load existing cache
            if WHO_2021_CACHE_PATH.exists():
                with open(WHO_2021_CACHE_PATH, 'r') as f:
                    cache_data = json.load(f)
            else:
                # Create new cache structure
                cache_data = {
                    "_metadata": {
                        "description": "WHO 2021 CNS Tumor Classification Cache for RADIANT PCA",
                        "schema_version": "1.0",
                        "last_updated": datetime.now().strftime('%Y-%m-%d'),
                        "workflow_prompt": "WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md"
                    },
                    "classifications": {}
                }

            # V5.0.3: Compute and store data fingerprint along with classification
            current_fingerprint = None
            if DATA_FINGERPRINT_AVAILABLE and self.fingerprint_manager:
                try:
                    current_fingerprint = self.fingerprint_manager.compute_fingerprint(
                        views=WHO_2021_FINGERPRINT_VIEWS,
                        patient_id=self.athena_patient_id
                    )
                    logger.info(f"📊 Computed data fingerprint for cache: {current_fingerprint}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not compute data fingerprint: {e}")

            # Update classification with cache metadata
            classification['cache_version'] = WHO_2021_CACHE_VERSION  # Tag with current cache version
            classification['fingerprint'] = current_fingerprint  # Tag with data fingerprint
            classification['timestamp'] = datetime.now().isoformat()  # Tag with timestamp
            cache_data["classifications"][self.athena_patient_id] = classification
            cache_data["_metadata"]["last_updated"] = datetime.now().strftime('%Y-%m-%d')
            cache_data["_metadata"]["cache_version"] = WHO_2021_CACHE_VERSION

            # Ensure cache directory exists
            WHO_2021_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Write updated cache
            with open(WHO_2021_CACHE_PATH, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"✅ Saved WHO classification to cache for {self.athena_patient_id}")

        except Exception as e:
            logger.error(f"Error saving WHO classification to cache: {e}")

    def _generate_who_classification(self) -> Dict[str, Any]:
        """
        Generate WHO 2021 classification using TWO-STAGE MedGemma workflow:

        STAGE 1: Extract molecular findings and diagnoses from structured data
          - Simple extraction task: pull molecular markers, histology, problem list diagnoses
          - Focus on: genomics results, IHC markers, pathology free-text diagnoses
          - Output: Structured list of findings

        STAGE 2: Map extracted findings to WHO 2021 classification
          - Focused mapping task: apply WHO CNS5 criteria to extracted findings
          - Use WHO reference for diagnostic logic
          - Output: WHO 2021 diagnosis

        This two-stage approach is more effective than single 45K char prompt.

        Returns:
            Dict with WHO 2021 classification fields
        """
        logger.info(f"Generating WHO 2021 classification for {self.athena_patient_id}")

        # Check if MedGemma agent is available
        if not self.medgemma_agent:
            logger.warning("⚠️  MedGemma agent not available, cannot generate WHO classification")
            return {
                "who_2021_diagnosis": "Classification not available (MedGemma not initialized)",
                "molecular_subtype": "Unknown",
                "grade": None,
                "key_markers": "Cannot generate without MedGemma",
                "clinical_significance": "Requires MedGemma for analysis",
                "expected_prognosis": "Cannot determine",
                "recommended_protocols": {
                    "radiation": "Cannot determine",
                    "chemotherapy": "Cannot determine",
                    "surveillance": "Cannot determine"
                },
                "classification_date": datetime.now().strftime('%Y-%m-%d'),
                "classification_method": "failed_no_medgemma",
                "confidence": "unavailable"
            }

        # PRIORITY 1: Query molecular_test_results for curated genomics data
        # This table contains actual genomics interpretation text in test_result_narrative
        # PRIORITY 2: Fallback to v_pathology_diagnostics for observations
        try:
            # Track molecular query attempt
            if self.completeness_tracker:
                self.completeness_tracker.mark_attempted('phase0_molecular_query')

            molecular_query = f"""
            SELECT
                patient_id as patient_fhir_id,
                'molecular_test_results' as diagnostic_source,
                lab_test_name as diagnostic_name,
                test_component as component_name,
                test_result_narrative as result_value,
                CAST(result_datetime AS VARCHAR) as diagnostic_date,
                'Genomics_Interpretation' as diagnostic_category,
                'Genomic Diagnostics Lab' as test_lab,
                1 as priority_tier
            FROM molecular_test_results
            WHERE patient_id = '{self.athena_patient_id}'
              AND test_result_narrative IS NOT NULL
              AND test_result_narrative != ''
              AND LENGTH(test_result_narrative) > 100
              AND (
                  LOWER(test_component) LIKE '%genomics interpretation%'
                  OR LOWER(test_component) LIKE '%genomics results%'
                  OR LOWER(lab_test_name) LIKE '%solid tumor%'
                  OR LOWER(lab_test_name) LIKE '%cancer panel%'
                  OR LOWER(lab_test_name) LIKE '%genomic%'
              )
            ORDER BY result_datetime DESC NULLS LAST
            LIMIT 10
            """

            molecular_data = query_athena(molecular_query, "Querying molecular_test_results for genomics data", suppress_output=True)
            logger.info(f"   Found {len(molecular_data) if molecular_data else 0} records from molecular_test_results")

            # Track molecular query success
            if self.completeness_tracker:
                self.completeness_tracker.mark_success(
                    'phase0_molecular_query',
                    record_count=len(molecular_data) if molecular_data else 0
                )

            # Track pathology query attempt
            if self.completeness_tracker:
                self.completeness_tracker.mark_attempted('phase0_pathology_query')

            # Fallback to v_pathology_diagnostics if no molecular test data
            pathology_query = f"""
            SELECT
                patient_fhir_id,
                diagnostic_source,
                diagnostic_name,
                component_name,
                result_value,
                CAST(diagnostic_date AS VARCHAR) as diagnostic_date,
                diagnostic_category,
                test_lab,
                2 as priority_tier
            FROM v_pathology_diagnostics
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND result_value IS NOT NULL
              AND result_value != ''
              AND result_value NOT LIKE '%| URL: Binary/%'
              AND LENGTH(result_value) > 50
              AND (
                  diagnostic_category IN ('Genomics_Method', 'Genomics_Interpretation', 'Final_Diagnosis')
                  OR (diagnostic_name LIKE '%IDH%' OR diagnostic_name LIKE '%BRAF%' OR diagnostic_name LIKE '%H3%'
                      OR diagnostic_name LIKE '%1p/19q%' OR diagnostic_name LIKE '%MGMT%' OR diagnostic_name LIKE '%ATRX%'
                      OR diagnostic_name LIKE '%TP53%' OR diagnostic_name LIKE '%EGFR%' OR diagnostic_name LIKE '%TERT%'
                      OR diagnostic_name LIKE '%MSH%' OR diagnostic_name LIKE '%MLH%' OR diagnostic_name LIKE '%PMS%')
              )
            ORDER BY diagnostic_date DESC NULLS LAST
            LIMIT 50
            """

            pathology_data = query_athena(pathology_query, "Querying v_pathology_diagnostics for fallback data", suppress_output=True)
            logger.info(f"   Found {len(pathology_data) if pathology_data else 0} records from v_pathology_diagnostics")

            # Track pathology query success
            if self.completeness_tracker:
                self.completeness_tracker.mark_success(
                    'phase0_pathology_query',
                    record_count=len(pathology_data) if pathology_data else 0
                )

            # Combine results: prioritize v_molecular_tests, then add v_pathology_diagnostics
            combined_data = []
            if molecular_data:
                combined_data.extend(molecular_data)
            if pathology_data:
                combined_data.extend(pathology_data)

            if not combined_data:
                logger.warning(f"No molecular or pathology data found for {self.athena_patient_id}")
                return {
                    "who_2021_diagnosis": "No molecular or pathology data available",
                    "molecular_subtype": "Unknown",
                    "grade": None,
                    "key_markers": "No data in v_molecular_tests or v_pathology_diagnostics",
                    "clinical_significance": "Patient not found in molecular/pathology views",
                    "expected_prognosis": "Cannot determine",
                    "recommended_protocols": {
                        "radiation": "Cannot determine",
                        "chemotherapy": "Cannot determine",
                        "surveillance": "Cannot determine"
                    },
                    "classification_date": datetime.now().strftime('%Y-%m-%d'),
                    "classification_method": "failed_no_data",
                    "confidence": "no_data"
                }

            # Use combined data for extraction
            pathology_data = combined_data
            logger.info(f"   Total records for extraction: {len(pathology_data)} ({len(molecular_data) if molecular_data else 0} from molecular tests, {len(combined_data) - (len(molecular_data) if molecular_data else 0)} from pathology)")

            # ========================================================================
            # PHASE 0.1: MULTI-SOURCE DIAGNOSTIC EVIDENCE AGGREGATION
            # ========================================================================
            logger.info("   [Phase 0.1] Collecting diagnostic evidence from multiple sources...")

            # Track Phase 0.1 attempt
            if self.completeness_tracker:
                self.completeness_tracker.mark_attempted('phase0_1_diagnostic_evidence_aggregation')

            from lib.diagnostic_evidence_aggregator import DiagnosticEvidenceAggregator

            # Initialize aggregator with query_athena function
            evidence_aggregator = DiagnosticEvidenceAggregator(query_athena)

            # Collect evidence from all sources
            all_diagnostic_evidence = evidence_aggregator.aggregate_all_evidence(self.athena_patient_id)

            logger.info(f"   ✅ Phase 0.1 complete: Collected {len(all_diagnostic_evidence)} pieces of diagnostic evidence")

            # Track Phase 0.1 success
            if self.completeness_tracker:
                self.completeness_tracker.mark_success(
                    'phase0_1_diagnostic_evidence_aggregation',
                    record_count=len(all_diagnostic_evidence)
                )

            # Log evidence summary
            if all_diagnostic_evidence:
                highest_authority = evidence_aggregator.get_highest_authority_diagnosis(all_diagnostic_evidence)
                if highest_authority:
                    logger.info(f"      Highest authority diagnosis: {highest_authority.diagnosis} "
                               f"(source: {highest_authority.source.name}, confidence: {highest_authority.confidence:.2f})")

                consensus = evidence_aggregator.get_consensus_diagnosis(all_diagnostic_evidence)
                if consensus:
                    logger.info(f"      Consensus diagnosis: {consensus}")

            # ========================================================================
            # STAGE 1: EXTRACT MOLECULAR FINDINGS AND DIAGNOSES
            # ========================================================================
            logger.info("   [Stage 1] Extracting molecular findings and diagnoses...")

            # Track Stage 1 attempt
            if self.completeness_tracker:
                self.completeness_tracker.mark_attempted('phase0_stage1_extract_findings')

            extracted_findings = self._stage1_extract_findings(pathology_data)

            # Enrich Stage 1 findings with Phase 0.1 evidence
            if all_diagnostic_evidence:
                extracted_findings['diagnostic_evidence'] = [
                    {
                        'diagnosis': ev.diagnosis,
                        'source': ev.source.name,
                        'confidence': ev.confidence,
                        'date': ev.date.strftime('%Y-%m-%d') if ev.date else None,
                        'extraction_method': ev.extraction_method
                    }
                    for ev in all_diagnostic_evidence
                ]
                logger.info(f"      Enriched Stage 1 findings with {len(all_diagnostic_evidence)} evidence items")

            if not extracted_findings or extracted_findings.get('extraction_status') == 'failed':
                logger.warning("   ⚠️  Stage 1 extraction failed, cannot proceed to Stage 2")

                # Track Stage 1 failure
                if self.completeness_tracker:
                    self.completeness_tracker.mark_failure(
                        'phase0_stage1_extract_findings',
                        error_message="Stage 1 extraction failed or returned no findings"
                    )

                return {
                    "who_2021_diagnosis": "Classification failed: No findings extracted",
                    "molecular_subtype": "Unknown",
                    "grade": None,
                    "key_markers": "Extraction failed",
                    "clinical_significance": "Could not extract findings from pathology data",
                    "expected_prognosis": "Cannot determine",
                    "recommended_protocols": {
                        "radiation": "Cannot determine",
                        "chemotherapy": "Cannot determine",
                        "surveillance": "Cannot determine"
                    },
                    "classification_date": datetime.now().strftime('%Y-%m-%d'),
                    "classification_method": "failed_stage1_extraction",
                    "confidence": "insufficient"
                }

            logger.info(f"   ✅ Stage 1 complete: Extracted {len(extracted_findings.get('molecular_markers', []))} molecular markers, "
                       f"{len(extracted_findings.get('histology_findings', []))} histology findings, "
                       f"{len(extracted_findings.get('problem_list_diagnoses', []))} problem list diagnoses")

            # Track Stage 1 success
            if self.completeness_tracker:
                total_findings = (len(extracted_findings.get('molecular_markers', [])) +
                                len(extracted_findings.get('histology_findings', [])) +
                                len(extracted_findings.get('problem_list_diagnoses', [])))
                self.completeness_tracker.mark_success(
                    'phase0_stage1_extract_findings',
                    record_count=total_findings
                )

            # ========================================================================
            # STAGE 2: MAP FINDINGS TO WHO 2021 CLASSIFICATION
            # ========================================================================
            logger.info("   [Stage 2] Mapping findings to WHO 2021 classification...")

            # Track Stage 2 attempt
            if self.completeness_tracker:
                self.completeness_tracker.mark_attempted('phase0_stage2_who_classification')

            classification = self._stage2_map_to_who2021(extracted_findings)

            if not classification or classification.get('confidence') == 'insufficient':
                logger.warning("   ⚠️  Stage 2 mapping resulted in insufficient confidence")

                # Track Stage 2 as having low confidence (not a failure, but note it)
                if self.completeness_tracker:
                    self.completeness_tracker.mark_success(
                        'phase0_stage2_who_classification',
                        record_count=1
                    )
            else:
                # Track Stage 2 success
                if self.completeness_tracker:
                    self.completeness_tracker.mark_success(
                        'phase0_stage2_who_classification',
                        record_count=1
                    )

            result_preview = classification.get('who_2021_diagnosis', 'Unknown')[:100]
            logger.info(f"   ✅ Stage 2 complete: {result_preview}")

            # ========================================================================
            # STAGE 3: VALIDATE DIAGNOSIS (BIOLOGICAL PLAUSIBILITY)
            # ========================================================================
            logger.info("   [Stage 3] Validating diagnosis against biological plausibility...")

            from lib.diagnosis_validator import DiagnosisValidator
            validator = DiagnosisValidator()

            # Validate classification against molecular markers and problem list
            validated_classification = validator.validate_diagnosis(
                who_classification=classification,
                stage1_findings=extracted_findings
            )

            # Log validation results
            validation = validated_classification.get('validation', {})
            if not validation.get('is_valid', True):
                logger.error(f"   ❌ Stage 3 FAILED: Diagnosis is biologically implausible!")
                logger.error(f"      Violations: {len(validation.get('violations', []))}")
            else:
                logger.info(f"   ✅ Stage 3 complete: Diagnosis is biologically plausible")

            if validation.get('warnings'):
                logger.warning(f"   ⚠️  Stage 3 warnings: {len(validation.get('warnings', []))}")

            if validation.get('conflicts'):
                logger.warning(f"   ⚠️  Stage 3 conflicts: {len(validation.get('conflicts', []))}")

            # Use validated classification (contains adjusted confidence and validation metadata)
            classification = validated_classification

            # Add metadata
            classification["classification_date"] = datetime.now().strftime('%Y-%m-%d')
            classification["classification_method"] = "medgemma_three_stage_validated"
            classification["stage1_findings"] = extracted_findings  # Store for audit trail

            # Convert confidence to string and lowercase (can be float from validation)
            confidence_raw = classification.get('confidence', 'unknown')

            # Handle numeric confidence (from validation) - convert low values to 'low'
            if isinstance(confidence_raw, (int, float)):
                if confidence_raw <= 0.3:
                    confidence = 'low'
                elif confidence_raw <= 0.6:
                    confidence = 'moderate'
                else:
                    confidence = 'high'
            else:
                confidence = str(confidence_raw).lower() if confidence_raw is not None else 'unknown'

            logger.info(f"   Three-stage classification confidence: {confidence} (raw: {confidence_raw})")

            # Tier 2: If confidence is low/insufficient, try binary pathology documents
            if confidence in ['low', 'insufficient', 'unknown']:
                logger.info(f"   ⚠️  Tier 1 confidence {confidence}, attempting Tier 2 (binary pathology fallback)...")

                # Format findings for binary enhancement
                findings_summary = json.dumps(extracted_findings, indent=2)

                enhanced_classification = self._enhance_classification_with_binary_pathology(
                    classification,
                    findings_summary
                )

                if enhanced_classification:
                    logger.info(f"   ✅ Generated WHO classification (Tier 2): {enhanced_classification.get('who_2021_diagnosis', 'Unknown')}")
                    return enhanced_classification
                else:
                    logger.info(f"   ℹ️  Tier 2 did not improve confidence, using Tier 1 result")

            return classification

        except Exception as e:
            logger.error(f"Error generating WHO classification: {e}")

            # Track failure in completeness tracker
            if self.completeness_tracker:
                # Determine which operation failed
                if 'molecular_query' in str(e) or 'molecular_test_results' in str(e):
                    self.completeness_tracker.mark_failure('phase0_molecular_query', error_message=str(e))
                elif 'pathology_query' in str(e) or 'v_pathology_diagnostics' in str(e):
                    self.completeness_tracker.mark_failure('phase0_pathology_query', error_message=str(e))
                elif 'stage1' in str(e).lower() or 'extract_findings' in str(e):
                    self.completeness_tracker.mark_failure('phase0_stage1_extract_findings', error_message=str(e))
                elif 'stage2' in str(e).lower() or 'who2021' in str(e):
                    self.completeness_tracker.mark_failure('phase0_stage2_who_classification', error_message=str(e))
                else:
                    # Generic Phase 0 failure
                    self.completeness_tracker.mark_failure('phase0_who_classification', error_message=str(e))

            return {
                "who_2021_diagnosis": f"Classification failed: {str(e)}",
                "molecular_subtype": "Unknown",
                "grade": None,
                "key_markers": "Classification generation failed",
                "clinical_significance": str(e),
                "expected_prognosis": "Cannot determine",
                "recommended_protocols": {
                    "radiation": "Cannot determine",
                    "chemotherapy": "Cannot determine",
                    "surveillance": "Cannot determine"
                },
                "classification_date": datetime.now().strftime('%Y-%m-%d'),
                "classification_method": "failed_error",
                "confidence": "error",
                "error": str(e)
            }

    def _stage1_extract_findings(self, pathology_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        STAGE 1: Extract molecular findings and diagnoses from structured pathology data

        This is a simple extraction task focusing on:
        - Molecular markers (IDH, BRAF, H3, 1p/19q, MGMT, ATRX, TP53, EGFR, TERT, MSH, MLH, PMS, etc.)
        - Histology findings (Final_Diagnosis from surgical pathology)
        - Problem list diagnoses (from condition/problem list resources)

        Args:
            pathology_data: List of pathology records from v_pathology_diagnostics

        Returns:
            Dict with extracted findings organized by category
        """
        # Format pathology data in SIMPLE format for extraction (includes FULL result_value!)
        pathology_summary = self._format_pathology_for_stage1_extraction(pathology_data)

        # DEBUG: Save formatted prompt to file for inspection
        debug_file = Path("/tmp/stage1_formatted_pathology.txt")
        with open(debug_file, 'w') as f:
            f.write(pathology_summary)
        logger.info(f"    🔍 DEBUG: Saved formatted pathology to {debug_file} ({len(pathology_summary)} chars, {len(pathology_data)} records)")

        extraction_prompt = f"""You are a medical data extraction specialist. Your task is to extract molecular findings and diagnoses from pathology data.

**CRITICAL EXTRACTION RULES:**
1. NEGATION DETECTION: If text says "negative", "not detected", "wild-type", "absent" → mark as NEGATIVE, not positive
2. EXACT TEXT QUOTES: Always quote the exact text where you found each finding
3. DISTINGUISH: Separate molecular markers, histology diagnoses, and problem list diagnoses
4. IGNORE: Descriptive text that isn't actual findings (e.g., "consistent with", "suggestive of")

**PATIENT PATHOLOGY DATA:**
{pathology_summary}

**YOUR TASK:**
Extract ALL molecular markers, histology findings, and diagnoses into this JSON structure:

{{
    "molecular_markers": [
        {{
            "marker_name": "IDH1",
            "status": "POSITIVE/NEGATIVE/INCONCLUSIVE",
            "details": "R132H mutation",
            "source_text": "exact quote from data",
            "test_method": "IHC/NGS/FISH/Sequencing/Unknown"
        }}
    ],
    "histology_findings": [
        {{
            "finding": "Diffuse astrocytoma",
            "source": "Final_Diagnosis/Pathology_Report/Biopsy",
            "source_text": "exact quote from data",
            "surgery_date": "YYYY-MM-DD"
        }}
    ],
    "problem_list_diagnoses": [
        {{
            "diagnosis": "Brain tumor diagnosis from problem list",
            "source_text": "exact quote from data"
        }}
    ],
    "tumor_location": "Anatomic location if mentioned",
    "patient_age_at_diagnosis": "Age if mentioned",
    "extraction_status": "success/partial/failed",
    "extraction_notes": "Any issues or ambiguities encountered"
}}

**IMPORTANT:** Return ONLY the JSON object, no additional text. If a category has no findings, use an empty list [].
"""

        try:
            result = self.medgemma_agent.extract(extraction_prompt)
            extracted = json.loads(result.raw_response)
            extracted["extraction_status"] = "success"
            return extracted
        except json.JSONDecodeError as e:
            logger.error(f"Stage 1 JSON parse error: {e}")
            logger.error(f"Response preview: {result.raw_response[:500]}")
            return {"extraction_status": "failed", "error": str(e)}
        except Exception as e:
            logger.error(f"Stage 1 extraction error: {e}")
            return {"extraction_status": "failed", "error": str(e)}

    def _stage2_map_to_who2021(self, extracted_findings: Dict[str, Any]) -> Dict[str, Any]:
        """
        STAGE 2: Map extracted findings to WHO 2021 CNS tumor classification

        This applies WHO CNS5 diagnostic criteria using the full WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md
        which includes episodic context for multi-surgery longitudinal tracking.

        V4 ENHANCEMENT: Uses two-stage selective WHO reference retrieval (5-10x context savings)

        Args:
            extracted_findings: Dict from Stage 1 with molecular_markers, histology_findings, etc.

        Returns:
            Dict with WHO 2021 classification
        """
        # Load WHO 2021 Diagnostic Agent Prompt (full episodic context preserved)
        if not WHO_2021_DIAGNOSTIC_AGENT_PROMPT_PATH.exists():
            logger.error(f"WHO Diagnostic Agent Prompt not found at {WHO_2021_DIAGNOSTIC_AGENT_PROMPT_PATH}")
            return {"confidence": "insufficient", "error": "WHO Diagnostic Agent Prompt not found"}

        with open(WHO_2021_DIAGNOSTIC_AGENT_PROMPT_PATH, 'r') as f:
            diagnostic_agent_prompt = f.read()

        # V4: Use selective WHO reference retrieval based on patient triage
        if not WHO_2021_REFERENCE_PATH.exists():
            logger.error(f"WHO reference not found at {WHO_2021_REFERENCE_PATH}")
            return {"confidence": "insufficient", "error": "WHO reference not found"}

        # Import WHO triage module
        from lib.who_reference_triage import WHOReferenceTriage

        # Initialize triage and identify relevant section
        triage = WHOReferenceTriage(WHO_2021_REFERENCE_PATH)
        section_key = triage.identify_relevant_section(extracted_findings)

        # Load only preamble + relevant section (5-10x less context)
        who_reference = triage.load_selective_reference(section_key)

        # Log context savings
        savings = triage.estimate_context_savings(section_key)
        logger.info(f"   📖 WHO Triage: {section_key} → {savings['selective_total_lines']} lines "
                   f"(saved {savings['savings_percentage']}% vs full reference)")

        # Format findings for mapping
        findings_json = json.dumps(extracted_findings, indent=2)

        mapping_prompt = f"""{diagnostic_agent_prompt}

================================================================================
WHO 2021 CNS TUMOR CLASSIFICATION REFERENCE
================================================================================

{who_reference}

================================================================================
EXTRACTED PATIENT FINDINGS (from Stage 1)
================================================================================

{findings_json}

================================================================================
YOUR TASK
================================================================================

Using the WHO 2021 reference above and following ALL the guidelines in the diagnostic agent prompt,
map the patient's extracted findings to the correct WHO 2021 CNS tumor classification.

Return this JSON structure:

{{
    "who_2021_diagnosis": "Complete WHO 2021 diagnosis (e.g., 'Astrocytoma, IDH-mutant, CNS WHO grade 3')",
    "molecular_subtype": "Key molecular classification (e.g., 'IDH-mutant astrocytoma')",
    "grade": 1-4 or null,
    "key_markers": "Comma-separated molecular markers used for classification",
    "clinical_significance": "Brief statement of clinical/prognostic significance",
    "expected_prognosis": "Prognosis summary based on WHO grade and molecular profile",
    "recommended_protocols": {{
        "radiation": "WHO-based radiation recommendation",
        "chemotherapy": "WHO-based chemotherapy recommendation",
        "surveillance": "WHO-based surveillance recommendation"
    }},
    "confidence": "high/moderate/low/insufficient",
    "classification_rationale": "Brief explanation of why this WHO classification was chosen"
}}

**IMPORTANT:** Return ONLY the JSON object, no additional text.
"""

        try:
            result = self.medgemma_agent.extract(mapping_prompt)
            classification = json.loads(result.raw_response)
            return classification
        except json.JSONDecodeError as e:
            logger.error(f"Stage 2 JSON parse error: {e}")
            logger.error(f"Response preview: {result.raw_response[:500]}")
            return {
                "who_2021_diagnosis": "Mapping failed: JSON parse error",
                "confidence": "insufficient",
                "error": str(e)
            }
        except Exception as e:
            import traceback
            logger.error(f"Stage 2 mapping error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "who_2021_diagnosis": "Mapping failed: Exception",
                "confidence": "insufficient",
                "error": str(e)
            }

    def _format_pathology_for_stage1_extraction(self, pathology_data: List[Dict[str, str]]) -> str:
        """
        Format pathology data in SIMPLE TABULAR format for Stage 1 extraction

        This method presents RAW DATA from v_pathology_diagnostics in a clean format
        that MedGemma can easily parse to extract molecular markers and diagnoses.

        Key differences from _format_pathology_for_who_prompt():
        - NO truncation of result_value (includes FULL text)
        - NO filtering by priority (includes ALL records)
        - NO grouping by surgery episode
        - SIMPLE one-record-per-section format

        Args:
            pathology_data: List of pathology records from v_pathology_diagnostics

        Returns:
            Simple formatted string with full data for extraction
        """
        # DEBUG: Log sample result_value fields to verify data quality
        records_with_molecular = []
        for record in pathology_data[:20]:  # Check first 20 records
            result = record.get('result_value', '')
            if result and any(marker in result for marker in ['IDH', 'BRAF', 'H3', 'ATRX', 'TP53', 'MGMT', '1p/19q']):
                records_with_molecular.append({
                    'name': record.get('diagnostic_name', 'Unknown'),
                    'preview': result[:200]
                })

        if records_with_molecular:
            logger.info(f"    🔍 DEBUG: Found {len(records_with_molecular)} records with molecular markers in first 20:")
            for r in records_with_molecular[:3]:  # Show first 3
                logger.info(f"       - {r['name']}: {r['preview']}")
        else:
            logger.warning(f"    ⚠️  DEBUG: No molecular markers found in first 20 records! Checking all {len(pathology_data)} records...")
            for record in pathology_data:
                result = record.get('result_value', '')
                if result and any(marker in result for marker in ['IDH', 'BRAF', 'H3', 'ATRX', 'TP53', 'MGMT', '1p/19q']):
                    logger.info(f"       ✅ Found marker in record: {record.get('diagnostic_name', 'Unknown')}")
                    break

        output = []
        output.append(f"PATHOLOGY DATA FOR EXTRACTION ({len(pathology_data)} records):")
        output.append("")

        for i, record in enumerate(pathology_data, 1):
            output.append(f"[Record {i}]")
            output.append(f"Source: {record.get('diagnostic_source', 'Unknown')}")
            output.append(f"Category: {record.get('diagnostic_category', 'Unknown')}")
            output.append(f"Date: {record.get('diagnostic_date', '')}")
            output.append(f"Test/Diagnosis Name: {record.get('diagnostic_name', '')}")
            output.append(f"Component: {record.get('component_name', '')}")
            output.append(f"Lab: {record.get('test_lab', 'Unknown')}")

            # CRITICAL: Include FULL result_value (NO truncation!)
            result = record.get('result_value', '')
            if result:
                output.append(f"Result: {result}")
            else:
                output.append("Result: [No result value]")

            output.append("")  # Blank line between records

        return "\n".join(output)

    def _format_pathology_for_who_prompt(self, pathology_data: List[Dict[str, str]]) -> str:
        """
        Format pathology data into structured text for WHO classification prompt

        Args:
            pathology_data: List of pathology records from v_pathology_diagnostics

        Returns:
            Formatted string for prompt
        """
        output = []

        # Group by surgery episode
        episodes = {}
        for record in pathology_data:
            surgery_date = record.get('linked_procedure_datetime', 'Unknown')
            if surgery_date not in episodes:
                episodes[surgery_date] = {
                    'procedure': record.get('linked_procedure_name', 'Unknown'),
                    'records': []
                }
            episodes[surgery_date]['records'].append(record)

        output.append(f"Patient ID: {self.athena_patient_id}")
        output.append(f"Total pathology records: {len(pathology_data)}")
        output.append(f"Number of surgery episodes: {len(episodes)}")
        output.append("")

        # Format each episode
        for surgery_date, episode_data in sorted(episodes.items(), reverse=True):
            output.append(f"{'='*80}")
            output.append(f"SURGERY EPISODE: {surgery_date}")
            output.append(f"Procedure: {episode_data['procedure']}")
            output.append(f"Total records: {len(episode_data['records'])}")
            output.append(f"{'='*80}")
            output.append("")

            # Count by priority
            priority_counts = {}
            for record in episode_data['records']:
                priority = record.get('extraction_priority', 'NULL')
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

            output.append("Document Priority Distribution:")
            for priority in sorted(priority_counts.keys()):
                output.append(f"  Priority {priority}: {priority_counts[priority]} documents")
            output.append("")

            # Show Priority 1-2 documents (most important for classification)
            priority_records = [r for r in episode_data['records']
                              if r.get('extraction_priority') in ['1', '2']]

            if priority_records:
                output.append(f"HIGH-PRIORITY DOCUMENTS (Priority 1-2): {len(priority_records)} records")
                output.append("-"*80)

                for i, record in enumerate(priority_records[:20], 1):  # Limit to first 20
                    output.append(f"\nRecord {i}:")
                    output.append(f"  Category: {record.get('document_category', 'Unknown')}")
                    output.append(f"  Priority: {record.get('extraction_priority', 'Unknown')}")
                    output.append(f"  Days from surgery: {record.get('days_from_surgery', 'Unknown')}")
                    output.append(f"  Diagnostic name: {record.get('diagnostic_name', 'Unknown')}")
                    output.append(f"  Component: {record.get('component_name', 'Unknown')}")
                    result_value = record.get('result_value', '')
                    if result_value:
                        # Truncate long values
                        if len(result_value) > 500:
                            result_value = result_value[:500] + "... [truncated]"
                        output.append(f"  Result: {result_value}")
                    output.append("")

                if len(priority_records) > 20:
                    output.append(f"\n[{len(priority_records) - 20} additional priority 1-2 records not shown]")

            output.append("")

        return "\n".join(output)

    def _enhance_classification_with_binary_pathology(
        self,
        tier1_classification: Dict[str, Any],
        structured_data_summary: str
    ) -> Optional[Dict[str, Any]]:
        """
        Enhance WHO classification by extracting text from binary pathology documents

        This is Tier 2 of the classification workflow, used when Tier 1 (structured data)
        produces low confidence results.

        Args:
            tier1_classification: Initial classification from structured data
            structured_data_summary: Formatted pathology summary from Tier 1

        Returns:
            Enhanced classification dict if successful and confidence improved, else None
        """
        try:
            logger.info("      [Tier 2] Querying v_binary_files for pathology documents...")

            # Query for pathology/molecular documents
            query = f"""
            SELECT
                binary_fhir_id,
                dr_fhir_id,
                patient_fhir_id,
                dr_type_text,
                content_type,
                size_bytes,
                linked_procedures_sorted,
                document_datetime,
                extraction_priority
            FROM v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND extraction_priority IN (1, 2)
              AND (
                LOWER(dr_type_text) LIKE '%pathology%'
                OR LOWER(dr_type_text) LIKE '%molecular%'
                OR LOWER(dr_type_text) LIKE '%biopsy%'
                OR LOWER(dr_type_text) LIKE '%histology%'
              )
            ORDER BY
                extraction_priority ASC,
                document_datetime DESC
            LIMIT 3
            """

            binary_docs = query_athena(query, "Tier 2: Querying pathology binary documents", suppress_output=True)

            if not binary_docs:
                logger.info("      [Tier 2] No binary pathology documents found")
                return None

            logger.info(f"      [Tier 2] Found {len(binary_docs)} binary pathology documents")

            # Extract text from documents
            extracted_texts = []
            for doc in binary_docs:
                binary_id = doc['binary_fhir_id']
                dr_type = doc['dr_type_text']
                content_type = doc['content_type']

                logger.info(f"      [Tier 2] Extracting from {dr_type} ({content_type})...")

                # Fetch and extract text from binary document
                binary_text = self._extract_text_from_binary_document(binary_id, content_type)

                if binary_text:
                    extracted_texts.append({
                        'source': dr_type,
                        'content_type': content_type,
                        'text': binary_text[:5000]  # Limit to 5000 chars per document
                    })
                    logger.info(f"      [Tier 2]    ✅ Extracted {len(binary_text)} characters")
                else:
                    logger.info(f"      [Tier 2]    ⚠️  No text extracted")

            if not extracted_texts:
                logger.info("      [Tier 2] No text extracted from binary documents")
                return None

            logger.info(f"      [Tier 2] Extracted text from {len(extracted_texts)} documents")

            # Construct enhanced prompt with both structured and binary data
            prompt_path = Path(__file__).parent.parent.parent / 'WHO_2021_DIAGNOSTIC_AGENT_PROMPT.md'
            with open(prompt_path, 'r') as f:
                who_prompt = f.read()

            # Format binary extractions
            binary_summary = "\n\n".join([
                f"BINARY DOCUMENT: {doc['source']} ({doc['content_type']})\n"
                f"{'='*80}\n"
                f"{doc['text']}\n"
                for doc in extracted_texts
            ])

            enhanced_prompt = f"""{who_prompt}

========================================================================================
TIER 2 ENHANCED CLASSIFICATION (Structured + Binary Pathology Data)
========================================================================================

TIER 1 RESULT (from structured data):
  WHO Diagnosis: {tier1_classification.get('who_2021_diagnosis', 'Unknown')}
  Confidence: {tier1_classification.get('confidence', 'Unknown')}
  Key Markers: {tier1_classification.get('key_markers', 'None')}

STRUCTURED DATA FROM v_pathology_diagnostics:
{structured_data_summary}

ADDITIONAL BINARY PATHOLOGY DOCUMENTS:
{binary_summary}

========================================================================================
YOUR TASK
========================================================================================

Re-evaluate the WHO 2021 classification using BOTH the structured data and the binary
document text. The binary documents may contain additional molecular details, histology
descriptions, or diagnostic conclusions not captured in structured fields.

Return your response as a JSON object with these fields:

{{
    "who_2021_diagnosis": "Complete WHO 2021 diagnosis string",
    "molecular_subtype": "Key molecular subtype/modifier",
    "grade": 1-4 or null,
    "key_markers": "Comma-separated list of key molecular markers",
    "clinical_significance": "Brief clinical significance statement",
    "expected_prognosis": "Prognosis summary",
    "recommended_protocols": {{
        "radiation": "Radiation recommendation",
        "chemotherapy": "Chemotherapy recommendation",
        "surveillance": "Surveillance recommendation"
    }},
    "confidence": "high/moderate/low/insufficient"
}}

Return ONLY the JSON object, no additional text.
"""

            # Call MedGemma with enhanced data
            logger.info("      [Tier 2] Calling MedGemma with enhanced data...")
            result = self.medgemma_agent.extract(enhanced_prompt)

            # Parse response
            enhanced_classification = json.loads(result.raw_response)
            enhanced_classification["classification_date"] = datetime.now().strftime('%Y-%m-%d')
            enhanced_classification["classification_method"] = "medgemma_tier2_structured_plus_binary"

            # Convert confidence to string and lowercase (can be float from averaging)
            tier2_conf_raw = enhanced_classification.get('confidence', 'unknown')
            tier2_confidence = str(tier2_conf_raw).lower() if tier2_conf_raw is not None else 'unknown'
            tier1_conf_raw = tier1_classification.get('confidence', 'unknown')
            tier1_confidence = str(tier1_conf_raw).lower() if tier1_conf_raw is not None else 'unknown'

            logger.info(f"      [Tier 2] Enhanced classification confidence: {tier2_confidence}")

            # Only return enhanced classification if confidence improved
            confidence_order = {'insufficient': 0, 'low': 1, 'moderate': 2, 'high': 3, 'unknown': 0}
            tier1_score = confidence_order.get(tier1_confidence, 0)
            tier2_score = confidence_order.get(tier2_confidence, 0)

            if tier2_score > tier1_score:
                logger.info(f"      [Tier 2] ✅ Confidence improved from {tier1_confidence} to {tier2_confidence}")
                return enhanced_classification
            else:
                logger.info(f"      [Tier 2] ℹ️  Confidence did not improve ({tier1_confidence} → {tier2_confidence})")
                return None

        except Exception as e:
            logger.error(f"      [Tier 2] Error during binary pathology enhancement: {e}")
            return None

    def _extract_text_from_binary_document(self, binary_id: str, content_type: str) -> Optional[str]:
        """
        Extract text from a binary document using appropriate method based on content type

        Args:
            binary_id: FHIR Binary resource ID
            content_type: MIME type of the document

        Returns:
            Extracted text or None if extraction failed
        """
        try:
            # Fetch binary document
            binary_data = self._fetch_binary_document(binary_id)
            if not binary_data:
                return None

            # Determine extraction method based on content type
            if content_type == 'application/pdf':
                # Use Binary File Agent for PDF extraction
                return self._extract_from_pdf(binary_data)

            elif content_type in ['image/tiff', 'image/jpeg', 'image/png']:
                # Use AWS Textract for images
                return self._extract_from_image_textract(binary_data)

            elif content_type in ['text/plain', 'text/html']:
                # Direct text extraction
                return binary_data.decode('utf-8', errors='ignore')

            else:
                logger.warning(f"Unsupported content type for text extraction: {content_type}")
                return None

        except Exception as e:
            logger.error(f"Error extracting text from binary {binary_id}: {e}")
            return None

    def _extract_from_pdf(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract text from PDF using Binary File Agent"""
        # TODO: Implement PDF extraction using Binary File Agent
        # For now, return None (will be implemented later)
        logger.info("         PDF extraction not yet implemented")
        return None

    def _extract_from_image_textract(self, image_bytes: bytes) -> Optional[str]:
        """Extract text from image using AWS Textract"""
        try:
            # Check if image needs conversion (TIFF to PNG)
            if self._is_tiff(image_bytes):
                logger.info("         Converting TIFF to PNG for Textract...")
                from PIL import Image
                import io

                tiff_image = Image.open(io.BytesIO(image_bytes))
                png_buffer = io.BytesIO()
                tiff_image.save(png_buffer, format='PNG')
                image_bytes = png_buffer.getvalue()

            # Call AWS Textract
            import boto3
            session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
            textract_client = session.client('textract')

            response = textract_client.detect_document_text(
                Document={'Bytes': image_bytes}
            )

            # Extract text from blocks
            lines = []
            for block in response.get('Blocks', []):
                if block['BlockType'] == 'LINE':
                    lines.append(block.get('Text', ''))

            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"Textract extraction error: {e}")
            return None

    def _is_tiff(self, image_bytes: bytes) -> bool:
        """Check if image bytes are TIFF format"""
        # TIFF magic numbers: II (little-endian) or MM (big-endian)
        return (image_bytes[:2] == b'II' or image_bytes[:2] == b'MM')

    def run(self, resume: bool = False) -> Dict[str, Any]:
        """Execute full iterative timeline abstraction workflow

        Args:
            resume: If True, attempt to resume from last successful checkpoint
        """

        print("="*80)
        print(f"PATIENT TIMELINE ABSTRACTION: {self.patient_id}")
        print("="*80)
        print()

        # Check for resume
        start_phase = None
        if resume and self.checkpoint_manager:
            latest_checkpoint = self.checkpoint_manager.get_latest_checkpoint()
            if latest_checkpoint:
                print(f"🔄 RESUMING from checkpoint: {latest_checkpoint}")
                print("="*80)
                print()
                # Determine which phase to start from
                phase_list = Phase.all_phases()
                last_completed_index = Phase.phase_index(latest_checkpoint)
                if last_completed_index >= 0 and last_completed_index < len(phase_list) - 1:
                    start_phase = phase_list[last_completed_index + 1]
                    print(f"✅ Last completed phase: {latest_checkpoint}")
                    print(f"▶️  Starting from phase: {start_phase}")
                    print()
            else:
                print("⚠️  No checkpoints found - starting from beginning")
                print()
        elif resume:
            print("⚠️  Checkpoint manager not available - starting from beginning")
            print()

        # PHASE 0: WHO 2021 TUMOR CLASSIFICATION (Run ONCE, cache forever)
        # This is the ONLY place tumor classification happens
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_0')

        print("PHASE 0: WHO 2021 TUMOR CLASSIFICATION")
        print("-"*80)
        print("This phase runs ONCE and caches the result.")
        print("Subsequent runs use cached classification (no reclassification).")
        print()
        # WHO classification already loaded in __init__ (from cache or generated)
        # Just display it here
        print(f"✅ WHO 2021 Diagnosis: {self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')}")
        print(f"   Grade: {self.who_2021_classification.get('grade', 'Unknown')}")
        print(f"   Key Markers: {self.who_2021_classification.get('key_markers', 'Unknown')}")
        print(f"   Confidence: {self.who_2021_classification.get('confidence', 'Unknown')}")
        print(f"   Method: {self.who_2021_classification.get('classification_method', 'Unknown')}")
        print()

        # PHASE 1: Load structured data from 6 Athena views FOR TIMELINE
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_1')

        if self._should_skip_phase(Phase.PHASE_1_DATA_LOADING, start_phase):
            print("⏭️  SKIPPING PHASE 1 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_1_DATA_LOADING)
            print()
        else:
            print("PHASE 1: LOAD STRUCTURED DATA FROM ATHENA VIEWS")
            print("-"*80)
            self._phase1_load_structured_data()
            print()
            self._save_checkpoint(Phase.PHASE_1_DATA_LOADING)

        # V4.6: Initialize investigation engine (needs Athena client from query_athena function)
        if self.schema_loader and not self.investigation_engine:
            try:
                from orchestration.investigation_engine import InvestigationEngine

                # Create a temporary Athena client for investigation engine
                import boto3
                session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
                athena_client = session.client('athena')

                self.investigation_engine = InvestigationEngine(
                    athena_client=athena_client,
                    schema_loader=self.schema_loader
                )
                logger.info("✅ V4.6: Investigation engine initialized")
            except Exception as e:
                logger.warning(f"⚠️  V4.6: Could not initialize investigation engine: {e}")

        # V5.0.3: Initialize data fingerprint manager (uses same Athena client)
        if DATA_FINGERPRINT_AVAILABLE and not self.fingerprint_manager:
            try:
                import boto3
                session = boto3.Session(profile_name='radiant-prod', region_name='us-east-1')
                athena_client = session.client('athena')

                self.fingerprint_manager = DataFingerprintManager(
                    athena_client=athena_client,
                    patient_id=self.athena_patient_id,
                    aws_profile='radiant-prod'
                )
                logger.info("✅ V5.0.3: Data fingerprint manager initialized")
            except Exception as e:
                logger.warning(f"⚠️  V5.0.3: Could not initialize fingerprint manager: {e}")

        # V4.6: PHASE 1.5: Validate schema coverage
        if self.schema_loader:
            print("PHASE 1.5: V4.6 SCHEMA COVERAGE VALIDATION")
            print("-"*80)
            self._phase1_5_validate_schema_coverage()
            print()

        # V4.7: PHASE 1 INVESTIGATION
        if self.investigation_engine:
            # Collect Phase 1 data loading statistics
            phase1_data = {
                'demographics': self.patient_demographics,
                'pathology_count': len(self.structured_data.get('pathology', [])),
                'procedures_count': len(self.structured_data.get('procedures', [])),
                'chemotherapy_count': len(self.structured_data.get('chemotherapy', [])),
                'radiation_count': len(self.structured_data.get('radiation', [])),
                'imaging_count': len(self.structured_data.get('imaging', []))
            }

            investigation = self.investigation_engine.investigate_phase1_data_loading(phase1_data)
            self._log_investigation_results('Phase 1', investigation)

        # PHASE 2: Construct initial timeline
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_2')

        if self._should_skip_phase(Phase.PHASE_2_TIMELINE_CONSTRUCTION, start_phase):
            print("⏭️  SKIPPING PHASE 2 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_2_TIMELINE_CONSTRUCTION)
            print()
        else:
            print("PHASE 2: CONSTRUCT INITIAL TIMELINE")
            print("-"*80)
            self._phase2_construct_initial_timeline()
            print()
            self._save_checkpoint(Phase.PHASE_2_TIMELINE_CONSTRUCTION)

        # PHASE 2.1: Validate minimal completeness (V4.6 REQUIREMENT)
        print("\n" + "="*80)
        print("PHASE 2.1: VALIDATE MINIMAL COMPLETENESS")
        print("="*80)
        self._validate_minimal_completeness()
        print()

        # PHASE 2.5: Assign treatment ordinality (V4 Enhancement)
        if not self._should_skip_phase(Phase.PHASE_2_5_TREATMENT_ORDINALITY, start_phase):
            self._phase2_5_assign_treatment_ordinality()
            print()
            self._save_checkpoint(Phase.PHASE_2_5_TREATMENT_ORDINALITY)

        # PHASE 3: Identify extraction gaps
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_3')

        if self._should_skip_phase(Phase.PHASE_3_GAP_IDENTIFICATION, start_phase):
            print("⏭️  SKIPPING PHASE 3 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_3_GAP_IDENTIFICATION)
            print()
        else:
            print("PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION")
            print("-"*80)
            self._phase3_identify_extraction_gaps()
            print()
            self._save_checkpoint(Phase.PHASE_3_GAP_IDENTIFICATION)

        # PHASE 3.5: Enrich EOR from v_imaging (before Phase 4 binary extraction)
        print("PHASE 3.5: ENRICH EOR FROM V_IMAGING STRUCTURED DATA")
        print("-"*80)
        print("  Querying v_imaging for post-op MRI/CT reports (fast structured query)")
        eor_enriched = self._enrich_eor_from_v_imaging()
        if eor_enriched > 0:
            print(f"  ✅ Enriched {eor_enriched} EOR values from v_imaging")
            print(f"  📊 Phase 4 will adjudicate operative notes vs imaging using EOROrchestrator")
        else:
            print(f"  ℹ️  No post-op imaging EOR found in v_imaging")
        print()

        # PHASE 4: Prioritize and extract from binaries (REAL MEDGEMMA INTEGRATION)
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_4')

        if self._should_skip_phase(Phase.PHASE_4_BINARY_EXTRACTION, start_phase):
            print("⏭️  SKIPPING PHASE 4 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_4_BINARY_EXTRACTION)
            print()
        else:
            print("PHASE 4: PRIORITIZED BINARY EXTRACTION WITH MEDGEMMA")
            print("-"*80)
            self._phase4_extract_from_binaries()
            print()
            self._save_checkpoint(Phase.PHASE_4_BINARY_EXTRACTION)

        # PHASE 4.5: Orchestrator assessment of extraction completeness
        if self._should_skip_phase(Phase.PHASE_4_5_COMPLETENESS_ASSESSMENT, start_phase):
            print("⏭️  SKIPPING PHASE 4.5 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_4_5_COMPLETENESS_ASSESSMENT)
            print()
        else:
            print("PHASE 4.5: ORCHESTRATOR ASSESSMENT OF EXTRACTION COMPLETENESS")
            print("-"*80)
            self._phase4_5_assess_extraction_completeness()
            print()
            self._save_checkpoint(Phase.PHASE_4_5_COMPLETENESS_ASSESSMENT)

        # V4.7: PHASE 4 INVESTIGATION (MedGemma extraction quality)
        if self.investigation_engine and hasattr(self, 'binary_extractions'):
            investigation = self.investigation_engine.investigate_phase4_medgemma_extraction(
                self.binary_extractions
            )
            self._log_investigation_results('Phase 4', investigation)

        # PHASE 5: Protocol validation
        # V5.2: Update structured logger context
        if self.structured_logger:
            self.structured_logger.update_context(phase='PHASE_5')

        if self._should_skip_phase(Phase.PHASE_5_PROTOCOL_VALIDATION, start_phase):
            print("⏭️  SKIPPING PHASE 5 (already completed)")
            print("-"*80)
            self._load_checkpoint_state(Phase.PHASE_5_PROTOCOL_VALIDATION)
            print()
        else:
            print("PHASE 5: WHO 2021 PROTOCOL VALIDATION")
            print("-"*80)
            self._phase5_protocol_validation()
            print()
            self._save_checkpoint(Phase.PHASE_5_PROTOCOL_VALIDATION)

        # PHASE 6: Generate final artifact
        print("PHASE 6: GENERATE FINAL TIMELINE ARTIFACT")
        print("-"*80)
        artifact = self._phase6_generate_artifact()
        print()
        self._save_checkpoint(Phase.PHASE_6_ARTIFACT_GENERATION)

        # PHASE 7: Investigation Engine QA/QC
        print("PHASE 7: INVESTIGATION ENGINE - END-TO-END QA/QC")
        print("-"*80)

        # Track Phase 7 investigation engine QA/QC attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase7_investigation_engine_qaqc')

        try:
            from lib.investigation_engine_qaqc import InvestigationEngineQAQC

            qaqc = InvestigationEngineQAQC(
                anchored_diagnosis=self.who_2021_classification,
                timeline_events=self.timeline_events,
                patient_fhir_id=self.athena_patient_id
            )
            validation_report = qaqc.run_comprehensive_validation()

            # Store validation report in artifact
            artifact['phase_7_validation'] = validation_report

            # Track Phase 7 success
            if self.completeness_tracker:
                # Count number of validations performed
                num_validations = 0
                if validation_report:
                    num_validations = len(validation_report.get('validations', []))
                self.completeness_tracker.mark_success(
                    'phase7_investigation_engine_qaqc',
                    record_count=num_validations
                )

        except Exception as e:
            logger.error(f"Phase 7 Investigation Engine QA/QC failed: {e}")
            artifact['phase_7_validation'] = {
                'status': 'ERROR',
                'error': str(e)
            }

            # Track Phase 7 failure
            if self.completeness_tracker:
                self.completeness_tracker.mark_failure(
                    'phase7_investigation_engine_qaqc',
                    error_message=str(e)
                )

        print()

        return artifact

    def _init_extraction_tracker(self) -> Dict:
        """
        V3: Initialize extraction tracking data structure

        Returns:
            Empty extraction tracker dictionary
        """
        return {
            'free_text_schema_fields': {},
            'binary_documents': {
                'fetched': [],
                'attempted_count': 0,
                'success_count': 0
            },
            'extraction_timeline': []
        }

    def _track_schema_query(self, schema_name: str, fields: List[str], row_count: int):
        """
        V3: Track a schema query execution

        Args:
            schema_name: Name of the schema/view queried
            fields: List of field names queried
            row_count: Number of rows returned
        """
        self.extraction_tracker['free_text_schema_fields'][schema_name] = {
            'fields_queried': fields,
            'rows_found': row_count,
            'query_timestamp': datetime.now().isoformat()
        }

        # Add to timeline
        self.extraction_tracker['extraction_timeline'].append({
            'timestamp': datetime.now().isoformat(),
            'phase': 'Phase 1',
            'action': f'Loaded {schema_name}',
            'rows': row_count
        })

        logger.debug(f"Tracked schema query: {schema_name} ({row_count} rows)")

    def _track_binary_fetch(self, binary_id: str, content_type: str, success: bool, metadata: Dict):
        """
        V3: Track a binary document fetch attempt

        Args:
            binary_id: Binary document ID
            content_type: Content type of document
            success: Whether fetch was successful
            metadata: Additional metadata (gap_type, text_length, etc.)
        """
        fetch_record = {
            'binary_id': binary_id,
            'content_type': content_type,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            **metadata
        }

        self.extraction_tracker['binary_documents']['fetched'].append(fetch_record)
        self.extraction_tracker['binary_documents']['attempted_count'] += 1
        if success:
            self.extraction_tracker['binary_documents']['success_count'] += 1

        # Add to timeline
        self.extraction_tracker['extraction_timeline'].append({
            'timestamp': datetime.now().isoformat(),
            'phase': 'Phase 4',
            'action': f"{'✅' if success else '❌'} Fetched binary {binary_id[:20]}...",
            'content_type': content_type,
            'gap_type': metadata.get('gap_type')
        })

        logger.debug(f"Tracked binary fetch: {binary_id} (success={success})")

    def _save_investigation_report(self, query_id: str, investigation: Dict):
        """
        V4.6: Save investigation report for manual review

        Args:
            query_id: Athena query execution ID
            investigation: Investigation results dictionary
        """
        import json
        from pathlib import Path

        report_dir = Path(self.output_dir) / "investigation_reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / f"{query_id}.json"
        with open(report_path, 'w') as f:
            json.dump(investigation, f, indent=2)

        logger.info(f"  📋 V4.6: Investigation report saved: {report_path}")

    def _get_cached_binary_text(self, binary_id: str) -> Optional[str]:
        """
        V4.6: Get cached binary document text from extraction tracker

        Args:
            binary_id: Binary document ID

        Returns:
            Extracted text if available, None otherwise
        """
        # Search through binary extractions for this ID
        for extraction in self.binary_extractions:
            if extraction.get('binary_id') == binary_id and extraction.get('extracted_text'):
                return extraction['extracted_text']

        return None

    def _should_skip_phase(self, phase_name: str, start_phase: str) -> bool:
        """
        Determine if a phase should be skipped during resume.

        Args:
            phase_name: Current phase name
            start_phase: Phase to start from (first phase to execute)

        Returns:
            True if phase should be skipped (already completed)
        """
        if not start_phase or not Phase:
            return False

        current_index = Phase.phase_index(phase_name)
        start_index = Phase.phase_index(start_phase)

        return current_index < start_index

    def _load_checkpoint_state(self, phase_name: str):
        """
        Load state from a checkpoint if available.

        Args:
            phase_name: Phase name to load checkpoint for
        """
        if not self.checkpoint_manager:
            return

        state = self.checkpoint_manager.load_checkpoint(phase_name)
        if state:
            # Restore state variables
            if 'structured_data' in state:
                self.structured_data = state['structured_data']
            if 'timeline_events' in state:
                self.timeline_events = state['timeline_events']
            if 'extraction_gaps' in state:
                self.extraction_gaps = state['extraction_gaps']
            if 'binary_extractions' in state:
                self.binary_extractions = state['binary_extractions']
            if 'protocol_validations' in state:
                self.protocol_validations = state['protocol_validations']
            if 'completeness_assessment' in state:
                self.completeness_assessment = state['completeness_assessment']
            if 'patient_demographics' in state:
                self.patient_demographics = state['patient_demographics']

    def _save_checkpoint(self, phase_name: str):
        """
        Save checkpoint after phase completion.

        Args:
            phase_name: Phase name that just completed
        """
        if not self.checkpoint_manager:
            return

        # Collect state to checkpoint
        state = {
            'structured_data': self.structured_data if hasattr(self, 'structured_data') else {},
            'timeline_events': self.timeline_events,
            'extraction_gaps': self.extraction_gaps,
            'binary_extractions': self.binary_extractions,
            'protocol_validations': self.protocol_validations,
            'completeness_assessment': self.completeness_assessment,
            'patient_demographics': self.patient_demographics,
            'extraction_tracker': self.extraction_tracker
        }

        self.checkpoint_manager.save_checkpoint(phase_name, state)

    def _log_investigation_results(self, phase_name: str, investigation: Dict):
        """
        V4.7: Log investigation results in a formatted way

        Args:
            phase_name: Name of the phase investigated (e.g., "Phase 1", "Phase 4")
            investigation: Investigation result dictionary with issues_found, suggestions, statistics
        """
        if not investigation:
            return

        # Store investigation for final report
        if not hasattr(self, 'v47_investigations'):
            self.v47_investigations = {}
        self.v47_investigations[phase_name] = investigation

        issues = investigation.get('issues_found', [])
        suggestions = investigation.get('suggestions', [])
        statistics = investigation.get('statistics', {})

        if not issues and not suggestions:
            logger.info(f"\n🔍 V4.7 {phase_name.upper()} INVESTIGATION: ✅ No issues found")
            return

        logger.info(f"\n🔍 V4.7 {phase_name.upper()} INVESTIGATION")
        logger.info(f"  Status: {'⚠️  Issues found' if issues else '✅ No issues'}")

        # Log statistics if available
        if statistics:
            logger.info(f"  Statistics:")
            for key, value in statistics.items():
                if isinstance(value, float):
                    logger.info(f"    - {key}: {value:.2f}")
                else:
                    logger.info(f"    - {key}: {value}")

        # Log issues
        if issues:
            logger.info(f"  Issues Found ({len(issues)}):")
            for issue in issues[:5]:  # Show first 5
                logger.info(f"    - {issue}")
            if len(issues) > 5:
                logger.info(f"    ... and {len(issues) - 5} more")

        # Log suggestions
        if suggestions:
            logger.info(f"  Remediation Suggestions ({len(suggestions)}):")
            for suggestion in suggestions[:5]:  # Show first 5
                method = suggestion.get('method', 'unknown')
                description = suggestion.get('description', '')
                confidence = suggestion.get('confidence', 0)
                logger.info(f"    - {method}: {description} ({confidence:.0%} confidence)")
            if len(suggestions) > 5:
                logger.info(f"    ... and {len(suggestions) - 5} more")

    def _track_extraction_attempt(self, gap: Dict, document: Dict, result: Dict):
        """
        V3: Track a MedGemma extraction attempt

        Args:
            gap: Gap being filled
            document: Document being extracted from
            result: Extraction result (success, confidence, etc.)
        """
        self.extraction_tracker['extraction_timeline'].append({
            'timestamp': datetime.now().isoformat(),
            'phase': 'Phase 4',
            'action': f"MedGemma extraction for {gap.get('gap_type')}",
            'binary_id': document.get('binary_id'),
            'success': result.get('success', False),
            'confidence': result.get('confidence', 'unknown')
        })

        logger.debug(f"Tracked extraction: {gap.get('gap_type')} (success={result.get('success')})")

    def _generate_extraction_report(self) -> Dict:
        """
        V3: Generate comprehensive extraction tracking report

        Returns:
            Dictionary with extraction statistics and timeline
        """
        report = {
            'total_schemas_queried': len(self.extraction_tracker['free_text_schema_fields']),
            'total_rows_fetched': sum(
                v['rows_found'] for v in self.extraction_tracker['free_text_schema_fields'].values()
            ),
            'schema_details': self.extraction_tracker['free_text_schema_fields'],
            'binary_fetch_stats': {
                'attempted': self.extraction_tracker['binary_documents']['attempted_count'],
                'successful': self.extraction_tracker['binary_documents']['success_count'],
                'success_rate': (
                    self.extraction_tracker['binary_documents']['success_count'] /
                    self.extraction_tracker['binary_documents']['attempted_count']
                ) if self.extraction_tracker['binary_documents']['attempted_count'] > 0 else 0.0
            },
            'extraction_timeline': self.extraction_tracker['extraction_timeline']
        }

        logger.info(f"Generated extraction report: {report['total_schemas_queried']} schemas, {report['binary_fetch_stats']['attempted']} binary fetches")

        return report

    def _load_patient_demographics(self):
        """
        V3: Load patient demographics from v_patient_demographics

        Used for age-appropriate protocol selection and risk stratification.
        """
        query = f"""
            SELECT
                patient_fhir_id,
                pd_gender,
                pd_race,
                pd_ethnicity,
                pd_birth_date,
                pd_age_years
            FROM fhir_prd_db.v_patient_demographics
            WHERE patient_fhir_id = '{self.athena_patient_id}'
        """

        try:
            demographics = query_athena(query, "Loading patient demographics")

            if demographics and len(demographics) > 0:
                self.patient_demographics = demographics[0]

                # Extract key fields for protocol considerations
                age_raw = self.patient_demographics.get('pd_age_years')
                gender = self.patient_demographics.get('pd_gender', 'Unknown')

                # Convert age to int (Athena returns as string)
                age = int(age_raw) if age_raw is not None else None

                logger.info(f"✅ Demographics loaded: Age={age}, Gender={gender}")

                # Add age-based protocol considerations
                if age is not None:
                    if age < 3:
                        consideration = "Infant protocol: Avoid/delay radiation due to neurotoxicity"
                        self.protocol_considerations.append(consideration)
                        logger.info(f"   ⚠️  {consideration}")
                    elif age >= 3 and age < 18:
                        self.protocol_considerations.append("Pediatric protocol: Age-appropriate dosing and long-term effects monitoring")
                    else:
                        self.protocol_considerations.append("Adult-type protocol: Standard adult dosing")

                return self.patient_demographics
            else:
                logger.warning(f"⚠️  No demographics found for {self.athena_patient_id}")
                return {}

        except Exception as e:
            logger.error(f"Error loading demographics: {e}")
            return {}

    def _phase1_load_structured_data(self):
        """Phase 1: Query 6 Athena views for structured data + V3: demographics"""

        # V3: Load patient demographics first
        self._load_patient_demographics()

        # CORRECT COLUMN NAMES from schema review
        queries = {
            'pathology': f"""
                SELECT
                    patient_fhir_id,
                    diagnostic_date,
                    diagnostic_name,
                    component_name,
                    result_value,
                    extraction_priority,
                    document_category
                FROM fhir_prd_db.v_pathology_diagnostics
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY diagnostic_date
            """,
            'procedures': f"""
                SELECT
                    patient_fhir_id,
                    procedure_fhir_id,
                    COALESCE(proc_performed_date_time, proc_performed_period_start) as proc_performed_date_time,
                    surgery_type,
                    proc_code_text,
                    proc_encounter_reference,
                    -- V2 NEW FIELDS: V4.1 Institution tracking + cross-resource annotation
                    specimen_id,
                    performer_org_id,
                    performer_org_name,
                    institution_confidence,
                    -- V5.0.2 FIX: Include validation fields for expanded filtering
                    is_tumor_surgery,
                    has_tumor_reason,
                    has_tumor_body_site,
                    procedure_classification,
                    classification_confidence
                FROM fhir_prd_db.v_procedures_tumor
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                    AND (
                        is_tumor_surgery = true
                        OR has_tumor_reason = true
                        OR has_tumor_body_site = true
                    )
                ORDER BY COALESCE(proc_performed_date_time, proc_performed_period_start)
            """,
            'chemotherapy': f"""
                SELECT
                    -- Episode identifiers
                    patient_fhir_id,
                    episode_id,
                    episode_encounter_reference,
                    -- V4.8: ALL date fields for intelligent adjudication
                    episode_start_datetime,
                    episode_end_datetime,
                    episode_duration_days,
                    medication_start_datetime,
                    medication_stop_datetime,
                    raw_medication_start_date,
                    raw_medication_stop_date,
                    raw_medication_authored_date,
                    -- V4.8.1: COMPREHENSIVE drug name fields (RxNorm, preferred names, categories)
                    episode_drug_names,
                    episode_drug_categories,
                    chemo_drug_id,
                    chemo_preferred_name,
                    chemo_drug_category,
                    medication_name,
                    -- Episode metadata
                    medication_count,
                    unique_drug_count,
                    medications_with_stop_date,
                    has_medications_without_stop_date,
                    -- Medication details
                    medication_dosage_instructions,
                    medication_route,
                    medication_status,
                    episode_routes,
                    episode_medication_statuses,
                    -- Clinical context
                    medication_notes,
                    medication_reason,
                    has_medication_notes,
                    -- Care plan context (protocol information)
                    episode_care_plan_id,
                    episode_care_plan_title,
                    episode_care_plan_status,
                    -- FHIR references
                    medication_request_fhir_id,
                    medication_fhir_id,
                    encounter_fhir_id,
                    medication_encounter_reference
                FROM fhir_prd_db.v_chemo_treatment_episodes
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY COALESCE(
                    episode_start_datetime,
                    CAST(raw_medication_start_date AS timestamp),
                    medication_start_datetime
                )
            """,
            'radiation': f"""
                SELECT
                    -- Episode identifiers
                    patient_fhir_id,
                    episode_id,
                    episode_detection_method,
                    -- Episode dates and duration
                    episode_start_date,
                    episode_end_date,
                    episode_duration_days,
                    -- Dose information
                    total_dose_cgy,
                    radiation_fields,
                    radiation_site_codes,
                    num_dose_records,
                    has_structured_dose,
                    -- Document availability
                    num_documents,
                    has_documents,
                    highest_priority_available,
                    nlp_extraction_priority,
                    -- V4.8.1: COMPREHENSIVE appointment enrichment
                    total_appointments,
                    fulfilled_appointments,
                    booked_appointments,
                    pre_treatment_appointments,
                    during_treatment_appointments,
                    post_treatment_appointments,
                    early_followup_appointments,
                    late_followup_appointments,
                    appointment_types,
                    first_appointment_date,
                    last_appointment_date,
                    first_pre_treatment_appointment,
                    first_during_treatment_appointment,
                    first_post_treatment_appointment,
                    first_followup_appointment,
                    appointment_fulfillment_rate_pct,
                    has_appointment_enrichment,
                    -- V4.8.1: COMPREHENSIVE care plan enrichment (protocol information)
                    total_care_plans,
                    care_plans_with_dates,
                    care_plans_intent_plan,
                    care_plans_intent_proposal,
                    care_plans_intent_order,
                    care_plans_active,
                    care_plans_completed,
                    care_plans_draft,
                    care_plan_titles,
                    care_plan_parent_references,
                    has_parent_care_plans,
                    earliest_care_plan_start,
                    latest_care_plan_end,
                    has_care_plan_enrichment,
                    -- Data quality metrics
                    enrichment_score,
                    data_completeness_tier,
                    treatment_phase_coverage
                FROM fhir_prd_db.v_radiation_episode_enrichment
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY episode_start_date
            """,
            'imaging': f"""
                SELECT
                    patient_fhir_id,
                    imaging_date,
                    imaging_modality,
                    result_information as report_conclusion,
                    result_diagnostic_report_id,
                    diagnostic_report_id,
                    -- V2 NEW FIELDS: V4.1 Institution tracking + binary content direct access
                    performer_org_id,
                    performer_org_name,
                    binary_content_id
                FROM fhir_prd_db.v_imaging
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY imaging_date
            """,
            'visits': f"""
                SELECT
                    patient_fhir_id,
                    visit_date,
                    visit_type
                FROM fhir_prd_db.v_visits_unified
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY visit_date
            """
        }

        # V5.2: Use parallel query execution if available, otherwise fall back to sequential
        self.structured_data = {}

        if self.athena_parallel_executor and ATHENA_PARALLEL_AVAILABLE:
            # V5.2: PARALLEL EXECUTION (50-75% faster)
            if self.structured_logger:
                self.structured_logger.info(f"Executing {len(queries)} Athena queries in parallel (max_concurrent=5)")
            else:
                logger.info(f"V5.2: Executing {len(queries)} Athena queries in parallel")

            try:
                # Mark all sources as attempted in completeness tracker
                if self.completeness_tracker:
                    for source_name in queries.keys():
                        self.completeness_tracker.mark_attempted(f'phase1_{source_name}')

                # Execute queries in parallel
                parallel_results = self.athena_parallel_executor.execute_parallel(queries)

                # Store results and track completeness
                for source_name, data in parallel_results.items():
                    self.structured_data[source_name] = data

                    # Track success in completeness tracker
                    if self.completeness_tracker:
                        self.completeness_tracker.mark_success(
                            f'phase1_{source_name}',
                            record_count=len(data)
                        )

                    if self.structured_logger:
                        self.structured_logger.info(f"Loaded {len(data)} {source_name} records")

                    # V3: Track schema query
                    field_names = []
                    query = queries[source_name]
                    if 'SELECT' in query:
                        # Extract field names from SELECT clause (simple parsing)
                        select_clause = query.split('FROM')[0].split('SELECT')[1].strip()
                        field_names = [f.strip().split(' as ')[-1].split(',')[0] for f in select_clause.split(',')]
                    self._track_schema_query(
                        schema_name=f"v_{source_name}",
                        fields=field_names,
                        row_count=len(self.structured_data[source_name])
                    )

                if self.structured_logger:
                    self.structured_logger.info("Parallel query execution completed successfully")
                else:
                    logger.info("✅ V5.2: Parallel query execution completed")

            except Exception as e:
                # Log error and fall back to sequential execution
                if self.completeness_tracker:
                    self.completeness_tracker.log_error(
                        error_type='parallel_query_failure',
                        message=f"Parallel query execution failed: {str(e)}",
                        phase='PHASE_1',
                        severity=ErrorSeverity.RECOVERABLE if EXCEPTION_HANDLING_AVAILABLE else None
                    )

                logger.warning(f"⚠️  V5.2: Parallel query execution failed: {e}")
                logger.warning("   Falling back to sequential execution...")

                # FALLBACK: Sequential execution
                for source_name, query in queries.items():
                    # Mark as attempted
                    if self.completeness_tracker:
                        self.completeness_tracker.mark_attempted(f'phase1_{source_name}')

                    try:
                        # V4.6: Pass investigation engine for automatic query failure investigation
                        self.structured_data[source_name] = query_athena(
                            query=query,
                            description=f"Loading {source_name}",
                            investigation_engine=self.investigation_engine if hasattr(self, 'investigation_engine') else None,
                            schema_loader=self.schema_loader if hasattr(self, 'schema_loader') else None
                        )

                        # Track success
                        if self.completeness_tracker:
                            self.completeness_tracker.mark_success(
                                f'phase1_{source_name}',
                                record_count=len(self.structured_data[source_name])
                            )

                        # V3: Track schema query
                        field_names = []
                        if 'SELECT' in query:
                            # Extract field names from SELECT clause (simple parsing)
                            select_clause = query.split('FROM')[0].split('SELECT')[1].strip()
                            field_names = [f.strip().split(' as ')[-1].split(',')[0] for f in select_clause.split(',')]
                        self._track_schema_query(
                            schema_name=f"v_{source_name}",
                            fields=field_names,
                            row_count=len(self.structured_data[source_name])
                        )
                    except Exception as query_error:
                        # Track failure
                        if self.completeness_tracker:
                            self.completeness_tracker.mark_failure(
                                f'phase1_{source_name}',
                                error_message=str(query_error)
                            )
                        raise
        else:
            # SEQUENTIAL EXECUTION (original behavior)
            if self.structured_logger:
                self.structured_logger.info("Executing Athena queries sequentially (parallel executor not available)")
            else:
                logger.info("Executing Athena queries sequentially")

            for source_name, query in queries.items():
                # Mark as attempted
                if self.completeness_tracker:
                    self.completeness_tracker.mark_attempted(f'phase1_{source_name}')

                try:
                    # V4.6: Pass investigation engine for automatic query failure investigation
                    self.structured_data[source_name] = query_athena(
                        query=query,
                        description=f"Loading {source_name}",
                        investigation_engine=self.investigation_engine if hasattr(self, 'investigation_engine') else None,
                        schema_loader=self.schema_loader if hasattr(self, 'schema_loader') else None
                    )

                    # Track success
                    if self.completeness_tracker:
                        self.completeness_tracker.mark_success(
                            f'phase1_{source_name}',
                            record_count=len(self.structured_data[source_name])
                        )

                    # V3: Track schema query
                    field_names = []
                    if 'SELECT' in query:
                        # Extract field names from SELECT clause (simple parsing)
                        select_clause = query.split('FROM')[0].split('SELECT')[1].strip()
                        field_names = [f.strip().split(' as ')[-1].split(',')[0] for f in select_clause.split(',')]
                    self._track_schema_query(
                        schema_name=f"v_{source_name}",
                        fields=field_names,
                        row_count=len(self.structured_data[source_name])
                    )
                except Exception as query_error:
                    # Track failure
                    if self.completeness_tracker:
                        self.completeness_tracker.mark_failure(
                            f'phase1_{source_name}',
                            error_message=str(query_error)
                        )
                    raise

        # V4.1: Extract institution from procedures and imaging (Steps 3 & 4) - V2 OPTIMIZED
        if self.institution_tracker:
            from datetime import datetime
            tier1_procedures = 0
            tier23_procedures = 0

            # Extract institution from procedures
            for proc_dict in self.structured_data.get('procedures', []):
                # V2 OPTIMIZATION: Check V2 institution_confidence field
                if proc_dict.get('institution_confidence') == 'HIGH':
                    # TIER 1: Use V2 performer_org fields directly (85% coverage from structured FHIR)
                    from lib.feature_object import FeatureObject, SourceRecord
                    institution_feature = FeatureObject(
                        value=proc_dict['performer_org_name'],
                        sources=[
                            SourceRecord(
                                source_type="structured_fhir",
                                extracted_value=proc_dict['performer_org_name'],
                                extraction_method="fhir_performer_reference",
                                confidence="HIGH",
                                source_id=proc_dict.get('performer_org_id'),
                                extracted_at=datetime.utcnow().isoformat() + 'Z'
                            )
                        ]
                    )
                    proc_dict['v41_institution'] = institution_feature.to_dict()
                    tier1_procedures += 1
                else:
                    # TIER 2/3: Use InstitutionTracker for metadata/text extraction (15% fallback)
                    institution_feature = self.institution_tracker.extract_from_procedure(proc_dict)
                    if institution_feature:
                        proc_dict['v41_institution'] = institution_feature.to_dict()
                        tier23_procedures += 1

            tier1_imaging = 0
            tier23_imaging = 0

            # Extract institution from imaging
            for img_dict in self.structured_data.get('imaging', []):
                # V2 OPTIMIZATION: Use performer_org_name if available
                if img_dict.get('performer_org_name'):
                    # TIER 1: Use V2 performer fields (85% coverage from structured FHIR)
                    from lib.feature_object import FeatureObject, SourceRecord
                    institution_feature = FeatureObject(
                        value=img_dict['performer_org_name'],
                        sources=[
                            SourceRecord(
                                source_type="structured_fhir",
                                extracted_value=img_dict['performer_org_name'],
                                extraction_method="fhir_performer_reference",
                                confidence="HIGH",
                                source_id=img_dict.get('performer_org_id'),
                                extracted_at=datetime.utcnow().isoformat() + 'Z'
                            )
                        ]
                    )
                    img_dict['v41_institution'] = institution_feature.to_dict()
                    tier1_imaging += 1
                else:
                    # TIER 2/3: Use InstitutionTracker
                    institution_feature = self.institution_tracker.extract_from_imaging(img_dict)
                    if institution_feature:
                        img_dict['v41_institution'] = institution_feature.to_dict()
                        tier23_imaging += 1

            logger.info(f"✅ V4.1: Institution tracking complete (V2 optimized)")
            logger.info(f"  Procedures: Tier 1={tier1_procedures}, Tier 2/3={tier23_procedures}")
            logger.info(f"  Imaging: Tier 1={tier1_imaging}, Tier 2/3={tier23_imaging}")

        print(f"  ✅ Loaded structured data from 6 views:")
        for source, data in self.structured_data.items():
            print(f"     {source}: {len(data)} records")

    def _phase1_5_validate_schema_coverage(self):
        """
        V4.6: Validate that all available FHIR resources were queried
        Uses schema loader to identify patient-scoped tables and check coverage
        """
        if not self.schema_loader:
            logger.warning("⚠️  V4.6: Schema loader not available - skipping coverage validation")
            return

        logger.info("\n🔍 V4.6: Validating FHIR schema coverage")

        # Get all patient-scoped tables from schema
        patient_tables = self.schema_loader.find_patient_reference_tables()
        logger.info(f"  Found {len(patient_tables)} patient-scoped tables in schema")

        # Check which tables we've queried
        queried_tables = set(self.extraction_tracker['free_text_schema_fields'].keys())

        # Identify missing tables
        missing_tables = set(patient_tables) - queried_tables

        if missing_tables:
            logger.warning(f"  ⚠️  {len(missing_tables)} tables NOT queried:")
            for table in sorted(missing_tables)[:10]:  # Show first 10
                # Note: We can't check counts here without Athena client access
                # Just log the missing table names
                logger.warning(f"    • {table}: NOT extracted")
        else:
            logger.info(f"  ✅ All {len(patient_tables)} patient-scoped tables queried")

        # Store coverage metrics
        self.schema_coverage = {
            'total_patient_tables': len(patient_tables),
            'queried_tables': len(queried_tables),
            'coverage_pct': (len(queried_tables) / len(patient_tables) * 100) if patient_tables else 0,
            'missing_tables': list(missing_tables)
        }

    def _phase2_construct_initial_timeline(self):
        """
        Phase 2: Construct timeline using STEPWISE STAGED approach

        Follows user-specified ordering:
        1. Molecular diagnosis (WHO 2021) - already loaded in Phase 0
        2. Encounters/appointments (visits)
        3. Procedures (surgeries)
        4. Chemotherapy episodes
        5. Radiation episodes
        6. Imaging studies

        Each stage validates against WHO 2021 expected treatment paradigm
        """

        events = []

        # Track Phase 2 timeline construction attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_timeline_construction')

        # STAGE 0: Add molecular diagnosis as anchor event
        print("  Stage 0: Molecular diagnosis")
        if self.who_2021_classification.get('who_2021_diagnosis'):
            events.append({
                'event_type': 'molecular_diagnosis',
                'event_date': None,  # Molecular diagnosis is not temporally anchored initially
                'stage': 0,
                'source': 'WHO_2021_CLASSIFICATIONS',
                'description': f"Molecular diagnosis: {self.who_2021_classification['who_2021_diagnosis']}",
                'who_2021_diagnosis': self.who_2021_classification.get('who_2021_diagnosis'),
                'molecular_subtype': self.who_2021_classification.get('molecular_subtype'),
                'grade': self.who_2021_classification.get('grade'),
                'expected_protocols': self.who_2021_classification.get('recommended_protocols')
            })
            print(f"    ✅ WHO 2021: {self.who_2021_classification['who_2021_diagnosis']}")
        else:
            print(f"    ⚠️  No WHO 2021 classification available")

        # STAGE 1: Encounters/appointments (visits)
        print("  Stage 1: Encounters/appointments")

        # Track visits extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_visits_extraction')

        visit_count = 0
        for record in self.structured_data.get('visits', []):
            events.append({
                'event_type': 'visit',
                'event_date': record.get('visit_date'),
                'stage': 1,
                'source': 'v_visits_unified',
                'description': f"{record.get('visit_type', '')} visit",
                'visit_type': record.get('visit_type')
            })
            visit_count += 1
        print(f"    ✅ Added {visit_count} encounters/appointments")

        # Track visits success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_visits_extraction', record_count=visit_count)

        # STAGE 2: Procedures (surgeries)
        print("  Stage 2: Procedures (surgeries)")

        # Track procedures extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_procedures_extraction')

        surgery_count = 0
        for record in self.structured_data.get('procedures', []):
            # V4.1 STEP 7: Create clinical_features dict for surgery events
            clinical_features = {}
            if record.get('v41_institution'):
                clinical_features['institution'] = record['v41_institution']
            if record.get('v41_tumor_location'):
                clinical_features['tumor_location'] = record['v41_tumor_location']

            # V2 STEP 5: Add cross-resource annotation for provenance tracking
            v2_annotation = {}
            if record.get('specimen_id'):
                v2_annotation['specimen_id'] = record['specimen_id']
            if record.get('proc_encounter_reference'):
                v2_annotation['encounter_id'] = record['proc_encounter_reference']
            if record.get('performer_org_id'):
                v2_annotation['performer_org_id'] = record['performer_org_id']
            if record.get('procedure_fhir_id'):
                v2_annotation['procedure_id'] = record['procedure_fhir_id']

            event = {
                'event_type': 'surgery',
                'event_date': record.get('proc_performed_date_time', '').split()[0] if record.get('proc_performed_date_time') else '',
                'stage': 2,
                'source': 'v_procedures_tumor',
                'description': record.get('proc_code_text'),
                'surgery_type': record.get('surgery_type'),
                'proc_performed_datetime': record.get('proc_performed_date_time')
            }
            # Add clinical_features if not empty
            if clinical_features:
                event['clinical_features'] = clinical_features

            # Add V2 annotation if not empty
            if v2_annotation:
                event['v2_annotation'] = v2_annotation

            events.append(event)
            surgery_count += 1
        print(f"    ✅ Added {surgery_count} surgical procedures")

        # Track procedures success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_procedures_extraction', record_count=surgery_count)

        # Validate against expected paradigm
        if surgery_count == 0 and self.who_2021_classification.get('who_2021_diagnosis'):
            print(f"    ⚠️  WARNING: No surgeries found for patient with {self.who_2021_classification.get('who_2021_diagnosis')}")

        # STAGE 3: Chemotherapy episodes with V4.8 intelligent date adjudication
        print("  Stage 3: Chemotherapy episodes (V4.8: Intelligent date adjudication)")

        # Track chemotherapy extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_chemotherapy_extraction')

        chemo_episode_count = 0
        chemo_adjudication_log = []

        for record in self.structured_data.get('chemotherapy', []):
            # V4.8: Intelligently adjudicate start/end dates using ALL available fields
            start_date, end_date, adjud_log = adjudicate_chemotherapy_dates(record)

            # Log adjudication decision
            drug_names = record.get('episode_drug_names', '') or record.get('medication_name', 'Unknown')
            logger.info(f"    V4.8 Adjudication: {drug_names} - {adjud_log}")
            chemo_adjudication_log.append({
                'drug': drug_names,
                'start_date': start_date,
                'end_date': end_date,
                'adjudication': adjud_log
            })

            # Only create events if we have at least a start date
            if start_date:
                # Start event
                events.append({
                    'event_type': 'chemotherapy_start',
                    'event_date': start_date,
                    'stage': 3,
                    'source': 'v_chemo_treatment_episodes',
                    'description': f"Chemotherapy started: {drug_names}",
                    'episode_drug_names': drug_names,
                    'episode_start_datetime': start_date,
                    'episode_end_datetime': end_date,
                    'medication_dosage_instructions': record.get('medication_dosage_instructions'),
                    'v48_adjudication': adjud_log,  # V4.8: Include adjudication provenance
                    # V4.8.1: COMPREHENSIVE FIELDS - Include RxNorm, drug categories, protocols
                    'chemo_preferred_name': record.get('chemo_preferred_name'),
                    'chemo_drug_id': record.get('chemo_drug_id'),
                    'chemo_drug_category': record.get('chemo_drug_category'),
                    'episode_drug_categories': record.get('episode_drug_categories'),
                    'episode_care_plan_title': record.get('episode_care_plan_title'),
                    'episode_care_plan_id': record.get('episode_care_plan_id'),
                    'episode_care_plan_status': record.get('episode_care_plan_status'),
                    'medication_count': record.get('medication_count'),
                    'unique_drug_count': record.get('unique_drug_count')
                })

                # End event (if end date available)
                if end_date:
                    events.append({
                        'event_type': 'chemotherapy_end',
                        'event_date': end_date,
                        'stage': 3,
                        'source': 'v_chemo_treatment_episodes',
                        'description': f"Chemotherapy ended: {drug_names}",
                        'episode_drug_names': drug_names,
                        'v48_adjudication': adjud_log  # V4.8: Include adjudication provenance
                    })

                chemo_episode_count += 1
            else:
                logger.warning(f"    ⚠️  Skipping chemotherapy record - no start date found for {drug_names}")

        print(f"    ✅ Added {chemo_episode_count} chemotherapy episodes (V4.8: Used intelligent date adjudication)")

        # Track chemotherapy success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_chemotherapy_extraction', record_count=chemo_episode_count)

        # V4.8: Log summary of adjudication decisions
        if chemo_adjudication_log:
            logger.info(f"    V4.8: Adjudicated {len(chemo_adjudication_log)} chemotherapy records using 5-tier fallback hierarchy")

        # Validate against expected paradigm
        expected_chemo = self.who_2021_classification.get('recommended_protocols', {}).get('chemotherapy')
        if expected_chemo:
            print(f"    📋 Expected per WHO 2021: {expected_chemo}")
            if chemo_episode_count == 0:
                print(f"    ⚠️  WARNING: No chemotherapy episodes found, but WHO 2021 recommends: {expected_chemo}")

        # STAGE 4: Radiation episodes
        print("  Stage 4: Radiation episodes")

        # Track radiation extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_radiation_extraction')

        radiation_episode_count = 0
        for record in self.structured_data.get('radiation', []):
            # Start event
            events.append({
                'event_type': 'radiation_start',
                'event_date': record.get('episode_start_date'),
                'stage': 4,
                'source': 'v_radiation_episode_enrichment',
                'description': f"Radiation started: {record.get('total_dose_cgy', '')} cGy",
                'total_dose_cgy': record.get('total_dose_cgy'),
                'radiation_fields': record.get('radiation_fields'),
                'episode_start_date': record.get('episode_start_date'),
                'episode_end_date': record.get('episode_end_date'),
                # V4.8.1: COMPREHENSIVE FIELDS - Include appointment data, care plans, quality metrics
                'total_appointments': record.get('total_appointments'),
                'fulfilled_appointments': record.get('fulfilled_appointments'),
                'booked_appointments': record.get('booked_appointments'),
                'appointment_fulfillment_rate_pct': record.get('appointment_fulfillment_rate_pct'),
                'care_plan_titles': record.get('care_plan_titles'),
                'total_care_plans': record.get('total_care_plans'),
                'enrichment_score': record.get('enrichment_score'),
                'data_completeness_tier': record.get('data_completeness_tier'),
                'treatment_phase_coverage': record.get('treatment_phase_coverage')
            })
            # End event
            if record.get('episode_end_date'):
                events.append({
                    'event_type': 'radiation_end',
                    'event_date': record.get('episode_end_date'),
                    'stage': 4,
                    'source': 'v_radiation_episode_enrichment',
                    'description': f"Radiation completed: {record.get('total_dose_cgy', '')} cGy",
                    'total_dose_cgy': record.get('total_dose_cgy')
                })
            radiation_episode_count += 1
        print(f"    ✅ Added {radiation_episode_count} radiation episodes")

        # Track radiation success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_radiation_extraction', record_count=radiation_episode_count)

        # Validate against expected paradigm
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation')
        if expected_radiation:
            print(f"    📋 Expected per WHO 2021: {expected_radiation}")
            if radiation_episode_count == 0:
                print(f"    ⚠️  WARNING: No radiation episodes found, but WHO 2021 recommends: {expected_radiation}")

        # STAGE 5: Imaging studies
        print("  Stage 5: Imaging studies")

        # Track imaging extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_imaging_extraction')

        imaging_count = 0
        for record in self.structured_data.get('imaging', []):
            # V4.1 STEP 7: Create clinical_features dict for imaging events
            clinical_features = {}
            if record.get('v41_institution'):
                clinical_features['institution'] = record['v41_institution']
            if record.get('v41_tumor_location'):
                clinical_features['tumor_location'] = record['v41_tumor_location']

            # V2 STEP 5: Add cross-resource annotation for provenance tracking
            v2_annotation = {}
            if record.get('binary_content_id'):
                v2_annotation['binary_content_id'] = record['binary_content_id']
            if record.get('performer_org_id'):
                v2_annotation['performer_org_id'] = record['performer_org_id']

            event = {
                'event_type': 'imaging',
                'event_date': record.get('imaging_date'),
                'stage': 5,
                'source': 'v_imaging',
                'description': f"{record.get('imaging_modality', '')} imaging",
                'imaging_modality': record.get('imaging_modality'),
                'report_conclusion': record.get('report_conclusion'),
                'result_diagnostic_report_id': record.get('result_diagnostic_report_id'),
                'diagnostic_report_id': record.get('diagnostic_report_id')
            }
            # Add clinical_features if not empty
            if clinical_features:
                event['clinical_features'] = clinical_features

            # Add V2 annotation if not empty
            if v2_annotation:
                event['v2_annotation'] = v2_annotation

            events.append(event)
            imaging_count += 1
        print(f"    ✅ Added {imaging_count} imaging studies")

        # Track imaging success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_imaging_extraction', record_count=imaging_count)

        # STAGE 6: Add pathology/diagnosis events (already integrated in Stage 0, but keep granular records)
        print("  Stage 6: Pathology events (granular)")

        # Track pathology extraction
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase2_pathology_extraction')

        pathology_count = 0
        for record in self.structured_data.get('pathology', []):
            events.append({
                'event_type': 'pathology_record',
                'event_date': record.get('diagnostic_date'),
                'stage': 6,
                'source': 'v_pathology_diagnostics',
                'description': record.get('diagnostic_name'),
                'component_name': record.get('component_name'),
                'result_value': record.get('result_value'),
                'extraction_priority': record.get('extraction_priority'),
                'document_category': record.get('document_category')
            })
            pathology_count += 1
        print(f"    ✅ Added {pathology_count} pathology records")

        # Track pathology success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_pathology_extraction', record_count=pathology_count)

        # Sort chronologically (None dates go to end)
        events.sort(key=lambda x: (x.get('event_date') is None, x.get('event_date', '')))

        # Add sequence numbers
        for i, event in enumerate(events, 1):
            event['event_sequence'] = i

        self.timeline_events = events

        # Track overall Phase 2 success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase2_timeline_construction', record_count=len(events))

        print(f"\n  ✅ Timeline construction complete: {len(events)} total events across 7 stages")
        print(f"     Stage 0: 1 molecular diagnosis anchor")
        print(f"     Stage 1: {visit_count} visits")
        print(f"     Stage 2: {surgery_count} surgeries")
        print(f"     Stage 3: {chemo_episode_count} chemotherapy episodes")
        print(f"     Stage 4: {radiation_episode_count} radiation episodes")
        print(f"     Stage 5: {imaging_count} imaging studies")
        print(f"     Stage 6: {pathology_count} pathology records")

    def _phase2_5_assign_treatment_ordinality(self):
        """
        Phase 2.5: Assign treatment ordinality labels (V4 ENHANCEMENT)

        This post-processes the timeline to assign:
          - Surgery ordinality (surgery #1, #2, #3)
          - Chemotherapy lines (1st-line, 2nd-line, 3rd-line)
          - Radiation courses (course #1, #2, #3)
          - Timing context (upfront, adjuvant, salvage)

        Enables queries like: "What was the first-line chemotherapy?"
        """
        print("\n" + "="*80)
        print("PHASE 2.5: ASSIGN TREATMENT ORDINALITY (V4 Enhancement)")
        print("="*80)

        # Import treatment ordinality module
        from lib.treatment_ordinality import TreatmentOrdinalityProcessor

        # Initialize processor with current timeline
        processor = TreatmentOrdinalityProcessor(self.timeline_events)

        # Assign all ordinality labels
        processor.assign_all_ordinality()

        # Generate and log summary
        summary = processor.get_treatment_summary()
        print(f"\n  ✅ Treatment ordinality assigned:")
        print(f"     Total surgeries: {summary['total_surgeries']}")
        print(f"     Chemotherapy lines: {summary['total_chemo_lines']}")
        print(f"     Radiation courses: {summary['total_radiation_courses']}")
        print(f"     Timing context: {summary['upfront_treatments']} upfront, "
              f"{summary['adjuvant_treatments']} adjuvant, {summary['salvage_treatments']} salvage")

        # V4.6 GAP #2: Compute treatment change reasons
        self._compute_treatment_change_reasons()

        # V4.6 GAP #3: Enrich event relationships
        self._enrich_event_relationships()

        # V4.6 GAP #5: Add RANO assessment to imaging events
        self._enrich_imaging_with_rano_assessment()

    def _phase3_identify_extraction_gaps(self):
        """Phase 3: Identify gaps in structured data requiring binary extraction"""

        # Track Phase 3 gap identification attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase3_gap_identification')

        gaps = []

        # Gap type 1: Surgeries without EOR - query v_binary_files for operative notes
        surgery_events = [e for e in self.timeline_events if e['event_type'] == 'surgery']
        for surgery in surgery_events:
            if not surgery.get('extent_of_resection'):
                # Query v_binary_files for operative notes near this surgery date
                # Use event_date if available, otherwise extract date from proc_performed_datetime
                event_date = surgery.get('event_date')
                if not event_date or event_date == '':
                    # Extract date from proc_performed_datetime (format: "YYYY-MM-DD HH:MM:SS.SSS")
                    proc_dt = surgery.get('proc_performed_datetime', '')
                    if proc_dt and proc_dt != '':
                        event_date = proc_dt.split(' ')[0]  # Get date part only

                # V4.2: Use V2 enhanced document discovery with encounter linkage
                v2_annotation = surgery.get('v2_annotation', {})
                encounter_id = v2_annotation.get('encounter_id')
                procedure_fhir_id = v2_annotation.get('procedure_id')

                operative_note_binary = self._find_operative_note_binary_v2(
                    procedure_fhir_id=procedure_fhir_id,
                    encounter_id=encounter_id,
                    surgery_date=event_date
                )

                gaps.append({
                    'gap_type': 'missing_eor',
                    'priority': 'HIGHEST',  # Changed to HIGHEST - EOR is critical
                    'event_date': event_date,
                    'surgery_type': surgery.get('surgery_type'),
                    'proc_performed_datetime': surgery.get('proc_performed_datetime'),
                    'recommended_action': 'Extract EOR from operative note binary',
                    'clinical_significance': 'EOR is critical for prognosis and protocol validation',
                    'medgemma_target': operative_note_binary if operative_note_binary else None
                })

        # Gap type 2: Radiation without comprehensive dose details - query v_radiation_documents
        radiation_events = [e for e in self.timeline_events if e['event_type'] == 'radiation_start']
        for radiation in radiation_events:
            # Check if we're missing ANY critical radiation fields
            missing_fields = []
            if not radiation.get('total_dose_cgy'):
                missing_fields.append('total_dose_cgy')
            if not radiation.get('radiation_fields'):
                missing_fields.append('radiation_fields')

            # Always try to extract comprehensive radiation details
            if missing_fields or True:  # Always extract for radiation to get full details
                event_date = radiation.get('event_date')

                # V4.2: Use V2 enhanced document discovery with encounter linkage
                v2_annotation = radiation.get('v2_annotation', {})
                encounter_id = v2_annotation.get('encounter_id')

                radiation_doc = self._find_radiation_document_v2(
                    encounter_id=encounter_id,
                    radiation_date=event_date
                )

                gaps.append({
                    'gap_type': 'missing_radiation_details',
                    'priority': 'HIGHEST',  # Changed to HIGHEST - radiation details critical
                    'event_date': event_date,
                    'missing_fields': missing_fields,
                    'recommended_action': 'Extract comprehensive radiation details including craniospinal/focal doses',
                    'clinical_significance': 'Complete radiation dosimetry required for WHO 2021 protocol validation',
                    'medgemma_target': radiation_doc if radiation_doc else None
                })

        # Gap type 3: Imaging without clear response assessment
        imaging_events = [e for e in self.timeline_events if e['event_type'] == 'imaging']
        for imaging in imaging_events:
            conclusion = imaging.get('report_conclusion', '')
            # Vague conclusion = NULL, empty, OR <50 characters
            if not conclusion or len(conclusion) < 50:
                # Get diagnostic report ID for MedGemma extraction
                diagnostic_report_id = imaging.get('diagnostic_report_id') or imaging.get('result_diagnostic_report_id')

                gaps.append({
                    'gap_type': 'imaging_conclusion',
                    'priority': 'MEDIUM',
                    'event_date': imaging.get('event_date'),
                    'imaging_modality': imaging.get('imaging_modality'),
                    'diagnostic_report_id': diagnostic_report_id,
                    'recommended_action': 'Extract full radiology report for detailed tumor measurements',
                    'clinical_significance': 'Detailed measurements needed for RANO response assessment',
                    'medgemma_target': f'DiagnosticReport/{diagnostic_report_id}' if diagnostic_report_id else 'MISSING_REFERENCE'
                })

        # Gap type 4: Chemotherapy without protocol details
        chemotherapy_events = [e for e in self.timeline_events if e.get('event_type', '').startswith('chemotherapy')]
        for chemo in chemotherapy_events:
            # Check if we're missing ANY critical chemotherapy fields
            missing_fields = []
            if not chemo.get('protocol_name'):
                missing_fields.append('protocol_name')
            if not chemo.get('on_protocol_status'):
                missing_fields.append('on_protocol_status')
            if not chemo.get('agent_names'):
                missing_fields.append('agent_names')

            # Identify gaps if critical fields missing
            if missing_fields:
                event_date = chemo.get('event_date') or chemo.get('med_admin_effective_datetime')
                chemo_doc = self._find_chemotherapy_document(event_date)

                gaps.append({
                    'gap_type': 'missing_chemotherapy_details',
                    'priority': 'HIGH',
                    'event_date': event_date,
                    'missing_fields': missing_fields,
                    'recommended_action': 'Extract protocol name, enrollment status, agents, and therapy changes',
                    'clinical_significance': 'Protocol tracking and therapy modification reasons required for treatment trajectory analysis',
                    'medgemma_target': chemo_doc if chemo_doc else None
                })

        self.extraction_gaps = gaps

        # Track Phase 3 success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase3_gap_identification', record_count=len(gaps))

        print(f"  ✅ Identified {len(gaps)} extraction opportunities")
        gap_counts = {}
        for gap in gaps:
            gap_type = gap['gap_type']
            gap_counts[gap_type] = gap_counts.get(gap_type, 0) + 1
        for gap_type, count in sorted(gap_counts.items()):
            print(f"     {gap_type}: {count}")

    def _find_operative_note_binary_v2(
        self,
        procedure_fhir_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        surgery_date: Optional[str] = None
    ) -> Optional[str]:
        """
        V2 Enhanced: Find operative notes using 5-tier discovery strategy

        This method implements V4.2 Enhancement #2: V2 Document Discovery
        Uses encounter-based lookup with multiple fallback strategies.

        Strategy:
        1. TIER 1 (PREFERRED): Direct encounter match via v_document_reference_enriched
           - Uses encounter_id to find OP notes with keywords: operative, op note, surgical
        2. TIER 2 (FALLBACK): Lookup encounter from procedure table if not provided
           - Queries procedure table for encounter_reference, then recursive Tier 1
        3. TIER 3 (LEGACY): Temporal document matching (±7 days from surgery date)
           - Uses v_binary_files view with date proximity search
        4. TIER 4 (ENCOUNTER DATE MATCH): Find OP notes via encounter date matching
           - Handles "encounter mismatch" (OP notes linked to different encounter same day)
           - Searches by patient + keywords + encounter date within ±1 day
           - Solves admission vs surgical encounter problem
        5. TIER 5 (ALTERNATIVE CLINICAL NOTES): Progress notes, H&P, discharge summaries
           - Fallback to other clinical documentation when OP notes don't exist
           - Searches within ±3 days, prioritizes discharge > encounter summary > H&P > progress
           - May contain surgical details, EOR, complications

        Args:
            procedure_fhir_id: FHIR ID of the procedure (e.g., "Procedure/abc123")
            encounter_id: Encounter ID from v2_annotation (e.g., "Encounter/xyz789")
            surgery_date: Date of surgery (YYYY-MM-DD) - used for Tier 3, 4, 5 fallback

        Returns:
            Binary ID if found (e.g., "Binary/12345"), None otherwise
        """
        # Track which tier we use for performance metrics
        tier_used = None

        # TIER 1: Use provided encounter_id
        if encounter_id:
            try:
                logger.debug(f"V2 Tier 1: Using provided encounter_id {encounter_id}")
                query = f"""
                SELECT
                    binary_id,
                    doc_type_text,
                    doc_date,
                    document_category,
                    custodian_org_name
                FROM fhir_prd_db.v_document_reference_enriched
                WHERE encounter_id = '{encounter_id}'
                  AND (
                      LOWER(doc_type_text) LIKE '%operative%'
                      OR LOWER(doc_type_text) LIKE '%procedure%'
                      OR LOWER(doc_type_text) LIKE '%surgical%'
                      OR LOWER(doc_type_text) LIKE '%op%note%'
                      OR LOWER(doc_type_text) LIKE 'op note%'
                      OR document_category = 'operative_note'
                  )
                ORDER BY
                    CASE
                        WHEN LOWER(doc_type_text) LIKE '%operative%' THEN 1
                        WHEN LOWER(doc_type_text) LIKE '%surgical%' THEN 2
                        WHEN LOWER(doc_type_text) LIKE '%procedure%' THEN 3
                        ELSE 4
                    END,
                    doc_date DESC
                LIMIT 1
                """

                results = query_athena(query, f"V2: Finding operative note via encounter {encounter_id}", suppress_output=True)

                if results and results[0].get('binary_id'):
                    binary_id = results[0]['binary_id']
                    tier_used = "v2_tier1_encounter_provided"
                    logger.info(f"V2 Tier 1 ✓: Found operative note {binary_id} via provided encounter_id")
                    if hasattr(self, 'v2_document_discovery_stats'):
                        self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                    return binary_id

            except Exception as e:
                logger.warning(f"V2 Tier 1 failed: {e}")

        # TIER 2: Query procedure table for encounter_reference
        if procedure_fhir_id and not encounter_id:
            try:
                logger.debug(f"V2 Tier 2: Looking up encounter_reference from procedure {procedure_fhir_id}")
                # Extract procedure ID from FHIR reference
                proc_id = procedure_fhir_id.replace('Procedure/', '')

                query = f"""
                SELECT encounter_reference
                FROM fhir_prd_db.procedure
                WHERE id = '{proc_id}'
                LIMIT 1
                """

                results = query_athena(query, f"V2: Finding encounter for procedure {proc_id}", suppress_output=True)

                if results and results[0].get('encounter_reference'):
                    encounter_ref = results[0]['encounter_reference']
                    logger.debug(f"V2 Tier 2: Found encounter_reference {encounter_ref}")

                    # Recursive call with encounter_id
                    return self._find_operative_note_binary_v2(
                        procedure_fhir_id=procedure_fhir_id,
                        encounter_id=encounter_ref,
                        surgery_date=surgery_date
                    )

            except Exception as e:
                logger.warning(f"V2 Tier 2 failed: {e}")

        # TIER 3: Temporal fallback (legacy method)
        if surgery_date:
            logger.debug(f"V2 Tier 3: Falling back to temporal matching for {surgery_date}")
            binary_id = self._find_operative_note_binary(surgery_date)
            if binary_id:
                tier_used = "v2_tier3_temporal_fallback"
                logger.info(f"V2 Tier 3 (FALLBACK): Found operative note {binary_id} via temporal matching")
                if hasattr(self, 'v2_document_discovery_stats'):
                    self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                return binary_id

        # TIER 4: Date-based encounter lookup (handles encounter mismatch cases)
        if surgery_date:
            try:
                logger.debug(f"V2 Tier 4: Looking for OP notes via encounter date matching for {surgery_date}")
                query = f"""
                SELECT
                    drc.content_attachment_url as binary_id,
                    dr.type_text as doc_type_text,
                    e.period_start as encounter_start,
                    dce.context_encounter_reference as encounter_id
                FROM fhir_prd_db.document_reference dr
                JOIN fhir_prd_db.document_reference_context_encounter dce
                    ON dr.id = dce.document_reference_id
                JOIN fhir_prd_db.document_reference_content drc
                    ON dr.id = drc.document_reference_id
                JOIN fhir_prd_db.encounter e
                    ON dce.context_encounter_reference = e.id
                WHERE dr.subject_reference = '{self.patient_id}'
                    AND (
                        LOWER(dr.type_text) LIKE '%operative%'
                        OR LOWER(dr.type_text) LIKE '%op%note%'
                        OR LOWER(dr.type_text) LIKE 'op note%'
                        OR LOWER(dr.type_text) LIKE '%surgical%'
                        OR LOWER(dr.type_text) LIKE '%procedure%'
                    )
                    AND DATE(e.period_start) BETWEEN DATE '{surgery_date}' - INTERVAL '1' DAY
                                                 AND DATE '{surgery_date}' + INTERVAL '1' DAY
                ORDER BY
                    CASE
                        WHEN LOWER(dr.type_text) LIKE '%operative%complete%' THEN 1
                        WHEN LOWER(dr.type_text) LIKE '%op%note%complete%' THEN 2
                        WHEN LOWER(dr.type_text) LIKE '%operative%' THEN 3
                        WHEN LOWER(dr.type_text) LIKE '%op%note%' THEN 4
                        ELSE 5
                    END,
                    e.period_start DESC
                LIMIT 1
                """

                results = query_athena(query, f"V2 Tier 4: Finding OP note via encounter date for {surgery_date}", suppress_output=True)

                if results and results[0].get('binary_id'):
                    binary_id = results[0]['binary_id']
                    encounter_id = results[0].get('encounter_id', 'unknown')
                    doc_type = results[0].get('doc_type_text', 'unknown')
                    tier_used = "v2_tier4_encounter_date_match"
                    logger.info(f"V2 Tier 4 ✓: Found operative note {binary_id} (type: {doc_type}) via encounter date matching (encounter: {encounter_id})")
                    if hasattr(self, 'v2_document_discovery_stats'):
                        self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                    return binary_id

            except Exception as e:
                logger.warning(f"V2 Tier 4 failed: {e}")

        # TIER 5: Alternative clinical notes (progress notes, H&P, discharge summaries, encounter summaries)
        if surgery_date:
            try:
                logger.debug(f"V2 Tier 5: Looking for alternative clinical notes for {surgery_date}")
                query = f"""
                SELECT
                    drc.content_attachment_url as binary_id,
                    dr.type_text as doc_type_text,
                    e.period_start as encounter_start,
                    dce.context_encounter_reference as encounter_id
                FROM fhir_prd_db.document_reference dr
                JOIN fhir_prd_db.document_reference_context_encounter dce
                    ON dr.id = dce.document_reference_id
                JOIN fhir_prd_db.document_reference_content drc
                    ON dr.id = drc.document_reference_id
                JOIN fhir_prd_db.encounter e
                    ON dce.context_encounter_reference = e.id
                WHERE dr.subject_reference = '{self.patient_id}'
                    AND (
                        LOWER(dr.type_text) LIKE '%progress%note%'
                        OR LOWER(dr.type_text) LIKE '%h&p%'
                        OR LOWER(dr.type_text) LIKE '%history%physical%'
                        OR LOWER(dr.type_text) LIKE '%discharge%summary%'
                        OR LOWER(dr.type_text) LIKE '%encounter%summary%'
                        OR LOWER(dr.type_text) LIKE '%physician%note%'
                        OR LOWER(dr.type_text) LIKE '%clinical%note%'
                        OR LOWER(dr.type_text) LIKE '%consult%'
                    )
                    AND DATE(e.period_start) BETWEEN DATE '{surgery_date}' - INTERVAL '3' DAY
                                                 AND DATE '{surgery_date}' + INTERVAL '3' DAY
                ORDER BY
                    CASE
                        WHEN LOWER(dr.type_text) LIKE '%discharge%summary%' THEN 1
                        WHEN LOWER(dr.type_text) LIKE '%encounter%summary%' THEN 2
                        WHEN LOWER(dr.type_text) LIKE '%h&p%' THEN 3
                        WHEN LOWER(dr.type_text) LIKE '%history%physical%' THEN 4
                        WHEN LOWER(dr.type_text) LIKE '%progress%' THEN 5
                        ELSE 6
                    END,
                    ABS(DATE_DIFF('day', DATE(e.period_start), DATE '{surgery_date}'))
                LIMIT 1
                """

                results = query_athena(query, f"V2 Tier 5: Finding alternative clinical notes for {surgery_date}", suppress_output=True)

                if results and results[0].get('binary_id'):
                    binary_id = results[0]['binary_id']
                    encounter_id = results[0].get('encounter_id', 'unknown')
                    doc_type = results[0].get('doc_type_text', 'unknown')
                    tier_used = "v2_tier5_alternative_clinical_notes"
                    logger.info(f"V2 Tier 5 ✓: Found alternative clinical note {binary_id} (type: {doc_type}) via encounter date (encounter: {encounter_id})")
                    logger.info(f"V2 Tier 5: Using '{doc_type}' as fallback for operative note - may contain surgical details")
                    if hasattr(self, 'v2_document_discovery_stats'):
                        self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                    return binary_id

            except Exception as e:
                logger.warning(f"V2 Tier 5 failed: {e}")

        # TIER 6: Direct document_reference query with comprehensive keyword matching (bypasses encounter join)
        # This catches cases where documents exist but aren't properly linked via encounter junction table
        if surgery_date:
            try:
                logger.debug(f"V2 Tier 6: Querying document_reference source table directly for {surgery_date}")
                query = f"""
                SELECT
                    drc.content_attachment_url as binary_id,
                    dr.type_text as doc_type_text,
                    dr.date as doc_date,
                    ABS(DATE_DIFF('day', DATE(SUBSTR(dr.date, 1, 10)), DATE '{surgery_date}')) as days_from_surgery
                FROM fhir_prd_db.document_reference dr
                JOIN fhir_prd_db.document_reference_content drc
                    ON dr.id = drc.document_reference_id
                WHERE dr.subject_reference = '{self.patient_id}'
                    AND dr.date IS NOT NULL
                    AND LENGTH(dr.date) >= 10
                    AND (
                        LOWER(dr.type_text) LIKE '%operative%'
                        OR LOWER(dr.type_text) LIKE '%op%note%'
                        OR LOWER(dr.type_text) LIKE '%op note%'
                        OR LOWER(dr.type_text) LIKE '%surgical%'
                        OR LOWER(dr.type_text) LIKE '%procedure%note%'
                        OR dr.type_text = 'Operative Record'
                        OR dr.type_text = 'External Operative Note'
                    )
                    AND ABS(DATE_DIFF('day', DATE(SUBSTR(dr.date, 1, 10)), DATE '{surgery_date}')) <= 7
                    AND drc.content_attachment_url IS NOT NULL
                ORDER BY
                    CASE
                        WHEN LOWER(dr.type_text) LIKE '%op%note%complete%' THEN 1
                        WHEN LOWER(dr.type_text) LIKE '%operative%complete%' THEN 2
                        WHEN LOWER(dr.type_text) LIKE '%op%note%' THEN 3
                        WHEN LOWER(dr.type_text) LIKE '%operative%' THEN 4
                        WHEN LOWER(dr.type_text) LIKE '%surgical%' THEN 5
                        ELSE 6
                    END,
                    days_from_surgery ASC
                LIMIT 1
                """

                results = query_athena(query, f"V2 Tier 6: Direct document_reference query for {surgery_date}", suppress_output=True)

                if results and results[0].get('binary_id'):
                    binary_id = results[0]['binary_id']
                    doc_type = results[0].get('doc_type_text', 'unknown')
                    days_diff = results[0].get('days_from_surgery', '?')
                    tier_used = "v2_tier6_direct_source_table"
                    logger.info(f"V2 Tier 6 ✓: Found operative note {binary_id} (type: {doc_type}) via direct source table query ({days_diff} days from surgery)")
                    logger.info(f"V2 Tier 6: This document was missing from encounter-based queries - possible encounter mismatch or junction table gap")
                    if hasattr(self, 'v2_document_discovery_stats'):
                        self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                    return binary_id

            except Exception as e:
                logger.warning(f"V2 Tier 6 failed: {e}")

        # All 6 tiers failed
        logger.warning(f"V2: No operative note or clinical note found (all 6 tiers exhausted)")
        if hasattr(self, 'v2_document_discovery_stats'):
            self.v2_document_discovery_stats['v2_not_found'] = self.v2_document_discovery_stats.get('v2_not_found', 0) + 1
        return None

    def _find_operative_note_binary(self, surgery_date: str) -> Optional[str]:
        """
        Query v_binary_files to find operative notes for a surgery (LEGACY - Tier 3 fallback)

        NOTE: This is the legacy temporal matching method. V4.2+ should use
        _find_operative_note_binary_v2() which uses encounter linkage for 95%+ success rate.

        Args:
            surgery_date: Date of surgery (YYYY-MM-DD)

        Returns:
            Binary ID if found, None otherwise
        """
        if not surgery_date:
            return None

        try:
            # Query v_binary_files for operative notes within ±7 days of surgery
            query = f"""
            SELECT binary_id, dr_type_text, dr_date, dr_description
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND (dr_type_text = 'Operative Record'
                   OR dr_type_text = 'External Operative Note')
              AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE))) <= 7
            ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{surgery_date}' AS DATE)))
            LIMIT 1
            """

            results = query_athena(query, f"Finding operative note for surgery on {surgery_date}", suppress_output=True)

            if results:
                binary_id = results[0].get('binary_id')
                logger.info(f"Found operative note Binary/{binary_id} for surgery on {surgery_date}")
                return f"Binary/{binary_id}"
            else:
                logger.debug(f"No operative note found for surgery on {surgery_date}")
                return None

        except Exception as e:
            logger.error(f"Error querying operative notes for {surgery_date}: {e}")
            return None

    def _find_radiation_document_v2(
        self,
        encounter_id: Optional[str] = None,
        radiation_date: Optional[str] = None
    ) -> Optional[str]:
        """
        V2 Enhanced: Find radiation documents using encounter linkage with temporal fallback

        This method implements V4.2 Enhancement #2: V2 Document Discovery Steps 3-4
        Uses encounter-based lookup for improved success rate.

        Strategy:
        1. TIER 1 (PREFERRED): Use encounter_id to query v2_document_reference_enriched
        2. TIER 2 (LEGACY): Fall back to temporal matching via v_radiation_documents

        Args:
            encounter_id: Encounter ID from v2_annotation (e.g., "Encounter/xyz789")
            radiation_date: Date of radiation start (YYYY-MM-DD) - used for Tier 2 fallback

        Returns:
            DocumentReference ID if found (e.g., "DocumentReference/12345"), None otherwise
        """
        tier_used = None

        # TIER 1: Use provided encounter_id
        if encounter_id:
            try:
                logger.debug(f"V2 Tier 1: Using provided encounter_id {encounter_id} for radiation doc")
                query = f"""
                SELECT
                    document_id,
                    binary_id,
                    doc_type_text,
                    doc_date,
                    document_category,
                    custodian_org_name
                FROM fhir_prd_db.v2_document_reference_enriched
                WHERE encounter_id = '{encounter_id}'
                  AND (
                      LOWER(doc_type_text) LIKE '%radiation%'
                      OR LOWER(doc_type_text) LIKE '%radiotherapy%'
                      OR LOWER(doc_type_text) LIKE '%oncology%'
                      OR LOWER(doc_type_text) LIKE '%treatment%'
                  )
                ORDER BY
                    CASE
                        WHEN LOWER(doc_type_text) LIKE '%radiation%' THEN 1
                        WHEN LOWER(doc_type_text) LIKE '%radiotherapy%' THEN 2
                        WHEN LOWER(doc_type_text) LIKE '%oncology%' THEN 3
                        ELSE 4
                    END,
                    doc_date DESC
                LIMIT 1
                """

                results = query_athena(query, f"V2: Finding radiation doc via encounter {encounter_id}", suppress_output=True)

                if results and results[0].get('document_id'):
                    doc_id = results[0]['document_id']
                    tier_used = "v2_tier1_encounter_provided"
                    logger.info(f"V2 Tier 1 ✓: Found radiation document {doc_id} via provided encounter_id")
                    if hasattr(self, 'v2_document_discovery_stats'):
                        self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                    return f"DocumentReference/{doc_id}"

            except Exception as e:
                logger.warning(f"V2 Tier 1 failed for radiation doc: {e}")

        # TIER 2: Temporal fallback (legacy method)
        if radiation_date:
            logger.debug(f"V2 Tier 2: Falling back to temporal matching for radiation on {radiation_date}")
            doc_ref = self._find_radiation_document(radiation_date)
            if doc_ref:
                tier_used = "v2_tier2_temporal_fallback"
                logger.info(f"V2 Tier 2 (FALLBACK): Found radiation document {doc_ref} via temporal matching")
                if hasattr(self, 'v2_document_discovery_stats'):
                    self.v2_document_discovery_stats[tier_used] = self.v2_document_discovery_stats.get(tier_used, 0) + 1
                return doc_ref

        # All tiers failed
        logger.warning(f"V2: No radiation document found (all tiers exhausted)")
        if hasattr(self, 'v2_document_discovery_stats'):
            self.v2_document_discovery_stats['v2_not_found'] = self.v2_document_discovery_stats.get('v2_not_found', 0) + 1
        return None

    def _map_gap_to_doc_type(self, gap_type: str) -> Optional[str]:
        """
        Map gap type to expected document type for Layer 1 validation

        Args:
            gap_type: Type of gap (e.g., 'missing_eor', 'missing_radiation_details')

        Returns:
            Expected document type key or None
        """
        gap_to_doc_type = {
            'missing_eor': 'operative_note',
            'missing_tumor_location': 'operative_note',
            'missing_laterality': 'operative_note',
            'missing_radiation_details': 'radiation_summary',
            'missing_radiation_dose': 'radiation_summary',
            'imaging_conclusion': 'imaging_report',
            'missing_chemotherapy_details': None  # Multiple possible doc types
        }
        return gap_to_doc_type.get(gap_type)

    def _validate_document_type(
        self,
        binary_id: str,
        expected_type: str
    ) -> bool:
        """
        V4.2+ Enhancement #1 Layer 1: Document Type Validation (Pre-Extraction)

        Verify document matches expected type before sending to MedGemma extraction.
        Prevents document mismatch errors (e.g., discharge summary sent to operative note prompt).

        Args:
            binary_id: FHIR Binary resource ID (e.g., "Binary/12345")
            expected_type: Expected document type key:
                - 'operative_note': Operative Record, Procedure Note
                - 'radiation_summary': Radiation Therapy Summary, Radiation Oncology Note
                - 'imaging_report': Diagnostic Imaging Report, Radiology Report
                - 'pathology_report': Pathology Report, Surgical Pathology

        Returns:
            True if document type matches expectation, False otherwise
        """
        if not binary_id:
            logger.warning("⚠️ Cannot validate document type: no binary_id provided")
            return False

        try:
            # Query v2_document_reference_enriched for document metadata
            query = f"""
                SELECT doc_type_text, document_category, document_confidence
                FROM fhir_prd_db.v2_document_reference_enriched
                WHERE binary_id = '{binary_id}'
                LIMIT 1
            """

            results = query_athena(
                query,
                f"V4.2+ Layer 1: Validating document type for {binary_id}",
                suppress_output=True
            )

            if not results or not results[0].get('doc_type_text'):
                logger.warning(f"⚠️ Could not verify document type for binary {binary_id} (no metadata)")
                # Track validation failures
                if hasattr(self, 'validation_stats'):
                    self.validation_stats['doc_type_validation_no_metadata'] = \
                        self.validation_stats.get('doc_type_validation_no_metadata', 0) + 1
                return False  # Fail-safe: reject if we can't verify

            doc_type = results[0]['doc_type_text']
            doc_category = results[0].get('document_category', '')

            # Fuzzy match for document type (case-insensitive, partial matching)
            type_matches = {
                'operative_note': [
                    'operative record', 'procedure note', 'operative report',
                    'surgical note', 'surgery note', 'operation note'
                ],
                'radiation_summary': [
                    'radiation therapy summary', 'radiation oncology note',
                    'radiotherapy summary', 'radiation treatment', 'oncology consult'
                ],
                'imaging_report': [
                    'diagnostic imaging report', 'radiology report',
                    'imaging report', 'mri report', 'ct report', 'diagnostic report'
                ],
                'pathology_report': [
                    'pathology report', 'surgical pathology', 'path report',
                    'pathology consultation', 'neuropathology'
                ]
            }

            # Get expected patterns
            expected_patterns = type_matches.get(expected_type, [])
            if not expected_patterns:
                logger.warning(f"⚠️ Unknown expected_type: {expected_type}")
                return False

            # Check if doc_type matches any expected pattern (case-insensitive)
            doc_type_lower = doc_type.lower()
            doc_category_lower = doc_category.lower() if doc_category else ''

            matched = any(
                pattern in doc_type_lower or pattern in doc_category_lower
                for pattern in expected_patterns
            )

            if matched:
                logger.info(f"✅ Document type validated: '{doc_type}' matches expected '{expected_type}'")
                # Track successful validation
                if hasattr(self, 'validation_stats'):
                    self.validation_stats['doc_type_validation_success'] = \
                        self.validation_stats.get('doc_type_validation_success', 0) + 1
                return True
            else:
                logger.warning(
                    f"⚠️ Document type mismatch: expected '{expected_type}', "
                    f"got doc_type='{doc_type}', category='{doc_category}'"
                )
                # Track mismatches
                if hasattr(self, 'validation_stats'):
                    self.validation_stats['doc_type_validation_mismatch'] = \
                        self.validation_stats.get('doc_type_validation_mismatch', 0) + 1
                return False

        except Exception as e:
            logger.error(f"❌ Error validating document type for {binary_id}: {e}")
            # Track errors
            if hasattr(self, 'validation_stats'):
                self.validation_stats['doc_type_validation_error'] = \
                    self.validation_stats.get('doc_type_validation_error', 0) + 1
            return False  # Fail-safe: reject on error

    def _validate_extraction_result(
        self,
        result: Dict[str, Any],
        gap_type: str,
        expected_schema: Optional[Dict[str, type]] = None
    ) -> Tuple[bool, List[str]]:
        """
        V4.2+ Enhancement #1 Layer 2: Extraction Result Validation (Post-Extraction)

        Validate MedGemma extraction result for semantic and structural correctness.
        Prevents integration of invalid/hallucinated/mismatched data into timeline.

        Args:
            result: Extracted data from MedGemma
            gap_type: Type of gap being filled (e.g., 'missing_eor', 'missing_radiation_dose')
            expected_schema: Optional dict mapping field names to expected types

        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        errors = []

        if not result:
            errors.append("Extraction result is empty")
            return False, errors

        # STEP 1: Check required fields (merged from original method)
        required_fields = {
            'missing_eor': ['extent_of_resection', 'surgeon_assessment'],
            'missing_radiation_details': [
                'date_at_radiation_start',
                'date_at_radiation_stop',
                'total_dose_cgy',
                'radiation_type'
            ],
            'imaging_conclusion': ['lesions', 'rano_assessment'],
            'missing_chemotherapy_details': [
                'protocol_name',
                'on_protocol_status',
                'agent_names'
            ]
        }

        # Field alternatives for validation
        field_alternatives = {
            'total_dose_cgy': [
                'total_dose_cgy',
                'radiation_focal_or_boost_dose',
                'completed_radiation_focal_or_boost_dose',
                'completed_craniospinal_or_whole_ventricular_radiation_dose'
            ]
        }

        required = required_fields.get(gap_type, [])
        for field in required:
            alternatives = field_alternatives.get(field, [field])
            field_found = False

            for alt_field in alternatives:
                if alt_field in result and result[alt_field] is not None and result[alt_field] != "":
                    field_found = True
                    break

            if not field_found:
                errors.append(field)  # Add missing required field to errors

        # STEP 2: Schema validation (if schema provided)
        if expected_schema:
            for field, field_type in expected_schema.items():
                if field not in result:
                    errors.append(f"Missing required field: {field}")
                elif result[field] is not None and not isinstance(result[field], field_type):
                    errors.append(
                        f"Field '{field}' has wrong type: "
                        f"expected {field_type.__name__}, got {type(result[field]).__name__}"
                    )

        # STEP 3: Gap-type specific semantic validation
        if gap_type == 'missing_eor':
            eor_value = result.get('extent_of_resection')
            valid_eor_values = ['GTR', 'NTR', 'STR', 'Biopsy', None]

            if eor_value not in valid_eor_values:
                errors.append(f"Invalid extent_of_resection value: '{eor_value}'")

            # Check for nonsensical text (likely document mismatch)
            if eor_value and len(str(eor_value)) > 50:
                errors.append(
                    f"Extent of resection value too long ({len(str(eor_value))} chars), "
                    f"likely extraction error: {str(eor_value)[:50]}..."
                )

        elif gap_type == 'missing_radiation_dose':
            dose = result.get('total_dose_cgy')

            if dose is not None:
                # Radiation dose sanity checks
                if not isinstance(dose, (int, float)):
                    errors.append(f"Invalid dose type: expected number, got {type(dose).__name__}")
                elif dose < 0 or dose > 10000:  # Typical range: 1800-6000 cGy
                    errors.append(f"Dose out of reasonable range (0-10000 cGy): {dose} cGy")

        elif gap_type == 'missing_tumor_location':
            location = result.get('tumor_location')

            if location:
                # Check if location is plausible (not generic text)
                generic_phrases = [
                    'patient was', 'discharged', 'follow-up', 'appointment',
                    'medication', 'vital signs', 'assessment', 'plan', 'hospital course'
                ]
                if any(phrase in location.lower() for phrase in generic_phrases):
                    errors.append(
                        f"Tumor location appears to be generic text (document mismatch): "
                        f"{location[:100]}"
                    )

                # Check location length
                if len(location) > 200:
                    errors.append(
                        f"Tumor location too long ({len(location)} chars), "
                        f"likely extracted wrong text: {location[:100]}..."
                    )

        elif gap_type == 'missing_laterality':
            laterality = result.get('laterality')
            valid_laterality = ['Left', 'Right', 'Bilateral', 'Midline', None]

            if laterality and laterality not in valid_laterality:
                errors.append(f"Invalid laterality value: '{laterality}'")

        # STEP 4: Confidence check
        confidence = result.get('confidence', 'MEDIUM')
        if confidence == 'LOW':
            errors.append(
                "Extraction confidence is LOW - may indicate document mismatch or unclear text"
            )

        # Track validation results
        is_valid = len(errors) == 0
        if hasattr(self, 'validation_stats'):
            if is_valid:
                self.validation_stats['extraction_validation_success'] = \
                    self.validation_stats.get('extraction_validation_success', 0) + 1
            else:
                self.validation_stats['extraction_validation_failed'] = \
                    self.validation_stats.get('extraction_validation_failed', 0) + 1

        return is_valid, errors

    def _log_failed_extraction(
        self,
        gap: Dict[str, Any],
        binary_id: Optional[str],
        result: Dict[str, Any],
        errors: List[str]
    ) -> None:
        """
        V4.2+ Enhancement #1: Log failed extractions for review

        Creates audit trail of extraction failures for quality improvement.

        Args:
            gap: Gap that was being filled
            binary_id: Document that was used for extraction
            result: Extraction result that failed validation
            errors: List of validation errors
        """
        failed_extraction = {
            'timestamp': datetime.now().isoformat(),
            'patient_id': self.patient_id,
            'gap_type': gap.get('gap_type'),
            'gap_priority': gap.get('priority'),
            'binary_id': binary_id,
            'extraction_result': result,
            'validation_errors': errors,
            'event_date': gap.get('event_date'),
            'event_type': gap.get('event_type')
        }

        if hasattr(self, 'failed_extractions'):
            self.failed_extractions.append(failed_extraction)

        logger.warning(
            f"📝 Failed extraction logged: {gap.get('gap_type')} for {gap.get('event_type')} "
            f"on {gap.get('event_date')} - {len(errors)} errors"
        )

    def _group_gaps_by_document(
        self,
        gaps: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        V4.2+ Enhancement #2: Group gaps by target document for batch processing

        Groups gaps that require the same document so we can extract all fields
        in a single MedGemma call instead of multiple calls.

        Example: If 3 gaps (missing_eor, missing_tumor_location, missing_laterality)
        all need the same operative note, batch them into one extraction.

        Args:
            gaps: List of identified gaps from Phase 3

        Returns:
            Dictionary mapping document_key -> list of gaps that need that document
        """
        grouped = {}

        for gap in gaps:
            medgemma_target = gap.get('medgemma_target')
            gap_type = gap.get('gap_type')

            # Determine document key based on gap type and target
            if gap_type in ['missing_eor', 'missing_tumor_location', 'missing_laterality']:
                # All surgical gaps use operative note for same procedure/encounter
                encounter_id = gap.get('v2_annotation', {}).get('encounter_id')
                procedure_id = gap.get('v2_annotation', {}).get('procedure_id')
                event_date = gap.get('event_date')

                if encounter_id:
                    doc_key = f"operative_note:encounter:{encounter_id}"
                elif procedure_id:
                    doc_key = f"operative_note:procedure:{procedure_id}"
                elif event_date:
                    doc_key = f"operative_note:date:{event_date}"
                else:
                    doc_key = f"operative_note:individual:{gap_type}"

            elif gap_type == 'missing_radiation_details':
                # Radiation gaps use radiation summary for same encounter/date
                encounter_id = gap.get('v2_annotation', {}).get('encounter_id')
                event_date = gap.get('event_date')

                if encounter_id:
                    doc_key = f"radiation_summary:encounter:{encounter_id}"
                elif event_date:
                    doc_key = f"radiation_summary:date:{event_date}"
                else:
                    doc_key = f"radiation_summary:individual:{gap_type}"

            elif gap_type == 'imaging_conclusion':
                # Imaging gaps use diagnostic report - already unique per imaging event
                diagnostic_report_id = gap.get('diagnostic_report_id')
                if diagnostic_report_id:
                    doc_key = f"imaging_report:{diagnostic_report_id}"
                else:
                    doc_key = f"imaging_report:individual:{gap.get('event_date')}"

            else:
                # Unknown gap type - process individually
                doc_key = f"individual:{gap_type}:{gap.get('event_date')}"

            # Add gap to grouped dictionary
            if doc_key not in grouped:
                grouped[doc_key] = []
            grouped[doc_key].append(gap)

        # Log batching statistics
        total_gaps = len(gaps)
        num_batches = len(grouped)
        if num_batches > 0:
            avg_gaps_per_batch = total_gaps / num_batches
            logger.info(
                f"📦 Grouped {total_gaps} gaps into {num_batches} document batches "
                f"(avg {avg_gaps_per_batch:.1f} gaps/batch)"
            )
        else:
            logger.info(f"📦 No gaps to batch (0 gaps)")

        return grouped

    def _create_batch_extraction_prompt(
        self,
        gaps: List[Dict[str, Any]],
        document_type: str
    ) -> str:
        """
        V4.2+ Enhancement #2: Create multi-gap extraction prompt

        Args:
            gaps: List of gaps to extract from same document
            document_type: Type of document (operative_note, radiation_summary, imaging_report)

        Returns:
            Comprehensive extraction prompt for all gaps
        """
        if document_type == 'operative_note':
            return """You are a medical AI extracting surgical information from an operative note.

Extract ALL of the following information (return null if not found):

OUTPUT SCHEMA (JSON):
{
  "extent_of_resection": "GTR" | "NTR" | "STR" | "Biopsy" | null,
  "surgeon_assessment": "description of resection quality" | null,
  "tumor_location": "specific anatomical location" | null,
  "laterality": "Left" | "Right" | "Bilateral" | "Midline" | null,
  "surgical_approach": "description of surgical approach" | null,
  "complications": "any intraoperative complications" | null,
  "estimated_blood_loss_ml": <number> | null,
  "procedure_duration_minutes": <number> | null,
  "confidence": {
    "extent_of_resection": "HIGH" | "MEDIUM" | "LOW",
    "tumor_location": "HIGH" | "MEDIUM" | "LOW",
    "laterality": "HIGH" | "MEDIUM" | "LOW"
  }
}

IMPORTANT: Extract ALL fields from the operative note. Return null for fields not mentioned."""

        elif document_type == 'radiation_summary':
            return """You are a medical AI extracting radiation therapy information from a radiation summary.

Extract ALL of the following information (return null if not found):

OUTPUT SCHEMA (JSON):
{
  "date_at_radiation_start": "YYYY-MM-DD" | null,
  "date_at_radiation_stop": "YYYY-MM-DD" | null,
  "total_dose_cgy": <number in centiGray> | null,
  "radiation_type": "craniospinal" | "focal" | "boost" | "whole_brain" | "other" | null,
  "radiation_fields": ["field1", "field2"] | null,
  "fractions": <number of fractions> | null,
  "technique": "IMRT" | "3D-CRT" | "Protons" | "VMAT" | "Other" | null,
  "target_volume": "description of treatment volume" | null,
  "confidence": {
    "total_dose_cgy": "HIGH" | "MEDIUM" | "LOW",
    "radiation_type": "HIGH" | "MEDIUM" | "LOW",
    "dates": "HIGH" | "MEDIUM" | "LOW"
  }
}

IMPORTANT: Extract ALL fields from the radiation summary. Return null for fields not mentioned."""

        elif document_type == 'imaging_report':
            return """You are a medical AI extracting imaging findings from a radiology report.

Extract ALL of the following information (return null if not found):

OUTPUT SCHEMA (JSON):
{
  "tumor_location": "anatomical location" | null,
  "lesions": [
    {
      "lesion_id": "target_1" | "target_2" | "non_target_1",
      "location": "specific anatomical location",
      "longest_diameter_mm": <number>,
      "perpendicular_diameter_mm": <number> | null,
      "measurement_type": "bidimensional" | "unidimensional" | "volumetric"
    }
  ] | null,
  "rano_assessment": "CR" | "PR" | "SD" | "PD" | "improved" | "stable" | "worse" | null,
  "enhancement_pattern": "description of enhancement" | null,
  "mass_effect": true | false | null,
  "edema_present": true | false | null,
  "confidence": {
    "tumor_location": "HIGH" | "MEDIUM" | "LOW",
    "lesions": "HIGH" | "MEDIUM" | "LOW",
    "rano_assessment": "HIGH" | "MEDIUM" | "LOW"
  }
}

IMPORTANT: Extract ALL fields from the imaging report. Use RANO criteria for assessment. Return null for fields not mentioned."""

        else:
            return f"""Extract all relevant clinical information from this {document_type} document.
Return as structured JSON with confidence levels."""

    def _find_document_for_batch(
        self,
        doc_key: str,
        gaps: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        V4.2+ Enhancement #2: Find document for batch extraction using V2 linkage

        Args:
            doc_key: Document key from grouping (e.g., 'operative_note:encounter:Enc123')
            gaps: List of gaps in this batch

        Returns:
            Binary ID or DocumentReference ID
        """
        parts = doc_key.split(':', 2)
        if len(parts) != 3:
            return None

        doc_type, resource_type, resource_id = parts

        if doc_type == 'operative_note':
            if resource_type == 'encounter':
                return self._find_operative_note_binary_v2(encounter_id=resource_id)
            elif resource_type == 'procedure':
                return self._find_operative_note_binary_v2(procedure_fhir_id=resource_id)
            elif resource_type == 'date':
                return self._find_operative_note_binary_v2(surgery_date=resource_id)

        elif doc_type == 'radiation_summary':
            if resource_type == 'encounter':
                return self._find_radiation_document_v2(encounter_id=resource_id)
            elif resource_type == 'date':
                return self._find_radiation_document_v2(radiation_date=resource_id)

        elif doc_type == 'imaging_report':
            # Imaging reports are already unique per diagnostic_report_id
            return resource_id

        return None

    def _validate_batch_extraction_result(
        self,
        result: Dict[str, Any],
        gaps: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """
        V4.2+ Enhancement #2: Validate batch extraction result

        Args:
            result: Batch extraction result from MedGemma
            gaps: List of gaps that were requested

        Returns:
            Tuple of (all_valid: bool, errors_by_gap: Dict[gap_type, List[errors]])
        """
        errors_by_gap = {}
        all_valid = True

        for gap in gaps:
            gap_type = gap['gap_type']
            is_valid, errors = self._validate_extraction_result(result, gap_type)

            if not is_valid:
                errors_by_gap[gap_type] = errors
                all_valid = False

        return all_valid, errors_by_gap

    def _find_radiation_document(self, radiation_date: str) -> Optional[str]:
        """
        Query v_radiation_documents for radiation treatment documents (LEGACY - Tier 2 fallback)

        NOTE: v_radiation_documents may include some false positives (e.g., ED visits mentioning
        radiation history), but we rely on:
        1. Document content validation (keyword checking) before extraction
        2. MedGemma's ability to recognize wrong document types
        3. Escalating search to alternative documents if primary fails validation

        This is the CORRECT approach - try v_radiation_documents first, then escalate if needed.

        V4.2+: This is the legacy temporal matching method. Use _find_radiation_document_v2()
        which uses encounter linkage for improved success rate.

        Args:
            radiation_date: Date of radiation start (YYYY-MM-DD)

        Returns:
            DocumentReference ID if found, None otherwise
        """
        if not radiation_date:
            return None

        try:
            # V4.6 ENHANCEMENT: Use extraction_priority from v_radiation_documents for better document selection
            # Priority 1 = Treatment summaries (best for dose extraction)
            # Priority 2 = Consult notes
            # Priority 3 = Outside summaries
            query = f"""
            SELECT document_id, doc_type_text, doc_date, doc_description,
                   extraction_priority, document_category, docc_attachment_url as binary_id
            FROM fhir_prd_db.v_radiation_documents
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 30
            ORDER BY extraction_priority ASC,
                     ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) ASC
            LIMIT 1
            """

            results = query_athena(
                query,
                f"Finding radiation document for {radiation_date}",
                suppress_output=True,
                investigation_engine=self.investigation_engine if hasattr(self, 'investigation_engine') else None,
                schema_loader=self.schema_loader if hasattr(self, 'schema_loader') else None
            )

            if results:
                doc_id = results[0].get('document_id')
                logger.info(f"Found radiation document {doc_id} for radiation on {radiation_date}")
                return f"DocumentReference/{doc_id}"
            else:
                logger.debug(f"No radiation document found for {radiation_date}")
                return None

        except Exception as e:
            logger.error(f"Error querying radiation documents for {radiation_date}: {e}")
            return None

    def _find_chemotherapy_document(self, chemo_date: str) -> Optional[str]:
        """
        Query v_binary_files for chemotherapy-related documents

        Look for treatment summaries, infusion records, or progress notes near chemotherapy date

        Args:
            chemo_date: Date of chemotherapy administration (YYYY-MM-DD)

        Returns:
            DocumentReference ID if found, None otherwise
        """
        if not chemo_date:
            return None

        try:
            # Query v_binary_files for chemotherapy-related documents
            # Look for keywords in dr_type_text or dr_description
            query = f"""
            SELECT dr_id, dr_type_text, dr_date, dr_description
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{chemo_date}' AS DATE))) <= 14
              AND (
                  LOWER(dr_type_text) LIKE '%chemotherapy%'
                  OR LOWER(dr_type_text) LIKE '%infusion%'
                  OR LOWER(dr_type_text) LIKE '%treatment%'
                  OR LOWER(dr_type_text) LIKE '%oncology%'
                  OR LOWER(dr_type_text) LIKE '%progress%'
                  OR LOWER(dr_description) LIKE '%protocol%'
                  OR LOWER(dr_description) LIKE '%chemotherapy%'
                  OR LOWER(dr_description) LIKE '%agent%'
              )
            ORDER BY ABS(DATE_DIFF('day', CAST(dr_date AS DATE), CAST(TIMESTAMP '{chemo_date}' AS DATE)))
            LIMIT 1
            """

            results = query_athena(query, f"Finding chemotherapy document for {chemo_date}", suppress_output=True)

            if results:
                doc_id = results[0].get('dr_id')
                logger.info(f"Found chemotherapy document {doc_id} for chemo on {chemo_date}")
                return f"DocumentReference/{doc_id}"
            else:
                logger.debug(f"No chemotherapy document found for {chemo_date}")
                return None

        except Exception as e:
            logger.error(f"Error querying chemotherapy documents for {chemo_date}: {e}")
            return None

    def _build_patient_document_inventory(self) -> Dict:
        """
        Build comprehensive inventory of ALL available documents for this patient
        Allows agent to make informed prioritization decisions based on what's actually available

        Returns:
            Dictionary with document types as keys and lists of documents as values
        """
        try:
            query = f"""
            SELECT
                binary_id,
                dr_type_text,
                dr_date,
                dr_description,
                content_type
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{self.athena_patient_id}'
            ORDER BY dr_date DESC
            """
            results = query_athena(query, f"Building document inventory for patient", suppress_output=True)

            inventory = {
                'operative_records': [],
                'discharge_summaries': [],
                'progress_notes': [],
                'imaging_reports': [],
                'pathology_reports': [],
                'consultation_notes': [],
                'radiation_documents': [],
                'treatment_plans': [],
                'other': []
            }

            for doc in results:
                doc_type = doc.get('dr_type_text', '').lower()
                doc_desc = doc.get('dr_description', '').lower()

                # Operative records: Include dr_type 'operative', 'op note', 'outside records'
                # Also check description for surgical keywords
                if ('operative' in doc_type or 'op note' in doc_type or 'outside' in doc_type or
                    'surgical' in doc_desc or 'operative' in doc_desc or 'surgery' in doc_desc):
                    inventory['operative_records'].append(doc)
                elif 'discharge' in doc_type:
                    inventory['discharge_summaries'].append(doc)
                elif 'progress' in doc_type:
                    inventory['progress_notes'].append(doc)
                elif 'imaging' in doc_type or 'radiology' in doc_type or 'diagnostic imaging' in doc_type:
                    inventory['imaging_reports'].append(doc)
                elif 'pathology' in doc_type:
                    inventory['pathology_reports'].append(doc)
                elif 'consultation' in doc_type or 'consult' in doc_type:
                    inventory['consultation_notes'].append(doc)
                elif 'rad onc' in doc_type or 'radiation' in doc_type:
                    inventory['radiation_documents'].append(doc)
                elif 'treatment plan' in doc_type:
                    inventory['treatment_plans'].append(doc)
                else:
                    inventory['other'].append(doc)

            logger.info(f"Document inventory: {sum(len(v) for v in inventory.values())} total documents")
            for key, docs in inventory.items():
                if docs:
                    logger.info(f"  {key}: {len(docs)} documents")

            return inventory

        except Exception as e:
            logger.error(f"Error building document inventory: {e}")
            return {}

    def _find_alternative_documents(self, gap: Dict, inventory: Dict) -> List[Dict]:
        """
        Find alternative documents based on gap type and patient-specific availability
        Returns prioritized list of candidate documents

        Args:
            gap: Extraction gap dictionary
            inventory: Patient document inventory from _build_patient_document_inventory()

        Returns:
            List of candidate documents sorted by priority and temporal proximity
        """
        gap_type = gap['gap_type']
        event_date = gap.get('event_date')
        candidates = []

        if gap_type == 'missing_eor':
            # TEMPORAL + TYPE APPROACH: No keyword filtering for surgery gaps
            # UPDATED PRIORITY: Post-op imaging moved to Priority #2 for objective volumetric assessment

            # Priority 1: Operative records (ALL - temporal filtering will narrow)
            operative_records = inventory.get('operative_records', [])
            print(f"       🔍 Priority 1: Adding ALL {len(operative_records)} operative_records (no keyword filter)")
            for doc in operative_records:
                candidates.append({
                    'priority': 1,
                    'source_type': 'operative_record',
                    **doc
                })

            # Priority 2: Post-op imaging reports (MOVED UP from Priority 4)
            # Check structured schema (v_imaging.report_conclusion) first, then fallback to binary
            imaging_reports = inventory.get('imaging_reports', [])
            print(f"       🔍 Priority 2: Adding ALL {len(imaging_reports)} imaging_reports (objective EOR assessment)")
            for doc in imaging_reports:
                candidates.append({
                    'priority': 2,
                    'source_type': 'postop_imaging',
                    **doc
                })

            # Priority 3: Discharge summaries (ALL - temporal filtering will narrow)
            discharge_summaries = inventory.get('discharge_summaries', [])
            print(f"       🔍 Priority 3: Adding ALL {len(discharge_summaries)} discharge_summaries (no keyword filter)")
            for doc in discharge_summaries:
                candidates.append({
                    'priority': 3,
                    'source_type': 'discharge_summary',
                    **doc
                })

            # Priority 4: Progress notes (ALL - temporal filtering will narrow)
            progress_notes = inventory.get('progress_notes', [])
            print(f"       🔍 Priority 4: Adding ALL {len(progress_notes)} progress_notes (no keyword filter)")
            for doc in progress_notes:
                candidates.append({
                    'priority': 4,
                    'source_type': 'progress_note',
                    **doc
                })

            print(f"       📊 Total {len(candidates)} candidates before temporal filtering")

        elif gap_type == 'missing_radiation_details':
            # TEMPORAL + TYPE APPROACH: No keyword filtering - rely on document type + date proximity
            # Rationale: dr_description often NULL/empty; progress notes near radiation WILL mention it

            # Priority 1: Radiation-specific documents (ALL within temporal window)
            rad_docs = inventory.get('radiation_documents', [])
            print(f"       🔍 Priority 1: Adding ALL {len(rad_docs)} radiation_documents (no keyword filter)")
            for doc in rad_docs:
                candidates.append({
                    'priority': 1,
                    'source_type': 'radiation_document',
                    **doc
                })

            # Priority 2: Progress notes (ALL - temporal filtering will narrow down)
            progress_notes = inventory.get('progress_notes', [])
            print(f"       🔍 Priority 2: Adding ALL {len(progress_notes)} progress_notes (no keyword filter)")
            for doc in progress_notes:
                candidates.append({
                    'priority': 2,
                    'source_type': 'progress_note',
                    **doc
                })

            # Priority 3: Discharge summaries (ALL - temporal filtering will narrow down)
            discharge_summaries = inventory.get('discharge_summaries', [])
            print(f"       🔍 Priority 3: Adding ALL {len(discharge_summaries)} discharge_summaries (no keyword filter)")
            for doc in discharge_summaries:
                candidates.append({
                    'priority': 3,
                    'source_type': 'discharge_summary',
                    **doc
                })

            # Priority 4: Treatment plans (ALL - temporal filtering will narrow down)
            treatment_plans = inventory.get('treatment_plans', [])
            print(f"       🔍 Priority 4: Adding ALL {len(treatment_plans)} treatment_plans (no keyword filter)")
            for doc in treatment_plans:
                candidates.append({
                    'priority': 4,
                    'source_type': 'treatment_plan',
                    **doc
                })

            print(f"       📊 Total {len(candidates)} candidates before temporal filtering")

        elif gap_type == 'imaging_conclusion':
            # For imaging, primary is already the imaging report
            # Look for clinical notes interpreting the imaging
            for doc in inventory.get('progress_notes', []):
                desc = doc.get('dr_description', '').lower()
                if any(kw in desc for kw in ['mri', 'imaging', 'scan', 'tumor']):
                    candidates.append({
                        'priority': 2,
                        'source_type': 'progress_note',
                        **doc
                    })

        elif gap_type == 'missing_chemotherapy_details':
            # TEMPORAL + TYPE APPROACH: Document type prioritization for chemotherapy protocol info
            # Rationale: Protocol enrollment and agent details most complete in treatment summaries

            # Priority 1: Medication administration notes (direct chemotherapy documentation)
            medication_notes = inventory.get('medication_notes', [])
            print(f"       🔍 Priority 1: Adding ALL {len(medication_notes)} medication_notes (no keyword filter)")
            for doc in medication_notes:
                candidates.append({
                    'priority': 1,
                    'source_type': 'medication_note',
                    **doc
                })

            # Priority 2: Oncology consultation notes (protocol discussions)
            consult_notes = inventory.get('consult_notes', [])
            print(f"       🔍 Priority 2: Adding ALL {len(consult_notes)} consult_notes (no keyword filter)")
            for doc in consult_notes:
                candidates.append({
                    'priority': 2,
                    'source_type': 'consult_note',
                    **doc
                })

            # Priority 3: Progress notes (treatment discussions, modifications)
            progress_notes = inventory.get('progress_notes', [])
            print(f"       🔍 Priority 3: Adding ALL {len(progress_notes)} progress_notes (no keyword filter)")
            for doc in progress_notes:
                candidates.append({
                    'priority': 3,
                    'source_type': 'progress_note',
                    **doc
                })

            # Priority 4: Discharge summaries (comprehensive treatment history)
            discharge_summaries = inventory.get('discharge_summaries', [])
            print(f"       🔍 Priority 4: Adding ALL {len(discharge_summaries)} discharge_summaries (no keyword filter)")
            for doc in discharge_summaries:
                candidates.append({
                    'priority': 4,
                    'source_type': 'discharge_summary',
                    **doc
                })

            # Priority 5: Treatment/care plans (protocol enrollment forms)
            treatment_plans = inventory.get('treatment_plans', [])
            print(f"       🔍 Priority 5: Adding ALL {len(treatment_plans)} treatment_plans (no keyword filter)")
            for doc in treatment_plans:
                candidates.append({
                    'priority': 5,
                    'source_type': 'treatment_plan',
                    **doc
                })

            print(f"       📊 Total {len(candidates)} candidates before temporal filtering")

        # Calculate temporal distance from event
        if event_date:
            from dateutil.parser import parse
            event_dt = parse(event_date)
            for candidate in candidates:
                if candidate.get('dr_date'):
                    try:
                        doc_dt = parse(candidate['dr_date'])
                        days_diff = abs((doc_dt - event_dt).days)
                        candidate['days_from_event'] = days_diff
                    except:
                        candidate['days_from_event'] = 9999
                else:
                    candidate['days_from_event'] = 9999

        # Sort by priority, then temporal proximity
        candidates.sort(key=lambda x: (x.get('priority', 99), x.get('days_from_event', 9999)))

        return candidates

    def _try_alternative_documents(self, gap: Dict, missing_fields: List[str]) -> bool:
        """
        Try extracting from alternative documents when primary document fails

        Returns True if extraction successful from an alternative, False if all exhausted
        """
        # Build document inventory if not already done
        if not hasattr(self, '_document_inventory'):
            print(f"       📋 Building patient document inventory...")
            self._document_inventory = self._build_patient_document_inventory()

        # Find alternative candidates
        candidates = self._find_alternative_documents(gap, self._document_inventory)

        if not candidates:
            print(f"       ⚠️  No alternative documents available for {gap['gap_type']}")
            print(f"       📊 Inventory summary:")
            for key, docs in self._document_inventory.items():
                if docs:
                    print(f"          {key}: {len(docs)} documents")
            return False

        print(f"       📄 Found {len(candidates)} alternative document(s) to try")

        # Try each alternative
        max_alternatives = 50  # Increased from 5 to allow more thorough document search
        for i, candidate in enumerate(candidates[:max_alternatives]):
            print(f"       [{i+1}/{min(len(candidates), max_alternatives)}] Trying {candidate['source_type']} from {candidate.get('dr_date', 'unknown date')} ({candidate.get('days_from_event', '?')} days from event)")

            # Fetch alternative document
            binary_id = candidate.get('binary_id')
            if not binary_id:
                print(f"          ⚠️  No binary_id for this document")
                continue

            # binary_id from v_binary_files already includes "Binary/" prefix
            alt_text = self._fetch_binary_document(binary_id)
            if not alt_text:
                print(f"          ⚠️  Could not fetch document")
                continue

            print(f"          ✅ Fetched document ({len(alt_text)} chars)")

            # Validate alternative document content
            is_valid, reason = self._validate_document_content(alt_text, gap['gap_type'])
            if not is_valid:
                print(f"          ⚠️  Validation failed: {reason}")
                continue

            print(f"          ✅ Document validated: {reason}")

            # Generate prompt
            prompt = self._generate_medgemma_prompt(gap)
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT:\n{alt_text}"

            # Extract from alternative
            try:
                result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

                if not result.success:
                    print(f"          ❌ Extraction failed: {result.error}")
                    continue

                # Validate extraction
                is_valid_result, still_missing = self._validate_extraction_result(result.extracted_data, gap['gap_type'])

                if is_valid_result:
                    print(f"          ✅ SUCCESSFUL extraction from alternative document!")
                    # Integrate into timeline
                    self._integrate_extraction_into_timeline(gap, result.extracted_data)
                    gap['status'] = 'RESOLVED'
                    gap['extraction_result'] = result.extracted_data
                    gap['extraction_source'] = candidate['source_type']
                    gap['extraction_document_date'] = candidate.get('dr_date')

                    self.binary_extractions.append({
                        'gap': gap,
                        'extraction_result': result.extracted_data,
                        'extraction_confidence': result.extracted_data.get('extraction_confidence', 'UNKNOWN'),
                        'source': 'alternative_document',
                        'source_type': candidate['source_type']
                    })

                    return True
                else:
                    print(f"          ⚠️  Still missing fields: {still_missing}")
                    # Continue to next alternative

            except Exception as e:
                print(f"          ❌ Extraction error: {e}")
                continue

        # All alternatives exhausted
        print(f"       ❌ Exhausted {min(len(candidates), max_alternatives)} alternative documents")
        gap['status'] = 'UNAVAILABLE_IN_RECORDS'
        return False

    def _verify_medgemma_available(self) -> bool:
        """Verify Ollama is running and gemma2:27b is available"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if "gemma2:27b" in model_names:
                logger.info("✅ MedGemma (gemma2:27b) is available via Ollama")
                return True
            else:
                logger.warning(f"⚠️  gemma2:27b not found. Available: {model_names}")
                logger.warning("Pull with: ollama pull gemma2:27b")
                return False
        except Exception as e:
            logger.warning(f"⚠️  Ollama not accessible: {e}")
            logger.warning("Start Ollama with: ollama serve")
            return False

    def _phase4_extract_from_binaries_placeholder(self):
        """Phase 4: PLACEHOLDER for MedGemma binary extraction"""

        print("  ⚠️  MedGemma integration not yet implemented")
        print("  ⚠️  In production, this phase would:")
        print("     1. Prioritize gaps by clinical significance + WHO 2021 context")
        print("     2. Fetch binary documents from DocumentReference")
        print("     3. Call MedGemma for structured extraction")
        print("     4. Validate and integrate extractions into timeline")
        print("     5. Re-assess for remaining gaps (iterative)")

    def _phase4_extract_from_binaries(self):
        """
        Phase 4: Real MedGemma extraction from binary documents
        """

        # Track Phase 4 binary extraction attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase4_binary_extraction')

        if not self.medgemma_agent or not self.binary_agent:
            print("  ⚠️  Ollama/MedGemma not available - skipping binary extraction")

            # Track Phase 4 as failed due to missing MedGemma
            if self.completeness_tracker:
                self.completeness_tracker.mark_failure(
                    'phase4_binary_extraction',
                    error_message="MedGemma/Ollama not available"
                )
            return

        # V4.2+ Route to batch or sequential extraction
        if self.use_batch_extraction:
            return self._phase4_batch_extraction()
        else:
            return self._phase4_sequential_extraction()

    def _phase4_batch_extraction(self):
        """
        V4.2+ Enhancement #2: Batch extraction - process multiple gaps per document
        """
        print("  📦 Using BATCH extraction mode (V4.2+)")

        # Group gaps by document
        grouped_gaps = self._group_gaps_by_document(self.extraction_gaps)

        print(f"  📊 Grouped {len(self.extraction_gaps)} gaps into {len(grouped_gaps)} document batches")

        batch_stats = {
            'total_batches': len(grouped_gaps),
            'successful_batches': 0,
            'failed_batches': 0,
            'gaps_filled': 0,
            'gaps_failed': 0
        }

        for doc_key, gaps in grouped_gaps.items():
            print(f"\n  📄 Batch: {doc_key} ({len(gaps)} gaps)")

            # Parse document type from key
            doc_type = doc_key.split(':')[0]

            # Find document for this batch
            document_id = self._find_document_for_batch(doc_key, gaps)
            if not document_id:
                print(f"    ❌ No document found")
                batch_stats['failed_batches'] += 1
                batch_stats['gaps_failed'] += len(gaps)
                for gap in gaps:
                    gap['status'] = 'NO_DOCUMENT_FOUND'
                continue

            print(f"    ✅ Found document: {document_id}")

            # Fetch document content
            try:
                extracted_text = self._fetch_binary_document(document_id)
                if not extracted_text:
                    print(f"    ❌ Failed to fetch document")
                    batch_stats['failed_batches'] += 1
                    batch_stats['gaps_failed'] += len(gaps)
                    continue
                print(f"    ✅ Fetched ({len(extracted_text)} chars)")
            except Exception as e:
                print(f"    ❌ Error fetching: {e}")
                batch_stats['failed_batches'] += 1
                batch_stats['gaps_failed'] += len(gaps)
                continue

            # Create batch prompt
            prompt = self._create_batch_extraction_prompt(gaps, doc_type)
            full_prompt = f"{prompt}\n\nDOCUMENT TEXT:\n{extracted_text}"

            # Call MedGemma once for all gaps in this batch
            try:
                result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

                if not result.success:
                    print(f"    ❌ MedGemma extraction failed: {result.error}")
                    batch_stats['failed_batches'] += 1
                    batch_stats['gaps_failed'] += len(gaps)
                    continue

                print(f"    ✅ Extracted {len(gaps)} fields in 1 call")

                # Validate batch result
                all_valid, errors_by_gap = self._validate_batch_extraction_result(
                    result.extracted_data, gaps
                )

                if all_valid:
                    print(f"    ✅ All extractions valid")
                else:
                    print(f"    ⚠️  Some validations failed: {len(errors_by_gap)} gaps")

                # Integrate results into timeline
                for gap in gaps:
                    gap_type = gap['gap_type']

                    # Check if this gap was successfully extracted
                    if gap_type in errors_by_gap:
                        print(f"      ❌ {gap_type}: {errors_by_gap[gap_type]}")
                        gap['status'] = 'VALIDATION_FAILED'
                        gap['validation_errors'] = errors_by_gap[gap_type]
                        batch_stats['gaps_failed'] += 1
                    else:
                        # Successful extraction - integrate into timeline
                        self._integrate_extraction_into_timeline(gap, result.extracted_data)
                        gap['status'] = 'RESOLVED'
                        gap['extraction_result'] = result.extracted_data
                        gap['extraction_source'] = 'batch'
                        batch_stats['gaps_filled'] += 1
                        print(f"      ✅ {gap_type}")

                self.binary_extractions.append({
                    'batch_key': doc_key,
                    'gaps': [g['gap_type'] for g in gaps],
                    'extraction_result': result.extracted_data,
                    'source': 'batch_extraction'
                })

                batch_stats['successful_batches'] += 1

            except Exception as e:
                print(f"    ❌ Batch extraction error: {e}")
                batch_stats['failed_batches'] += 1
                batch_stats['gaps_failed'] += len(gaps)

        # Report batch statistics
        print(f"\n  📊 Batch Extraction Summary:")
        print(f"    Batches processed: {batch_stats['total_batches']}")
        print(f"    Successful: {batch_stats['successful_batches']}")
        print(f"    Failed: {batch_stats['failed_batches']}")
        print(f"    Gaps filled: {batch_stats['gaps_filled']}")
        print(f"    Gaps failed: {batch_stats['gaps_failed']}")

        if batch_stats['total_batches'] > 0:
            efficiency = (batch_stats['total_batches'] / len(self.extraction_gaps)) * 100
            print(f"    Efficiency gain: {100 - efficiency:.0f}% fewer API calls")

        # Store batch stats
        if hasattr(self, 'validation_stats'):
            self.validation_stats['batch_extraction_stats'] = batch_stats

        # Track Phase 4 batch extraction success
        if self.completeness_tracker:
            if batch_stats['gaps_filled'] > 0:
                self.completeness_tracker.mark_success(
                    'phase4_binary_extraction',
                    record_count=batch_stats['gaps_filled']
                )
            elif batch_stats['failed_batches'] == batch_stats['total_batches']:
                self.completeness_tracker.mark_failure(
                    'phase4_binary_extraction',
                    error_message=f"All {batch_stats['total_batches']} batches failed"
                )
            else:
                # Partial success
                self.completeness_tracker.mark_success(
                    'phase4_binary_extraction',
                    record_count=batch_stats['gaps_filled']
                )

    def _phase4_sequential_extraction(self):
        """
        Phase 4: Sequential extraction (original method)
        """
        print("  🔄 Using SEQUENTIAL extraction mode (legacy)")

        # Prioritize gaps (HIGHEST → HIGH → MEDIUM)
        priority_map = {'HIGHEST': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        prioritized_gaps = sorted(
            self.extraction_gaps,
            key=lambda x: priority_map.get(x.get('priority', 'LOW'), 4)
        )

        # Apply max_extractions limit if set
        if self.max_extractions:
            prioritized_gaps = prioritized_gaps[:self.max_extractions]
            print(f"  ⚠️  Limiting to {self.max_extractions} extraction(s) for testing")

        print(f"  Extracting from {len(prioritized_gaps)} documents using MedGemma...")

        extracted_count = 0
        failed_count = 0

        for i, gap in enumerate(prioritized_gaps, 1):
            print(f"\n  [{i}/{len(prioritized_gaps)}] Processing {gap['gap_type']} (priority: {gap.get('priority')})")

            # STEP 1: Generate context-aware prompt
            try:
                prompt = self._generate_medgemma_prompt(gap)
                print(f"    ✅ Generated context-aware prompt ({len(prompt)} chars)")
            except Exception as e:
                print(f"    ❌ Error generating prompt: {e}")
                failed_count += 1
                continue

            # STEP 2: Fetch binary document
            try:
                medgemma_target = gap.get('medgemma_target', '')
                if not medgemma_target or medgemma_target == 'MISSING_REFERENCE':
                    print(f"    ⚠️  No medgemma_target - trying alternative documents...")
                    # ESCALATION: No primary target, go straight to alternative documents
                    alternative_success = self._try_alternative_documents(gap, [])
                    if alternative_success:
                        print(f"    ✅ Alternative document extraction successful!")
                        extracted_count += 1
                        continue  # Move to next gap
                    else:
                        print(f"    ❌ No suitable alternative documents found")
                        gap['status'] = 'NO_DOCUMENTS_AVAILABLE'
                        failed_count += 1
                        continue

                # V4.2+ STEP 2.1: LAYER 1 VALIDATION - Validate document type BEFORE fetching
                expected_doc_type = self._map_gap_to_doc_type(gap['gap_type'])
                if expected_doc_type and medgemma_target.startswith('Binary/'):
                    is_correct_type = self._validate_document_type(medgemma_target, expected_doc_type)
                    if not is_correct_type:
                        print(f"    ⚠️  Document type mismatch detected - searching for alternatives...")
                        # ESCALATION: Wrong document type, try alternatives immediately
                        alternative_success = self._try_alternative_documents(gap, [])
                        if alternative_success:
                            print(f"    ✅ Alternative document extraction successful!")
                            extracted_count += 1
                            continue
                        else:
                            print(f"    ❌ All alternatives exhausted")
                            gap['status'] = 'WRONG_DOCUMENT_TYPE'
                            failed_count += 1
                            continue
                    else:
                        print(f"    ✅ Document type validated: {expected_doc_type}")

                extracted_text = self._fetch_binary_document(medgemma_target)
                if not extracted_text:
                    print(f"    ❌ Failed to fetch document")
                    failed_count += 1
                    continue
                print(f"    ✅ Fetched document ({len(extracted_text)} chars)")
            except Exception as e:
                print(f"    ❌ Error fetching document: {e}")
                failed_count += 1
                continue

            # STEP 2.5: AGENT 1 VALIDATION - Validate document content before extraction
            is_valid_doc, validation_reason = self._validate_document_content(extracted_text, gap['gap_type'])
            if not is_valid_doc:
                print(f"    ⚠️  Document validation failed: {validation_reason}")
                print(f"    🔍 ESCALATION: Wrong document type - searching for alternatives...")

                # ESCALATION: Primary document is wrong type, try alternatives immediately
                alternative_success = self._try_alternative_documents(gap, [])
                if alternative_success:
                    print(f"    ✅ Alternative document extraction successful!")
                    extracted_count += 1
                    continue  # Move to next gap
                else:
                    print(f"    ❌ All alternative documents exhausted")
                    gap['status'] = 'WRONG_DOCUMENT_TYPE'
                    gap['validation_failure'] = validation_reason
                    failed_count += 1
                    continue
            else:
                print(f"    ✅ Document validated: {validation_reason}")

            # V4.1 STEP 5: Extract tumor location from imaging reports
            if self.location_extractor and extracted_text and gap['gap_type'] == 'imaging_conclusion':
                try:
                    diagnostic_report_id = gap.get('diagnostic_report_id')
                    location_feature = self.location_extractor.extract_location_from_text(
                        text=extracted_text,
                        source_type="imaging",
                        source_id=diagnostic_report_id,
                        progression_status=None  # Could be enhanced with temporal logic
                    )
                    if location_feature:
                        logger.info(f"📍 Extracted location from imaging report: {location_feature.locations}")
                        # Store location with imaging event
                        for img in self.timeline_events:
                            if img.get('event_type') == 'imaging' and img.get('diagnostic_report_id') == diagnostic_report_id:
                                if 'v41_tumor_location' not in img:
                                    img['v41_tumor_location'] = location_feature.to_dict()
                                break
                except Exception as e:
                    logger.warning(f"⚠️  Could not extract location from imaging report: {e}")

            # V4.2 STEP 5.5: Extract tumor measurements from imaging reports
            if self.measurement_extractor and extracted_text and gap['gap_type'] == 'imaging_conclusion':
                try:
                    diagnostic_report_id = gap.get('diagnostic_report_id')
                    imaging_modality = gap.get('imaging_modality', 'Unknown')

                    logger.info(f"📏 Extracting tumor measurements from imaging report...")
                    measurements = self.measurement_extractor.extract_measurements(
                        report_text=extracted_text,
                        source_id=diagnostic_report_id,
                        imaging_modality=imaging_modality
                    )

                    if measurements:
                        logger.info(f"📏 Extracted {len(measurements)} tumor measurements")
                        # Convert TumorMeasurement objects to dicts for JSON serialization
                        measurements_dicts = [m.to_dict() for m in measurements]

                        # Store measurements with imaging event
                        for img in self.timeline_events:
                            if img.get('event_type') == 'imaging' and img.get('diagnostic_report_id') == diagnostic_report_id:
                                if 'tumor_measurements' not in img:
                                    img['tumor_measurements'] = measurements_dicts
                                    logger.info(f"   Added {len(measurements)} measurements to imaging event on {img.get('event_date')}")
                                break
                    else:
                        logger.debug("   No measurements extracted from imaging report")

                except Exception as e:
                    logger.warning(f"⚠️  Could not extract measurements from imaging report: {e}")

            # V4.2 STEP 5.6: Extract treatment response from imaging reports
            if self.response_extractor and extracted_text and gap['gap_type'] == 'imaging_conclusion':
                try:
                    diagnostic_report_id = gap.get('diagnostic_report_id')
                    imaging_date = gap.get('event_date')

                    logger.info(f"📈 Extracting treatment response assessment...")
                    response = self.response_extractor.extract_response(
                        report_text=extracted_text,
                        imaging_date=imaging_date,
                        timeline_events=self.timeline_events,
                        source_id=diagnostic_report_id
                    )

                    if response:
                        logger.info(f"📈 Extracted treatment response: {response.response_category}")
                        # Convert TreatmentResponse object to dict for JSON serialization
                        response_dict = response.to_dict()

                        # Store response with imaging event
                        for img in self.timeline_events:
                            if img.get('event_type') == 'imaging' and img.get('diagnostic_report_id') == diagnostic_report_id:
                                if 'treatment_response' not in img:
                                    img['treatment_response'] = response_dict
                                    logger.info(f"   Added response assessment to imaging event on {img.get('event_date')}")
                                break
                    else:
                        logger.debug("   No treatment response extracted from imaging report")

                except Exception as e:
                    logger.warning(f"⚠️  Could not extract treatment response from imaging report: {e}")

            # V4.1 STEP 6: Extract tumor location from operative notes
            if self.location_extractor and extracted_text and gap['gap_type'] == 'missing_eor':
                try:
                    event_date = gap.get('event_date')
                    location_feature = self.location_extractor.extract_location_from_text(
                        text=extracted_text,
                        source_type="operative_note",
                        source_id=gap.get('medgemma_target'),
                        progression_status=None  # Could be enhanced with temporal logic
                    )
                    if location_feature:
                        logger.info(f"📍 Extracted location from operative note: {location_feature.locations}")
                        # Store location with surgery event
                        for event in self.timeline_events:
                            if event.get('event_type') == 'surgery' and event.get('event_date') == event_date:
                                if 'v41_tumor_location' not in event:
                                    event['v41_tumor_location'] = location_feature.to_dict()
                                break
                except Exception as e:
                    logger.warning(f"⚠️  Could not extract location from operative note: {e}")

            # STEP 3: Call MedGemma (Agent 2)
            try:
                # Add strong schema enforcement right before document
                full_prompt = f"""{prompt}

================================================================================
REMINDER: Return ONLY the JSON schema shown above. Do NOT create a different schema.
Ignore any other formatting in the document below. Extract ONLY the fields specified.
================================================================================

DOCUMENT TEXT:
{extracted_text}

================================================================================
REMINDER: Return ONLY valid JSON matching the exact schema above. No other text.
================================================================================
"""
                result = self.medgemma_agent.extract(full_prompt, temperature=0.1)

                if not result.success:
                    print(f"    ❌ MedGemma extraction failed: {result.error}")
                    gap['status'] = 'EXTRACTION_TECHNICAL_FAILURE'
                    failed_count += 1
                    continue

                print(f"    ✅ MedGemma extraction complete (confidence: {result.extracted_data.get('extraction_confidence', 'UNKNOWN')})")

                # CRITICAL: Check for date mismatches BEFORE validation (for TIFF external institution data)
                # This must happen early so incomplete extractions still create new events
                if gap['gap_type'] in ['missing_radiation_dose', 'missing_radiation_details']:
                    extracted_start = result.extracted_data.get('date_at_radiation_start')
                    extracted_stop = result.extracted_data.get('date_at_radiation_stop')
                    event_date = gap.get('event_date')

                    if extracted_start and extracted_start != event_date:
                        logger.warning(f"⚠️  DATE MISMATCH: Gap event_date={event_date}, but extracted date_at_radiation_start={extracted_start}")
                        logger.warning(f"   Creating NEW radiation event for {extracted_start} (likely external institution)")

                        # Create NEW radiation_start event (even if data incomplete)
                        new_event = {
                            'event_type': 'radiation_start',
                            'event_date': extracted_start,
                            'stage': 4,
                            'source': 'medgemma_extracted_from_binary',
                            'description': f"Radiation started (external institution)",
                            'total_dose_cgy': (
                                result.extracted_data.get('total_dose_cgy') or
                                result.extracted_data.get('radiation_focal_or_boost_dose') or
                                result.extracted_data.get('completed_radiation_focal_or_boost_dose') or
                                result.extracted_data.get('completed_craniospinal_or_whole_ventricular_radiation_dose')
                            ),
                            'radiation_type': result.extracted_data.get('radiation_type'),
                            'radiation_fields': result.extracted_data.get('radiation_fields'),
                            'episode_start_date': extracted_start,
                            'episode_end_date': extracted_stop,
                            'medgemma_extraction': result.extracted_data,
                            'event_sequence': len(self.timeline_events) + 1
                        }
                        self.timeline_events.append(new_event)
                        logger.info(f"✅ Created NEW radiation_start event for {extracted_start}")

                        # Create NEW radiation_end event if stop date available
                        if extracted_stop:
                            new_end_event = {
                                'event_type': 'radiation_end',
                                'event_date': extracted_stop,
                                'stage': 4,
                                'source': 'medgemma_extracted_from_binary',
                                'description': f"Radiation completed (external institution)",
                                'total_dose_cgy': new_event['total_dose_cgy'],
                                'event_sequence': len(self.timeline_events) + 1
                            }
                            self.timeline_events.append(new_end_event)
                            logger.info(f"✅ Created NEW radiation_end event for {extracted_stop}")

                        # Re-sort timeline by date
                        self.timeline_events.sort(key=lambda x: (x.get('event_date') is None, x.get('event_date', '')))

                        # Update sequence numbers
                        for i, event in enumerate(self.timeline_events, 1):
                            event['event_sequence'] = i

                        # Mark gap as resolved and skip validation
                        gap['status'] = 'RESOLVED_DATE_MISMATCH'
                        gap['extraction_result'] = result.extracted_data
                        gap['note'] = f"Date mismatch detected: created new event for {extracted_start}"
                        self.binary_extractions.append({
                            'gap': gap,
                            'extraction_result': result.extracted_data,
                            'extraction_confidence': result.extracted_data.get('extraction_confidence', 'UNKNOWN')
                        })
                        extracted_count += 1
                        continue  # Skip validation - already handled

                # STEP 4: AGENT 1 VALIDATION - Validate extraction result
                is_valid_result, missing_fields = self._validate_extraction_result(result.extracted_data, gap['gap_type'])

                if not is_valid_result:
                    print(f"    ⚠️  Extraction incomplete - missing required fields: {missing_fields}")

                    # STEP 5: AGENT 1 ↔ AGENT 2 NEGOTIATION - Re-extraction with clarification
                    retry_result = self._retry_extraction_with_clarification(gap, extracted_text, result.extracted_data, missing_fields)

                    if retry_result:
                        # Validate retry
                        is_valid_retry, still_missing = self._validate_extraction_result(retry_result, gap['gap_type'])
                        if is_valid_retry:
                            print(f"    ✅ Re-extraction successful - all required fields present")
                            result.extracted_data = retry_result
                        else:
                            print(f"    ❌ Re-extraction still incomplete - missing: {still_missing}")
                            print(f"    🔍 ESCALATION: Searching for alternative documents...")

                            # ESCALATION: Try alternative documents
                            alternative_success = self._try_alternative_documents(gap, still_missing)
                            if alternative_success:
                                print(f"    ✅ Alternative document extraction successful!")
                                extracted_count += 1
                                continue  # Move to next gap
                            else:
                                print(f"    ❌ All alternative documents exhausted")
                                gap['status'] = 'INCOMPLETE_EXTRACTION'
                                gap['missing_fields'] = still_missing
                                gap['extraction_result'] = retry_result
                                failed_count += 1
                                continue
                    else:
                        print(f"    ❌ Re-extraction failed")
                        print(f"    🔍 ESCALATION: Searching for alternative documents...")

                        # ESCALATION: Try alternative documents
                        alternative_success = self._try_alternative_documents(gap, missing_fields)
                        if alternative_success:
                            print(f"    ✅ Alternative document extraction successful!")
                            extracted_count += 1
                            continue  # Move to next gap
                        else:
                            print(f"    ❌ All alternative documents exhausted")
                            gap['status'] = 'RE_EXTRACTION_FAILED'
                            gap['missing_fields'] = missing_fields
                            failed_count += 1
                            continue

                # STEP 6: Success - all validations passed
                print(f"    ✅ Extraction SUCCESSFUL - all required fields present")
                self._integrate_extraction_into_timeline(gap, result.extracted_data)
                gap['status'] = 'RESOLVED'
                gap['extraction_result'] = result.extracted_data
                self.binary_extractions.append({
                    'gap': gap,
                    'extraction_result': result.extracted_data,
                    'extraction_confidence': result.extracted_data.get('extraction_confidence', 'UNKNOWN')
                })
                extracted_count += 1

            except Exception as e:
                print(f"    ❌ MedGemma error: {e}")
                gap['status'] = 'EXTRACTION_ERROR'
                gap['error'] = str(e)
                failed_count += 1

        print(f"\n  ✅ Extracted from {extracted_count} documents")
        print(f"  ❌ {failed_count} failed or require manual review")

        # Track Phase 4 sequential extraction success
        if self.completeness_tracker:
            if extracted_count > 0:
                self.completeness_tracker.mark_success(
                    'phase4_binary_extraction',
                    record_count=extracted_count
                )
            elif failed_count > 0 and extracted_count == 0:
                self.completeness_tracker.mark_failure(
                    'phase4_binary_extraction',
                    error_message=f"All {failed_count} extractions failed"
                )
            else:
                # No extractions attempted
                self.completeness_tracker.mark_success(
                    'phase4_binary_extraction',
                    record_count=0
                )

    def _generate_medgemma_prompt(self, gap: Dict) -> str:
        """Route to specialized prompt generator based on gap type"""
        gap_type = gap.get('gap_type')

        if gap_type == 'imaging_conclusion':
            return self._generate_imaging_prompt(gap)
        elif gap_type == 'missing_eor':
            return self._generate_operative_note_prompt(gap)
        elif gap_type in ['missing_radiation_dose', 'missing_radiation_details']:
            return self._generate_radiation_summary_prompt(gap)
        elif gap_type == 'missing_chemotherapy_details':
            return self._generate_chemotherapy_prompt(gap)
        else:
            # Default generic prompt
            return self._generate_generic_prompt(gap)

    def _generate_imaging_prompt(self, gap: Dict) -> str:
        """Generate context-aware prompt for imaging report extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        molecular_subtype = self.who_2021_classification.get('molecular_subtype', '')

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text or narrative summaries. ONLY return the JSON object.

You are a medical AI extracting structured data from a radiology report.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Molecular Subtype: {molecular_subtype}
- Imaging Date: {gap.get('event_date')}
- Imaging Modality: {gap.get('imaging_modality')}

TASK:
Extract structured tumor measurements and response assessment from this radiology report.

OUTPUT FORMAT (JSON):
{{
  "lesions": [
    {{
      "location": "anatomic location",
      "current_dimensions_cm": {{"ap": <float or null>, "ml": <float or null>, "si": <float or null>}},
      "prior_dimensions_cm": {{"ap": <float or null>, "ml": <float or null>, "si": <float or null>}} or null,
      "percent_change": <float or null>,
      "enhancement_pattern": "description"
    }}
  ],
  "rano_assessment": {{
    "new_lesions": "yes" or "no" or "unclear",
    "rano_category": "CR" or "PR" or "SD" or "PD" or "INDETERMINATE"
  }},
  "radiologist_impression": "verbatim impression/conclusion",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **lesions**: Array of tumor lesions with measurements. Use empty array [] if:
   - No tumor present (complete response)
   - Report states "no measurable disease"
   - Measurements not provided

2. **location**: Anatomic location (e.g., "right frontal lobe", "left temporal region", "cerebellar vermis")

3. **current_dimensions_cm**: Tumor dimensions in centimeters
   - ap = anterior-posterior diameter
   - ml = medial-lateral diameter
   - si = superior-inferior diameter
   - Extract bidimensional measurements (two perpendicular diameters)
   - Use null for dimensions not reported

4. **prior_dimensions_cm**: Previous scan measurements if mentioned for comparison
   - Use null if no prior mentioned or if this is baseline scan

5. **percent_change**: Percentage change from prior scan
   - Calculate if current and prior both available: ((current - prior) / prior) × 100
   - Use null if cannot calculate

6. **enhancement_pattern**: Description of contrast enhancement (e.g., "ring-enhancing", "heterogeneous enhancement", "no enhancement")

7. **new_lesions**:
   - "yes" = new lesions identified
   - "no" = no new lesions
   - "unclear" = not mentioned

8. **rano_category**: Response Assessment in Neuro-Oncology criteria
   - "CR" (Complete Response) = disappearance of all enhancing tumor
   - "PR" (Partial Response) = ≥50% decrease in enhancing tumor
   - "SD" (Stable Disease) = does not qualify for CR, PR, or PD
   - "PD" (Progressive Disease) = ≥25% increase in enhancing tumor OR new lesions
   - "INDETERMINATE" = cannot determine or report doesn't assess response

HANDLING AMBIGUOUS LANGUAGE:
- "Stable compared to prior" → rano_category: "SD", extract prior measurements if given
- "Slight interval increase" → May be SD or PD depending on percentage (check if ≥25%)
- "Decreased size" → Calculate percent_change if possible; if ≥50% → PR, else SD
- "No significant change" → rano_category: "SD"
- "No evidence of tumor" → rano_category: "CR", lesions: []

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: Explicit measurements provided, clear RANO category stated or easily inferred
- MEDIUM: Qualitative descriptions only ("stable", "decreased") without exact measurements
- LOW: Minimal description or conflicting information

EXAMPLES:
Example 1 - Measurable disease:
  Document: "Right frontal ring-enhancing lesion measures 2.3 x 1.8 cm, previously 3.1 x 2.4 cm. Decreased size consistent with partial response."
  Output: {{
    "lesions": [{{
      "location": "right frontal lobe",
      "current_dimensions_cm": {{"ap": 2.3, "ml": 1.8, "si": null}},
      "prior_dimensions_cm": {{"ap": 3.1, "ml": 2.4, "si": null}},
      "percent_change": -25.8,
      "enhancement_pattern": "ring-enhancing"
    }}],
    "rano_assessment": {{
      "new_lesions": "no",
      "rano_category": "SD"
    }},
    "extraction_confidence": "HIGH"
  }}

Example 2 - Complete response:
  Document: "No evidence of enhancing tumor. Post-surgical changes in right frontal region."
  Output: {{
    "lesions": [],
    "rano_assessment": {{
      "new_lesions": "no",
      "rano_category": "CR"
    }},
    "extraction_confidence": "HIGH"
  }}

CRITICAL VALIDATION:
- lesions and rano_assessment are REQUIRED fields (cannot be null)
- lesions can be empty array [] but cannot be null
- radiologist_impression should contain verbatim conclusion text
"""

        return prompt

    def _generate_operative_note_prompt(self, gap: Dict) -> str:
        """Generate prompt for extent of resection extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text or clinical note formatting. ONLY return the JSON object.

You are a medical AI extracting extent of resection from an operative note.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Surgery Date: {gap.get('event_date')}
- Surgery Type: {gap.get('surgery_type')}

TASK:
Extract the extent of resection (EOR) from this operative note.

OUTPUT FORMAT - RETURN ONLY THIS JSON SCHEMA (no other text):
{{
  "extent_of_resection": "GTR" or "NTR" or "STR" or "BIOPSY" or "UNCLEAR",
  "percent_resection": <integer 0-100> or null,
  "surgeon_assessment": "verbatim surgeon's description of resection",
  "residual_tumor": "yes" or "no" or "unclear",
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **extent_of_resection**: Categorize using these definitions:
   - "GTR" (Gross Total Resection) = >95% tumor removed, no visible residual on imaging or surgeon assessment
   - "NTR" (Near Total Resection) = 90-95% removed, minimal residual
   - "STR" (Subtotal Resection) = <90% removed, significant residual
   - "BIOPSY" = Biopsy only, no resection performed
   - "UNCLEAR" = Cannot determine from operative note

2. **percent_resection**: Extract if surgeon specifies percentage (e.g., "approximately 85% resection"). Use null if not mentioned.

3. **surgeon_assessment**: Extract the surgeon's EXACT words describing the resection. Look for phrases in the "Procedure Description" or "Impression" sections.

4. **residual_tumor**: Based on surgeon's assessment OR post-operative imaging (MRI) description:
   - "yes" = surgeon mentions residual tumor, visible tumor remaining, OR post-op imaging shows residual enhancement
   - "no" = surgeon states gross total resection, no visible residual, OR post-op imaging shows no residual enhancement
   - "unclear" = not mentioned or ambiguous

   POST-OPERATIVE IMAGING TERMINOLOGY (if document is imaging report):
   - "Minimal residual enhancement" → residual_tumor = "yes", likely NTR or STR
   - "No residual enhancement" → residual_tumor = "no", likely GTR or NTR
   - "Complete resection cavity" → residual_tumor = "no", likely GTR
   - "Residual tumor" / "persistent enhancement" → residual_tumor = "yes"
   - "Decreased tumor burden" → residual_tumor likely "yes" (compare to pre-op)
   - "Volumetric analysis: X% reduction" → Use to estimate percent_resection

INTERPRETATION GUIDE FOR AMBIGUOUS LANGUAGE:
- "Complete resection" → GTR
- "Gross total resection" → GTR
- "Near-complete resection" → NTR
- "Near-total resection" → NTR
- "Maximal safe resection" → Check for percentage; if >95% → GTR, if 90-95% → NTR, if <90% → STR
- "Subtotal resection" → STR
- "Partial resection" → STR
- "Debulking" → STR
- "Biopsy only" → BIOPSY

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: Surgeon explicitly states EOR category or percentage
- MEDIUM: EOR inferred from descriptive language (e.g., "complete resection of visible tumor")
- LOW: Minimal description or conflicting information

EXAMPLES:
Example 1:
  Document: "Gross total resection achieved. No visible residual tumor. Estimate >95% removed."
  Output: {{
    "extent_of_resection": "GTR",
    "percent_resection": 95,
    "surgeon_assessment": "Gross total resection achieved. No visible residual tumor. Estimate >95% removed.",
    "residual_tumor": "no",
    "extraction_confidence": "HIGH"
  }}

Example 2:
  Document: "Maximal safe resection performed. Small amount of tumor left on eloquent cortex. Approximately 85% resection."
  Output: {{
    "extent_of_resection": "STR",
    "percent_resection": 85,
    "surgeon_assessment": "Maximal safe resection performed. Small amount of tumor left on eloquent cortex. Approximately 85% resection.",
    "residual_tumor": "yes",
    "extraction_confidence": "HIGH"
  }}

CRITICAL VALIDATION:
- extent_of_resection is REQUIRED (cannot be null)
- If truly unclear, use "UNCLEAR" but set extraction_confidence to "LOW"
- surgeon_assessment should contain verbatim text (REQUIRED field for validation)
"""

        return prompt

    def _generate_radiation_summary_prompt(self, gap: Dict) -> str:
        """
        Generate prompt for comprehensive radiation details extraction

        V5.0.1 Enhancement: Now includes protocol-specific radiation signatures
        """

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation', 'Unknown')

        # V5.0.1: Add protocol-specific radiation signature guidance
        radiation_signature_guidance = self._get_radiation_signature_guidance()

        prompt = f"""CRITICAL: You MUST return ONLY valid JSON in the exact schema specified below. Do NOT include any explanatory text, narrative summaries, or clinical note formatting. ONLY return the JSON object.

You are a medical AI extracting COMPREHENSIVE radiation treatment details from a radiation summary.

PATIENT CONTEXT:
- WHO 2021 Diagnosis: {who_dx}
- Expected Radiation per WHO 2021: {expected_radiation}
- Radiation Start Date: {gap.get('event_date')}

TASK:
Extract ALL radiation treatment details from this document, including dates, doses, fields, and any additional treatments.

OUTPUT FORMAT - RETURN ONLY THIS JSON SCHEMA (no other text):
{{
  "date_at_radiation_start": "YYYY-MM-DD",
  "date_at_radiation_stop": "YYYY-MM-DD",
  "completed_craniospinal_or_whole_ventricular_radiation_dose": <integer in cGy or null>,
  "completed_craniospinal_or_whole_ventricular_radiation_dose_unit": "cGy",
  "radiation_focal_or_boost_dose": <integer in cGy or null>,
  "completed_radiation_focal_or_boost_dose_unit": "cGy",
  "radiation_type": "focal" or "craniospinal" or "whole_ventricular" or "focal_with_boost" or "other",
  "any_other_radiation_treatments_not_captured": "description of any additional treatments or null",
  "total_dose_cgy": <integer>,
  "fractions": <integer>,
  "dose_per_fraction_cgy": <integer>,
  "radiation_fields": "description of all radiation fields",
  "target_volumes": ["list of all target volumes"],
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}

FIELD-SPECIFIC INSTRUCTIONS:
1. **date_at_radiation_start**: First day of radiation treatment (format: YYYY-MM-DD, e.g., "2024-03-15")
2. **date_at_radiation_stop**: Last day of radiation treatment (format: YYYY-MM-DD)
3. **total_dose_cgy**: TOTAL cumulative radiation dose delivered in centiGray (cGy). Convert from Gy if needed: 54 Gy = 5400 cGy
4. **fractions**: Total number of radiation fractions/sessions
5. **dose_per_fraction_cgy**: Dose delivered per fraction in cGy (e.g., 180 cGy per fraction)
6. **radiation_type**:
   - "focal" = radiation to tumor bed only
   - "craniospinal" = radiation to entire brain and spine
   - "whole_ventricular" = radiation to entire ventricular system
   - "focal_with_boost" = craniospinal/whole ventricular followed by focal boost
   - "other" = any other pattern
7. **completed_craniospinal_or_whole_ventricular_radiation_dose**: If patient received craniospinal OR whole ventricular radiation, extract the dose here (in cGy). Use null if patient received focal-only radiation.
8. **radiation_focal_or_boost_dose**: If patient received focal or boost radiation, extract the dose here (in cGy). Use null if patient received craniospinal-only without boost.

UNIT CONVERSION RULES:
- 1 Gy = 100 cGy
- Example: "54 Gy in 30 fractions" = total_dose_cgy: 5400, fractions: 30, dose_per_fraction_cgy: 180

COMMON SCENARIOS - REAL EXAMPLES FROM RADIANT PCA:
Example 1 - Focal Proton Therapy Only (High-Grade Glioma):
  Document: "Patient received proton beam therapy to tumor bed. Total dose 59.4 Gy delivered in 33 fractions (1.8 Gy per fraction) from 04/18/2018 to 06/08/2018. Target: Right frontal tumor bed."
  Output: {{
    "date_at_radiation_start": "2018-04-18",
    "date_at_radiation_stop": "2018-06-08",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
    "radiation_focal_or_boost_dose": 5940,
    "radiation_type": "focal",
    "total_dose_cgy": 5940,
    "fractions": 33,
    "dose_per_fraction_cgy": 180,
    "radiation_fields": "tumor bed",
    "any_other_radiation_treatments_not_captured": null
  }}

Example 2 - CRITICAL: Craniospinal + Focal Boost (High-Risk Medulloblastoma):
  Document: "Proton therapy delivered per ACNS0126 protocol. Craniospinal irradiation to 23.4 Gy in 13 fractions (1.8 Gy/fx), completed 05/15/2023. Followed by posterior fossa boost to bring total posterior fossa dose to 54 Gy (additional 30.6 Gy in 17 fractions). Final treatment 06/02/2023."
  Output: {{
    "date_at_radiation_start": "2023-04-25",
    "date_at_radiation_stop": "2023-06-02",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": 2340,
    "radiation_focal_or_boost_dose": 5400,
    "radiation_type": "focal_with_boost",
    "total_dose_cgy": 5400,
    "fractions": 30,
    "dose_per_fraction_cgy": 180,
    "radiation_fields": "craniospinal axis and posterior fossa",
    "target_volumes": ["craniospinal axis", "posterior fossa"],
    "any_other_radiation_treatments_not_captured": "Sequential craniospinal irradiation (2340 cGy) followed by posterior fossa boost (3060 cGy additional) to total 5400 cGy per ACNS0126 protocol"
  }}

CRITICAL NOTE FOR CRANIOSPINAL + BOOST:
- completed_craniospinal_or_whole_ventricular_radiation_dose = dose to brain/spine only (e.g., 2340 cGy)
- radiation_focal_or_boost_dose = CUMULATIVE dose to tumor bed (e.g., 5400 cGy)
- Tumor bed receives: craniospinal dose + boost dose
- Example: 2340 cGy (CSI) + 3060 cGy (boost) = 5400 cGy total to posterior fossa

Example 3 - Standard Focal Photon Therapy:
  Document: "External beam radiation therapy 54 Gy in 30 fractions to left temporal lesion, treatment dates 02/10/2019 to 03/28/2019."
  Output: {{
    "date_at_radiation_start": "2019-02-10",
    "date_at_radiation_stop": "2019-03-28",
    "completed_craniospinal_or_whole_ventricular_radiation_dose": null,
    "radiation_focal_or_boost_dose": 5400,
    "radiation_type": "focal",
    "total_dose_cgy": 5400,
    "fractions": 30
  }}

EXTRACTION CONFIDENCE CRITERIA:
- HIGH: All dates and doses explicitly stated, no ambiguity
- MEDIUM: Most fields present but some require inference (e.g., stop date calculated from start + duration)
- LOW: Missing critical fields (e.g., no stop date, unclear total dose) or document quality poor

{radiation_signature_guidance}

CRITICAL VALIDATION:
- total_dose_cgy is REQUIRED (cannot be null)
- date_at_radiation_start is REQUIRED (cannot be null)
- If you cannot find these fields, set extraction_confidence to "LOW" and provide your best estimate
- Use null only for truly absent information, not for information you're uncertain about
- If document mentions a protocol name (e.g., "ACNS0332", "SJMB12"), include it in any_other_radiation_treatments_not_captured
"""

        return prompt

    def _generate_chemotherapy_prompt(self, gap: Dict) -> str:
        """
        Generate chemotherapy extraction prompt

        V5.0.1 Enhancement: Now includes comprehensive protocol examples from 42-protocol knowledge base
        """

        # V5.0.1: Generate protocol examples from knowledge base
        protocol_examples = self._get_protocol_examples_for_prompt()

        prompt = f"""Extract chemotherapy protocol and treatment information from this clinical document.

OUTPUT FORMAT - RETURN ONLY THIS JSON:
{{
  "protocol_name": "e.g., COG ACNS0332, SJMB12, AALL0434, ANBL0532, or null",
  "on_protocol_status": "enrolled, treated_as_per_protocol, treated_like_protocol, or off_protocol",
  "agent_names": ["Drug1", "Drug2"] or [],
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "change_in_therapy_reason": "progression, toxicity, patient_preference, or null",
  "extraction_confidence": "HIGH, MEDIUM, or LOW"
}}

INSTRUCTIONS:
- protocol_name: Look for protocol identifiers like:
  {protocol_examples}
- on_protocol_status: Distinguish enrolled vs. treated "as per" or "like" protocol
- agent_names: List ALL chemotherapy drugs mentioned (including signature agents like nelarabine, isotretinoin, dinutuximab, carboplatin, etc.)
- change_in_therapy_reason: Extract if therapy was modified and why
- Set confidence LOW if information is incomplete

SIGNATURE AGENTS (highly specific to protocols):
- Nelarabine → T-cell ALL protocols (AALL0434)
- Carboplatin during radiation → High-risk medulloblastoma (ACNS0332)
- Isotretinoin for brain tumor → ACNS0332
- Isotretinoin for solid tumor → Neuroblastoma (ANBL0532)
- Dinutuximab (anti-GD2) → High-risk neuroblastoma (ANBL0532)
- Bevacizumab for DIPG → DIPG-BATS or PNOC trials
- Vorinostat with radiation → ACNS0621 or PBTC-030 (DIPG)
- Lomustine (CCNU) + Temozolomide → ACNS0423 (high-grade glioma)

IMPORTANT: If you see a signature agent, include it in agent_names and note the likely protocol.
"""
        return prompt

    def _get_protocol_examples_for_prompt(self) -> str:
        """
        Generate protocol examples string for extraction prompts

        V5.0.1: Uses expanded protocol knowledge base (42 protocols)

        Returns:
            Formatted string with protocol examples
        """
        if not PROTOCOL_KB_AVAILABLE or not ALL_PROTOCOLS:
            # Fallback to original examples
            return """
  COG protocols: ACNS0331, ACNS0332, ACNS0334, ACNS0423, ACNS0822, ACNS0831, etc.
  St. Jude protocols: SJMB12, SJMB03, SJYC07, SJ-DIPG-BATS
  Leukemia protocols: AALL0434 (T-ALL), ANHL0131 (NHL)
  Neuroblastoma: ANBL0532, ANBL0531
  Consortium: PNOC003, PNOC007, PNOC013, PBTC-026, PBTC-027, Head Start II/III"""

        # Generate comprehensive examples from knowledge base
        protocol_examples = []

        # Group protocols by category
        cog_cns = []
        cog_leuk_lymph = []
        cog_neuro = []
        st_jude = []
        consortium = []

        for protocol_id, protocol in ALL_PROTOCOLS.items():
            trial_id = protocol.get('trial_id', '')
            if trial_id and trial_id != 'N/A':
                if trial_id.startswith('ACNS'):
                    cog_cns.append(trial_id)
                elif trial_id.startswith('AALL') or trial_id.startswith('ANHL') or trial_id.startswith('AAHOD'):
                    cog_leuk_lymph.append(trial_id)
                elif trial_id.startswith('ANBL') or trial_id.startswith('AREN'):
                    cog_neuro.append(trial_id)
                elif trial_id.startswith('SJ'):
                    st_jude.append(trial_id)
                elif trial_id.startswith('PNOC') or trial_id.startswith('PBTC') or 'Head Start' in trial_id:
                    consortium.append(trial_id)

        if cog_cns:
            protocol_examples.append(f"COG CNS: {', '.join(sorted(set(cog_cns)))}")
        if cog_leuk_lymph:
            protocol_examples.append(f"COG Leukemia/Lymphoma: {', '.join(sorted(set(cog_leuk_lymph)))}")
        if cog_neuro:
            protocol_examples.append(f"COG Solid Tumors: {', '.join(sorted(set(cog_neuro)))}")
        if st_jude:
            protocol_examples.append(f"St. Jude: {', '.join(sorted(set(st_jude)))}")
        if consortium:
            protocol_examples.append(f"Consortium: {', '.join(sorted(set(consortium)))}")

        return "\n  ".join(protocol_examples) if protocol_examples else "COG, St. Jude, PBTC, PNOC protocols"

    def _get_radiation_signature_guidance(self) -> str:
        """
        Generate protocol-specific radiation signature guidance for extraction prompts

        V5.0.1: Uses expanded protocol knowledge base to identify protocol-specific radiation doses

        Returns:
            Formatted string with radiation signature guidance
        """
        if not PROTOCOL_KB_AVAILABLE or not ALL_PROTOCOLS:
            # Fallback to basic guidance
            return """
PROTOCOL-SPECIFIC RADIATION SIGNATURES (if mentioned in document):
- CSI 23.4 Gy → Standard-risk medulloblastoma (ACNS0331)
- CSI 36 Gy → High-risk medulloblastoma (ACNS0332)
- Focal 54-60 Gy → High-grade glioma (various protocols)
"""

        guidance = []
        guidance.append("\nPROTOCOL-SPECIFIC RADIATION SIGNATURES (if mentioned in document):")

        # Extract unique radiation signatures from protocol knowledge base
        radiation_signatures = {}
        for protocol_id, protocol in ALL_PROTOCOLS.items():
            signature_radiation = protocol.get('signature_radiation', {})
            if not signature_radiation:
                continue

            trial_id = protocol.get('trial_id', '')
            name = protocol.get('name', '')

            # CSI doses
            if 'csi_dose_gy' in signature_radiation:
                dose = signature_radiation['csi_dose_gy']
                key = f"CSI {dose} Gy"
                if key not in radiation_signatures:
                    radiation_signatures[key] = []
                radiation_signatures[key].append(f"{name} ({trial_id})")

            # Focal doses
            elif 'dose_gy' in signature_radiation:
                dose_range = signature_radiation['dose_gy']
                if isinstance(dose_range, list):
                    key = f"Focal {dose_range[0]}-{dose_range[1]} Gy"
                elif isinstance(dose_range, (int, float)):
                    key = f"Focal {dose_range} Gy"
                else:
                    continue

                if key not in radiation_signatures:
                    radiation_signatures[key] = []
                radiation_signatures[key].append(f"{name} ({trial_id})")

            # Whole-ventricular doses
            elif 'wv_dose_gy' in signature_radiation:
                dose = signature_radiation['wv_dose_gy']
                key = f"Whole-ventricular {dose} Gy"
                if key not in radiation_signatures:
                    radiation_signatures[key] = []
                radiation_signatures[key].append(f"{name} ({trial_id})")

        # Add special signatures (very distinctive)
        special_signatures = [
            ("CSI 18 Gy", "SJMB12 WNT stratum (very rare, only on trial!)"),
            ("CSI 23.4 Gy", "ACNS0331 standard-risk medulloblastoma"),
            ("CSI 36 Gy", "ACNS0332 high-risk medulloblastoma"),
            ("Whole-ventricular 18 Gy + boost", "ACNS0232 germinoma"),
            ("Focal 54-59.4 Gy", "High-grade glioma protocols (ACNS0423, ACNS0822, Stupp)")
        ]

        for dose_pattern, protocol_info in special_signatures:
            guidance.append(f"- {dose_pattern} → {protocol_info}")

        # Add from radiation_signatures dict
        for dose_pattern, protocols in sorted(radiation_signatures.items()):
            if len(protocols) <= 3:
                guidance.append(f"- {dose_pattern} → {', '.join(protocols)}")

        return "\n".join(guidance) if len(guidance) > 1 else ""

    def _generate_generic_prompt(self, gap: Dict) -> str:
        """Generate generic extraction prompt"""

        prompt = f"""You are a medical AI extracting information from a clinical document.

GAP TYPE: {gap.get('gap_type')}
CLINICAL SIGNIFICANCE: {gap.get('clinical_significance')}

TASK:
Extract relevant structured information from this document.

OUTPUT FORMAT (JSON):
{{
  "extracted_data": {{}},
  "extraction_confidence": "HIGH" or "MEDIUM" or "LOW"
}}
"""

        return prompt

    def _fetch_binary_document(self, fhir_target: str) -> Optional[str]:
        """
        Fetch binary document from S3 and extract text

        CORRECT APPROACH (following MVP workflow):
        1. Query v_binary_files to find Binary IDs for DiagnosticReport or DocumentReference
        2. Fetch the Binary from S3 using BinaryFileAgent

        Args:
            fhir_target: FHIR target like "DiagnosticReport/12345" or "DocumentReference/abc" or "Binary/xyz"

        Returns:
            Extracted text or None
        """
        # Extract resource type and ID from FHIR target
        if '/' not in fhir_target:
            logger.warning(f"Invalid FHIR target format: {fhir_target}")
            return None

        resource_type, resource_id = fhir_target.split('/', 1)

        # For DiagnosticReport or DocumentReference, query v_binary_files to find associated Binary
        if resource_type in ['DiagnosticReport', 'DocumentReference']:
            try:
                # Query v_binary_files for this document reference
                query = f"""
                SELECT binary_id, content_type
                FROM fhir_prd_db.v_binary_files
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                  AND document_reference_id = '{resource_id}'
                LIMIT 1
                """

                # V4.6 BUG FIX #1: Pass investigation engine for empty result analysis
                results = query_athena(
                    query,
                    f"Finding Binary for {resource_type}/{resource_id}",
                    suppress_output=True,
                    investigation_engine=self.investigation_engine if hasattr(self, 'investigation_engine') else None,
                    schema_loader=self.schema_loader if hasattr(self, 'schema_loader') else None
                )

                if not results:
                    logger.warning(f"No Binary found for {fhir_target} in v_binary_files")
                    return None

                binary_id = results[0].get('binary_id')
                content_type = results[0].get('content_type', 'application/pdf')

                logger.info(f"Found Binary {binary_id} for {fhir_target}")

            except Exception as e:
                logger.error(f"Error querying v_binary_files for {fhir_target}: {e}")
                return None
        elif resource_type == 'Binary':
            # For direct Binary references, query v_binary_files to get actual content_type
            # (Alternative documents from escalation come as "Binary/xyz" but we still need content_type)
            binary_id = fhir_target
            try:
                query = f"""
                SELECT content_type
                FROM fhir_prd_db.v_binary_files
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                  AND binary_id = '{binary_id}'
                LIMIT 1
                """

                # V4.6 BUG FIX #1: Pass investigation engine for empty result analysis
                results = query_athena(
                    query,
                    f"Finding content_type for {binary_id}",
                    suppress_output=True,
                    investigation_engine=self.investigation_engine if hasattr(self, 'investigation_engine') else None,
                    schema_loader=self.schema_loader if hasattr(self, 'schema_loader') else None
                )

                if results and results[0].get('content_type'):
                    content_type = results[0]['content_type']
                    logger.info(f"Found content_type {content_type} for {binary_id}")
                else:
                    # Fallback to application/pdf if not found
                    content_type = "application/pdf"
                    logger.warning(f"No content_type found for {binary_id} in v_binary_files, defaulting to application/pdf")

            except Exception as e:
                logger.error(f"Error querying content_type for {binary_id}: {e}")
                content_type = "application/pdf"  # Fallback
        else:
            logger.warning(f"Unknown resource type: {resource_type}")
            return None

        # Fetch using BinaryFileAgent
        try:
            extracted_text, error = self.binary_agent.extract_text_from_binary(
                binary_id=binary_id,
                patient_fhir_id=self.athena_patient_id,
                content_type=content_type
            )

            if error:
                logger.warning(f"Error extracting text from {binary_id}: {error}")
                # Track failed binary fetch
                self._track_binary_fetch(
                    binary_id=binary_id,
                    content_type=content_type,
                    success=False,
                    metadata={'error': str(error), 'resource_type': resource_type}
                )
                return None

            # Track successful binary fetch
            self._track_binary_fetch(
                binary_id=binary_id,
                content_type=content_type,
                success=True,
                metadata={'text_length': len(extracted_text) if extracted_text else 0, 'resource_type': resource_type}
            )

            # V4.6 BUG FIX #2/#3: Store extracted text in binary_extractions for gap-filling reuse
            self.binary_extractions.append({
                'binary_id': binary_id,
                'extracted_text': extracted_text,
                'content_type': content_type,
                'resource_type': resource_type,
                'fhir_target': fhir_target
            })

            return extracted_text

        except Exception as e:
            logger.error(f"Error fetching binary {binary_id}: {e}")
            # Track failed binary fetch
            self._track_binary_fetch(
                binary_id=binary_id,
                content_type=content_type,
                success=False,
                metadata={'error': str(e), 'resource_type': resource_type}
            )
            return None

    def _get_patient_chemotherapy_keywords(self) -> List[str]:
        """
        Generate patient-specific chemotherapy keywords based on schema-extracted drug names

        V5.0.1 Enhancement: Now includes protocol trial IDs from expanded knowledge base (42 protocols)

        Returns:
            List of chemotherapy keywords including patient's actual drug names and protocol IDs
        """
        keywords = [
            # Protocol terms (generic)
            'protocol', 'trial', 'study', 'enrolled', 'enrollment', 'consent', 'regimen',
            # Major consortia
            'cog', 'pog', 'pbtc', 'pnoc', 'ccg',
            # Chemotherapy terms
            'chemotherapy', 'chemo', 'agent', 'drug', 'cycle', 'course', 'infusion',
            # Change indicators
            'changed', 'modified', 'discontinued', 'stopped', 'held', 'dose reduction', 'escalation', 'toxicity', 'progression'
        ]

        # V5.0.1: Add specific protocol trial IDs from knowledge base
        if PROTOCOL_KB_AVAILABLE and ALL_PROTOCOLS:
            # Extract trial IDs from all 42 protocols
            for protocol_id, protocol in ALL_PROTOCOLS.items():
                trial_id = protocol.get('trial_id', '')
                if trial_id and trial_id != 'N/A':
                    keywords.append(trial_id.lower())

                # Also add common acronyms (e.g., "ACNS0332" → "acns0332", "acns", "0332")
                if trial_id.startswith('ACNS') or trial_id.startswith('ANBL') or trial_id.startswith('ANHL'):
                    keywords.append(trial_id[:4].lower())  # Add "acns", "anbl", etc.

                # Add protocol name components
                name = protocol.get('name', '')
                if 'SJMB' in name:
                    keywords.extend(['sjmb', 'sjmb12', 'sjmb03', 'sjmb96'])
                if 'Head Start' in name:
                    keywords.extend(['head start', 'headstart'])
                if 'DIPG' in name or 'dipg' in name.lower():
                    keywords.extend(['dipg', 'dipg-bats'])

            # Add signature agents (highly specific protocol fingerprints)
            try:
                signature_agents = get_all_signature_agents()
                keywords.extend([agent.lower() for agent in signature_agents])
            except:
                pass  # Fail silently if function not available

        # Add patient-specific drug names from schema-extracted chemotherapy data
        for event in self.timeline_events:
            if event.get('event_type', '').startswith('chemotherapy'):
                drug_names = event.get('episode_drug_names', '')
                if drug_names:
                    # Split on common delimiters and clean
                    for drug in drug_names.replace(',', ';').replace('/', ';').split(';'):
                        drug = drug.strip().lower()
                        if drug and len(drug) > 3:  # Skip very short strings
                            keywords.append(drug)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(keywords))

    def _validate_document_content(self, extracted_text: str, gap_type: str) -> Tuple[bool, str]:
        """
        Validate that document content matches expected gap type (Agent 1 validation)

        Args:
            extracted_text: The extracted text from binary
            gap_type: Type of gap (missing_eor, missing_radiation_details, etc.)

        Returns:
            Tuple of (is_valid, reason)
        """
        if not extracted_text or len(extracted_text) < 100:
            return False, "Document too short or empty"

        text_lower = extracted_text.lower()

        # Validation keywords by gap type
        validation_rules = {
            'missing_eor': {
                'required_keywords': ['surgery', 'operative', 'procedure', 'resection', 'excision'],
                'forbidden_keywords': ['radiation', 'chemotherapy'],
                'min_keywords': 1
            },
            'missing_radiation_details': {
                'required_keywords': [
                    # Core radiation terms
                    'radiation', 'radiotherapy', 'radiosurgery', 'xrt', 'rt',
                    # Dose terms
                    'dose', 'gy', 'cgy', 'gray', 'dosage', 'fraction', 'fractions', 'fractionation',
                    # Treatment types
                    'imrt', 'sbrt', 'srs', 'cyberknife', 'gamma knife', 'proton',
                    # Anatomical patterns
                    'focal', 'craniospinal', 'csi', 'whole brain', 'wbrt', 'ventricular',
                    'spine', 'boost', 'local', 'field',
                    # Treatment planning
                    'treatment', 'therapy', 'plan', 'planning', 'simulation', 'sim',
                    # Delivery terms
                    'delivery', 'beam', 'beams', 'port', 'fields',
                    # Common abbreviations
                    'tx', 'rx'
                ],
                'forbidden_keywords': [],
                'min_keywords': 1  # Lowered to 1 to maximize document capture
            },
            'imaging_conclusion': {
                'required_keywords': ['imaging', 'mri', 'ct', 'scan', 'brain', 'tumor', 'mass'],
                'forbidden_keywords': [],
                'min_keywords': 1
            },
            'missing_chemotherapy_details': {
                'required_keywords': self._get_patient_chemotherapy_keywords(),
                'forbidden_keywords': [],
                'min_keywords': 1
            }
        }

        rules = validation_rules.get(gap_type)
        if not rules:
            return True, "No validation rules for this gap type"

        # Check for required keywords
        found_keywords = [kw for kw in rules['required_keywords'] if kw in text_lower]

        if len(found_keywords) < rules['min_keywords']:
            return False, f"Missing required keywords. Found: {found_keywords}, need at least {rules['min_keywords']}"

        # Check for forbidden keywords (indicates wrong document type)
        found_forbidden = [kw for kw in rules['forbidden_keywords'] if kw in text_lower]
        if found_forbidden:
            return False, f"Document contains forbidden keywords: {found_forbidden} (wrong document type)"

        return True, f"Document validated with keywords: {found_keywords}"

    def _retry_extraction_with_clarification(self, gap: Dict, extracted_text: str, first_result: Dict, missing_fields: List[str]) -> Optional[Dict]:
        """
        Agent 1 re-prompts Agent 2 (MedGemma) with clarification when extraction incomplete

        Args:
            gap: The extraction gap
            extracted_text: Original document text
            first_result: First extraction attempt result
            missing_fields: List of missing required fields

        Returns:
            Second extraction result or None
        """
        logger.info(f"Re-extraction attempt for {gap['gap_type']} - missing fields: {missing_fields}")
        print(f"    🔄 Re-extraction: First attempt missing {missing_fields}")

        # Field-specific guidance for re-extraction
        field_guidance = {
            'extent_of_resection': 'Look for phrases like "gross total resection", "subtotal resection", "biopsy only" in operative note AND post-operative imaging (MRI within 72 hours)',
            'surgeon_assessment': 'Extract verbatim text from surgeon describing the resection outcome (usually in procedure description or impression)',
            'date_at_radiation_start': 'Find the first date radiation was delivered (format: YYYY-MM-DD). May be in "Treatment Start" or "Course Start" section',
            'date_at_radiation_stop': 'Find the last date radiation was delivered (format: YYYY-MM-DD). May be calculated from start date + duration',
            'total_dose_cgy': 'Find total cumulative dose in cGy or Gy (convert: 1 Gy = 100 cGy). Look for phrases like "total dose", "cumulative dose"',
            'radiation_type': 'Determine if focal (tumor only), craniospinal (brain+spine), whole_ventricular, or focal_with_boost',
            'lesions': 'Extract array of tumor lesions with measurements. Use [] if no tumor present',
            'rano_assessment': 'Assess response using RANO criteria based on size change and new lesions',
            'protocol_name': 'Look for protocol name or study number (e.g., "COG ACNS0126", "SJMB12", "per protocol"). Check headers, treatment sections, enrollment forms',
            'on_protocol_status': 'Determine if patient is "enrolled" (formally consented to study), "treated_as_per_protocol" (following study treatment plan), "treated_like_protocol" (similar but not enrolled), or "off_protocol"',
            'agent_names': 'Extract ALL chemotherapy drug names mentioned (e.g., Temozolomide, Vincristine, Carboplatin). Return as array. Look in medication lists, treatment plans, infusion records',
            'start_date': 'Find first date of chemotherapy administration for THIS treatment episode (format: YYYY-MM-DD)',
            'end_date': 'Find last date of chemotherapy for THIS treatment episode (format: YYYY-MM-DD). May be listed as "completion date" or calculated from cycles',
            'change_in_therapy_reason': 'If therapy was modified, find reason: "progression" (disease not responding), "toxicity" (side effects), "patient_preference" (family request), or null if no change'
        }

        # Build specific instructions for missing fields
        specific_instructions = []
        for field in missing_fields:
            guidance = field_guidance.get(field, f'Extract {field} from the document')
            specific_instructions.append(f"- {field}: {guidance}")

        # Build clarification prompt
        clarification = f"""
IMPORTANT: The first extraction attempt was incomplete.

MISSING REQUIRED FIELDS: {', '.join(missing_fields)}

Please re-extract from the same document, focusing specifically on finding these missing fields:
{chr(10).join(specific_instructions)}

INSTRUCTIONS:
1. Search the document carefully for each missing field
2. If a field is truly not present in the document, set it to null
3. If you set required fields to null, set extraction_confidence to "LOW"
4. Return ALL fields from the original schema, not just the missing ones
"""

        # Generate new prompt with clarification
        base_prompt = self._generate_medgemma_prompt(gap)
        clarified_prompt = base_prompt + "\n\n" + clarification
        full_prompt = f"{clarified_prompt}\n\nDOCUMENT TEXT:\n{extracted_text}"

        try:
            result = self.medgemma_agent.extract(full_prompt, temperature=0.1)
            if result.success:
                print(f"    ✅ Re-extraction complete")
                return result.extracted_data
            else:
                print(f"    ❌ Re-extraction failed: {result.error}")
                return None
        except Exception as e:
            logger.error(f"Re-extraction error: {e}")
            return None

    def _integrate_extraction_into_timeline(self, gap: Dict, extraction_data: Dict):
        """
        Integrate MedGemma extraction results into timeline events

        CRITICAL FIX: Handles date mismatches by creating NEW events when extracted dates
        don't match gap event_date (e.g., TIFF from external institution with different dates)

        Args:
            gap: The gap that was filled
            extraction_data: The extracted data from MedGemma
        """
        event_date = gap.get('event_date')
        gap_type = gap.get('gap_type')

        # V4.6 BUG FIX #2: Extract document ID for source_document_ids tracking
        document_id = gap.get('medgemma_target', '')
        if document_id.startswith('DocumentReference/'):
            document_id = document_id.replace('DocumentReference/', '')

        # NOTE: Date mismatch detection now happens earlier in Phase 4 (before validation)
        # This function only handles NORMAL merging of data into existing events

        # NORMAL PATH: Find matching event and merge data
        event_merged = False
        for event in self.timeline_events:
            if event.get('event_date') == event_date:
                # Add medgemma_extraction field to event
                if gap_type == 'imaging_conclusion' and event.get('event_type') == 'imaging':
                    # Merge imaging-specific fields
                    event['report_conclusion'] = extraction_data.get('radiologist_impression', '')
                    event['medgemma_extraction'] = extraction_data
                    # V4.6 BUG FIX #2: Track source document for gap-filling reuse
                    if document_id:
                        if 'source_document_ids' not in event:
                            event['source_document_ids'] = []
                        if document_id not in event['source_document_ids']:
                            event['source_document_ids'].append(document_id)
                    logger.info(f"Merged imaging conclusion for {event_date}: {event.get('report_conclusion', '')[:100]}")
                    event_merged = True
                    break
                elif gap_type == 'missing_eor' and event.get('event_type') == 'surgery':
                    # V4 ENHANCEMENT: Multi-source EOR tracking with adjudication
                    from lib.feature_object import FeatureObject
                    from lib.eor_orchestrator import EOROrchestrator

                    # Determine source type from gap metadata
                    source_type = gap.get('extraction_source', 'operative_record')  # From alternative doc tracking
                    extracted_eor = extraction_data.get('extent_of_resection')
                    confidence = extraction_data.get('extraction_confidence', 'UNKNOWN')

                    # Check if we already have EOR data (from previous extraction)
                    existing_eor_feature = event.get('extent_of_resection_v4')

                    if existing_eor_feature and isinstance(existing_eor_feature, dict):
                        # MULTI-SOURCE SCENARIO: We have EOR from another source already
                        # Add this as a second source
                        # Use from_dict() to properly reconstruct SourceRecord objects
                        feature = FeatureObject.from_dict(existing_eor_feature)
                        feature.add_source(
                            source_type=source_type,
                            extracted_value=extracted_eor,
                            extraction_method='medgemma_llm',
                            confidence=confidence,
                            source_id=gap.get('medgemma_target'),
                            raw_text=extraction_data.get('surgeon_assessment', '')[:200]
                        )

                        # Check for conflict and adjudicate if needed
                        if feature.has_conflict():
                            orchestrator = EOROrchestrator()

                            # Extract EOR values and confidences from sources
                            sources_by_type = {}
                            for src in feature.sources:
                                sources_by_type[src.source_type] = {
                                    'eor': src.extracted_value,
                                    'confidence': src.confidence
                                }

                            operative_note_data = sources_by_type.get('operative_record', {})
                            postop_imaging_data = sources_by_type.get('postop_imaging', {})

                            if operative_note_data and postop_imaging_data:
                                # Use orchestrator to adjudicate
                                adjudicated_eor = orchestrator.adjudicate_eor(
                                    operative_note_eor=operative_note_data.get('eor'),
                                    operative_note_confidence=operative_note_data.get('confidence'),
                                    postop_imaging_eor=postop_imaging_data.get('eor'),
                                    postop_imaging_confidence=postop_imaging_data.get('confidence'),
                                    patient_age=self.patient_demographics.get('age'),
                                    tumor_location=extraction_data.get('tumor_site')
                                )

                                feature.adjudicate(
                                    final_value=adjudicated_eor['final_eor'],
                                    method=adjudicated_eor['method'],
                                    rationale=adjudicated_eor['rationale'],
                                    adjudicated_by='eor_orchestrator_v1',
                                    requires_manual_review=adjudicated_eor['requires_manual_review']
                                )
                                logger.info(f"🔀 EOR Adjudication for {event_date}: {adjudicated_eor['final_eor']} (method: {adjudicated_eor['method']})")

                        # Store V4 FeatureObject format using to_dict() for proper serialization
                        event['extent_of_resection_v4'] = feature.to_dict()
                        # Keep V3 backward compatibility
                        event['extent_of_resection'] = feature.value
                    else:
                        # SINGLE-SOURCE SCENARIO: First EOR extraction for this surgery
                        feature = FeatureObject.from_single_source(
                            value=extracted_eor,
                            source_type=source_type,
                            extracted_value=extracted_eor,
                            extraction_method='medgemma_llm',
                            confidence=confidence,
                            source_id=gap.get('medgemma_target'),
                            raw_text=extraction_data.get('surgeon_assessment', '')[:200]
                        )

                        # Store V4 FeatureObject format using to_dict() for proper serialization
                        event['extent_of_resection_v4'] = feature.to_dict()
                        # Keep V3 backward compatibility
                        event['extent_of_resection'] = extracted_eor

                    # Always update other fields
                    event['tumor_site'] = extraction_data.get('tumor_site')
                    event['medgemma_extraction'] = extraction_data
                    # V4.6 BUG FIX #2: Track source document for gap-filling reuse
                    if document_id:
                        if 'source_document_ids' not in event:
                            event['source_document_ids'] = []
                        if document_id not in event['source_document_ids']:
                            event['source_document_ids'].append(document_id)
                    logger.info(f"Merged EOR for {event_date}: {event.get('extent_of_resection')} (sources: {len(event['extent_of_resection_v4']['sources'])})")
                    event_merged = True
                    break
                elif gap_type in ['missing_radiation_dose', 'missing_radiation_details'] and 'radiation' in event.get('event_type', ''):
                    # Merge radiation-specific fields - handle both start and end events
                    # Try multiple field name variants (different prompts may return different field names)
                    event['total_dose_cgy'] = (
                        extraction_data.get('total_dose_cgy') or
                        extraction_data.get('radiation_focal_or_boost_dose') or
                        extraction_data.get('completed_radiation_focal_or_boost_dose') or
                        extraction_data.get('completed_craniospinal_or_whole_ventricular_radiation_dose')
                    )
                    event['radiation_type'] = extraction_data.get('radiation_type')
                    event['radiation_fields'] = extraction_data.get('radiation_fields')
                    event['date_at_radiation_start'] = extraction_data.get('date_at_radiation_start')
                    event['date_at_radiation_stop'] = extraction_data.get('date_at_radiation_stop')
                    event['medgemma_extraction'] = extraction_data
                    # V4.6 BUG FIX #2: Track source document for gap-filling reuse
                    if document_id:
                        if 'source_document_ids' not in event:
                            event['source_document_ids'] = []
                        if document_id not in event['source_document_ids']:
                            event['source_document_ids'].append(document_id)
                    logger.info(f"Merged radiation details for {event_date}: {event.get('total_dose_cgy')} cGy")
                    event_merged = True
                    break
                elif gap_type == 'missing_chemotherapy_details' and 'chemotherapy' in event.get('event_type', ''):
                    # Merge chemotherapy-specific fields
                    event['chemotherapy_agents'] = extraction_data.get('chemotherapy_agents')
                    event['chemotherapy_protocol'] = extraction_data.get('chemotherapy_protocol')
                    event['chemotherapy_intent'] = extraction_data.get('chemotherapy_intent')
                    event['medgemma_extraction'] = extraction_data
                    # V4.6 BUG FIX #2: Track source document for gap-filling reuse
                    if document_id:
                        if 'source_document_ids' not in event:
                            event['source_document_ids'] = []
                        if document_id not in event['source_document_ids']:
                            event['source_document_ids'].append(document_id)
                    logger.info(f"Merged chemotherapy details for {event_date}: {event.get('chemotherapy_agents')}")
                    event_merged = True
                    break

        if not event_merged:
            logger.warning(f"⚠️  No matching event found for gap_type={gap_type}, event_date={event_date}")

    def _assess_data_completeness(self) -> Dict:
        """
        V4.6: Assess data completeness across treatment modalities
        (Extracted from _phase4_5_assess_extraction_completeness for reuse)

        Returns:
            Assessment dictionary with completeness metrics
        """
        assessment = {
            'surgery': {'total': 0, 'missing_eor': 0, 'complete': 0},
            'radiation': {'total': 0, 'missing_dose': 0, 'complete': 0},
            'imaging': {'total': 0, 'missing_conclusion': 0, 'complete': 0},
            'chemotherapy': {'total': 0, 'missing_agents': 0, 'complete': 0}
        }

        # Assess surgery events
        for event in self.timeline_events:
            if event.get('event_type') == 'surgery':
                assessment['surgery']['total'] += 1
                if not event.get('extent_of_resection'):
                    assessment['surgery']['missing_eor'] += 1
                else:
                    assessment['surgery']['complete'] += 1

            # Assess radiation events
            elif event.get('event_type') == 'radiation_start':
                assessment['radiation']['total'] += 1
                if not event.get('total_dose_cgy'):
                    assessment['radiation']['missing_dose'] += 1
                else:
                    assessment['radiation']['complete'] += 1

            # Assess imaging events
            elif event.get('event_type') == 'imaging':
                assessment['imaging']['total'] += 1
                if not event.get('report_conclusion'):
                    assessment['imaging']['missing_conclusion'] += 1
                else:
                    assessment['imaging']['complete'] += 1

            # Assess chemotherapy events
            elif event.get('event_type') == 'chemotherapy_start':
                assessment['chemotherapy']['total'] += 1
                if not event.get('chemotherapy_agents') and not event.get('episode_drug_names'):
                    assessment['chemotherapy']['missing_agents'] += 1
                else:
                    assessment['chemotherapy']['complete'] += 1

        return assessment

    def _validate_minimal_completeness(self):
        """
        V4.6: Validate minimal timeline completeness before extracting optional features.

        REQUIRED (Core Timeline):
        - WHO Diagnosis
        - All tumor surgeries/biopsies
        - All chemotherapy start/stop dates
        - All radiation start/stop dates

        OPTIONAL (Features):
        - Extent of resection
        - Radiation doses
        - Imaging conclusions
        - Progression/recurrence flags
        - Protocols
        """
        logger.info("\n✅ V4.6 PHASE 2.1: Validating minimal timeline completeness...")

        validation = {
            'who_diagnosis': {'present': False, 'status': 'REQUIRED'},
            'surgeries': {'count': 0, 'status': 'REQUIRED'},
            'chemotherapy': {'count': 0, 'missing_end_dates': 0, 'status': 'REQUIRED'},
            'radiation': {'count': 0, 'missing_end_dates': 0, 'status': 'REQUIRED'},
            'optional_features': {
                'extent_of_resection': 0,
                'radiation_doses': 0,
                'imaging_conclusions': 0,
                'progression_flags': 0,
                'protocols': 0
            }
        }

        # Check WHO Diagnosis
        if self.who_2021_classification:
            validation['who_diagnosis']['present'] = True
            who_grade = self.who_2021_classification.get('who_grade') or self.who_2021_classification.get('final_diagnosis', 'Unknown')
            logger.info(f"  ✅ WHO Diagnosis: {who_grade}")
        else:
            logger.warning("  ⚠️  WHO Diagnosis: MISSING (REQUIRED)")

        # Count surgeries/biopsies
        surgery_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'surgery']
        validation['surgeries']['count'] = len(surgery_events)

        if validation['surgeries']['count'] > 0:
            logger.info(f"  ✅ Surgeries/Biopsies: {validation['surgeries']['count']} found")
        else:
            logger.warning("  ⚠️  Surgeries/Biopsies: NONE FOUND (REQUIRED)")

        # Validate chemotherapy start/stop dates
        chemo_start_events = [e for e in self.timeline_events
                             if e.get('event_type') in ['chemo_start', 'chemotherapy_start']]
        validation['chemotherapy']['count'] = len(chemo_start_events)

        for chemo in chemo_start_events:
            chemo_end = chemo.get('relationships', {}).get('related_events', {}).get('chemotherapy_end')
            if not chemo_end:
                validation['chemotherapy']['missing_end_dates'] += 1

        if validation['chemotherapy']['count'] > 0:
            logger.info(f"  ✅ Chemotherapy Regimens: {validation['chemotherapy']['count']} found")
            if validation['chemotherapy']['missing_end_dates'] > 0:
                logger.warning(f"  ⚠️  Chemotherapy: {validation['chemotherapy']['missing_end_dates']} missing end dates")
        else:
            logger.info("  ℹ️  Chemotherapy: None found (acceptable for surgical-only cases)")

        # Validate radiation start/stop dates
        radiation_start_events = [e for e in self.timeline_events
                                 if e.get('event_type') == 'radiation_start']
        validation['radiation']['count'] = len(radiation_start_events)

        for rad in radiation_start_events:
            rad_end = rad.get('relationships', {}).get('related_events', {}).get('radiation_end')
            if not rad_end:
                validation['radiation']['missing_end_dates'] += 1

        if validation['radiation']['count'] > 0:
            logger.info(f"  ✅ Radiation Courses: {validation['radiation']['count']} found")
            if validation['radiation']['missing_end_dates'] > 0:
                logger.warning(f"  ⚠️  Radiation: {validation['radiation']['missing_end_dates']} missing end dates")
        else:
            logger.info("  ℹ️  Radiation: None found (acceptable for non-radiation cases)")

        # Count optional features (for context only)
        for event in self.timeline_events:
            if event.get('extent_of_resection'):
                validation['optional_features']['extent_of_resection'] += 1
            if event.get('radiation_dose_gy'):
                validation['optional_features']['radiation_doses'] += 1
            if event.get('report_conclusion'):
                validation['optional_features']['imaging_conclusions'] += 1
            if event.get('progression_flag'):
                validation['optional_features']['progression_flags'] += 1
            if event.get('protocol_name'):
                validation['optional_features']['protocols'] += 1

        logger.info("\n  OPTIONAL FEATURES (will be extracted in Phase 3, 4, 4.5):")
        logger.info(f"    - Extent of Resection: {validation['optional_features']['extent_of_resection']}")
        logger.info(f"    - Radiation Doses: {validation['optional_features']['radiation_doses']}")
        logger.info(f"    - Imaging Conclusions: {validation['optional_features']['imaging_conclusions']}")
        logger.info(f"    - Progression Flags: {validation['optional_features']['progression_flags']}")
        logger.info(f"    - Protocols: {validation['optional_features']['protocols']}")

        # Determine overall completeness
        core_complete = (
            validation['who_diagnosis']['present'] and
            validation['surgeries']['count'] > 0
        )

        if core_complete:
            logger.info("\n  ✅ CORE TIMELINE: Complete (WHO + Surgeries present)")
        else:
            logger.warning("\n  ⚠️  CORE TIMELINE: Incomplete (missing WHO diagnosis or surgeries)")
            logger.warning("  → Proceeding to Phase 2.5+ to extract additional features")

        # Store validation results
        self.minimal_completeness_validation = validation

        # V4.6 ENHANCEMENT: Trigger Investigation Engine for core timeline gaps
        if self.investigation_engine:
            logger.info("\n  🔍 V4.6 ENHANCEMENT: Investigating core timeline gaps...")

            # Investigate missing surgeries
            if validation['surgeries']['count'] == 0:
                logger.info("  → Investigating missing surgeries...")
                investigation = self.investigation_engine.investigate_gap_filling_failure(
                    gap_type='missing_surgeries',
                    event={'event_type': 'surgery', 'patient_id': self.patient_id},
                    reason="No surgery events found in v_procedures_tumor"
                )
                if investigation.get('suggested_alternatives'):
                    logger.info(f"    💡 {investigation.get('explanation', '')}")
                    for alt in investigation['suggested_alternatives']:
                        logger.info(f"      - {alt.get('method', 'unknown')}: {alt.get('description', '')} (confidence: {alt.get('confidence', 0):.0%})")

            # Investigate missing chemo end dates
            if validation['chemotherapy']['missing_end_dates'] > 0:
                logger.info(f"  → Investigating {validation['chemotherapy']['missing_end_dates']} missing chemotherapy end dates...")
                investigation = self.investigation_engine.investigate_gap_filling_failure(
                    gap_type='missing_chemo_end_dates',
                    event={'event_type': 'chemotherapy', 'patient_id': self.patient_id},
                    reason=f"{validation['chemotherapy']['missing_end_dates']} chemotherapy regimens missing end dates"
                )
                if investigation.get('suggested_alternatives'):
                    logger.info(f"    💡 {investigation.get('explanation', '')}")
                    for alt in investigation['suggested_alternatives']:
                        logger.info(f"      - {alt.get('method', 'unknown')}: {alt.get('description', '')} (confidence: {alt.get('confidence', 0):.0%})")

            # Investigate missing radiation end dates
            if validation['radiation']['missing_end_dates'] > 0:
                logger.info(f"  → Investigating {validation['radiation']['missing_end_dates']} missing radiation end dates...")
                investigation = self.investigation_engine.investigate_gap_filling_failure(
                    gap_type='missing_radiation_end_dates',
                    event={'event_type': 'radiation', 'patient_id': self.patient_id},
                    reason=f"{validation['radiation']['missing_end_dates']} radiation courses missing end dates"
                )
                if investigation.get('suggested_alternatives'):
                    logger.info(f"    💡 {investigation.get('explanation', '')}")
                    for alt in investigation['suggested_alternatives']:
                        logger.info(f"      - {alt.get('method', 'unknown')}: {alt.get('description', '')} (confidence: {alt.get('confidence', 0):.0%})")

            # V4.6.3 PHASE 2.2: EXECUTE REMEDIATION STRATEGIES
            logger.info("\n🔧 V4.6.3 PHASE 2.2: Core Timeline Gap Remediation")
            logger.info("  Executing Investigation Engine suggestions...")

            remediation_count = 0

            # Remediate missing chemotherapy end dates
            if validation['chemotherapy']['missing_end_dates'] > 0:
                logger.info(f"  → Remediating {validation['chemotherapy']['missing_end_dates']} missing chemotherapy end dates...")
                filled = self._remediate_missing_chemo_end_dates()
                remediation_count += filled
                if filled > 0:
                    logger.info(f"    ✅ Found {filled} chemotherapy end dates")
                    validation['chemotherapy']['missing_end_dates'] -= filled

            # Remediate missing radiation end dates
            if validation['radiation']['missing_end_dates'] > 0:
                logger.info(f"  → Remediating {validation['radiation']['missing_end_dates']} missing radiation end dates...")
                filled = self._remediate_missing_radiation_end_dates()
                remediation_count += filled
                if filled > 0:
                    logger.info(f"    ✅ Found {filled} radiation end dates")
                    validation['radiation']['missing_end_dates'] -= filled

            # V4.6.4: Remediate missing extent of resection
            eor_filled = self._remediate_missing_extent_of_resection()
            if eor_filled > 0:
                remediation_count += eor_filled

            if remediation_count > 0:
                logger.info(f"\n  ✅ V4.6.3-V4.6.4: Remediated {remediation_count} missing data points")
            else:
                logger.info(f"\n  ⚠️  V4.6.3-V4.6.4: No data found via remediation")

        return validation

    def _phase4_5_assess_extraction_completeness(self):
        """
        V4.6: Orchestrator assessment with ITERATIVE GAP-FILLING
        Validates that critical fields were populated, and attempts to fill gaps
        """
        # Phase 4.5a: Assess completeness
        assessment = self._assess_data_completeness()

        # Phase 4.5b: V4.6 ITERATIVE GAP-FILLING
        if self.medgemma_agent and self.who_kb:
            logger.info("\n🔁 V4.6: Initiating iterative gap-filling")

            gaps_filled = self._attempt_gap_filling(assessment)

            if gaps_filled > 0:
                logger.info(f"  ✅ Filled {gaps_filled} gaps")

                # Re-assess after gap-filling
                logger.info("  Re-assessing data completeness...")
                final_assessment = self._assess_data_completeness()
                self.completeness_assessment = final_assessment
            else:
                logger.info("  ℹ️  No gaps could be filled automatically")
                self.completeness_assessment = assessment
        else:
            logger.warning("⚠️  V4.6: Gap-filling unavailable (MedGemma or WHO KB not initialized)")
            self.completeness_assessment = assessment

        # Report final assessment
        print("  DATA COMPLETENESS ASSESSMENT:")
        print()

        for category, stats in self.completeness_assessment.items():
            if stats['total'] > 0:
                completeness_pct = (stats['complete'] / stats['total']) * 100
                print(f"    {category.upper()}:")
                print(f"      Total events: {stats['total']}")
                print(f"      Complete: {stats['complete']} ({completeness_pct:.1f}%)")

                # Show specific missing fields
                for field, count in stats.items():
                    if field not in ['total', 'complete'] and count > 0:
                        print(f"      {field}: {count} events")

                if completeness_pct < 100:
                    print(f"      ⚠️  INCOMPLETE - {100-completeness_pct:.1f}% missing critical data")
                else:
                    print(f"      ✅ COMPLETE")
                print()

    def _attempt_gap_filling(self, assessment: Dict) -> int:
        """
        V4.6: Attempt to fill critical data gaps using targeted MedGemma extraction

        Args:
            assessment: Current completeness assessment

        Returns:
            Number of gaps successfully filled
        """
        gaps_filled = 0

        # Identify high-priority gaps
        priority_gaps = []

        # Surgery: Missing extent of resection
        if assessment['surgery']['missing_eor'] > 0:
            surgery_events = [e for e in self.timeline_events
                             if e.get('event_type') == 'surgery' and not e.get('extent_of_resection')]
            for event in surgery_events:
                priority_gaps.append({
                    'type': 'surgery_eor',
                    'event': event,
                    'field': 'extent_of_resection',
                    'source_documents': event.get('source_document_ids', [])
                })

        # Radiation: Missing dose
        if assessment['radiation']['missing_dose'] > 0:
            radiation_events = [e for e in self.timeline_events
                               if e.get('event_type') == 'radiation_start' and not e.get('total_dose_cgy')]
            for event in radiation_events:
                priority_gaps.append({
                    'type': 'radiation_dose',
                    'event': event,
                    'field': 'total_dose_cgy',
                    'source_documents': event.get('source_document_ids', [])
                })

        # Imaging: Missing conclusions
        if assessment['imaging']['missing_conclusion'] > 0:
            imaging_events = [e for e in self.timeline_events
                             if e.get('event_type') == 'imaging' and not e.get('report_conclusion')]
            for event in imaging_events:
                priority_gaps.append({
                    'type': 'imaging_conclusion',
                    'event': event,
                    'field': 'report_conclusion',
                    'source_documents': event.get('source_document_ids', [])
                })

        logger.info(f"  Found {len(priority_gaps)} high-priority gaps to fill")

        # Attempt to fill each gap
        for gap in priority_gaps:
            filled = self._fill_single_gap(gap)
            if filled:
                gaps_filled += 1

        return gaps_filled

    def _fill_single_gap(self, gap: Dict) -> bool:
        """
        V4.6: Attempt to fill a single gap using targeted MedGemma extraction

        Args:
            gap: Gap specification with event, field, and source documents

        Returns:
            True if gap was filled, False otherwise
        """
        event = gap['event']
        field = gap['field']
        gap_type = gap['type']

        logger.info(f"    Attempting to fill {gap_type} for event at {event.get('event_date', 'unknown date')}")

        # Get source documents for this event
        source_docs = gap.get('source_documents', [])
        if not source_docs:
            logger.warning(f"      ⚠️  No source documents available for gap-filling")

            # GAP #1 FIX: Trigger Investigation Engine to find alternative documents
            if self.investigation_engine:
                logger.info(f"      🔍 V4.6 GAP #1: Investigating alternative document sources for {gap_type}")
                investigation = self.investigation_engine.investigate_gap_filling_failure(
                    gap_type=gap_type,
                    event=event,
                    reason="No source_document_ids populated - likely due to MedGemma extraction failure in Phase 4"
                )

                if investigation and investigation.get('suggested_alternatives'):
                    logger.info(f"      💡 Investigation suggests: {investigation.get('explanation', '')}")

                    # Try suggested document sources (e.g., use v_radiation_documents instead of temporal matching)
                    alternatives = investigation.get('suggested_alternatives', [])
                    for alt in alternatives[:3]:  # Try top 3 alternatives
                        logger.info(f"      🔄 Trying alternative: {alt.get('method', 'unknown')}")
                        alt_docs = self._try_alternative_document_source(alt, event, gap_type)
                        if alt_docs:
                            source_docs = alt_docs
                            logger.info(f"      ✅ Found {len(source_docs)} alternative documents")
                            break

            # If still no documents after investigation, give up
            if not source_docs:
                return False

        # Construct targeted extraction prompt
        prompt = self._create_gap_filling_prompt(gap_type, field, event)

        # Fetch source document text
        combined_text = self._fetch_source_documents(source_docs)
        if not combined_text:
            logger.warning(f"      ⚠️  Could not fetch source document text")
            return False

        # Execute targeted MedGemma extraction
        try:
            full_prompt = f"{prompt}\n\nSOURCE DOCUMENTS:\n{combined_text}"
            result = self.medgemma_agent.extract(full_prompt)

            if result and result.success and result.extracted_data:
                # Update event with extracted field
                extracted_value = result.extracted_data.get(field)
                if extracted_value:
                    event[field] = extracted_value
                    logger.info(f"      ✅ Filled {field}: {extracted_value}")
                    return True

            logger.warning(f"      ❌ Could not extract {field}")
            return False

        except Exception as e:
            logger.error(f"      ❌ Gap-filling error: {e}")
            return False

    def _create_gap_filling_prompt(self, gap_type: str, field: str, event: Dict) -> str:
        """
        V4.6: Create targeted extraction prompt for specific gap type

        Args:
            gap_type: Type of gap (surgery_eor, radiation_dose, imaging_conclusion)
            field: Field name to extract
            event: Event dictionary with context

        Returns:
            Targeted prompt string
        """
        if gap_type == 'surgery_eor':
            return f"""
Extract the EXTENT OF RESECTION for the surgery performed on {event.get('event_date', 'unknown date')}.

Look for terms like:
- Gross total resection (GTR)
- Subtotal resection (STR)
- Biopsy only
- Complete resection
- Partial resection
- Near total resection (NTR)

Return JSON:
{{
  "extent_of_resection": "<one of: GTR, STR, NTR, Biopsy, Partial, Unknown>"
}}
"""

        elif gap_type == 'radiation_dose':
            return f"""
Extract the TOTAL RADIATION DOSE for radiation therapy starting on {event.get('event_date', 'unknown date')}.

Look for dose specifications like:
- "5400 cGy" or "54 Gy"
- "Prescribed dose: X cGy"
- Total dose in Gray or centiGray

Return JSON:
{{
  "total_dose_cgy": <numeric value in centiGray>
}}
"""

        elif gap_type == 'imaging_conclusion':
            return f"""
Extract the RADIOLOGIST'S CONCLUSION/IMPRESSION for the imaging study performed on {event.get('event_date', 'unknown date')}.

Look for sections labeled:
- IMPRESSION
- CONCLUSION
- FINDINGS SUMMARY
- ASSESSMENT

Return JSON:
{{
  "report_conclusion": "<full conclusion text>"
}}
"""

        return ""

    def _fetch_source_documents(self, doc_ids: List[str]) -> str:
        """
        V4.6.1: Fetch and combine text from source document IDs

        V4.6.1 ENHANCEMENT: Now actually fetches Binary resources for uncached documents
        using BinaryFileAgent, completing the Investigation Engine plumbing.

        Args:
            doc_ids: List of binary document IDs

        Returns:
            Combined document text
        """
        combined = []

        for doc_id in doc_ids[:5]:  # Limit to first 5 docs to avoid context overflow
            # Check if we've already fetched this binary
            text = self._get_cached_binary_text(doc_id)
            if text:
                combined.append(f"--- Document {doc_id} ---\n{text}\n")
                continue

            # V4.6.1: If not cached, fetch from S3 using BinaryFileAgent
            logger.info(f"      🔄 V4.6.1: Fetching uncached document {doc_id[:20]}...")

            try:
                # Stream Binary resource from S3
                binary_content = self.binary_agent.stream_binary_from_s3(doc_id)

                if not binary_content:
                    logger.warning(f"        ⚠️  Could not fetch Binary resource for {doc_id[:20]}")
                    continue

                # Extract text based on content type (PDF, HTML, TIFF, etc.)
                extracted_text = None
                extraction_error = None

                # Try PDF extraction
                text, error = self.binary_agent.extract_text_from_pdf(binary_content)
                if text and len(text.strip()) > 50:
                    extracted_text = text
                    content_type = 'application/pdf'
                elif error:
                    extraction_error = error
                    logger.warning(f"        ⚠️  PDF extraction failed: {error}")

                # If PDF failed, try HTML extraction
                if not extracted_text:
                    text, error = self.binary_agent.extract_text_from_html(binary_content)
                    if text and len(text.strip()) > 50:
                        extracted_text = text
                        content_type = 'text/html'

                # If text-based formats failed, try TIFF/image extraction
                if not extracted_text:
                    logger.info(f"        📸 Attempting OCR extraction for {doc_id[:20]}...")
                    text, error = self.binary_agent.extract_text_from_image(binary_content)
                    if text and len(text.strip()) > 50:
                        extracted_text = text
                        content_type = 'image/tiff'
                    elif error:
                        logger.warning(f"        ⚠️  OCR extraction failed: {error}")

                if extracted_text:
                    # Add to binary_extractions cache so _get_cached_binary_text() finds it
                    if not hasattr(self, 'binary_extractions'):
                        self.binary_extractions = []

                    self.binary_extractions.append({
                        'binary_id': doc_id,
                        'extracted_text': extracted_text,
                        'content_type': content_type,
                        'extraction_method': 'gap_filling_alternative',
                        'text_length': len(extracted_text)
                    })

                    combined.append(f"--- Document {doc_id} ---\n{extracted_text}\n")
                    logger.info(f"        ✅ V4.6.1: Extracted {len(extracted_text)} chars from {doc_id[:20]} ({content_type})")
                else:
                    logger.warning(f"        ⚠️  No text extracted from {doc_id[:20]} (tried PDF, HTML, OCR)")

            except Exception as e:
                logger.error(f"        ❌ Error fetching document {doc_id[:20]}: {e}")
                continue

        return "\n".join(combined)

    def _try_alternative_document_source(self, alternative: Dict, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Execute Investigation Engine's suggested alternative document source.

        Args:
            alternative: Dict with 'method', 'description', 'confidence'
            event: The event missing data
            gap_type: Type of gap (radiation_dose, surgery_eor, imaging_conclusion)

        Returns:
            List of document IDs found via alternative method, or []
        """
        method = alternative.get('method')
        logger.info(f"        Executing alternative method: {method}")

        try:
            if method == 'v_radiation_documents_priority':
                return self._query_radiation_documents_by_priority(event)
            elif method == 'structured_conclusion':
                return self._get_imaging_structured_conclusion(event)
            elif method == 'result_information_field':
                return self._get_imaging_result_information(event)
            elif method == 'v_document_reference_enriched':
                return self._query_document_reference_enriched(event)
            elif method == 'expand_temporal_window':
                return self._query_documents_expanded_window(event, gap_type)
            elif method == 'expand_document_categories':
                return self._query_alternative_document_categories(event, gap_type)
            else:
                logger.warning(f"        Unknown alternative method: {method}")
                return []
        except Exception as e:
            logger.error(f"        Error executing alternative {method}: {e}")
            return []

    def _query_radiation_documents_by_priority(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Query v_radiation_documents with extraction_priority sorting.
        """
        radiation_date = event.get('event_date')
        if not radiation_date:
            return []

        logger.info(f"        🔍 Querying v_radiation_documents for {radiation_date}")

        query = f"""
        SELECT document_id, doc_type_text, doc_date, docc_attachment_url as binary_id
        FROM fhir_prd_db.v_radiation_documents
        WHERE patient_fhir_id = '{self.athena_patient_id}'
          AND ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 45
        ORDER BY extraction_priority ASC,
                 ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) ASC
        LIMIT 3
        """

        results = query_athena(query, f"Priority radiation docs for {radiation_date}", suppress_output=True)
        if results:
            # V4.6.1 FIX: Prioritize binary_id over document_id for Binary resource fetch
            # binary_id format: "Binary/XXX" (correct for BinaryFileAgent)
            # document_id format: "DocumentReference/XXX" (wrong - not a Binary resource)
            doc_ids = [row.get('binary_id', row.get('document_id', '')) for row in results if row.get('binary_id') or row.get('document_id')]
            logger.info(f"        ✅ Found {len(doc_ids)} priority radiation documents")
            return doc_ids
        return []

    def _get_imaging_structured_conclusion(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Extract imaging conclusion from structured field.
        """
        result_info = event.get('result_information', '')
        if result_info and len(result_info) > 50:
            logger.info(f"        ✅ Found structured conclusion ({len(result_info)} chars)")
            pseudo_doc_id = f"structured_conclusion_{event.get('event_id', 'unknown')}"
            if not hasattr(self, 'binary_extractions'):
                self.binary_extractions = []
            self.binary_extractions.append({
                'binary_id': pseudo_doc_id,
                'extracted_text': result_info,
                'content_type': 'structured_field',
                'resource_type': 'DiagnosticReport',
                'fhir_target': event.get('event_id', '')
            })
            return [pseudo_doc_id]
        return []

    def _get_imaging_result_information(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Extract from result_information field.
        """
        result_info = event.get('result_information', '')
        if result_info and len(result_info) > 30:
            logger.info(f"        ✅ Found result_information field ({len(result_info)} chars)")
            pseudo_doc_id = f"result_information_{event.get('event_id', 'unknown')}"
            if not hasattr(self, 'binary_extractions'):
                self.binary_extractions = []
            self.binary_extractions.append({
                'binary_id': pseudo_doc_id,
                'extracted_text': result_info,
                'content_type': 'structured_field',
                'resource_type': 'DiagnosticReport',
                'fhir_target': event.get('event_id', '')
            })
            return [pseudo_doc_id]
        return []

    def _query_document_reference_enriched(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Query v_document_reference_enriched with encounter lookup.
        """
        event_date = event.get('event_date')
        if not event_date:
            return []

        logger.info(f"        🔍 Querying v_document_reference_enriched for {event_date}")

        query = f"""
        SELECT document_reference_id, binary_id
        FROM fhir_prd_db.v_document_reference_enriched
        WHERE patient_fhir_id = '{self.athena_patient_id}'
          AND ABS(DATE_DIFF('day', CAST(document_date AS DATE), CAST(TIMESTAMP '{event_date}' AS DATE))) <= 14
          AND document_type IN ('operative note', 'surgical note', 'procedure note')
        ORDER BY ABS(DATE_DIFF('day', CAST(document_date AS DATE), CAST(TIMESTAMP '{event_date}' AS DATE))) ASC
        LIMIT 2
        """

        results = query_athena(query, f"Encounter-based docs for {event_date}", suppress_output=True)
        if results:
            doc_ids = [row.get('document_reference_id', row.get('binary_id', '')) for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} encounter-based documents")
            return doc_ids
        return []

    def _query_documents_expanded_window(self, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Retry with expanded temporal window (±60 days).
        """
        event_date = event.get('event_date')
        if not event_date:
            return []

        logger.info(f"        🔍 Querying with expanded window (±60 days)")

        if gap_type == 'surgery_eor':
            categories = "('operative note', 'surgical note', 'procedure note')"
        elif gap_type == 'radiation_dose':
            categories = "('radiation summary', 'treatment summary')"
        else:
            categories = "('radiology report', 'imaging report')"

        query = f"""
        SELECT dr.id as document_id
        FROM fhir_prd_db.document_reference dr
        WHERE dr.subject_reference = 'Patient/{self.athena_patient_id}'
          AND dr.category_text IN {categories}
          AND ABS(DATE_DIFF('day',
              CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
              CAST(TIMESTAMP '{event_date}' AS DATE))) <= 60
        ORDER BY ABS(DATE_DIFF('day',
            CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
            CAST(TIMESTAMP '{event_date}' AS DATE))) ASC
        LIMIT 2
        """

        results = query_athena(query, f"Expanded window docs", suppress_output=True)
        if results:
            doc_ids = [row.get('document_id', '') for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} documents in expanded window")
            return doc_ids
        return []

    def _query_alternative_document_categories(self, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Query alternative document categories.
        """
        event_date = event.get('event_date')
        if not event_date:
            return []

        if gap_type == 'surgery_eor':
            categories = "('anesthesia record', 'discharge summary', 'post-operative note')"
        elif gap_type == 'radiation_dose':
            categories = "('consultation note', 'outside record')"
        else:
            return []

        query = f"""
        SELECT dr.id as document_id
        FROM fhir_prd_db.document_reference dr
        WHERE dr.subject_reference = 'Patient/{self.athena_patient_id}'
          AND dr.category_text IN {categories}
          AND ABS(DATE_DIFF('day',
              CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
              CAST(TIMESTAMP '{event_date}' AS DATE))) <= 30
        LIMIT 2
        """

        results = query_athena(query, f"Alternative category docs", suppress_output=True)
        if results:
            doc_ids = [row.get('document_id', '') for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} alternative documents")
            return doc_ids
        return []

    def _get_cached_binary_text(self, doc_id: str) -> Optional[str]:
        """
        V4.6 GAP #1: Get cached binary text (handles pseudo-documents).
        """
        if not hasattr(self, 'binary_extractions'):
            return None
        for extraction in self.binary_extractions:
            if extraction.get('binary_id') == doc_id:
                return extraction.get('extracted_text', '')
        return None

    def _compute_treatment_change_reasons(self):
        """V4.6 GAP #2: Compute reason for treatment changes."""
        logger.info("📊 V4.6 GAP #2: Computing treatment change reasons...")
        chemo_events = [e for e in self.timeline_events
                       if e.get('event_type') in ['chemo_start', 'chemotherapy_start']]
        chemo_events.sort(key=lambda x: x.get('event_date', ''))
        if len(chemo_events) < 2:
            logger.info("  No treatment line changes to analyze")
            return
        for i in range(1, len(chemo_events)):
            prior_event = chemo_events[i - 1]
            current_event = chemo_events[i]
            prior_end_date = self._find_chemo_end_date(prior_event)
            current_start_date = current_event.get('event_date')
            if not prior_end_date or not current_start_date:
                continue
            reason = self._analyze_treatment_change_reason(prior_end_date, current_start_date, prior_event, current_event)
            if 'relationships' not in current_event:
                current_event['relationships'] = {}
            if 'ordinality' not in current_event['relationships']:
                current_event['relationships']['ordinality'] = {}
            current_event['relationships']['ordinality']['reason_for_change_from_prior'] = reason
            logger.info(f"  Line {i} → {i+1} change reason: {reason}")
        logger.info("✅ Treatment change reasons computed")

    def _find_chemo_end_date(self, chemo_start_event: Dict) -> Optional[str]:
        """Find the end date for a chemotherapy episode."""
        start_date = chemo_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') in ['chemo_end', 'chemotherapy_end']:
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    return end_date
        return chemo_start_event.get('therapy_end_date')

    def _analyze_treatment_change_reason(self, prior_end_date: str, current_start_date: str, prior_event: Dict, current_event: Dict) -> str:
        """V4.6 GAP #2: Analyze why treatment changed."""
        interim_imaging = [e for e in self.timeline_events
                          if e.get('event_type') == 'imaging'
                          and prior_end_date <= e.get('event_date', '') <= current_start_date]
        for img in interim_imaging:
            conclusion = (img.get('report_conclusion', '') or img.get('result_information', '')).lower()
            progression_keywords = ['progression', 'progressing', 'progressive', 'increased', 'enlarging',
                                   'enlargement', 'expansion', 'growing', 'growth', 'worsening', 'worsen',
                                   'new lesion', 'new enhancement', 'recurrence', 'recurrent']
            if any(kw in conclusion for kw in progression_keywords):
                return 'progression'
            rano = img.get('rano_assessment', '')
            if rano == 'PD' or 'progressive disease' in rano.lower():
                return 'progression'
            if 'medgemma_extraction' in img:
                extraction = img['medgemma_extraction']
                rano_ext = extraction.get('rano_assessment', '')
                if rano_ext == 'PD':
                    return 'progression'
        protocol_status = prior_event.get('protocol_status', '')
        if 'complete' in protocol_status.lower():
            return 'completion'
        return 'unclear'

    def _enrich_event_relationships(self):
        """V4.6 GAP #3: Populate related_events for cross-event linkage."""
        logger.info("🔗 V4.6 GAP #3: Enriching event relationships...")
        for event in self.timeline_events:
            if 'relationships' not in event:
                event['relationships'] = {}
            event_type = event.get('event_type')
            event_date = event.get('event_date')
            if not event_date:
                continue
            if event_type == 'surgery':
                event['relationships']['related_events'] = {
                    'preop_imaging': self._find_imaging_before(event, days=7),
                    'postop_imaging': self._find_imaging_after(event, days=7),
                    'pathology_reports': self._find_pathology_for_surgery(event)
                }
            elif event_type in ['chemo_start', 'chemotherapy_start']:
                event['relationships']['related_events'] = {
                    'chemotherapy_end': self._find_chemo_end(event),
                    'response_imaging': self._find_response_imaging(event)
                }
            elif event_type == 'radiation_start':
                event['relationships']['related_events'] = {
                    'radiation_end': self._find_radiation_end(event),
                    'simulation_imaging': self._find_simulation_imaging(event)
                }
        logger.info("✅ Event relationships enriched")

    def _find_imaging_before(self, surgery_event: Dict, days: int = 7) -> List[str]:
        """Find imaging within N days before surgery."""
        from datetime import datetime, timedelta
        surgery_date = datetime.fromisoformat(surgery_event['event_date'].replace('Z', '+00:00'))
        window_start = surgery_date - timedelta(days=days)
        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and window_start <= datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) < surgery_date]
        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _find_imaging_after(self, surgery_event: Dict, days: int = 7) -> List[str]:
        """Find imaging within N days after surgery."""
        from datetime import datetime, timedelta
        surgery_date = datetime.fromisoformat(surgery_event['event_date'].replace('Z', '+00:00'))
        window_end = surgery_date + timedelta(days=days)
        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and surgery_date < datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) <= window_end]
        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _find_pathology_for_surgery(self, surgery_event: Dict) -> List[str]:
        """Find pathology reports matching surgery specimen."""
        specimen_id = surgery_event.get('specimen_id')
        if not specimen_id:
            return []
        pathology_events = [e for e in self.timeline_events
                           if e.get('event_type') == 'pathology'
                           and e.get('specimen_id') == specimen_id]
        return [e.get('event_id', e.get('fhir_id', '')) for e in pathology_events]

    def _find_chemo_end(self, chemo_start_event: Dict) -> Optional[str]:
        """Find corresponding chemo_end event."""
        start_date = chemo_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') in ['chemo_end', 'chemotherapy_end']:
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    return event.get('event_id', event.get('fhir_id', ''))
        return None

    def _find_response_imaging(self, chemo_start_event: Dict) -> List[str]:
        """Find response imaging (first imaging >30 days after chemo end)."""
        from datetime import datetime, timedelta, timezone
        end_date_str = self._find_chemo_end_date(chemo_start_event)
        if not end_date_str:
            return []

        # Parse end date and ensure timezone-aware
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        response_window_start = end_date + timedelta(days=30)

        # Filter imaging events with safe timezone handling
        imaging_events = []
        for e in self.timeline_events:
            if e.get('event_type') == 'imaging':
                try:
                    event_date = datetime.fromisoformat(e['event_date'].replace('Z', '+00:00'))
                    if event_date.tzinfo is None:
                        event_date = event_date.replace(tzinfo=timezone.utc)
                    if event_date >= response_window_start:
                        imaging_events.append(e)
                except (ValueError, KeyError):
                    continue

        imaging_events.sort(key=lambda x: x.get('event_date', ''))
        return [imaging_events[0].get('event_id', imaging_events[0].get('fhir_id', ''))] if imaging_events else []

    def _find_radiation_end(self, radiation_start_event: Dict) -> Optional[str]:
        """Find corresponding radiation_end event."""
        start_date = radiation_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') == 'radiation_end':
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    return event.get('event_id', event.get('fhir_id', ''))
        return None

    def _find_simulation_imaging(self, radiation_start_event: Dict) -> List[str]:
        """Find simulation/planning imaging (±7 days before radiation start)."""
        from datetime import datetime, timedelta, timezone

        # Parse radiation start date and ensure timezone-aware
        start_date = datetime.fromisoformat(radiation_start_event['event_date'].replace('Z', '+00:00'))
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        window_start = start_date - timedelta(days=7)
        window_end = start_date + timedelta(days=7)

        # Filter imaging events with safe timezone handling
        imaging_events = []
        for e in self.timeline_events:
            if e.get('event_type') == 'imaging':
                try:
                    event_date = datetime.fromisoformat(e['event_date'].replace('Z', '+00:00'))
                    if event_date.tzinfo is None:
                        event_date = event_date.replace(tzinfo=timezone.utc)
                    if window_start <= event_date <= window_end:
                        imaging_events.append(e)
                except (ValueError, KeyError):
                    continue

        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _check_still_on_therapy(self, start_date, treatment_type: str, agent_names: List[str]) -> bool:
        """
        V4.6.5: Check if patient is still on active therapy

        Searches recent progress notes (last 30 days from timeline end) for evidence
        that patient is currently receiving treatment. This prevents false negatives
        where missing end dates are actually ongoing therapy.

        Args:
            start_date: Treatment start date
            treatment_type: 'chemotherapy' or 'radiation'
            agent_names: List of chemo agents (for chemotherapy)

        Returns:
            True if evidence suggests patient is still on therapy, False otherwise
        """
        from datetime import datetime, timedelta

        # Get the most recent event date in the timeline as proxy for "current" date
        timeline_dates = [e.get('event_date') for e in self.timeline_events if e.get('event_date')]
        if not timeline_dates:
            return False

        most_recent_date_str = max(timeline_dates)
        most_recent_date = datetime.fromisoformat(most_recent_date_str.replace('Z', '+00:00')).date()

        # Search for recent progress notes (last 30 days of timeline)
        window_start = (most_recent_date - timedelta(days=30)).isoformat()
        window_end = most_recent_date.isoformat()

        query = f"""
        SELECT
            drc.content_attachment_url as binary_id,
            dr.type_text,
            dr.date as note_date
        FROM fhir_prd_db.document_reference dr
        JOIN fhir_prd_db.document_reference_content drc
            ON dr.id = drc.document_reference_id
        WHERE dr.subject_reference = '{self.patient_id}'
            AND dr.date IS NOT NULL
            AND LENGTH(dr.date) >= 10
            AND type_text = 'Progress Notes'
            AND DATE(SUBSTR(dr.date, 1, 10)) >= DATE '{window_start}'
            AND DATE(SUBSTR(dr.date, 1, 10)) <= DATE '{window_end}'
            AND drc.content_attachment_url IS NOT NULL
        ORDER BY DATE(SUBSTR(dr.date, 1, 10)) DESC
        LIMIT 5
        """

        try:
            results = query_athena(query, "Check still on therapy", suppress_output=True)
            if not results:
                return False

            # Keywords indicating ongoing therapy
            ongoing_keywords = [
                'continuing', 'ongoing', 'current', 'still receiving',
                'remains on', 'maintained on', 'tolerating', 'cycle',
                'next dose', 'will continue', 'plan to continue'
            ]

            # Check each recent note for ongoing therapy mentions
            for note in results:
                binary_id = note.get('binary_id')
                note_text = self._get_cached_binary_text(binary_id)

                if not note_text:
                    try:
                        binary_content = self.binary_agent.stream_binary_from_s3(binary_id)
                        if binary_content:
                            text, error = self.binary_agent.extract_text_from_pdf(binary_content)
                            if not text or len(text.strip()) < 50:
                                text, error = self.binary_agent.extract_text_from_html(binary_content)
                            if text and len(text.strip()) > 50:
                                note_text = text
                    except Exception:
                        continue

                if not note_text:
                    continue

                note_lower = note_text.lower()

                # Check for treatment type + ongoing keywords
                if treatment_type == 'chemotherapy':
                    # Check if any agent is mentioned with ongoing keywords
                    for agent in agent_names:
                        if agent.lower() in note_lower:
                            if any(kw in note_lower for kw in ongoing_keywords):
                                logger.info(f"          ℹ️  Evidence of ongoing therapy: '{agent}' mentioned with ongoing keywords in recent note")
                                return True

                elif treatment_type == 'radiation':
                    rad_keywords = ['radiation', 'radiotherapy', 'xrt', 'rt']
                    if any(kw in note_lower for kw in rad_keywords):
                        if any(kw in note_lower for kw in ongoing_keywords):
                            logger.info(f"          ℹ️  Evidence of ongoing radiation therapy in recent note")
                            return True

            return False

        except Exception as e:
            logger.debug(f"Still on therapy check failed: {e}")
            return False

    def _remediate_missing_chemo_end_dates(self) -> int:
        """
        V4.6.3 PHASE 2.2: Remediate missing chemotherapy end dates

        Multi-tier strategy with intelligent note prioritization and adaptive expansion:
        - Tier 1: Progress Notes (most likely to mention "completed chemotherapy")
        - Tier 2: Encounter Summary / Discharge Notes
        - Tier 3: Transfer Notes
        - Tier 4: H&P / Consult Notes

        Adaptive expansion: Start with ±30 days, expand to ±60/±90 if keywords found
        """
        from datetime import datetime, timedelta

        filled_count = 0

        # Find all chemotherapy events missing end dates
        chemo_events = [e for e in self.timeline_events
                       if e.get('event_type') == 'chemotherapy_start'
                       and not e.get('therapy_end_date')]

        if not chemo_events:
            return 0

        for chemo_event in chemo_events:
            start_date_str = chemo_event.get('event_date')
            if not start_date_str:
                continue

            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).date()

            # V4.8.3: Use episode_drug_names (V4.8.1 field) instead of agent_names
            # episode_drug_names is a pipe-separated string like "temozolomide | etoposide"
            drug_names_str = chemo_event.get('episode_drug_names', '')
            if drug_names_str:
                agent_names = [name.strip() for name in drug_names_str.split('|')]
            else:
                # Fallback to legacy agent_names if episode_drug_names missing
                agent_names = chemo_event.get('agent_names', [])
                if isinstance(agent_names, str):
                    agent_names = [agent_names]

            logger.debug(f"      Searching for end date for chemo starting {start_date_str}")

            end_date = None

            # TIER 1: Progress Notes (highest priority)
            end_date = self._search_notes_for_treatment_end(
                start_date=start_date,
                treatment_type='chemotherapy',
                agent_names=agent_names,
                note_types=['Progress Notes'],
                tier_name="Tier 1: Progress Notes"
            )

            # TIER 2: Encounter Summary / Discharge Notes
            if not end_date:
                end_date = self._search_notes_for_treatment_end(
                    start_date=start_date,
                    treatment_type='chemotherapy',
                    agent_names=agent_names,
                    note_types=['Encounter Summary'],
                    tier_name="Tier 2: Encounter Summary"
                )

            # TIER 3: Transfer Notes
            if not end_date:
                end_date = self._search_notes_for_treatment_end(
                    start_date=start_date,
                    treatment_type='chemotherapy',
                    agent_names=agent_names,
                    note_types=['Transfer Note'],
                    tier_name="Tier 3: Transfer Notes"
                )

            # TIER 4: H&P / Consult Notes
            if not end_date:
                end_date = self._search_notes_for_treatment_end(
                    start_date=start_date,
                    treatment_type='chemotherapy',
                    agent_names=agent_names,
                    note_types=['H&P', 'Consult Note'],
                    tier_name="Tier 4: H&P/Consult"
                )

            if end_date:
                chemo_event['therapy_end_date'] = end_date
                filled_count += 1
                logger.info(f"        ✅ Found chemo end date: {end_date} for treatment starting {start_date_str}")
            else:
                # V4.6.5: Check if patient is still on active therapy
                still_on_therapy = self._check_still_on_therapy(start_date, 'chemotherapy', agent_names)
                if still_on_therapy:
                    chemo_event['therapy_status'] = 'ongoing'
                    logger.info(f"        ℹ️  Patient appears to still be on active therapy for chemo starting {start_date_str}")
                else:
                    logger.info(f"        ❌ Could not find end date for chemo starting {start_date_str} (searched all tiers)")

        total_missing = len(chemo_events)
        logger.info(f"   📊 Chemotherapy End Date Remediation Summary:")
        logger.info(f"      Total missing: {total_missing}")
        logger.info(f"      Successfully filled: {filled_count} ({100*filled_count/total_missing if total_missing > 0 else 0:.1f}%)")
        logger.info(f"      Still missing: {total_missing - filled_count}")

        return filled_count

    def _remediate_missing_radiation_end_dates(self) -> int:
        """
        V4.6.3 PHASE 2.2: Remediate missing radiation end dates

        Multi-tier strategy optimized for radiation:
        - Tier 1: v_radiation_documents (treatment summaries, completion reports)
        - Tier 2: Progress Notes mentioning "completed radiation"
        - Tier 3: Calculate from start date + fractions (if available)
        """
        from datetime import datetime, timedelta

        filled_count = 0

        # Find all radiation events missing end dates
        radiation_events = [e for e in self.timeline_events
                           if e.get('event_type') == 'radiation_start'
                           and not e.get('date_at_radiation_stop')]

        if not radiation_events:
            return 0

        for rad_event in radiation_events:
            start_date_str = rad_event.get('event_date')
            if not start_date_str:
                continue

            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00')).date()

            logger.debug(f"      Searching for end date for radiation starting {start_date_str}")

            end_date = None

            # TIER 1: Query v_radiation_documents for completion summaries
            end_date = self._search_radiation_documents_for_end_date(start_date)

            # TIER 2: Progress Notes
            if not end_date:
                end_date = self._search_notes_for_treatment_end(
                    start_date=start_date,
                    treatment_type='radiation',
                    agent_names=[],
                    note_types=['Progress Notes'],
                    tier_name="Tier 2: Progress Notes"
                )

            # TIER 3: Calculate from fractions
            if not end_date:
                total_fractions = rad_event.get('total_fractions')
                if total_fractions and isinstance(total_fractions, (int, float)) and total_fractions > 0:
                    # Assume 5 fractions per week (Mon-Fri)
                    weeks = int(total_fractions / 5)
                    extra_days = total_fractions % 5
                    estimated_end = start_date + timedelta(weeks=weeks, days=extra_days)
                    end_date = estimated_end.isoformat()
                    logger.info(f"        💡 Tier 3: Calculated end date from {total_fractions} fractions: {end_date}")

            if end_date:
                rad_event['date_at_radiation_stop'] = end_date
                filled_count += 1
                logger.info(f"        ✅ Found radiation end date: {end_date} for treatment starting {start_date_str}")
            else:
                logger.info(f"        ❌ Could not find end date for radiation starting {start_date_str} (searched all tiers)")

        total_missing = len(radiation_events)
        logger.info(f"   📊 Radiation End Date Remediation Summary:")
        logger.info(f"      Total missing: {total_missing}")
        logger.info(f"      Successfully filled: {filled_count} ({100*filled_count/total_missing if total_missing > 0 else 0:.1f}%)")
        logger.info(f"      Still missing: {total_missing - filled_count}")

        return filled_count

    def _medgemma_extract_eor_from_imaging(self, report_text: str, surgery_date, img_date) -> Optional[str]:
        """
        V4.6.5 TIER 2B: MedGemma intelligent freetext interpretation of imaging reports

        Uses MedGemma to intelligently interpret radiology report text that may not
        contain explicit EOR keywords. This leverages TRUE LLM reasoning:

        - Clinical inference: Interpret indirect descriptions
        - Contextual understanding: Connect post-op changes to surgical extent
        - Ambiguity resolution: Make clinical judgment on unclear reports
        - Medical terminology mapping: Translate varied terminology to standard EOR

        Args:
            report_text: Full imaging report text
            surgery_date: Date of surgery
            img_date: Date of imaging study

        Returns:
            EOR string ('GTR', 'STR', 'Partial', 'Biopsy') or None
        """
        if not self.medgemma_agent:
            logger.debug(f"        Tier 2B: MedGemma agent not available")
            return None

        if len(report_text) < 50:
            logger.debug(f"        Tier 2B: Report text too short ({len(report_text)} chars)")
            return None

        # LLM REASONING PROMPT: Asks for clinical inference, not keyword matching
        prompt = f"""You are reviewing a post-operative radiology report from {img_date} for a brain tumor surgery performed on {surgery_date}.

**Your Task**: Use your clinical reasoning to classify the extent of tumor resection based on this radiology report.

**Classification Schema**:
- **GTR (Gross Total Resection)**: No evidence of residual enhancing tumor on imaging
- **STR (Subtotal Resection)**: Minimal residual tumor (typically <10% remaining)
- **Partial**: Significant residual tumor present (>10% remaining)
- **Biopsy**: Only tissue sampling performed, no resection attempt

**Clinical Reasoning Instructions**:

1. **Inference from Indirect Descriptions**:
   - "Post-operative changes in the resection cavity" → Infer surgery occurred
   - "Improved mass effect compared to pre-op" → Infer significant tissue removal
   - "Resection cavity with fluid and blood products" → Infer GTR if no enhancement mentioned

2. **Contextual Understanding**:
   - If report mentions "debulking" → Classify as Partial (incomplete resection)
   - If report describes "near-complete resection" → Classify as STR
   - If report notes "residual enhancement along margins" → Classify as STR or Partial based on extent

3. **Ambiguity Resolution**:
   - If unclear, favor more conservative classification (e.g., STR over GTR)
   - If report is contradictory, note in reasoning and make best clinical judgment
   - If truly insufficient information, return null

4. **Terminology Mapping**:
   - "Complete removal" → GTR
   - "Near-total" / "Subtotal" → STR
   - "Debulking" / "Incomplete" → Partial
   - "Biopsy site" / "No resection" → Biopsy

**Report Text**:
{report_text}

**IMPORTANT**: Return ONLY a valid JSON object in this EXACT format:

{{
    "extent_of_resection": "GTR" | "STR" | "Partial" | "Biopsy" | null,
    "clinical_reasoning": "Explain your interpretation and inference process in 1-2 sentences",
    "confidence": "HIGH" | "MEDIUM" | "LOW"
}}

Return null for extent_of_resection ONLY if the report genuinely does not contain sufficient information about resection extent.
"""

        try:
            logger.info(f"        Tier 2B (MedGemma): Applying clinical reasoning to report...")
            result = self.medgemma_agent.extract(prompt, temperature=0.2)

            if not result or not result.success:
                logger.warning(f"        Tier 2B (MedGemma): Extraction failed: {result.error if result else 'No result'}")
                return None

            # Parse JSON response
            try:
                data = json.loads(result.raw_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response if wrapped in other text
                import re
                json_match = re.search(r'\{.*\}', result.raw_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    logger.warning(f"        Tier 2B (MedGemma): Could not parse JSON response")
                    return None

            eor = data.get('extent_of_resection')
            reasoning = data.get('clinical_reasoning', 'No reasoning provided')
            confidence = data.get('confidence', 'UNKNOWN')

            if eor and eor in ['GTR', 'STR', 'Partial', 'Biopsy']:
                logger.info(f"        ✅ Tier 2B (MedGemma): Extracted EOR='{eor}' (confidence: {confidence})")
                logger.info(f"           Reasoning: {reasoning}")
                return eor
            else:
                logger.info(f"        Tier 2B (MedGemma): Could not determine EOR (returned: {eor})")
                return None

        except Exception as e:
            logger.error(f"        Tier 2B (MedGemma): Error during extraction: {e}")
            return None

    def _investigation_engine_review_imaging_for_eor(self, report_text: str, surgery_date, img_date) -> Optional[str]:
        """
        V4.6.5 TIER 2C: Investigation Engine reasoning fallback for failed MedGemma extractions

        When MedGemma fails to extract EOR from a document that EXISTS, the Investigation
        Engine reviews the document to:
        1. Confirm the document truly doesn't contain EOR information
        2. Provide reasoning about why extraction failed
        3. Suggest alternative interpretation strategies

        This implements the critical safety net: "if MedGemma fails to interpret an
        operative document or post-operative imaging document that exists, the reasoning
        engine reviews and assesses this document to confirm the document does not contain
        the required information."

        This is TRUE META-REASONING: Analyzing WHY extraction failed and applying
        fallback logic that goes beyond what the primary extraction agent attempted.

        Args:
            report_text: Full imaging report text
            surgery_date: Date of surgery
            img_date: Date of imaging study

        Returns:
            EOR string ('GTR', 'STR', 'Partial', 'Biopsy') or None
        """
        if not self.medgemma_agent:
            logger.debug(f"        Tier 2C: MedGemma agent not available for reasoning")
            return None

        if len(report_text) < 30:
            logger.debug(f"        Tier 2C: Report text too short for meaningful analysis ({len(report_text)} chars)")
            return None

        # INVESTIGATION ENGINE META-REASONING PROMPT WITH COMPREHENSIVE SYSTEM KNOWLEDGE
        # This leverages deep understanding of data architecture to leave NO STONE UNTURNED
        prompt = f"""You are the Investigation Engine performing a SECONDARY REVIEW after the primary extraction agent (MedGemma) failed to extract extent of resection from this post-operative imaging report.

**CRITICAL - Your Comprehensive System Knowledge**:
You have deep understanding of the ENTIRE data architecture:
- **Athena Views**: v_imaging, v_imaging_results, v_procedures_tumor, v_clinical_notes, v_pathology_diagnostics, v_binary_files
- **FHIR Resources**: DocumentReference (operative notes, discharge summaries), Binary (PDFs), Observation (structured findings), DiagnosticReport
- **Workflow**: Phase 1 (structured data) → Phase 3.5 (v_imaging EOR enrichment) → Phase 4 (binary extraction) → Phase 5 (gap-filling) → Phase 6 (artifact)
- **Data Quality Patterns**: External institution data gaps, truncated reports, alternative terminology
- **Clinical Domain**: Standard neurosurgical protocols, temporal expectations for post-op imaging

Your mission: LEAVE NO STONE UNTURNED in finding EOR information.

**Context**:
- Surgery Date: {surgery_date}
- Imaging Date: {img_date}
- Primary extraction attempt (MedGemma): FAILED (returned null or insufficient confidence)

**Your Meta-Reasoning Task**:

1. **Analyze WHY Primary Extraction Failed**:
   - Is the text corrupted or unreadable?
   - Is the terminology too ambiguous?
   - Is EOR information genuinely absent?
   - Was the report pre-operative (not post-op)?
   - Is this the wrong data source for EOR?

2. **Identify Alternative Data Sources** (leave no stone unturned):
   - Should we check v_imaging_results instead of v_imaging?
   - Should we look for discharge summary in v_clinical_notes (often contains EOR)?
   - Should we search v_binary_files for operative note PDFs?
   - Should we check v_procedures_tumor for structured EOR field?
   - Are there temporal clinical notes within 72h of surgery mentioning debulking/resection?

3. **Apply Fallback Reasoning Rules**:
   - **Rule 1 (Implicit GTR)**: "Resection cavity" or "post-op changes" WITHOUT residual tumor → Likely GTR
   - **Rule 2 (Conservative Default)**: Surgery occurred but unclear EOR → "Partial" (most conservative)
   - **Rule 3 (Temporal Check)**: >7 days post-op → Unreliable for EOR (may show recurrence)
   - **Rule 4 (Pre-op Detection)**: "Planned surgery" or "pre-operative" → Not applicable
   - **Rule 5 (Cross-view Inference)**: If radiation dose >54 Gy documented elsewhere → Suggests residual disease (STR/Partial)
   - **Rule 6 (External Institution)**: Missing standard documentation → Flag for transferred records search

4. **Generate Investigation Report**:
   - Document your reasoning process
   - Explain what clinical clues you used
   - **List alternative data sources to check**
   - Note any assumptions made
   - Flag data quality issues

5. **Make Final Determination**:
   - Based on fallback reasoning rules
   - Only return null if genuinely no surgical information AND no alternative sources available

**Report Text**:
{report_text}

**IMPORTANT**: Return ONLY a valid JSON object in this EXACT format:

{{
    "extent_of_resection": "GTR" | "STR" | "Partial" | "Biopsy" | null,
    "failure_analysis": "Why did primary extraction fail? (1-2 sentences)",
    "alternative_data_sources": ["v_clinical_notes for discharge summary", "v_procedures_tumor for structured EOR field"],
    "fallback_reasoning": "What reasoning rules were applied? (1-2 sentences)",
    "clinical_clues": ["List 2-3 specific text phrases that informed your decision"],
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "investigation_notes": "Any additional context, warnings, or data quality flags",
    "data_quality_flags": ["List any issues: truncated text, external institution, missing docs"]
}}

Return null for extent_of_resection ONLY if:
- Report is pre-operative (not post-op)
- Report is from >7 days post-surgery (unreliable for EOR)
- Report is genuinely about a different procedure/body part
- Text is too corrupted to interpret
- AND no alternative data sources identified

CRITICAL: Always populate "alternative_data_sources" if EOR not found - leave no stone unturned!
"""

        try:
            logger.info(f"        Tier 2C (Investigation): Performing meta-reasoning analysis...")
            result = self.medgemma_agent.extract(prompt, temperature=0.3)  # Slightly higher temp for reasoning

            if not result or not result.success:
                logger.warning(f"        Tier 2C (Investigation): Meta-reasoning failed: {result.error if result else 'No result'}")
                return None

            # Parse JSON response
            try:
                data = json.loads(result.raw_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response if wrapped in other text
                import re
                json_match = re.search(r'\{.*\}', result.raw_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    logger.warning(f"        Tier 2C (Investigation): Could not parse JSON response")
                    return None

            eor = data.get('extent_of_resection')
            failure_analysis = data.get('failure_analysis', 'No analysis provided')
            fallback_reasoning = data.get('fallback_reasoning', 'No reasoning provided')
            clinical_clues = data.get('clinical_clues', [])
            confidence = data.get('confidence', 'UNKNOWN')
            investigation_notes = data.get('investigation_notes', '')

            # V4.7: New comprehensive system knowledge fields (backward compatible)
            alternative_sources = data.get('alternative_data_sources', [])
            data_quality_flags = data.get('data_quality_flags', [])

            # Log investigation report
            logger.info(f"        Tier 2C (Investigation): Analysis complete")
            logger.info(f"           Failure Analysis: {failure_analysis}")
            logger.info(f"           Fallback Reasoning: {fallback_reasoning}")
            logger.info(f"           Clinical Clues: {', '.join(clinical_clues)}")

            # V4.7: Log comprehensive system knowledge outputs
            if alternative_sources:
                logger.info(f"           Alternative Sources: {', '.join(alternative_sources)}")
            if data_quality_flags:
                logger.warning(f"           Data Quality Flags: {', '.join(data_quality_flags)}")

            if investigation_notes:
                logger.info(f"           Notes: {investigation_notes}")

            if eor and eor in ['GTR', 'STR', 'Partial', 'Biopsy']:
                logger.info(f"        ✅ Tier 2C (Investigation): Reasoned EOR='{eor}' (confidence: {confidence})")
                return eor
            else:
                logger.info(f"        Tier 2C (Investigation): Confirmed document does not contain EOR (returned: {eor})")
                return None

        except Exception as e:
            logger.error(f"        Tier 2C (Investigation): Error during meta-reasoning: {e}")
            return None

    def _search_postop_imaging_for_eor(self, surgery_date) -> Optional[str]:
        """
        V4.6.5 TIER 2/3: Intelligent multi-tier search for EOR in post-operative imaging

        Three-tier extraction strategy:
        - Tier 2A: Enhanced keyword search (fast, covers both radiological + surgical terminology)
        - Tier 2B: MedGemma intelligent freetext interpretation (medium speed, high accuracy)
        - Tier 2C: Investigation Engine reasoning fallback (validates MedGemma failures)

        Post-operative MRI/CT (typically within 24-72 hours) provides objective
        assessment of residual tumor and can confirm/contradict surgeon's operative note.

        Args:
            surgery_date: Date object of surgery

        Returns:
            EOR string ('GTR', 'STR', 'Partial', 'Biopsy', None) or None
        """
        from datetime import timedelta

        # Search for imaging within 0-5 days post-surgery (same day to 5 days after)
        # Post-op imaging often occurs same-day (hours after surgery) or within 24-72h
        window_start = surgery_date.isoformat()
        window_end = (surgery_date + timedelta(days=5)).isoformat()

        query = f"""
        SELECT
            imaging_date,
            report_conclusion,
            result_information
        FROM fhir_prd_db.v_imaging
        WHERE patient_fhir_id = '{self.athena_patient_id}'
            AND imaging_date >= DATE '{window_start}'
            AND imaging_date <= DATE '{window_end}'
            AND (LOWER(imaging_modality) LIKE '%mri%' OR LOWER(imaging_modality) LIKE '%ct%')
            AND (report_conclusion IS NOT NULL OR result_information IS NOT NULL)
        ORDER BY imaging_date ASC
        LIMIT 3
        """

        try:
            logger.info(f"        Tier 2: Post-op Imaging: Searching post-operative imaging (0-5d from {surgery_date.isoformat()})...")
            results = query_athena(query, "Tier 2: Query post-op imaging", suppress_output=True)

            if not results:
                # V4.7.5: Invoke Investigation Engine with patient_context for clinical validation
                logger.warning(f"        ⚠️  Tier 2: Post-op Imaging: No post-operative imaging found - invoking Investigation Engine")

                # V4.7.5: Build patient_context for clinical protocol validation
                patient_context = {
                    'who_diagnosis': self.who_2021_classification.get('who_2021_diagnosis', 'Unknown') if self.who_2021_classification else 'Unknown',
                    'tumor_type': self.who_2021_classification.get('who_grade', 'Unknown') if self.who_2021_classification else 'Unknown',
                    'molecular_markers': self.who_2021_classification.get('molecular_markers', {}) if self.who_2021_classification else {},
                    'surgeries': [],  # Not needed for no_postop_imaging validation
                    'timeline_events': []  # Not needed for no_postop_imaging validation
                }

                investigation = self.investigation_engine.investigate_gap_filling_failure(
                    gap_type='no_postop_imaging',
                    event={'surgery_date': surgery_date.isoformat(), 'patient_id': self.athena_patient_id},
                    reason=f"v_imaging query returned 0 results for {surgery_date.isoformat()} (1-5 day post-op window)",
                    patient_context=patient_context  # V4.7.5: Pass patient_context for clinical validation
                )

                logger.info(f"        💡 Investigation Engine: {investigation['explanation']}")
                logger.info(f"        💡 Investigation suggests {len(investigation['suggested_alternatives'])} alternatives:")
                for alt in investigation['suggested_alternatives'][:3]:  # Show top 3
                    criticality = alt.get('criticality', '')
                    crit_marker = f" [{criticality}]" if criticality else ""
                    logger.info(f"          - {alt['method']}: {alt['description']}{crit_marker} (confidence: {alt['confidence']*100:.0f}%)")

                # V4.7.5: Log clinical validation results if present
                if investigation.get('clinical_validation'):
                    clinical = investigation['clinical_validation']
                    if not clinical['is_clinically_plausible']:
                        logger.warning(f"        🩺 CLINICAL PROTOCOL VIOLATION: {clinical['standard_of_care_violation']}")
                        logger.info(f"        🩺 Clinical Rationale: {clinical['clinical_rationale']}")
                        logger.info(f"        🩺 Expected Protocol: {clinical['expected_protocol']}")
                    else:
                        logger.info(f"        🩺 Clinical Assessment: {clinical['clinical_rationale']}")

                return None

            logger.info(f"        Tier 2: Post-op Imaging: ✅ Found {len(results)} post-op imaging study(ies)")

            # TIER 2A: Enhanced keyword search (fast first pass)
            for img in results:
                img_date = img.get('imaging_date')
                report_text = (img.get('report_conclusion', '') or img.get('result_information', '')).lower()

                if not report_text or len(report_text) < 20:
                    continue

                # Enhanced keyword lists covering BOTH radiological assessment AND surgical description

                # GTR keywords (complete resection)
                gtr_keywords = [
                    'no residual', 'no enhancing', 'complete resection', 'no enhancement',
                    'post-operative changes only', 'gross total', 'complete removal',
                    'no residual tumor', 'no mass effect'
                ]

                # STR keywords (subtotal resection)
                str_keywords = [
                    'minimal residual', 'small amount', 'near-complete', 'subtotal',
                    'near total', 'small residual'
                ]

                # Partial resection keywords (includes surgical terminology!)
                partial_keywords = [
                    'residual enhancement', 'residual tumor', 'persistent', 'remaining',
                    'partial resection', 'partial debulk', 'debulking', 'debulk',  # CRITICAL FIX
                    'incomplete resection', 'tumor remnant'
                ]

                # Biopsy keywords
                biopsy_keywords = [
                    'biopsy only', 'diagnostic biopsy', 'tissue sampling',
                    'no resection', 'biopsy site'
                ]

                if any(kw in report_text for kw in gtr_keywords):
                    logger.info(f"        💡 Tier 2A (Keywords): Found EOR='GTR' in imaging dated {img_date}")
                    return 'GTR'
                elif any(kw in report_text for kw in biopsy_keywords):
                    logger.info(f"        💡 Tier 2A (Keywords): Found EOR='Biopsy' in imaging dated {img_date}")
                    return 'Biopsy'
                elif any(kw in report_text for kw in str_keywords):
                    logger.info(f"        💡 Tier 2A (Keywords): Found EOR='STR' in imaging dated {img_date}")
                    return 'STR'
                elif any(kw in report_text for kw in partial_keywords):
                    logger.info(f"        💡 Tier 2A (Keywords): Found EOR='Partial' in imaging dated {img_date}")
                    return 'Partial'

            logger.info(f"        Tier 2A (Keywords): No clear keywords found - escalating to Tier 2B (MedGemma)")

            # TIER 2B: MedGemma intelligent interpretation
            # Only run if keywords failed but we have substantial text
            for img in results:
                img_date = img.get('imaging_date')
                report_text = img.get('report_conclusion', '') or img.get('result_information', '')

                if not report_text or len(report_text) < 100:  # Need substantial text for MedGemma
                    continue

                logger.info(f"        Tier 2B (MedGemma): Interpreting imaging report from {img_date} ({len(report_text)} chars)")

                eor_from_medgemma = self._medgemma_extract_eor_from_imaging(report_text, surgery_date, img_date)

                if eor_from_medgemma:
                    logger.info(f"        ✅ Tier 2B (MedGemma): Extracted EOR='{eor_from_medgemma}' from imaging dated {img_date}")
                    return eor_from_medgemma
                else:
                    logger.info(f"        ⚠️  Tier 2B (MedGemma): Failed to extract EOR - escalating to Tier 2C (Investigation Engine)")

                    # TIER 2C: Investigation Engine reasoning fallback
                    eor_from_investigation = self._investigation_engine_review_imaging_for_eor(
                        report_text, surgery_date, img_date
                    )

                    if eor_from_investigation:
                        logger.info(f"        ✅ Tier 2C (Investigation): Reasoned EOR='{eor_from_investigation}' from imaging dated {img_date}")
                        return eor_from_investigation

            logger.info(f"        ⚠️  All tiers exhausted: No EOR found in {len(results)} imaging report(s)")
            return None

        except Exception as e:
            logger.debug(f"        Tier 2 post-op imaging query failed: {e}")
            return None

    def _enrich_eor_from_v_imaging(self) -> int:
        """
        V4.6.4 PHASE 3.5: Proactively enrich EOR from v_imaging structured data

        This runs BEFORE Phase 4 binary extraction to leverage fast structured queries.
        Uses same logic as remediation Tier 2 but runs proactively.

        Benefits:
        - Fast: Structured query vs binary download
        - Reliable: Text already extracted
        - Budget-friendly: Doesn't count against --max-extractions
        - Feeds Phase 4: Results available for EOROrchestrator adjudication

        Returns:
            Number of EOR values enriched from v_imaging
        """
        from datetime import datetime, timedelta

        enriched_count = 0

        # Find all surgery events (regardless of whether EOR exists)
        surgery_events = [e for e in self.timeline_events if e.get('event_type') == 'surgery']

        if not surgery_events:
            logger.info("    No surgeries found - skipping v_imaging EOR enrichment")
            return 0

        logger.info(f"    Enriching EOR from v_imaging for {len(surgery_events)} surgeries...")

        for surg_event in surgery_events:
            event_date_str = surg_event.get('event_date')
            if not event_date_str:
                continue

            try:
                surgery_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00')).date()
            except (ValueError, AttributeError):
                continue

            # Query v_imaging for post-op MRI/CT (1-5 days post-surgery)
            eor_from_imaging = self._search_postop_imaging_for_eor(surgery_date)

            if eor_from_imaging:
                # Store in event as imaging-derived EOR
                # Phase 4 EOROrchestrator will adjudicate operative note vs imaging
                if 'v_imaging_eor' not in surg_event:
                    surg_event['v_imaging_eor'] = eor_from_imaging
                    surg_event['v_imaging_eor_date'] = event_date_str
                    enriched_count += 1
                    logger.info(f"      ✅ Enriched v_imaging EOR={eor_from_imaging} for surgery on {event_date_str[:10]}")

        logger.info(f"    📊 V_imaging EOR enrichment: {enriched_count}/{len(surgery_events)} surgeries enriched")
        return enriched_count

    def _remediate_missing_extent_of_resection(self) -> int:
        """
        V4.6.4 PHASE 2.2: Remediate missing extent of resection

        Multi-source strategy:
        - Tier 1: Operative notes (surgeon's assessment)
        - Tier 2: Post-operative imaging (objective radiological assessment)
        - Extract EOR keywords: GTR, STR, biopsy, partial resection, etc.
        - Map to standard values
        """
        from datetime import datetime, timedelta
        import re

        filled_count = 0

        # Find all surgery events missing extent of resection
        surgery_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'surgery'
                         and not e.get('extent_of_resection')]

        if not surgery_events:
            return 0

        logger.info(f"   → Remediating {len(surgery_events)} missing extent of resection...")

        for surg_event in surgery_events:
            surgery_date_str = surg_event.get('event_date')
            if not surgery_date_str:
                continue

            surgery_date = datetime.fromisoformat(surgery_date_str.replace('Z', '+00:00')).date()

            logger.info(f"      Searching for EOR for surgery on {surgery_date_str}")

            # Search for operative notes within ±7 days of surgery
            window_start = (surgery_date - timedelta(days=7)).isoformat()
            window_end = (surgery_date + timedelta(days=7)).isoformat()

            # CRITICAL FIX: dr.date contains timestamp strings like "2021-10-30T16:56:59Z"
            # Must use SUBSTR to extract date portion (same as treatment end date fix)
            query = f"""
            SELECT
                drc.content_attachment_url as binary_id,
                dr.type_text as doc_type_text,
                dr.date as doc_date
            FROM fhir_prd_db.document_reference dr
            JOIN fhir_prd_db.document_reference_content drc
                ON dr.id = drc.document_reference_id
            WHERE dr.subject_reference = '{self.patient_id}'
                AND dr.date IS NOT NULL
                AND LENGTH(dr.date) >= 10
                AND (
                    LOWER(dr.type_text) LIKE '%operative%'
                    OR LOWER(dr.type_text) LIKE '%op%note%'
                    OR LOWER(dr.type_text) LIKE '%surgery%'
                    OR LOWER(dr.type_text) LIKE '%procedure%note%'
                )
                AND DATE(SUBSTR(dr.date, 1, 10)) >= DATE '{window_start}'
                AND DATE(SUBSTR(dr.date, 1, 10)) <= DATE '{window_end}'
                AND drc.content_attachment_url IS NOT NULL
            ORDER BY ABS(DATE_DIFF('day', DATE(SUBSTR(dr.date, 1, 10)), DATE '{surgery_date.isoformat()}')) ASC
            LIMIT 5
            """

            try:
                logger.info(f"        Tier 1: Operative Notes: Searching operative notes (±7d from {surgery_date.isoformat()})...")
                results = query_athena(query, "Tier 1: Query operative notes for EOR", suppress_output=True)

                if not results:
                    logger.info(f"        Tier 1: Operative Notes: No operative notes found in ±7d window")
                    logger.info(f"        ❌ Could not find extent of resection for surgery on {surgery_date_str}")
                    continue

                logger.info(f"        Tier 1: Operative Notes: ✅ Found {len(results)} operative note(s) in ±7d window")

                # Search each operative note for EOR keywords
                eor_found = None
                for note in results:
                    binary_id = note.get('binary_id')
                    note_date = note.get('doc_date')

                    # Fetch note text from cache or S3
                    note_text = self._get_cached_binary_text(binary_id)

                    if not note_text:
                        try:
                            binary_content = self.binary_agent.stream_binary_from_s3(binary_id)
                            if binary_content:
                                text, error = self.binary_agent.extract_text_from_pdf(binary_content)
                                if not text or len(text.strip()) < 50:
                                    text, error = self.binary_agent.extract_text_from_html(binary_content)
                                if not text or len(text.strip()) < 50:
                                    text, error = self.binary_agent.extract_text_from_image(binary_content)

                                if text and len(text.strip()) > 50:
                                    note_text = text
                        except Exception as e:
                            logger.debug(f"          Could not fetch operative note {binary_id[:30]}: {e}")
                            continue

                    if not note_text:
                        continue

                    # Extract EOR from note text using keywords
                    note_lower = note_text.lower()

                    # EOR keyword patterns (in priority order - most specific first)
                    # GTR keywords
                    if any(kw in note_lower for kw in [
                        'gross total resection', 'gross-total resection', 'complete resection',
                        'total resection', 'radical resection', 'en bloc resection',
                        ' gtr ', 'gtr.', 'gtr,', 'gtr:', 'gtr;',  # GTR with word boundaries
                        'complete removal', 'total removal', 'complete excision',
                        'no residual tumor', 'no residual'
                    ]):
                        eor_found = 'GTR'
                    # STR keywords
                    elif any(kw in note_lower for kw in [
                        'subtotal resection', 'sub-total resection', 'near total resection',
                        'near-total resection', 'near complete resection',
                        ' str ', 'str.', 'str,', 'str:', 'str;',  # STR with word boundaries
                        'maximum safe resection', 'maximal safe resection',
                        'residual tumor', 'residual disease', 'incomplete resection'
                    ]):
                        eor_found = 'STR'
                    # Partial resection keywords
                    elif any(kw in note_lower for kw in [
                        'partial resection', 'partial removal', 'partial excision',
                        'debulking', 'de-bulking', 'cytoreduction', 'cyto-reduction',
                        'significant residual', 'substantial residual'
                    ]):
                        eor_found = 'Partial'
                    # Biopsy keywords
                    elif any(kw in note_lower for kw in [
                        'biopsy only', 'stereotactic biopsy', 'needle biopsy',
                        'open biopsy', 'incisional biopsy', 'diagnostic biopsy',
                        'tissue sampling only', 'sample obtained'
                    ]):
                        eor_found = 'Biopsy'

                    if eor_found:
                        logger.info(f"        💡 Tier 1: Operative Notes: Found EOR='{eor_found}' in note dated {note_date}")
                        surg_event['extent_of_resection'] = eor_found
                        filled_count += 1
                        logger.info(f"        ✅ Found extent of resection: {eor_found} for surgery on {surgery_date_str}")
                        break

                if not eor_found:
                    logger.info(f"        ❌ Could not extract EOR keywords from {len(results)} operative note(s) for surgery on {surgery_date_str}")

            except Exception as e:
                logger.debug(f"        Tier 1 operative notes query failed: {e}")
                logger.info(f"        ❌ Could not find extent of resection for surgery on {surgery_date_str} (query failed)")

            # TIER 2: Post-operative imaging (if Tier 1 failed)
            if not eor_found:
                eor_found = self._search_postop_imaging_for_eor(surgery_date)
                if eor_found:
                    surg_event['extent_of_resection'] = eor_found
                    filled_count += 1
                    logger.info(f"        ✅ Found extent of resection: {eor_found} for surgery on {surgery_date_str}")

        total_missing = len(surgery_events)
        logger.info(f"   📊 Extent of Resection Remediation Summary:")
        logger.info(f"      Total missing: {total_missing}")
        logger.info(f"      Successfully filled: {filled_count} ({100*filled_count/total_missing if total_missing > 0 else 0:.1f}%)")
        logger.info(f"      Still missing: {total_missing - filled_count}")
        if filled_count > 0:
            logger.info(f"     ✅ Found {filled_count} extent of resection values")

        return filled_count

    def _search_notes_for_treatment_end(self, start_date, treatment_type: str, agent_names: List[str],
                                        note_types: List[str], tier_name: str) -> Optional[str]:
        """
        Search clinical notes for treatment completion/end date with adaptive expansion

        Args:
            start_date: Treatment start date
            treatment_type: 'chemotherapy' or 'radiation'
            agent_names: List of chemo agents (for chemotherapy)
            note_types: List of note types to search
            tier_name: Name for logging

        Returns:
            End date string (YYYY-MM-DD) or None
        """
        from datetime import timedelta
        import re

        # Adaptive search windows: start narrow, expand if keywords found
        search_windows = [30, 60, 90]  # days

        for window_days in search_windows:
            window_start = (start_date - timedelta(days=window_days)).isoformat()
            window_end = (start_date + timedelta(days=window_days)).isoformat()

            # Build note type filter
            note_type_conditions = " OR ".join([f"type_text = '{nt}'" for nt in note_types])

            # CRITICAL FIX: dr.date contains timestamp strings like "2021-10-30T16:56:59Z"
            # Must use SUBSTR to extract date portion, same as Tier 6 operative note fix
            query = f"""
            SELECT
                drc.content_attachment_url as binary_id,
                dr.type_text,
                dr.date as note_date
            FROM fhir_prd_db.document_reference dr
            JOIN fhir_prd_db.document_reference_content drc
                ON dr.id = drc.document_reference_id
            WHERE dr.subject_reference = '{self.patient_id}'
                AND dr.date IS NOT NULL
                AND LENGTH(dr.date) >= 10
                AND ({note_type_conditions})
                AND DATE(SUBSTR(dr.date, 1, 10)) >= DATE '{window_start}'
                AND DATE(SUBSTR(dr.date, 1, 10)) <= DATE '{window_end}'
                AND drc.content_attachment_url IS NOT NULL
            ORDER BY ABS(DATE_DIFF('day', DATE(SUBSTR(dr.date, 1, 10)), DATE '{start_date.isoformat()}')) ASC
            LIMIT 10
            """

            try:
                logger.info(f"        {tier_name}: Searching {', '.join(note_types)} (±{window_days}d from {start_date.isoformat()})...")
                results = query_athena(query, f"{tier_name}: Query notes", suppress_output=True)

                if not results:
                    logger.info(f"        {tier_name}: No notes found in ±{window_days}d window")
                    continue

                logger.info(f"        {tier_name}: ✅ Found {len(results)} note(s) in ±{window_days}d window")

                # Search each note for completion keywords and dates
                for note in results:
                    binary_id = note.get('binary_id')
                    note_date = note.get('note_date')

                    # Fetch note text
                    note_text = self._get_cached_binary_text(binary_id)

                    if not note_text:
                        # Fetch from S3
                        try:
                            binary_content = self.binary_agent.stream_binary_from_s3(binary_id)
                            if binary_content:
                                # Try PDF extraction first
                                text, error = self.binary_agent.extract_text_from_pdf(binary_content)

                                if not text or len(text.strip()) < 50:
                                    # PDF failed or returned minimal text - try HTML fallback
                                    logger.debug(f"          PDF extraction failed/insufficient, trying HTML fallback...")
                                    text, error = self.binary_agent.extract_text_from_html(binary_content)

                                if text and len(text.strip()) > 50:
                                    note_text = text
                                    logger.debug(f"          ✅ Successfully extracted {len(text)} chars from note")
                                    # Cache it
                                    if not hasattr(self, 'binary_extractions'):
                                        self.binary_extractions = []
                                    self.binary_extractions.append({
                                        'binary_id': binary_id,
                                        'extracted_text': text,
                                        'content_type': 'application/pdf',
                                        'extraction_method': 'phase_2_2_remediation',
                                        'text_length': len(text)
                                    })
                        except Exception as e:
                            logger.debug(f"          Could not fetch note {binary_id[:20]}: {e}")
                            continue

                    if not note_text:
                        continue

                    # Search for completion keywords
                    completion_keywords = [
                        'complet', 'finish', 'last dose', 'final', 'end',
                        'discontinu', 'stopp', 'conclude'
                    ]

                    note_lower = note_text.lower()

                    # Check if note mentions completion
                    has_completion_keyword = any(kw in note_lower for kw in completion_keywords)

                    if not has_completion_keyword:
                        continue

                    # For chemotherapy: check if agent names are mentioned
                    if treatment_type == 'chemotherapy' and agent_names:
                        agent_mentioned = any(agent.lower() in note_lower for agent in agent_names)
                        if not agent_mentioned:
                            continue

                    # For radiation: check for radiation keywords
                    if treatment_type == 'radiation':
                        radiation_mentioned = any(kw in note_lower for kw in ['radiation', 'radiotherapy', 'xrt', 'rt'])
                        if not radiation_mentioned:
                            continue

                    # Found a relevant note! Use MedGemma reasoning to extract end date
                    # V4.8.2: Replace regex patterns with LLM reasoning for better accuracy
                    extracted_date = self._extract_therapy_end_date_with_medgemma(
                        note_text=note_text,
                        treatment_type=treatment_type,
                        agent_names=agent_names,
                        start_date=start_date.isoformat(),
                        tier_name=tier_name
                    )

                    if extracted_date:
                        logger.info(f"        ✅ {tier_name}: Found end date '{extracted_date}' via MedGemma reasoning")
                        return extracted_date

                    # V4.8.2: If MedGemma extraction fails, DO NOT fall back to note date
                    # (Previous behavior: used note_date as proxy, which was incorrect)
                    logger.info(f"        ⚠️  {tier_name}: MedGemma could not extract end date from note dated {note_date}")
                    # Continue searching other notes in this tier before giving up
                    continue

            except Exception as e:
                logger.debug(f"        {tier_name} query failed: {e}")
                continue

        return None

    def _extract_therapy_end_date_with_medgemma(
        self,
        note_text: str,
        treatment_type: str,
        agent_names: List[str],
        start_date: str,
        tier_name: str
    ) -> Optional[str]:
        """
        V4.8.2: Use MedGemma reasoning to extract therapy end date from clinical note.

        This replaces simple regex patterns with medical LLM reasoning, aligning with
        the two-agent orchestrator-extractor architecture.

        Args:
            note_text: Full clinical note text
            treatment_type: 'chemotherapy' or 'radiation'
            agent_names: List of drug names (for chemotherapy)
            start_date: Treatment start date (for context)
            tier_name: Tier name for logging

        Returns:
            End date string (YYYY-MM-DD) or None if not found
        """
        if not self.medgemma_agent:
            logger.debug(f"        {tier_name}: MedGemma not available, skipping reasoning-based extraction")
            return None

        # Build context-aware prompt
        treatment_description = treatment_type
        if treatment_type == 'chemotherapy' and agent_names:
            treatment_description = f"{treatment_type} with {', '.join(agent_names)}"

        # V4.8.3: Build more specific prompt with drug names
        drug_context = ""
        if treatment_type == 'chemotherapy' and agent_names:
            drug_list = ', '.join(agent_names)
            drug_context = f"""
SPECIFIC DRUGS TO MATCH:
- Only extract completion dates for: {drug_list}
- IGNORE completion dates for other drugs (e.g., if note mentions "completed temozolomide" but we're looking for etoposide, return null)
"""

        prompt = f"""You are a medical AI extracting treatment completion information from a clinical note.

TREATMENT CONTEXT:
- Type: {treatment_description}
- Start date: {start_date}
{drug_context}
TASK:
Extract the END DATE or COMPLETION DATE for THIS SPECIFIC TREATMENT from the note below.

Look for:
1. Explicit completion statements (e.g., "completed {treatment_description} on 2017-11-16")
2. "Last dose" dates for the specific drug(s) listed above
3. "Final cycle" dates
4. Treatment discontinuation dates
5. Statements like "finished {treatment_type}"

CRITICAL VALIDATION:
- End date MUST be ON OR AFTER start date ({start_date})
- If you find a completion date BEFORE {start_date}, it's for a DIFFERENT treatment - return null
- Return the ACTUAL TREATMENT END DATE, not the note date/timestamp
- If multiple dates are mentioned, use the one for THIS SPECIFIC DRUG that indicates completion
- If the note only mentions ongoing treatment or no completion date for THIS DRUG, return null
- Format: YYYY-MM-DD

OUTPUT SCHEMA (JSON):
{{
  "end_date": "YYYY-MM-DD" | null,
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "reasoning": "Brief explanation of how you determined the end date AND which drug it refers to"
}}

CLINICAL NOTE:
{note_text[:4000]}
"""

        try:
            logger.info(f"        {tier_name} (MedGemma): Extracting therapy end date with medical reasoning...")
            result = self.medgemma_agent.extract(prompt, temperature=0.1)

            if not result or not result.success:
                logger.warning(f"        {tier_name} (MedGemma): Extraction failed: {result.error if result else 'No result'}")
                return None

            # Parse JSON response
            import json
            try:
                data = json.loads(result.raw_response)
            except json.JSONDecodeError:
                # Try to extract JSON from response if wrapped in other text
                import re
                json_match = re.search(r'\{.*\}', result.raw_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    logger.warning(f"        {tier_name} (MedGemma): Could not parse JSON response")
                    return None

            end_date = data.get('end_date')
            confidence = data.get('confidence', 'UNKNOWN')
            reasoning = data.get('reasoning', 'No reasoning provided')

            if end_date and end_date != 'null':
                # V4.8.3: Temporal validation - reject end dates BEFORE start dates
                from datetime import datetime
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))

                    if end_dt < start_dt:
                        logger.warning(f"        ❌ {tier_name} (MedGemma): Rejected end_date='{end_date}' - BEFORE start_date '{start_date}'")
                        logger.warning(f"           Reasoning: {reasoning}")
                        logger.warning(f"           Likely extracted completion date for DIFFERENT treatment")
                        return None
                except Exception as e:
                    logger.debug(f"        {tier_name}: Could not validate temporal order: {e}")

                logger.info(f"        ✅ {tier_name} (MedGemma): Extracted end_date='{end_date}' (confidence: {confidence})")
                logger.info(f"           Reasoning: {reasoning}")
                return end_date
            else:
                logger.info(f"        {tier_name} (MedGemma): No end date found in note")
                logger.debug(f"           Reasoning: {reasoning}")
                return None

        except Exception as e:
            logger.error(f"        {tier_name} (MedGemma): Error during extraction: {e}")
            return None

    def _search_radiation_documents_for_end_date(self, start_date) -> Optional[str]:
        """
        Search v_radiation_documents for completion summaries
        """
        from datetime import timedelta

        window_start = (start_date - timedelta(days=60)).isoformat()
        window_end = (start_date + timedelta(days=60)).isoformat()

        query = f"""
        SELECT
            docc_attachment_url as binary_id,
            doc_type_text,
            doc_date
        FROM fhir_prd_db.v_radiation_documents
        WHERE patient_fhir_id = '{self.athena_patient_id}'
            AND doc_date >= DATE '{window_start}'
            AND doc_date <= DATE '{window_end}'
            AND (
                LOWER(doc_type_text) LIKE '%complet%'
                OR LOWER(doc_type_text) LIKE '%summary%'
                OR LOWER(doc_type_text) LIKE '%discharge%'
            )
            AND docc_attachment_url IS NOT NULL
        ORDER BY ABS(DATE_DIFF('day', doc_date, DATE '{start_date.isoformat()}')) ASC
        LIMIT 5
        """

        try:
            results = query_athena(query, "Tier 1: Query radiation completion documents", suppress_output=True)

            if not results:
                return None

            logger.debug(f"        Tier 1: Found {len(results)} radiation documents")

            # Search documents for end date
            for doc in results:
                binary_id = doc.get('binary_id')
                doc_date = doc.get('doc_date')

                doc_text = self._get_cached_binary_text(binary_id)

                if not doc_text:
                    try:
                        binary_content = self.binary_agent.stream_binary_from_s3(binary_id)
                        if binary_content:
                            text, error = self.binary_agent.extract_text_from_pdf(binary_content)
                            if not text or len(text.strip()) < 50:
                                text, error = self.binary_agent.extract_text_from_html(binary_content)

                            if text and len(text.strip()) > 50:
                                doc_text = text
                    except Exception as e:
                        logger.debug(f"          Could not fetch radiation doc {binary_id[:20]}: {e}")
                        continue

                if not doc_text:
                    continue

                # Look for completion keywords and dates
                doc_lower = doc_text.lower()
                if any(kw in doc_lower for kw in ['complet', 'finish', 'final', 'end', 'last fraction']):
                    # Use document date as end date
                    logger.info(f"        💡 Tier 1: Using radiation document date {doc_date} as end date")
                    return doc_date

        except Exception as e:
            logger.debug(f"        Tier 1 radiation documents query failed: {e}")

        return None

    def _classify_imaging_response(self, report_text: str) -> Dict:
        """V4.6 GAP #5: Classify imaging response using RANO keywords."""
        if not report_text:
            return {'rano_assessment': None, 'progression_flag': None, 'response_flag': None}
        text_lower = report_text.lower()
        progression_keywords = ['progression', 'progressing', 'progressive', 'increased', 'increase in', 'enlarging',
                               'enlargement', 'enlarged', 'expansion', 'growing', 'growth', 'larger',
                               'worsening', 'worsen', 'worse', 'new enhancement', 'new lesion', 'additional lesion']
        recurrence_keywords = ['recurrence', 'recurrent', 'recurred', 'tumor recurrence', 'disease recurrence']
        response_keywords = ['decreased', 'decrease in', 'decreasing', 'reduction', 'reduced', 'reducing',
                            'shrinkage', 'shrinking', 'smaller', 'improvement', 'improved', 'improving',
                            'resolving', 'resolved', 'resolution']
        stable_keywords = ['stable', 'stability', 'unchanged', 'no change', 'no significant change',
                          'similar', 'comparable to prior']
        complete_response_keywords = ['no evidence of', 'no residual', 'no tumor', 'complete resolution',
                                     'complete response', 'no enhancement', 'no enhancing lesion']
        if any(kw in text_lower for kw in progression_keywords):
            if any(kw in text_lower for kw in recurrence_keywords):
                return {'rano_assessment': 'PD', 'progression_flag': 'recurrence_suspected', 'response_flag': None}
            else:
                return {'rano_assessment': 'PD', 'progression_flag': 'progression_suspected', 'response_flag': None}
        if any(kw in text_lower for kw in complete_response_keywords):
            return {'rano_assessment': 'CR', 'progression_flag': None, 'response_flag': 'complete_response_suspected'}
        if any(kw in text_lower for kw in response_keywords):
            return {'rano_assessment': 'PR', 'progression_flag': None, 'response_flag': 'response_suspected'}
        if any(kw in text_lower for kw in stable_keywords):
            return {'rano_assessment': 'SD', 'progression_flag': None, 'response_flag': 'stable_disease'}
        return {'rano_assessment': None, 'progression_flag': None, 'response_flag': None}

    def _enrich_imaging_with_rano_assessment(self):
        """V4.6 GAP #5: Add RANO assessment to all imaging events."""
        logger.info("🏥 V4.6 GAP #5: Adding RANO assessment to imaging events...")
        imaging_count = 0
        classified_count = 0
        for event in self.timeline_events:
            if event.get('event_type') != 'imaging':
                continue
            imaging_count += 1
            report_text = (event.get('report_conclusion', '') or event.get('result_information', '') or
                          event.get('medgemma_extraction', {}).get('radiologist_impression', ''))
            classification = self._classify_imaging_response(report_text)
            if not event.get('rano_assessment'):
                event['rano_assessment'] = classification['rano_assessment']
            if not event.get('progression_flag'):
                event['progression_flag'] = classification['progression_flag']
            if not event.get('response_flag'):
                event['response_flag'] = classification['response_flag']
            if classification['rano_assessment']:
                classified_count += 1
        logger.info(f"  ✅ Classified {classified_count}/{imaging_count} imaging events")
        logger.info(f"     PD: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'PD')}")
        logger.info(f"     SD: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'SD')}")
        logger.info(f"     PR: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'PR')}")
        logger.info(f"     CR: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'CR')}")

    def _extract_molecular_findings(self) -> List[str]:
        """
        V4.6: Extract molecular markers from pathology data

        Returns:
            List of molecular markers found
        """
        findings = []

        # Check pathology events for molecular markers
        for event in self.timeline_events:
            if event.get('event_type') == 'pathology':
                markers = event.get('molecular_markers', [])
                findings.extend(markers)

        # Also check diagnosis data
        if hasattr(self, 'who_2021_classification'):
            diagnosis = self.who_2021_classification.get('who_2021_diagnosis', '')

            # Extract markers from diagnosis string
            if 'IDH' in diagnosis:
                findings.append('IDH-mutant' if 'mutant' in diagnosis else 'IDH-wildtype')
            if 'H3 K27' in diagnosis:
                findings.append('H3 K27-altered')
            if 'MGMT' in diagnosis:
                findings.append('MGMT methylated' if 'methylat' in diagnosis else 'MGMT unmethylated')

        return list(set(findings))  # Deduplicate

    def _phase5_protocol_validation(self):
        """
        V3 Phase 5: Validate care against WHO 2021 evidence-based protocols

        Uses MedGemma to analyze actual patient care against WHO CNS5 treatment standards
        """
        # Track Phase 5 protocol validation attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase5_protocol_validation')

        # VERBOSE DEBUG: Recursion guard and call stack tracking
        import traceback
        if hasattr(self, '_phase5_recursion_count'):
            self._phase5_recursion_count += 1
            logger.error(f"🔴 RECURSION DETECTED! Call #{self._phase5_recursion_count}")
            logger.error("Call stack:")
            for line in traceback.format_stack():
                logger.error(line.strip())
            if self._phase5_recursion_count > 5:
                raise RecursionError(f"Phase 5 called recursively {self._phase5_recursion_count} times!")
        else:
            self._phase5_recursion_count = 1
            logger.info(f"✅ Phase 5 entered for first time (patient: {self.patient_id})")

        print("\n" + "="*80)
        print("PHASE 5: WHO 2021 PROTOCOL VALIDATION")
        print("="*80)
        logger.info("Phase 5: Printed header")

        # Check if MedGemma is available
        logger.info("Phase 5: Checking MedGemma availability...")
        if not self.medgemma_agent:
            logger.warning("⚠️  MedGemma not available - skipping protocol validation")
            self.protocol_validations.append({
                'status': 'SKIPPED',
                'reason': 'MedGemma agent not initialized'
            })

            # Track Phase 5 as skipped
            if self.completeness_tracker:
                self.completeness_tracker.mark_failure(
                    'phase5_protocol_validation',
                    error_message="MedGemma not available"
                )
            return
        logger.info("Phase 5: MedGemma available")

        # Get WHO diagnosis
        logger.info("Phase 5: Getting WHO diagnosis...")
        diagnosis = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        logger.info(f"Phase 5: WHO diagnosis = {diagnosis}")

        if diagnosis in ['Unknown', 'Insufficient data', 'Classification failed']:
            logger.warning(f"⚠️  Cannot validate protocol - WHO classification: {diagnosis}")
            self.protocol_validations.append({
                'status': 'SKIPPED',
                'reason': f'No valid WHO classification (status: {diagnosis})'
            })

            # Track Phase 5 as skipped due to no WHO classification
            if self.completeness_tracker:
                self.completeness_tracker.mark_failure(
                    'phase5_protocol_validation',
                    error_message=f"No valid WHO classification: {diagnosis}"
                )
            return

        logger.info(f"Validating care for: {diagnosis}")

        # V4.6: Structured WHO KB validation
        if self.who_kb:
            logger.info("🔬 V4.6: Running structured WHO CNS validation")

            # Validate diagnosis against WHO 2021 criteria
            patient_age = self.patient_demographics.get('pd_age_years')
            tumor_location = self.patient_demographics.get('tumor_location')

            validation = self.who_kb.validate_diagnosis(
                diagnosis=diagnosis,
                patient_age=patient_age,
                tumor_location=tumor_location
            )

            logger.info(f"  Diagnosis validity: {validation['valid']}")
            if not validation['valid']:
                logger.warning(f"  ⚠️  Validation issues: {validation.get('issues', [])}")

            # Check for molecular grading overrides
            molecular_findings = self._extract_molecular_findings()
            if molecular_findings:
                override = self.who_kb.check_molecular_grading_override(
                    diagnosis=diagnosis,
                    molecular_findings=molecular_findings
                )

                if override:
                    logger.info(f"  🧬 Molecular override detected:")
                    logger.info(f"    Original grade: {override['original_grade']}")
                    logger.info(f"    Overridden by: {override['molecular_marker']}")
                    logger.info(f"    New classification: {override['revised_diagnosis']}")

                    # Store override for artifact
                    self.molecular_grade_override = override

            # Check NOS/NEC suffix appropriateness
            molecular_tested = len(molecular_findings) > 0
            nos_nec_suggestion = self.who_kb.suggest_nos_or_nec(
                diagnosis=diagnosis,
                molecular_testing_performed=molecular_tested,
                molecular_results_contradictory=validation.get('molecular_contradictory', False)
            )

            if nos_nec_suggestion:
                logger.info(f"  📝 WHO suffix suggestion: {nos_nec_suggestion}")

        # Load WHO 2021 Diagnostic Agent Prompt (cross-episode implications and treatment guidance)
        try:
            with open(WHO_2021_DIAGNOSTIC_AGENT_PROMPT_PATH, 'r') as f:
                # Load sections relevant to protocol validation (last 10K chars contain treatment implications)
                diagnostic_agent_content = f.read()
                # Extract CROSS-EPISODE IMPLICATIONS section and quality checklist
                treatment_sections = diagnostic_agent_content[25000:35000]  # Treatment/protocol sections
        except Exception as e:
            logger.warning(f"Could not load diagnostic agent prompt: {e}")
            treatment_sections = ""

        # Load WHO reference content (diagnostic criteria and treatment protocols)
        try:
            with open(WHO_2021_REFERENCE_PATH, 'r') as f:
                who_reference_content = f.read()[:15000]
        except Exception as e:
            logger.error(f"Error loading WHO reference: {e}")
            self.protocol_validations.append({
                'status': 'ERROR',
                'reason': f'Could not load WHO reference: {e}'
            })
            return

        # Prepare timeline summary for validation
        timeline_summary = self._prepare_timeline_summary_for_validation()

        # Create validation prompt
        prompt = self._create_protocol_validation_prompt(
            diagnosis=diagnosis,
            who_reference=who_reference_content,
            treatment_guidance=treatment_sections,
            timeline_summary=timeline_summary
        )

        # Execute MedGemma validation
        try:
            logger.info("Executing MedGemma protocol validation...")
            result = self.medgemma_agent.extract(prompt)

            if result and result.success:
                # Parse validation results
                validation_data = {
                    'diagnosis': diagnosis,
                    'validation_timestamp': datetime.now().isoformat(),
                    'who_reference_used': str(WHO_2021_REFERENCE_PATH),
                    'patient_age': self.patient_demographics.get('pd_age_years'),
                    'protocol_considerations': self.protocol_considerations,
                    'validation_result': result.raw_response,
                    'confidence': result.confidence if hasattr(result, 'confidence') else 'unknown'
                }

                self.protocol_validations.append(validation_data)
                logger.info("✅ Protocol validation complete")

                # Track Phase 5 success
                if self.completeness_tracker:
                    self.completeness_tracker.mark_success(
                        'phase5_protocol_validation',
                        record_count=1
                    )

                print(f"\n  Validation Summary:")
                print(f"  Diagnosis: {diagnosis}")
                print(f"  Age: {self.patient_demographics.get('pd_age_years')} years")
                print(f"  Confidence: {validation_data['confidence']}")

            else:
                logger.warning("⚠️  MedGemma validation returned unsuccessful result")
                self.protocol_validations.append({
                    'status': 'FAILED',
                    'reason': 'MedGemma extraction unsuccessful'
                })

                # Track Phase 5 failure
                if self.completeness_tracker:
                    self.completeness_tracker.mark_failure(
                        'phase5_protocol_validation',
                        error_message="MedGemma validation unsuccessful"
                    )

        except Exception as e:
            logger.error(f"Error during protocol validation: {e}")
            self.protocol_validations.append({
                'status': 'ERROR',
                'reason': str(e)
            })

            # Track Phase 5 error
            if self.completeness_tracker:
                self.completeness_tracker.mark_failure(
                    'phase5_protocol_validation',
                    error_message=str(e)
                )

    def _prepare_timeline_summary_for_validation(self) -> str:
        """
        V3: Prepare a concise timeline summary for protocol validation

        Returns:
            Formatted string summarizing patient's clinical journey
        """
        summary_parts = []

        # Surgeries
        surgeries = [e for e in self.timeline_events if 'surgery' in e.get('event_type', '')]
        if surgeries:
            summary_parts.append(f"\n**SURGERIES ({len(surgeries)}):**")
            for s in surgeries:
                date = s.get('date', 'Unknown date')
                surgery_type = s.get('surgery_type', 'Unknown')
                eor = s.get('extent_of_resection', 'Not documented')
                summary_parts.append(f"  - {date}: {surgery_type} (EOR: {eor})")

        # Radiation
        radiation = [e for e in self.timeline_events if 'radiation' in e.get('event_type', '')]
        if radiation:
            summary_parts.append(f"\n**RADIATION ({len(radiation)}):**")
            for r in radiation:
                date = s.get('date', 'Unknown date')
                dose = r.get('total_dose_cgy', 'Unknown')
                summary_parts.append(f"  - {date}: {dose} cGy")

        # Chemotherapy
        chemo = [e for e in self.timeline_events if 'chemotherapy' in e.get('event_type', '')]
        if chemo:
            summary_parts.append(f"\n**CHEMOTHERAPY ({len(chemo)}):**")
            for c in chemo:
                start = c.get('episode_start', 'Unknown')
                agents = c.get('agents', 'Unknown')
                summary_parts.append(f"  - {start}: {agents}")

        return "\n".join(summary_parts) if summary_parts else "No treatment events documented"

    def _create_protocol_validation_prompt(self, diagnosis: str, who_reference: str, treatment_guidance: str, timeline_summary: str) -> str:
        """
        V3: Create comprehensive prompt for WHO protocol validation

        Args:
            diagnosis: WHO 2021 diagnosis
            who_reference: Excerpt from WHO classification markdown
            treatment_guidance: Treatment sections from diagnostic agent prompt
            timeline_summary: Patient's actual care timeline

        Returns:
            Formatted prompt for MedGemma
        """
        patient_age = self.patient_demographics.get('pd_age_years', 'Unknown')

        prompt = f"""You are a pediatric neuro-oncology expert validating patient care against WHO 2021 evidence-based treatment protocols.

**WHO 2021 REFERENCE KNOWLEDGE BASE:**
{who_reference}

**TREATMENT GUIDANCE FROM DIAGNOSTIC AGENT (Cross-Episode Implications):**
{treatment_guidance if treatment_guidance else 'Not available'}

**PATIENT INFORMATION:**
- WHO 2021 Diagnosis: {diagnosis}
- Age at Diagnosis: {patient_age} years
- Protocol Considerations: {', '.join(self.protocol_considerations) if self.protocol_considerations else 'None'}

**ACTUAL PATIENT CARE TIMELINE:**
{timeline_summary}

**TASK:**
Based on the WHO 2021 reference, treatment guidance, and episodic context, analyze whether this patient's care adheres to evidence-based protocols for {diagnosis}.

**PROVIDE:**
1. **Expected Treatment Protocol** (from WHO reference for this diagnosis and age)
2. **Actual Care Received** (from patient timeline)
3. **Adherence Analysis:**
   - Diagnostic workup adherence (molecular testing, imaging, etc.)
   - Treatment adherence (surgery, radiation dose/fields, chemotherapy regimen)
   - Surveillance adherence (follow-up imaging, monitoring)
4. **Deviations** (missing or off-protocol elements)
5. **Positive Findings** (protocol-adherent care)
6. **Cross-Episode Considerations** (diagnosis-driven treatment decisions)
7. **Overall Adherence Score** (0-100%)

Be specific about expected doses, agents, frequencies based on the WHO reference and treatment guidance.
"""

        return prompt

    def _phase6_generate_artifact(self):
        """Phase 6: Generate final JSON timeline artifact"""

        # Track Phase 6 artifact generation attempt
        if self.completeness_tracker:
            self.completeness_tracker.mark_attempted('phase6_artifact_generation')

        # V3: Generate extraction tracking report
        extraction_report = self._generate_extraction_report()

        artifact = {
            'patient_id': self.patient_id,
            'abstraction_timestamp': datetime.now().isoformat(),
            'who_2021_classification': self.who_2021_classification,
            'patient_demographics': self.patient_demographics,  # V3: Demographics
            'protocol_considerations': self.protocol_considerations,  # V3: Age-based considerations
            'extraction_report': extraction_report,  # V3: Extraction tracking report
            'timeline_construction_metadata': {
                'structured_data_sources': {k: len(v) for k, v in self.structured_data.items()},
                'total_timeline_events': len(self.timeline_events),
                'extraction_gaps_identified': len(self.extraction_gaps),
                'binary_extractions_performed': len(self.binary_extractions),
                'protocol_validations': len(self.protocol_validations),
                'completeness_assessment': self.completeness_assessment,
                'v2_document_discovery_stats': self.v2_document_discovery_stats,  # V4.2: Performance tracking
                'validation_stats': self.validation_stats,  # V4.2+: Validation performance
                'failed_extractions_count': len(self.failed_extractions)  # V4.2+: Failed extraction count
            },
            'timeline_events': self.timeline_events,
            'extraction_gaps': self.extraction_gaps,
            'binary_extractions': self.binary_extractions,
            'protocol_validations': self.protocol_validations
        }

        # V5.2: Add completeness metadata if available
        if self.completeness_tracker and EXCEPTION_HANDLING_AVAILABLE:
            completeness_metadata = self.completeness_tracker.get_completeness_metadata()
            artifact['v5_2_completeness_metadata'] = completeness_metadata

            if self.structured_logger:
                self.structured_logger.info(
                    f"Completeness score: {completeness_metadata['completeness_score']:.1%} "
                    f"({completeness_metadata['total_sources_succeeded']}/{completeness_metadata['total_sources_attempted']} sources)"
                )
            else:
                logger.info(
                    f"V5.2: Completeness score: {completeness_metadata['completeness_score']:.1%} "
                    f"({completeness_metadata['total_sources_succeeded']}/{completeness_metadata['total_sources_attempted']} sources)"
                )

        # V5.0: Build therapeutic approach from timeline events
        if build_therapeutic_approach is not None:
            try:
                print()
                print("  🧬 V5.0: Building therapeutic approach...")
                therapeutic_approach = build_therapeutic_approach(artifact)
                if therapeutic_approach:
                    artifact['therapeutic_approach'] = therapeutic_approach
                    print(f"     ✅ Detected {len(therapeutic_approach.get('lines_of_therapy', []))} treatment line(s)")
                else:
                    print("     ⚠️  No therapeutic approach generated (insufficient data)")
            except Exception as e:
                print(f"     ⚠️  V5.0 therapeutic approach generation failed: {e}")
                print("     V4.8 timeline artifact will still be saved")
        else:
            print()
            print("  ℹ️  V5.0 therapeutic approach abstractor not available (module import failed)")

        # Save to file
        safe_patient_id = self.patient_id.replace('/', '_')
        output_file = self.output_dir / f"{safe_patient_id}_timeline_artifact.json"
        with open(output_file, 'w') as f:
            # Use custom encoder to handle SourceRecord/Adjudication dataclasses
            json.dump(artifact, f, indent=2, cls=DataclassJSONEncoder if DataclassJSONEncoder else None)

        print(f"  ✅ Artifact saved: {output_file}")

        # V4.2: Print document discovery performance stats
        if self.v2_document_discovery_stats:
            print()
            print("  📊 V4.2 Document Discovery Performance:")
            total_lookups = sum(self.v2_document_discovery_stats.values())
            tier1_count = self.v2_document_discovery_stats.get('v2_tier1_encounter_provided', 0)
            tier2_count = self.v2_document_discovery_stats.get('v2_tier2_encounter_lookup', 0)
            tier3_count = self.v2_document_discovery_stats.get('v2_tier3_temporal_fallback', 0)
            not_found = self.v2_document_discovery_stats.get('v2_not_found', 0)

            if total_lookups > 0:
                tier1_pct = (tier1_count / total_lookups) * 100
                tier3_pct = (tier3_count / total_lookups) * 100
                print(f"     Tier 1 (Encounter-based): {tier1_count}/{total_lookups} ({tier1_pct:.1f}%) ✓")
                print(f"     Tier 2 (Encounter lookup): {tier2_count}/{total_lookups} ({tier2_count/total_lookups*100:.1f}%)")
                print(f"     Tier 3 (Temporal fallback): {tier3_count}/{total_lookups} ({tier3_pct:.1f}%)")
                print(f"     Not found: {not_found}/{total_lookups} ({not_found/total_lookups*100:.1f}%)")
                print(f"     Success rate: {(total_lookups - not_found)/total_lookups*100:.1f}%")

        # V4.2+ Enhancement #1: Report validation statistics
        if self.validation_stats:
            print()
            print("  🛡️  V4.2+ Extraction Validation Performance:")

            # Document type validation
            doc_success = self.validation_stats.get('doc_type_validation_success', 0)
            doc_mismatch = self.validation_stats.get('doc_type_validation_mismatch', 0)
            doc_no_metadata = self.validation_stats.get('doc_type_validation_no_metadata', 0)
            doc_error = self.validation_stats.get('doc_type_validation_error', 0)
            doc_total = doc_success + doc_mismatch + doc_no_metadata + doc_error

            if doc_total > 0:
                print(f"     Document Type Validation:")
                print(f"       ✓ Success: {doc_success}/{doc_total} ({doc_success/doc_total*100:.1f}%)")
                print(f"       ⚠️ Mismatch detected: {doc_mismatch}/{doc_total} ({doc_mismatch/doc_total*100:.1f}%)")
                if doc_no_metadata > 0:
                    print(f"       ⚠️ No metadata: {doc_no_metadata}/{doc_total} ({doc_no_metadata/doc_total*100:.1f}%)")
                if doc_error > 0:
                    print(f"       ❌ Errors: {doc_error}/{doc_total} ({doc_error/doc_total*100:.1f}%)")

            # Extraction result validation
            extract_success = self.validation_stats.get('extraction_validation_success', 0)
            extract_failed = self.validation_stats.get('extraction_validation_failed', 0)
            extract_total = extract_success + extract_failed

            if extract_total > 0:
                print(f"     Extraction Result Validation:")
                print(f"       ✓ Valid extractions: {extract_success}/{extract_total} ({extract_success/extract_total*100:.1f}%)")
                print(f"       ❌ Invalid extractions: {extract_failed}/{extract_total} ({extract_failed/extract_total*100:.1f}%)")

            # Failed extractions
            if len(self.failed_extractions) > 0:
                print(f"     Failed Extractions Logged: {len(self.failed_extractions)}")
                print(f"       (See artifact metadata for details)")

        # Track Phase 6 success
        if self.completeness_tracker:
            self.completeness_tracker.mark_success('phase6_artifact_generation', record_count=1)

        return artifact


def main():
    parser = argparse.ArgumentParser(
        description='Patient Clinical Journey Timeline Abstraction V2 (with real Phase 4)'
    )
    parser.add_argument(
        '--patient-id',
        type=str,
        required=True,
        help='Patient FHIR ID (with or without "Patient/" prefix)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for timeline artifacts'
    )
    parser.add_argument(
        '--max-extractions',
        type=int,
        default=None,
        help='Maximum number of binary extractions to perform (for testing)'
    )
    parser.add_argument(
        '--force-reclassify',
        action='store_true',
        help='Force re-generation of WHO 2021 classification even if cached'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last successful checkpoint (if available)'
    )

    args = parser.parse_args()

    # Check AWS SSO
    if not check_aws_sso_token():
        print("\n❌ AWS SSO token invalid. Run: aws sso login --profile radiant-prod\n")
        sys.exit(1)

    # Create output directory
    # If resuming, use the most recent directory; otherwise create new timestamped directory
    if args.resume:
        # Find most recent output directory for this patient
        base_dir = Path(args.output_dir)
        if base_dir.exists():
            existing_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()], reverse=True)
            if existing_dirs:
                output_dir = existing_dirs[0]
                print(f"🔄 Resuming from existing directory: {output_dir}")
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_dir = base_dir / timestamp
                output_dir.mkdir(parents=True, exist_ok=True)
                print(f"⚠️  No existing directory found, starting fresh: {output_dir}")
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = base_dir / timestamp
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️  Output directory doesn't exist, starting fresh: {output_dir}")
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(args.output_dir) / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)

    # Run abstraction
    abstractor = PatientTimelineAbstractor(
        args.patient_id,
        output_dir,
        max_extractions=args.max_extractions,
        force_reclassify=args.force_reclassify
    )
    artifact = abstractor.run(resume=args.resume)

    # V4.8: Generate visualization and clinical summary
    print()
    print("="*80)
    print("V4.8: GENERATING VISUALIZATION & CLINICAL SUMMARY")
    print("="*80)

    try:
        import subprocess
        artifact_path = output_dir / f"{args.patient_id}_timeline_artifact.json"

        # Get the scripts directory (same directory as this script)
        scripts_dir = Path(__file__).parent
        viz_script = scripts_dir / "create_timeline_enhanced.py"
        summary_script = scripts_dir / "generate_clinical_summary.py"

        # Generate interactive timeline visualization
        print("\n  📊 Generating interactive timeline visualization...")
        viz_result = subprocess.run(
            ["python3", str(viz_script), str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes for large patient datasets
        )
        if viz_result.returncode == 0:
            print("  ✅ Timeline visualization created")
        else:
            print(f"  ⚠️  Visualization generation failed: {viz_result.stderr}")

        # Generate clinical summary
        print("\n  📝 Generating clinical summary...")
        summary_result = subprocess.run(
            ["python3", str(summary_script), str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        if summary_result.returncode == 0:
            print("  ✅ Clinical summary created")
        else:
            print(f"  ⚠️  Clinical summary generation failed: {summary_result.stderr}")

    except Exception as e:
        print(f"  ⚠️  V4.8 post-processing error: {e}")
        print("     Timeline artifact is still available for manual visualization")

    print()
    print("="*80)
    print("ABSTRACTION COMPLETE")
    print("="*80)
    print(f"Timeline events: {artifact['timeline_construction_metadata']['total_timeline_events']}")
    print(f"Extraction gaps: {artifact['timeline_construction_metadata']['extraction_gaps_identified']}")
    print(f"Protocol validations: {artifact['timeline_construction_metadata']['protocol_validations']}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
