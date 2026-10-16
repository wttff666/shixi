# 应用代码

产品代码入口。后端是 FastAPI，前端是原生页面（无构建工具）。

## 目录

```text
app/
  backend/       FastAPI、数据模型、诊断与检索服务
  frontend/      诊断工作台、知识库、诊断 Skill、用户管理页面
  data/          数据库、上传文件与运行日志
  docs/          架构、接口、存储与评测文档
  tools/         现场安装与运维脚本
```

## 启动

```powershell
cd D:\shixi\zuoye\app
.\start.bat              # 双击即可，启动后自动提示地址
.\start.ps1              # 前台，开发时看日志
.\start-background.ps1   # 后台，关闭终端后继续运行
.\stop-background.ps1    # 停止后台服务
```

默认地址 `http://127.0.0.1:8091`。端口可用 `-Port` 参数调整。

后台服务会一直运行到执行 `stop-background.ps1` 或手动结束进程为止。若浏览器提示
`ERR_CONNECTION_REFUSED`，说明服务没有在运行，重新执行 `start.bat` 即可。

首次启动会自动建库，并从 `../remotediag/数据包` 导入主数据和知识切片。

## 本目录文件

| 文件 | 说明 |
| --- | --- |
| `.env` | 本地配置（模型、检索、路径、初始账号）。含密钥，不要外发 |
| `.env.example` | 配置模板，含全部可配置项说明 |
| `.gitignore` | 忽略数据库、上传文件、缓存与虚拟环境 |
| `requirements.txt` | 运行依赖 |
| `requirements-postgres.txt` | 切换到 PostgreSQL 时额外需要的驱动 |
| `start.ps1` | 前台启动 |
| `start.bat` | 双击启动（调用 `start-background.ps1`，启动后提示访问地址） |
| `start-background.ps1` | 后台启动并写 PID 与日志 |
| `stop-background.ps1` | 停止后台服务 |
| `README.md` | 本文件 |

## 初始账号

```text
admin   / admin_change_me    系统管理员（首次登录需改密码）
agent01 / agent_demo_2026    客服工程师
tech01  / tech_demo_2026     技术支持工程师
cust01  / cust_demo_2026     客户联系人（镇江精工注塑厂）
```

详见 `docs/` 目录。
