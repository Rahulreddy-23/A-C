# A-C

New to the project? Start with the [plain-language project and local demo guide](docs/LOCAL_DEMO_GUIDE.md).

## 60-second quick start

With Python 3.12 and uv installed:

```sh
git clone --branch dev https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync --locked
./scripts/demo.sh
```

The offline demo owns a fresh native ADO mock and mock LLM config. No keys or .env changes are needed. Read `out/demo-latest.json` for generated Word drafts, explorers, tracked redline and audit ZIP. Use [the timed demo script](docs/DEMO_SCRIPT.md) and [judging map](docs/JUDGING_MAP.md); [checked-in fallbacks](data/demo/fallback/README.md) work before a demo run.

`./scripts/demo.sh --pause-before-change` pauses for the on-stage update. For the official AI path, configure the BD tenant's [generic prompt runner](port/copilot_studio/day1/generic_prompt.md), set `DHF_COPILOT_MODE=http` with a signed `DHF_COPILOT_FLOW_URL` in ignored `.env`, and run `DHF_LIVE_PROVIDER=copilotstudio ./scripts/demo.sh --live`. If HTTP is DLP-blocked, set `DHF_COPILOT_MODE=folder` and `DHF_COPILOT_EXCHANGE_DIR` for the [OneDrive document exchange](port/copilot_studio/day1/onedrive_prompt_flow.md). Preview one exact section payload with `uv run dhf copilot-request sstr anomaly_assessment --db out/evidence.sqlite` after ingest. Token usage defaults to strict `DHF_COPILOT_USAGE=reported`. If Run a prompt exposes no counts, omit them in the flow response and set `DHF_COPILOT_USAGE=estimated`; valid reported counts are preferred, and missing counts receive a labelled local estimate. Ledger/manifests/metrics preserve `usage_source`. Local credits are estimated under a 400-credit cap; check actual usage in tenant Monitor. Neither tenant mode has been run by this repo. If both modes fail, use the native Copilot Studio MVP and label other AI text as development output. Personal OpenAI/Anthropic `--live` runs remain development rehearsals only.

## DHF Automation — How to run

Python 3.12 and uv are required (`out/bin/uv` is the local workstation install).

```sh
uv sync
uv run dhf --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Configuration comes from the ignored `.env`. Copy `.env.example` on a fresh clone.
Tests use mock LLM responses and never call paid APIs. Provider model names and
prices are configurable; verify current pricing before enabling live calls.
Budget accounting reserves a conservative upper-bound cost before each request,
including failed requests. Cache hits are free. Paid calls require synthetic evidence.

The synthetic ADO backend uses real local bare Git repos and loopback HTTP:

```sh
uv run mock-ado init
uv run mock-ado serve --port 8089
# In another terminal:
uv run mock-ado apply-scenario change_1
uv run mock-ado reset
```

REST uses Basic-auth mock PATs from `.env.example`. Only the seed token can
invoke admin endpoints. The app token is refused source writes, and a Git
pre-receive hook independently rejects product pushes to the device repo.
Browser pages are public and contain only synthetic data. Run contract tests
with loopback sockets permitted; external network is blocked by the test fixture.

```sh
uv run dhf ingest --source fixtures   # offline file adapter
uv run dhf ingest --source ado        # HTTP + device Git clone; start mock first
```

Every ingestion stores an immutable SQLite snapshot, provenance, content hashes,
revisions and added/changed/removed IDs. Code units and signatures come from Python
ASTs, SOUP versions from pinned dependency manifests, and implementation links
from explicit ADO PR references and `AB#` commit messages. Real evidence lacking
explicit synthetic metadata is rejected by the external-provider guard.

ADO ingestion uses native revisions/history, ChangedDate, AreaPath, configured
acceptance-criteria and severity fields, state, residual-anomaly tags, test steps,
run/result completion times and associated bugs. Related-link type pairs and area
allocation are configured in `specs/ado_mapping.yaml`. Units also carry explicit
`# Implements: SRS-...` source annotations. The optional fixture marker controls
only the synthetic-data guard; no engineering fact depends on its JSON contents.

