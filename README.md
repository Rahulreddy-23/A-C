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
