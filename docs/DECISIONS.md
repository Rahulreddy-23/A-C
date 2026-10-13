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

## ADR-011 — Declarative gaps and latest-result counts
2026-10-12 · Accepted
- **Context:** Trace quality must be measurable against independent planted issues and cope with retests.
- **Decision:** Store rule predicates in YAML and evaluate only explicit/human-confirmed links. RTM joins requirements to components, completed PRs, units, tests and the latest result for each case in a release. G11 compares native history/change time to the last pass time. All summary statistics are deterministic.
- **Consequences:** Sixteen findings exactly match eleven rule answer keys. Orphan tests still count in release totals but cannot improve requirement coverage. A retest replaces a case's prior result rather than inflating totals.

## ADR-012 — Bounded evidence packs and section manifests
2026-10-12 · Accepted
- **Context:** Narrative source text can name artifacts outside a query's initial selection. Each prompt must stay bounded without discarding referenced context.
- **Decision:** Named queries compute facts and expand source-body ID references. Partitioning preserves each artifact's referenced context within the conservative byte budget, failing explicitly on oversized artifacts. Claims pass the same unknown-ID, number, citation and kind rules on every provider. Sections store query fingerprints, cited revisions, rendered text and validation events.
- **Consequences:** Retrieval timestamps cannot invalidate response caches. Deterministic Markdown has exact golden comparisons. Single-section CLI runs support the owner-run cross-provider check without paying for a complete document.

## ADR-013 — Provider-compatible schemas and manual fallback
2026-10-12 · Accepted (R-019/R-020)
- **Context:** The live check found unsupported numeric bounds in Anthropic's schema and a refusal on residual anomalies.
- **Decision:** Strip numeric-bound keywords recursively from the provider schema, retaining Pydantic's local bounds. Refusal, truncation, malformed output, provider failure or exhausted drafting budget yields an ai_unavailable section with a manual-authoring placeholder, safe reason metadata and no automatic retry. The document and manifest still persist; the readiness gate blocks the section.
- **Consequences:** A refused section cannot become a completed draft. The single live residual-anomaly recheck still refused with category bio, so its placeholder is retained. Failed calls retain conservative ledger reservations. SDK failure metadata excludes provider messages and payloads.

## ADR-014 — Single-call synthesis and readable evidence views
2026-10-12 · Accepted (R-016/R-017/R-021/R-022/R-023)
- **Context:** The live conclusion restated requirements across many calls and misclassified coverage terminology as artifact IDs; provider errors also exposed message text.
- **Decision:** Scope conclusions to adverse outcomes, linked defects, open anomalies and deterministic gap/coverage facts. Purpose and conclusion use one bounded call; other sections may partition. Specs cap accepted claims globally; excess claims are rejected and audited. Model-facing views retain artifact IDs, body, revision and human-labelled properties. Numeric ID shapes and unit IDs are recognized, with explicit citations always checked against the pack. Table labels and columns come from specs; links belong in cells, displayed hashes are short, and manifests retain complete provenance. SDK errors become safe metadata; CLI diagnostics omit exception messages and show sanitized stack details only with --debug. Ledger entries retain previous token counters before accumulating new usage.
- **Consequences:** No cross-chunk citation loss in synthesis sections. Query and full provenance remain auditable even when compact provider inputs omit transport metadata. Existing pre-fix ledger token totals cannot be reconstructed; subsequent calls accumulate correctly.

