
================================================================================
COMPREHENSIVE BRIM VALIDATION ANALYSIS
================================================================================
Generated: 2025-10-02 22:40:13
Patient: C1277724 (FHIR ID: e4BwD8ZYDBccepXcJ.Ilo3w3)

================================================================================
1. STRUCTURED DATA EXTRACTION (From Materialized Views)
================================================================================

Source: pilot_output/structured_data_enhanced.json
Extraction Time: 2025-10-02T20:20:41.500594

--------------------------------------------------------------------------------
1.1 Surgeries (from Procedure materialized view)
--------------------------------------------------------------------------------
Count: 6

Gold Standard: 2 neurosurgeries
Materialized View: 6 procedures

⚠️  DISCREPANCY: Materialized view has 4 extra procedures

  1. VENTRICULOCISTERNOSTOMY 3RD VNTRC *
     CPT: 62201
     Date: 

  2. CRNEC INFRATNTOR/POSTFOSSA EXC/FENESTRATION CYST
     CPT: 61524
     Date: 

  3. CRANIEC TREPHINE BONE FLP BRAIN TUMOR SUPRTENTOR
     CPT: 61510
     Date: 

  4. CRANIECTOMY, CRANIOTOMY POSTERIOR FOSSA/SUBOCCIPITAL BRAIN TUMOR RESECTION
     CPT: 61518
     Date: 

  5. ENDOSCOPIC THIRD VENTRICULOSTOMY
     CPT: 62201
     Date: 

  6. CRANIECTOMY W/EXCISION TUMOR/LESION SKULL
     CPT: 61500
     Date: 2018-05-28

--------------------------------------------------------------------------------
1.2 Molecular Markers (from Observation materialized view)
--------------------------------------------------------------------------------
Count: 1 genes

  BRAF:
    Next generation sequencing (NGS) analysis of genes in the CHOP Comprehensive ;;Solid Tumor NGS Panel performed on the DNA and RNA extracted from the s...

--------------------------------------------------------------------------------
1.3 Treatments (from MedicationRequest materialized view)
--------------------------------------------------------------------------------
Total records: 48
Unique medications: 5

Medications: ['bevacizumab 625 mg in sodium chloride 0.9% 100 mL infusion', 'bevacizumab infusion', 'bevacizumab 600 mg in sodium chloride 0.9% 100 mL infusion', 'bevacizumab 575 mg in sodium chloride 0.9% 100 mL infusion', 'bevacizumab 550 mg in sodium chloride 0.9% 100 mL infusion']

================================================================================
2. BRIM INPUT (project.csv)
================================================================================

Total documents: 45

Document type breakdown:
  - Pathology study: 20
  - OP Note - Complete (Template or Full Dictation): 4
  - Anesthesia Postprocedure Evaluation: 4
  - Anesthesia Preprocedure Evaluation: 4
  - OP Note - Brief (Needs Dictation): 3
  - Anesthesia Procedure Notes: 3
  - Procedures: 2
  - FHIR_BUNDLE: 1
  - Molecular Testing Summary: 1
  - Surgical History Summary: 1
  - Treatment History Summary: 1
  - Diagnosis Date Summary: 1

--------------------------------------------------------------------------------
2.1 Structured Finding Documents Included
--------------------------------------------------------------------------------

Count: 4

  ✓ STRUCTURED_molecular_markers
    Title: Molecular Testing Summary
    Date: 2025-10-03T00:56:40.275185Z
    Text Length: 789 chars

  ✓ STRUCTURED_surgeries
    Title: Surgical History Summary
    Date: 2025-10-03T00:56:40.275190Z
    Text Length: 1019 chars

  ✓ STRUCTURED_treatments
    Title: Treatment History Summary
    Date: 2019-07-02T17:05:22Z
    Text Length: 940 chars

  ✓ STRUCTURED_diagnosis_date
    Title: Diagnosis Date Summary
    Date: 2018-06-04
    Text Length: 127 chars

================================================================================
3. BRIM EXTRACTION RESULTS
================================================================================

Total extractions: 217
Variables extracted: 19
Documents processed: 46

