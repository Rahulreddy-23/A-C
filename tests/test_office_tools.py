import csv
import json
from pathlib import Path
from types import SimpleNamespace

from tools import office_check, real_run, review_sheet


def test_ado_only_preflight_works_before_copilot_setup(tmp_path, monkeypatch):
    scope = tmp_path / "scope.yaml"
    scope.write_text("{}", encoding="utf-8", newline="\n")
    monkeypatch.setenv("ADO_BASE_URL", "https://dev.azure.com/example")
    monkeypatch.setenv("ADO_PROJECT", "Synthetic Example")
    monkeypatch.setenv("APP_ADO_PAT", "test-placeholder")
    monkeypatch.setenv("ADO_SCOPE", str(scope))
    monkeypatch.setattr("sys.argv", ["office_check", "--ado-only"])
    assert office_check.main() == 0


def test_office_run_shares_credit_limit_and_forces_read_only(tmp_path, monkeypatch):
    calls = []

    def run(args, env=None):
        if env:
            assert env["ADO_READ_ONLY"] == "1"
        if args[1] == "generate":
            calls.append((args[2], float(env["DHF_COPILOT_CREDITS_PER_RUN"])))
            (tmp_path / f"{args[2]}.manifest.json").write_text(
                json.dumps({"copilot_credits": 3.0}), encoding="utf-8", newline="\n"
            )
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(real_run, "OUT", tmp_path)
    monkeypatch.setattr(real_run.shutil, "which", lambda name: name)
    monkeypatch.setattr(real_run.subprocess, "run", run)
    monkeypatch.setattr(real_run, "DOCS", str(tmp_path))
    monkeypatch.setenv("DHF_CACHE_ROOT", str(tmp_path))
    monkeypatch.setenv("DHF_PROVIDER", "copilotstudio")
    monkeypatch.setenv("DHF_COPILOT_CREDITS_PER_RUN", "5")
    monkeypatch.setenv("ADO_READ_ONLY", "0")
    monkeypatch.setattr("sys.argv", ["real_run", "--docs", "sstr,sad"])
    real_run.main()
    assert calls == [("sstr", 5), ("sad", 2)]


def test_review_sheet_preserves_verdicts_only_for_same_revision(tmp_path):
    gaps = tmp_path / "gaps.json"
    finding = {"rule": "G01", "artifact_id": "SRS-001", "message": "Verification missing"}
    gaps.write_text(
        json.dumps({"findings": [{**finding, "revision": "1"}]}), encoding="utf-8", newline="\n"
    )
    review_sheet.make(tmp_path)
    sheet = tmp_path / "findings_review.csv"
    row = review_sheet.read_sheet(sheet)[0]
    row.update(verdict="TRUE", notes="Checked the test association")
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_sheet.COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    review_sheet.make(tmp_path)
    assert review_sheet.read_sheet(sheet)[0]["verdict"] == "TRUE"

    gaps.write_text(
        json.dumps({"findings": [{**finding, "revision": "2"}]}), encoding="utf-8", newline="\n"
    )
    review_sheet.make(tmp_path)
    assert review_sheet.read_sheet(sheet)[0]["verdict"] == ""
    assert review_sheet.read_sheet(sheet)[0]["notes"] == ""
    gaps.write_text(json.dumps({"findings": []}), encoding="utf-8", newline="\n")
    review_sheet.make(tmp_path)
    review_sheet.score(tmp_path)
    assert "0 of 0 findings" in Path(tmp_path / "findings_score.md").read_text(encoding="utf-8")
