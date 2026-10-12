# A-C
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

OpenAI prompt tuning uses `gpt-4.1-mini` ($0.40 input / $1.60 output per million tokens, verified against https://developers.openai.com/api/docs/models/gpt-4.1-mini). Existing `.env` files are preserved; override old settings with `DHF_MODEL_OPENAI=gpt-4.1-mini DHF_OPENAI_INPUT_PER_MILLION=0.40 DHF_OPENAI_OUTPUT_PER_MILLION=1.60`. Nano remains an optional smoke test with its matching prices. Offline runs still default to mock.

Redlines compare visible paragraphs and individual cells in source-keyed table rows. Hyperlink destination updates alone do not mark text changed; Git artifact labels show short revisions. Word comments are reserved for review items. Synthesis sections use a 12k-token input budget with deterministic context reduction; the manifest records reductions and distinct failure reasons.
