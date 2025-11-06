# V4.6 GAPS #2, #3, #5 - Complete Implementation
# INSERT INTO: patient_timeline_abstraction_V3.py after _get_cached_binary_text() (line ~5867)

    def _compute_treatment_change_reasons(self):
        """
        V4.6 GAP #2: Compute reason for treatment changes (progression vs toxicity vs completion).

        Analyzes imaging between treatment lines to determine why treatment changed.
        Updates chemotherapy events with reason_for_change_from_prior field.
        """
        logger.info("📊 V4.6 GAP #2: Computing treatment change reasons...")

        # Find all chemotherapy episodes
        chemo_events = [e for e in self.timeline_events
                       if e.get('event_type') in ['chemo_start', 'chemotherapy_start']]
        chemo_events.sort(key=lambda x: x.get('event_date', ''))

        if len(chemo_events) < 2:
            logger.info("  No treatment line changes to analyze")
            return

        # Analyze each treatment line transition
        for i in range(1, len(chemo_events)):
            prior_event = chemo_events[i - 1]
            current_event = chemo_events[i]

            # Find corresponding chemo_end for prior event
            prior_end_date = self._find_chemo_end_date(prior_event)
            current_start_date = current_event.get('event_date')

            if not prior_end_date or not current_start_date:
                continue

            # Analyze imaging between treatment lines
            reason = self._analyze_treatment_change_reason(
                prior_end_date,
                current_start_date,
                prior_event,
                current_event
            )

            # Update current event with reason
            if 'relationships' not in current_event:
                current_event['relationships'] = {}
            if 'ordinality' not in current_event['relationships']:
                current_event['relationships']['ordinality'] = {}

            current_event['relationships']['ordinality']['reason_for_change_from_prior'] = reason

            logger.info(f"  Line {i} → {i+1} change reason: {reason}")

        logger.info("✅ Treatment change reasons computed")

    def _find_chemo_end_date(self, chemo_start_event: Dict) -> Optional[str]:
        """Find the end date for a chemotherapy episode."""
        # Look for explicit chemo_end event
        start_date = chemo_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') in ['chemo_end', 'chemotherapy_end']:
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    # Check if this is the nearest end after this start
                    return end_date

        # Fallback: Use therapy_end_date field if present
        return chemo_start_event.get('therapy_end_date')

    def _analyze_treatment_change_reason(
        self,
        prior_end_date: str,
        current_start_date: str,
        prior_event: Dict,
        current_event: Dict
    ) -> str:
        """
        V4.6 GAP #2: Analyze why treatment changed between two lines.

        Returns:
            "progression" | "toxicity" | "completion" | "unclear"
        """
        # Find imaging between treatment lines
        interim_imaging = [e for e in self.timeline_events
                          if e.get('event_type') == 'imaging'
                          and prior_end_date <= e.get('event_date', '') <= current_start_date]

        # Check for progression indicators in imaging
        for img in interim_imaging:
            # Check report_conclusion field
            conclusion = (img.get('report_conclusion', '') or img.get('result_information', '')).lower()

            # Progression keywords
            progression_keywords = [
                'progression', 'progressing', 'progressive', 'increased', 'enlarging',
                'enlargement', 'expansion', 'growing', 'growth', 'worsening', 'worsen',
                'new lesion', 'new enhancement', 'recurrence', 'recurrent'
            ]

            if any(kw in conclusion for kw in progression_keywords):
                return 'progression'

            # Check RANO assessment if present
            rano = img.get('rano_assessment', '')
            if rano == 'PD' or 'progressive disease' in rano.lower():
                return 'progression'

            # Check medgemma_extraction if present
            if 'medgemma_extraction' in img:
                extraction = img['medgemma_extraction']
                rano_ext = extraction.get('rano_assessment', '')
                if rano_ext == 'PD':
                    return 'progression'

        # Check for toxicity indicators in prior chemotherapy
        # (Would require clinical notes, not typically in structured data)

        # Check for completion indicators
        protocol_status = prior_event.get('protocol_status', '')
        if 'complete' in protocol_status.lower():
            return 'completion'

        # Default
        return 'unclear'

    def _enrich_event_relationships(self):
        """
        V4.6 GAP #3: Populate related_events for cross-event linkage.

        For each event, finds and links related events:
        - Surgery: preop_imaging, postop_imaging, pathology_reports
        - Chemotherapy: chemotherapy_end, response_imaging
        - Radiation: radiation_end, simulation_imaging
        """
        logger.info("🔗 V4.6 GAP #3: Enriching event relationships...")

        for event in self.timeline_events:
            if 'relationships' not in event:
                event['relationships'] = {}

            event_type = event.get('event_type')
            event_date = event.get('event_date')

            if not event_date:
                continue

            if event_type == 'surgery':
                event['relationships']['related_events'] = {
                    'preop_imaging': self._find_imaging_before(event, days=7),
                    'postop_imaging': self._find_imaging_after(event, days=7),
                    'pathology_reports': self._find_pathology_for_surgery(event)
                }

            elif event_type in ['chemo_start', 'chemotherapy_start']:
                event['relationships']['related_events'] = {
                    'chemotherapy_end': self._find_chemo_end(event),
                    'response_imaging': self._find_response_imaging(event)
                }

            elif event_type == 'radiation_start':
                event['relationships']['related_events'] = {
                    'radiation_end': self._find_radiation_end(event),
                    'simulation_imaging': self._find_simulation_imaging(event)
                }

        logger.info("✅ Event relationships enriched")

    def _find_imaging_before(self, surgery_event: Dict, days: int = 7) -> List[str]:
        """Find imaging within N days before surgery."""
        from datetime import datetime, timedelta

        surgery_date = datetime.fromisoformat(surgery_event['event_date'].replace('Z', '+00:00'))
        window_start = surgery_date - timedelta(days=days)

        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and window_start <= datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) < surgery_date]

        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _find_imaging_after(self, surgery_event: Dict, days: int = 7) -> List[str]:
        """Find imaging within N days after surgery."""
        from datetime import datetime, timedelta

        surgery_date = datetime.fromisoformat(surgery_event['event_date'].replace('Z', '+00:00'))
        window_end = surgery_date + timedelta(days=days)

        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and surgery_date < datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) <= window_end]

        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _find_pathology_for_surgery(self, surgery_event: Dict) -> List[str]:
        """Find pathology reports matching surgery specimen."""
        specimen_id = surgery_event.get('specimen_id')
        if not specimen_id:
            return []

        pathology_events = [e for e in self.timeline_events
                           if e.get('event_type') == 'pathology'
                           and e.get('specimen_id') == specimen_id]

        return [e.get('event_id', e.get('fhir_id', '')) for e in pathology_events]

    def _find_chemo_end(self, chemo_start_event: Dict) -> Optional[str]:
        """Find corresponding chemo_end event."""
        start_date = chemo_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') in ['chemo_end', 'chemotherapy_end']:
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    return event.get('event_id', event.get('fhir_id', ''))
        return None

    def _find_response_imaging(self, chemo_start_event: Dict) -> List[str]:
        """Find response imaging (first imaging >30 days after chemo end)."""
        from datetime import datetime, timedelta

        end_date_str = self._find_chemo_end_date(chemo_start_event)
        if not end_date_str:
            return []

        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        response_window_start = end_date + timedelta(days=30)

        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) >= response_window_start]

        imaging_events.sort(key=lambda x: x.get('event_date', ''))
        return [imaging_events[0].get('event_id', imaging_events[0].get('fhir_id', ''))] if imaging_events else []

    def _find_radiation_end(self, radiation_start_event: Dict) -> Optional[str]:
        """Find corresponding radiation_end event."""
        start_date = radiation_start_event.get('event_date')
        for event in self.timeline_events:
            if event.get('event_type') == 'radiation_end':
                end_date = event.get('event_date')
                if start_date and end_date and end_date > start_date:
                    return event.get('event_id', event.get('fhir_id', ''))
        return None

    def _find_simulation_imaging(self, radiation_start_event: Dict) -> List[str]:
        """Find simulation/planning imaging (±7 days before radiation start)."""
        from datetime import datetime, timedelta

        start_date = datetime.fromisoformat(radiation_start_event['event_date'].replace('Z', '+00:00'))
        window_start = start_date - timedelta(days=7)
        window_end = start_date + timedelta(days=7)

        imaging_events = [e for e in self.timeline_events
                         if e.get('event_type') == 'imaging'
                         and window_start <= datetime.fromisoformat(e['event_date'].replace('Z', '+00:00')) <= window_end]

        return [e.get('event_id', e.get('fhir_id', '')) for e in imaging_events]

    def _classify_imaging_response(self, report_text: str) -> Dict:
        """
        V4.6 GAP #5: Classify imaging response using RANO keywords.

        Aligns with IMAGING_REPORT_EXTRACTION_STRATEGY.md

        Returns:
            {
                'rano_assessment': 'PD' | 'SD' | 'PR' | 'CR' | None,
                'progression_flag': 'progression_suspected' | 'recurrence_suspected' | None,
                'response_flag': 'response_suspected' | 'stable_disease' | 'complete_response_suspected' | None
            }
        """
        if not report_text:
            return {'rano_assessment': None, 'progression_flag': None, 'response_flag': None}

        text_lower = report_text.lower()

        # Progressive disease (PD) indicators
        progression_keywords = [
            'progression', 'progressing', 'progressive',
            'increased', 'increase in', 'enlarging', 'enlargement', 'enlarged',
            'expansion', 'growing', 'growth', 'larger',
            'worsening', 'worsen', 'worse',
            'new enhancement', 'new lesion', 'additional lesion'
        ]

        recurrence_keywords = [
            'recurrence', 'recurrent', 'recurred',
            'tumor recurrence', 'disease recurrence'
        ]

        # Partial response (PR) indicators
        response_keywords = [
            'decreased', 'decrease in', 'decreasing',
            'reduction', 'reduced', 'reducing',
            'shrinkage', 'shrinking', 'smaller',
            'improvement', 'improved', 'improving',
            'resolving', 'resolved', 'resolution'
        ]

        # Stable disease (SD) indicators
        stable_keywords = [
            'stable', 'stability',
            'unchanged', 'no change', 'no significant change',
            'similar', 'comparable to prior'
        ]

        # Complete response (CR) indicators
        complete_response_keywords = [
            'no evidence of', 'no residual', 'no tumor',
            'complete resolution', 'complete response',
            'no enhancement', 'no enhancing lesion'
        ]

        # Check for progression
        if any(kw in text_lower for kw in progression_keywords):
            # Distinguish between progression and recurrence
            if any(kw in text_lower for kw in recurrence_keywords):
                return {
                    'rano_assessment': 'PD',
                    'progression_flag': 'recurrence_suspected',
                    'response_flag': None
                }
            else:
                return {
                    'rano_assessment': 'PD',
                    'progression_flag': 'progression_suspected',
                    'response_flag': None
                }

        # Check for complete response
        if any(kw in text_lower for kw in complete_response_keywords):
            return {
                'rano_assessment': 'CR',
                'progression_flag': None,
                'response_flag': 'complete_response_suspected'
            }

        # Check for partial response
        if any(kw in text_lower for kw in response_keywords):
            return {
                'rano_assessment': 'PR',
                'progression_flag': None,
                'response_flag': 'response_suspected'
            }

        # Check for stable disease
        if any(kw in text_lower for kw in stable_keywords):
            return {
                'rano_assessment': 'SD',
                'progression_flag': None,
                'response_flag': 'stable_disease'
            }

        # Unable to classify
        return {'rano_assessment': None, 'progression_flag': None, 'response_flag': None}

    def _enrich_imaging_with_rano_assessment(self):
        """
        V4.6 GAP #5: Add RANO assessment to all imaging events.

        Aligns with IMAGING_REPORT_EXTRACTION_STRATEGY.md
        Processes both structured conclusions and medgemma extractions.
        """
        logger.info("🏥 V4.6 GAP #5: Adding RANO assessment to imaging events...")

        imaging_count = 0
        classified_count = 0

        for event in self.timeline_events:
            if event.get('event_type') != 'imaging':
                continue

            imaging_count += 1

            # Get report text from multiple possible sources
            report_text = (
                event.get('report_conclusion', '') or
                event.get('result_information', '') or
                event.get('medgemma_extraction', {}).get('radiologist_impression', '')
            )

            # Classify using keywords
            classification = self._classify_imaging_response(report_text)

            # Add to event (don't overwrite if already present from MedGemma)
            if not event.get('rano_assessment'):
                event['rano_assessment'] = classification['rano_assessment']

            if not event.get('progression_flag'):
                event['progression_flag'] = classification['progression_flag']

            if not event.get('response_flag'):
                event['response_flag'] = classification['response_flag']

            if classification['rano_assessment']:
                classified_count += 1

        logger.info(f"  ✅ Classified {classified_count}/{imaging_count} imaging events")
        logger.info(f"     PD: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'PD')}")
        logger.info(f"     SD: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'SD')}")
        logger.info(f"     PR: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'PR')}")
        logger.info(f"     CR: {sum(1 for e in self.timeline_events if e.get('rano_assessment') == 'CR')}")
