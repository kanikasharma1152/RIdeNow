# 🚗 RideNow — AI-Native Mobility Platform

**Smarter Rides. Safer Journeys. Intelligent Mobility.**

RideNow is a full-stack ride-booking platform designed to connect passengers and drivers through a secure, intelligent, and modern mobility experience. Beyond traditional ride booking, the project explores AI-powered assistance, real-time ride tracking, safety intelligence, and machine-learning-driven mobility features.

<p align="center">
  <a href="https://frontend-lilac-chi-97.vercel.app/"><strong>🌐 Live Application</strong></a> •
  <a href="https://ridenow-uap6.onrender.com/docs"><strong>📚 API Documentation</strong></a> •
  <a href="https://github.com/kanikasharma1152/RIdeNow"><strong>💻 GitHub Repository</strong></a>
</p>

---

## ✨ Overview

RideNow brings together ride booking, driver workflows, authentication, real-time communication, and safety-oriented services in a modular full-stack architecture.

The project is designed to evolve from a conventional ride-booking application into an **AI-assisted mobility platform**, where intelligent services can support ride interactions, safety awareness, and mobility-related decisions.

### Key Highlights

- 🚘 Passenger and driver ride management
- 🔐 JWT authentication and role-based access
- ⚡ Real-time ride updates and WebSocket communication
- 🛡️ Safety features and trusted-contact workflows
- 🤖 AI assistant with tool-based interactions
- 🧠 Retrieval-Augmented Generation (RAG) integration
- 🎙️ Voice-assistant integration modules
- 📊 ML-oriented ETA, demand, anomaly detection, and ride-matching components
- 🗄️ PostgreSQL database with SQLAlchemy and Alembic migrations
- ☁️ Frontend and backend deployment using Vercel and Render

*Feature availability depends on the current codebase, environment configuration, and deployed service status.*

---

## 🧰 Tech Stack

| Category | Technologies |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.x |
| Database Driver | asyncpg |
| Migrations | Alembic |
| Authentication | JWT, password hashing, role-based authorization |
| Real-Time Communication | WebSockets |
| AI Integration | Groq, LLM tool calling |
| RAG | ChromaDB-based components |
| Voice | LiveKit and Cartesia integration modules |
| Maps | Leaflet-based interfaces |
| Supporting Services | Redis integration and fallback paths |
| Deployment | Vercel, Render |
| Containerization | Docker and Docker Compose configuration |

---

## 🚀 Features

### 1. Passenger Experience

- User registration and login.
- Request rides using pickup and destination details.
- View personal rides and their current status.
- Follow ride progress through the ride lifecycle.
- Access ride-sharing and safety-related interfaces.

### 2. Driver Experience

- Driver registration and authentication.
- View available ride requests.
- Accept eligible rides.
- View assigned rides.
- Start trips and manage ride status.

### 3. Ride Lifecycle Management

RideNow manages ride transitions through defined states, including:

`REQUESTED → ACCEPTED → STARTED → COMPLETED`

Eligible rides can also be cancelled according to their current state.

Backend validation helps ensure that ride actions follow the application's allowed workflow.

### 4. Authentication & Authorization

- JWT-based authentication.
- Secure password hashing.
- Role-aware access for passenger, driver, and admin workflows.
- OAuth integration modules for supported providers.

Protected operations are designed to distinguish users according to their roles and permissions.

### 5. Real-Time Ride Experience

- WebSocket-based communication.
- Live ride-status and location-update capabilities.
- Interfaces for following trip progress.
- Real-time tracking components for passenger and driver experiences.

### 6. Safety & Trusted Contacts

RideNow includes safety-focused modules intended to support:

- SOS and emergency workflows.
- Trusted-contact management.
- Ride-sharing through shareable trip links.
- Corridor-deviation detection.
- Prolonged-stop detection.
- Safety center and shared-trip tracking interfaces.

These features require appropriate configuration and testing before use in real-world journeys.

---

## 🤖 AI-Powered Mobility

RideNow explores how AI can improve the ride-booking experience without removing the need for human judgment or reliable application logic.

### AI Assistant

The project includes AI-assistant components designed around:

- Groq-backed language-model integration.
- Tool/function calling for supported ride-related actions.
- Intent handling and fallback behavior.
- Retrieval-Augmented Generation (RAG) using ChromaDB-based components.
- Ride, status, and safety-related assistant capabilities.

### Voice & Vision Integrations

- LiveKit and Cartesia integration modules for voice experiences.
- Vision-related components for image-aware interactions.

External provider credentials and service configuration are required for provider-dependent functionality.

### Machine Learning & Intelligent Services

The codebase includes or explores components for:

- **ETA estimation:** Supporting travel-time estimates.
- **Demand prediction:** Analyzing mobility demand patterns.
- **Anomaly detection:** Identifying unusual ride-related patterns.
- **Driver matching:** Supporting intelligent ride-assignment decisions.

Model accuracy and runtime behavior depend on the implementation, training data, and deployment configuration.

---

## 🏗️ System Architecture

