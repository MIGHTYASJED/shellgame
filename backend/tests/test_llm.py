"""Offline checks of the provider adapters (no network)."""
import json

from shellgame import llm

MSGS = [
    {"role": "user", "content": "Investigate E1"},
    {"role": "assistant", "text": "tracing", "tool_calls": [
        {"id": "t1", "name": "sanction_paths", "args": {"node_id": "E1"}},
        {"id": "t2", "name": "shell_cluster", "args": {"node_id": "E1"}}]},
    {"role": "tool", "tool_call_id": "t1", "name": "sanction_paths", "content": "{}"},
    {"role": "tool", "tool_call_id": "t2", "name": "shell_cluster", "content": "{}"},
]


def test_provider_selection(monkeypatch):
    for k in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert llm.provider() == "none" and not llm.enabled()
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    assert llm.provider() == "openai" and llm.model() == llm.DEFAULT_MODELS["openai"]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.provider() == "anthropic" and llm.model() == "claude-sonnet-4-5"
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert llm.provider() == "none"
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "my-model")
    assert llm.model() == "my-model"


def test_anthropic_message_shape():
    out = llm._anthropic_messages(MSGS)
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert [b["type"] for b in out[1]["content"]] == ["text", "tool_use", "tool_use"]
    assert [b["tool_use_id"] for b in out[2]["content"]] == ["t1", "t2"]


def test_openai_message_shape():
    out = llm._openai_messages("sys", MSGS)
    assert out[0] == {"role": "system", "content": "sys"}
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"node_id": "E1"}
    assert [m["role"] for m in out[3:]] == ["tool", "tool"]
