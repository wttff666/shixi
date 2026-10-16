# 诊断评测

评测用例来自 `remotediag/数据包/工单_测试集.csv`，共 15 条：12 条有明确真值，
3 条为信息不足样本（期望系统追问而不是硬答）。

## 运行

```powershell
cd D:\shixi\zuoye\app
..\.venv\Scripts\python.exe .\tools\run_diagnosis_eval.py --limit 5
```

或通过接口：

```text
POST /api/admin/evaluation/run?limit=5
```

结果写入 `data/diagnosis-eval.json`，含每条用例的期望故障、系统输出、置信度、
是否追问与到场建议。

## 指标口径

| 指标 | 定义 |
| --- | --- |
| `diagnosis_accuracy` | 有真值用例中，系统输出的故障 ID 与标准答案一致的比例 |
| `follow_up_accuracy` | 信息不足用例中，系统给出追问或未给出高置信结论的比例 |
| `over_ask_rate` | 有真值用例中，系统仍触发追问的比例（越低越好） |
| `false_dispatch_rate` | 标准答案为不到场、系统却建议到场的比例 |
| `missed_dispatch_rate` | 标准答案为到场、系统却建议远程处理的比例 |

## 当前基线

在默认数据集与 `REFERENCE_DATE=2026-07-31` 配置下：

```text
diagnosis_accuracy  1.00
follow_up_accuracy  1.00
over_ask_rate       0.17
false_dispatch_rate 0.00
missed_dispatch_rate 0.00
```

指标随数据集与故障树更新而变化，接入客户真实数据后需重新校准。
