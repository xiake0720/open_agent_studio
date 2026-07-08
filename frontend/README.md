# OpenAgent Studio Frontend

这是 OpenAgent Studio 的正式前端包，基于 React + TypeScript + Vite 构建，已按当前后端 Day10 以及后续规划接口预留。

## 已适配接口

当前已实际接入：

- `GET /api/health`
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `DELETE /api/conversations/{conversation_id}`
- `GET /api/conversations/{conversation_id}/messages`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/models?enabled_only=true`
- `POST /api/agent-runs`
- `GET /api/agent-runs/{run_id}`
- `GET /api/agent-runs/{run_id}/stream`
- `POST /api/chat`，作为流式接口未就绪时的兼容回退

已预留但后端可以后续再实现：

- `GET /api/agent-runs/{run_id}/events`
- `GET /api/agent-runs/{run_id}/tool-calls`
- `POST /api/images/generate`
- `GET /api/assets`
- `POST /api/model-compare`

这些预留接口不会影响当前 Day10 运行。不存在时前端会优雅降级。

## 明暗主题

右上角有太阳/月亮切换按钮：

- 夜间模式：默认深色 Agent 工作台风格
- 白天模式：干净明亮的生产级控制台风格

主题会保存到 `localStorage`，刷新页面后保持上次选择。

## 使用方式

把本目录替换到项目根目录：

```text
open_agent_studio/
├── backend/
└── frontend/
```

安装依赖并启动：

```bash
cd frontend
npm install
npm run dev
```

后端保持：

```bash
uvicorn backend.app.main:app --reload --port 9099
```

默认使用 Vite 代理：

```env
VITE_API_BASE_URL=/api
VITE_BACKEND_URL=http://127.0.0.1:9099
```

生产部署时，如果前端和后端同域，保留 `VITE_API_BASE_URL=/api` 即可。如果前后端分离部署，可以改成后端完整地址。

## 设计说明

本前端不是简单 demo，而是按后续上线准备的工作台结构：

- 左侧会话列表、搜索、新建、删除
- 中间 ChatGPT 风格对话区
- 顶部模型选择、Agent 模式选择、明暗主题切换、执行面板开关
- 右侧 Agent Trace 面板，展示 SSE 事件和运行状态
- 对 `code != 0` 的业务错误做统一提示
- 对未来工具调用、模型对比、图片生成、Run Events 落库做了 API 封装预留
