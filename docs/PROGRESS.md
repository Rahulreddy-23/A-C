# Build Progress
## Status
Current milestone: M5 (in progress) · Last updated: 2026-10-12 IST
## Milestones
| M | Status | Tag | Commit | Notes |
|---|---|---|---|---|
| M0 | done | m0-done | 98aa27a | Local checks and GitHub Actions green |
| M1 | done | m1-done | 6969c55 | Refreshed evidence in b74d84b after R-010 |
| M2 | done | m2-done (refreshed) | cfed7c3 | Native ADO parity, including metadata stripped, verified |
| M3 | done | m3-done | eb0f00c | 16 exact gaps; RTM golden verified |
| M4 | done | m4-done | see tag | 12-section SSTR and exact deterministic golden |
## Now / Next
- Working on: final M5 checkpoint; R-019/R-020 and pre-M6 follow-ups are fixed.
- Next: M6 SAD/SDD, local diagrams and component consistency.
## Acceptance evidence
### M0
- `uv run dhf --help` → `Usage: dhf [OPTIONS] COMMAND [ARGS]...`; `version` listed.
- `uv run pytest` → `5 passed in 0.09s`. Schema validity, cache miss/hit/version invalidation, ledger persistence, cumulative per-run cap, build cap and 80% hard stop covered.
- `uv run ruff check .` → `All checks passed!`
- `uv run ruff format --check .` → `20 files already formatted`.
- `.env` and attached PDF → `git check-ignore` prints both paths.
- CI workflow uses the same checks with mock provider. GitHub Actions passed (verified independently by reviewer).

### M0 review fixes
- `uv run pytest` → `8 passed in 1.81s`. Cache collision and prompt-edit regressions, memoized isolated config, loopback-only sockets and blocked actual provider transport tested.
- Reviewer independently verified GitHub Actions runs 38280581197 and 38280582320 passed.
- Provider review regression suite: `uv run pytest` → `11 passed in 1.01s`; ruff → `All checks passed!`, `47 files already formatted`. No paid calls. R-003–R-006 fixed in 688a1c3.
### M1
- `uv run mock-ado init` → `Mock initialized: 126 work items, 2 runs, 7 PRs`.
- `uv run python -m mock_ado.validate` → `{'artifacts': 248, 'links': 473, 'answer_key': 'exact', 'rules': 11}`.
- `uv run pytest` → `17 passed in 11.47s`. HTTP contracts exercise WIQL, batch, get/revisions, run/results, repos, PR list/workitems/create/status, HTML, admin reset/scenario, app-token 403 and device Git push denial. Scenario adds PR 8, run 3 and a changed commit; SRS-021 rev 1 → 2; repeat scenario is idempotent.
- `uv run ruff check .` → `All checks passed!`; format → `54 files already formatted`.
- `src/` has no mock admin endpoint references or tooling imports (test enforced).
### M2
- `uv run dhf ingest --source fixtures` → `{'snapshot': 1, 'changed': [], ... 'removed': [], 'artifacts': 248, 'links': 473}`. Full added-ID list is in the command output; no invented source IDs.
- `uv run pytest` → `22 passed in 15.78s`; ruff → `All checks passed!`, `56 files already formatted`.
- `test_fixture_http_graph_parity_and_exact_changes`: all artifact bodies/attributes/content hashes, types, source systems/revisions and trace endpoints match. Only URL/native ID, retrieval time and source-specific link-evidence description are normalized. Re-ingest is unchanged; scenario changes exactly SRS-021 and UNIT-sensor_pressure and adds PR-8, RUN-3, RES-3-021. Snapshots survive SQLite reopen.
- Real-source AST extraction lacks the synthetic flag; hash tampering and source-write attempts are rejected.
- R-008 fixed in 4064754; fake env-file keys reach both SDK client constructors, missing keys fail before transport.
### M2 review refresh — R-009, R-010, R-011
- `uv run pytest` → `25 passed in 24.29s`. This is the exact M2 tree; paused M3 prototypes are excluded.
- `test_metadata_stripped_equivalent_graph` passes: removing all DHF-META blobs preserves artifact semantics, hashes, source revisions and typed trace links. Native severity 5, Sensor Monitoring allocation and occlusion acceptance criteria remain present.
- `uv run python -m mock_ado.validate` → `{'artifacts': 248, 'links': 473, 'answer_key': 'exact', 'rules': 11}`.
- `PYTHONPATH=data/synthetic/code uv run pytest data/synthetic/code/tests` → `6 passed in 0.01s`. Dwell boundary, safe acknowledgement, inhibited sensor faults, atomic configuration and volume clamp verified.
- `uv run ruff check .` → `All checks passed!`; format → `58 files already formatted`.
- R-009/R-010/R-011 implementation: b74d84b; m2-done is re-tagged on the review-resolution checkpoint. Original c43b213 remains in dev history.
### M3
- `uv run dhf gaps` → `16 deterministic gaps → out/gaps.md + out/gaps.json`.
- `uv run dhf rtm` → `35 RTM rows → out/rtm.md + out/rtm.json`.
- `score_findings` over the ingested graph → `{'precision': 1.0, 'recall': 1.0, 'true_positive': 16, 'false_positive': 0, 'false_negative': 0}`.
- `test_rtm_matches_hand_checked_rows` validates five independent boundary/example rows. Release 1.0 totals 40/38 passed/2 failed; release 1.1 totals 40/39 passed/1 failed; SRS test coverage is 31/35 (88.57%).
- `uv run pytest` → `28 passed in 24.05s`; ruff → `All checks passed!`, `60 files already formatted`.


