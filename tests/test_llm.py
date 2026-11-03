import json
from pathlib import Path

import pytest

from dhf.llm import LLM, BudgetExceeded
from dhf.models import Claims

PACK = {
    "facts": {},
    "evidence": [
        {"id": "SRS-001", "body": "Deliver configured flow.", "attributes": {"synthetic": True}}
    ],
}


def test_mock_cache_and_schema(tmp_path: Path) -> None:
    llm = LLM(root=tmp_path)
    Claims.model_validate(llm.generate("test", 1, "Return claims.", PACK))
    llm.generate("test", 1, "Return claims.", PACK)
    assert (llm.calls, llm.hits) == (1, 1)
    llm.generate("test", 2, "Return claims.", PACK)
    assert llm.calls == 2
    assert LLM(root=tmp_path).generate("test", 1, "Return claims.", PACK)


def test_caps_persistence_and_failed_reservation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1000")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1000")
    from dhf.llm.adapters.mock import MockAdapter

    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=0.001)
    with pytest.raises(BudgetExceeded):
        llm.generate("t", 1, "p", PACK, 1000)
    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=20, build_cap=20, total_cap=5)
    llm.generate("t", 1, "p", PACK, 1000)
    spent = json.loads((tmp_path / "ledger.json").read_text())["openai"]["reserved_usd"]
    assert 2 < spent < 4  # First reservation fits the hard cap; a second cannot.
    with pytest.raises(BudgetExceeded):
        LLM("openai", tmp_path, MockAdapter(), run_cap=20, build_cap=20, total_cap=5).generate(
            "t", 2, "p", PACK, 1000
        )


def test_non_synthetic_never_sent(tmp_path: Path) -> None:
    from dhf.llm.adapters.mock import MockAdapter

    with pytest.raises(ValueError, match="synthetic"):
        LLM("openai", tmp_path, MockAdapter()).generate("t", 1, "p", {"evidence": [{"id": "REAL"}]})


def test_build_cap_and_cumulative_run_cap(tmp_path: Path, monkeypatch) -> None:
    from dhf.llm.adapters.mock import MockAdapter

    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1000")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1000")
    with pytest.raises(BudgetExceeded):
        LLM("openai", tmp_path, MockAdapter(), run_cap=20, build_cap=0.5).generate(
            "x", 1, "p", PACK, 1000
        )
    llm = LLM("openai", tmp_path, MockAdapter(), run_cap=4, build_cap=20, total_cap=25)
    llm.generate("x", 1, "p", PACK, 1000)
    with pytest.raises(BudgetExceeded):
        llm.generate("x", 2, "p", PACK, 1000)


def test_schema_file_matches_contract() -> None:
    assert (
        json.loads(Path("specs/schemas/claims.v1.json").read_text()) == Claims.model_json_schema()
    )


def test_cache_key_has_unambiguous_fields_and_prompt_hash(tmp_path: Path) -> None:
    llm = LLM(root=tmp_path)
    llm.generate("x", 12, "original prompt", PACK)
    llm.generate("x1", 2, "original prompt", PACK)
    llm.generate("x", 12, "edited prompt", PACK)
    assert llm.calls == 3
    llm.generate("x", 12, "edited prompt", PACK)
    assert llm.hits == 1


def test_env_isolation_and_memoization(tmp_path: Path, monkeypatch) -> None:
    import os

    from dhf.config import load_env, setting

    assert "ANTHROPIC_API_KEY" not in os.environ
    assert "OPENAI_API_KEY" not in os.environ
    assert setting("ANTHROPIC_API_KEY") == ""
    path = tmp_path / "config.env"
    path.write_text("SAMPLE=value\n")
    monkeypatch.setenv("DHF_ENV_FILE", str(path))
    assert setting("SAMPLE") == "value"
    path.write_text("SAMPLE=changed\n")
    assert setting("SAMPLE") == "value"
    assert load_env.cache_info().hits > 0


def test_real_provider_network_is_blocked(monkeypatch) -> None:
    import socket

    from dhf.llm.adapters.openai import OpenAIAdapter
    from dhf.llm.errors import DraftingUnavailable

    with pytest.raises(OSError, match="Tests prohibit"):
        socket.create_connection(("api.openai.com", 443))
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-not-a-real-key")
    with pytest.raises(DraftingUnavailable) as failed:
        OpenAIAdapter().complete("gpt-4.1-nano", "Return JSON claims.", PACK, 100)
    assert failed.value.details["error_type"] == "APIConnectionError"
    assert failed.value.details["reason"] == "provider_error"


