# Build Progress
## Status
Current milestone: M17 real-data readiness (Claude as engineer since 2026-11-03) · live ADO trial waits on a new read-only PAT (REVIEW R-058) · Last updated: 2026-11-03
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
| M9 | done | m9-done | e972cb5 | Complete port blueprint; tenant deployment pending |
| M10 | done | m10-done | ecac18b | Evaluation, clause appendix, YAML extensions, audit export and offline demo |
| M11 | done | m11-done | 279debf | Native synthetic seeder, read-only discovery and onboarding |
| M12 | done | m12-done | cbf0a85 implementation | Advisory support, effort assumptions and R-046/R-047 |
| M13 | done; reviewer visual check complete | m13-done | 2ae290c | REVIEW.md records offline browser rendering, search, filters and inspector verification; R-049 visually verified at c6795b4 |
| M14 | done | m14-done | 275c62c | Verified offline rehearsal and frozen demo pack |
| M15 | done | m15-done | 5a88eb9 | Day-1 kit and sandbox guardrails; tenant validation pending |
| M16 | done offline | m16-done | a4963c4 | Copilot HTTP/folder transport and credit guard; tenant execution pending |
| M17 | in progress | — | 6449ab5, e9ab449, 75c4c3f, c0bab04 + template sets | Read-only scoped real-org ingest, document-baseline import, not-assessable reporting, owner-structured SAD/SDD/SSTR; live ADO trial blocked on PAT |
## Now / Next
- Done: the real dataset imports locally (documents + CSV) with D01–D05 findings and a real-data explorer. Live ADO ingest is ready but unverified on the real project.
- Blocked on the owner:
  - a new read-only PAT (R-058);
  - a decision on company evidence and the BD tenant drafting path (R-059);
  - a decision on code evidence (R-061).
- Next: run scoped discovery and ingest on the real project, then write the reviewed mapping profile (R-060). The owner-structured templates (R-062) are done: `DHF_TEMPLATE_SET=bd`.


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
- Copilot Studio tenant deployment/parity is not executed; the local port pack and three-tier plan are complete. Full-document paid-provider semantic review remains a human check.
## Deviations from BRIEF (with reason)
- Synthetic fixture has 20 units and 4 unverified SRS (including risk control SRS-012), meeting the approximate sizes and at-least gap requirements.
- Local contract tests require sandbox elevation for loopback bind. The test fixture still blocks all external sockets.
- Default ADO fields, native revisions/history, area allocation and residual tags are mapped in YAML. Optional fixture metadata now holds only a synthetic marker; all product facts come from native evidence (ADR-010 supersedes ADR-008).
- uv was absent; installed inside ignored `out/bin` for this workstation. CI uses setup-uv.
## LLM spend (from out/ledger.json)
| Provider | Spent | Cap |
|---|---|---|
| anthropic | $0.0137161 actual + $0.0096725 reserved | $1.50 build / $2.50 owner hard cap |
| openai | $0.24695035 actual + $0.0021046 reserved | $1.50 build / $4.00 owner hard cap |

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

### M9
- `python tools/check_port.py` → `flows: 7, rules: 22, queries: 46, prompt_tools: 21, reference_contracts: pass, tenant_parity: pending`. Every current prompt body is preserved exactly; queries and G/C/F/L rules are mapped to named flow constructs and explicit deterministic operations.
- Pack contains architecture mapping, eleven Dataverse tables, seven step-by-step flows, converted prompt tools, deterministic rule/AST/hash/redline boundaries, agent topics/async job status, DLP/authentication/model/region capability gates, native/canonical contracts and frozen parity expectations.
- Native test IDs use run ID plus result ID (not test-case native ID); run/result revision is `1` with content-hash changes. Dataverse immutable key includes canonical ID and content hash to retain such revisions safely. Native ADO connector authentication does not accept PATs; supported Entra connection and source/docs permission boundaries are documented.
- Microsoft-primary-source checks document link-only trigger omissions and polling fallback, supported async infrastructure/Teams callback and run-status fallback. No tenant deployment, licenses, custom functions, residency or parity execution is claimed.
- Full reference checks: `62 passed in 70.28s`; ruff clean / `137 files already formatted`. No paid calls. R-036 is in 212e688 and R-037–R-039 in 450b11d before M10.


### M10 implementation and review follow-ups
- Offline demo includes native HTTP ingestion, docs-only PRs, readiness failures, explicitly labelled test-tooling owner review/merge, baselines, watch/change_1, selective regeneration, YAML SUTR/RTM, eval and checksum audit export. Fresh per-run mock/cache paths preserve owner .env and shared paid ledger. DRR impact input is explicit; it cannot load an unrelated run's global report.
- R-030: deterministic stdlib PNG (six components, 20 units, two declared interfaces, extracted pressure→alarm call), numbered embedded Word figure, Mermaid/PNG checksums and docs PR assets. Local LibreOffice PDF inspection: SAD 16 pages, sFMEA 26 pages, SSTR 12 pages; all contact sheets inspected and figure/pressure/occlusion pages inspected at full size. No clipping observed; tracked insertions/deletions remain visible. Desktop Word UI remains an optional owner check.
- R-041: every facts-referenced artifact joins query evidence; bounded synthesis retains compact context and adverse records. The all-AI-section subset and reduction tests pass. FMEA prompts v2 define failure-present effects and a worked row; no model assigns severity or residual risk. Clinical source narratives now agree with their component allocation. Frozen change_1 expectations remove spurious old rotated-component neighbors, add the actual RC-04/latch neighbor and track SRS-021 in pressure prose; occlusion remains stale. Golden visible sections are reviewed source tables; only environment URLs normalize in evaluation.
- R-042/R-043: BUILD_PLAN contains ordered MVP, hour ranges, cut line, capability gates and A/B/C tiers with scoped parity/native-offline storylines. Tier C specifies Artifact/Link/Section/Run SharePoint lists, indexed run queries, file storage and deliberately narrow size/row caps. Core validator uses native citation/kind/confidence and Power Fx number checks or explicitly blocked numeric compensation. All 21 prompt tools use text JSON inputs; tenant limits remain unverified.
- R-044/R-045: owner caps are Anthropic $2.50 / OpenAI $4.00 actual+reserved, in addition to run/build caps; paid CLI output shows headroom. Section YAML routes default/analytical models, records model/tier and prices per actual model, prohibits nano and includes reasoning settings in cache identity. GPT-5 omits temperature, sets low effort and reserves the inclusive visible+reasoning ceiling. Offline SDK spies and ledger tests verify this; no paid calls were made during M10 engineering.
- Initial M10 full suite found two regressions (67 passed, 2 failed): JSON transport overhead and scope mock selection. Both implementations were corrected without relaxing the redline assertions. Subsequent complete suite with model tiers: `73 passed in 78.96s`; final report-isolation check is included in the release suite below.
- Port completeness: `uv run python tools/check_port.py` → `flows: 7, rules: 22, queries: 47, prompt_tools: 21, reference_contracts: pass, tenant_parity: pending`.

