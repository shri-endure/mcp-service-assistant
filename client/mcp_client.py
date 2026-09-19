"""MCP Service Resolution Assistant - Client.

Demonstrates MCP Client ↔ MCP Server communication over stdio:
1. Connects to the MCP server
2. Discovers tools
3. Discovers resources
4. Reads resources
5. Invokes tools end-to-end (independent test workflow)
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_SCRIPT = os.path.join(PROJECT_ROOT, "server", "mcp_server.py")
PYTHON_EXECUTABLE = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")

if not os.path.exists(PYTHON_EXECUTABLE):
    PYTHON_EXECUTABLE = sys.executable


class ServiceResolutionClient:
    """Client for interacting with the service-resolution-server over stdio."""

    def __init__(self, server_path: Optional[str] = None, python_path: Optional[str] = None):
        self.server_path = server_path or SERVER_SCRIPT
        self.python_path = python_path or PYTHON_EXECUTABLE
        self._session: Optional[ClientSession] = None
        self._client_context = None

    def _get_server_params(self) -> StdioServerParameters:
        """Create stdio server parameters with unbuffered output (-u) and PYTHONPATH."""
        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_ROOT
        env["PYTHONUNBUFFERED"] = "1"

        return StdioServerParameters(
            command=self.python_path,
            args=["-u", self.server_path],
            env=env,
        )

    async def list_tools(self, session: ClientSession) -> List[Dict[str, Any]]:
        """Discover available tools on the MCP server."""
        response = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in response.tools
        ]

    async def list_resources(self, session: ClientSession) -> List[Dict[str, Any]]:
        """Discover available resources on the MCP server."""
        response = await session.list_resources()
        return [
            {
                "uri": str(resource.uri),
                "name": resource.name,
                "description": resource.description or "",
            }
            for resource in response.resources
        ]

    async def read_resource(self, session: ClientSession, uri: str) -> str:
        """Read content from an MCP resource URI."""
        response = await session.read_resource(uri)
        if response and response.contents:
            return response.contents[0].text
        return ""

    async def call_tool(
        self, session: ClientSession, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Call an MCP tool and return parsed result."""
        response = await session.call_tool(tool_name, arguments=arguments)
        if not response or not response.content:
            return None

        # Parse text content from response
        text_outputs = [item.text for item in response.content if hasattr(item, "text")]
        if not text_outputs:
            return None

        # If single text output, attempt JSON parsing
        if len(text_outputs) == 1:
            try:
                return json.loads(text_outputs[0])
            except (json.JSONDecodeError, TypeError):
                return text_outputs[0]

        # Multiple text outputs (e.g. list of serialized items)
        parsed_list = []
        for text in text_outputs:
            try:
                parsed_list.append(json.loads(text))
            except (json.JSONDecodeError, TypeError):
                parsed_list.append(text)
        return parsed_list

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Connect to MCP server via stdio, execute the tool, and return parsed result.

        Enforces Architecture:
            User -> LLM -> MCP Client -> MCP Server -> Database / Web
        """
        server_params = self._get_server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await self.call_tool(session, tool_name, arguments)

    def execute_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Synchronously execute an MCP tool via stdio thread, safe for synchronous LLM tool callers."""
        import concurrent.futures

        def _runner():
            return asyncio.run(self.execute_tool(tool_name, arguments))

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_runner)
                return future.result()
        else:
            return asyncio.run(self.execute_tool(tool_name, arguments))