--------------------------------------------------------------------------------
3.1 Extraction by Scope
--------------------------------------------------------------------------------
  Many Labels Per Note: 162 rows
  One Label Per Note: 42 rows
  One Label Per Patient: 8 rows
  Patient-Level Dependent Variable: 5 rows

--------------------------------------------------------------------------------
3.2 Critical Variable Extractions
--------------------------------------------------------------------------------

Surgery Detection:
  surgery_date extractions: 24
  Unique dates: 9
  Dates: ['2018-05-28', '2018-05-29', '2018-06-04', '2021-03-10', '2021-03-14', '2021-03-16', '2021-03-20', '2022-09-13', '2025-10-03']
  total_surgeries (dependent var): 8
  Gold standard: 2
  ❌ INCORRECT: Got 8 instead of 2

Molecular Detection:
  idh_mutation: no
  molecular_profile (dependent var): IDH mutation: no
  Gold standard: KIAA1549-BRAF fusion
  ❌ INCORRECT: Said 'no' but BRAF fusion is in structured_data!

Extractions from STRUCTURED documents: 33
  ✓ BRIM DID process structured finding documents

  Variables extracted from STRUCTURED docs:

    STRUCTURED_surgeries:
      - surgery_date: ['2018-05-28']
      - surgery_type: ['OTHER' 'RESECTION']
      - extent_of_resection: ['not specified']
      - surgery_location: ['ventricles' 'posterior fossa' 'supratentorial']
      - document_type: ['OPERATIVE_NOTE']

    STRUCTURED_treatments:
      - extent_of_resection: ['not specified']
      - chemotherapy_agent: ['bevacizumab']
      - document_type: ['OTHER']

    STRUCTURED_molecular_markers:
      - surgery_date: ['2025-10-03']
      - chemotherapy_agent: ['None identified']
      - extent_of_resection: ['not specified']
      - document_type: ['OTHER']

    STRUCTURED_diagnosis_date:
      - surgery_date: ['2018-06-04']
      - extent_of_resection: ['not specified']

================================================================================
4. ROOT CAUSE ANALYSIS
================================================================================

--------------------------------------------------------------------------------
4.1 Surgery Count Problem
--------------------------------------------------------------------------------

Gold Standard: 2 neurosurgeries
Materialized View: 6 procedures (includes non-surgical)
BRIM Extracted: 9 unique dates
BRIM Aggregated: 8

✓ STRUCTURED_surgeries document WAS created with 6 procedures
✓ STRUCTURED_surgeries document WAS included in project.csv
✓ BRIM DID extract from STRUCTURED_surgeries

Reasoning from BRIM:
  "Counted distinct surgery_date values. Context does not provide surgery_type, surgery_location, or narrative text descriptions to apply the full instructions."

❌ PROBLEM: Decision logic in decisions.csv is NOT filtering properly
   - It's counting unique surgery_date values
   - But surgery_date was extracted from anesthesia notes, pathology, etc.
   - Not filtering by surgery_type or CPT codes

--------------------------------------------------------------------------------
4.2 Molecular Marker Problem
--------------------------------------------------------------------------------

Gold Standard: KIAA1549-BRAF fusion
Materialized View: Has BRAF finding: "Next generation sequencing (NGS) analysis of genes in the CHOP Comprehensive ;;Solid Tumor NGS Panel..."

✓ STRUCTURED_molecular_markers document WAS created
✓ STRUCTURED_molecular_markers document WAS included in project.csv
⚠️  BRIM did NOT extract molecular variables from STRUCTURED doc

Reasoning from BRIM:
  "The context mentions a KIAA1549-BRAF fusion which is consistent with the pathologic diagnosis of pilocytic astrocytoma. This type of tumor is typically associated with the absence of IDH mutations. Th..."

❌ PROBLEM: Variable instruction doesn't explicitly search STRUCTURED_molecular_markers
   - Prompt searches FHIR Observations, pathology reports, clinical notes
   - But doesn't prioritize STRUCTURED_molecular_markers document
   - BRAF fusion text IS in the structured document but LLM missed it

