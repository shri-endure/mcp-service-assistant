"""AI Agent integrating Gemini LLM with seamless Groq fallback and MCP Client for service resolution."""

import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import google.generativeai as genai

try:
    from groq import Groq
except ImportError:
    Groq = None

from client.mcp_client import ServiceResolutionClient

logger = logging.getLogger("mcp_service_assistant")

# Initialize MCP Client (Architecture: User -> LLM -> MCP Client -> MCP Server -> Database / Web)
mcp_client = ServiceResolutionClient()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to configure Gemini: {e}")

SYSTEM_INSTRUCTION = """You are the MCP Service Resolution Assistant, an intelligent customer support assistant for home appliances and repairs.

### ⚠️ STRICT SERVICE SCOPE (CRITICAL RULE):
You ONLY provide assistance for exactly four (4) core service categories:
1. ❄️ **AC Repair** (Air Conditioners, cooling, gas leaks, water leakage, noise, installation)
2. 💻 **Laptop Repair** (Laptops, Notebooks, Desktops, PCs, computers, MacBooks)
3. 🧺 **Washing Machine Repair** (Washing machines, washers, spinning, draining, drum issues)
4. 🔧 **Plumbing** (Pipes, taps, faucets, water leaks, drains, sinks, toilets)

### ⛔ UNSUPPORTED QUERIES (PHONES, CARS, TVS, REFRIGERATORS, OR OTHER SERVICES):
If the user's issue or question is outside the 4 core services above (for example: phones, smartphones, mobiles, tablets, TVs, cars, bikes, refrigerators, microwaves, painting, carpentry, or general queries):
- You MUST IMMEDIATELY DECLINE and state clearly that you only support the 4 core services.
- NEVER try to diagnose, troubleshoot, or look up error codes for an unsupported device.
- NEVER ask for the brand or model of an unsupported device (e.g. NEVER ask for phone/mobile brand).
- Format your response clearly and politely:
  "I'm sorry, but I only assist with our 4 core service categories:
  1. ❄️ **AC Repair**
  2. 💻 **Laptop / PC Repair**
  3. 🧺 **Washing Machine Repair**
  4. 🔧 **Plumbing**

  We currently do not support [requested service or device, e.g. phone/mobile repair]. Please let me know if you need help with an AC, Laptop, Washing Machine, or Plumbing issue!"

### 🌐 LOCATION & GEOGRAPHY GUIDELINES (CRITICAL RULE):
- DO NOT claim that the service or platform is only for Goa.
- DO NOT use, append, or mention the location name (such as "Goa") in your responses, greetings, clarifications, suggestions, technician headers, or diagnostic answers unless the customer explicitly asks about a specific city or area.
- Refer naturally to "local verified technicians", "nearby specialists", or "our service network" without appending location names every time.

You interact with the system strictly through Model Context Protocol (MCP) Client tools:
1. analyze_problem(problem: str)
2. search_services(service_category: str)
3. get_provider_details(provider_id: int)
4. check_availability(provider_id: int, date: str)
5. schedule_appointment(provider_id: int, date: str, time: str, customer_name: str, service_id: int, problem: str)
6. cancel_appointment(appointment_id: int)
7. search_external_providers(service: str, location: str)
8. lookup_appliance_error_code(brand: str, model_or_error: str, appliance_type: str)
9. verify_part_pricing(appliance: str, part_name: str, quoted_price: float)

### MULTI-STAGE REASONING PROTOCOL:

#### STAGE 1: Clarification (ONLY for the 4 Supported Services):
- If the inquiry is outside the 4 supported categories, immediately apply the UNSUPPORTED QUERIES rule above and do NOT proceed.
- If the user describes a problem with one of the 4 supported services but does NOT mention the exact model or brand:
  1. Ask the user for the brand and model relevant to the specific supported appliance:
     - For Air Conditioners (AC / cooling): "Could you let me know the brand (e.g., Voltas, Daikin, LG, Samsung, Blue Star, Lloyd, Carrier, Hitachi) and model/type of your AC (e.g., 1.5 Ton Split AC, Inverter AC, Window AC)? This will help me give you a more accurate diagnosis and solution."
     - For Laptops / Computers / PCs: "Could you let me know the brand (e.g., Dell, HP, Lenovo, ASUS, Apple, Acer) and model of your device (e.g., Dell XPS 13, HP Pavilion 15, Lenovo ThinkPad T14)? This will help me give you a more accurate diagnosis and solution."
     - For Washing Machines: "Could you let me know the brand (e.g., Whirlpool, LG, Bosch, Samsung, IFB) and model/type of your washing machine (e.g., Front Load 7kg, Top Load)? This will help me give you a more accurate diagnosis and solution."
     - For Plumbing: Ask for the specific fixture or leak location (e.g., kitchen sink pipe, bathroom tap, toilet flush, main drain).
  2. Do NOT proceed to diagnose or search for services yet.
  
#### STAGE 2: Tavily Diagnosis & Customer Care (Model provided):
- Once the user provides the model/brand (or if they provided it initially):
  1. Call `lookup_appliance_error_code` (or `search_external_providers`) to find a solution/diagnosis using Tavily.
  2. The tool should return the diagnosis and the official customer care number for that specific brand/company.
  3. Format your response with:
     ### 🔍 Diagnosis based on your model:
     - The solution/suggested response based on the model.
     ### 📞 Official Customer Care:
     - Provide the official customer care number returned by the tool.
     ### ❓ Local Service
     - Ask: "Would you like us to provide local service? If you’d like a technician to come and look at your [Appliance Model], just let me know and we’ll find the best local repair provider for you."
#### STAGE 3: Local Service Offer Confirmation (User says Yes):
- If the user agrees to local service:
  1. Call `search_services(category)` to retrieve verified local providers.
  2. Call `get_provider_details` for top candidate providers.
  3. Format your response with:
     ### 📅 Local Service Technicians:
     - Present the candidate technicians in a clear, well-formatted Markdown table:
       | Provider | Rating | Price Range | Contact | Services & Specialization |
       |:---|:---|:---|:---|:---|
       | [Provider Name] | ★ [Rating] | [Price Range] | [Phone] | [Services / Specialization] |
     - Prompt them to choose their preferred provider and time slot to book.

#### STAGE 4: Booking & Confirmation:
- When the user confirms a provider and time slot:
  - Call `schedule_appointment` and generate the Official Confirmation Receipt.

### 🧾 APPOINTMENT CONFIRMATION RECEIPT PROTOCOL:
When an appointment is booked (via schedule_appointment), you MUST present the official confirmation receipt with all of these fields clearly listed:

### 🧾 Appointment Confirmation Receipt:
- **Receipt Reference:** #APPT-[appointment_id]
- **Customer Name:** [Customer Name]
- **Service Provider:** [Provider Name]
- **Provider's Phone No:** [Provider's Phone Number]
- **Service Issue / Problem:** [Problem description]
- **Scheduled Date:** [Date]
- **Time Slot:** [Time Slot e.g. 10:00 AM]
- **Booking Status:** Confirmed

Mention that if they need to cancel or modify, they can click the **[Cancel Appointment]** button on their receipt card or type "Cancel appointment #[ID]".

### CONFIRMATION SAFEGUARD (CRITICAL - STEP 20):
- NEVER call `schedule_appointment` automatically!
- ONLY call `schedule_appointment` AFTER the user explicitly confirms (e.g., 'Yes', 'Book CoolCare at 10:00', 'Go ahead').

### ERROR HANDLING (STEP 26):
- If service category is unsupported: "Sorry, this service category isn't currently supported."
- If no providers found: "No providers found for this service."
- If no slots available: "No slots available tomorrow. Would you like to check another date?"
- If external web search fails: "External provider search is temporarily unavailable."
"""

