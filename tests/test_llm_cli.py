import json

import pytest

from aqi.ledger import Ledger
from aqi.llm import LLM, _extract_json, _reply_text


def test_extract_json_from_prose_and_fences():
    assert _extract_json('Sure!\n```json\n{"action": "STOP", "reason": "done"}\n```') == {"action": "STOP", "reason": "done"}
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_reply_text_reads_each_cli_envelope(tmp_path):
    assert _reply_text("claude", json.dumps({"type": "result", "result": "hi", "is_error": False}), tmp_path / "x") == "hi"
    assert _reply_text("gemini", json.dumps({"response": "hello"}), tmp_path / "x") == "hello"
    agy = "a warning line\n" + json.dumps({"status": "SUCCESS", "response": "", "structured_output": {"ok": True}})
    assert json.loads(_reply_text("agy", agy, tmp_path / "x")) == {"ok": True}
    (tmp_path / "out.txt").write_text('{"ok": 1}', encoding="utf-8")
    assert _reply_text("codex", "event log", tmp_path / "out.txt") == '{"ok": 1}'
    with pytest.raises(RuntimeError):
        _reply_text("claude", json.dumps({"is_error": True, "result": "Usage limit reached"}), tmp_path / "x")


def test_missing_cli_falls_back_cleanly(tmp_path):
    llm = LLM({"enabled": True, "backend": "cli", "cli": ["definitely-not-installed"]}, Ledger("t", runs_dir=tmp_path))
    assert llm.ask("system", "user") is None
    assert "not installed" in llm.disabled_reason


def test_cached_answer_is_reused_without_calling_a_cli(tmp_path):
    led = Ledger("t", runs_dir=tmp_path)
    first = LLM({"enabled": True, "backend": "cli", "cli": []}, led)
    key_args = ("sys", "user", None, False, None)  # system, user, schema, web, mcp
    import hashlib
    key = hashlib.sha256(json.dumps(["cli", *key_args]).encode()).hexdigest()
    (led.dir / "llm_cache.json").write_text(json.dumps({key: "cached words"}))
    again = LLM({"enabled": True, "backend": "cli", "cli": []}, led)
    assert again.ask("sys", "user") == "cached words" and again.answered_by == "cache"
    assert first.cache == {}
