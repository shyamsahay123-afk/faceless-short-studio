"""
ANTAR - providers.

Groq and Gemini, with the key rules the old engine paid for:

  * a 401 marks a key dead. It is never tried again.
  * a 429 exhausts a key for this run. The engine advances the key, and when
    every key for that service is exhausted it advances the MODEL. A rate
    limit is never grounds for a second attempt on the same key.
  * JSON mode is never requested. Groq validates the raw generation, and a
    reasoning model's raw output carries a trace, so a perfectly good answer
    still fails validation. We ask for plain text and parse it ourselves.
  * if content comes back empty, the answer may be in the reasoning field.
  * if the request 400s, the model may have put the answer in
    error.failed_generation. We recover it rather than losing the call.

Every model used is reported. Nothing is chosen silently.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .. import log
from ..keys import ALIVE, DEAD, EXHAUSTED, AllKeysDown, KeyRing

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = "https://api.groq.com/openai/v1/models"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
GEMINI_MODELS = "https://generativelanguage.googleapis.com/v1beta/models?key={key}"
# OpenRouter uses the same shape as Groq (OpenAI-compatible)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
# Huggingface's free router (router.huggingface.co) is OpenAI-compatible
# and accepts Bearer tokens (HF tokens start with hf_). Real endpoint,
# not a mock - confirmed from HF's own docs (huggingface.co/blog/inference-providers).
HUGGINGFACE_URL = "https://router.huggingface.co/v1/chat/completions"
HUGGINGFACE_MODELS = "https://router.huggingface.co/v1/models"
# The HF router aggregates many model providers (Together, Sambanova, Groq,
# HF Inference, etc) under one endpoint. We pin a short list of free-tier
# models that survive cold-starts reliably for Hindi text generation.
HUGGINGFACE_MODELS_DEFAULT = [
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "google/gemma-2-9b-it",
]
# Together AI: real OpenAI-compatible endpoint (api.together.xyz).
# Free tier (with $5 deposit) covers small Hindi topic generation.
TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
TOGETHER_MODELS = "https://api.together.xyz/v1/models"
TOGETHER_MODELS_DEFAULT = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "Qwen/Qwen2.5-7B-Instruct-Turbo",
    "google/gemma-2-9b-it",
]
# OpenAI: real endpoint at api.openai.com. Paid service but small free
# credit applies to new accounts. The key prefix is sk-.
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS = "https://api.openai.com/v1/models"
OPENAI_MODELS_DEFAULT = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo",
]
# Anthropic: real endpoint at api.anthropic.com. Different shape (their
# own /v1/messages endpoint, not OpenAI-compatible). The key prefix is
# sk-ant-. Headers: x-api-key, anthropic-version.
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MODELS_DEFAULT = [
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-haiku-20240307",
]

TIMEOUT = 120


class ProviderError(RuntimeError):
    """A call failed for a reason the caller may want to see."""


@dataclass
class Call:
    """One attempt, kept so the run can report exactly what happened."""
    service: str
    model: str
    key: str
    attempt: int
    ok: bool
    seconds: float
    note: str = ""
    text: str = ""

    @property
    def masked_key(self) -> str:
        return f"{self.key[:6]}...{self.key[-4:]}" if len(self.key) > 10 else "***"


@dataclass
class Ledger:
    """The record of every model and key tried during a run."""
    calls: list[Call] = field(default_factory=list)

    def add(self, call: Call) -> None:
        self.calls.append(call)

    @property
    def models_tried(self) -> list[str]:
        seen: list[str] = []
        for call in self.calls:
            if call.model not in seen:
                seen.append(call.model)
        return seen

    def summary(self) -> str:
        ok = [c for c in self.calls if c.ok]
        if not ok:
            return f"{len(self.calls)} calls, none succeeded"
        best = ok[-1]
        return (f"{len(self.calls)} calls, {len(ok)} ok, answer from "
                f"{best.service}/{best.model}")


# ---------------------------------------------------------------- transport

def _http(url: str, headers: dict, payload: dict | None = None,
          timeout: int = TIMEOUT) -> tuple[int, dict | str]:
    """
    One HTTP call. Returns (status, parsed body or raw text).

    The caller's headers are merged OVER the common browser headers, so every
    request ANTAR makes carries a real user agent. Groq sits behind Cloudflare
    and answers 403 'error code: 1010' to Python's default urllib agent - which
    looks exactly like a dead key and is not one.
    """
    from ..probe import COMMON_HEADERS

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data,
                                     headers={**COMMON_HEADERS, **headers},
                                     method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- the caller

class Brain:
    """
    Holds the key ring and makes model calls.

    transport is injectable so tests can run the whole brain with no network.
    """

    def _next_key_with_fallback(self, service: str):
        """
        Like ring.next_key(service), but if AllKeysDown is raised AND the
        ladder has flagged _force_resurrect_on, retry with force_resurrect
        so an EXHAUSTED (not DEAD) key can come back for a paid fallback.
        """
        try:
            return self.ring.next_key(service)
        except AllKeysDown as exc:
            if getattr(self, "_force_resurrect_on", False):
                try:
                    return self.ring.next_key(service, force_resurrect=True)
                except AllKeysDown:
                    pass
            raise exc


    def __init__(self, ring: KeyRing, transport=None):
        self.ring = ring
        self.transport = transport or _http
        self.ledger = Ledger()
        self._known: dict[str, list[str]] = {}

    # -- model discovery

    def list_models(self, service: str) -> list[str]:
        """The live catalogue. Cached for the run."""
        if service in self._known:
            return self._known[service]

        ids: list[str] = []
        # Try every key for this service until one returns a model list.
        # The old code tried only one key, so if the first groq key was dead
        # it returned [] even though a second alive key existed.
        last_status = 0
        attempted_keys = 0
        while True:
            try:
                key = self.ring.next_key(service)
            except AllKeysDown as exc:
                if attempted_keys == 0:
                    log.warn(str(exc))
                break

            attempted_keys += 1
            status = 0
            body = None

            if service == "groq":
                status, body = self.transport(GROQ_MODELS, {"Authorization": f"Bearer {key.value}"}, None, 30)
                if status == 200 and isinstance(body, dict):
                    ids = [m.get("id", "") for m in body.get("data", []) if m.get("id")]
            elif service == "gemini":
                url = GEMINI_MODELS.format(key=key.value)
                status, body = self.transport(url, {}, None, 30)
                if status == 200 and isinstance(body, dict):
                    for m in body.get("models", []):
                        name = (m.get("name") or "").replace("models/", "")
                        methods = m.get("supportedGenerationMethods") or []
                        if name and ("generateContent" in methods or not methods):
                            ids.append(name)
            elif service == "openrouter":
                status, body = self.transport(
                    OPENROUTER_MODELS,
                    {"Authorization": f"Bearer {key.value}"}, None, 30)
                if status == 200 and isinstance(body, dict):
                    ids = [m.get("id", "") for m in body.get("data", []) if m.get("id")]
            elif service == "huggingface":
                status, body = self.transport(
                    HUGGINGFACE_MODELS,
                    {"Authorization": f"Bearer {key.value}"}, None, 30)
                if status == 200 and isinstance(body, dict):
                    ids = [m.get("id", "") for m in body.get("data", []) if m.get("id")]
                if not ids:
                    ids = list(HUGGINGFACE_MODELS_DEFAULT)
            elif service == "together":
                status, body = self.transport(
                    TOGETHER_MODELS,
                    {"Authorization": f"Bearer {key.value}"}, None, 30)
                if status == 200 and isinstance(body, dict):
                    data = body.get("data") if isinstance(body.get("data"), list) else body
                    if isinstance(data, list):
                        ids = [m.get("id") or m.get("name", "") for m in data if m]
                if not ids:
                    ids = list(TOGETHER_MODELS_DEFAULT)
            elif service == "openai":
                status, body = self.transport(
                    OPENAI_MODELS,
                    {"Authorization": f"Bearer {key.value}"}, None, 30)
                if status == 200 and isinstance(body, dict):
                    ids = [m.get("id", "") for m in body.get("data", []) if m.get("id")]
                if not ids:
                    ids = list(OPENAI_MODELS_DEFAULT)
            elif service == "anthropic":
                status = 200
                ids = list(ANTHROPIC_MODELS_DEFAULT)
            else:
                log.warn(f"{service}: no live model listing implemented (key is kept)")
                self._known[service] = []
                return []

            last_status = status

            if ids:
                break

            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status} on model list")
                continue
            elif status == 429:
                self.ring.mark_exhausted(key.value, "429 on model list")
                continue

            break

        # Listing models should not consume the key for the actual generation.
        # The ring's _tried_this_run set would otherwise block the only alive key.
        # Clear alive keys of this service from tried so _call_* can reuse them.
        if ids:
            for k in self.ring.all():
                if k.service == service and k.state == "alive":
                    self.ring._tried_this_run.discard(k.value)
            # also discard the last key we tried that succeeded, even if not yet marked alive
            # (list_models marks alive only after generation, not after listing)
            # So clear all tried for this service to allow generation to try them
            self.ring._tried_this_run = {v for v in self.ring._tried_this_run if self.ring.find(v) and self.ring.find(v).service != service}

        self._known[service] = ids
        return ids

    # -- a single call, with key rotation and never a retry

    def _call_groq(self, prompt: str, system: str, model: str,
                   temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """Returns (ok, text, note). Advances keys on failure, never retries one."""
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("groq")
            except AllKeysDown as exc:
                return False, "", str(exc)

            attempted += 1
            payload = {
                "model": model,
                "messages": ([{"role": "system", "content": system}] if system else [])
                            + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            # deliberately NO response_format - see the module docstring
            started = time.time()
            status, body = self.transport(
                GROQ_URL, {"Authorization": f"Bearer {key.value}",
                           "Content-Type": "application/json"}, payload)

            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                note = ""
                if not text:
                    # a reasoning model may have put the whole answer in reasoning
                    reasoning = (message.get("reasoning") or "").strip()
                    if reasoning:
                        text, note = reasoning, "answer recovered from the reasoning field"
                self.ring.mark_alive(key.value)
                self.ledger.add(Call("groq", model, key.value, attempted, True,
                                     time.time() - started, note, text))
                if not text:
                    return False, "", "empty response"
                return True, text, note

            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("groq", model, key.value, attempted, False,
                                     time.time() - started, f"{status} dead key"))
                continue                       # next key, this one is gone

            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("groq", model, key.value, attempted, False,
                                     time.time() - started, "429 rate limited"))
                continue                       # next key, never the same one again

            if status == 400:
                # the answer may still be sitting in failed_generation
                recovered = ""
                if isinstance(body, dict):
                    err = body.get("error") or {}
                    recovered = (err.get("failed_generation") or "").strip()
                self.ledger.add(Call("groq", model, key.value, attempted, bool(recovered),
                                     time.time() - started, "400", recovered))
                if recovered:
                    return True, recovered, "answer recovered from failed_generation"
                note = "400"
                if isinstance(body, dict):
                    err = body.get("error") or {}
                    note = f"400 {err.get('message', '')[:80]}"
                return False, "", note

            if status in (404, 422) or (isinstance(body, dict) and "model" in str(body).lower()):
                self.ledger.add(Call("groq", model, key.value, attempted, False,
                                     time.time() - started, f"{status} model unavailable"))
                return False, "", f"{status} model unavailable"

            if status == 503:
                # 503 = server overload, not a key problem.
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("groq", model, key.value, attempted, False,
                                     time.time() - started, "503 server overload"))
                time.sleep(2.0)
                return False, "", "503 overload (server side)"

            if status == 0:
                self.ledger.add(Call("groq", model, key.value, attempted, False,
                                     time.time() - started, "network"))
                return False, "", "network failure"

            self.ledger.add(Call("groq", model, key.value, attempted, False,
                                 time.time() - started, f"{status}"))
            return False, "", f"unexpected status {status}"

    def _call_gemini(self, prompt: str, system: str, model: str,
                     temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("gemini")
            except AllKeysDown as exc:
                return False, "", str(exc)

            attempted += 1
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature,
                                     "maxOutputTokens": max_tokens},
            }
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}

            started = time.time()
            status, body = self.transport(
                GEMINI_URL.format(model=model, key=key.value),
                {"Content-Type": "application/json"}, payload)

            if status == 200 and isinstance(body, dict):
                text = ""
                for candidate in body.get("candidates", []):
                    for part in (candidate.get("content") or {}).get("parts", []):
                        text += part.get("text", "")
                text = text.strip()
                self.ring.mark_alive(key.value)
                self.ledger.add(Call("gemini", model, key.value, attempted, bool(text),
                                     time.time() - started, "", text))
                return (True, text, "") if text else (False, "", "empty response")

            if status in (400, 401, 403):
                note = ""
                if isinstance(body, dict):
                    note = ((body.get("error") or {}).get("message") or "")[:90]
                # a 400 on Gemini usually means this key is bad or the model is wrong,
                # so the key goes dead and the caller may try another model
                self.ring.mark_dead(key.value, f"{status} {note}".strip())
                self.ledger.add(Call("gemini", model, key.value, attempted, False,
                                     time.time() - started, f"{status} {note}".strip()))
                continue

            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("gemini", model, key.value, attempted, False,
                                     time.time() - started, "429 rate limited"))
                continue

            if status == 404:
                self.ledger.add(Call("gemini", model, key.value, attempted, False,
                                     time.time() - started, "404 model unavailable"))
                return False, "", "404 model unavailable"

            if status == 503:
                # 503 Service Unavailable = Google's side, not the key.
                # Remove the key from the tried-this-run pool so the next
                # candidate can pick it again, and back off briefly so we
                # don't hammer the overloaded endpoint.
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("gemini", model, key.value, attempted, False,
                                     time.time() - started, f"{status} (server overloaded)"))
                time.sleep(2.0)
                return False, "", f"{status} overload (google side)"

            self.ledger.add(Call("gemini", model, key.value, attempted, False,
                                 time.time() - started, f"{status}"))
            return False, "", f"unexpected status {status}"

    def call(self, prompt: str, model: str, service: str = "groq",
             system: str = "", temperature: float = 0.85,
             max_tokens: int = 4000) -> tuple[bool, str, str]:
        """One call to one model. Returns (ok, text, note)."""
        try:
            if service == "groq":
                return self._call_groq(prompt, system, model, temperature, max_tokens)
            if service == "gemini":
                return self._call_gemini(prompt, system, model, temperature, max_tokens)
            if service == "openrouter":
                return self._call_openrouter(prompt, system, model, temperature, max_tokens)
            if service == "huggingface":
                return self._call_huggingface(prompt, system, model, temperature, max_tokens)
            if service == "together":
                return self._call_together(prompt, system, model, temperature, max_tokens)
            if service == "openai":
                return self._call_openai(prompt, system, model, temperature, max_tokens)
            if service == "anthropic":
                return self._call_anthropic(prompt, system, model, temperature, max_tokens)
        except Exception as exc:                # never let a provider crash a run
            return False, "", f"{type(exc).__name__}: {exc}"
        return False, "", f"unknown service {service}"

    def _call_openrouter(self, prompt: str, system: str, model: str,
                         temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """Same shape as Groq - OpenRouter is OpenAI-compatible."""
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("openrouter")
            except AllKeysDown as exc:
                return False, "", str(exc)
            attempted += 1
            payload = {
                "model": model,
                "messages": ([{"role": "system", "content": system}] if system else [])
                          + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            started = time.time()
            status, body = self.transport(
                OPENROUTER_URL,
                {"Authorization": f"Bearer {key.value}",
                 "HTTP-Referer": "https://antar.local",
                 "X-Title": "ANTAR"}, payload)
            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    self.ring.mark_alive(key.value)
                    self.ledger.add(Call("openrouter", model, key.value,
                                          attempted, True, time.time() - started, "", text))
                    return True, text, ""
                self.ledger.add(Call("openrouter", model, key.value,
                                      attempted, False, time.time() - started, "empty response"))
                return False, "", "empty response"
            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("openrouter", model, key.value,
                                      attempted, False, time.time() - started, f"{status} dead key"))
                continue
            if status == 429:
                self.ring.mark_exhausted(key.value, f"429")
                self.ledger.add(Call("openrouter", model, key.value,
                                      attempted, False, time.time() - started, "429 exhausted"))
                return False, "", "429 rate limited"
            self.ring.note_failure(key.value, f"{status} on {model}")
            note = f"unexpected status {status}"
            if isinstance(body, dict) and body.get("error"):
                err = body["error"]
                if isinstance(err, dict):
                    note = f"{status}: {err.get('message', note)}"
                else:
                    note = f"{status}: {err}"
            self.ledger.add(Call("openrouter", model, key.value,
                                  attempted, False, time.time() - started, note))
            return False, "", note

    def _call_huggingface(self, prompt: str, system: str, model: str,
                          temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """
        Huggingface router (router.huggingface.co) is OpenAI-compatible.
        Same shape as Groq / OpenRouter. Real provider, no mock.
        """
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("huggingface")
            except AllKeysDown as exc:
                return False, "", str(exc)
            attempted += 1
            payload = {
                "model": model,
                "messages": ([{"role": "system", "content": system}] if system else [])
                          + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            started = time.time()
            status, body = self.transport(
                HUGGINGFACE_URL,
                {"Authorization": f"Bearer {key.value}",
                 "Content-Type": "application/json"}, payload)
            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    self.ring.mark_alive(key.value)
                    self.ledger.add(Call("huggingface", model, key.value,
                                          attempted, True, time.time() - started, "", text))
                    return True, text, ""
                self.ledger.add(Call("huggingface", model, key.value,
                                      attempted, False, time.time() - started, "empty response"))
                return False, "", "empty response"
            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("huggingface", model, key.value,
                                      attempted, False, time.time() - started, f"{status} dead key"))
                continue
            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("huggingface", model, key.value,
                                      attempted, False, time.time() - started, "429 rate limited"))
                return False, "", "429 rate limited"
            if status == 503:
                # HF routes to many providers; some throttle. Back off and
                # let the next candidate model on the same key try.
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("huggingface", model, key.value,
                                      attempted, False, time.time() - started, "503 server overload"))
                time.sleep(2.0)
                return False, "", "503 overload (server side)"
            note = f"unexpected status {status}"
            if isinstance(body, dict) and body.get("error"):
                err = body["error"]
                if isinstance(err, dict):
                    note = f"{status}: {err.get('message', note)}"
                else:
                    note = f"{status}: {err}"
            self.ledger.add(Call("huggingface", model, key.value,
                                  attempted, False, time.time() - started, note))
            return False, "", note


    def _call_together(self, prompt: str, system: str, model: str,
                       temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """
        Together AI (api.together.xyz) is OpenAI-compatible.
        Real provider, no mock.
        """
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("together")
            except AllKeysDown as exc:
                return False, "", str(exc)
            attempted += 1
            payload = {
                "model": model,
                "messages": ([{"role": "system", "content": system}] if system else [])
                          + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            started = time.time()
            status, body = self.transport(
                TOGETHER_URL,
                {"Authorization": f"Bearer {key.value}",
                 "Content-Type": "application/json"}, payload)
            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    self.ring.mark_alive(key.value)
                    self.ledger.add(Call("together", model, key.value,
                                          attempted, True, time.time() - started, "", text))
                    return True, text, ""
                self.ledger.add(Call("together", model, key.value,
                                      attempted, False, time.time() - started, "empty response"))
                return False, "", "empty response"
            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("together", model, key.value,
                                      attempted, False, time.time() - started, f"{status} dead key"))
                continue
            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("together", model, key.value,
                                      attempted, False, time.time() - started, "429 rate limited"))
                return False, "", "429 rate limited"
            if status == 503:
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("together", model, key.value,
                                      attempted, False, time.time() - started, "503 server overload"))
                time.sleep(2.0)
                return False, "", "503 overload (server side)"
            note = f"unexpected status {status}"
            if isinstance(body, dict) and body.get("error"):
                err = body["error"]
                if isinstance(err, dict):
                    note = f"{status}: {err.get('message', note)}"
                else:
                    note = f"{status}: {err}"
            self.ledger.add(Call("together", model, key.value,
                                  attempted, False, time.time() - started, note))
            return False, "", note


    def _call_openai(self, prompt: str, system: str, model: str,
                     temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """
        OpenAI (api.openai.com) - real endpoint, OpenAI-compatible.
        Paid but has a free credit on new accounts.
        """
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("openai")
            except AllKeysDown as exc:
                return False, "", str(exc)
            attempted += 1
            payload = {
                "model": model,
                "messages": ([{"role": "system", "content": system}] if system else [])
                          + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            started = time.time()
            status, body = self.transport(
                OPENAI_URL,
                {"Authorization": f"Bearer {key.value}",
                 "Content-Type": "application/json"}, payload)
            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = (message.get("content") or "").strip()
                if text:
                    self.ring.mark_alive(key.value)
                    self.ledger.add(Call("openai", model, key.value,
                                          attempted, True, time.time() - started, "", text))
                    return True, text, ""
                self.ledger.add(Call("openai", model, key.value,
                                      attempted, False, time.time() - started, "empty response"))
                return False, "", "empty response"
            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("openai", model, key.value,
                                      attempted, False, time.time() - started, f"{status} dead key"))
                continue
            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("openai", model, key.value,
                                      attempted, False, time.time() - started, "429 rate limited"))
                return False, "", "429 rate limited"
            if status == 503:
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("openai", model, key.value,
                                      attempted, False, time.time() - started, "503 server overload"))
                time.sleep(2.0)
                return False, "", "503 overload (server side)"
            note = f"unexpected status {status}"
            if isinstance(body, dict) and body.get("error"):
                err = body["error"]
                if isinstance(err, dict):
                    note = f"{status}: {err.get('message', note)}"
                else:
                    note = f"{status}: {err}"
            self.ledger.add(Call("openai", model, key.value,
                                  attempted, False, time.time() - started, note))
            return False, "", note

    def _call_anthropic(self, prompt: str, system: str, model: str,
                        temperature: float, max_tokens: int) -> tuple[bool, str, str]:
        """
        Anthropic (api.anthropic.com) - real endpoint, NOT OpenAI-compatible.
        Uses their own /v1/messages shape with x-api-key + anthropic-version
        headers. System prompt goes in a top-level field, not in messages.
        """
        attempted = 0
        while True:
            try:
                key = self._next_key_with_fallback("anthropic")
            except AllKeysDown as exc:
                return False, "", str(exc)
            attempted += 1
            payload: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system
            started = time.time()
            status, body = self.transport(
                ANTHROPIC_URL,
                {"x-api-key": key.value,
                 "anthropic-version": ANTHROPIC_VERSION,
                 "Content-Type": "application/json"}, payload)
            if status == 200 and isinstance(body, dict):
                # Anthropic returns content blocks, not OpenAI choices
                content_blocks = body.get("content") or []
                text = "".join(
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                ).strip()
                if text:
                    self.ring.mark_alive(key.value)
                    self.ledger.add(Call("anthropic", model, key.value,
                                          attempted, True, time.time() - started, "", text))
                    return True, text, ""
                self.ledger.add(Call("anthropic", model, key.value,
                                      attempted, False, time.time() - started, "empty response"))
                return False, "", "empty response"
            if status in (401, 403):
                self.ring.mark_dead(key.value, f"{status}")
                self.ledger.add(Call("anthropic", model, key.value,
                                      attempted, False, time.time() - started, f"{status} dead key"))
                continue
            if status == 429:
                self.ring.mark_exhausted(key.value, "429")
                self.ledger.add(Call("anthropic", model, key.value,
                                      attempted, False, time.time() - started, "429 rate limited"))
                return False, "", "429 rate limited"
            if status == 529:
                # Anthropic-specific: 529 = overloaded
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("anthropic", model, key.value,
                                      attempted, False, time.time() - started, "529 overloaded"))
                time.sleep(2.0)
                return False, "", "529 overload (anthropic side)"
            if status == 503:
                self.ring._tried_this_run.discard(key.value)
                self.ledger.add(Call("anthropic", model, key.value,
                                      attempted, False, time.time() - started, "503 server overload"))
                time.sleep(2.0)
                return False, "", "503 overload (server side)"
            note = f"unexpected status {status}"
            if isinstance(body, dict) and body.get("error"):
                err = body["error"]
                if isinstance(err, dict):
                    note = f"{status}: {err.get('message', note)}"
                else:
                    note = f"{status}: {err}"
            self.ledger.add(Call("anthropic", model, key.value,
                                  attempted, False, time.time() - started, note))
            return False, "", note


# ---------------------------------------------------------------- json help

def extract_json(text: str) -> dict | None:
    """
    Pull one JSON object out of a model reply, tolerating the usual mess:
    markdown fences, leading prose, trailing commentary, trailing commas,
    nested braces in prose, and replies that contain multiple JSON objects.
    """
    if not text:
        return None
    cleaned = text.strip()

    # strip a leading markdown code fence: ```json ... ``` or ``` ... ```
    if cleaned.startswith("```"):
        # drop the first line (the opening ```json or ```)
        first_nl = cleaned.find("\n")
        if first_nl != -1:
            cleaned = cleaned[first_nl + 1:]
        # drop the trailing ``` if it is there
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()
        # drop the language tag if it survived (e.g. "json\n{...}")
        if cleaned.lower().startswith("json"):
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl + 1:]
            cleaned = cleaned.strip()

    # find every top-level JSON object using a balanced-brace scan.
    # we want the LONGEST balanced object whose first key is one we expect
    # (e.g. "topics", "title_hi", "script"), so we can pick the right one.
    candidates: list[str] = []
    i = 0
    n = len(cleaned)
    while i < n:
        if cleaned[i] == "{":
            depth = 0
            j = i
            in_string = False
            escape = False
            while j < n:
                ch = cleaned[j]
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            candidates.append(cleaned[i:j + 1])
                            break
                j += 1
            if j >= n:
                break
            i = j + 1
        else:
            i += 1

    if not candidates:
        return None

    # prefer the candidate whose first key is "topics" (the writer output shape)
    # then one whose first key is anything else. If neither, take the longest.
    preferred_keys = ("topics", "script", "title_hi", "render_id")
    ranked = sorted(
        candidates,
        key=lambda c: (
            -int(any((k + '"') in c[:200] for k in preferred_keys)),
            -len(c),
        ),
    )

    _trailing = re.compile(r",(\s*[}\]])")

    for raw in ranked:
        for attempt in (raw, _trailing.sub(r"\1", raw)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return None
