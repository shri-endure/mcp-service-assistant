"""Unit and Integration Tests for MCP Server Tools.

Tests all modular tools:
1. problem_analyzer (analyze_problem)
2. service_search (search_services, search_external_providers)
3. provider_details (get_provider_details)
4. availability (check_availability)
5. appointment (schedule_appointment)
6. cancellation (cancel_appointment)

Also covers STEP 26 error handling specs and STEP 27 test scenarios.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from database.database import get_connection, init_db
from server.tools import (
    analyze_problem,
    cancel_appointment,
    check_availability,
    get_provider_details,
    schedule_appointment,
    search_external_providers,
    search_services,
)


def test_scenario_1_ac_cooling():
    """Scenario 1: 'My AC is not cooling.' -> AC Repair"""
    res = analyze_problem("My AC is not cooling.")
    assert res["category"] == "AC Repair", f"Expected 'AC Repair', got {res['category']}"
    assert res["confidence"] > 0.8
    assert "causes" in res and len(res["causes"]) > 0


def test_scenario_2_laptop_overheating():
    """Scenario 2: 'My laptop is overheating.' -> Laptop Repair"""
    res = analyze_problem("My laptop is overheating.")
    assert res["category"] == "Laptop Repair", f"Expected 'Laptop Repair', got {res['category']}"
    assert res["confidence"] > 0.8
    assert "manual_checks" in res


def test_scenario_3_bathroom_leak():
    """Scenario 3: 'Water is leaking from my bathroom.' -> Plumbing"""
    res = analyze_problem("Water is leaking from my bathroom.")
    assert res["category"] == "Plumbing", f"Expected 'Plumbing', got {res['category']}"


def test_scenario_4_washing_machine_technician():
    """Scenario 4: 'Find me a washing machine technician.' -> Washing Machine Repair"""
    res = analyze_problem("Find me a washing machine technician.")
    assert res["category"] == "Washing Machine Repair", f"Expected 'Washing Machine Repair', got {res['category']}"


def test_scenario_5_end_to_end_pipeline():
    """Scenario 5: 'My AC isn't cooling. Find someone tomorrow.' (Analyze -> Search -> Details -> Availability)"""
    # 1. Analyze
    analysis = analyze_problem("My AC isn't cooling. Find someone tomorrow.")
    assert analysis["category"] == "AC Repair"

    # 2. Search
    providers = search_services(analysis["category"])
    assert len(providers) > 0, "Expected at least one provider for AC Repair"
    top_provider = providers[0]

    # 3. Details
    details = get_provider_details(top_provider["id"])
    assert details["id"] == top_provider["id"]
    assert "name" in details

    # 4. Availability
    avail = check_availability(top_provider["id"], "Tomorrow")
    assert "available_slots" in avail


def test_scenario_6_and_7_booking_and_cancellation():
    """Scenario 6: schedule_appointment & Scenario 7: cancel_appointment"""
    # Book a test appointment
    book_res = schedule_appointment(
        provider_id=1,
        date="2030-01-15",
        time="02:00 PM",
        customer_name="Test Checklist User",
        customer_phone="+91 98765 43210",
        problem="AC maintenance checklist test",
    )
    assert book_res["success"] is True, f"Booking failed: {book_res}"
    appt_id = book_res["appointment_id"]

    # Cancel the appointment
    cancel_res = cancel_appointment(appt_id)
    assert cancel_res["success"] is True, f"Cancellation failed: {cancel_res}"
    assert cancel_res["status"] == "cancelled"


def test_error_invalid_service():
    """STEP 26: Invalid service category handling"""
    res = analyze_problem("I need to fix my broken vintage clock")
    assert res["category"] == "Unknown"
    assert "Sorry, this service category isn't currently supported." in res.get("message", "")

    search_res = search_services("Carpentry")
    assert any("Sorry, this service category isn't currently supported." in item.get("message", "") for item in search_res)


def test_error_no_availability():
    """STEP 26: No availability handling when all slots are taken"""
    test_date = "2031-12-31"
    slots = ["10:00 AM", "12:00 PM", "02:00 PM", "04:00 PM"]
    created_ids = []
    with get_connection() as conn:
        cur = conn.cursor()
        for s in slots:
            cur.execute(
                """
                INSERT INTO appointments (provider_id, service_id, date, time, time_slot, status, customer_name, customer_phone)
                VALUES (4, 1, ?, ?, ?, 'confirmed', 'Busy Slot', '+91 99999 99999')
                """,
                (test_date, s, s)
            )
            created_ids.append(cur.lastrowid)
        conn.commit()

    try:
        avail_res = check_availability(4, test_date)
        assert len(avail_res.get("available_slots", [])) == 0
        assert "No slots available tomorrow. Would you like to check another date?" in avail_res.get("message", "")
    finally:
        with get_connection() as conn:
            cur = conn.cursor()
            for aid in created_ids:
                cur.execute("DELETE FROM appointments WHERE id = ?", (aid,))
            conn.commit()


