# Review-board demo · 6 minutes 40 seconds

Synthetic Kestrel evidence, local ADO mock, human review drafts. Set Word to All Markup before presenting. **Official AI path:** BD-approved Basic GPT through the BD tenant's Copilot Studio/Power Automate prompt, using HTTP first; if DLP blocks HTTP, use the OneDrive document exchange; if neither flow runs, use the native Copilot Studio two-section MVP (option A) and label every other draft **structural mock or personal-API development output**. This repository has not run in the tenant. No tenant deployment, approval, risk acceptance or clinical compliance is claimed until the owner records the real run. The six beats follow the 100-point rubric. Run the offline rehearsal once before the room opens. Browser/laptop verification of the local explorer remains an owner check; the automated DOM contract is not a paint benchmark.

## Preparation (outside the clock)

From a clean clone, with Python 3.12 and uv installed:

```sh
git clone --branch dev https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync --locked
./scripts/demo.sh | tee out-demo.log
uv run python tools/check_demo_pack.py
```

No .env is needed for this **structural rehearsal**; it creates its own empty config and mock. Its AI prose is mock output and is **outside the official AI evidence path**. Expected: exit 0, `Snapshot 1: 248 artifacts, 413 links`, `21 deterministic gaps`, `35 RTM rows`, source-write probe `403`, `2 changed, 3 added`, selective regeneration, support coverage 1/1, metrics precision/recall 1.00 and audit `33 verified files`. Read `out/demo-latest.json` for this run's paths. Variable UUIDs, ports, hashes, dates and timing are intentionally not fixed.

Checked-in fallbacks are under `data/demo/fallback/`; their index/checksums are tested. They came from an actual offline run, with source provenance intact. Local source links from that ended mock may no longer resolve; show the ID/revision or the ZIP's immutable snapshots. Never describe fallback playback as a live service operation.

Before the official run, the owner creates the [generic prompt](../port/copilot_studio/day1/generic_prompt.md) and either the [HTTP flow](../port/copilot_studio/day1/http_prompt_flow.md) or [OneDrive flow](../port/copilot_studio/day1/onedrive_prompt_flow.md), verifies the tenant-reported model and whether the action exposes token usage, uses `DHF_COPILOT_USAGE=reported` when measured counts are exposed or `estimated` with omitted counts otherwise, checks **Monitor** headroom, and records which transport and usage modes passed. Keep the signed flow URL in ignored `.env`; never show it on stage. Preview one exact synthetic section payload with `uv run dhf copilot-request sstr anomaly_assessment --db out/evidence.sqlite`. With verified tenant access, run:

```sh
DHF_LIVE_PROVIDER=copilotstudio ./scripts/demo.sh --live --pause-before-change
```

For folder mode, set `DHF_COPILOT_MODE=folder` and `DHF_COPILOT_EXCHANGE_DIR` in `.env` first. The command prints the active root and waits before applying change_1. Use a second terminal for files; press Enter at the change beat. Keep the mock running for source click-through. Inspect each manifest's `model.provider`, section `model.name` and `model.tier`; only `copilotstudio`/tenant-reported Basic GPT sections qualify as official AI prose. Check each manifest’s `usage_source` (`reported`, `estimated`, or `mixed`), the metrics’ **Copilot estimated credits**, and tenant Monitor after the rehearsal. A refused/failed section remains a human placeholder.

Capture a **real tenant** screenshot of the Copilot Studio agent test pane showing “Draft the release test report” → queued/run status → actual draft or PR link; keep it in the owner-controlled demo folder for a network fallback. No screenshot is supplied or simulated by this repo. If both model-runner flows are blocked, use the [native two-section MVP](../port/copilot_studio/day1/click_path_tier_b.md) in the agent pane and show its real screenshot if one exists. The remaining reference artifacts can illustrate deterministic workflow, but label their AI prose as non-tenant development output.

## 0:00–1:15 · Traceability (25)

Say: “Every line starts in recorded evidence. This fixture has 248 artifacts and 413 confirmed links. Requirements, units, code changes and tests have stable IDs and revisions; missing links stay visible.”

Show `explorer-baseline.html` in the active run folder. Start on Overview for actual coverage and verification counts. Open Findings and filter G06 to show RC-12's deliberately missing realization; G07 shows SRS-012's missing verification. In Traceability, use Find artifact to search SRS-021, inspect its direct arrows and relationship types, then select Full trace for the wider context. Click selects source details; double-click or Focus trace recenters the context. Evidence opens the complete artifact index. These are gaps, not AI-made trace links. Show the RTM revision and unit columns.

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

