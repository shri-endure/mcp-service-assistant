"""API Endpoint Tests for MCP Service Resolution Assistant.

Tests FastAPI endpoints:
- GET /health
- GET /booked-slots
- POST /book-appointment
- POST /cancel-appointment
- GET / (frontend static files)
"""

import os
import sys
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns 200 and healthy database status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in ["ok", "healthy"]
    assert data.get("database") in ["healthy", "connected"]


def test_booked_slots_endpoint():
    """Verify GET /booked-slots returns map of booked slots per provider."""
    response = client.get("/booked-slots")
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "booked_slots" in data
    assert isinstance(data["booked_slots"], dict)


def test_book_and_cancel_appointment_flow():
    """Verify booking a slot, detecting conflicts, and cancelling the appointment."""
    test_date = "2035-08-20"
    test_slot = "04:00 PM"
    provider_id = 3

    # 1. Book available slot
    book_payload = {
        "provider_id": provider_id,
        "date": test_date,
        "time_slot": test_slot,
        "customer_name": "API Test Customer",
        "customer_phone": "+91 99999 11111",
        "problem": "Leaking kitchen tap",
    }
    book_resp = client.post("/book-appointment", json=book_payload)
    assert book_resp.status_code == 200, f"Booking failed: {book_resp.text}"
    book_data = book_resp.json()
    assert book_data.get("success") is True
    appt_id = book_data.get("appointment_id")
    assert appt_id is not None

    try:
        # 2. Duplicate booking attempt should return 400
        dup_resp = client.post("/book-appointment", json=book_payload)
        assert dup_resp.status_code == 400
        dup_data = dup_resp.json()
        assert "This slot is no longer available." in dup_data.get("detail", "") or "already been booked" in dup_data.get("detail", "")

        # 3. Verify /booked-slots includes the slot
        slots_resp = client.get("/booked-slots")
        assert slots_resp.status_code == 200
        p_slots = slots_resp.json()["booked_slots"].get(str(provider_id), [])
        assert any(test_slot in s for s in p_slots)

    finally:
        # 4. Clean up / cancel appointment
        cancel_resp = client.post("/cancel-appointment", json={"appointment_id": appt_id})
        assert cancel_resp.status_code == 200
        assert cancel_resp.json().get("success") is True


def test_static_files():
    """Verify static assets are served properly."""
    index_resp = client.get("/")
    assert index_resp.status_code == 200
    assert "ResolveMCP" in index_resp.text or "MCP" in index_resp.text

    css_resp = client.get("/style.css")
    assert css_resp.status_code == 200

    js_resp = client.get("/app.js")
    assert js_resp.status_code == 200


def test_technician_portal_and_status_transitions():
    """Verify technician portal page, job retrieval, and status updates."""
    tech_page = client.get("/technician")
    assert tech_page.status_code == 200

    # 2. Get technician jobs
    jobs_resp = client.get("/api/technician/jobs")
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert isinstance(jobs, list)

    # 3. Book a temporary appointment to test status progression
    book_resp = client.post("/book-appointment", json={
        "provider_id": 1,
        "date": "2036-04-10",
        "time_slot": "12:00 PM",
        "customer_name": "Live Dispatch Customer",
        "customer_phone": "+91 98888 77777",
        "problem": "AC noisy vibration",
    })
    assert book_resp.status_code == 200
    appt_id = book_resp.json()["appointment_id"]

    try:
        # 4. Status update: Accept Job
        accept_resp = client.post("/api/technician/update-status", json={
            "appointment_id": appt_id,
            "status": "accepted",
            "technician_name": "Ramesh Naik",
        })
        assert accept_resp.status_code == 200
        assert accept_resp.json()["status"] == "accepted"
        assert accept_resp.json()["technician_name"] == "Ramesh Naik"

        # 5. Status update: En Route
        enroute_resp = client.post("/api/technician/update-status", json={
            "appointment_id": appt_id,
            "status": "en_route",
            "eta_minutes": 12,
        })
        assert enroute_resp.status_code == 200
        assert enroute_resp.json()["status"] == "en_route"
        assert enroute_resp.json()["eta_minutes"] == 12

    finally:
        # Clean up
        client.post("/cancel-appointment", json={"appointment_id": appt_id})


def test_cancellation_reason_and_date_slot_filtering():
    """Verify that booking on a specific date filters slots properly and cancellation records reason."""
    custom_date = "2027-11-15"
    slot = "10:00 AM"
    provider_id = 2

    # 1. Book with specific date
    book_resp = client.post("/book-appointment", json={
        "provider_id": provider_id,
        "date": custom_date,
        "time_slot": slot,
        "customer_name": "Test Date User",
        "customer_phone": "+91 91234 56789",
        "problem": "Washing machine not spinning"
    })
    assert book_resp.status_code == 200
    data = book_resp.json()
    appt_id = data["appointment_id"]

    try:
        # 2. Query booked slots for this date - should be booked
        slots_date_resp = client.get(f"/booked-slots?date={custom_date}")
        assert slots_date_resp.status_code == 200
        p_slots = slots_date_resp.json()["booked_slots"].get(str(provider_id), [])
        assert any(slot in s for s in p_slots)

        # 3. Query booked slots for a different date - should NOT be booked
        slots_other_resp = client.get("/booked-slots?date=2027-11-16")
        assert slots_other_resp.status_code == 200
        other_slots = slots_other_resp.json()["booked_slots"].get(str(provider_id), [])
        assert not any(slot in s for s in other_slots)

        # 4. Cancel appointment with custom reason
        custom_reason = "Schedule conflict: Had to travel for office work"
        cancel_resp = client.post("/cancel-appointment", json={
            "appointment_id": appt_id,
            "reason": custom_reason
        })
        assert cancel_resp.status_code == 200
        c_data = cancel_resp.json()
        assert c_data["success"] is True
        assert c_data["status"] == "cancelled"

        # 5. Check appointments list to verify reason is persisted
        appts_resp = client.get("/appointments")
        assert appts_resp.status_code == 200
        appt = next((a for a in appts_resp.json() if a["id"] == appt_id), None)
        assert appt is not None
        assert appt["status"] == "cancelled"
        assert appt["cancellation_reason"] == custom_reason
    finally:
        pass


if __name__ == "__main__":
    print("Running tests in tests/test_api.py...")
    test_health_endpoint()
    print("[PASS] GET /health")
    test_booked_slots_endpoint()
    print("[PASS] GET /booked-slots")
    test_book_and_cancel_appointment_flow()
    print("[PASS] POST /book-appointment and POST /cancel-appointment flow")
    test_cancellation_reason_and_date_slot_filtering()
    print("[PASS] Date slot filtering and cancellation reason persistence")
    test_static_files()
    print("[PASS] Static frontend file serving")
    test_technician_portal_and_status_transitions()
    print("[PASS] Technician Live Portal & Status Update API")
    print("\nALL tests in tests/test_api.py passed successfully!")

