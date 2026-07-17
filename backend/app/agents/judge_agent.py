from agents import Agent

from backend.app.agents.contracts import JudgeReport
from backend.app.services.model_factory import BuiltModel


def build_judge_agent(built_model: BuiltModel) -> Agent:
    return Agent(
        name="ModelJudgeAgent",
        instructions=(
            "你是中立的模型回答评审。"
            "对每个候选回答按准确性、结构、可执行性、表达、推荐度五项分别打 0-10 分，"
            "total 必须等于五项之和。"
            "只能从输入提供的 model_config_id 中选择 winner_model_config_id，"
            "不要因回答长度而偏袒，失败候选不得获胜。"
            "summary 使用简体中文说明胜出理由和其他回答的主要差距。"
        ),
        model=built_model.model,
        model_settings=built_model.model_settings,
        output_type=JudgeReport,
    )