- Final implementation suite: `uv run pytest -q` → `74 passed in 81.48s`; `uv run ruff check .` → `All checks passed!`; `uv run ruff format --check .` → `147 files already formatted`. No skips/xfails or paid API calls.
- `./scripts/demo.sh` → exit 0; final pre-commit run `out/demo/03c71dc466`. `dhf ingest` → `Snapshot 1: 248 artifacts, 413 links`; `dhf gaps` → `21 deterministic gaps`; `dhf rtm` → `35 RTM rows`; `dhf propose` → `40 proposal checks`; product source PATCH → `403`. Native watch detects `2 changed, 3 added`; selective regeneration completes all four docs and readiness blocks the new SSTR suggestions. All AI sections available, zero validation events.
- `dhf eval` → `Unknown IDs: 0; gaps precision=1.00 recall=1.00`; `out/metrics.md`/JSON and clause appendix produced. Saved change_1 impact → 75 exact section/status/cause records, precision/recall 1.00. Historical sad-v1 C01/C04 → 2 true positives, no false positives/negatives; current draft consistency → 0. Deterministic baseline goldens → SAD 4 / SDD 5 / SSTR 7 checked, no mismatches. Current coverage → SRS-to-test 31/35 (88.57%), SRS-to-code 33/35 (94.29%), hazard-control-verification paths 8/8; retained G06/G07 remain explicit findings.
- `dhf audit-pack` → `32 verified files`; tampered ZIP/document and absent manifest-referenced source revisions are rejected by regression tests. `sutr` has 2 sections and `rtm` 2 sections via specs only; Python hash inventory unchanged. SUTR explicitly records no source unit-test results; a separate classified-unit-result test proves filtering.

- Committed-code checkpoint: `./scripts/demo.sh` → exit 0, fresh run `out/demo/80077d4952`, generator version `e707d9a6acbc3da02fa1d8924d1aa2545a41dc4d`. Same exact metrics/goldens and 32 verified audit files. Section manifest records `{provider: mock, name: mock-v2, tier: analytical}` for the conclusion; no unavailable AI sections.
- Before the documentation checkpoint commit: full suite → `74 passed in 81.93s`; ruff → `All checks passed!`, `147 files already formatted`. Review scan → `Unresolved blocking items: []`. R-030/R-041–R-045 marked `Resolved in e707d9a`; earlier R-036/R-037 remain marked with their implementation SHAs.


### M11 — Phase 2 real-data readiness
- `pytest tests/test_onboarding.py -q -s` → `3 passed in 16.06s`; first seed → `{work_items_created: 126, runs_created: 2, results_created: 80, prs_created: 7, git_pushes: 9}`; rerun → all five counters 0. Native ingest/fixture parity is exact including content hashes and source system/revisions; only URLs/native IDs/retrieval time differ. SRS-030's planted two-revision history is replayed.
- Fresh native acceptance run `out/m11/ab3b3046`: `seed-ado --confirm-org kestrel-org --dry-run` → 126 planned work items, no writes; confirmed seed then rerun → zero new entities/pushes. `dhf discover --output …/ado_mapping.yaml` → `0 unknowns require confirmation`; `dhf ingest --db …/evidence.sqlite` → `Snapshot 1: 248 artifacts, 413 links`.
- Seed-only HTTP writes tested for work-item JSON Patch/create/update, native runs/results, source pushes and PR completion. App token gets 403; dhf source-write allowlist is unchanged. Renamed acceptance-criteria field is proposed as Custom.Acceptance and explicitly flagged for confirmation. Discovery drafts to out/, retaining the active mapping.
- `uv run pytest -q` → `77 passed in 101.72s`; ruff check → `All checks passed!`; format → `152 files already formatted`. `seed-ado --help` shows required --confirm-org and --dry-run. No paid calls.
- Native REST behavior was checked against Microsoft API contracts. Real tenant inherited-process/system-date/PR-completion permissions still need owner-provided sandbox verification; the test result is the empty local native mock, not a real organization.


### M12 — Advisory claim support and effort telemetry
- `dhf generate sstr --source fixtures` equivalent local fixture-store generation produced 12 sections and zero validation events in `out/m12-docs`. `dhf verify-support --doc sstr --sample 0` → `{'supported': 3, 'unsupported': 1}; support rate=0.75; advisory only` (mock lexical check).
- Live acceptance: `DHF_MODEL_OPENAI=gpt-4.1-mini uv run dhf verify-support --doc sstr --sample 0 --provider openai --db out/m12.sqlite --documents out/m12-docs` → `sstr: {'supported': 4}; support rate=1.0; advisory only`. Shared dhf ledger cost $0.0015514, 9.640 seconds. OpenAI cumulative actual $0.4752382 plus reserved $0.0021046, hard cap $4.00; Anthropic unchanged. This is a sampled model opinion, not correctness proof or human approval.
- `dhf eval --db out/m12.sqlite --documents out/m12-docs` → metrics show SSTR AI/deterministic/human = 4/7/1, assumed authoring hours 1.9, estimated hours saved 1.9, support 100%, verifier USD/seconds 0.001551/9.640. YAML assumptions AI .30h, deterministic .10h, human 0; measured generation time/cost separate; human review excluded.
- Tests preserve unsupported claim text, add Word comments and manifest flags, and show readiness unchanged. Typed support schema/cache/numeric validation, compact collaborator packs, source quantities 3s/256bytes and suggested-only conclusion v3 covered.
- R-047: `pytest tests/test_onboarding.py -q -s` → `5 passed in 21.31s`; historical opt-in remains exact fixture parity; default native chronology → graph 248/413, all 21 gaps exact, G11 TC-030 only; rerun zero. Mock rejects readonly dates without bypassRules=true. Foreign work items/repos/runs are listed and refused before mutation; explicit --allow-nonempty dry run remains read-only. No real ADO seeding.
- `python tools/check_port.py` → 7 flows, 22 rules, 47 queries, 22 prompt tools, reference_contracts pass, tenant_parity pending.
- Final complete offline suite: `uv run pytest -q` → `82 passed in 105.36s`; ruff check → `All checks passed!`, format → `156 files already formatted`.
- Review-resolution checkpoint suite → `82 passed in 109.77s`; ruff check/format remain green. R-046/R-047 marked `Resolved in cbf0a85`.


### M13 — Offline traceability explorer
- `dhf explore --db out/m12.sqlite --documents out/m12-docs --output out/m13/explorer.html` → `Explorer: 248 artifacts → out/m13/explorer.html; offline HTML`. Every node retains its source URL/revision. Search, G/C/F filters, current-result state and directed neighbor navigation are inline SVG/JS, without resource downloads or connections; inert data and connect-src none are enforced.
- `pytest tests/test_explorer.py tests/test_evaluation.py -q` → `6 passed in 5.10s`; all-node provenance, G/C/F flags, 40 latest results, zero external URL literals/fetches, hostile source markup remaining inert, stale section causes and audit checksum integration checked.
- `node tools/check_explorer.cjs out/m13/explorer.html` → 248 nodes, 413 links, DOM contract build 33.562 ms; search/G06/latest/inspector pass. This measures JS DOM construction in a dependency-free test harness, **not browser layout or paint**.
- `./scripts/demo.sh` → exit 0, run `out/demo/2ade52ff5c`; pre-regeneration explorer has 251 artifacts/416 links, 40 directly stale sections, exact causes PR-8/RES-3-021/RUN-3/SRS-021/UNIT-sensor_pressure, all G/C/F families. Post-regeneration explorer is exported separately. `dhf audit-pack` → 33 verified files including trace/explorer.html. Metrics/goldens/regeneration remain exact. No paid calls.
- Browser visual/laptop and true paint-time acceptance are pending: computer-use tool rejected file:// by protocol policy. No workaround attempted; owner requested to open the local artifact. DOM performance is not substituted for that unperformed check. Skill launcher was unavailable; source-derived PRODUCT/DESIGN context and inline review record this limitation.
- Complete suite before checkpoint: `84 passed in 110.75s`; ruff → `All checks passed!`, `160 files already formatted`. No skips/xfails. The m13-done tag records the implementation and automated checks; visual acceptance remains explicitly pending.

