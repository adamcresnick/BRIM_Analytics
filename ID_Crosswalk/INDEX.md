# ID Crosswalk - Complete Documentation Index

## 📁 Directory Structure

```
ID_Crosswalk/
├── README.md                    # Main project overview, performance metrics, quick start
├── CHANGELOG.md                 # Version history, migration notes, release notes
│
├── scripts/                     # Python scripts for matching
│   ├── match_cbtn_multi_database.py           # ★ PRODUCTION: Generic MRN+DOB matching
│   ├── match_cbtn_mrn_to_fhir_id.py          # Legacy: Basic MRN-only (v1.0.0)
│   ├── match_cbtn_mrn_to_fhir_id_with_padding.py  # Legacy: MRN padding test (v1.0.1)
│   └── list_athena_databases.py               # Utility: List Athena databases
│
├── outputs/                     # Match results (gitignored - contains PHI)
│   ├── .gitignore              # Prevents accidental PHI commits
│   └── [*.csv files]           # Generated output files (not in git)
│
└── docs/                        # Comprehensive documentation
    ├── MATCHING_STRATEGY.md    # Technical algorithm details
    ├── SECURITY.md             # PHI protection, HIPAA compliance
    ├── VERIFICATION_GUIDE.md   # Manual review procedures for VERIFY records
    └── USAGE_EXAMPLES.md       # 16 practical examples and recipes
```

---

## 📖 Documentation Guide

### For New Users - Start Here

1. **[README.md](../README.md)** - 10-minute overview
   - What this project does
   - Performance metrics
   - Quick start guide
   - Directory structure

2. **[docs/USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md)** - Practical recipes
   - Quick start examples (3 examples)
   - Advanced use cases (incremental updates, re-runs, database-specific)
   - Analysis & reporting
   - Troubleshooting

### For Data Analysts - Core Workflow

3. **[scripts/match_cbtn_multi_database.py](../scripts/match_cbtn_multi_database.py)** - Production script
   - Run matching across CHOP + UCSF databases
   - Generic MRN+DOB strategy
   - Outputs: CSV with FHIR_ID + match_strategy + match_database columns

4. **[docs/VERIFICATION_GUIDE.md](docs/VERIFICATION_GUIDE.md)** - Manual review
   - 700 VERIFY-flagged records (26.4% of matches)
   - Common name variation patterns
   - Step-by-step verification workflow
   - QA procedures

### For Technical Staff - Deep Dive

5. **[docs/MATCHING_STRATEGY.md](docs/MATCHING_STRATEGY.md)** - Algorithm details
   - Two-tier approach (MRN → DOB fallback)
   - Progressive name matching strategies
   - Confidence scoring logic
   - Performance characteristics

6. **[docs/SECURITY.md](docs/SECURITY.md)** - Compliance & security
   - Zero-display PHI policy
   - In-memory processing architecture
   - HIPAA compliance checklist
   - Threat model & incident response

### For Project Managers - History & Planning

7. **[CHANGELOG.md](../CHANGELOG.md)** - Version tracking
   - Release history (v0.9.0 → v1.3.0)
   - Performance comparison table
   - Migration notes between versions
   - Planned features

---

## 🎯 Quick Reference by Task

| I want to... | Read this... |
|--------------|-------------|
| **Run matching for the first time** | README.md → Quick Start section |
| **Understand match results** | README.md → Performance Summary section |
| **Review VERIFY-flagged records** | docs/VERIFICATION_GUIDE.md |
| **Re-run matching for new data** | docs/USAGE_EXAMPLES.md → Example 1 (Incremental Updates) |
| **Troubleshoot missing matches** | docs/USAGE_EXAMPLES.md → Example 12 (Debug Missing Matches) |
| **Understand the algorithm** | docs/MATCHING_STRATEGY.md |
| **Check security compliance** | docs/SECURITY.md |
| **Add a new database** | docs/MATCHING_STRATEGY.md → Future Enhancements section |
| **Compare v1 vs v3 results** | CHANGELOG.md → Version Comparison Summary |
| **Report a security issue** | docs/SECURITY.md → Incident Response section |

---

## 📊 Key Performance Metrics

### Current (v1.3.0)

- **Total enrollment records**: 6,599
- **Total matches**: 2,650 (40.2%)
- **High-confidence matches**: 1,950 (73.6% of matches)
- **Needs verification**: 700 (26.4% of matches)
- **Unmatched**: 3,949 (59.8%)

### By Database

| Database | Matches | Match Rate | MRN Exact | DOB Fallback |
|----------|---------|------------|-----------|--------------|
| CHOP | 1,877 | 84.4% | 1,241 | 636 |
| UCSF | 149 | 47.5% | 0 | 149 |

