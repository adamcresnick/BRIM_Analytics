"""
Complete implementation code for Agent 1 Phases 4, 5, and 6.

This file contains the exact code to replace the TODO sections in:
run_full_multi_source_abstraction.py

To apply: Copy the relevant sections into the script at the marked locations.
"""

# ================================================================
# PHASE 4: AGENT 1 <-> AGENT 2 ITERATIVE CLARIFICATION
# ================================================================
# Replace lines 959-968 in run_full_multi_source_abstraction.py

PHASE_4_IMPLEMENTATION = """
        clarifications = []

        # Query Agent 2 for clarification on high-severity inconsistencies
        high_severity_inc = [i for i in inconsistencies if i.get('requires_agent2_query')]

        for inc in high_severity_inc:
            try:
                # Build clarification prompt
                clarification_prompt = f'''# AGENT 1 REQUESTS CLARIFICATION FROM AGENT 2

## Temporal Inconsistency Detected

**Type:** {inc['type']}
**Severity:** {inc['severity']}
**Description:** {inc['description']}

## Timeline
- **{inc['prior_date']}**: {inc['prior_status']}
- **{inc['current_date']}**: {inc['current_status']}
- **Days between**: {inc['days_between']}

## Question for Agent 2

After reviewing the timeline above:

1. **Clinical Plausibility**: Is this rapid change clinically plausible?
2. **Potential Explanations**: What could explain this pattern?
3. **Recommendation**: Should either extraction be revised?

Provide recommendation: keep_both | revise_first | revise_second | escalate_to_human
'''

                # Query Agent 2
                result = medgemma.extract(clarification_prompt, "temporal_inconsistency_clarification")

                clarifications.append({
                    'inconsistency_id': inc['inconsistency_id'],
                    'type': inc['type'],
                    'agent2_response': result.extracted_data if result.success else None,
                    'success': result.success,
                    'confidence': result.confidence,
                    'error': result.error if not result.success else None
                })

                if result.success:
                    print(f"    ✅ {inc['type']}: {result.extracted_data.get('recommended_action', 'N/A')}")
                else:
                    print(f"    ❌ {inc['type']}: Failed to get clarification")

            except Exception as e:
                logger.error(f"Failed to query Agent 2 for {inc['inconsistency_id']}: {e}")
                clarifications.append({
                    'inconsistency_id': inc['inconsistency_id'],
                    'success': False,
                    'error': str(e)
                })

        print(f"  {len(clarifications)} Agent 2 queries sent")
        if clarifications:
            successful = len([c for c in clarifications if c.get('success')])
            print(f"    Successful: {successful}/{len(clarifications)}")
        print()

        comprehensive_summary['phases']['agent_feedback'] = {
            'queries_sent': len(clarifications),
            'successful_clarifications': len([c for c in clarifications if c.get('success')]),
            'clarifications': clarifications
        }
        save_checkpoint('agent_feedback', 'completed')
"""


# ================================================================
# PHASE 5: AGENT 1 MULTI-SOURCE EOR ADJUDICATION
# ================================================================
# Replace lines 978-988 in run_full_multi_source_abstraction.py