### M14 prerequisite — R-048 advisory verification coverage
- `pytest tests/test_support.py -q` → `4 passed in 2.23s`; bad rationale gets exactly one repair attempt, retains the unsupported verdict with rationale_unverified if still invalid, adds a safe Word warning, and never renders unvalidated model explanation. Original claims remain untouched. Missing cited revisions keep the specific cited_revision_unavailable reason.
- Support-rate denominator and verified/sample-eligible/document-eligible counts are explicit in CLI/metrics; unverified explanations and unavailable causes are counted separately.
- Full suite → `85 passed in 114.07s`; ruff check green, format `162 files already formatted`; port contracts → 23 prompt tools, all pass. No additional paid call; reviewer live evidence in REVIEW.md remains separately attributed.

### M14 — Demo pack and R-049 explorer usability
- R-049: the default SRS-021 view now shows its ten recorded upstream/downstream trace artifacts in compact lanes and a 160px graph viewport. Search/rule/state matches and direct neighbours reflow from the top; source excerpts and revisions remain in the inspector after the mock stops. Non-chain edges are dimmed, baseline C01/C04 findings are filterable, and reset clears search and focus. `node tools/check_explorer.cjs out/m13/explorer.html` → 248 nodes/413 links, focused chain 10 nodes, 29.62ms DOM contract build, search/G06/latest/inspector pass. This is not a browser paint benchmark. The owner's screenshot identified blank canvas and overlong inspector; those were tightened, but refreshed owner visual confirmation remains pending.
- `./scripts/demo.sh` → exit 0, actual offline run `out/demo/9c927fe7a7`: snapshot 248/413, 21 gaps, 35 RTM rows, product source write 403. Native watch found two changed and three added source artifacts; four draft documents had 40 directly stale sections, followed by selective regeneration and a blocked SSTR readiness check. Mock support sample: 1/1 covered and supported; eval unknown IDs 0 and gap precision/recall 1.00; audit ZIP 33 verified files. The on-stage pause option and optional `--live` provider/whole-demo cap were wired, but no paid full-demo rehearsal was run.
- `python tools/freeze_demo.py out/m14-demo-final.log` → 19 synthetic fallback files copied from that successful offline run. `python tools/check_demo_pack.py` → 48 judging/script links resolve, 19 SHA256 fallback files verified, 33 audit files verified, and Word XML has actual tracked insertions/deletions. The 6:40 script covers all six judging weights with exact commands and fallbacks. No tenant execution is claimed.
- Final implementation suite: `uv run pytest -q` → `88 passed in 122.80s`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `172 files already formatted`. Clean-clone rehearsal will be recorded after the M14 checkpoint commit so it tests committed contents.
- Clean clone of committed `dev` at `c49b24b` into `out/m14-cleanclone`: locked dependencies installed from local uv cache; `./scripts/demo.sh` → exit 0, new run `out/demo/d47fcd1516`; `tools/check_demo_pack.py` → 48 links, 19 hashed fallbacks, 33 verified audit files, tracked redline pass. The copy did not include uncommitted workspace files. This proves the documented offline path; `--live` and tenant execution remain unclaimed.

### M15 — Copilot Studio day-1 kit and sandbox guardrails
- Two ready-to-paste Prompt tool instructions preserve the complete versioned SSTR anomaly and SAD component bodies. Four text inputs (`facts_json`, `evidence_json`, `max_claims`, `preferred_kind`), fixed claims.v1 JSON output and Basic-tier GPT selection are explicit. Their synthetic sample facts/evidence and expected claims reproduce the reference `validate_claims` result with two accepted claims each and zero validation events. The separate citation/kind/confidence/MatchAll cards have offline reference cases for unknown IDs, 39 versus 40, missing/out-of-range confidence and sourced-without-citation downgrade; native Power Fx execution is pending tenant access.
- `mvp_columns.csv` lists the four MVP Dataverse tables (Artifact, TraceLink, DocumentSection, GenerationRun), required columns and alternate keys. The Tier B click path covers cloud flows 01→07, docs-only writes, and the thin start/status agent. R-050 adds the BD Experiment environment, original/Standard agent path, GPT Basic-only mapping, 600-credit Monitor check, two-section rehearsal budget, five-person named sharing and synthetic-only gate. Tier C-prime is a reviewed import if ADO DLP blocks the connector; it does not claim live ADO integration.
- `dhf export-snapshot --db out/m12.sqlite --output-dir out/m15-snapshot` → `248 artifacts, 413 links`; package contains canonical `graph.json`, `artifacts.csv`, `links.csv` and SHA256 index. Pure export and CLI tests prove deterministic order, complete rows/provenance and hashes; no upload or source write occurs. `python tools/check_port.py` → `flows: 7, rules: 22, queries: 47, prompt_tools: 23, reference_contracts: pass, tenant_parity: pending`.
- R-051 explorer: focused labels wrap to two lines with full ID/outcome tooltip; search moves the inspector to a matching record instead of leaving a hidden selection; Expand graph gives full-width projection. `node tools/check_explorer.cjs data/demo/fallback/explorer-stale.html` → 251 nodes/416 links, 11-node changed SRS-021 chain, 35.33ms DOM contract, search/G06/latest/inspector pass. `./scripts/demo.sh` offline exit 0 and refreshed 19 fallback files; checksum/link/redline audit remains 48/19/33/pass. Browser repaint and projector reading still need owner confirmation; DOM timing is not paint time.
- Targeted `pytest tests/test_day1.py tests/test_snapshot_export.py tests/test_explorer.py -q` → `8 passed in 2.77s`. Complete `pytest -q` → `93 passed in 107.43s`; ruff check → `All checks passed!`, format → `180 files already formatted`. No paid calls or tenant operations.

