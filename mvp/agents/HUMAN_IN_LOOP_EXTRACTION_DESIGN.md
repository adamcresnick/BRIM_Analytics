# Human-in-the-Loop Multi-Agent Clinical Data Extraction

**Date**: 2025-10-20
**Status**: Design Proposal
**Goal**: Interactive extraction workflow with real-time quality control and multi-source reconciliation

---

## Problem Statement

Current extraction pipeline revealed issues:
1. **Temporal inconsistencies**: "Increased" → "Decreased" in 2 days (likely duplicates)
2. **Wrong extraction type**: "Gross Total Resection" appearing as tumor_status instead of extent_of_resection
3. **Duplicate events**: Same dates appearing multiple times (2018-08-03, 2018-09-07)
4. **Single-source limitations**: Only using imaging text reports, missing PDF reports, progress notes, operative reports

**Goal**: Enable human orchestrator (you) to work interactively with extraction agents to review, query, and reconcile inconsistencies as they occur.

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                HUMAN ORCHESTRATOR (You via Claude)                   │
│                                                                       │
│  • Reviews extractions in real-time                                  │
│  • Queries agents about reasoning                                    │
│  • Flags inconsistencies                                             │
│  • Requests multi-source reconciliation                              │
│  • Approves/overrides extractions                                    │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
            ┌───────────┴────────────┐
            │                        │
    ┌───────▼──────┐        ┌────────▼────────┐
    │ QA Agent      │        │  Extraction     │
    │ (MedGemma)    │        │  Agents         │
    │               │        │  (MedGemma)     │
    │ • Explains    │        │                 │
    │ • Re-reviews  │        │ • Imaging text  │
    │ • Reconciles  │        │ • Imaging PDFs  │
    │               │        │ • Progress notes│
    └───────┬───────┘        │ • Op reports    │
            │                └────────┬─────────┘
            └──────────┬──────────────┘
                       │
            ┌──────────▼───────────┐
            │ Extraction Monitor    │
            │                       │
            │ • Detects duplicates  │
            │ • Flags temporal gaps │
            │ • Checks consistency  │
            │ • Generates alerts    │
            └──────────┬────────────┘
                       │
            ┌──────────▼───────────────┐
            │  Timeline Database       │
            │                          │
            │  • Events                │
            │  • Extracted variables   │
            │  • QA flags              │
            │  • Human decisions       │
            │  • Multi-source links    │
            └──────────────────────────┘
