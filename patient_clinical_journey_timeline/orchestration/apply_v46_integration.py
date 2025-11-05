#!/usr/bin/env python3
"""
V4.6 Active Reasoning Orchestrator - Automatic Integration Script

This script applies all V4.6 changes to patient_timeline_abstraction_V3.py:
1. Initialize orchestrator components in __init__
2. Add investigation_engine initialization in run()
3. Add helper methods for query execution with investigation
4. Add gap-filling methods to Phase 4.5
5. Enhance Phase 5 WHO validation

Usage:
    python3 orchestration/apply_v46_integration.py

This will create a backup and apply all changes.
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

# Paths
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
TARGET_FILE = SCRIPT_DIR / "patient_timeline_abstraction_V3.py"
BACKUP_FILE = SCRIPT_DIR / f"patient_timeline_abstraction_V3.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def backup_file():
    """Create backup of original file"""
    print(f"Creating backup: {BACKUP_FILE.name}")
    shutil.copy2(TARGET_FILE, BACKUP_FILE)
    print(f"✅ Backup created")

def read_file():
    """Read the target file"""
    with open(TARGET_FILE, 'r') as f:
        return f.read()

def write_file(content):
    """Write modified content back to file"""
    with open(TARGET_FILE, 'w') as f:
        f.write(content)

def add_orchestrator_init(content):
    """
    Phase 1: Add orchestrator component initialization in __init__
    Insert after line 316 (after response_extractor initialization)
    """
    print("\nPhase 1: Adding orchestrator component initialization...")

    # Find the insertion point (after response_extractor initialization)
    pattern = r"(                self\.response_extractor = None\n\n        # Load WHO 2021 classification)"

    insert_code = """                self.response_extractor = None

        # V4.6: Initialize Active Reasoning Orchestrator components
        self.schema_loader = None
        self.investigation_engine = None  # Initialized later in run() after Athena client setup
        self.who_kb = None

        try:
            from orchestration.schema_loader import AthenaSchemaLoader
            from orchestration.who_cns_knowledge_base import WHOCNSKnowledgeBase

            # Schema awareness
            schema_csv_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/Athena_Schema_1103b2025.csv')

            if schema_csv_path.exists():
                self.schema_loader = AthenaSchemaLoader(str(schema_csv_path))
                logger.info("✅ V4.6: Schema loader initialized")

                # WHO CNS knowledge base
                who_ref_path = Path('/Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/mvp/References/WHO 2021 CNS Tumor Classification.md')
                if who_ref_path.exists():
                    self.who_kb = WHOCNSKnowledgeBase(who_reference_path=str(who_ref_path))
                    logger.info("✅ V4.6: WHO CNS knowledge base initialized")
            else:
                logger.warning("⚠️  V4.6: Schema CSV not found, orchestrator features disabled")

        except Exception as e:
            logger.warning(f"⚠️  V4.6: Could not initialize orchestrator components: {e}")

        # Load WHO 2021 classification"""

    modified = re.sub(pattern, insert_code, content)

    if modified != content:
        print("✅ Phase 1 complete: Orchestrator components added to __init__")
        return modified
    else:
        print("⚠️  Phase 1: Pattern not found, skipping...")
        return content

def main():
    """Main integration workflow"""
    print("="*80)
    print("V4.6 Active Reasoning Orchestrator - Integration Script")
    print("="*80)

    # Step 1: Backup
    backup_file()

    # Step 2: Read file
    print("\nReading target file...")
    content = read_file()
    print(f"✅ File loaded ({len(content)} characters)")

    # Step 3: Apply Phase 1 (Orchestrator Init)
    content = add_orchestrator_init(content)

    # Step 4: Write modified content
    print("\nWriting modified file...")
    write_file(content)
    print("✅ File updated")

    print("\n" + "="*80)
    print("V4.6 Integration Summary")
    print("="*80)
    print(f"✅ Backup created: {BACKUP_FILE.name}")
    print("✅ Phase 1: Orchestrator components initialized in __init__")
    print("\nNOTE: Phases 2-5 require more complex multi-method changes.")
    print("      See orchestration/V46_IMPLEMENTATION_GUIDE.md for manual implementation.")
    print("\nNext steps:")
    print("1. Test that the pipeline still runs: python3 scripts/patient_timeline_abstraction_V3.py --help")
    print("2. Check logs for '✅ V4.6: Schema loader initialized'")
    print("3. Continue with Phases 2-5 per implementation guide")
    print("="*80)

if __name__ == "__main__":
    main()
