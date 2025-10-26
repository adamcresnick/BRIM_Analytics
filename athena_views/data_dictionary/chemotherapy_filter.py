"""
Chemotherapy Filter Module
===========================
Filters medications to identify chemotherapy agents using RADIANT unified drug reference system.

Uses 3-strategy approach:
1. RxNorm ingredient matching (drugs.csv)
2. Product-to-ingredient mapping (rxnorm_code_map.csv)
3. Name-based matching (drug_alias.csv)

Author: RADIANT PCA Project
Date: October 18, 2025
"""

import pandas as pd
import re
from pathlib import Path
from typing import List, Dict, Set, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChemotherapyFilter:
    """
    Filter medications to identify chemotherapy agents using unified drug reference.
    """

    def __init__(self, reference_dir: str = None):
        """
        Initialize chemotherapy filter with reference files.

        Args:
            reference_dir: Directory containing drugs.csv, drug_alias.csv, rxnorm_code_map.csv
        """
        if reference_dir is None:
            reference_dir = Path(__file__).parent / 'chemo_reference'
        else:
            reference_dir = Path(reference_dir)

        self.reference_dir = reference_dir
        self.drugs_df = None
        self.drug_alias_df = None
        self.rxnorm_map_df = None

        # Caches
        self.valid_rxnorm_in = None
        self.product_to_ingredient = None
        self.alias_lookup = None

        # Load reference data
        self._load_reference_data()
        self._build_lookups()

    def _load_reference_data(self):
        """Load RADIANT unified drug reference files."""
        logger.info(f"Loading chemotherapy reference files from {self.reference_dir}")

        # Load drugs.csv
        drugs_path = self.reference_dir / 'drugs.csv'
        if not drugs_path.exists():
            raise FileNotFoundError(f"drugs.csv not found at {drugs_path}")
        self.drugs_df = pd.read_csv(drugs_path)
        logger.info(f"  Loaded {len(self.drugs_df)} drugs")

        # Load drug_alias.csv
        alias_path = self.reference_dir / 'drug_alias.csv'
        if not alias_path.exists():
            raise FileNotFoundError(f"drug_alias.csv not found at {alias_path}")
        self.drug_alias_df = pd.read_csv(alias_path)
        logger.info(f"  Loaded {len(self.drug_alias_df)} drug aliases")

        # Load rxnorm_code_map.csv
        rxnorm_path = self.reference_dir / 'rxnorm_code_map.csv'
        if not rxnorm_path.exists():
            raise FileNotFoundError(f"rxnorm_code_map.csv not found at {rxnorm_path}")
        self.rxnorm_map_df = pd.read_csv(rxnorm_path)
        logger.info(f"  Loaded {len(self.rxnorm_map_df)} RxNorm mappings")

    def _build_lookups(self):
        """Build lookup dictionaries for fast filtering."""
        logger.info("Building chemotherapy lookup tables...")

        # Step 1: Identify supportive care drug base names (normalized_key)
        supportive_care_drugs = self.drugs_df[
            self.drugs_df['sources'].str.contains('Supportive_Care', na=False)
        ].copy()

        supportive_care_base_names = set(
            supportive_care_drugs['normalized_key'].dropna()
        )
        logger.info(f"  Found {len(supportive_care_base_names)} supportive care base names")

        # Step 2: Build exclusion function that checks if drug name starts with supportive care base
        def is_supportive_care_derivative(row):
            """Check if drug is supportive care or derivative."""
            # Direct match
            if 'Supportive_Care' in str(row.get('sources', '')):
                return True
            # Check if normalized_key starts with any supportive care base name
            normalized = str(row.get('normalized_key', ''))
            for sc_base in supportive_care_base_names:
                if normalized.startswith(sc_base):
                    return True
            return False

        # Step 3: Exclude supportive care drugs and derivatives
        chemo_mask = (
            (self.drugs_df['approval_status'].isin(['FDA_approved', 'investigational']))
        )
        supportive_care_mask = self.drugs_df.apply(is_supportive_care_derivative, axis=1)
        chemo_drugs = self.drugs_df[chemo_mask & ~supportive_care_mask].copy()

        logger.info(f"  Found {len(chemo_drugs)} chemotherapy drugs (excluding supportive care and derivatives)")

        # Build RxNorm ingredient lookup with therapeutic_normalized mapping
        self.valid_rxnorm_in = set(
            chemo_drugs['rxnorm_in'].dropna().astype(int)
        )

        # Build RxNorm -> therapeutic_normalized mapping
        self.rxnorm_to_therapeutic = {}
        for _, row in chemo_drugs.iterrows():
            if pd.notna(row['rxnorm_in']):
                rxnorm_cui = int(row['rxnorm_in'])
                therapeutic_norm = row.get('therapeutic_normalized', row['preferred_name'])
                self.rxnorm_to_therapeutic[rxnorm_cui] = therapeutic_norm

        logger.info(f"  Built RxNorm ingredient lookup: {len(self.valid_rxnorm_in)} codes")

        # Build product-to-ingredient mapping
        self.product_to_ingredient = {}
        for _, row in self.rxnorm_map_df.iterrows():
            if pd.notna(row['ingredient_rxcui']) and pd.notna(row['code_cui']):
                ingredient_cui = int(row['ingredient_rxcui'])
                if ingredient_cui in self.valid_rxnorm_in:
                    self.product_to_ingredient[int(row['code_cui'])] = ingredient_cui

        logger.info(f"  Built product-to-ingredient mapping: {len(self.product_to_ingredient)} products")

        # Build drug_id -> therapeutic_normalized mapping
        self.drug_id_to_therapeutic = {}
        for _, row in chemo_drugs.iterrows():
            if pd.notna(row['drug_id']):
                therapeutic_norm = row.get('therapeutic_normalized', row['preferred_name'])
                self.drug_id_to_therapeutic[row['drug_id']] = therapeutic_norm

        # Build drug name alias lookup
        chemo_drug_ids = set(chemo_drugs['drug_id'].dropna())
        chemo_aliases = self.drug_alias_df[
            (self.drug_alias_df['drug_id'].notna()) &
            (self.drug_alias_df['drug_id'].isin(chemo_drug_ids))
        ].copy()

        self.alias_lookup = {}
        for _, row in chemo_aliases.iterrows():
            # Skip if drug_id is NaN
            if pd.isna(row.get('drug_id')):
                continue

            normalized = row.get('normalized_key')
            if pd.isna(normalized):
                # Fall back to normalizing the alias manually
                normalized = self._normalize_text(str(row.iloc[1]))
            if normalized:
                self.alias_lookup[normalized] = row['drug_id']

        logger.info(f"  Built drug name alias lookup: {len(self.alias_lookup)} aliases")

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for matching: lowercase, remove spaces/punctuation.
        Matches normalization in drug_alias.csv normalized_key.
        """
        if pd.isna(text) or text == '':
            return ''
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9]', '', text)
        return text

    def _parse_rxnorm_codes(self, rx_norm_codes_str: str) -> List[int]:
        """Parse semicolon-separated RxNorm codes into list of integers."""
        if pd.isna(rx_norm_codes_str) or rx_norm_codes_str == '':
            return []

        codes = []
        for code in str(rx_norm_codes_str).split(';'):
            code = code.strip()
            if code and code.isdigit():
                codes.append(int(code))
        return codes

    def is_chemotherapy(
        self,
        medication_name: str,
        rx_norm_codes: str = None
    ) -> Dict[str, Any]:
        """
        Check if a medication is chemotherapy.

        Args:
            medication_name: Medication name
            rx_norm_codes: Semicolon-separated RxNorm codes (optional)

        Returns:
            Dict with is_chemo (bool), strategy (str), confidence (str)
        """
        # Strategy 1: RxNorm ingredient matching
        if rx_norm_codes:
            codes = self._parse_rxnorm_codes(rx_norm_codes)
            matched_ingredients = [c for c in codes if c in self.valid_rxnorm_in]
            if matched_ingredients:
                # Get therapeutic_normalized for first matched ingredient
                therapeutic_norm = self.rxnorm_to_therapeutic.get(matched_ingredients[0])
                return {
                    'is_chemo': True,
                    'strategy': 'rxnorm_ingredient',
                    'matched_codes': matched_ingredients,
                    'therapeutic_normalized': therapeutic_norm,
                    'confidence': 'high'
                }

        # Strategy 2: Product code mapping
        if rx_norm_codes:
            codes = self._parse_rxnorm_codes(rx_norm_codes)
            matched_products = [c for c in codes if c in self.product_to_ingredient]
            if matched_products:
                # Get therapeutic_normalized for first mapped ingredient
                mapped_ingredient = self.product_to_ingredient[matched_products[0]]
                therapeutic_norm = self.rxnorm_to_therapeutic.get(mapped_ingredient)
                return {
                    'is_chemo': True,
                    'strategy': 'product_code_mapping',
                    'matched_codes': matched_products,
                    'mapped_ingredients': [self.product_to_ingredient[c] for c in matched_products],
                    'therapeutic_normalized': therapeutic_norm,
                    'confidence': 'high'
                }

        # Strategy 3: Name-based matching (exact + substring)
        normalized_name = self._normalize_text(medication_name)

        # Try exact match first
        if normalized_name in self.alias_lookup:
            drug_id = self.alias_lookup[normalized_name]
            therapeutic_norm = self.drug_id_to_therapeutic.get(drug_id)
            return {
                'is_chemo': True,
                'strategy': 'drug_alias_exact',
                'matched_alias': medication_name,
                'drug_id': drug_id,
                'therapeutic_normalized': therapeutic_norm,
                'confidence': 'medium'
            }

        # Try substring match (e.g., "bevacizumab" in "bevacizumabinfusion")
        for alias_key, drug_id in self.alias_lookup.items():
            # Only match if alias is substantial (>= 8 chars to avoid false positives)
            if len(alias_key) >= 8 and alias_key in normalized_name:
                therapeutic_norm = self.drug_id_to_therapeutic.get(drug_id)
                return {
                    'is_chemo': True,
                    'strategy': 'drug_alias_substring',
                    'matched_alias': alias_key,
                    'drug_id': drug_id,
                    'therapeutic_normalized': therapeutic_norm,
                    'confidence': 'medium'
                }

        # No match
        return {
            'is_chemo': False,
            'strategy': None,
            'confidence': None
        }

    def filter_medications(
        self,
        medications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter list of medications to return only chemotherapy agents.

        Args:
            medications: List of medication dicts with 'medication_name' and optionally 'rx_norm_codes'

        Returns:
            List of chemotherapy medications with added filter metadata
        """
        chemo_medications = []

        for med in medications:
            medication_name = med.get('medication_name', '')
            rx_norm_codes = med.get('rx_norm_codes', '')

            result = self.is_chemotherapy(medication_name, rx_norm_codes)

            if result['is_chemo']:
                # Add filter metadata
                med_with_metadata = med.copy()
                med_with_metadata['chemo_filter'] = result
                chemo_medications.append(med_with_metadata)

        logger.info(f"Filtered {len(medications)} medications → {len(chemo_medications)} chemotherapy agents")

        return chemo_medications

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about loaded reference data."""
        return {
            'total_drugs': len(self.drugs_df),
            'chemotherapy_drugs': len(self.drugs_df[
                (self.drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
                (self.drugs_df['is_supportive_care'] == False)
            ]),
            'rxnorm_ingredient_codes': len(self.valid_rxnorm_in),
            'product_mappings': len(self.product_to_ingredient),
            'drug_aliases': len(self.alias_lookup)
        }


# ==================================================================================
# EXAMPLE USAGE
# ==================================================================================

if __name__ == '__main__':
    # Initialize filter
    chemo_filter = ChemotherapyFilter()

    # Print statistics
    print("\n=== Chemotherapy Filter Statistics ===")
    stats = chemo_filter.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test medications
    test_medications = [
        {'medication_name': 'vinBLAStine injection', 'rx_norm_codes': '11124'},
        {'medication_name': 'bevacizumab infusion', 'rx_norm_codes': '354426'},
        {'medication_name': 'amOXicillin suspension', 'rx_norm_codes': '723'},
        {'medication_name': 'acetaminophen tablet', 'rx_norm_codes': '161'},
    ]

    print("\n=== Testing Medications ===")
    for med in test_medications:
        result = chemo_filter.is_chemotherapy(
            med['medication_name'],
            med['rx_norm_codes']
        )
        print(f"{med['medication_name']}: {result}")

    # Filter medications
    print("\n=== Filtering Medication List ===")
    chemo_meds = chemo_filter.filter_medications(test_medications)
    print(f"Chemotherapy medications: {len(chemo_meds)}")
    for med in chemo_meds:
        print(f"  - {med['medication_name']} (strategy: {med['chemo_filter']['strategy']})")