# Global turn activities accumulator
_current_turn_activities: List[Dict[str, str]] = []
_current_turn_providers: List[Dict[str, Any]] = []
_current_turn_receipt: Optional[Dict[str, Any]] = None


def record_activity(tool_name: str, summary: str) -> None:
    """Record a tool activity for live MCP visualization (STEP 23)."""
    _current_turn_activities.append({
        "tool": tool_name,
        "summary": summary,
        "status": "completed",
    })


# ----------------------------------------------------------------------------
# MCP Client Tool Wrappers (invoking MCP Server over stdio)
# ----------------------------------------------------------------------------


def tool_analyze_problem(problem: str) -> Dict[str, Any]:
    """Analyze the user's issue and return category, issue summary, causes, and manual checks via MCP Client."""
    res = mcp_client.execute_tool_sync("analyze_problem", {"problem": problem})
    if isinstance(res, dict):
        cat = res.get("category", "Unknown")
        issue = res.get("issue", "detected problem")
        record_activity("analyze_problem", f"Identified: {cat} (Issue: {issue})")
        return res
    return {"category": "Unknown", "issue": "detected problem", "confidence": 0}


def tool_search_services(service_category: str) -> List[Dict[str, Any]]:
    """Search service providers by category from SQLite via MCP Client."""
    res = mcp_client.execute_tool_sync("search_services", {"service_category": service_category})
    global _current_turn_providers

    if isinstance(res, list):
        valid_providers = [p for p in res if isinstance(p, dict) and "name" in p]
        _current_turn_providers = valid_providers
        record_activity("search_services", f"Found: {len(valid_providers)} providers for '{service_category}'")
        return res
    elif isinstance(res, dict):
        record_activity("search_services", f"Status: {res.get('message', 'Queried providers')}")
        return [res]
    return []


