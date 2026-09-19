"""Availability Tool for MCP Service Resolution Assistant.

Checks available time slots for a service provider on a given date against existing confirmed bookings.
"""

import os
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import check_availability_db


def check_availability(provider_id: int, date: str) -> Dict[str, Any]:
    """Query available slots for a provider on a specific date (YYYY-MM-DD or relative like 'Tomorrow').

    If all slots are booked, returns:
    'No slots available tomorrow. Would you like to check another date?'
    per STEP 26 error handling specs.
    """
    return check_availability_db(provider_id, date)
