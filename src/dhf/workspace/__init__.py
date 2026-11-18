"""Local product workspace for Azure connections, input files and evidence snapshots."""

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from dhf.config import setting
from dhf.graph import Store
from dhf.llm import canonical
from dhf.models.evidence import validate_graph
from dhf.workspace.sources import (
    DOC_TYPES,
    REQUIREMENT_TYPES,
    ConnectionInput,
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
        azure = json.loads(snapshot["graph"]) if snapshot else EMPTY_GRAPH
        return uploaded_evidence(
            [{**dict(row), "blocks": json.loads(row["blocks"])} for row in uploads], azure
        )

    def save_evidence(self, actor: str, doc: str) -> dict:
        graph = self.graph(actor, doc)
        requirements = any(
            item["type"] in REQUIREMENT_TYPES and item["source"]["system"] == "ado"
            for item in graph["artifacts"]
        )
        roles = {item["attributes"].get("input_role") for item in graph["artifacts"]}
        if doc in {"sad", "sdd"} and not requirements and "requirements" not in roles:
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
            result = store.ingest(graph)
        finally:
            store.close()
        return {**result, "path": path.as_posix()}