================================================================================
5. DEDUPLICATION IMPACT
================================================================================

Original project.csv: 89 rows
Deduplicated project_dedup.csv: 45 rows
Rows removed: 44

✅ NO structured documents were removed by deduplication
   All 4 STRUCTURED_* documents are in final project_dedup.csv

================================================================================
6. AGGREGATION LOGIC ANALYSIS (decisions.csv)
================================================================================

--------------------------------------------------------------------------------
6.1 total_surgeries Decision
--------------------------------------------------------------------------------

Instruction: Count total unique surgical procedures across patient entire treatment history (longitudinal data). METHOD: 1) Count distinct surgery_date values where surgery_type != OTHER. 2) ALSO count surgeries mentioned in narrative without structured dates - look for: "prior craniotomy", "previous resection",...

Variables used: ["surgery_date", "surgery_type", "surgery_location"]

❌ PROBLEM:
   Instruction says to count distinct surgery_date where surgery_type != OTHER
   But reasoning shows: 'Context does not provide surgery_type'
   This means BRIM's aggregation doesn't have access to all extracted values
   It only sees surgery_date values, not the associated surgery_type!

--------------------------------------------------------------------------------
6.2 molecular_profile Decision
--------------------------------------------------------------------------------

Instruction: Summarize molecular/genetic testing results
Variables used: ["idh_mutation", "mgmt_methylation"]

❌ PROBLEM:
   Decision only aggregates idh_mutation and mgmt_methylation
   Doesn't look at raw molecular text or BRAF findings
   If idh_mutation extraction fails, the aggregation can't fix it

================================================================================
7. RECOMMENDATIONS
================================================================================

1. IMPROVE VARIABLE INSTRUCTIONS
   a. molecular markers: Explicitly search STRUCTURED_molecular_markers first
      Add: 'PRIORITY: Search NOTE_ID=STRUCTURED_molecular_markers document'
   
   b. surgery_count: Strengthen filtering in base variable, not just decision
      Add: 'ONLY count if NOTE_TITLE contains OP Note OR CPT code 61000-62258'

2. FIX AGGREGATION LOGIC
   a. total_surgeries decision needs access to surgery_type for filtering
      Currently only sees surgery_date values without context
   
   b. Consider creating intermediate aggregations:
      - neurosurgical_dates: Filter surgery_date where surgery_type=RESECTION|DEBULKING
      - total_surgeries: Count unique neurosurgical_dates

3. ENHANCE STRUCTURED DATA EXTRACTION
   a. Surgeries: Only include CPT codes 61000-62258 (neurosurgical range)
      Currently includes all procedures (shunts, biopsies, etc.)
   
   b. Add dates to surgeries from Procedure.performedDateTime
      Currently many surgeries have empty date field

4. VALIDATION WORKFLOW
   ✅ Structured data extraction: WORKING
   ✅ Document synthesis: WORKING (STRUCTURED_* docs created)
   ✅ Upload to BRIM: WORKING (docs included, not lost in dedup)
   ✅ BRIM processing: WORKING (docs were processed)
   ❌ Variable instructions: NEED IMPROVEMENT (don't prioritize structured docs)
   ❌ Aggregation logic: PARTIAL (lacks context for proper filtering)

================================================================================
8. SUMMARY
================================================================================

The structured data extraction workflow is FUNCTIONING:
  • Materialized views → structured_data.json ✓
  • structured_data.json → STRUCTURED_* documents ✓
  • STRUCTURED_* documents → project.csv ✓
  • Deduplication preserved structured docs ✓
  • BRIM processed structured docs ✓

The PROBLEMS are in:
  1. Variable instructions don't explicitly prioritize structured docs
  2. Aggregation decisions lack contextual info for proper filtering
  3. Structured data includes too many procedures (not pre-filtered)

The FIX is NOT in the deduplication workflow.
The FIX is in:
  1. Improving variable prompts (tell LLM to search STRUCTURED docs first)
  2. Fixing decision logic (better access to multi-variable context)
  3. Pre-filtering structured data (only include true neurosurgeries)