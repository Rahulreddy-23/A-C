"""Freeze an actual synthetic offline rehearsal as checksum-verified demo fallbacks."""

import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile


def freeze_demo(transcript: Path, target: Path = Path("data/demo/fallback")) -> dict:
    run = json.loads(Path("out/demo-latest.json").read_text())
    if run.get("live") or run.get("provider") != "mock":
        raise ValueError("Fallback capture requires an explicitly offline synthetic run")
    root = Path(run["root"])
    target.mkdir(parents=True, exist_ok=True)
    for name in (
        "explorer-baseline.html",
        "explorer-stale.html",
        "explorer.html",
        "redline-sstr.docx",
        "audit-pack.zip",
    ):
        shutil.copyfile(root / name, target / name)
    shutil.copyfile(root / "impact-before-regeneration.json", target / "impact.json")
    shutil.copyfile(transcript, target / "transcript.txt")
    shutil.copyfile("out/metrics.md", target / "metrics.md")
    for name in ("sstr", "sad", "sdd", "sfmea", "drr", "sutr", "rtm"):
        shutil.copyfile(Path(run["documents"]) / (name + ".docx"), target / (name + ".docx"))
    shutil.copyfile(Path(run["documents"]) / "sstr.manifest.json", target / "sstr.manifest.json")
    with ZipFile(root / "audit-pack.zip") as archive:
        for name, dest in (
            ("trace/rtm.md", "rtm.md"),
            ("trace/gaps.md", "gaps.md"),
            ("clause_coverage.md", "clause_coverage.md"),
        ):
            (target / dest).write_bytes(archive.read(name))
    index = {
        "source_run": run,
        "provider": "mock",
        "notice": "Recorded synthetic offline drafts, not a live system or approval",
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(target.iterdir())
            if p.is_file() and p.name not in ("index.json", "README.md")
        },
    }
    (target / "index.json").write_text(json.dumps(index, indent=2))
    return index


if __name__ == "__main__":
    import sys

    print(json.dumps({"files": len(freeze_demo(Path(sys.argv[1]))["files"])}))
