# 后端

FastAPI 应用。启动入口 `main.py`，默认端口 8091（见 `app/start.ps1`）。

## 本目录文件

| 文件 | 说明 |
| --- | --- |
| `main.py` | 应用装配：路由注册、启动初始化（建库、导入数据集、建初始账号）、页面路由与静态资源挂载 |
| `config.py` | 配置读取与路径解析（模型网关、MCP、数据集、OCR/Embedding、向量后端） |
| `database.py` | 引擎与会话、建表、pgvector 扩展与旧库兼容处理 |
| `models.py` | 数据模型：客户/设备/保修/备件/通报/故障定义/工单、知识库、会话与诊断运行、账号与审计 |
| `schemas.py` | 接口出入参模型 |
| `deps.py` | 依赖：当前登录用户、角色校验 |

## 子目录

| 目录 | 说明 |
| --- | --- |
| `routers/` | HTTP 接口与页面路由，见 `routers/README.md` |
| `services/` | 业务服务（诊断、检索、模型、工具、解析、OCR 等），见 `services/README.md` |
| `tests/` | 自动化测试，见 `tests/README.md` |

## 数据流概览

```text
请求 -> 路由 -> 服务层（诊断编排 / 检索 / 工具 / 模型）
     -> 数据模型（关系库）与 MCP 工具进程
```

配置项见 `config.py`，环境变量模板见 `app/.env.example`。
