# Security & PHI Protection

## Overview

The ID Crosswalk system handles **Protected Health Information (PHI)** including Medical Record Numbers (MRNs), dates of birth, and patient names. This document details the security architecture and compliance measures implemented to protect this sensitive data.

## PHI Data Handled

### Input Data (High Risk)
- **MRN** (Medical Record Number) - Direct patient identifier
- **DOB** (Date of Birth) - Quasi-identifier
- **First Name** - Quasi-identifier
- **Last Name** - Quasi-identifier
- **Organization Name** - Quasi-identifier (small populations)

### Output Data (Lower Risk)
- **FHIR_ID** - De-identified patient ID (`Patient/xyz123...`)
- **match_strategy** - Metadata about matching process (no PHI)
- **match_database** - Source system (no PHI)

### Not Included (Excluded by Design)
- Social Security Numbers
- Full addresses
- Contact information
- Clinical data

## Security Architecture

### Zero-Display Policy

**Core Principle**: PHI is NEVER displayed in terminal output, logs, or intermediate files.

#### Implementation

```python
# ✓ CORRECT - Aggregate statistics only
logger.info(f"Retrieved {len(df)} records from Athena")
logger.info(f"Matched: {matched_count} records")

# ✗ PROHIBITED - Individual PHI
# logger.info(f"MRN {mrn} matched to FHIR ID {fhir_id}")  # NEVER
# print(f"Patient: {first_name} {last_name}")             # NEVER
```

#### Validation

All log output is reviewed to ensure:
- Only counts and percentages displayed
- No individual record data shown
- No PHI field values printed

### In-Memory Processing

**Architecture**: All matching operations occur in RAM, avoiding persistent PHI storage.

```python
# Load data into memory
df = pd.read_csv(input_file)  # Read once

# All matching in-memory
for idx, row in df.iterrows():
    mrn = str(row['mrn']).strip()  # Exists only in RAM
    # ... matching logic ...
    df.at[idx, 'FHIR_ID'] = fhir_id  # Update in-memory

# Write output once
df.to_csv(output_file)  # Contains FHIR_ID, not MRN context
```

**Benefits**:
- No PHI in temporary files
- No PHI in database logs
- Memory automatically cleared on exit
- No disk caching of sensitive data

### Secure Data Flow

```
┌─────────────────────────────────────────┐
│  Input CSV (PHI-containing)             │
│  Location: Secure filesystem only       │
│  Access: Restricted by OS permissions   │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Python Process Memory (RAM)            │
│  - MRN lookup dictionaries              │
│  - DOB+name dataframes                  │
│  - Matching operations                  │
│  PHI exists ONLY here                   │
└─────────────────┬───────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Output CSV (FHIR_ID + metadata)        │
│  Location: Secure filesystem            │
│  PHI: Only FHIR_ID (de-identified)      │
└─────────────────────────────────────────┘

         (MRN, DOB, names NOT in output)
```

### AWS Security

#### Athena Query Protection

**All queries use parameterized approach** (no PHI in query strings):

```python
# ✓ SECURE - Generic query
query = """
SELECT id, identifier_mrn, birth_date, given_name, family_name
FROM patient
WHERE birth_date IS NOT NULL
"""

# ✗ INSECURE - PHI in query string
# query = f"SELECT * FROM patient WHERE identifier_mrn = '{mrn}'"  # NEVER
```

**Query results**: Fetched once, processed in-memory, never logged.

#### SSO Authentication

```bash
# Required before running scripts
aws sso login --profile radiant-prod
```

**Session expiration**: 4-8 hours (configured in AWS SSO)

**Audit trail**: All AWS API calls logged in CloudTrail (not accessible to script)

### Output File Protection

#### File Permissions

```bash
# Recommended: Restrict output file access
chmod 600 output_file.csv  # Owner read/write only
```

#### .gitignore Configuration

```bash
# Prevent accidental commits
outputs/*.csv
outputs/*.xlsx
outputs/*.json
*.csv  # Be aggressive - don't commit any CSVs
```

#### Encryption at Rest

