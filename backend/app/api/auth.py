from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import UserResponse, UserCreate
from app.services.auth import AuthService

router = APIRouter(prefix="/user", tags=["auth"])
auth_service = AuthService()

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(user_data, db)

