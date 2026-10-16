from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from deps import require_roles
from models import AuthSession, User
from schemas import PasswordReset, UserCreate, UserOut, UserUpdate
from services.audit import record_audit
from services.auth import ROLE_LABELS, create_user, hash_password


router = APIRouter(
    prefix="/api/admin",
    tags=["users"],
    dependencies=[Depends(require_roles("sys_admin"))],
)


def user_view(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "customer_name": user.customer_name,
        "active": user.active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
    }


def get_user(db: Session, user_id: int):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def revoke_sessions(db: Session, user_id: int):
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return [user_view(user) for user in users]


@router.post("/users", response_model=UserOut)
def add_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    current=Depends(require_roles("sys_admin")),
):
    if request.role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="未知角色")
    existing = db.query(User).filter(User.username == request.username.strip()).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = create_user(
        db,
        request.username,
        request.password,
        role=request.role,
        must_change_password=True,
        customer_name=request.customer_name,
    )
    record_audit(
        db,
        user_id=current.id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        detail={"username": user.username, "role": user.role},
    )
    return user_view(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    request: UserUpdate,
    db: Session = Depends(get_db),
    current=Depends(require_roles("sys_admin")),
):
    user = get_user(db, user_id)
    if user.id == current.id and request.active is False:
        raise HTTPException(status_code=400, detail="不能停用当前登录账号")
    if request.role is not None:
        if request.role not in ROLE_LABELS:
            raise HTTPException(status_code=400, detail="未知角色")
        user.role = request.role
    if request.active is not None:
        user.active = request.active
        if not request.active:
            revoke_sessions(db, user.id)
    if request.customer_name is not None:
        user.customer_name = request.customer_name.strip()
    db.commit()
    db.refresh(user)
    record_audit(
        db,
        user_id=current.id,
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        detail={"role": user.role, "active": user.active},
    )
    return user_view(user)


@router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int,
    request: PasswordReset,
    db: Session = Depends(get_db),
    current=Depends(require_roles("sys_admin")),
):
    user = get_user(db, user_id)
    password_hash, salt = hash_password(request.password)
    user.password_hash = password_hash
    user.password_salt = salt
    user.must_change_password = True
    revoke_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    record_audit(
        db,
        user_id=current.id,
        action="user.reset_password",
        entity_type="user",
        entity_id=user.id,
    )
    return user_view(user)


@router.post("/users/{user_id}/logout")
def force_logout(
    user_id: int,
    db: Session = Depends(get_db),
    current=Depends(require_roles("sys_admin")),
):
    user = get_user(db, user_id)
    revoke_sessions(db, user.id)
    db.commit()
    record_audit(
        db,
        user_id=current.id,
        action="user.force_logout",
        entity_type="user",
        entity_id=user.id,
    )
    return {"ok": True}