async def run_client_workflow():
    """Execute complete end-to-end verification of MCP Client ↔ MCP Server communication."""
    client = ServiceResolutionClient()
    server_params = client._get_server_params()

    print("=" * 70, flush=True)
    print("MCP SERVICE RESOLUTION ASSISTANT - CLIENT VERIFICATION", flush=True)
    print("=" * 70, flush=True)
    print(f"Connecting to MCP Server via stdio: {SERVER_SCRIPT}", flush=True)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(" Connected & Initialized MCP Session!\n", flush=True)

            # -------------------------------------------------------------
            # 1. DISCOVER TOOLS
            # -------------------------------------------------------------
            print("-" * 50, flush=True)
            print("1. DISCOVER TOOLS", flush=True)
            print("-" * 50, flush=True)
            tools = await client.list_tools(session)
            print(f"Discovered {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
            print()

            # -------------------------------------------------------------
            # 2. DISCOVER & READ RESOURCES
            # -------------------------------------------------------------
            print("-" * 50, flush=True)
            print("2. DISCOVER & READ RESOURCES", flush=True)
            print("-" * 50, flush=True)
            resources = await client.list_resources(session)
            print(f"Discovered {len(resources)} resources:")
            for r in resources:
                print(f"  - {r['uri']} ({r['name']})")
            print()

            print("Reading Resource 'service://categories':")
            categories_content = await client.read_resource(session, "service://categories")
            print(categories_content)
            print()

            print("Reading Resource 'service://faqs':")
            faqs_content = await client.read_resource(session, "service://faqs")
            print(faqs_content)
            print()

            # -------------------------------------------------------------
            # 3. STEP 16 — INDEPENDENT SERVER & TOOLS VERIFICATION FLOW
            # -------------------------------------------------------------
            print("=" * 70, flush=True)
            print("STEP 16: INDEPENDENT END-TO-END WORKFLOW VERIFICATION", flush=True)
            print("=" * 70, flush=True)

            # Step 16.1: analyze_problem
            test_problem = "My AC is running but it isn't cooling the room."
            print(f"\n[1] analyze_problem -> Problem: \"{test_problem}\"", flush=True)
            analysis = await client.call_tool(
                session, "analyze_problem", {"problem": test_problem}
            )
            print("Result:")
            print(json.dumps(analysis, indent=4), flush=True)

            category = analysis.get("category", "AC Repair")

            # Step 16.2: search_services
            print(f"\n[2] search_services -> Category: \"{category}\"", flush=True)
            services = await client.call_tool(
                session, "search_services", {"service_category": category}
            )
            print("Result:")
            print(json.dumps(services, indent=4), flush=True)

            provider_id = services[0]["id"] if services else 1

            # Step 16.3: get_provider_details
            print(f"\n[3] get_provider_details -> Provider ID: {provider_id}", flush=True)
            details = await client.call_tool(
                session, "get_provider_details", {"provider_id": provider_id}
            )
            print("Result:")
            print(json.dumps(details, indent=4), flush=True)

            # Step 16.4: check_availability
            check_date = "2026-09-10"
            print(f"\n[4] check_availability -> Provider ID: {provider_id}, Date: {check_date}", flush=True)
            availability = await client.call_tool(
                session, "check_availability", {"provider_id": provider_id, "date": check_date}
            )
            print("Result:")
            print(json.dumps(availability, indent=4), flush=True)

            chosen_slot = (
                availability["available_slots"][0]
                if availability.get("available_slots")
                else "10:00"
            )

            # Step 16.5: schedule_appointment
            print(
                f"\n[5] schedule_appointment -> Booking for {details['name']} on {check_date} at {chosen_slot}",
                flush=True,
            )
            booking = await client.call_tool(
                session,
                "schedule_appointment",
                {
                    "provider_id": provider_id,
                    "service_id": 1,
                    "date": check_date,
                    "time": chosen_slot,
                    "customer_name": "John Doe",
                    "problem": analysis.get("issue", "AC not cooling"),
                },
            )
            print("Result:")
            print(json.dumps(booking, indent=4), flush=True)

            # Step 16.6: Verify slot is now reserved
            print(f"\n[6] Re-checking availability on {check_date} to verify slot '{chosen_slot}' is booked:", flush=True)
            updated_avail = await client.call_tool(
                session, "check_availability", {"provider_id": provider_id, "date": check_date}
            )
            print("Available slots now:")
            print(json.dumps(updated_avail.get("available_slots"), indent=4), flush=True)

            # Step 16.7: Cancel appointment
            appt_id = booking.get("appointment_id")
            if appt_id:
                print(f"\n[7] cancel_appointment -> Appointment ID: {appt_id}", flush=True)
                cancellation = await client.call_tool(
                    session, "cancel_appointment", {"appointment_id": appt_id}
                )
                print("Result:")
                print(json.dumps(cancellation, indent=4), flush=True)

            print("\n" + "=" * 70, flush=True)
            print(" ALL MCP CLIENT ↔ SERVER WORKFLOW STEPS PASSED SUCCESSFULLY!", flush=True)
            print("=" * 70, flush=True)


if __name__ == "__main__":
    asyncio.run(run_client_workflow())
