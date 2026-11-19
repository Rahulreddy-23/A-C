"""Keep unsanitized uploads in memory and import only redacted source evidence."""

import csv
import hashlib
import re
import zipfile
from contextlib import suppress
from datetime import UTC, datetime
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote

import yaml

from dhf.ingest.documents import (
    BODY_LIMIT,
    artifact,
    block_text,
    content_revision,
    docx_blocks,
    edge,
    extract_document,
    resolve_links,
)
from dhf.llm import canonical
from dhf.models.evidence import validate_graph
from dhf.workspace.sources import WorkspaceError

# Real design documents carry many diagrams; a 24 MB SAD is normal.
MAX_FILE_BYTES = 40 * 1024 * 1024
ALLOWED_TYPES = {
    ".docx",
    ".md",
    ".txt",
    ".csv",
    ".py",
    ".json",
    ".log",
    ".yaml",
    ".yml",
    ".c",
    ".cpp",
    ".cs",
    ".h",
    ".java",
    ".js",
    ".ts",
    ".xml",
}
EMPTY_GRAPH = {"artifacts": [], "links": []}
REDACTED = "[REDACTED]"
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{75,76}AZDO[A-Za-z0-9]{4,5}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{52}(?![A-Za-z0-9])"),
    re.compile(r"(?im)(\b(?:basic|bearer) +)[a-z0-9._+/=-]{12,}"),
    re.compile(
        r"(?im)(\b(?:[A-Z0-9_]*_PAT|PAT|[A-Z0-9_]*SECRET|"
        r"[A-Z0-9_]*PASSWORD|[A-Z0-9_]*TOKEN|[A-Z0-9_]*API_KEY|[A-Z0-9_]*ENCRYPTION_KEY)"
        r"[\x22']?\s*[:=]\s*[\x22']?)[a-z0-9._+/=-]{8,}"
    ),
    re.compile(
        r"(?i)\b(?:sk-(?:proj-)?[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{16,}|"
        r"github_pat_[a-z0-9_]{16,}|AKIA[A-Z0-9]{16})\b"
    ),
    re.compile(
        r"(?is)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:"
        r"-----END [A-Z ]*PRIVATE KEY-----|\Z)"
    ),
)
KEY_START = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")


class SecretRedactor:
    def __init__(self, secrets: list[str]) -> None:
        self.secrets = sorted(set(filter(None, secrets)), key=len, reverse=True)
        self.count = 0
        self.in_key = False

    def text(self, value: str) -> str:
        for secret in self.secrets:
            self.count += value.count(secret)
            value = value.replace(secret, REDACTED)
        for pattern in SECRET_PATTERNS:
            replacement = r"\g<1>" + REDACTED if pattern.groups else REDACTED
            value, matches = pattern.subn(replacement, value)
            self.count += matches
        return value

    def word_paragraph(self, value: str) -> str:
        if self.in_key:
            end = KEY_END.search(value)
            self.in_key = end is None
            return self.text(value[end.end() :]) if end else ""
        if (start := KEY_START.search(value)) and not KEY_END.search(value, start.end()):
            self.in_key = True
        return self.text(value)

    def data(self, value: object) -> object:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {self.text(key): self.data(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self.data(child) for child in value]
        return value


def input_profile() -> dict:
    return yaml.safe_load(Path("specs/doc_import/workspace.yaml").read_text(encoding="utf-8"))


def upload_blocks(raw: bytes, suffix: str, redactor: SecretRedactor) -> list[dict]:
    if suffix not in ALLOWED_TYPES or not raw or len(raw) > MAX_FILE_BYTES:
        raise WorkspaceError(400, "Choose a supported file up to 40 MB.")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(raw)) as package:
                files = package.infolist()
                if len(files) > 1000 or sum(f.file_size for f in files) > 160 * 1024 * 1024:
                    raise WorkspaceError(413, "This Word document expands beyond the upload limit.")
            return docx_blocks(BytesIO(raw), redactor.word_paragraph)[0]
        except WorkspaceError:
            raise
        except Exception:
            raise WorkspaceError(422, "This file could not be read as a Word document.") from None
    try:
        content = redactor.text(raw.decode("utf-8-sig"))
    except UnicodeError:
        raise WorkspaceError(422, "Text, code and CSV uploads must use UTF-8.") from None
    # Keep unstructured evidence intact for document-section citation.
    if suffix in (".md", ".txt"):
        blocks = []
        for line in content.splitlines():
            match = re.fullmatch(r"(#{1,9})\s+(.*)", line)
            if match:
                blocks.append({"kind": "heading", "level": len(match[1]), "text": match[2]})
            elif line.strip():
                blocks.append({"kind": "para", "text": line})
        return blocks
    return [{"kind": "para", "text": content}]


