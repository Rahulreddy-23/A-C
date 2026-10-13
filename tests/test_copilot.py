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


def test_copilot_cap_exhaustion_prevents_transport(tmp_path, monkeypatch):
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


def test_folder_document_is_one_file_with_section_failures(tmp_path, monkeypatch):
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
    assert result["manifest"]["telemetry"]["cache_hits"] == 0
    assert result["manifest"]["telemetry"]["calls"] == len(seen[0]["sections"])
    assert "Human input required" in result["markdown"]


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
    root = Path("port/copilot_studio/day1/samples")
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
        Path("port/copilot_studio/day1/samples/copilot_request.json").read_text()
    )
    assert not (tmp_path / "llm/ledger.json").exists()
