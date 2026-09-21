# Database Design

users: id, name, email, phone, password_hash, role, created_at

driver_profiles: id, user_id, license_number, status, rating, is_online

vehicles: id, driver_id, vehicle_type, vehicle_number, model

rides: id, rider_id, driver_id, pickup/drop coordinates, status, estimated_fare, final_fare, timestamps

payments: id, ride_id, amount, method, status, transaction_reference

ratings: id, ride_id, from_user_id, to_user_id, rating, review

driver_locations: driver_id, latitude, longitude, updated_at

Relationships:
User → DriverProfile (1:1)
Driver → Vehicles (1:N)
Rider → Rides (1:N)
Driver → Rides (1:N)
Ride → Payment (1:1)
Ride → Ratings (1:N)
