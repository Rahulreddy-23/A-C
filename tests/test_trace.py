from pathlib import Path

import yaml

from dhf.ingest.fixtures import ingest_fixtures
from dhf.trace import coverage, gaps, results_summary, rtm, score_findings


def test_all_gap_rules_exact_answer_key() -> None:
    data = ingest_fixtures()
    expected = yaml.safe_load(Path("data/synthetic/expected_gaps.yaml").read_text(encoding="utf-8"))
    assert score_findings(gaps(data), expected) == {
        "precision": 1.0,
        "recall": 1.0,
        "true_positive": 21,
        "false_positive": 0,
        "false_negative": 0,
    }


def test_rtm_matches_hand_checked_rows() -> None:
    rows = {r["requirement"]: r for r in rtm(ingest_fixtures())}
    golden = yaml.safe_load(Path("eval/golden/rtm_hand_checked.yaml").read_text(encoding="utf-8"))
    for id, expected in golden.items():
        assert {
            **{k: rows[id][k] for k in ("components", "changes", "tests")},
            "outcomes": [r["outcome"] for r in rows[id]["results"]],
        } == expected
    assert len(rows) == 35


def test_counts_latest_results_and_inferred_links_do_not_count() -> None:
    graph = ingest_fixtures()
    assert results_summary(graph, "1.0") == {
        "release": "1.0",
        "total": 40,
        "passed": 38,
        "failed": 2,
        "blocked": 0,
        "not_run": 0,
    }
    assert results_summary(graph, "1.1") == {
        "release": "1.1",
        "total": 40,
        "passed": 39,
        "failed": 1,
        "blocked": 0,
        "not_run": 0,
    }
    assert coverage(graph)["srs_to_test"] == {"covered": 31, "total": 35, "percent": 88.57}
    graph["links"].append(
        {
            "src": "TC-040",
            "dst": "SRS-035",
            "type": "verifies",
            "origin": "ai_inferred",
            "confidence": 0.9,
            "evidence": "proposal",
        }
    )
    assert coverage(graph)["srs_to_test"]["covered"] == 31
    assert any(f["rule"] == "G01" and f["artifact_id"] == "SRS-035" for f in gaps(graph))
