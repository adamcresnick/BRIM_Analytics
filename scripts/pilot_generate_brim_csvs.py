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
    """Generate BRIM-compatible CSVs from FHIR Bundle, Clinical Notes, and Structured Data."""
    
    def __init__(self, bundle_path, output_dir='./pilot_output/brim_csvs', 
                 structured_data_path=None, prioritized_docs_path=None):
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
        
        # Load structured data (diagnosis, surgeries, molecular, treatments)
        self.structured_data = None
        if structured_data_path and Path(structured_data_path).exists():
            print(f"📊 Loading structured data from {structured_data_path}")
            with open(structured_data_path, 'r') as f:
                self.structured_data = json.load(f)
            print(f"✅ Loaded structured data: {len(self.structured_data.get('surgeries', []))} surgeries, "
                  f"{len(self.structured_data.get('molecular_markers', []))} molecular markers, "
                  f"{len(self.structured_data.get('treatments', []))} treatments")
        
        # Load prioritized documents list
        self.prioritized_docs = None
        if prioritized_docs_path and Path(prioritized_docs_path).exists():
            print(f"📄 Loading prioritized documents from {prioritized_docs_path}")
            with open(prioritized_docs_path, 'r') as f:
                self.prioritized_docs = json.load(f)
            print(f"✅ Loaded {len(self.prioritized_docs.get('prioritized_documents', []))} prioritized documents, "
                  f"{len(self.prioritized_docs.get('procedure_linked_documents', []))} procedure-linked documents")
        
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
    
    def extract_prioritized_documents(self):
        """Extract clinical notes from prioritized documents list.
        
        Uses the prioritized_documents.json file from athena_document_prioritizer.py
        which contains Binary IDs and metadata for the most relevant clinical documents.
        """
        if not self.prioritized_docs:
            print("\n⚠️  No prioritized documents list provided, skipping...")
            return
        
        print(f"\n📄 Extracting prioritized clinical documents...")
        
        # Get both prioritized and procedure-linked documents
        all_docs = []
        
        if 'prioritized_documents' in self.prioritized_docs:
            all_docs.extend(self.prioritized_docs['prioritized_documents'])
            print(f"   Processing {len(self.prioritized_docs['prioritized_documents'])} prioritized documents...")
        
        if 'procedure_linked_documents' in self.prioritized_docs:
            # Convert DataFrame records to dict format
            proc_docs = self.prioritized_docs['procedure_linked_documents']
            if proc_docs:  # Not empty list
                all_docs.extend(proc_docs)
                print(f"   Processing {len(proc_docs)} procedure-linked documents...")
        
        if not all_docs:
            print("   ⚠️  No documents found in prioritized list")
            return
        
        print(f"   Total documents to extract: {len(all_docs)}")
        
        # Track success/failure
        success_count = 0
        failure_count = 0
        
        for i, doc in enumerate(all_docs, 1):
            try:
                # Extract Binary ID from s3_url (format: Binary/fXXXXXXX...)
                s3_url = doc.get('s3_url', '')
                if not s3_url or 'Binary/' not in s3_url:
                    failure_count += 1
                    continue
                
                binary_id = s3_url.split('Binary/')[-1]
                
                # Progress update
                if i <= 10 or i % 50 == 0:
                    print(f"   Progress: {i}/{len(all_docs)} - Fetching Binary ID: {binary_id[:30]}...")
                
                # Fetch Binary content
                text_content = self._fetch_binary_content(binary_id)
                
                if not text_content:
                    failure_count += 1
                    if i <= 10:
                        print(f"      ⚠️  Failed to fetch Binary content")
                    continue
                
                # Sanitize HTML
                text_content = self._sanitize_html(text_content)
                
                # Create note entry
                note = {
                    'note_id': doc.get('document_id', binary_id),
                    'note_date': doc.get('document_date', ''),
                    'note_type': doc.get('type_text') or doc.get('document_type', 'Clinical Document'),
                    'note_text': text_content
                }
                
                self.clinical_notes.append(note)
                success_count += 1
                
                if i <= 10:
                    print(f"      ✅ Successfully extracted (Type: {note['note_type']}, {len(text_content)} chars)")
                
            except Exception as e:
                failure_count += 1
                if i <= 10:
                    print(f"      ⚠️  Error: {e}")
        
        print(f"\n✅ Successfully extracted {success_count} prioritized documents")
        if failure_count > 0:
            print(f"⚠️  Failed to extract {failure_count} documents")
        print(f"📊 Total clinical notes in memory: {len(self.clinical_notes)}")
    
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
        """Fetch Binary resource content from S3 source/Binary/ folder.
        
        Binary files are stored in prd/source/Binary/ with the Binary ID as the filename.
        NOTE: Due to S3 naming bug, periods (.) in Binary IDs are replaced with underscores (_) in filenames.
        
        Example:
            Binary ID: e.AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
            S3 Key: prd/source/Binary/e_AHt-I-WoBGSMKmuuusnGLrnV6wFTfGWHVBq1xg4H543
        """
        # Track fetch attempts for debugging
        if not hasattr(self, '_binary_fetch_count'):
            self._binary_fetch_count = 0
        self._binary_fetch_count += 1
        debug = self._binary_fetch_count <= 3  # Debug first 3 attempts
        
        try:
            if debug:
                print(f"         Fetching Binary ID: {binary_id}")
            
            # IMPORTANT: Replace periods with underscores due to S3 naming bug
            s3_filename = binary_id.replace('.', '_')
            s3_key = f"prd/source/Binary/{s3_filename}"
            
            if debug:
                print(f"         S3 Key: {s3_key}")
            
            # Fetch from S3 using boto3
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            binary_data = response['Body'].read()
            
            if debug:
                print(f"         Downloaded {len(binary_data)} bytes")
            
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
    
    def create_structured_findings_documents(self):
        """Create synthetic 'documents' from structured data findings.
        
        These are NOT from Binary HTML files, but rather from materialized views:
        - Molecular markers (molecular_tests view)
        - Surgery details (procedure view)
        - Treatment history (patient_medications view)
        
        These findings are fed into BRIM as supplementary context to improve extraction accuracy.
        """
        synthetic_docs = []
        
        if not self.structured_data:
            return synthetic_docs
        
        # 1. Molecular Markers Summary
        if self.structured_data.get('molecular_markers'):
            markers_text = "MOLECULAR/GENETIC TESTING RESULTS (Structured Data Extract):\n\n"
            
            # Handle both dict and list formats
            markers = self.structured_data['molecular_markers']
            if isinstance(markers, dict):
                # Format: {"BRAF": "fusion description text..."}
                for gene_name, finding in markers.items():
                    markers_text += f"Gene: {gene_name}\n"
                    markers_text += f"Finding: {finding}\n"
                    markers_text += "-" * 60 + "\n"
            elif isinstance(markers, list):
                # Format: [{"test_name": "...", "result": "..."}, ...]
                for marker in markers:
                    markers_text += f"Test: {marker.get('test_name', 'Unknown')}\n"
                    markers_text += f"Result: {marker.get('result_display', 'N/A')}\n"
                    markers_text += f"Value: {marker.get('value_string', 'N/A')}\n"
                    markers_text += f"Date: {marker.get('result_datetime', 'Unknown')}\n"
                    markers_text += "-" * 60 + "\n"
            
            synthetic_docs.append({
                'document_id': 'STRUCTURED_molecular_markers',
                'document_type': 'Molecular Testing Summary',
                'document_date': '',
                'text_content': markers_text
            })
        
        # 2. Surgery Details Summary
        if self.structured_data.get('surgeries'):
            surgery_text = "SURGICAL PROCEDURES (Structured Data Extract):\n\n"
            for i, surgery in enumerate(self.structured_data['surgeries'], 1):
                surgery_text += f"Surgery #{i}:\n"
                # Handle both formats: date vs performed_date_time
                surgery_date = surgery.get('date') or surgery.get('performed_date_time', 'Unknown')
                surgery_text += f"Date: {surgery_date if surgery_date else 'Not specified'}\n"
                # Handle both formats: description/code_text/cpt_display
                procedure_name = surgery.get('description') or surgery.get('code_text') or surgery.get('cpt_display', 'Unknown')
                surgery_text += f"Procedure: {procedure_name}\n"
                # Handle both formats: cpt_code (single) vs cpt_codes (list)
                if surgery.get('cpt_code'):
                    surgery_text += f"CPT Code: {surgery['cpt_code']}\n"
                elif surgery.get('cpt_codes'):
                    surgery_text += f"CPT Codes: {', '.join(surgery['cpt_codes'])}\n"
                if surgery.get('body_site_text'):
                    surgery_text += f"Body Site: {surgery['body_site_text']}\n"
                surgery_text += "-" * 60 + "\n"
            
            synthetic_docs.append({
                'document_id': 'STRUCTURED_surgeries',
                'document_type': 'Surgical History Summary',
                'document_date': self.structured_data['surgeries'][0].get('date') or self.structured_data['surgeries'][0].get('performed_date_time', ''),
                'text_content': surgery_text
            })
        
        # 3. Treatment History Summary
        if self.structured_data.get('treatments'):
            treatment_text = "TREATMENT HISTORY (Structured Data Extract):\n\n"
            
            # Group by medication name
            meds_by_name = {}
            for tx in self.structured_data['treatments']:
                # Handle both formats: medication vs medication_name
                med_name = tx.get('medication') or tx.get('medication_name', 'Unknown')
                if med_name not in meds_by_name:
                    meds_by_name[med_name] = []
                meds_by_name[med_name].append(tx)
            
            for med_name, records in meds_by_name.items():
                treatment_text += f"Medication: {med_name}\n"
                # Handle both formats: rx_norm_codes (string) vs rx_norm_code (single value)
                rx_codes = set()
                for r in records:
                    if r.get('rx_norm_codes'):
                        rx_codes.add(str(r['rx_norm_codes']))
                    elif r.get('rx_norm_code'):
                        rx_codes.add(str(r['rx_norm_code']))
                if rx_codes and rx_codes != {'None', 'null'}:
                    treatment_text += f"RxNorm Codes: {', '.join(rx_codes)}\n"
                # Handle both formats: start_date vs authored_on
                dates = [r.get('start_date') or r.get('authored_on', '9999') for r in records]
                treatment_text += f"First Recorded: {min(dates)}\n"
                treatment_text += f"Total Records: {len(records)}\n"
                treatment_text += "-" * 60 + "\n"
            
            synthetic_docs.append({
                'document_id': 'STRUCTURED_treatments',
                'document_type': 'Treatment History Summary',
                'document_date': min(tx.get('start_date') or tx.get('authored_on', '9999') for tx in self.structured_data['treatments']),
                'text_content': treatment_text
            })
        
        # 4. Diagnosis Summary
        if self.structured_data.get('diagnosis'):
            dx = self.structured_data['diagnosis']
            dx_text = "PRIMARY DIAGNOSIS (Structured Data Extract):\n\n"
            dx_text += f"Diagnosis: {dx.get('diagnosis_name', 'Unknown')}\n"
            dx_text += f"ICD-10 Code: {dx.get('icd10_code', 'N/A')}\n"
            dx_text += f"Onset Date: {dx.get('onset_date_time', 'Unknown')}\n"
            dx_text += f"Clinical Status: {dx.get('clinical_status', 'N/A')}\n"
            
            synthetic_docs.append({
                'document_id': 'STRUCTURED_diagnosis',
                'document_type': 'Diagnosis Summary',
                'document_date': dx.get('onset_date_time', ''),
                'text_content': dx_text
            })
        elif self.structured_data.get('diagnosis_date'):
            # Simpler format: just diagnosis_date
            dx_text = "PRIMARY DIAGNOSIS DATE (Structured Data Extract):\n\n"
            dx_text += f"Diagnosis Date: {self.structured_data['diagnosis_date']}\n"
            dx_text += "Source: problem_list_diagnoses materialized view\n"
            
            synthetic_docs.append({
                'document_id': 'STRUCTURED_diagnosis_date',
                'document_type': 'Diagnosis Date Summary',
                'document_date': self.structured_data['diagnosis_date'],
                'text_content': dx_text
            })
        
        print(f"   Created {len(synthetic_docs)} structured finding documents")
        return synthetic_docs
    
    def generate_project_csv(self):
        """Generate project.csv with FHIR Bundle + Clinical Notes + Structured Findings."""
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
        
        # Rows 2-N: Structured Findings (molecular, surgical, treatment summaries)
        structured_docs = self.create_structured_findings_documents()
        for doc in structured_docs:
            rows.append({
                'NOTE_ID': doc['document_id'],
                'PERSON_ID': self.subject_id,
                'NOTE_DATETIME': doc['document_date'] or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'NOTE_TEXT': doc['text_content'],
                'NOTE_TITLE': doc['document_type']
            })
        
        # Rows N+1...: Clinical Notes from Binary HTML files
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
                'instruction': 'Extract the patient\'s date of birth in YYYY-MM-DD format. Priority order: 1) If document_type is FHIR_BUNDLE: Find Patient.birthDate (exact date). 2) If clinical text contains age (e.g., "19 yo", "35 year old"): Calculate approximate birth year by subtracting age from document date year, return YYYY-01-01. 3) If neither available: return "Not documented". Examples: Patient.birthDate="2005-03-15" → "2005-03-15". "19 yo female" in 2024 → "2005-01-01" (approximate). No age or DOB → "Not documented".',
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
                'instruction': 'Find the date when the primary brain tumor was first diagnosed. Priority order: 1) If document_type is FHIR_BUNDLE: Check Condition resources for onsetDateTime or recordedDate fields (search for Condition with resourceType="Condition"). 2) If narrative: Look for phrases like "diagnosed on", "diagnosis date", "initial diagnosis", or dates near diagnostic statements. 3) Fallback: Use earliest surgery date or clinical note mention. Return in YYYY-MM-DD format. If only month/year available, use first day of month (YYYY-MM-01). If not found, return "unknown".',
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
                'instruction': 'Classify neurosurgical procedures only. EXCLUDE non-surgical procedures like anesthesia, administrative orders, or nursing procedures. INCLUDE: Craniotomy, craniectomy, tumor resection, debulking, excision, biopsy, shunt placement - any procedure with "SURGERY", "RESECTION", "CRANIOTOMY" in name. EXCLUDE: Anesthesia procedures (ANES...), surgical case requests/orders (administrative), pre/post-op care orders, nursing procedures. Options: BIOPSY (tissue sampling only), RESECTION (tumor removal), DEBULKING (cytoreductive surgery), SHUNT (shunt placement), OTHER (other surgical procedures). If excluded, do NOT create an entry. Return one classification per actual surgery.',
                'variable_type': 'text',
                'scope': 'many_per_note',
                'option_definitions': '{"BIOPSY": "Biopsy procedure", "RESECTION": "Tumor resection", "DEBULKING": "Debulking procedure", "SHUNT": "Shunt placement", "OTHER": "Other surgical procedure"}',
            },
            
            {
                'variable_name': 'extent_of_resection',
                'instruction': 'Determine extent of surgical tumor removal from explicit statements AND indirect evidence. EXPLICIT: "gross total resection" (GTR), "complete resection", "near total resection" (NTR), "95% resection", "subtotal resection" (STR), "partial resection", "biopsy". INDIRECT: "surgical cavity" / "resection bed" / "postoperative changes" → resection occurred (check context for extent). "residual tumor" / "incomplete resection" → subtotal. "enhancing cystic structures...gross total resection" → GTR. Return: gross total resection | near total resection | subtotal resection | biopsy only | not specified. Only use "not specified" if no direct OR indirect evidence exists. Scope is many_per_note for multiple surgeries.',
                'variable_type': 'text',
                'scope': 'many_per_note',
            },
            
            {
                'variable_name': 'surgery_location',
                'instruction': 'Extract anatomical location of brain surgery. Common locations: posterior fossa, cerebellum, frontal lobe, parietal lobe, temporal lobe, occipital lobe, midbrain, thalamus, brainstem, ventricles, corpus callosum. Look in: 1) Operative reports (procedure site descriptions). 2) Radiology reports describing "surgical changes" / "craniotomy site" / "resection cavity" (e.g., "left parietal craniotomy", "posterior fossa surgical changes"). 3) FHIR Procedure.bodySite if available. Return specific anatomical location per surgery. If multiple locations mentioned for one surgery (e.g., tumor crossing midline), list primary location. Scope is many_per_note to capture each surgery\'s location separately.',
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
                'instruction': 'Determine if patient received radiation therapy for brain tumor. Search both FHIR Procedure resources AND clinical note text. Look for: "radiation therapy", "radiotherapy", "RT", "XRT", "external beam radiation", "IMRT", "proton therapy", "stereotactic radiosurgery", "gamma knife", "CyberKnife", "radiation oncology", dose mentions like "Gy" (Gray units), "fractions". Return "true" if ANY radiation treatment mentioned. Return "false" if explicitly stated patient did NOT receive radiation (e.g., "no prior radiation", "radiation not indicated"). Return "false" as default if not mentioned (assume not done if not documented). This is one_per_patient scope - determine overall radiation status.',
                'variable_type': 'boolean',
                'scope': 'one_per_patient',
            },
            
            # Molecular/Genetic
            {
                'variable_name': 'idh_mutation',
                'instruction': 'Extract IDH (isocitrate dehydrogenase) mutation status from molecular testing. Search in: 1) FHIR Observation resources with codes related to IDH testing. 2) Pathology report text (look for "pathology", "molecular", "genetic" sections). 3) Clinical notes mentioning "IDH" or "molecular testing". Patterns indicating WILDTYPE: "IDH wildtype", "IDH wild-type", "IDH WT", "IDH: negative", "no IDH mutation". Patterns indicating MUTANT: "IDH mutant", "IDH mutation", "IDH1 R132H", "IDH2", "IDH positive". Patterns indicating UNKNOWN: "IDH testing not performed", "IDH pending", "molecular testing incomplete". Return: wildtype | mutant | unknown. This is critical molecular marker - search thoroughly in all text.',
                'variable_type': 'text',
                'scope': 'one_per_patient',
                'option_definitions': '{"wildtype": "IDH wildtype (no mutation)", "mutant": "IDH mutation positive", "unknown": "Unknown or not tested"}',
            },
            
            {
                'variable_name': 'mgmt_methylation',
                'instruction': 'Extract MGMT promoter methylation status from molecular testing. MGMT methylation is a prognostic biomarker in glioblastoma. Search in: 1) FHIR Observation resources with MGMT-related codes. 2) Pathology report text (molecular/genetic sections). 3) Clinical notes mentioning "MGMT". Patterns indicating METHYLATED: "MGMT promoter methylated", "MGMT methylation positive", "MGMT: methylated", "methylated MGMT promoter". Patterns indicating UNMETHYLATED: "MGMT unmethylated", "MGMT promoter unmethylated", "MGMT methylation negative", "MGMT: unmethylated". Patterns indicating UNKNOWN: "MGMT not tested", "MGMT pending", "MGMT unavailable". Return: methylated | unmethylated | unknown.',
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
                'instruction': 'Count total unique surgical procedures across patient entire treatment history (longitudinal data). METHOD: 1) Count distinct surgery_date values where surgery_type != OTHER. 2) ALSO count surgeries mentioned in narrative without structured dates - look for: "prior craniotomy", "previous resection", "status post surgery", "surgical changes from prior [location] surgery". 3) Use surgery_location to identify separate surgeries: different anatomical sites (posterior fossa, parietal, frontal) indicate separate procedures even if dates unknown. 4) Same date + same location = 1 surgery (even if multiple procedure codes). Same date + different locations = count each location separately. EXAMPLES: surgery_date=2021-03-10 (posterior fossa) + radiology mentions "prior left parietal craniotomy" + "right frontal shunt" = 3 surgeries total. surgery_date=2021-03-10 (2 procedures same site) = 1 surgery. No dates but text describes 2 different surgical sites = 2 surgeries. Return count as number string.',
                'decision_type': 'text',
                'prompt_template': '',
                'variables': '["surgery_date", "surgery_type", "surgery_location"]',
                'default_value_for_empty_response': '0'
            },
            
            {
                'decision_name': 'best_resection',
                'instruction': 'Determine MOST EXTENSIVE tumor resection achieved across ALL surgeries in patient history (longitudinal analysis). ALWAYS prioritize extent_of_resection over surgery_type (radiological confirmation is more accurate than procedure coding). Priority order (most to least extensive): 1. "gross total resection" (GTR), 2. "near total resection" (NTR), 3. "subtotal resection" (STR), 4. RESECTION, 5. DEBULKING, 6. BIOPSY. Search ALL extent_of_resection AND surgery_type entries. Return BEST outcome ever achieved, not just most recent. KEY RULE: If radiology states "gross total resection" but procedure coded as "DEBULKING", return "gross total resection" (trust imaging over coding). EXAMPLES: extent=["not specified", "gross total resection", "not specified"], type=[DEBULKING, OTHER] → "gross total resection". extent=["subtotal resection"], type=[RESECTION, BIOPSY] → "subtotal resection". extent=["not specified"], type=[DEBULKING, RESECTION] → "RESECTION".',
                'decision_type': 'text',
                'prompt_template': '',
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
        
        # Extract clinical notes (try prioritized documents first, fallback to full S3 scan)
        if self.prioritized_docs:
            print("\n📌 Using prioritized documents list for targeted extraction...")
            self.extract_prioritized_documents()
        else:
            print("\n📥 No prioritized documents list provided, falling back to full S3 scan...")
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
    parser = argparse.ArgumentParser(description='Generate BRIM CSVs from FHIR Bundle, Structured Data, and Prioritized Documents')
    parser.add_argument('--bundle-path', default='./pilot_output/fhir_bundle_e4BwD8ZYDBccepXcJ.Ilo3w3.json',
                        help='Path to FHIR Bundle JSON file')
    parser.add_argument('--structured-data', dest='structured_data_path',
                        help='Path to structured data JSON (diagnosis, surgeries, molecular, treatments)')
    parser.add_argument('--prioritized-docs', dest='prioritized_docs_path',
                        help='Path to prioritized documents JSON from athena_document_prioritizer.py')
    parser.add_argument('--output-dir', default='./pilot_output/brim_csvs',
                        help='Output directory for BRIM CSVs')
    
    args = parser.parse_args()
    
    # Generate CSVs
    generator = BRIMCSVGenerator(
        args.bundle_path, 
        args.output_dir,
        structured_data_path=args.structured_data_path,
        prioritized_docs_path=args.prioritized_docs_path
    )
    generator.generate_all()


if __name__ == '__main__':
    main()
