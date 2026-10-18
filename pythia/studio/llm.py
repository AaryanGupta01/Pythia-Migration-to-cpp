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
GROQ_MODEL = "openai/gpt-oss-120b"                # free tier on Groq; strongest open model available there
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
NO_KEY_HINT = "Set GROQ_API_KEY (free) or ANTHROPIC_API_KEY to enable the LLM fixer"
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


def detect_provider(settings: Optional[dict] = None):
    """(provider, api_key) from settings/env: explicit `provider`, else Anthropic if its key exists, else Groq."""
    st = settings or {}
    want = (st.get("provider") or os.environ.get("PYTHIA_LLM_PROVIDER") or "auto").lower()
    key = st.get("api_key")
    a = os.environ.get("ANTHROPIC_API_KEY")
    g = os.environ.get("GROQ_API_KEY")
    if key:                                           # a key typed into Settings: infer its provider
        if want == "auto":
            want = "groq" if str(key).startswith("gsk_") else "anthropic"
        return want, key
    if want in ("anthropic", "auto") and a:
        return "anthropic", a
    if want in ("groq", "auto") and g:
        return "groq", g
    return None, None


def pick_model(provider: Optional[str], requested: Optional[str]) -> str:
    if provider == "groq":
        return GROQ_MODEL if not requested or requested.startswith("claude") else requested
    return requested if requested and requested.startswith("claude") else DEFAULT_MODEL


class GroqClient:
    """OpenAI-compatible chat completions on Groq (stdlib only; free tier => retry politely on 429)."""
    source = "api"

    def __init__(self, model: str = GROQ_MODEL, api_key: Optional[str] = None, record_dir=None):
        self.model = model
        self.key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.key:
            raise LLMError("GROQ_API_KEY is not set")
        self.record_dir = record_dir or os.environ.get("PYTHIA_RECORD_LLM_DIR")

    def complete(self, system: str, messages: List[Dict[str, str]], *, function_source: Optional[str] = None,
                 attempt: int = 1) -> str:
        import time
        import urllib.error
        import urllib.request
        body = {"model": self.model, "messages": [{"role": "system", "content": system}] + list(messages),
                "max_completion_tokens": MAX_TOKENS, "temperature": 0.2}
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = "low"
        data = json.dumps(body).encode()
        last = "unknown error"
        for n in range(5):
            req = urllib.request.Request(GROQ_URL, data=data, headers={
                "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                "User-Agent": "pythia-studio/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    out = json.loads(r.read())
                text = (out["choices"][0]["message"].get("content") or "")
                if not text.strip():
                    raise LLMError("the model returned no text")
                if self.record_dir and function_source is not None:
                    write_cache_entry(self.record_dir, function_source, attempt, text, self.model, "recorded")
                return text
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                last = f"Groq API error {e.code}: {detail}"
                if e.code in (429, 500, 502, 503):
                    wait = float(e.headers.get("retry-after") or 2 * (n + 1))
                    time.sleep(min(wait, 20))
                    continue
                raise LLMError(last)
            except (urllib.error.URLError, TimeoutError) as e:
                last = f"cannot reach the Groq API: {e}"
                time.sleep(2 * (n + 1))
        raise LLMError(last)


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


def make_client(model: Optional[str] = None, offline_cache_dir=None, *, offline: Optional[bool] = None,
                record_dir=None, settings: Optional[dict] = None):
    """OfflineCache when offline (default: whenever `offline_cache_dir` is given), else the provider whose key
    is available (Anthropic, then Groq), else None (fixer disabled)."""
    if offline is None:
        offline = offline_cache_dir is not None
    if offline:
        return OfflineCache(offline_cache_dir, model or DEFAULT_MODEL) if offline_cache_dir else None
    provider, key = detect_provider(settings)
    try:
        if provider == "anthropic":
            return AnthropicClient(pick_model(provider, model), api_key=key, record_dir=record_dir)
        if provider == "groq":
            return GroqClient(pick_model(provider, model), api_key=key, record_dir=record_dir)
    except Exception:
        return None
    return None


def llm_status(model: Optional[str] = None, offline: bool = False, offline_cache_dir=None,
               settings: Optional[dict] = None) -> dict:
    """The `env().llm` payload."""
    if offline:
        ok = bool(offline_cache_dir) and Path(offline_cache_dir).is_dir()
        return {"enabled": ok, "model": model or DEFAULT_MODEL, "provider": "offline-cache",
                "hint": "Offline: replaying cached LLM responses" if ok else "Offline cache not found"}
    provider, _ = detect_provider(settings)
    if provider:
        return {"enabled": True, "model": pick_model(provider, model), "provider": provider, "hint": ""}
    return {"enabled": False, "model": model or GROQ_MODEL, "provider": None, "hint": NO_KEY_HINT}


def test_key(provider: Optional[str], api_key: Optional[str]) -> dict:
    """Check a key with a free, read-only call (list models). Never logs or returns the key."""
    import urllib.error
    import urllib.request
    key = (api_key or "").strip()
    prov = (provider or "auto").lower()
    if prov == "auto":
        prov = "groq" if key.startswith("gsk_") else "anthropic" if key.startswith("sk-ant-") else "groq"
    if not key:
        return {"ok": False, "provider": prov, "error": "paste a key first"}
    if prov == "groq":
        req = urllib.request.Request("https://api.groq.com/openai/v1/models",
                                     headers={"Authorization": f"Bearer {key}", "User-Agent": "pythia-studio/1.0"})
    elif prov == "anthropic":
        req = urllib.request.Request("https://api.anthropic.com/v1/models",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                              "User-Agent": "pythia-studio/1.0"})
    else:
        return {"ok": False, "provider": prov, "error": f"unknown provider {prov!r}"}
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read() or b"{}")
        ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
        model = pick_model(prov, None)
        return {"ok": True, "provider": prov, "model": model, "model_available": (model in ids) if ids else None}
    except urllib.error.HTTPError as e:
        why = {401: "the key was rejected (401): check you copied all of it",
               403: "the key is not allowed to use this API (403)"}.get(e.code, f"the provider answered HTTP {e.code}")
        return {"ok": False, "provider": prov, "error": why}
    except Exception as e:
        return {"ok": False, "provider": prov, "error": f"could not reach {prov}: {e.__class__.__name__}. Check the internet connection."}
