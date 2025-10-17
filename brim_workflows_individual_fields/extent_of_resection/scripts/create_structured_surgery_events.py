#!/usr/bin/env python3
"""
Create STRUCTURED Surgery Events Document with Event Type Classification

Generates a markdown document linking surgeries to operative notes with proper
event_type classification based on data dictionary logic.

Event Type Logic (from data dictionary):
- First surgery: event_type = 5 (Initial CNS Tumor)
- After GTR/NTR + regrowth: event_type = 7 (Recurrence)
- After Partial/STR/Biopsy + regrowth: event_type = 8 (Progressive)

Author: RADIANT PCA Analytics Team
Created: 2025-10-11
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import yaml
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StructuredSurgeryEventsGenerator:
    """
    Generates STRUCTURED surgery events document with event_type classification
    """

    def __init__(self, config_file: str):
        """Initialize with patient configuration"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.patient_fhir_id = self.config['patient_fhir_id']
        self.birth_date = datetime.strptime(self.config['birth_date'], '%Y-%m-%d')

        logger.info(f"Initialized for patient {self.patient_fhir_id}")

    def load_staging_files(self):
        """Load required Athena staging files"""
        logger.info("Loading staging files...")

        self.procedures_df = pd.read_csv(self.config['staging_files']['procedures'])
        logger.info(f"  Loaded {len(self.procedures_df)} procedures")

        self.documents_df = pd.read_csv(self.config['staging_files']['documents'])
        logger.info(f"  Loaded {len(self.documents_df)} documents")

    def identify_surgical_procedures(self):
        """Identify surgical procedures from procedures dataframe"""
        logger.info("Identifying surgical procedures...")

        # Filter for surgical procedures
        surgical_keywords = [
            'CRANIOTOMY', 'CRANIECTOMY', 'RESECTION', 'EXCISION',
            'BIOPSY', 'VENTRICULOSTOMY', 'SHUNT'
        ]

        surgeries = []
        for idx, proc in self.procedures_df.iterrows():
            code_text = str(proc.get('code_text', '')).upper()

            if any(keyword in code_text for keyword in surgical_keywords):
                # Extract surgery date
                surgery_date = proc.get('performed_period_start', proc.get('performed_date_time', ''))
                if pd.isna(surgery_date) or surgery_date == '':
                    continue

                surgery_date_str = surgery_date[:10]  # YYYY-MM-DD

                # Try age_at_procedure_resolved first (more reliable), fallback to age_at_procedure_days
                age_days = proc.get('age_at_procedure_resolved')
                if pd.isna(age_days):
                    age_days = proc.get('age_at_procedure_days', 0)
                if pd.isna(age_days):
                    age_days = 0

                surgeries.append({
                    'procedure_fhir_id': proc['procedure_fhir_id'],
                    'surgery_date': surgery_date_str,
                    'surgery_datetime': surgery_date,
                    'age_at_surgery_days': int(age_days),
                    'code_text': proc.get('code_text', ''),
                    'encounter_reference': proc.get('encounter_reference', ''),
                    'performer': proc.get('performer_actor_display', ''),
                    'reason': proc.get('reason_code_text', '')
                })

        self.surgeries_df = pd.DataFrame(surgeries).sort_values('age_at_surgery_days').reset_index(drop=True)
        logger.info(f"  Identified {len(self.surgeries_df)} surgical procedures")

        return self.surgeries_df

    def link_operative_notes(self):
        """Link operative notes to surgeries via context_period_start matching"""
        logger.info("Linking operative notes to surgeries...")

        op_note_types = [
            'OP Note - Complete (Template or Full Dictation)',
            'OP Note - Brief (Needs Dictation)',
            'Operative Record',
            'Anesthesia Postprocedure Evaluation'
        ]

        # Priority map for document types
        priority_map = {
            'OP Note - Complete (Template or Full Dictation)': 1,
            'OP Note - Brief (Needs Dictation)': 2,
            'Operative Record': 3,
            'Anesthesia Postprocedure Evaluation': 4
        }

        linked_surgeries = []

        for idx, surgery in self.surgeries_df.iterrows():
            surgery_date = surgery['surgery_date']

            # Find documents with context_period_start matching surgery date
            matching_docs = self.documents_df[
                (self.documents_df['context_period_start'].str.startswith(surgery_date, na=False)) &
                (self.documents_df['document_type'].isin(op_note_types))
            ].copy()

            if len(matching_docs) > 0:
                # Add priority ranking
                matching_docs['priority'] = matching_docs['document_type'].map(priority_map).fillna(99)

                # Add S3 availability priority (prefer Yes > No)
                matching_docs['s3_priority'] = matching_docs['s3_available'].map({'Yes': 1, 'No': 2}).fillna(3)

                # Sort by document type priority first, then S3 availability
                best_doc = matching_docs.sort_values(['priority', 's3_priority']).iloc[0]

                linked_surgeries.append({
                    **surgery.to_dict(),
                    'op_note_id': best_doc['document_reference_id'],
                    'op_note_type': best_doc['document_type'],
                    'op_note_date': best_doc['document_date'],
                    'op_note_context_start': best_doc['context_period_start'],
                    'op_note_s3_available': best_doc['s3_available'],
                    'op_note_s3_key': best_doc.get('s3_key', ''),
                    'linkage_status': 'LINKED'
                })

                logger.info(f"  ✓ Surgery {surgery_date}: Linked to {best_doc['document_type']}")
            else:
                linked_surgeries.append({
                    **surgery.to_dict(),
                    'op_note_id': None,
                    'op_note_type': None,
                    'op_note_date': None,
                    'op_note_context_start': None,
                    'op_note_s3_available': None,
                    'op_note_s3_key': None,
                    'linkage_status': 'NO_OP_NOTE_FOUND'
                })

                logger.warning(f"  ✗ Surgery {surgery_date}: No operative note found")

        self.linked_surgeries_df = pd.DataFrame(linked_surgeries)
        return self.linked_surgeries_df

    def classify_event_types(self):
        """
        Classify event_type for each surgery based on data dictionary logic

        Rules:
        1. First surgery = Initial CNS Tumor (5)
        2. After GTR/NTR + regrowth = Recurrence (7)
        3. After Partial/STR/Biopsy + regrowth = Progressive (8)

        NOTE: Since we don't have extent_of_resection extracted yet,
        we'll mark first surgery as 5 and subsequent as 8 (conservative assumption)
        """
        logger.info("Classifying event types...")

        event_types = []
        event_labels = []

        for idx, surgery in self.linked_surgeries_df.iterrows():
            if idx == 0:
                # First surgery is always Initial CNS Tumor
                event_types.append(5)
                event_labels.append('Initial CNS Tumor')
                logger.info(f"  Surgery {idx+1} ({surgery['surgery_date']}): Event Type 5 (Initial CNS Tumor)")
            else:
                # For subsequent surgeries, we assume Progressive (8) as conservative default
                # In production, this would check previous surgery extent_of_resection
                event_types.append(8)
                event_labels.append('Progressive')
                logger.info(f"  Surgery {idx+1} ({surgery['surgery_date']}): Event Type 8 (Progressive - default)")

        self.linked_surgeries_df['event_type'] = event_types
        self.linked_surgeries_df['event_label'] = event_labels

        return self.linked_surgeries_df

    def generate_markdown_document(self):
        """Generate STRUCTURED markdown document"""
        logger.info("Generating STRUCTURED markdown document...")

        output_lines = []

        # Header
        output_lines.append(f"# STRUCTURED Surgery Events with Event Type Classification")
        output_lines.append(f"")
        output_lines.append(f"**Patient FHIR ID**: {self.patient_fhir_id}")
        output_lines.append(f"**Patient FHIR ID**: {self.patient_fhir_id}")
        output_lines.append(f"**Birth Date**: {self.birth_date.strftime('%Y-%m-%d')}")
        output_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"")
        output_lines.append(f"---")
        output_lines.append(f"")

        # Summary table
        output_lines.append(f"## Summary")
        output_lines.append(f"")
        output_lines.append(f"| Event | Age (days) | Surgery Date | Event Type | Operative Note Status |")
        output_lines.append(f"|-------|-----------|--------------|------------|----------------------|")

        for idx, surgery in self.linked_surgeries_df.iterrows():
            status = "✓ Linked" if surgery['linkage_status'] == 'LINKED' else "✗ Not Found"
            output_lines.append(
                f"| Event {idx+1} | {surgery['age_at_surgery_days']} | "
                f"{surgery['surgery_date']} | {surgery['event_type']} ({surgery['event_label']}) | {status} |"
            )

        output_lines.append(f"")
        output_lines.append(f"---")
        output_lines.append(f"")

        # Detailed event sections
        for idx, surgery in self.linked_surgeries_df.iterrows():
            event_num = idx + 1
            output_lines.append(f"## Event {event_num}: {surgery['event_label']} (age {surgery['age_at_surgery_days']} days)")
            output_lines.append(f"")
            output_lines.append(f"**Event Number**: {event_num}")
            output_lines.append(f"**Event Type**: {surgery['event_type']} ({surgery['event_label']})")
            output_lines.append(f"**Surgery Date**: {surgery['surgery_date']}")
            output_lines.append(f"**Age at Surgery**: {surgery['age_at_surgery_days']} days (~{surgery['age_at_surgery_days']/365.25:.1f} years)")
            output_lines.append(f"**Surgery Type**: {surgery['code_text']}")
            output_lines.append(f"**Procedure FHIR ID**: `{surgery['procedure_fhir_id']}`")
            output_lines.append(f"**Performer**: {surgery['performer']}")

            if surgery['reason']:
                output_lines.append(f"**Indication**: {surgery['reason']}")

            output_lines.append(f"")

            # Operative note details
            if surgery['linkage_status'] == 'LINKED':
                output_lines.append(f"### Linked Operative Note")
                output_lines.append(f"")
                output_lines.append(f"- **Document Type**: {surgery['op_note_type']}")
                output_lines.append(f"- **Document Date**: {surgery['op_note_date']}")
                output_lines.append(f"- **Context Period Start**: {surgery['op_note_context_start']} ✓ (matches surgery date)")
                output_lines.append(f"- **S3 Available**: {surgery['op_note_s3_available']}")
                output_lines.append(f"- **Document FHIR ID**: `{surgery['op_note_id']}`")

                if surgery['op_note_s3_available'] == 'Yes':
                    output_lines.append(f"- **S3 Key**: `{surgery['op_note_s3_key']}`")

                output_lines.append(f"")
                output_lines.append(f"### Extent of Resection")
                output_lines.append(f"")
                output_lines.append(f"**BRIM Extraction Target**: Extract extent from operative note sections:")
                output_lines.append(f"- Procedure performed")
                output_lines.append(f"- Post-operative impression")
                output_lines.append(f"- Surgeon's assessment")
                output_lines.append(f"")
                output_lines.append(f"**Expected Values** (Data Dictionary):")
                output_lines.append(f"- `1` = Gross/Near total resection")
                output_lines.append(f"- `2` = Partial resection")
                output_lines.append(f"- `3` = Biopsy only")
                output_lines.append(f"- `4` = Unavailable")
            else:
                output_lines.append(f"### ⚠️ No Operative Note Found")
                output_lines.append(f"")
                output_lines.append(f"No operative note was found with `context_period_start` matching {surgery['surgery_date']}.")
                output_lines.append(f"Manual review may be required.")

            output_lines.append(f"")

            # Event type determination logic
            output_lines.append(f"### Event Type Determination Logic")
            output_lines.append(f"")

            if idx == 0:
                output_lines.append(f"**Logic**: First surgery → Always event_type = 5 (Initial CNS Tumor)")
            else:
                output_lines.append(f"**Logic**: Subsequent surgery → event_type = 8 (Progressive) [default assumption]")
                output_lines.append(f"")
                output_lines.append(f"⚠️ **Note**: In production, event type would be determined by:")
                output_lines.append(f"- If previous surgery was GTR/NTR → event_type = 7 (Recurrence)")
                output_lines.append(f"- If previous surgery was Partial/STR/Biopsy → event_type = 8 (Progressive)")

            output_lines.append(f"")
            output_lines.append(f"---")
            output_lines.append(f"")

        # Data dictionary mapping
        output_lines.append(f"## Data Dictionary Field Mapping")
        output_lines.append(f"")
        output_lines.append(f"| Event | event_type | age_at_event_days | surgery | age_at_surgery | extent_of_tumor_resection |")
        output_lines.append(f"|-------|-----------|------------------|---------|----------------|---------------------------|")

        for idx, surgery in self.linked_surgeries_df.iterrows():
            output_lines.append(
                f"| Event {idx+1} | {surgery['event_type']} | {surgery['age_at_surgery_days']} | "
                f"1 (Yes) | {surgery['age_at_surgery_days']} | [EXTRACT FROM OP NOTE] |"
            )

        output_lines.append(f"")
        output_lines.append(f"---")
        output_lines.append(f"")
        output_lines.append(f"## Instructions for BRIM Upload")
        output_lines.append(f"")
        output_lines.append(f"1. Upload this STRUCTURED document as `NOTE_ID='STRUCTURED_surgery_events'`")
        output_lines.append(f"2. Upload linked operative notes (S3 documents) for extent of resection extraction")
        output_lines.append(f"3. Update BRIM variables.csv to prioritize this STRUCTURED document")
        output_lines.append(f"4. Run BRIM extraction job")
        output_lines.append(f"5. Validate extracted extent values against data dictionary codes")
        output_lines.append(f"")

        self.markdown_content = "\n".join(output_lines)
        return self.markdown_content

    def save_outputs(self):
        """Save markdown document and CSV staging file"""
        output_dir = Path(self.config['output_directory'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save markdown
        md_file = output_dir / f"STRUCTURED_surgery_events_{self.patient_fhir_id}.md"
        with open(md_file, 'w') as f:
            f.write(self.markdown_content)
        logger.info(f"✓ Saved markdown: {md_file}")

        # Add event_number column to staging CSV
        self.linked_surgeries_df['event_number'] = range(1, len(self.linked_surgeries_df) + 1)

        # Save CSV staging file
        csv_file = output_dir / f"surgery_events_staging_{self.patient_fhir_id}.csv"
        self.linked_surgeries_df.to_csv(csv_file, index=False)
        logger.info(f"✓ Saved CSV: {csv_file}")

        return md_file, csv_file

    def run(self):
        """Execute full pipeline"""
        logger.info("="*80)
        logger.info("STRUCTURED SURGERY EVENTS GENERATOR")
        logger.info("="*80)

        self.load_staging_files()
        self.identify_surgical_procedures()
        self.link_operative_notes()
        self.classify_event_types()
        self.generate_markdown_document()
        md_file, csv_file = self.save_outputs()

        logger.info("="*80)
        logger.info("✓ COMPLETED SUCCESSFULLY")
        logger.info(f"  Markdown: {md_file}")
        logger.info(f"  CSV: {csv_file}")
        logger.info("="*80)

        return md_file, csv_file


def main():
    parser = argparse.ArgumentParser(
        description='Generate STRUCTURED surgery events document with event type classification'
    )
    parser.add_argument(
        'config_file',
        help='Path to patient configuration YAML file'
    )

    args = parser.parse_args()

    generator = StructuredSurgeryEventsGenerator(args.config_file)
    generator.run()


if __name__ == '__main__':
    main()
