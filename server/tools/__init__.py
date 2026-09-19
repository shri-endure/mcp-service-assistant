"""MCP Service Resolution Assistant - Tools Package.

Exposes individual modular tool handlers:
- problem_analyzer: analyze_problem
- service_search: search_services, search_external_providers
- provider_details: get_provider_details
- availability: check_availability
- appointment: schedule_appointment
- cancellation: cancel_appointment
"""

from server.tools.problem_analyzer import analyze_problem
from server.tools.service_search import search_services, search_external_providers
from server.tools.provider_details import get_provider_details
from server.tools.availability import check_availability
from server.tools.appointment import schedule_appointment
from server.tools.cancellation import cancel_appointment
from server.tools.diagnostic_lookup import lookup_appliance_error_code, verify_part_pricing

__all__ = [
    "analyze_problem",
    "search_services",
    "search_external_providers",
    "get_provider_details",
    "check_availability",
    "schedule_appointment",
    "cancel_appointment",
    "lookup_appliance_error_code",
    "verify_part_pricing",
]
