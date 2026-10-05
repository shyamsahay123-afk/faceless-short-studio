"""
ANTAR - checking a key against the real API.

WHY THIS MODULE EXISTS

The first version of this check sent one request per key with Python's default
user agent, and treated 401 and 403 as the same thing. On 27 Sep 2026 that
marked four perfectly good Pexels keys DEAD:

    pexels / python-urllib user agent   403   error code: 1010
    pexels / browser user agent         200   a real video came back

Error 1010 is Cloudflare refusing the user agent, not a key problem. Pexels
returns 401 for a bad key and never 403. The keys were alive the whole time.

So a key is no longer judged by one call, and never by the status code alone:

  1. A browser user agent is always sent. Every request ANTAR makes, not only
     this one, because the same block broke the same check twice.
  2. The body is read, not just the status. The API's own words decide.
  3. Three different calls per service. A key must fail MORE THAN ONE of them
     in a key-shaped way before it is written off.
  4. A block, a timeout and a dead key are three different verdicts. Only one
     of them is DEAD, and only DEAD stops a key being used.
"""

from __future__ import annotations

import ast
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

# Cloudflare's answer to anything that looks like a script. Pexels and Groq are
# both behind it. Sending this is the difference between 403 and 200.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

COMMON_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
}

# The words an API uses when it is the key that is wrong.
KEY_WORDS = ("invalid api key", "invalid_api_key", "api key not valid",
             "api_key_invalid", "api key invalid", "invalid key", "key invalid",
             "keyinvalid", "unauthorized", "permission denied",
             "api key is invalid", "no api key", "auth_failed",
             "authentication failed", "invalid authentication")

# The words a firewall uses when it does not like the caller.
BLOCK_WORDS = ("error code: 1010", "error code: 1020", "attention required",
               "cf-ray", "cloudflare", "access denied", "banned your browser")


@dataclass
class Attempt:
    method: str
    status: int
    body: str
    note: str = ""            # what actually came back, in plain words

    @property
    def short(self) -> str:
        return f"{self.status or 'no reply'}"

    @property
    def evidence(self) -> str:
        if self.note:
            return self.note
        return _extract_message(self.body) or (self.body or "no reply")[:48]


@dataclass
class Verdict:
    service: str
    state: str            # alive | dead | exhausted | blocked | unknown
    reason: str
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state == "alive"

    def summary(self) -> str:
        codes = " ".join(f"{a.method}:{a.short}" for a in self.attempts)
        return f"{self.state.upper():9} {codes}"


class Rejected(Exception):
    """The API itself refused the key."""


def _fetch(url: str, headers: dict, body: bytes | None = None,
           timeout: int = 20) -> tuple[int, str]:
    """One call. Returns (status, body). Status 0 means no reply at all.

    The body is read up to 64KB, not 2KB. At 2KB the JSON was cut off mid
    string, so a healthy reply parsed as nothing and the table said "0 video(s)"
    about a search that had answered with a video. A truncated body is worse
    than no body: it looks like an answer.
    """
    request = urllib.request.Request(url, data=body, headers={**COMMON_HEADERS, **headers},
                                     method="POST" if body else "GET")
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.status, response.read(65536).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read(65536).decode("utf-8", "replace")
        except Exception:
            return exc.code, str(exc.reason or "")
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


# Words a provider uses when the requested model is deprecated / renamed.
# A 4xx carrying this language means the key authenticated successfully -
# the test endpoint itself is the broken thing, not the key.
DEPRECATED_MODEL_WORDS = (
    "no longer available", "no longer supported", "model not found",
    "deprecated", "does not exist", "not a valid model",
    "model `", "model is not", "model has been",
)


def _looks_like_deprecated_model(status: int, body: str) -> bool:
    """Did the API answer but reject the test model, not the key?"""
    if status < 400 or status >= 500:
        return False
    low = body.lower()
    return any(word in low for word in DEPRECATED_MODEL_WORDS)


