import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class FakeClient:
    def __init__(self, response: dict, recorder: dict | None = None):
        self.response = response
        self.recorder = recorder

    async def chat(self, **kwargs):
        if self.recorder is not None:
            self.recorder["kwargs"] = kwargs
        return self.response


def reset_server_state(server):
    server._conversation_history.clear()
    server._loaded_sessions.clear()


@pytest.fixture
def server_module():
    import mcp_aurai.server as server

    server = importlib.reload(server)
    reset_server_state(server)
    yield server
    reset_server_state(server)


def configure_persistence(server, tmp_path: Path) -> Path:
    history_path = tmp_path / "history.json"
    server.server_config.enable_persistence = True
    server.server_config.history_path = str(history_path)
    reset_server_state(server)
    server._ensure_session_loaded(server.DEFAULT_SESSION_ID)
    server._save_history_to_file()
    return history_path


def read_history(history_path: Path) -> list[dict]:
    return json.loads(history_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_sync_context_clear_persists_empty_history(server_module, tmp_path):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._add_to_history({
        "type": "consult",
        "problem_type": "other",
        "error_message": "旧问题",
        "response": {"resolved": False},
    })

    result = await server.sync_context(
        operation="clear",
        files=None,
        project_info=None,
        session_id=None,
    )

    assert result["status"] == "success"
    assert server._get_session_history(None) == []
    assert read_history(history_path) == []


@pytest.mark.asyncio
async def test_consult_resolved_clears_persisted_history(server_module, tmp_path, monkeypatch):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "旧错误",
        "response": {"resolved": False},
    })

    monkeypatch.setattr(
        server,
        "get_aurai_config",
        lambda: SimpleNamespace(max_iterations=10, provider="custom", model="test-model"),
    )
    monkeypatch.setattr(server, "build_consult_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(
        server,
        "get_aurai_client",
        lambda: FakeClient({
            "status": "success",
            "analysis": "已解决",
            "guidance": "无需继续处理",
            "action_items": [],
            "resolved": True,
        }),
    )

    result = await server.consult_aurai(
        problem_type="other",
        error_message="新问题",
        code_snippet=None,
        context=None,
        attempts_made=None,
        answers_to_questions=None,
        is_new_question=False,
        session_id=None,
    )

    assert result["status"] == "success"
    assert result["resolved"] is True
    assert server._get_session_history(None) == []
    assert read_history(history_path) == []


@pytest.mark.asyncio
async def test_report_progress_resolved_clears_persisted_history(server_module, tmp_path, monkeypatch):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "旧错误",
        "response": {"resolved": False},
    })

    monkeypatch.setattr(
        server,
        "get_aurai_config",
        lambda: SimpleNamespace(max_iterations=10, provider="custom", model="test-model"),
    )
    monkeypatch.setattr(server, "build_progress_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(
        server,
        "get_aurai_client",
        lambda: FakeClient({
            "analysis": "已完成",
            "guidance": "结束",
            "action_items": [],
            "resolved": True,
        }),
    )

    result = await server.report_progress(
        actions_taken="执行修复",
        result="success",
        new_error=None,
        feedback=None,
        session_id=None,
    )

    assert result["resolved"] is True
    assert server._get_session_history(None) == []
    assert read_history(history_path) == []


@pytest.mark.asyncio
async def test_sync_context_clear_only_affects_target_session(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)

    alpha_entry = {
        "type": "consult",
        "problem_type": "other",
        "error_message": "alpha",
        "response": {"resolved": False},
    }
    beta_entry = {
        "type": "consult",
        "problem_type": "other",
        "error_message": "beta",
        "response": {"resolved": False},
    }
    server._add_to_history(alpha_entry, "alpha")
    server._add_to_history(beta_entry, "beta")

    alpha_history_path = server._get_history_file_for_session("alpha")
    beta_history_path = server._get_history_file_for_session("beta")

    result = await server.sync_context(
        operation="clear",
        files=None,
        project_info=None,
        session_id="alpha",
    )

    assert result["status"] == "success"
    assert server._get_session_history("alpha") == []
    assert server._get_session_history("beta") == [beta_entry]
    assert read_history(alpha_history_path) == []
    assert read_history(beta_history_path) == [beta_entry]


@pytest.mark.asyncio
async def test_consult_uses_only_target_session_history(server_module, tmp_path, monkeypatch):
    server = server_module
    configure_persistence(server, tmp_path)

    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "alpha-history",
        "response": {"resolved": False},
    }, "alpha")
    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "beta-history",
        "response": {"resolved": False},
    }, "beta")

    recorder = {}
    monkeypatch.setattr(
        server,
        "get_aurai_config",
        lambda: SimpleNamespace(max_iterations=10, provider="custom", model="test-model"),
    )
    monkeypatch.setattr(server, "build_consult_prompt", lambda **kwargs: "prompt")
    monkeypatch.setattr(
        server,
        "get_aurai_client",
        lambda: FakeClient({
            "status": "success",
            "analysis": "继续",
            "guidance": "继续",
            "action_items": [],
            "resolved": False,
        }, recorder=recorder),
    )

    await server.consult_aurai(
        problem_type="other",
        error_message="新问题",
        code_snippet=None,
        context=None,
        attempts_made=None,
        answers_to_questions=None,
        is_new_question=False,
        session_id="alpha",
    )

    sent_history = recorder["kwargs"]["conversation_history"]
    assert len(sent_history) == 1
    assert sent_history[0]["error_message"] == "alpha-history"
