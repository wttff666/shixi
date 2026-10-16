"""生成注塑机厂商远程诊断的练习数据包。

用法：
    python run.py

输出：remotediag/数据包/
全部为合成数据，公司和机型均为虚构，不可用于生产决策。
"""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import domain as D


OUT = Path(__file__).resolve().parent / "数据包"
TELEMETRY_MACHINES = ["M001", "M004", "M007", "M010", "M013", "M016"]


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def fmt(moment):
    return moment.strftime("%Y-%m-%d %H:%M")


# --- 主数据 -------------------------------------------------------------

def build_machines():
    machines = []
    used = set()
    for site in D.SITES:
        for index, model in enumerate(site["models"], start=1):
            spec = D.MODELS[model]
            machine_id = f"M{len(machines) + 1:03d}"
            production = datetime(2026, 6, 1) - timedelta(
                days=int(site["commission_years_ago"] * 365) + random.randint(0, 60)
            )
            while True:
                serial = f"{model.replace('-', '')}{random.randint(100000, 999999)}"
                if serial not in used:
                    used.add(serial)
                    break
            install = production + timedelta(days=random.randint(20, 70))
            machines.append(
                {
                    "machine_id": machine_id,
                    "model": model,
                    "model_name": spec["name"],
                    "serial": serial,
                    "site_id": site["site_id"],
                    "customer": site["customer"],
                    "customer_level": site["customer_level"],
                    "region": site["region"],
                    "city": site["city"],
                    "site": site["site"],
                    "line": f"{index} 号线",
                    "production_date": production,
                    "install_date": install,
                    "warranty_end": production
                    + timedelta(days=site["warranty_months"] * 30),
                    "warranty_type": site["warranty_type"],
                    "coverage": site["coverage"],
                    "service_level": site["service_level"],
                    "firmware": f"HMI V3.2.{random.choice(['1', '2', '4'])}",
                    "options": "STD",
                    "status": random.choice(["运行", "运行", "运行", "停机保养"]),
                    "last_service": D.START
                    - timedelta(days=random.randint(7, 160)),
                }
            )
    return machines


def write_master_data(machines):
    write_csv(
        OUT / "客户与站点.csv",
        ["站点编号", "客户", "客户等级", "区域", "城市", "站点", "在用机型",
         "服务等级", "质保月数", "保修状态"],
        [
            [s["site_id"], s["customer"], s["customer_level"], s["region"], s["city"],
             s["site"], " / ".join(s["models"]), s["service_level"],
             s["warranty_months"], s["warranty_type"]]
            for s in D.SITES
        ],
    )
    write_csv(
        OUT / "设备主表.csv",
        ["设备编号", "机型", "机型名称", "出厂编号", "客户", "站点", "产线",
         "生产年月", "投产日期", "保修截止", "保修状态", "质保范围", "服务等级",
         "HMI 版本", "当前状态", "上次保养"],
        [
            [m["machine_id"], m["model"], m["model_name"], m["serial"], m["customer"],
             m["site"], m["line"], m["production_date"].strftime("%Y-%m"),
             m["install_date"].strftime("%Y-%m-%d"),
             m["warranty_end"].strftime("%Y-%m-%d"), m["warranty_type"],
             m["coverage"], m["service_level"], m["firmware"], m["status"],
             m["last_service"].strftime("%Y-%m-%d")]
            for m in machines
        ],
    )
    write_csv(
        OUT / "保修与服务合同.csv",
        ["设备编号", "客户", "机型", "出厂编号", "保修类型", "质保范围",
         "服务等级", "保修截止"],
        [
            [m["machine_id"], m["customer"], m["model"], m["serial"],
             m["warranty_type"], m["coverage"], m["service_level"],
             m["warranty_end"].strftime("%Y-%m-%d")]
            for m in machines
        ],
    )
    write_csv(
        OUT / "故障码表.csv",
        ["故障ID", "故障码", "名称", "分组", "严重度", "报警条件", "关键测点",
         "手册章节", "复位方式", "涉及物料", "是否到场"],
        [
            [fid, f"{fid}_{f['module']}_{f['name']}", f["name"],
             D.MODULES[f["module"]], f["severity"], f["alarm"], f["params"],
             f["section"], f["reset"], f["parts"], f["on_site"]]
            for fid, f in D.FAULTS.items()
        ],
    )
    write_csv(
        OUT / "测点表.csv",
        ["测点", "名称", "单位", "正常范围", "所属系统"],
        [list(row) for row in D.PARAM_ROWS],
    )
    write_csv(
        OUT / "备件物料清单.csv",
        ["物料号", "物料名称", "规格型号", "适用机型", "供应商",
         "参考单价(元)", "安全库存", "货期(天)"],
        [list(row) for row in D.PARTS],
    )
    write_csv(
        OUT / "服务通报.csv",
        ["通报号", "适用机型", "适用批次", "问题描述", "处理措施", "检索提示", "有效期"],
        [list(row) for row in D.SERVICE_BULLETINS],
    )


