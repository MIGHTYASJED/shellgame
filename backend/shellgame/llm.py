"""LLM provider abstraction. The LLM only ever chooses among fixed tools with typed args — it never writes Cypher.

Env:
  LLM_PROVIDER = anthropic | openai | none   (default: anthropic if ANTHROPIC_API_KEY is set, else openai if
                                              OPENAI_API_KEY is set, else none)
  LLM_MODEL    = model name override (defaults below)
  ANTHROPIC_API_KEY / OPENAI_API_KEY

Neutral message format used by agents.py:
  {"role": "user", "content": str}
  {"role": "assistant", "text": str, "tool_calls": [{"id", "name", "args": dict}]}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}
Neutral tool spec: {"name", "description", "parameters": <JSON schema object>}
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("shellgame.llm")

DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4.1"}
MAX_TOKENS = 1500
TIMEOUT_S = 60.0


class LLMUnavailable(RuntimeError):
    """Raised when provider is 'none' -> callers use the scripted path."""


def provider() -> str:
    p = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if p in {"anthropic", "openai", "none"}:
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "none"


def model() -> str:
    return os.environ.get("LLM_MODEL") or DEFAULT_MODELS.get(provider(), "")


def enabled() -> bool:
    return provider() != "none"


def info() -> dict:
    return {"provider": provider(), "model": model() if enabled() else None, "scripted": not enabled()}


# ---------------------------------------------------------------- anthropic
def _anthropic_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks: list[dict] = []
            if m.get("text"):
                blocks.append({"type": "text", "text": m["text"]})
            for tc in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc.get("args") or {}})
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": "..."}]})
        elif m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)  # merge consecutive tool results into one user turn
            else:
                out.append({"role": "user", "content": [block]})
    return out


async def _anthropic_chat(system: str, messages: list[dict], tools: list[dict] | None) -> dict:
    import anthropic

    client = anthropic.AsyncAnthropic(timeout=TIMEOUT_S)
    kwargs: dict[str, Any] = {
        "model": model(),
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": _anthropic_messages(messages),
    }
    if tools:
        kwargs["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
    resp = await client.messages.create(**kwargs)
    text, calls = [], []
    for b in resp.content:
        if b.type == "text":
            text.append(b.text)
        elif b.type == "tool_use":
            calls.append({"id": b.id, "name": b.name, "args": dict(b.input or {})})
    return {"text": "\n".join(text).strip(), "tool_calls": calls, "stop_reason": resp.stop_reason}


# ---------------------------------------------------------------- openai
def _openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.get("text") or None}
            if m.get("tool_calls"):
                msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc.get("args") or {})}}
                    for tc in m["tool_calls"]
                ]
            out.append(msg)
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
    return out


async def _openai_chat(system: str, messages: list[dict], tools: list[dict] | None) -> dict:
    import openai

    client = openai.AsyncOpenAI(timeout=TIMEOUT_S)
    kwargs: dict[str, Any] = {
        "model": model(),
        "messages": _openai_messages(system, messages),
        "max_completion_tokens": MAX_TOKENS,
    }
    if tools:
        kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
    resp = await client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"__invalid_json__": tc.function.arguments}
        calls.append({"id": tc.id, "name": tc.function.name, "args": args if isinstance(args, dict) else {}})
    return {"text": (msg.content or "").strip(), "tool_calls": calls, "stop_reason": resp.choices[0].finish_reason}


# ---------------------------------------------------------------- public
async def chat_tools(system: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
    """One model turn. Returns {"text": str, "tool_calls": [{"id","name","args"}], "stop_reason"}."""
    p = provider()
    if p == "anthropic":
        return await _anthropic_chat(system, messages, tools)
    if p == "openai":
        return await _openai_chat(system, messages, tools)
    raise LLMUnavailable("LLM_PROVIDER=none (scripted mode)")


async def write(prompt: str, system: str = "You are a precise compliance analyst. Write in plain, neutral English.") -> str:
    """Free-text generation (memo prose, skeptic commentary)."""
    r = await chat_tools(system, [{"role": "user", "content": prompt}], None)
    return r["text"]
