#!/usr/bin/env python3
"""
Filter Chemotherapy from All Medications Metadata
Uses RADIANT unified drug reference system for comprehensive chemotherapy identification

Integration Strategy:
1. RxNorm ingredient matching (drugs.csv)
2. Name-based matching (drug_alias.csv)
3. Product-to-ingredient mapping (rxnorm_code_map.csv)
4. Care plan linkage ('ONCOLOGY TREATMENT' category)
5. Reason code filtering ('antineoplastic chemotherapy')

Reference: /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/docs/MATERIALIZED_VIEW_STRATEGY_VALIDATION.md
"""

import pandas as pd
import numpy as np
import logging
import re
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
ATHENA_VALIDATION_DIR = SCRIPT_DIR.parent
BRIM_ANALYTICS_DIR = ATHENA_VALIDATION_DIR.parent
STAGING_DIR = BRIM_ANALYTICS_DIR / 'staging_files'
REFERENCE_DIR = Path('/Users/resnick/Downloads/RADIANT_Portal/RADIANT_PCA/unified_chemo_index')

# Input/Output files
INPUT_FILE = STAGING_DIR / 'ALL_MEDICATIONS_METADATA_C1277724.csv'
OUTPUT_FILE = STAGING_DIR / 'CHEMOTHERAPY_C1277724.csv'

# Reference files
DRUGS_REF = REFERENCE_DIR / 'drugs.csv'
DRUG_ALIAS_REF = REFERENCE_DIR / 'drug_alias.csv'
RXNORM_MAP_REF = REFERENCE_DIR / 'rxnorm_code_map.csv'


def normalize_text(text):
    """
    Normalize text for matching: lowercase, remove spaces/punctuation
    Matches the normalization in drug_alias.csv normalized_key
    """
    if pd.isna(text) or text == '':
        return ''
    # Convert to lowercase
    text = str(text).lower()
    # Remove all non-alphanumeric characters
    text = re.sub(r'[^a-z0-9]', '', text)
    return text


def load_reference_data():
    """Load RADIANT unified drug reference files"""
    logger.info("Loading RADIANT unified drug reference files...")
    
    # Load drugs.csv
    drugs_df = pd.read_csv(DRUGS_REF)
    logger.info(f"  Loaded {len(drugs_df)} drugs from drugs.csv")
    logger.info(f"    - FDA approved: {(drugs_df['approval_status'] == 'FDA_approved').sum()}")
    logger.info(f"    - Investigational: {(drugs_df['approval_status'] == 'investigational').sum()}")
    logger.info(f"    - Supportive care flagged: {drugs_df['is_supportive_care'].sum()}")
    
    # Load drug_alias.csv
    drug_alias_df = pd.read_csv(DRUG_ALIAS_REF)
    logger.info(f"  Loaded {len(drug_alias_df)} drug aliases from drug_alias.csv")
    
    # Load rxnorm_code_map.csv
    rxnorm_map_df = pd.read_csv(RXNORM_MAP_REF)
    logger.info(f"  Loaded {len(rxnorm_map_df)} RxNorm code mappings from rxnorm_code_map.csv")
    
    return drugs_df, drug_alias_df, rxnorm_map_df


def parse_rxnorm_codes(rx_norm_codes_str):
    """Parse semicolon-separated RxNorm codes into list of integers"""
    if pd.isna(rx_norm_codes_str) or rx_norm_codes_str == '':
        return []
    
    # Split by semicolon and clean
    codes = []
    for code in str(rx_norm_codes_str).split(';'):
        code = code.strip()
        if code and code.isdigit():
            codes.append(int(code))
    return codes


