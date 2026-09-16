"""
Regression and Integration Tests for AI Chat & MCP Server
=========================================================
Tests:
1. AI chat UI hygiene: no internal tool names or Action: leaks.
2. Hard iteration cap in tool loop.
3. Notification deduplication on ride completion.
4. MCP tool listing and schema inspection.
5. MCP tool execution with authorization enforcement.
6. JSON-RPC 2.0 initialize, tools/list, and tools/call.
"""

import pytest
import asyncio
from starlette.testclient import TestClient
from app.main import app
from app.routers.user import get_current_user
from app.mcp.server import mcp_server
from app.mcp.client import mcp_client
from app.models.user import User


class MockUser:
    def __init__(self, user_id=1, role="passenger", name="Test Passenger"):
        self.id = user_id
        self.role = role
        self.name = name
        self.email = f"{role}@test.com"
        self.is_active = True


def test_mcp_tools_list_schema():
    """Verify MCP tools/list returns compliant schemas for passenger."""
    passenger = MockUser(user_id=1, role="passenger")
    tools = mcp_server.list_tools(current_user=passenger)
    tool_names = [t["name"] for t in tools]
    
    assert "get_active_ride" in tool_names
    assert "estimate_fare" in tool_names
    assert "get_ride_history" in tool_names
    assert "search_policies_and_faq" in tool_names
    assert "get_user_profile" in tool_names
    # Driver-only tools should NOT be available to passenger
    assert "get_driver_earnings" not in tool_names


def test_mcp_tools_list_driver():
    """Verify MCP tools/list includes driver-specific tools for driver role."""
    driver = MockUser(user_id=2, role="driver", name="Test Driver")
    tools = mcp_server.list_tools(current_user=driver)
    tool_names = [t["name"] for t in tools]
    
    assert "get_driver_earnings" in tool_names
    assert "get_driver_summary" in tool_names
    assert "get_route_tip" in tool_names


def test_mcp_jsonrpc_initialize():
    """Verify MCP server JSON-RPC 2.0 initialize handshake."""
    client = TestClient(app)
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    assert data["result"]["serverInfo"]["name"] == "ridenow-mobility-mcp"


