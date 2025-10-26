#!/usr/bin/env python3
"""
Fix drugs.csv therapeutic normalization and categorization

ROOT CAUSES ADDRESSED:
1. Brand names not mapped to generic names in therapeutic_normalized
2. Supportive care drugs miscategorized as 'chemotherapy' when sourced from FDA_old
3. Inconsistent drug_category assignments between brand and generic versions

FIXES:
1. Create brand→generic mappings for therapeutic_normalized
2. Mark ALL supportive care drugs (brand and generic) with proper category
3. Ensure is_supportive_care flag is consistent
4. Normalize salt forms and biosimilars properly
"""

import pandas as pd
import re
from pathlib import Path

# Brand → Generic mappings for chemotherapy drugs
BRAND_TO_GENERIC = {
    # Antiemetics (should be supportive_care)
    'zofran': 'ondansetron',
    'emend': 'aprepitant',
    'aloxi': 'palonosetron',

    # Targeted therapy brand names
    'afinitor': 'everolimus',
    'mekinist': 'trametinib',
    'tafinlar': 'dabrafenib',
    'koselugo': 'selumetinib',
    'vitrakvi': 'larotrectinib',

    # Hormone therapy
    'lupron depot': 'leuprolide',
    'lupron': 'leuprolide',
    'zoladex': 'goserelin',
    'casodex': 'bicalutamide',
    'eulexin': 'flutamide',

    # Biosimilars (filgrastim)
    'fulphila': 'pegfilgrastim',
    'zarxio': 'filgrastim',
    'nivestym': 'filgrastim',
    'granix': 'filgrastim',
    'udenyca': 'pegfilgrastim',

    # Other common brand names
    'camptosar': 'irinotecan',
    'gemzar': 'gemcitabine',
    'taxol': 'paclitaxel',
    'abraxane': 'paclitaxel albumin-bound',  # Special formulation
    'paraplatin': 'carboplatin',
    'platinol': 'cisplatin',
    'adriamycin': 'doxorubicin',
    'doxil': 'doxorubicin liposomal',  # Special formulation
    'taxotere': 'docetaxel',
    'avastin': 'bevacizumab',
    'herceptin': 'trastuzumab',
    'rituxan': 'rituximab',
    'opdivo': 'nivolumab',
    'keytruda': 'pembrolizumab',
    'yervoy': 'ipilimumab',
    'tecentriq': 'atezolizumab',
    'etopophos': 'etoposide',  # Phosphate formulation
    'gleevec': 'imatinib',
    'sprycel': 'dasatinib',
    'tasigna': 'nilotinib',
    'tarceva': 'erlotinib',
    'iressa': 'gefitinib',
    'alkeran': 'melphalan',
    'cosmegen': 'dactinomycin',
}

# Supportive care drug identifiers (generic names)
SUPPORTIVE_CARE_GENERICS = {
    # Antiemetics
    'ondansetron', 'granisetron', 'dolasetron', 'palonosetron',
    'aprepitant', 'fosaprepitant', 'rolapitant',
    'metoclopramide', 'prochlorperazine',

    # Growth factors (when used for supportive care, not therapeutic)
    # Note: filgrastim/pegfilgrastim can be therapeutic in some contexts
    # We'll handle these based on context in paradigm analysis

    # Antihistamines
    'diphenhydramine', 'hydroxyzine',

    # Corticosteroids used primarily for supportive care in pediatric oncology
    # triamcinolone: Used for managing cerebral edema, inflammation, allergic reactions
    # Note: dexamethasone can be therapeutic (lymphoma) or supportive (antiemetic)
    'triamcinolone',
}

# Corticosteroids that can be both therapeutic and supportive
CORTICOSTEROIDS = {
    'dexamethasone', 'prednisone', 'prednisolone', 'methylprednisolone',
    'hydrocortisone', 'triamcinolone', 'betamethasone'
}

def normalize_therapeutic_name(preferred_name: str, drug_category: str, sources: str) -> str:
    """
    Normalize drug name for therapeutic equivalence.

    Args:
        preferred_name: The drug's preferred name
        drug_category: Current drug category
        sources: Source datasets (pipe-delimited)

    Returns:
        Normalized therapeutic name
    """
    name = str(preferred_name).lower().strip()

    # Step 1: Check if it's a known brand name
    if name in BRAND_TO_GENERIC:
        return BRAND_TO_GENERIC[name]

    # Step 2: Remove biosimilar suffixes (-awwb, -xxxx pattern) BEFORE checking for special formulations
    name = re.sub(r'-[a-z]{4}$', '', name)

    # Step 3: Remove "and hyaluronidase-xxxx" (SC formulation markers)
    name = re.sub(r'\s+and hyaluronidase-[a-z]{4}', '', name, flags=re.IGNORECASE)

    # Step 4: Remove common salt forms (but preserve special formulations)
    # Preserve: liposomal, pegylated, albumin-bound, depot
    if not any(special in name for special in ['liposomal', 'pegylated', 'albumin-bound', 'depot', 'extended-release']):
        # Remove salt forms
        name = re.sub(r'\s+(hydrochloride|hcl|sulfate|sodium|phosphate|mesylate|acetate|malate|tartrate|citrate|maleate)$', '', name, flags=re.IGNORECASE)

    # Step 5: Remove simple dosage forms (but preserve special formulations)
    if not any(special in name for special in ['liposomal', 'pegylated', 'albumin-bound']):
        name = re.sub(r'\s+(tablet|capsule|injection|solution|suspension|cream|gel|ointment)s?$', '', name, flags=re.IGNORECASE)

    # Step 6: Handle "dimethyl sulfoxide" variants
    name = re.sub(r'\s+dimethyl sulfoxide$', '', name, flags=re.IGNORECASE)

    # Step 7: Handle "dihydrochloride monohydrate" (keep as is, just remove at end)
    name = re.sub(r'\s+monohydrate$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+dihydrochloride$', '', name, flags=re.IGNORECASE)

    # Step 8: Final cleanup
    name = name.strip()

    return name

