# Sandbox build plan and cut line

Target: one native vertical slice before expanding to the full reference. Estimates are engineering ranges for a new tenant, not delivery promises. Day 1 is a capability check; log actual tenant results in parity_tests.md. The official agent must run in Copilot Studio. Offline reference artifacts cannot substitute for that claim.

BD's **Copilot Studio Citizen Development Sandbox** is an Experiment-stage shared environment with restricted connectors. Use the original **Agent** creation experience, or new experience → Other ways to build → Agent, Standard. Never choose a GitHub Copilot agent/workflow. Only BD-listed GPT Prompt models are eligible. Run ingestion, gap calculation, assembly, PR and impact loops as **Power Automate cloud flows**; the agent has one start action and one status action, without generative answers or knowledge grounding for routine status. ADO/Dataverse/AI Builder availability is a day-1 gate, not assumed from local tests. [Day-1 kit](day1/README.md) gives the actual click path.

### Credit plan for the 600-credit monthly sandbox limit

Use approved **Basic** Prompt models at an estimated 0.1 credit per 1K total tokens. The reference `default` tier maps to Basic. The `analytical` tier also maps to Basic unless one Standard showcase section is explicitly budgeted at 1.5 credits/1K; reasoning/Premium at 10 credits/1K is excluded. Assume 4K total tokens per section, two agent actions at 5 credits each per run, and no generative answer. Actual billing/model labels must be checked in the tenant **Monitor** tab after each run. Power Automate cloud-flow licensing is separate; do not put 126-item loops in agent flows (13 credits per 100 agent-flow actions). These are planning estimates, not observed consumption. [Microsoft billing rates](https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-messages-management).

| Planned activity | Prompt credits | Agent-action credits | Total estimate | Remaining under 400-credit M16 guard |
|---|---:|---:|---:|---:|
| One two-section MVP run | 2 × 4K × 0.1/1K = 0.8 | 10 | 10.8 | 389.2 |
| Twenty MVP rehearsals plus one demo | 21 × 0.8 = 16.8 | 210 | 226.8 | 173.2 |
| Above plus one 120-section full run | 48 more | 10 more | 284.8 cumulative | 115.2 |
| Above plus one Standard showcase section | 5.6 extra versus Basic | 0 extra | 290.4 cumulative | 109.6 |

The 400-credit local guard deliberately leaves 200 credits below BD's 600-credit limit for tenant-side overhead and other users; the guard cannot see every tenant charge. Stop if Monitor shows less headroom. A full 120-section run consumes about 48 prompt credits at this assumption, and 20 **full** rehearsals would exceed the monthly allocation, so the 20-run plan is MVP-only.

| Order | Native MVP step | Hours | Completion evidence |
|---|---|---:|---|
| 0 | Verify licenses, connectors, environment/DLP, model, text/JSON limits and numeric extraction | 2–3 | Checklist below with an actual synthetic call and validator rejection |
| 1 | Agent topic “Draft the release test report”; queued request and GetRunStatus | 1–2 | Topic returns run ID promptly; later status shows draft URL |
| 2 | Flows 01/02: native work items/revisions/relations and run/results into Dataverse | 4–6 | SRS-021 revision/history, TC-021 latest outcome and links visible; no DHF-META dependence |
| 3 | Flow 03: G01/G05/G07/G11 only, deterministic counts and latest results | 2–3 | Exact corresponding answer-key IDs on synthetic inputs |
| 4 | Flow 04: one SSTR anomaly synthesis and one SAD component/SDD unit section | 3–5 | JSON-string prompt inputs; native citation/kind/confidence/numeric validator; unknown-ID and numeric failure tests |
| 5 | Flow 05: Markdown sections, provenance manifest and unresolved review markers | 2–3 | Deterministic failed-result table survives refusal; no approval claim |
| 6 | Flow 06: docs-only branch/PR/readiness status | 2–4 | Required reviewers; blocked status for suggestion/manual fields; source write denied |
| 7 | Flow 07: update trigger plus polling catches SRS-021 and stale sections | 2–4 | Saved before/after revisions and exact affected sections from the MVP scope |
| 8 | Parity run, demo rehearsal and connector failure handling | 2–3 | Recorded tenant outcomes and honest native/offline split |

