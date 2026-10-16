from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import (
    FRONTEND_DIR,
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USER,
    MODEL_API_KEY,
)
from database import SessionLocal, init_db
from models import User
from routers import (
    admin,
    auth,
    conversations,
    devices,
    diagnosis,
    documents,
    evaluation,
    service_requests,
    skills,
    tasks,
    users,
)
from services.auth import create_user, user_from_token
from services.seed import seed_all
from services.task_runner import mark_running_tasks_failed


DEMO_USERS = [
    ("agent01", "agent_demo_2026", "agent", ""),
    ("tech01", "tech_demo_2026", "tech", ""),
    ("cust01", "cust_demo_2026", "customer", "镇江精工注塑厂"),
]


def seed_initial_admin():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        create_user(
            db,
            INITIAL_ADMIN_USER,
            INITIAL_ADMIN_PASSWORD,
            role="sys_admin",
            must_change_password=True,
        )
        for username, password, role, customer in DEMO_USERS:
            create_user(
                db,
                username,
                password,
                role=role,
                must_change_password=False,
                customer_name=customer,
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    mark_running_tasks_failed()
    seed_initial_admin()
    seed_all()
    yield


app = FastAPI(
    title="设备厂商远程诊断客服平台",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_frontend_cache(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith((".js", ".css", ".html")) or path in (
        "/",
        "/login",
        "/service",
        "/portal",
        "/documents",
        "/skills",
        "/users",
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth.router)
app.include_router(diagnosis.router)
app.include_router(conversations.router)
app.include_router(devices.router)
app.include_router(documents.router)
app.include_router(service_requests.router)
app.include_router(skills.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(evaluation.router)


@app.get("/api/health")
def health():
    return {
        "app": "remotediag",
        "ok": True,
        "model_configured": bool(MODEL_API_KEY),
        "frontend_dir": str(FRONTEND_DIR),
    }


def page_user(request: Request):
    token = request.cookies.get("diag_token", "")
    if not token:
        return None
    db = SessionLocal()
    try:
        return user_from_token(db, token)
    finally:
        db.close()


@app.get("/login")
def login_page():
    return FileResponse(Path(FRONTEND_DIR) / "login.html")


@app.get("/")
def diagnosis_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.role == "customer":
        return RedirectResponse("/portal")
    return FileResponse(Path(FRONTEND_DIR) / "index.html")


@app.get("/service")
def service_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.role == "customer":
        return RedirectResponse("/portal")
    return FileResponse(Path(FRONTEND_DIR) / "service.html")


@app.get("/portal")
def portal_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    return FileResponse(Path(FRONTEND_DIR) / "portal.html")


@app.get("/documents")
def documents_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.role not in ("kb_admin", "sys_admin"):
        return RedirectResponse("/")
    return FileResponse(Path(FRONTEND_DIR) / "documents.html")


@app.get("/skills")
def skills_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.role not in ("kb_admin", "sys_admin"):
        return RedirectResponse("/")
    return FileResponse(Path(FRONTEND_DIR) / "skills.html")


@app.get("/users")
def users_page(request: Request):
    user = page_user(request)
    if not user:
        return RedirectResponse("/login")
    if user.role != "sys_admin":
        return RedirectResponse("/")
    return FileResponse(Path(FRONTEND_DIR) / "users.html")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