**Recommended setup**:
```bash
# macOS FileVault (full disk encryption)
# Enable in System Preferences > Security & Privacy > FileVault

# Alternatively, encrypt specific directories
# Use encrypted disk images or volumes
```

## Compliance Framework

### HIPAA Compliance

#### Required Safeguards (45 CFR § 164.312)

| Requirement | Implementation |
|-------------|----------------|
| **Access Control** | OS-level file permissions, AWS SSO |
| **Audit Controls** | AWS CloudTrail, script execution logs (no PHI) |
| **Integrity** | Hash verification of input/output files (optional) |
| **Transmission Security** | HTTPS for AWS API calls, encrypted filesystem |

#### Administrative Safeguards (45 CFR § 164.308)

| Requirement | Implementation |
|-------------|----------------|
| **Risk Analysis** | This document, threat modeling |
| **Workforce Training** | Documentation review required before use |
| **Access Authorization** | AWS IAM roles, OS-level permissions |
| **Incident Response** | See "Incident Response" section below |

### IRB Compliance

**Study approval required**:
- IRB protocol number: [TO BE FILLED]
- Data Use Agreement: CBTN DUA on file
- Informed consent: Per CBTN protocol

**Approved uses**:
- Linking research IDs to clinical FHIR data
- Aggregate analysis (no individual identification)
- Quality assurance of data matching

**Prohibited uses**:
- Re-identification of patients
- Contact of patients
- Sharing outside authorized team

### Data Governance

#### Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| MRN, DOB, Names | **Highly Restricted** | In-memory only, never logged |
| FHIR_ID | **Restricted** | De-identified, but still controlled |
| Match statistics | **Internal** | Can be shared within team |
| Code/algorithms | **Public** | Can be open-sourced (no data) |

#### Retention Policy

- **Input files**: Delete after successful matching (or archive encrypted)
- **Output files**: Retain per IRB protocol (typically 7 years)
- **Logs**: Retain 90 days (no PHI, statistical only)
- **Code**: Version control, no expiration

## Security Best Practices

### Before Running

1. **Verify AWS SSO session**:
   ```bash
   aws sts get-caller-identity --profile radiant-prod
   ```

2. **Check file permissions**:
   ```bash
   ls -la input_file.csv
   # Should show restricted access (e.g., -rw------- or -rw-r-----)
   ```

3. **Ensure secure location**:
   ```bash
   # Run on encrypted volume only
   # NOT in /tmp, ~/Downloads (if not encrypted), or shared folders
   ```

### During Execution

1. **No screen sharing** during runs that display counts by institution
2. **Close terminals** when not in use
3. **Monitor memory usage** (should be <100MB for typical datasets)

### After Running

1. **Verify output**:
   ```bash
   # Check that output contains FHIR_ID, not MRN
   head -1 output_file.csv  # Should show column headers
   # Verify no MRN column in output
   ```

2. **Secure output file**:
   ```bash
   chmod 600 output_file.csv
   # Move to secure storage
   mv output_file.csv /secure/location/
   ```

3. **Clear terminal history** (optional, for extra security):
   ```bash
   history -c  # Clear bash/zsh history
   ```

## Threat Model

### Identified Threats

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|------------|
| **Accidental PHI logging** | Medium | High | Code review, no logging of variables |
| **Output file left unsecured** | Medium | High | Documentation, .gitignore, file permissions |
| **AWS credentials compromised** | Low | Critical | SSO with MFA, session timeout |
| **Git commit of PHI** | Low | High | .gitignore, pre-commit hooks |
| **Screen sharing exposure** | Low | Medium | Training, awareness |
| **Memory dump** | Very Low | High | Process isolation, OS security |

### Residual Risks

1. **OS-level compromise**: If attacker has root access, can read process memory
   - **Mitigation**: Rely on OS security, encrypted filesystem

2. **Athena query logs**: Queries visible in AWS console (but no PHI in queries)
   - **Mitigation**: Generic queries only, results not logged

3. **Swap space**: OS may page memory to disk
   - **Mitigation**: Encrypted swap (FileVault on macOS)

## Incident Response

### PHI Breach Scenarios

#### Scenario 1: Accidental Git Commit

**If output file accidentally committed**:

