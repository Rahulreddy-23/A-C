import copy
from pathlib import Path

import yaml
from mock_ado.state import apply_scenario, merge_docs_pr
from typer.testing import CliRunner

from dhf.cli import app
from dhf.generate import generate_document
from dhf.graph import Store
from dhf.impact import impact, read_sections, regenerate
from dhf.ingest.ado import ADO, git_command
from dhf.llm import LLM
from dhf.trace.consistency import consistency, legacy_design


def test_watch_selective_regeneration_preserves_human_edits(ado_server, tmp_path, monkeypatch):
    monkeypatch.setenv("ADO_BASE_URL", f"http://127.0.0.1:{ado_server.server_port}/kestrel-org")
    monkeypatch.setenv("APP_ADO_PAT", "mock-app-token")
    ado = ADO()
    root = tmp_path / "docs"
    store = Store(tmp_path / "evidence.sqlite")
    llm = LLM(root=tmp_path / "llm")
    try:
        before = ado.ingest(tmp_path / "clones")
        store.ingest(before)
        baseline = {
            doc: generate_document(doc, before, {"release": "1.1"}, out=root, llm=llm)
            for doc in ("sad", "sdd", "sstr", "sfmea")
        }
        sstr = baseline["sstr"]
        sstr["markdown"] = sstr["markdown"].replace(
            "[Human input required", "Owner draft retained. [Human input required"
        )
        # Test tooling simulates owner-reviewed baselines, never product auto-approval.
        from test_review import resolved_markdown

        from dhf.review import DocsReview

        for doc, result in baseline.items():
            review = DocsReview(ado)
            published = review.publish(result)
            result["markdown"] = resolved_markdown(result)
            (review.root / (doc + ".md")).write_text(result["markdown"])
            git_command(["add", doc + ".md"], review.root)
            git_command(
                [
                    "-c",
                    "user.name=Synthetic Owner",
                    "-c",
                    "user.email=owner@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "Human: review fixture",
                ],
                review.root,
            )
            git_command(["push", "origin", "HEAD"], review.root, ado.token)
            assert review.check_pr(doc, published["pr_id"])["ready"]
            merge_docs_pr(published["pr_id"], ado_server.root)
            review.create_baseline(doc, published["pr_id"])
            (root / (doc + ".md")).write_text(result["markdown"])
        import time

        real_sleep = time.sleep
        applied: list[dict] = []

        def between_cycles(seconds: float) -> None:
            # Apply the source change exactly between watch cycles (no timing race).
            if applied:
                real_sleep(seconds)
            else:
                applied.append(apply_scenario("change_1", ado_server.root))

        monkeypatch.setattr(time, "sleep", between_cycles)
        run = CliRunner().invoke(
            app,
            [
                "watch",
                "--cycles",
                "2",
                "--interval",
                "3",
                "--db",
                str(tmp_path / "evidence.sqlite"),
                "--documents",
                str(root),
            ],
        )
        assert applied and run.exit_code == 0, run.output
        assert "2 changed, 3 added" in run.output
        graph = store.graph()
        expected = yaml.safe_load(Path("data/synthetic/scenarios/change_1.yaml").read_text())[
            "expected_sections"
        ]
        for doc, original in baseline.items():
            report = impact(graph, original["manifest"], before)
            actual = {
                s["id"]: {
                    "status": s["status"],
                    "artifacts": sorted({c["artifact"] for c in s["causes"] if c["artifact"]}),
                }
                for s in report["sections"]
            }
            assert actual == expected[doc]
            new = regenerate(graph, original["manifest"], original["markdown"], report, root, llm)
            old_text = read_sections(original["markdown"])
            stale = {s["id"] for s in report["sections"] if s["status"] == "stale"}
            assert new["manifest"]["changed_sections"] == sorted(stale)
            for s in new["manifest"]["sections"]:
                if s["id"] not in stale:
                    assert s["markdown"] == old_text[s["id"]]
                assert s["status"] != "ai_unavailable"
            if doc == "sstr":
                assert "Owner draft retained." in new["markdown"]
            review = __import__("dhf.review", fromlist=["DocsReview"]).DocsReview(ado)
            published = review.publish(new, changed_sections=sorted(stale))
            assert published["pr_id"] >= 9
            main = git_command(["show", "origin/main:" + doc + ".md"], review.root)
            for id, text in read_sections(main + "\n").items():
                if id not in stale:
                    assert read_sections(new["markdown"])[id] == text
            assert new["manifest"]["changed_sections"] == sorted(stale)
        assert (
            consistency(
                graph,
                [__import__("json").loads(p.read_text()) for p in root.glob("*.manifest.json")],
            )
            == []
        )
    finally:
        ado.close()
        store.close()


def test_consistency_all_rules(tmp_path):
    from dhf.ingest.fixtures import ingest_fixtures

    graph = ingest_fixtures()
    doc = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path / "llm")
    )["manifest"]
    broken = copy.deepcopy(doc)
    broken["sections"][0]["cited_revisions"]["SRS-999"] = "1"
    broken["sections"][1]["cited_revisions"]["SRS-021"] = "0"
    next(s for s in broken["sections"] if s["id"] == "results_summary")["facts"]["summary"][
        "passed"
    ] = 0
    assert {f["rule"] for f in consistency(graph, [broken])} == {"C02", "C03"}
    legacy = legacy_design(Path("data/synthetic/sad_v1.md").read_text())
    findings = consistency(graph, [legacy])
    assert {f["rule"] for f in findings} == {"C01", "C04"}
    assert next(f for f in findings if f["rule"] == "C01")["missing"] == ["COMP-06"]
    assert next(f for f in findings if f["rule"] == "C04")["artifact"] == "COMP-03"
    broken["sections"][0]["evidence_status"] = "stale"
    from dhf.review import readiness

    assert any(
        b["reason"] == "stale"
        for b in readiness(doc["sections"][0]["markdown"], broken)["blockers"]
    )