def parse_upload(filename: str, raw: bytes, secrets: list[str]) -> dict:
    redactor = SecretRedactor(secrets)
    # Strip client paths before saving the display name. No original bytes reach disk.
    name = redactor.text(re.split(r"[/\\]", filename)[-1])
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    suffix = Path(name).suffix.lower()
    if not name or len(name) > 255:
        raise WorkspaceError(400, "Enter a file name of at most 255 characters.")
    blocks = upload_blocks(raw, suffix, redactor)
    if not any(block_text(block).strip() for block in blocks):
        raise WorkspaceError(422, "The file contains no readable text.")
    digest = hashlib.sha256(canonical(blocks).encode()).hexdigest()
    return {"filename": name, "blocks": blocks, "digest": digest, "redactions": redactor.count}


def uploaded_evidence(uploads: list[dict], azure: dict) -> dict:
    profile = input_profile()["inputs"]
    extractor = yaml.safe_load(
        Path("specs/doc_import/dhf_documents.yaml").read_text(encoding="utf-8")
    )
    rules = {rule["name"]: rule for rule in extractor["documents"]}
    held = {item["id"]: item for item in azure["artifacts"]}
    items, pending, test_links, classes = [], [], [], {}
    for upload in uploads:
        role, name = upload["role"], upload["filename"]
        document = f"{upload['id']}/{name}"
        source = {
            "url": f"file:workspace/{upload['id']}/{quote(name)}",
            "revision": upload["digest"],
            "retrieved_at": upload["uploaded_at"],
            "document": document,
        }
        rule = rules.get(profile[role].get("rule"), {})
        blocks = upload["blocks"]
        extracted = extract_document(blocks, rule, source)
        pending.extend(extracted["pending_links"])
        original = [*extracted["artifacts"], *document_sections(blocks, upload, source)]
        if role == "test_evidence" and Path(name).suffix.lower() == ".csv":
            records, result_links = test_evidence_csv(blocks[0]["text"], upload, source, held)
            original.extend(records)
            test_links.extend(result_links)
        if role == "safety_classification" and Path(name).suffix.lower() == ".csv":
            classes.update({k: (v, name) for k, v in safety_classes(blocks[0]["text"]).items()})
        for item in original:
            item["attributes"].update({"input_role": role, "input_file": name, "link_classes": []})
            if item["type"] in {"software_unit", "component", "system_req", "software_req"}:
                item["attributes"]["link_classes"] = ["allocated_to"]
            if item["type"] == "test_result":
                item["attributes"]["link_classes"] = ["executes", "derives_from"]
            if item["id"] in held:
                item["attributes"]["source_identifier"] = item["id"]
                item["id"] += "-" + upload["id"][:8]
            # Repeated labels inside a file still get distinct evidence, in source order.
            if item["id"] in held:
                item["id"] += f"-{len(items) + 1}"
            items.append(item)
            held[item["id"]] = item
    known = frozenset(item["id"] for item in azure["artifacts"])
    links, _ = resolve_links(items, pending, known)
    distinct = {(e["src"], e["dst"], e["type"]): e for e in [*azure["links"], *links, *test_links]}
    # The CSV fills classes the evidence lacks; a class a source states always wins.
    for item in [*azure["artifacts"], *items]:
        if item["type"] in {"component", "software_unit"} and not item["attributes"].get(
            "safety_class"
        ):
            recorded = classes.get(item["id"].lower()) or classes.get(item["title"].lower())
            if recorded:
                item["attributes"].update(safety_class=recorded[0], safety_class_source=recorded[1])
                item.pop("content_hash", None)  # recomputed, so the change reaches the store
    for item in items:
        item["source"]["revision"] = content_revision(item)
    return validate_graph(
        {"artifacts": [*azure["artifacts"], *items], "links": list(distinct.values())}
    )