Total MVP estimate: **20–33 hours**, plus admin wait time. Start with Artifact, TraceLink, DocumentSection and GenerationRun tables; store snapshot/config/manifest files in the governed SharePoint library. Add immutable snapshot membership, cache and serialized reservation tables before unattended multi-user runs. Until the ledger is deployed, allow one operator/provider at a time, require a configured conservative call cap, and keep persistent run spend; do not claim concurrent-budget parity.

Cut first: automatic DOCX redlines/PNG, full SDD, audit ZIP, sFMEA/DRR and L01–L03, then full G/C/F rule coverage and automatic regeneration. Keep two validated native sections, adverse-result facts, citations, the blocked readiness status and the change notification. Never cut the source-write boundary or citation/kind/confidence checks. Number validation can use the explicit native compensation below; it cannot silently disappear.

| Day-1 capability gate | Probe | Fallback / consequence |
|---|---|---|
| Dataverse access and role | Create/read synthetic Artifact and TraceLink | Governed SharePoint JSON/list storage with immutable run folders; document weaker relational/audit parity. No unattended runs until revision integrity is tested |
| Premium ADO connector and Entra permissions | Native GET/batch reads and docs-repo PR permission; source PATCH denied | Request the admin-provided connector/license. While waiting, manually import a signed-off synthetic export and show PR publication from reference; native live-ADO integration remains unverified |
| SharePoint/DLP | Read versioned config, write only draft run folder | Admin enables governed library; without approved storage stop publishing and retain a clearly labelled in-chat synthetic preview |
| Prompt tool/model/JSON output | Send facts_json/evidence_json as text and parse schema | Reduce to one bounded entity. Manual placeholder on refusal/schema failure. No raw free-text output |
| Actual input/output size limits | Probe bounded 6k/12k token-equivalent texts | Record tenant limits; split queries/reduce deterministic context before calling. Do not assume configured reference limits are accepted |
| MatchAll numeric extraction / locale | Native cases 39, 39.0, -0, 120.01 and artifact IDs | Digits outside known IDs force Suggested + numeric-unverified disposition; numbers appear only in deterministic tables. Native full-number parity remains pending |
| Approved function endpoint | AST, canonical SHA256, DOCX test | Reviewed source inventory and locally computed source hashes uploaded as governed inputs; Word Compare/PR diff offline. No custom function needed for core native validation |
| Async channel/infrastructure | Queue request and GetRunStatus; Teams callback if supported | Status polling topic; never long work in a chat turn |
| Docs-only Git writes | Native push/PR test and denied source write | Read-only MVP while admin fixes scope. Never grant device-repo write to the agent |

Judge-facing split: **native Copilot Studio** shows the topic, native work-item/test evidence, four gaps, two validated sections, Markdown assembly, docs PR/readiness, and “SRS-021 changed → these sections stale.” **Reference implementation, same specs executed offline** shows full SDD, function FMEA/DRR, local Word tracked changes/PNG and the checksum audit ZIP. Label the latter visibly; no tenant parity is claimed for it. If a capability fallback removes a native step, change the demo label and parity log before presenting.

## Pick the tier after day 1

The owner's answers in [SANDBOX_QUESTIONS.md](../../docs/SANDBOX_QUESTIONS.md) select one row below. All three tiers retain the native citation/kind/confidence validator and source-read/docs-write separation. If premium ADO access is also missing, import a reviewed synthetic snapshot while waiting and label live ingestion/PR publication pending.

