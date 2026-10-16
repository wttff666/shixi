"""远程诊断 MCP 工具服务（只读）。

标准库实现，stdio 传输，每行一条 JSON-RPC 2.0 消息（MCP 2025-06-18）。
数据目录由环境变量 DATA_PACK_DIR 指定，默认当前目录下的“数据包”。

提供的工具覆盖设备档案、设备状态、遥测、报警、历史工单、故障树、备件、
服务通报与保修。全部为只读工具，写操作不经过本服务。
"""

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


PROTOCOL = "2025-06-18"
SERVER = {"name": "remotediag-mcp", "version": "1.0.0"}
DATA_DIR = Path(os.getenv("DATA_PACK_DIR", "数据包"))

STOPWORDS = {"的", "了", "和", "与", "及", "或", "在", "是", "为", "按", "先", "再"}


def _tool(name, description, properties, required):
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOLS = [
    _tool(
        "device_profile",
        "什么时候用：需要确认设备归属客户、机型、投产日期、保修与配置时。"
        "参数：machine_code 必填，如 M001。边界：只返回设备档案，不返回遥测。",
        {"machine_code": {"type": "string", "description": "设备编号，如 M001"}},
        ["machine_code"],
    ),
    _tool(
        "device_latest",
        "什么时候用：需要设备最新工艺参数与状态时。"
        "参数：machine_code 必填。边界：返回最近一个采样点的各测点值。",
        {"machine_code": {"type": "string"}},
        ["machine_code"],
    ),
    _tool(
        "device_telemetry",
        "什么时候用：需要某台设备一段时间的测点趋势时，如判断温度是缓慢上升还是突变。"
        "参数：machine_code 必填；params 可选，测点列表；start/end 可选，格式 "
        "YYYY-MM-DD HH:MM，缺省为数据窗口最后 24 小时。",
        {
            "machine_code": {"type": "string"},
            "params": {"type": "array", "items": {"type": "string"}},
            "start": {"type": "string"},
            "end": {"type": "string"},
        },
        ["machine_code"],
    ),
    _tool(
        "device_active_faults",
        "什么时候用：需要设备最近发生的报警与故障时。"
        "参数：machine_code 必填。边界：只返回数据窗口内判定为真实故障的报警。",
        {"machine_code": {"type": "string"}},
        ["machine_code"],
    ),
    _tool(
        "alarm_history",
        "什么时候用：查询设备历史报警，含误报。参数：machine_code 必填；limit 可选。",
        {
            "machine_code": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        ["machine_code"],
    ),
    _tool(
        "tickets_search",
        "什么时候用：需要找相似历史工单、判断是否常见故障时。"
        "参数：query 必填；machine_code、fault_code 可选；limit 可选。",
        {
            "query": {"type": "string"},
            "machine_code": {"type": "string"},
            "fault_code": {"type": "string"},
            "limit": {"type": "integer", "default": 5},
        },
        ["query"],
    ),
    _tool(
        "tickets_get",
        "什么时候用：需要某条工单的完整处置过程时。参数：ticket_no 必填。",
        {"ticket_no": {"type": "string", "description": "如 ZJ-2026-0001"}},
        ["ticket_no"],
    ),
    _tool(
        "fault_tree_lookup",
        "什么时候用：需要查某个现象、报警或故障码对应的判断和处置说明时。"
        "参数：query 必填；model 可选，按机型过滤；limit 可选。",
        {
            "query": {"type": "string"},
            "model": {"type": "string"},
            "limit": {"type": "integer", "default": 3},
        },
        ["query"],
    ),
    _tool(
        "spare_part_lookup",
        "什么时候用：需要确认备件物料号、库存与货期时。"
        "参数：part_no 或 keyword 至少一个；model 可选。",
        {
            "part_no": {"type": "string"},
            "keyword": {"type": "string"},
            "model": {"type": "string"},
        },
        [],
    ),
    _tool(
        "service_bulletin_lookup",
        "什么时候用：怀疑是批次性质量问题时，查是否有对应服务通报。"
        "参数：model 与 keyword 均可选，至少给出一个。",
        {"model": {"type": "string"}, "keyword": {"type": "string"}},
        [],
    ),
    _tool(
        "warranty_lookup",
        "什么时候用：需要判断设备保修状态与到场时限时。参数：machine_code 必填。",
        {"machine_code": {"type": "string"}},
        ["machine_code"],
    ),
]

for _tool_item in TOOLS:
    _tool_item["annotations"] = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


class ToolError(Exception):
    pass


def read_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def bigrams(text):
    value = re.sub(r"\s+", "", text or "").lower()
    if len(value) < 2:
        return {value} if value else set()
    return {
        value[index:index + 2]
        for index in range(len(value) - 1)
        if value[index:index + 2] not in STOPWORDS
    }


class DataPack:
    def __init__(self, directory):
        self.dir = Path(directory)
        if not self.dir.exists():
            raise ToolError(f"数据目录不存在：{self.dir}")
        self.machines = {row["设备编号"]: row for row in read_csv("设备主表.csv")}
        self.warranties = {row["设备编号"]: row for row in read_csv("保修与服务合同.csv")}
        self.spare_parts = read_csv("备件物料清单.csv")
        self.bulletins = read_csv("服务通报.csv")
        self.faults = read_csv("故障码表.csv")
        self.alarms = read_csv("报警记录.csv")
        self.tickets = read_csv("工单_知识库.csv")
        self.params = read_csv("测点表.csv")
        self._telemetry = {}

    def machine(self, machine_code):
        row = self.machines.get((machine_code or "").strip().upper())
        if not row:
            raise ToolError(f"未找到设备：{machine_code}")
        return row

    def telemetry(self, machine_code):
        code = (machine_code or "").strip().upper()
        if code not in self._telemetry:
            rows = []
            for path in sorted(self.dir.glob(f"遥测_{code}_*.csv")):
                rows.extend(read_csv(path.name))
            self._telemetry[code] = rows
        return self._telemetry[code]

    def profile(self, machine_code):
        row = self.machine(machine_code)
        warranty = self.warranties.get(row["设备编号"], {})
        return {
            "machine_code": row["设备编号"],
            "model": row["机型"],
            "model_name": row["机型名称"],
            "serial_no": row["出厂编号"],
            "customer": row["客户"],
            "site": row["站点"],
            "line": row["产线"],
            "production_date": row["生产年月"],
            "install_date": row["投产日期"],
            "warranty_end": row["保修截止"],
            "warranty_type": row["保修状态"],
            "coverage": row["质保范围"],
            "service_level": warranty.get("服务等级") or row["服务等级"],
            "firmware": row["HMI 版本"],
            "status": row["当前状态"],
            "last_service": row["上次保养"],
        }

    def latest(self, machine_code):
        rows = self.telemetry(machine_code)
        for row in reversed(rows):
            if row.get("T_BARREL1"):
                values = {key: value for key, value in row.items() if key != "timestamp"}
                return {
                    "machine_code": machine_code.strip().upper(),
                    "timestamp": row["timestamp"],
                    "values": values,
                }
        raise ToolError(f"设备 {machine_code} 无遥测数据")

    def telemetry_window(self, machine_code, params, start, end):
        rows = [row for row in self.telemetry(machine_code) if row.get("T_BARREL1")]
        if not rows:
            raise ToolError(f"设备 {machine_code} 无遥测数据")
        if not end:
            end = rows[-1]["timestamp"]
        if not start:
            end_time = datetime.strptime(end, "%Y-%m-%d %H:%M")
            start = (end_time - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        selected = [row for row in rows if start <= row["timestamp"] <= end]
        keys = [row["测点"] for row in self.params]
        if params:
            wanted = {item.strip().upper() for item in params}
            keys = [key for key in keys if key in wanted]
        series = [
            {"timestamp": row["timestamp"], **{key: row.get(key, "") for key in keys}}
            for row in selected
        ]
        return {
            "machine_code": machine_code.strip().upper(),
            "start": start,
            "end": end,
            "params": keys,
            "points": len(series),
            "series": series,
        }

    def alarms_of(self, machine_code):
        code = machine_code.strip().upper()
        return [row for row in self.alarms if row["设备编号"] == code]

    def active_faults(self, machine_code):
        rows = [row for row in self.alarms_of(machine_code) if row["判定"] == "真实故障"]
        rows.sort(key=lambda item: item["触发时间"], reverse=True)
        return {
            "machine_code": machine_code.strip().upper(),
            "faults": [
                {
                    "param": row["测点"],
                    "name": row["报警名称"],
                    "peak": row["峰值"],
                    "threshold": row["阈值"],
                    "start": row["触发时间"],
                    "end": row["恢复时间"],
                }
                for row in rows[:3]
            ],
        }

    def search_tickets(self, query, machine_code, fault_code, limit):
        grams = bigrams(query)
        scored = []
        for row in self.tickets:
            if machine_code and row["设备编号"] != machine_code.strip().upper():
                continue
            if fault_code and row["故障ID"] != fault_code.strip().upper():
                continue
            body = f"{row['现象描述']}\n{row['原因']}\n{row['处置过程']}"
            score = sum(1 for gram in grams if gram in body.lower())
            if machine_code:
                score += 2
            if fault_code and row["故障ID"] == fault_code.strip().upper():
                score += 5
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["报修时间"]))
        return {
            "count": len(scored),
            "tickets": [
                {
                    "ticket_no": row["工单号"],
                    "machine_code": row["设备编号"],
                    "customer": row["客户"],
                    "fault_id": row["故障ID"],
                    "reported_at": row["报修时间"],
                    "symptom": row["现象描述"][:200],
                    "cause": row["原因"],
                    "action": row["处置过程"],
                    "manual_section": row["手册依据"],
                    "on_site": row["是否到场"],
                    "settlement": row["结算方式"],
                }
                for _, row in scored[: max(1, min(limit, 10))]
            ],
        }

    def get_ticket(self, ticket_no):
        for row in self.tickets:
            if row["工单号"] == ticket_no.strip().upper():
                return row
        raise ToolError(f"未找到工单：{ticket_no}")

    def lookup_fault_tree(self, query, model, limit):
        grams = bigrams(query)
        scored = []
        for row in self.faults:
            body = f"{row['名称']}\n{row['故障码']}\n{row['报警条件']}\n{row['关键测点']}"
            score = sum(1 for gram in grams if gram in body.lower())
            if row["名称"] in (query or ""):
                score += 6
            code_match = re.findall(r"\d+", query or "")
            if row["故障ID"] in (query or ""):
                score += 8
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: -item[0])
        results = []
        for _, row in scored[: max(1, min(limit, 5))]:
            results.append(
                {
                    "fault_id": row["故障ID"],
                    "name": row["名称"],
                    "group": row["分组"],
                    "severity": row["严重度"],
                    "alarm_condition": row["报警条件"],
                    "key_params": row["关键测点"],
                    "manual_section": row["手册章节"],
                    "reset_method": row["复位方式"],
                    "parts": row["涉及物料"],
                    "on_site": row["是否到场"],
                }
            )
        return {"count": len(results), "faults": results}

    def lookup_parts(self, part_no, keyword, model):
        results = []
        for row in self.spare_parts:
            if part_no and row["物料号"] != part_no.strip().upper():
                continue
            if keyword and keyword not in f"{row['物料名称']}{row['规格型号']}":
                continue
            if model and model not in row["适用机型"] and row["适用机型"] != "全系列":
                continue
            if not part_no and not keyword and not model:
                continue
            results.append(
                {
                    "part_no": row["物料号"],
                    "name": row["物料名称"],
                    "spec": row["规格型号"],
                    "applicable_models": row["适用机型"],
                    "stock": int(row["安全库存"]),
                    "lead_days": int(row["货期(天)"]),
                    "unit_price": int(row["参考单价(元)"]),
                }
            )
        return {"count": len(results), "parts": results[:5]}

    def lookup_bulletins(self, model, keyword):
        grams = bigrams(keyword) if keyword else set()
        results = []
        for row in self.bulletins:
            if model and model not in row["适用机型"] and row["适用机型"] != "全系列":
                continue
            body = f"{row['问题描述']}{row['检索提示']}{row['处理措施']}"
            if grams:
                if not any(gram in body for gram in grams):
                    continue
            elif not model:
                continue
            results.append(
                {
                    "bulletin_no": row["通报号"],
                    "applicable_models": row["适用机型"],
                    "applicable_batch": row["适用批次"],
                    "description": row["问题描述"],
                    "action": row["处理措施"],
                    "hint": row["检索提示"],
                    "valid_until": row["有效期"],
                }
            )
        return {"count": len(results), "bulletins": results[:3]}

    def warranty(self, machine_code):
        row = self.machine(machine_code)
        warranty = self.warranties.get(row["设备编号"], {})
        return {
            "machine_code": row["设备编号"],
            "customer": row["客户"],
            "model": row["机型"],
            "warranty_type": warranty.get("保修类型", row["保修状态"]),
            "coverage": warranty.get("质保范围", row["质保范围"]),
            "service_level": warranty.get("服务等级", row["服务等级"]),
            "warranty_end": warranty.get("保修截止", row["保修截止"]),
        }