def tool_get_provider_details(provider_id: int) -> Dict[str, Any]:
    """Get full details (name, service, rating, location, price_range, phone, score) for a provider by ID via MCP Client."""
    res = mcp_client.execute_tool_sync("get_provider_details", {"provider_id": int(provider_id)})
    if isinstance(res, dict) and "name" in res:
        record_activity("get_provider_details", f"Selected: {res.get('name')} (Rating: {res.get('rating', '4.5')} ★)")
        return res
    return {"error": f"Provider with ID {provider_id} not found."}


def tool_check_availability(provider_id: int, date: str) -> Dict[str, Any]:
    """Check available time slots for a provider on a specific date (YYYY-MM-DD) via MCP Client."""
    res = mcp_client.execute_tool_sync("check_availability", {"provider_id": int(provider_id), "date": str(date)})
    if isinstance(res, dict):
        slots = res.get("available_slots", [])
        prov = res.get("provider", f"Provider #{provider_id}")
        record_activity("check_availability", f"Found: {len(slots)} slots for {prov} on {date}")
        return res
    return {"error": "Failed to check availability."}


def tool_schedule_appointment(
    provider_id: int,
    date: str,
    time: str,
    customer_name: str,
    service_id: int = 1,
    problem: str = "",
) -> Dict[str, Any]:
    """Book an appointment in SQLite via MCP Client after explicit user confirmation."""
    global _current_turn_receipt
    res = mcp_client.execute_tool_sync(
        "schedule_appointment",
        {
            "provider_id": int(provider_id),
            "date": str(date),
            "time": str(time),
            "customer_name": str(customer_name),
            "service_id": int(service_id),
            "problem": str(problem),
        },
    )
    if isinstance(res, dict) and res.get("success"):
        _current_turn_receipt = {
            "appointment_id": res.get("appointment_id"),
            "customer_name": res.get("customer_name", customer_name),
            "provider": res.get("provider"),
            "provider_phone": res.get("provider_phone", "+91 98765 43210"),
            "problem": res.get("problem", problem or "Appliance repair"),
            "issue": res.get("issue", problem or "Appliance repair"),
            "date": res.get("date", date),
            "time_slot": res.get("time_slot", time),
            "status": "confirmed",
        }
        record_activity(
            "schedule_appointment",
            f"Confirmed: Appointment #{res.get('appointment_id')} for {res.get('customer_name', customer_name)} with {res.get('provider')} on {date} at {time}",
        )
    elif isinstance(res, dict):
        record_activity("schedule_appointment", f"Notice: {res.get('message', 'Booking failed')}")
    return res


