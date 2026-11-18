"""Validated Azure DevOps Services connections and project-scoped, read-only imports."""

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from dhf.config import setting
from dhf.ingest.ado import ADO, DEFAULT_FOLLOW

DOC_TYPES = ("sad", "sdd", "sstr", "drr")
REQUIREMENT_TYPES = {"user_need", "system_req", "software_req"}
MAX_ITEMS = 5000


class WorkspaceError(Exception):
    def __init__(self, status: int, message: str, action: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.action = action


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: Literal["sad", "sdd", "sstr", "drr"] | None = None
    org_url: str = Field(min_length=1, max_length=250)
    project_name: str = Field(min_length=1, max_length=128)
    query_type: Literal["saved_query", "wiql", "area_path", "work_item_ids"]
    query_value: str = Field(min_length=1, max_length=40_000)
    pat: SecretStr | None = None
    pat_expiry: datetime | None = None
    test_plan_ids: list[int] = Field(default_factory=list, max_length=100)
    test_run_ids: list[int] = Field(default_factory=list, max_length=100)

    def validated(self) -> dict:
        values = self.model_dump(mode="json", exclude={"pat", "pat_expiry"})
        values["org_url"] = organization_url(self.org_url)
        if self.project_name in {".", ".."} or re.search(r"[/\\%\x00-\x1f\x7f]", self.project_name):
            raise WorkspaceError(400, "Enter the Azure DevOps project name.")
        if self.query_type == "saved_query":
            try:
                values["query_value"] = str(UUID(self.query_value))
            except ValueError:
                raise WorkspaceError(400, "Enter the Saved Query ID as a GUID.") from None
        if self.query_type == "work_item_ids":
            values["query_value"] = ", ".join(map(str, item_ids(self.query_value)))
        if self.query_type == "area_path" and len(self.query_value) > 400:
            raise WorkspaceError(400, "Enter an Azure DevOps Area Path of at most 400 characters.")
        for key in ("test_plan_ids", "test_run_ids"):
            if any(not 0 < value <= 2**31 - 1 for value in values[key]):
                raise WorkspaceError(400, "Test plan and run IDs must be positive integers.")
            values[key] = sorted(set(values[key]))
        if self.pat is not None and not re.fullmatch(
            r"[A-Za-z0-9_-]{16,256}", self.pat.get_secret_value()
        ):
            raise WorkspaceError(400, "Enter a Personal Access Token from Azure DevOps.")
        if self.pat_expiry is not None and (self.pat_expiry.tzinfo is None or self.pat is None):
            raise WorkspaceError(400, "Set a timezone-aware expiry when saving a new PAT.")
        return values


def item_ids(value: str) -> list[int]:
    parts = value.split(",")
    if not all(re.fullmatch(r"[0-9]{1,10}", part.strip()) for part in parts):
        raise WorkspaceError(400, "Enter comma-separated work item IDs.")
    ids = list(dict.fromkeys(int(part) for part in parts))
    if len(ids) > MAX_ITEMS or any(not 0 < item <= 2**31 - 1 for item in ids):
        raise WorkspaceError(400, f"Enter up to {MAX_ITEMS} valid work item IDs.")
    return ids


def organization_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        match = re.fullmatch(r"/([A-Za-z0-9][A-Za-z0-9-]{0,63})/?", parts.path)
        legacy = re.fullmatch(r"([a-z0-9][a-z0-9-]{0,63})\.visualstudio\.com", parts.netloc.lower())
        if parts.scheme == "https" and not parts.query and not parts.fragment:
            if parts.netloc.lower() == "dev.azure.com" and match:
                return "https://dev.azure.com/" + match[1].lower()
            if legacy and parts.path in ("", "/"):
                return "https://dev.azure.com/" + legacy[1]
    except ValueError:
        pass
    raise WorkspaceError(400, "Use the HTTPS organization URL, like https://dev.azure.com/my-org.")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class WorkspaceADO(ADO):
    """Use the existing graph normalization and ADO batching with an explicit selector."""

    def __init__(self, connection: dict, pat: str, document_type: str) -> None:
        path = Path(setting("APP_ADO_MAPPING", "specs/ado_workspace_mapping.yaml"))
        mapping = yaml.safe_load(path.read_text(encoding="utf-8"))
        mapping["default_work_item_type"] = "document_section"
        self.connection = connection
        self.document_type = document_type
        self.selected_runs: list[dict] | None = None
        self.run_results: dict[str, list[dict]] = {}
        super().__init__(
            connection["org_url"],
            connection["project_name"],
            pat,
            {"follow": {"types": list(DEFAULT_FOLLOW)}, "history": False},
            trust_env=False,
            mapping=mapping,
        )
        self.read_only = True

    @property
    def seeded(self) -> bool:
        return True

    def workitems(self, since: str | None = None) -> list[dict]:
        query_type = self.connection["query_type"]
        value = self.connection["query_value"]
        params = {"$top": MAX_ITEMS + 1}
        if query_type == "work_item_ids":
            ids = item_ids(value)
        else:
            if query_type == "saved_query":
                matches = self.request("GET", f"/_apis/wit/wiql/{value}", params=params)
            else:
                if query_type == "area_path":
                    project = self.project.replace("'", "''")
                    area = value.replace("'", "''")
                    value = (
                        "SELECT [System.Id] FROM WorkItems "
                        f"WHERE [System.TeamProject] = '{project}' AND "
                        f"([System.AreaPath] = '{area}' OR [System.AreaPath] UNDER '{area}')"
                    )
                matches = self.request("POST", "/_apis/wit/wiql", {"query": value}, params)
            ids = list(
                dict.fromkeys(
                    [item["id"] for item in matches.get("workItems", [])]
                    + [
                        link[key]["id"]
                        for link in matches.get("workItemRelations", [])
                        for key in ("source", "target")
                        if link.get(key)
                    ]
                )
            )
            if len(ids) >= MAX_ITEMS + 1 or len(matches.get("workItemRelations", [])) > MAX_ITEMS:
                raise WorkspaceError(
                    422, f"The query is too broad. Select up to {MAX_ITEMS} items."
                )

        items = self.fetch(ids)
        if self.runs_read():
            related = {
                int(relation["url"].rsplit("/", 1)[-1])
                for item in items
                for relation in item.get("relations", [])
                if relation["rel"] == "Microsoft.VSTS.Common.TestedBy-Forward"
                and relation["url"].rsplit("/", 1)[-1].isdigit()
            }
            for run in self.test_runs():
                path = f"/_apis/test/runs/{run['id']}/results"
                results = self.collection(path)
                self.run_results[path] = results
                related.update(
                    int(ident)
                    for result in results
                    if (ident := str((result.get("testCase") or {}).get("id", ""))).isdigit()
                )
            related.difference_update(item["id"] for item in items)
            if len(items) + len(related) > MAX_ITEMS:
                raise WorkspaceError(422, "The selection and its linked test cases are too broad.")
            items.extend(self.fetch(sorted(related)))
        return items

    def collection(self, path: str, params: dict | None = None) -> list[dict]:
        if path in self.run_results:
            return self.run_results[path]
        return super().collection(path, params)

    def fetch(self, ids: list[int]) -> list[dict]:
        return [
            item
            for item in super().fetch(ids)
            if (item["fields"].get("System.TeamProject") or "").casefold()
            == self.project.casefold()
        ]

    def runs_read(self) -> bool:
        return self.document_type == "sstr" and bool(
            self.connection["test_plan_ids"] or self.connection["test_run_ids"]
        )

    def test_runs(self) -> list[dict]:
        if not self.runs_read():
            return []
        if self.selected_runs is not None:
            return self.selected_runs
        runs = {
            run["id"]: run
            for plan in self.connection["test_plan_ids"]
            for run in self.collection("/_apis/test/runs", {"planId": plan})
        }
        for run in self.connection["test_run_ids"]:
            runs[run] = self.request("GET", f"/_apis/test/runs/{run}")
        self.selected_runs = list(runs.values())
        return self.selected_runs

    def test_connection(self) -> list[str]:
        self.request("GET", "/_apis/wit/workitemtypes")
        verified = ["Work Items (Read)"]
        if self.document_type == "sstr":
            self.request("GET", "/_apis/test/runs", params={"$top": 1})
            verified.append("Test Management (Read)")
        return verified


def translate_ado_error(error: Exception) -> WorkspaceError:
    if isinstance(error, PermissionError):
        message = (
            "The PAT has expired."
            if "expired" in str(error).lower()
            else ("Azure DevOps rejected the PAT. It may be invalid, revoked or expired.")
        )
        return WorkspaceError(401, message, "Update PAT")
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 403:
            return WorkspaceError(
                403,
                "Azure DevOps denied access. Check project permissions and required PAT scopes.",
                "Update PAT",
            )
        if status == 404:
            return WorkspaceError(
                404, "Check the organization, project and selected query or test IDs."
            )
        if 300 <= status < 400 or status == 401:
            return WorkspaceError(401, "Azure DevOps requires a valid PAT.", "Update PAT")
        if status == 400:
            return WorkspaceError(
                422, "Azure DevOps rejected the selection. Check the query syntax and IDs."
            )
    return WorkspaceError(502, "Could not read Azure DevOps. Check the connection and try again.")
