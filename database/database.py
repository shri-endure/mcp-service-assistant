"""Database management for MCP Service Resolution Assistant using SQLite."""

import os
import sqlite3
from typing import Any, Dict, List, Optional
from data.seed_data import FAQS, SEED_PROVIDERS, SERVICE_CATEGORIES, STANDARD_TIME_SLOTS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "services.db")


def get_connection() -> sqlite3.Connection:
    """Return a connection with Row row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reseed: bool = False) -> None:
    """Initialize SQLite database tables, migrate schema if needed, and populate seed data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()

        # Service table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS service (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT
            )
            """
        )

        # Providers table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                rating REAL NOT NULL,
                location TEXT NOT NULL,
                price_min INTEGER NOT NULL,
                price_max INTEGER NOT NULL,
                phone TEXT,
                email TEXT,
                description TEXT
            )
            """
        )

        # Availability table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT,
                available TEXT,
                FOREIGN KEY (provider_id) REFERENCES providers (id)
            )
            """
        )

        # Customers table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Appointments table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                service_id INTEGER DEFAULT 1,
                customer_id INTEGER,
                customer_name TEXT NOT NULL,
                customer_phone TEXT,
                customer_email TEXT,
                customer_address TEXT,
                date TEXT NOT NULL,
                time TEXT,
                time_slot TEXT,
                problem TEXT,
                status TEXT DEFAULT 'confirmed',
                cancellation_reason TEXT,
                cancelled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (provider_id) REFERENCES providers (id),
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
            """
        )

        # Job Messages table (Real-time customer <-> technician communication)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS job_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (appointment_id) REFERENCES appointments (id)
            )
            """
        )

        # Migration check: ensure new columns exist if created with an older schema
        cursor.execute("PRAGMA table_info(appointments)")
        cols = {row["name"] for row in cursor.fetchall()}
        if "time" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN time TEXT")
        if "time_slot" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN time_slot TEXT")
        if "service_id" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN service_id INTEGER DEFAULT 1")
        if "problem" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN problem TEXT")
        if "customer_id" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN customer_id INTEGER")
        if "customer_email" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN customer_email TEXT")
        if "customer_address" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN customer_address TEXT")
        if "cancellation_reason" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN cancellation_reason TEXT")
        if "cancelled_at" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN cancelled_at TIMESTAMP")
        if "updated_at" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN updated_at TIMESTAMP")
        if "technician_name" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN technician_name TEXT")
        if "eta_minutes" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN eta_minutes INTEGER DEFAULT 0")
        if "technician_notes" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN technician_notes TEXT")
        if "completed_at" not in cols:
            cursor.execute("ALTER TABLE appointments ADD COLUMN completed_at TIMESTAMP")

        cursor.execute("SELECT COUNT(*) FROM providers")
        count = cursor.fetchone()[0]

        # Reseed if empty or requested
        if count == 0 or force_reseed:
            cursor.execute("DELETE FROM providers")
            for p in SEED_PROVIDERS:
                cursor.execute(
                    """
                    INSERT INTO providers (id, name, category, rating, location, price_min, price_max, phone, email, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        p["id"],
                        p["name"],
                        p["category"],
                        p["rating"],
                        p["location"],
                        p["price_min"],
                        p["price_max"],
                        p.get("phone", ""),
                        p.get("email", ""),
                        p.get("description", ""),
                    ),
                )

        # Seed service table if empty
        cursor.execute("SELECT COUNT(*) FROM service")
        if cursor.fetchone()[0] == 0:
            for s in [
                ("Air Conditioner Repair", "AC Repair", "AC servicing, gas charging, leak repair, capacitor replacement"),
                ("Laptop & PC Repair", "Laptop Repair", "Screen replacement, chip-level motherboard repair, OS setup"),
                ("Plumbing Maintenance", "Plumbing", "Pipe leak repair, tap installation, drain unclogging, bathroom fittings"),
                ("Washing Machine Repair", "Washing Machine Repair", "Drum spin repair, motor fix, drain pump unclog, belt replacement"),
            ]:
                cursor.execute("INSERT INTO service (name, category, description) VALUES (?, ?, ?)", s)

        # Seed availability table if empty
        cursor.execute("SELECT COUNT(*) FROM availability")
        if cursor.fetchone()[0] == 0:
            from datetime import date, timedelta
            today_str = date.today().isoformat()
            tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
            for prov in SEED_PROVIDERS:
                for d in [today_str, tomorrow_str]:
                    for t in STANDARD_TIME_SLOTS:
                        cursor.execute(
                            "INSERT INTO availability (provider_id, date, time, available) VALUES (?, ?, ?, 'yes')",
                            (prov["id"], d, t),
                        )

        conn.commit()