### M16 — BD-approved prompt transport (offline implementation)
- Implementation and offline kit committed as `f8964e6`; R-052/R-053 review resolutions and this evidence follow in the milestone checkpoint commit.
- `copilotstudio` delegates only typed section drafting to a BD-tenant Basic GPT prompt. HTTP mode sends the exact eight-field request to a signed Power Automate flow URL; folder mode writes one atomic request file per document with uncached section requests and polls one response file. Successful sections use the existing claims.v1 schema, citation/number validator and cache. Refusal, empty output, malformed JSON, timeout and invalid usage become distinct `ai_unavailable` human placeholders; deterministic sections survive. The signed URL is never logged. Each successful section records the tenant-reported model and Basic tier, and document manifests include locally estimated/reconciled Copilot credits. No tenant response has been observed by this repo.
- A local ledger reserves a conservative UTF-8-byte token bound at the configured Basic rate (minimum 0.1 credits/1K). The cumulative cap is clamped at 400 even if configured higher, below BD's 600-credit monthly limit; per-run cap defaults to 250. Offline preview of SSTR/SAD/SDD/sFMEA baseline sections estimated 5.08/24.47/66.23/46.21 = **142.00 local credits** before change and DRR work. This is a deliberately conservative reservation estimate, **not actual tenant billing**. Failed calls retain reservations; Monitor remains the authoritative tenant check. Both default and analytical sections route to the same Basic model.
- `dhf ingest --source fixtures --db out/m16/evidence.sqlite` → `Snapshot 1: 248 artifacts, 413 links`. `dhf copilot-request sstr anomaly_assessment --db out/m16/evidence.sqlite` printed the exact eight-field request; its JSON matched the checked-in synthetic sample, request ID `1505c5dc2ffd937e919921d3968574033eacc1726126e69eb49f811b4a7653a0`. The preview made no transport or ledger reservation. The sample response's model/usage are visibly illustrative. Its two claims pass the reference validator with zero rejection events.
- Offline HTTP stub and synced-folder stub tests cover success, per-document batching, refusal, empty/malformed output, timeout, hard-cap exhaustion, cache hit, secret redaction, model/tier recording and unknown-ID rejection. `pytest tests/test_copilot.py tests/test_day1.py tests/test_port.py -q` → `21 passed in 3.24s`. Complete offline checkpoint suite with local loopback mock → `110 passed in 118.02s`; `ruff check .` → `All checks passed!`; `ruff format --check .` → `188 files already formatted`. No skips, paid API calls or tenant calls.
- `python tools/check_port.py` → 7 flows, 22 rules, 47 queries, **24 prompt tools**, reference contracts pass, tenant parity pending. The generic prompt body is versioned in `specs/` and byte-matched by the port check. `./scripts/demo.sh` offline → exit 0, run `out/demo/ff731fffe3`, 248/413 ingest, 21 gaps, source-write 403, change/redline and 33-file verified audit. `python tools/check_demo_pack.py` → 51 links, 19 fallback files, 33 audit files, tracked redline pass, tenant execution pending.
- R-053: day-1 flow 04 now uses WDL cards for citation/kind/confidence; hosted Power Fx `MatchAll` is isolated to Dataverse instant plug-in or an agent-topic handoff, with blocked `numeric_unverified` compensation otherwise. R-052: official demo script names the BD provider for qualifying AI prose, selects HTTP → OneDrive → native MVP, adds the thin-agent status beat and requires a **real owner-captured screenshot** for visual fallback. Checked-in mock and personal-API prose are labelled development output.
- Live demo mode now requires an explicit `DHF_LIVE_PROVIDER`; it cannot silently default to a personal API. `DHF_LIVE_PROVIDER=copilotstudio` is the documented official path. Personal-provider rehearsals require their own explicit choice and stay outside official AI evidence.
- After that safeguard, the final complete offline suite passed again: `110 passed in 116.83s`; ruff check and format remain green. The command did not contact BD or any paid model.
- **Deviations:** the brief specified a 400-credit cumulative cap but no whole-demo run cap; 250 credits was chosen so the conservative 142-credit baseline estimate does not preempt SDD while still leaving 150 credits of cumulative headroom. The generic tenant flow handles `claims.v1` drafting only; `support.v1` is not sent to a claims-only flow.
- **Pending live verification / known issues:** BD sandbox DLP permissions, prompt model identity, fixed JSON and actual token fields, credit Monitor usage, OneDrive sync/trigger deduplication, agent/Teams status-link beat and screenshot are all untested. `support.v1` advisory verification is explicitly skipped for the tenant provider until an approved flow/schema is built; the official M16 demo may state that check is pending. The R-051 graph's final projector/browser visual check remains with the owner. No real ADO or BD tenant capability is claimed from offline tests.

### Explorer redesign — owner follow-up after M16
- Replaced the fixed nine-lane SVG layout with a focused incoming/outgoing relationship map, selected-artifact card, five groups of trace context, searchable sidebar, complete evidence table and a compact source inspector. Every mapped relationship retains its recorded direction and type. Group placement explicitly does not assert a link. Gap/latest/stale states have text badges; long Git revisions display compactly with complete provenance available. The page remains one offline HTML file with inert base64 evidence, safe source anchors and no added dependency.
- `.venv/bin/pytest -q` → `110 passed in 118.00s`; ruff check → `All checks passed!`; format → `188 files already formatted`. After the final direction/provenance polish, `.venv/bin/pytest -q tests/test_explorer.py` → `3 passed in 2.26s`.
- `node tools/check_explorer.cjs data/demo/fallback/explorer-baseline.html` → 248 artifacts / 413 confirmed links, 10-artifact SRS-021 context, 6 direct links, 27.15 ms DOM build; search, all 248 index rows, component selection, G06, latest results, empty/reset states and source inspector pass. The stale and regenerated fallbacks pass the same contract with 251 artifacts / 416 links, 11-artifact context and 7 direct links (28.44 / 36.36 ms). These timings measure the dependency-free DOM contract, **not browser layout/paint**.
- `./scripts/demo.sh` → exit 0, fresh offline mock run `out/demo/1021e08b96`; baseline 248/413, change_1 251/416, unknown IDs 0, gaps precision/recall 1.00, audit pack 33 verified files. Refreshed the three saved explorer snapshots with the final template, rebuilt the audit ZIP and froze the coherent 19-file rehearsal pack. `python tools/check_demo_pack.py` → 51 links, 19 fallback files, 33 audit files, tracked redline pass, tenant execution pending.
- Preview: `out/ui/explorer.html`; checked-in baseline: `data/demo/fallback/explorer-baseline.html`. Open generated HTML rather than `specs/render/explorer.html`, which is a template.
- **Deviation:** the owner requested a complete layout redesign. The full graph is indexed in the page; direct confirmed relationships are mapped around one selected artifact instead of drawing all edges simultaneously. This preserves evidence and traversal while avoiding crossings. See ADR-036.
- **Known issue / pending verification:** the browser tool rejects local file URLs and explicitly forbids bypassing that restriction. Actual laptop/projector visual inspection and the under-two-second browser paint check remain with the owner. No paid API or tenant calls were made.

### Explorer missing-data follow-up
- Owner reported no visible evidence; the active browser path was `specs/render/explorer.html`. That file is the source template and retains the evidence placeholder. Decoding the generated baseline confirmed 248 artifacts / 413 links; `out/ui/explorer.html` has the same counts.
- Added a visible startup notice explaining template versus generated-file navigation and JavaScript requirements. Failed initialization keeps the notice visible; successful evidence rendering hides it. The app browser was queued to open the generated baseline instead of the template.
- `node tools/check_explorer.cjs specs/render/explorer.html` → `template: clear missing-evidence message, embedded_evidence: false`. Generated baseline/stale DOM contracts pass (248/413 and 251/416); no evidence changed. Rebuilt the audit explorer and fallback checksums: `check_demo_pack.py` → 51 links, 19 files, 33 verified audit files, tracked redline pass. `pytest -q tests/test_explorer.py` → `3 passed in 1.67s`; ruff check/format green. Actual browser viewing remains unverified by the tool.


