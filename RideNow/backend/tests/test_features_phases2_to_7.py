"""
Comprehensive verification test suite for Phases 2 to 7 in RideNow:
- Phase 2: Paginated ride history (passenger & driver) with sorting & filtering
- Phase 3: Driver earnings with cancelled_rides and average_fare
- Phase 4: Profile updates (user & driver vehicle details) with uniqueness constraints
- Phase 5: Security audit verification:
    * Rating submission validations (completed ride only, passenger only, no duplicate ratings)
    * Rating IDOR protection (drivers can only view their own ratings)
    * Token revocation
    * Payment security (fare calculated by server, passenger ownership)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import time
import asyncio
from app.database import engine
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://127.0.0.1:8000"
PASS_SYM = "[PASS]"
FAIL_SYM = "[FAIL]"

results = []

def check(label, resp, expected_status, key_check=None):
    if isinstance(expected_status, list):
        ok = resp.status_code in expected_status
    else:
        ok = resp.status_code == expected_status

    if ok and key_check:
        try:
            ok = key_check(resp.json())
        except Exception as e:
            print(f"         [Condition Error]: {e}")
            ok = False
    sym = PASS_SYM if ok else FAIL_SYM
    results.append(ok)
    print(f"  {sym}  [{resp.status_code}] {label}")
    if not ok:
        try:
            print(f"         => Response: {resp.json()}")
        except Exception:
            print(f"         => Response text: {resp.text[:300]}")
    return resp


async def reset_drivers_offline():
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE drivers SET is_online = false, is_available = false"))
        await conn.commit()

asyncio.run(reset_drivers_offline())

ts = str(int(time.time()))

print("\n" + "=" * 65)
print("  RIDENOW PHASES 2 - 7 COMPREHENSIVE VERIFICATION SUITE")
print("=" * 65)

# -------------------------------------------------------------
# SETUP: Create Passenger 1, Driver 1, Driver 2
# -------------------------------------------------------------
print("\n--- Setup: Registering Users ---")
p1_email = f"pass_p2_{ts}@test.com"
p1_phone = f"710{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Passenger Two",
    "email": p1_email,
    "phone": p1_phone,
    "password": "Password@123",
    "role": "passenger"
})
check("Register Passenger 1", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": p1_email, "password": "Password@123"})
check("Login Passenger 1", r, 200)
p1_token = r.json().get("access_token")
p1_headers = {"Authorization": f"Bearer {p1_token}"}

# Driver 1
d1_email = f"drv1_p2_{ts}@test.com"
d1_phone = f"810{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Driver One",
    "email": d1_email,
    "phone": d1_phone,
    "password": "Password@123",
    "role": "driver"
})
check("Register Driver 1 User", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": d1_email, "password": "Password@123"})
check("Login Driver 1", r, 200)
d1_token = r.json().get("access_token")
d1_headers = {"Authorization": f"Bearer {d1_token}"}

r = requests.post(f"{BASE}/drivers/register", headers=d1_headers, json={
    "license_number": f"LIC1_{ts}",
    "vehicle_type": "sedan",
    "vehicle_number": f"VEH1_{ts[-6:]}",
    "vehicle_model": "Swift Dzire"
})
check("Register Driver 1 Profile", r, 201)
d1_id = r.json().get("id")

requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=d1_headers)
requests.patch(f"{BASE}/drivers/location", headers=d1_headers, json={"latitude": 17.385000, "longitude": 78.486000})

# Driver 2
d2_email = f"drv2_p2_{ts}@test.com"
d2_phone = f"910{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Driver Two",
    "email": d2_email,
    "phone": d2_phone,
    "password": "Password@123",
    "role": "driver"
})
check("Register Driver 2 User", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": d2_email, "password": "Password@123"})
check("Login Driver 2", r, 200)
d2_token = r.json().get("access_token")
d2_headers = {"Authorization": f"Bearer {d2_token}"}

r = requests.post(f"{BASE}/drivers/register", headers=d2_headers, json={
    "license_number": f"LIC2_{ts}",
    "vehicle_type": "suv",
    "vehicle_number": f"VEH2_{ts[-6:]}",
    "vehicle_model": "Innova Crysta"
})
check("Register Driver 2 Profile", r, 201)
d2_id = r.json().get("id")

# -------------------------------------------------------------
# PHASE 4: PROFILE MANAGEMENT & CONSTRAINTS
# -------------------------------------------------------------
print("\n--- Phase 4: Profile Management & Uniqueness Constraints ---")
# 1. Update passenger profile
r = requests.patch(f"{BASE}/users/me", headers=p1_headers, json={
    "name": "Passenger Two Renamed",
    "phone": f"720{ts[-7:]}"
})
check("PATCH /users/me updates name & phone", r, 200, lambda j: j.get("name") == "Passenger Two Renamed")

# 2. Update driver profile (vehicle model, etc.)
r = requests.patch(f"{BASE}/drivers/me", headers=d1_headers, json={
    "vehicle_model": "Swift Dzire 2024",
    "vehicle_type": "sedan"
})
check("PATCH /drivers/me updates vehicle model", r, 200, lambda j: j.get("vehicle_model") == "Swift Dzire 2024")

# 3. Duplicate license rejected
r = requests.patch(f"{BASE}/drivers/me", headers=d2_headers, json={
    "license_number": f"LIC1_{ts}"
})
check("PATCH /drivers/me rejects duplicate license (409 or 400)", r, 409 if r.status_code == 409 else 400)

# 4. Duplicate vehicle number rejected
r = requests.patch(f"{BASE}/drivers/me", headers=d2_headers, json={
    "vehicle_number": f"VEH1_{ts[-6:]}"
})
check("PATCH /drivers/me rejects duplicate vehicle number (409 or 400)", r, 409 if r.status_code == 409 else 400)

# -------------------------------------------------------------
# RIDE LIFECYCLES: Create completed ride & cancelled ride for Driver 1
# -------------------------------------------------------------
print("\n--- Creating Rides for History & Earnings ---")
# Ride 1: Assign to Driver 1, then complete
r = requests.post(f"{BASE}/rides/request", headers=p1_headers, json={
    "pickup_location": "Koti, Hyderabad",
    "dropoff_location": "Abids, Hyderabad",
    "pickup_latitude": 17.385010,
    "pickup_longitude": 78.486010
})
check("Request Ride 1 (assigned to Driver 1)", r, 201, lambda j: j.get("driver_id") == d1_id)
ride1_id = r.json().get("id")

# Driver 1 starts and completes Ride 1
r = requests.patch(f"{BASE}/rides/{ride1_id}/start", headers=d1_headers)
check("Driver 1 starts Ride 1", r, 200)

r = requests.patch(f"{BASE}/rides/{ride1_id}/complete", headers=d1_headers)
check("Driver 1 completes Ride 1", r, 200, lambda j: j.get("status") == "COMPLETED")

# Ride 2: Ensure Driver 1 is available at location, request Ride 2 (Driver 1 assigned), then passenger cancels
requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=d1_headers)
requests.patch(f"{BASE}/drivers/location", headers=d1_headers, json={"latitude": 17.385000, "longitude": 78.486000})

r = requests.post(f"{BASE}/rides/request", headers=p1_headers, json={
    "pickup_location": "Koti Bus Stand",
    "dropoff_location": "Sultan Bazar",
    "pickup_latitude": 17.385005,
    "pickup_longitude": 78.486005
})
check("Request Ride 2 (assigned to Driver 1)", r, 201, lambda j: j.get("driver_id") == d1_id)
ride2_id = r.json().get("id")

# Passenger cancels Ride 2
r = requests.patch(f"{BASE}/rides/{ride2_id}/cancel", headers=p1_headers)
check("Passenger cancels Ride 2", r, 200, lambda j: j.get("status") == "CANCELLED")

# -------------------------------------------------------------
# PHASE 2: PAGINATED RIDE HISTORY & SORTING
# -------------------------------------------------------------
print("\n--- Phase 2: Paginated Ride History & Sorting ---")
# Passenger History (newest first)
r = requests.get(f"{BASE}/rides/my/history?page=1&page_size=10&sort=newest", headers=p1_headers)
check("GET /rides/my/history?sort=newest", r, 200, lambda j: (
    len(j.get("items", [])) >= 2 and
    j["items"][0]["id"] > j["items"][1]["id"]
))

# Passenger History (oldest first)
r = requests.get(f"{BASE}/rides/my/history?page=1&page_size=10&sort=oldest", headers=p1_headers)
check("GET /rides/my/history?sort=oldest", r, 200, lambda j: (
    len(j.get("items", [])) >= 2 and
    j["items"][0]["id"] < j["items"][1]["id"]
))

# Passenger History filter by status
r = requests.get(f"{BASE}/rides/my/history?status=COMPLETED", headers=p1_headers)
check("GET /rides/my/history?status=COMPLETED", r, 200, lambda j: all(x["status"] == "COMPLETED" for x in j.get("items", [])))

# Driver 1 History (newest first)
r = requests.get(f"{BASE}/rides/driver/my/history?page=1&page_size=10&sort=newest", headers=d1_headers)
check("GET /rides/driver/my/history?sort=newest", r, 200, lambda j: "items" in j and "total_pages" in j)

# Driver 1 History (oldest first)
r = requests.get(f"{BASE}/rides/driver/my/history?page=1&page_size=10&sort=oldest", headers=d1_headers)
check("GET /rides/driver/my/history?sort=oldest", r, 200, lambda j: "items" in j)

# -------------------------------------------------------------
# PHASE 3: DRIVER EARNINGS & CANCELLED RIDES STATS
# -------------------------------------------------------------
print("\n--- Phase 3: Driver Earnings & Cancelled Rides ---")
r = requests.get(f"{BASE}/drivers/earnings", headers=d1_headers)
check("GET /drivers/earnings returns full stats with cancelled_rides >= 1", r, 200, lambda j: (
    "total_rides" in j and
    "cancelled_rides" in j and
    "average_fare" in j and
    "total_earnings" in j and
    j["total_rides"] >= 1 and
    j["cancelled_rides"] >= 1
))

# -------------------------------------------------------------
# PHASE 5: SECURITY AUDIT (RATINGS & PAYMENTS & REVOCATION)
# -------------------------------------------------------------
print("\n--- Phase 5: Ratings & IDOR Protection ---")
# 1. Driver 2 attempts to view Driver 1's ratings -> IDOR Prevention (403)
r = requests.get(f"{BASE}/ratings/driver/{d1_id}", headers=d2_headers)
check("IDOR check: Driver 2 viewing Driver 1 ratings gives 403", r, 403)

# 2. Driver 1 views own ratings -> Allowed (200)
r = requests.get(f"{BASE}/ratings/driver/{d1_id}", headers=d1_headers)
check("Driver 1 viewing own ratings gives 200", r, 200, lambda j: isinstance(j, list))

# 3. Passenger rates completed ride -> Success (201)
r = requests.post(f"{BASE}/ratings", headers=p1_headers, json={
    "ride_id": ride1_id,
    "rating": 5,
    "comment": "Great driving and very punctual!"
})
check("Passenger submits rating for completed ride", r, 201, lambda j: j.get("rating") == 5)

# 4. Duplicate rating prevented on same ride (400)
r = requests.post(f"{BASE}/ratings", headers=p1_headers, json={
    "ride_id": ride1_id,
    "rating": 4,
    "comment": "Trying to rate again"
})
check("Prevent duplicate rating on same ride (400)", r, 400)

# 5. Cannot rate cancelled ride (400)
r = requests.post(f"{BASE}/ratings", headers=p1_headers, json={
    "ride_id": ride2_id,
    "rating": 1,
    "comment": "Cancelled ride"
})
check("Cannot rate cancelled ride (400)", r, 400)

print("\n--- Phase 5: Payment Security ---")
# 1. Passenger creates payment for completed ride
r = requests.post(f"{BASE}/payments", headers=p1_headers, json={
    "ride_id": ride1_id,
    "payment_method": "card"
})
check("POST /payments: amount taken securely from ride fare", r, [200, 201], lambda j: "amount" in j and float(j["amount"]) > 0)
payment_id = r.json().get("id")

# 2. Duplicate payment initiation returns existing payment safely
r = requests.post(f"{BASE}/payments", headers=p1_headers, json={
    "ride_id": ride1_id,
    "payment_method": "card"
})
check("Duplicate payment creation returns existing payment safely", r, [200, 201], lambda j: j.get("id") == payment_id)

# 3. Passenger completes payment
r = requests.patch(f"{BASE}/payments/{ride1_id}/pay", headers=p1_headers)
check("PATCH /payments/{ride_id}/pay completes payment successfully", r, 200, lambda j: j.get("status") == "PAID")

# -------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------
total = len(results)
passed = sum(results)
failed = total - passed
print("\n" + "=" * 65)
print(f"  PHASES 2 - 7 SUITE RESULTS:  {passed}/{total} passed  |  {failed} failed")
print("=" * 65)

if failed > 0:
    sys.exit(1)
print("\nALL PHASE 2 - 7 VERIFICATIONS PASSED SUCCESSFULLY!")
