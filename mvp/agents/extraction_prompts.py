"""
Extraction Prompt Templates for Medical Agent

Contains structured prompts for:
1. Imaging Classification (pre-op / post-op / surveillance)
2. Extent of Resection (GTR / STR / Partial / Biopsy)
3. Tumor Status (NED / Stable / Increased / Decreased / New_Malignancy)

Based on MULTI_AGENT_TUMOR_STATUS_WORKFLOW.md specifications.
"""

from typing import Dict, Any, List
import json


def build_imaging_classification_prompt(
    report: Dict[str, Any],
    context: Dict[str, Any]
) -> str:
    """
    Build prompt for imaging classification extraction.

    Classifies imaging as:
    - pre_operative: Imaging before first tumor surgery
    - post_operative: Imaging within 72 hours after surgery (assesses extent of resection)
    - surveillance: Follow-up imaging for monitoring (3-6 months intervals)
    """
    import json

    # Extract key fields with fallbacks for different field names
    report_text = report.get('document_text', report.get('radiology_report_text', ''))
    imaging_date = report.get('document_date', report.get('imaging_date', 'Unknown'))
    modality = report.get('metadata', {}).get('imaging_modality', report.get('imaging_modality', 'Unknown'))

    # Extract temporal context
    procedures_before = context.get('events_before', [])
    procedures_after = context.get('events_after', [])

    # Build context summary
    context_summary = []

    # Surgeries before this imaging
    tumor_surgeries_before = [
        p for p in procedures_before
        if p.get('event_type') == 'Procedure' and
        'tumor' in (p.get('event_category', '') + p.get('description', '')).lower()
    ]

    if tumor_surgeries_before:
        for surg in tumor_surgeries_before[:2]:  # Show up to 2 most recent
            days_diff = abs(surg.get('days_diff', 999))
            context_summary.append(
                f"- Tumor surgery {days_diff} days BEFORE this imaging: {surg.get('description', 'Unknown procedure')}"
            )

    # Surgeries after this imaging
    tumor_surgeries_after = [
        p for p in procedures_after
        if p.get('event_type') == 'Procedure' and
        'tumor' in (p.get('event_category', '') + p.get('description', '')).lower()
    ]

    if tumor_surgeries_after:
        for surg in tumor_surgeries_after[:1]:  # Show next surgery
            days_diff = abs(surg.get('days_diff', 999))
            context_summary.append(
                f"- Tumor surgery {days_diff} days AFTER this imaging: {surg.get('description', 'Unknown procedure')}"
            )

    if not context_summary:
        context_summary.append("- No tumor surgeries found in surrounding timeline (±30 days)")

    context_text = "\n".join(context_summary)

    # Format entire report as JSON for MedGemma to see all available fields
    report_json = json.dumps(report, indent=2, default=str)

    prompt = f"""You are a medical AI analyzing a radiology report to classify the imaging study.

**TASK:** Classify this imaging study as one of:
- "pre_operative": Imaging before first tumor surgery (baseline/diagnostic imaging)
- "post_operative": Imaging within 72 hours after surgery to assess extent of resection
- "surveillance": Follow-up monitoring imaging (typically 3-6 months after treatment)

**IMAGING INFORMATION:**
Date: {imaging_date}
Modality: {modality}

**TEMPORAL CONTEXT (procedures near this imaging):**
{context_text}

**COMPLETE REPORT DATA (JSON):**
```json
{report_json}
```

**RADIOLOGY REPORT TEXT:**
{report_text}

**CLASSIFICATION CRITERIA:**
1. **Post-operative** if:
   - Report mentions "post-operative" or "status post resection"
   - Imaging is 0-3 days after a tumor surgery
   - Report assesses surgical changes or residual tumor

2. **Pre-operative** if:
   - This is the earliest imaging in timeline
   - Report describes initial tumor without prior surgery mentioned
   - Imaging occurs before any tumor surgery

3. **Surveillance** if:
   - Report compares to prior imaging ("compared to [date]")
   - Imaging is >14 days after surgery
   - Report monitors for recurrence/progression/stability

**OUTPUT FORMAT (JSON):**
{{
  "imaging_classification": "post_operative" | "pre_operative" | "surveillance",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of classification based on temporal context and report text",
  "keywords_found": ["list", "of", "relevant", "keywords", "from", "report"]
}}

**IMPORTANT:**
- Base classification primarily on temporal proximity to surgeries
- Use report keywords as supporting evidence
- If uncertain, choose most likely classification and set confidence < 0.8
- Return ONLY valid JSON, no additional text
"""

    return prompt


