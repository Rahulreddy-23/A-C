# Review-board demo · 6 minutes 40 seconds

Synthetic Kestrel evidence, local ADO mock, human review drafts. Set Word to All Markup before presenting. No tenant deployment, approval, risk acceptance or clinical compliance is claimed. The six beats follow the 100-point rubric. Run the offline rehearsal once before the room opens. Browser/laptop verification of the local explorer remains an owner check; the automated DOM contract is not a paint benchmark.

## Preparation (outside the clock)

From a clean clone, with Python 3.12 and uv installed:

```sh
git clone --branch dev https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync --locked
./scripts/demo.sh | tee out-demo.log
uv run python tools/check_demo_pack.py
```

No .env is needed for this offline run; it creates its own empty config and mock. Expected: exit 0, `Snapshot 1: 248 artifacts, 413 links`, `21 deterministic gaps`, `35 RTM rows`, source-write probe `403`, `2 changed, 3 added`, selective regeneration, support coverage 1/1, metrics precision/recall 1.00 and audit `33 verified files`. Read `out/demo-latest.json` for this run's paths. Variable UUIDs, ports, hashes, dates and timing are intentionally not fixed.

Checked-in fallbacks are under `data/demo/fallback/`; their index/checksums are tested. They came from an actual offline run, with source provenance intact. Local source links from that ended mock may no longer resolve; show the ID/revision or the ZIP's immutable snapshots. Never describe fallback playback as a live service operation.

For a paced on-stage run use `./scripts/demo.sh --pause-before-change`. It prints the active root and waits before applying change_1. Use a second terminal for files; press Enter at the change beat. Keep the mock running for source click-through.

## 0:00–1:15 · Traceability (25)

Say: “Every line starts in recorded evidence. This fixture has 248 artifacts and 413 confirmed links. Requirements, units, code changes and tests have stable IDs and revisions; missing links stay visible.”

Show `explorer-baseline.html` in the active run folder. Search SRS-021, select its recorded test/component/control neighbors, and open a source revision. Filter G06 to show RC-12's deliberately missing realization; G07 to show SRS-012's missing verification. These are gaps, not AI-made trace links. Show the RTM revision and unit columns.

Exact commands if using the completed rehearsal:

```sh
dhf_demo_db=$(uv run python -c "import json; print(json.load(open('out/demo-latest.json'))['db'])")
dhf_demo_docs=$(uv run python -c "import json; print(json.load(open('out/demo-latest.json'))['documents'])")
uv run dhf explore --db "$dhf_demo_db" --documents "$dhf_demo_docs" --output out/explorer.html --baseline-file data/synthetic/sad_v1.md
```

For the paused on-stage run, use out/demo-active.json instead of out/demo-latest.json in those two path commands. The demo also logs each exact native command.

Fallback: [baseline explorer](../data/demo/fallback/explorer-baseline.html), [RTM](../data/demo/fallback/rtm.md), and [gap report](../data/demo/fallback/gaps.md). Stop clicking if the local source server is unavailable; show the recorded revision.

## 1:15–2:20 · Workflow fit (25)

Say: “The product reads source systems and writes drafts only to the docs repository. A PR carries Word, Markdown and a provenance manifest. Readiness blocks missing human inputs and unresolved suggestions. An owner review and merge creates the baseline; the product does not approve or merge.”

Show the SSTR and SAD Word drafts, a manifest, and the logged `Product-token source write: 403`. Explain that the local demo's review/merge is explicitly labelled test tooling. The review status is a draft gate; eQMS approval remains separate.

Fallback: [SSTR Word](../data/demo/fallback/sstr.docx), [SAD Word](../data/demo/fallback/sad.docx), [SSTR manifest](../data/demo/fallback/sstr.manifest.json), and [terminal transcript](../data/demo/fallback/transcript.txt).

## 2:20–3:45 · Accuracy and governance (20), live-change moment

Say: “Watch what a source update does. The planted change raises the occlusion requirement and updates the pressure code. A new result and PR enter the graph. We identify stale sections by revision dependencies and deterministic query facts, then regenerate those sections.”

Press Enter in the paused demo. Expected source delta: SRS-021 and UNIT-sensor_pressure changed; PR-8, RUN-3, RES-3-021 added. The pre-regeneration explorer highlights 40 directly stale sections and the five exact causes. The saved report also distinguishes possibly affected neighbors; the 75 total status/cause records match the reviewed expectation.