def document_sections(blocks: list[dict], upload: dict, source: dict) -> list[dict]:
    # Keep all usable text in bounded evidence units with stable per-file citations.
    sections: list[tuple[str, list[str]]] = [(upload["filename"], [])]
    for block in blocks:
        if block["kind"] == "heading":
            sections.append((block["text"], []))
        elif text := block_text(block).strip():
            sections[-1][1].append(text)
    result = []
    for name, body in sections:
        text = "\n".join(body)
        for offset in range(0, len(text), BODY_LIMIT):
            ident = f"DOC-{upload['id']}-{len(result) + 1}"
            result.append(
                artifact(
                    "document_section", ident, name, text[offset : offset + BODY_LIMIT], {}, source
                )
            )
    if not result:
        ident = f"DOC-{upload['id']}-1"
        result.append(artifact("document_section", ident, upload["filename"], "", {}, source))
    return result


def safety_classes(text: str) -> dict[str, str]:
    """Owner-recorded IEC 62304 classes by item ID or title (lowercase): Item, Safety class."""
    reader = csv.DictReader(StringIO(text))
    columns = {k.strip().lower(): k for k in reader.fieldnames or []}
    if not {"item", "safety class"} <= columns.keys():
        return {}
    classes = {}
    for row in reader:
        item = (row.get(columns["item"]) or "").strip().lower()
        match = re.fullmatch(
            r"(?:class\s*)?([abc])", (row.get(columns["safety class"]) or "").strip(), re.I
        )
        if item and match:
            classes[item] = match[1].upper()
    return classes


def test_evidence_csv(
    text: str, upload: dict, source: dict, held: dict
) -> tuple[list[dict], list[dict]]:
    """Import a simple execution export with Test Case ID, Outcome and optional Release."""
    reader = csv.DictReader(StringIO(text))
    columns = {k.strip().lower(): k for k in reader.fieldnames or []}
    if not {"test case id", "outcome"} <= columns.keys():
        return [], []
    records, links, runs, cases = [], [], {}, {}
    case_ids = {
        item["source"]["native_id"]: ident
        for ident, item in held.items()
        if item["type"] == "test_case" and item["source"]["system"] == "ado"
    }
    for index, row in enumerate(reader, 1):
        native_case = (row.get(columns["test case id"]) or "").strip()
        recorded = (row.get(columns["outcome"]) or "").strip()
        if not native_case or not recorded:
            continue
        case = case_ids.get(native_case)
        if case is None and held.get(native_case, {}).get("type") == "test_case":
            case = native_case
        if case is None:
            if native_case not in cases:
                ident = f"TC-{upload['id']}-{index}"
                cases[native_case] = ident
                records.append(artifact("test_case", ident, native_case, "", {}, source))
            case = cases[native_case]
        release = (row.get(columns.get("release", "")) or "").strip()
        if release not in runs:
            ident = f"RUN-{upload['id']}-{index}"
            runs[release] = ident
            records.append(
                artifact(
                    "test_run",
                    ident,
                    upload["filename"],
                    "",
                    {
                        "release": release,
                        "completed_at": "",
                        "environment": "",
                        "is_retest": False,
                    },
                    source,
                )
            )
        run = runs[release]
        outcomes = {
            name.lower(): name
            for name in (
                "Passed",
                "Failed",
                "Blocked",
                "NotExecuted",
                "NotRun",
                "Inconclusive",
                "Aborted",
            )
        }
        outcome = outcomes.get(re.sub(r"\s+", "", recorded.lower()), recorded)
        attrs = {"test_case": case, "outcome": outcome, "run": run, "release": release}
        timestamp = row.get(columns.get("completed date", ""), "")
        if timestamp:
            with suppress(ValueError):
                date = datetime.fromisoformat(timestamp)
                attrs["completed_at"] = (
                    date.astimezone(UTC).isoformat() if date.tzinfo else timestamp
                )
        result = f"RES-{upload['id']}-{index}"
        records.append(artifact("test_result", result, native_case, "", attrs, source))
        links.extend(
            [
                edge(result, case, "executes", upload["filename"]),
                edge(result, run, "derives_from", upload["filename"]),
            ]
        )
    return records, links
