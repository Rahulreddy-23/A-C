"""Review readiness is a draft gate; approval remains a human/eQMS action."""

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dhf.config import setting
from dhf.generate import sha
from dhf.ingest.ado import ADO, ReadOnlyViolation, clone_location, git_command
from dhf.llm import canonical
from dhf.render import render_docx

SECTION = re.compile(r"<!-- section:([\w.-]+) -->\n(.*?)<!-- endsection:\1 -->", re.S)
RESOLUTION = re.compile(
    r"<!-- dhf-resolution:([a-f0-9]{16}) (accepted|rejected) reviewer=([^\n<>]+?) "
    r"rationale=([^\n<>]+?) -->"
)
VALIDATION = re.compile(
    r"<!-- dhf-validation:([a-f0-9]{16}) reviewed reviewer=([^\n<>]+?) "
    r"rationale=([^\n<>]+?) -->"
)


def claim_key(claim: dict) -> str:
    return hashlib.sha256(canonical(claim).encode()).hexdigest()[:16]


def readiness(markdown: str, manifest: dict) -> dict:
    """Pure checks over the edited PR Markdown and original generation manifest."""
    sections = {id: text for id, text in SECTION.findall(markdown)}
    resolutions = {
        key: {"decision": decision, "reviewer": reviewer.strip(), "rationale": rationale.strip()}
        for key, decision, reviewer, rationale in RESOLUTION.findall(markdown)
    }
    validation_reviews = {
        key
        for key, reviewer, rationale in VALIDATION.findall(markdown)
        if reviewer.strip() and rationale.strip()
    }
    blockers = []
    manual_authors = {}
    expected = {s["id"] for s in manifest["sections"]}
    if set(sections) != expected or len(SECTION.findall(markdown)) != len(expected):
        blockers.append({"reason": "section_integrity"})
    for section in manifest["sections"]:
        id = section["id"]
        text = sections.get(id, "")
        if section["status"] == "ai_unavailable":
            authored = re.search(
                r"<!-- dhf-authoring:"
                + re.escape(id)
                + r" reviewer=([^\n<>]+?) rationale=([^\n<>]+?) -->",
                text,
            )
            body = re.sub(r"<!--.*?-->|^#+[^\n]*", "", text, flags=re.S | re.M).strip()
            if (
                not authored
                or not body
                or "AI drafting unavailable" in text
                or not all(group.strip() for group in authored.groups())
            ):
                blockers.append({"section": id, "reason": "ai_unavailable"})
            else:
                manual_authors[id] = {
                    "reviewer": authored[1].strip(),
                    "rationale": authored[2].strip(),
                }
        if section["status"] == "stale" or section.get("evidence_status") == "stale":
            blockers.append({"section": id, "reason": "stale"})
        if section["mode"] == "human":
            visible = re.sub(r"<!--.*?-->|^#+[^\n]*", "", text, flags=re.S | re.M).strip()
            if not visible or "Human input required" in visible:
                blockers.append({"section": id, "reason": "human_input_required"})
        for claim in section["claims"]:
            if claim["kind"] != "suggested":
                continue
            key = claim_key(claim)
            resolution = resolutions.get(key)
            if not resolution or not resolution["reviewer"] or not resolution["rationale"]:
                blockers.append({"section": id, "reason": "unresolved_suggestion", "claim": key})
            elif resolution["decision"] == "rejected" and claim["text"] in text:
                blockers.append({"section": id, "reason": "rejected_text_present", "claim": key})
        if "[Suggested" in text:
            blockers.append({"section": id, "reason": "suggestion_label_present"})
    for event in manifest["validation"]["rejected"]:
        key = claim_key(event)
        if key not in validation_reviews:
            blockers.append({"reason": "unreviewed_validator_rejection", "event": key})
    return {
        "ready": not blockers,
        "blockers": blockers,
        "resolutions": resolutions,
        "manual_authors": manual_authors,
        "document_sha256": sha(markdown),
    }


