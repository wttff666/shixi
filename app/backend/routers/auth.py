from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user
from services.auth import ROLE_LABELS, change_password, login, logout
from services.audit import record_audit


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class PasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=200)


def user_view(user):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "customer_name": user.customer_name,
        "must_change_password": user.must_change_password,
    }


@router.post("/login")
def auth_login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    result = login(db, request.username, request.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, user = result
    record_audit(
        db,
        user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
    )
    response.set_cookie(
        "diag_token",
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return {"token": token, "user": user_view(user)}


@router.post("/logout")
def auth_logout(
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if authorization and authorization.lower().startswith("bearer "):
        logout(db, authorization.split(" ", 1)[1].strip())
    record_audit(
        db,
        user_id=None,
        action="auth.logout",
    )
    response.delete_cookie("diag_token", path="/")
    return {"ok": True}


@router.get("/me")
def auth_me(user=Depends(get_current_user)):
    return user_view(user)


@router.post("/change-password")
def auth_change_password(
    request: PasswordRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, user, request.password)
    record_audit(
        db,
        user_id=user.id,
        action="auth.change_password",
        entity_type="user",
        entity_id=user.id,
    )
    return {"ok": True}
