# RideNow Model Context Protocol (MCP) Server

## Architecture Overview
The RideNow MCP server exposes standard Model Context Protocol interfaces (JSON-RPC 2.0) for tool discovery and execution.
It connects directly to RideNow's existing service and repository layer, ensuring full reuse of business logic, role-based security, and data integrity.

### Components
1. **pp/mcp/config.py**: MCP tool definitions, input schemas, and role permissions.
2. **pp/mcp/server.py**: JSON-RPC 2.0 server supporting initialize, 	ools/list, and 	ools/call.
3. **pp/mcp/client.py**: Async client interface for internal agent and worker invocations.
4. **pp/routers/mcp.py**: FastAPI router exposing /mcp/tools (GET) and /mcp (POST JSON-RPC).

### Exposed Tools
- **Passenger/Common**: get_active_ride, estimate_fare, get_ride_history, get_user_profile, get_notifications, get_payment_status, get_rating
- **Driver**: get_driver_earnings, get_driver_summary, get_route_tip
- **Knowledge Base (RAG)**: search_policies_and_faq

### Security
All MCP tool calls require authenticated user context passed securely from the session. Role-based access control strictly isolates driver telemetry from passengers and prevents IDOR vulnerabilities.
