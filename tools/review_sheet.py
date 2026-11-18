"""Human check of gap findings: make a sheet to mark, then score it.

Usage:
  uv run python tools/review_sheet.py make  [--dir out/real]   gaps.json -> findings_review.csv
  uv run python tools/review_sheet.py score [--dir out/real]   findings_review.csv -> score

Mark the verdict column TRUE, FALSE ALARM or UNSURE in Excel and save as CSV.
`make` keeps verdicts already entered, so it is safe to rerun after a new ingest.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from dhf.trace.reports import gap_rules

COLUMNS = [
    "no",
    "rule",
    "rule_title",
    "item_id",
    "finding",
    "suggested_action",
    "source_link",
    "verdict",
    "reviewer",
    "notes",
]
VERDICTS = ("TRUE", "FALSE ALARM", "UNSURE")
HUMAN = ("verdict", "reviewer", "notes")


def read_sheet(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make(root: Path) -> None:
    source = root / "gaps.json"
    if not source.exists():
        sys.exit(f"{source} not found; run: uv run dhf gaps --output-dir {root}")
    findings = json.loads(source.read_text(encoding="utf-8"))["findings"]
    titles = {rule["id"]: rule["title"] for rule in gap_rules()}
    sheet = root / "findings_review.csv"
    kept = {(row["rule"], row["item_id"]): row for row in read_sheet(sheet)}
    rows = []
    for number, finding in enumerate(findings, 1):
        old = kept.get((finding["rule"], finding["artifact_id"]), {})
        rows.append(
            {
                "no": number,
                "rule": finding["rule"],
                "rule_title": titles.get(finding["rule"], ""),
                "item_id": finding["artifact_id"],
                "finding": finding["message"],
                "suggested_action": finding.get("action", ""),
                "source_link": finding.get("source_url", ""),
                **{name: old.get(name, "") for name in HUMAN},
            }
        )
    # utf-8-sig lets Excel open the file with the right characters.
    with sheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    marked = sum(1 for row in rows if row["verdict"])
    print(f"{len(rows)} findings -> {sheet} ({marked} already marked)")


def score(root: Path) -> None:
    rows = read_sheet(root / "findings_review.csv")
    if not rows:
        sys.exit("No review sheet yet; run the make step first")
    bad = [r["no"] for r in rows if r["verdict"] and r["verdict"].strip().upper() not in VERDICTS]
    if bad:
        sys.exit(f"Rows {', '.join(bad)} have a verdict other than {', '.join(VERDICTS)}")
    by_rule: dict[str, Counter] = {}
    for row in rows:
        verdict = row["verdict"].strip().upper() or "NOT CHECKED"
        by_rule.setdefault(row["rule"] + " " + row["rule_title"], Counter())[verdict] += 1
    total = sum(by_rule.values(), Counter())
    lines = [
        "# Findings check",
        "",
        "| Rule | Checked | True | False alarm | Unsure | Correct |",
        "|---|---|---|---|---|---|",
    ]
    for rule, counts in sorted(by_rule.items()) + [("**All rules**", total)]:
        true, false = counts["TRUE"], counts["FALSE ALARM"]
        checked = true + false + counts["UNSURE"]
        correct = f"{true / (true + false):.0%}" if true + false else "-"
        lines.append(f"| {rule} | {checked} | {true} | {false} | {counts['UNSURE']} | {correct} |")
    lines += [
        "",
        f"{total['NOT CHECKED']} of {len(rows)} findings not checked yet.",
        "Correct = true / (true + false alarm); unsure findings are left out.",
    ]
    report = root / "findings_score.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"\n-> {report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Human check of gap findings")
    parser.add_argument("action", choices=("make", "score"))
    parser.add_argument("--dir", default="out/real")
    options = parser.parse_args()
    (make if options.action == "make" else score)(Path(options.dir))
