import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_env_variables_are_applied_to_config(monkeypatch):
    monkeypatch.setenv("AURAI_TEMPERATURE", "0.25")
    monkeypatch.setenv("AURAI_MAX_ITERATIONS", "7")
    monkeypatch.setenv("AURAI_LOG_LEVEL", "debug")
    monkeypatch.setenv("AURAI_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("AURAI_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("AURAI_MODEL", "test-model")

    import mcp_aurai.config as config

    config = importlib.reload(config)
    config.reset_config()

    aurai_config = config.get_aurai_config()
    server_config = config.get_server_config()

    assert aurai_config.temperature == 0.25
    assert aurai_config.max_iterations == 7
    assert server_config.log_level == "DEBUG"


def test_build_consult_prompt_includes_answers_and_extra_context():
    from mcp_aurai.prompts import build_consult_prompt

    prompt = build_consult_prompt(
        problem_type="runtime_error",
        error_message="报错",
        code_snippet=None,
        context={
            "answers_to_questions": "这里是补充回答",
            "expected_behavior": "应该输出成功",
            "actual_behavior": "实际抛异常",
        },
        attempts_made="已经重试一次",
    )

    assert "这里是补充回答" in prompt
    assert "expected_behavior" in prompt
    assert "实际抛异常" in prompt


def test_sync_context_history_messages_include_project_info():
    from mcp_aurai.llm import AuraiClient

    client = AuraiClient.__new__(AuraiClient)
    client.config = SimpleNamespace(max_message_tokens=5000)

    messages = client._build_messages_from_history([
        {
            "type": "sync_context",
            "project_info": {
                "project_name": "示例项目",
                "tech_stack": "Python + FastMCP",
            },
            "file_contents": {},
        }
    ])

    assert len(messages) == 1
    assert "已同步项目背景" in messages[0]["content"]
    assert "示例项目" in messages[0]["content"]
