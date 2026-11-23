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

## Set up on Windows

Use **Windows PowerShell** (Start menu → type *PowerShell*). Every command below runs there.

### 1. Install Git and uv (once)

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Close PowerShell and open a new window so both commands are found, then check:

```powershell
git --version
uv --version
```

uv installs Python 3.12 for the project, so you do not need to install Python. Without winget, use [Git for Windows](https://git-scm.com/download/win) and the [uv installer](https://docs.astral.sh/uv/getting-started/installation/).

### 2. Get the code and run setup

```powershell
cd $HOME
git clone https://github.com/Rahulreddy-23/A-C.git
cd A-C
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1`:
- installs uv with winget if it is missing
- installs Python and the project libraries (`uv sync`)
- creates `.env` from `.env.example` with a key that encrypts saved Azure DevOps tokens (`uv run dhf setup`)

`-ExecutionPolicy Bypass` lets this one script run without changing any Windows setting. Running setup again is safe: it never replaces an existing key.

- **Folder:** clone into your home folder, as above, not into a OneDrive-synced Desktop or Documents folder. Syncing can lock files under `.venv` and `out`.
- **Without the script:** `uv sync` then `uv run dhf setup` do the same steps.

### 3. Start the workspace

```powershell
uv run dhf serve --project-id my-project
```

- **Browser:** your default browser opens the workspace on a one-time link.
- **Stopping:** keep the PowerShell window open while you work, and press **Ctrl+C** in it to stop.
- **Restarting:** run the same command again. Each start opens a new one-time link in a new tab, and a link works only once, so close tabs from earlier starts.
- **This computer only:** the workspace listens only on this computer (`http://127.0.0.1:8765`). If Windows asks whether Python may use networks, you can choose **Cancel**.
- **Saved work:** projects, inputs and drafts are saved under `out\workspaces\`. They are still there after you stop, and the next start lists every project.

### 4. Your first project

1. The **Projects** page opens and lists `my-project`, with no release yet. Open it, then enter its name and release under **Settings → Project**, or select **Create project** for a new one. The release (for example `1.1`) decides which test results count.
2. Under **Settings → Azure DevOps**, enter:
   - the organization URL (`https://dev.azure.com/<org>`)
   - the project name
   - how to select requirements: a saved query, WIQL, an area path or work item IDs
   - a PAT with **Work Items (Read)**, plus **Test Management (Read)** for the SSTR

   Then **Save connection** and **Test connection**.
3. Open a document from the left menu, or from a cell on the Projects page. Select **Fetch requirements**, then **Add files** for its inputs (see [Document inputs](#document-inputs)).
4. Select **Generate draft**. It uses `DHF_PROVIDER` from `.env`: `mock` by default, which needs no keys.
5. Under **Review**:
   - decide the AI suggestions, one at a time or in bulk with one rationale
   - write the sections only a person can write
   - when the document is ready, record its eQMS approval reference

### Update to the latest version

```powershell
cd $HOME\A-C
git pull
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Your `.env` and everything under `out\` are kept.

### Troubleshooting on Windows

| Problem | Fix |
|---|---|
| `git` or `uv` is not recognized | Open a new PowerShell window after installing. |
| `running scripts is disabled on this system` | Run the script as shown: `powershell -ExecutionPolicy Bypass -File .\setup.ps1`. |
| `uv sync` fails with a certificate error, such as `UnknownIssuer` | Your network inspects HTTPS. Run `powershell -ExecutionPolicy Bypass -File .\setup.ps1 -NativeTls`. |
| `Access is denied` for a file in `.venv` | Stop any running workspace (Ctrl+C) and keep the folder out of OneDrive. |
| The page says "This access link was already used, or the workspace restarted." | Close that tab. In the window running `dhf serve`, press Ctrl+C and start it again; it opens a new link. |
| "Port 8765 is already in use, probably by another DHF workspace." | A workspace is still running, for example from `setup.ps1 -Start` in another window. Stop it with Ctrl+C there, or add `--port 8766`. |
| "Saving a PAT needs APP_ENCRYPTION_KEY in .env" | Stop the workspace, run `uv run dhf setup`, then start it again. |
| "The saved PAT cannot be decrypted. Save a replacement." | The key in `.env` changed. Enter the PAT again under **Settings → Azure DevOps**. |
| `dhf` is not recognized | Run it through `uv run` from the `A-C` folder. |

To run the real project from the command line on the office laptop (read-only Azure DevOps, drafting through the BD Copilot flow), follow [docs/OFFICE_LAPTOP_GUIDE.md](docs/OFFICE_LAPTOP_GUIDE.md).

## Set up on macOS

```bash
xcode-select --install   # Git, once
brew install uv          # once
git clone https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync
uv run dhf setup
uv run dhf serve --project-id my-project
```

Then follow [Your first project](#4-your-first-project). Press Ctrl+C in Terminal to stop the workspace.

## The workspace

It opens on **Projects**: one row per project and one cell per document (SAD, SDD, SSTR, DRR, sFMEA). Each cell shows the draft version, its review blockers and its status, and opens that document. Inside a project, the left rail names the project and its release. The address always carries the project (`#/p/<project>/documents/sstr`), so Back, bookmarks and shared links open the right one. Select the project name in the top bar to switch; you stay on the same page in the other project.

| Area | What you do there |
|---|---|
| **Projects** | See every project and the state of each of its documents, create, open, archive and restore projects. Each keeps its own Azure DevOps connections, inputs, drafts and approvals. |
| **Overview** | See one project's requirements, coverage at each trace level, latest results, documentation and traceability completeness, gaps by category, and each document's status. |
| **Documents** | For SAD, SDD, SSTR, DRR and sFMEA: choose the requirements source, add existing documents and evidence, then **Generate draft** and download Word. DRR collects inputs only for now. |
| **Traceability** | Check requirements, design, code, verification and risk coverage in a filterable RTM, gaps grouped by what is missing, and the trace graph. Export the RTM as CSV. |
| **Review** | Accept or reject AI suggestions one at a time or in bulk with one rationale, write the sections only people can write, see tracked changes, and record the eQMS approval. |
| **Settings** | Set the project's Azure DevOps connection and PAT, check the AI configuration, and edit or archive the project. |

### Document inputs

Each input accepts multiple files, including multiple existing SDDs. Word `.docx` and the listed UTF-8 text, code and CSV formats are supported, up to 40 MB per file. The workspace warns when it redacts a likely secret.

- **SAD, SDD and sFMEA** accept an SRD or PRD in place of Azure requirements.
- **SSTR:** a results CSV with `Test Case ID` and `Outcome` columns, and optional `Release` and `Completed Date` columns.
- **sFMEA:** it analyses only Class C units, so every unit needs a recorded IEC 62304 class.
  - When the design documents do not state one, add a **Safety classification** CSV with `Item` (unit or component ID or title) and `Safety class` (`A`, `B` or `C`) columns.
  - The file fills only classes the evidence does not state, and a unit's own class wins over its component's.
  - Drafting stops and names the units still missing a class; it never guesses.

### Keeping drafts current

Drafts are saved under `out/workspaces/<project-id>/<document>/drafts/`. After evidence changes, the document page lists which sections went stale, and why.

- **Update draft** redrafts only the stale sections, and the Word file shows the changes as tracked changes.
- **After a release change,** **Update draft** redrafts every section. **Redraft from scratch** does the same on demand, as a new version.
- **Approval:** a recorded eQMS reference makes that version the baseline. A later change needs approval again.

### Access and tokens

- **Access link:** the local workspace uses a one-time access link for the owner. Add local members with repeated `--member` flags; each member gets their own link.
- **PATs:** they are encrypted with `APP_ENCRYPTION_KEY` and never shown again. PAT changes are attributed to the signed-in local session, and the browser shows an expiry when you supply one from Azure DevOps.
- **Future work:** hosted organization sign-in and Key Vault integration. See the [Microsoft PAT documentation](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops).

## Configuration

Settings are read from `.env`, which git ignores and `dhf setup` creates. The defaults work for the browser workspace with the mock AI provider.

| Setting | Purpose |
|---|---|
| `APP_ENCRYPTION_KEY` | Encrypts saved PATs. `dhf setup` fills it in; keep it unchanged. |
| `APP_ADO_MAPPING` | Optional custom Azure DevOps work-item mapping for the browser workspace. |
| `DHF_PROVIDER` | The AI provider for drafting (see [AI providers](#ai-providers)). |
| `ADO_*`, `APP_ADO_PAT` | Command-line ingest only. The defaults point at the local Azure DevOps mock. |

Enter Azure DevOps credentials in the browser, never in `.env`. AI credentials go in `.env`.

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
| `uv run dhf setup` | Creates `.env` from `.env.example` with a PAT encryption key; never replaces an existing key. |
| `uv run dhf serve` | Opens the DHF workspace in the browser: projects, documents, traceability, review and settings. |
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

These commands are the same in PowerShell and macOS Terminal:

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
