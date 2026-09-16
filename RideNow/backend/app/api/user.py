from fastapi import APIRouter, Depends

from app.routers.user import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Protected"]
)


@router.get("/protected")
async def protected_route(
    current_user=Depends(get_current_user)
):
    return {
        "message": "Authentication successful",
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role
    }