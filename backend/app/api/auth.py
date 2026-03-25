from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependecies import get_current_user
from app.models.user import User
from app.schemas.token import LoginRequest, TokenResponse
from app.schemas.user import UserResponse, UserCreate
from app.services.auth import AuthService

router = APIRouter(prefix="/user", tags=["auth"])
auth_service = AuthService()


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await auth_service.register(user_data, db)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await auth_service.authenticate_user(
        form_data.email, form_data.password, db
    )
    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access = auth_service.create_access_token(result.id)
    refresh = auth_service.create_refresh_token(result.id)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )
    return TokenResponse(access_token=access)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await auth_service.verify_refresh_token(token, db)
    access_token = auth_service.create_access_token(user.id)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"message": "Successfully logged out"}