def test_mcp_jsonrpc_tools_list_endpoint():
    """Verify /mcp/tools HTTP GET endpoint returns tool list."""
    client = TestClient(app)
    response = client.get("/mcp/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) > 0


def test_ai_chat_response_hygiene():
    """Verify that chat responses never contain Action: or internal tool function names in reply."""
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    client = TestClient(app)

    queries = [
        "What is my active ride?",
        "Estimate fare for 15 km",
        "What is the cancellation policy?",
        "Tell me a short taxi joke.",
    ]

    for q in queries:
        res = client.post(
            "/chat/message",
            json={"message": q},
            headers={"Authorization": "Bearer fake-token"},
        )
        assert res.status_code == 200
        reply = res.json().get("reply", "")
        # Absolutely NO leaked Action: or svgAction:
        assert "Action:" not in reply
        assert "svgAction:" not in reply
        assert "tool_call_id" not in reply
        assert "arguments" not in reply

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_notification_deduplication_model_logic():
    """Verify notification deduplication logic: query before insert returns existing match."""
    from unittest.mock import AsyncMock, MagicMock
    from app.repositories.notification import create_notification
    from app.models.notification import Notification

    mock_db = AsyncMock()
    existing_notif = Notification(
        id=42,
        user_id=10,
        ride_id=20,
        title="Ride Completed",
        message="Completed fare ₹150",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = existing_notif
    mock_db.execute.return_value = mock_result

    # Call create_notification with matching ride_id
    result = await create_notification(
        db=mock_db,
        user_id=10,
        title="Ride Completed",
        message="Completed fare ₹150",
        ride_id=20,
    )

    # Must return existing notification without calling db.add
    assert result.id == 42
    assert result.title == "Ride Completed"
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_call_tool_driver_authorization():
    """Verify MCP server rejects unauthorized role access to driver earnings."""
    passenger = MockUser(user_id=1, role="passenger")
    res = await mcp_server.call_tool(
        tool_name="get_driver_earnings",
        arguments={},
        current_user=passenger,
        db=None,
    )
    assert res["isError"] is True
    assert "Permission denied" in res["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_driver_earnings_tool_dict_compatibility():
    """Verify get_driver_earnings_tool correctly reads dictionary stats without AttributeError."""
    from unittest.mock import patch, AsyncMock
    from decimal import Decimal
    from app.ai.tools.driver_tools import get_driver_earnings_tool

    driver = MockUser(user_id=2, role="driver", name="Test Driver")
    fake_stats = {
        "total_rides": 12,
        "cancelled_rides": 1,
        "total_earnings": Decimal("4850.50"),
        "today_earnings": Decimal("750.00"),
        "week_earnings": Decimal("2400.00"),
        "month_earnings": Decimal("4850.50"),
        "average_fare": Decimal("404.21"),
    }

    with patch("app.ai.tools.driver_tools.get_driver_earnings", new=AsyncMock(return_value=fake_stats)):
        res = await get_driver_earnings_tool(current_user=driver, db=None)

    assert res["success"] is True
    assert res["today_earnings"] == "₹750.00"
    assert res["total_earnings"] == "₹4850.50"
    assert res["week_earnings"] == "₹2400.00"
    assert res["month_earnings"] == "₹4850.50"
    assert res["completed_rides"] == 12
    assert "dict" not in str(res)
    assert "AttributeError" not in str(res)


@pytest.mark.asyncio
async def test_copilot_driver_summary_dict_compatibility():
    """Verify copilot get_driver_summary handles dictionary stats without error."""
    from unittest.mock import patch, AsyncMock
    from decimal import Decimal
    from app.ai.tools.copilot_tools import get_driver_summary

    driver = MockUser(user_id=2, role="driver")
    fake_driver_profile = type("Profile", (), {"id": 2, "is_online": True, "is_available": True})()
    fake_stats = {
        "total_rides": 8,
        "today_earnings": Decimal("520.00"),
        "today_rides": 3,
    }

    with patch("app.services.driver.get_my_driver_profile", new=AsyncMock(return_value=fake_driver_profile)), \
         patch("app.services.ride.get_driver_earnings", new=AsyncMock(return_value=fake_stats)):
        res = await get_driver_summary(current_user=driver, db=None)

    assert res["success"] is True
    assert res["today_earnings"] == "₹520.00"
    assert res["total_completed"] == 8
    assert res["is_online"] is True


@pytest.mark.asyncio
async def test_driver_chat_earnings_natural_response():
    """Verify driver asking 'What are my earnings today?' gets a clean, natural response with zero attribute errors."""
    from unittest.mock import patch, AsyncMock
    from decimal import Decimal

    driver = MockUser(user_id=2, role="driver", name="Ravi Driver")
    fake_stats = {
        "total_rides": 5,
        "cancelled_rides": 0,
        "total_earnings": Decimal("1500.00"),
        "today_earnings": Decimal("450.00"),
        "week_earnings": Decimal("1200.00"),
        "month_earnings": Decimal("1500.00"),
        "average_fare": Decimal("300.00"),
    }

    app.dependency_overrides[get_current_user] = lambda: driver
    client = TestClient(app)

    with patch("app.ai.tools.driver_tools.get_driver_earnings", new=AsyncMock(return_value=fake_stats)):
        res = client.post(
            "/chat/message",
            json={"message": "What are my earnings today?"},
            headers={"Authorization": "Bearer fake-token"},
        )

    app.dependency_overrides.pop(get_current_user, None)

    assert res.status_code == 200
    data = res.json()
    reply = data.get("reply", "")

    # Must contain earnings info
    assert "450" in reply or "Earnings" in reply
    # Must never leak exception or internal object names
    assert "'dict' object has no attribute" not in reply
    assert "AttributeError" not in reply
    assert "Action:" not in reply
    assert "svgAction:" not in reply


@pytest.mark.asyncio
async def test_mcp_call_tool_driver_earnings_authorized():
    """Verify authorized driver calling get_driver_earnings through MCP gets valid result."""
    from unittest.mock import patch, AsyncMock
    from decimal import Decimal

    driver = MockUser(user_id=2, role="driver", name="Ravi Driver")
    fake_stats = {
        "total_rides": 10,
        "cancelled_rides": 0,
        "total_earnings": Decimal("3200.00"),
        "today_earnings": Decimal("600.00"),
        "week_earnings": Decimal("1800.00"),
        "month_earnings": Decimal("3200.00"),
        "average_fare": Decimal("320.00"),
    }

    with patch("app.ai.tools.driver_tools.get_driver_earnings", new=AsyncMock(return_value=fake_stats)):
        res = await mcp_server.call_tool(
            tool_name="get_driver_earnings",
            arguments={},
            current_user=driver,
            db=None,
        )

    assert res["isError"] is False
    content_text = res["content"][0]["text"]
    assert "₹600.00" in content_text
    assert "₹3200.00" in content_text
    assert "AttributeError" not in content_text


@pytest.mark.asyncio
async def test_ride_started_notification_deduplication():
    """A & E: Verify starting a ride creates/returns only ONE Ride Started notification without duplicate inserts."""
    from unittest.mock import AsyncMock, MagicMock
    from app.repositories.notification import create_notification
    from app.models.notification import Notification

    mock_db = AsyncMock()
    existing_notif = Notification(
        id=77,
        user_id=15,
        ride_id=33,
        title="Ride Started",
        message="Your ride has started. Enjoy your trip!",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = existing_notif
    mock_db.execute.return_value = mock_result

    result = await create_notification(
        db=mock_db,
        user_id=15,
        title="Ride Started",
        message="Your ride has started. Enjoy your trip!",
        ride_id=33,
    )

    assert result.id == 77
    assert result.title == "Ride Started"
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_two_different_rides_each_generate_start_notifications():
    """D: Two different rides can still each generate their own Ride Started notification."""
    from unittest.mock import AsyncMock, MagicMock
    from app.repositories.notification import create_notification

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    # No existing notification found for new ride
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    res1 = await create_notification(
        db=mock_db,
        user_id=15,
        title="Ride Started",
        message="Your ride has started. Enjoy your trip!",
        ride_id=101,
    )
    assert mock_db.add.call_count == 1

    res2 = await create_notification(
        db=mock_db,
        user_id=15,
        title="Ride Started",
        message="Your ride has started. Enjoy your trip!",
        ride_id=102,
    )
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_ws_manager_send_ride_event_no_duplicate_dispatch_when_same_user():
    """B & C: Verify send_ride_event deduplicates target user IDs and emits only once when passenger_id == driver_id."""
    from unittest.mock import patch, AsyncMock
    from app.core.connection_manager import ws_manager

    with patch.object(ws_manager, "send_personal_message", new=AsyncMock()) as mock_send:
        await ws_manager.send_ride_event(
            event_type="RIDE_STARTED",
            ride_id=55,
            passenger_user_id=99,
            driver_user_id=99, # Same user ID
            payload={"status": "STARTED"},
        )
        # Must be called exactly ONCE, not twice
        assert mock_send.call_count == 1
        call_args = mock_send.call_args_list[0]
        assert call_args[0][0] == 99
        assert call_args[0][1]["type"] == "RIDE_STARTED"



