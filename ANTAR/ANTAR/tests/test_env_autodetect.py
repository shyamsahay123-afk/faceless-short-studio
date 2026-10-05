"""
Tests for vendor auto-detection from key value prefix.

The rule: when an env-var name has no service hint (e.g. G1=...),
ANTAR should still know which service the key is for, based on the
value's prefix. False positives are worse than no detection.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from antar.envfile import _detect_service_from_value, parse


def test_groq_prefix():
    assert _detect_service_from_value("gsk_abc123def456") == "groq"


def test_anthropic_prefix_takes_priority_over_openai():
    # sk-ant- is a real Anthropic prefix; the generic sk- check must
    # not eat it.
    assert _detect_service_from_value("sk-ant-api03-xxxxxxxxxxxxxx") == "anthropic"


def test_openai_standard_prefix():
    assert _detect_service_from_value("sk-abcdefghijklmnopqrstuvwxyz") == "openai"


def test_openai_project_prefix():
    assert _detect_service_from_value("sk-proj-abc123def456") == "openai"


def test_openai_service_account_prefix():
    assert _detect_service_from_value("sk-svcacct-abc123def456") == "openai"


def test_huggingface_prefix():
    assert _detect_service_from_value("hf_xxxxxxxxxxxxxxxxxxxxxxxx") == "huggingface"


def test_xai_prefix_falls_back_to_groq_bucket():
    # xAI / Grok has no ladder slot yet; best fit is to use the key
    # as if it were a Groq-class LLM. The user can still rename
    # the env var to override.
    assert _detect_service_from_value("xai-1234567890") == "groq"


def test_google_ai_studio_prefix():
    assert _detect_service_from_value("AIzaSyAbcDefGhiJkl") == "gemini"


def test_perplexity_returns_none_no_provider_yet():
    # pplx- is real but ANTAR has no Perplexity provider. Returning
    # None is the right answer - the loader will file it as unknown
    # with a clear note rather than burning the key on a wrong vendor.
    assert _detect_service_from_value("pplx-xxxxxxxxxxxx") is None


def test_unrecognised_returns_none():
    assert _detect_service_from_value("random_thing") is None


def test_empty_returns_none():
    assert _detect_service_from_value("") is None


def test_parse_picks_up_value_when_name_has_no_hint():
    env_text = (
        "G1=gsk_YOUR_GROQ_KEY_HERE\n"
        "O1=sk-abcdefghijklmnopqrstuvwxyz\n"
        "H1=hf_xxxxxxxxxxxxxxxxxxxxxxx\n"
    )
    keys, unused, unknown = parse(env_text)
    assert ("groq", "gsk_YOUR_GROQ_KEY_HERE") in keys
    assert ("openai", "sk-abcdefghijklmnopqrstuvwxyz") in keys
    assert ("huggingface", "hf_xxxxxxxxxxxxxxxxxxxxxxx") in keys
    assert unused == []
    assert unknown == []


def test_parse_unrecognised_goes_to_unknown_not_garbage():
    env_text = "R1=just_a_random_thing_without_a_prefix\n"
    keys, unused, unknown = parse(env_text)
    assert keys == []
    assert "R1" in unknown
    assert unused == []


def test_name_hint_still_takes_priority_over_value():
    # If both the name AND the value give a hint, the name wins. The
    # user wrote KEY_HINT_1=... and that's authoritative.
    env_text = "OPENAI_KEY_1=hf_this_is_a_hf_key_with_openai_in_the_name\n"
    keys, _, _ = parse(env_text)
    assert keys == [("openai", "hf_this_is_a_hf_key_with_openai_in_the_name")]


if __name__ == "__main__":
    test_groq_prefix()
    print("PASS  groq prefix")
    test_anthropic_prefix_takes_priority_over_openai()
    print("PASS  anthropic prefix priority")
    test_openai_standard_prefix()
    print("PASS  openai standard prefix")
    test_openai_project_prefix()
    print("PASS  openai project prefix")
    test_openai_service_account_prefix()
    print("PASS  openai service account prefix")
    test_huggingface_prefix()
    print("PASS  huggingface prefix")
    test_xai_prefix_falls_back_to_groq_bucket()
    print("PASS  xai prefix -> groq bucket")
    test_google_ai_studio_prefix()
    print("PASS  google ai studio prefix")
    test_perplexity_returns_none_no_provider_yet()
    print("PASS  perplexity returns None (no provider)")
    test_unrecognised_returns_none()
    print("PASS  unrecognised returns None")
    test_empty_returns_none()
    print("PASS  empty returns None")
    test_parse_picks_up_value_when_name_has_no_hint()
    print("PASS  parse picks up value when name has no hint")
    test_parse_unrecognised_goes_to_unknown_not_garbage()
    print("PASS  unrecognised goes to unknown, not garbage")
    test_name_hint_still_takes_priority_over_value()
    print("PASS  name hint still wins over value")
    print("\nAll 14 tests passed")
