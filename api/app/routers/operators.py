"""Operators router (admin only)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from wss_common.db import get_session
from wss_common.enums import TargetStatus
from wss_common.models import User, WssTarget

from app.core.deps import require_admin
from app.core.security import get_password_hash
from app.schemas import UserCreate, UserResponse, UserUpdate, UserWithStats

router = APIRouter()


@router.get("", response_model=list[UserWithStats])
def list_operators(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    users = db.query(User).all()
    result = []
    for user in users:
        completed = (
            db.query(func.count(WssTarget.id))
            .filter(WssTarget.assigned_to == user.id, WssTarget.status == TargetStatus.COMPLETED)
            .scalar()
            or 0
        )
        assigned = (
            db.query(func.count(WssTarget.id))
            .filter(WssTarget.assigned_to == user.id, WssTarget.status == TargetStatus.ASSIGNED)
            .scalar()
            or 0
        )
        result.append(
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "role": user.role.value,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "completed": completed,
                "assigned": assigned,
            }
        )
    return result


@router.post("", response_model=UserResponse)
def create_operator(
    req: UserCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> User:
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    user = User(
        name=req.name,
        username=req.username,
        password_hash=get_password_hash(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_operator(
    user_id: str,
    req: UserUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> User:
    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if req.name is not None:
        user.name = req.name
    if req.password is not None:
        user.password_hash = get_password_hash(req.password)
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.role is not None:
        user.role = req.role

    db.commit()
    db.refresh(user)
    return user
