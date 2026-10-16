# 运行时数据

本目录存放运行期生成的数据，不纳入版本控制。

| 路径 | 说明 |
| --- | --- |
| `app.db` | SQLite 数据库（首次启动自动创建并导入诊断数据集） |
| `uploads/` | 上传的原始文档 |
| `ocr/` | OCR 中间渲染图片，按文档编号分目录 |
| `server.log` / `server.log.error` | 后台启动时的输出与错误日志 |
| `server.pid` | 后台服务的进程号 |
| `diagnosis-eval.json` | 诊断评测结果（运行 `tools/run_diagnosis_eval.py` 后生成） |

清空本目录即可把系统恢复到初始状态：删除 `app.db` 后重启，会重新建库并导入数据集。
