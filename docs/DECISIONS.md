# Architecture Decision Log

Append-only. Format: `ADR-NNN — Title` · date · status · context · decision · consequences.

## ADR-001 — Evidence graph first, LLM second
2026-10-12 · Accepted
- **Context:** Scoring weights traceability, workflow fit and sourced-vs-inferred accuracy at 70%.
- **Decision:** All IDs, links, counts and coverage are computed deterministically from an evidence graph. LLMs only write prose and suggestions as typed, cited claims that a validator checks.
- **Consequences:** Invented IDs are impossible by construction. The design is cheap, and prompts are portable across models.

## ADR-002 — Pull-request review as the change-tracking backbone; DOCX redlines on top
2026-10-12 · Accepted
- **Context:** Change tracking for human review is mandatory. Power Automate can fill Word templates but can't produce tracked changes.
- **Decision:** Generated documents (md + docx + manifest) go to a docs repo via ADO PRs. The PR diff is the redline, required reviewers handle review, and baseline tags mark approved versions. The reference implementation also emits DOCX with real tracked changes.
- **Consequences:** Works in both the reference implementation and Copilot Studio (ADO REST). DOCX redlines in Copilot Studio need an Azure Function or fall back to Word Compare.

## ADR-003 — Python reference implementation + Copilot Studio port pack
2026-10-12 · Accepted
- **Context:** The final submission must run in Copilot Studio. Prototyping uses paid APIs with a $5 budget per provider.
- **Decision:** Build a Python reference implementation and prompt lab. Prompts, specs, schemas and rules live as data, and each step is a pure JSON function so it maps 1:1 to flows and prompt tools. A port pack documents the mapping.
- **Consequences:** No second product to maintain. The port to Copilot Studio is mechanical.

## ADR-004 — Free ADO org on the CMMI process for development
2026-10-12 · Superseded by ADR-005
- **Context:** The hackathon dataset isn't available yet, and ADO integration is mandatory.
- **Decision:** Seed a free ADO org (CMMI process: Requirement, Risk, Review, Bug, Test Case) from a synthetic dataset. All mapping lives in `specs/ado_mapping.yaml`.
- **Consequences:** Real ADO integration is testable now. Swapping in the company process means changing config, not code.

## ADR-005 — Contract-faithful local ADO mock instead of a real org (for now)
2026-10-12 · Accepted · Supersedes ADR-004
- **Context:** No ADO org is available yet. ADO integration is mandatory and must be credible in the demo.
- **Decision:** Build `tools/mock_ado/`, a stdlib HTTP server implementing the subset of the ADO REST API (api-version 7.1) we use, with real response shapes, real revision history, git-backed repos, clickable HTML pages, scenario injection, and a PAT guardrail that refuses product writes outside the docs repo. The product's ADO adapter is the real one and points at `ADO_BASE_URL`. One contract test suite runs against the mock, and against a real org via `pytest -m live_ado`.
- **Consequences:** No dependency on credentials or network. The demo is deterministic and repeatable. Moving to a real org (M11) means changing config and running the seeder. Risk: the mock drifts from real ADO behavior, mitigated by following the official response shapes and running the live contract suite once an org exists.

## ADR-006 — Conservative pre-call reservations
2026-10-12 · Accepted
- **Context:** Paid requests may fail after consumption; token estimates must not allow budget overruns.
- **Decision:** Reserve cost using UTF-8 bytes as an upper bound on input tokens and the maximum output tokens. Persist under an exclusive file lock before the request; retain reservations after failures. The ledger reports reserved cost, not a fabricated invoice amount.
- **Consequences:** Budget enforcement is conservative. Models and prices remain config; owner verifies live pricing before live checks. External requests reject evidence not explicitly synthetic.

## ADR-007 — Structured provider output and settled spend
2026-10-12 · Accepted (owner requested R-003–R-005 fixes)
- **Context:** Current Haiku 5.5 rejects temperature zero and emits thinking blocks; successful requests expose actual usage. See https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide and https://platform.claude.com/docs/en/models/haiku-5-5/overview.
- **Decision:** Both adapters request the claims JSON schema, reject truncation/refusal and return usage. Haiku uses low effort and default sampling (necessary exception to temperature zero requested by the owner); OpenAI uses temperature zero. SDK retries are disabled so one budget reservation covers one request. Successful usage settles reservations into actual_usd; failures retain reserved_usd. Persist actual + outstanding for cap enforcement.
- **Consequences:** Cache and validator provide repeatability for Haiku. Paid input is bounded to the configured small-prompt pricing tier. Credentials are read via config without entering process globals. No live calls have been made.

## ADR-008 — Synthetic fixture metadata and source-write guard
2026-10-12 · Accepted
- **Context:** The real org process has not been configured. Contracts must use ordinary ADO fields and Git transport.
- **Decision:** Encode stable IDs in DHF tags, fixture-only structured attributes in the description/comment following DHF-META, and typed Related relation names in DHF metadata. Use native Parent and Tests relation reference names where applicable. Device Git's pre-receive hook independently rejects non-seeder pushes. Public mock HTML contains only synthetic fixtures.
- **Consequences:** No custom ADO fields are required for the demo. Real-org field/tag mapping remains data configuration; source without synthetic markers cannot be sent to paid providers.

## ADR-009 — Immutable JSON snapshots and stable per-file revisions
2026-10-12 · Accepted
- **Context:** A commit affecting one unit must not mark all units changed. Pure JSON transformations must remain portable.
- **Decision:** Validate/normalize evidence, diff graphs and extract code as pure functions. SQLite persists complete immutable JSON snapshots transactionally. Git unit revision is its blob object ID, with citation URLs pinned to the last commit touching that file. Link changes also flag their source artifact.
- **Consequences:** Fixture/HTTP parity preserves semantic fields and source revisions, normalizing transport URL/native ID, retrieval time and link-evidence descriptions. Historical snapshots remain readable; selective impact can compare any pair.

## ADR-010 — Native ADO fields and explicit code traces
2026-10-12 · Accepted · Supersedes ADR-008's structured-attribute encoding
- **Context:** Reviewer R-009 showed that fixture JSON descriptions hid real integration problems; R-010 required substantive source evidence for credible DHF drafts.
- **Decision:** Normalize native rev/ChangedDate/revision-history, AreaPath, acceptance criteria, severity, state, residual-anomaly tags, test steps XML, completedDate, testRun, associatedBugs and PR work-item references. Configured work-item type pairs determine Related semantics. Extract explicit Implements annotations from unit source. Fixture metadata holds only the synthetic marker; stripping it changes no semantic graph data. Assigned fictional harm severities and their scale live in the risk fixture; sixteen safety modules now have substantive state, validation and recovery behavior.
- **Consequences:** G11 derives staleness from native completion times/history, with no verified_revision field. Ordinary source narratives retain context, measurable acceptance criteria, test steps, anomaly impact and ADR reasoning. Source schemas and area/tag mappings remain configurable. R-011 contract fixes are included while this area is being changed.
