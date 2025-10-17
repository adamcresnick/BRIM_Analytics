"""
Comprehensive Chemotherapy Identification with Treatment Periods
=================================================================
Full 5-Strategy Approach with Standardized Date Processing
Based on RADIANT unified drug reference system
"""

import pandas as pd
import numpy as np
import re
import logging
from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ComprehensiveChemotherapyIdentifier:
    """
    Full 5-Strategy Chemotherapy Identification:
    1. RxNorm ingredient code matching
    2. Product-to-ingredient mapping
    3. Medication name pattern matching
    4. Care plan ONCOLOGY category
    5. Reason code indicators

    Plus: Treatment period extraction and standardization
    """

    def __init__(self, reference_dir: Optional[Path] = None):
        """Initialize with RADIANT reference files if available"""
        self.reference_dir = reference_dir or Path('/Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index')
        self.drugs_df = None
        self.drug_alias_df = None
        self.rxnorm_map_df = None

        # Try to load reference files
        self._load_reference_data()

        # Comprehensive chemotherapy patterns (for name matching)
        self.CHEMO_PATTERNS = self._build_chemo_patterns()

    def _load_reference_data(self):
        """Load RADIANT unified drug reference files"""
        try:
            if self.reference_dir.exists():
                drugs_file = self.reference_dir / 'drugs.csv'
                alias_file = self.reference_dir / 'drug_alias.csv'
                rxnorm_file = self.reference_dir / 'rxnorm_code_map.csv'

                if drugs_file.exists():
                    self.drugs_df = pd.read_csv(drugs_file)
                    logger.info(f"Loaded {len(self.drugs_df)} drugs from reference")

                if alias_file.exists():
                    self.drug_alias_df = pd.read_csv(alias_file)
                    logger.info(f"Loaded {len(self.drug_alias_df)} drug aliases")

                if rxnorm_file.exists():
                    self.rxnorm_map_df = pd.read_csv(rxnorm_file)
                    logger.info(f"Loaded {len(self.rxnorm_map_df)} RxNorm mappings")
        except Exception as e:
            logger.warning(f"Could not load reference files: {e}")

    def _build_chemo_patterns(self) -> Dict[str, List[str]]:
        """Build comprehensive chemotherapy patterns for name matching"""
        return {
            # Anti-VEGF agents
            'bevacizumab': ['bevacizumab', 'avastin'],

            # Vinca alkaloids
            'vinblastine': ['vinblastine', 'velban'],
            'vincristine': ['vincristine', 'oncovin'],
            'vinorelbine': ['vinorelbine', 'navelbine'],

            # MEK inhibitors
            'selumetinib': ['selumetinib', 'koselugo'],
            'trametinib': ['trametinib', 'mekinist'],
            'cobimetinib': ['cobimetinib', 'cotellic'],

            # BRAF inhibitors
            'dabrafenib': ['dabrafenib', 'tafinlar'],
            'vemurafenib': ['vemurafenib', 'zelboraf'],

            # Alkylating agents
            'temozolomide': ['temozolomide', 'temodar'],
            'lomustine': ['lomustine', 'ccnu', 'ceenu'],
            'carmustine': ['carmustine', 'bcnu', 'gliadel'],
            'procarbazine': ['procarbazine', 'matulane'],

            # Platinum compounds
            'carboplatin': ['carboplatin', 'paraplatin'],
            'cisplatin': ['cisplatin', 'platinol'],

            # Topoisomerase inhibitors
            'etoposide': ['etoposide', 'vepesid'],
            'irinotecan': ['irinotecan', 'camptosar'],

            # Antimetabolites
            'methotrexate': ['methotrexate', 'trexall'],
            'pemetrexed': ['pemetrexed', 'alimta'],
            '5-fluorouracil': ['fluorouracil', '5-fu'],

            # mTOR inhibitors
            'everolimus': ['everolimus', 'afinitor'],

            # Other chemotherapy
            'cyclophosphamide': ['cyclophosphamide', 'cytoxan'],
            'ifosfamide': ['ifosfamide', 'ifex']
        }

    def parse_rxnorm_codes(self, rx_norm_codes_str: str) -> List[str]:
        """Parse semicolon-separated RxNorm codes"""
        if pd.isna(rx_norm_codes_str) or rx_norm_codes_str == '':
            return []

        # Split by semicolon and clean
        codes = []
        for code in str(rx_norm_codes_str).split(';'):
            code = code.strip()
            if code and code.isdigit():
                codes.append(code)
        return codes

    def identify_chemotherapy(self, medications_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Main method: Execute full 5-strategy identification

        Returns:
            Tuple of (chemotherapy_df, summary_stats)
        """
        logger.info("Starting comprehensive 5-strategy chemotherapy identification...")

        all_matches = []

        # Strategy 1: RxNorm ingredient matching
        if 'rx_norm_codes' in medications_df.columns and self.drugs_df is not None:
            rxnorm_matches = self._match_by_rxnorm_ingredient(medications_df)
            all_matches.append(rxnorm_matches)

        # Strategy 2: Product-to-ingredient mapping
        if 'rx_norm_codes' in medications_df.columns and self.rxnorm_map_df is not None:
            product_matches = self._match_by_product_mapping(medications_df)
            all_matches.append(product_matches)

        # Strategy 3: Medication name pattern matching
        if 'medication_name' in medications_df.columns:
            name_matches = self._match_by_name(medications_df)
            all_matches.append(name_matches)

        # Strategy 4: Care plan ONCOLOGY category
        if 'cpc_categories_aggregated' in medications_df.columns:
            care_plan_matches = self._match_by_care_plan_category(medications_df)
            all_matches.append(care_plan_matches)

        # Strategy 5: Reason code indicators
        if 'mrr_reason_code_text_aggregated' in medications_df.columns:
            reason_matches = self._match_by_reason_codes(medications_df)
            all_matches.append(reason_matches)

        # Consolidate all matches
        chemo_df, summary = self._consolidate_matches(all_matches, medications_df)

        return chemo_df, summary

    def _match_by_rxnorm_ingredient(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 1: Direct RxNorm ingredient matching"""
        logger.info("Strategy 1: RxNorm ingredient matching...")

        # Get valid chemotherapy RxNorm IN codes
        chemo_drugs = self.drugs_df[
            (self.drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
            (self.drugs_df['is_supportive_care'] == False)
        ]
        valid_rxnorm_in = set(chemo_drugs['rxnorm_in'].dropna().astype(int).astype(str))

        matches = []
        for idx, row in medications_df.iterrows():
            rx_codes = self.parse_rxnorm_codes(row.get('rx_norm_codes', ''))
            matched_codes = [code for code in rx_codes if code in valid_rxnorm_in]

            if matched_codes:
                # Look up drug names for matched codes
                drug_names = []
                for code in matched_codes:
                    drug = chemo_drugs[chemo_drugs['rxnorm_in'] == int(code)]
                    if not drug.empty:
                        drug_names.append(drug.iloc[0]['preferred_name'])

                matches.append({
                    'index': idx,
                    'strategy': 'rxnorm_ingredient',
                    'matched_codes': matched_codes,
                    'drug_names': drug_names,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications by RxNorm ingredient")
        return matches

    def _match_by_product_mapping(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 2: Product code to ingredient mapping"""
        logger.info("Strategy 2: Product-to-ingredient mapping...")

        # Get chemotherapy ingredient codes
        chemo_drugs = self.drugs_df[
            (self.drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
            (self.drugs_df['is_supportive_care'] == False)
        ]
        valid_rxnorm_in = set(chemo_drugs['rxnorm_in'].dropna().astype(int).astype(str))

        # Build product-to-ingredient mapping
        product_to_ingredient = {}
        for _, row in self.rxnorm_map_df.iterrows():
            if pd.notna(row['ingredient_rxcui']) and pd.notna(row['code_cui']):
                ingredient_cui = str(int(row['ingredient_rxcui']))
                if ingredient_cui in valid_rxnorm_in:
                    product_to_ingredient[str(int(row['code_cui']))] = ingredient_cui

        matches = []
        for idx, row in medications_df.iterrows():
            rx_codes = self.parse_rxnorm_codes(row.get('rx_norm_codes', ''))
            matched_products = [code for code in rx_codes if code in product_to_ingredient]

            if matched_products:
                matches.append({
                    'index': idx,
                    'strategy': 'product_mapping',
                    'matched_codes': matched_products,
                    'mapped_ingredients': [product_to_ingredient[code] for code in matched_products],
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications by product mapping")
        return matches

    def _match_by_name(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 3: Medication name pattern matching"""
        logger.info("Strategy 3: Medication name pattern matching...")

        matches = []
        for idx, row in medications_df.iterrows():
            med_name = str(row.get('medication_name', '')).lower()

            matched_drugs = []
            for drug_name, patterns in self.CHEMO_PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in med_name:
                        matched_drugs.append(drug_name)
                        break

            if matched_drugs:
                matches.append({
                    'index': idx,
                    'strategy': 'name_pattern',
                    'matched_drugs': matched_drugs,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications by name pattern")
        return matches

    def _match_by_care_plan_category(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 4: Care plan ONCOLOGY TREATMENT category"""
        logger.info("Strategy 4: Care plan ONCOLOGY category...")

        matches = []
        for idx, row in medications_df.iterrows():
            categories = str(row.get('cpc_categories_aggregated', ''))

            if 'ONCOLOGY' in categories.upper():
                # Also check care plan title for drug names
                cp_title = str(row.get('cp_title', '')).lower()
                matched_drugs = []

                for drug_name, patterns in self.CHEMO_PATTERNS.items():
                    for pattern in patterns:
                        if pattern.lower() in cp_title:
                            matched_drugs.append(drug_name)
                            break

                matches.append({
                    'index': idx,
                    'strategy': 'oncology_care_plan',
                    'care_plan_categories': categories,
                    'care_plan_title': row.get('cp_title', ''),
                    'matched_drugs': matched_drugs,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'high'
                })

        logger.info(f"  Found {len(matches)} medications in ONCOLOGY care plans")
        return matches

    def _match_by_reason_codes(self, medications_df: pd.DataFrame) -> List[Dict]:
        """Strategy 5: Reason code chemotherapy indicators"""
        logger.info("Strategy 5: Reason code indicators...")

        chemo_indicators = [
            'antineoplastic chemotherapy',
            'chemotherapy encounter',
            'encounter for antineoplastic',
            'chemotherapy administration',
            'malignant neoplasm'
        ]

        matches = []
        for idx, row in medications_df.iterrows():
            reason_codes = str(row.get('mrr_reason_code_text_aggregated', '')).lower()

            if any(indicator in reason_codes for indicator in chemo_indicators):
                matched_indicators = [ind for ind in chemo_indicators if ind in reason_codes]
                matches.append({
                    'index': idx,
                    'strategy': 'reason_codes',
                    'matched_indicators': matched_indicators,
                    'medication_name': row.get('medication_name', ''),
                    'confidence': 'medium'
                })

        logger.info(f"  Found {len(matches)} medications by reason codes")
        return matches

    def _consolidate_matches(self, all_matches: List[List[Dict]],
                            medications_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Consolidate matches from all strategies"""
        logger.info("Consolidating matches from all strategies...")

        # Collect unique indices with their match details
        matched_indices = {}
        for strategy_matches in all_matches:
            for match in strategy_matches:
                idx = match['index']
                if idx not in matched_indices:
                    matched_indices[idx] = {
                        'strategies': [],
                        'drug_names': set(),
                        'confidence_scores': [],
                        'details': []
                    }

                matched_indices[idx]['strategies'].append(match['strategy'])
                matched_indices[idx]['details'].append(match)

                # Collect drug names from various fields
                if 'drug_names' in match:
                    matched_indices[idx]['drug_names'].update(match['drug_names'])
                if 'matched_drugs' in match:
                    matched_indices[idx]['drug_names'].update(match['matched_drugs'])

                # Add confidence score
                conf = 1.0 if match.get('confidence') == 'high' else 0.5
                matched_indices[idx]['confidence_scores'].append(conf)

        # Create chemotherapy DataFrame using loc (not iloc) since keys are index values
        chemo_df = medications_df.loc[list(matched_indices.keys())].copy()

        # Add metadata columns
        chemo_df['matching_strategies'] = chemo_df.index.map(
            lambda idx: '|'.join(matched_indices[idx]['strategies'])
        )
        chemo_df['identified_drugs'] = chemo_df.index.map(
            lambda idx: '|'.join(matched_indices[idx]['drug_names']) if matched_indices[idx]['drug_names'] else ''
        )
        chemo_df['confidence_score'] = chemo_df.index.map(
            lambda idx: sum(matched_indices[idx]['confidence_scores'])
        )
        chemo_df['strategy_count'] = chemo_df.index.map(
            lambda idx: len(matched_indices[idx]['strategies'])
        )

        # Create summary
        summary = self._create_summary(chemo_df, matched_indices, medications_df)

        logger.info(f"  Total chemotherapy medications identified: {len(chemo_df)}")

        return chemo_df, summary

    def _create_summary(self, chemo_df: pd.DataFrame, matched_indices: Dict,
                       medications_df: pd.DataFrame) -> Dict:
        """Create comprehensive summary of findings"""
        summary = {
            'total_medications': len(medications_df),
            'chemotherapy_identified': len(chemo_df),
            'percentage': len(chemo_df) / len(medications_df) * 100 if len(medications_df) > 0 else 0,
            'unique_drugs': set(),
            'strategy_breakdown': {},
            'drug_counts': {}
        }

        # Collect unique drugs
        for data in matched_indices.values():
            summary['unique_drugs'].update(data['drug_names'])

        # Count by strategy
        for data in matched_indices.values():
            for strategy in data['strategies']:
                summary['strategy_breakdown'][strategy] = summary['strategy_breakdown'].get(strategy, 0) + 1

        # Count medications by drug
        if 'medication_name' in chemo_df.columns:
            for drug in summary['unique_drugs']:
                count = chemo_df['identified_drugs'].str.contains(drug, na=False).sum()
                if count > 0:
                    summary['drug_counts'][drug] = count

        summary['unique_drugs'] = list(summary['unique_drugs'])

        return summary

    def extract_treatment_periods(self, chemo_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract and standardize treatment periods for each therapy

        Returns DataFrame with columns:
        - drug_name
        - start_date
        - end_date
        - duration_days
        - total_administrations
        - care_plan
        - treatment_phase (induction/maintenance/salvage)
        """
        logger.info("Extracting treatment periods...")

        # Identify date columns - check all possible date sources
        # Priority order: medication dates, care plan periods, validity periods
        start_cols = []
        end_cols = []

        # Check medication dates
        if 'medication_start_date' in chemo_df.columns:
            start_cols.append('medication_start_date')
        if 'medication_end_date' in chemo_df.columns:
            end_cols.append('medication_end_date')

        # Check medication given dates
        if 'med_date_given_start' in chemo_df.columns:
            start_cols.append('med_date_given_start')
        if 'med_date_given_end' in chemo_df.columns:
            end_cols.append('med_date_given_end')

        # Check care plan periods
        if 'cp_period_start' in chemo_df.columns:
            start_cols.append('cp_period_start')
        if 'cp_period_end' in chemo_df.columns:
            end_cols.append('cp_period_end')

        # Check validity periods
        if 'mr_validity_period_start' in chemo_df.columns:
            start_cols.append('mr_validity_period_start')
        if 'mr_validity_period_end' in chemo_df.columns:
            end_cols.append('mr_validity_period_end')

        if not start_cols:
            logger.warning("No start date columns found for treatment period extraction")
            return pd.DataFrame()

        logger.info(f"  Using date columns: start={start_cols}, end={end_cols}")

        # Parse all date columns with proper format handling (ensure UTC for consistency)
        for col in start_cols + end_cols:
            if col in chemo_df.columns:
                chemo_df[col] = pd.to_datetime(chemo_df[col], utc=True, errors='coerce')

        treatment_periods = []

        # Extract unique individual drugs from pipe-separated lists
        all_drugs = set()
        for drug_list in chemo_df['identified_drugs'].dropna():
            if drug_list:
                drugs = [d.strip() for d in drug_list.split('|') if d.strip()]
                all_drugs.update(drugs)

        # Group by individual drug
        for drug in all_drugs:
            # Find records containing this specific drug
            drug_records = chemo_df[
                chemo_df['identified_drugs'].apply(
                    lambda x: drug in str(x).split('|') if pd.notna(x) else False
                )
            ]

            if drug_records.empty:
                continue

            # Further group by care plan if available
            if 'cp_title' in drug_records.columns:
                for care_plan in drug_records['cp_title'].dropna().unique():
                    cp_records = drug_records[drug_records['cp_title'] == care_plan]
                    period = self._extract_period_from_records(cp_records, drug, care_plan, start_cols, end_cols)
                    if period:
                        treatment_periods.append(period)
            else:
                period = self._extract_period_from_records(drug_records, drug, None, start_cols, end_cols)
                if period:
                    treatment_periods.append(period)

        # Create DataFrame from periods
        periods_df = pd.DataFrame(treatment_periods)

        if not periods_df.empty:
            # Sort by start date
            periods_df = periods_df.sort_values('start_date')

            # Classify treatment phases
            periods_df = self._classify_treatment_phases(periods_df)

        logger.info(f"  Extracted {len(periods_df)} treatment periods")

        return periods_df

    def _extract_period_from_records(self, records: pd.DataFrame, drug_name: str,
                                    care_plan: Optional[str], start_cols: List[str],
                                    end_cols: List[str]) -> Optional[Dict]:
        """Extract treatment period from a set of records"""
        # Collect all valid start dates from any column
        all_start_dates = []
        for col in start_cols:
            if col in records.columns:
                valid_dates = records[col].dropna()
                if not valid_dates.empty:
                    all_start_dates.extend(valid_dates.tolist())

        if not all_start_dates:
            return None

        start_date = min(all_start_dates)

        # Collect all valid end dates
        all_end_dates = []
        for col in end_cols:
            if col in records.columns:
                valid_dates = records[col].dropna()
                if not valid_dates.empty:
                    all_end_dates.extend(valid_dates.tolist())

        # If no end dates found, use the max start date as end date
        end_date = max(all_end_dates) if all_end_dates else max(all_start_dates)

        # Calculate duration
        duration_days = (end_date - start_date).days if pd.notna(end_date) and pd.notna(start_date) else 0

        # Count administrations
        total_administrations = len(records)

        # Extract dosing information if available
        dosing_info = self._extract_dosing_info(records)

        return {
            'drug_name': drug_name,
            'care_plan': care_plan or 'Not specified',
            'start_date': start_date,
            'end_date': end_date,
            'duration_days': duration_days,
            'total_administrations': total_administrations,
            'dosing_info': dosing_info,
            'medication_names': records['medication_name'].unique().tolist()[:3]  # Sample names
        }

    def _extract_dosing_info(self, records: pd.DataFrame) -> str:
        """Extract dosing information from medication names"""
        doses = []
        for med_name in records['medication_name'].dropna().unique():
            # Look for dose patterns (e.g., "600 mg", "10 mg/kg")
            dose_pattern = r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|mg/kg|units?|mL)'
            matches = re.findall(dose_pattern, med_name, re.IGNORECASE)
            if matches:
                doses.extend([f"{match[0]} {match[1]}" for match in matches])

        return '|'.join(set(doses)) if doses else 'Not specified'

    def _classify_treatment_phases(self, periods_df: pd.DataFrame) -> pd.DataFrame:
        """Classify treatment into phases (induction/maintenance/salvage)"""
        if periods_df.empty:
            return periods_df

        periods_df['treatment_phase'] = 'Unknown'

        # Sort by start date
        periods_df = periods_df.sort_values('start_date')

        # Classify based on order and timing
        for drug in periods_df['drug_name'].unique():
            drug_periods = periods_df[periods_df['drug_name'] == drug].copy()

            if len(drug_periods) == 1:
                # Single period - likely primary treatment
                periods_df.loc[drug_periods.index, 'treatment_phase'] = 'Primary'
            else:
                # Multiple periods - classify by timing
                for i, (idx, row) in enumerate(drug_periods.iterrows()):
                    if i == 0:
                        periods_df.loc[idx, 'treatment_phase'] = 'Induction'
                    elif row['duration_days'] > 90:
                        periods_df.loc[idx, 'treatment_phase'] = 'Maintenance'
                    else:
                        periods_df.loc[idx, 'treatment_phase'] = 'Salvage/Recurrence'

        return periods_df

    def create_treatment_timeline(self, periods_df: pd.DataFrame) -> Dict[str, Any]:
        """Create a comprehensive treatment timeline"""
        if periods_df.empty:
            return {'timeline': [], 'summary': {}}

        timeline = []

        for _, period in periods_df.iterrows():
            timeline.append({
                'date': period['start_date'].isoformat() if pd.notna(period['start_date']) else None,
                'event': f"{period['drug_name']} started",
                'phase': period['treatment_phase'],
                'care_plan': period['care_plan'],
                'duration_days': period['duration_days'],
                'doses': period['total_administrations']
            })

            if pd.notna(period['end_date']) and period['end_date'] != period['start_date']:
                timeline.append({
                    'date': period['end_date'].isoformat(),
                    'event': f"{period['drug_name']} ended",
                    'phase': period['treatment_phase'],
                    'care_plan': period['care_plan']
                })

        # Sort timeline
        timeline.sort(key=lambda x: x['date'] if x['date'] else '9999-12-31')

        # Create summary
        summary = {
            'total_drugs': periods_df['drug_name'].nunique(),
            'total_periods': len(periods_df),
            'treatment_duration_days': (periods_df['end_date'].max() - periods_df['start_date'].min()).days
                if not periods_df.empty else 0,
            'drugs_used': periods_df['drug_name'].unique().tolist(),
            'phases': periods_df['treatment_phase'].value_counts().to_dict()
        }

        return {'timeline': timeline, 'summary': summary}


# Example usage
if __name__ == "__main__":
    # Initialize identifier
    identifier = ComprehensiveChemotherapyIdentifier()

    # Load medications
    staging_path = Path("/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/athena_extraction_validation/staging_files")
    patient_path = staging_path / "patient_e4BwD8ZYDBccepXcJ.Ilo3w3"
    meds_df = pd.read_csv(patient_path / "medications.csv")

    # Identify chemotherapy
    chemo_df, summary = identifier.identify_chemotherapy(meds_df)

    # Extract treatment periods
    periods_df = identifier.extract_treatment_periods(chemo_df)

    # Create timeline
    timeline = identifier.create_treatment_timeline(periods_df)

    print(f"\nChemotherapy identified: {summary['chemotherapy_identified']}")
    print(f"Unique drugs: {summary['unique_drugs']}")
    print(f"\nTreatment periods: {len(periods_df)}")
    print(f"Timeline events: {len(timeline['timeline'])}")