### M4
- `uv run pytest` → `31 passed in 24.58s` (offline HTTP contracts and all claim-validator rules).
- `uv run ruff check .` → `All checks passed!`; `uv run ruff format --check .` → `68 files already formatted`.
- `dhf ingest --source fixtures --db out/m4.sqlite` → `Snapshot 1: 248 artifacts, 473 links`; compact per-type added/changed/removed counts.
- `dhf generate sstr --release 1.1 --db out/m4.sqlite` → `sstr: 12 sections → out/documents/sstr.md + manifest`; `Validation: {'rejected': 0, 'downgraded': 0, 'coerced': 0}`.
- Golden deterministic summary: `{'release': '1.1', 'total': 40, 'passed': 39, 'failed': 1, 'blocked': 0, 'not_run': 0}`. Seven deterministic sections match `eval/golden/sstr_deterministic.json` exactly. Unknown IDs in rendered Markdown: zero, asserted against the graph.
- Repeat generation produces byte-identical Markdown with zero new calls. Prompt budgets are enforced with referenced context retained; oversized artifacts fail explicitly.
- `dhf generate-section sstr purpose_scope --db out/m4.sqlite` → `3 validated claims; $0.000000 → out/cross-provider/sstr-purpose_scope-mock.json`.
- `dhf rtm --db out/m4.sqlite` → `35 RTM rows → out/rtm.md + out/rtm.json`; Markdown includes linked requirement, revision, components, units, changes, tests and latest results.
- `dhf gaps --db out/m4.sqlite` → `16 deterministic gaps → out/gaps.md + out/gaps.json`; per-rule summary and recommended actions now come from YAML (R-014).

### M4 live verification
- Reviewer live check exposed R-019–R-024; guarded retests and fixes are recorded below. Tests never use paid APIs.