def tool_search_external_providers(service: str, location: str = "Goa") -> List[Dict[str, Any]]:
    """Search the web for external service providers via Tavily API on MCP Server via MCP Client."""
    res = mcp_client.execute_tool_sync(
        "search_external_providers",
        {"service": str(service), "location": str(location)},
    )
    if isinstance(res, list):
        record_activity(
            "search_external_providers",
            f"Found: {len(res)} external web listings via Tavily for '{service}' in {location}",
        )
        return res
    elif isinstance(res, dict):
        record_activity("search_external_providers", f"Notice: {res.get('message', 'Search finished')}")
        return [res]
    return []


def tool_cancel_appointment(appointment_id: int, reason: str = "Customer request") -> Dict[str, Any]:
    """Cancel an appointment in SQLite by appointment ID via MCP Client."""
    res = mcp_client.execute_tool_sync(
        "cancel_appointment",
        {"appointment_id": int(appointment_id), "reason": str(reason)},
    )
    record_activity("cancel_appointment", f"Cancelled: Appointment #{appointment_id} (Reason: {reason})")
    return res


def tool_lookup_appliance_error_code(brand: str, model_or_error: str, appliance_type: str = "appliance") -> Dict[str, Any]:
    """Look up official manufacturer diagnostic error codes and manual solutions via Tavily."""
    res = mcp_client.execute_tool_sync(
        "lookup_appliance_error_code",
        {"brand": str(brand), "model_or_error": str(model_or_error), "appliance_type": str(appliance_type)},
    )
    record_activity("lookup_appliance_error_code", f"Diagnostic Manual: Looked up {brand} error '{model_or_error}' via Tavily")
    return res if isinstance(res, dict) else {"status": "error", "message": "Lookup failed"}


def tool_verify_part_pricing(appliance: str, part_name: str, quoted_price: Optional[float] = None) -> Dict[str, Any]:
    """Verify live fair-market repair and spare parts pricing to protect customers against overcharging."""
    params = {"appliance": str(appliance), "part_name": str(part_name)}
    if quoted_price is not None:
        params["quoted_price"] = float(quoted_price)
    res = mcp_client.execute_tool_sync("verify_part_pricing", params)
    record_activity("verify_part_pricing", f"Price Audit: Verified fair market rate for {appliance} {part_name}")
    return res if isinstance(res, dict) else {"status": "error", "message": "Price verification failed"}


# Mapping for tool execution by name
TOOL_MAP = {
    "analyze_problem": tool_analyze_problem,
    "search_services": tool_search_services,
    "get_provider_details": tool_get_provider_details,
    "check_availability": tool_check_availability,
    "schedule_appointment": tool_schedule_appointment,
    "search_external_providers": tool_search_external_providers,
    "cancel_appointment": tool_cancel_appointment,
    "lookup_appliance_error_code": tool_lookup_appliance_error_code,
    "verify_part_pricing": tool_verify_part_pricing,
}

# Python functions list for Gemini automatic function calling
AGENT_TOOLS = [
    tool_analyze_problem,
    tool_search_services,
    tool_get_provider_details,
    tool_check_availability,
    tool_schedule_appointment,
    tool_search_external_providers,
    tool_cancel_appointment,
    tool_lookup_appliance_error_code,
    tool_verify_part_pricing,
]