def call_tool(pack, name, arguments):
    if name == "device_profile":
        return pack.profile(arguments["machine_code"])
    if name == "device_latest":
        return pack.latest(arguments["machine_code"])
    if name == "device_telemetry":
        return pack.telemetry_window(
            arguments["machine_code"],
            arguments.get("params"),
            arguments.get("start"),
            arguments.get("end"),
        )
    if name == "device_active_faults":
        return pack.active_faults(arguments["machine_code"])
    if name == "alarm_history":
        rows = pack.alarms_of(arguments["machine_code"])
        rows.sort(key=lambda item: item["触发时间"], reverse=True)
        limit = max(1, min(int(arguments.get("limit") or 10), 50))
        return {"machine_code": arguments["machine_code"], "alarms": rows[:limit]}
    if name == "tickets_search":
        return pack.search_tickets(
            arguments.get("query", ""),
            arguments.get("machine_code"),
            arguments.get("fault_code"),
            int(arguments.get("limit") or 5),
        )
    if name == "tickets_get":
        return pack.get_ticket(arguments["ticket_no"])
    if name == "fault_tree_lookup":
        return pack.lookup_fault_tree(
            arguments.get("query", ""),
            arguments.get("model"),
            int(arguments.get("limit") or 3),
        )
    if name == "spare_part_lookup":
        return pack.lookup_parts(
            arguments.get("part_no"),
            arguments.get("keyword"),
            arguments.get("model"),
        )
    if name == "service_bulletin_lookup":
        return pack.lookup_bulletins(
            arguments.get("model"),
            arguments.get("keyword"),
        )
    if name == "warranty_lookup":
        return pack.warranty(arguments["machine_code"])
    raise ToolError(f"未知工具：{name}")


def handle(pack, message):
    method = message.get("method")
    ident = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER,
            },
        }
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            data = call_tool(pack, name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": ident,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(data, ensure_ascii=False)}
                    ],
                    "structuredContent": data,
                    "isError": False,
                },
            }
        except ToolError as error:
            return {
                "jsonrpc": "2.0",
                "id": ident,
                "result": {
                    "content": [{"type": "text", "text": str(error)}],
                    "isError": True,
                },
            }
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "error": {"code": -32601, "message": f"未知方法：{method}"},
    }


def main():
    try:
        pack = DataPack(DATA_DIR)
    except ToolError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        response = handle(pack, message)
        if response is None:
            continue
        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