def test_actual_cost_reconciliation_and_failure_reservation(tmp_path: Path, monkeypatch) -> None:
    from dhf.llm.adapters.mock import MockAdapter

    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1")

    class UsageAdapter(MockAdapter):
        def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
            return {
                **super().complete(model, prompt, pack, limit),
                "_usage": {"input_tokens": 10, "output_tokens": 20},
            }

    llm = LLM("openai", tmp_path, UsageAdapter())
    llm.generate("usage", 1, "p", PACK)
    ledger = json.loads((tmp_path / "ledger.json").read_text())["openai"]
    assert ledger["reserved_usd"] == pytest.approx(0)
    assert ledger["actual_usd"] == pytest.approx(0.00003)

    class FailureAdapter(UsageAdapter):
        def complete(self, model: str, prompt: str, pack: dict, limit: int) -> dict:
            raise ValueError("Provider failure")

    with pytest.raises(ValueError, match="failure"):
        LLM("openai", tmp_path, FailureAdapter()).generate("fail", 1, "p", PACK)
    failed = json.loads((tmp_path / "ledger.json").read_text())["openai"]
    assert failed["reserved_usd"] > 0
    assert failed["actual_usd"] == ledger["actual_usd"]
    llm.generate("empty", 1, "p", {"evidence": [], "facts": {}})