PHASE_5_IMPLEMENTATION = """
        eor_adjudications = []

        # Group operative reports with their post-op imaging (within 72 hours)
        operative_reports = [e for e in all_extractions if e['source'] == 'operative_report']

        for op_report in operative_reports:
            try:
                surgery_date_str = op_report.get('surgery_date')
                if not surgery_date_str:
                    continue

                surgery_date = datetime.fromisoformat(str(surgery_date_str))
                proc_id = op_report['source_id']

                # Get EOR from operative report
                operative_eor = None
                if 'eor' in op_report and isinstance(op_report['eor'], dict):
                    eor_data = op_report['eor']
                    if not eor_data.get('error'):
                        operative_eor = eor_data.get('extent_of_resection')

                if not operative_eor or operative_eor == 'Unknown':
                    continue  # Skip if no EOR extracted

                # Find post-op imaging within 72 hours
                postop_imaging = []
                for ext in all_extractions:
                    if ext['source'] in ['imaging_text', 'imaging_pdf']:
                        try:
                            img_date = datetime.fromisoformat(str(ext['date']))
                            hours_diff = (img_date - surgery_date).total_seconds() / 3600

                            # Post-op imaging: 0-72 hours after surgery
                            if 0 <= hours_diff <= 72:
                                # Check if imaging mentions resection/EOR
                                classification = ext.get('classification', {})
                                if isinstance(classification, dict) and not classification.get('error'):
                                    imaging_type = classification.get('imaging_type', '').lower()
                                    # Look for post-op assessment keywords
                                    if any(keyword in imaging_type for keyword in ['post', 'operative', 'resection', 'surgical']):
                                        postop_imaging.append({
                                            'imaging_id': ext['source_id'],
                                            'imaging_date': ext['date'],
                                            'hours_after_surgery': round(hours_diff, 1),
                                            'tumor_status': ext.get('tumor_status', {}).get('overall_status'),
                                            'imaging_type': imaging_type
                                        })
                        except (ValueError, TypeError):
                            continue

                # Only adjudicate if we have both sources
                if postop_imaging:
                    # Build EOR sources for adjudicator
                    sources = [
                        EORSource(
                            source_type='operative_report',
                            source_id=proc_id,
                            source_date=surgery_date,
                            eor=operative_eor,
                            confidence=op_report.get('confidence', 0.85),
                            evidence=f"Operative report from {surgery_date.date()}",
                            extracted_by='agent2_medgemma'
                        )
                    ]

                    # Infer EOR from post-op imaging tumor status
                    for img in postop_imaging:
                        tumor_status = img.get('tumor_status')
                        inferred_eor = 'Unknown'

                        # Inference rules
                        if tumor_status == 'NED' or tumor_status == 'Decreased':
                            inferred_eor = 'Gross Total Resection'
                        elif tumor_status == 'Stable':
                            inferred_eor = 'Near Total Resection'
                        elif tumor_status == 'Increased':
                            inferred_eor = 'Partial Resection'

                        if inferred_eor != 'Unknown':
                            sources.append(
                                EORSource(
                                    source_type='postop_imaging',
                                    source_id=img['imaging_id'],
                                    source_date=datetime.fromisoformat(img['imaging_date']),
                                    eor=inferred_eor,
                                    confidence=0.70,  # Lower confidence for inferred EOR
                                    evidence=f"Post-op imaging ({img['hours_after_surgery']}h after surgery) shows {tumor_status}",
                                    extracted_by='agent2_medgemma'
                                )
                            )

                    # Adjudicate
                    adjudication = eor_adjudicator.adjudicate_eor(proc_id, surgery_date, sources)

                    eor_adjudications.append({
                        'procedure_id': proc_id,
                        'surgery_date': str(surgery_date.date()),
                        'final_eor': adjudication.final_eor,
                        'confidence': adjudication.confidence,
                        'primary_source': adjudication.primary_source,
                        'agreement_status': adjudication.agreement,
                        'sources_count': len(sources),
                        'operative_report_eor': operative_eor,
                        'postop_imaging_count': len(postop_imaging),
                        'discrepancy_notes': adjudication.discrepancy_notes,
                        'reasoning': adjudication.adjudication_reasoning
                    })

                    print(f"    Procedure {proc_id[:20]}... ({surgery_date.date()})")
                    print(f"      Operative: {operative_eor}")
                    print(f"      Final: {adjudication.final_eor} (confidence: {adjudication.confidence:.2f})")
                    if adjudication.agreement == 'discrepancy':
                        print(f"      ⚠️  Discrepancy: {adjudication.discrepancy_notes}")

            except Exception as e:
                logger.error(f"Failed to adjudicate EOR for {proc_id}: {e}")
                continue

        print(f"  {len(eor_adjudications)} EOR adjudications completed")
        if eor_adjudications:
            agreements = len([a for a in eor_adjudications if a['agreement_status'] == 'full_agreement'])
            discrepancies = len([a for a in eor_adjudications if a['agreement_status'] == 'discrepancy'])
            print(f"    Full agreement: {agreements}")
            print(f"    Discrepancies: {discrepancies}")
        print()

        comprehensive_summary['phases']['eor_adjudication'] = {
            'count': len(eor_adjudications),
            'full_agreement': len([a for a in eor_adjudications if a['agreement_status'] == 'full_agreement']),
            'discrepancies': len([a for a in eor_adjudications if a['agreement_status'] == 'discrepancy']),
            'adjudications': eor_adjudications
        }
        save_checkpoint('eor_adjudication', 'completed')
"""


