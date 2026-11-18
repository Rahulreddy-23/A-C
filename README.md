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
uv run dhf serve --project-id my-project
```

The browser workspace starts empty for a new project. Choose SAD, SDD or SSTR. DRR is available for input collection as a future document type.

1. To save a PAT, generate a Fernet key and set `APP_ENCRYPTION_KEY` to that value in the ignored `.env` file or process environment. Keep the key stable across launches.

   ```bash
   uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. Under **Azure DevOps Requirements Source**, enter the organization URL, project name, PAT and selector. Save the project default or choose **Override for this document**. Use **Work Items (Read)** and include **Test Management (Read)** for SSTR. Select **Test Connection**, then **Fetch Requirements**. SSTR can also fetch results for selected Test Plan or Test Run IDs.
3. Add files to the document checklist. Each input accepts multiple files, including multiple existing SDDs. SAD and SDD accept an SRD or PRD in place of fetched Azure requirements. Word `.docx` and the listed UTF-8 text, code and CSV formats are supported, up to 12 MB per file. The workspace shows a warning when it redacts a likely secret. For structured SSTR results, CSV accepts `Test Case ID`, `Outcome`, and optional `Release` and `Completed Date` columns.
4. Review **Requirements Snapshot** and **Open evidence explorer**. Select **Save evidence for drafting** to create `out/workspaces/<project-id>/<document-type>/evidence.sqlite`. Use that database with the existing drafting command and specify the actual release and approved provider.

   ```bash
   uv run dhf generate sdd --db out/workspaces/my-project/sdd/evidence.sqlite --documents out/workspaces/my-project/sdd/drafts --release 2.0 --provider copilotstudio
   ```

The browser shows verified access and an expiry when you supplied one from Azure DevOps. Reading PAT lifecycle metadata requires a separate user-delegated Microsoft Entra credential. The local workspace uses a one-time access link for the owner. The owner can add local members with repeated `--member` flags. PAT changes are attributed to the signed-in local session. Hosted organization sign-in and Key Vault integration are future deployment work. [Microsoft PAT documentation](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops)

## Configuration

Settings are read from `.env`, which git ignores. Create it from the template:

| macOS | Windows (PowerShell) |
|---|---|
| `cp .env.example .env` | `Copy-Item .env.example .env` |

The browser reads `APP_ENCRYPTION_KEY` and optionally `APP_ADO_MAPPING` from configuration. Enter its Azure credential in the browser form. The CLI development defaults point at the local ADO mock. Store AI credentials in `.env`.

To run the real project on the office laptop (read-only ADO, drafting through the BD Copilot flow), follow [docs/OFFICE_LAPTOP_GUIDE.md](docs/OFFICE_LAPTOP_GUIDE.md).

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
| `uv run dhf refresh` | Reads ADO again, records changes and stale sections, and updates the gap reports and explorer. |
| `uv run dhf serve` | Opens the local document workspace for Azure requirements and file uploads. |
| `uv run dhf serve --explorer-only` | Opens the existing CLI evidence explorer and its **Refresh from ADO** action. |
| `uv run dhf audit-pack` | Exports drafts, provenance and verified hashes as a ZIP. |

## Review workflow

1. `generate --open-pr` opens a draft PR with Markdown, Word and a manifest.
2. Reviewers edit the Markdown in the PR. AI suggestions are marked `[Suggested — review required]`. To accept one, remove that prefix; to reject it, remove the claim. In both cases, record the decision with the claim's `dhf-claim` ID, as `accepted` or `rejected`:
   ```md
   <!-- dhf-resolution:<claim-id> accepted reviewer=Name rationale=Why -->
   ```
3. `check --pr-id` rebuilds the Word document and posts the `DHF review readiness` status.
4. A person merges the PR. `baseline` tags it (`sstr-v1`, `sstr-v2`, …), and later drafts show Word redlines against that baseline.

The tool never merges PRs and never writes to ADO work items or source repositories. Approvals and e-signatures stay in the eQMS.

## AI providers

Set `DHF_PROVIDER` in `.env` or choose a provider per command with `--provider`. The default is `mock`.

| Provider | Use |
|---|---|
| `mock` | Offline. Copies source text to test the pipeline, not the prose. |
| `copilotstudio` | The approved path, through the BD tenant. Set `DHF_COPILOT_MODE=http` with `DHF_COPILOT_FLOW_URL`, or `folder` with `DHF_COPILOT_EXCHANGE_DIR`. |
| `openai`, `anthropic` | Development rehearsals on **synthetic data only**. Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. |

Paid calls go through a cost ledger (`out/ledger.json`) with per-run and total spending caps. Responses are cached, and cache hits are free. Company evidence requires a recorded clearance and verified destination for the BD Copilot flow. Personal API providers require synthetic evidence.

## Scripted CLI onboarding

For direct CLI ingest from a real organization, set `ADO_BASE_URL`, `ADO_PROJECT`, `APP_ADO_PAT` and `ADO_SCOPE` in `.env`. Real organizations are read-only by default. `uv run dhf discover` drafts a field mapping for review. Company data is processed on your machine and stays under `out/`. [Onboard a real project](docs/REAL_DATA_ONBOARDING.md)

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests use the mock provider and an in-process ADO mock. CI runs the tests and the offline demo on Ubuntu and Windows. Run `uv run python tools/demo.py` explicitly to rehearse with synthetic data.

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
- Browser PATs are encrypted in local SQLite. Encryption and provider keys stay in the environment or ignored `.env`.

The full rulebook for contributors is in [AGENTS.md](AGENTS.md).

## Documentation

- [Product brief](docs/BRIEF.md): specification and milestones
- [Onboard a real project](docs/REAL_DATA_ONBOARDING.md)
- [Decisions](docs/DECISIONS.md): architecture decision log
- [Progress](docs/PROGRESS.md): milestone evidence and known issues
- [Review](docs/REVIEW.md): review findings