```

---

## Core Components

### 1. Extraction Monitor (Automated QA)

**Purpose**: Automatically detect issues that require human review

```python
class ExtractionMonitor:
    """
    Real-time monitoring for extraction quality issues
    """

    def check_extraction(
        self,
        patient_id: str,
        new_extraction: Dict[str, Any],
        timeline_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check extraction for issues requiring human review

        Returns:
            {
                'requires_review': bool,
                'issues': List[str],
                'severity': 'low' | 'medium' | 'high',
                'suggested_actions': List[str]
            }
        """
        issues = []

        # Check 1: Duplicate event (same date as prior event)
        if self._is_duplicate_event(patient_id, new_extraction):
            issues.append({
                'type': 'duplicate_event',
                'severity': 'high',
                'message': f"Event on {new_extraction['event_date']} may be duplicate",
                'action': 'Skip or merge with existing event'
            })

        # Check 2: Temporal inconsistency (rapid status flip)
        temporal_issue = self._check_temporal_consistency(
            patient_id, new_extraction, timeline_context
        )
        if temporal_issue:
            issues.append(temporal_issue)

        # Check 3: Wrong extraction type
        if self._is_wrong_extraction_type(new_extraction):
            issues.append({
                'type': 'wrong_extraction_type',
                'severity': 'high',
                'message': f"'{new_extraction['value']}' is EOR, not tumor_status",
                'action': 'Re-extract with correct type'
            })

        # Check 4: Low confidence
        if new_extraction['confidence'] < 0.75:
            issues.append({
                'type': 'low_confidence',
                'severity': 'medium',
                'message': f"Confidence {new_extraction['confidence']:.2f} below threshold",
                'action': 'Human review or multi-source validation'
            })

        # Check 5: Missing context (no prior imaging for comparison)
        if new_extraction['variable_name'] == 'tumor_status':
            if not timeline_context.get('prior_imaging'):
                issues.append({
                    'type': 'missing_comparison',
                    'severity': 'medium',
                    'message': 'No prior imaging available for comparison',
                    'action': 'Review classification confidence'
                })

        return {
            'requires_review': len(issues) > 0,
            'issues': issues,
            'severity': max([i['severity'] for i in issues], default='low'),
            'suggested_actions': [i['action'] for i in issues]
        }

    def _is_duplicate_event(self, patient_id: str, extraction: Dict) -> bool:
        """Check if event date already exists for same event type"""
        existing = self.timeline.query_events(
            patient_id=patient_id,
            event_type='Imaging',
            event_date=extraction['event_date']
        )
        return len(existing) > 0

    def _check_temporal_consistency(
        self,
        patient_id: str,
        extraction: Dict,
        context: Dict
    ) -> Optional[Dict]:
        """Check for rapid status changes"""
        prior_status = context.get('prior_tumor_status')

        if not prior_status:
            return None

        # "Increased" → "Decreased" in < 7 days is suspicious
        if (prior_status['value'] == 'Increased' and
            extraction['value'] == 'Decreased'):

            days_diff = (extraction['event_date'] - prior_status['event_date']).days

            if days_diff < 7:
                return {
                    'type': 'temporal_inconsistency',
                    'severity': 'high',
                    'message': f"Status changed Increased→Decreased in {days_diff} days",
                    'action': 'Check for treatment intervention or verify with progress notes'
                }

        return None

    def _is_wrong_extraction_type(self, extraction: Dict) -> bool:
        """Check if value belongs to different extraction type"""
        EOR_VALUES = ['Gross Total Resection', 'Near Total Resection',
                      'Subtotal Resection', 'Biopsy Only']

        if extraction['variable_name'] == 'tumor_status':
            return extraction['value'] in EOR_VALUES

        return False
```

---

### 2. QA Agent (Interactive Question-Answering)

**Purpose**: Answer human questions about extraction reasoning

```python
class QAAgent:
    """
    Interactive agent for explaining and re-reviewing extractions
    """

    def __init__(self, medgemma_agent):
        self.medgemma = medgemma_agent

    def explain_extraction(
        self,
        extraction: Dict[str, Any],
        source_text: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Explain why extraction was made

        Example question from human:
        "Why did you classify this as 'Increased' when it was 'Decreased'
        just 2 days prior?"
        """

        prompt = f"""You previously classified this imaging report as:

**Classification**: {extraction['variable_name']} = {extraction['value']}
**Confidence**: {extraction['confidence']}
**Date**: {extraction['event_date']}

**Source Report**:
{source_text}

**Prior Context**:
{self._format_context(context)}

**Question**: Explain your reasoning for this classification.
- What specific phrases led to this decision?
- Why did you choose '{extraction['value']}' over alternatives?
- Did you consider the temporal context (prior status)?

Provide a structured explanation with direct quotes from the report."""

        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are explaining your previous extraction decision.",
            expected_schema={
                "required": ["explanation", "key_phrases", "alternatives_considered"]
            }
        )

        return result.raw_response

    def re_review_with_additional_sources(
        self,
        original_extraction: Dict[str, Any],
        additional_sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Re-extract using multiple sources for validation

        Example sources:
        - Imaging PDF (full radiology report)
        - Progress note 2 days after imaging
        - Operative report (if within window)
        """

        prompt = f"""Re-review tumor status classification using multiple sources.

**ORIGINAL CLASSIFICATION** (from imaging text report):
- Value: {original_extraction['value']}
- Confidence: {original_extraction['confidence']}
- Date: {original_extraction['event_date']}

**ORIGINAL REPORT**:
{original_extraction['source_text']}

---

**ADDITIONAL SOURCES**:
"""

        for i, source in enumerate(additional_sources, 1):
            prompt += f"""
Source {i}: {source['type']} ({source['date']})
{source['text']}

---
"""

        prompt += f"""
**TASK**: Provide updated classification considering ALL sources.

1. Do sources agree or conflict?
2. Does progress note mention treatment changes that explain imaging changes?
3. Does operative report provide context (e.g., post-op changes)?
4. Final classification: NED / Stable / Increased / Decreased / New_Malignancy
5. Updated confidence (0.0-1.0)
6. Recommendation: Approve / Human review needed

Output as JSON."""

        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are performing multi-source clinical data reconciliation.",
            expected_schema={
                "required": [
                    "source_agreement",
                    "final_classification",
                    "confidence",
                    "explanation",
                    "requires_human_review"
                ]
            }
        )

        return result.extracted_data

    def answer_custom_question(
        self,
        question: str,
        extraction_context: Dict[str, Any]
    ) -> str:
        """
        Answer arbitrary human question about extraction

        Examples:
        - "Is this actually a duplicate of the prior scan?"
        - "What evidence suggests progression vs pseudoprogression?"
        - "Should we trust this low-confidence extraction?"
        """

        prompt = f"""A human reviewer has a question about an extraction.

**Extraction Context**:
{json.dumps(extraction_context, indent=2)}

**Human Question**: {question}

Provide a clear, direct answer. Cite specific evidence. Acknowledge uncertainty."""

        result = self.medgemma.extract(
            prompt=prompt,
            system_prompt="You are answering questions about clinical data extraction.",
            expected_schema={"required": ["answer"]}
        )

        return result.extracted_data['answer']
```

---

### 3. Multi-Source Integration

**Purpose**: Extract from and reconcile multiple document types

**Document Sources**:

| Source | Type | Use For | Priority |
|--------|------|---------|----------|
| Imaging text (DiagnosticReport) | FHIR text | Tumor status, baseline | Medium |
| Imaging PDF (Binary) | PDF | Tumor status, measurements | High |
| Progress notes (DocumentReference) | Text/PDF | Clinical context, validation | Medium |
| Operative reports (DocumentReference) | Text/PDF | Extent of resection (gold standard) | Highest |
| Pathology reports (DiagnosticReport) | Text | Tumor grade, histology | Highest |

```python
class MultiSourceExtractionManager:
    """
    Coordinate extraction across multiple document types
    """

    def extract_with_multi_source_validation(
        self,
        patient_id: str,
        imaging_event: Dict[str, Any],
        variable_name: str  # 'tumor_status' or 'extent_of_resection'
    ) -> Dict[str, Any]:
        """
        Extract variable from primary source, then validate with additional sources
        """

        # Step 1: Extract from primary source (imaging text)
        primary_extraction = self.extract_from_imaging_text(
            imaging_event, variable_name
        )

        # Step 2: Check if additional sources available
        additional_sources = self.find_additional_sources(
            patient_id=patient_id,
            imaging_date=imaging_event['event_date'],
            window_days=30
        )

        if not additional_sources:
            # No additional validation possible
            return {
                **primary_extraction,
                'validation_status': 'single_source',
                'num_sources': 1
            }

        # Step 3: Extract from additional sources
        additional_extractions = []

        for source in additional_sources:
            extraction = self.extract_from_source(source, variable_name)
            if extraction['success']:
                additional_extractions.append({
                    **extraction,
                    'source_type': source['type']
                })

        # Step 4: Reconcile across sources
        reconciled = self.reconcile_extractions(
            primary=primary_extraction,
            additional=additional_extractions
        )

        return reconciled

    def find_additional_sources(
        self,
        patient_id: str,
        imaging_date: datetime,
        window_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Find all relevant documents within temporal window
        """
        sources = []

        # 1. Imaging PDFs from v_binary_files
        imaging_pdfs = self.athena.query(f"""
            SELECT binary_id, content_title, dr_date
            FROM fhir_prd_db.v_binary_files
            WHERE patient_fhir_id = '{patient_id}'
              AND content_type = 'application/pdf'
              AND dr_category_text = 'Imaging Result'
              AND ABS(DATE_DIFF('day', CAST(dr_date AS DATE), DATE '{imaging_date}')) <= {window_days}
        """)

        for pdf in imaging_pdfs:
            sources.append({
                'type': 'imaging_pdf',
                'id': pdf['binary_id'],
                'date': pdf['dr_date'],
                'title': pdf['content_title']
            })

        # 2. Progress notes
        progress_notes = self.athena.query(f"""
            SELECT id, type_text, date, description
            FROM fhir_prd_db.document_reference
            WHERE subject_reference = '{patient_id}'
              AND (type_text LIKE '%Progress%' OR type_text LIKE '%Oncology%')
              AND ABS(DATE_DIFF('day', CAST(date AS DATE), DATE '{imaging_date}')) <= {window_days}
        """)

        for note in progress_notes:
            sources.append({
                'type': 'progress_note',
                'id': note['id'],
                'date': note['date'],
                'title': note['description']
            })

        # 3. Operative reports (for EOR)
        if variable_name == 'extent_of_resection':
            op_reports = self.athena.query(f"""
                SELECT id, type_text, date, description
                FROM fhir_prd_db.document_reference
                WHERE subject_reference = '{patient_id}'
                  AND (type_text LIKE '%Operative%' OR type_text LIKE '%Surgical%')
                  AND ABS(DATE_DIFF('day', CAST(date AS DATE), DATE '{imaging_date}')) <= 14
            """)

            for report in op_reports:
                sources.append({
                    'type': 'operative_report',
                    'id': report['id'],
                    'date': report['date'],
                    'title': report['description']
                })

        return sources

    def reconcile_extractions(
        self,
        primary: Dict[str, Any],
        additional: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reconcile primary extraction with additional sources
        """
        all_values = [primary['value']] + [e['value'] for e in additional]
        unique_values = set(all_values)

        # Perfect agreement
        if len(unique_values) == 1:
            return {
                **primary,
                'validation_status': 'confirmed',
                'num_sources': len(all_values),
                'source_agreement': 'perfect'
            }

        # Conflict - use source priority
        SOURCE_PRIORITY = {
            'operative_report': 1,
            'imaging_pdf': 2,
            'imaging_text': 3,
            'progress_note': 4
        }

        all_extractions = [primary] + additional
        best = min(
            all_extractions,
            key=lambda e: SOURCE_PRIORITY.get(e.get('source_type', 'imaging_text'), 5)
        )

        return {
            **best,
            'validation_status': 'conflicting_sources',
            'num_sources': len(all_values),
            'conflicting_values': list(unique_values),
            'requires_human_review': True
        }
```

---

## Interactive Workflow (Human-in-the-Loop)

### Workflow Design

```
1. Start extraction batch
   ↓
2. For each imaging event:
   ├─ Extract from primary source (imaging text)
   ├─ ExtractionMonitor checks for issues
   │
   ├─ If NO ISSUES:
   │  └─ Auto-approve and store
   │
   └─ If ISSUES DETECTED:
      ├─ PAUSE extraction
      ├─ Present issue to human (you)
      ├─ Human options:
      │  ├─ View source document
      │  ├─ Ask QA Agent: "Why did you choose this?"
      │  ├─ Request multi-source review
      │  ├─ Ask custom question
      │  ├─ Manually override
      │  ├─ Approve as-is
      │  └─ Skip extraction
      │
      ├─ Human makes decision
      └─ Continue to next event

3. End of batch
   ├─ Generate QA summary report
   └─ Export approved extractions
```

### Implementation (Interactive CLI)

```python
class InteractiveExtractionSession:
    """
    Interactive session for human-in-the-loop extraction
    """

    def run(self, patient_id: str):
        """
        Run interactive extraction for one patient
        """
        print(f"\n{'='*80}")
        print(f"INTERACTIVE EXTRACTION SESSION")
        print(f"Patient: {patient_id}")
        print(f"{'='*80}\n")

        # Get imaging events
        events = self.timeline.get_imaging_events(patient_id)
        print(f"Found {len(events)} imaging events\n")

        approved = []
        skipped = []
        reviewed = []

        for i, event in enumerate(events, 1):
            print(f"\n[{i}/{len(events)}] {event['event_date']} - {event.get('description', 'N/A')}")

            # Extract
            extraction = self.master_agent.extract_tumor_status(
                event, patient_id
            )

            print(f"  ✓ Extracted: {extraction['value']} (conf: {extraction['confidence']:.2f})")

            # Monitor for issues
            monitor_result = self.monitor.check_extraction(
                patient_id, extraction, self._get_context(patient_id, event)
            )

            if not monitor_result['requires_review']:
                # Auto-approve
                print(f"  ✓ Auto-approved")
                self.timeline.store_extraction(extraction)
                approved.append(extraction)
                continue

            # PAUSE FOR HUMAN REVIEW
            print(f"\n  ⚠️  REVIEW REQUIRED")
            for issue in monitor_result['issues']:
                print(f"    [{issue['severity'].upper()}] {issue['message']}")

            # Interactive menu
            decision = self.interactive_review(
                extraction=extraction,
                monitor_result=monitor_result,
                event=event,
                patient_id=patient_id
            )

            if decision['action'] == 'approve':
                self.timeline.store_extraction(decision['extraction'])
                approved.append(decision['extraction'])
                reviewed.append(decision)
            elif decision['action'] == 'skip':
                skipped.append(extraction)

        # Summary
        print(f"\n{'='*80}")
        print(f"SESSION SUMMARY")
        print(f"{'='*80}")
        print(f"Total events: {len(events)}")
        print(f"Auto-approved: {len(approved) - len(reviewed)}")
        print(f"Human-reviewed: {len(reviewed)}")
        print(f"Skipped: {len(skipped)}")
        print(f"Success rate: {len(approved)/len(events)*100:.1f}%")

    def interactive_review(
        self,
        extraction: Dict,
        monitor_result: Dict,
        event: Dict,
        patient_id: str
    ) -> Dict:
        """
        Interactive review menu for flagged extraction
        """
        while True:
            print(f"\n  Options:")
            print(f"    1. View source document")
            print(f"    2. Ask agent to explain reasoning")
            print(f"    3. Get multi-source validation")
            print(f"    4. View timeline context")
            print(f"    5. Ask custom question")
            print(f"    6. Manually override value")
            print(f"    7. Approve as-is")
            print(f"    8. Skip this event")

            choice = input(f"\n  Your choice (1-8): ").strip()

            if choice == '1':
                self._show_source_document(event)

            elif choice == '2':
                explanation = self.qa_agent.explain_extraction(
                    extraction=extraction,
                    source_text=event.get('report_text', ''),
                    context=self._get_context(patient_id, event)
                )
                print(f"\n{explanation}")

            elif choice == '3':
                # Multi-source validation
                sources = self.multi_source.find_additional_sources(
                    patient_id=patient_id,
                    imaging_date=event['event_date']
                )

                if not sources:
                    print(f"\n  No additional sources available")
                    continue

                print(f"\n  Found {len(sources)} additional sources:")
                for s in sources:
                    print(f"    - {s['type']}: {s['title']} ({s['date']})")

                print(f"\n  Re-extracting with multi-source validation...")
                updated = self.qa_agent.re_review_with_additional_sources(
                    original_extraction=extraction,
                    additional_sources=self._load_sources(sources)
                )

                print(f"\n  Multi-Source Result:")
                print(f"    Classification: {updated['final_classification']}")
                print(f"    Confidence: {updated['confidence']:.2f}")
                print(f"    Agreement: {updated['source_agreement']}")
                print(f"    Explanation: {updated['explanation']}")

                if not updated['requires_human_review']:
                    extraction = {**extraction, **updated}
                    return {'action': 'approve', 'extraction': extraction}

            elif choice == '4':
                self._show_timeline_context(patient_id, event['event_date'])

            elif choice == '5':
                question = input(f"\n  Your question: ")
                answer = self.qa_agent.answer_custom_question(
                    question=question,
                    extraction_context={
                        'extraction': extraction,
                        'event': event,
                        'monitor_result': monitor_result
                    }
                )
                print(f"\n  {answer}")

            elif choice == '6':
                new_value = input(f"\n  Enter correct value (NED/Stable/Increased/Decreased): ")
                extraction['value'] = new_value
                extraction['human_override'] = True
                return {'action': 'approve', 'extraction': extraction}

            elif choice == '7':
                return {'action': 'approve', 'extraction': extraction}

            elif choice == '8':
                return {'action': 'skip', 'extraction': extraction}
```

---

## Pilot Implementation Plan

### Phase 1: Core Components (Week 1)

**Goal**: Implement monitoring and QA agents

**Tasks**:
1. ✅ Review existing extraction results (done - found 4 issues)
2. ⏳ Implement ExtractionMonitor
3. ⏳ Implement QAAgent
4. ⏳ Test on 10 flagged extractions from patient e4BwD8ZYDBccepXcJ.Ilo3w3

**Success Criteria**:
- Monitor correctly identifies all 4 known issues
- QA Agent provides clinically accurate explanations

### Phase 2: Multi-Source Integration (Week 2)

**Goal**: Add PDF and progress note extraction

**Tasks**:
1. ⏳ Extend BinaryFileAgent to extract from 77 imaging PDFs
2. ⏳ Query and extract from progress notes (DocumentReference)
3. ⏳ Implement MultiSourceExtractionManager
4. ⏳ Test reconciliation on 5 cases with multi-source conflicts

**Data Sources for Pilot**:
```sql
-- Imaging PDFs for patient
SELECT binary_id, content_title, dr_date
FROM fhir_prd_db.v_binary_files
WHERE patient_fhir_id = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND content_type = 'application/pdf'
  AND dr_category_text = 'Imaging Result';
-- Expected: 77 PDFs

-- Progress notes
SELECT id, type_text, date
FROM fhir_prd_db.document_reference
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND (type_text LIKE '%Progress%' OR type_text LIKE '%Oncology%');
-- Expected: 50-100 notes

-- Operative reports
SELECT id, type_text, date
FROM fhir_prd_db.document_reference
WHERE subject_reference = 'e4BwD8ZYDBccepXcJ.Ilo3w3'
  AND type_text LIKE '%Operative%';
-- Expected: 5-10 reports
```

### Phase 3: Interactive Workflow (Week 3)

**Goal**: Enable human-in-the-loop review

**Tasks**:
1. ⏳ Implement InteractiveExtractionSession
2. ⏳ Run full extraction on patient e4BwD8ZYDBccepXcJ.Ilo3w3 with human review
3. ⏳ Track metrics:
   - % requiring human review
   - Time per review
   - Override rate
   - Multi-source agreement rate

**Expected Metrics** (targets):
- < 20% of extractions require human review
- < 2 minutes average review time
- < 10% human override rate
- > 80% multi-source agreement

### Phase 4: Optimization (Week 4)

**Goal**: Refine prompts and rules based on pilot data

**Optimizations**:
1. Improve duplicate detection (same-date imaging)
2. Add treatment-context rules (check for surgery, chemo between scans)
3. Refine confidence thresholds
4. Update extraction prompts based on common errors

---

## Addressing Specific Issues from Current Data

### Issue 1: Duplicates (Same Date)

**Example**: Events #3-4 both on 2018-08-03

**Solution**:
```python
def check_for_duplicate(self, patient_id, new_event):
    """
    Check if event date already exists for this patient
    """
    existing = self.timeline.query_events(
        patient_id=patient_id,
        event_type='Imaging',
        event_date=new_event['event_date']
    )

    if len(existing) > 0:
        return {
            'is_duplicate': True,
            'action': 'skip',
            'message': f"Duplicate: Already have imaging on {new_event['event_date']}"
        }

    return {'is_duplicate': False}
```

### Issue 2: "Gross Total Resection" as tumor_status

**Example**: Event #46 (2024-09-27)

**Solution**: Add value validation
```python
VALID_TUMOR_STATUS = ['NED', 'Stable', 'Increased', 'Decreased', 'New_Malignancy']
EOR_VALUES = ['Gross Total Resection', 'Near Total Resection', 'Subtotal Resection']

if extraction['variable_name'] == 'tumor_status':
    if extraction['value'] not in VALID_TUMOR_STATUS:
        if extraction['value'] in EOR_VALUES:
            # Wrong extraction type - should be EOR
            return {
                'requires_review': True,
                'issue': 'Value belongs to extent_of_resection, not tumor_status',
                'action': 'Re-extract with correct variable type'
            }
```

### Issue 3: Rapid status changes

**Example**: Increased (2018-05-27) → Decreased (2018-05-29) in 2 days

**Solution**: Check for treatment intervention
```python
def validate_rapid_status_change(
    self,
    patient_id: str,
    prior_status: str,
    new_status: str,
    days_diff: int
):
    """
    Validate rapid status change by checking for treatment
    """
    if prior_status == 'Increased' and new_status == 'Decreased':
        if days_diff < 7:
            # Look for treatment between scans
            treatments = self.timeline.query_events(
                patient_id=patient_id,
                event_type=['Procedure', 'Medication'],
                start_date=prior_date,
                end_date=new_date
            )

            if not treatments:
                return {
                    'plausible': False,
                    'reason': f'Status improved in {days_diff} days without treatment',
                    'action': 'Verify with progress notes or check for duplicate'
                }

    return {'plausible': True}
```

---

## Expected Output: Interactive Session Example

```
================================================================================
INTERACTIVE EXTRACTION SESSION
Patient: e4BwD8ZYDBccepXcJ.Ilo3w3
================================================================================

Found 51 imaging events

[1/51] 2018-05-27 - MR Brain W & W/O IV Contrast
  ✓ Extracted: Increased (conf: 0.80)
  ✓ Auto-approved

[2/51] 2018-05-29 - MR Brain W & W/O IV Contrast
  ✓ Extracted: Decreased (conf: 0.85)

  ⚠️  REVIEW REQUIRED
    [HIGH] Status changed Increased→Decreased in 2 days
    [MEDIUM] No treatment intervention found

  Options:
    1. View source document
    2. Ask agent to explain reasoning
    3. Get multi-source validation
    4. View timeline context
    5. Ask custom question
    6. Manually override value
    7. Approve as-is
    8. Skip this event

  Your choice (1-8): 2

  Agent Explanation:
  ────────────────────────────────────────────────────
  I classified this as "Decreased" based on:

  Key phrases:
  - "Decreased size of cystic component" (line 18)
  - "Reduction in T2 signal abnormality" (line 22)

  However, I acknowledge this is only 2 days after a scan showing
  "Increased". This rapid change is clinically unusual.

  Alternative interpretation: These may be the same imaging study
  viewed at different times, or there is a data entry error creating
  duplicate events.

  Recommendation: Verify these are truly separate scans or merge as duplicate.
  ────────────────────────────────────────────────────

  Your choice (1-8): 3

  Found 2 additional sources:
    - imaging_pdf: Full MRI Report (2018-05-27)
    - progress_note: Oncology Visit (2018-06-01)

  Re-extracting with multi-source validation...

  Multi-Source Result:
    Classification: Increased
    Confidence: 0.90
    Agreement: 2/3 sources agree (imaging PDF + progress note say "Increased")
    Explanation: Original "Decreased" finding from 2018-05-29 report appears
    to be misclassification. Both PDF report and oncology note document tumor
    progression. The 2018-05-29 report likely refers to decreased edema after
    steroids, not tumor size.

  Your choice (1-8): 7
  ✓ Approved with multi-source validation

[3/51] 2018-08-03 - MR Brain W & W/O IV Contrast
  ✓ Extracted: Increased (conf: 0.80)

  ⚠️  REVIEW REQUIRED
    [HIGH] Duplicate event - already have imaging on 2018-08-03

  Your choice (1-8): 8
  ✓ Skipped (duplicate)

[Continues through all 51 events...]

================================================================================
SESSION SUMMARY
================================================================================
Total events: 51
Auto-approved: 38 (74.5%)
Human-reviewed: 10 (19.6%)
Skipped (duplicates): 3 (5.9%)
Success rate: 94.1%

Issues resolved:
  - 3 duplicates identified and skipped
  - 1 wrong extraction type corrected (EOR → tumor_status)
  - 4 temporal inconsistencies validated with multi-source data
  - 2 low-confidence extractions approved after QA review
```

---

## Next Steps

1. **Implement Phase 1**: Build ExtractionMonitor and QAAgent
2. **Test on known issues**: Run on 51 existing extractions to validate detection
3. **Gather additional data**: Query for PDFs, progress notes, op reports
4. **Build interactive CLI**: Enable human review workflow
5. **Run pilot**: Extract full timeline for patient e4BwD8ZYDBccepXcJ.Ilo3w3 with human-in-the-loop

**Ready to proceed with Phase 1 implementation?**