### DHF workspace redesign — owner feedback and graph routing corrections
- The owner rejected graph-only composition, then the wider workspace's dark-blue rail, dot grid and SRS-012 graph in the supplied 11:52 PM screenshot. Replaced the palette with an explicit light default and neutral chrome; colour marks selection and recorded gap/pass/fail/stale state. Visual approval is **pending**, not inferred from code checks.
- Added Overview, Documents, Findings, Change impact, Traceability and Risk evidence. The JSON-only payload uses existing `coverage`, `latest_results` and `risk_rows` queries, YAML rule titles/actions and manifest sections/typed claims/cited revisions. Mock drafts remain labelled. Citation inspection warns when a document's cited revision differs from the snapshot excerpt. Findings inspection keeps its task page; trace navigation follows the selected artifact. Empty impact reports show an explicit no-affected-sections state.
- Direct links now contain only anchor-incident relationships. Peer-to-peer edges no longer produce the UNIT-to-COMP roof shown in the rejected screenshot. Port order follows peer vertical positions; relationship types are in peer footers so they do not cut arrows. Full traces retain all scoped confirmed relationships, use unique skip tracks and separate label placement. Actual DOM node height governs spacing; full labels wrap. Failed latest-result badges are red. Fit frames the selected artifact horizontally and vertically while preserving at least 90% scale.
- Full offline suite after the payload/task-view implementation: `.venv/bin/pytest -q` → `110 passed in 110.56s`. After final routing changes, targeted `.venv/bin/pytest -q tests/test_explorer.py` → `3 passed in 1.93s`; `.venv/bin/ruff check .` → `All checks passed!`; `.venv/bin/ruff format --check .` → `189 files already formatted`.
- Fresh offline `./scripts/demo.sh` → exit 0, run `out/demo/187f33a140`; baseline 248 artifacts/413 links/4 documents; stale 251/416/4 documents with 40 directly stale sections; regenerated 251/416/7 documents with zero directly stale sections. Evaluation: unknown IDs 0, gap precision/recall 1.00. No paid or tenant call.
- Final populated-preview `node tools/check_explorer.cjs out/ui/kestrel-workspace.html` → 251 nodes, 416 links, 7 documents, 6 workspace views, **502 graph contexts**, full labels/measured layout/edge directions/label collisions/focused-artifact visibility/failure colour/search/filter/index/pan/zoom/navigation pass. Final frozen-current DOM initialization `212.91 ms`; **not browser layout/paint**. The strengthened camera assertion requires the entire selected node to fit inside the canvas, excluding the header and bottom controls. Baseline and stale snapshots are checked separately, with every artifact in both scopes.
- Read-only Impeccable finish review examined the supplied screenshot, source and contracts. It caught a vertical framing defect that left large-trace anchors offscreen; corrected it and added an onscreen-anchor assertion. The second finish review reported no remaining concrete code/contract blocker and independently passed preview/baseline/stale/current sweeps (502/496/502/502 contexts), with exact current-template matching. This is code/geometry review, not visual approval of the new browser rendering. Research and Before/After audit: `docs/EXPLORER_DESIGN.md`; actual palette/layout contract: `DESIGN.md` (both removed in the 2026-11-03 cleanup; see git history).
- Generated preview: `out/ui/kestrel-workspace.html`. Re-rendered all three coherent snapshots, rebuilt audit HTML and refreshed the frozen rehearsal pack from the successful run. `dhf audit-pack` → `33 verified files`; `freeze_demo.py` → `19 files`; `check_demo_pack.py` → `51 links`, `19 fallback_files`, `33 audit_verified_files`, `tracked_redline: pass`, `tenant_execution: pending`.
- **Deviation:** the owner's later instruction that the product must not primarily focus on the graph supersedes the earlier graph-first choice. Overview now opens first. Static snapshot review is functional; source editing, generation and publication remain in the real CLI workflow. No new dependency or external resource is introduced. See ADR-037.
- **Known issue / pending verification:** the browser tool rejects local file access and forbids alternate routes. New browser appearance, responsive/projector legibility and true under-two-second browser paint have not been measured. The owner's screenshots are rejection evidence. R-054 remains open before tenant execution.

- Payload purity follow-up: moved YAML presentation loading into local orchestration; `explorer_payload` now receives JSON presentation metadata and performs no file reads. A regression blocks `Path.read_text` during payload construction and checks JSON round-trip. The initial sandboxed full-suite run could not bind loopback mock servers (95 passed, 2 failures and 14 setup errors, all socket permission failures); rerun uses the approved local-server test permission with external sockets still prohibited.
- Final approved-loopback complete offline suite: `.venv/bin/pytest -q` → **`111 passed in 132.98s (0:02:12)`**. Ruff check → `All checks passed!`; format → `189 files already formatted`. No skips, paid calls or tenant calls.

### Owner acceptance and smaller arrowheads — 2026-10-14
- Owner feedback: “looking much better now”, “rest looks good”; requested reduced arrow size. Reduced both normal and selected SVG marker dimensions 8×8 → 6×6 (25%). Routes, line weights and workspace layout are unchanged. Re-rendered the populated preview and all three fallback snapshots, rebuilt audit HTML and refreshed checksums. Owner feedback accepts layout/colour direction; no under-two-second browser paint measurement is claimed.
- Verification: `pytest -q tests/test_explorer.py` → `4 passed in 2.64s`; populated workspace contract → 502 graph contexts / six views / all direction, geometry and interaction checks pass (108.16 ms simulated DOM only); ruff check/format → `All checks passed!` / `189 files already formatted`; demo pack → 51 links / 19 hashed fallbacks / 33 verified audit files / tracked redline pass.


### M16 follow-up — R-054 missing token-usage fallback
- Added `DHF_COPILOT_USAGE=reported|estimated`, default `reported`, to `.env.example`. Reported mode rejects missing/null counts; estimated mode prefers valid reported counts and otherwise applies the shared rounded-up UTF-8 bytes ÷ 3 estimate to the eight prompt text inputs and serialized `claims_json`. Supplied boolean, negative, fractional or string counts remain `invalid_usage`. Invalid mode fails before dispatch.
- Both HTTP and OneDrive batches persist `usage_source` in cache/ledger and section/document manifests. Cache hits retain the original source even after changing mode and incur no credits. Cumulative ledger credits distinguish reported and estimated contributions; aggregates report `mixed`. Existing successful pre-R-054 caches/ledgers retain reported provenance without rebilling. Metrics JSON includes credits/source and Markdown labels **Copilot estimated credits**, with tenant Monitor authoritative for billing.
- Selective Copilot regeneration now records its own run's credits (zero for cached regeneration), keeps credit amounts out of `llm_cost_usd`, and preserves provenance on reused sections. Refusal/timeout and other parsing/validation failures retain reservations and their existing human-placeholder path.
- `pytest -q tests/test_copilot.py tests/test_llm.py tests/test_evaluation.py` → `53 passed in 11.76s` before the added both-mode cap and legacy-ledger cases. Final `pytest -q tests/test_copilot.py` → `31 passed in 7.23s`. Covers strict reported rejection, missing/partial estimated usage, preference for real counts, malformed usage, mixed totals, legacy migration, both transports, cached sources, document/metrics source and cached-regeneration credits.
- `python out/r054/verify_usage.py` (HTTP MockTransport only; model explicitly named `OFFLINE STUB - Basic placeholder`) → reported mode: 12 sections, 0 ai_unavailable, 0.076 local credits, source `reported`; estimated mode with omitted usage: 12 sections, 0 ai_unavailable, 0.9967 local credits, source `estimated`. Review artifacts: `out/r054/{reported,estimated}/documents/sstr.manifest.json`, `metrics.json`, `metrics.md`, and isolated stub ledgers. These are structural offline checks, **not tenant calls or narrative-quality verification**.
- Updated HTTP, OneDrive and generic prompt flow notes plus README/demo guidance: return measured fields when available; otherwise omit them and select estimated mode. Never return illustrative zero fields as actual usage. The tenant model and Monitor still require owner verification. No `.env` edit, paid call or tenant action.
- `ruff check .` → `All checks passed!`; `ruff format --check .` → `189 files already formatted`. `check_port.py` → 7 flows / 22 rules / 47 queries / 24 prompt tools / reference contracts pass / tenant parity pending. `check_demo_pack.py` → 51 links / 19 fallbacks / 33 verified audit files / tracked redline pass / tenant execution pending.
- M13 current status now credits the reviewer's completed visual check at `m13-done`/R-049, as recorded in REVIEW.md. The later workspace layout/colour acceptance from the owner is recorded above. Historical pending-check notes describe their original checkpoints; the current status supersedes them. No new browser paint-time measurement is claimed.
- **Stop state:** M16 offline implementation done, R-054 fixed; waiting for owner sandbox answers. Real ADO/BD capabilities, prompt model identity, DLP, Monitor billing and transport execution remain unverified. No further development or sandbox operation is started.
- Final complete offline regression: `.venv/bin/pytest -q` → **`126 passed in 119.27s (0:01:59)`**. Tests used approved loopback binding only, blocked all external sockets, and made no paid or tenant calls. No skipped or xfailed tests.


