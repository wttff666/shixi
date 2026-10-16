# 服务层

业务逻辑集中在这里，路由只做参数校验与响应组织。

## 诊断与决策

| 文件 | 说明 |
| --- | --- |
| `diagnosis.py` | 诊断编排：识别设备、调用工具、选出最可能的故障、生成结构化结论与追问 |
| `service_request.py` | 服务工单编号、创建、状态推进与诊断结论回写 |
| `dispatch.py` | 派工建议（远程/上门、SLA、预计工时、备件、二线复核）与对外话术生成 |
| `warranty.py` | 保修状态与结算方式判定（质保内 / 批次性通报 / 过保收费） |
| `skill_runtime.py` | 声明式 Skill 的加载、匹配与检索范围过滤 |

## 检索

| 文件 | 说明 |
| --- | --- |
| `retrieval.py` | 词法检索（中文 2-gram + 故障码 + 章节号加权） |
| `hybrid_retrieval.py` | 混合检索：词法召回 + 向量召回归一化融合 |
| `retrieval_facade.py` | 检索入口，按配置分派词法或混合 |
| `vector_store.py` | 向量生成、余弦/`<=>` 检索与索引建立 |
| `vector_types.py` | 跨后端向量列类型（SQLite 存 JSON，PostgreSQL 存 `vector(n)`） |
| `embedding.py` | BGE-M3 调用（子进程常驻）与可用性检查 |
| `embedding_worker.py` | BGE-M3 子进程，按行读取文本返回向量 |

## 模型与工具

| 文件 | 说明 |
| --- | --- |
| `model_gateway.py` | 统一模型调用、提示词组装、流式输出与本地兜底回答 |
| `mcp_gateway.py` | MCP stdio 客户端，启动工具进程并做 JSON-RPC 交互 |

## 文档与解析

| 文件 | 说明 |
| --- | --- |
| `parser.py` | TXT/Markdown/DOCX/PDF 解析与文本清洗 |
| `chunker.py` | 四种切片策略（标点/段落/标题/固定长度） |
| `ocr.py` | 扫描件 OCR 调度与结果整理 |
| `ocr_worker.py` | PaddleOCR 子进程 |
| `task_runner.py` | 后台任务线程池与 OCR 任务执行 |

## 数据与账号

| 文件 | 说明 |
| --- | --- |
| `seed.py` | 从诊断数据集导入主数据并构建知识切片 |
| `auth.py` | 密码哈希、登录会话、角色标签与客户可见范围 |
| `conversation.py` | 会话与消息的读写 |
| `evaluation.py` | 诊断评测：加载用例、跑诊断、计算指标 |
| `audit.py` | 审计日志写入 |
