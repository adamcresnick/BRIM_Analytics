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
from pathlib import Path
from datetime import datetime, timedelta
import boto3
import time
from typing import Dict, List, Any, Optional, Tuple

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
    from lib.checkpoint_manager import DataclassJSONEncoder
except ImportError as e:
    logger.warning(f"Could not import DataclassJSONEncoder: {e}")
    DataclassJSONEncoder = None  # Fallback to default str encoder

# WHO 2021 CLASSIFICATION CACHE PATH
# Cache file stores all WHO 2021 classifications to avoid expensive re-computation
WHO_2021_CACHE_PATH = Path(__file__).parent.parent / 'data' / 'who_2021_classification_cache.json'

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


def check_aws_sso_token(profile_name: str = 'radiant-prod') -> bool:
    """Check if AWS SSO token is valid"""
    try:
        session = boto3.Session(profile_name=profile_name)
        sts = session.client('sts')
        sts.get_caller_identity()
        logger.info(f"AWS SSO token for '{profile_name}' is valid")
        return True
    except Exception as e:
        logger.error(f"AWS SSO token invalid: {e}")
        return False


def query_athena(query: str, description: str = None, profile: str = 'radiant-prod', suppress_output: bool = False) -> List[Dict[str, Any]]:
    """Execute Athena query and return results as list of dicts"""
    if description and not suppress_output:
        print(f"  {description}...", end='', flush=True)

    session = boto3.Session(profile_name=profile)
    client = session.client('athena', region_name='us-east-1')

    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': 'fhir_prd_db'},
        ResultConfiguration={
            'OutputLocation': 's3://aws-athena-query-results-343218191717-us-east-1/'
        }
    )

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
                logger.info(f"✅ Loaded WHO classification from cache for {self.athena_patient_id}")
                cached = classifications[self.athena_patient_id]
                logger.info(f"   Diagnosis: {cached.get('who_2021_diagnosis', 'Unknown')}")
                logger.info(f"   Classification date: {cached.get('classification_date', 'Unknown')}")
                logger.info(f"   Method: {cached.get('classification_method', 'Unknown')}")
                return cached

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

            # Update classification
            cache_data["classifications"][self.athena_patient_id] = classification
            cache_data["_metadata"]["last_updated"] = datetime.now().strftime('%Y-%m-%d')

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
            # STAGE 1: EXTRACT MOLECULAR FINDINGS AND DIAGNOSES
            # ========================================================================
            logger.info("   [Stage 1] Extracting molecular findings and diagnoses...")
            extracted_findings = self._stage1_extract_findings(pathology_data)

            if not extracted_findings or extracted_findings.get('extraction_status') == 'failed':
                logger.warning("   ⚠️  Stage 1 extraction failed, cannot proceed to Stage 2")
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

            # ========================================================================
            # STAGE 2: MAP FINDINGS TO WHO 2021 CLASSIFICATION
            # ========================================================================
            logger.info("   [Stage 2] Mapping findings to WHO 2021 classification...")
            classification = self._stage2_map_to_who2021(extracted_findings)

            if not classification or classification.get('confidence') == 'insufficient':
                logger.warning("   ⚠️  Stage 2 mapping resulted in insufficient confidence")

            result_preview = classification.get('who_2021_diagnosis', 'Unknown')[:100]
            logger.info(f"   ✅ Stage 2 complete: {result_preview}")

            # Add metadata
            classification["classification_date"] = datetime.now().strftime('%Y-%m-%d')
            classification["classification_method"] = "medgemma_two_stage_tier1"
            classification["stage1_findings"] = extracted_findings  # Store for audit trail

            confidence = classification.get('confidence', 'unknown').lower()
            logger.info(f"   Two-stage classification confidence: {confidence}")

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
            logger.error(f"Stage 2 mapping error: {e}")
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

            tier2_confidence = enhanced_classification.get('confidence', 'unknown').lower()
            tier1_confidence = tier1_classification.get('confidence', 'unknown').lower()

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

    def run(self) -> Dict[str, Any]:
        """Execute full iterative timeline abstraction workflow"""

        print("="*80)
        print(f"PATIENT TIMELINE ABSTRACTION: {self.patient_id}")
        print("="*80)
        print()

        # PHASE 0: WHO 2021 TUMOR CLASSIFICATION (Run ONCE, cache forever)
        # This is the ONLY place tumor classification happens
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
        print("PHASE 1: LOAD STRUCTURED DATA FROM ATHENA VIEWS")
        print("-"*80)
        self._phase1_load_structured_data()
        print()

        # PHASE 2: Construct initial timeline
        print("PHASE 2: CONSTRUCT INITIAL TIMELINE")
        print("-"*80)
        self._phase2_construct_initial_timeline()
        print()

        # PHASE 2.5: Assign treatment ordinality (V4 Enhancement)
        self._phase2_5_assign_treatment_ordinality()
        print()

        # PHASE 3: Identify extraction gaps
        print("PHASE 3: IDENTIFY GAPS REQUIRING BINARY EXTRACTION")
        print("-"*80)
        self._phase3_identify_extraction_gaps()
        print()

        # PHASE 4: Prioritize and extract from binaries (REAL MEDGEMMA INTEGRATION)
        print("PHASE 4: PRIORITIZED BINARY EXTRACTION WITH MEDGEMMA")
        print("-"*80)
        self._phase4_extract_from_binaries()
        print()

        # PHASE 4.5: Orchestrator assessment of extraction completeness
        print("PHASE 4.5: ORCHESTRATOR ASSESSMENT OF EXTRACTION COMPLETENESS")
        print("-"*80)
        self._phase4_5_assess_extraction_completeness()
        print()

        # PHASE 5: Protocol validation
        print("PHASE 5: WHO 2021 PROTOCOL VALIDATION")
        print("-"*80)
        self._phase5_protocol_validation()
        print()

        # PHASE 6: Generate final artifact
        print("PHASE 6: GENERATE FINAL TIMELINE ARTIFACT")
        print("-"*80)
        artifact = self._phase6_generate_artifact()
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
                    proc_performed_date_time,
                    surgery_type,
                    proc_code_text,
                    proc_encounter_reference,
                    -- V2 NEW FIELDS: V4.1 Institution tracking + cross-resource annotation
                    specimen_id,
                    performer_org_id,
                    performer_org_name,
                    institution_confidence
                FROM fhir_prd_db.v_procedures_tumor
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                    AND is_tumor_surgery = true
                ORDER BY proc_performed_date_time
            """,
            'chemotherapy': f"""
                SELECT
                    patient_fhir_id,
                    episode_start_datetime,
                    episode_end_datetime,
                    episode_drug_names
                FROM fhir_prd_db.v_chemo_treatment_episodes
                WHERE patient_fhir_id = '{self.athena_patient_id}'
                ORDER BY episode_start_datetime
            """,
            'radiation': f"""
                SELECT
                    patient_fhir_id,
                    episode_start_date,
                    episode_end_date,
                    total_dose_cgy,
                    radiation_fields
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

        self.structured_data = {}
        for source_name, query in queries.items():
            self.structured_data[source_name] = query_athena(query, f"Loading {source_name}")

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

        # STAGE 2: Procedures (surgeries)
        print("  Stage 2: Procedures (surgeries)")
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

        # Validate against expected paradigm
        if surgery_count == 0 and self.who_2021_classification.get('who_2021_diagnosis'):
            print(f"    ⚠️  WARNING: No surgeries found for patient with {self.who_2021_classification.get('who_2021_diagnosis')}")

        # STAGE 3: Chemotherapy episodes
        print("  Stage 3: Chemotherapy episodes")
        chemo_episode_count = 0
        for record in self.structured_data.get('chemotherapy', []):
            # Start event
            events.append({
                'event_type': 'chemotherapy_start',
                'event_date': record.get('episode_start_datetime', '').split()[0] if record.get('episode_start_datetime') else '',
                'stage': 3,
                'source': 'v_chemo_treatment_episodes',
                'description': f"Chemotherapy started: {record.get('episode_drug_names', '')}",
                'episode_drug_names': record.get('episode_drug_names'),
                'episode_start_datetime': record.get('episode_start_datetime'),
                'episode_end_datetime': record.get('episode_end_datetime')
            })
            # End event
            if record.get('episode_end_datetime'):
                events.append({
                    'event_type': 'chemotherapy_end',
                    'event_date': record.get('episode_end_datetime', '').split()[0] if record.get('episode_end_datetime') else '',
                    'stage': 3,
                    'source': 'v_chemo_treatment_episodes',
                    'description': f"Chemotherapy ended: {record.get('episode_drug_names', '')}",
                    'episode_drug_names': record.get('episode_drug_names')
                })
            chemo_episode_count += 1
        print(f"    ✅ Added {chemo_episode_count} chemotherapy episodes")

        # Validate against expected paradigm
        expected_chemo = self.who_2021_classification.get('recommended_protocols', {}).get('chemotherapy')
        if expected_chemo:
            print(f"    📋 Expected per WHO 2021: {expected_chemo}")
            if chemo_episode_count == 0:
                print(f"    ⚠️  WARNING: No chemotherapy episodes found, but WHO 2021 recommends: {expected_chemo}")

        # STAGE 4: Radiation episodes
        print("  Stage 4: Radiation episodes")
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
                'episode_end_date': record.get('episode_end_date')
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

        # Validate against expected paradigm
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation')
        if expected_radiation:
            print(f"    📋 Expected per WHO 2021: {expected_radiation}")
            if radiation_episode_count == 0:
                print(f"    ⚠️  WARNING: No radiation episodes found, but WHO 2021 recommends: {expected_radiation}")

        # STAGE 5: Imaging studies
        print("  Stage 5: Imaging studies")
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

        # STAGE 6: Add pathology/diagnosis events (already integrated in Stage 0, but keep granular records)
        print("  Stage 6: Pathology events (granular)")
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

        # Sort chronologically (None dates go to end)
        events.sort(key=lambda x: (x.get('event_date') is None, x.get('event_date', '')))

        # Add sequence numbers
        for i, event in enumerate(events, 1):
            event['event_sequence'] = i

        self.timeline_events = events

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

    def _phase3_identify_extraction_gaps(self):
        """Phase 3: Identify gaps in structured data requiring binary extraction"""

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
        V2 Enhanced: Find operative notes using encounter linkage with temporal fallback

        This method implements V4.2 Enhancement #2: V2 Document Discovery Steps 3-4
        Uses encounter-based lookup for 95%+ success rate vs ~70% with temporal matching alone.

        Strategy:
        1. TIER 1 (PREFERRED): Use encounter_id to query v2_document_reference_enriched
        2. TIER 2 (FALLBACK): Query procedure table for encounter_reference if encounter_id not provided
        3. TIER 3 (LEGACY): Fall back to temporal matching if encounter linkage fails

        Args:
            procedure_fhir_id: FHIR ID of the procedure (e.g., "Procedure/abc123")
            encounter_id: Encounter ID from v2_annotation (e.g., "Encounter/xyz789")
            surgery_date: Date of surgery (YYYY-MM-DD) - used for Tier 3 fallback

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
                FROM fhir_prd_db.v2_document_reference_enriched
                WHERE encounter_id = '{encounter_id}'
                  AND (
                      LOWER(doc_type_text) LIKE '%operative%'
                      OR LOWER(doc_type_text) LIKE '%procedure%'
                      OR LOWER(doc_type_text) LIKE '%surgical%'
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

        # All tiers failed
        logger.warning(f"V2: No operative note found (all tiers exhausted)")
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
            # Query v_radiation_documents for documents near radiation start
            query = f"""
            SELECT document_id, doc_type_text, doc_date, doc_description
            FROM fhir_prd_db.v_radiation_documents
            WHERE patient_fhir_id = '{self.athena_patient_id}'
              AND ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 30
            ORDER BY ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE)))
            LIMIT 1
            """

            results = query_athena(query, f"Finding radiation document for {radiation_date}", suppress_output=True)

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

        if not self.medgemma_agent or not self.binary_agent:
            print("  ⚠️  Ollama/MedGemma not available - skipping binary extraction")
            return

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
        """Generate prompt for comprehensive radiation details extraction"""

        who_dx = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')
        expected_radiation = self.who_2021_classification.get('recommended_protocols', {}).get('radiation', 'Unknown')

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

CRITICAL VALIDATION:
- total_dose_cgy is REQUIRED (cannot be null)
- date_at_radiation_start is REQUIRED (cannot be null)
- If you cannot find these fields, set extraction_confidence to "LOW" and provide your best estimate
- Use null only for truly absent information, not for information you're uncertain about
"""

        return prompt

    def _generate_chemotherapy_prompt(self, gap: Dict) -> str:
        """Generate chemotherapy extraction prompt"""

        prompt = f"""Extract chemotherapy protocol and treatment information from this clinical document.

OUTPUT FORMAT - RETURN ONLY THIS JSON:
{{
  "protocol_name": "e.g., COG ACNS0126, SJMB12, or null",
  "on_protocol_status": "enrolled, treated_as_per_protocol, treated_like_protocol, or off_protocol",
  "agent_names": ["Drug1", "Drug2"] or [],
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "change_in_therapy_reason": "progression, toxicity, patient_preference, or null",
  "extraction_confidence": "HIGH, MEDIUM, or LOW"
}}

INSTRUCTIONS:
- protocol_name: Look for "per protocol", "COG", "ACNS", "SJMB", study numbers
- on_protocol_status: Distinguish enrolled vs. treated "as per" or "like" protocol
- agent_names: List ALL chemotherapy drugs mentioned
- change_in_therapy_reason: Extract if therapy was modified and why
- Set confidence LOW if information is incomplete
"""
        return prompt

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

                results = query_athena(query, f"Finding Binary for {resource_type}/{resource_id}", suppress_output=True)

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

                results = query_athena(query, f"Finding content_type for {binary_id}", suppress_output=True)

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
                return None

            return extracted_text

        except Exception as e:
            logger.error(f"Error fetching binary {binary_id}: {e}")
            return None

    def _get_patient_chemotherapy_keywords(self) -> List[str]:
        """
        Generate patient-specific chemotherapy keywords based on schema-extracted drug names

        Returns:
            List of chemotherapy keywords including patient's actual drug names
        """
        keywords = [
            # Protocol terms
            'protocol', 'trial', 'study', 'enrolled', 'enrollment', 'consent', 'cog', 'acns', 'sjmb', 'pog',
            # Chemotherapy terms
            'chemotherapy', 'chemo', 'agent', 'drug', 'cycle', 'course', 'regimen', 'infusion',
            # Change indicators
            'changed', 'modified', 'discontinued', 'stopped', 'held', 'dose reduction', 'escalation', 'toxicity', 'progression'
        ]

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
                    logger.info(f"Merged radiation details for {event_date}: {event.get('total_dose_cgy')} cGy")
                    event_merged = True
                    break
                elif gap_type == 'missing_chemotherapy_details' and 'chemotherapy' in event.get('event_type', ''):
                    # Merge chemotherapy-specific fields
                    event['chemotherapy_agents'] = extraction_data.get('chemotherapy_agents')
                    event['chemotherapy_protocol'] = extraction_data.get('chemotherapy_protocol')
                    event['chemotherapy_intent'] = extraction_data.get('chemotherapy_intent')
                    event['medgemma_extraction'] = extraction_data
                    logger.info(f"Merged chemotherapy details for {event_date}: {event.get('chemotherapy_agents')}")
                    event_merged = True
                    break

        if not event_merged:
            logger.warning(f"⚠️  No matching event found for gap_type={gap_type}, event_date={event_date}")

    def _phase4_5_assess_extraction_completeness(self):
        """
        Orchestrator assessment of extraction completeness
        Validates that critical fields were successfully populated
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

        # Report assessment
        print("  DATA COMPLETENESS ASSESSMENT:")
        print()

        for category, stats in assessment.items():
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

        # Store assessment for artifact
        self.completeness_assessment = assessment

    def _phase5_protocol_validation(self):
        """
        V3 Phase 5: Validate care against WHO 2021 evidence-based protocols

        Uses MedGemma to analyze actual patient care against WHO CNS5 treatment standards
        """
        print("\n" + "="*80)
        print("PHASE 5: WHO 2021 PROTOCOL VALIDATION")
        print("="*80)

        # Check if MedGemma is available
        if not self.medgemma_agent:
            logger.warning("⚠️  MedGemma not available - skipping protocol validation")
            self.protocol_validations.append({
                'status': 'SKIPPED',
                'reason': 'MedGemma agent not initialized'
            })
            return

        # Get WHO diagnosis
        diagnosis = self.who_2021_classification.get('who_2021_diagnosis', 'Unknown')

        if diagnosis in ['Unknown', 'Insufficient data', 'Classification failed']:
            logger.warning(f"⚠️  Cannot validate protocol - WHO classification: {diagnosis}")
            self.protocol_validations.append({
                'status': 'SKIPPED',
                'reason': f'No valid WHO classification (status: {diagnosis})'
            })
            return

        logger.info(f"Validating care for: {diagnosis}")

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

        except Exception as e:
            logger.error(f"Error during protocol validation: {e}")
            self.protocol_validations.append({
                'status': 'ERROR',
                'reason': str(e)
            })

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

    args = parser.parse_args()

    # Check AWS SSO
    if not check_aws_sso_token():
        print("\n❌ AWS SSO token invalid. Run: aws sso login --profile radiant-prod\n")
        sys.exit(1)

    # Create output directory
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
    artifact = abstractor.run()

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