### Local opening and beginner guide — 2026-10-28
- Added `docs/LOCAL_DEMO_GUIDE.md` and linked it from README. Explains the problem/goal, implemented features, six workspace views, document names, saved-page versus engine behaviour, exact Mac opening commands, fresh offline startup and a five-step presentation. Company sandbox execution remains pending; product development has not resumed.
- Verified existing Python `3.12.15` and local uv `0.13.0`. `./scripts/demo.sh` → exit 0, fresh run `out/demo/d39e956b82`; provider mock, live false. Baseline 248 records / 4 documents / 0 stale; changed 251 / 4 / 40 stale; regenerated 251 / 7 / 0 stale. Evaluation: unknown IDs 0, gap precision/recall 1.00; audit 33 verified files. Log: `out/local-demo-2026-10-28.log`. No paid, tenant or real-source calls.
- Populated workspace contract → 502 graph contexts / six views / geometry and interaction checks pass (77.25 ms simulated DOM only); guide links and all referenced fresh outputs exist. Demo pack check → 51 links / 19 fallbacks / 33 verified audit files / tracked redline pass. `git diff --check` clean. No product code changes or new tests.
- Finder accepted the project-folder opening request. Guide and fresh populated explorer were queued through the app's open tool; this is not a new browser-rendering observation. M16 remains done offline, M13 reviewer visual verification remains complete, and company setup still awaits owner sandbox answers.


### Input-to-output explanation and verified walkthrough — 2026-10-28
- Added `docs/INPUT_OUTPUT_DEMO.md`, linked from README and the local guide. Covers actual inputs, intermediate evidence storage, checks, drafting, review/export, outputs, a show/say flow and exact Terminal commands. Explicitly records that the browser has no upload button and arbitrary PDF/DOCX/ZIP importing is not implemented. Documents the supported fixture/ADO paths, Python extraction scope, mapping review, and the specific meanings of `--documents`, `--input-file` and `--baseline-file`. No source/document upload or company connection is claimed.
- Executed each documented baseline command using the bundled fixture and mock provider: `ingest` → 248 artifacts / 413 links; `gaps` → 21 deterministic findings; `rtm` → 35 rows; `generate sstr` → 12 sections / zero validation events; `explore` → 248 artifacts / one generated report; `audit-pack` → 11 verified files. Outputs under `out/flow-demo/`; command transcript `out/flow-demo/walkthrough.log`. The full demo remains separately available with seven document types and a 33-file audit.
- Verified the HTML's embedded record/link/document counts, manifest provider/section count, all three generated SSTR files, guide links and audit checksums. `check_demo_pack.py` remains 51 links / 19 fallbacks / 33 audit files / tracked redline pass. `git diff --check` clean. Documentation-only change; no new tests or product code, paid calls, tenant operations or source writes. Core development remains stopped pending sandbox answers.

### M17 — Real-data readiness (owner dataset trial)

Dataset-specific results are local only (`out/real-docs/`, gitignored). This section records product evidence, not dataset contents.

- **First real-project contact (before fixes)**
  - ADO rejected the supplied PAT as expired (`x-tfs-serviceerror`).
  - None of the dataset's files could be ingested: the ADO adapter needed whole-project reads and the Kestrel repository, and there was no document or CSV adapter.
- **6449ab5 — read-only scoped ADO ingest**
  - Real organizations are read-only by default, with a transport-level guard.
  - `ADO_SCOPE` covers seeds, WIQL, link expansion, caps, test plans, repository and history.
  - Rich-text fields become plain text; `id_fields` and `attribute_fields` added; expired-PAT reason reported.
  - The mock shows reciprocal links and honours `errorPolicy` and `planId`.
- **e9ab449 — `dhf import-docs`**
  - A profile-driven document and CSV baseline with D01–D05 and personal columns dropped.
  - Gaps report rules as not assessable when the link class is absent.
  - Watch-test race removed.
- **75c4c3f — explorer**
  - Product, subject and release are settings; synthetic or confidential label; not-assessable coverage.
  - D-findings shown for document-sourced evidence only.
- **Real dataset, run locally:**
  - `import-docs` read the latest issue of each document family, excluded redlines and reference copies, and dropped the personal CSV column.
  - It produced requirements, specifications, architecture items, design units, test cases and allocation links.
  - The parser bugs it exposed were fixed before commit.
  - The import found consistency findings in the existing documents, under every D rule except D03 after the ID fix.
  - `dhf gaps` reports the 9 ADO-link rules as not assessable instead of thousands of false gaps.
  - The explorer renders the baseline offline.
- **Verification (2026-11-03):**
  - `uv run pytest -q` → `138 passed in 163.69s`
  - `uv run ruff check .` → `All checks passed!`
  - `uv run ruff format --check .` → `194 files already formatted`
  - `./scripts/demo.sh` → completed in 48 s; `out/metrics.md`: unknown IDs 0, baseline gaps precision 1.00 / recall 1.00 (21), change_1 impact precision 1.00 / recall 1.00 (75 records).
- **Known issues**
  - Live ADO ingest, the real mapping profile and drafting from company evidence are unverified (R-058, R-059, R-060).
  - The RTM is specification-centric, so on a document baseline its rows show allocation only through requirements.
- **Template sets (R-062)**
  - `DHF_TEMPLATE_SET=bd` generates the SAD, SDD and SSTR in the owner's heading structure, with items and units nested. Shared sections are byte-identical to the default drafts apart from headings.
  - Regeneration keeps the recorded template.
  - The watch test's docs clone moved into its temporary folder: reused mock ports were colliding with stale clones in `out/`, which was the real cause of its intermittent failures.
  - Verification: `uv run pytest -q` → `142 passed in 129.04s`; ruff check and format clean. The owner's curl request (GET work item, Bearer PAT) was re-run on request: still HTTP 401 "The Personal Access Token used has expired."
- **PR #1 fresh-perspective review fixes (2026-11-03; details in REVIEW.md)**
  - `uv run pytest -q` → `164 passed in 150.44s` after the gap-sweep fixes; ruff check and format clean.
  - `./scripts/demo.sh` → exit 0, unknown IDs 0, baseline gaps P/R 1.00 (21), change_1 impact P/R 1.00 (75).
  - Real baseline, run locally: same 112 consistency findings. `dhf gaps` names the 6 ADO-link rules as not assessable.
  - `node tools/check_explorer.cjs` passes on the demo explorer; it is a demo-specific harness, so not run against real data.
