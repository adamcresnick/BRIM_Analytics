"""
V4.8: Intelligent Chemotherapy Date Adjudication Module

This module provides intelligent date adjudication for chemotherapy regimens,
using ALL available date fields and parsing dosage instructions to construct
accurate start/end dates.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def parse_dosage_duration(dosage_instructions: str) -> Optional[int]:
    """
    V4.8.2: Parse dosage instructions to extract treatment duration in days.

    Examples:
        "for 5 days" -> 5
        "every 24 hours for 5 days" -> 5
        "once daily for 1 week" -> 7
        "Starting 10/5/2017, Until Thu 11/16/17" -> calculated days
        "twice daily" -> None (ongoing)

    Args:
        dosage_instructions: Free text dosage instructions

    Returns:
        Duration in days, or None if ongoing/unclear
    """
    if not dosage_instructions:
        return None

    instructions_lower = dosage_instructions.lower()

    # V4.8.2: Pattern: "Starting [date], Until [date]" or "Until [date]"
    # Example: "Starting 10/5/2017, Until Thu 11/16/17"
    # Try to extract both dates and calculate duration
    starting_match = re.search(r'starting\s+(\d{1,2}/\d{1,2}/\d{4})', instructions_lower)
    until_match = re.search(r'until\s+(?:\w+\s+)?(\d{1,2}/\d{1,2}/\d{2,4})', instructions_lower)

    if starting_match and until_match:
        try:
            start_str = starting_match.group(1)
            until_str = until_match.group(1)

            # Parse dates (handles MM/DD/YYYY and MM/DD/YY formats)
            start_date = datetime.strptime(start_str, '%m/%d/%Y')

            # Handle 2-digit vs 4-digit year
            if len(until_str.split('/')[-1]) == 2:
                until_date = datetime.strptime(until_str, '%m/%d/%y')
            else:
                until_date = datetime.strptime(until_str, '%m/%d/%Y')

            duration_days = (until_date - start_date).days
            if duration_days > 0:
                return duration_days
        except Exception as e:
            logger.debug(f"Could not parse Starting/Until dates: {e}")

    # Pattern: "for X days"
    match = re.search(r'for\s+(\d+)\s+days?', instructions_lower)
    if match:
        return int(match.group(1))

    # Pattern: "for X weeks"
    match = re.search(r'for\s+(\d+)\s+weeks?', instructions_lower)
    if match:
        return int(match.group(1)) * 7

    # Pattern: "for X months"
    match = re.search(r'for\s+(\d+)\s+months?', instructions_lower)
    if match:
        return int(match.group(1)) * 30  # Approximate

    # V4.8.2 FIX: Only match "once" if NOT followed by "a day", "daily", "a week", etc.
    # This prevents "once a day" from being treated as a single dose
    if re.search(r'\bonce\b(?!\s+(a\s+)?(day|daily|week|weekly|month|monthly))', instructions_lower):
        return 1

    # Pattern: "1 dose" (single dose)
    if re.search(r'\b1\s+dose\b', instructions_lower):
        return 1

    # If no duration pattern found, return None (ongoing treatment)
    return None


def adjudicate_chemotherapy_dates(record: Dict) -> Tuple[Optional[str], Optional[str], str]:
    """
    V4.8: Intelligently adjudicate chemotherapy start and end dates using ALL available fields.

    Fallback Hierarchy:
    1. episode_start_datetime / episode_end_datetime (if both present)
    2. raw_medication_start_date / raw_medication_stop_date
    3. medication_start_datetime / medication_stop_datetime
    4. Calculate end date from start date + dosage instructions duration
    5. Use authored_date as fallback start if nothing else available

    Args:
        record: Chemotherapy record from v_chemo_treatment_episodes with all date fields

    Returns:
        Tuple of (start_date, end_date, adjudication_log)
    """
    start_date = None
    end_date = None
    adjudication_steps = []

    # TIER 1: episode-level dates (preferred if complete)
    episode_start = record.get('episode_start_datetime')
    episode_end = record.get('episode_end_datetime')

    if episode_start and episode_end:
        # Both episode dates present - use them
        start_date = episode_start.split()[0] if ' ' in episode_start else episode_start
        end_date = episode_end.split()[0] if ' ' in episode_end else episode_end
        adjudication_steps.append("✓ Tier 1: Used episode_start_datetime + episode_end_datetime")
        return start_date, end_date, " | ".join(adjudication_steps)

    # TIER 2: raw_medication dates (most reliable individual medication dates)
    raw_start = record.get('raw_medication_start_date')
    raw_stop = record.get('raw_medication_stop_date')

    if not start_date and raw_start:
        start_date = raw_start.split()[0] if ' ' in raw_start else raw_start
        adjudication_steps.append("✓ Tier 2a: Used raw_medication_start_date for start")

    if not end_date and raw_stop:
        end_date = raw_stop.split()[0] if ' ' in raw_stop else raw_stop
        adjudication_steps.append("✓ Tier 2a: Used raw_medication_stop_date for end")

    # TIER 3: medication_start/stop_datetime (structured medication dates)
    med_start = record.get('medication_start_datetime')
    med_stop = record.get('medication_stop_datetime')

    if not start_date and med_start:
        start_date = med_start.split()[0] if ' ' in med_start else med_start.split('T')[0]
        adjudication_steps.append("✓ Tier 3a: Used medication_start_datetime for start")

    if not end_date and med_stop:
        end_date = med_stop.split()[0] if ' ' in med_stop else med_stop.split('T')[0]
        adjudication_steps.append("✓ Tier 3a: Used medication_stop_datetime for end")

    # TIER 4: Calculate end date from dosage instructions + start date
    if start_date and not end_date:
        dosage_instructions = record.get('medication_dosage_instructions', '')
        duration_days = parse_dosage_duration(dosage_instructions)

        if duration_days:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', ''))
                end_dt = start_dt + timedelta(days=duration_days)
                end_date = end_dt.date().isoformat()
                adjudication_steps.append(f"✓ Tier 4: Calculated end date from dosage instructions ({duration_days} days)")
            except Exception as e:
                logger.debug(f"Could not calculate end date from dosage: {e}")

    # TIER 5: Fallback start date from authored_date
    if not start_date:
        authored_date = record.get('raw_medication_authored_date')
        if authored_date:
            start_date = authored_date.split()[0] if ' ' in authored_date else authored_date.split('T')[0]
            adjudication_steps.append("✓ Tier 5: Used raw_medication_authored_date as fallback start")
        elif episode_start:
            start_date = episode_start.split()[0] if ' ' in episode_start else episode_start
            adjudication_steps.append("✓ Tier 5: Used episode_start_datetime as fallback start")

    # Log if still missing dates
    if not start_date:
        adjudication_steps.append("⚠️  No start date found in any field")
    if not end_date:
        adjudication_steps.append("⚠️  No end date found - treatment may be ongoing or incomplete")

    return start_date, end_date, " | ".join(adjudication_steps)
