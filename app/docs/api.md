# 后端接口

所有接口使用 JSON 通信，前端负责转换为业务化展示。

## 认证与账号

```text
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me
POST   /api/auth/change-password
GET    /api/admin/users
POST   /api/admin/users
PATCH  /api/admin/users/{id}
POST   /api/admin/users/{id}/reset-password
POST   /api/admin/users/{id}/logout
```

## 诊断与会话

```text
POST   /api/diagnosis                诊断（流式 NDJSON）
                                      可带 service_request_id，结论回写工单
GET    /api/conversations
POST   /api/conversations
GET    /api/conversations/{id}
PATCH  /api/conversations/{id}
DELETE /api/conversations/{id}
```

## 服务工单

```text
GET    /api/service-requests/options  状态、来源与优先级取值
GET    /api/service-requests          支持 status / customer / machine_code 过滤
POST   /api/service-requests          登记工单（内部角色）
GET    /api/service-requests/{id}
PATCH  /api/service-requests/{id}     状态、优先级、处理人与关闭备注
```

客户账号只能读取本企业工单，不能建立或修改工单。

诊断流事件类型：`conversation`、`skill`、`machine`、`status`、`citations`、
`tool`、`diagnosis`、`delta`、`done`、`error`。

## 页面路由

```text
GET    /              诊断工作台（客户账号跳转到 /portal）
GET    /service       服务工单台
GET    /portal        客户服务门户（只读）
GET    /documents     知识库与资料
GET    /skills        诊断 Skill
GET    /users         用户管理
GET    /login         登录
```

## 设备与主数据

```text
GET    /api/customers
GET    /api/machine-models
GET    /api/machines                  支持 customer / model / q 过滤
GET    /api/machines/{machine_code}
GET    /api/machines/{machine_code}/latest
GET    /api/machines/{machine_code}/telemetry
GET    /api/machines/{machine_code}/alarms
GET    /api/faults
GET    /api/spare-parts
GET    /api/service-bulletins
GET    /api/tickets
```

## 知识库

```text
GET    /api/chunk-strategies
GET    /api/documents
GET    /api/documents/{id}
POST   /api/documents/upload
POST   /api/documents/{id}/preview
POST   /api/documents/{id}/publish
POST   /api/documents/{id}/reprocess
POST   /api/documents/{id}/ocr
GET    /api/documents/{id}/ocr-pages
PUT    /api/documents/{id}/ocr-pages
DELETE /api/documents/{id}
GET    /api/tasks/{task_id}
```

## Skill

```text
GET    /api/skills
POST   /api/skills/upload
POST   /api/skills/{skill_id}/publish
POST   /api/skills/{skill_id}/disable
DELETE /api/skills/{skill_id}
```

## 管理与评测

```text
GET    /api/admin/diagnosis-runs
GET    /api/admin/model-calls
GET    /api/admin/tool-calls
GET    /api/admin/audit-logs
GET    /api/admin/metrics
GET    /api/admin/evaluation/cases
POST   /api/admin/evaluation/run
GET    /api/health
```
