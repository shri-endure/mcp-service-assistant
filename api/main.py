"""FastAPI application for MCP Service Resolution Assistant."""

import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from client.ai_agent import ServiceAssistantAgent
from database.database import get_connection, init_db

# Initialize database
init_db()

# Initialize FastAPI app
app = FastAPI(
    title="MCP Service Resolution Assistant API",
    description="FastAPI interface connecting users to the Gemini AI Agent and MCP Server",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Connection Manager for live WebSockets across Customer & Technician portals
class ConnectionManager:
    """Manages active WebSockets for real-time customer and technician updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all active WebSocket clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()

# Shared AI Agent instance
agent = ServiceAssistantAgent()


# Request / Response Models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None
    tool_activities: List[Dict[str, Any]] = []
    providers: List[Dict[str, Any]] = []
    receipt: Optional[Dict[str, Any]] = None
    backend: Optional[str] = "gemini"
    model: Optional[str] = None


class CancelRequest(BaseModel):
    appointment_id: int
    reason: Optional[str] = "Customer request"


class BookingRequest(BaseModel):
    provider_id: int
    date: str
    time_slot: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = ""
    customer_address: Optional[str] = ""
    problem: Optional[str] = "Appliance / Service repair"
    service_id: Optional[int] = 1
    conversation_id: Optional[str] = None


class TechnicianStatusUpdate(BaseModel):
    appointment_id: int
    status: str
    technician_name: Optional[str] = "Technician"
    eta_minutes: Optional[int] = 0
    technician_notes: Optional[str] = ""


class TechnicianRegisterRequest(BaseModel):
    name: str
    category: str
    location: str
    phone: str
    rating: Optional[float] = 4.8
    price_min: Optional[int] = 300
    price_max: Optional[int] = 1000
    description: Optional[str] = ""
    email: Optional[str] = ""


class JobMessageRequest(BaseModel):
    sender_type: str
    sender_name: str
    message: str


# WebSocket Live Hub
@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time customer and technician dispatch synchronization."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# API Endpoints


@app.get("/health")
def health() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM providers")
            providers_count = cursor.fetchone()[0]
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
        providers_count = 0

    tavily_key = bool(os.getenv("TAVILY_API_KEY"))
    groq_key = bool(os.getenv("GROQ_API_KEY"))

    return {
        "status": "ok",
        "database": db_status,
        "providers_loaded": providers_count,
        "mcp_server": "active",
        "agent_model": agent.model_name,
        "active_backend": agent.active_backend,
        "groq_fallback": "configured" if groq_key else "not_configured",
        "tavily_search": "configured" if tavily_key else "not_configured",
    }


@app.post("/api/admin/clear-bookings")
async def clear_bookings_endpoint() -> Dict[str, Any]:
    """Preserve all booking data permanently as requested - no deletion."""
    return {
        "success": True,
        "message": "Booking data is permanently recorded and preserved.",
        "cleared_appointments": 0,
        "cleared_messages": 0,
    }



@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Chat endpoint communicating with Gemini LLM (with in-place Groq fallback) and MCP tools."""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        result = await agent.chat(
            message=request.message,
            conversation_id=request.conversation_id,
        )
        return ChatResponse(
            response=result["response"],
            conversation_id=result["conversation_id"],
            tool_activities=result.get("tool_activities", []),
            providers=result.get("providers", []),
            receipt=result.get("receipt"),
            backend=result.get("backend", agent.active_backend),
            model=result.get("model", agent.model_name),
        )
    except Exception as e:
        import logging
        logging.getLogger("mcp_service_assistant").error(f"Chat endpoint unhandled error: {e}", exc_info=True)
        return ChatResponse(
            response=f"I'm sorry, an issue occurred with the assistant: {str(e)}. Please try again.",
            conversation_id=request.conversation_id,
            tool_activities=[],
            providers=[],
            receipt=None,
            backend=agent.active_backend,
            model=agent.model_name,
        )


@app.post("/book-appointment")
async def book_appointment_endpoint(request: BookingRequest) -> Dict[str, Any]:
    """Book a service appointment with complete customer details saved to database."""
    from database.database import schedule_appointment_db
    res = schedule_appointment_db(
        provider_id=request.provider_id,
        date=request.date,
        time=request.time_slot,
        customer_name=request.customer_name,
        service_id=request.service_id or 1,
        problem=request.problem or "Appliance repair",
        customer_phone=request.customer_phone,
        customer_email=request.customer_email or "",
        customer_address=request.customer_address or "",
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Could not book appointment"))

    # Broadcast new job to connected technician portals in real time
    await manager.broadcast({
        "type": "NEW_JOB",
        "data": {
            "appointment_id": res.get("appointment_id"),
            "provider_id": request.provider_id,
            "provider_name": res.get("provider", "Service Provider"),
            "customer_name": request.customer_name,
            "customer_phone": request.customer_phone,
            "customer_address": request.customer_address or "Local Area",
            "date": request.date,
            "time_slot": request.time_slot,
            "problem": request.problem or "Appliance repair",
            "status": "confirmed",
            "created_at": "Just now",
        }
    })
    return res


@app.post("/cancel-appointment")
def cancel_appointment_endpoint(request: CancelRequest) -> Dict[str, Any]:
    """Cancel an appointment endpoint."""
    from database.database import cancel_appointment_db
    res = cancel_appointment_db(request.appointment_id, reason=request.reason or "Customer request")
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Appointment not found"))
    return res



@app.delete("/appointments/{appointment_id}")
def delete_appointment_endpoint(appointment_id: int) -> Dict[str, Any]:
    """Delete / cancel an appointment by ID."""
    from database.database import cancel_appointment_db
    res = cancel_appointment_db(appointment_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Appointment not found"))
    return res


@app.get("/customers")
def list_customers() -> List[Dict[str, Any]]:
    """Retrieve all customers registered in SQLite."""
    from database.database import get_customers_db
    return get_customers_db()


@app.get("/appointments")
def list_appointments() -> List[Dict[str, Any]]:
    """Retrieve all appointments from SQLite with rich customer & status information."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.provider_id, p.name as provider_name, p.phone as provider_phone, p.category,
                   a.customer_id, a.customer_name, a.customer_phone, a.customer_email, a.customer_address,
                   a.date, a.time, COALESCE(a.time_slot, a.time) as time_slot,
                   a.problem, a.problem as issue, a.status, a.cancellation_reason, a.cancelled_at, a.created_at
            FROM appointments a
            LEFT JOIN providers p ON a.provider_id = p.id
            ORDER BY a.id DESC
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


@app.get("/cancel-appointment")
def cancel_appointment_get_endpoint(appointment_id: int, reason: Optional[str] = "Customer request") -> Dict[str, Any]:
    """Cancel an appointment via GET query param."""
    from database.database import cancel_appointment_db
    res = cancel_appointment_db(appointment_id, reason=reason or "Customer request")
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Appointment not found"))
    return res


@app.post("/appointments/{appointment_id}/cancel")
def cancel_appointment_path_endpoint(appointment_id: int, reason: Optional[str] = "Customer request") -> Dict[str, Any]:
    """Cancel an appointment via POST path."""
    from database.database import cancel_appointment_db
    res = cancel_appointment_db(appointment_id, reason=reason or "Customer request")
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Appointment not found"))
    return res


@app.get("/booked-slots")
def get_booked_slots_endpoint(date: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve all currently booked slots grouped by provider ID for real-time client sync."""
    from database.database import normalize_time_slot
    with get_connection() as conn:
        cursor = conn.cursor()
        if date:
            import datetime
            tomorrow_iso = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
            if date.lower() == "tomorrow" or date == tomorrow_iso:
                cursor.execute(
                    """
                    SELECT provider_id, COALESCE(time, time_slot) as slot_time, date
                    FROM appointments
                    WHERE LOWER(status) = 'confirmed' AND (date = ? OR LOWER(date) = 'tomorrow')
                    """,
                    (date,),
                )
            else:
                cursor.execute(
                    """
                    SELECT provider_id, COALESCE(time, time_slot) as slot_time, date
                    FROM appointments
                    WHERE LOWER(status) = 'confirmed' AND date = ?
                    """,
                    (date,),
                )
        else:
            cursor.execute(
                """
                SELECT provider_id, COALESCE(time, time_slot) as slot_time, date
                FROM appointments
                WHERE LOWER(status) = 'confirmed'
                """
            )
        rows = cursor.fetchall()

    booked_by_provider: Dict[str, List[str]] = {}
    for r in rows:
        pid = str(r["provider_id"])
        if pid not in booked_by_provider:
            booked_by_provider[pid] = []
        slot = r["slot_time"]
        if slot and slot not in booked_by_provider[pid]:
            booked_by_provider[pid].append(slot)

    return {
        "success": True,
        "booked_slots": booked_by_provider,
    }



@app.get("/catalog")
def get_catalog() -> Dict[str, Any]:
    """Retrieve live catalog information, categories, provider counts, and registered MCP tools."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT category, COUNT(*) as count FROM providers GROUP BY category ORDER BY category ASC")
        categories = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM providers")
        total_providers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM customers")
        total_customers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM appointments WHERE status = 'confirmed'")
        active_bookings = cursor.fetchone()[0]

    return {
        "stats": {
            "total_providers": total_providers,
            "total_customers": total_customers,
            "active_bookings": active_bookings,
        },
        "categories": categories,
        "tools": [
            {"name": "analyze_problem", "desc": "Keyword & semantic issue categorization", "type": "Diagnostic"},
            {"name": "search_services", "desc": "Provider lookup filtered by rating and location", "type": "Database"},
            {"name": "get_provider_details", "desc": "Detailed pricing, score, and contact", "type": "Database"},
            {"name": "check_availability", "desc": "Verify real-time date/time slot availability", "type": "Availability"},
            {"name": "schedule_appointment", "desc": "Commit booking & create customer record in DB", "type": "Booking"},
            {"name": "cancel_appointment", "desc": "Cancel booking & release slot to availability", "type": "Lifecycle"},
            {"name": "search_external_providers", "desc": "Tavily web API external search fallback", "type": "External API"},
        ],
        "resources": [
            {"uri": "service://categories", "name": "Service Categories", "desc": "AC, Laptop, Plumbing, Washer"},
            {"uri": "service://faqs", "name": "Service Knowledge Base", "desc": "Issue causes and diagnostic steps"},
            {"uri": "service://customers", "name": "Customer Profiles", "desc": "Registered customer records in SQLite"},
        ]
    }


@app.get("/services")
def list_services(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve available service providers from the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute(
                """
                SELECT id, name, category, rating, location, price_min, price_max, phone, email, description
                FROM providers
                WHERE LOWER(category) = LOWER(?)
                ORDER BY id ASC
                """,
                (category.strip(),),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, category, rating, location, price_min, price_max, phone, email, description
                FROM providers
                ORDER BY id ASC
                """
            )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "category": row["category"],
                "rating": row["rating"],
                "location": row["location"],
                "price": f"₹{row['price_min']}–₹{row['price_max']}",
                "price_min": row["price_min"],
                "price_max": row["price_max"],
                "phone": row["phone"],
                "email": row["email"],
                "description": row["description"],
            }
            for row in rows
        ]


