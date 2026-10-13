"""Offline synthetic demo tooling; owner review/merge simulation never enters src/."""

import hashlib
import json
import os
import sys
import threading
import uuid
from pathlib import Path

from mock_ado.server import Server
from mock_ado.state import apply_scenario, merge_docs_pr
from typer.testing import CliRunner

from dhf.cli import app
from dhf.config import load_env
from dhf.ingest.ado import ADO, git_command
from dhf.review import DocsReview, claim_key


def python_hashes() -> dict:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path("src").rglob("*.py")}


def human_fixture_review(result: dict) -> str:
    text = result["markdown"].replace("**[Suggested — review required]** ", "")
    for section in result["manifest"]["sections"]:
        decisions = "".join(
            f"<!-- dhf-resolution:{claim_key(c)} accepted reviewer=SyntheticDemoReviewer "
            "rationale=Fixture draft completeness reviewed; eQMS approval pending -->\n"
            for c in section["claims"]
            if c["kind"] == "suggested"
        )
        text = text.replace(
            "<!-- endsection:" + section["id"] + " -->",
            decisions + "<!-- endsection:" + section["id"] + " -->",
        )
    return text.replace(
        "[Human input required — complete in the controlled review workflow.]",
        "Synthetic reviewer supplied draft content. eQMS approval remains pending.",
    )


