"""Provider Details Tool for MCP Service Resolution Assistant.

Retrieves detailed provider information (rating, location, price range, contact) from SQLite.
"""

import os
import sys
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.database import get_provider_details_db


def get_provider_details(provider_id: int) -> Dict[str, Any]:
    """Retrieve full provider information from SQLite by provider ID."""
    details = get_provider_details_db(provider_id)
    if not details:
        return {"error": f"Provider with ID {provider_id} not found."}
    return details
