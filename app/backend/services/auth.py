from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from config import SESSION_DAYS
from models import AuthSession, User


ROLE_LABELS = {
    "agent": "客服工程师",
    "tech": "技术支持工程师",
    "field": "现场服务工程师",
    "kb_admin": "知识库管理员",
    "supervisor": "服务主管",
    "sys_admin": "系统管理员",
    "customer": "客户联系人",
}


def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        200_000,
    ).hex()
    return digest, salt


def verify_password(password: str, password_hash: str, salt: str):
    digest, _ = hash_password(password, salt)
    return secrets.compare_digest(digest, password_hash)


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "agent",
    must_change_password: bool = False,
    customer_name: str = "",
):
    if role not in ROLE_LABELS:
        raise ValueError("未知角色")
    if role == "customer" and not customer_name.strip():
        raise ValueError("客户联系人必须绑定客户")
    password_hash, salt = hash_password(password)
    user = User(
        username=username.strip(),
        password_hash=password_hash,
        password_salt=salt,
        role=role,
        customer_name=customer_name.strip(),
        active=True,
        must_change_password=must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username.strip()).first()
    if not user or not user.active:
        return None
    if not verify_password(password, user.password_hash, user.password_salt):
        return None
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = AuthSession(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    )
    db.add(session)
    db.commit()
    return token, user


def logout(db: Session, token: str):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db.query(AuthSession).filter(AuthSession.token_hash == token_hash).delete()
    db.commit()


def user_from_token(db: Session, token: str):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == token_hash)
        .first()
    )
    if not session:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def change_password(db: Session, user: User, new_password: str):
    password_hash, salt = hash_password(new_password)
    user.password_hash = password_hash
    user.password_salt = salt
    user.must_change_password = False
    db.commit()


def visible_customer(user) -> str | None:
    """客户方账号只能看自己客户的数据，其他角色不受限。"""
    if user is None:
        return None
    if getattr(user, "role", "") == "customer":
        return user.customer_name
    return None
