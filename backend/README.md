# FinAssistant 后端（FastAPI）

面向前端的统一 API，提供认证与以下功能：股票综合诊断、大盘板块指数分析（行业/概念）、金融投教问答、资讯查询解读、以及通用投研检索。

## 快速开始
```bash
cd FinAssistant/backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认允许前端来源：`http://localhost:5173`（可在 `app/core/config.py` 中通过环境变量调整）。

## 主要接口
- 认证
  - `POST /auth/login`（OAuth2 密码模式，表单：username/password）
  - `POST /auth/register`
- 用户
  - `GET /users/me`
  - `GET /users/` | `POST /users/` | `PUT /users/{id}` | `DELETE /users/{id}`
- 功能
  - `GET /features/research?query=...&mode=vector|hybrid|rerank`
  - `GET /features/stocks/diagnosis?code=600519`
  - `GET /features/indices/overview?kind=industry|concept`
  - `GET /features/qa?question=...`
  - `GET /features/news?query=...&limit=10`

> 以上为演示实现，可逐步对接 MySQL/Milvus/LLM 等真实数据源。

## 配置
- `FA_JWT_SECRET`：JWT 秘钥
- `FA_SQLITE_URL`：SQLite/其他数据库连接串（默认 `sqlite:///./fa.db`）
- `FA_FRONTEND_ORIGIN`：允许的前端域

## 对接前端
- 在前端的 `services/*.ts` 中，将 mock 替换为真实调用：
  - 登录：`POST /auth/login` 获取 `access_token`
  - 鉴权：在请求头加入 `Authorization: Bearer <token>`
  - 检索/诊断/指数/问答/资讯：对应 `features` 路由

## 下一步
- 将 `features` 中的 TODO 与模块内 `services` 层对接：
  - MySQL：新闻与指标数据查询（参考项目中的数据结构与现有脚本）
  - Milvus：向量检索/混合检索
  - LLM：金融投教问答与解读
- 增加分页、过滤、排序与缓存
- 加入审计日志与角色权限细化（RBAC）
