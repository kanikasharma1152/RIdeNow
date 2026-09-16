"""
Centralized custom exceptions for RideNow.

All domain-level errors are defined here so that:
- Error codes are consistent.
- Routers can catch specific exceptions instead of bare ValueError.
- Global exception handlers can produce a clean JSON response.
"""


class RideNowError(Exception):
    """Base class for all domain exceptions."""
    status_code: int = 400
    error_code: str = "ERROR"

    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code
        super().__init__(message)


# ─── Ride errors ────────────────────────────────────────────────────────────

class RideNotFoundError(RideNowError):
    status_code = 404
    error_code = "RIDE_NOT_FOUND"

    def __init__(self, message: str = "Ride not found"):
        super().__init__(message)


class UnauthorizedRideAccessError(RideNowError):
    status_code = 403
    error_code = "UNAUTHORIZED_RIDE_ACCESS"

    def __init__(self, message: str = "You are not allowed to access this ride"):
        super().__init__(message)


class InvalidRideStateError(RideNowError):
    status_code = 400
    error_code = "INVALID_RIDE_STATE"

    def __init__(self, message: str = "Invalid ride state transition"):
        super().__init__(message)


class RideAlreadyCancelledError(RideNowError):
    status_code = 400
    error_code = "RIDE_ALREADY_CANCELLED"

    def __init__(self, message: str = "Ride is already cancelled"):
        super().__init__(message)


# ─── Driver errors ───────────────────────────────────────────────────────────

class DriverNotFoundError(RideNowError):
    status_code = 404
    error_code = "DRIVER_NOT_FOUND"

    def __init__(self, message: str = "Driver profile not found"):
        super().__init__(message)


class DriverUnavailableError(RideNowError):
    status_code = 400
    error_code = "DRIVER_UNAVAILABLE"

    def __init__(self, message: str = "Driver is not available"):
        super().__init__(message)


class NoAvailableDriverError(RideNowError):
    status_code = 404
    error_code = "NO_AVAILABLE_DRIVER"

    def __init__(self, message: str = "No available drivers found"):
        super().__init__(message)


# ─── Auth errors ─────────────────────────────────────────────────────────────

class AuthenticationError(RideNowError):
    status_code = 401
    error_code = "AUTHENTICATION_FAILED"

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class TokenRevokedError(RideNowError):
    status_code = 401
    error_code = "TOKEN_REVOKED"

    def __init__(self, message: str = "Token has been revoked"):
        super().__init__(message)


# ─── Generic errors ───────────────────────────────────────────────────────────

class DuplicateResourceError(RideNowError):
    status_code = 409
    error_code = "DUPLICATE_RESOURCE"

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message)


class ValidationError(RideNowError):
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class PaymentError(RideNowError):
    status_code = 400
    error_code = "PAYMENT_ERROR"

    def __init__(self, message: str = "Payment error"):
        super().__init__(message)


class RatingError(RideNowError):
    status_code = 400
    error_code = "RATING_ERROR"

    def __init__(self, message: str = "Rating error"):
        super().__init__(message)
