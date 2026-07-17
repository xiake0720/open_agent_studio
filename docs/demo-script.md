# OpenAgent Studio 5-8 分钟演示脚本

## 0:00-0:30 项目定位

说明这不是普通聊天壳，而是可切换模型、可观察 Agent 执行过程、可审计和可回放的面试型智能体工作台。强调当前使用 GLM 5.1 等 OpenAI-compatible 模型，不依赖 OpenAI API Key。

## 0:30-1:30 普通聊天与模型切换

- 新建会话，选择 GLM 5.1。
- 输入：“请用中文解释 OpenAI Agents SDK 的 Runner 是做什么的。”
- 展示 SSE 流式输出、消息落库和右侧 `run.started` / `run.completed`。
- 切换另一个模型再次提问，展示消息记录中的实际模型名称。

## 1:30-3:00 技术报错与自动路由

- 模式选择 Auto。
- 输入：`TypeError: object NoneType can't be used in 'await' expression`。
- 展示 `route.decision -> tech`、`ask_tech_expert`、`explain_error_signature` 的工具参数、输出和耗时。
- 强调 TriageAgent 保留最终答复控制权，TechAgent 作为工具提供专业分析。

## 3:00-4:30 电商文案审核

- 可先手动选择 Ecommerce，再用 Auto 演示一次。
- 输入：“把这条标题改得更像天猫风格，并检查违规词：史上最低！全网第一！绝对治愈失眠。”
- 展示 `check_sensitive_words` 返回风险词和替代表达，以及最终优化文案。

## 4:30-6:30 多模型 Compare + Judge

- 选择 Compare 模式并勾选 2-3 个模型。
- 输入：“为智能体工作台写一段 618 活动文案，并给出三个核心卖点。”
- 展示模型并发卡片、各自耗时、单模型失败隔离、Judge 五维评分和最终推荐。
- 右侧展示 `compare.model.*` 与 `judge.*` 时间线，数据库展示 `model_compares` / `model_compare_results`。

## 6:30-7:30 收尾

打开架构图，说明第三方 Provider 统一接入、SQLite 审计、Triage manager 模式与 SSE 事件规范化。后续可扩展真实图片生成、Guardrails、HITL、Docker 部署和评估集。

## 演示前检查

- 后端 `GET /api/health` 正常，前端能加载模型列表。
- `.env` 中实际使用的 Provider Key 已配置，数据库不保存明文 Key。
- 至少两个文本模型可调用；如只演示一个 Provider 的多个模型，先验证其限流。
- 清理无关会话，准备好四段示例输入。
- 浏览器宽度足够展示左侧会话、中间回答和右侧执行过程。
