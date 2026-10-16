from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from sqlalchemy.orm import Session

from config import DATA_PACK_DIR
from database import SessionLocal
from models import (
    Customer,
    Document,
    DocumentChunk,
    FaultDefinition,
    Machine,
    MachineModel,
    ServiceBulletin,
    SparePart,
    Ticket,
    Warranty,
)


FAULT_HEADER = re.compile(r"^##\s+(\S+)\s+(F\d+)\s+(.+?)\s*$")
KNOWLEDGE_KEY = "diagnostic-knowledge"


def read_csv(name):
    path = DATA_PACK_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_fault_tree(text: str) -> dict:
    result: dict[str, dict] = {}
    current = None
    mode = None
    for raw in text.splitlines():
        line = raw.rstrip()
        header = FAULT_HEADER.match(line)
        if header:
            current = {
                "section": header.group(1),
                "fault_id": header.group(2),
                "name": header.group(3),
                "questions": [],
                "steps": [],
                "risk": "",
                "cause": "",
                "text": [line],
            }
            result[current["fault_id"]] = current
            mode = None
            continue
        if current is None:
            continue
        current["text"].append(line)
        if line.startswith("先追问："):
            mode = "questions"
            continue
        if line.startswith("排查步骤："):
            mode = "steps"
            continue
        if line.startswith("风险提示："):
            current["risk"] = line.split("：", 1)[1].strip()
            mode = None
            continue
        if line.startswith("- 典型原因："):
            current["cause"] = line.split("：", 1)[1].strip()
            continue
        if line.startswith("- "):
            continue
        item = re.match(r"^\d+\.\s+(.+)$", line.strip())
        if item and mode == "questions":
            current["questions"].append(item.group(1).strip())
        elif item and mode == "steps":
            current["steps"].append(item.group(1).strip())
        elif not line.strip():
            mode = None
    return result


def model_spec(code: str) -> dict:
    match = re.search(r"(\d+)T", code or "")
    clamp = int(match.group(1)) if match else 0
    return {
        "code": code,
        "name": f"{code} 锁模 {clamp} 吨" if clamp else code,
        "clamp_force": clamp,
        "screw_diameter": 0,
        "shot_size": 0,
        "launch_year": 0,
    }


def seed_master(db: Session):
    customers = read_csv("客户与站点.csv")
    by_name = {}
    for row in customers:
        customer = Customer(
            name=row["客户"],
            level=row.get("客户等级", ""),
            region=row.get("区域", ""),
            city=row.get("城市", ""),
            site=row.get("站点", ""),
            site_code=row.get("站点编号", ""),
            service_level=row.get("服务等级", ""),
        )
        db.add(customer)
        by_name[customer.name] = customer
    db.flush()

    models_seen = {}
    for row in read_csv("设备主表.csv"):
        code = row["机型"]
        if code not in models_seen:
            spec = model_spec(code)
            spec["name"] = row.get("机型名称") or spec["name"]
            db.add(MachineModel(**spec))
            models_seen[code] = spec
        customer = by_name.get(row["客户"])
        db.add(
            Machine(
                machine_code=row["设备编号"],
                model_code=code,
                model_name=row.get("机型名称", ""),
                serial_no=row.get("出厂编号", ""),
                customer_id=customer.id if customer else None,
                customer_name=row.get("客户", ""),
                site_name=row.get("站点", ""),
                line_name=row.get("产线", ""),
                production_date=row.get("生产年月", ""),
                install_date=row.get("投产日期", ""),
                status=row.get("当前状态", ""),
                firmware=row.get("HMI 版本", ""),
                last_service_at=row.get("上次保养", ""),
            )
        )
    db.flush()

    machines = {row.machine_code: row for row in db.query(Machine).all()}
    for row in read_csv("保修与服务合同.csv"):
        machine = machines.get(row["设备编号"])
        if not machine:
            continue
        db.add(
            Warranty(
                machine_id=machine.id,
                warranty_type=row.get("保修类型", ""),
                coverage=row.get("质保范围", ""),
                service_level=row.get("服务等级", ""),
                warranty_end=row.get("保修截止", ""),
            )
        )

    for row in read_csv("备件物料清单.csv"):
        db.add(
            SparePart(
                part_no=row["物料号"],
                name=row["物料名称"],
                spec=row.get("规格型号", ""),
                applicable_models=row.get("适用机型", ""),
                supplier=row.get("供应商", ""),
                unit_price=int(row.get("参考单价(元)") or 0),
                stock=int(row.get("安全库存") or 0),
                lead_days=int(row.get("货期(天)") or 0),
            )
        )

    for row in read_csv("服务通报.csv"):
        db.add(
            ServiceBulletin(
                bulletin_no=row["通报号"],
                applicable_models=row.get("适用机型", ""),
                applicable_batch=row.get("适用批次", ""),
                description=row.get("问题描述", ""),
                action=row.get("处理措施", ""),
                hint=row.get("检索提示", ""),
                valid_until=row.get("有效期", ""),
            )
        )
    db.flush()


