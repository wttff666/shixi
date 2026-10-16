from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from services.auth import user_from_token


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    token = request.cookies.get("diag_token", "")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    user = user_from_token(db, token)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return user


def require_roles(*roles: str):
    def dependency(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="没有权限执行此操作")
        return user

    return dependency
