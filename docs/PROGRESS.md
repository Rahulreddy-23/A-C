# Build Progress
## Status
Current milestone: M8 (done) · Development resumed by owner · Last updated: 2026-10-13 IST
## Milestones
| M | Status | Tag | Commit | Notes |
|---|---|---|---|---|
| M0 | done | m0-done | 98aa27a | Local checks and GitHub Actions green |
| M1 | done | m1-done | 6969c55 | Refreshed evidence in b74d84b after R-010 |
| M2 | done | m2-done (refreshed) | cfed7c3 | Native ADO parity, including metadata stripped, verified |
| M3 | done | m3-done | eb0f00c | 16 exact gaps; RTM golden verified |
| M4 | done | m4-done | bfae4d5 | 12-section SSTR and exact deterministic golden |
| M5 | done (refreshed) | m5-done | 18ee5e8 implementation | Localized change_1 redlines; token budgets; review fixes |
| M6 | done | m6-done | c98915a | SAD/SDD, allocations and local diagram source |
| M7 | done | m7-done | 3bde3d8 | Native watch, exact impact, selective PRs and C01–C04 |
| M8 | done | m8-done | b82108b | DRR, sFMEA, proposals and readability fixes |
## Now / Next
- Working on: M6 complete; starting M7 impact and selective regeneration.
- Next: M7 impact and selective regeneration, then M8–M10. The restored stash remains as a backup.
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


### M5
- `dhf ingest --source ado --db out/m5-acceptance.sqlite` → `Snapshot 3: 248 artifacts, 473 links`; added/changed/removed all zero.
- `dhf generate sstr --release 1.1 --db out/m5-acceptance.sqlite --open-pr` → 12 sections, zero validation rejects/downgrades/coercions/normalizations; PR 10 visible via API and HTML, 9 readiness blockers. The isolated HTTP server used port 54064; acceptance URL is historical test evidence.
- `dhf check sstr --pr-id 10` → exit 1, `ready: false`, 9 blockers. After a test-only human edit with explicit dispositions: exit 0, `ready: true`, zero blockers; PR status succeeded. Test tooling simulated owner merge; product never merges.
- `dhf baseline sstr --pr-id 10` → `sstr-v2`; md/docx/manifest exist in docs Git branch. DOCX hash matches the published manifest.
- OOXML round-trip tests prove real insertions/deletions, cited comments, highlights and hyperlinks. Local bundled LibreOffice rendered the final 11-page fresh SSTR and one-page redline; all PNG pages inspected, no layout overflow. Redline sample reports 2 insertions, 1 deletion and 2 comments; fresh drafts have no artificial full-document insertion. Desktop Word UI remains unverified.
- R-016/R-017/R-021/R-022: bounded one-call synthesis, claim caps, human-labelled properties, linked table IDs, short displayed revisions and prompt examples verified. Seven deterministic sections match the revised golden exactly.
- R-023: sanitized SDK-error/CLI tests and cumulative token accounting verified; pre-fix token counts cannot be reconstructed.
- R-024: exact unique source URL citations normalize with audit events; lookalikes remain rejected. Mini defaults and prices updated without editing .env. First guarded anomaly check: `6 validated claims; $0.001052`; inspection found a false missing-link statement. Injecting explicit defect links and revising instructions produced `5 validated claims; $0.000960` with the sourced result/defect association citing both IDs and zero validation events. Prose still needs human review.

- Final M5 regression: `uv run pytest -q` → `45 passed in 34.44s`; ruff → `All checks passed!`, `73 files already formatted`.

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

### M5 refresh — R-025/R-026 (plus touched-area R-027/R-028)
- `uv run pytest -q -s` → `52 passed in 39.34s`; exact HTTP scenario regression: `redline: 46/744 paragraphs; 15/175 rows; {'insertions': 30, 'deletions': 16, 'comments': 7}`. Changes are under 10%, confined to affected rows/sections; hyperlink-only changes have zero tracked edits.
- `uv run ruff check .` → `All checks passed!`; `ruff format --check .` → `75 files already formatted`.
- CLI acceptance on a fresh isolated mock: `dhf ingest --source ado --db out/m5-refresh.sqlite` → snapshot 1, 248 artifacts/473 links; `dhf generate sstr` → 12 sections, zero validation events.
- `apply_scenario('change_1')` → `{'applied': 'change_1', 'revision': 2, 'pr': 8, 'run': 3}`. Re-ingest → snapshot 2, 251 artifacts/476 links; three added and two changed (`SRS-021`, `UNIT-sensor_pressure`), zero removed.
- `dhf generate sstr --db out/m5-refresh.sqlite --open-pr` → 12 sections, zero validation events; mock docs PR 9, nine ordinary unresolved human/suggestion blockers. `AI unavailable sections: 0`; summary `total: 40, passed: 38, failed: 2`. No paid calls were made. The acceptance server is now stopped.
- `out/redline-check/sstr-change_1.docx` rendered locally to 12 PNG pages; every page inspected. Requirement revision, unit revisions, latest result and summary changes are visible; unaffected table cells retain their normal text. Nested tracked hyperlink runs fixed a local-render blank-label defect. Desktop Word UI remains unverified.
- Synthesis reduction is tested with artificially expanded source narratives, preserves critical evidence and gap facts, records omitted IDs/injected counts/excerpts, and is deterministic. Separate failure tests cover evidence_over_budget, invalid_output and budget_exceeded with safe internal messages.
- R-027: sourced citations remain hyperlinks without comments. Review comments retain basis/confidence; placeholders receive a review comment. Scenario redline has seven comments. R-028: only the conclusion carries conclusion-specific instructions; all SSTR prompt versions are now 2.
- Paused M6 smoke test had one unverified allocation expectation; it is not counted as acceptance evidence. Resume by inspecting/applying the preserved stash and resolving conflicts with these M5 fixes, then verify M6 fully.

