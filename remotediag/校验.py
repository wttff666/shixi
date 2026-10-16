"""校验生成的数据包：事件窗口外的样本不应越限，报警应能对应到注入事件。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

import domain as D


OUT = Path(__file__).resolve().parent / "数据包"
TELEMETRY_MACHINES = ["M001", "M004", "M007", "M010", "M013", "M016"]


def load(name):
    return list(csv.DictReader(io.open(OUT / name, encoding="utf-8-sig")))


def main():
    alarms = load("报警记录.csv")
    print(f"报警总数: {len(alarms)}")

    windows = {}
    for event_id, machine_id, fault_id, mode, offset, duration, params in D.EVENTS:
        if mode == "amb":
            continue
        start = D.START + timedelta(hours=offset)
        windows.setdefault(machine_id, []).append(
            (start, start + timedelta(hours=duration), set(params))
        )

    violations = 0
    for machine_id in TELEMETRY_MACHINES:
        rows = load(f"遥测_{machine_id}_202607.csv")
        machine_windows = windows.get(machine_id, [])
        for row in rows:
            moment = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M")
            inside = any(
                start <= moment < end
                for start, end, _ in machine_windows
            )
            if inside:
                continue
            for name, (label, threshold, predicate) in D.ALARM_RULES.items():
                if row[name] and predicate(float(row[name])):
                    violations += 1
                    if violations <= 10:
                        print(
                            f"  窗口外越限: {machine_id} {row['timestamp']} "
                            f"{name}={row[name]} ({threshold})"
                        )
    print(f"事件窗口外越限样本: {violations}")

    # 每个报警的触发时间应落在某个事件窗口内
    unmatched = []
    for alarm in alarms:
        moment = datetime.strptime(alarm["触发时间"], "%Y-%m-%d %H:%M")
        matched = any(
            start - timedelta(minutes=30) <= moment <= end + timedelta(minutes=30)
            for start, end, _ in windows.get(alarm["设备编号"], [])
        )
        if not matched:
            unmatched.append(alarm)
    print(f"无法对应到事件窗口的报警: {len(unmatched)}")
    for alarm in unmatched:
        print("   ", alarm["报警号"], alarm["设备编号"], alarm["测点"], alarm["触发时间"])

    tickets = load("工单_知识库.csv")
    missing_part = [
        row["工单号"]
        for row in tickets
        if not row["更换备件"] and D.FAULTS[row["故障ID"]]["parts"]
    ]
    print(f"工单缺少应换备件记录: {len(missing_part)}")
    print("校验完成")


if __name__ == "__main__":
    main()
