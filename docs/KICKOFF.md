# Kickoff Instructions for the Engineer (Codex)

You are the sole engineer building the "DHF Automation" product in this folder, end to end and autonomously. Claude is the PM and code reviewer and watches this folder while you work. The repo owner is the product owner.

## Read first, in full, before writing any code

- `AGENTS.md`: the rules. The "Non-negotiable rules" are hard constraints.
- `docs/BRIEF.md`: the product spec, plus milestones M0–M11 with acceptance criteria in §15.
- `docs/DECISIONS.md`: decisions already made. Don't reopen them.
- `docs/REVIEW.md`: the reviewer's findings. Check it at the start of every milestone.

## Goal

Deliver every milestone M0 → M10 in BRIEF §15 and meet every acceptance criterion. If time remains, do the P2 items in BRIEF §12 (AB9 → AB13). M11 (real ADO org) only happens if the owner provides real credentials.

Work continuously. Don't stop between milestones to ask permission.

## Step 0: Setup

1. If this folder is not a git repo: `git init`, add origin `https://github.com/Rahulreddy-23/A-C.git`, fetch, check out `main` (keep all local files), then create and switch to branch `dev`.
2. Before the first commit, run `git status` and confirm that `docs/*.pdf` and `.env` are ignored. Never commit them.
3. First commit: the existing spec files (`AGENTS.md`, `docs/`, `.github/`, `.gitignore`).
4. Create `docs/PROGRESS.md` from the template below.

## Loop, for each milestone

1. Re-read `AGENTS.md`, the milestone's row in BRIEF §15 plus the BRIEF sections it references, `docs/PROGRESS.md` and `docs/REVIEW.md`.
2. Fix every open `[blocking]` item in `docs/REVIEW.md` before new work.
   - Under each one, append `Resolved in <sha>: <note>`. Don't edit or delete the reviewer's text.
   - If you disagree, write your reasoning under the item and continue with other work.
3. Implement in small commits prefixed `M<N>: …`.
4. Verify: `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` must all pass. Run the CLI commands that prove the acceptance criteria and keep their real output.
5. Update `docs/PROGRESS.md` with that output as evidence. Paste real output, not claims.
6. Commit, tag `m<N>-done`, and push `dev` and the tags to origin. Never push to `main`.
7. Move on to the next milestone.

## Live systems

**Azure DevOps.** There is no real org. Build and use the local ADO mock (`tools/mock_ado/`, BRIEF §5.5) as the default ADO backend for development, tests and the demo.
- The product's ADO adapter must be real HTTP against `ADO_BASE_URL`, so a real org later is only a config change.
- Ship working mock defaults in `.env.example`, and create `.env` from it if `.env` doesn't exist. If `.env` exists, never overwrite or rewrite it; only append missing mock ADO keys.
- If the owner later adds real ADO credentials, run M11.

**Paid LLM APIs** (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in `.env`, optional):
- Call them only through the `dhf` LLM layer, which has the ledger and cache.
- Build-time cap is $1.50 per provider in total; the rest is reserved for demo tuning.
- Use the cheapest configured model for dev runs.
- Tests and CI never call paid APIs.
- If keys are missing, use the mock LLM and list the check under "Pending live verification".

**Secrets and data**
- Never print, log or commit secrets.
- Only synthetic data may be sent to external APIs.
- Never read `docs/*.pdf`.

## Stop and ask the owner only if

- an action would delete or overwrite something you didn't create, or touch anything outside this folder;
- you'd need to write to any real external system other than pushing branch `dev` to the GitHub origin;
- a paid call would exceed the budget cap.

Otherwise, decide, record the decision under "Deviations" in `docs/PROGRESS.md` (or as an ADR in `docs/DECISIONS.md`), and continue.

## Quality bar (the reviewer rejects work that misses this)

- Deterministic first: no LLM-computed IDs, numbers or links.
- Every LLM claim is typed (sourced, inferred or suggested), cited, and checked by the validator.
- The product never modifies source systems, and the mock's token guardrail proves it.
- Prompts, specs, rules and schemas live in `specs/` as data.
- Each pipeline step is a pure function with JSON in and JSON out.
- The mock is contract-faithful to the ADO REST API (response shapes, revisions, link types). It's not a shortcut.
- Prefer simple over clever. Add a dependency only if it's listed in AGENTS.md or justified in an ADR. No speculative abstractions.
- Tests assert behavior. Never skip, xfail or weaken a test to make the suite pass.
- Never fake progress. If something doesn't work, put it under "Known issues" instead of stubbing it to look finished.

## `docs/PROGRESS.md` template

Keep it current; the reviewer reads it.

```
# Build Progress
## Status
Current milestone: M<N> (in progress | blocked | done) · Last updated: <timestamp>
## Milestones
| M | Status | Tag | Commit | Notes |
## Now / Next
- Working on:
- Next:
## Acceptance evidence
### M<N>
- [x] <criterion>: `<command>` → <real output excerpt>
## Pending live verification
- <command> — needs <credential/network> — expected result
## Known issues
## Deviations from BRIEF (with reason)
## LLM spend (from out/ledger.json)
| Provider | Spent | Cap |
```

## Done means all of

- Tags `m0-done` … `m10-done` exist.
- `scripts/demo.sh` starts the ADO mock and runs the whole demo end to end offline.
- `out/metrics.md` is generated.
- The README explains setup, the mock, how to switch to a real ADO org, and the demo.
- Every acceptance criterion in `PROGRESS.md` has evidence.
- `docs/REVIEW.md` has no open `[blocking]` items.

Then do the P2 items, tagging each `p2-<id>-done`.
