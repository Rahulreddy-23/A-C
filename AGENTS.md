# AGENTS.md — rules for coding agents

Read this file and `docs/BRIEF.md` before every task. `docs/BRIEF.md` is the product spec and milestone plan; this file is the rulebook. If they conflict, stop and say so in the PR description.

## Roles

- **Claude** — engineer, PM and code reviewer. Since 2026-11-03 the owner has put Claude in charge of the project. Claude builds milestone by milestone, reviews against the acceptance criteria in `docs/BRIEF.md` and the rules below, and records findings in `docs/REVIEW.md`.
- **Codex** — built M0–M16 as engineer; may be re-engaged by the owner, in which case the review workflow below applies unchanged.
- **Repo owner** — product owner. Owns credentials, merges `dev` into `main`, has final say on scope and on any use of company data.

## Environment

- Codex works locally in this folder on branch `dev`.
- **ADO = the local mock by default** (`tools/mock_ado/`, BRIEF §5.5). Start it with `uv run mock-ado serve`; tests start it in-process on a random port.
  - `.env.example` ships working mock defaults: `ADO_BASE_URL=http://localhost:8089/kestrel-org`, `ADO_PROJECT=Kestrel`, and mock tokens for `APP_ADO_PAT` / `SEED_ADO_PAT`. Mock tokens aren't secrets.
  - A real ADO org is optional (M11). Use it only if the owner puts real credentials in `.env`.
- Paid LLM keys are optional. Without them, use the mock LLM and list the live check under "Pending live verification" in `docs/PROGRESS.md`. Never block on missing credentials.
- Paid LLM calls go **only** through the `dhf` LLM layer (ledger + cache). Build-time cap: `DHF_BUILD_BUDGET_USD` = 1.50 per provider; the rest is reserved for demo tuning.

## Stack

- Python 3.12, `uv` for environment and dependencies
- `typer` (CLI), `pydantic` v2 (models), `httpx` (HTTP), stdlib `sqlite3` (evidence store), `jinja2` (templates), `pyyaml`, `python-docx` plus raw OOXML (DOCX and tracked changes)
- Dev: `pytest`, `respx` (HTTP mocking), `ruff`
- LLM SDKs: `anthropic`, `openai` — only inside `src/dhf/llm/adapters/`
- The ADO mock uses stdlib `http.server`.
- No web framework, ORM, LangChain or vector DB. Ask in the PR before adding any dependency not listed here, and justify it.

## Commands

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run dhf --help
```

## Repo layout

```
src/dhf/
  models/      canonical evidence model (pydantic)
  ingest/      source adapters: fixtures/, ado/, code/ (AST extraction)
  graph/       SQLite evidence store, named queries, revision tracking
  trace/       RTM, coverage, gap + consistency rules engine
  generate/    template-spec engine, section pipeline, claim validator
  llm/         provider interface, adapters (anthropic, openai, mock), cache, budget ledger
  render/      markdown, docx (incl. tracked changes), diagrams
  review/      docs-repo PR workflow, manifests, baselines, readiness check
  impact/      change detection, staleness, selective regeneration
  cli.py
specs/
  documents/   one YAML template spec per DHF document
  prompts/     prompt files (markdown + front matter: id, version, inputs, output_schema)
  schemas/     JSON Schemas for LLM outputs
  rules/       gap and consistency rules (YAML)
  ado_mapping.yaml   ADO process/work-item/link mapping (config, not code)
