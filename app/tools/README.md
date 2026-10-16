# Deployment Tools

本目录是现场部署与运维脚本。脚本不依赖网络的服务都可在内网运行。

## 诊断评测

对内置评测用例（`remotediag/数据包/工单_测试集.csv`）跑一遍完整诊断链路，
输出首次诊断准确率、追问触发准确率、误派工率等指标。

```powershell
cd D:\shixi\zuoye\app
..\.venv\Scripts\python.exe .\tools\run_diagnosis_eval.py --limit 5
```

结果写入 `data\diagnosis-eval.json`，含每条用例的期望与模型输出对比。

## 构建 BGE-M3 向量

为已发布的知识切片生成向量（混合检索用）。需要先安装 BGE-M3。

```powershell
..\.venv\Scripts\python.exe .\tools\build_embeddings.py
```

## 安装 BGE-M3

```powershell
.\tools\install_bge.ps1 -Drive D
```

脚本会创建 `D:\BGE-M3`、安装依赖并从 ModelScope 下载模型。

## 安装 OCR

```powershell
.\tools\install_ocr.ps1 -Drive D
```

脚本会在指定盘创建 `PaddleOCR` 目录、建立独立虚拟环境、安装 PaddleOCR，
并把模型缓存与解释器路径写入 `app\.env`。

客户机器需要：Windows、Python 3.12（或用 `-PythonExe` 指定）、首次安装可联网、
目标盘至少 3 GB 可用空间。

## PostgreSQL + pgvector

一条命令完成起库、装驱动与数据迁移（需先装好 Docker Desktop）：

```powershell
cd D:\shixi\zuoye\app
.\tools\setup_pgvector.ps1 -UpdateEnv
```

`migrate_to_postgres.py` 把 `app\data\app.db` 的内容搬到 PostgreSQL，含
`chunk_embeddings` 里的 1024 维向量，并建好 HNSW 余弦索引。加 `--dry-run`
只统计行数：

```powershell
..\.venv\Scripts\python.exe .\tools\migrate_to_postgres.py --dry-run `
  --target-url postgresql+psycopg://remotediag:密码@127.0.0.1:5432/remotediag
```

细节见 `docs\database.md`。
