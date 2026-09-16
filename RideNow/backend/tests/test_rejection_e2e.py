"""
Comprehensive automated test suite for:
DRIVER REJECT RIDE + NEXT DRIVER AUTOMATIC MATCHING (Phase 1 Feature)

Tests all 10 Test Cases required by the specification:
- Test Case 1: Passenger requests ride -> Nearest available driver is assigned
- Test Case 2: Assigned driver rejects -> Next nearest eligible driver assigned
- Test Case 3: Second driver rejects -> Third eligible driver searched & assigned
- Test Case 4: All drivers reject -> Ride remains REQUESTED, next_driver_found=False
- Test Case 5: Rejected drivers are permanently excluded for that ride
- Test Case 6: Passenger cannot call driver reject endpoint (403)
- Test Case 7: Driver cannot reject another driver's ride (403)
- Test Case 8: Cannot reject completed ride (400)
- Test Case 9: Cannot reject cancelled ride (400)
- Test Case 10: Duplicate rejection prevented & cannot corrupt DB
"""

import sys
import os
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import asyncio
from app.database import engine
from sqlalchemy import text

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://127.0.0.1:8000"
PASS_SYM = "[PASS]"
FAIL_SYM = "[FAIL]"

results = []

def check(label, resp, expected_status, condition=None):
    ok = (resp.status_code == expected_status)
    if ok and condition:
        try:
            ok = condition(resp.json())
        except Exception as e:
            print(f"         Condition check exception: {e}")
            ok = False
    sym = PASS_SYM if ok else FAIL_SYM
    results.append(ok)
    print(f"  {sym}  [{resp.status_code}] {label}")
    if not ok:
        try:
            print(f"         => Response: {resp.json()}")
        except Exception:
            print(f"         => Response text: {resp.text[:300]}")
    return ok


async def reset_drivers_offline():
    async with engine.connect() as conn:
        await conn.execute(text("UPDATE drivers SET is_online = false, is_available = false"))
        await conn.commit()


