"""
Pass 2: Structured Data Interrogation
Query Phase 1-2 data when document extraction fails
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from .extraction_result import PassResult
import pandas as pd

logger = logging.getLogger(__name__)

class StructuredDataQuerier:
    """Query structured data and timeline when document extraction fails"""

    def __init__(self, phase1_data: Dict, phase2_timeline: List, data_sources: Dict):
        self.phase1_data = phase1_data or {}
        self.phase2_timeline = phase2_timeline or []
        self.data_sources = data_sources or {}
        self.surgical_context = None  # Will be set per event

    def query_for_variable(self, variable: str, event_date: str, pass1_result: Any,
                          surgical_context: Optional[Dict] = None) -> PassResult:
        """
        Query structured data sources for variable hints with surgical context.

        Args:
            variable: Variable to extract
            event_date: Date of the event
            pass1_result: Result from Pass 1
            surgical_context: Dict containing prior surgeries, treatments, disease trajectory
        """
        result = PassResult(pass_number=2, method='structured_query')

        # Store surgical context for use in query methods
        self.surgical_context = surgical_context or {}

        # Parse event date
        try:
            event_dt = pd.to_datetime(event_date)
        except:
            logger.error(f"Could not parse event date: {event_date}")
            return result

        # Route to variable-specific query method
        query_methods = {
            'extent_of_tumor_resection': self._query_extent_of_resection,
            'tumor_location': self._query_tumor_location,
            'histopathology': self._query_histopathology,
            'who_grade': self._query_who_grade,
            'surgery_type': self._query_surgery_type,
            'specimen_to_cbtn': self._query_specimen_to_cbtn,
            'molecular_testing': self._query_molecular_testing
        }

        query_method = query_methods.get(variable, self._query_generic)
        return query_method(event_dt, result)

    def _query_extent_of_resection(self, event_dt: datetime, result: PassResult) -> PassResult:
        """
        Query for extent of resection from structured data.

        GOLD STANDARD HIERARCHY (per POST_OP_IMAGING_FINDINGS.md):
        1. Post-op MRI (24-72h) - confidence 0.95
        2. Post-op CT (24-72h) - confidence 0.85
        3. Pathology report - confidence 0.90
        4. Operative note/procedures - confidence 0.75
        5. Discharge summary - confidence 0.70
        """
        logger.info("Querying structured data for extent of resection")

        # =====================================================================
        # PRIORITY 1: POST-OP IMAGING (24-72 hours = GOLD STANDARD)
        # =====================================================================
        if 'imaging' in self.data_sources:
            imaging = self.data_sources['imaging']

            # Early post-op imaging (24-72 hours = 1-3 days) - GOLD STANDARD
            early_postop = imaging[
                (pd.to_datetime(imaging['imaging_date']) > event_dt) &
                (pd.to_datetime(imaging['imaging_date']) <= event_dt + timedelta(days=3))
            ]

            for _, img in early_postop.iterrows():
                img_date = pd.to_datetime(img['imaging_date'])
                days_post_surgery = (img_date - event_dt).days
                modality = str(img.get('modality', img.get('imaging_modality', ''))).upper()
                findings = str(img.get('result_information', img.get('result_display', ''))).lower()

                # Set confidence based on modality and timing
                if 'MR' in modality or 'MRI' in modality:
                    confidence = 0.95  # MRI is gold standard
                elif 'CT' in modality:
                    confidence = 0.85  # CT is secondary
                else:
                    confidence = 0.80  # Other modalities

                # Extract extent from imaging findings (comprehensive keyword detection)
                extent_found = False

                # Near-total / Gross total resection indicators
                if any(phrase in findings for phrase in [
                    'near total debulking', 'near-total debulking',
                    'substantial tumor debulking', 'substantial debulking',
                    'gross total resection', 'complete resection',
                    'no residual tumor', 'no residual enhancement',
                    'complete removal'
                ]):
                    result.add_candidate('GTR', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_gold_standard')
                    result.add_note(f"🏆 GOLD STANDARD: Post-op imaging at {days_post_surgery} days")
                    extent_found = True

                # Subtotal resection indicators
                elif any(phrase in findings for phrase in [
                    'subtotal resection', 'near total resection',
                    'small amount of residual', 'minimal residual',
                    'small residual tumor', 'small residual enhancement'
                ]):
                    result.add_candidate('STR', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_gold_standard')
                    result.add_note(f"🏆 GOLD STANDARD: Post-op imaging at {days_post_surgery} days")
                    extent_found = True

                # Partial resection indicators
                elif any(phrase in findings for phrase in [
                    'residual tumor', 'residual mass', 'residual enhancement',
                    'persistent tumor', 'remnant tumor',
                    'stable tumor', 'grossly stable'
                ]):
                    result.add_candidate('Partial', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_gold_standard')
                    result.add_note(f"🏆 GOLD STANDARD: Post-op imaging at {days_post_surgery} days")
                    extent_found = True

                if extent_found:
                    # If we found gold standard imaging, don't check procedures (imaging overrides)
                    logger.info(f"  ✓ GOLD STANDARD imaging found at {days_post_surgery} days post-op")
                    return result  # Early return - imaging is authoritative

            # Extended post-op window (4-7 days) - still high confidence
            extended_postop = imaging[
                (pd.to_datetime(imaging['imaging_date']) > event_dt + timedelta(days=3)) &
                (pd.to_datetime(imaging['imaging_date']) <= event_dt + timedelta(days=7))
            ]

            for _, img in extended_postop.iterrows():
                img_date = pd.to_datetime(img['imaging_date'])
                days_post_surgery = (img_date - event_dt).days
                modality = str(img.get('modality', img.get('imaging_modality', ''))).upper()
                findings = str(img.get('result_information', img.get('result_display', ''))).lower()

                # Slightly lower confidence for extended window
                if 'MR' in modality or 'MRI' in modality:
                    confidence = 0.90
                elif 'CT' in modality:
                    confidence = 0.80
                else:
                    confidence = 0.75

                # Same extraction logic but note it's extended window
                if any(phrase in findings for phrase in ['near total', 'gross total', 'complete resection', 'no residual']):
                    result.add_candidate('GTR', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_extended')
                elif any(phrase in findings for phrase in ['subtotal', 'minimal residual', 'small residual']):
                    result.add_candidate('STR', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_extended')
                elif any(phrase in findings for phrase in ['residual', 'remnant', 'persistent', 'stable']):
                    result.add_candidate('Partial', confidence,
                        f"Post-op {modality} ({days_post_surgery}d): {findings[:150]}",
                        'postop_imaging_extended')

        # =====================================================================
        # PRIORITY 2: OPERATIVE NOTES / PROCEDURES (only if no imaging found)
        # =====================================================================
        # Only check procedures if we didn't find authoritative post-op imaging
        if not result.candidates and 'procedures' in self.data_sources:
            procs = self.data_sources['procedures']
            event_procs = procs[
                (pd.to_datetime(procs['proc_performed_date_time']) >= event_dt - timedelta(days=1)) &
                (pd.to_datetime(procs['proc_performed_date_time']) <= event_dt + timedelta(days=1))
            ]

            for _, proc in event_procs.iterrows():
                proc_text = str(proc.get('proc_code_text', '')).lower()

                if 'gross total' in proc_text or 'complete resection' in proc_text:
                    result.add_candidate('GTR', 0.75, f"Procedure: {proc_text[:100]}", 'procedure_code')
                elif 'subtotal' in proc_text or 'near total' in proc_text:
                    result.add_candidate('STR', 0.75, f"Procedure: {proc_text[:100]}", 'procedure_code')
                elif 'partial' in proc_text:
                    result.add_candidate('Partial', 0.75, f"Procedure: {proc_text[:100]}", 'procedure_code')
                elif 'biopsy' in proc_text:
                    result.add_candidate('Biopsy only', 0.80, f"Procedure: {proc_text[:100]}", 'procedure_code')

            if result.candidates:
                result.add_note("⚠ Based on procedure codes only - post-op imaging would be more accurate")

        # Check for repeat surgeries (suggests incomplete resection)
        surgeries_within_30days = [e for e in self.phase2_timeline
                                   if e.event_type == 'surgical'
                                   and abs((e.event_date - event_dt).days) <= 30]

        if len(surgeries_within_30days) > 2:
            result.add_note(f"Multiple surgeries ({len(surgeries_within_30days)}) within 30 days suggests incomplete resection")
            if not result.candidates:
                result.add_candidate('STR', 0.5, f"{len(surgeries_within_30days)} surgeries in 30 days", 'inference')

        # Check for post-op radiation (suggests residual)
        radiation_events = [e for e in self.phase2_timeline
                           if 'radiation' in str(e.event_type).lower()
                           and (e.event_date - event_dt).days > 0
                           and (e.event_date - event_dt).days <= 90]

        if radiation_events:
            result.add_note(f"Post-op radiation within 90 days suggests residual tumor")
            if not result.candidates:
                result.add_candidate('STR', 0.5, "Post-op radiation indicates residual", 'inference')

        # =====================================================================
        # USE SURGICAL CONTEXT (prior surgeries, disease trajectory)
        # =====================================================================
        if self.surgical_context:
            surgery_number = self.surgical_context.get('surgery_number', 1)
            prior_surgeries = self.surgical_context.get('prior_surgeries', [])
            prior_treatments = self.surgical_context.get('prior_treatments', [])

            # Add contextual notes
            if surgery_number > 1:
                result.add_note(f"📍 Context: Surgery #{surgery_number} (recurrent disease)")

                # If prior surgery had incomplete resection, this surgery likely targeting residual
                if prior_surgeries:
                    last_surgery = prior_surgeries[-1]
                    last_extent = last_surgery.get('extent')
                    if last_extent and any(term in str(last_extent).lower() for term in ['partial', 'subtotal', 'str', 'biopsy']):
                        result.add_note(f"Prior surgery had {last_extent} - this surgery may be completion resection")

            if prior_treatments:
                treatment_types = [t.get('type', '') for t in prior_treatments]
                if 'radiation' in treatment_types or 'chemotherapy' in treatment_types:
                    result.add_note(f"Prior treatments: {', '.join(treatment_types)} - may affect resectability")

        return result

    def _query_tumor_location(self, event_dt: datetime, result: PassResult) -> PassResult:
        """Query for tumor location from structured data"""
        logger.info("Querying structured data for tumor location")

        # Check diagnoses for anatomical mentions
        if 'diagnoses' in self.data_sources:
            diagnoses = self.data_sources['diagnoses']

            anatomical_terms = {
                'frontal': ['frontal lobe', 'frontal'],
                'temporal': ['temporal lobe', 'temporal'],
                'parietal': ['parietal lobe', 'parietal'],
                'occipital': ['occipital lobe', 'occipital'],
                'cerebellum': ['cerebellar', 'cerebellum', 'posterior fossa'],
                'brainstem': ['brain stem', 'brainstem', 'pons', 'medulla'],
                'thalamus': ['thalamus', 'thalamic'],
                'basal_ganglia': ['basal ganglia']
            }

            for _, dx in diagnoses.iterrows():
                dx_text = str(dx.get('diagnosis_name', dx.get('icd10_display', ''))).lower()

                for location, keywords in anatomical_terms.items():
                    for keyword in keywords:
                        if keyword in dx_text:
                            result.add_candidate(
                                location.replace('_', ' ').title(),
                                0.6,
                                f"Diagnosis: {dx_text[:100]}",
                                'structured_data'
                            )

        # Check imaging for anatomical mentions
        if 'imaging' in self.data_sources:
            imaging = self.data_sources['imaging']
            preop_imaging = imaging[
                (pd.to_datetime(imaging['imaging_date']) <= event_dt) &
                (pd.to_datetime(imaging['imaging_date']) >= event_dt - timedelta(days=90))
            ]

            anatomical_terms = ['frontal', 'temporal', 'parietal', 'occipital',
                              'cerebellum', 'cerebellar', 'brainstem', 'thalamus']

            for _, img in preop_imaging.iterrows():
                findings = str(img.get('result_information', img.get('result_display', ''))).lower()

                for term in anatomical_terms:
                    if term in findings:
                        result.add_candidate(
                            term.title() + (' lobe' if term in ['frontal', 'temporal', 'parietal', 'occipital'] else ''),
                            0.7,
                            f"Pre-op imaging: {findings[:100]}",
                            'structured_data'
                        )

        # Check procedures for anatomical mentions
        if 'procedures' in self.data_sources:
            procs = self.data_sources['procedures']
            event_procs = procs[
                (pd.to_datetime(procs['proc_performed_date_time']) >= event_dt - timedelta(days=1)) &
                (pd.to_datetime(procs['proc_performed_date_time']) <= event_dt + timedelta(days=1))
            ]

            for _, proc in event_procs.iterrows():
                proc_text = str(proc.get('proc_code_text', '')).lower()

                if 'posterior fossa' in proc_text:
                    result.add_candidate('Cerebellum/Posterior Fossa', 0.8, f"Procedure: {proc_text[:100]}", 'structured_data')
                elif 'supratentorial' in proc_text:
                    result.add_note("Supratentorial location (need more specific data)")

        return result

    def _query_histopathology(self, event_dt: datetime, result: PassResult) -> PassResult:
        """
        Query for histopathology from structured data.

        DIAGNOSIS SOURCE HIERARCHY:
        1. Pathology reports - confidence 0.90
        2. ICD-10 diagnoses - confidence 0.70
        3. Problem list - confidence 0.50
        """
        logger.info("Querying structured data for histopathology")

        tumor_keywords = {
            'Glioblastoma': ['glioblastoma', 'gbm'],
            'Astrocytoma': ['astrocytoma'],
            'Pilocytic Astrocytoma': ['pilocytic'],
            'Ependymoma': ['ependymoma'],
            'Medulloblastoma': ['medulloblastoma'],
            'ATRT': ['atrt', 'rhabdoid'],
            'Craniopharyngioma': ['craniopharyngioma'],
            'DIPG': ['dipg', 'diffuse intrinsic pontine'],
            'Oligodendroglioma': ['oligodendroglioma'],
            'Ganglioglioma': ['ganglioglioma']
        }

        # PRIORITY 1: Check for pathology procedure/specimen
        if 'procedures' in self.data_sources:
            procs = self.data_sources['procedures']
            path_procs = procs[
                (pd.to_datetime(procs['proc_performed_date_time']) >= event_dt - timedelta(days=1)) &
                (pd.to_datetime(procs['proc_performed_date_time']) <= event_dt + timedelta(days=14)) &
                (procs['proc_code_text'].str.contains('pathology|frozen section|specimen', case=False, na=False))
            ]

            if not path_procs.empty:
                result.add_flag('pathology_procedure_exists', True)
                result.add_recommendation('🏆 Pathology report exists - retrieve and parse (highest confidence source)')

        # PRIORITY 2: ICD-10 coded diagnoses (confidence 0.70)
        if 'diagnoses' in self.data_sources:
            diagnoses = self.data_sources['diagnoses']

            # Filter for diagnoses with ICD-10 codes (higher confidence)
            icd10_diagnoses = diagnoses[diagnoses.get('icd10_code', pd.Series()).notna()]

            for _, dx in icd10_diagnoses.iterrows():
                dx_text = str(dx.get('diagnosis_name', dx.get('icd10_display', ''))).lower()
                dx_code = str(dx.get('icd10_code', '')).lower()
                dx_source = str(dx.get('diagnosis_source', 'ICD-10')).lower()

                for tumor_type, keywords in tumor_keywords.items():
                    for keyword in keywords:
                        if keyword in dx_text or keyword in dx_code:
                            result.add_candidate(
                                tumor_type,
                                0.70,
                                f"ICD-10 Diagnosis: {dx_text[:100]} ({dx_code})",
                                'icd10_coded_diagnosis'
                            )

        # PRIORITY 3: Problem list diagnoses (confidence 0.50)
        if 'problem_list_diagnoses' in self.data_sources:
            prob_list = self.data_sources['problem_list_diagnoses']

            for _, prob in prob_list.iterrows():
                prob_text = str(prob.get('diagnosis_name', prob.get('problem_text', ''))).lower()

                for tumor_type, keywords in tumor_keywords.items():
                    for keyword in keywords:
                        if keyword in prob_text:
                            result.add_candidate(
                                tumor_type,
                                0.50,
                                f"Problem List: {prob_text[:100]}",
                                'problem_list'
                            )

        return result

    def _query_who_grade(self, event_dt: datetime, result: PassResult) -> PassResult:
        """
        Query for WHO grade from structured data.

        DIAGNOSIS SOURCE HIERARCHY:
        1. Pathology reports - confidence 0.90
        2. ICD-10 diagnoses - confidence 0.70
        3. Problem list - confidence 0.50
        """
        logger.info("Querying structured data for WHO grade")

        grade_keywords = {
            'Grade I': ['grade 1', 'grade i', 'low grade', 'pilocytic'],
            'Grade II': ['grade 2', 'grade ii', 'diffuse astrocytoma'],
            'Grade III': ['grade 3', 'grade iii', 'anaplastic'],
            'Grade IV': ['grade 4', 'grade iv', 'glioblastoma', 'gbm']
        }

        # PRIORITY 1: Check for pathology procedure (flag that pathology exists)
        if 'procedures' in self.data_sources:
            procs = self.data_sources['procedures']
            path_procs = procs[
                (pd.to_datetime(procs['proc_performed_date_time']) >= event_dt - timedelta(days=1)) &
                (pd.to_datetime(procs['proc_performed_date_time']) <= event_dt + timedelta(days=14)) &
                (procs['proc_code_text'].str.contains('pathology|frozen section|specimen', case=False, na=False))
            ]

            if not path_procs.empty:
                result.add_recommendation('🏆 Pathology report exists - retrieve for WHO grade (highest confidence source)')

        # PRIORITY 2: ICD-10 coded diagnoses (confidence 0.70)
        if 'diagnoses' in self.data_sources:
            diagnoses = self.data_sources['diagnoses']

            # Filter for diagnoses with ICD-10 codes
            icd10_diagnoses = diagnoses[diagnoses.get('icd10_code', pd.Series()).notna()]

            for _, dx in icd10_diagnoses.iterrows():
                dx_text = str(dx.get('diagnosis_name', dx.get('icd10_display', ''))).lower()

                for grade, keywords in grade_keywords.items():
                    for keyword in keywords:
                        if keyword in dx_text:
                            result.add_candidate(
                                grade,
                                0.70,
                                f"ICD-10 Diagnosis: {dx_text[:100]}",
                                'icd10_coded_diagnosis'
                            )

        # PRIORITY 3: Problem list diagnoses (confidence 0.50)
        if 'problem_list_diagnoses' in self.data_sources:
            prob_list = self.data_sources['problem_list_diagnoses']

            for _, prob in prob_list.iterrows():
                prob_text = str(prob.get('diagnosis_name', prob.get('problem_text', ''))).lower()

                for grade, keywords in grade_keywords.items():
                    for keyword in keywords:
                        if keyword in prob_text:
                            result.add_candidate(
                                grade,
                                0.50,
                                f"Problem List: {prob_text[:100]}",
                                'problem_list'
                            )

        return result

    def _query_surgery_type(self, event_dt: datetime, result: PassResult) -> PassResult:
        """Query for surgery type from structured data"""
        logger.info("Querying structured data for surgery type")

        # Check procedures
        if 'procedures' in self.data_sources:
            procs = self.data_sources['procedures']
            event_procs = procs[
                (pd.to_datetime(procs['proc_performed_date_time']) >= event_dt - timedelta(days=1)) &
                (pd.to_datetime(procs['proc_performed_date_time']) <= event_dt + timedelta(days=1))
            ]

            surgery_keywords = {
                'Craniotomy': ['craniotomy'],
                'Craniectomy': ['craniectomy'],
                'Shunt placement': ['shunt', 'ventriculostomy', 'vp shunt'],
                'Biopsy': ['biopsy'],
                'Debulking': ['debulking']
            }

            for _, proc in event_procs.iterrows():
                proc_text = str(proc.get('proc_code_text', '')).lower()

                for surgery_type, keywords in surgery_keywords.items():
                    for keyword in keywords:
                        if keyword in proc_text:
                            result.add_candidate(
                                surgery_type,
                                0.8,
                                f"Procedure: {proc_text[:100]}",
                                'structured_data'
                            )

        return result

    def _query_specimen_to_cbtn(self, event_dt: datetime, result: PassResult) -> PassResult:
        """Query for specimen to CBTN from structured data"""
        # This would require CBTN-specific data sources
        result.add_note("CBTN specimen data not available in structured sources")
        return result

    def _query_molecular_testing(self, event_dt: datetime, result: PassResult) -> PassResult:
        """Query for molecular testing from structured data"""
        logger.info("Querying structured data for molecular testing")

        # Check Phase 1 for molecular tests
        molecular_tests = self.phase1_data.get('molecular_tests', [])

        if molecular_tests:
            for test in molecular_tests:
                result.add_candidate(
                    f"{test.get('marker', 'Unknown')}: {test.get('result', 'Unknown')}",
                    0.8,
                    f"Molecular test: {test}",
                    'structured_data'
                )
        else:
            result.add_note("No molecular testing data in Phase 1")

        return result

    def _query_generic(self, event_dt: datetime, result: PassResult) -> PassResult:
        """Generic query for unknown variables"""
        result.add_note("No structured data query method defined for this variable")
        return result
