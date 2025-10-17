# Project Restructure Plan
**Date**: 2025-10-17
**Branch**: feature/multi-agent-framework
**Purpose**: Organize multiagent workflow and staging extraction work into clean structure

---

## Current State

Work from October 16-17 includes:
- Athena view creation and validation (15 views)
- Staging extraction pipeline with config-driven scripts
- Patient identifier standardization
- Date/time format analysis
- All scattered across `local_llm_extraction/staging_extraction/`

---

## Proposed New Structure

```
RADIANT_PCA/BRIM_Analytics/
│
├── athena_views/                          # NEW: Centralized Athena view management
│   ├── README.md                          # Overview of all 15 views
│   ├── views/
│   │   ├── ATHENA_VIEW_CREATION_QUERIES.sql  # All 15 CREATE VIEW statements
│   │   ├── RERUN_STANDARDIZED_VIEWS.sql      # Patient ID standardization
│   │   └── validation_queries.sql            # Test queries for all views
│   ├── documentation/
│   │   ├── ATHENA_VIEW_FIXES.md              # Complete fix history
│   │   ├── PATIENT_IDENTIFIER_ANALYSIS.md    # Patient ID standardization
│   │   ├── DATE_TIME_STANDARDIZATION_ANALYSIS.md
│   │   ├── DATE_STANDARDIZATION_EXAMPLE.sql
│   │   └── STANDARDIZATION_SUMMARY.md
│   └── verification/
│       ├── ATHENA_VIEWS_VERIFICATION.md      # Test results
│       └── test_all_views.py                 # Automated testing
│
├── staging_extraction/                     # RENAMED: Clean staging extraction
│   ├── README.md                           # Quick start guide
│   ├── config_driven/                      # 15 extraction scripts
│   │   ├── extract_patient_demographics.py
│   │   ├── extract_problem_list_diagnoses.py
│   │   ├── extract_all_procedures_metadata.py
│   │   ├── extract_all_medications_metadata.py
│   │   ├── extract_all_imaging_metadata.py
│   │   ├── extract_all_encounters_metadata.py
│   │   ├── extract_all_measurements_metadata.py
│   │   ├── extract_all_binary_files_metadata.py
│   │   ├── extract_all_molecular_tests_metadata.py
│   │   ├── extract_radiation_data.py          # All 6 radiation outputs
│   │   └── shared_utilities.py
│   ├── documentation/
│   │   ├── STAGING_FILES_CANONICAL_REFERENCE.md
│   │   ├── STAGING_EXTRACTION_MIGRATION_SUMMARY.md
│   │   └── README_ATHENA_EXTRACTION.md
│   ├── patient_config_template.json
│   ├── initialize_patient_config.py
│   └── staging_files/                      # Output directory
│       └── patient_XXXX/                   # Per-patient outputs
│           ├── patient_demographics.csv
│           ├── problem_list_diagnoses.csv
│           └── ...15 total CSV files
│
├── local_llm_extraction/                   # CLEANED: Multi-agent workflows only
│   ├── README.md                           # Updated to focus on multi-agent
│   ├── MULTI_AGENT_BRANCH_README.md
│   ├── event_based_extraction/
│   ├── form_extractors/
│   ├── iterative_extraction/
│   ├── utils/
│   ├── Dictionary/
│   ├── patient_config.json                 # Symlink to staging_extraction/
│   └── [other multi-agent files]
│
└── docs/                                    # PROJECT-WIDE DOCUMENTATION
    ├── multiagent_workflows/               # NEW: Multi-agent docs
    │   ├── WORKFLOW_REQUIREMENTS.md
    │   ├── IMPLEMENTATION_COVERAGE_ANALYSIS.md
    │   └── STAGING_VIEWS_REFERENCE.md
    └── database/                           # NEW: Database docs
        ├── schema/
        └── updates/
            └── DATABASE_UPDATE_2025-10-16.md
```

---

## Move Operations

### Phase 1: Create athena_views/ directory
```bash
mkdir -p athena_views/{views,documentation,verification}
```