| Tier | Built flows and prompt tools | Hours, including capability check/rehearsal | Native demo storyline | Parity cases eligible for execution |
|---|---|---:|---|---|
| A: Dataverse + premium ADO + approved function/custom connector | 01–07 vertical slice; SSTR anomaly and SAD component prompts first; functions add AST and SHA256, then DOCX only if time remains. Native core validator still runs | 20–33 for MVP; optional AST/hash/DOCX endpoint integration 6–10 more | Native ingest → four gaps → two governed sections → Markdown PR/readiness → changed occlusion traces; optional native Word redline shown only if deployed | Native ingest full graph with AST, selected G01/G05/G07/G11, latest results, validator, scoped impact/regen, readiness, source guard, refusal; full-rule/consistency/budget/export cases only after their additional implementation |
| B: Dataverse + premium ADO, no code endpoint | 01–07 vertical slice; same two prompts; reviewed reference unit inventory and source hashes imported into Dataverse. Word Compare/reference redlines external to native flow | 20–33; no automatic AST/hash/DOCX integration | Show native work-item/test ingestion and governed PR; identify imported reviewed code evidence; native SRS-021 impact. Label Word/redline, full SDD and audit pack as offline reference | Selected gaps/latest results, citation/kind/confidence, readiness, source guard, scoped impact; native-ingest parity only for work-item/test subset. AST, freshly computed hashes and automatic DOCX parity pending |
| C: no Dataverse; SharePoint available | 01/02 store reviewed SSTR evidence in Artifact/Link lists; 03 four gaps; 04 SSTR anomaly prompt only; 05 Markdown; 06 docs PR/readiness if premium ADO available; 07 SRS-021 polling/impact. SAD/SDD prompt deferred | 16–26: capability 2–3, topic 1–2, list ingest 3–5, gaps 2–3, prompt/validator 3–4, Markdown/PR 3–5, impact/rehearsal 2–4 | Native SSTR counts/gaps/governed draft → SRS-021 stale SSTR section. SAD/SDD, FMEA, redlines and export visibly run from reference | SSTR latest results, four gaps, validator, SSTR-only impact and readiness; source guard if native ADO enabled. Dataverse relational snapshot, whole-graph ingest, whole-document impact and concurrency parity pending |

### Tier C-prime: no ADO connector

If BD DLP blocks the Azure DevOps connector, use `dhf ingest` against the **synthetic mock or an owner-approved ADO source**, then `dhf export-snapshot --db … --output-dir …` to create a canonical JSON graph and Artifact/TraceLink CSV with hashes. Review the package, import its synthetic snapshot to Dataverse or versioned SharePoint, and have cloud flows 03–05/07 read only that import. Store documents in a SharePoint library with version history and named human review as the change record; docs PR parity is pending. For the impact demo, import a separately exported **post-change_1** snapshot, then show stale sections from the two versions. The reference implementation demonstrates ADO integration outside the tenant; the agent demonstrates generation, governance and impact on imported evidence. Label this split explicitly. A Digital Innovation Request for the Prototype environment with premium connectors is the later integration route, not a demo prerequisite. Never upload real hackathon data unless the owner confirms it is cleared for the sandbox.

Eligible means a tenant case can be run; it does not assert that it has passed. Numeric parity additionally requires MatchAll/decimal probes; otherwise log numeric compensation as a separate, weaker outcome. Budget/cache concurrency remains pending until serialized reservations are built.

Tier C storage contract: create **Artifact, Link, Section and Run** lists. Artifact/Link records use a composite synthetic key plus RunId and Revision; never update prior-run records. Section contains doc/section IDs, status, cited IDs and paths to full files. Run contains state, timestamps, selected source revisions and output folder. Index RunId/ArtifactId before ingestion, query by indexed run and page results; do not perform an unfiltered full-list scan. Store bodies, graph JSON, evidence packs and manifests as versioned files in a governed library, not giant list fields.

Microsoft documents a **30 million-item** list capacity and a **5,000-item list-view/query threshold**; the latter is not a total capacity limit. A list attachment is limited to **250 MB** and a library file to **250 GB**. Our narrower MVP caps are **1,000 Artifact, 2,000 Link, 100 Section and 100 Run rows**, and **1 MB per JSON file**; rotate to a new governed run library before reaching the caps. Those are design limits, not service guarantees. Keep the SSTR subset within them; full graph impact remains on the reference. A single operator serializes run writes; SharePoint storage does not claim Dataverse transaction/audit parity. Verify actual tenant connector payload limits and retention on day 1. [SharePoint Online service limits](https://learn.microsoft.com/en-us/office365/servicedescriptions/sharepoint-online-service-description/sharepoint-online-limits), [list-view threshold](https://learn.microsoft.com/en-us/troubleshoot/sharepoint/lists-and-libraries/items-exceeds-list-view-threshold).