```sh
uv run dhf gaps                # out/gaps.md + JSON and coverage
uv run dhf rtm --release 1.1    # out/rtm.md + JSON
```

Only explicit or human-confirmed links count. Gap definitions live in YAML.
G11 compares native requirement-change history with the last passed result time.

Generate the system test report after ingesting evidence:

```sh
uv run dhf generate sstr --release 1.1
```

Documents and provenance manifests appear in `out/documents/`. SSTR summary tables
use the latest result for each test case. AI text is typed and cited; suggested
release conclusions and residual-anomaly rationale require review. Approval fields
remain for human input. The default provider is `mock`, which copies source prose
for offline workflow testing rather than judging evidence quality.

The owner can compare one section with both paid providers, through the guarded
LLM layer (synthetic evidence, ledger, cache and budget caps):

```sh
uv run dhf generate-section sstr purpose_scope --provider anthropic
uv run dhf generate-section sstr purpose_scope --provider openai
```

Inspect `out/cross-provider/` for typed claims, citations and validation events.
`dhf ingest --verbose` prints the complete change lists; normal output shows counts
by artifact type and at most twenty changed IDs.

Create a docs-repo draft PR with Word output and its manifest:

```sh
uv run dhf generate sstr --release 1.1 --open-pr
uv run dhf check sstr --pr-id <id>
```

The checker fetches the edited PR Markdown, rebuilds Word output and posts the
`DHF review readiness` status. A model refusal leaves a manual-authoring
placeholder and blocks readiness while other sections still generate. Provider
errors print sanitized metadata; `--debug` includes safe diagnostic details.

Reviewers edit the Markdown in the docs PR. To accept a suggested claim, remove
its `[Suggested — review required]` prefix and record its `dhf-claim` identifier:

```md
<!-- dhf-resolution:<16-character-claim-hash> accepted reviewer=YourName rationale=Your reviewed rationale -->
```

To reject it, remove the claim text and record the same marker with `rejected`.
Fill human placeholders in the existing section boundaries. To manually author
an unavailable AI section, replace its placeholder and record:

```md
<!-- dhf-authoring:residual_anomalies reviewer=YourName rationale=Manually authored and reviewed -->
```

Validator rejections also need a `dhf-validation:<event-hash> reviewed` marker
with reviewer and rationale. These decisions are saved in the review manifest.
Readiness is a draft-completeness gate; company approval and e-signatures remain
in the eQMS. After the owner merges a ready PR, create its controlled baseline:

```sh
uv run dhf baseline sstr --pr-id <id>
```

Baseline tags (`sstr-v1`, `sstr-v2`, …) drive paragraph-level Word redlines in
subsequent drafts. The product never merges a PR. Test tooling separately offers
`mock-ado merge-docs-pr <id>` to simulate an owner's merge on the local mock.

