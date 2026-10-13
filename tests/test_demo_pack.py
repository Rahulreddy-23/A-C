import json
from pathlib import Path
from runpy import run_path

import pytest

DEMO = run_path("tools/demo.py")


def test_live_demo_shared_ledger_budget_and_offline_isolation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "run"
    root.mkdir()
    offline = DEMO["demo_configuration"](root, False)
    assert offline["provider"] == "mock" and offline["environment"]["DHF_CACHE_ROOT"] != "out"
    assert Path(offline["environment"]["DHF_ENV_FILE"]).read_text() == ""
    with pytest.raises(ValueError, match="configured provider key"):
        DEMO["demo_configuration"](root, True)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-never-called")
    monkeypatch.setenv("DHF_MAX_USD_PER_RUN", "9")
    Path("out").mkdir()
    Path("out/ledger.json").write_text(
        json.dumps({"openai": {"actual_usd": 0.63, "reserved_usd": 0.02}})
    )
    live = DEMO["demo_configuration"](root, True)
    assert "DHF_ENV_FILE" not in live["environment"]
    assert live["environment"]["DHF_CACHE_ROOT"] == "out" and live["provider"] == "openai"
    assert live["run_cap"] == 0.25 and live["starting_spend"] == 0.65
    Path("out/ledger.json").write_text(
        json.dumps({"openai": {"actual_usd": 0.73, "reserved_usd": 0.07}})
    )
    assert DEMO["remaining_run_cap"](live) == pytest.approx(0.10)
    Path("out/ledger.json").write_text(json.dumps({"openai": {"actual_usd": 1}}))
    assert DEMO["remaining_run_cap"](live) == 0


def test_demo_evidence_links_hashes_redline_and_audit():
    result = run_path("tools/check_demo_pack.py")["check_demo_pack"]()
    assert result["audit_verified_files"] == 33
    assert result["tracked_redline"] == "pass"
