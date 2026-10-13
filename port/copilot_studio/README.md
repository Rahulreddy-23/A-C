# DHF Automation — Copilot Studio build pack

This is an implementation blueprint and parity fixture pack, not an imported solution or a claim that a tenant deployment was tested. Build in a dedicated development environment using only synthetic evidence first. Capability gates and fallbacks are in [governance](governance.md). No Python reading is needed to follow the flow specs.

| Reference step | Copilot Studio / Power Automate construct | Input → output | Spec |
|---|---|---|---|
| Native ADO normalization | Child flow; Parse JSON, Select, Filter array; Dataverse revision upsert | WIT fields/history/relations → Artifact revisions and links | [Ingest work items](flows/01-ingest-work-items.md) |
| Native test normalization / latest result | Child flow; ADO HTTP; sorted result view | Runs/results → versioned result evidence | [Ingest tests](flows/02-ingest-test-results.md) |
| Code signatures, structures, import calls and SOUP | Approved AST function or human-verified unit inventory | Git files/revisions → units, components, dependencies, SOUP | [Code boundary](deterministic_logic.md#code-and-hash-boundaries) |
| Graph snapshots and revision diff | Dataverse immutable Artifact revisions + SnapshotMember links | Complete ingest → atomic snapshot and delta | [Dataverse schema](dataverse_schema.md) |
| RTM, coverage, G01–G12, C01–C04, F01–F03 | Child flow anti-joins / Power Fx filters | Snapshot + latest baselines → facts and findings | [Coverage and gaps](flows/03-coverage-gaps.md) |
| Named queries, bounded evidence pack | Child flow for each query; deterministic context closure | Section spec + params + snapshot → facts/evidence JSON | [Query catalog](query_catalog.md) |
| Prompt loading, cache, ledger reservation | Dataverse CacheEntry and serialized BudgetLedger transaction | Prompt/version/model/pack → cached response or reserved call | [Generate section](flows/04-generate-section.md) |
| Provider call and claim validator | Prompt tool with JSON output; deterministic validation child flow | JSON → accepted typed/cited claims + rejection events | [Prompt tools](prompts/) |
| Repeat expansion, section Markdown, manifest | Array sorting + data-driven child flow; SharePoint file storage | Spec + sections → Markdown, manifest and DOCX | [Assemble](flows/05-assemble-document.md) |
| Tracked DOCX changes and review comments | Approved local renderer function; manual Word Compare fallback | Baseline + draft → DOCX redline | [Rendering boundary](deterministic_logic.md#code-and-hash-boundaries) |
| Docs branch / commit / PR / status / baseline | Docs-scoped ADO connection and HTTP; explicit human merge | Document bundle → PR URL and readiness status | [Open docs PR](flows/06-open-docs-pr.md) |
| Impact, stale status, selective regeneration | Work-item update trigger plus scheduled poll; saved section bytes | New snapshot + manifests → impact, regenerated subset | [Impact](flows/07-impact.md) |
| L01–L03 proposals | Bounded prompt jobs; Dataverse Proposal and SharePoint files | Requirement/code/design packs → suggested proposals | [Rules and proposal mapping](deterministic_logic.md) |
| Evaluation and audit export | Deterministic set comparisons and checksum bundle function | Snapshot + documents + answer key → metrics and ZIP | [Parity cases](parity_tests.md) |

Build flows 01–03 before prompts, then 04–06, then 07. Import unchanged document/rule/schema files from `specs/` into a versioned SharePoint configuration library; keep their checksums in GenerationRun. Prompt-tool wrappers below preserve the exact prompt body and cite the same claims.v1 contract. The Azure DevOps connector exposes **Send an HTTP request to Azure DevOps** for REST operations; source reads and docs writes use separate permission boundaries. [Connector reference](https://learn.microsoft.com/en-us/connectors/visualstudioteamservices/).

`catalog.yaml` is the coverage index. `uv run python tools/check_port.py` checks the pack against current specs; executable reference tests remain offline. See [parity_tests.md](parity_tests.md) for tenant execution instructions and expected outputs. Tenant parity is pending, not scored as passed by the local validator.
