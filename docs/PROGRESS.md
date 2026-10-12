# Build Progress
## Status
Current milestone: M0 (in progress) · Last updated: 2026-10-12 IST
## Milestones
| M | Status | Tag | Commit | Notes |
|---|---|---|---|---|
## Now / Next
- Working on: scaffolding and guarded LLM layer.
- Next: synthetic dataset and contract-faithful ADO mock.
## Acceptance evidence
## Pending live verification
- Paid-provider section parity — optional API keys; tests and demo use mock.
- GitHub Actions result — pending first push.
- Real ADO M11 — needs a real org; not part of the offline build.
## Known issues
## Deviations from BRIEF (with reason)
- uv was absent; installed inside ignored `out/bin` for this workstation. CI uses setup-uv.
## LLM spend (from out/ledger.json)
| Provider | Spent | Cap |
|---|---|---|
| anthropic | $0 | $1.50 build / $4 hard stop |
| openai | $0 | $1.50 build / $4 hard stop |

### M0
- `uv run dhf --help` → `Usage: dhf [OPTIONS] COMMAND [ARGS]...`; `version` listed.
- `uv run pytest` → `5 passed in 0.09s`. Schema validity, cache miss/hit/version invalidation, ledger persistence, cumulative per-run cap, build cap and 80% hard stop covered.
- `uv run ruff check .` → `All checks passed!`
- `uv run ruff format --check .` → `20 files already formatted`.
- `.env` and attached PDF → `git check-ignore` prints both paths.
- CI workflow uses the same checks with mock provider. Remote run remains pending until pushed.
