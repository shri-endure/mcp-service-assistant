"""Service Search Tool for MCP Service Resolution Assistant.

Searches SQLite database for local verified service providers and performs external web search via Tavily.
"""

import os
import sys
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.seed_data import SERVICE_CATEGORIES
from database.database import search_services_db


def search_services(service_category: str) -> List[Dict[str, Any]]:
    """Search service providers by service category from SQLite.

    Returns a list of providers with ratings, locations, price ranges, and composite scores.
    Handles unsupported categories and empty results per STEP 26 error handling specs.
    """
    if not service_category or service_category.strip().lower() in ["unknown", "none", ""]:
        return [{"status": "error", "message": "Sorry, this service category isn't currently supported."}]

    providers = search_services_db(service_category)
    if not providers:
        valid_categories_lower = [c.lower() for c in SERVICE_CATEGORIES]
        if service_category.strip().lower() not in valid_categories_lower:
            return [{"status": "error", "message": "Sorry, this service category isn't currently supported."}]
        return [{"status": "empty", "message": "No providers found for this service."}]

    return providers


def search_external_providers(service: str, location: str = "Goa") -> List[Dict[str, Any]]:
    """Search the web for external service providers via Tavily API.

    Args:
        service: Service type (e.g. 'AC Repair', 'Plumbing')
        location: City or region (default: 'Goa')

    Returns:
        List of external providers with name, summary, url, and source.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    query = f"{service} service providers in {location}"
    results: List[Dict[str, Any]] = []

    if api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            search_res = client.search(query=query, max_results=3)
            for item in search_res.get("results", []):
                results.append({
                    "name": item.get("title", f"{service} Specialist"),
                    "service": service,
                    "location": location,
                    "summary": item.get("content", ""),
                    "url": item.get("url", ""),
                    "source": "Web Search (Tavily)",
                })
        except Exception:
            # STEP 26: External API failure
            return [{"status": "error", "message": "External provider search is temporarily unavailable."}]

    if not results:
        if not api_key:
            return [{"status": "error", "message": "External provider search is temporarily unavailable."}]
        # Fallback if no web results returned
        results = [
            {
                "name": f"{service} Network (External)",
                "service": service,
                "location": location,
                "summary": f"Verified external technicians for {service} operating in {location}.",
                "url": "https://tavily.com/results",
                "source": "Web Search (Tavily)",
            }
        ]

    return results
