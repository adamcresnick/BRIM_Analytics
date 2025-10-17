#!/usr/bin/env python3
"""
Generate BRIM CSVs for Radiology and Operative Note Data Dictionary Fields

This focused script generates the 3 BRIM CSV files needed to extract fields from
the radiology_op_note_data_dictionary.csv:

1. project.csv - Contains STRUCTURED documents + relevant clinical notes
2. variables.csv - Extraction instructions for each field
3. decisions.csv - Aggregation rules across events

Strategy:
- Leverages context_period_start matching to link documents to surgeries
- Uses STRUCTURED synthetic documents for event classification
- Only includes relevant operative notes and imaging reports (not all documents)

Author: RADIANT PCA Analytics Team
Created: 2025-10-11
"""

import pandas as pd
import json
import csv
import boto3
import base64
from datetime import datetime
from pathlib import Path
import argparse
import yaml
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RadiologyOpNoteBRIMGenerator:
    """
    Generate BRIM CSVs focused on radiology and operative note fields
    """

    def __init__(self, config_file: str):
        """Initialize with patient configuration"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.patient_fhir_id = self.config['patient_fhir_id']
        # PERSON_ID for BRIM - use pseudoMRN if provided, otherwise FHIR ID
        self.person_id = self.config.get('pseudo_mrn', self.patient_fhir_id)

        # AWS setup
        self.aws_profile = self.config.get('aws_profile', 'radiant-dev')
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.s3_client = self.session.client('s3', region_name='us-east-1')
        self.s3_bucket = 'radiant-prd-343218191717-us-east-1-prd-ehr-pipeline'

        self.output_dir = Path(self.config['output_directory'])

        logger.info(f"Initialized for patient FHIR ID: {self.patient_fhir_id}")

        # Storage for documents to include in project.csv
        self.project_rows = []

    def load_staging_files(self):
        """Load surgery events and imaging metadata staging files"""
        logger.info("Loading staging files...")

        # Load surgery events
        surgery_file = self.output_dir / f"surgery_events_staging_{self.patient_fhir_id}.csv"
        if not surgery_file.exists():
            raise FileNotFoundError(
                f"Surgery events staging file not found: {surgery_file}\n"
                f"Run create_structured_surgery_events.py first"
            )
        self.surgery_df = pd.read_csv(surgery_file)
        logger.info(f"  Loaded {len(self.surgery_df)} surgical events")

        # Load imaging metadata from Athena extraction (optional)
        # Build path to BRIM_Analytics/staging_files
        # output_dir structure: .../BRIM_Analytics/brim_workflows_individual_fields/extent_of_resection/staging_files/FHIR_ID
        # So parent.parent.parent.parent = BRIM_Analytics
        brim_analytics_dir = self.output_dir.parent.parent.parent.parent
        staging_files_dir = brim_analytics_dir / 'staging_files'

        # Check multiple possible file naming patterns
        # Note: Imaging files may be named with MRN (C1277724) rather than FHIR ID
        imaging_file_options = [
            self.output_dir / f"imaging_timeline_staging_{self.patient_fhir_id}.csv",
            staging_files_dir / f"ALL_IMAGING_METADATA_{self.patient_fhir_id}.csv",
        ]

        # Also glob for any ALL_IMAGING_METADATA files in staging_files
        import glob
        glob_pattern = str(staging_files_dir / "ALL_IMAGING_METADATA_*.csv")
        glob_matches = glob.glob(glob_pattern)

        if glob_matches:
            logger.info(f"  Found {len(glob_matches)} imaging metadata files via glob")
            imaging_file_options.extend([Path(p) for p in glob_matches])

        imaging_file = None
        for option in imaging_file_options:
            if option.exists():
                imaging_file = option
                logger.info(f"  Using imaging file: {option.name}")
                break

        if imaging_file:
            self.imaging_df = pd.read_csv(imaging_file)
            # Filter to this patient's FHIR ID
            if 'patient_id' in self.imaging_df.columns:
                before_count = len(self.imaging_df)
                self.imaging_df = self.imaging_df[
                    self.imaging_df['patient_id'] == self.patient_fhir_id
                ]
                logger.info(f"  Loaded {len(self.imaging_df)} imaging studies for patient (filtered from {before_count})")
            else:
                logger.info(f"  Loaded {len(self.imaging_df)} imaging studies from {imaging_file.name}")
        else:
            self.imaging_df = pd.DataFrame()
            logger.warning(f"  No imaging metadata found")

    def create_structured_surgery_document_row(self):
        """Create project.csv row for STRUCTURED surgery events document"""
        logger.info("Creating STRUCTURED surgery events document...")

        # Read the generated markdown file
        md_file = self.output_dir / f"STRUCTURED_surgery_events_{self.patient_fhir_id}.md"
        with open(md_file, 'r') as f:
            markdown_content = f.read()

        row = {
            'NOTE_ID': 'STRUCTURED_surgery_events',
            'PERSON_ID': self.person_id,
            'NOTE_DATETIME': datetime.now().isoformat() + 'Z',
            'NOTE_TEXT': markdown_content,
            'NOTE_TITLE': 'STRUCTURED Surgery Events with Event Type Classification'
        }

        self.project_rows.append(row)
        logger.info(f"  Added STRUCTURED_surgery_events ({len(markdown_content)} chars)")

    def create_structured_imaging_document_row(self):
        """Create project.csv row for STRUCTURED imaging timeline"""
        if len(self.imaging_df) == 0:
            logger.info("Skipping STRUCTURED imaging (no imaging data)")
            return

        logger.info("Creating STRUCTURED imaging timeline document...")

        md_file = self.output_dir / f"STRUCTURED_imaging_timeline_{self.patient_fhir_id}.md"
        if md_file.exists():
            with open(md_file, 'r') as f:
                markdown_content = f.read()

            row = {
                'NOTE_ID': 'STRUCTURED_imaging',
                'PERSON_ID': self.person_id,
                'NOTE_DATETIME': datetime.now().isoformat() + 'Z',
                'NOTE_TEXT': markdown_content,
                'NOTE_TITLE': 'STRUCTURED Imaging Timeline'
            }

            self.project_rows.append(row)
            logger.info(f"  Added STRUCTURED_imaging ({len(markdown_content)} chars)")

    def fetch_operative_notes_from_s3(self):
        """Fetch operative note content from S3 Binary files"""
        logger.info("Fetching operative notes from S3...")

        for idx, surgery in self.surgery_df.iterrows():
            if surgery['linkage_status'] != 'LINKED':
                logger.warning(f"  Surgery {idx+1}: No operative note linked, skipping")
                continue

            if surgery['op_note_s3_available'] != 'Yes':
                logger.warning(f"  Surgery {idx+1}: Operative note not available in S3, skipping")
                continue

            # Extract Binary ID from S3 key (format: prd/source/Binary/{binary_id})
            s3_key = surgery['op_note_s3_key']
            if pd.isna(s3_key) or s3_key == '':
                logger.warning(f"  Surgery {idx+1}: No S3 key provided, skipping")
                continue

            binary_id = s3_key.split('/')[-1]  # Get last part of path
            content = self._fetch_binary_from_s3(binary_id)

            if content:
                # Sanitize HTML if present
                clean_content = self._sanitize_html(content)

                # NOTE_ID includes event number for linkage
                event_num = surgery.get('event_number', idx+1)

                row = {
                    'NOTE_ID': f"op_note_{event_num}_{surgery['surgery_date']}",
                    'PERSON_ID': self.person_id,
                    'NOTE_DATETIME': surgery['op_note_date'],
                    'NOTE_TEXT': clean_content,
                    'NOTE_TITLE': surgery['op_note_type']
                }

                self.project_rows.append(row)
                logger.info(f"  Added operative note {idx+1} ({len(clean_content)} chars)")
            else:
                logger.error(f"  Surgery {idx+1}: Failed to fetch operative note from S3")

    def _fetch_binary_from_s3(self, binary_id: str):
        """Fetch Binary content from S3"""
        try:
            # Replace periods with underscores (S3 naming convention)
            s3_filename = binary_id.replace('.', '_')
            s3_key = f"prd/source/Binary/{s3_filename}"

            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            binary_data = response['Body'].read()

            # Try JSON format first (FHIR Binary resource)
            try:
                binary_resource = json.loads(binary_data.decode('utf-8'))
                data = binary_resource.get('data', '')
                if data:
                    return base64.b64decode(data).decode('utf-8', errors='ignore')
            except json.JSONDecodeError:
                # Try direct decoding
                return binary_data.decode('utf-8', errors='ignore')

        except Exception as e:
            logger.error(f"Error fetching Binary {binary_id}: {e}")
            return None

    def _sanitize_html(self, text: str):
        """Remove HTML tags and clean text"""
        if not text:
            return ""

        soup = BeautifulSoup(text, 'html.parser')
        clean_text = soup.get_text()
        clean_text = '\n'.join(line.strip() for line in clean_text.split('\n') if line.strip())

        return clean_text

    def fetch_imaging_reports_from_s3(self):
        """Add imaging reports from Athena structured data (not S3)"""
        if len(self.imaging_df) == 0:
            logger.info("Skipping imaging reports (no imaging data)")
            return

        logger.info("Adding imaging reports from Athena structured data...")

        # Use all imaging studies with result_information
        imaging_with_reports = self.imaging_df[
            ~self.imaging_df['result_information'].isna()
        ].copy()

        logger.info(f"  Found {len(imaging_with_reports)} imaging studies with reports")

        # Add each imaging study as a separate document
        for idx, img in imaging_with_reports.iterrows():
            # Get report text from result_information
            report_text = img['result_information']

            if pd.isna(report_text) or str(report_text).strip() == '':
                continue

            # Determine imaging date
            imaging_date = img.get('imaging_date', '')
            if pd.notna(imaging_date):
                # Extract just the date portion (YYYY-MM-DD)
                try:
                    imaging_date_str = pd.to_datetime(imaging_date).strftime('%Y-%m-%d')
                except:
                    imaging_date_str = str(imaging_date)[:10]
            else:
                imaging_date_str = 'unknown'

            # Create NOTE_ID using imaging procedure ID or index
            imaging_id = img.get('imaging_procedure_id', f'img_{idx}')
            modality = img.get('imaging_modality', 'Imaging')

            # Determine if Narrative or Impression
            display_type = img.get('result_display', 'Narrative')

            row = {
                'NOTE_ID': f"imaging_{imaging_date_str}_{idx}",
                'PERSON_ID': self.person_id,
                'NOTE_DATETIME': img.get('imaging_date', datetime.now().isoformat() + 'Z'),
                'NOTE_TEXT': str(report_text),
                'NOTE_TITLE': f"{modality} Report - {display_type}"
            }

            self.project_rows.append(row)
            logger.info(f"  Added imaging report {idx+1}: {modality} {display_type} ({len(str(report_text))} chars)")

    def create_project_csv(self):
        """Generate project.csv file"""
        logger.info("Generating project.csv...")

        output_file = self.output_dir / f"project_{self.patient_fhir_id}.csv"

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'NOTE_ID', 'PERSON_ID', 'NOTE_DATETIME', 'NOTE_TEXT', 'NOTE_TITLE'
            ])
            writer.writeheader()
            writer.writerows(self.project_rows)

        logger.info(f"  Saved project.csv with {len(self.project_rows)} documents")
        return output_file

    def create_variables_csv(self):
        """Generate variables.csv with extraction instructions"""
        logger.info("Generating variables.csv...")

        variables = []

        # Variable 0: event_number (linking variable - 100% automated)
        variables.append({
            'variable_name': 'event_number',
            'instruction': (
                'Extract event number from NOTE_ID. '
                'For operative notes: NOTE_ID format is "op_note_{EVENT_NUM}_{date}". '
                'For imaging: NOTE_ID format is "imaging_postop_event{EVENT_NUM}_{date}". '
                'For STRUCTURED documents: extract from "Event N:" headers. '
                'Return only the numeric event number (e.g., "1", "2", "3").'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'unknown'
        })

        # Variable 1: event_type_structured (from STRUCTURED document - algorithmic baseline)
        variables.append({
            'variable_name': 'event_type_structured',
            'instruction': (
                'Extract event_type from STRUCTURED_surgery_events document. '
                'Look for "Event Type:" in each Event section. '
                'Return the full text label from these options: '
                '"Initial CNS Tumor", "Second Malignancy", "Recurrence", "Progressive", "Unavailable", "Deceased". '
                'Skip if document is not STRUCTURED_surgery_events.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 2: age_at_event_days (from STRUCTURED document - 100% automated)
        variables.append({
            'variable_name': 'age_at_event_days',
            'instruction': (
                'Extract age_at_event_days from STRUCTURED_surgery_events document. '
                'Look for "Age at Surgery: X days" in each Event section. '
                'Return only the numeric value (days).'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'unknown'
        })

        # Variable 3: surgery (from STRUCTURED document - 100% automated)
        variables.append({
            'variable_name': 'surgery',
            'instruction': (
                'Determine if surgery was performed. '
                'If document is STRUCTURED_surgery_events: always return "Yes". '
                'For other documents: look for surgical procedure descriptions. '
                'Return one of: "Yes", "No", "Unavailable".'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 4: age_at_surgery (from STRUCTURED document - 100% automated)
        variables.append({
            'variable_name': 'age_at_surgery',
            'instruction': (
                'Extract age_at_surgery from STRUCTURED_surgery_events document. '
                'Look for "Age at Surgery: X days" in each Event section. '
                'Return only the numeric value (days). '
                'If no surgery, return empty.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': ''
        })

        # Variable 5a: progression_recurrence_indicator_operative_note (Clinical validation)
        variables.append({
            'variable_name': 'progression_recurrence_indicator_operative_note',
            'instruction': (
                'From OPERATIVE NOTES only: Identify language indicating tumor progression or recurrence. '
                'Look for phrases like: '
                '"recurrent tumor", "tumor recurrence", "regrowth", "re-do craniotomy", "second surgery", '
                '"progressive disease", "residual tumor growth", "increasing size", '
                '"initial resection", "first surgery", "newly diagnosed", "new diagnosis". '
                'Return one of: "Recurrence" (if recurrent/regrowth mentioned), '
                '"Progressive" (if progression/residual growth mentioned), '
                '"Initial" (if first/initial/new diagnosis mentioned), '
                '"Unavailable" (if no clear indication). '
                'Include the supporting text snippet in parentheses. '
                'Example: "Recurrence (tumor recurrence at the resection cavity)" '
                'Skip if not an operative note.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 5b: progression_recurrence_indicator_imaging (Clinical validation)
        variables.append({
            'variable_name': 'progression_recurrence_indicator_imaging',
            'instruction': (
                'From IMAGING REPORTS only: Identify language indicating tumor progression or recurrence. '
                'Look for phrases like: '
                '"recurrent tumor", "new enhancement at resection cavity", "tumor recurrence", '
                '"progressive disease", "interval growth", "increasing size of residual tumor", '
                '"new enhancing mass", "new diagnosis", "newly identified mass". '
                'Return one of: "Recurrence" (if recurrent/regrowth at prior resection site), '
                '"Progressive" (if growth of residual/incompletely resected tumor), '
                '"Initial" (if new/first diagnosis mentioned), '
                '"Unavailable" (if no clear indication). '
                'Include the supporting text snippet in parentheses. '
                'Example: "Recurrence (new enhancement at the right cerebellar resection cavity)" '
                'Skip if not an imaging report.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 5c: extent_from_operative_note (BRIM extraction - source 1)
        variables.append({
            'variable_name': 'extent_from_operative_note',
            'instruction': (
                'Extract extent of tumor resection from operative note ONLY (NOTE_TITLE contains "OP Note"). '
                'Look in sections: Procedure Performed, Post-operative Assessment, Surgeon Summary. '
                'Keywords: GTR (gross total), NTR (near total), Partial, Subtotal (STR), Biopsy only. '
                'Return one of these exact text labels: '
                '"Gross/Near total resection", "Partial resection", "Biopsy only", "Unavailable", "N/A". '
                'If document is not an operative note, skip.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 5d: extent_from_postop_imaging (BRIM extraction - source 2)
        variables.append({
            'variable_name': 'extent_from_postop_imaging',
            'instruction': (
                'Extract extent of residual tumor from POST-OPERATIVE imaging report ONLY '
                '(NOTE_TITLE contains "Post-operative Imaging"). '
                'Look for: "residual tumor", "extent of resection", "gross total resection", '
                '"complete resection", "partial resection", "near total resection". '
                'Assess based on radiologist description of residual disease. '
                'Return one of these exact text labels: '
                '"Gross/Near total resection" (no residual), "Partial resection" (residual tumor present), '
                '"Unavailable" (not mentioned). '
                'If document is not post-op imaging, skip.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 6: tumor_location_per_document (from op notes + imaging - BRIM extraction)
        # Note: This extracts per-document, aggregation happens in decisions.csv
        variables.append({
            'variable_name': 'tumor_location_per_document',
            'instruction': (
                'Extract tumor anatomical location(s) from this specific document. '
                'Search operative notes and imaging reports. '
                'Return comma-separated text labels from these options: '
                '"Frontal Lobe", "Temporal Lobe", "Parietal Lobe", "Occipital Lobe", '
                '"Thalamus", "Ventricles", "Suprasellar/Hypothalamic/Pituitary", '
                '"Cerebellum/Posterior Fossa", "Brain Stem-Medulla", '
                '"Brain Stem-Midbrain/Tectum", "Brain Stem-Pons", '
                '"Spinal Cord-Cervical", "Spinal Cord-Thoracic", "Spinal Cord-Lumbar/Thecal Sac", '
                '"Optic Pathway", "Cranial Nerves NOS", "Pineal Gland", "Basal Ganglia", '
                '"Hippocampus", "Meninges/Dura", "Skull", "Unavailable". '
                'Example: "Cerebellum/Posterior Fossa" or "Cerebellum/Posterior Fossa, Brain Stem-Pons". '
                'If no locations mentioned, return "Unavailable".'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 7: metastasis (from imaging reports - BRIM extraction)
        variables.append({
            'variable_name': 'metastasis',
            'instruction': (
                'Determine if metastatic disease was present at time of diagnosis/clinical event. '
                'Search imaging reports (especially pre-operative) for: '
                'CSF spread, leptomeningeal involvement, spine metastases, bone marrow involvement, '
                'distant brain metastases. '
                'Return one of: "Yes" (metastases present), "No" (localized disease), "Unavailable".'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 8: metastasis_location (from imaging - BRIM extraction)
        variables.append({
            'variable_name': 'metastasis_location',
            'instruction': (
                'If metastases present (metastasis=Yes), extract location(s). '
                'Return comma-separated text labels from: '
                '"CSF", "Spine", "Bone Marrow", "Other", "Brain", "Leptomeningeal", "Unavailable". '
                'Example: "Leptomeningeal, Spine" or "CSF". '
                'Skip if metastasis=No.'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Variable 9: site_of_progression (from imaging - BRIM extraction)
        variables.append({
            'variable_name': 'site_of_progression',
            'instruction': (
                'For Progressive events, determine site of progression. '
                'Compare current imaging to previous studies. '
                'Look for: growth at original site (Local) vs new distant sites (Metastatic). '
                'Return one of: "Local", "Metastatic", "Unavailable".'
            ),
            'prompt_template': '',
            'aggregation_instruction': '',
            'aggregation_prompt_template': '',
            'variable_type': 'text',
            'scope': 'many_per_note',
            'option_definitions': '',
            'aggregation_option_definitions': '',
            'only_use_true_value_in_aggregation': '',
            'default_value_for_empty_response': 'Unavailable'
        })

        # Save to CSV
        output_file = self.output_dir / f"variables_{self.patient_fhir_id}.csv"

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'variable_name', 'instruction', 'prompt_template',
                'aggregation_instruction', 'aggregation_prompt_template',
                'variable_type', 'scope', 'option_definitions',
                'aggregation_option_definitions', 'only_use_true_value_in_aggregation',
                'default_value_for_empty_response'
            ])
            writer.writeheader()
            writer.writerows(variables)

        logger.info(f"  Saved variables.csv with {len(variables)} variables")
        return output_file

    def create_decisions_csv(self):
        """Generate decisions.csv with aggregation rules"""
        logger.info("Generating decisions.csv...")

        decisions = []

        # Decision 0: event_type_adjudicated (ADJUDICATION - clinical validation vs temporal logic)
        decisions.append({
            'decision_name': 'event_type_adjudicated',
            'instruction': (
                'Adjudicate event_type by comparing STRUCTURED temporal logic with clinical note evidence. '
                'Sources: '
                '1) event_type_structured (temporal/algorithmic baseline) '
                '2) progression_recurrence_indicator_operative_note (clinical evidence from op note) '
                '3) progression_recurrence_indicator_imaging (clinical evidence from imaging) '
                'Logic: '
                '- If clinical notes (op note OR imaging) indicate "Recurrence" → use "Recurrence" '
                '- Else if clinical notes indicate "Progressive" → use "Progressive" '
                '- Else if clinical notes indicate "Initial" → use "Initial CNS Tumor" '
                '- Else use event_type_structured (temporal baseline) '
                'Return one of: "Initial CNS Tumor", "Recurrence", "Progressive", "Second Malignancy", "Unavailable", "Deceased". '
                'Group by event_number. Include justification with supporting text snippets.'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['event_type_structured', 'progression_recurrence_indicator_operative_note',
                                    'progression_recurrence_indicator_imaging', 'event_number']),
            'dependent_variables': json.dumps([]),
            'default_value_for_empty_response': 'Unavailable'
        })

        # Decision 1: extent_of_tumor_resection_adjudicated (ADJUDICATION)
        decisions.append({
            'decision_name': 'extent_of_tumor_resection_adjudicated',
            'instruction': (
                'Adjudicate extent of tumor resection from multiple sources. '
                'Priority order: 1) extent_from_postop_imaging (most objective), '
                '2) extent_from_operative_note (surgeon assessment). '
                'Rules: '
                '- If postop imaging available (not "Unavailable"), use imaging value '
                '- Else use operative note value '
                '- If both unavailable, return "Unavailable" '
                'Return one of: "Gross/Near total resection", "Partial resection", "Biopsy only", "Unavailable", "N/A". '
                'Group by event_number when aggregating.'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['extent_from_operative_note', 'extent_from_postop_imaging', 'event_number']),
            'dependent_variables': json.dumps([]),
            'default_value_for_empty_response': 'Unavailable'
        })

        # Decision 2: tumor_location_by_event (PER-EVENT AGGREGATION)
        decisions.append({
            'decision_name': 'tumor_location_by_event',
            'instruction': (
                'Aggregate all unique tumor locations for each clinical event. '
                'Group by event_number. '
                'Combine all tumor_location_per_document values for the same event. '
                'Return unique location text labels as comma-separated list. '
                'Remove duplicates and "Unavailable" if other locations present. '
                'Format: "Event 1: Cerebellum/Posterior Fossa | Event 2: Cerebellum/Posterior Fossa, Brain Stem-Pons" '
                'If no locations found, return "Unavailable".'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['tumor_location_per_document', 'event_number']),
            'dependent_variables': json.dumps([]),
            'default_value_for_empty_response': 'Unavailable'
        })

        # Decision 3: metastasis_location_by_event (PER-EVENT AGGREGATION)
        decisions.append({
            'decision_name': 'metastasis_location_by_event',
            'instruction': (
                'Aggregate all unique metastasis locations for each clinical event. '
                'Group by event_number. '
                'Only include if metastasis=Yes. '
                'Combine all metastasis_location values for the same event. '
                'Return unique text labels as comma-separated list. '
                'Format: "Event 1: Leptomeningeal, Spine | Event 2: None"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['metastasis', 'metastasis_location', 'event_number']),
            'dependent_variables': json.dumps([]),
            'default_value_for_empty_response': 'None'
        })

        # Decision 3: event_sequence
        decisions.append({
            'decision_name': 'event_sequence',
            'instruction': (
                'Create chronological sequence of clinical events. '
                'Sort by age_at_event_days ascending. '
                'For each event, return: "Event N: event_type=X, age=Y days, surgery=Z". '
                'Example: "Event 1: event_type=5, age=4763 days, surgery=1"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['event_type', 'age_at_event_days', 'surgery', 'event_number']),
            'dependent_variables': json.dumps([]),
            'default_value_for_empty_response': 'unknown'
        })

        # Decision 5: total_surgical_events
        decisions.append({
            'decision_name': 'total_surgical_events',
            'instruction': (
                'Count total number of surgical events. '
                'Count how many unique event_number values have surgery=Yes. '
                'Return as text number (e.g., "2").'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['surgery', 'event_number']),
            'dependent_variables': json.dumps(['event_type_adjudicated']),
            'default_value_for_empty_response': '0'
        })

        # Decision 6: progression_vs_recurrence_count
        decisions.append({
            'decision_name': 'progression_vs_recurrence_count',
            'instruction': (
                'Categorize subsequent events as Progression vs Recurrence using adjudicated values. '
                'Count: event_type_adjudicated=Recurrence and event_type_adjudicated=Progressive. '
                'Return format: "Recurrence: N, Progressive: M"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['event_number']),
            'dependent_variables': json.dumps(['event_type_adjudicated']),
            'default_value_for_empty_response': 'Recurrence: 0, Progressive: 0'
        })

        # Decision 7: extent_progression_validation (VALIDATION)
        decisions.append({
            'decision_name': 'extent_progression_validation',
            'instruction': (
                'Validate event_type_adjudicated classification against extent_of_tumor_resection_adjudicated. '
                'For each subsequent event (event_number > 1): '
                '- Compare previous extent to current event_type_adjudicated '
                '- Expected: Previous extent="Gross/Near total resection" → event_type="Recurrence" '
                '- Expected: Previous extent="Partial resection" or "Biopsy only" → event_type="Progressive" '
                'Return validation summary: "Event N: previous_extent=X, event_type=Y, match=True/False"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['event_number']),
            'dependent_variables': json.dumps(['extent_of_tumor_resection_adjudicated', 'event_type_adjudicated']),
            'default_value_for_empty_response': 'Not applicable'
        })

        # Decision 8: site_of_progression_by_event (PER-EVENT)
        decisions.append({
            'decision_name': 'site_of_progression_by_event',
            'instruction': (
                'For Progressive events (event_type_adjudicated=Progressive), determine if progression is Local vs Metastatic. '
                'Group by event_number. '
                'Logic: '
                '- If tumor_location_by_event same as initial event → Local '
                '- If new distant locations or metastasis=Yes → Metastatic '
                '- If unclear → Unavailable '
                'Return format: "Event 2: Local | Event 3: Metastatic"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['event_number', 'site_of_progression']),
            'dependent_variables': json.dumps(['event_type_adjudicated', 'tumor_location_by_event', 'metastasis_location_by_event']),
            'default_value_for_empty_response': 'Unavailable'
        })

        # Decision 9: metastatic_disease_summary
        decisions.append({
            'decision_name': 'metastatic_disease_summary',
            'instruction': (
                'Determine if metastatic disease was ever documented across all events. '
                'If any event has metastasis=Yes, return "Yes" with event numbers and locations. '
                'If all events have metastasis=No, return "No". '
                'Otherwise return "Unavailable". '
                'Format: "Event 1: Yes (Leptomeningeal, Spine) | Event 2: No"'
            ),
            'decision_type': 'text',
            'prompt_template': '',
            'variables': json.dumps(['metastasis', 'event_number']),
            'dependent_variables': json.dumps(['metastasis_location_by_event']),
            'default_value_for_empty_response': 'Unavailable'
        })

        # Save to CSV
        output_file = self.output_dir / f"decisions_{self.patient_fhir_id}.csv"

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'decision_name', 'instruction', 'decision_type',
                'prompt_template', 'variables', 'dependent_variables',
                'default_value_for_empty_response'
            ])
            writer.writeheader()
            writer.writerows(decisions)

        logger.info(f"  Saved decisions.csv with {len(decisions)} decisions")
        return output_file

    def run(self):
        """Execute complete pipeline"""
        logger.info("="*80)
        logger.info("RADIOLOGY/OPERATIVE NOTE BRIM CSV GENERATOR")
        logger.info("="*80)

        # Step 1: Load staging files
        self.load_staging_files()

        # Step 2: Create STRUCTURED document rows
        self.create_structured_surgery_document_row()
        self.create_structured_imaging_document_row()

        # Step 3: Fetch operative notes from S3
        self.fetch_operative_notes_from_s3()

        # Step 4: Fetch imaging reports from S3 (optional)
        self.fetch_imaging_reports_from_s3()

        # Step 5: Generate BRIM CSVs
        project_file = self.create_project_csv()
        variables_file = self.create_variables_csv()
        decisions_file = self.create_decisions_csv()

        logger.info("="*80)
        logger.info("✓ BRIM CSV GENERATION COMPLETED")
        logger.info("="*80)
        logger.info(f"Generated files:")
        logger.info(f"  1. {project_file}")
        logger.info(f"  2. {variables_file}")
        logger.info(f"  3. {decisions_file}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Upload these 3 CSV files to BRIM platform")
        logger.info("  2. Run BRIM extraction job")
        logger.info("  3. Download results and validate")
        logger.info("="*80)

        return project_file, variables_file, decisions_file


def main():
    parser = argparse.ArgumentParser(
        description='Generate BRIM CSVs for radiology and operative note fields'
    )
    parser.add_argument(
        'config_file',
        help='Path to patient configuration YAML file'
    )

    args = parser.parse_args()

    generator = RadiologyOpNoteBRIMGenerator(args.config_file)
    generator.run()


if __name__ == '__main__':
    main()