# JSON schema definitions for Groq OpenAI-compatible tool calling
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_problem",
            "description": "Analyze the user's issue and return category, issue summary, causes, and manual DIY checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {
                        "type": "string",
                        "description": "The user's reported issue or description of the problem",
                    }
                },
                "required": ["problem"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_services",
            "description": "Search service providers by category from SQLite via MCP Client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_category": {
                        "type": "string",
                        "description": "The category of service, e.g. 'AC Repair', 'Washing Machine Repair', 'Laptop Repair', 'Plumbing'",
                    }
                },
                "required": ["service_category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_provider_details",
            "description": "Get full details (name, service, rating, location, price_range, phone, composite score) for a provider by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "integer",
                        "description": "The unique integer ID of the provider",
                    }
                },
                "required": ["provider_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available time slots for a provider on a specific date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "integer",
                        "description": "The unique integer ID of the provider",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g. 2026-09-17)",
                    },
                },
                "required": ["provider_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_appointment",
            "description": "Book an appointment in SQLite after explicit user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_id": {
                        "type": "integer",
                        "description": "The unique integer ID of the provider",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Time slot, e.g. '10:00 AM' or '02:00 PM'",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Name of the customer",
                    },
                    "service_id": {
                        "type": "integer",
                        "description": "ID of the service (default 1)",
                    },
                    "problem": {
                        "type": "string",
                        "description": "Description of the problem",
                    },
                },
                "required": ["provider_id", "date", "time", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an appointment in SQLite by appointment ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "The appointment ID to cancel",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancelling the appointment (e.g. 'Issue resolved myself', 'Found another provider')",
                    },
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_external_providers",
            "description": "Search the web for external service providers via Tavily API on MCP Server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "The service name to search for",
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional location to search in (e.g. city or region)",
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_appliance_error_code",
            "description": "Look up official manufacturer diagnostic error codes (e.g. Whirlpool F02, Daikin 5 blinks, Samsung 4C) and repair steps from live service manuals via Tavily.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {
                        "type": "string",
                        "description": "Brand of appliance, e.g. 'Whirlpool', 'Daikin', 'Samsung', 'LG', 'Voltas'",
                    },
                    "model_or_error": {
                        "type": "string",
                        "description": "The specific error code or fault blink count, e.g. 'F02', '5 blinks', '4C', 'OE'",
                    },
                    "appliance_type": {
                        "type": "string",
                        "description": "Type of appliance, e.g. 'Washing Machine', 'AC', 'Refrigerator'",
                    },
                },
                "required": ["brand", "model_or_error"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_part_pricing",
            "description": "Verify fair-market spare parts and labor repair costs in India to protect consumers against inflated repair bills.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appliance": {
                        "type": "string",
                        "description": "Appliance or service type, e.g. 'AC', 'Washing Machine', 'Laptop', 'Plumbing'",
                    },
                    "part_name": {
                        "type": "string",
                        "description": "Name of the component/service, e.g. 'Capacitor', 'Drain pump', 'Gas refill', 'Battery'",
                    },
                    "quoted_price": {
                        "type": "number",
                        "description": "The price in INR quoted to the customer to evaluate if fair or overpriced",
                    },
                },
                "required": ["appliance", "part_name"],
            },
        },
    },
]