### Live-review fixes R-019/R-020
- `pytest tests/test_llm.py tests/test_generate.py -q` → `22 passed in 4.12s`.
- Provider schemas have no minimum/maximum/exclusive bound keywords; local Pydantic rejects confidence outside 0–1.
- Parameterized refusal/max_tokens/unparseable/provider_error tests preserve all 12 sections and the manifest, record ai_unavailable/category, block readiness and make exactly one failed attempt.
- Single live `dhf generate-section sstr residual_anomalies --provider anthropic --db out/m4.sqlite` → `0 validated claims; $0.002416 → out/cross-provider/sstr-residual_anomalies-anthropic.json`.
- Output status: `ai_unavailable`; reason `refusal`; `stop_details.category: bio`. The request passed schema validation, but drafting remains manual. No further refusal retries.
- The displayed failed-call cost is a retained worst-case reservation, not an actual provider invoice. Prior reviewer live checks were merged into `out/ledger.json` (actual Anthropic $0.0128976, OpenAI $0.000328 before this retry).

- Full review-fix regression: `uv run pytest` → `41 passed in 32.44s`; ruff check/format clean. M5 remains in progress; its visual and CLI acceptance is still to finish.

## Pending live verification
- Full-document paid-provider narrative review remains optional; single-section OpenAI and Anthropic checks are recorded below. Tests and offline demo use mock.
- Real ADO M11 — needs a real org; not part of the offline build.
## Known issues
## Deviations from BRIEF (with reason)
- Synthetic fixture has 20 units and 4 unverified SRS (including risk control SRS-012), meeting the approximate sizes and at-least gap requirements.
- Local contract tests require sandbox elevation for loopback bind. The test fixture still blocks all external sockets.
- Default ADO fields, native revisions/history, area allocation and residual tags are mapped in YAML. Optional fixture metadata now holds only a synthetic marker; all product facts come from native evidence (ADR-010 supersedes ADR-008).
- uv was absent; installed inside ignored `out/bin` for this workstation. CI uses setup-uv.
## LLM spend (from out/ledger.json)
| Provider | Spent | Cap |
|---|---|---|
| anthropic | $0.0137161 actual + $0.0096725 reserved | $1.50 build / $4 hard stop |
| openai | $0.0023408 actual + $0.0021046 reserved | $1.50 build / $4 hard stop |

### M5
- `dhf ingest --source ado --db out/m5-acceptance.sqlite` → `Snapshot 3: 248 artifacts, 473 links`; added/changed/removed all zero.
- `dhf generate sstr --release 1.1 --db out/m5-acceptance.sqlite --open-pr` → 12 sections, zero validation rejects/downgrades/coercions/normalizations; PR 10 visible via API and HTML, 9 readiness blockers. The isolated HTTP server used port 54064; acceptance URL is historical test evidence.
- `dhf check sstr --pr-id 10` → exit 1, `ready: false`, 9 blockers. After a test-only human edit with explicit dispositions: exit 0, `ready: true`, zero blockers; PR status succeeded. Test tooling simulated owner merge; product never merges.
- `dhf baseline sstr --pr-id 10` → `sstr-v2`; md/docx/manifest exist in docs Git branch. DOCX hash matches the published manifest.
- OOXML round-trip tests prove real insertions/deletions, cited comments, highlights and hyperlinks. Local bundled LibreOffice rendered the final 11-page fresh SSTR and one-page redline; all PNG pages inspected, no layout overflow. Redline sample reports 2 insertions, 1 deletion and 2 comments; fresh drafts have no artificial full-document insertion. Desktop Word UI remains unverified.
- R-016/R-017/R-021/R-022: bounded one-call synthesis, claim caps, human-labelled properties, linked table IDs, short displayed revisions and prompt examples verified. Seven deterministic sections match the revised golden exactly.
- R-023: sanitized SDK-error/CLI tests and cumulative token accounting verified; pre-fix token counts cannot be reconstructed.
- R-024: exact unique source URL citations normalize with audit events; lookalikes remain rejected. Mini defaults and prices updated without editing .env. First guarded anomaly check: `6 validated claims; $0.001052`; inspection found a false missing-link statement. Injecting explicit defect links and revising instructions produced `5 validated claims; $0.000960` with the sourced result/defect association citing both IDs and zero validation events. Prose still needs human review.