# ================================================================
# PHASE 6: AGENT 1 EVENT TYPE CLASSIFICATION FIX
# ================================================================
# Replace try block at lines 910-928 in run_full_multi_source_abstraction.py

PHASE_6_FIX = """
        try:
            # Write extractions to timeline first so classifier can access them
            workflow_logger.log_info("Writing tumor status extractions to timeline for event classification")

            for ext in all_extractions:
                if ext['source'] in ['imaging_text', 'imaging_pdf']:
                    if 'tumor_status' in ext and isinstance(ext['tumor_status'], dict):
                        ts_data = ext['tumor_status']
                        if not ts_data.get('error'):
                            tumor_status = ts_data.get('overall_status') or ts_data.get('tumor_status')
                            if tumor_status and tumor_status != 'Unknown':
                                try:
                                    # Write to timeline so event_classifier can query it
                                    timeline.conn.execute('''
                                        INSERT OR IGNORE INTO extracted_variables
                                        (patient_id, source_event_id, variable_name, variable_value, variable_confidence, extraction_date)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    ''', [
                                        args.patient_id,
                                        ext['source_id'],
                                        'tumor_status',
                                        tumor_status,
                                        ext.get('tumor_status_confidence', 0.0),
                                        datetime.now().isoformat()
                                    ])
                                except Exception as e:
                                    logger.warning(f"Failed to write tumor_status to timeline: {e}")

            timeline.conn.commit()

            # Write EOR extractions to timeline
            for ext in all_extractions:
                if ext['source'] == 'operative_report' and 'eor' in ext:
                    if isinstance(ext['eor'], dict) and not ext['eor'].get('error'):
                        eor_value = ext['eor'].get('extent_of_resection')
                        if eor_value and eor_value != 'Unknown':
                            try:
                                timeline.conn.execute('''
                                    INSERT OR IGNORE INTO extracted_variables
                                    (patient_id, source_event_id, variable_name, variable_value, variable_confidence, extraction_date)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', [
                                    args.patient_id,
                                    ext['source_id'],
                                    'extent_of_resection',
                                    eor_value,
                                    ext.get('confidence', 0.0),
                                    datetime.now().isoformat()
                                ])
                            except Exception as e:
                                logger.warning(f"Failed to write EOR to timeline: {e}")

            timeline.conn.commit()

            # Now classify events
            event_classifications_raw = event_classifier.classify_patient_events(args.patient_id)

            # Convert to dict format
            event_classifications = []
            for cls in event_classifications_raw:
                event_classifications.append({
                    'event_id': cls.event_id,
                    'event_date': cls.event_date.isoformat() if isinstance(cls.event_date, datetime) else str(cls.event_date),
                    'event_type': cls.event_type,
                    'confidence': cls.confidence,
                    'reasoning': cls.reasoning,
                    'supporting_evidence': cls.supporting_evidence
                })

            print(f"  ✅ Classified {len(event_classifications)} events")

            # Show sample with counts by type
            type_counts = {}
            for cls in event_classifications:
                event_type = cls['event_type']
                type_counts[event_type] = type_counts.get(event_type, 0) + 1

            for event_type, count in sorted(type_counts.items()):
                print(f"    {event_type}: {count}")

            # Show samples
            for cls in event_classifications[:3]:
                print(f"    - {cls['event_date']}: {cls['event_type']} (confidence: {cls['confidence']:.2f})")

            comprehensive_summary['phases']['event_classification'] = {
                'count': len(event_classifications),
                'by_type': type_counts,
                'classifications': event_classifications
            }
        except Exception as e:
            logger.error(f"Event classification failed: {e}", exc_info=True)
            print(f"  ❌ Event classification failed: {e}")
            comprehensive_summary['phases']['event_classification'] = {
                'count': 0,
                'error': str(e)
            }

        print()
        save_checkpoint('event_classification', 'completed')
"""


# How to apply these changes:
# 1. Open run_full_multi_source_abstraction.py
# 2. Find Phase 4 section (around line 959)
# 3. Replace the TODO block with PHASE_4_IMPLEMENTATION code
# 4. Find Phase 5 section (around line 978)
# 5. Replace the TODO block with PHASE_5_IMPLEMENTATION code
# 6. Find Phase 6 section (around line 910)
# 7. Replace the try block with PHASE_6_FIX code
