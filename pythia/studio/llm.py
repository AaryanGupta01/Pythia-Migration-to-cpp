"""LLM clients for the fixer: Anthropic API, offline cache, scripted fake (for checks).

All clients share one call: `complete(system, messages, function_source=..., attempt=n) -> str`.
The offline cache key is sha256(f"{sha256(function_source)}|{attempt}") (CONTRACTS section 7), so the
cache is independent of prompt wording and of earlier turns.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_MODEL = "claude-sonnet-5-5"
NO_KEY_HINT = "Set ANTHROPIC_API_KEY to enable the LLM fixer"
MAX_TOKENS = 8000


class LLMError(Exception):
    """The LLM could not answer (network/API error, cache miss, refusal)."""


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def cache_key(function_source: str, attempt: int) -> str:
    return _sha(f"{_sha(function_source)}|{attempt}")


def write_cache_entry(cache_dir, function_source: str, attempt: int, response: str,
                      model: str = DEFAULT_MODEL, provenance: str = "authored") -> Path:
    """Author/record one offline-cache entry (`provenance`: "recorded" | "authored")."""
    d = Path(cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{cache_key(function_source, attempt)}.json"
    p.write_text(json.dumps({"model": model, "attempt": attempt, "function_sha": _sha(function_source),
                             "response": response, "provenance": provenance}, indent=1), encoding="utf-8")
    return p


class AnthropicClient:
    source = "api"

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None, record_dir=None):
        import anthropic                                  # lazy: the studio runs without it when offline
        self.model = model
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.record_dir = record_dir or os.environ.get("PYTHIA_RECORD_LLM_DIR")

    def complete(self, system: str, messages: List[Dict[str, str]], *, function_source: Optional[str] = None,
                 attempt: int = 1) -> str:
        a = self._anthropic
        try:
            # no temperature/top_p: newer models reject non-default sampling parameters
            resp = self.client.messages.create(model=self.model, max_tokens=MAX_TOKENS,
                                               system=system, messages=messages)
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}: {getattr(e, 'message', e)}")
        except a.APIConnectionError as e:
            raise LLMError(f"cannot reach the Anthropic API: {e}")
        except a.APIError as e:
            raise LLMError(f"Anthropic API error: {e}")
        if getattr(resp, "stop_reason", None) == "refusal":
            raise LLMError("the model declined this request (safety refusal)")
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if not text.strip():
            raise LLMError("the model returned no text")
        if self.record_dir and function_source is not None:
            write_cache_entry(self.record_dir, function_source, attempt, text, self.model, "recorded")
        return text


class OfflineCache:
    source = "cache"

    def __init__(self, cache_dir, model: str = DEFAULT_MODEL):
        self.dir, self.model = Path(cache_dir), model

    def complete(self, system: str, messages: List[Dict[str, str]], *, function_source: Optional[str] = None,
                 attempt: int = 1) -> str:
        if function_source is None:
            raise LLMError("offline cache needs the function source to look up a response")
        p = self.dir / f"{cache_key(function_source, attempt)}.json"
        if not p.is_file():
            raise LLMError(f"no cached LLM response for this function (attempt {attempt}); offline mode cannot call the API")
        return json.loads(p.read_text(encoding="utf-8"))["response"]


class ScriptedClient:
    """Deterministic fake: returns the given replies in order (for checks, never for production)."""
    source = "api"
    model = "scripted"

    def __init__(self, replies: List[str], source: str = "api"):
        self.replies, self.calls, self.source = list(replies), [], source

    def complete(self, system: str, messages: List[Dict[str, str]], *, function_source: Optional[str] = None,
                 attempt: int = 1) -> str:
        self.calls.append({"system": system, "messages": [dict(m) for m in messages], "attempt": attempt})
        if not self.replies:
            raise LLMError("scripted client has no more replies")
        return self.replies.pop(0)


def make_client(model: str = DEFAULT_MODEL, offline_cache_dir=None, *, offline: Optional[bool] = None,
                record_dir=None):
    """OfflineCache when offline (default: whenever `offline_cache_dir` is given), else Anthropic when
    ANTHROPIC_API_KEY is set, else None (fixer disabled)."""
    if offline is None:
        offline = offline_cache_dir is not None
    if offline:
        return OfflineCache(offline_cache_dir, model) if offline_cache_dir else None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicClient(model, record_dir=record_dir)
        except Exception:
            return None
    return None


def llm_status(model: str = DEFAULT_MODEL, offline: bool = False, offline_cache_dir=None) -> dict:
    """The `env().llm` payload."""
    if offline:
        ok = bool(offline_cache_dir) and Path(offline_cache_dir).is_dir()
        return {"enabled": ok, "model": model,
                "hint": "Offline: replaying cached LLM responses" if ok else "Offline cache not found"}
    if os.environ.get("ANTHROPIC_API_KEY"):
        return {"enabled": True, "model": model, "hint": ""}
    return {"enabled": False, "model": model, "hint": NO_KEY_HINT}
