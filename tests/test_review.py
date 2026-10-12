import json
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from docx import Document
from lxml import etree
from mock_ado.state import merge_docs_pr

from dhf.generate import generate_document
from dhf.ingest.ado import ADO, git_command
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.render import AUTHOR, render_docx
from dhf.review import DocsReview, claim_key, readiness


def resolved_markdown(result: dict) -> str:
    """A synthetic human edit, never a product auto-approval function."""
    text = result["markdown"].replace("**[Suggested — review required]** ", "")
    for section in result["manifest"]["sections"]:
        decisions = "".join(
            f"<!-- dhf-resolution:{claim_key(c)} accepted reviewer=SyntheticReviewer "
            "rationale=Source prose reviewed for draft completeness only -->\n"
            for c in section["claims"]
            if c["kind"] == "suggested"
        )
        text = text.replace(
            "<!-- endsection:" + section["id"] + " -->",
            decisions + "<!-- endsection:" + section["id"] + " -->",
        )
    return text.replace(
        "[Human input required — complete in the controlled review workflow.]",
        "Human reviewer: SyntheticReviewer. eQMS approval remains outstanding.",
    )


def test_word_redlines_comments_and_hyperlinks(tmp_path: Path) -> None:
    path = tmp_path / "draft.docx"
    text = (
        "# Verification report\n\n**[Inferred]** Basis [SRS-021@r2](http://localhost/item?rev=2)\n\n"
        "**[Suggested — review required]** Review anomaly [BUG-01@r1](http://localhost/bug)\n"
    )
    counts = render_docx(
        text, path, "# Verification report\n\nOld conclusion\n", "2026-10-12T12:00:00Z"
    )
    assert counts["deletions"] == 1 and counts["insertions"] == 2 and counts["comments"] == 2
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as archive:
        xml = etree.fromstring(archive.read("word/document.xml"))
        comments = etree.fromstring(archive.read("word/comments.xml"))
        assert xml.xpath("//w:del//w:delText/text()", namespaces=ns) == ["Old conclusion"]
        assert not xml.xpath("//w:del//w:t", namespaces=ns)
        assert all(
            n.get("{" + ns["w"] + "}author") == AUTHOR
            for n in xml.xpath("//w:ins|//w:del", namespaces=ns)
        )
        assert xml.xpath("//w:hyperlink", namespaces=ns)
        assert xml.xpath('//w:highlight[@w:val="yellow"]', namespaces=ns)
        assert xml.xpath('//w:highlight[@w:val="cyan"]', namespaces=ns)
        for c in comments:
            id = c.get("{" + ns["w"] + "}id")
            for tag in ("commentRangeStart", "commentRangeEnd", "commentReference"):
                assert xml.xpath(f'//w:{tag}[@w:id="{id}"]', namespaces=ns)
        assert b"comments.xml" in archive.read("[Content_Types].xml")
        assert b"relationships/comments" in archive.read("word/_rels/document.xml.rels")
    reopened = Document(path)
    assert reopened.core_properties.title == "Verification report"
    reopened.save(tmp_path / "roundtrip.docx")
    with ZipFile(tmp_path / "roundtrip.docx") as archive:
        assert b"w:ins" in archive.read("word/document.xml")
        assert b"REVIEW REQUIRED" in archive.read("word/comments.xml")


def test_readiness_cannot_be_bypassed_by_deleting_labels(tmp_path: Path) -> None:
    result = generate_document(
        "sstr",
        ingest_fixtures(),
        {"release": "1.1"},
        out=tmp_path / "docs",
        llm=LLM(root=tmp_path / "llm"),
    )
    assert not readiness(result["markdown"], result["manifest"])["ready"]
    hidden = result["markdown"].replace("**[Suggested — review required]** ", "")
    assert not readiness(hidden, result["manifest"])["ready"]
    resolved = resolved_markdown(result)
    assert readiness(resolved, result["manifest"])["ready"]
    result["manifest"]["sections"][0]["status"] = "stale"
    assert not readiness(resolved, result["manifest"])["ready"]
    result["manifest"]["sections"][0]["status"] = "draft"
    event = {"section": "purpose_scope", "reason": "unknown_ids", "ids": ["SRS-999"]}
    result["manifest"]["validation"]["rejected"] = [event]
    assert not readiness(resolved, result["manifest"])["ready"]
    resolved += (
        f"<!-- dhf-validation:{claim_key(event)} reviewed reviewer=Owner rationale=Rejected -->\n"
    )
    assert readiness(resolved, result["manifest"])["ready"]


def test_docs_pr_push_readiness_recheck_and_merged_baseline(ado_server, tmp_path: Path) -> None:
    ado = ADO(base_url=f"http://127.0.0.1:{ado_server.server_port}/kestrel-org")
    review = DocsReview(ado, tmp_path / "docs-clone")
    result = generate_document(
        "sstr",
        ingest_fixtures(),
        {"release": "1.1"},
        out=tmp_path / "generated",
        llm=LLM(root=tmp_path / "llm"),
    )
    published = review.publish(result, gap_count=16)
    pr_id = published["pr_id"]
    assert not published["readiness"]["ready"]
    assert httpx.get(published["pr_url"]).status_code == 200
    statuses = ado.collection(review.api + f"/{pr_id}/statuses")
    assert statuses[-1]["state"] == "failed"
    assert statuses[-1]["context"]["name"] == "DHF review readiness"
    pr = ado.request("GET", review.api + f"/{pr_id}")
    assert pr["reviewers"] == [{"id": "mock-reviewer", "isRequired": True}]
    assert "Deterministic gaps: 16" in pr["description"]
    with pytest.raises(ValueError, match="human-merged"):
        review.create_baseline("sstr", pr_id)
    files = git_command(["ls-tree", "-r", "--name-only", "HEAD"], review.root).splitlines()
    assert {"sstr.md", "sstr.docx", "sstr.manifest.json"} <= set(files)
    # Simulate a human editing and pushing Markdown in the PR.
    (review.root / "sstr.md").write_text(resolved_markdown(result))
    git_command(["add", "sstr.md"], review.root)
    git_command(
        [
            "-c",
            "user.name=Synthetic Reviewer",
            "-c",
            "user.email=review@example.invalid",
            "commit",
            "-m",
            "Human: resolve draft suggestions",
        ],
        review.root,
    )
    git_command(["push", "origin", "HEAD"], review.root, ado.token)
    assert review.check_pr("sstr", pr_id)["ready"]
    assert ado.collection(review.api + f"/{pr_id}/statuses")[-1]["state"] == "succeeded"
    merged = merge_docs_pr(pr_id, ado_server.root)
    assert merged["status"] == "completed"
    assert review.create_baseline("sstr", pr_id) == "sstr-v1"
    tag, previous = review.baseline("sstr")
    assert tag == "sstr-v1" and previous == (review.root / "sstr.md").read_text()
    manifest = json.loads((review.root / "sstr.manifest.json").read_text())
    assert manifest["review"]["status"] == "ready_for_review"
    ado.close()


def test_clone_location_never_reuses_a_different_remote(tmp_path: Path) -> None:
    from dhf.ingest.ado import clone_location

    root = tmp_path / "clone"
    root.mkdir()
    git_command(["init"], root)
    git_command(["remote", "add", "origin", "/fictional/repo-a.git"], root)
    assert clone_location(root, "/fictional/repo-a.git") == root
    isolated = clone_location(root, "/fictional/repo-b.git")
    assert isolated != root and isolated.parent == root.parent
    assert git_command(["remote", "get-url", "origin"], root) == "/fictional/repo-a.git"
    assert clone_location(root, "/fictional/repo-b.git") == isolated