def calculate_provider_score(
    rating: float,
    price_min: int,
    price_max: int,
    available_slots_count: int = 4,
) -> Dict[str, Any]:
    """Calculate provider composite score based on rating (40%), price (30%), and availability (30%).

    STEP 25: Provider selection strategy formula:
        provider_score = rating_score + availability_score + price_score
    """
    # 1. Rating score (up to 40 pts)
    rating_score = round((float(rating) / 5.0) * 40.0, 1)

    # 2. Price score (up to 30 pts) - lower average price gives higher score
    avg_price = (price_min + price_max) / 2.0
    price_score = round(max(5.0, min(30.0, 30.0 - ((avg_price - 500.0) / 1000.0) * 12.0)), 1)

    # 3. Availability score (up to 30 pts) - more available slots gives higher score
    availability_score = round(min(available_slots_count * 7.5, 30.0), 1)

    # Composite score (out of 100)
    total_score = round(rating_score + price_score + availability_score, 1)

    return {
        "provider_score": total_score,
        "rating_score": rating_score,
        "price_score": price_score,
        "availability_score": availability_score,
        "score_explanation": (
            f"Overall Score: {total_score}/100 [Rating: {rating_score}/40, "
            f"Pricing: {price_score}/30, Availability: {availability_score}/30]"
        ),
    }


def search_services_db(service_category: str) -> List[Dict[str, Any]]:
    """Search providers by service category with structured scoring (STEP 25) and error handling (STEP 26).

    Matches category case-insensitively.
    Returns list of dicts with: id, name, rating, location, price, scores, and ranking.
    """
    init_db()

    clean_category = service_category.strip() if service_category else ""

    # Check for invalid / unsupported service (STEP 26)
    valid_categories_lower = [c.lower() for c in SERVICE_CATEGORIES]
    if clean_category.lower() not in valid_categories_lower and clean_category.lower() != "all":
        return []

    with get_connection() as conn:
        cursor = conn.cursor()
        if clean_category.lower() == "all":
            cursor.execute(
                """
                SELECT id, name, category, rating, location, price_min, price_max, phone, description
                FROM providers
                ORDER BY rating DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT id, name, category, rating, location, price_min, price_max, phone, description
                FROM providers
                WHERE LOWER(category) = LOWER(?)
                ORDER BY rating DESC
                """,
                (clean_category,),
            )
        rows = cursor.fetchall()

    providers_list = []
    with get_connection() as conn:
        cursor = conn.cursor()
        for row in rows:
            cursor.execute(
                """
                SELECT COALESCE(time, time_slot) as booked_time
                FROM appointments
                WHERE provider_id = ? AND LOWER(status) = 'confirmed'
                """,
                (row["id"],),
            )
            booked_slots = [
                r["booked_time"] for r in cursor.fetchall() if r["booked_time"]
            ]
            avail_count = max(0, 4 - len(booked_slots))

            scores = calculate_provider_score(
                rating=row["rating"],
                price_min=row["price_min"],
                price_max=row["price_max"],
                available_slots_count=avail_count,
            )
            providers_list.append({
                "id": row["id"],
                "name": row["name"],
                "category": row["category"],
                "rating": row["rating"],
                "location": row["location"],
                "price": f"₹{row['price_min']}–₹{row['price_max']}",
                "price_min": row["price_min"],
                "price_max": row["price_max"],
                "phone": row["phone"],
                "description": row["description"],
                "booked_slots": booked_slots,
                "provider_score": scores["provider_score"],
                "rating_score": scores["rating_score"],
                "price_score": scores["price_score"],
                "availability_score": scores["availability_score"],
                "score_explanation": scores["score_explanation"],
            })

    # Sort by provider_score descending (STEP 25)
    providers_list.sort(key=lambda x: x["provider_score"], reverse=True)
    return providers_list