class DocsReview:
    def __init__(self, ado: ADO, root: Path = Path("out/docs-clone")) -> None:
        self.ado = ado
        self.name = setting("ADO_DOCS_REPO", "kestrel-dhf-docs")
        self.api = "/_apis/git/repositories/" + self.name + "/pullrequests"
        repo = next(r for r in ado.collection("/_apis/git/repositories") if r["name"] == self.name)
        root = clone_location(root, repo["remoteUrl"])
        self.root = root
        if not root.exists():
            root.parent.mkdir(parents=True, exist_ok=True)
            git_command(["clone", repo["remoteUrl"], str(root.resolve())], root.parent, ado.token)
        # Mirror the remote's tags exactly so a recreated remote never leaves stale baselines.
        git_command(
            ["fetch", "origin", "--prune", "--prune-tags", "--force", "--tags"], root, ado.token
        )
        self.main = repo.get("defaultBranch", "refs/heads/main").removeprefix("refs/heads/")

    def baseline(self, doc: str) -> tuple[str, str]:
        tags = git_command(["tag", "--list", doc + "-v*", "--sort=-version:refname"], self.root)
        for tag in tags.splitlines():
            if re.fullmatch(re.escape(doc) + r"-v\d+", tag):
                return tag, git_command(["show", tag + ":" + doc + ".md"], self.root, strip=False)
        return "", ""

    def push(self, refspec: str) -> None:
        """The only way this class writes to the docs remote; read-only mode refuses it."""
        if self.ado.read_only:
            raise ReadOnlyViolation("Read-only mode: refusing to push to the docs repository")
        git_command(["push", "origin", refspec], self.root, self.ado.token)

    def commit(self, branch: str, doc: str, markdown: str, manifest: dict, previous: str) -> None:
        if self.ado.read_only:
            raise ReadOnlyViolation("Read-only mode: refusing to push to the docs repository")
        (self.root / (doc + ".md")).write_text(markdown, encoding="utf-8", newline="\n")
        from dhf.generate.support import support_comments

        counts = render_docx(
            markdown,
            self.root / (doc + ".docx"),
            previous,
            manifest["generated_at"],
            support_findings=support_comments(manifest),
        )
        manifest["docx"] = {
            "sha256": hashlib.sha256((self.root / (doc + ".docx")).read_bytes()).hexdigest(),
            **counts,
        }
        (self.root / (doc + ".manifest.json")).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        from dhf.render.diagram import write_diagrams

        diagrams = write_diagrams(doc, manifest["sections"], self.root)
        manifest["diagrams"] = diagrams
        (self.root / (doc + ".manifest.json")).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        git_command(
            [
                "add",
                "--",
                doc + ".md",
                doc + ".docx",
                doc + ".manifest.json",
                *(d["file"] for d in diagrams),
            ],
            self.root,
        )
        if git_command(["diff", "--cached", "--name-only"], self.root):
            git_command(
                [
                    "-c",
                    "user.name=DHF Assistant",
                    "-c",
                    "user.email=dhf@example.invalid",
                    "commit",
                    "-m",
                    f"DHF: draft {doc} for human review",
                ],
                self.root,
            )
        self.push("HEAD:refs/heads/" + branch)

    def status(self, pr_id: int, check: dict) -> dict:
        return self.ado.request(
            "POST",
            self.api + f"/{pr_id}/statuses",
            {
                "state": "succeeded" if check["ready"] else "failed",
                "description": "Draft ready for human review"
                if check["ready"]
                else f"{len(check['blockers'])} unresolved draft blockers",
                "context": {"name": "DHF review readiness", "genre": "dhf"},
            },
        )

    def approved_documents(self) -> list[dict]:
        """Read the latest approved tag per document, including legacy Markdown baselines."""
        from dhf.trace.consistency import legacy_design

        tags = git_command(["tag", "--list"], self.root).splitlines()
        latest = {}
        for tag in tags:
            match = re.fullmatch(r"([a-z_]+)-v(\d+)", tag)
            if match and int(match[2]) > latest.get(match[1], (0, ""))[0]:
                latest[match[1]] = (int(match[2]), tag)
        documents = []
        for doc, (_, tag) in sorted(latest.items()):
            files = git_command(["ls-tree", "-r", "--name-only", tag], self.root).splitlines()
            if doc + ".manifest.json" in files:
                document = json.loads(
                    git_command(["show", tag + ":" + doc + ".manifest.json"], self.root)
                )
            elif doc == "sad" and doc + ".md" in files:
                document = legacy_design(git_command(["show", tag + ":" + doc + ".md"], self.root))
            else:
                continue
            documents.append({**document, "baseline_tag": tag})
        return documents

    def publish(
        self, result: dict, changed_sections: list[str] | None = None, gap_count: int = 0
    ) -> dict:
        manifest = result["manifest"]
        doc = manifest["doc_id"]
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        release = str(manifest["params"].get("release", "draft"))
        if not re.fullmatch(r"[\w.-]+", doc + release):
            raise ValueError("Invalid document/parameter branch name")
        branch = f"dhf/{doc}/{release}/{timestamp}"
        git_command(["checkout", "-b", branch, "origin/" + self.main], self.root)
        tag, previous = self.baseline(doc)
        manifest["baseline"] = tag or None
        required = [
            r.strip()
            for r in setting("ADO_REQUIRED_REVIEWERS", "mock-reviewer").split(",")
            if r.strip()
        ]
        manifest["review"] = {"pr_url": None, "reviewers": required, "status": "draft"}
        self.commit(branch, doc, result["markdown"], manifest, previous)
        counts = Counter()
        for section in manifest["sections"]:
            counts.update(section["claim_counts"])
        changed = (
            changed_sections
            if changed_sections is not None
            else [s["id"] for s in manifest["sections"]]
        )
        pr = self.ado.request(
            "POST",
            self.api,
            {
                "sourceRefName": "refs/heads/" + branch,
                "targetRefName": "refs/heads/" + self.main,
                "title": f"DHF draft: {doc} release {release}",
                "description": "Changed sections: "
                + ", ".join(changed)
                + "\nClaim counts: "
                + canonical(dict(counts))
                + f"\nDeterministic gaps: {gap_count}\nHuman review and eQMS approvals required.",
                "reviewers": [{"id": r, "isRequired": True} for r in required],
            },
        )
        pr_id = pr["pullRequestId"]
        manifest["review"]["pr_url"] = pr["_links"]["web"]["href"]
        manifest["review"]["pr_id"] = pr_id
        manifest["review"]["branch"] = branch
        self.commit(branch, doc, result["markdown"], manifest, previous)
        check = readiness(result["markdown"], manifest)
        self.status(pr_id, check)
        return {
            "pr_id": pr_id,
            "pr_url": manifest["review"]["pr_url"],
            "branch": branch,
            "readiness": check,
            "docx": manifest["docx"],
        }

    def check_pr(self, doc: str, pr_id: int) -> dict:
        pr = self.ado.request("GET", self.api + f"/{pr_id}")
        ref = pr["sourceRefName"]
        if not ref.startswith("refs/heads/dhf/" + doc + "/"):
            raise ValueError("PR does not belong to the requested DHF document")
        git_command(["fetch", "origin", ref], self.root, self.ado.token)
        git_command(["checkout", "-B", ref.removeprefix("refs/heads/"), "FETCH_HEAD"], self.root)
        markdown = (self.root / (doc + ".md")).read_text(encoding="utf-8")
        manifest = json.loads((self.root / (doc + ".manifest.json")).read_text(encoding="utf-8"))
        check = readiness(markdown, manifest)
        manifest["review"]["status"] = "ready_for_review" if check["ready"] else "draft"
        manifest["review"]["readiness"] = check
        for section in manifest["sections"]:
            if section["id"] in check["manual_authors"]:
                section["status"] = "human_authored"
                section["manual_authoring"] = check["manual_authors"][section["id"]]
        manifest.setdefault("draft_sha256", manifest["document_sha256"])
        manifest["document_sha256"] = sha(markdown)
        self.commit(ref.removeprefix("refs/heads/"), doc, markdown, manifest, self.baseline(doc)[1])
        self.status(pr_id, check)
        return check

    def create_baseline(self, doc: str, pr_id: int) -> str:
        if self.ado.read_only:
            raise ReadOnlyViolation("Read-only mode: refusing to tag the docs repository")
        pr = self.ado.request("GET", self.api + f"/{pr_id}")
        if pr["status"] != "completed":
            raise ValueError("Only a human-merged completed PR may become a baseline")
        git_command(["fetch", "origin", self.main, "--tags"], self.root, self.ado.token)
        manifest = json.loads(
            git_command(["show", f"origin/{self.main}:{doc}.manifest.json"], self.root)
        )
        markdown = git_command(["show", f"origin/{self.main}:{doc}.md"], self.root, strip=False)
        if manifest["review"].get("pr_id") != pr_id or not readiness(markdown, manifest)["ready"]:
            raise ValueError("Merged document has not passed the readiness gate")
        if sha(markdown) != manifest["document_sha256"]:
            raise ValueError("Merged document hash does not match the checked manifest")
        latest = self.baseline(doc)[0]
        version = int(latest.rsplit("-v", 1)[1]) + 1 if latest else 1
        tag = f"{doc}-v{version}"
        git_command(["tag", tag, "origin/" + self.main], self.root)
        try:
            self.push("refs/tags/" + tag)
        except Exception:
            git_command(["tag", "--delete", tag], self.root)  # no local-only "approved" baseline
            raise
        return tag
