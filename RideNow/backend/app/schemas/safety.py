import re
from datetime import datetime
from typing import Optional, Any, List, Dict
from pydantic import BaseModel, ConfigDict, field_validator


def _validate_phone_number(v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Phone number cannot be empty")
    # Allow optional leading +, digits, dashes, spaces, parentheses, length 7 to 20
    if not re.match(r"^\+?[0-9\s\-()]{7,20}$", cleaned):
        raise ValueError("Invalid phone number format. Please provide 7 to 20 digits, optionally prefixed with '+'.")
    return cleaned


class SafetyEventResponse(BaseModel):
    id: int
    ride_id: Optional[int] = None
    user_id: int
    driver_id: Optional[int] = None
    event_type: str
    severity: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    description: Optional[str] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    evidence: Optional[Any] = None
    event_metadata: Optional[Any] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SafetyEventCreate(BaseModel):
    ride_id: Optional[int] = None
    event_type: str = "SAFETY_CONCERN"
    severity: str = "MEDIUM"
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SOSTriggerRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    note: Optional[str] = None
    ride_id: Optional[int] = None


class SOSTriggerResponse(BaseModel):
    success: bool
    event_id: int
    status: str
    severity: str
    message: str
    emergency_services_contacted: bool = False
    disclaimer: str = (
        "RideNow Safety Event created. Note: RideNow does NOT directly contact emergency services "
        "or dispatch police/ambulance. In immediate physical danger, dial 112 / 911 directly."
    )


class DriverSOSRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    note: Optional[str] = None
    ride_id: Optional[int] = None


class TelemetryCheckRequest(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = None
    route_waypoints: Optional[List[List[float]]] = None


class TelemetryCheckResponse(BaseModel):
    safe: bool
    highest_severity: Optional[str] = None
    anomalies: List[dict] = []
    events_created: List[int] = []


class TrustedContactCreate(BaseModel):
    name: str
    phone: str
    relationship: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone_number(v)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Contact name cannot be empty")
        return s


class TrustedContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    relationship: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_phone_number(v)
        return v


class TrustedContactResponse(BaseModel):
    id: int
    user_id: int
    name: str
    phone: str
    relationship: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RideShareCreateResponse(BaseModel):
    share_token: str
    share_url: str
    expires_at: datetime
    share_text: Optional[str] = None
    external_messaging_sent: bool = False
    message: str = "Ride information ready to share. Browser copy/share supported."


class SharedRideStatusResponse(BaseModel):
    ride_id: int
    status: str
    pickup_location: str
    dropoff_location: str
    passenger_name: str
    driver_name: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_latitude: Optional[float] = None
    driver_longitude: Optional[float] = None
    active_safety_alert: bool = False
    safety_status: str = "NORMAL"
    updated_at: datetime


class SafetyCenterResponse(BaseModel):
    has_active_ride: bool = False
    ride_id: Optional[int] = None
    ride_status: Optional[str] = None
    pickup_location: Optional[str] = None
    dropoff_location: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    driver_latitude: Optional[float] = None
    driver_longitude: Optional[float] = None
    eta_minutes: Optional[int] = None
    trusted_contacts: List[TrustedContactResponse] = []
    active_safety_events: List[SafetyEventResponse] = []
    available_actions: List[str] = []
    capability_flags: Dict[str, Any] = {}
    safety_status: str = "NORMAL"


class AdminSafetyMetricsResponse(BaseModel):
    active_sos_count: int
    events_today_count: int
    route_deviations_count: int
    speed_anomalies_count: int
    long_stops_count: int
    unresolved_critical_count: int
    recent_critical_events: List[SafetyEventResponse] = []
