# 路由层

每个文件对应一组 HTTP 接口，业务逻辑放在 `services/`。

| 文件 | 前缀 | 说明 |
| --- | --- | --- |
| `auth.py` | `/api/auth` | 登录、登出、当前用户、修改密码；写入安全 Cookie |
| `diagnosis.py` | `/api/diagnosis` | 诊断主接口，流式返回（NDJSON），编排检索、工具与结构化结论 |
| `conversations.py` | `/api/conversations` | 诊断会话的增删改查与消息历史 |
| `devices.py` | `/api` | 客户、机型、设备档案、实时数据、报警、故障树、备件、通报、工单查询 |
| `service_requests.py` | `/api/service-requests` | 服务工单：登记、列表、详情与状态流转（客户账号只读） |
| `documents.py` | `/api/documents` | 知识库：上传、解析、切片预览、发布、OCR、校对与删除 |
| `skills.py` | `/api/skills` | 声明式 Skill 上传、发布、停用与删除 |
| `tasks.py` | `/api/tasks` | 后台任务状态查询（如 OCR） |
| `users.py` | `/api/admin/users` | 用户管理：新增、角色调整、停用、重置密码、强制退出 |
| `admin.py` | `/api/admin` | 诊断运行、模型调用、工具调用、审计日志与服务质量指标 |
| `evaluation.py` | `/api/admin/evaluation` | 诊断评测用例与运行 |
| `__init__.py` | - | 包标识 |

权限说明：

- `devices.py` 与 `diagnosis.py` 对客户账号做数据隔离，只能访问本企业设备。
- 诊断只有内部角色可用；客户账号调用返回 403。
- 建立或修改工单仅内部角色可用，客户账号只能读取本企业工单。
- 知识库、Skill 与用户管理仅对应管理员角色可访问。
- 管理与评测接口仅服务主管与系统管理员可访问。