def run_tests():
    print("\n" + "=" * 60)
    print("  RIDE REJECTION & AUTO-MATCHING E2E TEST SUITE")
    print("=" * 60)

    # Set all existing drivers offline for test isolation
    asyncio.run(reset_drivers_offline())

    ts = str(int(time.time()))

    # 1. Setup: Create Passenger
    print("\n-- Setup: Creating Passenger --")
    pass_email = f"rej_pass_{ts}@example.com"
    r = requests.post(f"{BASE}/users/register", json={
        "name": "Rejection Test Passenger",
        "email": pass_email,
        "phone": f"910{ts[-7:]}",
        "password": "Password123!",
        "role": "passenger"
    })
    check("Register Passenger", r, 201)

    r = requests.post(f"{BASE}/users/login", data={
        "username": pass_email,
        "password": "Password123!"
    })
    check("Login Passenger", r, 200)
    pass_token = r.json()["access_token"]
    pass_headers = {"Authorization": f"Bearer {pass_token}"}

    # 2. Setup: Create 3 Drivers at varying distances
    # Pickup location will be at (17.3850, 78.4866)
    # Driver A: ~0.1 km away (17.3855, 78.4870) -> Nearest
    # Driver B: ~2.5 km away (17.4000, 78.5000) -> 2nd nearest
    # Driver C: ~6.0 km away (17.4300, 78.5200) -> 3rd nearest
    driver_coords = [
        ("Driver A", 17.3855, 78.4870),
        ("Driver B", 17.4000, 78.5000),
        ("Driver C", 17.4300, 78.5200),
    ]
    drivers = []

    print("\n-- Setup: Creating 3 Drivers (A, B, C) --")
    for idx, (dname, dlat, dlng) in enumerate(driver_coords):
        d_email = f"rej_drv_{idx}_{ts}@example.com"
        d_phone = f"92{idx}{ts[-7:]}"
        # Register user
        r = requests.post(f"{BASE}/users/register", json={
            "name": dname,
            "email": d_email,
            "phone": d_phone,
            "password": "Password123!",
            "role": "driver"
        })
        check(f"Register {dname}", r, 201)

        # Login user
        r = requests.post(f"{BASE}/users/login", data={
            "username": d_email,
            "password": "Password123!"
        })
        check(f"Login {dname}", r, 200)
        d_token = r.json()["access_token"]
        d_headers = {"Authorization": f"Bearer {d_token}"}

        # Driver profile
        r = requests.post(f"{BASE}/drivers/register", headers=d_headers, json={
            "license_number": f"LIC_{idx}_{ts}",
            "vehicle_type": "Sedan",
            "vehicle_number": f"DL{idx}{ts[-6:]}",
            "vehicle_model": "Swift Dzire"
        })
        check(f"Register Profile {dname}", r, 201)
        driver_id = r.json()["id"]

        # Set status online & available
        r = requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=d_headers)
        check(f"Set {dname} Online & Available", r, 200)

        # Set location
        r = requests.patch(f"{BASE}/drivers/location", headers=d_headers, json={
            "latitude": dlat,
            "longitude": dlng
        })
        check(f"Set {dname} Location ({dlat}, {dlng})", r, 200)

        drivers.append({
            "name": dname,
            "id": driver_id,
            "headers": d_headers,
            "email": d_email
        })

    # =========================================================================
    # TEST CASE 1: Passenger requests ride -> Nearest available driver (A) assigned
    # =========================================================================
    print("\n-- TEST CASE 1: Request Ride -> Nearest Driver A Assigned --")
    r = requests.post(f"{BASE}/rides/request", headers=pass_headers, json={
        "pickup_location": "Hyderabad Central",
        "dropoff_location": "Secunderabad Station",
        "pickup_latitude": 17.3850,
        "pickup_longitude": 78.4866
    })
    check("Passenger requests ride", r, 201)
    ride_data = r.json()
    ride_id = ride_data["id"]

    # Verify Driver A is assigned
    check("TC1: Nearest Driver A is assigned", r, 201,
          lambda j: j["driver_id"] == drivers[0]["id"] and j["status"] == "ACCEPTED")

    # =========================================================================
    # TEST CASE 6: Passenger tries to call reject endpoint -> 403 Forbidden
    # =========================================================================
    print("\n-- TEST CASE 6: Passenger Tries to Reject -> 403 Forbidden --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=pass_headers)
    check("TC6: Passenger calling reject gives 403", r, 403)

    # =========================================================================
    # TEST CASE 7: Driver B tries to reject Driver A's ride -> 403 Forbidden
    # =========================================================================
    print("\n-- TEST CASE 7: Unassigned Driver B Tries to Reject -> 403 Forbidden --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=drivers[1]["headers"])
    check("TC7: Unassigned Driver B calling reject gives 403", r, 403)

    # =========================================================================
    # TEST CASE 2: Assigned Driver A rejects -> Driver B assigned
    # =========================================================================
    print("\n-- TEST CASE 2: Driver A Rejects -> Next Driver B Assigned --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=drivers[0]["headers"])
    check("TC2: Driver A rejects successfully", r, 200,
          lambda j: j["next_driver_found"] is True and j["ride_id"] == ride_id)

    # Verify ride now has Driver B assigned
    r_ride = requests.get(f"{BASE}/rides/{ride_id}", headers=pass_headers)
    check("TC2: Ride now assigned to Driver B", r_ride, 200,
          lambda j: j["driver_id"] == drivers[1]["id"] and j["status"] == "ACCEPTED")

    # Verify Driver A is available again
    r_drva = requests.get(f"{BASE}/drivers/me/profile", headers=drivers[0]["headers"])
    check("TC2: Driver A is now available again", r_drva, 200,
          lambda j: j["is_available"] is True)

    # =========================================================================
    # TEST CASE 10: Duplicate rejection by Driver A -> Prevented
    # =========================================================================
    print("\n-- TEST CASE 10: Duplicate Rejection by Driver A -> Prevented --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=drivers[0]["headers"])
    check("TC10: Duplicate rejection blocked (403 or 409)", r, 403)

    # =========================================================================
    # TEST CASE 3: Second Driver B rejects -> Driver C searched & assigned
    # =========================================================================
    print("\n-- TEST CASE 3: Driver B Rejects -> Driver C Assigned --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=drivers[1]["headers"])
    check("TC3: Driver B rejects successfully", r, 200,
          lambda j: j["next_driver_found"] is True and j["ride_id"] == ride_id)

    # Verify ride now has Driver C assigned
    r_ride = requests.get(f"{BASE}/rides/{ride_id}", headers=pass_headers)
    check("TC3: Ride now assigned to Driver C", r_ride, 200,
          lambda j: j["driver_id"] == drivers[2]["id"] and j["status"] == "ACCEPTED")

    # =========================================================================
    # TEST CASE 4: All drivers reject -> Ride stays REQUESTED, next_driver_found=False
    # =========================================================================
    print("\n-- TEST CASE 4: Driver C Rejects -> No More Drivers --")
    r = requests.post(f"{BASE}/rides/{ride_id}/reject", headers=drivers[2]["headers"])
    check("TC4: Driver C rejects, next_driver_found is False", r, 200,
          lambda j: j["next_driver_found"] is False and j["ride_id"] == ride_id)

    # Verify ride stays in REQUESTED state with driver_id = None
    r_ride = requests.get(f"{BASE}/rides/{ride_id}", headers=pass_headers)
    check("TC4: Ride stays in REQUESTED state with driver_id=None", r_ride, 200,
          lambda j: j["status"] == "REQUESTED" and j["driver_id"] is None)

    # =========================================================================
    # TEST CASE 5: Rejected drivers are excluded from this ride
    # =========================================================================
    print("\n-- TEST CASE 5: Auto-match Excludes Previously Rejected Drivers --")
    # All 3 drivers are online and available now
    # Try auto-match for this ride -> should NOT match Driver A, B, or C
    r_match = requests.patch(f"{BASE}/rides/{ride_id}/match", headers=pass_headers)
    check("TC5: Matching fails because all drivers previously rejected (404)", r_match, 404)

    # =========================================================================
    # TEST CASE 8: Cannot reject COMPLETED ride -> 400 Bad Request
    # =========================================================================
    print("\n-- TEST CASE 8: Cannot Reject COMPLETED Ride --")
    # Create a fresh ride and assign Driver A
    r = requests.post(f"{BASE}/rides/request", headers=pass_headers, json={
        "pickup_location": "Banjara Hills",
        "dropoff_location": "Jubilee Hills",
        "pickup_latitude": 17.3855,
        "pickup_longitude": 78.4870
    })
    check("Create ride for completion test", r, 201)
    comp_ride_id = r.json()["id"]

    # Start ride
    r = requests.patch(f"{BASE}/rides/{comp_ride_id}/start", headers=drivers[0]["headers"])
    check("Driver A starts ride", r, 200)

    # Complete ride
    r = requests.patch(f"{BASE}/rides/{comp_ride_id}/complete", headers=drivers[0]["headers"])
    check("Driver A completes ride", r, 200)

    # Driver A attempts to reject the completed ride
    r = requests.post(f"{BASE}/rides/{comp_ride_id}/reject", headers=drivers[0]["headers"])
    check("TC8: Cannot reject completed ride (400)", r, 400)

    # =========================================================================
    # TEST CASE 9: Cannot reject CANCELLED ride -> 400 Bad Request
    # =========================================================================
    print("\n-- TEST CASE 9: Cannot Reject CANCELLED Ride --")
    # Create another fresh ride
    r = requests.post(f"{BASE}/rides/request", headers=pass_headers, json={
        "pickup_location": "Gachibowli",
        "dropoff_location": "Hitec City",
        "pickup_latitude": 17.3855,
        "pickup_longitude": 78.4870
    })
    check("Create ride for cancellation test", r, 201)
    canc_ride_id = r.json()["id"]

    # Passenger cancels the ride
    r = requests.patch(f"{BASE}/rides/{canc_ride_id}/cancel", headers=pass_headers)
    check("Passenger cancels ride", r, 200)

    # Driver A attempts to reject the cancelled ride
    r = requests.post(f"{BASE}/rides/{canc_ride_id}/reject", headers=drivers[0]["headers"])
    check("TC9: Cannot reject cancelled ride (400)", r, 400)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    total = len(results)
    passed = sum(results)
    failed = total - passed
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed}/{total} checks PASSED | {failed} FAILED")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("\nALL 10 TEST CASES PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
