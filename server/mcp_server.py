"""MCP Service Resolution Assistant - Server.

Exposes the 'service-resolution-server' MCP server with tools and resources:
- Tools:
    1. analyze_problem(problem: str)
    2. search_services(service_category: str)
    3. get_provider_details(provider_id: int)
    4. check_availability(provider_id: int, date: str)
    5. schedule_appointment(provider_id: int, date: str, time: str, customer_name: str, service_id: int, problem: str)
    6. cancel_appointment(appointment_id: int)
    7. search_external_providers(service: str, location: str)
- Resources:
    - service://categories (and service://service_categories)
    - service://faqs (and service://service_faqs)
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path regardless of execution working directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    # Official MCP Python SDK v2+
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("service-resolution-server")
except (ImportError, ModuleNotFoundError):
    # Fallback for MCP Python SDK v1
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("service-resolution-server")

from data.seed_data import FAQS, SERVICE_CATEGORIES
from database.database import init_db

# Import modular tools
from server.tools.problem_analyzer import analyze_problem as _analyze_problem
from server.tools.service_search import (
    search_external_providers as _search_external_providers,
    search_services as _search_services,
)
from server.tools.provider_details import get_provider_details as _get_provider_details
from server.tools.availability import check_availability as _check_availability
from server.tools.appointment import schedule_appointment as _schedule_appointment
from server.tools.cancellation import cancel_appointment as _cancel_appointment
from server.tools.diagnostic_lookup import (
    lookup_appliance_error_code as _lookup_appliance_error_code,
    verify_part_pricing as _verify_part_pricing,
)

# Initialize database schema and ensure providers are seeded
init_db(force_reseed=True)


# ============================================================================
# TOOL #1: analyze_problem
# ============================================================================


@mcp.tool(
    name="analyze_problem",
    description="Analyze a user problem and identify the service category, issue summary, and confidence using keyword matching."
)
def analyze_problem(problem: str) -> Dict[str, Any]:
    """Analyze the user's issue and return category, issue summary, and confidence."""
    return _analyze_problem(problem)


# ============================================================================
# TOOL #2: search_services
# ============================================================================


@mcp.tool(
    name="search_services",
    description="Search service providers by service category from SQLite. Returns list of providers with ratings, location, and price ranges."
)
def search_services(service_category: str) -> List[Dict[str, Any]]:
    """Query the SQLite database for providers matching the category."""
    return _search_services(service_category)


# ============================================================================
# TOOL #3: get_provider_details
# ============================================================================


@mcp.tool(
    name="get_provider_details",
    description="Get detailed information for a specific service provider by provider ID (service, rating, location, price range, phone)."
)
def get_provider_details(provider_id: int) -> Dict[str, Any]:
    """Retrieve full provider information from SQLite."""
    return _get_provider_details(provider_id)


# ============================================================================
# TOOL #4: check_availability
# ============================================================================


@mcp.tool(
    name="check_availability",
    description="Check available time slots for a service provider on a given date (YYYY-MM-DD)."
)
def check_availability(provider_id: int, date: str) -> Dict[str, Any]:
    """Query available slots for a provider on a specific date."""
    return _check_availability(provider_id, date)


# ============================================================================
# TOOL #5: schedule_appointment
# ============================================================================


@mcp.tool(
    name="schedule_appointment",
    description="Schedule a service appointment with a provider and save it to the SQLite database."
)
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
    """Insert a new appointment into SQLite and return confirmation."""
    return _schedule_appointment(
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


# ============================================================================
# TOOL #6: cancel_appointment
# ============================================================================


@mcp.tool(
    name="cancel_appointment",
    description="Cancel an existing service appointment in SQLite by appointment ID."
)
def cancel_appointment(appointment_id: int) -> Dict[str, Any]:
    """Cancel an appointment in the database."""
    return _cancel_appointment(appointment_id)


# ============================================================================
# TOOL #7: search_external_providers (Tavily Web Search)
# ============================================================================


@mcp.tool(
    name="search_external_providers",
    description="Search for external web-listed service providers using Tavily Web Search (demonstrates MCP + external API integration)."
)
def search_external_providers(service: str, location: str = "Goa") -> List[Dict[str, Any]]:
    """Search the web for external service providers via Tavily API."""
    return _search_external_providers(service, location)


# ============================================================================
# TOOL #8: lookup_appliance_error_code (Tavily AI Manual & Error Code Engine)
# ============================================================================


@mcp.tool(
    name="lookup_appliance_error_code",
    description="Look up official manufacturer diagnostic error codes, causes, and DIY/safety steps from live service manuals via Tavily."
)
def lookup_appliance_error_code(
    brand: str,
    model_or_error: str,
    appliance_type: str = "appliance",
) -> Dict[str, Any]:
    """Look up official manufacturer diagnostic error codes and manual solutions."""
    return _lookup_appliance_error_code(brand, model_or_error, appliance_type)


# ============================================================================
# TOOL #9: verify_part_pricing (Tavily AI Spare Part Anti-Fraud Checker)
# ============================================================================


@mcp.tool(
    name="verify_part_pricing",
    description="Check fair-market price benchmarks for spare parts and labor in India to protect consumers against inflated repair bills."
)
def verify_part_pricing(
    appliance: str,
    part_name: str,
    quoted_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify live fair-market repair and spare parts pricing."""
    return _verify_part_pricing(appliance, part_name, quoted_price)


# ============================================================================
# MCP RESOURCES
# ============================================================================


@mcp.resource("service://categories")
def get_service_categories() -> str:
    """Return supported service categories."""
    return json.dumps(SERVICE_CATEGORIES, indent=2)


@mcp.resource("service://service_categories")
def get_service_categories_alias() -> str:
    """Alias for service_categories resource."""
    return json.dumps(SERVICE_CATEGORIES, indent=2)


@mcp.resource("service://faqs")
def get_service_faqs() -> str:
    """Return common service mappings and FAQs."""
    return (
        "Common Service Mappings:\n"
        "AC not cooling → AC Repair\n"
        "Laptop overheating → Laptop Repair\n"
        "Water leakage → Plumbing\n"
        "Washing machine not spinning → Washing Machine Repair\n\n"
        "Frequently Asked Questions:\n"
        "1. How do I schedule an appointment?\n"
        "   First use analyze_problem to find the category, then search_services to pick a provider, "
        "check_availability for slots, and schedule_appointment to book.\n"
        "2. What is the cancellation policy?\n"
        "   Appointments can be cancelled before the scheduled slot using cancel_appointment.\n"
        "3. Are prices guaranteed?\n"
        "   Listed prices are standard estimates; final costs depend on parts and labor."
    )


@mcp.resource("service://service_faqs")
def get_service_faqs_alias() -> str:
    """Alias for service_faqs resource."""
    return get_service_faqs()


if __name__ == "__main__":
    mcp.run(transport="stdio")
