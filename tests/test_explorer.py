import base64
import json
import re
from pathlib import Path
from zipfile import ZipFile

from dhf.generate import generate_document
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.render.explorer import create_explorer, explorer_payload, render_explorer, trace_chain
from dhf.review.audit import audit_pack
from dhf.trace.consistency import legacy_design


def decode(html: str) -> dict:
    encoded = re.search(r"atob\('([A-Za-z0-9+/=]+)'\)", html)[1]
    return json.loads(base64.b64decode(encoded))


def test_all_nodes_provenance_gap_families_and_inert_offline_html():
    graph = ingest_fixtures()
    historical = legacy_design(Path("data/synthetic/sad_v1.md").read_text())
    payload = decode(create_explorer(graph, [], baselines=[historical]))
    html = render_explorer(payload, Path("specs/render/explorer.html").read_text())
    assert len(payload["nodes"]) == 248 and len(payload["links"]) == 413
    assert all(n["source"]["url"] and n["source"]["revision"] for n in payload["nodes"])
    assert {r[0] for n in payload["nodes"] for r in n["rules"]} == {"G", "C", "F"}
    assert sum(n["latest"] for n in payload["nodes"]) == 40
    assert set(trace_chain(graph, "SRS-021")) == {
        "UN-001",
        "SYS-007",
        "SRS-021",
        "COMP-03",
        "UNIT-sensor_pressure",
        "PR-3",
        "TC-021",
        "RES-2-021",
        "RC-04",
        "HAZ-04",
    }
    assert payload["chains"]["SRS-021"] == trace_chain(graph, "SRS-021")
    assert payload["coverage"]["srs_to_test"] == {
        "covered": 31,
        "total": 35,
        "percent": 88.57,
    }
    assert payload["verification"] == {"Passed": 39, "Failed": 1}
    assert len(payload["risk"]) == 8
    assert {r["id"] for r in payload["rules"]} >= {"G06", "G07", "C01", "F03"}
    assert next(n for n in payload["nodes"] if n["id"] == "SRS-021")["body_excerpt"]
    assert not re.search(
        r"https?://|<(?:script|link)[^>]+(?:src|href)=|fetch\(|XMLHttpRequest|WebSocket", html
    )
    assert "connect-src 'none'" in html and decode(html) == payload
    graph["artifacts"][0]["title"] = '</script><img src="https://example.invalid">'
    html = create_explorer(graph, [])
    assert "example.invalid" not in html and "</script><img" not in html
    assert decode(html)["nodes"][0]["title"].startswith("</script>")


def test_baseline_consistency_is_filterable_in_explorer():
    graph = ingest_fixtures()
    historical = legacy_design(Path("data/synthetic/sad_v1.md").read_text())
    payload = decode(create_explorer(graph, [], baselines=[historical]))
    baseline = [f for f in payload["findings"] if f.get("scope") == "baseline"]
    assert {f["rule"] for f in baseline} == {"C01", "C04"}


def test_saved_change_impact_stale_sections_and_audit_explorer(tmp_path):
    graph = ingest_fixtures()
    result = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=LLM(root=tmp_path / "llm")
    )
    report = [
        {
            "document": "sstr",
            "sections": [
                {
                    "id": "release_conclusion",
                    "status": "stale",
                    "causes": [{"artifact": "SRS-021", "reason": "cited_revision_changed"}],
                }
            ],
        }
    ]
    html = create_explorer(graph, [result["manifest"]], report)
    payload = decode(html)
    document = payload["documents"][0]
    assert document["id"] == "sstr" and document["title"] == "Software System Test Report"
    assert len(document["sections"]) == 12
    assert document["sections"][0]["claims"] == result["manifest"]["sections"][0]["claims"]
    assert (
        document["sections"][0]["cited_revisions"]
        == result["manifest"]["sections"][0]["cited_revisions"]
    )
    assert document["model"]["provider"] == "mock"
    assert payload["impact_reports"] == report
    assert payload["stale_sections"][0]["document"] == "sstr"
    assert next(n for n in payload["nodes"] if n["id"] == "SRS-021")["stale"]
    audit_pack([graph], tmp_path / "docs", tmp_path / "audit.zip", "1.1")
    with ZipFile(tmp_path / "audit.zip") as archive:
        assert len(decode(archive.read("trace/explorer.html").decode())["nodes"]) == 248


def test_payload_uses_injected_presentation_without_file_reads(monkeypatch):
    graph = ingest_fixtures()

    def no_file_reads(*args, **kwargs):
        raise AssertionError("Pure payload step must not read files")

    monkeypatch.setattr(Path, "read_text", no_file_reads)
    presentation = {"rules": [{"id": "G06", "title": "Missing trace", "action": "Review"}]}
    payload = explorer_payload(graph, [], [], presentation=presentation)
    assert payload["rules"] == presentation["rules"]
    assert json.loads(json.dumps(payload)) == payload