def seed_faults(db: Session):
    tree_path = DATA_PACK_DIR / "故障树.md"
    tree = parse_fault_tree(
        tree_path.read_text(encoding="utf-8") if tree_path.exists() else ""
    )
    for row in read_csv("故障码表.csv"):
        fault_id = row["故障ID"]
        detail = tree.get(fault_id, {})
        keywords = " ".join(
            [
                row.get("名称", ""),
                row.get("分组", ""),
                row.get("报警条件", ""),
                row.get("关键测点", ""),
                detail.get("cause", ""),
            ]
        )
        db.add(
            FaultDefinition(
                fault_id=fault_id,
                code=row.get("故障码", ""),
                name=row.get("名称", ""),
                group_name=row.get("分组", ""),
                severity=row.get("严重度", ""),
                alarm_condition=row.get("报警条件", ""),
                key_params=row.get("关键测点", ""),
                manual_section=row.get("手册章节", ""),
                reset_method=row.get("复位方式", ""),
                part_no=row.get("涉及物料", ""),
                on_site=row.get("是否到场", ""),
                keywords=keywords[:500],
                cause=detail.get("cause", ""),
                risk=detail.get("risk", ""),
                questions_json=json.dumps(
                    detail.get("questions", []), ensure_ascii=False
                ),
                steps_json=json.dumps(
                    detail.get("steps", []), ensure_ascii=False
                ),
            )
        )


def seed_tickets(db: Session):
    for row in read_csv("工单_知识库.csv"):
        db.add(
            Ticket(
                ticket_no=row["工单号"],
                machine_code=row.get("设备编号", ""),
                customer_name=row.get("客户", ""),
                model_code=row.get("机型", ""),
                warranty_status=row.get("保修状态", ""),
                reported_at=row.get("报修时间", ""),
                fault_id=row.get("故障ID", ""),
                symptom=row.get("现象描述", ""),
                anomaly=row.get("相关测点及异常", ""),
                cause=row.get("原因", ""),
                action=row.get("处置过程", ""),
                manual_section=row.get("手册依据", ""),
                on_site=row.get("是否到场", ""),
                parts=row.get("更换备件", ""),
                hours=str(row.get("耗时(h)", "")),
                settlement=row.get("结算方式", ""),
                cost=int(row.get("费用(元)") or 0),
            )
        )
    db.flush()


def seed_knowledge(db: Session):
    """把故障树、服务通报与历史工单构建成可检索的知识切片。"""
    document = Document(
        filename="故障诊断知识库",
        stored_name=KNOWLEDGE_KEY,
        source_path=str(DATA_PACK_DIR),
        media_type="application/x-diagnostic-index",
        size=0,
        sha256="seed-knowledge",
        status="published",
        parse_method="seed",
        chunk_strategy="section",
        max_chars=0,
        overlap_chars=0,
        published=True,
    )
    db.add(document)
    db.flush()

    tree_path = DATA_PACK_DIR / "故障树.md"
    tree = parse_fault_tree(
        tree_path.read_text(encoding="utf-8") if tree_path.exists() else ""
    )

    order = 0
    for fault_id, detail in tree.items():
        order += 1
        content = "\n".join(detail["text"]).strip()
        db.add(
            DocumentChunk(
                document_id=document.id,
                order_index=order,
                section=detail["section"],
                title=f"{fault_id} {detail['name']}",
                content=content,
                source_file="故障树.md",
                page_start=1,
                page_end=1,
                citation=f"故障树 · {detail['section']} {fault_id} {detail['name']}",
                strategy="section",
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                published=True,
            )
        )

    for row in read_csv("服务通报.csv"):
        order += 1
        content = (
            f"{row['通报号']}｜适用机型 {row['适用机型']}｜适用批次 {row['适用批次']}\n"
            f"问题：{row['问题描述']}\n处理措施：{row['处理措施']}\n"
            f"检索提示：{row['检索提示']}"
        )
        db.add(
            DocumentChunk(
                document_id=document.id,
                order_index=order,
                section="服务通报",
                title=row["通报号"],
                content=content,
                source_file="服务通报.csv",
                page_start=1,
                page_end=1,
                citation=f"服务通报 · {row['通报号']}",
                strategy="section",
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                published=True,
            )
        )

    for row in read_csv("工单_知识库.csv"):
        order += 1
        content = (
            f"工单 {row['工单号']}｜机型 {row['机型']}｜故障 {row['故障ID']}\n"
            f"现象：{row['现象描述']}\n原因：{row['原因']}\n处置：{row['处置过程']}"
        )
        db.add(
            DocumentChunk(
                document_id=document.id,
                order_index=order,
                section=row.get("手册依据", ""),
                title=f"历史工单 {row['工单号']}",
                content=content,
                source_file="工单_知识库.csv",
                page_start=1,
                page_end=1,
                citation=f"历史工单 · {row['工单号']} · {row.get('手册依据', '')}",
                strategy="section",
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                published=True,
            )
        )


def seed_all():
    db = SessionLocal()
    try:
        if db.query(Machine).count() > 0:
            return
        seed_master(db)
        seed_faults(db)
        seed_tickets(db)
        seed_knowledge(db)
        db.commit()
    finally:
        db.close()
