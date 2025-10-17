#!/usr/bin/env python3
"""
Extract Data Dictionary Fields from STRUCTURED Documents

Pre-populates data dictionary fields that can be extracted directly from
structured Athena data (before BRIM LLM extraction).

Fields automated:
- event_type (determined by surgery sequence logic)
- age_at_event_days (from Procedure.performedPeriodStart)
- surgery (Yes/No based on Procedure resource)
- age_at_surgery (from Procedure.performedPeriodStart)

Fields requiring BRIM extraction:
- extent_of_tumor_resection (from operative note text)
- tumor_location (from imaging + operative notes)
- metastasis (from imaging reports)
- site_of_progression (from sequential imaging)

Author: RADIANT PCA Analytics Team
Created: 2025-10-11
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import argparse
import yaml
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataDictionaryFieldExtractor:
    """
    Extract data dictionary fields from structured surgery and imaging data
    """

    # Data dictionary value mappings
    EVENT_TYPE_MAP = {
        5: "Initial CNS Tumor",
        6: "Second Malignancy",
        7: "Recurrence",
        8: "Progressive",
        9: "Unavailable",
        10: "Deceased"
    }

    SURGERY_MAP = {
        1: "Yes",
        2: "No",
        3: "Unavailable"
    }

    EXTENT_MAP = {
        1: "Gross/Near total resection",
        2: "Partial resection",
        3: "Biopsy only",
        4: "Unavailable",
        5: "N/A"
    }

    def __init__(self, config_file: str):
        """Initialize with patient configuration"""
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

        self.patient_fhir_id = self.config['patient_mrn']
        self.patient_fhir_id = self.config['patient_fhir_id']

        logger.info(f"Initialized for patient {self.patient_fhir_id}")

    def load_staging_files(self):
        """Load surgery and imaging staging files"""
        logger.info("Loading staging files...")

        output_dir = Path(self.config['output_directory'])

        # Load surgery events
        surgery_file = output_dir / f"surgery_events_staging_{self.patient_fhir_id}.csv"
        self.surgery_df = pd.read_csv(surgery_file)
        logger.info(f"  Loaded {len(self.surgery_df)} surgery events")

        # Load imaging timeline
        imaging_file = output_dir / f"imaging_timeline_staging_{self.patient_fhir_id}.csv"
        if imaging_file.exists():
            self.imaging_df = pd.read_csv(imaging_file)
            logger.info(f"  Loaded {len(self.imaging_df)} imaging studies")
        else:
            self.imaging_df = pd.DataFrame()
            logger.warning("  No imaging timeline found")

    def extract_surgical_events(self):
        """
        Extract data dictionary fields for surgical events

        Automated fields:
        - event_type
        - age_at_event_days
        - surgery (always 1=Yes for surgical events)
        - age_at_surgery

        Manual/BRIM fields (marked for extraction):
        - extent_of_tumor_resection
        - tumor_location
        - metastasis
        """
        logger.info("Extracting surgical event fields...")

        surgical_records = []

        for idx, surgery in self.surgery_df.iterrows():
            record = {
                # Automated fields
                'event_number': idx + 1,
                'event_type': int(surgery['event_type']),
                'event_type_label': self.EVENT_TYPE_MAP[int(surgery['event_type'])],
                'age_at_event_days': int(surgery['age_at_surgery_days']),
                'surgery': 1,  # Yes
                'surgery_label': 'Yes',
                'age_at_surgery': int(surgery['age_at_surgery_days']),

                # Fields requiring BRIM extraction
                'extent_of_tumor_resection': None,  # Extract from OP note
                'extent_of_tumor_resection_label': '[EXTRACT FROM OP NOTE]',
                'tumor_location': None,  # Extract from OP note + imaging
                'metastasis': None,  # Extract from imaging
                'metastasis_location': None,  # Extract from imaging
                'site_of_progression': None,  # Extract from imaging (if event_type=8)

                # Source references
                'surgery_date': surgery['surgery_date'],
                'procedure_fhir_id': surgery['procedure_fhir_id'],
                'op_note_id': surgery.get('op_note_id'),
                'op_note_available': 'Yes' if surgery['linkage_status'] == 'LINKED' else 'No'
            }

            surgical_records.append(record)

            logger.info(f"  Event {idx+1}: event_type={record['event_type']} ({record['event_type_label']})")

        self.surgical_events_df = pd.DataFrame(surgical_records)
        return self.surgical_events_df

    def identify_non_surgical_progressive_events(self):
        """
        Identify progressive events documented in imaging without surgery

        These are clinical progression events where:
        - No surgery performed
        - Evidence in imaging of tumor growth
        - May trigger chemotherapy
        """
        logger.info("Identifying non-surgical progressive events...")

        # This would require analyzing imaging reports for progression keywords
        # For now, we create a placeholder structure

        non_surgical_records = []

        # TODO: Implement logic to detect progression from imaging timeline
        # Would look for:
        # - Surveillance imaging with keywords like "progression", "increased size"
        # - Temporal gaps > 6 months between surgeries with imaging showing growth
        # - Chemotherapy initiation dates

        logger.info(f"  Found {len(non_surgical_records)} non-surgical progressive events")

        return pd.DataFrame(non_surgical_records)

    def generate_data_dictionary_csv(self):
        """Generate CSV with data dictionary field structure"""
        logger.info("Generating data dictionary CSV...")

        # Combine surgical and non-surgical events
        all_events = pd.concat([
            self.surgical_events_df,
            pd.DataFrame()  # Non-surgical events (if any)
        ], ignore_index=True)

        # Create data dictionary structured output
        dd_output = []

        for _, event in all_events.iterrows():
            dd_row = {
                # Identifiers
                'patient_mrn': self.patient_fhir_id,
                'patient_fhir_id': self.patient_fhir_id,
                'event_number': event['event_number'],

                # Diagnosis tab fields
                'event_type': event['event_type'],
                'age_at_event_days': event['age_at_event_days'],
                'metastasis': event['metastasis'],
                'metastasis_location': event['metastasis_location'],
                'site_of_progression': event['site_of_progression'],
                'tumor_location': event['tumor_location'],

                # Treatment tab fields
                'surgery': event['surgery'],
                'age_at_surgery': event['age_at_surgery'],
                'extent_of_tumor_resection': event['extent_of_tumor_resection'],

                # Source documentation
                'surgery_date': event.get('surgery_date'),
                'procedure_fhir_id': event.get('procedure_fhir_id'),
                'op_note_id': event.get('op_note_id'),
                'op_note_available': event.get('op_note_available'),

                # Extraction status
                'automated_fields': 'event_type, age_at_event_days, surgery, age_at_surgery',
                'brim_required_fields': 'extent_of_tumor_resection, tumor_location, metastasis'
            }

            dd_output.append(dd_row)

        self.dd_df = pd.DataFrame(dd_output)
        return self.dd_df

    def generate_brim_instructions(self):
        """Generate instructions for BRIM extraction"""
        logger.info("Generating BRIM extraction instructions...")

        instructions = []

        instructions.append("# BRIM Extraction Instructions")
        instructions.append("")
        instructions.append(f"**Patient**: {self.patient_fhir_id}")
        instructions.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        instructions.append("")
        instructions.append("---")
        instructions.append("")
        instructions.append("## Pre-Populated Fields (Automated)")
        instructions.append("")
        instructions.append("The following fields have been pre-populated from Athena structured data:")
        instructions.append("")
        instructions.append("- `event_type`: Determined by surgery sequence logic")
        instructions.append("- `age_at_event_days`: Extracted from Procedure.performedPeriodStart")
        instructions.append("- `surgery`: Always 1 (Yes) for surgical events")
        instructions.append("- `age_at_surgery`: Same as age_at_event_days for surgical events")
        instructions.append("")
        instructions.append("**✓ These fields do NOT require BRIM extraction**")
        instructions.append("")
        instructions.append("---")
        instructions.append("")
        instructions.append("## Fields Requiring BRIM Extraction")
        instructions.append("")

        for idx, event in self.surgical_events_df.iterrows():
            instructions.append(f"### Event {event['event_number']}: {event['event_type_label']} (age {event['age_at_event_days']} days)")
            instructions.append("")
            instructions.append(f"**Surgery Date**: {event['surgery_date']}")
            instructions.append(f"**Operative Note**: {event['op_note_id']}")
            instructions.append(f"**OP Note Available**: {event['op_note_available']}")
            instructions.append("")
            instructions.append("**Extract from operative note:**")
            instructions.append("1. `extent_of_tumor_resection`")
            instructions.append("   - Valid values: 1 (Gross/Near total), 2 (Partial), 3 (Biopsy only), 4 (Unavailable)")
            instructions.append("   - Keywords: GTR, NTR, partial, subtotal, STR, biopsy only")
            instructions.append("")
            instructions.append("2. `tumor_location`")
            instructions.append("   - Valid values: See data dictionary for full list")
            instructions.append("   - Keywords: frontal, temporal, parietal, occipital, cerebellum, brainstem, etc.")
            instructions.append("")
            instructions.append("**Extract from pre-operative imaging:**")
            instructions.append("3. `metastasis`")
            instructions.append("   - Valid values: 0 (Yes), 1 (No), 2 (Unavailable)")
            instructions.append("   - Look for: metastatic disease, CSF spread, leptomeningeal, spine involvement")
            instructions.append("")

            if event['event_type'] == 8:  # Progressive
                instructions.append("4. `site_of_progression`")
                instructions.append("   - Valid values: 1 (Local), 2 (Metastatic), 3 (Unavailable)")
                instructions.append("   - Compare to previous imaging to determine local vs metastatic progression")
                instructions.append("")

            instructions.append("---")
            instructions.append("")

        self.brim_instructions = "\n".join(instructions)
        return self.brim_instructions

    def save_outputs(self):
        """Save data dictionary CSV and BRIM instructions"""
        output_dir = Path(self.config['output_directory'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save data dictionary CSV
        dd_file = output_dir / f"data_dictionary_fields_{self.patient_fhir_id}.csv"
        self.dd_df.to_csv(dd_file, index=False)
        logger.info(f"✓ Saved data dictionary CSV: {dd_file}")

        # Save BRIM instructions
        instructions_file = output_dir / f"BRIM_extraction_instructions_{self.patient_fhir_id}.md"
        with open(instructions_file, 'w') as f:
            f.write(self.brim_instructions)
        logger.info(f"✓ Saved BRIM instructions: {instructions_file}")

        return dd_file, instructions_file

    def run(self):
        """Execute full pipeline"""
        logger.info("="*80)
        logger.info("DATA DICTIONARY FIELD EXTRACTOR")
        logger.info("="*80)

        self.load_staging_files()
        self.extract_surgical_events()
        self.identify_non_surgical_progressive_events()
        self.generate_data_dictionary_csv()
        self.generate_brim_instructions()
        dd_file, instructions_file = self.save_outputs()

        logger.info("="*80)
        logger.info("✓ COMPLETED SUCCESSFULLY")
        logger.info(f"  Data Dictionary CSV: {dd_file}")
        logger.info(f"  BRIM Instructions: {instructions_file}")
        logger.info("="*80)

        # Summary statistics
        logger.info("")
        logger.info("EXTRACTION SUMMARY:")
        logger.info(f"  Total Events: {len(self.dd_df)}")
        logger.info(f"  Automated Fields: event_type, age_at_event_days, surgery, age_at_surgery")
        logger.info(f"  BRIM Required: extent_of_tumor_resection, tumor_location, metastasis")
        logger.info("")

        return dd_file, instructions_file


def main():
    parser = argparse.ArgumentParser(
        description='Extract data dictionary fields from structured surgery and imaging data'
    )
    parser.add_argument(
        'config_file',
        help='Path to patient configuration YAML file'
    )

    args = parser.parse_args()

    extractor = DataDictionaryFieldExtractor(args.config_file)
    extractor.run()


if __name__ == '__main__':
    main()
