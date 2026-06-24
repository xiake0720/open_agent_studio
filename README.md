# OpenAgent Studio

OpenAgent Studio 是一个基于 React、FastAPI、SQLite 和 OpenAI Agents SDK 构建的多模型智能体工作台。

项目目标不是做一个普通聊天机器人，而是做一个可观察、可审计、可扩展的 Agent Runtime 演示系统。

## 核心目标

- ChatGPT 风格多轮对话界面
- 多模型切换
- OpenAI-compatible 模型接入
- OpenAI Agents SDK 智能体运行
- 工具调用
- Agent 执行过程可视化
- SQLite 本地会话存储
- 多 Agent 分工
- 电商运营 Agent
- 技术助手 Agent
- 图片生成 Agent
- 多模型对比评测

## 技术栈

### Frontend

- React
- TypeScript
- Vite

### Backend

- FastAPI
- Python
- OpenAI Agents SDK
- SQLAlchemy
- SQLite

## 当前进度

### Day 1

- [x] 创建项目结构
- [x] 初始化 FastAPI 后端
- [x] 初始化 React 前端
- [x] 完成 `/api/health` 健康检查接口
- [x] 前端成功请求后端健康检查接口

## 启动后端

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 9099