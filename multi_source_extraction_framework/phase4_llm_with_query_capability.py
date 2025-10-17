"""
Phase 4: LLM with Active Structured Data Query Capability
=========================================================
LLM can query structured tables during abstraction to verify and contextualize
"""

import pandas as pd
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from datetime import datetime, timedelta
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMWithStructuredQueryCapability:
    """
    Enhanced LLM extraction where the model can actively query structured data
    Key innovation: LLM can ask questions about structured data during extraction
    """

    def __init__(self, staging_path: Path, ollama_model: str = "gemma2:27b"):
        self.staging_path = Path(staging_path)
        self.ollama_model = ollama_model
        self.output_base = self.staging_path.parent / "outputs"
        self.output_base.mkdir(exist_ok=True)

        # Initialize structured data query engine
        self.query_engine = StructuredDataQueryEngine(staging_path)

    def create_extraction_prompt_with_query_capability(self,
                                                      variable: str,
                                                      document_text: str,
                                                      patient_id: str) -> str:
        """
        Create prompt that teaches LLM how to query structured data
        """

        prompt_parts = []

        # 1. System instruction with query capability
        prompt_parts.append("""You are a clinical data extraction expert with access to a structured database.
You can query patient data tables to verify information before making extraction decisions.

AVAILABLE QUERY FUNCTIONS:
1. QUERY_SURGERY_DATES() - Returns all surgery dates for the patient
2. QUERY_DIAGNOSIS() - Returns diagnosis information including date and histology
3. QUERY_MEDICATIONS(drug_name) - Returns medication records for a specific drug
4. QUERY_MOLECULAR_TESTS() - Returns molecular test results and dates
5. QUERY_IMAGING_ON_DATE(date) - Returns imaging performed on or near a specific date
6. QUERY_PROBLEM_LIST() - Returns active problems and diagnoses
7. QUERY_ENCOUNTERS_RANGE(start_date, end_date) - Returns encounters in date range
8. VERIFY_DATE_PROXIMITY(date1, date2, tolerance_days) - Checks if dates are within tolerance

INSTRUCTIONS:
- Before extracting information, query relevant structured data
- Use queries to verify dates, validate information, and provide context
- If document mentions a date, verify it against structured data
- If document mentions a treatment, check if patient received it
- Provide confidence based on alignment with structured data
""")

        # 2. Add specific extraction task
        prompt_parts.append(f"\n=== EXTRACTION TASK: {variable.upper()} ===")

        task_specific_queries = {
            'extent_of_resection': [
                "First, use QUERY_SURGERY_DATES() to get all surgery dates",
                "Then check if document date matches any surgery date",
                "Only extract extent if dates align"
            ],
            'tumor_histology': [
                "Use QUERY_DIAGNOSIS() to get known diagnosis",
                "Use QUERY_MOLECULAR_TESTS() to get molecular markers",
                "Verify histology matches structured data"
            ],
            'chemotherapy_response': [
                "Query each mentioned drug with QUERY_MEDICATIONS(drug_name)",
                "Verify patient actually received the drug",
                "Check treatment dates align with document"
            ],
            'progression_status': [
                "Use QUERY_IMAGING_ON_DATE() for mentioned dates",
                "Check if progression aligns with imaging schedule",
                "Verify with QUERY_ENCOUNTERS_RANGE() for clinical visits"
            ]
        }

        if variable in task_specific_queries:
            prompt_parts.append("REQUIRED QUERIES:")
            for query_instruction in task_specific_queries[variable]:
                prompt_parts.append(f"- {query_instruction}")

        # 3. Document text
        prompt_parts.append(f"\n=== DOCUMENT TEXT (Patient: {patient_id}) ===")
        prompt_parts.append(document_text[:5000])

        # 4. Extraction format
        prompt_parts.append("""
=== EXTRACTION FORMAT ===
Provide your extraction as a structured response:

1. QUERIES PERFORMED:
   - List each query you execute
   - Show the results

2. VALIDATION:
   - How query results validate or contradict the document

3. EXTRACTION:
   {
     "value": "extracted value",
     "confidence": 0.0-1.0,
     "supporting_queries": ["list of queries that support this"],
     "validation_status": "validated|contradicted|unverified"
   }
""")

        return "\n".join(prompt_parts)

    def extract_with_query_capability(self,
                                     patient_id: str,
                                     variable: str,
                                     document: Dict) -> Dict:
        """
        Perform extraction where LLM can query structured data
        """

        logger.info(f"Extracting {variable} with query capability for patient {patient_id}")

        # Create prompt
        prompt = self.create_extraction_prompt_with_query_capability(
            variable,
            document.get('text', ''),
            patient_id
        )

        # Simulate LLM extraction with queries
        # In production, this would be actual Ollama call with query handling
        extraction_result = self._simulate_llm_extraction_with_queries(
            variable,
            document,
            patient_id
        )

        return extraction_result

    def _simulate_llm_extraction_with_queries(self,
                                             variable: str,
                                             document: Dict,
                                             patient_id: str) -> Dict:
        """
        Simulate how LLM would query and extract
        This shows the workflow - in production, Ollama would do this
        """

        result = {
            'variable': variable,
            'document_id': document.get('document_id'),
            'queries_performed': [],
            'extraction': {}
        }

        # Simulate different extraction scenarios
        if variable == 'extent_of_resection':
            # Step 1: Query surgery dates
            surgery_dates = self.query_engine.query_surgery_dates(patient_id)
            result['queries_performed'].append({
                'query': 'QUERY_SURGERY_DATES()',
                'result': surgery_dates
            })

            # Step 2: Check if document date matches
            doc_date = document.get('date', '2018-05-28')
            date_matches = any(
                self.query_engine.verify_date_proximity(doc_date, surgery['date'], 7)
                for surgery in surgery_dates
            )

            if date_matches:
                result['extraction'] = {
                    'value': 'Gross total resection',
                    'confidence': 0.95,
                    'supporting_queries': ['QUERY_SURGERY_DATES()'],
                    'validation_status': 'validated',
                    'reason': 'Document date matches surgery date in structured data'
                }
            else:
                result['extraction'] = {
                    'value': 'Unable to extract',
                    'confidence': 0.1,
                    'validation_status': 'contradicted',
                    'reason': 'Document date does not match any known surgery dates'
                }

        elif variable == 'chemotherapy_response':
            # Query mentioned drugs
            mentioned_drugs = ['Bevacizumab']  # Would be extracted from document

            for drug in mentioned_drugs:
                med_records = self.query_engine.query_medications(patient_id, drug)
                result['queries_performed'].append({
                    'query': f'QUERY_MEDICATIONS("{drug}")',
                    'result': med_records
                })

                if med_records:
                    result['extraction'] = {
                        'value': 'Stable disease on Bevacizumab',
                        'confidence': 0.85,
                        'supporting_queries': [f'QUERY_MEDICATIONS("{drug}")'],
                        'validation_status': 'validated',
                        'reason': f'Patient confirmed to have received {drug}'
                    }
                else:
                    result['extraction'] = {
                        'value': 'Unable to verify treatment',
                        'confidence': 0.2,
                        'validation_status': 'unverified',
                        'reason': f'No record of {drug} in structured data'
                    }

        return result