1. **Immediately**:
   ```bash
   git reset --hard HEAD~1  # Undo commit (if not pushed)
   # OR
   git rebase -i HEAD~1  # Remove commit from history
   ```

2. **If already pushed**:
   ```bash
   # Contact repository admin immediately
   # Force push may be required (breaks others' history)
   git push --force-with-lease origin main
   ```

3. **Report incident** to:
   - IRB coordinator
   - Institutional compliance office
   - CBTN data team

4. **Document**:
   - What data was exposed
   - How long it was accessible
   - Who had access
   - Remediation steps taken

#### Scenario 2: Log File Contains PHI

**If PHI accidentally logged**:

1. **Immediately delete log file**:
   ```bash
   rm -f log_file.txt
   shred -u log_file.txt  # Secure deletion (Linux)
   srm log_file.txt       # Secure deletion (macOS)
   ```

2. **Review code** to prevent recurrence

3. **Report incident** (same as above)

#### Scenario 3: Unsecured Output File

**If output file permissions too permissive**:

1. **Immediately restrict**:
   ```bash
   chmod 600 output_file.csv
   ```

2. **Check who had access**:
   ```bash
   ls -l output_file.csv  # Check creation time
   last  # Check who was logged in
   ```

3. **Assess exposure** and report if necessary

### Reporting Requirements

**Report to IRB within 5 business days** if:
- PHI exposed to unauthorized individuals
- PHI transmitted insecurely
- Data breach affects >10 subjects

**Report to CBTN immediately** if:
- CBTN data involved in breach
- External party gained access

### Contact Information

- **IRB Office**: [TO BE FILLED]
- **Compliance Officer**: [TO BE FILLED]
- **CBTN Data Coordinator**: [TO BE FILLED]
- **IT Security**: [TO BE FILLED]

## Audit & Monitoring

### Execution Logs

**What is logged** (no PHI):
```
2025-10-26 12:43:22 - INFO - Total records: 6,599
2025-10-26 12:43:29 - INFO - Matched: 2,650 records (40.2%)
2025-10-26 12:43:29 - INFO - CHOP MRN exact match: 1,843 records
```

**What is NOT logged**:
- Individual MRNs, DOBs, names
- FHIR_IDs for specific patients
- Any record-level data

### Access Logs

**AWS CloudTrail** automatically logs:
- Who ran Athena queries
- When queries executed
- What databases accessed

**OS-level logging** (if enabled):
- File access times
- Process execution
- User logins

### Regular Audits

**Monthly**:
- Review .gitignore effectiveness
- Check for committed output files
- Verify file permissions on secure storage

**Quarterly**:
- Code review for PHI exposure risks
- Update threat model
- Training refresher for team

**Annually**:
- Full security assessment
- IRB protocol renewal
- Update documentation

## Training Requirements

### Required Reading

Before using ID Crosswalk system:
- [ ] This document (SECURITY.md)
- [ ] MATCHING_STRATEGY.md (understand data flow)
- [ ] README.md (usage guidelines)
- [ ] Institutional HIPAA training (current certification)

### Competency Checklist

- [ ] Can identify PHI in dataset
- [ ] Knows what can/cannot be logged
- [ ] Understands in-memory processing model
- [ ] Can secure output files properly
- [ ] Knows how to report incidents
- [ ] Familiar with .gitignore usage

### Annual Refresher

All users must:
- Re-read security documentation
- Acknowledge understanding
- Complete HIPAA recertification

## Code Review Checklist

Before committing changes to scripts:

- [ ] No `print()` or `logger.info()` statements with PHI variables
- [ ] No PHI in SQL query strings
- [ ] All matching operations in-memory
- [ ] No intermediate files with PHI
- [ ] .gitignore includes all output patterns
- [ ] Documentation updated if security model changes

## References

- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [Python Secure Coding Guidelines](https://wiki.sei.cmu.edu/confluence/display/java/SEI+CERT+Oracle+Coding+Standard+for+Java)

---

**Document Version**: 1.0  
**Last Updated**: October 26, 2025  
**Classification**: Internal Use Only  
**Author**: RADIANT/BRIM Analytics Team