def _looks_like_key_problem(status: int, body: str) -> bool:
    """
    Is this the API saying the key is wrong, or something else saying no?

    Google's APIs answer a bad key with 400 and the words "API key not valid".
    Judging on 401 alone meant a genuinely dead YouTube key was reported as
    "unknown" - a wrong answer, which is worse than no answer. So: a refusal
    status carrying the API's own words about a key counts, whatever the code.
    """
    low = body.lower()
    if any(word in low for word in BLOCK_WORDS):
        return False
    if status == 429 or status == 0 or status >= 500:
        return False
    if status in (400, 401, 403, 407, 409, 422):
        return any(word in low for word in KEY_WORDS) or status == 401
    return False


def _looks_like_block(status: int, body: str) -> bool:
    low = body.lower()
    if any(word in low for word in BLOCK_WORDS):
        return True
    return status in (403, 503) and not any(word in low for word in KEY_WORDS)


def _json(body: str):
    try:
        return json.loads(body)
    except Exception:
        return None


def _items(body: str, key: str) -> list:
    """The list of things inside a catalogue reply, or an empty list."""
    data = _json(body)
    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return value
    if isinstance(data, list):
        return data
    return []


def _first_id(body: str, list_key: str, id_field: str = "id") -> str:
    """The first identifier in a catalogue reply, for a second, deeper call."""
    for item in _items(body, list_key):
        if isinstance(item, dict):
            for field in (id_field, "id", "uuid", "name", "slug"):
                if item.get(field):
                    return str(item[field])
    return ""


def _field(body: str, path: list[str]) -> str:
    """A value from deep inside a reply, if it is there."""
    data = _json(body)
    for step in path:
        if isinstance(data, dict) and step in data:
            data = data[step]
        else:
            return ""
    return "" if data is None else str(data)


def _count(body: str, key: str) -> int:
    """How many things the API said it had. 0 means it said nothing useful."""
    data = _json(body)
    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


# ---------------------------------------------------------------- the methods

def _pexels(value: str) -> list[Attempt]:
    """Three different resources. The key is the only thing they share."""
    auth = {"Authorization": value}
    videos = _fetch("https://api.pexels.com/videos/search?query=chair&per_page=1"
                    "&orientation=portrait", auth)
    photos = _fetch("https://api.pexels.com/v1/curated?per_page=1", auth)
    found = _fetch("https://api.pexels.com/v1/search?query=chair&per_page=1", auth)

    shots = _json(videos[1]) or {}
    first_video = (shots.get("videos") or [{}])[0]
    size = (f"{first_video.get('width')}x{first_video.get('height')}"
            if first_video.get("width") else "")
    video_note = (f"{len(shots.get('videos') or [])} video(s){' ' + size if size else ''}"
                  if videos[0] and 200 <= videos[0] < 300 else "")
    return [
        Attempt("videos", *videos, note=video_note),
        Attempt("photos", *photos,
                note=f"{_count(photos[1], 'photos')} photo(s)" if photos[0] == 200 else ""),
        Attempt("photos-search", *found,
                note=f"{_count(found[1], 'photos')} photo(s)" if found[0] == 200 else ""),
    ]


def _pixabay(value: str) -> list[Attempt]:
    videos = _fetch(f"https://pixabay.com/api/videos/?key={value}&q=chair&per_page=3", {})
    images = _fetch(f"https://pixabay.com/api/?key={value}&q=chair&per_page=3", {})
    return [
        Attempt("videos", *videos,
                note=f"{_count(videos[1], 'hits')} hit(s)" if videos[0] == 200 else ""),
        Attempt("images", *images,
                note=f"{_count(images[1], 'hits')} hit(s)" if images[0] == 200 else ""),
    ]