- Implementation and R-025–R-028 resolutions: 18ee5e8. m5-done is refreshed on the resolution checkpoint. M6 remains paused; no m6-done tag is claimed.

### M6
- Restored the named M6 stash without conflicts after committing the current review file in dd41a81. The stash remains as a backup.
- `uv run pytest -q` → `53 passed in 41.49s`; ruff → `All checks passed!`, `88 files already formatted`.
- `dhf generate sad --db out/m6.sqlite` → `sad: 28 sections`; `dhf generate sdd --db out/m6.sqlite` → `sdd: 162 sections`; both report zero validation events. All six components and twenty units are represented, with deterministic allocations and extracted signatures/data structures.
- `dhf consistency --db out/m6.sqlite` → `0 consistency findings`. Test removes COMP-06 from a manifest and proves C01 detects it.
- `python -m mock_ado.validate` → `{'artifacts': 248, 'links': 473, 'answer_key': 'exact', 'rules': 11}` after the diagnostics_trace rename and natural BUG-03 wording (R-018).
- Architecture diagram is a checksummed local Mermaid source file with 26 nodes and 20 explicit allocation edges; no online renderer. Five SOUP entries use parsed dependency versions. Unit verification tables honestly state the absence of explicitly linked unit-level tests.
- Local LibreOffice renders inspected: SAD 11 pages; final compact SDD 28 pages. PDF text extraction confirms full unit labels and source claims. Desktop Word visual verification remains pending.
- R-029 regression: change_1 anomaly table contains RES-2-008 and RES-3-021, with the missing defect explicitly shown as `none — see G05`; offline narrative cites both. The complete deterministic table precedes any AI failure placeholder.
- Mock model version is mock-v2 to invalidate obsolete cached narratives; mock prose is a structural demonstration and still requires human review. No paid calls made.

### M7
- `uv run pytest -q` → `55 passed in 62.97s`; ruff → `All checks passed!`, `90 files already formatted`.
- Live-loopback watch regression applies change_1 during a two-cycle watcher: two changed artifacts, three added. The frozen expected fixture distinguishes direct staleness from one-hop possible impact and records changed artifact causes (R-012).
- `dhf impact` → SAD 6 stale / 3 possibly affected; SDD 12 stale / 21 possibly affected; SSTR 9 stale / 0 possibly affected. Deterministic query-fact changes include added results/run membership, not just old citations.
- `dhf regenerate --stale --open-pr` → SAD 6 sections, PR 9; SDD 12 sections, PR 10; SSTR 9 sections, PR 11. Isolated CLI server port 64147; URLs are historical evidence. No paid calls.
- Regression simulates owner review/merge/tag before changing source. Unchanged section Markdown is byte-identical to the approved baseline, including a human edit. PR metadata names only stale sections. Source writes remain forbidden.
- `dhf consistency` → `2 consistency findings`: approved `sad-v1` misses COMP-06 (C01) and names COMP-03 Pressure Monitoring (C04). Fresh documents pass all four rules. Separate stale/unknown citation and summary mismatch tests exercise C02/C03.
- Expanded `generate-section` now accepts per-unit/per-component IDs (R-034). The impact command persists stale evidence status and readiness blocks it.
- Before M8 document work: address R-033 synthesis evidence; R-030/R-031 remain scheduled before M10.

### Pre-M8 R-033
- `pytest tests/test_design.py tests/test_impact.py tests/test_generate.py -q` → `17 passed in 27.25s`; final hazard-context query tests → `2 passed in 2.43s`. Ruff clean.
- AST detects exactly `UNIT-sensor_pressure → UNIT-alarm_latch: kestrel.alarm_latch.latched`, represented as COMP-03 → COMP-04 in the Mermaid source. All twenty units/signatures and traced hazard/control context are supplied to synthesis.
- Six component descriptions now differ in responsibility, collaborators and safety mechanisms. The source architecture.yaml is built from these same records. Separate v2 unit prompts cover why/what, algorithm, and invalid-input/recovery behavior.
- Source enrichment legitimately changes component/unit revisions in the RTM golden. Structural signatures contain the pressure default, so change_1 also stales overview/runtime/component responsibility and SDD conventions; frozen expectations record that cause. No IDs or trace links changed; dataset validator remains 248 artifacts / 473 links / exact answer key.

