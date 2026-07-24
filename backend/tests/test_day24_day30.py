import os
import unittest

from backend.app.agents.contracts import JudgeScore
from backend.app.agents.ecommerce_agent import build_ecommerce_agent
from backend.app.agents.image_agent import build_image_agent
from backend.app.agents.routing import fallback_route_decision
from backend.app.agents.triage_agent import build_triage_agent
from backend.app.models.model_config import ModelConfig
from backend.app.schemas.agent_run import AgentRunCreateRequest
from backend.app.services.compare_runner import CandidateOutput, fallback_judge_report, format_judge_markdown
from backend.app.services.model_factory import build_chat_model


def fake_model_config() -> ModelConfig:
    return ModelConfig(
        id="model-test",
        provider="test",
        display_name="Test Model",
        model_id="test-model",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_MODEL_KEY",
        api_shape="chat_completions",
        support_streaming=True,
        support_tools=True,
        support_image=False,
        enabled=True,
        extra_body_json=None,
    )


class RoutingTests(unittest.TestCase):
    def test_route_examples(self) -> None:
        cases = {
            "TypeError: object NoneType can't be used in await": "tech",
            "检查商品标题：全网第一，100%有效": "ecommerce",
            "生成一张极简科技风海报": "image",
            "比较 GLM 和 Qwen 的回答": "compare",
            "介绍一下杭州": "general",
        }
        for user_input, expected in cases.items():
            with self.subTest(user_input=user_input):
                self.assertEqual(fallback_route_decision(user_input).specialist, expected)

    def test_agent_run_schema_accepts_new_and_legacy_model_field(self) -> None:
        modern = AgentRunCreateRequest(
            conversation_id="conv",
            content="hello",
            primary_model_id="model-a",
            agent_mode="compare",
            compare_model_ids=["model-a", "model-b"],
        )
        legacy = AgentRunCreateRequest(
            conversation_id="conv",
            content="hello",
            model_config_id="model-a",
            agent_mode="tech",
        )
        self.assertEqual(modern.primary_model_id, "model-a")
        self.assertEqual(legacy.primary_model_id, "model-a")


class AgentConstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["TEST_MODEL_KEY"] = "test-key"
        cls.built_model = build_chat_model(fake_model_config())

    @classmethod
    def tearDownClass(cls) -> None:
        os.environ.pop("TEST_MODEL_KEY", None)

    def test_ecommerce_agent_has_sensitive_word_tool(self) -> None:
        agent = build_ecommerce_agent(self.built_model)
        self.assertEqual(agent.name, "EcommerceAgent")
        self.assertIn("check_sensitive_words", [tool.name for tool in agent.tools])

    def test_triage_does_not_embed_specialists_as_tools(self) -> None:
        decision = fallback_route_decision("Python TypeError 报错")
        agent = build_triage_agent(self.built_model, decision)
        names = {tool.name for tool in agent.tools}
        self.assertFalse({"ask_tech_expert", "ask_ecommerce_expert", "ask_image_expert"} & names)

    def test_image_agent_has_nvidia_flux_tool(self) -> None:
        agent = build_image_agent(self.built_model)
        self.assertIn("generate_flux_image", [tool.name for tool in agent.tools])


class JudgeFallbackTests(unittest.TestCase):
    def test_fallback_judge_returns_winner_and_markdown(self) -> None:
        candidates = [
            CandidateOutput("a", "Model A", "a", "completed", "## 建议\n1. 先检查配置", None, 800),
            CandidateOutput("b", "Model B", "b", "completed", "可以这样处理。", None, 1200),
            CandidateOutput("c", "Model C", "c", "failed", None, "timeout", 2000),
        ]
        report = fallback_judge_report(candidates)
        self.assertTrue(report.fallback_used)
        self.assertIn(report.winner_model_config_id, {"a", "b"})
        self.assertEqual(len(report.scores), 2)
        self.assertIn("多模型对比结论", format_judge_markdown(report))
        self.assertTrue(all(isinstance(item, JudgeScore) for item in report.scores))


if __name__ == "__main__":
    unittest.main()
