"""
Test date of birth and age extraction
"""

from pathlib import Path
from enhanced_clinical_prioritization import EnhancedClinicalPrioritization

staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
patient_id = "e4BwD8ZYDBccepXcJ.Ilo3w3"

enhancer = EnhancedClinicalPrioritization(staging_path)
endpoints = enhancer.extract_survival_endpoints(patient_id)

print("="*60)
print("PATIENT DEMOGRAPHICS AND SURVIVAL ENDPOINTS")
print("="*60)

print(f"\nPatient ID: {patient_id}")
print(f"Date of Birth: {endpoints.get('date_of_birth', 'NOT FOUND')}")
print(f"Diagnosis Date: {endpoints.get('diagnosis_date', 'NOT FOUND')}")
print(f"Age at Diagnosis: {endpoints.get('age_at_diagnosis', 'NOT CALCULATED')} years")
print(f"Current Age or Age at Death: {endpoints.get('current_age_or_age_at_death', 'NOT CALCULATED')} years")

print(f"\nVital Status: {endpoints.get('vital_status', 'unknown')}")
print(f"Death Date: {endpoints.get('death_date', 'N/A')}")

print(f"\nLast Contact Information:")
print(f"  Last Clinical Contact: {endpoints.get('last_clinical_contact', 'unknown')}")
print(f"  Last Imaging: {endpoints.get('last_imaging', 'unknown')}")
print(f"  Last Treatment: {endpoints.get('last_treatment', 'unknown')}")
print(f"  Last Lab: {endpoints.get('last_lab', 'unknown')}")
print(f"  Last Known Alive: {endpoints.get('last_known_alive', 'unknown')}")

# Calculate survival time if diagnosis date available
if endpoints.get('diagnosis_date') and endpoints.get('last_known_alive'):
    import pandas as pd
    diagnosis = pd.to_datetime(endpoints['diagnosis_date'], utc=True)
    last_contact = pd.to_datetime(endpoints['last_known_alive'], utc=True)
    survival_days = (last_contact - diagnosis).days
    survival_years = round(survival_days / 365.25, 1)
    print(f"\nSurvival from Diagnosis: {survival_days} days ({survival_years} years)")