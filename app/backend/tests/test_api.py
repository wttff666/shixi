from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR.parent / "data" / "test_app.db"
TEST_UPLOAD_DIR = BACKEND_DIR.parent / "data" / "test_uploads"
TEST_OCR_DIR = BACKEND_DIR.parent / "data" / "test_ocr"
TEST_DB.unlink(missing_ok=True)
shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)
shutil.rmtree(TEST_OCR_DIR, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["MODEL_API_KEY"] = ""
os.environ["UPLOAD_DIR"] = str(TEST_UPLOAD_DIR)
os.environ["OCR_TEMP_DIR"] = str(TEST_OCR_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from services.evaluation import load_cases, run_evaluation  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)
    shutil.rmtree(TEST_UPLOAD_DIR, ignore_errors=True)
    shutil.rmtree(TEST_OCR_DIR, ignore_errors=True)


def login(client, username, password):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def events(response):
    return [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]


def diagnosis_event(response):
    items = [item for item in events(response) if item["type"] == "diagnosis"]
    assert items, response.text[:400]
    return items[0]["data"]


def test_health_pages_and_auth():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ok"] is True
        assert client.get("/").status_code == 200
        assert client.get("/login").status_code == 200
        assert client.get("/documents").status_code == 200
        assert client.get("/skills").status_code == 200
        assert client.get("/api/machines").status_code == 401


def test_master_data_seeded():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        machines = client.get("/api/machines", headers=headers).json()
        assert len(machines) == 18
        detail = client.get("/api/machines/M001", headers=headers).json()
        assert detail["machine_code"] == "M001"
        assert detail["model_code"] == "IMP-160T"
        assert detail["warranty_status"] in ("保修内", "已过保")
        assert len(client.get("/api/faults", headers=headers).json()) == 13
        assert len(client.get("/api/spare-parts", headers=headers).json()) >= 10
        assert len(client.get("/api/service-bulletins", headers=headers).json()) == 3
        assert client.get("/api/tickets", headers=headers).json()


def test_diagnosis_clear_case():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        response = client.post(
            "/api/diagnosis",
            headers=headers,
            json={"message": "M001 液压油温高报警，运行两小时后触发"},
        )
        assert response.status_code == 200
        data = diagnosis_event(response)
        assert data["fault_id"] == "F03"
        assert data["manual_section"] == "4.2.1"
        assert data["on_site"] == "是"
        assert data["confidence"] == "high"
        assert data["warranty"]["status"] == "保修内"
        assert data["parts"] and data["parts"][0]["part_no"] == "P-1303"


def test_diagnosis_asks_follow_up_when_vague():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        response = client.post(
            "/api/diagnosis",
            headers=headers,
            json={"message": "机器有点热，摸起来烫手，说不清哪里"},
        )
        data = diagnosis_event(response)
        assert data["follow_up"]
        assert data["confidence"] != "high"
        assert data["missing"]


def test_diagnosis_without_machine_asks_for_code():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        response = client.post(
            "/api/diagnosis",
            headers=headers,
            json={"message": "油温高报警，冷却水正常"},
        )
        data = diagnosis_event(response)
        assert "设备编号" in "".join(data["missing"]) or "设备编号" in "".join(
            data["follow_up"]
        )


def test_customer_data_isolation():
    with TestClient(app) as client:
        headers = login(client, "cust01", "cust_demo_2026")
        rows = client.get("/api/machines", headers=headers).json()
        assert {row["machine_code"] for row in rows} == {"M001", "M002", "M003"}
        assert client.get("/api/machines/M004", headers=headers).status_code == 404
        # 客户账号不能进入知识库管理页
        assert client.get("/api/documents", headers=headers).status_code == 403


def test_customer_cannot_run_diagnosis():
    """诊断是内部客服能力，客户账号只能查询服务记录。"""
    with TestClient(app) as client:
        headers = login(client, "cust01", "cust_demo_2026")
        response = client.post(
            "/api/diagnosis",
            headers=headers,
            json={"message": "M001 液压油温高"},
        )
        assert response.status_code == 403
        assert "客户账号" in response.json()["detail"]
        assert client.get("/api/service-requests", headers=headers).status_code == 200
        assert client.get("/", headers=headers, follow_redirects=False).status_code == 307


def test_service_request_flow():
    """工单闭环：建单 -> 诊断回写结论与派工建议 -> 状态推进。"""
    with TestClient(app) as client:
        agent = login(client, "agent01", "agent_demo_2026")
        created = client.post(
            "/api/service-requests",
            headers=agent,
            json={
                "customer_name": "镇江精工注塑厂",
                "machine_code": "M001",
                "channel": "电话",
                "priority": "高",
                "symptom": "客户来电反映油温高报警，运行两个多小时后触发",
            },
        )
        assert created.status_code == 200, created.text
        request_row = created.json()
        assert request_row["request_no"].startswith("SR-")
        assert request_row["status"] == "待研判"
        request_id = request_row["id"]

        # 描述里不带设备编号，设备应从工单带入
        response = client.post(
            "/api/diagnosis",
            headers=agent,
            json={
                "message": "油温高报警，运行两个多小时后触发，冷却水温度正常",
                "service_request_id": request_id,
            },
        )
        data = diagnosis_event(response)
        assert data["machine_code"] == "M001"
        assert data["service_request_no"] == request_row["request_no"]
        assert data["fault_id"] == "F03"
        assert data["dispatch"]["mode"] == "上门处理"
        assert data["dispatch"]["eta_hours"]
        assert data["dispatch"]["sla"]
        assert data["customer_reply"]
        assert data["internal_notes"]

        # 对外话术不能泄露内部信息
        reply = data["customer_reply"]
        for leaked in (
            "P-1303",
            "库存",
            "货期",
            "参考价",
            "结算",
            "SLA",
            "服务通报",
            "SB-",
        ):
            assert leaked not in reply, f"对外话术泄露内部信息：{leaked}"
        notes = " ".join(data["internal_notes"])
        assert "P-1303" in notes or "备件" in notes

        after = client.get(
            f"/api/service-requests/{request_id}", headers=agent
        ).json()
        assert after["fault_id"] == "F03"
        assert after["status"] == "待派工"
        assert after["dispatch"]["mode"] == "上门处理"
        assert after["customer_reply"]

        closed = client.patch(
            f"/api/service-requests/{request_id}",
            headers=agent,
            json={"status": "已派工", "closed_note": "已安排华东区工程师"},
        )
        assert closed.status_code == 200
        assert closed.json()["status"] == "已派工"


def test_customer_sees_only_own_service_requests():
    with TestClient(app) as client:
        agent = login(client, "agent01", "agent_demo_2026")
        other = client.post(
            "/api/service-requests",
            headers=agent,
            json={
                "customer_name": "武汉长江电子科技有限公司",
                "machine_code": "M016",
                "symptom": "周期变长，产量不达标",
            },
        )
        assert other.status_code == 200
        other_id = other.json()["id"]

        customer = login(client, "cust01", "cust_demo_2026")
        rows = client.get("/api/service-requests", headers=customer).json()
        assert all(row["customer_name"] == "镇江精工注塑厂" for row in rows)
        assert client.get(
            f"/api/service-requests/{other_id}", headers=customer
        ).status_code == 404
        assert client.post(
            "/api/service-requests",
            headers=customer,
            json={
                "customer_name": "镇江精工注塑厂",
                "machine_code": "M001",
                "symptom": "客户自行建单",
            },
        ).status_code == 403


def test_role_permissions():
    with TestClient(app) as client:
        agent = login(client, "agent01", "agent_demo_2026")
        assert client.get("/api/machines", headers=agent).status_code == 200
        assert client.get("/api/documents", headers=agent).status_code == 403
        assert client.get("/api/admin/metrics", headers=agent).status_code == 403
        admin = login(client, "admin", "admin_change_me")
        assert client.get("/api/admin/metrics", headers=admin).status_code == 200


def test_knowledge_upload_and_preview():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        upload = client.post(
            "/api/documents/upload",
            headers=headers,
            files={
                "file": (
                    "manual-add.txt",
                    "# 4.9 测试章节\n温控异常时先核对设定值与实测值。".encode("utf-8"),
                    "text/plain",
                )
            },
            data={"strategy": "heading", "max_chars": "400", "overlap_chars": "50"},
        )
        assert upload.status_code == 200, upload.text
        document = upload.json()
        assert document["status"] == "preview_ready"
        assert document["chunks"]
        preview = client.post(
            f"/api/documents/{document['id']}/preview",
            headers=headers,
            json={"strategy": "punctuation", "max_chars": 300, "overlap_chars": 30},
        )
        assert preview.status_code == 200
        publish = client.post(
            f"/api/documents/{document['id']}/publish", headers=headers
        )
        assert publish.status_code == 200
        assert publish.json()["published"] is True


def test_skills_upload_and_publish():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        payload = {
            "id": "cooling-triage",
            "name": "冷却系统研判",
            "version": "1.0.0",
            "description": "针对油温与冷却水流量的初步研判",
            "instructions": "先看冷却水流量，再看油温趋势。",
            "allowed_tools": ["device_latest", "device_active_faults"],
            "retrieval_scope": ["fault_tree", "ticket"],
        }
        upload = client.post(
            "/api/skills/upload",
            headers=headers,
            files={
                "file": (
                    "cooling-triage.json",
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json",
                )
            },
        )
        assert upload.status_code == 200, upload.text
        assert upload.json()["status"] == "draft"
        publish = client.post(
            "/api/skills/cooling-triage/publish", headers=headers
        )
        assert publish.status_code == 200
        assert publish.json()["status"] == "published"


def test_evaluation_metrics():
    with TestClient(app) as client:
        login(client, "admin", "admin_change_me")
        cases = load_cases()
        assert len(cases) == 15
        db = SessionLocal()
        try:
            metrics = run_evaluation(db)
        finally:
            db.close()
        assert metrics["diagnosis_accuracy"] >= 0.9
        assert metrics["follow_up_accuracy"] == 1.0
        assert metrics["false_dispatch_rate"] <= 0.1
        assert metrics["missed_dispatch_rate"] <= 0.1
        assert metrics["answerable_count"] == 12


def test_conversation_persists_diagnosis():
    with TestClient(app) as client:
        headers = login(client, "admin", "admin_change_me")
        response = client.post(
            "/api/diagnosis",
            headers=headers,
            json={"message": "M007 冷却水流量低，过滤器水垢多"},
        )
        data = diagnosis_event(response)
        assert data["fault_id"] == "F06"
        conversation_id = [
            item for item in events(response) if item["type"] == "conversation"
        ][0]["id"]
        detail = client.get(
            f"/api/conversations/{conversation_id}", headers=headers
        ).json()
        assistant = [
            message for message in detail["messages"] if message["role"] == "assistant"
        ]
        assert assistant
        assert assistant[-1]["meta"]["diagnosis"]["fault_id"] == "F06"