def match_by_rxnorm_ingredient(medications_df, drugs_df):
    """
    Strategy 1: Direct RxNorm ingredient matching
    Match rx_norm_codes against drugs.rxnorm_in
    """
    logger.info("\nStrategy 1: RxNorm ingredient matching...")
    
    # Filter to non-supportive care chemo drugs
    chemo_drugs = drugs_df[
        (drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
        (drugs_df['is_supportive_care'] == False)
    ].copy()
    
    # Get valid RxNorm IN codes
    valid_rxnorm_in = set(chemo_drugs['rxnorm_in'].dropna().astype(int))
    logger.info(f"  Found {len(valid_rxnorm_in)} valid chemotherapy RxNorm IN codes")
    
    # Parse and match RxNorm codes from medications
    matches = []
    for idx, row in medications_df.iterrows():
        rx_codes = parse_rxnorm_codes(row['rx_norm_codes'])
        matched_codes = [code for code in rx_codes if code in valid_rxnorm_in]
        
        if matched_codes:
            matches.append({
                'index': idx,
                'strategy': 'rxnorm_ingredient',
                'matched_codes': matched_codes,
                'confidence': 'high'
            })
    
    logger.info(f"  Matched {len(matches)} medications by RxNorm ingredient codes")
    return matches


def match_by_product_code_mapping(medications_df, drugs_df, rxnorm_map_df):
    """
    Strategy 2: Product code to ingredient mapping
    Use rxnorm_code_map to convert product/brand codes to ingredient codes
    """
    logger.info("\nStrategy 2: Product-to-ingredient RxNorm mapping...")
    
    # Get valid ingredient RxNorm codes (non-supportive care chemo)
    chemo_drugs = drugs_df[
        (drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
        (drugs_df['is_supportive_care'] == False)
    ].copy()
    valid_rxnorm_in = set(chemo_drugs['rxnorm_in'].dropna().astype(int))
    
    # Create product-to-ingredient lookup
    product_to_ingredient = {}
    for _, row in rxnorm_map_df.iterrows():
        if pd.notna(row['ingredient_rxcui']) and pd.notna(row['code_cui']):
            ingredient_cui = int(row['ingredient_rxcui'])
            if ingredient_cui in valid_rxnorm_in:
                product_to_ingredient[int(row['code_cui'])] = ingredient_cui
    
    logger.info(f"  Found {len(product_to_ingredient)} product codes mapping to chemotherapy ingredients")
    
    # Match medications
    matches = []
    for idx, row in medications_df.iterrows():
        rx_codes = parse_rxnorm_codes(row['rx_norm_codes'])
        matched_products = [code for code in rx_codes if code in product_to_ingredient]
        
        if matched_products:
            matches.append({
                'index': idx,
                'strategy': 'product_code_mapping',
                'matched_codes': matched_products,
                'mapped_ingredients': [product_to_ingredient[code] for code in matched_products],
                'confidence': 'high'
            })
    
    logger.info(f"  Matched {len(matches)} medications by product code mapping")
    return matches


def match_by_drug_alias(medications_df, drug_alias_df, drugs_df):
    """
    Strategy 3: Name-based matching via drug_alias
    Normalize medication names and match against drug_alias.normalized_key
    """
    logger.info("\nStrategy 3: Name-based matching via drug aliases...")
    
    # Get drug IDs for non-supportive care chemo (from drugs_df)
    chemo_drug_ids = set(drugs_df[
        (drugs_df['approval_status'].isin(['FDA_approved', 'investigational'])) &
        (drugs_df['is_supportive_care'] == False)
    ]['drug_id'])
    
    # Filter drug aliases to only chemotherapy drugs
    chemo_aliases = drug_alias_df[
        drug_alias_df['drug_id'].isin(chemo_drug_ids)
    ].copy()
    
    # Create normalized name lookup
    alias_lookup = {}
    for _, row in chemo_aliases.iterrows():
        normalized = row['normalized_key'] if pd.notna(row['normalized_key']) else normalize_text(row.iloc[1])
        if normalized:
            alias_lookup[normalized] = row['drug_id']
    
    logger.info(f"  Created lookup with {len(alias_lookup)} normalized chemotherapy drug names")
    
    # Normalize and match medication names
    matches = []
    for idx, row in medications_df.iterrows():
        normalized_name = normalize_text(row['medication_name'])
        
        if normalized_name in alias_lookup:
            matches.append({
                'index': idx,
                'strategy': 'drug_alias',
                'matched_name': normalized_name,
                'drug_id': alias_lookup[normalized_name],
                'confidence': 'high'
            })
    
    logger.info(f"  Matched {len(matches)} medications by drug alias")
    return matches


def match_by_care_plan_oncology(medications_df):
    """
    Strategy 4: Care plan ONCOLOGY TREATMENT category
    Medications linked to care plans with 'ONCOLOGY TREATMENT' category
    """
    logger.info("\nStrategy 4: Care plan ONCOLOGY TREATMENT category matching...")
    
    matches = []
    for idx, row in medications_df.iterrows():
        care_plan_categories = str(row.get('care_plan_categories', ''))
        
        if 'ONCOLOGY TREATMENT' in care_plan_categories.upper():
            matches.append({
                'index': idx,
                'strategy': 'care_plan_oncology',
                'care_plan_title': row.get('care_plan_title', ''),
                'confidence': 'high'
            })
    
    logger.info(f"  Matched {len(matches)} medications by ONCOLOGY TREATMENT care plan")
    return matches


def match_by_reason_codes(medications_df):
    """
    Strategy 5: Reason codes containing chemotherapy indicators
    Look for 'antineoplastic chemotherapy', 'chemotherapy encounter', etc.
    """
    logger.info("\nStrategy 5: Reason code chemotherapy indicators...")
    
    chemo_patterns = [
        'antineoplastic chemotherapy',
        'chemotherapy encounter',
        'encounter for antineoplastic',
        'chemotherapy administration'
    ]
    
    matches = []
    for idx, row in medications_df.iterrows():
        reason_codes = str(row.get('reason_codes', '')).lower()
        
        if any(pattern in reason_codes for pattern in chemo_patterns):
            matched_patterns = [p for p in chemo_patterns if p in reason_codes]
            matches.append({
                'index': idx,
                'strategy': 'reason_codes',
                'matched_patterns': matched_patterns,
                'confidence': 'medium'
            })
    
    logger.info(f"  Matched {len(matches)} medications by chemotherapy reason codes")
    return matches


def consolidate_matches(all_matches, medications_df):
    """
    Consolidate all matching strategies and create final chemotherapy dataset
    """
    logger.info("\nConsolidating matches from all strategies...")
    
    # Collect all matched indices with their strategies
    matched_indices = {}
    for strategy_matches in all_matches:
        for match in strategy_matches:
            idx = match['index']
            if idx not in matched_indices:
                matched_indices[idx] = {
                    'strategies': [],
                    'details': []
                }
            matched_indices[idx]['strategies'].append(match['strategy'])
            matched_indices[idx]['details'].append(match)
    
    logger.info(f"  Total unique medications matched: {len(matched_indices)}")
    
    # Create chemotherapy dataset
    chemo_df = medications_df.iloc[list(matched_indices.keys())].copy()
    
    # Add matching metadata
    chemo_df['matching_strategies'] = chemo_df.index.map(
        lambda idx: '|'.join(matched_indices[idx]['strategies'])
    )
    chemo_df['strategy_count'] = chemo_df.index.map(
        lambda idx: len(matched_indices[idx]['strategies'])
    )
    
    # Sort by strategy count (most confident first), then by date
    chemo_df = chemo_df.sort_values(
        by=['strategy_count', 'authored_on'],
        ascending=[False, False]
    )
    
    return chemo_df, matched_indices


def generate_summary(chemo_df, matched_indices, medications_df):
    """Generate comprehensive summary statistics"""
    logger.info("\n" + "="*80)
    logger.info("CHEMOTHERAPY EXTRACTION SUMMARY")
    logger.info("="*80)
    
    logger.info(f"\nTotal medications analyzed: {len(medications_df)}")
    logger.info(f"Chemotherapy medications identified: {len(chemo_df)}")
    logger.info(f"Percentage: {len(chemo_df)/len(medications_df)*100:.1f}%")
    
    # Strategy breakdown
    logger.info("\nMatching Strategy Breakdown:")
    strategy_counts = {}
    for idx_data in matched_indices.values():
        for strategy in idx_data['strategies']:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    
    strategy_names = {
        'rxnorm_ingredient': 'RxNorm Ingredient Match',
        'product_code_mapping': 'Product Code Mapping',
        'drug_alias': 'Drug Alias Name Match',
        'care_plan_oncology': 'ONCOLOGY TREATMENT Care Plan',
        'reason_codes': 'Chemotherapy Reason Codes'
    }
    
    for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {strategy_names.get(strategy, strategy)}: {count} medications")
    
    # Confidence levels
    logger.info("\nConfidence Distribution:")
    logger.info(f"  High confidence (2+ strategies): {(chemo_df['strategy_count'] >= 2).sum()}")
    logger.info(f"  Single strategy match: {(chemo_df['strategy_count'] == 1).sum()}")
    
    # Top medications
    logger.info("\nTop 10 Chemotherapy Medications:")
    top_meds = chemo_df['medication_name'].value_counts().head(10)
    for med_name, count in top_meds.items():
        logger.info(f"  {med_name}: {count} orders")
    
    # Care plan linkage
    care_plan_linked = (chemo_df['care_plan_title'] != '').sum()
    logger.info(f"\nCare Plan Linkage:")
    logger.info(f"  Medications linked to care plans: {care_plan_linked}")
    logger.info(f"  Care plans represented:")
    if care_plan_linked > 0:
        for plan in chemo_df[chemo_df['care_plan_title'] != '']['care_plan_title'].unique():
            count = (chemo_df['care_plan_title'] == plan).sum()
            logger.info(f"    '{plan}': {count} medications")
    
    # Date range
    if not chemo_df.empty:
        logger.info(f"\nTemporal Coverage:")
        logger.info(f"  First chemotherapy order: {chemo_df['authored_on'].min()}")
        logger.info(f"  Last chemotherapy order: {chemo_df['authored_on'].max()}")
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Output saved to: {OUTPUT_FILE}")
    logger.info(f"{'='*80}\n")


def main():
    """Main execution"""
    start_time = datetime.now()
    
    logger.info("="*80)
    logger.info("CHEMOTHERAPY FILTERING - RADIANT Unified Drug Reference Integration")
    logger.info("="*80)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Verify reference files exist
    for ref_file in [DRUGS_REF, DRUG_ALIAS_REF, RXNORM_MAP_REF]:
        if not ref_file.exists():
            logger.error(f"Reference file not found: {ref_file}")
            logger.error("Please ensure RADIANT unified_chemo_index files are available")
            return 1
    
    # Load input data
    logger.info(f"Loading medications metadata from: {INPUT_FILE}")
    medications_df = pd.read_csv(INPUT_FILE)
    logger.info(f"  Loaded {len(medications_df)} medication records\n")
    
    # Load reference data
    drugs_df, drug_alias_df, rxnorm_map_df = load_reference_data()
    
    # Execute all matching strategies
    all_matches = []
    
    # Strategy 1: RxNorm ingredient matching
    matches_1 = match_by_rxnorm_ingredient(medications_df, drugs_df)
    all_matches.append(matches_1)
    
    # Strategy 2: Product code mapping
    matches_2 = match_by_product_code_mapping(medications_df, drugs_df, rxnorm_map_df)
    all_matches.append(matches_2)
    
    # Strategy 3: Drug alias name matching
    matches_3 = match_by_drug_alias(medications_df, drug_alias_df, drugs_df)
    all_matches.append(matches_3)
    
    # Strategy 4: Care plan ONCOLOGY category
    matches_4 = match_by_care_plan_oncology(medications_df)
    all_matches.append(matches_4)
    
    # Strategy 5: Reason codes
    matches_5 = match_by_reason_codes(medications_df)
    all_matches.append(matches_5)
    
    # Consolidate all matches
    chemo_df, matched_indices = consolidate_matches(all_matches, medications_df)
    
    # Save output
    chemo_df.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"\nSaved {len(chemo_df)} chemotherapy records to {OUTPUT_FILE}")
    
    # Generate summary
    generate_summary(chemo_df, matched_indices, medications_df)
    
    # Execution time
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logger.info(f"Total execution time: {duration:.1f} seconds")
    
    return 0


if __name__ == '__main__':
    exit(main())