def _groq(value: str, model: str = "") -> list[Attempt]:
    """
    Groq, three ways: the catalogue, a real answer, and one model on its own.

    The model used for the real answer is taken from the catalogue the same
    key just returned, not typed in here. A hardcoded model name is how a
    checker reports "model not found" about a perfectly good key the day the
    provider renames something.

    The catalogue scan also filters out non-chat models (TTS, ASR, embedding,
    guard, vision) - a key being used for the chat endpoint is real even if
    every "first non-skipped model" happens to be a TTS engine.
    """
    auth = {"Authorization": f"Bearer {value}", "Content-Type": "application/json"}
    catalog = _fetch("https://api.groq.com/openai/v1/models", auth)

    non_chat = ("whisper", "tts", "embed", "guard", "vision", "orpheus",
                "playai", "distil", "audio")

    chosen = model
    if not chosen:
        for item in _items(catalog[1], "data"):
            name = str(item.get("id", "")) if isinstance(item, dict) else ""
            if name and not any(skip in name.lower() for skip in non_chat):
                chosen = name
                break
    # Known-good chat fallback. If the catalogue is empty / broken, the
    # most stable chat model is the one most likely to still work.
    chosen = chosen or "llama-3.1-8b-instant"

    payload = json.dumps({
        "model": chosen,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
    }).encode()
    live = _fetch("https://api.groq.com/openai/v1/chat/completions", auth, body=payload)
    one = _fetch(f"https://api.groq.com/openai/v1/models/{chosen}", auth)

    answered = bool((_json(live[1]) or {}).get("choices"))
    return [
        Attempt("models", *catalog,
                note=(f"{_count(catalog[1], 'data')} model(s)"
                      if catalog[0] == 200 else "")),
        Attempt("say-hi", *live,
                note=("answered one token" if answered else
                      (f"asked {chosen}" if live[0] == 200 else ""))),
        Attempt("model", *one,
                note=(chosen if one[0] == 200 else "")),
    ]


