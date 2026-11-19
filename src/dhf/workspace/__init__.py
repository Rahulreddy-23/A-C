"""Local product workspace for Azure connections, input files and evidence snapshots."""

import hashlib
import json
import sqlite3
import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from dhf.config import setting
from dhf.generate import generate_document
from dhf.generate.support import support_comments
from dhf.graph import Store, diff_graph
from dhf.impact import impact, regenerate
from dhf.llm import LLM, canonical
from dhf.models.evidence import validate_graph
from dhf.render import render_docx
from dhf.render.explorer import evidence_findings
from dhf.review import (
    author_section,
    claim_key,
    readiness,
    resolve_suggestion,
    review_validation,
)
from dhf.workspace.insights import gap_groups, merged_graph, requirement_trace
from dhf.workspace.sources import (
    DOC_TYPES,
    REQUIREMENT_TYPES,
    ConnectionInput,
    ProjectInput,
    WorkspaceADO,
    WorkspaceError,
    now,
    translate_ado_error,
)
from dhf.workspace.uploads import (
    EMPTY_GRAPH,
    SecretRedactor,
    input_profile,
    parse_upload,
    uploaded_evidence,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, owner TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS azure_connections (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
    document_type TEXT, org_url TEXT NOT NULL, project_name TEXT NOT NULL,
    encrypted_pat BLOB, pat_last4 TEXT, pat_expiry TEXT, pat_saved_at TEXT,
    query_type TEXT NOT NULL, query_value TEXT NOT NULL,
    test_plan_ids TEXT NOT NULL, test_run_ids TEXT NOT NULL,
    created_by TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS connection_scope
    ON azure_connections(project_id, coalesce(document_type, ''));
CREATE TABLE IF NOT EXISTS project_audit (
    id INTEGER PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
    connection_id TEXT NOT NULL REFERENCES azure_connections(id),
    actor TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_sources (
    project_id TEXT NOT NULL REFERENCES projects(id),
    document_type TEXT NOT NULL, mode TEXT NOT NULL, PRIMARY KEY(project_id, document_type)
);
CREATE TABLE IF NOT EXISTS requirements_snapshots (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
    document_type TEXT NOT NULL, connection_id TEXT NOT NULL REFERENCES azure_connections(id),
    configuration TEXT NOT NULL, graph TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_details (
    project_id TEXT PRIMARY KEY REFERENCES projects(id), details TEXT NOT NULL,
    archived INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_approvals (
    project_id TEXT NOT NULL REFERENCES projects(id), document_type TEXT NOT NULL,
    version INTEGER NOT NULL, reference TEXT NOT NULL, approver TEXT NOT NULL,
    comment TEXT NOT NULL, document_sha256 TEXT NOT NULL, approved_at TEXT NOT NULL,
    PRIMARY KEY (project_id, document_type, version)
);
CREATE INDEX IF NOT EXISTS requirements_snapshot_scope
    ON requirements_snapshots(project_id, document_type, connection_id, configuration, created_at);
CREATE TABLE IF NOT EXISTS input_uploads (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
    document_type TEXT NOT NULL, role TEXT NOT NULL, filename TEXT NOT NULL,
    digest TEXT NOT NULL, blocks TEXT NOT NULL, redactions INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL, UNIQUE (project_id, document_type, role, filename, digest)
);
"""
CONNECTION_FIELDS = (
    "document_type",
    "org_url",
    "project_name",
    "query_type",
    "query_value",
    "test_plan_ids",
    "test_run_ids",
)
UPLOAD_METADATA = "id, role, filename, digest, redactions, uploaded_at"


class Workspace:
    def __init__(self, root: Path, project_id: str, owner: str, members: list[str]) -> None:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = root
        self.project_id = project_id
        self.path = root / "workspace.sqlite"
        self.profile = input_profile()
        with self.database() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT OR IGNORE INTO projects VALUES (?, ?)", (project_id, owner))
            saved_owner = db.execute(
                "SELECT owner FROM projects WHERE id=?", (project_id,)
            ).fetchone()["owner"]
        if saved_owner != owner:
            raise WorkspaceError(403, "Only the workspace owner can start this project.")
        self.authorized = frozenset({owner, *members})
        # One writer per project's drafts: reviews never interleave with a redraft.
        self.edit = threading.Lock()
        self.graphs: dict[str, tuple[tuple, dict]] = {}

    @contextmanager
    def database(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA secure_delete=ON")
            yield db

    def require_member(self, actor: str) -> None:
        if actor not in self.authorized:
            raise WorkspaceError(403, "You need project membership to use these inputs.")

    @staticmethod
    def cipher() -> Fernet:
        try:
            return Fernet(setting("APP_ENCRYPTION_KEY").encode())
        except ValueError:
            raise WorkspaceError(
                503, "Set a valid APP_ENCRYPTION_KEY before using saved PATs."
            ) from None

    def credential(self, row: sqlite3.Row) -> str | None:
        if not row["encrypted_pat"]:
            return None
        try:
            return self.cipher().decrypt(row["encrypted_pat"]).decode()
        except InvalidToken:
            raise WorkspaceError(
                503, "The saved PAT cannot be decrypted. Save a replacement.", "Update PAT"
            ) from None

    def connections(self, db: sqlite3.Connection) -> list[sqlite3.Row]:
        return db.execute(
            "SELECT * FROM azure_connections WHERE project_id=? ORDER BY document_type",
            (self.project_id,),
        ).fetchall()

    def connection(self, db: sqlite3.Connection, cid: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT * FROM azure_connections WHERE project_id=? AND id=?",
            (self.project_id, cid),
        ).fetchone()
        if row is None:
            raise WorkspaceError(404, "Azure connection not found.")
        return row

    @staticmethod
    def properties(row: sqlite3.Row) -> dict:
        result = {key: row[key] for key in CONNECTION_FIELDS}
        for key in ("test_plan_ids", "test_run_ids"):
            result[key] = json.loads(result[key])
        return result

    def public_connection(self, row: sqlite3.Row) -> dict:
        return {
            **self.properties(row),
            **{
                key: row[key]
                for key in (
                    "id",
                    "project_id",
                    "pat_expiry",
                    "pat_saved_at",
                    "created_by",
                    "updated_at",
                )
            },
            "pat_mask": "••••••••" + row["pat_last4"] if row["pat_last4"] else None,
        }

    def audit(self, db: sqlite3.Connection, cid: str, actor: str, action: str, at: str) -> None:
        db.execute(
            "INSERT INTO project_audit(project_id,connection_id,actor,action,at) "
            "VALUES (?,?,?,?,?)",
            (self.project_id, cid, actor, action, at),
        )

    def save_connection(self, actor: str, change: ConnectionInput) -> dict:
        self.require_member(actor)
        inputs = change.validated()
        token = change.pat.get_secret_value() if change.pat is not None else None
        encrypted = self.cipher().encrypt(token.encode()) if token else None
        at = now()
        with self.database() as db:
            db.execute("BEGIN IMMEDIATE")
            connections = self.connections(db)
            current = next(
                (row for row in connections if row["document_type"] == change.document_type), None
            )
            # Replacing an encrypted credential must work after key rotation. Reject likely
            # secrets in other fields, including the exact replacement value.
            redactor = SecretRedactor([token] if token else [])
            redactor.data(inputs)
            if redactor.count:
                raise WorkspaceError(400, "Enter the PAT only in the Personal Access Token field.")
            if current and current["org_url"] != inputs["org_url"] and not encrypted:
                if current["encrypted_pat"]:
                    raise WorkspaceError(400, "Enter a PAT for the new organization.", "Update PAT")
            cid = current["id"] if current else uuid4().hex
            metadata = {
                **inputs,
                "test_plan_ids": canonical(inputs["test_plan_ids"]),
                "test_run_ids": canonical(inputs["test_run_ids"]),
                "updated_at": at,
            }
            if encrypted is not None:
                metadata.update(
                    encrypted_pat=encrypted,
                    pat_last4=token[-4:],
                    pat_saved_at=at,
                    pat_expiry=change.pat_expiry.astimezone(UTC).isoformat()
                    if change.pat_expiry
                    else None,
                )
            if current:
                sets = ", ".join(f"{key}=:{key}" for key in metadata)
                db.execute(
                    f"UPDATE azure_connections SET {sets} WHERE id=:id", {**metadata, "id": cid}
                )
            else:
                metadata.update(id=cid, project_id=self.project_id, created_by=actor)
                fields = ", ".join(metadata)
                bind = ", ".join(f":{key}" for key in metadata)
                db.execute(f"INSERT INTO azure_connections ({fields}) VALUES ({bind})", metadata)
            if encrypted is not None:
                action = "pat_replaced" if current and current["encrypted_pat"] else "pat_saved"
                self.audit(db, cid, actor, action, at)
            return self.public_connection(self.connection(db, cid))

    def remove_pat(self, actor: str, cid: str) -> dict:
        self.require_member(actor)
        at = now()
        with self.database() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.connection(db, cid)
            if row["encrypted_pat"] is not None:
                db.execute(
                    """UPDATE azure_connections SET encrypted_pat=NULL, pat_last4=NULL,
                       pat_saved_at=NULL, pat_expiry=NULL, updated_at=? WHERE id=?""",
                    (at, cid),
                )
                self.audit(db, cid, actor, "pat_removed", at)
            return self.public_connection(self.connection(db, cid))

    def set_source(
        self, actor: str, doc: str, mode: Literal["default", "override", "none"]
    ) -> None:
        self.require_member(actor)
        self.document(doc)
        with self.database() as db:
            db.execute(
                """INSERT INTO document_sources VALUES (?, ?, ?)
                   ON CONFLICT(project_id,document_type) DO UPDATE SET mode=excluded.mode""",
                (self.project_id, doc, mode),
            )

    def document(self, doc: str) -> dict:
        if doc not in DOC_TYPES:
            raise WorkspaceError(404, "Document type not found.")
        return self.profile["documents"][doc]

    @staticmethod
    def fingerprint(row: sqlite3.Row) -> str:
        values = [row[field] for field in CONNECTION_FIELDS]
        return hashlib.sha256(canonical(values).encode()).hexdigest()

    def fetch_or_test(self, actor: str, cid: str, doc: str | None, fetch: bool) -> dict:
        self.require_member(actor)
        with self.database() as db:
            row = self.connection(db, cid)
            doc = doc or row["document_type"] or "sad"
            self.document(doc)
            if row["document_type"] and row["document_type"] != doc:
                raise WorkspaceError(404, "Azure connection not found for this document.")
            if row["pat_expiry"] and datetime.fromisoformat(row["pat_expiry"]) <= datetime.now(UTC):
                raise WorkspaceError(401, "The saved PAT has expired.", "Update PAT")
            token = self.credential(row)
            if not token:
                raise WorkspaceError(401, "Save a Personal Access Token first.", "Update PAT")
        settings = self.properties(row)
        try:
            ado = WorkspaceADO(settings, token, doc)
            try:
                verified = ado.test_connection()
                if not fetch:
                    return {"verified_access": verified, "pat_expiry": row["pat_expiry"]}
                graph = ado.ingest()
            finally:
                ado.close()
        except WorkspaceError:
            raise
        except Exception as error:
            raise translate_ado_error(error) from None
        redactor = SecretRedactor([token])
        for item in graph["artifacts"]:
            item.pop("content_hash")
            # Azure imports belong to the same confidential workspace even if source tags
            # happen to resemble a demo marker.
            item["attributes"]["synthetic"] = False
        graph = validate_graph(redactor.data(graph))
        if not graph["artifacts"]:
            raise WorkspaceError(422, "No work items matched in this Azure DevOps project.")
        sid, at = uuid4().hex, now()
        with self.database() as db:
            db.execute("BEGIN IMMEDIATE")
            if self.connection(db, cid)["updated_at"] != row["updated_at"]:
                raise WorkspaceError(409, "Connection changed while reading. Fetch again.")
            db.execute(
                "INSERT INTO requirements_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, self.project_id, doc, cid, self.fingerprint(row), canonical(graph), at),
            )
        return self.snapshot_metadata(sid, at, graph)

    @staticmethod
    def snapshot_metadata(sid: str, at: str, graph: dict) -> dict:
        counts = Counter(item["type"] for item in graph["artifacts"])
        return {
            "id": sid,
            "created_at": at,
            "requirements": sum(counts[k] for k in REQUIREMENT_TYPES),
            "artifact_counts": dict(counts),
            "items": [{k: item[k] for k in ("id", "type", "title")} for item in graph["artifacts"]],
        }

    def upload(self, actor: str, doc: str, role: str, filename: str, raw: bytes) -> dict:
        self.require_member(actor)
        if role not in self.document(doc)["inputs"]:
            raise WorkspaceError(400, "Choose an input from this document's checklist.")
        with self.database() as db:
            # Read active credentials before constructing evidence. Only sanitized blocks
            # and a digest of those blocks are persisted.
            tokens = [self.credential(row) for row in self.connections(db)]
            upload = parse_upload(filename, raw, [token for token in tokens if token])
            row = {
                "id": uuid4().hex,
                "project_id": self.project_id,
                "document_type": doc,
                "role": role,
                "uploaded_at": now(),
                **upload,
            }
            db.execute(
                """INSERT INTO input_uploads VALUES (:id,:project_id,:document_type,:role,
                   :filename,:digest,:blocks,:redactions,:uploaded_at)
                   ON CONFLICT(project_id,document_type,role,filename,digest) DO NOTHING""",
                {**row, "blocks": canonical(upload["blocks"])},
            )
            saved = db.execute(
                f"""SELECT {UPLOAD_METADATA} FROM input_uploads WHERE project_id=:project_id
                    AND document_type=:document_type AND role=:role AND filename=:filename
                    AND digest=:digest""",
                row,
            ).fetchone()
            return {**dict(saved), "redactions": upload["redactions"]}

    def delete_upload(self, actor: str, doc: str, file_id: str) -> None:
        self.require_member(actor)
        self.document(doc)
        with self.database() as db:
            cursor = db.execute(
                "DELETE FROM input_uploads WHERE project_id=? AND document_type=? AND id=?",
                (self.project_id, doc, file_id),
            )
            if not cursor.rowcount:
                raise WorkspaceError(404, "Input file not found.")

    def read_inputs(
        self, db: sqlite3.Connection, doc: str
    ) -> tuple[str, list[sqlite3.Row], sqlite3.Row | None]:
        source = db.execute(
            "SELECT mode FROM document_sources WHERE project_id=? AND document_type=?",
            (self.project_id, doc),
        ).fetchone()
        mode = source["mode"] if source else "default"
        connections = self.connections(db)
        selected = (
            None
            if mode == "none"
            else next(
                (
                    row
                    for row in connections
                    if row["document_type"] == (doc if mode == "override" else None)
                ),
                None,
            )
        )
        snapshot = None
        if selected:
            snapshot = db.execute(
                """SELECT id,created_at,graph FROM requirements_snapshots WHERE project_id=?
                   AND document_type=? AND connection_id=? AND configuration=?
                   ORDER BY created_at DESC LIMIT 1""",
                (self.project_id, doc, selected["id"], self.fingerprint(selected)),
            ).fetchone()
        return mode, connections, snapshot

    def state(self, actor: str, doc: str) -> dict:
        self.require_member(actor)
        self.document(doc)
        with self.database() as db:
            mode, connections, snapshot = self.read_inputs(db, doc)
            files = db.execute(
                f"""SELECT {UPLOAD_METADATA} FROM input_uploads WHERE project_id=?
                    AND document_type=? ORDER BY uploaded_at""",
                (self.project_id, doc),
            ).fetchall()
            audit = db.execute(
                """SELECT action, actor, at, connection_id FROM project_audit WHERE project_id=?
                   ORDER BY id DESC LIMIT 20""",
                (self.project_id,),
            ).fetchall()
        return {
            "source": mode,
            "connections": [
                self.public_connection(row)
                for row in connections
                if row["document_type"] in (None, doc)
            ],
            "snapshot": self.snapshot_metadata(
                snapshot["id"], snapshot["created_at"], json.loads(snapshot["graph"])
            )
            if snapshot
            else None,
            "uploads": [dict(row) for row in files],
            "audit": [dict(row) for row in audit],
        }

    def graph(self, actor: str, doc: str) -> dict:
        self.require_member(actor)
        self.document(doc)
        with self.database() as db:
            db.execute("BEGIN")
            _, _, snapshot = self.read_inputs(db, doc)
            uploads = db.execute(
                "SELECT * FROM input_uploads WHERE project_id=? AND document_type=? "
                "ORDER BY uploaded_at",
                (self.project_id, doc),
            ).fetchall()
        # Extraction is the slow part; reuse it until the snapshot or an upload changes.
        key = (snapshot["id"] if snapshot else None, *((r["id"], r["digest"]) for r in uploads))
        cached = self.graphs.get(doc)
        if cached and cached[0] == key:
            return cached[1]
        azure = json.loads(snapshot["graph"]) if snapshot else EMPTY_GRAPH
        graph = uploaded_evidence(
            [{**dict(row), "blocks": json.loads(row["blocks"])} for row in uploads], azure
        )
        self.graphs[doc] = (key, graph)
        return graph

    def save_evidence(self, actor: str, doc: str) -> dict:
        graph = self.graph(actor, doc)
        requirements = any(
            item["type"] in REQUIREMENT_TYPES and item["source"]["system"] == "ado"
            for item in graph["artifacts"]
        )
        roles = {item["attributes"].get("input_role") for item in graph["artifacts"]}
        if doc in {"sad", "sdd", "sfmea"} and not requirements and "requirements" not in roles:
            raise WorkspaceError(422, "Fetch Azure requirements or add an SRD or PRD first.")
        if doc == "sstr":
            if not requirements:
                raise WorkspaceError(422, "Fetch Azure requirements before saving SSTR evidence.")
            if "test_evidence" not in roles and not any(
                item["type"] == "test_result" for item in graph["artifacts"]
            ):
                raise WorkspaceError(422, "Fetch Azure test runs or upload test evidence first.")
        if self.document(doc).get("future"):
            raise WorkspaceError(422, "This document type is not available for drafting yet.")
        directory = self.root / doc
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / "evidence.sqlite"
        store = Store(path)
        try:
            previous = store.graph()
            if previous["artifacts"] and not any(diff_graph(previous, graph).values()):
                # Unchanged evidence keeps its snapshot instead of storing a copy per click.
                latest = store.db.execute("SELECT max(id) FROM snapshots").fetchone()[0]
                result = {
                    "snapshot": latest,
                    "changed": [],
                    "added": [],
                    "removed": [],
                    "artifacts": len(graph["artifacts"]),
                    "links": len(graph["links"]),
                }
            else:
                result = store.ingest(graph)
        finally:
            store.close()
        return {**result, "path": path.as_posix()}

    def details(self) -> dict:
        with self.database() as db:
            row = db.execute(
                "SELECT details, archived, updated_at FROM project_details WHERE project_id=?",
                (self.project_id,),
            ).fetchone()
        return {
            "id": self.project_id,
            **(json.loads(row["details"]) if row else {}),
            "archived": bool(row and row["archived"]),
            "updated_at": row["updated_at"] if row else None,
        }

    def save_details(self, actor: str, change: ProjectInput, archived: bool | None = None) -> dict:
        self.require_member(actor)
        with self.database() as db:
            held = db.execute(
                "SELECT archived FROM project_details WHERE project_id=?", (self.project_id,)
            ).fetchone()
            flag = int(archived if archived is not None else bool(held and held["archived"]))
            db.execute(
                """INSERT INTO project_details VALUES (?, ?, ?, ?) ON CONFLICT(project_id)
                   DO UPDATE SET details=excluded.details, archived=excluded.archived,
                   updated_at=excluded.updated_at""",
                (self.project_id, canonical(change.model_dump()), flag, now()),
            )
        return self.details()

    def set_archived(self, actor: str, archived: bool) -> dict:
        details = {k: v for k, v in self.details().items() if k in ProjectInput.model_fields}
        if not details:
            raise WorkspaceError(422, "Save the project details first.", "Edit project")
        return self.save_details(actor, ProjectInput.model_validate(details), archived)

    def drafts_dir(self, doc: str) -> Path:
        return self.root / doc / "drafts"

    def manifest(self, doc: str) -> dict | None:
        path = self.drafts_dir(doc) / f"{doc}.manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def draft(self, actor: str, doc: str, provider: str, fresh: bool = False) -> dict:
        """The first draft, or later only the sections the latest evidence made stale, so a
        reviewer's edits elsewhere stay byte for byte and Word shows the changes. `fresh`, or
        a changed project release, redrafts every section and redlines against the old text."""
        release = self.details().get("release")
        if not release:
            raise WorkspaceError(422, "Set the project release before drafting.", "Edit project")
        with self.edit:
            saved = self.save_evidence(actor, doc)
            store = Store(Path(saved["path"]))
            try:
                graph = store.graph()
            finally:
                store.close()
            out, llm = self.drafts_dir(doc), LLM(provider)
            manifest = self.manifest(doc)
            previous = out / f"{doc}.previous.md"
            if manifest is None or fresh or manifest["params"].get("release") != release:
                old = (out / f"{doc}.md").read_text(encoding="utf-8") if manifest else ""
                params = {"release": release}
                result = generate_document(doc, graph, params, provider, out=out, llm=llm)
                if manifest is None:
                    return {"updated": True, "version": 1, "stale": [], "redrafted": False}
                # A full redraft continues the version line and shows Word what changed.
                result["manifest"]["doc_version"] = manifest["doc_version"] + 1
                previous.write_text(old, encoding="utf-8", newline="\n")
                self.rerender(doc, result["markdown"], result["manifest"])
                version = result["manifest"]["doc_version"]
                return {"updated": True, "version": version, "stale": [], "redrafted": True}
            markdown = (out / f"{doc}.md").read_text(encoding="utf-8")
            report = impact(graph, manifest)
            stale = sorted(s["id"] for s in report["sections"] if s["status"] == "stale")
            if not stale:
                version = manifest["doc_version"]
                return {"updated": False, "version": version, "stale": [], "redrafted": False}
            # Later review edits re-render Word against this version, keeping the redline.
            previous.write_text(markdown, encoding="utf-8", newline="\n")
            result = regenerate(graph, manifest, markdown, report, out, llm)
            version = result["manifest"]["doc_version"]
            return {"updated": True, "version": version, "stale": stale, "redrafted": False}

    def changes(self, actor: str, doc: str) -> dict:
        """What Update draft would redraft: stale and possibly affected sections with their
        causes, read against the current inputs without saving a snapshot."""
        self.require_member(actor)
        manifest = self.manifest(doc)
        if manifest is None:
            raise WorkspaceError(404, "Generate a draft first.")
        report = impact(self.graph(actor, doc), manifest)
        titles = {s["id"]: s["title"] for s in manifest["sections"]}
        release = self.details().get("release")
        return {
            "release_changed": manifest["params"].get("release") != release,
            "sections": [{**s, "title": titles.get(s["id"], s["id"])} for s in report["sections"]],
        }

    def approvals(self, doc: str) -> list[dict]:
        with self.database() as db:
            rows = db.execute(
                """SELECT version, reference, approver, comment, document_sha256, approved_at
                   FROM document_approvals WHERE project_id=? AND document_type=?
                   ORDER BY version DESC""",
                (self.project_id, doc),
            ).fetchall()
        return [dict(row) for row in rows]

    def draft_state(self, actor: str, doc: str, with_evidence: bool = False) -> dict | None:
        self.require_member(actor)
        self.document(doc)
        manifest = self.manifest(doc)
        if manifest is None:
            return None
        out = self.drafts_dir(doc)
        check = readiness((out / f"{doc}.md").read_text(encoding="utf-8"), manifest)
        cited = {
            id
            for s in manifest["sections"]
            for c in s["claims"]
            if with_evidence and c["kind"] == "suggested"
            for id in c["citations"]
        }
        nodes = {}
        if cited:  # only the Review Center shows citation titles; skip the snapshot read
            store = Store(self.root / doc / "evidence.sqlite")
            try:
                nodes = {a["id"]: a for a in store.graph()["artifacts"] if a["id"] in cited}
            finally:
                store.close()
        return {
            "version": manifest["doc_version"],
            "generated_at": manifest["generated_at"],
            "model": manifest["model"],
            "sections": [
                {k: s[k] for k in ("id", "title", "mode", "status", "claims")}
                for s in manifest["sections"]
            ],
            "validation": manifest["validation"],
            "readiness": {k: check[k] for k in ("ready", "blockers", "resolutions")},
            "document_sha256": check["document_sha256"],
            "docx": {k: manifest.get("docx", {}).get(k, 0) for k in ("insertions", "deletions")},
            "redline": (out / f"{doc}.previous.md").is_file(),
            "changed_sections": manifest.get("changed_sections", []),
            "evidence": {
                id: {
                    "id": id,
                    "title": a["title"],
                    "type": a["type"],
                    "url": a["source"]["url"],
                    "revision": a["source"]["revision"],
                }
                for id, a in nodes.items()
            },
        }

    def rerender(self, doc: str, markdown: str, manifest: dict, redline: bool = True) -> None:
        out = self.drafts_dir(doc)
        previous = out / f"{doc}.previous.md"
        base = previous.read_text(encoding="utf-8") if redline and previous.is_file() else ""
        counts = render_docx(
            markdown,
            out / f"{doc}.docx",
            base,
            manifest["generated_at"],
            support_findings=support_comments(manifest),
        )
        digest = hashlib.sha256((out / f"{doc}.docx").read_bytes()).hexdigest()
        manifest["docx"] = {"sha256": digest, **counts}
        (out / f"{doc}.md").write_text(markdown, encoding="utf-8", newline="\n")
        (out / f"{doc}.manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )

    def review(self, actor: str, doc: str, action: dict) -> dict:
        """Reviewer decisions on the local draft, as the same edits the docs PR would hold:
        suggestions (one or many), sections that need a person, and validator rejections."""
        self.require_member(actor)
        self.document(doc)
        if not self.edit.acquire(timeout=10):
            raise WorkspaceError(409, "This draft is being updated. Try again in a moment.")
        try:
            manifest = self.manifest(doc)
            if manifest is None:
                raise WorkspaceError(404, "Generate a draft first.")
            markdown = (self.drafts_dir(doc) / f"{doc}.md").read_text(encoding="utf-8")
            suggested = {
                claim_key(c)
                for s in manifest["sections"]
                for c in s["claims"]
                if c["kind"] == "suggested"
            }
            try:
                kind = action["kind"]
                if kind == "suggestion":
                    keys = action["keys"] if "keys" in action else [action["key"]]
                    if not isinstance(keys, list) or not keys or len(keys) > 2000:
                        raise ValueError("Choose the suggestions to decide.")
                    if any(key not in suggested for key in keys):
                        raise ValueError("Only AI suggestions in this draft can be decided here.")
                    for key in dict.fromkeys(keys):
                        markdown = resolve_suggestion(
                            markdown, key, action["decision"], actor, action["rationale"]
                        )
                elif kind == "section":
                    section = next(s for s in manifest["sections"] if s["id"] == action["section"])
                    if section["mode"] != "human" and section["status"] != "ai_unavailable":
                        raise ValueError("Only sections that need a person can be written here.")
                    markdown = author_section(
                        markdown,
                        section["id"],
                        action["text"],
                        actor,
                        action.get("rationale", ""),
                        section["status"] == "ai_unavailable",
                    )
                elif kind == "validation":
                    rejected = {claim_key(e) for e in manifest["validation"]["rejected"]}
                    if action["key"] not in rejected:
                        raise ValueError("That validation event is not in this draft.")
                    markdown = review_validation(
                        markdown, action["key"], actor, action["rationale"]
                    )
                else:
                    raise ValueError("Choose a review action.")
            except ValueError as error:
                raise WorkspaceError(400, str(error)) from None
            except (KeyError, TypeError, StopIteration, AttributeError):
                raise WorkspaceError(400, "Check the review fields.") from None
            self.rerender(doc, markdown, manifest)
        finally:
            self.edit.release()
        state = self.draft_state(actor, doc)
        assert state is not None
        return state

    def approve(self, actor: str, doc: str, reference: str, comment: str) -> dict:
        """Record that a ready draft was approved in the eQMS, and keep that version as the
        baseline. Approval itself (signatures) stays in the eQMS."""
        if not self.edit.acquire(timeout=10):
            raise WorkspaceError(409, "This draft is being updated. Try again in a moment.")
        try:
            return self.record_approval(actor, doc, reference, comment)
        finally:
            self.edit.release()

    def record_approval(self, actor: str, doc: str, reference: str, comment: str) -> dict:
        state = self.draft_state(actor, doc)
        if state is None:
            raise WorkspaceError(404, "Generate a draft first.")
        if not state["readiness"]["ready"]:
            raise WorkspaceError(409, "Resolve the review blockers before recording approval.")
        reference, comment = reference.strip(), comment.strip()
        if not 0 < len(reference) <= 120 or any(c in reference for c in "\r\n<>"):
            raise WorkspaceError(400, "Enter the eQMS approval reference.")
        if len(comment) > 2000:
            raise WorkspaceError(400, "Keep the approval comment under 2000 characters.")
        out = self.drafts_dir(doc)
        markdown = (out / f"{doc}.md").read_text(encoding="utf-8")
        baseline = self.root / doc / "baselines" / f"{doc}-v{state['version']}.md"
        baseline.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        baseline.write_text(markdown, encoding="utf-8", newline="\n")
        with self.database() as db:
            db.execute(
                """INSERT INTO document_approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, document_type, version) DO UPDATE SET
                   reference=excluded.reference, approver=excluded.approver,
                   comment=excluded.comment, document_sha256=excluded.document_sha256,
                   approved_at=excluded.approved_at""",
                (
                    self.project_id,
                    doc,
                    state["version"],
                    reference,
                    actor,
                    comment,
                    state["document_sha256"],
                    now(),
                ),
            )
        # The approved copy is clean; the next update redlines against it.
        (out / f"{doc}.previous.md").unlink(missing_ok=True)
        manifest = self.manifest(doc)
        assert manifest is not None
        self.rerender(doc, markdown, manifest, redline=False)
        return self.approvals(doc)[0]

    def inputs_ready(self, doc: str) -> bool:
        with self.database() as db:
            _, _, snapshot = self.read_inputs(db, doc)
            uploads = db.execute(
                "SELECT count(*) FROM input_uploads WHERE project_id=? AND document_type=?",
                (self.project_id, doc),
            ).fetchone()[0]
        return snapshot is not None or uploads > 0

    def documents(self, actor: str, with_evidence: bool = False) -> list[dict]:
        """Each document type with its review stage, from inputs through recorded approval."""
        rows = []
        for doc in DOC_TYPES:
            meta = self.document(doc)
            draft = self.draft_state(actor, doc, with_evidence)
            approvals = self.approvals(doc)
            if draft is None:
                stage = "inputs_ready" if self.inputs_ready(doc) else "no_inputs"
            elif approvals and approvals[0]["document_sha256"] == draft["document_sha256"]:
                stage = "approved"
            elif draft["readiness"]["ready"]:
                stage = "ready"
            else:
                stage = "in_review" if draft["readiness"]["resolutions"] else "draft"
            rows.append(
                {
                    "type": doc,
                    "title": meta["title"],
                    "future": bool(meta.get("future")),
                    "stage": stage,
                    "draft": draft,
                    "approvals": approvals,
                }
            )
        return rows

    def provenance(self) -> dict:
        """Where the project's evidence came from, for the status bar on every page."""
        with self.database() as db:
            fetched = db.execute(
                "SELECT max(created_at) FROM requirements_snapshots WHERE project_id=?",
                (self.project_id,),
            ).fetchone()[0]
            uploads = db.execute(
                "SELECT count(*) FROM input_uploads WHERE project_id=?", (self.project_id,)
            ).fetchone()[0]
            default = next((r for r in self.connections(db) if r["document_type"] is None), None)
        return {
            "fetched_at": fetched,
            "uploads": uploads,
            "azure": {"org_url": default["org_url"], "project": default["project_name"]}
            if default
            else None,
        }

    def project_graph(self, actor: str) -> dict:
        return merged_graph([self.graph(actor, doc) for doc in DOC_TYPES])

    def insights(self, actor: str) -> dict:
        """The project's merged evidence, requirement trace and grouped gap findings."""
        graph = self.project_graph(actor)
        manifests = [m for doc in DOC_TYPES if (m := self.manifest(doc)) is not None]
        findings, blind, rules = evidence_findings(graph, manifests)
        groups = gap_groups(findings, blind, [r for group in rules.values() for r in group])
        return {"graph": graph, "trace": requirement_trace(graph), "groups": groups}
