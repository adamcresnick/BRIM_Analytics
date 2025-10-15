"""
Standardized Chemotherapy Identification Module
================================================
Based on RADIANT unified drug reference system
Implements comprehensive multi-strategy identification
"""

import pandas as pd
import re
import logging
from typing import Dict, List, Set, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ChemotherapyIdentifier:
    """
    Standardized chemotherapy identification using multiple strategies:
    1. Direct medication name matching
    2. Care plan ONCOLOGY TREATMENT category
    3. Care plan title drug name extraction
    4. RxNorm code matching (if reference available)
    5. Reason code filtering
    """

    # Comprehensive chemotherapy keywords based on RADIANT reference
    CHEMO_KEYWORDS = {
        # Anti-VEGF agents
        'bevacizumab': ['bevacizumab', 'avastin'],

        # MEK inhibitors
        'selumetinib': ['selumetinib', 'koselugo'],
        'trametinib': ['trametinib', 'mekinist'],
        'cobimetinib': ['cobimetinib', 'cotellic'],

        # BRAF inhibitors
        'dabrafenib': ['dabrafenib', 'tafinlar'],
        'vemurafenib': ['vemurafenib', 'zelboraf'],

        # Vinca alkaloids
        'vincristine': ['vincristine', 'oncovin'],
        'vinblastine': ['vinblastine', 'velban'],
        'vinorelbine': ['vinorelbine', 'navelbine'],

        # Alkylating agents
        'temozolomide': ['temozolomide', 'temodar'],
        'lomustine': ['lomustine', 'ccnu', 'ceenu'],
        'carmustine': ['carmustine', 'bcnu', 'gliadel'],
        'procarbazine': ['procarbazine', 'matulane'],
        'thiotepa': ['thiotepa', 'tepadina'],

        # Platinum compounds
        'carboplatin': ['carboplatin', 'paraplatin'],
        'cisplatin': ['cisplatin', 'platinol'],

        # Topoisomerase inhibitors
        'etoposide': ['etoposide', 'vepesid', 'toposar'],
        'irinotecan': ['irinotecan', 'camptosar'],
        'topotecan': ['topotecan', 'hycamtin'],

        # Antimetabolites
        'methotrexate': ['methotrexate', 'trexall'],
        'pemetrexed': ['pemetrexed', 'alimta'],
        '5-fluorouracil': ['fluorouracil', '5-fu', 'adrucil'],
        'capecitabine': ['capecitabine', 'xeloda'],

        # mTOR inhibitors
        'everolimus': ['everolimus', 'afinitor'],
        'sirolimus': ['sirolimus', 'rapamune'],

        # Other targeted therapies
        'imatinib': ['imatinib', 'gleevec'],
        'regorafenib': ['regorafenib', 'stivarga'],
        'sunitinib': ['sunitinib', 'sutent'],
        'lapatinib': ['lapatinib', 'tykerb'],

        # Immunotherapy agents
        'pembrolizumab': ['pembrolizumab', 'keytruda'],
        'nivolumab': ['nivolumab', 'opdivo'],
        'ipilimumab': ['ipilimumab', 'yervoy'],
        'atezolizumab': ['atezolizumab', 'tecentriq'],

        # Other chemotherapy
        'cyclophosphamide': ['cyclophosphamide', 'cytoxan'],
        'ifosfamide': ['ifosfamide', 'ifex'],
        'doxorubicin': ['doxorubicin', 'adriamycin'],
        'bleomycin': ['bleomycin', 'blenoxane']
    }

    # Supportive care medications to exclude
    SUPPORTIVE_CARE = [
        'dexamethasone', 'prednisone', 'methylprednisolone',  # Steroids
        'ondansetron', 'granisetron', 'palonosetron',  # Antiemetics
        'scopolamine', 'promethazine',  # Motion sickness
        'filgrastim', 'pegfilgrastim',  # Growth factors
        'epoetin', 'darbepoetin',  # Anemia support
        'albuterol', 'pentamidine',  # Respiratory
        'omeprazole', 'pantoprazole',  # GI protection
        'bacitracin', 'mupirocin'  # Topical antibiotics
    ]

    def __init__(self):
        """Initialize the chemotherapy identifier"""
        self.all_chemo_patterns = self._build_patterns()

    def _build_patterns(self) -> List[str]:
        """Build comprehensive list of chemotherapy patterns"""
        patterns = []
        for drug_variants in self.CHEMO_KEYWORDS.values():
            patterns.extend(drug_variants)
        return patterns

    def normalize_text(self, text: str) -> str:
        """Normalize text for matching: lowercase, remove spaces/punctuation"""
        if pd.isna(text) or text == '':
            return ''
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9]', '', text)
        return text

    def identify_chemotherapy(self, medications_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Main method to identify chemotherapy medications

        Args:
            medications_df: DataFrame with medication records

        Returns:
            Tuple of (chemotherapy_df, summary_stats)
        """
        logger.info("Starting standardized chemotherapy identification...")

        # Initialize results tracking
        all_matches = []

        # Strategy 1: Direct medication name matching
        name_matches = self._match_by_name(medications_df)
        all_matches.append(name_matches)

        # Strategy 2: ONCOLOGY TREATMENT care plan
        if 'cpc_categories_aggregated' in medications_df.columns:
            care_plan_matches = self._match_by_care_plan(medications_df)
            all_matches.append(care_plan_matches)

        # Strategy 3: Care plan title containing drug names
        if 'cp_title' in medications_df.columns:
            title_matches = self._match_by_care_plan_title(medications_df)
            all_matches.append(title_matches)

        # Consolidate all matches
        chemo_df, summary = self._consolidate_matches(all_matches, medications_df)

        # Filter out supportive care if needed
        chemo_df = self._filter_supportive_care(chemo_df)

        return chemo_df, summary

    def _match_by_name(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 1: Direct medication name matching"""
        logger.info("Strategy 1: Direct medication name matching...")

        matches = []
        pattern = '|'.join(self.all_chemo_patterns)

        for idx, row in medications_df.iterrows():
            med_name = str(row.get('medication_name', '')).lower()

            # Check each drug category
            matched_drugs = []
            for drug_name, variants in self.CHEMO_KEYWORDS.items():
                for variant in variants:
                    if variant.lower() in med_name:
                        matched_drugs.append(drug_name)
                        break

            if matched_drugs:
                matches.append({
                    'index': idx,
                    'strategy': 'name_match',
                    'matched_drugs': matched_drugs,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications by name matching")
        return matches

    def _match_by_care_plan(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 2: ONCOLOGY TREATMENT care plan category"""
        logger.info("Strategy 2: ONCOLOGY TREATMENT care plan matching...")

        matches = []
        for idx, row in medications_df.iterrows():
            categories = str(row.get('cpc_categories_aggregated', ''))

            if 'ONCOLOGY' in categories.upper():
                matches.append({
                    'index': idx,
                    'strategy': 'oncology_care_plan',
                    'care_plan_categories': categories,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications in ONCOLOGY care plans")
        return matches

    def _match_by_care_plan_title(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 3: Care plan titles containing drug names"""
        logger.info("Strategy 3: Care plan title drug name matching...")

        matches = []
        for idx, row in medications_df.iterrows():
            cp_title = str(row.get('cp_title', '')).lower()

            matched_drugs = []
            for drug_name, variants in self.CHEMO_KEYWORDS.items():
                for variant in variants:
                    if variant.lower() in cp_title:
                        matched_drugs.append(drug_name)
                        break

            if matched_drugs:
                matches.append({
                    'index': idx,
                    'strategy': 'care_plan_title',
                    'care_plan_title': row.get('cp_title', ''),
                    'matched_drugs': matched_drugs,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'medium'
                })

        logger.info(f"  Found {len(matches)} medications by care plan title")
        return matches

    def _consolidate_matches(self, all_matches: List[List[Dict]],
                            medications_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Consolidate matches from all strategies"""
        logger.info("Consolidating matches from all strategies...")

        # Collect unique indices
        matched_indices = {}
        for strategy_matches in all_matches:
            for match in strategy_matches:
                idx = match['index']
                if idx not in matched_indices:
                    matched_indices[idx] = {
                        'strategies': [],
                        'matched_drugs': set(),
                        'details': []
                    }
                matched_indices[idx]['strategies'].append(match['strategy'])
                if 'matched_drugs' in match:
                    matched_indices[idx]['matched_drugs'].update(match['matched_drugs'])
                matched_indices[idx]['details'].append(match)

        # Create chemotherapy DataFrame
        chemo_df = medications_df.iloc[list(matched_indices.keys())].copy()

        # Add metadata
        chemo_df['chemo_strategies'] = chemo_df.index.map(
            lambda idx: '|'.join(matched_indices[idx]['strategies'])
        )
        chemo_df['identified_drugs'] = chemo_df.index.map(
            lambda idx: '|'.join(matched_indices[idx]['matched_drugs'])
        )
        chemo_df['confidence_score'] = chemo_df.index.map(
            lambda idx: len(matched_indices[idx]['strategies'])
        )

        # Create summary
        summary = {
            'total_medications': len(medications_df),
            'chemotherapy_identified': len(chemo_df),
            'percentage': len(chemo_df) / len(medications_df) * 100,
            'unique_drugs': list(set().union(*[m['matched_drugs'] for m in matched_indices.values()])),
            'strategy_counts': {},
            'drug_counts': {}
        }

        # Count by strategy
        for data in matched_indices.values():
            for strategy in data['strategies']:
                summary['strategy_counts'][strategy] = summary['strategy_counts'].get(strategy, 0) + 1

        # Count by drug
        for data in matched_indices.values():
            for drug in data['matched_drugs']:
                summary['drug_counts'][drug] = summary['drug_counts'].get(drug, 0) + 1

        logger.info(f"  Total chemotherapy medications identified: {len(chemo_df)}")
        logger.info(f"  Unique drugs found: {len(summary['unique_drugs'])}")

        return chemo_df, summary

    def _filter_supportive_care(self, chemo_df: pd.DataFrame) -> pd.DataFrame:
        """Filter out supportive care medications if they're the only match"""
        initial_count = len(chemo_df)

        # Only filter if medication is ONLY supportive care (not also chemo)
        supportive_pattern = '|'.join(self.SUPPORTIVE_CARE)

        def is_only_supportive(row):
            med_name = str(row.get('medication_name', '')).lower()
            # Check if it's supportive care
            is_supportive = any(supp.lower() in med_name for supp in self.SUPPORTIVE_CARE)
            # Check if it's also chemotherapy
            is_chemo = any(pattern.lower() in med_name for pattern in self.all_chemo_patterns)
            # Keep if it's chemo or not supportive
            return not (is_supportive and not is_chemo)

        if 'medication_name' in chemo_df.columns:
            chemo_df = chemo_df[chemo_df.apply(is_only_supportive, axis=1)]

        filtered_count = initial_count - len(chemo_df)
        if filtered_count > 0:
            logger.info(f"  Filtered {filtered_count} supportive care medications")

        return chemo_df

    def get_treatment_timeline(self, chemo_df: pd.DataFrame) -> pd.DataFrame:
        """Extract treatment timeline from chemotherapy records"""
        if 'medication_start_date' in chemo_df.columns:
            date_col = 'medication_start_date'
        elif 'med_date_given_start' in chemo_df.columns:
            date_col = 'med_date_given_start'
        else:
            return pd.DataFrame()

        # Group by drug and date
        timeline = []
        for drug in chemo_df['identified_drugs'].unique():
            drug_records = chemo_df[chemo_df['identified_drugs'] == drug]
            drug_records[date_col] = pd.to_datetime(drug_records[date_col])

            start_date = drug_records[date_col].min()
            end_date = drug_records[date_col].max()

            timeline.append({
                'drug': drug,
                'start_date': start_date,
                'end_date': end_date,
                'total_orders': len(drug_records),
                'care_plans': drug_records['cp_title'].dropna().unique().tolist()
            })

        return pd.DataFrame(timeline).sort_values('start_date')


# Example usage
if __name__ == "__main__":
    # Test with sample data
    identifier = ChemotherapyIdentifier()

    # Load medications
    meds_df = pd.read_csv('/path/to/medications.csv')

    # Identify chemotherapy
    chemo_df, summary = identifier.identify_chemotherapy(meds_df)

    # Print summary
    print(f"Found {summary['chemotherapy_identified']} chemotherapy medications")
    print(f"Unique drugs: {', '.join(summary['unique_drugs'])}")
    print(f"Drug counts: {summary['drug_counts']}")