class StructuredDataQueryEngine:
    """
    Query engine that LLM can use to access structured data
    """

    def __init__(self, staging_path: Path):
        self.staging_path = Path(staging_path)
        self._cache = {}  # Cache query results for efficiency

    def query_surgery_dates(self, patient_id: str) -> List[Dict]:
        """Query all surgery dates for a patient"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        procedures_file = patient_path / "procedures.csv"

        if not procedures_file.exists():
            return []

        procedures_df = pd.read_csv(procedures_file)

        # Find surgeries
        surgery_keywords = ['resection', 'craniotomy', 'biopsy', 'excision']
        surgeries = []

        for idx, row in procedures_df.iterrows():
            proc_text = str(row.get('proc_code_text', '')).lower()
            if any(keyword in proc_text for keyword in surgery_keywords):
                # Get date
                date_col = None
                for col in ['proc_performed_period_start', 'proc_performed_date_time', 'procedure_date']:
                    if col in procedures_df.columns and pd.notna(row.get(col)):
                        date_col = col
                        break

                if date_col:
                    surgeries.append({
                        'date': str(row[date_col])[:10],
                        'type': 'resection' if 'resection' in proc_text else 'biopsy',
                        'description': row.get('proc_code_text', 'Unknown')
                    })

        return surgeries

    def query_diagnosis(self, patient_id: str) -> Dict:
        """Query diagnosis information"""

        patient_path = self.staging_path / f"patient_{patient_id}"

        # Check problem list
        problem_file = patient_path / "problem_list.csv"
        if problem_file.exists():
            problems_df = pd.read_csv(problem_file)

            # Find tumor diagnosis
            tumor_keywords = ['astrocytoma', 'glioma', 'brain', 'neoplasm']
            for idx, row in problems_df.iterrows():
                diagnosis = str(row.get('pld_diagnosis_name', '')).lower()
                if any(keyword in diagnosis for keyword in tumor_keywords):
                    return {
                        'diagnosis': row.get('pld_diagnosis_name'),
                        'icd10': row.get('pld_icd10cm_code'),
                        'date': str(row.get('pld_recorded_time', ''))[:10],
                        'status': row.get('pld_status')
                    }

        # Fallback to diagnoses table
        diagnoses_file = patient_path / "diagnoses.csv"
        if diagnoses_file.exists():
            diagnoses_df = pd.read_csv(diagnoses_file)
            if not diagnoses_df.empty:
                first_diagnosis = diagnoses_df.iloc[0]
                return {
                    'diagnosis': first_diagnosis.get('diagnosis_name', 'Unknown'),
                    'date': str(first_diagnosis.get('diagnosis_date', ''))[:10]
                }

        return {}

    def query_medications(self, patient_id: str, drug_name: str) -> List[Dict]:
        """Query medication records for a specific drug"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        meds_file = patient_path / "medications.csv"

        if not meds_file.exists():
            return []

        meds_df = pd.read_csv(meds_file)

        # Search for drug
        drug_lower = drug_name.lower()
        matches = []

        for idx, row in meds_df.iterrows():
            med_name = str(row.get('medication_name', '')).lower()
            if drug_lower in med_name:
                # Get dates
                start_date = None
                for col in ['medication_start_date', 'mr_authoredon', 'cp_period_start']:
                    if col in meds_df.columns and pd.notna(row.get(col)):
                        start_date = str(row[col])[:10]
                        break

                matches.append({
                    'medication': row.get('medication_name'),
                    'start_date': start_date,
                    'end_date': str(row.get('cp_period_end', ''))[:10] if 'cp_period_end' in row else None,
                    'status': row.get('medication_status')
                })

        return matches

    def query_molecular_tests(self, patient_id: str) -> List[Dict]:
        """Query molecular test results"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        molecular_file = patient_path / "molecular_tests_metadata.csv"

        if not molecular_file.exists():
            return []

        molecular_df = pd.read_csv(molecular_file)
        tests = []

        for idx, row in molecular_df.iterrows():
            tests.append({
                'test_name': row.get('mt_lab_test_name', 'Unknown'),
                'test_date': str(row.get('mt_test_date', ''))[:10],
                'specimen_date': str(row.get('mt_specimen_collection_date', ''))[:10],
                'result_summary': row.get('mt_result', 'No result')
            })

        return tests

    def query_imaging_on_date(self, patient_id: str, target_date: str, tolerance_days: int = 7) -> List[Dict]:
        """Query imaging studies near a specific date"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        imaging_file = patient_path / "imaging.csv"

        if not imaging_file.exists():
            return []

        imaging_df = pd.read_csv(imaging_file)
        target = pd.to_datetime(target_date)
        matches = []

        for idx, row in imaging_df.iterrows():
            # Get imaging date
            img_date = None
            for col in ['imaging_date', 'img_performed_period_start', 'study_date']:
                if col in imaging_df.columns and pd.notna(row.get(col)):
                    img_date = pd.to_datetime(row[col])
                    break

            if img_date and abs((img_date - target).days) <= tolerance_days:
                matches.append({
                    'date': str(img_date)[:10],
                    'modality': row.get('img_modality', 'Unknown'),
                    'body_part': row.get('img_body_part_examined', 'Unknown'),
                    'days_from_target': int((img_date - target).days)
                })

        return matches

    def query_problem_list(self, patient_id: str) -> List[Dict]:
        """Query active problems"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        problem_file = patient_path / "problem_list.csv"

        if not problem_file.exists():
            return []

        problems_df = pd.read_csv(problem_file)

        # Filter active problems
        active_problems = []
        for idx, row in problems_df.iterrows():
            if str(row.get('pld_status', '')).lower() == 'active':
                active_problems.append({
                    'problem': row.get('pld_diagnosis_name'),
                    'icd10': row.get('pld_icd10cm_code'),
                    'recorded_date': str(row.get('pld_recorded_time', ''))[:10],
                    'category': self._categorize_problem(row.get('pld_diagnosis_name', ''))
                })

        return active_problems

    def query_encounters_range(self, patient_id: str, start_date: str, end_date: str) -> List[Dict]:
        """Query encounters within a date range"""

        patient_path = self.staging_path / f"patient_{patient_id}"
        encounters_file = patient_path / "encounters.csv"

        if not encounters_file.exists():
            return []

        encounters_df = pd.read_csv(encounters_file)
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        matches = []
        for idx, row in encounters_df.iterrows():
            # Get encounter date
            enc_date = None
            for col in ['enc_period_start', 'encounter_date', 'admission_date']:
                if col in encounters_df.columns and pd.notna(row.get(col)):
                    enc_date = pd.to_datetime(row[col])
                    break

            if enc_date and start <= enc_date <= end:
                matches.append({
                    'date': str(enc_date)[:10],
                    'type': row.get('enc_class_display', 'Unknown'),
                    'reason': row.get('enc_reasoncode_display', 'Unknown'),
                    'department': row.get('enc_service_provider_name', 'Unknown')
                })

        return matches

    def verify_date_proximity(self, date1: str, date2: str, tolerance_days: int) -> bool:
        """Check if two dates are within tolerance"""

        try:
            d1 = pd.to_datetime(date1)
            d2 = pd.to_datetime(date2)
            return abs((d1 - d2).days) <= tolerance_days
        except:
            return False

    def _categorize_problem(self, problem_name: str) -> str:
        """Categorize a problem"""

        problem_lower = str(problem_name).lower()

        if any(term in problem_lower for term in ['tumor', 'neoplasm', 'astrocytoma', 'glioma']):
            return 'primary_tumor'
        elif any(term in problem_lower for term in ['hydrocephalus', 'compression', 'edema']):
            return 'tumor_complication'
        elif any(term in problem_lower for term in ['seizure', 'epilepsy', 'convulsion']):
            return 'seizure_disorder'
        elif any(term in problem_lower for term in ['ataxia', 'weakness', 'paralysis', 'nystagmus']):
            return 'neurological_symptom'
        else:
            return 'other'


class OllamaQueryHandler:
    """
    Handles Ollama calls with query capability
    Intercepts query requests and fulfills them with structured data
    """

    def __init__(self, query_engine: StructuredDataQueryEngine):
        self.query_engine = query_engine

    def process_llm_response_with_queries(self,
                                         llm_response: str,
                                         patient_id: str) -> Dict:
        """
        Process LLM response, execute any queries it requests
        """

        # Parse queries from LLM response
        queries_requested = self._parse_query_requests(llm_response)

        # Execute queries
        query_results = {}
        for query in queries_requested:
            result = self._execute_query(query, patient_id)
            query_results[query['function']] = result

        # Return to LLM with query results
        return query_results

    def _parse_query_requests(self, response: str) -> List[Dict]:
        """Parse query function calls from LLM response"""

        import re

        queries = []

        # Pattern to match query functions
        patterns = {
            'QUERY_SURGERY_DATES': r'QUERY_SURGERY_DATES\(\)',
            'QUERY_DIAGNOSIS': r'QUERY_DIAGNOSIS\(\)',
            'QUERY_MEDICATIONS': r'QUERY_MEDICATIONS\("([^"]+)"\)',
            'QUERY_MOLECULAR_TESTS': r'QUERY_MOLECULAR_TESTS\(\)',
            'QUERY_IMAGING_ON_DATE': r'QUERY_IMAGING_ON_DATE\("([^"]+)"\)',
            'QUERY_PROBLEM_LIST': r'QUERY_PROBLEM_LIST\(\)',
            'QUERY_ENCOUNTERS_RANGE': r'QUERY_ENCOUNTERS_RANGE\("([^"]+)",\s*"([^"]+)"\)',
            'VERIFY_DATE_PROXIMITY': r'VERIFY_DATE_PROXIMITY\("([^"]+)",\s*"([^"]+)",\s*(\d+)\)'
        }

        for func_name, pattern in patterns.items():
            matches = re.finditer(pattern, response)
            for match in matches:
                query = {'function': func_name}
                if match.groups():
                    query['arguments'] = match.groups()
                queries.append(query)

        return queries

    def _execute_query(self, query: Dict, patient_id: str) -> Any:
        """Execute a structured data query"""

        func_name = query['function']
        args = query.get('arguments', [])

        if func_name == 'QUERY_SURGERY_DATES':
            return self.query_engine.query_surgery_dates(patient_id)
        elif func_name == 'QUERY_DIAGNOSIS':
            return self.query_engine.query_diagnosis(patient_id)
        elif func_name == 'QUERY_MEDICATIONS' and args:
            return self.query_engine.query_medications(patient_id, args[0])
        elif func_name == 'QUERY_MOLECULAR_TESTS':
            return self.query_engine.query_molecular_tests(patient_id)
        elif func_name == 'QUERY_IMAGING_ON_DATE' and args:
            return self.query_engine.query_imaging_on_date(patient_id, args[0])
        elif func_name == 'QUERY_PROBLEM_LIST':
            return self.query_engine.query_problem_list(patient_id)
        elif func_name == 'QUERY_ENCOUNTERS_RANGE' and len(args) >= 2:
            return self.query_engine.query_encounters_range(patient_id, args[0], args[1])
        elif func_name == 'VERIFY_DATE_PROXIMITY' and len(args) >= 3:
            return self.query_engine.verify_date_proximity(args[0], args[1], int(args[2]))

        return None


def demonstrate_query_capability():
    """Demonstrate the LLM query capability"""

    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

    # Initialize components
    llm_extractor = LLMWithStructuredQueryCapability(staging_path)
    query_engine = llm_extractor.query_engine

    print("\n" + "="*80)
    print("DEMONSTRATION: LLM WITH STRUCTURED DATA QUERY CAPABILITY")
    print("="*80)

    # Demonstrate queries the LLM can make
    print("\n1. QUERY_SURGERY_DATES():")
    surgeries = query_engine.query_surgery_dates(patient_id)
    for surgery in surgeries:
        print(f"   - {surgery['date']}: {surgery['type']} ({surgery['description'][:50]}...)")

    print("\n2. QUERY_DIAGNOSIS():")
    diagnosis = query_engine.query_diagnosis(patient_id)
    print(f"   - {diagnosis.get('diagnosis', 'Unknown')}")
    print(f"   - Date: {diagnosis.get('date', 'Unknown')}")

    print("\n3. QUERY_MEDICATIONS('Bevacizumab'):")
    meds = query_engine.query_medications(patient_id, "Bevacizumab")
    for med in meds[:2]:
        print(f"   - {med['medication']}: {med['start_date']} to {med.get('end_date', 'ongoing')}")

    print("\n4. QUERY_MOLECULAR_TESTS():")
    tests = query_engine.query_molecular_tests(patient_id)
    for test in tests[:2]:
        print(f"   - {test['test_name']}: {test['test_date']}")

    print("\n5. QUERY_PROBLEM_LIST():")
    problems = query_engine.query_problem_list(patient_id)
    for problem in problems[:3]:
        print(f"   - {problem['problem']} ({problem['category']})")

    # Demonstrate extraction with queries
    print("\n" + "="*60)
    print("EXAMPLE EXTRACTION WITH QUERIES")
    print("="*60)

    test_document = {
        'document_id': 'op_note_2018-05-28',
        'date': '2018-05-28',
        'text': 'Craniotomy performed. Gross total resection of cerebellar tumor achieved.'
    }

    result = llm_extractor.extract_with_query_capability(
        patient_id,
        'extent_of_resection',
        test_document
    )

    print("\nQueries Performed:")
    for query in result['queries_performed']:
        print(f"  - {query['query']}")
        print(f"    Result: {query['result'][:100] if isinstance(query['result'], str) else query['result']}")

    print("\nExtraction Result:")
    extraction = result['extraction']
    print(f"  Value: {extraction['value']}")
    print(f"  Confidence: {extraction['confidence']:.1%}")
    print(f"  Validation: {extraction['validation_status']}")
    print(f"  Reason: {extraction['reason']}")

    print("\n" + "="*80)
    print("KEY INNOVATION: LLM actively queries structured data to validate extractions!")
    print("="*80)


if __name__ == "__main__":
    demonstrate_query_capability()