def get_provider_details_db(provider_id: int) -> Optional[Dict[str, Any]]:
    """Fetch complete details of a service provider by ID including calculated score."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, category, rating, location, price_min, price_max, phone, email, description
            FROM providers
            WHERE id = ?
            """,
            (provider_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute(
            """
            SELECT COALESCE(time, time_slot) as booked_time
            FROM appointments
            WHERE provider_id = ? AND LOWER(status) = 'confirmed'
            """,
            (provider_id,),
        )
        booked_slots = [r["booked_time"] for r in cursor.fetchall() if r["booked_time"]]
        avail_count = max(0, 4 - len(booked_slots))

        scores = calculate_provider_score(
            rating=row["rating"],
            price_min=row["price_min"],
            price_max=row["price_max"],
            available_slots_count=avail_count,
        )

        return {
            "id": row["id"],
            "name": row["name"],
            "service": row["category"],
            "category": row["category"],
            "rating": row["rating"],
            "location": row["location"],
            "price_range": f"₹{row['price_min']}–₹{row['price_max']}",
            "price_min": row["price_min"],
            "price_max": row["price_max"],
            "phone": row["phone"],
            "email": row["email"],
            "description": row["description"],
            "booked_slots": booked_slots,
            "provider_score": scores["provider_score"],
            "rating_score": scores["rating_score"],
            "price_score": scores["price_score"],
            "availability_score": scores["availability_score"],
            "score_explanation": scores["score_explanation"],
        }


def normalize_time_slot(slot: str) -> str:
    """Normalize time slot between 12-hour AM/PM and 24-hour format."""
    s = (slot or "").strip().upper()
    mapping = {
        "10:00 AM": "10:00",
        "10:00": "10:00",
        "12:00 PM": "12:00",
        "12:00": "12:00",
        "02:00 PM": "14:00",
        "2:00 PM": "14:00",
        "14:00": "14:00",
        "04:00 PM": "16:00",
        "4:00 PM": "16:00",
        "16:00": "16:00",
    }
    return mapping.get(s, s)


def check_availability_db(provider_id: int, date: str) -> Dict[str, Any]:
    """Check available time slots for a provider on a given date.

    STEP 26: Returns friendly guidance when no slots are available.
    """
    init_db()
    provider = get_provider_details_db(provider_id)
    if not provider:
        return {"error": f"Provider with ID {provider_id} not found."}

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(time, time_slot) as booked_time
            FROM appointments
            WHERE provider_id = ? AND date = ? AND LOWER(status) = 'confirmed'
            """,
            (provider_id, date),
        )
        booked_slots = {
            normalize_time_slot(row["booked_time"]) for row in cursor.fetchall() if row["booked_time"]
        }

    display_slots = ["10:00 AM", "12:00 PM", "02:00 PM", "04:00 PM"]
    available_slots = [
        slot for slot in display_slots if normalize_time_slot(slot) not in booked_slots
    ]
    booked_display_slots = [
        slot for slot in display_slots if normalize_time_slot(slot) in booked_slots
    ]

    result = {
        "provider": provider["name"],
        "date": date,
        "available_slots": available_slots,
        "booked_slots": booked_display_slots,
    }

    if not available_slots:
        result["message"] = "No slots available tomorrow. Would you like to check another date?"

    return result


def save_customer_db(
    name: str,
    phone: str,
    email: str = "",
    address: str = "",
) -> int:
    """Insert or update customer record in SQLite and return customer_id."""
    init_db()
    name = (name or "Valued Customer").strip()
    phone = (phone or "").strip()
    email = (email or "").strip()
    address = (address or "").strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        if phone:
            cursor.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
            row = cursor.fetchone()
            if row:
                customer_id = row["id"]
                cursor.execute(
                    """
                    UPDATE customers 
                    SET name = ?, email = COALESCE(NULLIF(?, ''), email),
                        address = COALESCE(NULLIF(?, ''), address),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (name, email, address, customer_id),
                )
                conn.commit()
                return customer_id

        cursor.execute(
            """
            INSERT INTO customers (name, phone, email, address)
            VALUES (?, ?, ?, ?)
            """,
            (name, phone or "Not Provided", email, address),
        )
        conn.commit()
        return cursor.lastrowid


