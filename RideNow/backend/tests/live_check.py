"""
Live API verification script for RideNow.
Runs against the live backend at http://127.0.0.1:8000
"""

import sys
import requests
import time

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://127.0.0.1:8000"
PASS_SYM = "[PASS]"
FAIL_SYM = "[FAIL]"

results = []

def check(label, resp, expected_status, key_check=None):
    ok = resp.status_code == expected_status
    if ok and key_check:
        try:
            ok = key_check(resp.json())
        except Exception:
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

# ---- 1. Health ----------------------------------------------------------
print("\n== Health ==")
r = requests.get(f"{BASE}/health")
check("GET /health", r, 200, lambda j: j.get("status") == "healthy")

# ---- 2-5. Passenger auth + profile --------------------------------------
ts = str(int(time.time()))
PASS_EMAIL = f"e2e_passenger_{ts}@test.com"
PASS_PHONE = f"800{ts[-7:]}"

print("\n== Passenger Auth ==")
r = requests.post(f"{BASE}/users/register", json={
    "name": "E2E Passenger",
    "email": PASS_EMAIL,
    "phone": PASS_PHONE,
    "password": "Pass@123",
    "role": "passenger"
})
check("POST /users/register (passenger)", r, 201)

r = requests.post(f"{BASE}/users/login", data={
    "username": PASS_EMAIL,
    "password": "Pass@123"
})
check("POST /users/login (passenger)", r, 200, lambda j: "access_token" in j)
PASS_TOKEN = r.json().get("access_token", "")
PASS_HEADERS = {"Authorization": f"Bearer {PASS_TOKEN}"}

r = requests.get(f"{BASE}/users/me", headers=PASS_HEADERS)
check("GET /users/me", r, 200, lambda j: j.get("email") == PASS_EMAIL)

r = requests.patch(f"{BASE}/users/me", headers=PASS_HEADERS,
                   json={"name": "E2E Passenger Updated"})
check("PATCH /users/me", r, 200, lambda j: j.get("name") == "E2E Passenger Updated")

# ---- 6-13. Driver auth + profile + earnings -----------------------------
DRV_EMAIL = f"e2e_driver_{ts}@test.com"
DRV_PHONE = f"900{ts[-7:]}"

print("\n== Driver Auth & Profile ==")
r = requests.post(f"{BASE}/users/register", json={
    "name": "E2E Driver",
    "email": DRV_EMAIL,
    "phone": DRV_PHONE,
    "password": "Driver@123",
    "role": "driver"
})
check("POST /users/register (driver user)", r, 201)

r = requests.post(f"{BASE}/users/login", data={
    "username": DRV_EMAIL,
    "password": "Driver@123"
})
check("POST /users/login (driver)", r, 200, lambda j: "access_token" in j)
DRV_TOKEN = r.json().get("access_token", "")
DRV_HEADERS = {"Authorization": f"Bearer {DRV_TOKEN}"}

r = requests.post(f"{BASE}/drivers/register", headers=DRV_HEADERS, json={
    "license_number": f"LIC{ts}",
    "vehicle_type": "Sedan",
    "vehicle_number": f"TS{ts[-6:]}",
    "vehicle_model": "Honda City"
})
check("POST /drivers/register", r, 201)

r = requests.patch(
    f"{BASE}/drivers/status?is_online=true&is_available=true",
    headers=DRV_HEADERS
)
check("PATCH /drivers/status (online+available)", r, 200)

r = requests.patch(f"{BASE}/drivers/location", headers=DRV_HEADERS, json={
    "latitude": 17.385044,
    "longitude": 78.486671
})
check("PATCH /drivers/location", r, 200)

r = requests.get(f"{BASE}/drivers/me/profile", headers=DRV_HEADERS)
check("GET /drivers/me/profile", r, 200, lambda j: "id" in j)

r = requests.patch(f"{BASE}/drivers/me", headers=DRV_HEADERS,
                   json={"vehicle_model": "Honda City 2024"})
check("PATCH /drivers/me", r, 200, lambda j: j.get("vehicle_model") == "Honda City 2024")

r = requests.get(f"{BASE}/drivers/earnings", headers=DRV_HEADERS)
check("GET /drivers/earnings", r, 200, lambda j: "total_rides" in j)

# ---- 14-17. Ride lifecycle -----------------------------------------------
print("\n== Ride Lifecycle ==")
r = requests.post(f"{BASE}/rides/request", headers=PASS_HEADERS, json={
    "pickup_location": "Hyderabad Railway Station",
    "dropoff_location": "Charminar, Hyderabad"
})
check("POST /rides/request", r, 201, lambda j: "id" in j)
RIDE_ID = r.json().get("id") if r.status_code == 201 else None

r = requests.get(f"{BASE}/rides/my", headers=PASS_HEADERS)
check("GET /rides/my", r, 200, lambda j: isinstance(j, list))

r = requests.get(f"{BASE}/rides/my/history?page=1&page_size=5", headers=PASS_HEADERS)
check("GET /rides/my/history (paginated)", r, 200,
      lambda j: "items" in j and "total" in j)

r = requests.get(f"{BASE}/rides/driver/my", headers=DRV_HEADERS)
check("GET /rides/driver/my", r, 200, lambda j: isinstance(j, list))

r = requests.get(f"{BASE}/rides/driver/my/history?page=1&page_size=5", headers=DRV_HEADERS)
check("GET /rides/driver/my/history (paginated)", r, 200,
      lambda j: "items" in j and "total" in j)

r = requests.get(f"{BASE}/rides/available", headers=DRV_HEADERS)
check("GET /rides/available (driver online+available)", r, 200,
      lambda j: isinstance(j, list))

if RIDE_ID:
    r = requests.get(f"{BASE}/rides/{RIDE_ID}", headers=PASS_HEADERS)
    check(f"GET /rides/{RIDE_ID}", r, 200)

# ---- 18. Notifications ---------------------------------------------------
print("\n== Notifications ==")
r = requests.get(f"{BASE}/notifications", headers=PASS_HEADERS)
check("GET /notifications", r, 200, lambda j: isinstance(j, list))

r = requests.get(f"{BASE}/notifications/unread-count", headers=PASS_HEADERS)
check("GET /notifications/unread-count", r, 200, lambda j: "count" in j)

# ---- 19-20. Logout + token revocation -----------------------------------
print("\n== Logout & Token Revocation ==")
r = requests.post(f"{BASE}/users/logout", headers=PASS_HEADERS)
check("POST /users/logout", r, 200, lambda j: "message" in j)

r = requests.get(f"{BASE}/users/me", headers=PASS_HEADERS)
check("GET /users/me after logout (expect 401)", r, 401)

# ---- Summary ------------------------------------------------------------
total = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*55}")
print(f"  RESULTS:  {passed}/{total} passed  |  {failed} failed")
print(f"{'='*55}")
if failed > 0:
    sys.exit(1)
