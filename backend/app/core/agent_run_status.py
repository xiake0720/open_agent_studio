from enum import StrEnum


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        return self in TERMINAL_AGENT_RUN_STATUSES


TERMINAL_AGENT_RUN_STATUSES = frozenset(
    {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.TIMEOUT,
        AgentRunStatus.INTERRUPTED,
    }
)

CANCELLABLE_AGENT_RUN_STATUSES = frozenset(
    {AgentRunStatus.PENDING, AgentRunStatus.RUNNING}
)
