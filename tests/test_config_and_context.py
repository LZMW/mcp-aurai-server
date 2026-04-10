import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_env_variables_are_applied_to_config(monkeypatch):
    monkeypatch.setenv("AURAI_TEMPERATURE", "0.25")
    monkeypatch.setenv("AURAI_MAX_ITERATIONS", "7")
    monkeypatch.setenv("AURAI_LOG_LEVEL", "debug")
    monkeypatch.setenv("AURAI_HISTORY_LOCK_TIMEOUT", "3.5")
    monkeypatch.setenv("AURAI_ENABLE_HISTORY_SUMMARY", "false")
    monkeypatch.setenv("AURAI_HISTORY_SUMMARY_KEEP_RECENT", "4")
    monkeypatch.setenv("AURAI_HISTORY_SUMMARY_TRIGGER", "9")
    monkeypatch.setenv("AURAI_STDIO_IDLE_TIMEOUT_SECONDS", "321")
    monkeypatch.setenv("AURAI_STDIO_IDLE_CHECK_INTERVAL_SECONDS", "7")
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
    assert server_config.history_lock_timeout == 3.5
    assert server_config.enable_history_summary is False
    assert server_config.history_summary_keep_recent == 4
    assert server_config.history_summary_trigger_entries == 9
    assert server_config.stdio_idle_timeout_seconds == 321
    assert server_config.stdio_idle_check_interval_seconds == 7


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


def test_summary_history_messages_are_included():
    from mcp_aurai.llm import AuraiClient

    client = AuraiClient.__new__(AuraiClient)
    client.config = SimpleNamespace(max_message_tokens=5000)

    messages = client._build_messages_from_history([
        {
            "type": "summary",
            "summary_text": "这里是旧历史纪要",
        }
    ])

    assert len(messages) == 1
    assert "历史摘要" in messages[0]["content"]
    assert "旧历史纪要" in messages[0]["content"]


def test_context_window_prefers_latest_sync_context():
    from mcp_aurai.llm import AuraiClient

    client = AuraiClient.__new__(AuraiClient)
    client.config = SimpleNamespace(
        max_message_tokens=5000,
        max_tokens=40,
        context_window=80,
    )

    sync_message = {"role": "system", "content": "S" * 40}
    consult_messages = [
        {"role": "user", "content": "U" * 40},
        {"role": "assistant", "content": "A" * 40},
    ]

    budget = client._estimate_messages_tokens(sync_message if isinstance(sync_message, list) else [sync_message]) + 1
    selected, trimmed = client._select_history_messages_within_budget(
        [
            {"type": "sync_context", "messages": [sync_message]},
            {"type": "consult", "messages": consult_messages},
        ],
        budget=budget,
    )

    assert trimmed is True
    assert selected == [sync_message]


@pytest.mark.asyncio
async def test_chat_caps_output_tokens_by_context_window():
    from mcp_aurai.llm import AuraiClient

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"status":"ok"}')
                    )
                ]
            )

    client = AuraiClient.__new__(AuraiClient)
    client.config = SimpleNamespace(
        api_key="test-api-key-12345",
        base_url="https://example.com/v1",
        model="test-model",
        temperature=0.3,
        max_message_tokens=5000,
        max_tokens=40,
        context_window=60,
    )
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    response = await client.chat(
        user_message="U" * 80,
        system_prompt="S" * 80,
        conversation_history=None,
    )

    prompt_tokens = client._estimate_messages_tokens(captured["messages"])
    expected_max_tokens = min(
        client.config.max_tokens,
        max(client.config.context_window - prompt_tokens, 1),
    )

    assert response["status"] == "ok"
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == expected_max_tokens