def build_eor_extraction_prompt(
    report: Dict[str, Any],
    context: Dict[str, Any]
) -> str:
    """
    Build prompt for extent of resection extraction from post-op imaging.

    Extracts:
    - GTR (Gross Total Resection)
    - STR (Subtotal Resection)
    - Partial (Partial Resection)
    - Biopsy (Biopsy only, no resection)
    - Unknown (Insufficient information)
    """
    report_text = report.get('document_text', '')
    imaging_date = report.get('document_date', 'Unknown')

    # Find most recent surgery
    procedures_before = context.get('events_before', [])
    tumor_surgeries = [
        p for p in procedures_before
        if p.get('event_type') == 'Procedure' and
        'tumor' in (p.get('event_category', '') + p.get('description', '')).lower()
    ]

    surgery_context = "No recent tumor surgery found"
    if tumor_surgeries:
        most_recent = tumor_surgeries[0]
        days_diff = abs(most_recent.get('days_diff', 999))
        surgery_context = f"Surgery {days_diff} days before imaging: {most_recent.get('description', 'Unknown')}"

    prompt = f"""You are a neurosurgical AI assistant analyzing a post-operative MRI report to determine the extent of tumor resection.

**TASK:** Determine the extent of resection (EOR) from this post-operative imaging report.

**IMAGING INFORMATION:**
Date: {imaging_date}
Context: {surgery_context}

**RADIOLOGY REPORT TEXT:**
{report_text}

**CLASSIFICATION CATEGORIES:**

1. **GTR (Gross Total Resection)** - Keywords:
   - "gross total resection"
   - "complete resection"
   - "no residual enhancing tumor"
   - "no residual enhancement"
   - "complete removal"
   - "100% resection"

2. **STR (Subtotal Resection)** - Keywords:
   - "subtotal resection"
   - "near-total resection"
   - "90-99% resection"
   - "small amount of residual tumor"
   - "minimal residual enhancement"

3. **Partial (Partial Resection)** - Keywords:
   - "partial resection"
   - "debulking"
   - "significant residual tumor"
   - "extensive residual enhancement"
   - "<90% resection"

4. **Biopsy (Biopsy only)** - Keywords:
   - "biopsy only"
   - "stereotactic biopsy"
   - "no resection performed"
   - "diagnostic biopsy"

5. **Unknown** - If report:
   - Doesn't clearly describe resection status
   - Is not a post-operative study
   - Has insufficient information

**OUTPUT FORMAT (JSON):**
{{
  "extent_of_resection": "GTR" | "STR" | "Partial" | "Biopsy" | "Unknown",
  "confidence": 0.0-1.0,
  "evidence": "Direct quote(s) from report supporting this classification",
  "residual_tumor_description": "Description of any residual tumor mentioned, or 'None' if GTR",
  "measurement_if_available": "Size of residual tumor if measured (e.g., '1.2 cm'), or null"
}}

**IMPORTANT:**
- Quote exact phrases from the report as evidence
- If report doesn't explicitly state resection completeness, use descriptions of residual tumor
- Higher confidence (>0.9) only if explicit EOR statement in report
- Return ONLY valid JSON, no additional text
"""

    return prompt