OpenAI prompt tuning uses `gpt-4.1-mini` ($0.40 input / $1.60 output per million tokens, verified against https://developers.openai.com/api/docs/models/gpt-4.1-mini). Existing `.env` files are preserved; override old settings with `DHF_MODEL_OPENAI=gpt-4.1-mini DHF_OPENAI_INPUT_PER_MILLION=0.40 DHF_OPENAI_OUTPUT_PER_MILLION=1.60`. Offline runs still default to mock.

Redlines compare visible paragraphs and individual cells in source-keyed table rows. Hyperlink destination updates alone do not mark text changed; Git artifact labels show short revisions. Word comments are reserved for review items. Synthesis sections use a 12k-token input budget with deterministic context reduction; the manifest records reductions and distinct failure reasons.

Generate design drafts and check their component inventories:

```sh
uv run dhf generate sad --release 1.1
uv run dhf generate sdd --release 1.1
uv run dhf consistency
```

The SAD includes checksummed local Mermaid source and PNG files, with the figure embedded in Word. The SDD groups extracted
interfaces, structures and explicit allocations per unit. Missing recorded unit
tests are shown as gaps in the source evidence. Offline mock prose verifies the
pipeline structure; use a configured provider for human-reviewed prose tuning.
The SSTR always lists every failed or blocked result before its AI assessment.

Change impact and selective regeneration:

```sh
uv run dhf watch --interval 60
uv run mock-ado apply-scenario change_1
uv run dhf impact --since baseline
uv run dhf regenerate --stale --open-pr
uv run dhf consistency
```

The local document manifest records its source baseline. `--since` also accepts an ingest snapshot number or UTC timestamp. Direct revision changes and changed query facts are stale; confirmed one-hop neighbors are labelled possibly affected and require review. Regeneration preserves every untouched section's edited Markdown bytes. To get a PR containing only these changes, start from a human-reviewed, merged document baseline. Draft and latest approved baseline consistency are both checked; `--no-baselines` checks local drafts without contacting ADO. Historical SAD v1 deliberately has C01/C04 findings. `watch --cycles 2` gives a finite demonstration run; Ctrl+C stops continuous polling.

Risk analysis and design review drafts:

```sh
uv run dhf generate drr --input-file data/synthetic/review_input.json --since 1
uv run dhf generate sfmea --release 1.1
uv run dhf propose
```

DRR identity comes from your JSON input (`type`, `date`, `baseline`, `participants`); `--since` selects the previous ingested snapshot for its deterministic scope diff. Discussion, decisions, new actions and approvals remain human fields. Supply `--impact-file <saved-report>` explicitly to include impact findings; reports from unrelated runs are never loaded implicitly. sFMEA keeps source severity/controls/verification separate from the suggested analysis cells and human residual-risk assessment. Proposed failure modes do not close F03 until confirmed by a reviewer. L01–L03 proposal files are local suggestions with citations/confidence; they never update ADO. SAD/SDD use grouped navigation headings, readable structure columns and named hazards/controls. G12 identifies missing SOUP requirements or known-anomaly evaluation; the synthetic baseline now has 21 deterministic gaps.

The [Copilot Studio port pack](port/copilot_studio/README.md) maps the reference to Dataverse, prompt tools and seven Power Automate flows. Run `uv run python tools/check_port.py` to verify exact prompt/contract coverage. Tenant deployment and parity remain pending capability verification.


Run the complete offline synthetic demo after `uv sync`:

```sh
./scripts/demo.sh
```

Each run starts its own loopback ADO mock and Git repositories in a fresh `out/demo/` folder, uses only the mock LLM, and shuts the server down afterwards. It demonstrates docs PRs, blocked readiness, explicit **test-tooling** simulation of human draft review/owner merge, controlled baselines, live `change_1`, selective redline PRs, YAML-only SUTR/RTM, evaluation and a verified audit ZIP. No eQMS approval is simulated. `out/demo-latest.json` gives paths to the newest run; `out/metrics.md` and JSON contain its metrics. Dependencies must already be installed; the script runs uv offline without synchronization.

```sh
uv run dhf generate sutr --release 1.1
uv run dhf generate rtm --release 1.1
uv run dhf eval --impact-file out/impact.json
uv run dhf audit-pack --release 1.1
```

Use `--db` and `--documents` to select a demo run's saved evidence/drafts. For impact evaluation, use its saved **pre-regeneration** report, listed in `out/demo-latest.json`; a missing report is pending, never a perfect score. Impact metrics are regression against a reviewer-audited expectation. The clause appendix indexes source evidence and flags missing unit/integration results and human assessment; it does not assert compliance. Audit export includes prior source revisions used by manifests, cited RTM/gap reports and SHA256SUMS; tampering or a missing referenced source revision fails export/verification.

To switch to a real ADO organization, the owner sets `ADO_BASE_URL`, `ADO_PROJECT`, `ADO_DEVICE_REPO`, `ADO_DOCS_REPO`, source-read/docs-write `APP_ADO_PAT` and `ADO_REQUIRED_REVIEWERS` in the ignored `.env`. Review `specs/ado_mapping.yaml` against the organization's process first. Keep seeder credentials separate; the optional M11 seeder/live contract run is pending a real org. Real company evidence is forbidden from external LLM providers. The latest owner budget instruction imposes a cumulative hard caps of **$2.50 for Anthropic / $4.00 for OpenAI**, actual plus reserved, with Codex's $1.50 build cap and $0.25 run cap; legacy $5 configuration cannot raise those hard caps. Owner `.env` is preserved.

The [sandbox build plan](port/copilot_studio/BUILD_PLAN.md) has three capability tiers, estimates, a cut line and the native/offline demo split. [Sandbox questions](docs/SANDBOX_QUESTIONS.md) select the tier. Tenant execution and native parity still require those capabilities and a recorded test run.


Sections select `model_tier: default|analytical` as YAML data. OpenAI defaults to GPT-4.1 mini, with GPT-5.4 mini for risk modes, SSTR conclusion, DRR suggestions and L01–L03. Set `DHF_MODEL_OPENAI_ANALYTICAL` to change that tier. Per-model prices live in `specs/llm/prices.yaml` and accept model-specific overrides (e.g. `DHF_OPENAI_GPT_5_4_MINI_OUTPUT_PER_MILLION`); unknown models require explicit prices. GPT-5 calls omit temperature, use `DHF_OPENAI_REASONING_EFFORT=low` and reserve the visible cap plus `DHF_OPENAI_REASONING_TOKENS=4000` inclusive completion allowance. Each section records model ID and tier; cache identity includes model/tier/reasoning settings. Paid command output shows cumulative headroom. No nano models are enabled. [Official GPT-5.4 mini pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [reasoning token billing](https://developers.openai.com/api/docs/guides/reasoning).

For Phase 2 onboarding, run `uv run dhf discover` to inspect native fields/types/tags/links and create a mapping draft, then follow [REAL_DATA_ONBOARDING.md](docs/REAL_DATA_ONBOARDING.md). `uv run seed-ado --confirm-org kestrel-org --dry-run` previews the synthetic seeder. Only the separate seed identity can create source work items, test evidence and source Git history; `dhf` remains read-only outside the docs repo.

If the sandbox has no ADO connector, `uv run dhf export-snapshot --db out/evidence.sqlite --output-dir out/snapshot-export` writes a local canonical graph JSON, Artifact/TraceLink CSV and SHA256 index for a **reviewed synthetic import**. The post-`change_1` graph can be exported the same way for the impact demonstration. This command does not upload or modify ADO. Follow the [M15 day-1 kit](port/copilot_studio/day1/README.md) and [Tier C-prime path](port/copilot_studio/BUILD_PLAN.md#tier-c-prime-no-ado-connector); tenant execution remains pending.

Claim-support review is a second, advisory pass:

```sh
uv run dhf verify-support --doc sstr --sample 5
uv run dhf eval
# Only for synthetic evidence, when live verification is needed:
uv run dhf verify-support --doc sstr --sample 5 --provider openai
```

`--sample 0` checks every sourced/inferred claim in the selected document; suggestions are not asserted source facts and are excluded. Supported/partial/unsupported findings stay in the manifest and produce advisory Word comments; no original claim is removed and readiness is unchanged. Mock support uses lexical comparison, not semantic proof. `specs/metrics/manual_effort.yaml` supplies explicit draft-authoring assumptions, with human review excluded from estimated savings. Metrics show section counts, generation/verifier time and cost, support rate and assumption-based hours saved.


`uv run dhf explore` writes `out/explorer.html`: a read-only offline DHF workspace. Overview shows computed coverage and verification; Documents exposes generated sections and typed, revision-cited claims; Findings filters G/C/F rules with recorded actions; Change impact distinguishes directly stale and possibly affected sections; Risk evidence shows recorded hazard/control/requirement/test paths. Traceability provides a connected graph, direct-link/full-trace scopes, pan/zoom, an artifact search drawer, a complete evidence index and source inspection. Names wrap fully. Use `--db`, `--documents`, `--output` for a separate run, or `--impact-file` for a saved pre-regeneration assessment. Include the generated documents directory to populate the document reader. Open generated HTML, rather than the template in `specs/render`. Source links navigate only on an explicit click; the page loads no external resources. Generation and publishing continue through the CLI. Audit ZIPs include `trace/explorer.html`.