# --- 遥测与报警 ---------------------------------------------------------

def sensor_values(machine, moment, active):
    spec = D.MODELS[machine["model"]]
    hour = moment.hour
    minute = moment.minute
    # 开机升温：90 分钟内从偏低 1.5% 线性回升，避免冷启动噪声误触低温报警。
    warm = 0.985 if hour == 0 else 1.0
    if hour == 1:
        warm = 0.985 + 0.015 * minute / 60.0
    values = {
        "T_SET1": spec["T_SET1"],
        "T_BARREL1": spec["T_SET1"] - 1.0 + random.uniform(-1.0, 1.0),
        "T_BARREL2": spec["T_SET2"] - 1.5 + random.uniform(-1.0, 1.0),
        "T_BARREL3": spec["T_SET3"] - 1.0 + random.uniform(-1.0, 1.0),
        "P_INJ": spec["P_INJ_BASE"] + random.uniform(-3.0, 3.0),
        "P_HOLD": spec["P_HOLD_BASE"] + random.uniform(-2.0, 2.0),
        "V_INJ": spec["V_INJ_BASE"] + random.uniform(-2.0, 2.0),
        "CYCLE_TIME": spec["CYCLE_BASE"] + random.uniform(-0.04, 0.04),
        "T_OIL": 40.0 + (3.0 if 12 <= hour <= 20 else 0.0) + random.uniform(-1.0, 1.0),
        "P_HYD": 15.6 + random.uniform(-0.25, 0.25),
        "C_MOTOR": 17.5 + random.uniform(-0.9, 0.9),
        "T_MOTOR": 46.0 + random.uniform(-1.5, 1.5),
        "F_COOL": 14.5 + random.uniform(-0.6, 0.6),
        "T_COOL_IN": 23.5 + random.uniform(-0.8, 0.8),
        "F_CLAMP": spec["F_CLAMP_BASE"] + random.uniform(-2.0, 2.0),
        "V_CLAMP": 300.0 + random.uniform(-10.0, 10.0),
        "T_MOLD": 55.0 + random.uniform(-1.5, 1.5),
        "FREQ_DRV": 42.0 + random.uniform(-1.0, 1.0),
        "POS_ERR": random.uniform(-0.3, 0.3),
        "T_INJ": 1.95 + random.uniform(-0.05, 0.05),
        "T_DRY": 3.0 + random.uniform(-0.1, 0.1),
        "P_DRY": 88.0 + random.uniform(-1.5, 1.5),
    }
    values["T_BARREL1"] = values["T_BARREL1"] * warm + 24.0 * (1 - warm)
    for name, (amplitude, direction) in (active or {}).items():
        if name == "__missing__":
            continue
        values[name] = values[name] + amplitude * direction
    return {key: round(value, 2) for key, value in values.items()}


def build_events(machines):
    index = {m["machine_id"]: m for m in machines}
    prepared = []
    for event_id, machine_id, fault_id, mode, offset, duration, params in D.EVENTS:
        start = D.START + timedelta(hours=offset)
        prepared.append(
            {
                "event_id": event_id,
                "machine_id": machine_id,
                "machine": index[machine_id],
                "fault_id": fault_id,
                "mode": mode,
                "start": start,
                "end": start + timedelta(hours=duration),
                "params": params,
            }
        )
    return prepared


def active_overlay(event, moment):
    if not (event["start"] <= moment < event["end"]):
        return None
    if event["mode"] in ("amb", "spike"):
        return None
    if "__missing__" in event["params"]:
        return {"__missing__": (1, 1)}
    span = max(1.0, (event["end"] - event["start"]).total_seconds())
    progress = (moment - event["start"]).total_seconds() / span
    factor = 0.25 + 0.75 * progress if event["mode"] == "slow" else 1.0
    return {
        name: (amplitude * factor, direction)
        for name, (amplitude, direction) in event["params"].items()
    }