class ServiceAssistantAgent:
    """Manages multi-turn conversation sessions with Gemini LLM and seamless in-place Groq fallback connected to MCP tools."""

    def __init__(
        self,
        gemini_model_name: str = "gemini-2.5-flash",
        groq_model_name: str = "openai/gpt-oss-20b",
    ):
        self.gemini_model_name = gemini_model_name
        self.groq_model_name = groq_model_name
        self.active_backend = "gemini" if GEMINI_API_KEY else "groq"
        self.fallback_triggered = False

        # Gemini session tracking
        self.gemini_sessions: Dict[str, Any] = {}
        self.gemini_model: Optional[Any] = None

        if GEMINI_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel(
                    model_name=self.gemini_model_name,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=AGENT_TOOLS,
                )
            except Exception as e:
                logger.warning(f"Could not initialize {self.gemini_model_name}, trying gemini-flash-latest: {e}")
                try:
                    self.gemini_model_name = "gemini-flash-latest"
                    self.gemini_model = genai.GenerativeModel(
                        model_name=self.gemini_model_name,
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=AGENT_TOOLS,
                    )
                except Exception as inner_e:
                    logger.error(f"Gemini initialization failed completely: {inner_e}")
                    self.gemini_model = None
                    self.active_backend = "groq"

        # Groq client initialization
        self.groq_client: Optional[Any] = None
        if Groq and GROQ_API_KEY:
            try:
                self.groq_client = Groq(api_key=GROQ_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")

        # Groq session tracking: conv_id -> list of message dicts
        self.groq_sessions: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def model_name(self) -> str:
        """Return the current active model identifier for status reporting."""
        if self.active_backend == "groq":
            return f"Groq ({self.groq_model_name})"
        return f"Gemini ({self.gemini_model_name})"

    def get_or_create_gemini_chat(self, conversation_id: str) -> Any:
        """Retrieve existing Gemini chat session or create a new one."""
        if conversation_id not in self.gemini_sessions:
            if not self.gemini_model:
                raise RuntimeError("Gemini model is not initialized.")
            chat = self.gemini_model.start_chat(enable_automatic_function_calling=True)
            self.gemini_sessions[conversation_id] = chat
        return self.gemini_sessions[conversation_id]

    def get_or_create_groq_session(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieve existing Groq messages list or initialize a new one with system prompt."""
        if conversation_id not in self.groq_sessions:
            self.groq_sessions[conversation_id] = [
                {"role": "system", "content": SYSTEM_INSTRUCTION}
            ]
        return self.groq_sessions[conversation_id]

    def _is_gemini_tier_expired(self, error: Exception) -> bool:
        """Detect if an exception is caused by Gemini tier expiry, quota exhaustion, or rate limiting."""
        err_str = str(error).lower()
        tier_signals = [
            "resourceexhausted",
            "429",
            "quota",
            "tier",
            "billing",
            "permissiondenied",
            "rate limit",
            "exhausted",
            "limit exceeded",
            "serviceunavailable",
            "503",
        ]
        return any(signal in err_str for signal in tier_signals)

    async def _chat_with_gemini(self, message: str, conv_id: str) -> str:
        """Execute chat turn using Gemini LLM."""
        chat = self.get_or_create_gemini_chat(conv_id)
        response = chat.send_message(message)
        
        reply = ""
        try:
            reply = response.text or ""
        except Exception as text_err:
            logger.warning(f"Could not directly access response.text: {text_err}. Parsing candidate parts...")
            try:
                if response.candidates:
                    parts = response.candidates[0].content.parts
                    reply = "\n".join(p.text for p in parts if hasattr(p, "text") and p.text)
            except Exception as cand_err:
                logger.warning(f"Could not parse candidate parts: {cand_err}")
                reply = ""

        # Mirror turn in Groq session to keep context synchronized in case fallback occurs later
        groq_msgs = self.get_or_create_groq_session(conv_id)
        groq_msgs.append({"role": "user", "content": message})
        if reply:
            groq_msgs.append({"role": "assistant", "content": reply})

        return reply

    async def _chat_with_groq(self, message: str, conv_id: str) -> str:
        """Execute chat turn using Groq LLM with OpenAI-compatible tool calling over MCP."""
        if not self.groq_client:
            raise RuntimeError("Groq client is not configured or GROQ_API_KEY is missing.")

        groq_msgs = self.get_or_create_groq_session(conv_id)
        groq_msgs.append({"role": "user", "content": message})

        max_rounds = 6
        final_text = ""

        for round_idx in range(max_rounds):
            try:
                resp = self.groq_client.chat.completions.create(
                    model=self.groq_model_name,
                    messages=groq_msgs,
                    tools=GROQ_TOOLS,
                    tool_choice="auto",
                    temperature=0.2,
                )
            except Exception as e:
                # If primary groq model encounters error, try secondary fallback model
                logger.warning(f"Groq {self.groq_model_name} failed: {e}. Trying openai/gpt-oss-20b...")
                try:
                    resp = self.groq_client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=groq_msgs,
                        tools=GROQ_TOOLS,
                        tool_choice="auto",
                        temperature=0.2,
                    )
                except Exception as inner_e:
                    raise RuntimeError(f"Groq API error: {inner_e}") from e

            choice = resp.choices[0]
            msg = choice.message

            if msg.tool_calls:
                # Append assistant tool call request to history
                groq_msgs.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # Execute requested tools via MCP Client
                for tc in msg.tool_calls:
                    fname = tc.function.name
                    try:
                        args = (
                            json.loads(tc.function.arguments)
                            if isinstance(tc.function.arguments, str)
                            else (tc.function.arguments or {})
                        )
                    except Exception:
                        args = {}

                    tool_fn = TOOL_MAP.get(fname)
                    if tool_fn:
                        try:
                            result = tool_fn(**args)
                        except Exception as tool_err:
                            result = {"error": f"Tool execution failed: {str(tool_err)}"}
                    else:
                        result = {"error": f"Tool '{fname}' is not implemented"}

                    # Append tool result back into message history
                    groq_msgs.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fname,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            else:
                final_text = msg.content or ""
                groq_msgs.append({"role": "assistant", "content": final_text})
                break

        return final_text

    async def chat(self, message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to the agent and receive the AI-generated response, with in-place Groq fallback."""
        global _current_turn_activities, _current_turn_providers, _current_turn_receipt
        _current_turn_activities = []
        _current_turn_providers = []
        _current_turn_receipt = None

        conv_id = conversation_id or str(uuid.uuid4())
        reply_text = ""

        # Check if Groq is already the active backend
        if self.active_backend == "groq" or not self.gemini_model:
            try:
                reply_text = await self._chat_with_groq(message, conv_id)
            except Exception as e:
                reply_text = f"An error occurred with Groq service assistant: {str(e)}"
            return {
                "response": reply_text,
                "conversation_id": conv_id,
                "tool_activities": list(_current_turn_activities),
                "providers": list(_current_turn_providers),
                "receipt": _current_turn_receipt,
                "backend": "groq",
                "model": self.groq_model_name,
            }

        # Attempt turn with Gemini first
        gemini_failed = False
        gemini_err = None

        try:
            reply_text = await self._chat_with_gemini(message, conv_id)
        except Exception as e:
            gemini_failed = True
            gemini_err = e

        if gemini_failed or not reply_text:
            logger.warning(
                f"Gemini issue encountered ({gemini_err or 'Empty response'}). "
                f"Seamlessly switching in-place to Groq ({self.groq_model_name})..."
            )
            self.active_backend = "groq"
            self.fallback_triggered = True

            reason = "Gemini tier expired/quota reached" if (gemini_err and self._is_gemini_tier_expired(gemini_err)) else f"Gemini error: {str(gemini_err or 'Empty response')[:80]}"
            record_activity(
                "llm_fallback",
                f"{reason}. Seamlessly switched in-place to Groq ({self.groq_model_name})",
            )

            # Execute seamlessly via Groq
            try:
                reply_text = await self._chat_with_groq(message, conv_id)
            except Exception as groq_err:
                logger.error(f"Groq fallback also encountered error: {groq_err}")
                # Check if booking was already confirmed
                confirmed = [
                    act for act in _current_turn_activities
                    if act.get("tool") == "schedule_appointment" and "Confirmed" in act.get("summary", "")
                ]
                if confirmed:
                    reply_text = f"Your appointment has been confirmed! {confirmed[0].get('summary')}."
                else:
                    reply_text = (
                        f"Both primary and secondary AI assistants encountered an error: {str(groq_err)}. Please try sending your message again."
                    )

        return {
            "response": reply_text,
            "conversation_id": conv_id,
            "tool_activities": list(_current_turn_activities),
            "providers": list(_current_turn_providers),
            "receipt": _current_turn_receipt,
            "backend": self.active_backend,
            "model": self.groq_model_name if self.active_backend == "groq" else self.gemini_model_name,
        }
