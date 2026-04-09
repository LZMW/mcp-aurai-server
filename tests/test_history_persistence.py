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
    server.server_config.history_lock_timeout = 10.0
    server.server_config.enable_history_summary = True
    server.server_config.history_summary_keep_recent = 3
    server.server_config.history_summary_trigger_entries = 8
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
async def test_sync_context_auto_converts_code_file_to_text(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)

    code_file = tmp_path / "main.py"
    code_file.write_text("print('hello')\n", encoding="utf-8")

    result = await server.sync_context(
        operation="incremental",
        files=[str(code_file)],
        project_info=None,
        session_id=None,
    )

    assert result["status"] == "success"
    assert len(result["auto_converted_files"]) == 1
    uploaded = result["uploaded_files"][0]
    assert uploaded["original_path"] == str(code_file)
    assert uploaded["sent_as_path"].endswith(".txt")
    assert uploaded["auto_converted"] is True

    latest_entry = server._get_session_history(None)[-1]
    sent_as_path = uploaded["sent_as_path"]
    assert sent_as_path in latest_entry["file_contents"]
    assert "[原始文件:" in latest_entry["file_contents"][sent_as_path]
    assert "print('hello')" in latest_entry["file_contents"][sent_as_path]


@pytest.mark.asyncio
async def test_sync_context_skips_binary_file_but_keeps_text_file(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)

    code_file = tmp_path / "worker.js"
    code_file.write_text("console.log('ok')\n", encoding="utf-8")
    binary_file = tmp_path / "image.png"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    result = await server.sync_context(
        operation="incremental",
        files=[str(code_file), str(binary_file)],
        project_info=None,
        session_id=None,
    )

    assert result["status"] == "success"
    assert len(result["uploaded_files"]) == 1
    assert len(result["skipped_files"]) == 1
    assert result["skipped_files"][0]["path"] == str(binary_file)
    assert "二进制" in result["skipped_files"][0]["reason"]


@pytest.mark.asyncio
async def test_sync_context_returns_error_when_all_files_are_binary(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)

    binary_file = tmp_path / "archive.zip"
    binary_file.write_bytes(b"PK\x03\x04\x00\x00\x00\x00")

    result = await server.sync_context(
        operation="incremental",
        files=[str(binary_file)],
        project_info=None,
        session_id=None,
    )

    assert result["status"] == "error"
    assert result["text_files_read"] == 0
    assert result["skipped_files"][0]["path"] == str(binary_file)


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


def test_history_file_lock_times_out_when_already_held(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)
    server.server_config.history_lock_timeout = 0.1

    with server._history_file_lock(None):
        with pytest.raises(TimeoutError):
            with server._history_file_lock(None):
                pass


def test_save_history_uses_atomic_replace_and_cleans_temp_files(server_module, tmp_path, monkeypatch):
    server = server_module
    history_path = configure_persistence(server, tmp_path)

    original_replace = server.os.replace
    replace_calls = []

    def tracking_replace(src, dst):
        replace_calls.append((Path(src), Path(dst)))
        return original_replace(src, dst)

    monkeypatch.setattr(server.os, "replace", tracking_replace)

    server._add_to_history({
        "type": "consult",
        "problem_type": "other",
        "error_message": "原子写入测试",
        "response": {"resolved": False},
    })

    assert replace_calls
    temp_path, target_path = replace_calls[-1]
    assert target_path == history_path
    assert temp_path.suffix == ".tmp"
    assert not temp_path.exists()


def test_history_summary_compacts_older_entries(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)
    server.server_config.history_summary_keep_recent = 2
    server.server_config.history_summary_trigger_entries = 5

    for index in range(6):
        server._add_to_history({
            "type": "consult",
            "problem_type": "runtime_error",
            "error_message": f"问题{index}",
            "response": {
                "resolved": False,
                "analysis": f"分析{index}",
            },
        })

    history = server._get_session_history(None)

    assert history[0]["type"] == server.SUMMARY_ENTRY_TYPE
    assert "问题0" in history[0]["summary_text"]
    assert "问题3" in history[0]["summary_text"]
    assert [entry["error_message"] for entry in history[1:]] == ["问题4", "问题5"]


def test_history_summary_keeps_latest_sync_context(server_module, tmp_path):
    server = server_module
    configure_persistence(server, tmp_path)
    server.server_config.history_summary_keep_recent = 2
    server.server_config.history_summary_trigger_entries = 4

    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "旧问题",
        "response": {"resolved": False},
    })
    server._add_to_history({
        "type": "sync_context",
        "operation": "incremental",
        "files": ["docs/old.md"],
        "temp_files": [],
        "file_contents": {"docs/old.md": "重要上下文"},
        "project_info": {},
    })
    server._add_to_history({
        "type": "progress",
        "actions_taken": "尝试一",
        "result": "partial",
        "response": {"resolved": False},
    })
    server._add_to_history({
        "type": "consult",
        "problem_type": "runtime_error",
        "error_message": "较新问题",
        "response": {"resolved": False},
    })
    server._add_to_history({
        "type": "progress",
        "actions_taken": "尝试二",
        "result": "failed",
        "response": {"resolved": False},
    })

    history = server._get_session_history(None)
    assert history[0]["type"] == server.SUMMARY_ENTRY_TYPE
    assert any(entry.get("type") == "sync_context" for entry in history[1:])