### M8
- `uv run pytest -q` → `59 passed in 67.83s`; ruff → `All checks passed!`, `99 files already formatted`. No paid calls.
- `dhf generate drr --input-file data/synthetic/review_input.json --since 1 --db out/m8.sqlite` → `drr: 9 sections`; zero validation events and no AI-unavailable sections after bounded grouping of consistency facts. Identity exactly matches the input JSON. Discussion, decisions, new actions and approvals remain human placeholders.
- `dhf generate sfmea --db out/m8.sqlite` → `sfmea: 27 sections`; zero validation events, 40 suggested cells, source-only severity for all eight hazards, source controls/requirements/unit/test traces, human residual risk. Risk-rating text in AI cells is rejected by a regression.
- Risk gaps include F02/RC-12 and eight F03 entries pending reviewer-confirmed failure modes. An independent removed-control example proves F01. Proposed modes do not imply approval.
- `dhf propose --db out/m8.sqlite` → `42 proposal checks → out/proposals/proposals.md + JSON`; L01 covers 35 requirements, L02 drafts a requirement for diagnostics_trace, L03 checks six components and returns no invented contradiction. The graph is unchanged.
- `python -m mock_ado.validate` → `{'artifacts': 248, 'links': 473, 'answer_key': 'exact', 'rules': 12}`; `dhf gaps --db out/m8.sqlite` → `21 deterministic gaps`. G12 adds the five missing SOUP requirements/anomaly-evaluation records, shown in SAD design gaps.
- R-013: six cases now contain explicit stimuli (80 kPa/3 s dwell, air 0.11 vs 0.1 limit, clamped 1 mL target, unsafe acknowledgement, 120.01 rate and 10.01 drug-dose boundaries); IDs/links unchanged.
- R-031: grouped H2 navigation and H3 subsections, name/bases/fields structure table, hazard/control names, and G12 regression all pass. R-035: impact Markdown starts with per-document counts and groups the 21 possible sibling subsections into three optional unit rows.
- Local LibreOffice rendered and inspected every page: sFMEA nine landscape pages; final DRR two pages. Suggested cells are visibly highlighted and source tables remain separate. Desktop Word UI remains pending.
- The exact native watch/approved-baseline/regeneration regression now covers SAD, SDD, SSTR and sFMEA. All untouched section bytes and owner edits survive. Frozen expected causes include the new risk document.

### M8 follow-up R-036 before M10
- Corrected all risk bundles and requirement/component/unit/PR annotations by their actual functions. `python -m mock_ado.validate` → `248 artifacts, 413 links, answer_key exact, rules 12`. Removed spurious rotated implementation links; IDs remain stable.
- G06 remains RC-12 (independent pressure plausibility control); G07 remains SRS-012. G01's missing audit-export case was reassigned from a duplicate case, leaving SRS-032 as the planted non-risk verification gap. Hand-checked RTM and deterministic SSTR golden changed accordingly.
- Data/trace/generation/risk targeted run: 27 passing checks; the watcher initially failed against an accidentally already-changed inspection baseline. Corrected the frozen baseline and reran `pytest tests/test_impact.py -q` → `2 passed in 23.79s`; ruff → `All checks passed!`.
- Reviewed frozen change_1 causes: `risk_row.HAZ-04`, `control_trace.HAZ-04` stale from SRS-021/UNIT-sensor_pressure; `failure_modes.HAZ-04` stale also from new RES-3-021. Risk drafting now records its evidence revision dependencies. The native approved-baseline/watch/selective-redline regression passes with untouched bytes preserved.

### M8 follow-up R-037–R-039
- `dhf generate sfmea --db out/m9.sqlite` → `61 sections`; zero validation events. Seventeen Class C primary functions have source trace tables and five distinct suggested cells each, alongside the eight hazard summaries (125 suggested cells total). Configured primary functions are asserted to exist in the extracted AST; source severity stays separate and residual risk stays human.
- `dhf generate drr --input-file data/synthetic/review_input.json --since 1 --db out/m9.sqlite` → `10 sections`; zero validation events. Complete G/C/F findings table, safety-first suggestions including C01/C04/G06/G07/G05, named empty-diff notice, and specific prior action descriptions. Missing historical IDs remain findings, never fabricated source records.
- `dhf propose --db out/m9.sqlite` → `40 proposal checks`; G02 requirements SRS-034/035 are deterministic no-implementation findings, not LLM jobs. The mock flags only SRS-020's missing checksum activation check; L01 agreement returns no claims and empty checks are omitted from the proposal Markdown. Local proposal output never changes the evidence graph.
- Full regression `pytest -q` → `62 passed in 70.28s`; ruff → `All checks passed!`, `137 files already formatted`. Exact native change/watch/regeneration cases include the new function-level risk rows. No paid calls.