def run_demo() -> dict:
    root = Path("out/demo") / uuid.uuid4().hex[:10]
    root.mkdir(parents=True)
    empty = root / "empty.env"
    empty.write_text("")
    os.environ.update(
        {
            "DHF_ENV_FILE": str(empty),
            "APP_ADO_PAT": "mock-app-token",
            "ADO_PROJECT": "Kestrel",
            "ADO_DOCS_REPO": "kestrel-dhf-docs",
            "DHF_MODEL_MOCK": "mock-v2",
            "DHF_CACHE_ROOT": str(root / "llm"),
        }
    )
    load_env.cache_clear()
    server = Server(root / "mock", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    os.environ["ADO_BASE_URL"] = f"http://127.0.0.1:{server.server_port}/kestrel-org"
    db = root / "evidence.sqlite"
    docs = root / "documents"
    docs.mkdir()
    runner = CliRunner()
    ado = ADO()

    def command(args: list[str], expected_exit: int = 0) -> str:
        print("$ dhf " + " ".join(args), flush=True)
        result = runner.invoke(app, args)
        print(result.output, flush=True)
        if result.exit_code != expected_exit:
            raise RuntimeError(f"Demo command failed: {args[0]}: {result.exception}")
        return result.output

    try:
        print(f"Synthetic local demo: {root}; native mock port {server.server_port}", flush=True)
        command(["ingest", "--db", str(db)])
        for doc in ("sstr", "sad", "sdd", "sfmea"):
            command(["generate", doc, "--db", str(db), "--documents", str(docs), "--open-pr"])
        command(["gaps", "--db", str(db)])
        command(["rtm", "--db", str(db)])
        command(["propose", "--db", str(db), "--documents", str(docs)])
        command(
            [
                "generate",
                "drr",
                "--db",
                str(db),
                "--documents",
                str(docs),
                "--input-file",
                "data/synthetic/review_input.json",
                "--since",
                "1",
            ]
        )
        command(["consistency", "--db", str(db), "--documents", str(docs)])
        # A product-token source write must be denied by the actual native endpoint.
        import httpx

        response = httpx.patch(
            os.environ["ADO_BASE_URL"] + "/_apis/wit/workitems/1",
            auth=("", "mock-app-token"),
            json=[],
        )
        assert response.status_code == 403
        print("Product-token source write: 403", flush=True)
        print(
            "DEMO TOOLING: simulate reviewer draft completion and owner merge in local mock only.",
            flush=True,
        )
        for doc in ("sstr", "sad", "sdd", "sfmea"):
            manifest = json.loads((docs / (doc + ".manifest.json")).read_text())
            result = {"manifest": manifest, "markdown": (docs / (doc + ".md")).read_text()}
            review = DocsReview(ado)
            pr = (
                manifest["review"]["pr_id"]
                if "pr_id" in manifest["review"]
                else manifest["review"]["pr_url"].rsplit("/", 1)[1]
            )
            pr = int(pr)
            initial = review.check_pr(doc, pr)
            if doc != "sdd":
                assert not initial["ready"]
            edited = human_fixture_review(result)
            (review.root / (doc + ".md")).write_text(edited)
            git_command(["add", doc + ".md"], review.root)
            git_command(
                [
                    "-c",
                    "user.name=Synthetic Owner",
                    "-c",
                    "user.email=owner@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "Human: fixture draft review",
                ],
                review.root,
            )
            git_command(["push", "origin", "HEAD"], review.root, ado.token)
            assert review.check_pr(doc, pr)["ready"]
            # Other drafts were opened before earlier merges. The simulated owner
            # rebases its own local docs branch before the mock's fast-forward merge.
            git_command(["fetch", "origin", "main"], review.root, ado.token)
            git_command(["rebase", "origin/main"], review.root)
            git_command(["push", "--force-with-lease", "origin", "HEAD"], review.root, ado.token)
            merge_docs_pr(pr, server.root)
            tag = review.create_baseline(doc, pr)
            (docs / (doc + ".md")).write_text(edited)
            (docs / (doc + ".manifest.json")).write_bytes(
                (review.root / (doc + ".manifest.json")).read_bytes()
            )
            (docs / (doc + ".docx")).write_bytes((review.root / (doc + ".docx")).read_bytes())
            print(f"Mock owner baseline: {tag}", flush=True)
        # DRR is generated again after the source change, outside the four impact demo docs.
        review_docs = root / "review"
        review_docs.mkdir()
        for suffix in (".md", ".docx", ".manifest.json"):
            (review_docs / ("drr" + suffix)).write_bytes((docs / ("drr" + suffix)).read_bytes())
            (docs / ("drr" + suffix)).unlink()
        timer = threading.Timer(2, apply_scenario, args=("change_1", server.root))
        timer.start()
        command(
            ["watch", "--cycles", "2", "--interval", "3", "--db", str(db), "--documents", str(docs)]
        )
        timer.join()
        saved = root / "impact-before-regeneration.json"
        from dhf.cli import document_impacts

        _, own_reports = document_impacts(str(db), str(docs))
        saved.write_text(json.dumps(own_reports, indent=2))
        command(["regenerate", "--stale", "--open-pr", "--db", str(db), "--documents", str(docs)])
        sstr = json.loads((docs / "sstr.manifest.json").read_text())
        command(
            ["check", "sstr", "--pr-id", str(int(sstr["review"]["pr_url"].rsplit("/", 1)[1]))],
            expected_exit=1,
        )
        before = python_hashes()
        for doc in ("sutr", "rtm"):
            command(["generate", doc, "--db", str(db), "--documents", str(docs)])
        assert python_hashes() == before
        print(
            "YAML extensibility: Python files unchanged; "
            "SUTR reports missing recorded unit results.",
            flush=True,
        )
        command(
            [
                "generate",
                "drr",
                "--db",
                str(db),
                "--documents",
                str(docs),
                "--input-file",
                "data/synthetic/review_input.json",
                "--since",
                "1",
                "--impact-file",
                str(saved),
            ]
        )
        command(["eval", "--db", str(db), "--documents", str(docs), "--impact-file", str(saved)])
        metrics = json.loads(Path("out/metrics.json").read_text())
        assert metrics["unknown_id_count"] == 0
        assert metrics["gap_detection"]["precision"] == metrics["gap_detection"]["recall"] == 1
        assert (
            metrics["impact_detection"]["precision"] == metrics["impact_detection"]["recall"] == 1
        )
        assert all(not d["ai_unavailable"] for d in metrics["documents"])
        command(
            [
                "audit-pack",
                "--db",
                str(db),
                "--documents",
                str(docs),
                "--output",
                str(root / "audit-pack.zip"),
            ]
        )
        result = {
            "root": str(root),
            "documents": str(docs),
            "db": str(db),
            "impact": str(saved),
            "metrics": "out/metrics.md",
            "audit": str(root / "audit-pack.zip"),
            "status": "drafts require human review",
        }
        (root / "run.json").write_text(json.dumps(result, indent=2))
        Path("out/demo-latest.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2), flush=True)
        return result
    finally:
        ado.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit("demo.sh takes no arguments; each run owns a fresh out/demo folder")
    run_demo()