def build_operative_report_eor_extraction_prompt(
    operative_report: Dict[str, Any],
    context: Dict[str, Any]
) -> str:
    """
    Build prompt for extent of resection extraction from operative report (GOLD STANDARD).

    Agent 1 uses this to get EOR from operative notes, which takes precedence over imaging assessment.

    Extracts:
    - Gross Total Resection (GTR) / Near Total Resection
    - Partial Resection
    - Biopsy Only
    """
    import json

    # Extract key fields with fallbacks
    report_text = operative_report.get('note_text', operative_report.get('document_text', ''))
    procedure_date = operative_report.get('procedure_date', operative_report.get('surgery_date', 'Unknown'))
    procedure_code = operative_report.get('proc_code_text', operative_report.get('surgery_type', 'Unknown'))

    # Build timeline context
    prior_surgeries = []
    events_before = context.get('events_before', [])
    for event in events_before:
        if event.get('event_type') == 'Procedure':
            days_ago = abs(event.get('days_diff', 0))
            prior_surgeries.append(f"- {event.get('description', 'Surgery')}: {days_ago} days before (date: {event.get('event_date', 'Unknown')})")

    timeline_context = "\n".join(prior_surgeries) if prior_surgeries else "- No prior tumor surgeries found"

    # Format complete report as JSON
    report_json = json.dumps(operative_report, indent=2, default=str)

    prompt = f"""You are a neurosurgical AI assistant analyzing an operative report to determine the extent of tumor resection.

**TASK:** Extract the extent of resection (EOR) from this operative note. This is the GOLD STANDARD for EOR determination.

**OPERATIVE REPORT INFORMATION:**
Date: {procedure_date}
Procedure: {procedure_code}

**SURGICAL TIMELINE (prior surgeries):**
{timeline_context}

**COMPLETE OPERATIVE REPORT DATA (JSON):**
```json
{report_json}
```

**OPERATIVE NOTE TEXT:**
{report_text}

**CLASSIFICATION CATEGORIES:**

1. **Gross Total Resection / Near Total Resection** - Surgeon's assessment:
   - "gross total resection"
   - "complete resection"
   - "all visible tumor removed"
   - "no residual tumor identified"
   - "95-100% resection"
   - "near total resection"

2. **Partial Resection** - Surgeon's assessment:
   - "partial resection"
   - "subtotal resection"
   - "debulking"
   - "residual tumor left" (with reason: eloquent cortex, vascular involvement)
   - "<95% resection"

3. **Biopsy Only** - Surgeon's assessment:
   - "biopsy only"
   - "stereotactic biopsy"
   - "no resection performed"
   - "tissue sampling only"

**OUTPUT FORMAT (JSON):**
{{
  "extent_of_resection": "Gross Total Resection" | "Near Total Resection" | "Partial Resection" | "Biopsy Only",
  "confidence": 0.0-1.0,
  "surgeon_statement": "Direct quote from operative note describing resection extent",
  "residual_tumor_reason": "If residual tumor left, reason stated by surgeon (e.g., 'proximity to motor cortex') or null",
  "estimated_percent_resection": "If surgeon provides % estimate (e.g., '95%') or null",
  "complications": "Any intraoperative complications mentioned or 'None'"
}}

**IMPORTANT:**
- Quote surgeon's exact assessment of resection completeness
- Operative report EOR is more reliable than imaging assessment
- Higher confidence (>0.9) if surgeon explicitly states resection extent
- Return ONLY valid JSON, no additional text
"""

    return prompt


