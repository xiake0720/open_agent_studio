from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppRunContext:
    """Serializable, non-secret application context shared by an Agents SDK run."""

    user_id: str
    conversation_id: str
    run_id: str
    selected_model_id: str
    agent_mode: str
    permissions: frozenset[str]
    locale: str = "zh-CN"

    def require_identity(self) -> None:
        if not self.user_id or not self.run_id:
            raise ValueError("工具运行上下文缺少 user_id 或 run_id")

    def require_permission(self, permission: str) -> None:
        self.require_identity()
        if permission not in self.permissions:
            raise PermissionError(f"当前运行缺少工具权限：{permission}")
