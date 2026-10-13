"""Local audit bundles with complete source snapshots and verified payload checksums."""

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from dhf.evaluation import clause_coverage, clause_markdown
from dhf.models.evidence import validate_graph
from dhf.trace import coverage, gaps, rtm
from dhf.trace.reports import gap_rules, gaps_markdown, rtm_markdown


def safe_name(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and "\\" not in name


def audit_payload(
    snapshots: list[dict], files: dict[str, str], documents: list[dict], release: str
) -> dict:
    """JSON-only core: base64 document files + canonical snapshots → checksummed payload."""
    import base64

    if not snapshots or not documents:
        raise ValueError("Audit pack requires documents and evidence snapshots")
    snapshots = [validate_graph(s) for s in snapshots]
    provenance = {
        (a["id"], a["source"]["revision"], a["content_hash"])
        for s in snapshots
        for a in s["artifacts"]
    }
    for doc in documents:
        id = doc["doc_id"]
        for source in doc["source_snapshot"]:
            if (
                source["artifact_id"],
                source["revision"],
                source["content_hash"],
            ) not in provenance:
                raise ValueError("Missing source revision: " + source["artifact_id"])
        if (
            hashlib.sha256(base64.b64decode(files["documents/" + id + ".md"])).hexdigest()
            != doc["document_sha256"]
        ):
            raise ValueError("Document checksum mismatch: " + id)
        if (
            hashlib.sha256(base64.b64decode(files["documents/" + id + ".docx"])).hexdigest()
            != doc["docx"]["sha256"]
        ):
            raise ValueError("DOCX checksum mismatch: " + id)
        for diagram in doc.get("diagrams", []):
            if not safe_name(diagram["file"]) or "/" in diagram["file"]:
                raise ValueError("Unsafe diagram filename")
            if (
                hashlib.sha256(base64.b64decode(files["documents/" + diagram["file"]])).hexdigest()
                != diagram["sha256"]
            ):
                raise ValueError("Diagram checksum mismatch")
    payload = dict(files)

    def add(name: str, value: str) -> None:
        payload[name] = base64.b64encode(value.encode()).decode()

    for i, graph in enumerate(snapshots, 1):
        add(f"evidence/snapshot-{i}.json", json.dumps(graph, indent=2))
    current = snapshots[-1]
    from dhf.render.explorer import create_explorer

    add("trace/explorer.html", create_explorer(current, documents))
    add("trace/rtm.json", json.dumps(rtm(current, release), indent=2))
    add(
        "trace/gaps.json",
        json.dumps({"findings": gaps(current), "coverage": coverage(current, release)}, indent=2),
    )
    add("trace/rtm.md", rtm_markdown(current, rtm(current, release)))
    add("trace/gaps.md", gaps_markdown(gaps(current), gap_rules()))
    add("clause_coverage.md", clause_markdown(clause_coverage(documents)))
    add(
        "README.md",
        (
            "# Audit evidence draft\n\nSynthetic evidence and document drafts. "
            "No product approval, risk acceptance or e-signature is implied. "
            "Verify every checksum before use. "
            "Snapshots retain prior revisions used by manifests.\n"
        ),
    )
    if not all(safe_name(name) for name in payload):
        raise ValueError("Unsafe audit path")
    add(
        "SHA256SUMS",
        "".join(
            hashlib.sha256(base64.b64decode(value)).hexdigest() + "  " + name + "\n"
            for name, value in sorted(payload.items())
        ),
    )
    return {"files": payload, "release": release, "status": "draft — human review required"}


def audit_pack(snapshots: list[dict], root: Path, target: Path, release: str) -> dict:
    import base64

    if not re.fullmatch(r"[\w.-]+", release):
        raise ValueError("Invalid release")
    docs = [json.loads(p.read_text()) for p in sorted(root.glob("*.manifest.json"))]
    files = {}
    for doc in docs:
        names = [doc["doc_id"] + suffix for suffix in (".md", ".docx", ".manifest.json")]
        names += [d["file"] for d in doc.get("diagrams", [])]
        for name in names:
            path = root / name
            if (
                not safe_name(name)
                or "/" in name
                or not path.resolve().is_relative_to(root.resolve())
            ):
                raise ValueError("Unsafe input document path")
            files["documents/" + name] = base64.b64encode(path.read_bytes()).decode()
    payload = audit_payload(snapshots, files, docs, release)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(payload["files"].items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, base64.b64decode(value))
    return {"file": str(target), **verify_audit(target)}


def verify_audit(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not all(safe_name(name) for name in names):
            raise ValueError("Unsafe or duplicate archive members")
        sums = {}
        for line in archive.read("SHA256SUMS").decode().splitlines():
            digest, name = line.split("  ", 1)
            if name in sums or not re.fullmatch("[0-9a-f]{64}", digest):
                raise ValueError("Invalid checksum list")
            sums[name] = digest
        if set(sums) != set(names) - {"SHA256SUMS"}:
            raise ValueError("Incomplete checksum list")
        for name, digest in sums.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError("Checksum mismatch: " + name)
    return {
        "verified_files": len(sums),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "status": "checksums verified; human review pending",
    }
