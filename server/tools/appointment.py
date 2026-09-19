"""Appointment Scheduling Tool for MCP Service Resolution Assistant.

Schedules confirmed service appointments in SQLite database with conflict prevention.
"""

import os
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import schedule_appointment_db


def schedule_appointment(
    provider_id: int,
    date: str,
    time: str,
    customer_name: str,
    service_id: int = 1,
    problem: str = "",
    customer_phone: str = "",
    customer_email: str = "",
    customer_address: str = "",
) -> Dict[str, Any]:
    """Insert a new appointment into SQLite and return confirmation.

    If the slot is already taken, returns:
    {'success': False, 'message': 'This slot is no longer available.', ...}
    per STEP 26 error handling specs.
    """
    return schedule_appointment_db(
        provider_id=provider_id,
        date=date,
        time=time,
        customer_name=customer_name,
        service_id=service_id,
        problem=problem,
        customer_phone=customer_phone,
        customer_email=customer_email,
        customer_address=customer_address,
    )
