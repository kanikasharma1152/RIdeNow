"""
RideNow Realistic Demo Seed Data Generator — Phase 8
=====================================================
Generates realistic, reproducible demonstration seed data:
- Admin user: admin@ridenow.test
- Demo driver: driver@ridenow.test
- Demo passenger: passenger@ridenow.test
- Configurable scale: defaults to a fast testing set (50 passengers, 15 drivers, 100 rides)
  or full scale when run with --scale full (500 passengers, 100 drivers, 5,000 rides)
- Safe domain: @example.test / @ridenow.test
- Realistic Indian names, city landmarks, vehicle models, and fare amounts

Usage:
  python scripts/seed_demo.py [--scale quick|full]
"""

import sys
import os
import random
import argparse
import asyncio
from datetime import datetime, timedelta

# Ensure backend root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.driver import Driver
from app.models.ride import Ride
from app.services.user import hash_password

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna",
    "Ishaan", "Shaurya", "Dhruv", "Kabir", "Rudra", "Ananya", "Diya", "Saanvi", "Aadhya",
    "Pari", "Myra", "Anika", "Navya", "Riya", "Avani", "Ira", "Prisha", "Tanvi", "Kavya",
    "Rajesh", "Suresh", "Ramesh", "Pooja", "Neha", "Rohit", "Priya", "Sunil", "Anita", "Vikram"
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Reddy", "Kumar", "Singh", "Yadav", "Joshi",
    "Nair", "Iyer", "Rao", "Chopra", "Malhotra", "Mehta", "Bhat", "Deshmukh", "Kulkarni"
]

LOCATIONS = [
    {"name": "Indiranagar 100ft Road", "lat": 12.9784, "lon": 77.6408},
    {"name": "Koramangala Sony World Signal", "lat": 12.9352, "lon": 77.6245},
    {"name": "Whitefield ITPL Main Gate", "lat": 12.9866, "lon": 77.7380},
    {"name": "MG Road Metro Station", "lat": 12.9756, "lon": 77.6066},
    {"name": "KIAL Kempegowda Airport Terminal 1", "lat": 13.1986, "lon": 77.7066},
    {"name": "Electronic City Phase 1 Toll", "lat": 12.8399, "lon": 77.6770},
    {"name": "HSR Layout Sector 2 BDA Complex", "lat": 12.9116, "lon": 77.6389},
    {"name": "Jayanagar 4th Block Shopping Complex", "lat": 12.9299, "lon": 77.5824},
    {"name": "Hebbal Flyover Junction", "lat": 13.0358, "lon": 77.5970},
    {"name": "Malleshwaram 8th Cross", "lat": 13.0031, "lon": 77.5703},
]

VEHICLES = [
    ("sedan", "Honda City", "KA-01-AB-"),
    ("sedan", "Hyundai Verna", "KA-03-CD-"),
    ("hatchback", "Maruti Swift", "KA-04-EF-"),
    ("hatchback", "Tata Tiago", "KA-05-GH-"),
    ("suv", "Toyota Innova Crysta", "KA-02-IJ-"),
    ("suv", "Mahindra XUV700", "KA-51-KL-"),
    ("auto", "Bajaj Compact 4S", "KA-01-F-"),
]

STATUSES = ["COMPLETED", "COMPLETED", "COMPLETED", "CANCELLED", "REQUESTED"]


