# Architecture

Rider / Driver / Admin
        ↓
React Frontend
        ↓
REST API + WebSocket
        ↓
FastAPI Backend
        ↓
Service / Business Logic Layer
   ↙          ↓           ↘
PostgreSQL   Redis     External APIs
                         Maps / Payments / Notifications
        ↓
AI/ML Services
        ↓
Analytics / Admin Dashboard

## Backend Services
Auth, User, Driver, Vehicle, Ride, Matching, Location, Fare, Payment, Notification, Rating, Analytics and AI.

## Realtime Flow
Rider requests ride → backend finds nearby drivers → matching ranks drivers → driver accepts → WebSocket sends status → driver location streams → ride starts → ride completes.
