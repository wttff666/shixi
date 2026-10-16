# 数据存储与向量后端

## 当前默认

开发阶段默认使用 SQLite，单文件、零安装：

```text
app/data/app.db
```

首次启动时会自动建表，并从诊断数据集（`remotediag/数据包`）导入客户、设备、
保修、备件、服务通报、故障定义、历史工单，以及由故障树与服务通报构建的知识切片。

## 主要数据表

| 表 | 内容 |
| --- | --- |
| `customers` / `machines` / `machine_models` | 客户、设备档案与机型谱系 |
| `warranties` | 保修与服务合同 |
| `spare_parts` / `service_bulletins` | 备件主数据与服务通报 |
| `fault_definitions` | 故障树节点（含追问与排查步骤） |
| `tickets` | 历史服务工单 |
| `documents` / `document_chunks` / `chunk_embeddings` | 知识库与向量 |
| `conversations` / `messages` | 诊断会话 |
| `diagnosis_runs` | 诊断结论与运行记录 |
| `model_calls` / `tool_calls` / `audit_logs` | 模型调用、工具调用与审计 |
| `users` / `auth_sessions` | 账号与会话 |

## 可切换的向量后端

| 后端 | 适用场景 | 检索实现 |
| --- | --- | --- |
| `sqlite` | 本机开发、几千条切片 | Python 逐条算余弦 |
| `pgvector` | 客户现场、几万条以上切片 | PostgreSQL `<=>` 算子 + HNSW 索引 |

相关配置（`app/.env`）：

```env
DATABASE_URL=sqlite:///data/app.db
VECTOR_BACKEND=sqlite
EMBEDDING_DIM=1024
```

`VECTOR_BACKEND` 不填时按 `DATABASE_URL` 自动推断。切换后端只改这两行。

## 切换到 PostgreSQL + pgvector

推荐用 Docker 镜像 `pgvector/pgvector:pg16`，数据文件放在 `D:\PostgreSQL\data`。

### 一条命令

先安装 Docker Desktop 并启用 WSL2，启动到托盘图标变绿，然后：

```powershell
cd D:\shixi\zuoye\app
.\tools\setup_pgvector.ps1 -UpdateEnv
```

脚本会依次完成：检查 Docker、建数据目录、起容器、等数据库就绪、装 psycopg 驱动、
迁移 SQLite 数据、把 `DATABASE_URL` 和 `VECTOR_BACKEND` 写进 `.env`。

### 验证

```powershell
cd D:\shixi\zuoye\app
.\stop-background.ps1
.\start-background.ps1
..\.venv\Scripts\python.exe .\tools\run_diagnosis_eval.py
```

## 回滚

把 `.env` 里的 `DATABASE_URL` 改回 SQLite、`VECTOR_BACKEND` 改成 `sqlite`，
重启服务即可。SQLite 原库一直在，迁移过程不修改它。

## 注意事项

- 向量维度固定 1024（BGE-M3）。换 embedding 模型时要清空 `chunk_embeddings`、
  改 `EMBEDDING_DIM` 并重新执行 `tools/build_embeddings.py`。
- 数据库密码只写在 `.env` 和连接串里，不要提交到版本库或截图外发。
- 生产环境还需补：定时备份、连接池上限和只读账号。
