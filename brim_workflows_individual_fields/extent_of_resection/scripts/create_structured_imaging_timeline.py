#!/usr/bin/env python3
"""
Create STRUCTURED Imaging Timeline Document

Generates a markdown document organizing imaging studies in temporal relation
to surgical events, enabling BRIM to extract imaging-related data dictionary fields.

Categorizes imaging as:
- Pre-operative (within 30 days before surgery)
- Post-operative (within 90 days after surgery)
- Surveillance (all other time periods)

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


class StructuredImagingTimelineGenerator:
    """
    Generates STRUCTURED imaging timeline linked to surgical events
    """

    def __init__(self, config_file: str, surgery_events_csv: str):
        """Initialize with patient configuration and surgery events"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.patient_fhir_id = self.config['patient_fhir_id']
        self.birth_date = datetime.strptime(self.config['birth_date'], '%Y-%m-%d')

        # Load surgery events
        self.surgery_events_df = pd.read_csv(surgery_events_csv)
        self.surgery_events_df['surgery_date'] = pd.to_datetime(
            self.surgery_events_df['surgery_date']
        )

        logger.info(f"Initialized for patient {self.patient_fhir_id}")
        logger.info(f"  Loaded {len(self.surgery_events_df)} surgical events")

    def load_imaging_data(self):
        """Load imaging metadata from Athena staging file"""
        logger.info("Loading imaging data...")

        imaging_file = self.config['staging_files'].get('imaging')

        if imaging_file and Path(imaging_file).exists():
            self.imaging_df = pd.read_csv(imaging_file)
            self.imaging_df['imaging_date'] = pd.to_datetime(
                self.imaging_df['imaging_date']
            )
            logger.info(f"  Loaded {len(self.imaging_df)} imaging studies from CSV")
        else:
            # Fallback: extract from DocumentReference metadata
            logger.warning(f"  Imaging CSV not found, using DocumentReference metadata")
            self.imaging_df = self._extract_from_document_references()

        return self.imaging_df

    def _extract_from_document_references(self):
        """Extract imaging from DocumentReference metadata as fallback"""
        docs_df = pd.read_csv(self.config['staging_files']['documents'])

        imaging_types = [
            'MR Brain', 'CT Brain', 'MRI', 'CT scan',
            'Diagnostic imaging study', 'Radiology'
        ]

        imaging_docs = docs_df[
            docs_df['document_type'].str.contains('|'.join(imaging_types), case=False, na=False)
        ].copy()

        imaging_docs['imaging_date'] = pd.to_datetime(imaging_docs['document_date'])

        logger.info(f"  Extracted {len(imaging_docs)} imaging documents from DocumentReference")

        return imaging_docs

    def categorize_imaging_studies(self):
        """Categorize imaging studies relative to surgical events"""
        logger.info("Categorizing imaging studies...")

        categorized_studies = []

        for idx, study in self.imaging_df.iterrows():
            study_date = study['imaging_date']

            # Find temporal relationship to surgeries
            category = 'Surveillance'
            related_surgery = None
            days_from_surgery = None

            for _, surgery in self.surgery_events_df.iterrows():
                surgery_date = surgery['surgery_date']
                days_diff = (study_date - surgery_date).days

                # Pre-operative: 1-30 days before surgery
                if -30 <= days_diff < 0:
                    category = 'Pre-operative'
                    related_surgery = surgery['surgery_date'].strftime('%Y-%m-%d')
                    days_from_surgery = days_diff
                    break

                # Post-operative: 0-90 days after surgery
                elif 0 <= days_diff <= 90:
                    category = 'Post-operative'
                    related_surgery = surgery['surgery_date'].strftime('%Y-%m-%d')
                    days_from_surgery = days_diff
                    break

            categorized_studies.append({
                **study.to_dict(),
                'category': category,
                'related_surgery_date': related_surgery,
                'days_from_surgery': days_from_surgery
            })

        self.categorized_imaging_df = pd.DataFrame(categorized_studies)

        # Log summary
        category_counts = self.categorized_imaging_df['category'].value_counts()
        for category, count in category_counts.items():
            logger.info(f"  {category}: {count} studies")

        return self.categorized_imaging_df

    def generate_markdown_document(self):
        """Generate STRUCTURED markdown document"""
        logger.info("Generating STRUCTURED imaging timeline...")

        output_lines = []

        # Header
        output_lines.append(f"# STRUCTURED Imaging Timeline")
        output_lines.append(f"")
        output_lines.append(f"**Patient FHIR ID**: {self.patient_fhir_id}")
        output_lines.append(f"**Patient FHIR ID**: {self.patient_fhir_id}")
        output_lines.append(f"**Birth Date**: {self.birth_date.strftime('%Y-%m-%d')}")
        output_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"")
        output_lines.append(f"---")
        output_lines.append(f"")

        # Summary statistics
        output_lines.append(f"## Imaging Summary")
        output_lines.append(f"")
        output_lines.append(f"| Category | Count | Description |")
        output_lines.append(f"|----------|-------|-------------|")

        for category in ['Pre-operative', 'Post-operative', 'Surveillance']:
            count = len(self.categorized_imaging_df[
                self.categorized_imaging_df['category'] == category
            ])
            if category == 'Pre-operative':
                desc = "Within 30 days before surgery"
            elif category == 'Post-operative':
                desc = "Within 90 days after surgery"
            else:
                desc = "All other time periods"

            output_lines.append(f"| {category} | {count} | {desc} |")

        output_lines.append(f"")
        output_lines.append(f"---")
        output_lines.append(f"")

        # Imaging organized by surgical event
        for idx, surgery in self.surgery_events_df.iterrows():
            surgery_date = surgery['surgery_date'].strftime('%Y-%m-%d')
            event_num = idx + 1

            output_lines.append(f"## Event {event_num}: Surgery on {surgery_date}")
            output_lines.append(f"")
            output_lines.append(f"**Surgery Type**: {surgery.get('code_text', 'N/A')}")
            output_lines.append(f"**Age at Surgery**: {surgery['age_at_surgery_days']} days")
            output_lines.append(f"**Event Type**: {surgery['event_type']} ({surgery['event_label']})")
            output_lines.append(f"")

            # Pre-operative imaging
            preop = self.categorized_imaging_df[
                (self.categorized_imaging_df['related_surgery_date'] == surgery_date) &
                (self.categorized_imaging_df['category'] == 'Pre-operative')
            ].sort_values('imaging_date')

            if len(preop) > 0:
                output_lines.append(f"### Pre-operative Imaging")
                output_lines.append(f"")
                output_lines.append(f"| Date | Days Before Surgery | Modality | Findings |")
                output_lines.append(f"|------|-------------------|----------|----------|")

                for _, img in preop.iterrows():
                    days_before = abs(img['days_from_surgery'])
                    modality = img.get('imaging_modality', img.get('document_type', 'Unknown'))

                    # Extract impression/findings if available
                    findings = self._extract_findings_summary(img)

                    output_lines.append(
                        f"| {img['imaging_date'].strftime('%Y-%m-%d')} | "
                        f"{days_before} days | {modality} | {findings} |"
                    )

                output_lines.append(f"")
            else:
                output_lines.append(f"### Pre-operative Imaging")
                output_lines.append(f"")
                output_lines.append(f"⚠️ No pre-operative imaging found within 30 days before surgery.")
                output_lines.append(f"")

            # Post-operative imaging
            postop = self.categorized_imaging_df[
                (self.categorized_imaging_df['related_surgery_date'] == surgery_date) &
                (self.categorized_imaging_df['category'] == 'Post-operative')
            ].sort_values('imaging_date')

            if len(postop) > 0:
                output_lines.append(f"### Post-operative Imaging")
                output_lines.append(f"")
                output_lines.append(f"| Date | Days After Surgery | Modality | Findings |")
                output_lines.append(f"|------|------------------|----------|----------|")

                for _, img in postop.iterrows():
                    days_after = img['days_from_surgery']
                    modality = img.get('imaging_modality', img.get('document_type', 'Unknown'))

                    findings = self._extract_findings_summary(img)

                    output_lines.append(
                        f"| {img['imaging_date'].strftime('%Y-%m-%d')} | "
                        f"{days_after} days | {modality} | {findings} |"
                    )

                output_lines.append(f"")
            else:
                output_lines.append(f"### Post-operative Imaging")
                output_lines.append(f"")
                output_lines.append(f"⚠️ No post-operative imaging found within 90 days after surgery.")
                output_lines.append(f"")

            output_lines.append(f"---")
            output_lines.append(f"")

        # Surveillance imaging (not tied to specific surgery)
        surveillance = self.categorized_imaging_df[
            self.categorized_imaging_df['category'] == 'Surveillance'
        ].sort_values('imaging_date')

        if len(surveillance) > 0:
            output_lines.append(f"## Surveillance Imaging")
            output_lines.append(f"")
            output_lines.append(f"Imaging studies not temporally linked to surgical events:")
            output_lines.append(f"")
            output_lines.append(f"| Date | Age (days) | Modality | Findings |")
            output_lines.append(f"|------|-----------|----------|----------|")

            for _, img in surveillance.iterrows():
                age_at_imaging = img.get('age_at_imaging_days', 'N/A')
                modality = img.get('imaging_modality', img.get('document_type', 'Unknown'))
                findings = self._extract_findings_summary(img)

                output_lines.append(
                    f"| {img['imaging_date'].strftime('%Y-%m-%d')} | "
                    f"{age_at_imaging} | {modality} | {findings} |"
                )

            output_lines.append(f"")
            output_lines.append(f"---")
            output_lines.append(f"")

        # Instructions
        output_lines.append(f"## Instructions for BRIM Upload")
        output_lines.append(f"")
        output_lines.append(f"1. Upload this STRUCTURED document as `NOTE_ID='STRUCTURED_imaging'`")
        output_lines.append(f"2. Upload individual imaging reports (S3 documents) for detailed extraction")
        output_lines.append(f"3. Use this timeline to guide temporal extraction of:")
        output_lines.append(f"   - tumor_location (from pre-operative imaging)")
        output_lines.append(f"   - metastasis status (from staging imaging)")
        output_lines.append(f"   - extent of resection assessment (from post-operative imaging)")
        output_lines.append(f"   - site_of_progression (from surveillance imaging)")
        output_lines.append(f"")

        self.markdown_content = "\n".join(output_lines)
        return self.markdown_content

    def _extract_findings_summary(self, img_row):
        """Extract concise findings summary from imaging row"""
        # Try result_information field first (from Athena CSV)
        if 'result_information' in img_row and pd.notna(img_row['result_information']):
            findings = str(img_row['result_information'])

            # Extract impression if available
            if 'IMPRESSION:' in findings.upper():
                impression_start = findings.upper().find('IMPRESSION:')
                impression_text = findings[impression_start:impression_start+200]
                return impression_text.replace('\n', ' ').strip()[:100] + "..."

            # Otherwise return first 100 characters
            return findings.replace('\n', ' ').strip()[:100] + "..."

        # Fallback to description field
        elif 'description' in img_row and pd.notna(img_row['description']):
            return str(img_row['description'])[:100]

        return "[Extract from full report]"

    def save_outputs(self):
        """Save markdown document and CSV staging file"""
        output_dir = Path(self.config['output_directory'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save markdown
        md_file = output_dir / f"STRUCTURED_imaging_timeline_{self.patient_fhir_id}.md"
        with open(md_file, 'w') as f:
            f.write(self.markdown_content)
        logger.info(f"✓ Saved markdown: {md_file}")

        # Save CSV staging file
        csv_file = output_dir / f"imaging_timeline_staging_{self.patient_fhir_id}.csv"
        self.categorized_imaging_df.to_csv(csv_file, index=False)
        logger.info(f"✓ Saved CSV: {csv_file}")

        return md_file, csv_file

    def run(self):
        """Execute full pipeline"""
        logger.info("="*80)
        logger.info("STRUCTURED IMAGING TIMELINE GENERATOR")
        logger.info("="*80)

        self.load_imaging_data()
        self.categorize_imaging_studies()
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
        description='Generate STRUCTURED imaging timeline linked to surgical events'
    )
    parser.add_argument(
        'config_file',
        help='Path to patient configuration YAML file'
    )
    parser.add_argument(
        'surgery_events_csv',
        help='Path to surgery events staging CSV from previous step'
    )

    args = parser.parse_args()

    generator = StructuredImagingTimelineGenerator(
        args.config_file,
        args.surgery_events_csv
    )
    generator.run()


if __name__ == '__main__':
    main()
