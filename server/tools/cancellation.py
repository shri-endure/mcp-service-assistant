"""Appointment Cancellation Tool for MCP Service Resolution Assistant.

Cancels existing appointments in SQLite by appointment ID.
"""

import os
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import cancel_appointment_db


def cancel_appointment(appointment_id: int, reason: str = "Customer request") -> Dict[str, Any]:
    """Cancel an appointment in the database with an optional cancellation reason."""
    return cancel_appointment_db(appointment_id, reason=reason)
