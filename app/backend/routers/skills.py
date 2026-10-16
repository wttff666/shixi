from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user, require_roles
from models import Skill
from services.audit import record_audit
from schemas import SkillCreate, SkillOut


router = APIRouter(prefix="/api", tags=["skills"])


def simple_front_matter(text: str):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    metadata = {}
    for line in parts[1].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            metadata[key] = value
    return metadata, parts[2].strip()


def markdown_skill_payload(text: str, filename: str):
    metadata, body = simple_front_matter(text)
    stem = Path(filename).stem
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-").lower()
    if not slug:
        slug = "skill-" + hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
    heading = next(
        (
            line.lstrip("#").strip()
            for line in body.splitlines()
            if line.strip().startswith("#")
        ),
        "",
    )
    description = ""
    for line in body.splitlines():
        value = line.strip()
        if value and not value.startswith("#") and not value.startswith("---"):
            description = value[:300]
            break
    return {
        "id": metadata.get("id") or slug,
        "name": metadata.get("name") or heading or stem,
        "version": metadata.get("version") or "1.0.0",
        "description": metadata.get("description") or description,
        "instructions": body,
        "allowed_tools": [
            item.strip()
            for item in metadata.get("allowed_tools", "").split(",")
            if item.strip()
        ],
        "retrieval_scope": [
            item.strip()
            for item in metadata.get("retrieval_scope", "").split(",")
            if item.strip()
        ],
        "input_schema": {},
        "output_schema": {},
        "response_template": metadata.get("response_template") or "",
        "examples": [],
    }


def zip_skill_payload(data: bytes, filename: str):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {
            name.replace("\\", "/").lower(): name
            for name in archive.namelist()
            if not name.endswith("/")
        }
        json_name = next(
            (original for lower, original in files.items() if lower.endswith("skill.json")),
            None,
        )
        if not json_name:
            raise ValueError("ZIP 中缺少 skill.json")
        payload = json.loads(archive.read(json_name).decode("utf-8-sig"))
        md_name = next(
            (original for lower, original in files.items() if lower.endswith("skill.md")),
            None,
        )
        if md_name:
            md_text = archive.read(md_name).decode("utf-8-sig")
            metadata, body = simple_front_matter(md_text)
            if not payload.get("instructions"):
                payload["instructions"] = body
            for key in ("description", "version", "response_template"):
                if not payload.get(key) and metadata.get(key):
                    payload[key] = metadata[key]
        return payload


def skill_payload(filename: str, data: bytes):
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return json.loads(data.decode("utf-8-sig"))
    if suffix == ".md":
        return markdown_skill_payload(data.decode("utf-8-sig"), filename)
    if suffix == ".zip":
        return zip_skill_payload(data, filename)
    raise ValueError("Skill 只接受 JSON、Markdown 或 ZIP 包")


@router.get("/skills", response_model=list[SkillOut])
def list_skills(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Skill)
    if user.role not in ("kb_admin", "sys_admin"):
        query = query.filter(Skill.status == "published")
    return query.order_by(Skill.updated_at.desc()).all()


@router.post("/skills/upload", response_model=SkillOut)
async def upload_skill(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    filename = file.filename or "skill"
    try:
        payload = skill_payload(filename, await file.read())
        config = SkillCreate.model_validate(payload)
    except (ValueError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=f"Skill 配置无效：{exc}") from exc

    skill = db.query(Skill).filter(Skill.skill_id == config.id).first()
    if skill is None:
        skill = Skill(
            skill_id=config.id,
            name=config.name,
            version=config.version,
            description=config.description,
            status="draft",
            config_json=json.dumps(config.model_dump(), ensure_ascii=False),
        )
        db.add(skill)
    else:
        skill.name = config.name
        skill.version = config.version
        skill.description = config.description
        skill.status = "draft"
        skill.config_json = json.dumps(config.model_dump(), ensure_ascii=False)
    db.commit()
    db.refresh(skill)
    record_audit(
        db,
        user_id=user.id,
        action="skill.upload",
        entity_type="skill",
        entity_id=skill.skill_id,
        detail={"version": skill.version},
    )
    return skill


@router.post("/skills/{skill_id}/publish", response_model=SkillOut)
def publish_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    skill.status = "published"
    db.commit()
    db.refresh(skill)
    record_audit(
        db,
        user_id=user.id,
        action="skill.publish",
        entity_type="skill",
        entity_id=skill.skill_id,
    )
    return skill


@router.post("/skills/{skill_id}/disable", response_model=SkillOut)
def disable_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    skill.status = "disabled"
    db.commit()
    db.refresh(skill)
    record_audit(
        db,
        user_id=user.id,
        action="skill.disable",
        entity_type="skill",
        entity_id=skill.skill_id,
    )
    return skill


@router.delete("/skills/{skill_id}")
def delete_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles("kb_admin", "sys_admin")),
):
    skill = db.query(Skill).filter(Skill.skill_id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    db.delete(skill)
    db.commit()
    record_audit(
        db,
        user_id=user.id,
        action="skill.delete",
        entity_type="skill",
        entity_id=skill_id,
    )
    return {"ok": True}