- **Live ADO trial (2026-11-03, read-only; data local under out/real/)**
  - With the renewed PAT, `dhf discover` read the hackathon scope (seed lists plus direct links) in about 3 s. It found the work-item types, link types and the document-ID field, and reported repositories as not readable without Code scope.
  - Scoped `dhf ingest`: requirements, specifications, test cases and in-scope results from three test plans; about 9 minutes, dominated by run results. No write left the process.
  - Fixes from the trial (ADR-043):
    - follow the mapping's Dependency links;
    - declare unread sources, so G02 is not assessable without code;
    - keep only runs that hold in-scope results;
    - a scope `release` for runs whose names carry none.
  - The owner-format SSTR was generated from the live evidence (mock provider, local) with 0 validation rejections. Traceability rows link to the live work items.
  - `uv run pytest -q` → `168 passed in 146.07s`; ruff clean.

- **PR #2 fresh-perspective review fixes (2026-11-03)**
  - **Company data:** a test used a test-run title copied from the owner's dataset. It now uses a fictional name. The commit that added it exists only on this unmerged branch.
  - **Scope `release`:**
    - It must be quoted text; an unquoted `1.10` used to become "1.1".
    - It labels only runs of the scope's own test plans; the ingest report counts them.
    - A blank value means no release.
  - **Link following:**
    - `follow.relations: []` follows no links again.
    - The scope example no longer lists relations, so copying it keeps the mapping-based default.
    - Both ends of every `-Forward`/`-Reverse` link type are followed, and discovery treats them the same way.
  - **Link classes:** mapped work-item links are declared as `link:peer` pairs for work-item types, so a work-item `implements` mapping no longer makes the code rule G02 assessable without a repository.
  - **Runs:** whole-project reads keep empty or aborted runs again. Seeded scopes still keep only runs with in-scope results, and the report counts the ones they skip.
  - **Docs:** the port contract's assessability text matches. The REVIEW.md headings are restored, with outcomes appended under each item.
  - Verification: `uv run pytest -q` → `172 passed in 160.12s`; ruff check and format clean; `tools/check_port.py` reference contracts pass.
  - **Gap sweep follow-up:**
    - A seeded scope declares only the link types it follows, so Related pairs, which are not followed by default, no longer produce false G06 gaps.
    - A rule with no subjects is not assessable when no source can read its link, or what it `requires` (G11 needs results). A scope without test plans now reads "not assessable" for G05 and G11 instead of zero.
    - `uv run pytest -q` → `173 passed in 160.24s`.
