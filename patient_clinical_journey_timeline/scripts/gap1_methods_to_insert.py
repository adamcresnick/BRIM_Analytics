# V4.6 GAP #1 - Methods to insert after _fetch_source_documents() at line 5648
# INSERT LOCATION: After line 5648 in patient_timeline_abstraction_V3.py

    def _try_alternative_document_source(self, alternative: Dict, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Execute Investigation Engine's suggested alternative document source.

        Args:
            alternative: Dict with 'method', 'description', 'confidence'
            event: The event missing data
            gap_type: Type of gap (radiation_dose, surgery_eor, imaging_conclusion)

        Returns:
            List of document IDs found via alternative method, or []
        """
        method = alternative.get('method')
        logger.info(f"        Executing alternative method: {method}")

        try:
            if method == 'v_radiation_documents_priority':
                return self._query_radiation_documents_by_priority(event)

            elif method == 'structured_conclusion':
                return self._get_imaging_structured_conclusion(event)

            elif method == 'result_information_field':
                return self._get_imaging_result_information(event)

            elif method == 'v_document_reference_enriched':
                return self._query_document_reference_enriched(event)

            elif method == 'expand_temporal_window':
                return self._query_documents_expanded_window(event, gap_type)

            elif method == 'expand_document_categories':
                return self._query_alternative_document_categories(event, gap_type)

            else:
                logger.warning(f"        Unknown alternative method: {method}")
                return []

        except Exception as e:
            logger.error(f"        Error executing alternative {method}: {e}")
            return []

    def _query_radiation_documents_by_priority(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Query v_radiation_documents with extraction_priority sorting.

        Prioritizes treatment summaries (priority=1) over progress notes.
        """
        from utils.athena_helpers import query_athena

        radiation_date = event.get('event_date')
        if not radiation_date:
            return []

        logger.info(f"        🔍 Querying v_radiation_documents for {radiation_date}")

        query = f"""
        SELECT document_id, doc_type_text, doc_date, doc_description,
               extraction_priority, document_category, docc_attachment_url as binary_id
        FROM fhir_prd_db.v_radiation_documents
        WHERE patient_fhir_id = '{self.athena_patient_id}'
          AND ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) <= 45
        ORDER BY extraction_priority ASC,
                 ABS(DATE_DIFF('day', CAST(doc_date AS DATE), CAST(TIMESTAMP '{radiation_date}' AS DATE))) ASC
        LIMIT 3
        """

        results = query_athena(
            query,
            f"Finding priority radiation documents for {radiation_date}",
            suppress_output=True
        )

        if results:
            doc_ids = [row.get('document_id', row.get('binary_id', '')) for row in results if row.get('document_id') or row.get('binary_id')]
            logger.info(f"        ✅ Found {len(doc_ids)} priority radiation documents")
            return doc_ids

        return []

    def _get_imaging_structured_conclusion(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Extract imaging conclusion from structured DiagnosticReport.conclusion field.

        Instead of extracting from Binary, use the structured conclusion field directly.
        This is MUCH more reliable than OCR + LLM extraction.
        """
        # Check if event already has result_information from v2_imaging
        result_info = event.get('result_information', '')

        if result_info and len(result_info) > 50:
            logger.info(f"        ✅ Found structured conclusion ({len(result_info)} chars)")
            # Create a pseudo-document ID for tracking
            pseudo_doc_id = f"structured_conclusion_{event.get('event_id', 'unknown')}"

            # Cache this as if it were a binary document
            if not hasattr(self, 'binary_extractions'):
                self.binary_extractions = []

            self.binary_extractions.append({
                'binary_id': pseudo_doc_id,
                'extracted_text': result_info,
                'content_type': 'structured_field',
                'resource_type': 'DiagnosticReport',
                'fhir_target': event.get('event_id', '')
            })

            return [pseudo_doc_id]

        return []

    def _get_imaging_result_information(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Extract from v2_imaging.result_information field.

        Alternative to structured conclusion - checks result_information field.
        """
        result_info = event.get('result_information', '')

        if result_info and len(result_info) > 30:
            logger.info(f"        ✅ Found result_information field ({len(result_info)} chars)")
            pseudo_doc_id = f"result_information_{event.get('event_id', 'unknown')}"

            if not hasattr(self, 'binary_extractions'):
                self.binary_extractions = []

            self.binary_extractions.append({
                'binary_id': pseudo_doc_id,
                'extracted_text': result_info,
                'content_type': 'structured_field',
                'resource_type': 'DiagnosticReport',
                'fhir_target': event.get('event_id', '')
            })

            return [pseudo_doc_id]

        return []

    def _query_document_reference_enriched(self, event: Dict) -> List[str]:
        """
        V4.6 GAP #1: Query v_document_reference_enriched with encounter-based lookup.

        Better for finding operative notes that may be attached to different encounters.
        """
        from utils.athena_helpers import query_athena

        event_date = event.get('event_date')
        if not event_date:
            return []

        logger.info(f"        🔍 Querying v_document_reference_enriched for {event_date}")

        # Query with broader temporal window since encounter linkage is more precise
        query = f"""
        SELECT document_reference_id, binary_id, document_type, document_date
        FROM fhir_prd_db.v_document_reference_enriched
        WHERE patient_fhir_id = '{self.athena_patient_id}'
          AND ABS(DATE_DIFF('day', CAST(document_date AS DATE), CAST(TIMESTAMP '{event_date}' AS DATE))) <= 14
          AND document_type IN ('operative note', 'surgical note', 'procedure note')
        ORDER BY ABS(DATE_DIFF('day', CAST(document_date AS DATE), CAST(TIMESTAMP '{event_date}' AS DATE))) ASC
        LIMIT 2
        """

        results = query_athena(
            query,
            f"Finding encounter-based documents for {event_date}",
            suppress_output=True
        )

        if results:
            doc_ids = [row.get('document_reference_id', row.get('binary_id', '')) for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} encounter-based documents")
            return doc_ids

        return []

    def _query_documents_expanded_window(self, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Retry document query with expanded temporal window (±30 → ±60 days).

        Last resort for finding documents when normal temporal matching fails.
        """
        from utils.athena_helpers import query_athena

        event_date = event.get('event_date')
        if not event_date:
            return []

        logger.info(f"        🔍 Querying with expanded window (±60 days) for {event_date}")

        # Build category filter based on gap type
        if gap_type == 'surgery_eor':
            categories = "('operative note', 'surgical note', 'procedure note', 'surgeon note')"
        elif gap_type == 'radiation_dose':
            categories = "('radiation summary', 'treatment summary', 'radiation plan')"
        else:
            categories = "('radiology report', 'imaging report', 'diagnostic report')"

        query = f"""
        SELECT dr.id as document_id, dr.subject_reference as patient_ref
        FROM fhir_prd_db.document_reference dr
        WHERE dr.subject_reference = 'Patient/{self.athena_patient_id}'
          AND dr.category_text IN {categories}
          AND ABS(DATE_DIFF('day',
              CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
              CAST(TIMESTAMP '{event_date}' AS DATE)
          )) <= 60
        ORDER BY ABS(DATE_DIFF('day',
            CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
            CAST(TIMESTAMP '{event_date}' AS DATE)
        )) ASC
        LIMIT 2
        """

        results = query_athena(
            query,
            f"Finding documents with expanded window for {event_date}",
            suppress_output=True
        )

        if results:
            doc_ids = [row.get('document_id', '') for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} documents in expanded window")
            return doc_ids

        return []

    def _query_alternative_document_categories(self, event: Dict, gap_type: str) -> List[str]:
        """
        V4.6 GAP #1: Query alternative document categories (e.g., anesthesia records for EOR).

        Expands beyond primary categories to find any relevant documents.
        """
        from utils.athena_helpers import query_athena

        event_date = event.get('event_date')
        if not event_date:
            return []

        logger.info(f"        🔍 Querying alternative document categories for {event_date}")

        # Alternative categories by gap type
        if gap_type == 'surgery_eor':
            # Include anesthesia records, discharge summaries, post-op notes
            categories = "('anesthesia record', 'discharge summary', 'post-operative note', 'clinical note')"
        elif gap_type == 'radiation_dose':
            # Include consultation notes, outside records
            categories = "('consultation note', 'outside record', 'transfer summary')"
        else:
            return []  # No alternatives for imaging

        query = f"""
        SELECT dr.id as document_id
        FROM fhir_prd_db.document_reference dr
        WHERE dr.subject_reference = 'Patient/{self.athena_patient_id}'
          AND dr.category_text IN {categories}
          AND ABS(DATE_DIFF('day',
              CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
              CAST(TIMESTAMP '{event_date}' AS DATE)
          )) <= 30
        ORDER BY ABS(DATE_DIFF('day',
            CAST(TRY(date_parse(dr.date, '%Y-%m-%dT%H:%i:%s.%fZ')) AS DATE),
            CAST(TIMESTAMP '{event_date}' AS DATE)
        )) ASC
        LIMIT 2
        """

        results = query_athena(
            query,
            f"Finding alternative category documents for {event_date}",
            suppress_output=True
        )

        if results:
            doc_ids = [row.get('document_id', '') for row in results]
            logger.info(f"        ✅ Found {len(doc_ids)} alternative category documents")
            return doc_ids

        return []

    def _get_cached_binary_text(self, doc_id: str) -> Optional[str]:
        """
        V4.6 GAP #1: Get cached binary text from binary_extractions or structured fields.

        Returns text from either Binary extraction or structured field pseudo-documents.
        """
        if not hasattr(self, 'binary_extractions'):
            return None

        for extraction in self.binary_extractions:
            if extraction.get('binary_id') == doc_id:
                return extraction.get('extracted_text', '')

        return None
