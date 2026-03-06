"""Auth & User Management Routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from database import get_db
from models import User, UserRole
from schemas import (
    LoginRequest, PinLoginRequest, TokenResponse,
    UserCreate, UserUpdate, UserResponse
)
from dependencies import (
    get_current_user, require_admin, log_audit,
    hash_password, verify_password, create_token
)

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")

    token = create_token(user.id, user.username, user.role)
    await log_audit(db, user, "login", "user", user.id)

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name
        }
    )


@router.post("/auth/pin-login", response_model=TokenResponse)
async def pin_login(data: PinLoginRequest, db: AsyncSession = Depends(get_db)):
    """Quick PIN login for staff"""
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()

    for user in users:
        if user.pin_hash and verify_password(data.pin, user.pin_hash):
            token = create_token(user.id, user.username, user.role)
            await log_audit(db, user, "pin_login", "user", user.id)
            return TokenResponse(
                access_token=token,
                user={
                    "id": user.id,
                    "username": user.username,
                    "role": user.role,
                    "display_name": user.display_name
                }
            )

    raise HTTPException(status_code=401, detail="Invalid PIN")


@router.get("/auth/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name, is_active=user.is_active,
        created_at=user.created_at
    )


# ===== User Management (Admin Only) =====

@router.get("/users", response_model=List[UserResponse])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [UserResponse(
        id=u.id, username=u.username, role=u.role,
        display_name=u.display_name, is_active=u.is_active, created_at=u.created_at
    ) for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        pin_hash=hash_password(data.pin) if data.pin else None,
        role=data.role,
        display_name=data.display_name
    )
    db.add(user)
    await db.flush()
    await log_audit(db, admin, "create_user", "user", user.id, {"username": data.username})

    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name, is_active=user.is_active, created_at=user.created_at
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.pin is not None:
        user.pin_hash = hash_password(data.pin)

    await db.flush()
    await log_audit(db, admin, "update_user", "user", user_id)

    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        display_name=user.display_name, is_active=user.is_active, created_at=user.created_at
    )


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    await db.execute(delete(User).where(User.id == user_id))
    await log_audit(db, admin, "delete_user", "user", user_id, {"username": user.username})
    return {"message": "User deleted"}