def build_tumor_status_extraction_prompt(
    report: Dict[str, Any],
    context: Dict[str, Any],
    prior_imaging: List[Dict[str, Any]] = None
) -> str:
    """
    Build prompt for tumor status extraction from surveillance imaging.

    Extracts:
    - NED (No Evidence of Disease)
    - Stable (No change)
    - Increased (Progression - size increase, new enhancement)
    - Decreased (Partial response - size reduction)
    - New_Malignancy (Second primary or new lesion)
    """
    import json

    # Extract key fields
    report_text = report.get('document_text', report.get('radiology_report_text', ''))
    imaging_date = report.get('document_date', report.get('imaging_date', 'Unknown'))

    # Find prior imaging for comparison context
    prior_context = "No prior imaging available for comparison"

    events_before = context.get('events_before', [])
    prior_imaging_events = [
        e for e in events_before
        if e.get('event_type') == 'Imaging' and e.get('event_category') == 'MRI Brain'
    ]

    if prior_imaging_events:
        most_recent_prior = prior_imaging_events[0]
        days_diff = abs(most_recent_prior.get('days_diff', 999))
        prior_date = most_recent_prior.get('event_date', 'Unknown')
        prior_context = f"Prior imaging: {days_diff} days before (date: {prior_date})"

    # Format entire report as JSON for MedGemma to see all available fields
    report_json = json.dumps(report, indent=2, default=str)

    prompt = f"""You are a neuro-oncology AI assistant analyzing a surveillance MRI report to determine tumor status.

**TASK:** Determine the tumor status by comparing this imaging to prior studies.

**IMAGING INFORMATION:**
Current imaging date: {imaging_date}
Comparison: {prior_context}

**COMPLETE REPORT DATA (JSON):**
```json
{report_json}
```

**RADIOLOGY REPORT TEXT:**
{report_text}

**CLASSIFICATION CATEGORIES:**

1. **NED (No Evidence of Disease)** - Indicators:
   - "no evidence of tumor"
   - "no residual or recurrent disease"
   - "complete response"
   - "no abnormal enhancement"

2. **Stable** - Indicators:
   - "stable"
   - "unchanged"
   - "no significant change"
   - "similar to prior"
   - Measurements within 20% of prior

3. **Increased (Progression)** - Indicators:
   - "increased size"
   - "progression"
   - "new enhancement"
   - "enlarging"
   - Size increase >20%
   - New areas of enhancement

4. **Decreased (Partial Response)** - Indicators:
   - "decreased size"
   - "reduction in tumor burden"
   - "improved"
   - "smaller"
   - Size decrease >20%

5. **New_Malignancy** - Indicators:
   - "new lesion" distinct from primary site
   - "second primary"
   - "new tumor" in different location
   - "metastasis" (rare in primary brain tumors)

**OUTPUT FORMAT (JSON):**
{{
  "tumor_status": "NED" | "Stable" | "Increased" | "Decreased" | "New_Malignancy",
  "confidence": 0.0-1.0,
  "comparison_findings": "Description of how current imaging compares to prior",
  "measurements": {{
    "current_size": "e.g., '2.1 x 1.8 cm' or null",
    "prior_size": "e.g., '2.0 x 1.7 cm' or null",
    "change_description": "e.g., 'slight increase' or null"
  }},
  "enhancement_pattern": "Description of enhancement if mentioned",
  "evidence": "Direct quote(s) from report supporting classification"
}}

**IMPORTANT:**
- Rely heavily on radiologist's comparison statements
- Extract measurements if provided
- If report says "stable" explicitly, classify as Stable even without measurements
- Higher confidence (>0.9) if explicit comparison statement present
- Return ONLY valid JSON, no additional text
"""

    return prompt


