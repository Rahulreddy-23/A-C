"""Run the real-project chain in order on the office laptop; stops at the first failure.

Usage: uv run python tools/real_run.py [--docs sstr,sad,sdd] [--no-ai] [--skip-ingest]

Steps: read-only ADO ingest -> gaps -> RTM -> AI drafts (Copilot Studio) -> explorer
-> findings review sheet. Everything lands in out/real/, which git ignores.
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dhf.config import setting

OUT = Path("out/real")
DB = str(OUT / "evidence.sqlite")
DOCS = str(OUT / "docs")


def step(title: str, args: list[str], **settings: str) -> None:
    print(f"\n=== {title} ===", flush=True)
    dhf = shutil.which("dhf")
    if dhf is None:
        sys.exit("dhf command not found; run this with: uv run python tools/real_run.py")
    env = {**os.environ, **settings, "ADO_READ_ONLY": "1"}
    if subprocess.run([dhf, *args], env=env).returncode != 0:
        sys.exit(f"\nStopped: '{title}' failed. Fix the message above, then run again.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", default="sstr", help="comma-separated: sstr,sad,sdd,rtm")
    parser.add_argument("--no-ai", action="store_true", help="skip AI drafting")
    parser.add_argument("--skip-ingest", action="store_true", help="reuse the last snapshot")
    options = parser.parse_args()
    docs = [doc.strip() for doc in options.docs.split(",") if doc.strip()]
    if not options.no_ai and (
        not docs or any(doc not in ("sstr", "sad", "sdd", "rtm") for doc in docs)
    ):
        parser.error("--docs must list one or more of sstr,sad,sdd,rtm")
    release = setting("DHF_RELEASE", "1.0")
    OUT.mkdir(parents=True, exist_ok=True)

    if not options.skip_ingest:
        step("1. Read ADO (read-only snapshot)", ["ingest", "--source", "ado", "--db", DB])
    step("2. Find gaps", ["gaps", "--db", DB, "--output-dir", str(OUT)])
    step("3. Trace matrix", ["rtm", "--release", release, "--db", DB, "--output-dir", str(OUT)])
    if not options.no_ai:
        if setting("DHF_PROVIDER") != "copilotstudio":
            sys.exit("\nStopped: DHF_PROVIDER must be copilotstudio for company data.")
        try:
            run_cap = float(setting("DHF_COPILOT_CREDITS_PER_RUN", "250"))
        except ValueError:
            run_cap = -1
        if not math.isfinite(run_cap) or run_cap < 0:
            parser.error("DHF_COPILOT_CREDITS_PER_RUN must be finite and nonnegative")

        remaining = run_cap
        for doc in dict.fromkeys(docs):
            step(
                f"4. Draft {doc.upper()} (Copilot Studio)",
                [
                    "generate",
                    doc,
                    "--provider",
                    "copilotstudio",
                    "--release",
                    release,
                    "--db",
                    DB,
                    "--documents",
                    DOCS,
                ],
                DHF_COPILOT_CREDITS_PER_RUN=str(remaining),
            )
            manifest = json.loads((Path(DOCS) / f"{doc}.manifest.json").read_text(encoding="utf-8"))
            remaining = max(0.0, remaining - manifest["copilot_credits"])
    step(
        "5. Evidence explorer",
        ["explore", "--db", DB, "--documents", DOCS, "--output", str(OUT / "explorer.html")],
    )
    print("\n=== 6. Findings review sheet ===", flush=True)
    if subprocess.run([sys.executable, "tools/review_sheet.py", "make"]).returncode != 0:
        sys.exit("Stopped: review sheet failed.")

    print("\nDone. Open these:")
    for name in ("gaps.md", "rtm.md", "explorer.html", "findings_review.csv"):
        print(f"  {OUT / name}")
    if not options.no_ai:
        print(f"  {DOCS}/  (Word drafts + manifests)")


if __name__ == "__main__":
    main()
