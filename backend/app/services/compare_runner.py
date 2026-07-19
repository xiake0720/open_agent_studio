import json
import time
from dataclasses import asdict, dataclass

from agents import Agent, Runner
from agents.items import TResponseInputItem

from backend.app.agents.context import AppRunContext
from backend.app.agents.contracts import JudgeReport, JudgeScore
from backend.app.agents.judge_agent import build_judge_agent
from backend.app.models.model_config import ModelConfig
from backend.app.services.model_factory import build_chat_model
from backend.app.services.token_usage_service import extract_token_usage


@dataclass(slots=True)
class CandidateOutput:
    model_config_id: str
    display_name: str
    model_id: str
    status: str
    output_text: str | None
    error_message: str | None
    duration_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def to_event_data(self) -> dict:
        return asdict(self)


async def run_compare_candidate(
    model_config: ModelConfig,
    user_input: str | list[TResponseInputItem],
    context: AppRunContext,
) -> CandidateOutput:
    started = time.perf_counter()
    try:
        built_model = build_chat_model(model_config)
        candidate_agent = Agent(
            name=f"CompareCandidate-{model_config.display_name}",
            instructions=(
                "你正在参加同题多模型对比。直接完成用户任务，保持事实准确、结构清晰、"
                "建议可执行；不要讨论评分流程，也不要调用与任务无关的工具。使用简体中文。"
            ),
            model=built_model.model,
            model_settings=built_model.model_settings,
        )
        result = await Runner.run(
            candidate_agent,
            user_input,
            context=context,
        )
        input_tokens, output_tokens, total_tokens = extract_token_usage(result)
        return CandidateOutput(
            model_config_id=model_config.id,
            display_name=model_config.display_name,
            model_id=model_config.model_id,
            status="completed",
            output_text=str(result.final_output or ""),
            error_message=None,
            duration_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except Exception as exc:
        return CandidateOutput(
            model_config_id=model_config.id,
            display_name=model_config.display_name,
            model_id=model_config.model_id,
            status="failed",
            output_text=None,
            error_message=str(exc),
            duration_ms=round((time.perf_counter() - started) * 1000),
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )


def fallback_judge_report(candidates: list[CandidateOutput]) -> JudgeReport:
    successful = [item for item in candidates if item.status == "completed" and item.output_text]
    if not successful:
        raise ValueError("没有可供评审的成功模型回答")

    fastest = min(successful, key=lambda item: item.duration_ms).model_config_id
    scores: list[JudgeScore] = []

    for item in successful:
        text = item.output_text or ""
        structure_bonus = 1.0 if any(mark in text for mark in ("\n- ", "\n1.", "##", "###")) else 0.0
        action_bonus = 1.0 if any(word in text for word in ("步骤", "建议", "可以", "首先")) else 0.0
        speed_bonus = 1.0 if item.model_config_id == fastest else 0.0
        values = {
            "accuracy": 7.0,
            "structure": 6.5 + structure_bonus,
            "actionability": 6.5 + action_bonus,
            "expression": 7.0,
            "recommendation": 6.5 + speed_bonus,
        }
        scores.append(JudgeScore(
            model_config_id=item.model_config_id,
            display_name=item.display_name,
            total=round(sum(values.values()), 2),
            strengths=["成功返回完整回答", "规则降级评审中表现稳定"],
            weaknesses=["JudgeAgent 未返回结构化评分，本分数仅用于降级展示"],
            **values,
        ))

    winner = max(scores, key=lambda item: item.total)
    return JudgeReport(
        winner_model_config_id=winner.model_config_id,
        winner_display_name=winner.display_name,
        scores=scores,
        summary=(
            "ModelJudgeAgent 未能返回合法结构化结果，系统已按回答完整度、结构、"
            "可执行性和耗时进行规则降级评审。"
        ),
        fallback_used=True,
    )


async def judge_compare_candidates(
    judge_model_config: ModelConfig,
    user_input: str,
    candidates: list[CandidateOutput],
    context: AppRunContext,
) -> tuple[JudgeReport, tuple[int, int, int]]:
    successful = [item for item in candidates if item.status == "completed" and item.output_text]
    if not successful:
        raise ValueError("没有可供评审的成功模型回答")

    payload = {
        "user_question": user_input,
        "candidates": [
            {
                "model_config_id": item.model_config_id,
                "display_name": item.display_name,
                "answer": item.output_text,
                "latency_ms": item.duration_ms,
            }
            for item in successful
        ],
    }

    usage = (0, 0, 0)
    try:
        built_model = build_chat_model(judge_model_config)
        result = await Runner.run(
            build_judge_agent(built_model),
            json.dumps(payload, ensure_ascii=False),
            context=context,
            max_turns=2,
        )
        usage = extract_token_usage(result)
        report = result.final_output
        if isinstance(report, JudgeReport):
            allowed_ids = {item.model_config_id for item in successful}
            if report.winner_model_config_id in allowed_ids:
                return report, usage
    except Exception:
        pass

    return fallback_judge_report(candidates), usage


def format_judge_markdown(report: JudgeReport) -> str:
    lines = [
        "## 多模型对比结论",
        "",
        f"推荐模型：**{report.winner_display_name}**",
        "",
        report.summary,
        "",
        "| 模型 | 准确性 | 结构 | 可执行性 | 表达 | 推荐度 | 总分 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for score in report.scores:
        lines.append(
            f"| {score.display_name} | {score.accuracy:g} | {score.structure:g} | "
            f"{score.actionability:g} | {score.expression:g} | "
            f"{score.recommendation:g} | {score.total:g} |"
        )
    if report.fallback_used:
        lines.extend(["", "> 本次 Judge 使用了规则降级结果。"])
    return "\n".join(lines)
