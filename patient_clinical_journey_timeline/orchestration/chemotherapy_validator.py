"""
V4.8.2: Reasoning-Based Chemotherapy Data Quality Validator

Uses LLM reasoning to validate chemotherapy episode data quality,
identify implausible durations, missing dates, and suggest remediation strategies.
"""

import json
from typing import Dict, List, Any, Optional
import logging
from agents.medgemma_agent import MedGemmaAgent

logger = logging.getLogger(__name__)


class ChemotherapyValidator:
    """
    Reasoning-based validator for chemotherapy episode data quality.

    Uses medical LLM to assess clinical plausibility of:
    - Treatment durations
    - Missing stop dates
    - Dosage instructions vs structured dates mismatches
    """

    def __init__(self, medgemma_agent: Optional[MedGemmaAgent] = None):
        """
        Initialize validator with LLM agent.

        Args:
            medgemma_agent: Optional MedGemma agent for reasoning.
                          If None, will create default agent.
        """
        self.medgemma_agent = medgemma_agent or MedGemmaAgent(
            model_name="gemma2:27b",
            temperature=0.1  # Low temperature for consistent reasoning
        )

    def validate_chemotherapy_episodes(
        self,
        episodes: List[Dict[str, Any]],
        patient_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate chemotherapy episodes using LLM reasoning.

        Args:
            episodes: List of chemotherapy episode records from Phase 1
            patient_context: Optional patient context (diagnosis, age, etc.)

        Returns:
            Validation result with issues, reasoning, and recommendations
        """
        if not episodes:
            return {
                'issues_found': [],
                'validation_passed': True,
                'reasoning': 'No chemotherapy episodes to validate'
            }

        # Build reasoning prompt
        prompt = self._build_validation_prompt(episodes, patient_context)

        # Call LLM for reasoning
        logger.info(f"🤔 Validating {len(episodes)} chemotherapy episodes with LLM reasoning...")

        try:
            result = self.medgemma_agent.extract(
                prompt=prompt,
                document_text="",  # Prompt contains all needed context
                extraction_type="chemotherapy_validation"
            )

            if result.success:
                validation_data = result.extracted_data
                logger.info(f"✅ LLM validation complete: {len(validation_data.get('issues', []))} issues found")
                return {
                    'issues_found': validation_data.get('issues', []),
                    'validation_passed': len(validation_data.get('issues', [])) == 0,
                    'reasoning': validation_data.get('reasoning', ''),
                    'recommendations': validation_data.get('recommendations', []),
                    'raw_llm_response': result.raw_response
                }
            else:
                logger.error(f"LLM validation failed: {result.error}")
                return {
                    'issues_found': [],
                    'validation_passed': None,
                    'reasoning': f'Validation error: {result.error}'
                }

        except Exception as e:
            logger.error(f"Error during chemotherapy validation: {e}")
            return {
                'issues_found': [],
                'validation_passed': None,
                'reasoning': f'Validation exception: {str(e)}'
            }

    def _build_validation_prompt(
        self,
        episodes: List[Dict[str, Any]],
        patient_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build LLM reasoning prompt for chemotherapy validation.

        Args:
            episodes: Chemotherapy episode records
            patient_context: Patient diagnosis, age, etc.

        Returns:
            Structured prompt for LLM validation
        """
        # Summarize episodes for LLM
        episodes_summary = []
        for i, ep in enumerate(episodes[:20]):  # Limit to first 20 for token efficiency
            summary = {
                'episode_num': i + 1,
                'drug': ep.get('episode_drug_names') or ep.get('chemo_preferred_name', 'Unknown'),
                'drug_category': ep.get('chemo_drug_category'),
                'start_date': ep.get('episode_start_datetime') or ep.get('raw_medication_start_date'),
                'end_date': ep.get('episode_end_datetime') or ep.get('raw_medication_stop_date'),
                'duration_days': ep.get('episode_duration_days'),
                'dosage_instructions': ep.get('medication_dosage_instructions', '')[:200],  # Truncate
                'has_stop_date': bool(ep.get('raw_medication_stop_date')),
                'medications_with_stop_date': ep.get('medications_with_stop_date', 0),
                'care_plan': ep.get('episode_care_plan_title')
            }
            episodes_summary.append(summary)

        # Build context
        context = ""
        if patient_context:
            diagnosis = patient_context.get('diagnosis', 'Unknown')
            context = f"Patient diagnosis: {diagnosis}\n"

        prompt = f"""You are a medical data quality expert reviewing chemotherapy episode data from an EHR system.

{context}
CHEMOTHERAPY EPISODES TO VALIDATE:
{json.dumps(episodes_summary, indent=2)}

TASK:
Analyze each chemotherapy episode for data quality issues. Look for:

1. **Implausible durations**:
   - Treatment durations that are clinically unlikely for the drug type
   - Example: Temozolomide typically given for 5-42 days per cycle, not 1 day or 2000+ days
   - Consider drug category (chemotherapy vs immunotherapy vs targeted therapy)

2. **Missing stop dates**:
   - Episodes with start dates but no stop dates
   - Especially when dosage instructions contain duration information (e.g., "Until 11/16/17")

3. **Data inconsistencies**:
   - Duration_days doesn't match start/end dates
   - Dosage instructions contradict structured dates

4. **Clinical implausibility**:
   - Multiple overlapping episodes of same drug
   - Drug combinations that don't make clinical sense

For each issue found, provide:
- Episode number(s) affected
- Issue type and description
- Clinical reasoning for why it's problematic
- Recommended remediation strategy

Return your analysis as JSON:
{{
  "issues": [
    {{
      "episode_num": 1,
      "issue_type": "implausible_duration",
      "description": "Temozolomide episode shows 1 day duration",
      "reasoning": "Temozolomide is typically given for 5-day cycles or 28-day continuous regimens, not single doses",
      "recommended_action": "Parse dosage instructions to extract correct end date",
      "confidence": 0.9
    }}
  ],
  "reasoning": "Overall summary of data quality assessment",
  "recommendations": [
    {{
      "action": "use_v482_dosage_parser",
      "description": "Apply V4.8.2 dosage instruction parser to extract end dates from text",
      "applies_to_episodes": [1, 2, 3]
    }}
  ]
}}

Provide thoughtful medical reasoning. Do not use arbitrary thresholds - use clinical knowledge."""

        return prompt
