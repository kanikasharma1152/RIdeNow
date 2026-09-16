"""
RideNow AI — Additional Controlled Tools
=========================================
Tools for:
- User Profile
- Notifications
- Rating & Reviews
- Payment Status
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_profile_tool(
    current_user,
    db: AsyncSession,
    **kwargs,
) -> Dict[str, Any]:
    """Retrieve the authenticated user's profile information."""
    try:
        return {
            "success": True,
            "user_id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "phone": current_user.phone,
            "role": current_user.role,
            "created_at": str(current_user.created_at) if hasattr(current_user, "created_at") else None,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def get_notifications_tool(
    current_user,
    db: AsyncSession,
    limit: int = 5,
    **kwargs,
) -> Dict[str, Any]:
    """Retrieve recent notifications and unread alert count for the user."""
    from app.services.notification import get_notifications, get_notification_unread_count
    try:
        notifs = await get_notifications(db, current_user.id)
        unread_count = await get_notification_unread_count(db, current_user.id)
        items = []
        for n in notifs[:limit]:
            items.append({
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": str(n.created_at)[:16] if n.created_at else None,
            })
        return {
            "success": True,
            "unread_count": unread_count,
            "total": len(notifs),
            "notifications": items,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def mark_notification_read_tool(
    current_user,
    db: AsyncSession,
    notification_id: Optional[int] = None,
    mark_all: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """Mark a specific notification or all notifications as read."""
    from app.services.notification import read_notification, mark_all_read
    try:
        if mark_all or notification_id is None:
            updated = await mark_all_read(db, current_user.id)
            return {"success": True, "message": "All notifications marked as read.", "updated_count": updated}
        else:
            await read_notification(db, current_user.id, notification_id)
            return {"success": True, "message": f"Notification #{notification_id} marked as read."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def get_rating_tool(
    current_user,
    db: AsyncSession,
    ride_id: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Get rating details: for drivers, returns rating score & reviews; for passengers, returns ride rating."""
    try:
        if current_user.role == "driver":
            from app.repositories.driver import get_driver_by_user_id
            from app.repositories.ratings import get_driver_ratings
            driver = await get_driver_by_user_id(db, current_user.id)
            if not driver:
                return {"success": False, "error": "Driver profile not found."}
            ratings = await get_driver_ratings(db, driver.id)
            if not ratings:
                return {
                    "success": True,
                    "average_rating": 5.0,
                    "total_ratings": 0,
                    "message": "You have not received any ratings yet. Default rating is 5.0.",
                }
            avg = sum(r.rating for r in ratings) / len(ratings)
            recent = [{"rating": r.rating, "comment": r.comment, "date": str(r.created_at)[:10]} for r in ratings[:3]]
            return {
                "success": True,
                "average_rating": round(avg, 2),
                "total_ratings": len(ratings),
                "recent_reviews": recent,
            }
        else:
            # Passenger: check ride rating
            from app.repositories.ratings import get_rating_by_ride
            if ride_id:
                r = await get_rating_by_ride(db, ride_id)
                if r and getattr(r, "passenger_id", None) != current_user.id:
                    return {"success": False, "error": "You are not allowed to view this rating."}
                if r:
                    return {
                        "success": True,
                        "ride_id": ride_id,
                        "rating": r.rating,
                        "comment": r.comment,
                    }
                return {"success": True, "ride_id": ride_id, "rated": False, "message": "This ride has not been rated yet."}
            return {
                "success": True,
                "message": "Passengers can rate any completed ride from 1 to 5 stars on the ride details page.",
            }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def get_payment_status_tool(
    current_user,
    db: AsyncSession,
    ride_id: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Check payment and fare settlement status for an active or completed ride."""
    from app.services.ride import get_passenger_rides, get_driver_rides
    try:
        if current_user.role == "driver":
            rides = await get_driver_rides(db, current_user.id)
        else:
            rides = await get_passenger_rides(db, current_user.id)
        rides_list = rides if isinstance(rides, list) else getattr(rides, "items", [])

        target_ride = None
        if ride_id:
            target_ride = next((r for r in rides_list if r.id == ride_id), None)
        if not target_ride:
            # Check most recent ride
            target_ride = rides_list[0] if rides_list else None

        if not target_ride:
            return {"success": True, "message": "No ride records found to check payment status."}

        is_settled = target_ride.status == "COMPLETED"
        return {
            "success": True,
            "ride_id": target_ride.id,
            "fare": float(target_ride.fare) if target_ride.fare else 0.0,
            "status": target_ride.status,
            "payment_settled": is_settled,
            "payment_method": "Cash / UPI supported",
            "message": f"Ride #{target_ride.id} fare is ₹{target_ride.fare}. Status: {target_ride.status}.",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
