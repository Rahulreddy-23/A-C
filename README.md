# DHF Automation

Drafts IEC 62304 Design History File (DHF) documents from Azure DevOps (ADO) evidence. Traceability is computed deterministically and every draft goes through human review.

The tool reads requirements, risks, tests and design documents from ADO (read-only) or from local exports. It computes traceability, coverage and gaps in code. AI drafts only the narrative sections, as typed claims that cite source artifacts and are validated against the evidence. Drafts reach reviewers as pull requests in a separate docs repository, as Word documents with a provenance manifest.

## What it does

- **Ingests evidence** from ADO work items, test runs and repositories, or from existing DHF Word documents and ADO CSV exports.
- **Traces and finds gaps**: requirements trace matrix (RTM), coverage, and rule-based gap and consistency findings.
- **Drafts documents**: SSTR, SUTR, RTM, SAD, SDD, DRR and sFMEA, as Word and Markdown.
- **Supports review**: draft PRs, a readiness check, controlled baselines and tracked-change redlines.
- **Tracks change impact**: finds stale sections after evidence changes and regenerates only those sections.
- **Exports**: an offline HTML evidence explorer and an audit pack with verified hashes.

## Requirements

| | macOS | Windows |
|---|---|---|
| Git | `xcode-select --install` | `winget install --id Git.Git -e` |
| [uv](https://docs.astral.sh/uv/) | `brew install uv` | `winget install --id astral-sh.uv -e` |

uv installs Python 3.12 automatically. Without Homebrew or winget, use the [uv installer](https://docs.astral.sh/uv/getting-started/installation/) and [Git for Windows](https://git-scm.com/download/win). Open a new terminal after installing.

## Quick start

These commands are the same in macOS Terminal and Windows PowerShell:

```bash
git clone https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync
uv run python tools/demo.py
```

The demo runs offline and needs no keys. It starts a local ADO mock and uses the mock AI provider, then runs the full workflow: ingest, draft PRs, review, baseline, a live evidence change, selective regeneration and an audit pack. `out/demo-latest.json` lists the generated Word drafts, explorer pages, redline and audit pack.

To try the steps yourself, using the bundled synthetic evidence:

```bash
uv run dhf ingest --source fixtures
uv run dhf gaps
uv run dhf generate sstr
uv run dhf explore
```

## Configuration

Settings are read from `.env`, which git ignores. Create it from the template:

| macOS | Windows (PowerShell) |
|---|---|
| `cp .env.example .env` | `Copy-Item .env.example .env` |

The defaults point at the local ADO mock and need no changes. Put real ADO credentials and AI keys only in `.env`.

## Commands

Run every command from the repository root. `uv run dhf --help` lists all commands, and `uv run dhf <command> --help` shows the options of one.

| Command | What it does |
|---|---|
| `uv run mock-ado serve` | Starts the local ADO mock on port 8089. Keep it running in a second terminal. |
| `uv run dhf ingest` | Reads evidence from ADO into a versioned snapshot (`--source fixtures` works offline). |
| `uv run dhf import-docs <folder>` | Imports an existing DHF (Word documents and ADO CSV exports) offline. |
| `uv run dhf gaps` | Writes gap findings and coverage to `out/gaps.md`. |
| `uv run dhf rtm` | Writes the requirements trace matrix to `out/rtm.md`. |
| `uv run dhf generate <doc>` | Drafts `sstr`, `sutr`, `rtm`, `sad`, `sdd`, `drr` or `sfmea` into `out/documents/`. |
| `uv run dhf generate <doc> --open-pr` | Opens a draft PR in the docs repository. |
| `uv run dhf check <doc> --pr-id <id>` | Rechecks the edited PR and posts its readiness status. |
| `uv run dhf baseline <doc> --pr-id <id>` | Tags a merged document as a controlled baseline. |
| `uv run dhf impact --since baseline` | Reports which sections are stale after evidence changes. |
| `uv run dhf regenerate --stale --open-pr` | Regenerates only the stale sections. |
| `uv run dhf explore` | Writes the offline evidence explorer to `out/explorer.html`. |
| `uv run dhf audit-pack` | Exports drafts, provenance and verified hashes as a ZIP. |

## Review workflow

1. `generate --open-pr` opens a draft PR with Markdown, Word and a manifest.
2. Reviewers edit the Markdown in the PR. AI suggestions are marked `[Suggested — review required]`. To accept or reject one, record a marker with the claim's ID:
   ```md
   <!-- dhf-resolution:<claim-id> accepted reviewer=Name rationale=Why -->
   ```
3. `check --pr-id` rebuilds the Word document and posts the `DHF review readiness` status.
4. A person merges the PR. `baseline` tags it (`sstr-v1`, `sstr-v2`, …), and later drafts show Word redlines against that baseline.

The tool never merges PRs and never writes to ADO work items or source repositories. Approvals and e-signatures stay in the eQMS.

## AI providers

Choose a provider per command with `--provider`. The default is `mock`.

| Provider | Use |
|---|---|
| `mock` | Offline. Copies source text to test the pipeline, not the prose. |
| `copilotstudio` | The approved path, through the BD tenant. Set `DHF_COPILOT_MODE=http` with `DHF_COPILOT_FLOW_URL`, or `folder` with `DHF_COPILOT_EXCHANGE_DIR`. |
| `openai`, `anthropic` | Development rehearsals on **synthetic data only**. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. |

Paid calls go through a cost ledger (`out/ledger.json`) with per-run and total spending caps. Responses are cached, and cache hits are free. A guard blocks company evidence from external AI providers.

## Real projects

To use a real ADO organization, set `ADO_BASE_URL`, `ADO_PROJECT`, `APP_ADO_PAT` and `ADO_SCOPE` in `.env`. Real organizations are read-only by default. `uv run dhf discover` drafts a field mapping for review. Company data is processed on your machine and stays under `out/`. For the full steps, see [Onboard a real project](docs/REAL_DATA_ONBOARDING.md).

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests use the mock provider and an in-process ADO mock, and never call paid APIs. CI runs the tests and the offline demo on Ubuntu and Windows.

```
src/dhf/      product: ingest, graph, trace, generate, llm, render, review, impact, cli
specs/        document templates, prompts, schemas, rules and ADO mapping (data, not code)
tools/        local ADO mock, synthetic seeder and demo (test tooling, not product)
data/         synthetic Kestrel dataset
tests/        unit and contract tests
docs/         specification, decisions, progress and onboarding
```

## Rules

- Counts, coverage, IDs and dates are computed in code, never by AI.
- Every AI claim is typed and cited, and claims with unknown citations are rejected.
- Source systems are read-only. The only write is a branch, commit or PR in the docs repository.
- Only synthetic data goes to external AI APIs.
- Secrets go only in `.env`.

The full rulebook for contributors is in [AGENTS.md](AGENTS.md).

## Documentation

- [Product brief](docs/BRIEF.md): specification and milestones
- [Onboard a real project](docs/REAL_DATA_ONBOARDING.md)
- [Decisions](docs/DECISIONS.md): architecture decision log
- [Progress](docs/PROGRESS.md): milestone evidence and known issues
- [Review](docs/REVIEW.md): review findings