def test_provider_contracts_thinking_strict_json_and_usage(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    from types import SimpleNamespace as NS

    import dhf.llm.adapters.anthropic as aa
    import dhf.llm.adapters.openai as oa

    captured = {}

    def anthropic_create(**kwargs):
        captured["anthropic"] = kwargs
        return NS(
            stop_reason="end_turn",
            content=[NS(type="thinking"), NS(type="text", text='{"claims":[]}')],
            usage=NS(input_tokens=10, output_tokens=20),
        )

    monkeypatch.setattr(aa, "Anthropic", lambda **_: NS(messages=NS(create=anthropic_create)))
    assert (
        aa.AnthropicAdapter().complete("claude-haiku-5-5", "schema prompt", PACK, 4000)["_usage"][
            "output_tokens"
        ]
        == 20
    )
    assert "temperature" not in captured["anthropic"]
    assert captured["anthropic"]["system"] == "schema prompt"

    def openai_create(**kwargs):
        captured["openai"] = kwargs
        return NS(
            choices=[NS(finish_reason="stop", message=NS(refusal=None, content='{"claims":[]}'))],
            usage=NS(prompt_tokens=10, completion_tokens=20),
        )

    monkeypatch.setattr(oa, "OpenAI", lambda **_: NS(chat=NS(completions=NS(create=openai_create))))
    assert (
        oa.OpenAIAdapter().complete("gpt-4.1-nano", "schema prompt", PACK, 4000)["_usage"][
            "input_tokens"
        ]
        == 10
    )
    schema = captured["openai"]["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert "confidence" in schema["schema"]["$defs"]["Claim"]["required"]
    assert captured["openai"]["max_completion_tokens"] == 4000


def test_provider_truncation_and_refusal_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    from types import SimpleNamespace as NS

    import dhf.llm.adapters.anthropic as aa
    import dhf.llm.adapters.openai as oa

    for reason in ("max_tokens", "refusal"):
        monkeypatch.setattr(
            aa,
            "Anthropic",
            lambda reason=reason, **_: NS(messages=NS(create=lambda **_: NS(stop_reason=reason))),
        )
        from dhf.llm.errors import DraftingUnavailable

        with pytest.raises(DraftingUnavailable) as failure:
            aa.AnthropicAdapter().complete("test", "p", PACK, 4000)
        assert failure.value.details["reason"] == reason
    monkeypatch.setattr(
        oa,
        "OpenAI",
        lambda **_: NS(
            chat=NS(completions=NS(create=lambda **_: NS(choices=[NS(finish_reason="length")])))
        ),
    )
    with pytest.raises(ValueError, match="truncated"):
        oa.OpenAIAdapter().complete("test", "p", PACK, 4000)


def test_provider_keys_from_env_file_and_missing_key_fail_fast(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace as NS

    import dhf.llm.adapters.anthropic as aa
    import dhf.llm.adapters.openai as oa

    for adapter, key in [
        (aa.AnthropicAdapter(), "ANTHROPIC_API_KEY"),
        (oa.OpenAIAdapter(), "OPENAI_API_KEY"),
    ]:
        with pytest.raises(ValueError, match="Missing " + key):
            adapter.complete("test", "p", PACK, 4000)
    env = tmp_path / "fake.env"
    env.write_text("ANTHROPIC_API_KEY=fake-anthropic\nOPENAI_API_KEY=fake-openai\n")
    monkeypatch.setenv("DHF_ENV_FILE", str(env))
    received = {}

    def anthropic_factory(**kwargs):
        received["anthropic"] = kwargs["api_key"]
        return NS(
            messages=NS(
                create=lambda **_: NS(
                    stop_reason="end_turn",
                    content=[NS(type="text", text='{"claims":[]}')],
                    usage=NS(input_tokens=1, output_tokens=1),
                )
            )
        )

    def openai_factory(**kwargs):
        received["openai"] = kwargs["api_key"]
        return NS(
            chat=NS(
                completions=NS(
                    create=lambda **_: NS(
                        choices=[
                            NS(
                                finish_reason="stop",
                                message=NS(refusal=None, content='{"claims":[]}'),
                            )
                        ],
                        usage=NS(prompt_tokens=1, completion_tokens=1),
                    )
                )
            )
        )

    monkeypatch.setattr(aa, "Anthropic", anthropic_factory)
    monkeypatch.setattr(oa, "OpenAI", openai_factory)
    aa.AnthropicAdapter().complete("test", "p", PACK, 4000)
    oa.OpenAIAdapter().complete("test", "p", PACK, 4000)
    assert received == {"anthropic": "fake-anthropic", "openai": "fake-openai"}


def test_provider_schema_has_no_numeric_bounds_but_response_validation_does() -> None:
    from pydantic import ValidationError

    from dhf.models import Claims, strict_claims_schema

    def assert_unbounded(value):
        if isinstance(value, dict):
            assert not {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"} & set(value)
            for v in value.values():
                assert_unbounded(v)
        if isinstance(value, list):
            for v in value:
                assert_unbounded(v)

    assert_unbounded(strict_claims_schema())
    for confidence in (-0.01, 1.01):
        with pytest.raises(ValidationError):
            Claims.model_validate(
                {
                    "claims": [
                        {
                            "text": "Point",
                            "kind": "suggested",
                            "citations": [],
                            "confidence": confidence,
                        }
                    ]
                }
            )


def test_ledger_tokens_accumulate_across_distinct_calls(tmp_path: Path) -> None:
    class UsageAdapter:
        def complete(self, *args):
            return {"claims": [], "_usage": {"input_tokens": 10, "output_tokens": 20}}

    llm = LLM(provider="anthropic", adapter=UsageAdapter(), root=tmp_path)
    for version in (1, 2):
        llm.generate("test", version, "p", PACK)
    entry = json.loads((tmp_path / "ledger.json").read_text())["anthropic"]
    assert entry["calls"] == 2
    assert entry["input_tokens"] == 20 and entry["output_tokens"] == 40


def test_sdk_error_is_sanitized_in_section_cli(capsys) -> None:
    from dhf.cli import report_drafting_failures
    from dhf.llm.errors import DraftingUnavailable, provider_error

    class UnsafeSDKError(Exception):
        status_code = 401
        request_id = "req-test"

    error = provider_error(UnsafeSDKError("invalid_api_key sk-sensitive-secret-fragment"), "openai")
    assert isinstance(error, DraftingUnavailable)
    report_drafting_failures([{"id": "purpose_scope", "ai_unavailable": error.details}])
    output = capsys.readouterr().out
    assert "openai" in output and "http=401" in output and "request=req-test" in output
    assert "sk-sensitive" not in output and "Traceback" not in output


@pytest.mark.parametrize("provider,cap", [("openai", 4.00), ("anthropic", 2.50)])
def test_owner_hard_cap_counts_actual_and_outstanding_even_with_legacy_config(
    tmp_path, monkeypatch, provider, cap
):
    from dhf.llm.adapters.mock import MockAdapter

    monkeypatch.setenv("DHF_PROVIDER_BUDGET_USD", "5")
    monkeypatch.setenv("DHF_HARD_CAP_USD", "5")
    monkeypatch.setenv("DHF_OPENAI_INPUT_PER_MILLION", "1")
    monkeypatch.setenv("DHF_OPENAI_OUTPUT_PER_MILLION", "1")
    path = tmp_path / "ledger.json"
    tmp_path.mkdir(exist_ok=True)
    path.write_text(json.dumps({provider: {"actual_usd": cap - 0.10, "reserved_usd": 0.0999}}))
    llm = LLM(provider, tmp_path, MockAdapter(), run_cap=10, build_cap=10, total_cap=10)
    assert llm.hard_cap == cap
    with pytest.raises(BudgetExceeded):
        llm.generate("cap", 1, "p", PACK, 1000)
    assert llm.calls == 0
    from typer.testing import CliRunner

    from dhf.cli import report_budget

    assert llm.budget_status()["remaining_usd"] == pytest.approx(0.0001)
    import typer

    cli = typer.Typer()
    cli.command()(lambda: report_budget(llm))
    output = CliRunner().invoke(cli).output
    assert f"cumulative headroom: $0.000100 of ${cap:.2f} hard cap" in output
    assert json.loads(path.read_text())[provider]["actual_usd"] == cap - 0.10


def test_openai_gpt5_parameters_and_inclusive_usage(monkeypatch):
    from types import SimpleNamespace as NS

    import dhf.llm.adapters.openai as oa

    monkeypatch.setenv("OPENAI_API_KEY", "fake-not-a-real-key")
    captured = []

    def create(**kwargs):
        captured.append(kwargs)
        return NS(
            choices=[NS(finish_reason="stop", message=NS(refusal=None, content='{"claims":[]}'))],
            usage=NS(prompt_tokens=20, completion_tokens=150),
        )

    monkeypatch.setattr(oa, "OpenAI", lambda **_: NS(chat=NS(completions=NS(create=create))))
    result = oa.OpenAIAdapter().complete("gpt-5.4-mini", "p", PACK, 8000)
    assert "temperature" not in captured[0]
    assert captured[0]["reasoning_effort"] == "low"
    assert captured[0]["max_completion_tokens"] == 8000
    assert result["_usage"]["output_tokens"] == 150
    oa.OpenAIAdapter().complete("gpt-4.1-mini", "p", PACK, 4000)
    assert captured[1]["temperature"] == 0 and "reasoning_effort" not in captured[1]


def test_model_tiers_prices_reasoning_reservation_and_cache(tmp_path, monkeypatch):
    from dhf.llm.adapters.mock import MockAdapter

    seen = []

    class CaptureAdapter(MockAdapter):
        def complete(self, model, prompt, pack, limit):
            seen.append((model, limit))
            return {"claims": []}

    llm = LLM("openai", tmp_path, CaptureAdapter())
    llm.generate("tier", 1, "p", PACK, 4000)
    llm.generate("tier", 1, "p", PACK, 4000, model_tier="analytical")
    assert seen == [("gpt-4.1-mini", 4000), ("gpt-5.4-mini", 8000)]
    assert llm.prices("gpt-5.4-mini") == (0.75, 4.50)
    assert llm.prices("gpt-5.5") == (5.00, 30.00)
    # Reasoning allowance alone reserves at least 4000 * $4.50 / 1M.
    assert json.loads((tmp_path / "ledger.json").read_text())["openai"]["reserved_usd"] > 0.036
    llm.generate("tier", 1, "p", PACK, 4000, model_tier="analytical")
    assert llm.hits == 1 and len(seen) == 2
    monkeypatch.setenv("DHF_OPENAI_REASONING_EFFORT", "medium")
    llm.generate("tier", 1, "p", PACK, 4000, model_tier="analytical")
    assert len(seen) == 3
    monkeypatch.setenv("DHF_MODEL_OPENAI_ANALYTICAL", "gpt-5.4-nano")
    with pytest.raises(ValueError, match="Nano"):
        llm.generate("tier", 1, "p", PACK, model_tier="analytical")