```text
                Passenger / Driver / Admin
                           |
                           v
                    React + Vite UI
                           |
                REST API / WebSockets
                           |
                           v
                    FastAPI Backend
                           |
          ┌────────────────┼────────────────┐
          |                |                |
          v                v                v
     Authentication    Ride Services    Safety Services
          |                |                |
          └────────────────┼────────────────┘
                           |
                ┌──────────┴──────────┐
                |                     |
                v                     v
          PostgreSQL          AI / ML Services
          SQLAlchemy          RAG / Voice / Tools
          Alembic              External Providers
```

The backend is organized into separate application layers to support maintainability, testing, and future feature development.

---

## 📂 Project Structure

The main backend is located under `RideNow/backend`.

```text
RIdeNow/
├── RideNow/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── models/
│   │   │   ├── repositories/
│   │   │   ├── routers/
│   │   │   ├── schemas/
│   │   │   └── services/
│   │   ├── alembic/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── seed_admin.py
│   └── frontend/
├── docker-compose.production.yml
└── README.md
```

*Directory names are illustrative; refer to the current repository for the exact structure.*

---

## 💻 Getting Started

### Prerequisites

- Python 3.11 or a compatible version supported by the project
- Node.js and npm
- PostgreSQL
- Git
- Optional: Docker

### 1. Clone the Repository

```bash
git clone https://github.com/kanikasharma1152/RIdeNow.git
cd RIdeNow
```

### 2. Set Up the Backend

Open PowerShell on Windows:

```powershell
cd "RideNow\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configure the local environment variables using the project's configuration and example files.

Example database URL format:

```dotenv
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://DB_USER:DB_PASSWORD@localhost:5432/ridenow_db
```

Replace the placeholders with your own local database credentials.

### 3. Apply Database Migrations

After verifying that the configured database is the intended development database, run:

```powershell
alembic upgrade head
```

**Important:** Always verify `DATABASE_URL` before running migrations. Do not accidentally apply development commands to the production database.

### 4. Start the Backend

Use the FastAPI application entry point defined in the repository. For example, if the ASGI application is `app.main:app`:

```powershell
uvicorn app.main:app --reload
```

The interactive API documentation will usually be available at:

```text
http://127.0.0.1:8000/docs
```

### 5. Set Up the Frontend

```bash
cd RideNow/frontend
npm install
npm run dev
```

Configure the frontend's API base URL according to its environment configuration.

*If the current branch uses different scripts or an application entry point, follow the repository's configuration.*

---

## 🌐 Deployment

RideNow uses a split-deployment approach:

| Component | Platform |
|---|---|
| Frontend | Vercel |
| Backend API | Render |
| Database | Supabase PostgreSQL |

### Production Checklist

1. Configure required environment variables in the hosting provider.
2. Verify the production database URL, driver, host, port, username, database, and password.
3. Configure JWT signing secrets and token settings securely.
4. Set CORS to the correct frontend origin.
5. Apply database migrations to the intended database.
6. Check the latest application logs after deployment.
7. Test authentication, ride workflows, and database-backed routes.
8. Verify WebSocket and external AI/voice integrations separately.

**Deployment notes:**

- `.env` is intended for local environment configuration.
- `.env.production` is not automatically loaded unless the application or deployment explicitly loads it.
- Render environment variables should be configured in the Render service settings.
- `docker-compose.production.yml` is for a Compose-based workflow when explicitly used; Render does not automatically execute it merely because it exists.
- Never commit real secrets or production connection strings.

---

## 🔒 Security

Security is an important part of RideNow's design.

- Hash passwords before storing them.
- Keep database credentials, API keys, and JWT secrets private.
- Use separate credentials for development and production.
- Rotate secrets that have been exposed.
- Validate authorization for protected endpoints.
- Restrict CORS to trusted frontend origins.
- Avoid exposing sensitive internal errors in API responses.
- Remove passwords, tokens, and connection strings from logs before sharing them.

---

## 🛣️ Future Improvements

Potential areas for continued development include:

- More comprehensive automated integration and end-to-end testing.
- Stronger monitoring and production observability.
- Further improvements to live ride tracking.
- Expanded safety workflows and error handling.
- Evaluation and monitoring of ETA and demand models.
- More comprehensive AI-assistant testing.
- Improved administrative tools and reporting.

These are roadmap ideas unless already implemented and enabled in the current version.

---

## 🤝 Contributing

Contributions and suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Run relevant tests.
5. Keep secrets and local environment files out of commits.
6. Open a pull request with a clear explanation of your changes.

For bug reports, include reproducible steps and sanitized logs.

---

## 📄 License

Add a `LICENSE` file before specifying the project's reuse and redistribution terms. Until a license is included, do not assume that the repository is open source under a particular license.

---

## 🔗 Project Links

- **GitHub Repository:** [kanikasharma1152/RIdeNow](https://github.com/kanikasharma1152/RIdeNow)
- **Live Frontend:** [RideNow Web App](https://frontend-lilac-chi-97.vercel.app/)
- **Backend API:** [RideNow API](https://ridenow-uap6.onrender.com)
- **Swagger Documentation:** [Explore API](https://ridenow-uap6.onrender.com/docs)

---

<p align="center">
  <strong>RideNow — Smarter Rides. Safer Journeys. Intelligent Mobility. 🚗</strong>
</p>