def get_customers_db() -> List[Dict[str, Any]]:
    """Retrieve all customers with booking count from SQLite."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id, c.name, c.phone, c.email, c.address, c.created_at,
                   COUNT(a.id) as total_bookings
            FROM customers c
            LEFT JOIN appointments a ON a.customer_id = c.id
            GROUP BY c.id
            ORDER BY c.id DESC
            """
        )
        return [dict(r) for r in cursor.fetchall()]


def schedule_appointment_db(
    provider_id: int,
    date: str,
    time: str,
    customer_name: str,
    service_id: int = 1,
    problem: str = "",
    customer_phone: str = "",
    customer_email: str = "",
    customer_address: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """Schedule a new appointment for a customer with a provider in SQLite.

    Maintains complete customer and booking lifecycle data.
    """
    init_db()
    provider = get_provider_details_db(provider_id)
    if not provider:
        return {"success": False, "message": f"Provider with ID {provider_id} not found."}

    # Verify slot availability using normalized comparison
    norm_time = normalize_time_slot(time)
    availability = check_availability_db(provider_id, date)
    avail_norms = [normalize_time_slot(s) for s in availability.get("available_slots", [])]
    if norm_time not in avail_norms:
        return {
            "success": False,
            "message": "This slot is no longer available.",
            "detail": "This slot is no longer available.",
        }

    # Save customer to customers table first
    customer_id = save_customer_db(customer_name, customer_phone, customer_email, customer_address)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO appointments (
                provider_id, service_id, customer_id, customer_name, customer_phone,
                customer_email, customer_address, date, time, time_slot, problem, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')
            """,
            (
                provider_id,
                service_id,
                customer_id,
                customer_name,
                customer_phone,
                customer_email,
                customer_address,
                date,
                time,
                time,
                problem,
            ),
        )
        appointment_id = cursor.lastrowid

        # Update availability table to mark slot as booked
        cursor.execute(
            """
            UPDATE availability SET available = 'no' WHERE provider_id = ? AND date = ? AND time = ?
            """,
            (provider_id, date, time),
        )
        conn.commit()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "customer_id": customer_id,
        "customer_name": customer_name or "Valued Customer",
        "customer_phone": customer_phone or "+91 98765 00000",
        "customer_email": customer_email,
        "customer_address": customer_address or "Local Area",
        "provider": provider["name"],
        "provider_phone": provider.get("phone", "+91 98765 43210"),
        "date": date,
        "time": time,
        "time_slot": time,
        "problem": problem or "Appliance / Service repair",
        "issue": problem or "Appliance / Service repair",
        "status": "confirmed",
    }


def cancel_appointment_db(appointment_id: int, reason: str = "Customer request") -> Dict[str, Any]:
    """Cancel an existing appointment by ID and record cancellation timestamps."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, provider_id, date, time, status, customer_name FROM appointments WHERE id = ?",
            (appointment_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": f"Appointment with ID {appointment_id} not found."}

        if str(row["status"]).lower() == "cancelled":
            return {
                "success": True,
                "appointment_id": appointment_id,
                "status": "cancelled",
                "message": f"Appointment #{appointment_id} is already cancelled.",
            }

        cursor.execute(
            """
            UPDATE appointments 
            SET status = 'cancelled', cancellation_reason = ?, cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, appointment_id),
        )
        # Release the slot in availability table if present
        if row["date"] and row["time"]:
            cursor.execute(
                """
                UPDATE availability SET available = 'yes' WHERE provider_id = ? AND date = ? AND time = ?
                """,
                (row["provider_id"], row["date"], row["time"]),
            )
        conn.commit()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": "cancelled",
        "message": f"Appointment #{appointment_id} has been successfully cancelled.",
    }


def update_appointment_status_db(
    appointment_id: int,
    status: str,
    technician_name: str = "",
    eta_minutes: int = 0,
    technician_notes: str = "",
) -> Dict[str, Any]:
    """Update appointment status in SQLite and return the updated appointment record."""
    init_db()
    valid_statuses = ["confirmed", "accepted", "en_route", "arrived", "in_progress", "completed", "cancelled"]
    normalized_status = status.strip().lower()
    if normalized_status not in valid_statuses:
        return {"success": False, "message": f"Invalid status '{status}'. Valid statuses: {valid_statuses}"}

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.*, p.name as provider_name, p.category as provider_category, p.phone as provider_phone
            FROM appointments a
            LEFT JOIN providers p ON a.provider_id = p.id
            WHERE a.id = ?
            """,
            (appointment_id,),
        )
        existing = cursor.fetchone()
        if not existing:
            return {"success": False, "message": f"Appointment #{appointment_id} not found."}

        completed_clause = ", completed_at = CURRENT_TIMESTAMP" if normalized_status == "completed" else ""

        cursor.execute(
            f"""
            UPDATE appointments
            SET status = ?,
                technician_name = CASE WHEN ? != '' THEN ? ELSE technician_name END,
                eta_minutes = ?,
                technician_notes = CASE WHEN ? != '' THEN ? ELSE technician_notes END,
                updated_at = CURRENT_TIMESTAMP
                {completed_clause}
            WHERE id = ?
            """,
            (normalized_status, technician_name, technician_name, eta_minutes, technician_notes, technician_notes, appointment_id),
        )
        conn.commit()

        cursor.execute(
            """
            SELECT a.*, p.name as provider_name, p.category as provider_category, p.phone as provider_phone
            FROM appointments a
            LEFT JOIN providers p ON a.provider_id = p.id
            WHERE a.id = ?
            """,
            (appointment_id,),
        )
        updated = cursor.fetchone()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": normalized_status,
        "technician_name": updated["technician_name"] or technician_name or "Service Technician",
        "eta_minutes": updated["eta_minutes"] or eta_minutes,
        "technician_notes": updated["technician_notes"] or "",
        "customer_name": updated["customer_name"],
        "customer_phone": updated["customer_phone"],
        "customer_address": updated["customer_address"],
        "date": updated["date"],
        "time_slot": updated["time_slot"] or updated["time"],
        "problem": updated["problem"],
        "provider_name": updated["provider_name"],
        "provider_id": updated["provider_id"],
        "message": f"Appointment #{appointment_id} updated to '{normalized_status}'.",
    }


def get_technician_jobs_db(provider_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve all jobs/appointments formatted for the technician live dashboard."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                a.id as appointment_id,
                a.provider_id,
                p.name as provider_name,
                p.category as service_category,
                p.phone as provider_phone,
                a.customer_name,
                a.customer_phone,
                a.customer_email,
                a.customer_address,
                a.date,
                a.time as time,
                a.time_slot,
                a.problem,
                a.status,
                a.technician_name,
                a.eta_minutes,
                a.technician_notes,
                a.created_at,
                a.updated_at
            FROM appointments a
            LEFT JOIN providers p ON a.provider_id = p.id
        """
        params = []
        if provider_id is not None:
            query += " WHERE a.provider_id = ?"
            params.append(provider_id)
        query += " ORDER BY a.id DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [
            {
                "appointment_id": r["appointment_id"],
                "provider_id": r["provider_id"],
                "provider_name": r["provider_name"] or "Unknown Provider",
                "service_category": r["service_category"] or "General Service",
                "provider_phone": r["provider_phone"] or "",
                "customer_name": r["customer_name"] or "Customer",
                "customer_phone": r["customer_phone"] or "",
                "customer_email": r["customer_email"] or "",
                "customer_address": r["customer_address"] or "Local Area",
                "date": r["date"],
                "time_slot": r["time_slot"] or r["time"] or "10:00 AM",
                "problem": r["problem"] or "General Appliance Servicing",
                "status": r["status"] or "confirmed",
                "technician_name": r["technician_name"] or "Technician",
                "eta_minutes": r["eta_minutes"] or 0,
                "technician_notes": r["technician_notes"] or "",
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def clear_all_bookings_db() -> Dict[str, Any]:
    """Clear all bookings and messages to start with a clean application state (0 active bookings)."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM appointments")
        cursor.execute("DELETE FROM job_messages")
        cursor.execute("UPDATE availability SET available = 'yes'")
        conn.commit()
    return {"success": True, "message": "All bookings and messages cleared successfully. Active bookings: 0."}


def register_provider_db(
    name: str,
    category: str,
    location: str,
    phone: str,
    price_min: int,
    price_max: int,
    description: str = "",
    email: str = "",
) -> Dict[str, Any]:
    """Register a new service professional/technician into the system (JobSetu model)."""
    init_db()
    from datetime import date, timedelta
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO providers (name, category, rating, location, price_min, price_max, phone, email, description)
            VALUES (?, ?, 4.8, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                category.strip(),
                location.strip(),
                int(price_min),
                int(price_max),
                phone.strip(),
                email.strip() if email else f"{name.lower().replace(' ', '')}@gmail.com",
                description.strip() if description else f"Verified {category} specialist serving {location}.",
            ),
        )
        provider_id = cursor.lastrowid

        # Generate standard availability slots for the next 7 days
        today = date.today()
        for offset in range(0, 7):
            slot_date = (today + timedelta(days=offset)).strftime("%Y-%m-%d")
            for slot_time in STANDARD_TIME_SLOTS:
                cursor.execute(
                    """
                    INSERT INTO availability (provider_id, date, time, available)
                    VALUES (?, ?, ?, 'yes')
                    """,
                    (provider_id, slot_date, slot_time),
                )
        conn.commit()

    return {
        "success": True,
        "provider_id": provider_id,
        "name": name,
        "category": category,
        "location": location,
        "phone": phone,
        "rating": 4.8,
        "price_range": f"₹{price_min}–₹{price_max}",
        "message": f"Technician '{name}' successfully registered to the network.",
    }


def add_job_message_db(
    appointment_id: int,
    sender_type: str,
    sender_name: str,
    message: str,
) -> Dict[str, Any]:
    """Save a direct chat message between customer and technician for an appointment."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO job_messages (appointment_id, sender_type, sender_name, message)
            VALUES (?, ?, ?, ?)
            """,
            (appointment_id, sender_type, sender_name, message),
        )
        msg_id = cursor.lastrowid
        cursor.execute("SELECT * FROM job_messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        conn.commit()

    return {
        "id": row["id"],
        "appointment_id": row["appointment_id"],
        "sender_type": row["sender_type"],
        "sender_name": row["sender_name"],
        "message": row["message"],
        "created_at": str(row["created_at"]),
    }


def get_job_messages_db(appointment_id: int) -> List[Dict[str, Any]]:
    """Retrieve chat history between customer and technician for an appointment."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, appointment_id, sender_type, sender_name, message, created_at
            FROM job_messages
            WHERE appointment_id = ?
            ORDER BY id ASC
            """,
            (appointment_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "appointment_id": r["appointment_id"],
                "sender_type": r["sender_type"],
                "sender_name": r["sender_name"],
                "message": r["message"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