async def seed_data(scale: str = "quick"):
    print(f"[*] Starting RideNow Demo Seed Generator (Scale: {scale.upper()})...")

    # Counts based on scale
    if scale == "full":
        num_passengers = 500
        num_drivers = 100
        num_rides = 5000
    else:
        num_passengers = 40
        num_drivers = 15
        num_rides = 100

    async with AsyncSessionLocal() as db:
        # Pre-hash shared password for demo accounts
        demo_pwd_hash = hash_password("DemoPass123!")

        # 1. Ensure Core Demo Users exist
        core_accounts = [
            ("Admin User", "admin@ridenow.test", "9999900001", "admin"),
            ("Demo Driver", "driver@ridenow.test", "9999900002", "driver"),
            ("Demo Passenger", "passenger@ridenow.test", "9999900003", "passenger"),
        ]

        for name, email, phone, role in core_accounts:
            q = await db.execute(select(User).where(User.email == email))
            existing = q.scalar_one_or_none()
            if not existing:
                u = User(
                    name=name,
                    email=email,
                    phone=phone,
                    password_hash=demo_pwd_hash,
                    role=role,
                    is_active=True,
                )
                db.add(u)
                await db.flush()

                if role == "driver":
                    drv = Driver(
                        user_id=u.id,
                        license_number="DL-CORE-0001",
                        vehicle_type="sedan",
                        vehicle_number="KA-01-RN-9999",
                        vehicle_model="Toyota Camry Hybrid",
                        is_online=True,
                        is_available=True,
                        latitude=12.9716,
                        longitude=77.5946,
                        location_updated_at=datetime.utcnow(),
                    )
                    db.add(drv)

        await db.commit()
        print("[+] Core demo accounts created (admin, driver, passenger).")

        # 2. Seed Passengers
        passengers = []
        for i in range(1, num_passengers + 1):
            email = f"rider{i}_{random.randint(100, 9999)}@example.test"
            q = await db.execute(select(User).where(User.email == email))
            if not q.scalar_one_or_none():
                fn = random.choice(FIRST_NAMES)
                ln = random.choice(LAST_NAMES)
                p = User(
                    name=f"{fn} {ln}",
                    email=email,
                    phone=f"98{random.randint(10000000, 99999999)}",
                    password_hash=demo_pwd_hash,
                    role="passenger",
                    is_active=True,
                )
                db.add(p)
                passengers.append(p)

        await db.flush()
        print(f"[+] Generated {len(passengers)} passengers.")

        # 3. Seed Drivers
        drivers = []
        for i in range(1, num_drivers + 1):
            email = f"driver{i}_{random.randint(100, 9999)}@example.test"
            q = await db.execute(select(User).where(User.email == email))
            if not q.scalar_one_or_none():
                fn = random.choice(FIRST_NAMES)
                ln = random.choice(LAST_NAMES)
                u = User(
                    name=f"{fn} {ln}",
                    email=email,
                    phone=f"97{random.randint(10000000, 99999999)}",
                    password_hash=demo_pwd_hash,
                    role="driver",
                    is_active=True,
                )
                db.add(u)
                await db.flush()

                v_type, v_model, v_prefix = random.choice(VEHICLES)
                loc = random.choice(LOCATIONS)
                drv = Driver(
                    user_id=u.id,
                    license_number=f"DL-{random.randint(1000000, 9999999)}",
                    vehicle_type=v_type,
                    vehicle_number=f"{v_prefix}{random.randint(1000, 9999)}",
                    vehicle_model=v_model,
                    is_online=random.random() > 0.3,
                    is_available=random.random() > 0.4,
                    latitude=loc["lat"] + random.uniform(-0.02, 0.02),
                    longitude=loc["lon"] + random.uniform(-0.02, 0.02),
                    location_updated_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 120)),
                )
                db.add(drv)
                drivers.append(drv)

        await db.flush()
        print(f"[+] Generated {len(drivers)} drivers with vehicle profiles.")

        # Gather all passenger and driver IDs
        all_passengers_q = await db.execute(select(User.id).where(User.role == "passenger"))
        all_passenger_ids = [row[0] for row in all_passengers_q.all()]

        all_drivers_q = await db.execute(select(Driver.id))
        all_driver_ids = [row[0] for row in all_drivers_q.all()]

        # 4. Seed Rides across the last 30 days
        now = datetime.utcnow()
        rides_to_add = []
        for _ in range(num_rides):
            pid = random.choice(all_passenger_ids)
            did = random.choice(all_driver_ids) if all_driver_ids else None
            pickup = random.choice(LOCATIONS)
            dropoff = random.choice([loc for loc in LOCATIONS if loc["name"] != pickup["name"]])

            dist_km = round(random.uniform(2.5, 32.0), 2)
            fare = round(50.0 + dist_km * 12.0, 2)
            status = random.choice(STATUSES)

            # Random timestamp within last 30 days
            created_at = now - timedelta(
                days=random.randint(0, 29),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )
            started_at = created_at + timedelta(minutes=random.randint(3, 8)) if status in ["STARTED", "COMPLETED"] else None
            completed_at = started_at + timedelta(minutes=int(dist_km * 3)) if status == "COMPLETED" else None

            ride = Ride(
                passenger_id=pid,
                driver_id=did if status != "REQUESTED" else None,
                pickup_location=pickup["name"],
                pickup_latitude=pickup["lat"],
                pickup_longitude=pickup["lon"],
                dropoff_location=dropoff["name"],
                distance_km=dist_km,
                fare=fare if status == "COMPLETED" else None,
                status=status,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
            )
            rides_to_add.append(ride)

        db.add_all(rides_to_add)
        await db.commit()
        print(f"[+] Generated {len(rides_to_add)} rides with realistic lifecycle timestamps.")

    print("[*] Seed data generation complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RideNow Demo Seed Data Generator")
    parser.add_argument("--scale", choices=["quick", "full"], default="quick", help="Data volume scale (quick or full)")
    args = parser.parse_args()

    asyncio.run(seed_data(args.scale))