Fallback: [SSTR Word](../data/demo/fallback/sstr.docx), [SAD Word](../data/demo/fallback/sad.docx), [SSTR manifest](../data/demo/fallback/sstr.manifest.json), and [terminal transcript](../data/demo/fallback/transcript.txt). Their AI prose is structural mock output; do not attribute it to BD-approved models.

## 2:20–3:45 · Accuracy and governance (20), live-change moment

Say: “Watch what a source update does. The planted change raises the occlusion requirement and updates the pressure code. A new result and PR enter the graph. We identify stale sections by revision dependencies and deterministic query facts, then regenerate those sections.”

Press Enter in the paused demo. Expected source delta: SRS-021 and UNIT-sensor_pressure changed; PR-8, RUN-3, RES-3-021 added. The pre-regeneration explorer highlights 40 directly stale sections and the five exact causes. The saved report also distinguishes possibly affected neighbors; the 75 total status/cause records match the reviewed expectation.

Show Change impact in `explorer-stale.html` for directly stale versus possibly affected sections and their exact causes. Documents exposes generated sections and typed claims with citation revisions; Risk evidence shows recorded control paths without accepting residual risk. Then open `redline-sstr.docx` with All Markup. In the results table, TC-021 goes from RES-2-021 to RES-3-021. The redline preserves unaffected rows. Show `dhf check` blocking the new unresolved suggestions. Unknown citations/unsupported numbers are rejected; refusals become visible human placeholders.

Fallback: [stale explorer](../data/demo/fallback/explorer-stale.html), [saved impact](../data/demo/fallback/impact.json), [actual tracked Word changes](../data/demo/fallback/redline-sstr.docx), [transcript](../data/demo/fallback/transcript.txt). Say “This is the recorded offline rehearsal; its AI prose is structural mock output” if using these.

## 3:45–4:30 · Effort reduction (10)

Say: “Time and API spend are measured. Manual authoring hours are configurable assumptions, not measured labor savings. Human review is excluded. YAML-only SUTR and RTM extensions demonstrate reuse without changing Python.”

Show the metrics per-document section counts, measured seconds/cost, assumptions and estimated hours saved. SUTR explicitly says the fixture contains no recorded unit-test results; do not imply system tests are unit tests.

Fallback: [metrics](../data/demo/fallback/metrics.md), [manual-effort assumptions](../specs/metrics/manual_effort.yaml), [SUTR Word](../data/demo/fallback/sutr.docx). Mock provider cost is not tenant Copilot Credit billing.

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

**Copilot Studio agent beat:** in the real tenant test pane or allowed Teams channel, ask “Draft the release test report”, show the queued ID, then ask for status and open the actual PR/SharePoint draft link. This thin agent calls the same governed flows; it does not invent the report in chat. If the tenant view fails during the presentation, show only the owner's previously captured real screenshot, state when it was captured, and use the local reference to explain the deterministic pipeline. If there was no tenant run, say the agent beat is pending and show the [day-1 build plan](../port/copilot_studio/BUILD_PLAN.md) as a plan, not proof. End: “The reference pipeline is reproducible; reviewers retain every decision.”

Fallback: the same checked-in metrics, review log and port plan, plus an owner-captured tenant screenshot **only if one exists**. Do not substitute offline contract tests or a fabricated screenshot for tenant execution.

## Optional personal-API development rehearsal — not the official AI path

```sh
DHF_LIVE_PROVIDER=openai ./scripts/demo.sh --live
# Optional secondary provider, with its configured key/models:
DHF_LIVE_PROVIDER=anthropic ./scripts/demo.sh --live
```

Only this explicit flag calls paid models through dhf. **Personal OpenAI/Anthropic outputs must never be presented as the official BD-approved AI result.** OpenAI defaults: gpt-4.1-mini with configured analytical gpt-5.4-mini; no price/model overrides are silently added. Sources remain the synthetic local mock. Paid mode retains owner .env and uses shared out/ledger.json/cache. Each command gets only the remaining whole-demo $0.25 run cap; the existing $1.50 build guard and actual-plus-reserved provider caps ($2.50 Anthropic, $4 OpenAI) remain enforced. A refused/unavailable section or insufficient headroom stops the rehearsal with a fallback hint. It does not retry refusals or raise the cap. Tests never call paid APIs. A complete paid rehearsal is optional, not claimed from the offline dry run.