### Phase 2: Move Athena view files
```bash
# Move SQL files
mv local_llm_extraction/staging_extraction/ATHENA_VIEW_CREATION_QUERIES.sql \
   athena_views/views/

mv local_llm_extraction/staging_extraction/RERUN_STANDARDIZED_VIEWS.sql \
   athena_views/views/

# Move documentation
mv local_llm_extraction/staging_extraction/ATHENA_VIEW_FIXES.md \
   athena_views/documentation/

mv local_llm_extraction/staging_extraction/PATIENT_IDENTIFIER_ANALYSIS.md \
   athena_views/documentation/

mv local_llm_extraction/staging_extraction/DATE_TIME_STANDARDIZATION_ANALYSIS.md \
   athena_views/documentation/

mv local_llm_extraction/staging_extraction/DATE_STANDARDIZATION_EXAMPLE.sql \
   athena_views/documentation/

mv local_llm_extraction/staging_extraction/STANDARDIZATION_SUMMARY.md \
   athena_views/documentation/

# Move verification files
mv local_llm_extraction/staging_extraction/ATHENA_VIEWS_VERIFICATION.md \
   athena_views/verification/

mv local_llm_extraction/staging_extraction/ATHENA_VIEWS_README.md \
   athena_views/README.md
```

### Phase 3: Rename staging_extraction to top-level
```bash
# Move entire directory up one level
mv local_llm_extraction/staging_extraction staging_extraction

# Move staging_files too
mv local_llm_extraction/staging_files staging_extraction/staging_files
```

### Phase 4: Create symlink for patient_config.json
```bash
# So local_llm_extraction scripts can still find it
cd local_llm_extraction
ln -s ../staging_extraction/patient_config.json patient_config.json
```

### Phase 5: Update documentation references
- Update all README files with new paths
- Update Python scripts that reference staging_extraction/
- Update relative imports

---

## Benefits

### 1. Clear Separation of Concerns
- **athena_views/**: Database layer (SQL views)
- **staging_extraction/**: Extraction scripts (Python → CSV)
- **local_llm_extraction/**: Multi-agent workflows (LLM processing)

### 2. Easier Navigation
- All Athena work in one place
- All staging extraction in one place
- Multi-agent work separate from data extraction

### 3. Better for Collaboration
- Database admins can focus on athena_views/
- Data engineers can focus on staging_extraction/
- ML engineers can focus on local_llm_extraction/

### 4. Cleaner Git History
- Changes to views don't mix with workflow changes
- Easier to track what changed where

### 5. Documentation Hierarchy
- Project-wide docs in docs/
- Component-specific docs in each directory
- Clear README at each level

---

## Implementation Steps

1. ✅ Create new directory structure
2. ✅ Move files to new locations
3. ✅ Update README files
4. ✅ Update relative paths in Python scripts
5. ✅ Create symlinks where needed
6. ✅ Test that all scripts still work
7. ✅ Update .gitignore if needed
8. ✅ Commit with clear message

---

## Git Commit Message

```
refactor: Reorganize multi-agent and staging extraction work

- Create athena_views/ for centralized view management
  - Move all SQL view definitions and documentation
  - Organize into views/, documentation/, verification/

- Move staging_extraction/ to project root
  - Better visibility as standalone component
  - Includes config_driven scripts and outputs

- Clean up local_llm_extraction/
  - Focus on multi-agent workflows only
  - Remove staging extraction overlap

- Update all documentation with new paths
- Create symlinks for backward compatibility

Part of feature/multi-agent-framework branch work (Oct 16-17, 2025)
```

---

## Rollback Plan

If issues arise:
```bash
# Undo all moves
git reset --hard HEAD
git clean -fd
```

Or restore from backup:
```bash
cp -r local_llm_extraction.backup local_llm_extraction
```

---

## Validation Checklist

After restructure, verify:
- [ ] All 15 Athena views documented in athena_views/
- [ ] All 15 extraction scripts in staging_extraction/config_driven/
- [ ] Patient config template accessible from both locations
- [ ] README files updated with correct paths
- [ ] Python imports still work
- [ ] Git status shows expected changes
- [ ] Documentation cross-references correct

---

## Next Steps

1. Review this plan
2. Create backup: `cp -r local_llm_extraction local_llm_extraction.backup`
3. Execute move operations
4. Update documentation
5. Test extraction pipeline
6. Commit changes