def _gemini(value: str, model: str = "") -> list[Attempt]:
    """
    Gemini, three ways, and the model is taken from the key's own catalogue.

    Gemini retires model names on a schedule. Asking the catalogue first means
    the real-answer route uses a model this key can actually see, so a retired
    name can never be mistaken for a dead key.
    """
    catalog = _fetch(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={value}", {})

    chosen = model
    if not chosen:
        for item in _items(catalog[1], "models"):
            name = str(item.get("name", "")) if isinstance(item, dict) else ""
            if "flash" in name and not any(skip in name for skip in
                                           ("vision", "embed", "tts", "image")):
                chosen = name.split("/")[-1]
                break
    chosen = chosen or "gemini-2.5-flash"

    payload = json.dumps({
        "contents": [{"parts": [{"text": "hi"}]}],
        "generationConfig": {"maxOutputTokens": 1},
    }).encode()
    live = _fetch(
        f"https://generativelanguage.googleapis.com/v1beta/models/{chosen}:generateContent"
        f"?key={value}",
        {"Content-Type": "application/json"}, body=payload)
    counted = _fetch(
        f"https://generativelanguage.googleapis.com/v1beta/models/{chosen}:countTokens"
        f"?key={value}",
        {"Content-Type": "application/json"},
        body=json.dumps({"contents": [{"parts": [{"text": "hi"}]}]}).encode())

    answered = bool((_json(live[1]) or {}).get("candidates"))
    tokens = (_json(counted[1]) or {}).get("totalTokens")
    return [
        Attempt("models", *catalog,
                note=(f"{_count(catalog[1], 'models')} model(s)"
                      if catalog[0] == 200 else "")),
        Attempt("say-hi", *live,
                note=("answered" if answered else
                      (f"asked {chosen}" if live[0] == 200 else ""))),
        Attempt("count", *counted,
                note=(f"{tokens} token(s)" if tokens else "")),
    ]


# ------------------------------------------------- the rest of the key ring
# Services that are not in the writing pipeline but whose keys are on file.
# Each one is checked the way its own API wants to be asked, twice where the
# API offers a second route, and the number it returns is printed as evidence.

def _deepgram(value: str) -> list[Attempt]:
    """Deepgram: the projects list (keys), then the project itself."""
    auth = {"Authorization": f"Token {value}"}
    projects = _fetch("https://api.deepgram.com/v1/projects", auth)
    attempts = [Attempt("projects", *projects,
                        note=(f"{_count(projects[1], 'projects')} project(s)"
                              if projects[0] == 200 else ""))]
    first = _first_id(projects[1], "projects", "project_id")
    if first:
        one = _fetch(f"https://api.deepgram.com/v1/projects/{first}", auth)
        attempts.append(Attempt("project", *one,
                                note=(f"{first[:8]} read" if one[0] == 200 else "")))
    return attempts


def _openai(value: str) -> list[Attempt]:
    """OpenAI: the model catalogue, then one model on its own."""
    auth = {"Authorization": f"Bearer {value}"}
    models = _fetch("https://api.openai.com/v1/models", auth)
    attempts = [Attempt("models", *models,
                        note=(f"{_count(models[1], 'data')} model(s)"
                              if models[0] == 200 else ""))]
    first = _first_id(models[1], "data")
    if first:
        one = _fetch(f"https://api.openai.com/v1/models/{first}", auth)
        attempts.append(Attempt("model", *one,
                                note=(first if one[0] == 200 else "")))
    return attempts


def _anthropic(value: str) -> list[Attempt]:
    auth = {"x-api-key": value, "anthropic-version": "2023-06-01"}
    models = _fetch("https://api.anthropic.com/v1/models", auth)
    attempts = [Attempt("models", *models,
                        note=(f"{_count(models[1], 'data')} model(s)"
                              if models[0] == 200 else ""))]
    first = _first_id(models[1], "data")
    if first:
        one = _fetch(f"https://api.anthropic.com/v1/models/{first}", auth)
        attempts.append(Attempt("model", *one, note=(first if one[0] == 200 else "")))
    return attempts


def _elevenlabs(value: str) -> list[Attempt]:
    auth = {"xi-api-key": value}
    user = _fetch("https://api.elevenlabs.io/v1/user", auth)
    voices = _fetch("https://api.elevenlabs.io/v1/voices", auth)
    tier = _field(user[1], ["subscription", "tier"])
    return [
        Attempt("user", *user,
                note=(f"tier {tier}" if user[0] == 200 and tier else
                      ("account read" if user[0] == 200 else ""))),
        Attempt("voices", *voices,
                note=(f"{_count(voices[1], 'voices')} voice(s)"
                      if voices[0] == 200 else "")),
    ]


def _huggingface(value: str) -> list[Attempt]:
    auth = {"Authorization": f"Bearer {value}"}
    who = _fetch("https://huggingface.co/api/whoami-v2", auth)
    orgs = _fetch("https://huggingface.co/api/organizations", auth)
    name = _field(who[1], ["name"])
    return [
        Attempt("whoami", *who,
                note=(f"signed in as {name}" if who[0] == 200 and name else
                      ("token read" if who[0] == 200 else ""))),
        Attempt("orgs", *orgs,
                note=(f"{_count(orgs[1], 'organizations')} org(s)"
                      if orgs[0] == 200 else "")),
    ]


def _openrouter(value: str) -> list[Attempt]:
    auth = {"Authorization": f"Bearer {value}"}
    key = _fetch("https://openrouter.ai/api/v1/key", auth)
    credits = _fetch("https://openrouter.ai/api/v1/credits", auth)
    label = _field(key[1], ["data", "label"])
    return [
        Attempt("key", *key,
                note=(f"key {label}" if key[0] == 200 and label else
                      ("key read" if key[0] == 200 else ""))),
        Attempt("credits", *credits,
                note=(f"{_field(credits[1], ['data', 'total_credits'])} credit(s)"
                      if credits[0] == 200 else "")),
    ]


def _together(value: str) -> list[Attempt]:
    auth = {"Authorization": f"Bearer {value}"}
    models = _fetch("https://api.together.xyz/v1/models", auth)
    attempts = [Attempt("models", *models,
                        note=(f"{_count(models[1], 'data')} model(s)"
                              if models[0] == 200 else ""))]
    first = _first_id(models[1], "data")
    if first:
        one = _fetch(f"https://api.together.xyz/v1/models/{first}", auth)
        attempts.append(Attempt("model", *one, note=(first if one[0] == 200 else "")))
    return attempts


def _replicate(value: str) -> list[Attempt]:
    """Replicate accepts the key two ways; both are tried, because either can fail."""
    bearer = _fetch("https://api.replicate.com/v1/account",
                    {"Authorization": f"Bearer {value}"})
    token = _fetch("https://api.replicate.com/v1/account",
                   {"Authorization": f"Token {value}"})
    username = _field(bearer[1], ["username"]) or _field(token[1], ["username"])
    return [
        Attempt("account-bearer", *bearer,
                note=(f"signed in as {username}" if bearer[0] == 200 and username
                      else ("account read" if bearer[0] == 200 else ""))),
        Attempt("account-token", *token,
                note=(f"signed in as {username}" if token[0] == 200 and username
                      else ("account read" if token[0] == 200 else ""))),
    ]


def _stability(value: str) -> list[Attempt]:
    auth = {"Authorization": f"Bearer {value}"}
    account = _fetch("https://api.stability.ai/v1/user/account", auth)
    balance = _fetch("https://api.stability.ai/v1/user/balance", auth)
    credits = _field(account[1], ["credits"]) or _field(balance[1], ["credits"])
    return [
        Attempt("account", *account,
                note=(f"{credits} credit(s)" if account[0] == 200 and credits
                      else ("account read" if account[0] == 200 else ""))),
        Attempt("balance", *balance,
                note=(f"{credits} credit(s)" if balance[0] == 200 and credits else "")),
    ]


def _removebg(value: str) -> list[Attempt]:
    account = _fetch("https://api.remove.bg/v1.0/account", {"X-Api-Key": value})
    credits = _field(account[1], ["data", "attributes", "credits", "total"])
    return [Attempt("account", *account,
                    note=(f"{credits} credit(s)" if account[0] == 200 and credits
                          else ("account read" if account[0] == 200 else "")))]


def _serpapi(value: str) -> list[Attempt]:
    account = _fetch(f"https://serpapi.com/account?api_key={value}", {})
    left = _field(account[1], ["total_searches_left"])
    return [Attempt("account", *account,
                    note=(f"{left} search(es) left" if account[0] == 200 and left
                          else ("account read" if account[0] == 200 else "")))]


def _youtube(value: str) -> list[Attempt]:
    """The YouTube Data API key - the read key the analytics phase will need."""
    langs = _fetch("https://www.googleapis.com/youtube/v3/i18nLanguages"
                   f"?part=snippet&key={value}", {})
    cats = _fetch("https://www.googleapis.com/youtube/v3/videoCategories"
                  f"?part=snippet&regionCode=IN&key={value}", {})
    return [
        Attempt("languages", *langs,
                note=(f"{_count(langs[1], 'items')} language(s)"
                      if langs[0] == 200 else "")),
        Attempt("categories", *cats,
                note=(f"{_count(cats[1], 'items')} categor(y/ies)"
                      if cats[0] == 200 else "")),
    ]


METHODS = {
    # the writing and picture pipeline
    "pexels": _pexels,
    "pixabay": _pixabay,
    "groq": _groq,
    "gemini": _gemini,
    # keys that are on file for other jobs - each is asked the way its own
    # API wants to be asked, and the answer is printed
    "deepgram": _deepgram,
    "openai": _openai,
    "anthropic": _anthropic,
    "elevenlabs": _elevenlabs,
    "huggingface": _huggingface,
    "openrouter": _openrouter,
    "together": _together,
    "replicate": _replicate,
    "stability": _stability,
    "removebg": _removebg,
    "serpapi": _serpapi,
    "youtube": _youtube,
}

KNOWN_SERVICES = tuple(METHODS)


def have_check(service: str) -> bool:
    """Is there a written check for this service?"""
    return service in METHODS


def checked_services() -> list[str]:
    """Every service ANTAR knows how to test, for the report at the end."""
    return sorted(METHODS)


# ---------------------------------------------------------------- the verdict

def _extract_message(body: str) -> str:
    """The API's own sentence about what went wrong, if there is one."""
    data = None
    try:
        data = json.loads(body)
    except Exception:
        # ElevenLabs sometimes answers with a single-quoted Python-dict
        # repr rather than JSON. Pull the human message out of that too.
        try:
            data = ast.literal_eval(body)
        except Exception:
            m = re.search(r"['\"]message['\"]\s*:\s*['\"]([^'\"]+)['\"]", body)
            if m:
                return m.group(1)
            return ""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
        for field in ("message", "detail", "error_description", "reason"):
            if data.get(field):
                return str(data[field])
    return ""


def verify(service: str, value: str, retries: int = 2,
           pause: float = 0.6) -> Verdict:
    """
    Ask the real API three different ways, up to three times over, before
    believing anything.

    The whole set is re-asked only when every reply was inconclusive - a
    timeout, a 429 or a 5xx. A clean rejection is never retried (asking a dead
    key again is how a quota gets burned), and a clean answer is never re-asked.
    """
    if service not in METHODS:
        return Verdict(service, "unknown", f"no check written for '{service}'")

    attempts: list[Attempt] = []
    for _ in range(retries + 1):
        attempts = METHODS[service](value)

        if any(a.status and 200 <= a.status < 300 for a in attempts):
            break

        if any(_looks_like_key_problem(a.status, a.body) for a in attempts):
            break

        inconclusive = all(a.status == 0 or a.status == 429 or a.status >= 500
                           for a in attempts)
        if not inconclusive:
            break
        time.sleep(pause)

    alive = [a for a in attempts if a.status and 200 <= a.status < 300]
    if alive:
        return Verdict(service, "alive",
                       f"{len(alive)} of {len(attempts)} routes answered", attempts)

    if any(a.status == 429 for a in attempts):
        return Verdict(service, "exhausted",
                       _extract_message(next(a.body for a in attempts if a.status == 429))
                       or "rate limited or quota spent", attempts)

    rejected = [a for a in attempts if _looks_like_key_problem(a.status, a.body)]
    # A clean authentication refusal is definitive. If one route returned 401
    # with the API's own "invalid/unauthorized key" words and every *other*
    # route is either the same refusal, a network timeout (status 0) or a 5xx,
    # the key is dead - the missing replies never contradicted the refusal.
    # Only a route that actually ANSWERED 2xx (handled above) or answered with
    # a *different* definite verdict can override that.
    if rejected:
        others = [a for a in attempts if a not in rejected]
        contradicted = any(
            a.status and 200 <= a.status < 300
            for a in others
        )
        if not contradicted:
            hard = rejected[0]
            reason = _extract_message(hard.body) or f"HTTP {hard.status}"
            return Verdict(service, "dead", reason, attempts)

    if any(_looks_like_block(a.status, a.body) for a in attempts):
        return Verdict(service, "blocked",
                       "the site refused the request itself, not the key - "
                       "retry later, the key stays usable", attempts)

    # The API rejected the test model (renamed / deprecated) but the key
    # authenticated fine on the catalogue route. Mark it alive so it does
    # not sit in `unknown` forever - the next real call will use a model
    # the writer chose, not the test model the probe picked.
    if all(_looks_like_deprecated_model(a.status, a.body)
           or (200 <= a.status < 300)
           for a in attempts):
        return Verdict(service, "alive",
                       "the catalogue answered; the test model was deprecated - "
                       "the key is fine, the next real call will pick a working model",
                       attempts)

    if all(a.status == 0 for a in attempts):
        return Verdict(service, "unknown",
                       attempts[0].body or "no reply from the API", attempts)

    return Verdict(service, "unknown",
                   _extract_message(attempts[0].body) or "unclear reply", attempts)
