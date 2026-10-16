from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from deps import require_roles
from models import BackgroundTask
from schemas import TaskOut


router = APIRouter(
    prefix="/api",
    tags=["tasks"],
    dependencies=[Depends(require_roles("kb_admin", "sys_admin"))],
)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(BackgroundTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