def build_progress_note_disease_state_prompt(
    progress_note: Dict[str, Any],
    context: Dict[str, Any]
) -> str:
    """
    Build prompt for disease state validation from oncology progress notes.

    Agent 1 uses this to validate imaging-based tumor status against clinical assessment.
    Oncologist's clinical exam + assessment takes precedence over imaging alone.

    Extracts:
    - Clinical tumor status assessment
    - Physical exam findings
    - Treatment response assessment
    """
    import json

    # Extract key fields with fallbacks
    note_text = progress_note.get('note_text', progress_note.get('document_text', ''))
    note_date = progress_note.get('dr_date', progress_note.get('document_date', 'Unknown'))
    note_type = progress_note.get('dr_type_text', 'Progress Note')

    # Build timeline context - show recent imaging and surgeries
    timeline_summary = []

    events_before = context.get('events_before', [])

    # Recent imaging (last 3 months)
    recent_imaging = [e for e in events_before if e.get('event_type') == 'Imaging' and abs(e.get('days_diff', 999)) <= 90]
    if recent_imaging:
        timeline_summary.append("Recent Imaging:")
        for img in recent_imaging[:3]:  # Last 3 imaging studies
            days_ago = abs(img.get('days_diff', 0))
            timeline_summary.append(f"  - {img.get('event_category', 'MRI')}: {days_ago} days before (date: {img.get('event_date', 'Unknown')})")

    # Recent surgeries
    recent_surgeries = [e for e in events_before if e.get('event_type') == 'Procedure']
    if recent_surgeries:
        timeline_summary.append("Surgical History:")
        for surg in recent_surgeries[:2]:  # Last 2 surgeries
            days_ago = abs(surg.get('days_diff', 0))
            timeline_summary.append(f"  - {surg.get('description', 'Surgery')}: {days_ago} days before (date: {surg.get('event_date', 'Unknown')})")

    if not timeline_summary:
        timeline_summary.append("No recent imaging or surgeries found in timeline")

    timeline_context = "\n".join(timeline_summary)

    # Format complete progress note as JSON
    note_json = json.dumps(progress_note, indent=2, default=str)

    prompt = f"""You are a neuro-oncology AI assistant analyzing a progress note to extract the oncologist's disease state assessment.

**TASK:** Extract the oncologist's clinical assessment of tumor status. This validates and may override imaging-only assessments.

**PROGRESS NOTE INFORMATION:**
Date: {note_date}
Type: {note_type}

**CLINICAL TIMELINE (context for this assessment):**
{timeline_context}

**COMPLETE PROGRESS NOTE DATA (JSON):**
```json
{note_json}
```

**PROGRESS NOTE TEXT:**
{note_text}

**EXTRACTION TARGETS:**

1. **Disease Status Assessment** - Look for:
   - "no evidence of disease" (NED)
   - "stable disease"
   - "disease progression"
   - "partial response"
   - "complete response"
   - "recurrence"
   - "new lesion"

2. **Physical Exam Findings** - Neurological status:
   - Neurological exam changes
   - New or worsening symptoms
   - Improvement in deficits
   - Performance status (KPS, ECOG)

3. **Treatment Response** - Oncologist's interpretation:
   - Response to chemotherapy
   - Response to radiation
   - Post-surgical status
   - Steroid requirements

4. **Plan/Assessment** - Management decisions:
   - Continue current therapy (suggests stability)
   - Change therapy (suggests progression)
   - Surveillance only (suggests NED/stable)
   - Re-resection planned (suggests progression)

**OUTPUT FORMAT (JSON):**
{{
  "clinical_disease_status": "NED" | "Stable" | "Progressive" | "Responding" | "Recurrence" | "Uncertain",
  "confidence": 0.0-1.0,
  "oncologist_assessment": "Direct quote from Assessment/Plan section",
  "neurological_exam": {{
    "status": "improved" | "stable" | "worsened" | "not_documented",
    "findings": "Description of neuro exam or 'Not documented'"
  }},
  "treatment_response_statement": "Quote about response to treatment if mentioned, or null",
  "performance_status": {{
    "kps": "Karnofsky score if mentioned (e.g., '90') or null",
    "ecog": "ECOG score if mentioned (e.g., '1') or null",
    "description": "Functional status description or null"
  }},
  "imaging_correlation": {{
    "imaging_mentioned": "yes" | "no",
    "imaging_interpretation": "Oncologist's interpretation of recent imaging or null",
    "agrees_with_imaging": "yes" | "no" | "uncertain"
  }},
  "management_plan": "Treatment plan indicating disease trajectory (e.g., 'continue TMZ, repeat MRI 3 months')"
}}

**IMPORTANT:**
- Focus on oncologist's clinical assessment, not just imaging results
- Clinical exam + assessment may reveal progression before imaging changes
- Quote exact statements from Assessment & Plan sections
- Higher confidence (>0.9) if explicit disease status statement present
- Return ONLY valid JSON, no additional text
"""

    return prompt


