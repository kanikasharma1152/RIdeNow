import pytest
from app.ai.tools.registry import execute_tool, get_available_tools_for_role


class FakeUser:
    def __init__(self, id, role, name="Test User"):
        self.id = id
        self.role = role
        self.name = name


@pytest.mark.asyncio
async def test_estimate_fare_tool():
    res = await execute_tool(
        tool_name="estimate_fare",
        tool_args={"distance_km": 10.0},
        current_user=FakeUser(1, "passenger"),
        db=None,
    )
    assert res["success"] is True
    # Base 50 + 10*12 = 170
    assert res["estimated_fare"] == "₹170.00"
    assert res["distance_km"] == 10.0


@pytest.mark.asyncio
async def test_search_policies_tool():
    res = await execute_tool(
        tool_name="search_policies_and_faq",
        tool_args={"query": "cancellation fee"},
        current_user=FakeUser(1, "passenger"),
        db=None,
    )
    assert res["success"] is True
    assert res["results_count"] > 0
    assert "cancellation" in res["context"].lower() or "policy" in res["context"].lower()


@pytest.mark.asyncio
async def test_role_security_enforcement():
    # Passenger cannot call driver earnings tool
    res = await execute_tool(
        tool_name="get_driver_earnings",
        tool_args={},
        current_user=FakeUser(1, "passenger"),
        db=None,
    )
    assert res["success"] is False
    assert "Permission denied" in res["error"]