### By Match Strategy

| Strategy | Count | % of Matches | Confidence |
|----------|-------|--------------|------------|
| MRN exact | 1,241 | 46.8% | High |
| DOB + exact name | 387 | 14.6% | High |
| DOB + name initial | 322 | 12.1% | Medium-High |
| DOB only (single) | 700 | 26.4% | Medium (_VERIFY) |

---

## 🔄 Workflow Overview

```
┌─────────────────────────────────────────────────────────┐
│ 1. PREPARE INPUT DATA                                   │
│    stg_cbtn_enrollment_final_10262025.csv (6,599 rows)  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 2. RUN MATCHING                                         │
│    scripts/match_cbtn_multi_database.py                 │
│    - Query CHOP & UCSF Athena databases                 │
│    - Apply MRN exact matching                           │
│    - Apply DOB+name fallback (4 strategies)             │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 3. REVIEW RESULTS                                       │
│    outputs/stg_cbtn_enrollment_with_fhir_id_generic.csv │
│    - 2,650 matches (40.2%)                              │
│    - 3,949 unmatched (59.8%)                            │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 4. VERIFY FLAGGED RECORDS                               │
│    docs/VERIFICATION_GUIDE.md                           │
│    - Extract 700 _VERIFY records                        │
│    - Manual review (nickname, typo, name variations)    │
│    - CONFIRM or REJECT each match                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 5. EXPORT FOR DOWNSTREAM USE                            │
│    docs/USAGE_EXAMPLES.md → Example 10                  │
│    - High-confidence matches only (1,950 records)       │
│    - Feed to BRIM Analytics extraction pipeline         │
│    - Or generate Athena SQL for further analysis        │
└─────────────────────────────────────────────────────────┘
```

---

## 🔒 Security Checklist

Before using ID Crosswalk outputs:

- [ ] Verify AWS SSO session active (`aws sso login --profile radiant-prod`)
- [ ] Confirm output files saved to secure location (e.g., `~/Downloads`, not shared drives)
- [ ] Check that no MRN/DOB/names logged to terminal (review script output)
- [ ] Encrypt output files if transferring (`openssl enc -aes-256-cbc -in file.csv -out file.csv.enc`)
- [ ] Delete outputs after downstream processing complete
- [ ] Review VERIFY records in secure environment only
- [ ] Document verification decisions with rationale
- [ ] Report any PHI exposure incidents immediately (see docs/SECURITY.md)

---

## 🚀 Quick Commands

### Run full matching (CHOP + UCSF)
```bash
cd /Users/resnick/Documents/GitHub/RADIANT_PCA/BRIM_Analytics/ID_Crosswalk

python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --output ~/Downloads/stg_cbtn_enrollment_with_fhir_id_generic.csv \
  --databases chop ucsf
```

### Test connection only
```bash
python3 scripts/match_cbtn_multi_database.py \
  --input ~/Downloads/stg_cbtn_enrollment_final_10262025.csv \
  --dry-run
```

### List available databases
```bash
python3 scripts/list_athena_databases.py
```

### Extract verification queue
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('outputs/stg_cbtn_enrollment_with_fhir_id_generic.csv')
verify_df = df[df['match_strategy'].str.contains('VERIFY', na=False)]
verify_df.to_csv('outputs/verification_queue.csv', index=False)
print(f'{len(verify_df)} records need verification')
"
```

---

## 📞 Support & Contact

### For Questions
- **General questions**: Contact RADIANT/BRIM Analytics team
- **Technical issues**: File issue in GitHub repository
- **Security concerns**: Contact compliance officer immediately

### For Verification Help
- **Uncertain matches**: Consult with clinical team lead
- **Systematic issues**: Contact data quality team
- **Process improvements**: Contact senior data analyst

---

## 🔮 Future Enhancements

See [CHANGELOG.md](../CHANGELOG.md) → Unreleased section for planned features:

- Interactive verification UI
- Additional database support (Stanford, Seattle Children's)
- ML-based name similarity scoring
- Automated notifications for new enrollment data

---

## 📄 License & Compliance

- **Classification**: Internal Use Only - CHOP/RADIANT/BRIM Analytics
- **Data Sensitivity**: Contains PHI - Restricted Access
- **Compliance**: HIPAA, IRB approval required for research use
- **Version**: 1.3.0
- **Last Updated**: October 26, 2025
- **Maintained by**: RADIANT/BRIM Analytics Team

---

**This index is your starting point. Follow the links to dive deeper into any topic.**
