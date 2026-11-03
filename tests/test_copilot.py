"""Offline contract tests for the BD-tenant model transport."""

import json
import threading
import time
from pathlib import Path

import httpx
import pytest

from dhf.generate import expand_sections, generate_document, generate_section, load_spec
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM, BudgetExceeded
from dhf.llm.adapters.copilotstudio import CopilotStudioAdapter
from dhf.llm.errors import DraftingUnavailable

PACK = {
    "facts": {"passed": 39},
    "evidence": [{"id": "SRS-021", "body": "Occlusion", "attributes": {"synthetic": True}}],
    "max_claims": 2,
}


def reply(request: dict, *, claims: list | None = None, **changes: object) -> dict:
    return {
        "request_id": request["request_id"],
        "claims_json": json.dumps({"claims": [] if claims is None else claims}),
        "model": "BD GPT Basic",
        "input_tokens": 150,
        "output_tokens": 40,
        **changes,
    }


def test_http_request_cache_ledger_preview_and_secret_redaction(tmp_path, monkeypatch):
    secret = "https://example.invalid/flow?sig=SECRET-NEVER-LOG"
    monkeypatch.setenv("DHF_COPILOT_MODE", "http")
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", secret)
    seen = []

    def endpoint(request: httpx.Request) -> httpx.Response:
        assert request.url == secret
        payload = json.loads(request.content)
        seen.append(payload)
        return httpx.Response(200, json=reply(payload))

    adapter = CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(endpoint)))
    llm = LLM("copilotstudio", tmp_path, adapter)
    preview = llm.copilot_request("test", 1, "Write claims", PACK, 100)
    assert set(preview) == {
        "request_id",
        "prompt_id",
        "prompt_version",
        "instructions",
        "facts_json",
        "evidence_json",
        "output_schema_json",
        "max_claims",
    }
    assert llm.generate("test", 1, "Write claims", PACK, 100) == {"claims": []}
    assert seen == [preview]
    assert llm.last_model == "BD GPT Basic"
    assert llm.generate("test", 1, "Write claims", PACK, 100) == {"claims": []}
    assert (llm.calls, llm.hits) == (1, 1)
    status = llm.budget_status()
    assert status["actual_credits"] == pytest.approx(0.019)
    assert status["reserved_credits"] == pytest.approx(0)
    assert secret not in json.dumps(status)
    assert secret not in (tmp_path / "ledger.json").read_text()


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        ({"status": "refused"}, "refusal"),
        ({"claims_json": ""}, "empty_output"),
        ({"claims_json": "{"}, "unparseable"),
        ({"input_tokens": None}, "invalid_usage"),
        ({"request_id": "wrong"}, "request_id_mismatch"),
    ],
)
def test_http_failures_are_distinct_and_reservations_remain(tmp_path, monkeypatch, patch, reason):
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/signed?sig=SECRET")
    adapter = CopilotStudioAdapter(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json=reply(json.loads(request.content), **patch)
                )
            )
        )
    )
    llm = LLM("copilotstudio", tmp_path, adapter)
    with pytest.raises(DraftingUnavailable) as error:
        llm.generate("test", 1, "Write claims", PACK, 100)
    assert error.value.details["reason"] == reason
    assert "SECRET" not in str(error.value)
    assert llm.budget_status()["reserved_credits"] > 0


def test_http_transport_error_redacts_signed_url(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/signed?sig=SECRET")

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("SECRET", request=request)

    llm = LLM(
        "copilotstudio",
        tmp_path,
        CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(fail))),
    )
    with pytest.raises(DraftingUnavailable) as error:
        llm.generate("test", 1, "Write claims", PACK, 100)
    assert error.value.details["reason"] == "provider_error"
    assert "SECRET" not in str(error.value.details)


