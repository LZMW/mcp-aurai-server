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
    def __init__(self, response: dict):
        self.response = response

    async def chat(self, **kwargs):
        return self.response


@pytest.fixture
def server_module():
    import mcp_aurai.server as server

    server = importlib.reload(server)
    server._conversation_history.clear()
    yield server
    server._conversation_history.clear()


def configure_persistence(server, tmp_path: Path) -> Path:
    history_path = tmp_path / "history.json"
    server.server_config.enable_persistence = True
    server.server_config.history_path = str(history_path)
    server._conversation_history.clear()
    server._save_history_to_file()
    return history_path


def read_history(history_path: Path) -> list[dict]:
    return json.loads(history_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_sync_context_clear_persists_empty_history(server_module, tmp_path):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._conversation_history.append({
        "type": "consult",
        "problem_type": "other",
        "error_message": "旧问题",
        "response": {"resolved": False},
    })
    server._save_history_to_file()

    result = await server.sync_context(
        operation="clear",
        files=None,
        project_info=None,
    )

    assert result["status"] == "success"
    assert server._conversation_history == []
    assert read_history(history_path) == []


@pytest.mark.asyncio
async def test_consult_resolved_clears_persisted_history(server_module, tmp_path, monkeypatch):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._conversation_history.append({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "旧错误",
        "response": {"resolved": False},
    })
    server._save_history_to_file()

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
    )

    assert result["status"] == "success"
    assert result["resolved"] is True
    assert server._conversation_history == []
    assert read_history(history_path) == []


@pytest.mark.asyncio
async def test_report_progress_resolved_clears_persisted_history(server_module, tmp_path, monkeypatch):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    server._conversation_history.append({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "旧错误",
        "response": {"resolved": False},
    })
    server._save_history_to_file()

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
    )

    assert result["resolved"] is True
    assert server._conversation_history == []
    assert read_history(history_path) == []
