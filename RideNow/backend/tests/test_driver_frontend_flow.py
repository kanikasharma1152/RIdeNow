"""
End-to-End Simulation of Driver Frontend Workflow:
Verifies the exact endpoints, queries, payloads, and response payloads
consumed by the updated React frontend:
1. Driver registers/logs in and fetches profile (for /driver/profile)
2. Driver navigates to /driver/notifications and fetches notifications
3. Driver goes online & available (/drivers/status)
4. Passenger requests ride, auto-matches to Driver
5. Driver Dashboard calls GET /rides/driver/my -> finds matched ride (ACCEPTED)
6. Driver starts ride via PATCH /rides/{id}/start -> status becomes STARTED
7. Driver dashboard polling returns active ride in STARTED state
8. Driver completes ride via PATCH /rides/{id}/complete -> status becomes COMPLETED
9. Driver calls GET /rides/driver/my -> active ride is gone (COMPLETED)
10. Driver checks /rides/driver/my/history -> completed ride appears in history
11. Second ride: Passenger requests, Driver rejects via POST /rides/{id}/reject
12. Driver calls GET /rides/driver/my -> rejected ride is immediately gone
13. Backend assigns next driver
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
print("  FRONTEND DRIVER FLOW & MATCHING E2E VERIFICATION")
print("=" * 65)

# 1. Register Passenger
print("\n-- 1. Setup Passenger --")
pass_email = f"flow_pass_{ts}@test.com"
pass_phone = f"610{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Flow Passenger",
    "email": pass_email,
    "phone": pass_phone,
    "password": "Password@123",
    "role": "passenger"
})
check("Register Passenger", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": pass_email, "password": "Password@123"})
check("Login Passenger", r, 200)
pass_token = r.json().get("access_token")
pass_headers = {"Authorization": f"Bearer {pass_token}"}

# 2. Register Driver A & Driver B
print("\n-- 2. Setup Driver A (Primary) & Driver B (Fallback) --")
# Driver A
drva_email = f"flow_drva_{ts}@test.com"
drva_phone = f"710{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Flow Driver A",
    "email": drva_email,
    "phone": drva_phone,
    "password": "Password@123",
    "role": "driver"
})
check("Register Driver A User", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": drva_email, "password": "Password@123"})
check("Login Driver A", r, 200)
drva_token = r.json().get("access_token")
drva_headers = {"Authorization": f"Bearer {drva_token}"}

r = requests.post(f"{BASE}/drivers/register", headers=drva_headers, json={
    "license_number": f"LICA_{ts}",
    "vehicle_type": "sedan",
    "vehicle_number": f"VEHA_{ts[-6:]}",
    "vehicle_model": "Toyota Etios"
})
check("Register Driver A Profile", r, 201)
drva_id = r.json().get("id")

# Driver B
drvb_email = f"flow_drvb_{ts}@test.com"
drvb_phone = f"810{ts[-7:]}"
r = requests.post(f"{BASE}/users/register", json={
    "name": "Flow Driver B",
    "email": drvb_email,
    "phone": drvb_phone,
    "password": "Password@123",
    "role": "driver"
})
check("Register Driver B User", r, 201)

r = requests.post(f"{BASE}/users/login", data={"username": drvb_email, "password": "Password@123"})
check("Login Driver B", r, 200)
drvb_token = r.json().get("access_token")
drvb_headers = {"Authorization": f"Bearer {drvb_token}"}

r = requests.post(f"{BASE}/drivers/register", headers=drvb_headers, json={
    "license_number": f"LICB_{ts}",
    "vehicle_type": "sedan",
    "vehicle_number": f"VEHB_{ts[-6:]}",
    "vehicle_model": "Hyundai Aura"
})
check("Register Driver B Profile", r, 201)
drvb_id = r.json().get("id")

# Position Driver A at 17.385, 78.486 (nearest)
requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=drva_headers)
requests.patch(f"{BASE}/drivers/location", headers=drva_headers, json={"latitude": 17.385, "longitude": 78.486})

# Position Driver B at 17.390, 78.490 (second nearest)
requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=drvb_headers)
requests.patch(f"{BASE}/drivers/location", headers=drvb_headers, json={"latitude": 17.390, "longitude": 78.490})

# 3. Test Driver Profile page backend API (used on /driver/profile)
print("\n-- 3. Driver Profile Navigation & API (/driver/profile) --")
r = requests.get(f"{BASE}/drivers/me/profile", headers=drva_headers)
check("GET /drivers/me/profile returns authenticated driver vehicle info", r, 200, lambda j: (
    j.get("vehicle_model") == "Toyota Etios" and
    j.get("vehicle_type") == "sedan"
))

# 4. Test Driver Notifications page backend API (used on /driver/notifications)
print("\n-- 4. Driver Notifications Navigation & API (/driver/notifications) --")
r = requests.get(f"{BASE}/notifications", headers=drva_headers)
check("GET /notifications returns driver notifications list", r, 200, lambda j: isinstance(j, list))

r = requests.get(f"{BASE}/notifications/unread-count", headers=drva_headers)
check("GET /notifications/unread-count returns badge count", r, 200, lambda j: "count" in j)

# 5. Passenger requests a ride -> Backend matches Driver A
print("\n-- 5. Passenger Requests Ride -> Auto-matched to Driver A --")
r = requests.post(f"{BASE}/rides/request", headers=pass_headers, json={
    "pickup_location": "Charminar, Hyderabad",
    "dropoff_location": "Golconda Fort, Hyderabad",
    "pickup_latitude": 17.38501,
    "pickup_longitude": 78.48601
})
check("Passenger requests ride (auto-matched to Driver A)", r, 201, lambda j: (
    j.get("status") == "ACCEPTED" and j.get("driver_id") == drva_id
))
ride1_id = r.json().get("id")

# 6. Driver Dashboard fetches assigned rides via GET /rides/driver/my
print("\n-- 6. Driver Dashboard active ride detection (GET /rides/driver/my) --")
r = requests.get(f"{BASE}/rides/driver/my", headers=drva_headers)
check("GET /rides/driver/my contains assigned ride in ACCEPTED state", r, 200, lambda j: any(
    ride["id"] == ride1_id and ride["status"] == "ACCEPTED" for ride in j
))

# 7. Driver clicks "Start Ride" on Dashboard -> PATCH /rides/{id}/start
print("\n-- 7. Driver starts ride from Dashboard (PATCH /rides/{id}/start) --")
r = requests.patch(f"{BASE}/rides/{ride1_id}/start", headers=drva_headers)
check("Driver starts ride -> status becomes STARTED", r, 200, lambda j: j.get("status") == "STARTED")

# Driver dashboard polling: active ride now in STARTED state
r = requests.get(f"{BASE}/rides/driver/my", headers=drva_headers)
check("Driver dashboard polling finds active ride in STARTED state", r, 200, lambda j: any(
    ride["id"] == ride1_id and ride["status"] == "STARTED" for ride in j
))

# 8. Driver clicks "Complete Ride" on Dashboard -> PATCH /rides/{id}/complete
print("\n-- 8. Driver completes ride from Dashboard (PATCH /rides/{id}/complete) --")
r = requests.patch(f"{BASE}/rides/{ride1_id}/complete", headers=drva_headers)
check("Driver completes ride -> status becomes COMPLETED", r, 200, lambda j: j.get("status") == "COMPLETED")

# 9. Verify Driver active ride is now cleared, and ride is in History
print("\n-- 9. Active ride cleared & appears in Driver History --")
r = requests.get(f"{BASE}/rides/driver/my", headers=drva_headers)
# In my_rides, none of the rides are active anymore
check("Active ride cleared from active states", r, 200, lambda j: not any(
    ride["id"] == ride1_id and ride["status"] in ["REQUESTED", "ACCEPTED", "STARTED"] for ride in j
))

# Check Driver History (/driver/rides)
r = requests.get(f"{BASE}/rides/driver/my/history?page=1&page_size=10", headers=drva_headers)
check("Completed ride appears in Driver History (/driver/rides)", r, 200, lambda j: any(
    ride["id"] == ride1_id and ride["status"] == "COMPLETED" for ride in j.get("items", [])
))

# 10. Test Driver Rejection flow
print("\n-- 10. Ride Rejection flow (POST /rides/{id}/reject) --")
# Make Driver A online & available again
requests.patch(f"{BASE}/drivers/status?is_online=true&is_available=true", headers=drva_headers)
requests.patch(f"{BASE}/drivers/location", headers=drva_headers, json={"latitude": 17.385, "longitude": 78.486})

# Passenger requests second ride (matches Driver A)
r = requests.post(f"{BASE}/rides/request", headers=pass_headers, json={
    "pickup_location": "Salar Jung Museum",
    "dropoff_location": "Mecca Masjid",
    "pickup_latitude": 17.38502,
    "pickup_longitude": 78.48602
})
check("Passenger requests second ride (matched to Driver A)", r, 201, lambda j: (
    j.get("status") == "ACCEPTED" and j.get("driver_id") == drva_id
))
ride2_id = r.json().get("id")

# Driver A clicks "Decline" -> POST /rides/{id}/reject
r = requests.post(f"{BASE}/rides/{ride2_id}/reject", headers=drva_headers)
check("Driver A rejects ride -> next driver re-matched", r, 200, lambda j: j.get("next_driver_found") is True)

# Driver A dashboard polling: ride2 is no longer assigned to Driver A
r = requests.get(f"{BASE}/rides/driver/my", headers=drva_headers)
check("Ride 2 is immediately removed from Driver A's assigned rides", r, 200, lambda j: not any(
    ride["id"] == ride2_id for ride in j
))

# Driver B dashboard polling: ride2 is now assigned to Driver B
r = requests.get(f"{BASE}/rides/driver/my", headers=drvb_headers)
check("Ride 2 is now automatically assigned to Driver B", r, 200, lambda j: any(
    ride["id"] == ride2_id and ride["status"] == "ACCEPTED" for ride in j
))

# -------------------------------------------------------------
# SUMMARY
# -------------------------------------------------------------
total = len(results)
passed = sum(results)
failed = total - passed
print("\n" + "=" * 65)
print(f"  FLOW VERIFICATION:  {passed}/{total} passed  |  {failed} failed")
print("=" * 65)

if failed > 0:
    sys.exit(1)
print("\nALL DRIVER FRONTEND FLOW CHECKS PASSED SUCCESSFULLY!")
