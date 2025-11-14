#!/usr/bin/env python3
"""
Phase 0.3: WHO 2021 Nomenclature Translator

Assesses whether a diagnosis uses WHO 2021 terminology and translates if needed.
This uses REASONING, not pattern matching, to handle 100+ molecular subtypes.

Part of Phase 0 WHO 2021 Nomenclature Standardization redesign.

Usage:
    from lib.phase0_who_translator import WHO2021Translator

    translator = WHO2021Translator(medgemma_agent, who_reference_path)
    result = translator.assess_and_translate(primary_diagnosis_extraction)
"""

import logging
import json
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class WHO2021Translator:
    """
    Phase 0.3: Assess WHO 2021 alignment and translate diagnosis if needed.

    Uses LLM reasoning to determine:
    1. Does this diagnosis use WHO 2021 terminology?
    2. Is molecular evidence sufficient for modern classification?
    3. What's the appropriate WHO 2021 equivalent?
    4. When should NOS/NEC be appended?
    """

    def __init__(self, medgemma_agent, who_reference_path: Path):
        """
        Initialize WHO 2021 translator.

        Args:
            medgemma_agent: MedGemma agent for reasoning tasks
            who_reference_path: Path to WHO 2021 CNS Tumor Classification reference
        """
        self.medgemma_agent = medgemma_agent
        self.who_reference_path = Path(who_reference_path)

        if not self.who_reference_path.exists():
            logger.warning(f"WHO reference not found at {who_reference_path}")
            self.who_reference = None
        else:
            with open(self.who_reference_path, 'r') as f:
                self.who_reference = f.read()
            logger.info(f"✅ V5.6: WHO 2021 reference loaded ({len(self.who_reference)} chars)")

        logger.info("✅ V5.6: Phase 0.3 WHO Translator initialized")

    def assess_and_translate(self, primary_diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess if diagnosis aligns with WHO 2021 and translate if needed.

        Args:
            primary_diagnosis: Output from Phase 0.2 with:
                - primary_diagnosis: The diagnosis string
                - supporting_evidence: Molecular/histologic details
                - evidence_quality: complete / partial / minimal

        Returns:
            Dict with:
                - alignment_status: who_2021_compliant / needs_translation / insufficient_evidence
                - reasoning: Step-by-step analysis
                - who_2021_diagnosis: Final diagnosis using WHO 2021 terminology
                - molecular_subtype: Molecular classification if applicable
                - grade: 1-4 or null
                - key_markers: Markers supporting classification
                - evidence_level: complete / partial / minimal
                - translation_notes: What changed and why
                - nos_nec_rationale: If NOS/NEC appended, why
                - confidence: high / moderate / low
        """
        logger.info("   [Phase 0.3] Assessing WHO 2021 alignment and translating if needed...")

        # Extract diagnosis and evidence from Phase 0.2
        diagnosis_text = primary_diagnosis.get('primary_diagnosis', '')
        evidence = primary_diagnosis.get('supporting_evidence', [])
        evidence_quality = primary_diagnosis.get('evidence_quality', 'unknown')
        source_quote = primary_diagnosis.get('source_text_quote', '')

        logger.info(f"      Diagnosis to assess: {diagnosis_text}")
        logger.info(f"      Evidence quality: {evidence_quality}")

        if not self.who_reference:
            logger.error("   ❌ WHO reference not available, cannot translate")
            return {
                "alignment_status": "error",
                "who_2021_diagnosis": diagnosis_text,
                "error": "WHO reference not loaded"
            }

        # Build reasoning prompt
        translation_prompt = f"""You are a neuropathology expert assessing whether a diagnosis aligns with WHO 2021 CNS tumor classification standards.

**YOUR ROLE:**
You are NOT re-diagnosing the tumor. The pathologist/clinician already made the diagnosis.
Your job is to assess if their terminology matches WHO 2021 standards, and if not, translate it using available evidence.

**PATHOLOGIST'S/CLINICIAN'S DIAGNOSIS:**
{diagnosis_text}

**SOURCE QUOTE:**
{source_quote}

**MOLECULAR/HISTOLOGIC EVIDENCE AVAILABLE:**
{json.dumps(evidence, indent=2) if evidence else 'No specific molecular markers documented'}

**EVIDENCE QUALITY:** {evidence_quality}

**REASONING TASK:**

1. **WHO 2021 Alignment Assessment:**
   - Does this diagnosis use WHO 2021 terminology?
   - Look for: molecular subtype designations (IDH-mutant, SHH-activated, etc.), modern grading (CNS WHO grade X), appropriate NOS/NEC usage
   - Check if it references WHO 2021 / 5th edition / WHO CNS5 / WHO Paediatric Tumours 5th ed

2. **Evidence Sufficiency Evaluation:**
   - Is the available molecular/histologic evidence sufficient for WHO 2021 classification?
   - Complete: All required markers tested → definitive classification possible
   - Partial: Core markers tested → classification possible with caveats
   - Minimal: Insufficient testing → NOS designation required

3. **Translation Strategy (if needed):**
   - If already WHO 2021 compliant → use as-is
   - If old terminology + complete evidence → translate to WHO 2021 equivalent
   - If old terminology + partial evidence → translate with caveats
   - If old terminology + minimal evidence → translate + append "NOS"

   Translation Examples:
   - "Anaplastic astrocytoma" + no IDH testing → "Diffuse glioma, NOS, CNS WHO grade 3"
   - "Medulloblastoma, classic" + PTCH1 mutation + TP53-wildtype → "Medulloblastoma, SHH-activated, TP53-wildtype, CNS WHO grade 4"
   - "Glioblastoma multiforme" + IDH-wildtype confirmed → "Glioblastoma, IDH-wildtype, CNS WHO grade 4"
   - "Medulloblastoma, SHH-activated, TP53-wildtype [WHO 5th ed]" → already compliant, use as-is

**WHO 2021 CNS TUMOR CLASSIFICATION REFERENCE:**
{self.who_reference}

**OUTPUT FORMAT:**

Return this JSON:

{{
  "alignment_status": "who_2021_compliant / needs_translation / insufficient_evidence",

  "reasoning": "Step-by-step analysis:\n1. Is this WHO 2021 terminology? [explain]\n2. What evidence is available? [list]\n3. Is evidence sufficient? [explain]\n4. Translation needed? [explain decision]",

  "who_2021_diagnosis": "Final diagnosis using WHO 2021 terminology",

  "molecular_subtype": "Molecular classification (e.g., 'SHH-activated medulloblastoma') or null",

  "grade": 1-4 or null,

  "key_markers": "Comma-separated molecular markers supporting this classification, or 'None documented' or 'Insufficient molecular characterization'",

  "evidence_level": "complete / partial / minimal",

  "translation_notes": "What changed from original diagnosis (if anything) and why. If no change, say 'Diagnosis already WHO 2021 compliant'",

  "nos_nec_rationale": "If NOS or NEC appended, explain what evidence is missing that prevents definitive classification. Otherwise null.",

  "confidence": "high / moderate / low",

  "confidence_rationale": "Explain why this confidence level based on evidence quality and terminology clarity",

  "clinical_significance": "Brief statement of clinical/prognostic significance based on WHO 2021 classification"
}}

**CRITICAL RULES:**
1. TRUST the pathologist's fundamental tumor type (medulloblastoma, glioma, ependymoma, etc.)
2. DO NOT change the tumor family - only update terminology and molecular subtype designations
3. When in doubt, use "NOS" rather than making unsupported molecular claims
4. If pathologist already used WHO 2021 terms, return their diagnosis unchanged
5. Grade should always be included for CNS tumors (grades 1-4)

**IMPORTANT:** Return ONLY the JSON object, no additional text.
"""

        try:
            # Use MedGemma for reasoning-based translation
            # Slightly higher temperature (0.1) to allow reasoning flexibility
            result = self.medgemma_agent.extract(translation_prompt, temperature=0.1)

            # Parse JSON response
            translation = json.loads(result.raw_response)

            # Log result
            alignment = translation.get('alignment_status', 'unknown')
            who_dx = translation.get('who_2021_diagnosis', 'Unknown')
            evidence_level = translation.get('evidence_level', 'unknown')
            confidence = translation.get('confidence', 'unknown')

            logger.info(f"      Alignment status: {alignment}")
            logger.info(f"      WHO 2021 diagnosis: {who_dx}")
            logger.info(f"      Evidence level: {evidence_level}")
            logger.info(f"      Confidence: {confidence}")

            # Add audit trail
            translation['raw_translation'] = result.raw_response
            translation['translation_timestamp'] = datetime.now().isoformat()
            translation['original_diagnosis'] = diagnosis_text

            return translation

        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Phase 0.3 JSON parse error: {e}")
            logger.error(f"      Response preview: {result.raw_response[:500]}")
            return {
                "alignment_status": "error",
                "who_2021_diagnosis": diagnosis_text,
                "error": str(e),
                "raw_response": result.raw_response[:1000]
            }
        except Exception as e:
            logger.error(f"   ❌ Phase 0.3 translation error: {e}")
            return {
                "alignment_status": "error",
                "who_2021_diagnosis": diagnosis_text,
                "error": str(e)
            }