- **End-to-end flow (2026-11-03; owner: no source-code evidence for the hackathon; AI drafting runs in the Copilot agents; ChatGPT/Claude keys for development)**
  - **SAD and SDD without code (ADR-044, closes R-061).**
    - Design queries read code-derived or document-derived items. Missing facts read "Not recorded in the source", or name the document section.
    - A real-project scope can name `documents:`. Every ADO ingest then adds software items, units and allocations from the SAD/SDDs.
    - The component diagram lays out any inventory; the synthetic PNG is byte-identical.
  - **Change tracking:** adding `documents:` changed every ADO artifact's declared link classes, so the real merged ingest reported 454 "changed". An attempt to leave `link_classes` out of the content hash was reverted in review (see below). The ingest report now says how many changes are configuration-only, and drafts citing them are re-flagged, because assessability can change with the scope.
  - **Other fixes:**
    - The offline drafter quotes the opening sentence of bodies over 1,000 characters (synthetic maximum 706, so synthetic drafts are unchanged).
    - `dhf check --documents`.
    - `copilot-request` applies the data guard before any section work.
  - **Verification on the final tree:**
    - `uv run pytest -q` → `174 passed in 145.00s`
    - `uv run ruff check .` → `All checks passed!`
    - `uv run ruff format --check .` → `196 files already formatted`
    - `./scripts/demo.sh` → exit 0 in 35 s; unknown IDs 0; baseline gaps P/R 1.00 (21); change_1 impact P/R 1.00 (75 records).
  - **Live OpenAI demo** (`DHF_LIVE_PROVIDER=openai ./scripts/demo.sh --live`, synthetic data, before the last three small fixes above, which don't touch the live path):
    - The first, cold pass reached the $0.25 per-run cap in the sFMEA/DRR sections ($0.20 spent). Those sections became placeholders, and the review step correctly refused "ready".
    - The second pass ($0.20) completed every stage up to the final impact assertion, whose change_1 key records the offline drafter's citations.
    - The third pass, after the live-mode impact check: exit 0, 0 drafting failures, all 40 directly stale sections detected, $0.07 (DRR and proposal inputs carry run-specific review state).
    - Cumulative OpenAI spend: $1.10 of the $4.00 hard cap.
  - **Live Anthropic demo** (Claude Haiku 5.5, $0.12):
    - SSTR, SAD, SDD and sFMEA were drafted, but the model's safety classifier declined `residual_anomalies` and `release_conclusion`.
    - Two DRR sections returned suggested claims without confidence and were rejected by the claim validator.
    - The review step therefore stops at "not ready", as designed. OpenAI stays the live default (R-045).
    - Cumulative Anthropic spend: $0.12 of the $2.50 hard cap.
  - **Copilot folder transport rehearsal** (synthetic): `dhf generate sstr|sad --provider copilotstudio` with `DHF_COPILOT_MODE=folder` and a scratch ledger and cache.
    - A local stand-in for the tenant flow answered with the offline drafter, reporting zero tokens.
    - SSTR: one request file carried 4 AI sections; SAD: one file carried 11. 0 sections unavailable.
    - Credits settled at 0 and the manifests record the answering model. No tenant execution is claimed.
  - **Real project, local and read-only** (offline drafter only; outputs under `out/real/`):
    - The scoped live ingest with `documents:` ran in 8 m 47 s and read 21 design documents. It added 18 software items, 129 units and 119 allocation links; 136 matrix rows name requirements outside the scope.
    - `dhf gaps`: 91 gaps, 2 rules not assessable. `dhf rtm`: 33 rows.
    - SSTR (20 sections), SAD (59) and SDD (1,036) in the owner's template set, with 0 validation rejections.
    - Explorer: 601 artifacts. Audit pack: 20 verified files. Impact right after generation: 0 stale. `dhf check sstr`: not ready (human sections pending).
    - `copilot-request` refuses the company evidence (R-059).
  - **Deviations:** with a live drafter, the demo checks change_1 impact exactly for deterministic sections only. AI sections cite what their claims cite, while the key records the offline drafter's citations. The offline demo keeps the exact check over every section.
  - **Known issues:**
    - **Prompt budget:** on the owner's 129-unit architecture, the three architecture-wide AI sections (SAD overview and runtime, SDD purpose) exceed the prompt budget. They are marked for manual authoring; per-component fact summaries are a follow-up.
    - **Cold live demo cost:** about $0.40, above the $0.25 per-run cap, so a cold cache needs two passes.
- **PR #3 fresh-perspective review fixes (2026-11-03)**
  - **Content hash rule reverted.** Leaving `link_classes` out of the hash made `dhf audit-pack` refuse earlier manifests. It also changed document revisions on re-import, and made reading old snapshots depend on today's model. The ingest report now marks configuration-only changes instead.
  - **Merged documents:**
    - Every `import-docs` warning reaches the ingest report.
    - The folder and profile are checked when an ingest starts (not in every `ADO()`, and not after the ADO read).
    - Only `allocated_to` links merge.
    - The import report schema is unchanged.
  - **SAD/SDD:**
    - Allocation tables list allocated system requirements.
    - Notices name the heading path, not the versioned file, so a re-issue stales nothing.
    - "Responsibility" skips labels and table rows, and long quotes are cut between words.
    - `#` in file names is kept.
    - A missing Severity reads "Not recorded".
  - **Fail closed:**
    - A dangling unit→component reference raises again.
    - The sFMEA safety-class filter raises when a class is unknown, instead of dropping the item.
  - **Diagram:**
    - Only component-to-component edges are dependencies, so a reviewer's unit edge no longer breaks the DOCX.
    - Boxes list up to ten units; unallocated units are counted on the figure.
    - The DOCX figure fits the page.
    - Labels keep a distinctive end.
  - **Demo:** with a live drafter, deterministic sections are scored exactly against change_1; the offline run still scores every section exactly.
  - **Verification:**
    - `uv run pytest -q` → `179 passed in 179.63s`; ruff check and format clean.
    - `./scripts/demo.sh` → exit 0 in 40 s; unknown IDs 0; gaps P/R 1.00 (21); deterministic impact exact (51 records); change_1 impact P/R 1.00 (75).
    - `DHF_LIVE_PROVIDER=openai ./scripts/demo.sh --live` → exit 0, 0 drafting failures, deterministic impact exact (51), $0.066 (cumulative OpenAI $1.17 of $4.00).
    - Real project, local, from the stored read-only snapshot:
      - SSTR/SAD/SDD in the owner's format with 0 rejections.
      - SAD allocation tables now show 23 allocation rows (0 before), and the matrix lists the 6 allocated system requirements.
      - 0 of 129 SDD notices name a file. Audit pack 20 verified files; impact 0 stale.
  - **Gap sweep follow-up:**
    - SDD units keep their design-section text and a digest of it, so an edit to processing logic or error handling is a tracked change. The first re-import of an existing baseline therefore reports its units changed once.
    - Documented software items reach hazards and risk controls through their SAD allocations.
    - Orphan-code proposals (L02) skip units from documents.
    - `uv run pytest -q` → `182 passed in 172.72s`; ruff clean; `./scripts/demo.sh` → exit 0, gaps P/R 1.00, deterministic impact exact (51), change_1 impact P/R 1.00 (75). Real baseline re-import: 129 of 129 units carry design text.

### Windows support and README refresh — 2026-11-03

The owner asked for native Windows support as a priority, and for a clear README for macOS and Windows.

- **Windows (ADR-045)**
  - `dhf` could not start on Windows: the LLM layer imported `fcntl`. The ledger and cache lock now uses `flock` or `msvcrt`.
  - Every text read and write states UTF-8, and every write states LF line endings (246 calls, of which ruff's PLW1514 flags only 89). `tests/test_portability.py` enforces this, together with UTF-8 decoding of text subprocess output.
  - `.gitattributes` checks out LF. Git runs with `core.autocrlf=false` and decodes UTF-8.
  - The `dhf` entry point (`dhf.cli:run`) and the demo print UTF-8 on Windows pipes.
  - Code-file keys use `/`. The mock's reset clears git's read-only files before deleting.
  - CI runs pytest, ruff, `dhf --help` and the offline demo on `ubuntu-latest` and `windows-latest`.
- **README** rewritten: requirements and install for macOS and Windows, quick start, configuration, a command table, the review workflow, AI providers, real projects, development, rules and documentation links (tracked docs only).
- **Verification (macOS, with Windows encodings simulated)**
  - `uv run ruff check .` → `All checks passed!`; `uv run ruff format --check .` → `128 files already formatted`
  - `PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 LC_ALL=C uv run pytest -q` (no UTF-8 defaults, as on Windows) → `178 passed in 161.12s`
  - `PYTHONIOENCODING=cp1252 uv run dhf --help` (a Windows pipe) → exit 0; the `→` in the help text prints.
  - `PYTHONIOENCODING=cp1252 uv run python tools/demo.py` → exit 0; unknown IDs 0; gaps P/R 1.00; deterministic impact exact (51 records); audit pack 33 verified files.
  - README quick start in a clean worktree: `dhf ingest --source fixtures` (248 artifacts), `dhf gaps` (21 gaps), `dhf generate sstr` (12 sections, 0 rejections), `dhf explore` → all succeeded.
- **Found by the new CI demo step:** on Ubuntu, the demo's simulated owner ran `git rebase` without a git identity. That fails on any machine with no `user.name`/`user.email` (CI runners, fresh laptops); developer machines had hidden it. The rebase now passes the same synthetic identity as the commit before it.
  - With git's global config disabled and `user.useConfigOnly=true`: the previous commit fails at the same step as CI (exit 1); the fix → exit 0, all four baselines tagged, gaps P/R 1.00, deterministic impact exact (51), audit pack 33 verified files.
- **First native Windows run** (`windows-latest`): `1 failed, 177 passed in 378.28s`. The hook-guarded git pushes, the `msvcrt` lock, ingest, review PRs and redlines all pass.
  - The failure was `test_seed_admin_and_reset_contract`. The mock's reset rebuilds every repository, and on Windows git that outlasts httpx's 5 s default client timeout; the server's `WinError 10053` was it answering a client that had already gone.
  - That call now waits up to 120 s. The product's own ADO client already allows 60 s.
  - CI's later steps now run after a failure, so one run also reports the demo.
- **Native Windows, all green** (`windows-latest`, PR run on 2e277b4): `178 passed in 500.54s`. The offline demo completed: all four baselines tagged, gaps P/R 1.00, deterministic impact exact (51 records), audit pack 33 verified files.
- **Flaky explorer budget:** the push run on the same commit failed one test (`1 failed, 177 passed in 352.03s`) — the explorer DOM harness's 2 s initial-render budget.
  - `render_ms` counts from page start and refreshes on every update. The harness read it only after its whole scripted session, so a runner stall during any interaction counted against the initial render.
  - Locally, the initial render takes 19 ms and the whole session 33 ms; 25 hash seeds all pass, so the generated page does not vary.
  - The budget now applies to the stats taken at load, and a failure reports the measured time.

### Product input workspace — 2026-11-19

- Added the empty product workspace, project default and document-specific Azure connections, the four requirements selectors, SSTR plan/run inputs, immutable Azure snapshots, and per-document multi-file evidence.
- Added encrypted PAT storage, local owner/member sessions, credential activity, 401/403 recovery actions, expiry warnings and upload redaction ahead of evidence extraction.
- Exported selected Azure evidence and uploads into a document-specific database for the existing drafting engine.

Acceptance evidence:

```text
uv run --locked pytest -q --tb=short
203 passed in 164.96s (0:02:44)

ruff check .
All checks passed!
ruff format --check .
141 files already formatted
```

In a clean browser workspace, selecting two SDD files together produced the message “2 file(s) added. Potential secrets were redacted in SDD-reader.txt.” With a PRD alongside them, **Save evidence for drafting** reported “Saved 3 evidence artifacts”.

**Pending live verification:** run the browser workflow against the owner's Azure DevOps organization using an owner-supplied read-only PAT, confirmed work-item mapping and approved test scope. The current Azure contract checks use stubbed responses.

**Deviations:** the synthetic dataset stays in the test and explicit rehearsal paths. The deployed scope here is the local browser workspace. Shared hosting, Microsoft Entra identity, managed encryption keys and browser DRR drafting remain future work.
