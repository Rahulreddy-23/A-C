# Build Progress
## Status
Current milestone: M3 (done) · Last updated: 2026-10-12 IST
## Milestones
| M | Status | Tag | Commit | Notes |
|---|---|---|---|---|
| M0 | done | m0-done | 98aa27a | Local checks and GitHub Actions green |
| M1 | done | m1-done | 6969c55 | Refreshed evidence in b74d84b after R-010 |
| M2 | done | m2-done (refreshed) | b74d84b | Native ADO parity, including metadata stripped, verified |
## Now / Next
- Working on: M3 RTM, coverage and YAML-driven gap rules.
- Next: M4 SSTR section generation, typed claim validation and manifests.
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
## Pending live verification
- Paid-provider section parity — optional API keys; tests and demo use mock.
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
| anthropic | $0 | $1.50 build / $4 hard stop |
| openai | $0 | $1.50 build / $4 hard stop |

