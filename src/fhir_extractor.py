"""
FHIR Extractor Module
=====================

Extract structured clinical data from Athena FHIR tables.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd


class FHIRExtractor:
    """
    Extract structured data from FHIR resources in Athena.
    
    This class handles queries for:
    - Patient demographics
    - Surgical procedures with dates
    - Diagnoses/conditions with ICD-10 codes
    - Medications with RxNorm codes
    - Clinical notes metadata (DocumentReference)
    - Binary content extraction
    """
    
    def __init__(self, connection):
        """
        Initialize FHIR extractor with database connection.
        
        Args:
            connection: Database connection object (e.g., pyathena, sqlalchemy)
        """
        self.conn = connection
    
    def extract_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """
        Extract complete clinical context for a patient.
        
        Args:
            patient_id: FHIR Patient resource ID
            
        Returns:
            Dictionary with keys: demographics, surgeries, diagnoses, medications
        """
        
        context = {
            'patient_id': patient_id,
            'demographics': self.get_demographics(patient_id),
            'surgeries': self.get_surgical_procedures(patient_id),
            'diagnoses': self.get_diagnoses(patient_id),
            'medications': self.get_medications(patient_id),
            'encounters': self.get_encounters(patient_id),
        }
        
        return context
    
    def get_demographics(self, patient_id: str) -> Dict[str, Any]:
        """
        Extract patient demographics.
        
        Returns:
            Dict with birth_date, gender, race, ethnicity
        """
        
        query = """
        SELECT 
            id,
            birthDate as birth_date,
            gender,
            -- Extract race from extension (simplified)
            -- Actual extraction depends on FHIR extension structure
            extension as race_ethnicity_extensions
        FROM patient
        WHERE id = %(patient_id)s
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        
        if result.empty:
            return {}
        
        return result.iloc[0].to_dict()
    
    def get_surgical_procedures(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Extract all surgical procedures with dates.
        
        Returns:
            List of procedures with date, code, and description
        """
        
        query = """
        SELECT 
            p.id as procedure_id,
            p.performedDateTime as procedure_date,
            p.code.text as procedure_description,
            p.code.coding[1].code as procedure_code,
            p.code.coding[1].system as coding_system,
            p.status,
            p.category.text as category
        FROM procedure p
        WHERE p.subject.reference = CONCAT('Patient/', %(patient_id)s)
            AND LOWER(p.category.text) LIKE '%%surg%%'
            OR LOWER(p.code.text) LIKE '%%craniotomy%%'
            OR LOWER(p.code.text) LIKE '%%resection%%'
        ORDER BY p.performedDateTime
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        return result.to_dict('records')
    
    def get_diagnoses(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Extract diagnoses/conditions with ICD-10 codes.
        
        Returns:
            List of conditions with dates, ICD-10, SNOMED codes
        """
        
        query = """
        SELECT 
            c.id as condition_id,
            c.code.text as diagnosis_text,
            c.code.coding[1].code as icd10_code,
            c.code.coding[1].display as icd10_display,
            c.onsetDateTime as onset_date,
            c.recordedDate as recorded_date,
            c.clinicalStatus.text as clinical_status,
            c.verificationStatus.text as verification_status,
            c.category[1].text as category
        FROM condition c
        WHERE c.subject.reference = CONCAT('Patient/', %(patient_id)s)
        ORDER BY c.recordedDate DESC
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        return result.to_dict('records')
    
    def get_medications(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Extract medications with RxNorm codes.
        
        Returns:
            List of medications with dates, RxNorm codes, and dosages
        """
        
        query = """
        SELECT 
            mr.id as medication_request_id,
            mr.authoredOn as authored_date,
            mr.medicationReference.display as medication_name,
            m.id as medication_id,
            mcc.code_coding_code as rxnorm_code,
            mcc.code_coding_display as rxnorm_display,
            mr.status,
            mr.intent,
            mr.encounter.reference as encounter_reference
        FROM medicationrequest mr
        LEFT JOIN medication m 
            ON m.id = mr.medicationReference.reference
        LEFT JOIN medication_code_coding mcc 
            ON mcc.medication_id = m.id
            AND mcc.code_coding_system = 'http://www.nlm.nih.gov/research/umls/rxnorm'
        WHERE mr.subject.reference = CONCAT('Patient/', %(patient_id)s)
        ORDER BY mr.authoredOn
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        return result.to_dict('records')
    
    def get_encounters(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Extract encounter information.
        
        Returns:
            List of encounters with dates, types, and locations
        """
        
        query = """
        SELECT 
            e.id as encounter_id,
            e.period.start as period_start,
            e.period.end as period_end,
            e.class.display as class_display,
            e.type[1].text as encounter_type,
            e.status,
            e.serviceType.text as service_type
        FROM encounter e
        WHERE e.subject.reference = CONCAT('Patient/', %(patient_id)s)
        ORDER BY e.period.start
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        return result.to_dict('records')
    
    def discover_clinical_notes(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Discover all DocumentReference records for a patient.
        
        Returns:
            List of document metadata with Binary references
        """
        
        query = """
        SELECT 
            dr.id as document_id,
            dr.date as document_date,
            dr.type.text as document_type,
            dr.category[1].text as category,
            dr.status,
            dr.description,
            -- Extract Binary reference from content array
            dr.content[1].attachment.url as binary_url,
            dr.content[1].attachment.contentType as content_type,
            dr.content[1].attachment.size as content_size,
            dr.context.encounter[1].reference as encounter_reference
        FROM documentreference dr
        WHERE dr.subject.reference = CONCAT('Patient/', %(patient_id)s)
            AND dr.status = 'current'
        ORDER BY dr.date
        """
        
        result = pd.read_sql(query, self.conn, params={'patient_id': patient_id})
        return result.to_dict('records')
    
    def extract_binary_content(self, binary_id: str, max_size_mb: float = 10.0) -> Optional[str]:
        """
        Extract and decode Binary content.
        
        Args:
            binary_id: Binary resource ID
            max_size_mb: Maximum size to extract (safety limit)
            
        Returns:
            Decoded text content or None if too large/unavailable
        """
        
        import base64
        
        query = """
        SELECT 
            id,
            contentType as content_type,
            LENGTH(data) as size_bytes,
            data
        FROM binary
        WHERE id = %(binary_id)s
        """
        
        result = pd.read_sql(query, self.conn, params={'binary_id': binary_id})
        
        if result.empty:
            return None
        
        row = result.iloc[0]
        size_mb = row['size_bytes'] / (1024 * 1024)
        
        if size_mb > max_size_mb:
            print(f"Warning: Binary {binary_id} is {size_mb:.2f}MB (max: {max_size_mb}MB), skipping")
            return None
        
        try:
            # Decode base64 content
            content = base64.b64decode(row['data']).decode('utf-8', errors='ignore')
            return content
        except Exception as e:
            print(f"Error decoding Binary {binary_id}: {e}")
            return None
    
    def assign_surgery_number(self, document_date: datetime, surgeries: List[Dict]) -> str:
        """
        Assign a document to a surgery based on temporal proximity.
        
        Args:
            document_date: Date of the document
            surgeries: List of surgical procedures with dates
            
        Returns:
            Surgery number as string ('1', '2', '3', etc.) or 'other'
        """
        
        if not surgeries:
            return 'other'
        
        # Sort surgeries by date
        sorted_surgeries = sorted(surgeries, key=lambda x: x['procedure_date'])
        
        # Find closest surgery within reasonable time window (±90 days)
        from datetime import timedelta
        
        for idx, surgery in enumerate(sorted_surgeries, start=1):
            surgery_date = pd.to_datetime(surgery['procedure_date'])
            doc_date = pd.to_datetime(document_date)
            
            days_diff = abs((doc_date - surgery_date).days)
            
            # Documents within 90 days of surgery are assigned to that surgery
            if days_diff <= 90:
                return str(idx)
        
        # If not close to any surgery, assign to nearest
        closest_surgery = min(
            enumerate(sorted_surgeries, start=1),
            key=lambda x: abs((pd.to_datetime(x[1]['procedure_date']) - pd.to_datetime(document_date)).days)
        )
        
        return str(closest_surgery[0])
    
    def get_relevant_diagnosis(self, document_date: datetime, diagnoses: List[Dict]) -> str:
        """
        Get the most relevant diagnosis for a document date.
        
        Returns the diagnosis recorded closest to (but not after) the document date.
        """
        
        if not diagnoses:
            return ''
        
        doc_date = pd.to_datetime(document_date)
        
        # Filter to diagnoses before or on document date
        relevant = [
            d for d in diagnoses 
            if pd.to_datetime(d.get('recorded_date', d.get('onset_date'))) <= doc_date
        ]
        
        if not relevant:
            # If no diagnosis before document, return earliest diagnosis
            return diagnoses[0].get('diagnosis_text', '')
        
        # Return most recent diagnosis before document date
        closest = max(
            relevant,
            key=lambda x: pd.to_datetime(x.get('recorded_date', x.get('onset_date')))
        )
        
        return closest.get('diagnosis_text', '')
    
    def extract_who_grade(self, diagnosis_text: str) -> str:
        """
        Extract WHO grade from diagnosis text.
        
        Args:
            diagnosis_text: Diagnosis description
            
        Returns:
            WHO grade ('I', 'II', 'III', 'IV') or empty string
        """
        
        import re
        
        if not diagnosis_text:
            return ''
        
        # Look for WHO grade patterns
        patterns = [
            r'WHO\s+[Gg]rade\s+([IVX]+)',
            r'[Gg]rade\s+([IVX]+)',
            r'WHO\s+([IVX]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, diagnosis_text)
            if match:
                grade = match.group(1).upper()
                # Normalize to Roman numerals
                if grade in ['I', 'II', 'III', 'IV']:
                    return grade
        
        return ''
    
    def get_active_medications(self, document_date: datetime, medications: List[Dict], window_days: int = 30) -> List[str]:
        """
        Get medications active around document date.
        
        Args:
            document_date: Date of document
            medications: List of all medications
            window_days: Days before/after to consider active
            
        Returns:
            List of medication names
        """
        
        from datetime import timedelta
        
        doc_date = pd.to_datetime(document_date)
        active = []
        
        for med in medications:
            med_date = pd.to_datetime(med.get('authored_date'))
            
            if not pd.isna(med_date):
                days_diff = abs((doc_date - med_date).days)
                
                if days_diff <= window_days:
                    med_name = med.get('medication_name', '')
                    if med_name:
                        active.append(med_name)
        
        return list(set(active))  # Remove duplicates