def categorize_drug(row: pd.Series) -> tuple:
    """
    Determine correct drug_category and is_supportive_care flag.

    Args:
        row: Row from drugs dataframe

    Returns:
        (drug_category, is_supportive_care)
    """
    preferred_name = str(row['preferred_name']).lower().strip()
    therapeutic_norm = str(row.get('therapeutic_normalized', preferred_name)).lower().strip()
    sources = str(row.get('sources', ''))
    current_category = str(row.get('drug_category', ''))

    # WHITELIST APPROACH: Only mark as supportive care if it's definitely supportive care
    # Check if generic name is a known supportive care drug
    if therapeutic_norm in SUPPORTIVE_CARE_GENERICS:
        return 'supportive_care', True

    # Check if brand name maps to supportive care generic
    if preferred_name in BRAND_TO_GENERIC:
        if BRAND_TO_GENERIC[preferred_name] in SUPPORTIVE_CARE_GENERICS:
            return 'supportive_care', True

    # Corticosteroids: Check if they're primarily supportive care
    if therapeutic_norm in CORTICOSTEROIDS:
        # dexamethasone and triamcinolone are primarily supportive care in pediatric oncology
        if therapeutic_norm in ('dexamethasone', 'triamcinolone'):
            return 'supportive_care', True
        # Other corticosteroids: keep existing category (may be therapeutic)
        return current_category, False

    # Otherwise keep existing categorization
    return current_category, row.get('is_supportive_care', False)

def main():
    """Fix drugs.csv normalization and categorization."""

    # Load drugs.csv
    drugs_file = Path(__file__).parent / 'drugs.csv'
    print(f"Loading {drugs_file}...")
    df = pd.read_csv(drugs_file)

    print(f"Loaded {len(df)} drugs")
    print(f"\nOriginal therapeutic_normalized unique values: {df['therapeutic_normalized'].nunique()}")

    # Backup original file
    backup_file = drugs_file.parent / 'drugs_before_fix.csv'
    df.to_csv(backup_file, index=False)
    print(f"Backed up original to {backup_file}")

    # Apply normalization
    print("\nApplying therapeutic normalization...")
    df['therapeutic_normalized_new'] = df.apply(
        lambda row: normalize_therapeutic_name(
            row['preferred_name'],
            row.get('drug_category', ''),
            row.get('sources', '')
        ),
        axis=1
    )

    # Apply categorization
    print("Fixing drug categorization...")
    categorization = df.apply(categorize_drug, axis=1)
    df['drug_category_new'] = categorization.apply(lambda x: x[0])
    df['is_supportive_care_new'] = categorization.apply(lambda x: x[1])

    # Show changes
    print("\n" + "="*80)
    print("NORMALIZATION CHANGES")
    print("="*80)

    changes = df[df['therapeutic_normalized'] != df['therapeutic_normalized_new']]
    print(f"\n{len(changes)} drugs changed normalization:")
    for _, row in changes.head(20).iterrows():
        print(f"  {row['preferred_name']:40s} '{row['therapeutic_normalized']}' → '{row['therapeutic_normalized_new']}'")
    if len(changes) > 20:
        print(f"  ... and {len(changes)-20} more")

    print("\n" + "="*80)
    print("CATEGORIZATION CHANGES")
    print("="*80)

    cat_changes = df[
        (df['drug_category'] != df['drug_category_new']) |
        (df['is_supportive_care'] != df['is_supportive_care_new'])
    ]
    print(f"\n{len(cat_changes)} drugs changed categorization:")
    for _, row in cat_changes.iterrows():
        old_cat = f"{row['drug_category']}, supportive={row['is_supportive_care']}"
        new_cat = f"{row['drug_category_new']}, supportive={row['is_supportive_care_new']}"
        print(f"  {row['preferred_name']:40s} {old_cat} → {new_cat}")

    # Apply changes
    df['therapeutic_normalized'] = df['therapeutic_normalized_new']
    df['drug_category'] = df['drug_category_new']
    df['is_supportive_care'] = df['is_supportive_care_new']

    # Drop temporary columns
    df = df.drop(columns=['therapeutic_normalized_new', 'drug_category_new', 'is_supportive_care_new'])

    # Save fixed file
    df.to_csv(drugs_file, index=False)
    print(f"\n✓ Saved fixed drugs.csv ({len(df)} drugs)")
    print(f"  Unique therapeutic_normalized values: {df['therapeutic_normalized'].nunique()}")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    print("\nDrug category distribution:")
    print(df['drug_category'].value_counts())

    print("\nSupportive care drugs:")
    supportive = df[df['is_supportive_care'] == True]
    print(f"  Total: {len(supportive)}")
    print(f"  Categories: {supportive['drug_category'].value_counts().to_dict()}")

    print("\nNormalization collapse:")
    print(f"  Original drugs: {len(df)}")
    print(f"  Unique normalized names: {df['therapeutic_normalized'].nunique()}")
    print(f"  Variants collapsed: {len(df) - df['therapeutic_normalized'].nunique()}")
    print(f"  Reduction: {(len(df) - df['therapeutic_normalized'].nunique()) / len(df) * 100:.1f}%")

if __name__ == '__main__':
    main()