@pytest.mark.parametrize("mode", ["reported", "estimated"])
def test_copilot_cap_exhaustion_prevents_transport(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("DHF_COPILOT_USAGE", mode)
    monkeypatch.setenv("DHF_COPILOT_CREDIT_CAP", "0.001")
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/flow")
    sent = []
    adapter = CopilotStudioAdapter(
        httpx.Client(transport=httpx.MockTransport(lambda request: sent.append(request)))
    )
    llm = LLM("copilotstudio", tmp_path, adapter)
    with pytest.raises(BudgetExceeded):
        llm.generate("test", 1, "Write claims", PACK, 100)
    assert not sent
    assert not (tmp_path / "ledger.json").exists()


def test_basic_tier_and_owner_credit_ceiling_cannot_be_raised(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_MODEL_COPILOTSTUDIO", "Approved Basic")
    monkeypatch.setenv("DHF_MODEL_COPILOTSTUDIO_ANALYTICAL", "Unapproved Premium")
    monkeypatch.setenv("DHF_COPILOT_CREDIT_CAP", "999")
    llm = LLM("copilotstudio", tmp_path)
    assert llm.model_for("analytical") == "Approved Basic"
    assert llm.budget_status()["hard_cap_credits"] == 400


@pytest.mark.parametrize("mode", ["reported", "estimated"])
def test_folder_document_is_one_file_with_section_failures(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("DHF_COPILOT_USAGE", mode)
    exchange = tmp_path / "exchange"
    monkeypatch.setenv("DHF_COPILOT_MODE", "folder")
    monkeypatch.setenv("DHF_COPILOT_EXCHANGE_DIR", str(exchange))
    monkeypatch.setenv("DHF_COPILOT_TIMEOUT_S", "4")
    seen = []

    def flow() -> None:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            requests = (
                list((exchange / "requests").glob("*.json"))
                if (exchange / "requests").exists()
                else []
            )
            if requests:
                batch = json.loads(requests[0].read_text())
                seen.append(batch)
                rows = [reply(item) for item in batch["sections"]]
                rows[0] = reply(batch["sections"][0], status="refused")
                if mode == "estimated":
                    for row in rows:
                        row.pop("input_tokens")
                        row.pop("output_tokens")
                responses = exchange / "responses"
                responses.mkdir(exist_ok=True)
                (responses / requests[0].name).write_text(
                    json.dumps(
                        {
                            "request_id": batch["request_id"],
                            "document_id": batch["document_id"],
                            "sections": rows,
                        }
                    )
                )
                return
            time.sleep(0.01)

    thread = threading.Thread(target=flow)
    thread.start()
    graph = ingest_fixtures()
    llm = LLM("copilotstudio", tmp_path / "llm")
    result = generate_document("sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=llm)
    thread.join(timeout=4)
    assert len(seen) == 1
    assert seen[0]["document_id"] == "sstr"
    assert len(seen[0]["sections"]) > 1
    assert len(list((exchange / "requests").glob("*.json"))) == 1
    sections = result["manifest"]["sections"]
    assert any(item["status"] == "ai_unavailable" for item in sections)
    assert any(item["model"]["name"] == "BD GPT Basic" for item in sections)
    assert result["manifest"]["model"]["provider"] == "copilotstudio"
    assert result["manifest"]["model"]["tier"] == "basic"
    assert result["manifest"]["copilot_credits"] > 0
    assert result["manifest"]["usage_source"] == mode
    assert llm.budget_status()["usage_source"] == mode
    assert all(
        s["usage_source"] == mode
        for s in sections
        if s["mode"] == "ai" and s["status"] != "ai_unavailable"
    )
    assert result["manifest"]["telemetry"]["cache_hits"] == 0
    assert result["manifest"]["telemetry"]["calls"] == len(seen[0]["sections"])
    assert "Human input required" in result["markdown"]
    successful = next(s for s in sections if s["mode"] == "ai" and s["status"] != "ai_unavailable")
    definition = next(
        s for s in expand_sections(load_spec("sstr"), graph) if s["id"] == successful["id"]
    )
    calls = llm.calls
    cached = generate_section(definition, graph, {"release": "1.1"}, llm)
    assert cached["usage_source"] == mode
    assert llm.calls == calls


def test_folder_timeout_is_sanitized(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_MODE", "folder")
    monkeypatch.setenv("DHF_COPILOT_EXCHANGE_DIR", str(tmp_path / "exchange"))
    monkeypatch.setenv("DHF_COPILOT_TIMEOUT_S", "0.01")
    llm = LLM("copilotstudio", tmp_path / "llm")
    with pytest.raises(DraftingUnavailable) as error:
        llm.generate("test", 1, "Write claims", PACK, 100)
    assert error.value.details["reason"] == "timeout"


def test_folder_document_timeout_keeps_deterministic_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_MODE", "folder")
    monkeypatch.setenv("DHF_COPILOT_EXCHANGE_DIR", str(tmp_path / "exchange"))
    monkeypatch.setenv("DHF_COPILOT_TIMEOUT_S", "0.01")
    result = generate_document(
        "sstr",
        ingest_fixtures(),
        {"release": "1.1"},
        out=tmp_path / "docs",
        llm=LLM("copilotstudio", tmp_path / "llm"),
    )
    sections = result["manifest"]["sections"]
    assert any(s["mode"] == "deterministic" and s["status"] == "draft" for s in sections)
    assert all(s["ai_unavailable"]["reason"] == "timeout" for s in sections if s["mode"] == "ai")
    assert len(list((tmp_path / "exchange/requests").glob("*.json"))) == 1


def test_copilot_claims_still_use_reference_validator(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/flow")
    graph = ingest_fixtures()
    section = next(
        item
        for item in expand_sections(load_spec("sstr"), graph)
        if item["id"] == "anomaly_assessment"
    )

    def endpoint(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json=reply(
                payload,
                claims=[
                    {
                        "text": "Invented SRS-999",
                        "kind": "sourced",
                        "citations": ["SRS-999"],
                        "confidence": None,
                    }
                ],
            ),
        )

    llm = LLM(
        "copilotstudio",
        tmp_path,
        CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(endpoint))),
    )
    rendered = generate_section(section, graph, {"release": "1.1"}, llm)
    assert rendered["validation"]["rejected"]
    assert rendered["claims"] == []
    assert rendered["model"]["name"] == "BD GPT Basic"


def test_preview_rejects_non_synthetic(tmp_path):
    llm = LLM("copilotstudio", tmp_path)
    with pytest.raises(ValueError, match="synthetic"):
        llm.copilot_request("test", 1, "Write", {"facts": {}, "evidence": [{"id": "X"}]})


def test_day1_sample_is_exact_preview_and_passes_reference_validator(tmp_path):
    from dhf.generate import prepare_ai, section_pack
    from dhf.generate.validator import validate_claims

    graph = ingest_fixtures()
    section = next(
        item
        for item in expand_sections(load_spec("sstr"), graph)
        if item["id"] == "anomaly_assessment"
    )
    prompt, chunks, _ = prepare_ai(section, section_pack(section, graph, {"release": "1.1"}))
    request = LLM("copilotstudio", tmp_path).copilot_request(
        prompt["id"],
        prompt["version"],
        prompt["body"],
        chunks[0],
        prompt["max_output_tokens"],
    )
    root = Path("tests/fixtures")
    assert request == json.loads((root / "copilot_request.json").read_text())
    response = json.loads((root / "copilot_response.json").read_text())
    assert response["request_id"] == request["request_id"]
    claims = json.loads(response["claims_json"])
    validated = validate_claims(claims, chunks[0], section["allowed_kinds"])
    assert len(validated["claims"]) == 2
    assert not validated["validation"]["rejected"]


def test_copilot_request_cli_is_read_only(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from dhf.cli import app
    from dhf.graph import Store

    db = tmp_path / "evidence.sqlite"
    monkeypatch.setenv("DHF_CACHE_ROOT", str(tmp_path / "llm"))
    store = Store(db)
    try:
        store.ingest(ingest_fixtures())
    finally:
        store.close()
    output = CliRunner().invoke(
        app, ["copilot-request", "sstr", "anomaly_assessment", "--db", str(db)]
    )
    assert output.exit_code == 0, output.output
    assert json.loads(output.output) == json.loads(
        Path("tests/fixtures/copilot_request.json").read_text()
    )
    assert not (tmp_path / "llm/ledger.json").exists()


@pytest.mark.parametrize("mode", ["reported", "estimated"])
@pytest.mark.parametrize("available", [True, False])
def test_http_usage_mode_provenance_and_cache(tmp_path, monkeypatch, mode, available):
    monkeypatch.setenv("DHF_COPILOT_USAGE", mode)
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/flow?sig=SECRET")
    requests = []
    claims_json = json.dumps({"claims": []})

    def endpoint(request):
        payload = json.loads(request.content)
        requests.append(payload)
        response = reply(payload)
        if not available:
            response.pop("input_tokens")
            response.pop("output_tokens")
        return httpx.Response(200, json=response)

    adapter = CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(endpoint)))
    llm = LLM("copilotstudio", tmp_path, adapter)
    if mode == "reported" and not available:
        with pytest.raises(DraftingUnavailable) as error:
            llm.generate("test", 1, "Write café claims", PACK, 100)
        assert error.value.details["reason"] == "invalid_usage"
        assert llm.budget_status()["reserved_credits"] > 0
        assert not list(llm.cache.glob("*.json"))
        return
    assert llm.generate("test", 1, "Write café claims", PACK, 100) == {"claims": []}
    source = "reported" if available else "estimated"
    expected_input = (
        150 if available else (len("".join(str(v) for v in requests[0].values()).encode()) + 2) // 3
    )
    expected_output = 40 if available else (len(claims_json.encode()) + 2) // 3
    entry = json.loads((tmp_path / "ledger.json").read_text())["copilotstudio"]
    assert entry["input_tokens"] == expected_input
    assert entry["output_tokens"] == expected_output
    assert entry["actual_credits"] == pytest.approx((expected_input + expected_output) * 0.1 / 1000)
    assert entry["usage_source"] == source
    assert entry["credits_by_usage_source"] == {source: entry["actual_credits"]}
    assert llm.last_usage_source == source
    # Cache provenance survives a new process and switching the configured mode.
    monkeypatch.setenv("DHF_COPILOT_USAGE", "reported")
    cached = LLM("copilotstudio", tmp_path, adapter)
    before = (tmp_path / "ledger.json").read_text()
    assert cached.generate("test", 1, "Write café claims", PACK, 100) == {"claims": []}
    assert cached.last_usage_source == source
    assert (cached.calls, cached.hits) == (0, 1)
    assert len(requests) == 1
    assert (tmp_path / "ledger.json").read_text() == before
    assert "SECRET" not in before


@pytest.mark.parametrize("bad", [True, -1, "150", 1.5])
def test_estimated_mode_rejects_supplied_corrupt_counts(tmp_path, monkeypatch, bad):
    monkeypatch.setenv("DHF_COPILOT_USAGE", "estimated")
    request = LLM("copilotstudio", tmp_path).copilot_request("test", 1, "Write", PACK)
    with pytest.raises(DraftingUnavailable) as error:
        CopilotStudioAdapter._parse(
            reply(request, input_tokens=bad), request["request_id"], request
        )
    assert error.value.details["reason"] == "invalid_usage"


def test_estimated_partial_usage_and_mixed_cumulative_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_USAGE", "estimated")
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/flow")
    count = 0

    def endpoint(request):
        nonlocal count
        count += 1
        payload = json.loads(request.content)
        return httpx.Response(
            200, json=reply(payload, **({"output_tokens": None} if count == 2 else {}))
        )

    llm = LLM(
        "copilotstudio",
        tmp_path,
        CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(endpoint))),
    )
    llm.generate("test", 1, "Reported", PACK, 100)
    legacy = json.loads((tmp_path / "ledger.json").read_text())
    legacy["copilotstudio"].pop("usage_source")
    legacy["copilotstudio"].pop("credits_by_usage_source")
    (tmp_path / "ledger.json").write_text(json.dumps(legacy))
    llm.generate("test", 1, "Estimated", PACK, 100)
    entry = json.loads((tmp_path / "ledger.json").read_text())["copilotstudio"]
    assert entry["usage_source"] == "mixed"
    assert entry["credits_by_usage_source"]["reported"] == pytest.approx(0.019)
    assert entry["credits_by_usage_source"]["estimated"] > 0
    assert sum(entry["credits_by_usage_source"].values()) == pytest.approx(entry["actual_credits"])
    assert entry["reserved_credits"] == pytest.approx(0)


@pytest.mark.parametrize("mode", ["reported", "estimated", "mixed"])
def test_usage_in_document_regeneration_and_metrics(tmp_path, monkeypatch, mode):
    from dhf.evaluation import evaluate, metrics_markdown
    from dhf.impact import regenerate

    monkeypatch.setenv("DHF_COPILOT_USAGE", "estimated" if mode == "mixed" else mode)
    monkeypatch.setenv("DHF_COPILOT_FLOW_URL", "https://example.invalid/flow")

    request_count = 0

    def endpoint(request):
        nonlocal request_count
        request_count += 1
        response = reply(json.loads(request.content))
        if mode == "estimated" or (mode == "mixed" and request_count % 2 == 0):
            response.pop("input_tokens")
            response.pop("output_tokens")
        return httpx.Response(200, json=response)

    graph = ingest_fixtures()
    llm = LLM(
        "copilotstudio",
        tmp_path / "llm",
        CopilotStudioAdapter(httpx.Client(transport=httpx.MockTransport(endpoint))),
    )
    result = generate_document("sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=llm)
    manifest = result["manifest"]
    assert manifest["usage_source"] == mode
    assert manifest["llm_cost_usd"] == 0
    assert not any(s["status"] == "ai_unavailable" for s in manifest["sections"])
    metrics = evaluate(graph, graph, [manifest], {"sstr": result["markdown"]})
    measured = metrics["documents"][0]
    assert measured["usage_source"] == mode
    assert measured["copilot_credits"] == manifest["copilot_credits"] > 0
    markdown = metrics_markdown(metrics)
    assert "Copilot estimated credits" in markdown and "tenant Monitor" in markdown
    assert f"| {mode} |" in markdown
    # A free cached regeneration must not retain the prior run's credits or bill USD.
    section = next(s["id"] for s in manifest["sections"] if s["mode"] == "ai")
    regenerated = regenerate(
        graph,
        manifest,
        result["markdown"],
        {"sections": [{"id": section, "status": "stale", "causes": []}]},
        tmp_path / "regen",
        llm,
    )
    assert regenerated["manifest"]["usage_source"] == mode
    assert regenerated["manifest"]["copilot_credits"] == pytest.approx(0)
    assert regenerated["manifest"]["llm_cost_usd"] == 0


def test_invalid_usage_mode_prevents_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_COPILOT_USAGE", "invented")
    with pytest.raises(ValueError, match="DHF_COPILOT_USAGE"):
        LLM("copilotstudio", tmp_path)
    assert not (tmp_path / "ledger.json").exists()