# ----------------------------------------------------------------------------
# Technician Live Portal & Job Dispatch Endpoints
# ----------------------------------------------------------------------------


@app.get("/technician")
def get_technician_page():
    """Serve the MCP Technician Live Dispatch portal page."""
    tech_html = os.path.join(PROJECT_ROOT, "frontend", "technician.html")
    if os.path.exists(tech_html):
        return FileResponse(tech_html)
    return FileResponse(os.path.join(PROJECT_ROOT, "frontend", "index.html"))


@app.get("/api/technician/jobs")
def get_technician_jobs_endpoint(provider_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve all jobs/appointments formatted for the technician live dashboard."""
    from database.database import get_technician_jobs_db
    return get_technician_jobs_db(provider_id)


@app.post("/api/technician/register")
def register_technician_endpoint(req: TechnicianRegisterRequest) -> Dict[str, Any]:
    """Register a new service technician into the system."""
    from database.database import register_provider_db
    res = register_provider_db(
        name=req.name,
        category=req.category,
        location=req.location,
        phone=req.phone,
        price_min=req.price_min or 300,
        price_max=req.price_max or 1000,
        description=req.description or "",
        email=req.email or "",
    )
    return {
        "success": True,
        "provider": {
            "id": res["provider_id"],
            "name": res["name"],
            "category": res["category"],
            "location": res["location"],
            "phone": res["phone"],
            "rating": res["rating"],
            "price_range": res["price_range"],
        },
        "message": res["message"],
    }


@app.post("/api/technician/update-status")
async def update_technician_status_endpoint(update: TechnicianStatusUpdate) -> Dict[str, Any]:
    """Update job status across dispatch lifecycle with real-time broadcast."""
    from database.database import update_appointment_status_db
    res = update_appointment_status_db(
        appointment_id=update.appointment_id,
        status=update.status,
        technician_name=update.technician_name or "Technician",
        eta_minutes=update.eta_minutes or 0,
        technician_notes=update.technician_notes or "",
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Update failed"))
    await manager.broadcast({
        "type": "JOB_STATUS_UPDATED",
        "data": res,
    })
    return res


@app.post("/api/appointments/{appointment_id}/messages")
async def post_job_message_endpoint(appointment_id: int, req: JobMessageRequest) -> Dict[str, Any]:
    """Post direct message between customer and technician for a specific appointment."""
    from database.database import add_job_message_db
    res = add_job_message_db(
        appointment_id=appointment_id,
        sender_type=req.sender_type,
        sender_name=req.sender_name,
        message=req.message,
    )
    await manager.broadcast({
        "type": "NEW_JOB_MESSAGE",
        "data": res,
    })
    return res


@app.get("/api/appointments/{appointment_id}/messages")
def get_job_messages_endpoint(appointment_id: int) -> Dict[str, Any]:
    """Retrieve all direct chat messages for a specific appointment."""
    from database.database import get_job_messages_db
    msgs = get_job_messages_db(appointment_id)
    return {"messages": msgs}


# Mount frontend static directory if exists
frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
