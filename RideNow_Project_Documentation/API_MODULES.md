# API Plan

POST /auth/register
POST /auth/login
POST /auth/refresh

GET /users/me
PATCH /users/me

POST /drivers/profile
PATCH /drivers/status
GET /drivers/me/earnings

POST /rides
GET /rides/{ride_id}
POST /rides/{ride_id}/accept
POST /rides/{ride_id}/reject
POST /rides/{ride_id}/start
POST /rides/{ride_id}/complete
GET /rides/history

POST /drivers/location
WS /ws/rides/{ride_id}

POST /fare/estimate
POST /payments/create
POST /payments/verify
POST /ratings

GET /admin/dashboard
GET /admin/users
GET /admin/drivers
GET /admin/rides
GET /admin/revenue
