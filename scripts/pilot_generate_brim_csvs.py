#!/usr/bin/env python3
"""
Generate BRIM-compatible CSVs from FHIR Bundle and Clinical Notes

This script:
1. Loads the extracted FHIR Bundle
2. Extracts clinical notes from S3 NDJSON files (DocumentReference + Binary)
3. Generates 3 BRIM CSVs:
   - project.csv: FHIR Bundle + Clinical Notes
   - variables.csv: Extraction rules for LLM
   - decisions.csv: Aggregation and cross-validation rules

Usage:
    python scripts/pilot_generate_brim_csvs.py --bundle-path pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json
"""

import os
import json
import csv
import boto3
import base64
import argparse
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment
load_dotenv()


class BRIMCSVGenerator:
    """Generate BRIM-compatible CSVs from FHIR Bundle and Clinical Notes."""
    
    def __init__(self, bundle_path, output_dir='./pilot_output/brim_csvs'):
        self.bundle_path = bundle_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # AWS Configuration
        self.aws_profile = os.getenv('AWS_PROFILE')
        self.s3_bucket = os.getenv('S3_NDJSON_BUCKET')
        self.s3_prefix = os.getenv('S3_NDJSON_PREFIX')
        self.patient_id = os.getenv('PILOT_PATIENT_ID')  # FHIR ID for queries
        self.subject_id = os.getenv('PILOT_SUBJECT_ID')  # Subject ID for BRIM (pseudonymized MRN)
        
        # Initialize AWS clients
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        
        # Load FHIR Bundle
        print(f"📂 Loading FHIR Bundle from {bundle_path}")
        with open(bundle_path, 'r') as f:
            self.bundle = json.load(f)
        print(f"✅ Loaded bundle with {len(self.bundle.get('entry', []))} resources")
        
        # Storage for clinical notes
        self.clinical_notes = []
    
    def extract_clinical_notes(self):
        """Extract clinical notes from S3 using S3 Select on NDJSON files."""
        print(f"\n📥 Extracting clinical notes from S3...")
        
        # Query DocumentReference NDJSON files using S3 Select
        doc_ref_prefix = f"{self.s3_prefix}DocumentReference/"
        
        try:
            # List ALL NDJSON files in DocumentReference folder using pagination
            print(f"🔍 Listing all DocumentReference NDJSON files...")
            paginator = self.s3_client.get_paginator('list_objects_v2')
            files = []
            
            for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=doc_ref_prefix):
                if 'Contents' in page:
                    page_files = [obj['Key'] for obj in page['Contents'] if obj['Key'].endswith('.ndjson')]
                    files.extend(page_files)
            
            if not files:
                print(f"⚠️  No DocumentReference files found at {doc_ref_prefix}")
                return []
            
            print(f"✅ Found {len(files)} DocumentReference NDJSON files")
            
            # Query each file for patient's documents
            document_refs = []
            print(f"   Querying all {len(files)} files for patient documents...")
            for i, file_key in enumerate(files, 1):
                if i % 100 == 0 or i == 1:  # Progress update every 100 files
                    print(f"   Progress: {i}/{len(files)} files queried...")
                docs = self._query_s3_select(file_key)
                document_refs.extend(docs)
                if len(document_refs) > 0 and i % 100 == 0:
                    print(f"   Found {len(document_refs)} DocumentReferences so far...")
            
            print(f"✅ Found {len(document_refs)} DocumentReference resources")
            
            # Extract Binary content for each DocumentReference
            print(f"\n📄 Processing {len(document_refs)} DocumentReferences to extract Binary content...")
            for i, doc_ref in enumerate(document_refs, 1):
                if i <= 5 or i % 20 == 0:  # Debug first 5 and every 20th
                    print(f"   Processing document {i}/{len(document_refs)}...")
                note = self._process_document_reference(doc_ref)
                if note:
                    self.clinical_notes.append(note)
                    if i <= 5:
                        print(f"      ✅ Successfully extracted note (ID: {note['note_id']})")
                elif i <= 5:
                    print(f"      ⚠️  Failed to extract note")
            
            print(f"✅ Extracted {len(self.clinical_notes)} clinical notes")
            
        except Exception as e:
            print(f"⚠️  Could not extract clinical notes: {e}")
        
        return self.clinical_notes
    
    def _query_s3_select(self, file_key):
        """Use S3 Select to query NDJSON file for patient documents."""
        sql = f"""
        SELECT *
        FROM S3Object[*] s
        WHERE s.subject.reference LIKE '%{self.patient_id}%'
        """
        
        try:
            response = self.s3_client.select_object_content(
                Bucket=self.s3_bucket,
                Key=file_key,
                ExpressionType='SQL',
                Expression=sql,
                InputSerialization={'JSON': {'Type': 'LINES'}},
                OutputSerialization={'JSON': {'RecordDelimiter': '\n'}}
            )
            
            # Parse streaming response
            records = []
            for event in response['Payload']:
                if 'Records' in event:
                    payload = event['Records']['Payload'].decode('utf-8')
                    for line in payload.strip().split('\n'):
                        if line:
                            records.append(json.loads(line))
            
            return records
            
        except Exception as e:
            # Silent failure for individual file queries
            return []
    
    def _process_document_reference(self, doc_ref):
        """Process DocumentReference to extract note content."""
        try:
            doc_id = doc_ref.get('id', 'unknown')
            doc_date = doc_ref.get('date', '')
            doc_type = doc_ref.get('type', {}).get('text', 'Unknown')
            
            # Get Binary reference from attachment
            content = doc_ref.get('content', [])
            if not content:
                return None
            
            attachment = content[0].get('attachment', {})
            binary_url = attachment.get('url', '')
            
            if not binary_url or 'Binary/' not in binary_url:
                return None
            
            # Extract Binary ID
            binary_id = binary_url.split('Binary/')[-1]
            
            # Fetch Binary content
            text_content = self._fetch_binary_content(binary_id)
            
            if not text_content:
                return None
            
            # Sanitize HTML if present
            text_content = self._sanitize_html(text_content)
            
            return {
                'note_id': doc_id,
                'note_date': doc_date,
                'note_type': doc_type,
                'note_text': text_content
            }
            
        except Exception as e:
            print(f"      ⚠️  Error processing DocumentReference {doc_ref.get('id', 'unknown')}: {e}")
            return None
    
    def _fetch_binary_content(self, binary_id):
        """Fetch Binary resource content directly from S3 source/Binary/ folder.
        
        Binary files are stored in prd/source/Binary/ with the Binary ID as the filename.
        """
        # Track fetch attempts for debugging
        if not hasattr(self, '_binary_fetch_count'):
            self._binary_fetch_count = 0
        self._binary_fetch_count += 1
        debug = self._binary_fetch_count <= 3  # Debug first 3 attempts
        
        try:
            if debug:
                print(f"         Fetching Binary ID: {binary_id}")
            
            # Try to fetch directly from prd/source/Binary/{binary_id}
            s3_key = f"prd/source/Binary/{binary_id}"
            
            try:
                response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
                binary_data = response['Body'].read()
                
                if debug:
                    print(f"         Downloaded {len(binary_data)} bytes from {s3_key}")
                
                # Try to decode as JSON first (FHIR Binary resource format)
                try:
                    binary_resource = json.loads(binary_data.decode('utf-8'))
                    # Extract base64 data field
                    data = binary_resource.get('data', '')
                    if data:
                        decoded = base64.b64decode(data).decode('utf-8', errors='ignore')
                        if debug:
                            print(f"         Decoded {len(decoded)} characters from base64")
                        return decoded
                except json.JSONDecodeError:
                    # If not JSON, try direct decoding (plain text or HTML)
                    try:
                        decoded = binary_data.decode('utf-8', errors='ignore')
                        if debug:
                            print(f"         Decoded {len(decoded)} characters directly")
                        return decoded
                    except:
                        return None
                
                return None
                
            except self.s3_client.exceptions.NoSuchKey:
                if debug:
                    print(f"         Binary file not found: {s3_key}")
                return None
            
        except Exception as e:
            if debug:
                print(f"         Error fetching Binary {binary_id}: {e}")
            return None
    
    def _sanitize_html(self, text):
        """Remove HTML tags and clean up text."""
        if not text:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(text, 'html.parser')
        
        # Extract text
        clean_text = soup.get_text()
        
        # Clean up whitespace
        clean_text = '\n'.join(line.strip() for line in clean_text.split('\n') if line.strip())
        
        return clean_text
    
    def generate_project_csv(self):
        """Generate project.csv with FHIR Bundle + Clinical Notes."""
        print(f"\n📝 Generating project.csv...")
        
        project_file = self.output_dir / 'project.csv'
        
        rows = []
        
        # Row 1: FHIR Bundle as JSON
        bundle_json = json.dumps(self.bundle, separators=(',', ':'))
        rows.append({
            'NOTE_ID': 'FHIR_BUNDLE',
            'PERSON_ID': self.subject_id,  # Use subject_id (1277724) not patient_id
            'NOTE_DATETIME': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'NOTE_TEXT': bundle_json,
            'NOTE_TITLE': 'FHIR_BUNDLE'
        })
        
        # Rows 2-N: Clinical Notes
        for note in self.clinical_notes:
            rows.append({
                'NOTE_ID': note['note_id'],
                'PERSON_ID': self.subject_id,  # Use subject_id (1277724) not patient_id
                'NOTE_DATETIME': note['note_date'],
                'NOTE_TEXT': note['note_text'],
                'NOTE_TITLE': note['note_type']
            })
        
        # Write CSV with proper escaping
        with open(project_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE'], 
                                    quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✅ Generated {project_file} with {len(rows)} rows")
        return project_file
    
    def generate_variables_csv(self):
        """Generate variables.csv with extraction rules."""
        print(f"\n📋 Generating variables.csv...")
        
        variables_file = self.output_dir / 'variables.csv'
        
        # Helper function to ensure proper defaults per BRIM spec
        def fill_defaults(var):
            """Fill empty fields with appropriate defaults matching production format."""
            if not var.get('aggregation_instruction'):
                var['aggregation_instruction'] = ''  # Leave blank per production examples
            if not var.get('aggregation_prompt_template'):
                var['aggregation_prompt_template'] = ''  # Leave blank per production examples
            # only_use_true_value_in_aggregation should be EMPTY for non-boolean types
            if not var.get('only_use_true_value_in_aggregation'):
                var['only_use_true_value_in_aggregation'] = ''  # Empty string, not 'false'
            if not var.get('default_value_for_empty_response'):
                if var['variable_type'] == 'boolean':
                    var['default_value_for_empty_response'] = 'false'
                elif var['variable_type'] == 'integer':
                    var['default_value_for_empty_response'] = '0'
                else:
                    var['default_value_for_empty_response'] = 'unknown'
            if not var.get('option_definitions'):
                var['option_definitions'] = ''  # Empty string, not '{}'
            if not var.get('aggregation_option_definitions'):
                var['aggregation_option_definitions'] = ''  # Empty string, not '{}'
            return var
        
        # Define variables for extraction (11-COLUMN FORMAT per BRIM spec)
        variables = [
            # Document Classification (MUST BE FIRST)
            {
                'variable_name': 'document_type',
                'instruction': 'Classify this document as one of: FHIR_BUNDLE, OPERATIVE_NOTE, PATHOLOGY, RADIOLOGY, PROGRESS_NOTE, CONSULTATION, DISCHARGE_SUMMARY, OTHER. Base classification on NOTE_TITLE field and document content. FHIR_BUNDLE = JSON with resourceType fields. OPERATIVE_NOTE = surgical procedure description. PATHOLOGY = histopathology/microscopic examination. RADIOLOGY = imaging reports (MRI/CT/PET). PROGRESS_NOTE = clinical progress notes. CONSULTATION = specialist consultation. DISCHARGE_SUMMARY = hospital discharge summary. OTHER = any other document type. Return ONLY the classification value.',
                'variable_type': 'text',
                'scope': 'one_per_note',
                'option_definitions': '{"FHIR_BUNDLE": "Complete FHIR resource bundle", "OPERATIVE_NOTE": "Surgical operative note", "PATHOLOGY": "Pathology report", "RADIOLOGY": "Radiology report", "PROGRESS_NOTE": "Progress note", "CONSULTATION": "Consultation note", "DISCHARGE_SUMMARY": "Discharge summary", "OTHER": "Other document type"}',
                'default_value_for_empty_response': 'OTHER'
            },
            
            # Demographics (from FHIR Bundle)
            {
                'variable_name': 'patient_gender',
                'instruction': 'If document_type is FHIR_BUNDLE: Search for the Patient resource (resourceType: "Patient") and extract the gender field. Return one of: male, female, other, or unknown. If not a FHIR_BUNDLE, look for gender/sex mentioned in clinical text. Be case-insensitive. If gender not found or ambiguous, return "unknown".',
                'variable_type': 'text',
                'scope': 'one_per_patient',
                'option_definitions': '{"male": "Male", "female": "Female", "other": "Other or non-binary", "unknown": "Unknown or not specified"}',
            },
            
            {
                'variable_name': 'date_of_birth',
                'instruction': 'If document_type is FHIR_BUNDLE: Find the Patient resource and extract the birthDate field in YYYY-MM-DD format. If not a FHIR_BUNDLE, look for "Date of Birth", "DOB", or birth date mentioned in clinical text. Always return in YYYY-MM-DD format. If not found, return "Not documented".',
                'variable_type': 'text',
                'scope': 'one_per_patient',
            },
            
            # Diagnosis (from FHIR + Narrative)
            {
                'variable_name': 'primary_diagnosis',
                'instruction': 'Extract the primary brain tumor diagnosis. If document_type is FHIR_BUNDLE: Check Condition resources for oncology diagnoses (code.coding.display fields). If narrative document: Look for diagnostic terms like glioblastoma, astrocytoma, medulloblastoma, ependymoma, oligodendroglioma, meningioma, etc. Include WHO grade if mentioned (e.g., "Grade II astrocytoma"). Prioritize pathology-confirmed diagnoses over clinical impressions. Return the most specific diagnosis found. If multiple tumors, return primary/dominant tumor.',
                'variable_type': 'text',
                'scope': 'one_per_patient',
            },
            
            {
                'variable_name': 'diagnosis_date',
                'instruction': 'Find the date when the primary brain tumor was first diagnosed. If document_type is FHIR_BUNDLE: Check Condition.recordedDate or Condition.onsetDateTime. If narrative: Look for phrases like "diagnosed on", "diagnosis date", "initial diagnosis", or dates near diagnostic statements. Return in YYYY-MM-DD format. If only month/year available, use first day of month (YYYY-MM-01). If not found, return "Not documented".',
                'variable_type': 'text',
                'scope': 'one_per_patient',
            },
            
            {
                'variable_name': 'who_grade',
                'instruction': 'Extract WHO tumor grade (I, II, III, or IV). Check pathology reports for phrases like "WHO Grade", "Grade I", "Grade II", "Grade III", "Grade IV", or Roman numerals I-IV in diagnosis context. Prioritize pathology over clinical impressions. Return one of: I, II, III, IV, or "unknown" if not specified. Do not return Arabic numerals (1-4), use Roman numerals only.',
                'variable_type': 'text',
                'scope': 'one_per_patient',
                'option_definitions': '{"I": "WHO Grade I", "II": "WHO Grade II", "III": "WHO Grade III", "IV": "WHO Grade IV", "unknown": "Grade not specified"}',
            },
            
            # Surgical Details
            {
                'variable_name': 'surgery_date',
                'instruction': 'Extract all brain surgery dates from this document. If document_type is FHIR_BUNDLE: Find Procedure resources where code indicates neurosurgery and extract performedDateTime. If OPERATIVE_NOTE: Extract date from note header or "Date of Surgery" field. If PATHOLOGY/RADIOLOGY: Extract procedure date if surgical procedure mentioned. Return each date in YYYY-MM-DD format. If multiple surgeries in one document, return all dates. Scope is many_per_note so return each surgery date separately.',
                'variable_type': 'text',
                'scope': 'many_per_note',
            },
            
            {
                'variable_name': 'surgery_type',
                'instruction': 'Classify the type of neurosurgical procedure. Options: BIOPSY (tissue sampling only), SUBTOTAL_RESECTION (partial tumor removal), GROSS_TOTAL_RESECTION (complete visible tumor removal), PARTIAL_RESECTION (incomplete removal), DEBULKING (cytoreductive surgery), VP_SHUNT (ventriculoperitoneal shunt placement), OTHER (other procedures). If FHIR_BUNDLE: Check Procedure.code.coding.display. If OPERATIVE_NOTE: Analyze procedure description and extent of resection statements. Return one classification per surgery.',
                'variable_type': 'text',
                'scope': 'many_per_note',
                'option_definitions': '{"BIOPSY": "Biopsy procedure", "SUBTOTAL_RESECTION": "Subtotal resection", "GROSS_TOTAL_RESECTION": "Gross total resection", "PARTIAL_RESECTION": "Partial resection", "DEBULKING": "Debulking procedure", "VP_SHUNT": "Ventriculoperitoneal shunt", "OTHER": "Other surgical procedure"}',
            },
            
            {
                'variable_name': 'extent_of_resection',
                'instruction': 'For tumor resection surgeries (not biopsies or shunts), extract the extent of tumor removal. Look for explicit statements like "gross total resection" (GTR), "near-total resection", "subtotal resection" (STR), "partial resection", or percentages like "95% resection", "80% removed". Check surgeon\'s impression section and postoperative imaging descriptions. Return the specific extent described. If only surgery type without extent specified, return "not specified". Scope is many_per_note for multiple surgeries.',
                'variable_type': 'text',
                'scope': 'many_per_note',
            },
            
            # Treatments
            {
                'variable_name': 'chemotherapy_agent',
                'instruction': 'Extract names of chemotherapy drugs administered or prescribed. If FHIR_BUNDLE: Look in MedicationRequest, MedicationAdministration, or MedicationStatement resources for oncology drugs. If narrative: Identify drug names like temozolomide (TMZ), vincristine, carboplatin, cisplatin, lomustine (CCNU), bevacizumab (Avastin), cyclophosphamide, etoposide, etc. Return each drug name separately. Include both generic and brand names if mentioned. Scope is many_per_note so list all agents found in the document.',
                'variable_type': 'text',
                'scope': 'many_per_note',
            },
            
            {
                'variable_name': 'radiation_therapy',
                'instruction': 'Determine if patient received radiation therapy. Look for: "radiation therapy", "radiotherapy", "RT", "XRT", "external beam radiation", "IMRT" (intensity-modulated), "proton therapy", "stereotactic radiosurgery", "gamma knife", "CyberKnife", or mentions of radiation oncology consultations. Return "yes" if any radiation treatment mentioned, "no" if explicitly stated patient did not receive radiation, "unknown" if not addressed. This is one_per_patient scope - determine overall radiation status across all documents.',
                'variable_type': 'boolean',
                'scope': 'one_per_patient',
            },
            
            # Molecular/Genetic
            {
                'variable_name': 'idh_mutation',
                'instruction': 'Extract IDH (isocitrate dehydrogenase) mutation status. Look for IDH1 or IDH2 testing results. Return "positive" if mutation detected, "negative" or "wildtype" if no mutation found, "unknown" if not tested or results not reported. Check molecular pathology sections, genetic testing results, or comprehensive genomic profiling reports. Common phrases: "IDH1 R132H mutation", "IDH-mutant", "IDH-wildtype", "IDH negative".',
                'variable_type': 'text',
                'scope': 'one_per_patient',
                'option_definitions': '{"positive": "IDH mutation positive", "negative": "IDH mutation negative", "wildtype": "IDH wildtype", "unknown": "Unknown or not tested"}',
            },
            
            {
                'variable_name': 'mgmt_methylation',
                'instruction': 'Extract MGMT promoter methylation status. MGMT methylation is a prognostic biomarker in glioblastoma. Return "methylated" if promoter methylation detected, "unmethylated" if not detected, "unknown" if not tested. Look in molecular pathology reports, genetic testing results, or biomarker analysis sections. Common phrases: "MGMT promoter methylated", "MGMT methylation positive", "unmethylated MGMT", "MGMT methylation status: positive/negative".',
                'variable_type': 'text',
                'scope': 'one_per_patient',
                'option_definitions': '{"methylated": "MGMT methylated", "unmethylated": "MGMT unmethylated", "unknown": "Unknown or not tested"}',
            }
        ]
        
        # Apply defaults to all variables
        variables = [fill_defaults(v) for v in variables]
        
        # Write CSV with FULL 11-COLUMN FORMAT (matching production config)
        # This is the format used in production DIAGNOSIS_variables_GENERALIZABLE.csv
        with open(variables_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'variable_name', 'instruction', 'prompt_template',
                'aggregation_instruction', 'aggregation_prompt_template',
                'variable_type', 'scope', 'option_definitions',
                'aggregation_option_definitions', 'only_use_true_value_in_aggregation',
                'default_value_for_empty_response'
            ]
            
            # Ensure prompt_template is empty string (per production examples)
            for var in variables:
                var['prompt_template'] = ''
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(variables)
        
        print(f"✅ Generated {variables_file} with {len(variables)} variables")
        return variables_file
    
    def generate_decisions_csv(self):
        """Generate decisions.csv with aggregation rules."""
        print(f"\n🎯 Generating decisions.csv...")
        
        decisions_file = self.output_dir / 'decisions.csv'
        
        # Helper function to ensure no empty fields
        def fill_decision_defaults(dec):
            """Fill empty fields with appropriate defaults."""
            if not dec.get('dependent_variables'):
                dec['dependent_variables'] = '[]'
            if not dec.get('default_value_for_empty_response'):
                if dec['decision_type'] == 'boolean':
                    dec['default_value_for_empty_response'] = 'false'
                elif dec['decision_type'] == 'integer':
                    dec['default_value_for_empty_response'] = '0'
                else:
                    dec['default_value_for_empty_response'] = 'unknown'
            return dec
        
        # Define dependent variables for cross-validation and aggregation (7-COLUMN FORMAT)
        decisions = [
            {
                'decision_name': 'confirmed_diagnosis',
                'instruction': 'Cross-validate primary diagnosis from FHIR and narrative sources',
                'decision_type': 'text',
                'prompt_template': 'Compare primary_diagnosis values from FHIR_BUNDLE and narrative documents. If they match, return that diagnosis. If different, return both separated by " OR ". Prioritize pathology reports.',
                'variables': '["primary_diagnosis"]',
            },
            
            {
                'decision_name': 'total_surgeries',
                'instruction': 'Count total number of unique surgical procedures',
                'decision_type': 'text',
                'prompt_template': 'Count the total number of unique surgery_date values across all documents. Return the count as a text number (e.g., "1", "2", "3"). If no surgeries found, return "0".',
                'variables': '["surgery_date"]',
                'default_value_for_empty_response': '0'
            },
            
            {
                'decision_name': 'best_resection',
                'instruction': 'Determine the most extensive resection achieved',
                'decision_type': 'text',
                'prompt_template': 'From all surgeries (excluding biopsies and shunts), determine which had the best/most extensive resection. Prioritize: gross_total > near_total > subtotal > partial > debulking.',
                'variables': '["surgery_type", "extent_of_resection"]',
            },
            
            {
                'decision_name': 'chemotherapy_regimen',
                'instruction': 'Aggregate all chemotherapy agents into treatment regimen',
                'decision_type': 'text',
                'prompt_template': 'List all unique chemotherapy agents the patient received. Remove duplicates and format as comma-separated list.',
                'variables': '["chemotherapy_agent"]',
            },
            
            {
                'decision_name': 'molecular_profile',
                'instruction': 'Summarize molecular/genetic testing results',
                'decision_type': 'text',
                'prompt_template': 'Summarize all molecular test results including IDH mutation and MGMT methylation status. Format as "IDH: [status], MGMT: [status]".',
                'variables': '["idh_mutation", "mgmt_methylation"]',
            }
        ]
        
        # Apply defaults to all decisions
        decisions = [fill_decision_defaults(d) for d in decisions]
        
        # Write CSV with 7-COLUMN FORMAT (per official BRIM documentation)
        # decision_name,instruction,decision_type,prompt_template,variables,dependent_variables,default_value_for_empty_response
        with open(decisions_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'decision_name', 'instruction', 'decision_type', 'prompt_template', 
                'variables', 'dependent_variables', 'default_value_for_empty_response'
            ]
            
            # Ensure prompt_template is empty string (per documentation)
            for dec in decisions:
                dec['prompt_template'] = ''
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(decisions)
        
        print(f"✅ Generated {decisions_file} with {len(decisions)} decisions")
        return decisions_file
    
    def generate_all(self):
        """Generate all BRIM CSVs."""
        print("\n" + "="*70)
        print("🚀 BRIM CSV GENERATION")
        print("="*70)
        print(f"FHIR Patient ID: {self.patient_id}")
        print(f"Subject ID (PERSON_ID): {self.subject_id}")
        print(f"Output Dir: {self.output_dir}")
        print("="*70)
        
        # Extract clinical notes
        self.extract_clinical_notes()
        
        # Generate CSVs
        project_file = self.generate_project_csv()
        variables_file = self.generate_variables_csv()
        decisions_file = self.generate_decisions_csv()
        
        print("\n" + "="*70)
        print("✅ GENERATION COMPLETE")
        print("="*70)
        print("\n📁 Generated files:")
        print(f"   1. {project_file}")
        print(f"   2. {variables_file}")
        print(f"   3. {decisions_file}")
        print("\n📋 Next steps:")
        print("   1. Review the generated CSVs")
        print("   2. Upload to BRIM platform (https://app.brimhealth.com)")
        print("   3. Run extraction job in BRIM UI")
        print("   4. Download results and validate against manual CSVs")
        print("="*70)
        
        return project_file, variables_file, decisions_file


def main():
    parser = argparse.ArgumentParser(description='Generate BRIM CSVs from FHIR Bundle')
    parser.add_argument('--bundle-path', default='./pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json',
                        help='Path to FHIR Bundle JSON file')
    parser.add_argument('--output-dir', default='./pilot_output/brim_csvs',
                        help='Output directory for BRIM CSVs')
    
    args = parser.parse_args()
    
    # Generate CSVs
    generator = BRIMCSVGenerator(args.bundle_path, args.output_dir)
    generator.generate_all()


if __name__ == '__main__':
    main()