## ADR-015 — Exact citation normalization and guarded OpenAI tuning
2026-10-12 · Accepted (R-024)
- **Context:** Nano cited a known source URL instead of its artifact ID, and relationships were absent from model inputs.
- **Decision:** Normalize only unique exact source URL matches to artifact IDs and audit each transformation. Unknown, ambiguous and modified URLs still fail validation. Model views omit URLs; the original chunk provenance is used for validation. Failed-result queries inject explicit defect relationships as facts. OpenAI dev defaults are GPT-4.1 mini at $0.40 input/$1.60 output per million tokens (https://developers.openai.com/api/docs/models/gpt-4.1-mini, checked 2026-10-12). Never rewrite the owner's .env.
- **Consequences:** A single guarded live check returned six validated claims; inspection found a false missing-link statement, prompting the explicit relationship facts. Clone remotes are checked and isolated when ADO configuration changes. Docs review gates remain human-controlled; mock merge simulation is test tooling only.

## ADR-016 — Visible-text redlines and synthesis token budgets
2026-10-13 · Accepted (R-025/R-026/R-027/R-028)
- **Context:** The end-to-end change scenario redlined whole tables and overflowed a byte limit labelled as tokens.
- **Decision:** Match paragraphs on visible text and align table rows by source ID (rule plus artifact for repeated gap rows). Compare matched cells independently. Link-target changes update hyperlinks without a redline; Git revision labels remain visible. Hyperlinks enclose tracked run markup so their labels render in Word-compatible local previews. Keep comments for inferred/suggested/manual review items; inferred comments include the basis and confidence footnote.
- **Decision:** Use ceil(UTF-8 bytes / 3) for all section token-budget comparisons, including prompt/schema overhead, with 12k-token synthesis limits. The spend ledger retains its stricter byte-as-token worst-case reservations. Oversized synthesis views retain adverse results, defects and gap facts; omit supporting context with deterministic counts and audit IDs, then excerpt critical narratives if required. Full evidence stays in the source graph. Impossible minimum facts/configuration limits report evidence_over_budget; output validation and spend caps have distinct reasons and safe internal messages. Prompt versions are bumped; conclusion instructions stay in the conclusion.
- **Consequences:** change_1 produces no unavailable sections and only 46/744 paragraphs and 15/175 rows carry changes. Invalid or exhausted drafting still blocks human readiness. No paid calls are needed for this regression.

## ADR-017 — Repeated design sections and source diagram fallback
2026-10-13 · Accepted
- **Context:** SAD and SDD must expose every source component and unit without oversized monolithic prompts.
- **Decision:** YAML repeat declarations expand adjacent sections together per component or unit. AST extraction returns callable signatures and class fields. Allocation tables use explicit traces. Architecture diagrams emit local Mermaid source with a manifest checksum; no remote renderer is used. C01 compares the document component inventories to code. Missing unit-test traces are stated explicitly.
- **Consequences:** All six components and twenty units are represented. Mock unit prose is structural smoke-test output, not a live narrative-quality claim. Mock model revision v2 invalidates prior cached fixture prose. R-029 adds a deterministic adverse-result table before AI drafting, including when drafting fails.

## ADR-018 — Section impact and approved-baseline consistency

Direct cited revisions and authoritative query-fact changes trigger regeneration; added result IDs and confirmed dependency paths identify the cause. Numeric validation context alone does not trigger staleness. One-hop neighbors remain explicitly possibly affected. The checked-in scenario expectations are frozen, reviewed cause records, not computed by the evaluation harness. Untouched edited section bytes are retained using stable section boundaries. Impact marks stale evidence in manifests so readiness blocks until regeneration. C01–C04 inspect both drafts and the latest approved docs-repository tags, importing the older Markdown SAD inventory when no manifest exists. A selective PR requires an existing reviewed baseline; the product never creates approval or merges it.

## ADR-019 — Structural design evidence before narrative synthesis

Component records now have distinct responsibilities, declared collaborators and interfaces; these records are also the generated architecture.yaml source. AST resolves imported function calls to source units and components. The synthetic pressure_alarm integration actually calls the shared latch, providing an evidenced COMP-03 → COMP-04 dependency. Narrative packs contain unit allocations, signatures, extracted dependencies, ADRs and traced hazard/control context. Declared collaborators are not promoted to code dependency links. Purpose, behavior and error prompts have separate duties and bumped versions. Source revisions in the deterministic golden are refreshed for the intentional dataset changes; IDs and trace links are unchanged.

## ADR-020 — Human review and risk-analysis boundaries

DRR identity is supplied in JSON; the source diff uses an explicit earlier snapshot. Missing baseline evidence is labelled, never guessed. Deterministically grouped consistency/impact facts keep review synthesis bounded. Risk rows copy severity, allocation, controls and verification from the graph; separate suggested cells cover failure mode/cause/effects/actions. A local contract rejects risk-rating terminology in AI cells. Residual-risk acceptance is a human field. F01–F03 rules are data; proposed failure modes remain F03 gaps until reviewer-confirmed. L01–L03 use bounded jobs, cited JSON claims and separate local proposal files. No source writes occur.

Readability changes preserve section IDs: one H2 per unit/component/hazard and H3 subsections; structures have name/bases/fields columns; hazards and controls show names. Reviewer-requested G12 extends the answer key by the five SOUP evidence gaps. Optional sibling impact is grouped by unit rather than twenty-one separate rows. Generic query-level filtering is available before adding the unit-report spec in M10; absent unit results are explicitly stated.

## ADR-021 — Clinically meaningful synthetic risk traces

Risk bundles follow hazard functions, not fixture indices. Source code annotations, requirements' component allocations and historical PR work-item links use those same functions. Occlusion includes pressure threshold/filtering and the critical latch; verification includes TC-021. RC-12 deliberately remains an unrealised independent pressure plausibility control. A duplicate test now verifies audit export, while residual-anomaly display is the non-risk G01 gap. Risk draft packs include revision dependencies so changed code or retest evidence invalidates their analysis. Frozen change expectations and hand-checked goldens reflect the intentional dataset correction; the exact graph has 248 artifacts and 413 confirmed links.

## ADR-022 — Function-level risk drafts and focused review findings

Class C units each have a configured primary safety function, checked against the AST. Source hazard/control/requirement/test traces and severity sit beside five distinct suggested analysis cells; the hazard summary points back to unit analysis rows. This bounds cost while retaining a bottom-up function view. DRR includes a complete deterministic G/C/F table before safety-prioritized drafting and explicitly says when its named baseline has no source changes. L01 pre-screens missing implementations deterministically and emits only likely gaps; agreement returns no proposal. Mock checksum-gap prose is a fixture check, not an external-model quality claim.