def write_telemetry(machines, events):
    """写遥测 CSV 并按阈值生成告警记录（2 采样确认 + 回差）。"""
    by_machine = {}
    for event in events:
        by_machine.setdefault(event["machine_id"], []).append(event)

    columns = ["timestamp"] + [row[0] for row in D.PARAM_ROWS]
    alarms = []
    alarm_id = 0

    for machine in machines:
        machine_id = machine["machine_id"]
        if machine_id not in TELEMETRY_MACHINES:
            continue
        machine_events = by_machine.get(machine_id, [])
        states = {
            name: {"up": 0, "down": 0, "active": False, "start": None, "peak": None}
            for name in D.ALARM_RULES
        }
        body = []
        for step in range(D.DAYS * 24 * 60 // D.STEP_MIN):
            moment = D.START + timedelta(minutes=step * D.STEP_MIN)
            overlay = None
            for event in machine_events:
                candidate = active_overlay(event, moment)
                if candidate:
                    overlay = candidate
                    break
            missing = bool(overlay and "__missing__" in overlay)
            values = None if missing else sensor_values(machine, moment, overlay)
            if values is not None:
                values = apply_spike(machine, moment, values, machine_events)

            if missing:
                body.append([fmt(moment)] + [""] * len(D.PARAM_ROWS))
            else:
                body.append([fmt(moment)] + [values[r[0]] for r in D.PARAM_ROWS])

            if values is None:
                continue
            for name, (label, threshold, predicate) in D.ALARM_RULES.items():
                state = states[name]
                value = values[name]
                if predicate(value):
                    state["up"] += 1
                    state["down"] = 0
                else:
                    state["down"] += 1
                    state["up"] = 0
                if not state["active"] and state["up"] >= 2:
                    state["active"] = True
                    state["start"] = moment
                    state["peak"] = value
                    state["threshold"] = threshold
                    state["label"] = label
                    state["lower_bound"] = threshold.startswith("<")
                elif state["active"]:
                    if state["lower_bound"]:
                        worse = value < state["peak"]
                    else:
                        worse = value > state["peak"]
                    if worse:
                        state["peak"] = value
                    if state["down"] >= 2:
                        alarm_id += 1
                        alarms.append(
                            {
                                "alarm_id": f"AL-{alarm_id:04d}",
                                "machine_id": machine_id,
                                "customer": machine["customer"],
                                "model": machine["model"],
                                "param": name,
                                "label": state["label"],
                                "threshold": state["threshold"],
                                "value": round(state["peak"], 2),
                                "start": state["start"],
                                "end": moment,
                            }
                        )
                        state.update(
                            up=0, down=0, active=False, start=None, peak=None
                        )
        write_csv(OUT / f"遥测_{machine_id}_202607.csv", columns, body)
    return alarms


def event_of_alarm(alarm, events):
    for event in events:
        if event["machine_id"] != alarm["machine_id"]:
            continue
        if event["start"] - timedelta(minutes=45) <= alarm["start"] <= event["end"] + timedelta(minutes=45):
            if alarm["param"] in (event["params"] or {}):
                return event
    return None


def apply_spike(machine, moment, values, events):
    """误报样本：在指定窗口内叠加一个短暂尖峰，覆盖基础噪声。"""
    spec = D.MODELS[machine["model"]]
    for event in events:
        if event["machine_id"] != machine["machine_id"]:
            continue
        if event["mode"] != "spike":
            continue
        if event["start"] <= moment < event["end"]:
            for name, (amplitude, direction) in event["params"].items():
                base = spec["T_SET1"] - 1.0 if name == "T_BARREL1" else values[name]
                values[name] = round(base + amplitude * direction, 2)
    return values


def write_alarms(alarms, events):
    rows = []
    for alarm in alarms:
        origin = event_of_alarm(alarm, events)
        if origin and origin["mode"] == "spike":
            tag, note = "疑似误报", "传感器瞬时尖峰，无对应工单，建议结合现场确认后判定为误报"
        elif origin:
            tag, note = "真实故障", "与注入异常对应，已确认"
        else:
            tag, note = "疑似误报", "阈值瞬间越限后自恢复，建议结合现场确认"
        duration = (
            alarm["end"] - alarm["start"]
        ).total_seconds() / 60.0
        rows.append(
            [
                alarm["alarm_id"], alarm["machine_id"], alarm["customer"],
                alarm["model"], alarm["param"], alarm["label"],
                fmt(alarm["start"]), fmt(alarm["end"]),
                alarm["value"], alarm["threshold"], round(duration),
                tag, note,
            ]
        )
    write_csv(
        OUT / "报警记录.csv",
        ["报警号", "设备编号", "客户", "机型", "测点", "报警名称", "触发时间",
         "恢复时间", "峰值", "阈值", "持续(分钟)", "判定", "说明"],
        rows,
    )


# --- 工单与评测集 -------------------------------------------------------

SYMPTOM_TEXT = {
    "F01": "操作工反映料筒一段温度上不去，制品表面有冷斑，检查时发现该区加热圈不发热。",
    "F02": "连续几天发现料筒一段实测温度比设定值高十几度，换过原料也没变化，怀疑测温不准。",
    "F03": "设备运行两个多小时后开始报油温高，摸冷却器进出油管温差很小，车间水温正常。",
    "F04": "开机后系统压力只有 12 MPa 左右，锁模无力，调溢流阀没有改善。",
    "F05": "运行中油泵电机突然跳闸，热继电器动作，复位后再次运行又跳，电机外壳温度偏高。",
    "F06": "冷却水流量一直上不去，进水压力看起来正常，过滤器拆检发现水垢很多。",
    "F07": "变频器报过流停机，复位后能运行，但隔一两天又报一次。",
    "F08": "最近一个月制品重量波动变大，连续统计十模的注塑时间，离散明显比之前大。",
    "F09": "开合模过程中偶尔报编码器故障，重启后能恢复，一天出现两三次。",
    "F10": "安全门已经关到位，系统仍然提示未闭合，无法进行锁模动作。",
    "F11": "早班发现干燥机没有启动，面板不亮，同一路电源上其他辅机正常。",
    "F12": "最近周期比平时长了将近一秒，产量完不成，操作工说参数没人动过。",
    "F13": "平台上这台设备显示离线，现场看机器还在正常生产，重启网关也没用。",
}


def symptom_for(event):
    machine = event["machine"]
    return (
        f"{machine['site']}的 {machine['machine_id']}（{machine['model']}，{machine['line']}）"
        f"在 {fmt(event['start'])} 前后，{SYMPTOM_TEXT.get(event['fault_id'], '出现异常。')}"
    )


def anomaly_note(event):
    pieces = []
    for name, (amplitude, direction) in event["params"].items():
        if name == "__missing__":
            pieces.append("该窗口全部测点缺失")
            continue
        arrow = "升" if direction > 0 else "降"
        pieces.append(f"{name} {arrow}约 {abs(amplitude)}")
    if not pieces:
        return "无遥测越限，靠现场现象或人工判断"
    return "；".join(pieces)


def part_of(fault_id):
    fault = D.FAULTS[fault_id]
    for part in D.PARTS:
        if part[0] == fault["parts"]:
            return part
    return None


def build_knowledge(machines, events):
    rows = []
    state = {"n": 0}

    def add(machine, fault_id, reported, symptom, anomaly, hours):
        state["n"] += 1
        fault = D.FAULTS[fault_id]
        part = part_of(fault_id)
        onsite = fault["on_site"]
        in_warranty = machine["warranty_end"] > datetime(2026, 9, 1)
        settled = "保修内免费" if in_warranty else "客户付费"
        parts_used = f"{part[0]} {part[1]}" if part else ""
        parts_cost = part[5] if part else 0
        cost = 0 if in_warranty else int(hours * 220 + parts_cost)
        rows.append(
            [
                f"ZJ-2026-{state['n']:04d}",
                machine["machine_id"],
                machine["customer"],
                machine["model"],
                "保修内" if in_warranty else "已过保",
                fmt(reported),
                fault_id,
                symptom,
                anomaly,
                fault["cause"],
                f"按《{fault['section']}》排查并确认根因，处理后再观察 30 分钟。",
                fault["section"],
                onsite,
                parts_used,
                hours,
                settled,
                cost,
            ]
        )

    for event in events:
        if event["fault_id"] not in D.FAULTS:
            continue
        add(
            event["machine"],
            event["fault_id"],
            event["start"] - timedelta(hours=1),
            symptom_for(event),
            anomaly_note(event),
            round(random.uniform(1.0, 2.5) + (2.5 if D.FAULTS[event["fault_id"]]["on_site"] == "是" else 0.0), 1),
        )

    for fault_id, symptom in D.HIST_SYMPTOMS:
        machine = random.choice(machines)
        add(
            machine,
            fault_id,
            D.START - timedelta(days=random.randint(10, 900), hours=random.randint(0, 20)),
            symptom,
            "客户口述现象，平台数据未留存",
            round(random.uniform(1.0, 3.0) + (2.0 if D.FAULTS[fault_id]["on_site"] == "是" else 0.0), 1),
        )
    return rows


def build_test_set(machines, events):
    by_event = {event["event_id"]: event for event in events}
    index = {m["machine_id"]: m for m in machines}
    rows = []
    for event_id, case_id in D.TEST_CASES:
        event = by_event[event_id]
        machine = event["machine"]
        fault = D.FAULTS[event["fault_id"]]
        in_warranty = machine["warranty_end"] > datetime(2026, 9, 1)
        answer = {
            "故障ID": event["fault_id"],
            "原因": fault["cause"],
            "处置要点": f"按 {fault['section']} 排查；{fault['risk']}",
            "手册章节": fault["section"],
            "是否到场": fault["on_site"],
            "备件": (part_of(event["fault_id"]) or [""])[0],
            "保修判定": "保修内免费" if in_warranty else "已过保，需报价",
        }
        rows.append(
            [
                case_id, machine["machine_id"], machine["customer"], machine["model"],
                symptom_for(event), "",
                json.dumps(answer, ensure_ascii=False),
            ]
        )
    for item in D.AMBIGUOUS:
        machine = index[item["machine_id"]]
        rows.append(
            [
                item["case_id"], machine["machine_id"], machine["customer"],
                machine["model"], item["symptom"], item["note"],
                json.dumps(item["expected"], ensure_ascii=False),
            ]
        )
    write_csv(
        OUT / "工单_测试集.csv",
        ["用例编号", "设备编号", "客户", "机型", "现象描述", "备注", "标准答案"],
        rows,
    )
    return rows


def write_knowledge(rows):
    write_csv(
        OUT / "工单_知识库.csv",
        ["工单号", "设备编号", "客户", "机型", "保修状态", "报修时间", "故障ID",
         "现象描述", "相关测点及异常", "原因", "处置过程", "手册依据",
         "是否到场", "更换备件", "耗时(h)", "结算方式", "费用(元)"],
        rows,
    )


# --- 人读文档 -----------------------------------------------------------

def write_fault_tree():
    lines = [
        "# 故障诊断决策树（练习数据）",
        "",
        "> 本文档为虚构教学材料，用于练习远程诊断问答，不作为现场作业依据。",
        "> 结构对应 `故障码表.csv`，章节号可直接作为引用来源。",
        "",
    ]
    for fault_id, fault in D.FAULTS.items():
        lines.append(f"## {fault['section']} {fault_id} {fault['name']}")
        lines.append("")
        lines.append(f"- 分组：{D.MODULES[fault['module']]}　严重度：{fault['severity']}")
        lines.append(f"- 报警条件：{fault['alarm']}")
        lines.append(f"- 关键测点：{fault['params']}")
        lines.append(f"- 典型原因：{fault['cause']}")
        lines.append(f"- 复位方式：{fault['reset']}")
        lines.append(f"- 涉及备件：{fault['parts'] or '无'}")
        lines.append(f"- 通常是否需要到场：{fault['on_site']}")
        lines.append("")
        lines.append("先追问：")
        for index, question in enumerate(fault["questions"], start=1):
            lines.append(f"{index}. {question}")
        lines.append("")
        lines.append("排查步骤：")
        for index, step in enumerate(fault["diagnosis"], start=1):
            lines.append(f"{index}. {step}")
        lines.append("")
        lines.append(f"风险提示：{fault['risk']}")
        lines.append("")
    (OUT / "故障树.md").write_text("\n".join(lines), encoding="utf-8")


def write_master_notes(machines, events, knowledge, test_rows, alarms):
    real = [a for a in alarms if event_of_alarm(a, events)]
    false = [a for a in alarms if not event_of_alarm(a, events)]
    event_list = [
        "| 事件 | 设备 | 故障ID | 类型 | 开始时间 | 时长(h) | 注入测点变化 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    mode_label = {
        "abrupt": "突变",
        "slow": "渐变",
        "amb": "仅现象",
        "spike": "瞬时尖峰（误报样本）",
    }
    for event in events:
        event_list.append(
            f"| {event['event_id']} | {event['machine_id']} | {event['fault_id']} "
            f"| {mode_label[event['mode']]} | {fmt(event['start'])} "
            f"| {(event['end'] - event['start']).total_seconds() / 3600:.1f} "
            f"| {anomaly_note(event)} |"
        )

    lines = [
        "# 主数据说明（全部为合成数据）",
        "",
        "本文件描述 `数据包/` 的生成结果，由 `run.py` 自动生成，种子固定可复现。",
        "所有公司、机型、故障机理和参数均为虚构的教学材料，不可用于生产决策。",
        "",
        "## 1. 文件清单",
        "",
        "| 文件 | 行数/规模 | 内容 |",
        "| --- | --- | --- |",
        f"| `客户与站点.csv` | {len(D.SITES)} | 六个客户站点及服务等级 |",
        f"| `设备主表.csv` | {len(machines)} | 设备档案，含型号、出厂编号、保修截止 |",
        f"| `保修与服务合同.csv` | {len(machines)} | 每台设备的保修与 SLA |",
        f"| `故障码表.csv` | {len(D.FAULTS)} | 故障目录与报警条件 |",
        f"| `故障树.md` | 全文 | 每个故障的追问、排查步骤和风险 |",
        f"| `测点表.csv` | {len(D.PARAM_ROWS)} | 工艺与状态测点定义 |",
        f"| `备件物料清单.csv` | {len(D.PARTS)} | 备件主数据与适用机型 |",
        f"| `服务通报.csv` | {len(D.SERVICE_BULLETINS)} | 批次性问题通报 |",
        "| `遥测_M***_202607.csv` | 2976 行/台 | 15 分钟采样的工艺时序，含注入异常 |",
        f"| `报警记录.csv` | {len(alarms)} | 按阈值扫描出的报警，含误报 |",
        f"| `工单_知识库.csv` | {len(knowledge)} | 历史工单，可作相似案例检索 |",
        f"| `工单_测试集.csv` | {len(test_rows)} | 评测用例，含标准答案与含混样本 |",
        "",
        "## 2. 遥测数据",
        "",
        f"时间为 2026-07-01 00:00 至 2026-07-31 23:45，间隔 {D.STEP_MIN} 分钟，",
        f"覆盖 {'、'.join(TELEMETRY_MACHINES)} 六台设备。基线按型号的功率与温度设定生成，",
        "叠加正态噪声；异常窗口在事件时间附近注入。窗口之外没有越限样本。",
        "",
        "## 3. 注入事件",
        "",
        "\n".join(event_list),
        "",
        "## 4. 报警与误报",
        "",
        f"共生成 {len(alarms)} 条报警记录，其中 {len(real)} 条对应注入异常，",
        f"{len(false)} 条为阈值抖动造成的疑似误报。报警逻辑带 2 个采样的确认与回差，",
        "模拟真实 SCADA 的抖动。",
        "",
        "## 5. 工单与评测集",
        "",
        f"历史工单 {len(knowledge)} 条，其中一部分与注入事件对应（可用遥测核实），",
        "一部分只有客户口述现象（模拟平台数据未留存）。",
        f"评测集 {len(test_rows)} 条，前 12 条有明确真值，后 3 条为含混样本，",
        "期望系统追问或转人工而不是硬答。",
        "",
        "## 6. 已知局限",
        "",
        "- 数据为合成生成，不代表任何真实机型参数。",
        "- 遥测只覆盖六台设备，其余设备的工单没有对应时序。",
        "- 报警扫描不设延时和回差之外的复杂逻辑，误报率高于真实系统。",
        "- 工单现象由模板加随机值生成，多条之间可能看出模板痕迹。",
        "- 备件价格、库存与货期均为示意值。",
    ]
    (OUT / "主数据说明.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    random.seed(D.SEED)
    machines = build_machines()
    write_master_data(machines)
    events = build_events(machines)
    alarms = write_telemetry(machines, events)
    write_alarms(alarms, events)
    knowledge = build_knowledge(machines, events)
    write_knowledge(knowledge)
    test_rows = build_test_set(machines, events)
    write_fault_tree()
    write_master_notes(machines, events, knowledge, test_rows, alarms)
    print(
        f"完成：{len(machines)} 台设备，{len(events)} 个注入事件，"
        f"{len(alarms)} 条报警，{len(knowledge)} 条历史工单，"
        f"{len(test_rows)} 条评测用例。"
    )
    print(f"输出目录：{OUT}")


if __name__ == "__main__":
    main()
