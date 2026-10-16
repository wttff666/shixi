# 测试

```powershell
cd D:\shixi\zuoye\app\backend
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

| 文件 | 说明 |
| --- | --- |
| `test_api.py` | 端到端接口测试：登录与页面、主数据、诊断（清晰/含混/无设备号）、客户数据隔离、角色权限、知识库上传发布、Skill 上传发布、评测指标、会话落库 |
| `test_vector_backend.py` | 向量层单元测试：余弦相似度、pgvector 字面量格式、BGE-M3 维度（环境不可用时跳过） |

测试使用独立的 `data/test_app.db` 与临时上传目录，运行结束后自动清理，
不影响开发库。诊断测试需要 `remotediag/数据包` 存在。