def test_error_invalid_appointment():
    """STEP 26: Invalid appointment (slot no longer available)"""
    # Book a slot first
    first_book = schedule_appointment(
        provider_id=2,
        date="2032-05-20",
        time="10:00 AM",
        customer_name="First Booker",
        customer_phone="+91 91111 22222",
    )
    assert first_book["success"] is True

    try:
        # Second user attempts to book the identical slot
        second_book = schedule_appointment(
            provider_id=2,
            date="2032-05-20",
            time="10:00 AM",
            customer_name="Second Booker",
            customer_phone="+91 93333 44444",
        )
        assert second_book["success"] is False
        assert "This slot is no longer available." in second_book.get("message", "")
    finally:
        cancel_appointment(first_book["appointment_id"])


def test_error_external_api_failure():
    """STEP 26: External API failure when Tavily is unavailable"""
    old_key = os.environ.get("TAVILY_API_KEY")
    try:
        os.environ.pop("TAVILY_API_KEY", None)
        res = search_external_providers("AC Repair", "Goa")
        assert any("External provider search is temporarily unavailable." in item.get("message", "") for item in res)
    finally:
        if old_key:
            os.environ["TAVILY_API_KEY"] = old_key


def test_lookup_appliance_error_code():
    """Test Tavily AI Manufacturer Service Manual & Error Code Engine."""
    from server.tools import lookup_appliance_error_code

    # Whirlpool F02 Long Drain
    res_whirlpool = lookup_appliance_error_code("Whirlpool", "F02", "Washing Machine")
    assert res_whirlpool["status"] in ["found", "found_fallback"]
    assert "F02" in res_whirlpool["error_code"]
    assert "Long Drain" in res_whirlpool["title"] or "Drain" in res_whirlpool["meaning"]
    assert len(res_whirlpool.get("probable_causes", [])) > 0
    assert len(res_whirlpool.get("diy_steps", [])) > 0

    # Daikin 5 blinks
    res_daikin = lookup_appliance_error_code("Daikin", "5 blinks", "AC")
    assert res_daikin["status"] in ["found", "found_fallback"]
    assert "fan" in str(res_daikin).lower() or "motor" in str(res_daikin).lower()


def test_verify_part_pricing():
    """Test Tavily AI Fair-Market Pricing & Anti-Fraud Checker."""
    from server.tools import verify_part_pricing

    # AC Capacitor Fair Price check
    res_fair = verify_part_pricing("AC", "Capacitor", quoted_price=850)
    assert res_fair["status"] == "success"
    assert res_fair["verdict"] == "Fair Market Price"
    assert res_fair["verdict_badge"] == "success"

    # AC Capacitor Overpriced check
    res_high = verify_part_pricing("AC", "Capacitor", quoted_price=2200)
    assert res_high["status"] == "success"
    assert "Overpriced" in res_high["verdict"]
    assert res_high["verdict_badge"] == "danger"


def test_search_external_providers_real_location_and_db_persistence():
    """Verify that search_external_providers creates valid SQLite providers with IDs and supports booking."""
    from server.tools import search_external_providers, get_provider_details, schedule_appointment, cancel_appointment
    res = search_external_providers("AC Repair", "Bandra, Mumbai")
    assert isinstance(res, list)
    assert len(res) > 0
    p = res[0]
    assert "id" in p
    assert p["id"] > 0
    assert "Bandra" in p["location"] or "Mumbai" in p["location"]

    # Verify get_provider_details retrieves this discovered provider from SQLite
    details = get_provider_details(p["id"])
    assert details is not None
    assert details["name"] == p["name"]

    # Test booking with this discovered provider
    book_res = schedule_appointment(
        provider_id=p["id"],
        date="2028-05-12",
        time="02:00 PM",
        customer_name="Discovered Tech Customer",
        service_id=1,
        problem="Cooling gas refill"
    )
    assert book_res.get("success") is True
    cancel_appointment(book_res["appointment_id"])


if __name__ == "__main__":
    init_db()
    print("Running tests in tests/test_tools.py...")
    test_scenario_1_ac_cooling()
    print("[PASS] Scenario 1: AC Repair")
    test_scenario_2_laptop_overheating()
    print("[PASS] Scenario 2: Laptop Repair")
    test_scenario_3_bathroom_leak()
    print("[PASS] Scenario 3: Plumbing")
    test_scenario_4_washing_machine_technician()
    print("[PASS] Scenario 4: Washing Machine Repair")
    test_scenario_5_end_to_end_pipeline()
    print("[PASS] Scenario 5: Tool Pipeline")
    test_scenario_6_and_7_booking_and_cancellation()
    print("[PASS] Scenario 6 & 7: Booking and Cancellation")
    test_error_invalid_service()
    print("[PASS] STEP 26: Invalid service category")
    test_error_no_availability()
    print("[PASS] STEP 26: No availability")
    test_error_invalid_appointment()
    print("[PASS] STEP 26: Invalid appointment (slot taken)")
    test_error_external_api_failure()
    print("[PASS] STEP 26: External API failure")
    test_search_external_providers_real_location_and_db_persistence()
    print("[PASS] Tavily + SQLite: Real-time provider discovery and booking")
    test_lookup_appliance_error_code()
    print("[PASS] Tavily AI: lookup_appliance_error_code (Manufacturer Manuals)")
    test_verify_part_pricing()
    print("[PASS] Tavily AI: verify_part_pricing (Anti-Fraud & Fair Market Rates)")
    print("\nALL tests in tests/test_tools.py passed successfully!")


