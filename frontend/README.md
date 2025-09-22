# FinAssistant 前端（Vue 3 + Vite + TypeScript）

美观、简洁的智能投研助手前端，含用户管理（本地存储演示实现）、登录注册、仪表盘、投研检索页与管理员用户管理页。UI 基于 Element Plus。

## 功能特性
- 登录 / 注册（Pinia + localStorage 演示）
- 路由鉴权与角色控制（Admin 专属“用户管理”）
- 仪表盘（KPI 卡片 + 概览）
- 投研检索页（向量/混合/重排 模式切换，演示结果列表）
- 用户管理（增/删/改/查，本地存储）

## 目录结构
```
frontend/
  ├─ index.html
  ├─ package.json
  ├─ tsconfig.json
  ├─ vite.config.ts
  └─ src/
     ├─ main.ts
     ├─ App.vue
     ├─ types.d.ts
     ├─ router/
     │   └─ index.ts
     ├─ store/
     │   └─ auth.ts
     ├─ services/
     │   ├─ auth.ts
     │   ├─ users.ts
     │   └─ research.ts
     └─ pages/
         ├─ Shell.vue
         ├─ Login.vue
         ├─ Register.vue
         ├─ Dashboard.vue
         └─ Research.vue
```

## 本地运行
```bash
# 进入目录
cd FinAssistant/frontend

# 安装依赖（建议 Node 18+）
npm install

# 启动开发服务
npm run dev

# 构建生产包
npm run build

# 预览构建产物
npm run preview
```

## 使用说明
- 打开 `http://localhost:5173`
- 首次登录：任意用户名/密码将自动创建演示账户（角色默认为 user）
- 注册页可选择角色（user/admin）
- 登录后可访问：
  - “仪表盘”：概览
  - “投研助手”：输入问题，选择检索模式（演示数据）
  - “管理/用户管理”：仅 Admin 可见，支持本地用户增删改查

## 与后端集成（可选）
- 替换 `src/services/*.ts` 中的逻辑为真实 API 调用（Axios）
- 典型接口：`/auth/login`、`/auth/register`、`/users`、`/research/search` 等
- 在 `vite.config.ts` 配置代理或在 Axios 设置 `baseURL`

## 设计说明
- 技术栈：Vue 3、Vite、TypeScript、Pinia、Vue Router、Element Plus
- 状态与鉴权：Pinia 存储当前用户，路由守卫限制访问和角色权限
- UI：Element Plus 组件 + 简洁布局（侧边导航 + 顶部用户栏）

## 后续可扩展
- 接入真实登录态（JWT）与刷新机制
- 统一错误处理与消息提示
- 接入真实投研检索接口、加入可视化图表
- 国际化（i18n）与深色主题
