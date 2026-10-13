"""Check committed evidence links, fallback hashes and actual Word redline/audit payloads."""

import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

from dhf.review.audit import verify_audit


def check_demo_pack() -> dict:
    count = 0
    for source in (Path("docs/DEMO_SCRIPT.md"), Path("docs/JUDGING_MAP.md")):
        for link in re.findall(r"\]\(([^)]+)\)", source.read_text()):
            if "://" in link or link.startswith("#"):
                continue
            target = source.parent / link.split("#")[0]
            if not target.is_file():
                raise ValueError(f"Missing evidence link: {source}: {link}")
            count += 1
    root = Path("data/demo/fallback")
    index = json.loads((root / "index.json").read_text())
    for name, digest in index["files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Fallback checksum mismatch: " + name)
    audit = verify_audit(root / "audit-pack.zip")
    with ZipFile(root / "redline-sstr.docx") as archive:
        xml = archive.read("word/document.xml").decode()
        if "<w:ins " not in xml or "<w:del " not in xml:
            raise ValueError("Fallback Word redline missing tracked insertions/deletions")
    return {
        "links": count,
        "fallback_files": len(index["files"]),
        "audit_verified_files": audit["verified_files"],
        "tracked_redline": "pass",
        "tenant_execution": "pending",
    }


if __name__ == "__main__":
    print(json.dumps(check_demo_pack(), indent=2))