Show `explorer-stale.html`, then `redline-sstr.docx` with All Markup. In the results table, TC-021 goes from RES-2-021 to RES-3-021. The redline preserves unaffected rows. Show `dhf check` blocking the new unresolved suggestions. Unknown citations/unsupported numbers are rejected; refusals become visible human placeholders.

Fallback: [stale explorer](../data/demo/fallback/explorer-stale.html), [saved impact](../data/demo/fallback/impact.json), [actual tracked Word changes](../data/demo/fallback/redline-sstr.docx), [transcript](../data/demo/fallback/transcript.txt). Say “This is the recorded offline rehearsal” if using these.

## 3:45–4:30 · Effort reduction (10)

Say: “Time and API spend are measured. Manual authoring hours are configurable assumptions, not measured labor savings. Human review is excluded. YAML-only SUTR and RTM extensions demonstrate reuse without changing Python.”

Show the metrics per-document section counts, measured seconds/cost, assumptions and estimated hours saved. SUTR explicitly says the fixture contains no recorded unit-test results; do not imply system tests are unit tests.

Fallback: [metrics](../data/demo/fallback/metrics.md), [manual-effort assumptions](../specs/metrics/manual_effort.yaml), [SUTR Word](../data/demo/fallback/sutr.docx).

## 4:30–5:25 · Audit readiness (10)

Say: “The audit ZIP includes drafts, manifests, all required source revisions, RTM, gaps, explorer, clause coverage and exhaustive SHA256 checksums. Integrity is verified locally. Uncovered clauses and human responsibilities are stated explicitly.”

```sh
uv run python -c "from pathlib import Path; from dhf.review.audit import verify_audit; print(verify_audit(Path('data/demo/fallback/audit-pack.zip')))"
```

Expected `verified_files: 33`, `status: checksums verified; human review pending`. Point at UNCOVERED IEC 62304 §5.5/5.6 and ISO 14971 §6/8. No approval, e-signature or standards certification is implied.

Fallback: [audit ZIP](../data/demo/fallback/audit-pack.zip), [clause appendix](../data/demo/fallback/clause_coverage.md), and its existing verified checksum report in [index](../data/demo/fallback/index.json).

## 5:25–6:40 · Good-to-have and close (10)

Say: “The explorer works without a hosted service. A second-pass support verifier helps reviewers catch a plausible but unsupported claim; its coverage denominator is visible, and its judgement does not gate release.”

Show support/coverage metrics and the live-review observation in [REVIEW.md](REVIEW.md): the SDD alarm-latch error section claimed invalid-input rejection without that handling in the cited code. Attribute that finding to the reviewer's live run; the fallback metrics are mock lexical checks. Unsupported prose remains visible with advisory flags/comments. A failed explanation gets one budgeted repair, then a warning; the verdict is retained.

Show the [Copilot Studio build plan](../port/copilot_studio/BUILD_PLAN.md), the ready-to-paste day-1 kit when M15 is available, and [onboarding](REAL_DATA_ONBOARDING.md). End: “The local pipeline is reproducible; tenant capabilities and governance are explicit day-1 gates. Reviewers retain every decision.”

Fallback: the same checked-in metrics, review log and port plan. Do not substitute offline contract tests for tenant execution.

## Optional paid rehearsal

```sh
./scripts/demo.sh --live
# Optional secondary provider, with its configured key/models:
DHF_LIVE_PROVIDER=anthropic ./scripts/demo.sh --live
```

Only this explicit flag calls paid models through dhf. OpenAI defaults: gpt-4.1-mini with configured analytical gpt-5.4-mini; no price/model overrides are silently added. Sources remain the synthetic local mock. Paid mode retains owner .env and uses shared out/ledger.json/cache. Each command gets only the remaining whole-demo $0.25 run cap; the existing $1.50 build guard and actual-plus-reserved provider caps ($2.50 Anthropic, $4 OpenAI) remain enforced. A refused/unavailable section or insufficient headroom stops the rehearsal with a fallback hint. It does not retry refusals or raise the cap. Tests never call paid APIs. A complete paid rehearsal is optional, not claimed from the offline dry run.