def build_tumor_location_extraction_prompt(
    report: Dict[str, Any],
    context: Dict[str, Any]
) -> str:
    """
    Build prompt for tumor location extraction from clinical reports.

    Extracts anatomical location(s) from imaging, operative, or progress note text.
    MedGemma returns free-text location mentions which are then normalized to CBTN codes.

    Args:
        report: Report dict with document_text, report_text, or note_text
        context: Context dict with patient_id, report_date, events_before/after

    Returns:
        Formatted prompt string for MedGemma
    """
    import json

    # Extract report text with multiple fallbacks
    report_text = report.get('document_text',
                             report.get('radiology_report_text',
                             report.get('note_text', '')))

    report_date = report.get('document_date',
                            report.get('imaging_date',
                            report.get('dr_date',
                            report.get('procedure_date', 'Unknown'))))

    report_type = report.get('report_type', 'clinical report')

    # Format complete report as JSON
    report_json = json.dumps(report, indent=2, default=str)

    prompt = f"""You are a neuro-oncology AI assistant analyzing a {report_type} to extract brain tumor location information.

**TASK:** Extract ALL anatomical locations where tumor is mentioned in this report. Be comprehensive - include primary location, areas of extension, and any metastatic sites.

**REPORT INFORMATION:**
Date: {report_date}
Type: {report_type}

**COMPLETE REPORT DATA (JSON):**
```json
{report_json}
```

**REPORT TEXT:**
{report_text}

**EXTRACTION TARGETS:**

Extract ALL locations mentioned using anatomically precise terminology:

**Supratentorial Locations:**
- Frontal lobe (specify: superior, middle, inferior, precentral, orbitofrontal, etc.)
- Temporal lobe (specify: superior, middle, inferior, mesial, temporal pole, etc.)
- Parietal lobe (specify: superior, inferior, postcentral, etc.)
- Occipital lobe (specify: calcarine, occipital pole, cuneus, etc.)
- Thalamus (specify: anterior, medial, lateral, pulvinar, etc.)
- Basal ganglia (specify: caudate, putamen, globus pallidus, etc.)
- Corpus callosum (specify: genu, body, splenium)
- Insula
- Internal capsule
- Lateral ventricles, third ventricle, fourth ventricle
- Suprasellar region, hypothalamus, pituitary region
- Pineal gland

**Infratentorial/Posterior Fossa:**
- Cerebellum (specify: vermis, hemisphere, peduncle)
- Brain stem - Midbrain/tectum (specify: tectum, tegmentum, cerebral peduncle)
- Brain stem - Pons
- Brain stem - Medulla
- Fourth ventricle
- Cerebellopontine angle

**Spinal Locations:**
- Cervical spine (specify level if mentioned: C1-C7)
- Thoracic spine (specify level if mentioned: T1-T12)
- Lumbar spine (specify level if mentioned: L1-L5)
- Sacral spine
- Thecal sac
- Conus medullaris
- Cauda equina

**Special Regions:**
- Optic pathway (optic nerve, chiasm, tract)
- Cranial nerves (specify: CN II, CN III, etc.)
- Meninges/dura
- Leptomeninges
- Skull base

**LATERALITY:**
Always specify if mentioned:
- Left, Right, Bilateral
- Midline
- Crossing midline

**EXTRACTION RULES:**

1. **Primary Location**: The main anatomical site of the tumor
2. **Areas of Extension**: Any regions tumor extends into
3. **Multifocal Sites**: If multiple separate lesions, list each location
4. **Precise Terminology**: Use the exact anatomical terms from the report
5. **Include Descriptors**: "left frontal lobe", "right cerebellar hemisphere", "bilateral thalami"
6. **Quote Evidence**: Provide exact phrases supporting each location

**OUTPUT FORMAT (JSON):**
{{
  "primary_location": "Main anatomical site (e.g., 'left frontal lobe', 'fourth ventricle')",
  "laterality": "left" | "right" | "bilateral" | "midline" | "not specified",
  "additional_locations": [
    {{
      "location": "Anatomical site (e.g., 'corpus callosum', 'thalamus')",
      "relationship": "extension" | "separate lesion" | "leptomeningeal spread",
      "evidence": "Quote from report mentioning this location"
    }}
  ],
  "all_locations_mentioned": [
    "List of all distinct anatomical locations mentioned (free text)"
  ],
  "confidence": 0.0-1.0,
  "extraction_notes": "Any ambiguities or clarifications about location determination"
}}

**IMPORTANT:**
- Extract locations EXACTLY as described in the report (preserve clinical terminology)
- If multiple areas involved, list ALL locations
- Higher confidence (>0.9) if explicit anatomical location statements present
- Lower confidence (<0.7) if location is inferred or vague
- If no location mentioned, return primary_location: "Not specified"
- Return ONLY valid JSON, no additional text

**EXAMPLES:**

Example 1: "Large heterogeneous mass in the left frontal lobe extending into the corpus callosum and crossing midline"
→ primary_location: "left frontal lobe"
→ laterality: "left"
→ additional_locations: [{{"location": "corpus callosum", "relationship": "extension"}}, {{"location": "right frontal lobe", "relationship": "extension"}}]

Example 2: "Fourth ventricular mass with extension into the cerebellar vermis"
→ primary_location: "fourth ventricle"
→ laterality: "midline"
→ additional_locations: [{{"location": "cerebellar vermis", "relationship": "extension"}}]

Example 3: "Enhancing lesion in the left midbrain and left thalamus"
→ primary_location: "left midbrain"
→ laterality: "left"
→ additional_locations: [{{"location": "left thalamus", "relationship": "extension or separate lesion"}}]
"""

    return prompt


# Export functions for MasterAgent to use
__all__ = [
    'build_imaging_classification_prompt',
    'build_eor_extraction_prompt',
    'build_tumor_status_extraction_prompt',
    'build_operative_report_eor_extraction_prompt',
    'build_progress_note_disease_state_prompt',
    'build_tumor_location_extraction_prompt'
]
