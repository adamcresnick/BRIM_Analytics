"""
Service Request Integration for Diagnostic Workflows
=====================================================
Maps service requests to procedures/surgeries to understand diagnostic cascades
and treatment planning workflows.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ServiceRequestIntegration:
    """
    Integrate service requests with surgical timelines to understand
    diagnostic workflows and treatment coordination.
    """

    def __init__(self, staging_path: str):
        self.staging_path = Path(staging_path)

    def map_diagnostic_cascade(self,
                              patient_id: str,
                              surgery_date: datetime) -> Dict[str, List[Dict]]:
        """
        Map the diagnostic cascade around a surgical event.

        Returns diagnostic workflow showing:
        - Pre-operative studies and their timing
        - Post-operative imaging for validation
        - Treatment planning studies
        """
        patient_path = self.staging_path / f"patient_{patient_id}"

        cascade = {
            'pre_operative': [],
            'immediate_post_operative': [],  # 24-72 hours
            'treatment_planning': []  # 30 days post
        }

        # Load service requests
        service_requests = self._load_service_requests(patient_path)
        if service_requests.empty:
            return cascade

        # Define critical windows
        pre_op_window = (surgery_date - timedelta(days=30), surgery_date)
        immediate_post_window = (surgery_date, surgery_date + timedelta(hours=72))
        planning_window = (surgery_date + timedelta(days=3), surgery_date + timedelta(days=30))

        # Map requests to windows
        for _, request in service_requests.iterrows():
            request_date = pd.to_datetime(request.get('authored_on'))
            if not request_date:
                continue

            request_info = {
                'date': request_date,
                'service': request.get('code_text', ''),
                'reason': self._extract_reason(request),
                'urgency': request.get('priority', 'routine'),
                'category': request.get('category_text', '')
            }

            # Categorize by timing
            if pre_op_window[0] <= request_date < pre_op_window[1]:
                cascade['pre_operative'].append(request_info)

            elif immediate_post_window[0] <= request_date <= immediate_post_window[1]:
                cascade['immediate_post_operative'].append(request_info)
                # Flag critical post-op imaging
                if 'MRI' in request_info['service'].upper():
                    request_info['critical_for_extent'] = True

            elif planning_window[0] <= request_date <= planning_window[1]:
                cascade['treatment_planning'].append(request_info)

        # Sort by date
        for category in cascade:
            cascade[category].sort(key=lambda x: x['date'])

        return cascade

    def _load_service_requests(self, patient_path: Path) -> pd.DataFrame:
        """Load service request data."""
        request_file = patient_path / "service_requests.csv"
        if not request_file.exists():
            return pd.DataFrame()

        df = pd.read_csv(request_file)

        # Parse dates
        date_cols = ['authored_on', 'occurrence_date_time']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        return df

    def _extract_reason(self, request: pd.Series) -> str:
        """Extract reason from service request."""
        # Check reason code first
        if 'reason_code_text' in request and pd.notna(request['reason_code_text']):
            return request['reason_code_text']

        # Check reason reference
        if 'reason_reference' in request and pd.notna(request['reason_reference']):
            return f"Reference: {request['reason_reference']}"

        # Check notes
        if 'note_text' in request and pd.notna(request['note_text']):
            # Extract first 100 chars of note
            return request['note_text'][:100]

        return "Not specified"

    def identify_diagnostic_patterns(self,
                                    patient_id: str,
                                    all_surgeries: List[datetime]) -> Dict[str, Any]:
        """
        Identify diagnostic patterns across all surgical events.

        Returns patterns like:
        - Standard pre-op workup components
        - Post-op imaging compliance
        - Re-operation diagnostic differences
        """
        patterns = {
            'standard_preop_studies': [],
            'postop_imaging_compliance': [],
            'reoperation_changes': [],
            'urgency_patterns': {}
        }

        for idx, surgery_date in enumerate(all_surgeries):
            cascade = self.map_diagnostic_cascade(patient_id, surgery_date)

            # Analyze pre-op pattern
            preop_types = [r['service'] for r in cascade['pre_operative']]
            patterns['standard_preop_studies'].extend(preop_types)

            # Check post-op imaging compliance (CRITICAL)
            has_postop_mri = any(
                'MRI' in r['service'].upper()
                for r in cascade['immediate_post_operative']
            )
            patterns['postop_imaging_compliance'].append({
                'surgery_date': surgery_date,
                'surgery_number': idx + 1,
                'has_24_72h_mri': has_postop_mri
            })

            # Track urgency patterns
            for request in cascade['pre_operative']:
                urgency = request['urgency']
                patterns['urgency_patterns'][urgency] = patterns['urgency_patterns'].get(urgency, 0) + 1

            # Compare to prior surgery if exists
            if idx > 0:
                patterns['reoperation_changes'].append({
                    'surgery_number': idx + 1,
                    'additional_studies': len(preop_types)
                })

        # Identify most common pre-op studies
        from collections import Counter
        study_counts = Counter(patterns['standard_preop_studies'])
        patterns['common_preop_studies'] = study_counts.most_common(5)

        # Calculate compliance rate
        compliant = sum(1 for p in patterns['postop_imaging_compliance'] if p['has_24_72h_mri'])
        patterns['postop_imaging_rate'] = compliant / len(all_surgeries) if all_surgeries else 0

        return patterns

    def extract_treatment_coordination(self,
                                      patient_id: str,
                                      surgery_date: datetime) -> Dict[str, Any]:
        """
        Extract treatment coordination from service requests.

        Identifies:
        - Multi-disciplinary coordination
        - Treatment sequencing
        - Clinical trial screening
        """
        cascade = self.map_diagnostic_cascade(patient_id, surgery_date)

        coordination = {
            'radiation_planning': False,
            'chemotherapy_planning': False,
            'clinical_trial_screening': False,
            'multi_disciplinary_meeting': False,
            'services_involved': set()
        }

        # Check treatment planning requests
        for request in cascade['treatment_planning']:
            service_text = request['service'].lower()
            reason_text = request['reason'].lower()

            # Check for radiation planning
            if any(term in service_text + reason_text for term in ['radiation', 'rad onc', 'rt planning']):
                coordination['radiation_planning'] = True
                coordination['services_involved'].add('radiation_oncology')

            # Check for chemotherapy planning
            if any(term in service_text + reason_text for term in ['chemotherapy', 'oncology consult', 'chemo']):
                coordination['chemotherapy_planning'] = True
                coordination['services_involved'].add('medical_oncology')

            # Check for clinical trial
            if any(term in service_text + reason_text for term in ['clinical trial', 'protocol', 'study screening']):
                coordination['clinical_trial_screening'] = True

            # Check for tumor board/MDM
            if any(term in service_text + reason_text for term in ['tumor board', 'multidisciplinary', 'mdm']):
                coordination['multi_disciplinary_meeting'] = True

        coordination['services_involved'] = list(coordination['services_involved'])

        return coordination

    def validate_surgical_occurrence(self,
                                    patient_id: str,
                                    planned_surgery_date: datetime) -> Dict[str, Any]:
        """
        Validate that a planned surgery actually occurred by checking
        for expected post-operative service requests.
        """
        cascade = self.map_diagnostic_cascade(patient_id, planned_surgery_date)

        validation = {
            'surgery_likely_occurred': False,
            'evidence': [],
            'confidence': 0.0
        }

        # Check for post-op imaging (strongest evidence)
        if cascade['immediate_post_operative']:
            validation['surgery_likely_occurred'] = True
            validation['evidence'].append('post_operative_imaging_ordered')
            validation['confidence'] = 0.9

        # Check for treatment planning (moderate evidence)
        elif cascade['treatment_planning']:
            has_path_related = any(
                'pathology' in r['service'].lower()
                for r in cascade['treatment_planning']
            )
            if has_path_related:
                validation['surgery_likely_occurred'] = True
                validation['evidence'].append('pathology_follow_up')
                validation['confidence'] = 0.7

        return validation