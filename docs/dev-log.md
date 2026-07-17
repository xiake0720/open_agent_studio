# 开发记录

## Day 24-30

- Day 24：新增 EcommerceAgent，接入 `check_sensitive_words`，支持手动 Ecommerce 模式。
- Day 25：新增结构化 RouteDecision 与 Auto 路由，保留规则降级。
- Day 26：TriageAgent 通过 Agent.as_tool 调用 Tech/Ecommerce/Image 专家，时间线展示专家工具调用。
- Day 27：模型 API 返回安全的完整能力信息，前端选择模型并通过 `primary_model_id` 传递，消息保存实际模型。
- Day 28：新增 2-3 模型并发对比、失败隔离、结果持久化和对比卡片。
- Day 29：新增 ModelJudgeAgent、五维评分、推荐结论和规则降级。
- Day 30：补充 README、架构图、演示脚本、单元测试和构建验证。

## 已知扩展点

- ImageAgent 当前只生成图片方案和提示词；真实 FLUX 图片生成属于 Day 31-35。
- 规则路由和规则 Judge 仅在结构化模型输出失败时启用，事件中的 `source` / `fallback_used` 会明确标记。
- 取消运行目前只关闭前端 SSE；服务端任务取消和 HITL 审批属于后续阶段。