data/synthetic/      synthetic dataset, answer key, change scenarios
tools/mock_ado/      local ADO REST mock: state, git-backed repos, HTML pages, scenarios (dev + demo)
tools/seed_ado/      optional real-org seeder (M11)
port/copilot_studio/ Copilot Studio port pack
eval/                golden outputs, metrics harness
docs/                BRIEF.md, DECISIONS.md
out/                 generated artifacts (gitignored)
```

## Non-negotiable rules (PRs that break these are rejected)

1. **Deterministic first.** IDs, links present in sources, counts, percentages, pass/fail stats, coverage, SOUP lists and dates are computed in code, never by an LLM. LLMs receive these as inputs (`facts`).
2. **Every generated claim is typed and cited.** LLM output is JSON validated against `specs/schemas/`. Each claim has `text`, `kind` (`sourced` | `inferred` | `suggested`), `citations` (artifact IDs) and `confidence` (0–1, required for inferred and suggested). The validator:
   - rejects any claim citing an ID not in the evidence pack
   - downgrades `sourced` with no valid citation to `inferred`
   - rejects claims whose numbers don't match the injected `facts`

   No free-text LLM output reaches a document.
3. **Never modify source systems.** The product only reads ADO work items, code and test data. Its only allowed write is branch/commit/PR in the **docs repo**. AI-proposed requirements or trace links go to proposal files, never to ADO.
   - Test tooling in `tools/` (the ADO mock and the optional seeder) is separate from the product. `src/` never imports from `tools/` and never calls `/_mock/` endpoints.
   - The product uses `APP_ADO_PAT`. The mock rejects that token on any write outside the docs repo, and a test proves it.
   - The seeder uses `SEED_ADO_PAT` and refuses to run unless `--confirm-org <name>` matches the configured org.
4. **Prompts, templates, rules and schemas are data, not code.** They live in `specs/` so they can be ported to Copilot Studio unchanged. No prompt text inside Python beyond trivial glue.
5. **Each pipeline step is a pure function with JSON-serializable input and output.** One step = one future Power Automate flow or Copilot Studio prompt-tool call.
6. **Provider-agnostic LLM layer.** One interface with adapters for Anthropic, OpenAI and `mock`. Model names come from config. **Tests and CI never call paid APIs.**
7. **Budget guard.** The owner's **hard cap is $2.50 for Anthropic and $4.00 for OpenAI for the whole hackathon** (set 2026-10-13; OpenAI includes an extra $1.50 for model comparisons). That covers every paid call by Codex, the reviewer and demo runs, cumulatively.
   - Estimate tokens before every call and enforce a per-run cap (`DHF_MAX_USD_PER_RUN`, default 0.25).
   - Keep a persisted cumulative ledger (`out/ledger.json`). Codex's own build-time calls stop at `DHF_BUILD_BUDGET_USD` (1.50). Nothing may push actual plus reserved spend past the provider's hard cap: `DHF_HARD_CAP_USD_ANTHROPIC` = 2.50, `DHF_HARD_CAP_USD_OPENAI` = 4.00.
   - Cache responses by `sha256(prompt_id + prompt_version + model + canonical_json(evidence_pack))`. Cache hits are free.
   - Temperature 0.
8. **Synthetic data only** goes to external LLM APIs. Never commit real company data. Never read or commit `docs/*.pdf`.
   - The owner's dataset in `Hackathon_2026/` is company data. It is gitignored and is processed locally only: deterministic import, gaps and the explorer, with outputs under `out/`.
   - Committed docs describe product behaviour, not dataset contents (no IDs, names or text from it).
   - A real ADO organization is read-only by default (`ADO_READ_ONLY=auto`). Never weaken that, or the synthetic-only LLM guard, without the owner's explicit decision.
9. **Secrets** only via `.env` (gitignored), with a `.env.example`. Never log tokens.
10. **Provenance everywhere.** Every artifact stores source system, URL, revision, retrieved_at and content hash. Every generated document gets a manifest (BRIEF §7).
11. **Local processing.** No external rendering, telemetry or analytics services (no online Mermaid, Kroki or PlantUML servers, no CDN-loaded JS in generated HTML). Diagrams render locally or stay as source text.

## Commit and checkpoint rules

- Work on branch `dev`. Never commit to or push `main`; the owner merges.
- Make small commits with prefixed messages, e.g. `M3: add G01–G11 rules engine`.
- **At the start of every milestone**, read the open items in `docs/REVIEW.md` and fix every `[blocking]` item before new work.
  - Mark each fixed item with `Resolved in <sha>: <note>`. Don't edit or delete the reviewer's text.
  - If you disagree with an item, write your reasoning under it and continue with other work.
  - Fix `[non-blocking]` items when you touch that area, and no later than M10.
- **At the end of every milestone:**
  1. Run tests and ruff; they must be green.
  2. Run the milestone's acceptance commands.
  3. Update `docs/PROGRESS.md` with the **real output** as evidence.
  4. Commit, tag `m<N>-done`, and push `dev` plus tags to origin.
- If a requirement is ambiguous, choose the simplest reasonable option, record it under "Deviations" in `docs/PROGRESS.md`, and keep going.
- Append architectural choices to `docs/DECISIONS.md` (ADR log, append-only).
- **Never fake progress.**
  - Don't stub something so it looks complete.
  - Don't skip tests, mark them xfail, or weaken them to get green.
  - Don't claim an acceptance criterion without pasted evidence.
  - Anything that doesn't work goes under "Known issues".

## Definition of done (every milestone)

- The milestone's acceptance criteria in `docs/BRIEF.md` §15 are met, with evidence in `docs/PROGRESS.md`.
- `uv run pytest` and ruff pass. New code has type hints.
- No rule above is broken. No open `[blocking]` items in `docs/REVIEW.md` for earlier milestones.
- README "How to run" is updated if commands changed.
