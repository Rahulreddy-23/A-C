# DHF Automation — Product Brief & Build Plan

Owner: repo owner (product) · PM/reviewer: Claude · Engineer: Codex
Dev window: **2026-10-12 → 2026-10-23** · Demo to review board: **2026-10-27**

---

## 0. TL;DR

Build an **evidence system that writes regulated documents**, not a document generator.

1. Ingest engineering data from Azure DevOps (ADO) into an **evidence graph**: every item has a stable ID, revision and source link, and links are typed.
2. Compute traceability, coverage and gaps **deterministically**.
3. Generate DHF documents **one section at a time** from YAML template specs. The LLM writes only prose, and every claim it makes is tagged **sourced / inferred / suggested** and cited.
4. Publish drafts as **pull requests with redlines** into a docs repo, plus a manifest that makes each document auditable.
5. When ADO changes, detect **which sections went stale**, regenerate only those, and open a redline PR.

Final submission must run as a **Microsoft Copilot Studio agent** in a company sandbox. This repo is the **reference implementation and prompt lab**, plus a **port pack** that makes the Copilot Studio build mechanical.

---

## 1. Context

Medical-device software teams keep a Design History File (DHF). Today it's assembled by hand at milestones, so it suffers from:

- **Late updates:** evidence is collected at milestone closure, not as work happens.
- **Traceability gaps:** links between requirement, design, code change, test case and result are incomplete or inconsistent.
- **Stale documentation:** architecture, risk files and test reports drift apart.

**In scope:**
- Must have: Software Architecture Document (SAD), Software Detailed Design (SDD), Software System Test Report (SSTR).
- Good to have: Design Review Record (DRR), software FMEA (sFMEA), and detecting missing requirements and implementation gaps.

**Must have:**
- ADO integration
- Extensible to all DHF documents
- Approved AI tools only
- Data privacy and local processing
- Change tracking for human review

**Out of scope:** modifying data in source systems, product code development, SAP.

**Judging weights — optimize for these, in this order:**

| Criterion | Weight | What it means for us |
|---|---|---|
| Traceability quality | 25% | Inputs, outputs, risks, verification and change evidence visibly connected |
| Regulated workflow fit | 25% | Human review, approval, document control, evidence integrity |
| Accuracy & governance | 20% | Source-backed content clearly separated from inferred or suggested content |
| Manual effort reduction | 10% | Less repeated authoring and evidence collection |
| Audit readiness | 10% | Structured, source-linked, reviewable outputs |
| Good-to-have features | 10% | DRR, sFMEA, gap identification |

---

## 2. Deliverables of this repo

1. **Reference implementation** (Python CLI `dhf`) that runs end to end against a **local ADO mock server**. The mock follows the real ADO REST API and is loaded with synthetic data. Switching to a real ADO org is a config change only.
2. **Port pack** (`port/copilot_studio/`) that maps every pipeline step to a Copilot Studio / Power Automate / Dataverse equivalent, with parity test cases.
3. **Eval harness and metrics** that prove accuracy (zero invented IDs, gap precision and recall, % sourced claims, cost per document).
4. **Demo assets**: the change scenario, a scripted run, and the metrics report.

---

## 3. Architecture

```
ADO work items + links ─┐
ADO Git (code, PRs) ────┤  ingest (deterministic)
ADO test results ───────┤──────────────────────────► Evidence graph (SQLite)
Docs (PRD/SRD, risk) ───┘                             artifacts + typed links + revisions
                                                              │
                                trace/ (deterministic) ◄──────┤ RTM, coverage, gaps, consistency
                                                              │
                     specs/documents/*.yaml ──► generate/ ────┤ section-by-section
                     specs/prompts/*.md                       │   evidence pack → LLM → claims JSON
                                                              │   → validator → typed, cited claims
                                                              ▼
                                                        render/ (md, docx w/ tracked changes)
                                                              │
                                                        review/ → branch + PR in docs repo
                                                              │   manifest, readiness check, baseline tag
                                                              ▼
                                                        impact/ (on ADO change: stale sections →
                                                                 selective regen → redline PR)
```

The key properties are listed in AGENTS.md "Non-negotiable rules". The most important are deterministic-first, typed and cited claims, a read-only view of source systems, specs-as-data, and pure JSON steps.

---

## 4. Canonical data model (`src/dhf/models/`)

**Artifact**

| Field | Notes |
|---|---|
| `id` | Stable human ID, e.g. `SRS-021`, `HAZ-03`, `TC-114`, `PR-17`, `UNIT-alarm.manager` |
| `type` | `user_need`, `system_req`, `software_req`, `hazard`, `risk_control`, `component`, `software_unit`, `soup`, `adr`, `code_change`, `test_case`, `test_run`, `test_result`, `defect`, `review`, `action_item`, `document_section` |
| `title`, `body` | Text |
| `attributes` | Typed dict per type (e.g. severity for hazards, outcome for test results, version for SOUP) |
| `source` | `{system: ado|git|file|derived, url, native_id, revision, retrieved_at}` |
| `content_hash` | sha256 of the canonical body plus attributes |

**TraceLink**

| Field | Notes |
|---|---|
| `src`, `dst` | Artifact IDs |
| `type` | `derives_from`, `allocated_to`, `implements`, `verifies`, `mitigates`, `detects`, `executes`, `reports_defect`, `changes`, `reviews` |
| `origin` | `explicit` (found in source) · `ai_inferred` (proposal) · `human_confirmed` |
| `confidence` | Only for `ai_inferred` |
| `evidence` | Where the link was found (ADO relation, `AB#` commit message, test name, …) |

Only `explicit` and `human_confirmed` links count toward traceability metrics. `ai_inferred` links appear as suggestions.

---

## 5. Synthetic dataset and ADO mock (M1)

### 5.1 Fictional product

**"Kestrel Infusion Controller"**: software for a fictional volumetric infusion pump. It's IEC 62304 Class C overall, with some Class B items. It is entirely fictional; don't model it on any real product. The domain is chosen because it gives a rich sFMEA (occlusion, air-in-line, over/under-infusion, alarm failure).

### 5.2 Contents (single source of truth: `data/synthetic/*.yaml`)

| Set | Approx. size |
|---|---|
| User needs | 6 |
| System requirements (SRD) + short PRD narrative (markdown) | 15 |
| Software requirements (SRS), with acceptance criteria | 35 |
| Hazards (severity 1–5) + risk controls (some realized as software requirements) | 8 hazards, 12 controls |
| Components (UI, Infusion Control, Sensor Monitoring, Alarm Manager, Drug Library, Logging & Comms) | 6 |
| Software units | ~15 |
| ADRs | 2 |
| Device code: small Python package (~20 modules) implementing most SRS, with unit tests and ~5 pinned third-party deps (SOUP) | — |
| System test cases | ~40 |
| Test runs: Release 1.0 (2 failures), Release 1.1 (after changes, 1 retest) | 2 |
| Defects | 5 |
| Previous design review record, with action items (2 closed, 2 open) | 1 review, 4 actions |
| Approved baseline `SAD v1.0` (markdown), slightly out of date on purpose | 1 |

### 5.3 Planted issues and answer key

`data/synthetic/expected_gaps.yaml` lists exact IDs for every planted issue. Plant at least:

- 3 software requirements with no verifying test
- 2 software requirements with no implementing code change
- 1 orphan code module or PR with no linked requirement
- 1 test case not linked to any requirement
- 1 failed test result with no linked defect
- 1 risk control not traced to any requirement
- 1 risk-control requirement with no verification
- 1 system requirement with no derived software requirement
- 1 component present in code but missing from `SAD v1.0`
- 1 component named differently between `SAD v1.0` and code
- 1 open defect not listed as a residual anomaly

### 5.4 Change scenario for the demo

`data/synthetic/scenarios/change_1.yaml` describes one change. `SRS-021` (occlusion detection threshold) is edited. A PR changes the sensor module, and a re-run makes one occlusion test fail. List the **expected impacted sections** per document (SAD, SDD, SSTR, sFMEA) so impact detection can be tested exactly.

### 5.5 ADO mock server (default for development and demo)

There's no real ADO org yet. Build `tools/mock_ado/`, a local server that **matches the contract** of the subset of the Azure DevOps REST API (api-version 7.1) the product uses. The product's ADO adapter is the real one and talks HTTP to `ADO_BASE_URL`. Moving to a real org later changes only `.env`.

**Implementation**
- Python stdlib `http.server` (`ThreadingHTTPServer`); no web framework.
- State lives in a JSON or SQLite file under `out/mock_ado/`.
- Git repos are real local bare repos under `out/mock_ado/git/`.
- The product (`src/`) never imports from `tools/`.

**Commands**
- `uv run mock-ado init` builds state and git repos from `data/synthetic/`.
- `uv run mock-ado serve --port 8089`
- `uv run mock-ado apply-scenario change_1`
- `uv run mock-ado reset`

**Endpoints.** Response shapes must follow the official ADO REST docs: `id`, `rev`, `fields` keyed by `System.*` / `Microsoft.VSTS.*` reference names, `relations` with link-type reference names in `rel`, `url`, and `_links.html.href`.

| Area | Endpoints |
|---|---|
| Work items | `POST …/_apis/wit/wiql` · `POST …/_apis/wit/workitemsbatch` (with relations) · `GET …/_apis/wit/workitems/{id}` · `GET …/_apis/wit/workitems/{id}/revisions` |
| Test results | `GET …/_apis/test/runs` · `GET …/_apis/test/runs/{id}/results` (`testCase.id`, `outcome`) |
| Pull requests | `GET …/_apis/git/repositories` · `GET …/pullrequests?searchCriteria.status=all` · `GET …/pullrequests/{id}/workitems` · `POST …/pullrequests` · `POST …/pullrequests/{id}/statuses` |
| Git transport | Clone and push with plain `git` against the local bare repos. With real ADO, the same code clones over HTTPS with the PAT |
| Web pages | Minimal HTML at the `_links.html.href` URLs (`/{org}/{project}/_workitems/edit/{id}`, PR pages) showing the item, its revision history and links, so citations are clickable in the demo |
| Mock admin (not ADO) | `/_mock/reset` · `/_mock/apply-scenario/{name}` · `/_mock/state`. Only `tools/` and tests may call these. A test asserts `src/` never references `/_mock/` |

**Behavior**
- **Revisions are real.** Every change bumps `rev` and `System.ChangedDate` and keeps history, so impact detection behaves exactly as it would against ADO.
- **Device repo history.** `mock-ado init` builds `kestrel-device-sw` from `data/synthetic/code/` plus `data/synthetic/history.yaml`. That's a sequence of commits and completed PRs whose messages carry `AB#<id>` work-item links, including the planted orphan change.
- **Scenarios** edit work-item fields, add a commit and a completed PR to the device repo, and add a test run.
- **Auth and the read-only guardrail.** Every request needs a Basic-auth PAT.
  - `APP_ADO_PAT` (the product) may read work items, tests and code, and may write only to the docs repo (push, PRs, PR statuses).
  - Any other write with it returns **403**.
  - `SEED_ADO_PAT` (tools only) may write anything.
  - A test proves the product token is refused on a work-item write. This is a demo point for "never modifies source systems".
- **Contract tests.** One adapter test suite (`tests/contract/`) runs against the mock by default, started in-process on a random port. With real credentials it runs against a real org via `pytest -m live_ado`.

**Real org later (M11, optional).** A seeder loads the same dataset into a free ADO org on the **CMMI** process through the write APIs. It is idempotent and has `--dry-run` and `--confirm-org`.

**Mapping** (applies to both mock and real org). The mock uses CMMI work-item types (Requirement, Risk, Review, Bug, Test Case, Task) and CMMI link types. All mapping lives in `specs/ado_mapping.yaml` (work-item types, tags, fields, link types → our model). The real company process will differ, so mapping must be config only. Default mapping:

  | ADO | Our model |
  |---|---|
  | Requirement tagged `UN` / `SYS` / `SRS` / `RISK-CONTROL` | user need / system req / software req / risk control |
  | Risk | hazard |
  | Bug | defect |
  | Test Case | test case |
  | Review + child Tasks | review + action items |
  | Parent/Child | derives_from |
  | Tests/Tested By | verifies |
  | Related + tag | mitigates |

- Two Git repos:
  - `kestrel-device-sw`: device code. Commit and PR messages use `AB#<id>` to link work items.
  - `kestrel-dhf-docs`: generated documents. This is the **product's only write target**.
- **Test results** use the Test Runs/Results API shape, with test-case references.

---

## 6. Template specs: extensibility (M4)

Each DHF document is one YAML file in `specs/documents/`. **Adding a document type must need zero Python changes.**

```yaml
id: sstr
title: Software System Test Report
spec_version: 1
standard_refs: ["IEC 62304 5.7", "IEC 62304 5.8"]
params:
  release: {type: string, required: true}
sections:
  - id: results_summary
    title: Summary of Results
    mode: deterministic            # deterministic | ai | human
    query: test_results_summary    # named query in graph/queries
    render: table
    standard_refs: ["IEC 62304 5.7.5"]
  - id: anomaly_assessment
    title: Failed Tests and Anomaly Assessment
    mode: ai
    query: failed_results_with_defects
    prompt: sstr.anomaly_assessment@1
    output_schema: claims.v1
    allowed_kinds: [sourced, inferred, suggested]
    rules: [no_unknown_ids, numbers_match_facts]
  - id: release_conclusion
    title: Conclusion
    mode: ai
    query: release_readiness_facts
    prompt: sstr.conclusion@1
    allowed_kinds: [suggested]     # release decisions are always human
  - id: approvals
    title: Approvals
    mode: human                    # placeholder only; approvals happen in the eQMS
```

- **Named queries** return `{facts, evidence: [artifact...]}`. The evidence pack is exactly what the LLM may cite.
- **Prompt files** (`specs/prompts/*.md`) have front matter (`id`, `version`, `inputs`, `output_schema`, `max_input_tokens`) and a body. They must tell the model to use only the evidence pack, cite IDs, never compute numbers, and mark anything not directly supported as `inferred` or `suggested`.
- Keep each section's evidence pack bounded (`max_input_tokens`, default 6k). Split by component or unit when larger. This keeps prompts inside Copilot Studio limits.

---

## 7. Generation, validation, provenance, manifest (M4–M5)

**Claims schema `claims.v1`:**

```json
{ "claims": [ { "text": "...", "kind": "sourced|inferred|suggested",
                "citations": ["SRS-021", "TC-114"], "confidence": 0.8 } ] }
```

**Validator (deterministic):**
- `no_unknown_ids`: drop the claim and log it.
- `sourced` with no valid citation: downgrade to `inferred`.
- `numbers_match_facts`: every number in the text must appear in `facts`, otherwise reject.
- `allowed_kinds` violations: coerce to `suggested`.

Every reject or downgrade is recorded in the manifest.

**Rendering provenance:**

| Kind | Markdown | DOCX |
|---|---|---|
| sourced | plain text + citation link `[SRS-021@r3](ado-url)` | plain text + hyperlinked citation |
| inferred | `**[Inferred]**` prefix + footnote listing basis | yellow highlight + Word comment "AI-inferred from …" |
| suggested | `**[Suggested — review required]**` prefix | blue highlight + Word comment "REVIEW REQUIRED" |

**Manifest** (`<doc>.manifest.json`, committed next to each document):
- `doc_id`, `doc_version`, `generated_at`, `generator_version` (git sha)
- `template_spec` {id, version, sha256}, `prompts` [{id, version, sha256}], `model` {provider, name}, `llm_cost_usd`
- `source_snapshot` [{artifact_id, system, native_id, revision, content_hash}]
- `sections` [{id, mode, status, cited_revisions, claim_counts {sourced, inferred, suggested}}]
- `validation` {rejected, downgraded, coerced}
- `document_sha256`, `review` {pr_url, reviewers, status}

---

## 8. Review and change tracking (M5)

- `dhf generate <doc> [--params] --open-pr`
  1. Write md, docx and manifest into `kestrel-dhf-docs` on branch `dhf/<doc>/<param>/<timestamp>`.
  2. Open an ADO PR whose description lists changed sections, claim stats and gaps, with required reviewers from config.
  3. Post a PR status **"DHF review readiness"**.
- **Readiness check** (`dhf check <doc>`) fails if there are unresolved `suggested` claims, rejected claims, stale sections, or `human` sections left empty. Resolution happens by editing the md in the PR; the checker re-runs.
- **Baselines:** after merge, tag `<doc>-v<N>`. "Previous approved version" means the latest baseline tag.
- **DOCX tracked changes:** compute a paragraph-level diff between the baseline and the new version.
  - Emit real `w:ins` / `w:del` with author `DHF Assistant (AI draft)` and a timestamp.
  - Carry citations as Word comments.
  - The file must open cleanly in Word. Round-trip it with python-docx in tests, and convert with LibreOffice headless if it's installed.
- Approvals and e-signatures stay in the company's existing eQMS. We never claim to approve.

---

## 9. Change impact and staleness (M7)

- `dhf impact --since <baseline|timestamp>`
  - Changed artifacts are those whose revision or content_hash changed since the last ingest.
  - **Directly stale** sections are those whose `cited_revisions` include a changed artifact.
  - **Possibly affected** sections cite a 1-hop linked neighbor.
  - Writes an impact report (md + json).
- `dhf regenerate --stale --open-pr` regenerates only stale sections. Untouched sections must be **byte-identical**. Opens a redline PR.
- `dhf watch --interval 60` polls ADO for changes (by revision / `System.ChangedDate`) and runs impact automatically. A webhook (ADO service hook) is optional; polling is the demo default.

---

## 10. Per-document specs

### 10.1 SSTR (build first; mostly deterministic)

1. Purpose & scope (release, baseline) — ai, mostly template text
2. References (SRS, test plan, RTM versions) — deterministic
3. Test environment (from test run metadata) — deterministic
4. Summary of results (total / passed / failed / blocked / not run) — deterministic
5. Results by requirement (req → test cases → latest result) — deterministic
6. Failed tests & anomaly assessment (failure → defect → status → impact) — ai
7. Retest results — deterministic
8. Known residual anomalies (open defects + rationale) — ai, `suggested` only (IEC 62304 5.8)
9. Verification coverage gaps — deterministic
10. Conclusion / release readiness — ai, `suggested` only
11. Evidence index (all run IDs, revisions) — deterministic
12. Approvals — human

### 10.2 SAD

1. Purpose, scope, definitions — ai
2. System context & external interfaces — ai from SRD/PRD + interface artifacts
3. Software safety classification reference — deterministic, from the risk file
4. Architecture overview + component diagram — diagram generated from the graph, text ai
5. Components: responsibility (ai), allocated requirements (deterministic), interfaces
6. Interfaces (internal/external) — code extraction + ai
7. SOUP items: name, version, purpose, requirements on SOUP — name and version deterministic from manifests, purpose ai
8. Runtime/deployment view — ai
9. Segregation & risk-control measures in the architecture — hazards and controls via graph
10. Requirements-to-architecture matrix — deterministic
11. Architectural decisions — sourced from ADRs
12. Open issues / gaps — deterministic + suggested

### 10.3 SDD

Doc-level: design conventions and a unit traceability table (deterministic).

Per software unit:
- ID, parent component
- Purpose (ai)
- Interfaces: signatures extracted with `ast` (deterministic)
- Behavior/algorithm (ai from code + SRS)
- Data structures (extraction + ai)
- Error handling (ai)
- Allocated requirements and related risk controls (deterministic)
- Unit tests (deterministic)

Keep the code extractor behind an interface; real data may be C/C#, which would need tree-sitter later.

### 10.4 DRR

1. Review identification: type, date, baseline, participants — **from an input file only, never invented**
2. Scope: artifacts changed since previous baseline — deterministic diff
3. Status of previous action items — deterministic
4. Pre-review findings: gaps, consistency issues, stale sections — suggested
5. Suggested checklist questions — suggested
6. Discussion, decisions, new action items — human placeholders
7. Approvals — human

### 10.5 sFMEA (table)

Columns: ID, component/unit, function, failure mode, cause, local effect, system effect, hazard link, **severity**, existing controls, detection/verification, residual risk, recommended actions.

- Failure modes, causes and effects: ai, always `suggested`.
- **Severity: copied only from the hazard analysis (sourced). The AI never assigns severity, probability, RPN or residual risk.** Those cells are either sourced or left for humans.
- Controls (requirements/code) and detection (test cases): via graph, sourced.
- Gaps: failure mode with no control, control with no verification, hazard with no failure mode.

---

## 11. Gap and consistency rules (`specs/rules/*.yaml`, M3/M7)

**Deterministic:**

| Rule | Detects |
|---|---|
| G01 | SRS with no verifying test |
| G02 | SRS with no implementing change |
| G03 | Orphan code module or PR |
| G04 | Test case with no requirement |
| G05 | Failed result with no defect |
| G06 | Risk control not traced to a requirement |
| G07 | Risk-control requirement with no verification |
| G08 | System req with no derived SRS |
| G09 | SRS with no parent system req |
| G10 | Open defect not in residual anomalies |
| G11 | Test case verified against an older requirement revision (requirement changed after the test last passed) |

**Consistency:**

| Rule | Detects |
|---|---|
| C01 | Component set differs across code / SAD / SDD / sFMEA |
| C02 | A referenced ID doesn't exist or isn't at its current revision |
| C03 | SSTR summary numbers ≠ RTM numbers |
| C04 | Naming mismatch for the same component |

**LLM-assisted (output is always `suggested`, written to a proposals file):**
- L01: requirement likely not implemented (acceptance criteria vs code), with confidence
- L02: proposed requirement text for orphan code
- L03: semantic contradiction between SAD component responsibility and SDD unit behavior

---

## 12. Above and beyond (prioritized)

**P1: build these; they drive the demo and the top-weighted criteria.**

| ID | Feature | Why it scores |
|---|---|---|
| AB1 | **Change-impact redline PR** (§9): live ADO change → exact stale sections → regenerate only those → redline PR | Shows late-update, traceability and stale-doc fixes at once |
| AB2 | **Review-readiness gate** posted as an ADO PR status | Regulated workflow fit |
| AB3 | **Cross-document consistency checker** (C01–C04) | Stale documentation; "one design story" |
| AB4 | **DOCX with real tracked changes + citation comments** | Must-have change tracking, in the reviewers' native tool |
| AB5 | **Regulatory clause coverage appendix**: IEC 62304 / ISO 14971 clauses → sections → evidence, with uncovered clauses flagged | QMS fit, audit readiness |
| AB6 | **Gap detection scored against the answer key** (precision/recall in the metrics report) | Proves accuracy, not just claims it |
| AB7 | **Zero-code extensibility proof**: add `sutr.yaml` (Software *Unit* Test Report, from unit-test results) and `rtm.yaml` as specs only, with a test that asserts no Python changed | Must-have extensibility. Also covers the "SUTR vs SSTR" ambiguity in the problem statement |
| AB8 | **Audit pack export** (`dhf audit-pack --release 1.1`): zip of documents, manifests, RTM, gap report, evidence snapshot and a `SHA256SUMS` file | Audit readiness, evidence integrity |

**P2: only after M10 is done.**

| ID | Feature |
|---|---|
| AB9 | Claim-support verifier: a cheap-model second pass judges whether the cited evidence supports each claim; report the support rate on a sample |
| AB10 | Traceability explorer: a single self-contained static HTML file (inline JS/SVG, no CDN) showing need → req → design → code → test → result → risk, with gaps highlighted |
| AB11 | "Ask the DHF" CLI Q&A (`dhf ask "what is unverified in 1.1?"`): routes to named queries, LLM only phrases the answer. Maps to Copilot Studio topics |
| AB12 | Proposed-requirements workflow for orphan code: proposal file → reviewer accepts → instructions for a human to create it in ADO |
| AB13 | Cost and time telemetry per document vs a configurable manual-effort baseline |

---

## 13. Copilot Studio port pack (M9) — `port/copilot_studio/`

| File | Content |
|---|---|
| `README.md` | Architecture mapping table (reference step → Copilot Studio construct) |
| `dataverse_schema.md` | Tables, columns and relationships for Artifact, TraceLink, DocumentSection, GenerationRun, Proposal |
| `prompts/` | Each `specs/prompts` file converted to prompt-tool form: instructions, named inputs, JSON output example/schema, token budget notes |
| `flows/` | Step-by-step Power Automate specs (trigger, connector actions, expressions, inputs/outputs) for: ingest work items, ingest test results, compute coverage and gaps, generate section, assemble document, open docs PR, impact on ADO work-item-updated trigger |
| `agent.md` | Agent instructions, tools, topics, conversation starters, and the async pattern (chat starts a flow, then notifies when the PR is ready; no long work inside a chat turn) |
| `deterministic_logic.md` | How each rule (G/C) maps to flow logic, Power Fx or a Dataverse view. What needs an Azure Function if allowed (DOCX redlines, AST extraction), with fallbacks (PR diff + Word Compare; manual unit list) |
| `governance.md` | Environment setup, DLP connector policy (ADO, SharePoint, Dataverse only), model selection, web search off, data residency notes |
| `parity_tests.md` | Synthetic inputs and expected outputs to prove the Copilot Studio build matches the reference |

Assume Copilot Studio runs OpenAI-family models. Prompts must work on both providers; M4 includes a cross-provider check on one section.

---

## 14. Evaluation (M10) — `dhf eval`

`dhf eval` writes `out/metrics.md` (used in the demo) and `out/metrics.json`, covering:

- Unknown/invented IDs in final documents (**must be 0**)
- Claim mix per document (% sourced / inferred / suggested) and validator reject/downgrade counts
- Gap detection precision/recall vs `expected_gaps.yaml`
- Trace coverage (SRS → test, SRS → code, hazard → control → verification)
- Impact detection precision/recall vs `change_1.yaml` expected sections
- Consistency findings count
- $ and seconds per document; cache hit rate

Golden outputs live in `eval/golden/`. Deterministic sections must match exactly; AI sections are checked structurally.

---

## 15. Milestones and acceptance criteria

Build the milestones in order and continuously, following the commit and checkpoint rules in AGENTS.md. Before starting each milestone, clear the `[blocking]` items in `docs/REVIEW.md`.

| M | Target | Scope | Acceptance criteria |
|---|---|---|---|
| **M0** | Oct 12–13 | Scaffolding: `uv` project, `dhf` CLI skeleton, CI (ruff + pytest), `.env.example`, PR template in use, `docs/DECISIONS.md`. LLM layer: interface, mock/anthropic/openai adapters, response cache, budget ledger + per-run cap, claims schema | `uv run dhf --help` works. Mock returns schema-valid claims. Tests cover cache hit/miss, ledger persistence, per-run cap and 80% hard stop. CI green |
| **M1** | Oct 13–15 | Synthetic dataset (§5.1–5.4) + answer key + change scenario + device-repo history; `specs/ado_mapping.yaml`; **ADO mock server** (§5.5) with init/serve/apply-scenario/reset, git-backed repos, HTML pages and the auth guardrail; contract tests | Dataset validator passes (all link targets exist; planted issues match the answer key exactly). Contract tests pass for every endpoint, with shapes per ADO docs. `apply-scenario change_1` bumps revisions and adds the commit, PR and test run. Product-token work-item write → 403. No `/_mock/` references in `src/` |
| **M2** | Oct 15 | Ingest: fixtures adapter + ADO adapter (HTTP, against the mock) → SQLite graph with provenance and revisions; code extractor (`ast`) for units, signatures and SOUP from a git clone | Graph from the fixtures adapter ≡ graph from the ADO adapter over HTTP against the mock, ignoring URLs/native IDs. Re-ingest after `apply-scenario` detects exactly the changed artifacts. Every artifact has full `source` and `content_hash` |
| **M3** | Oct 15–16 | Trace: RTM, coverage, rules engine (G01–G11) from YAML; `dhf gaps` (md + json) | Precision = recall = 1.0 vs answer key for deterministic rules. RTM matches a hand-checked fixture |
| **M4** | Oct 16–17 | Template-spec engine, named queries, section pipeline, validator, Markdown renderer with provenance, manifest. **SSTR end to end.** One-section cross-provider check (owner runs live) | `dhf generate sstr --release 1.1` → md + manifest. 0 unknown IDs. Deterministic sections match golden. Validator tests for each rule. Prompts contain no numbers the model must compute |
| **M5** | Oct 17–19 | DOCX renderer with tracked changes + comments; docs-repo PR workflow in ADO; baselines; `dhf check` + PR status (AB2, AB4) | PR created in mock ADO: branch pushed to the docs bare repo with md/docx/manifest, PR visible via the API and the mock HTML page, readiness status posted. DOCX opens with visible tracked changes and comments. `dhf check` fails on unresolved suggestions and passes once resolved |
| **M6** | Oct 19–20 | SAD + SDD specs and prompts; diagrams from the graph (local Graphviz/Mermaid render, or source-only fallback); SOUP section | Every code component and unit appears. Allocation tables are deterministic. Diagrams generated locally. C01 passes on fresh docs |
| **M7** | Oct 20–21 | Impact + staleness, selective regeneration, `dhf impact`, `dhf regenerate --stale`, `dhf watch`; consistency rules C01–C04 (AB1, AB3) | Running `mock-ado apply-scenario change_1` while `dhf watch` runs flags exactly the expected sections. Untouched sections are byte-identical. The redline PR contains only impacted sections |
| **M8** | Oct 21–22 | DRR + sFMEA; L01–L03 proposals | sFMEA severity only from the risk file. AI cells are `suggested`. sFMEA gaps listed. DRR invents no participants, decisions or approvals |
| **M9** | Oct 20–22 (parallel) | Copilot Studio port pack (§13) | Every pipeline step and rule has a mapped construct. Parity cases defined. A reviewer can follow the flow specs without reading Python |
| **M10** | Oct 22–23 | `dhf eval`, golden outputs, AB5 clause appendix, AB7 extensibility proof (`sutr.yaml`, `rtm.yaml`), AB8 audit pack, `scripts/demo.sh`, README | `out/metrics.md` produced. `scripts/demo.sh` starts the mock and runs the whole demo end to end offline |
| **M11** | optional, once a real ADO org exists | Real-org seeder (§5.5) + `pytest -m live_ado` contract run | The same contract suite passes against the real org. A seeder re-run creates 0 new items |

---

## 16. Target demo (build toward this)

1. Start from ADO (the mock by default, a real org if one is available) with requirements, code, tests and risks. Run `dhf generate sstr --release 1.1 --open-pr`. A PR appears; clicking any citation opens the ADO item at that revision.
2. `dhf gaps` shows the planted gaps with precision/recall, plus an AI-drafted requirement for orphan code marked *suggested*.
3. **Live change:** `mock-ado apply-scenario change_1`. With a real org, edit the requirement in the ADO UI instead. `dhf watch` flags the exact stale sections across SAD, SDD, SSTR and sFMEA and opens a redline PR with only those sections. The DOCX shows tracked changes, and the readiness gate blocks until suggestions are resolved.
4. `dhf audit-pack` produces documents, manifests and checksums; `out/metrics.md` shows 0 invented IDs, the claim mix, coverage and cost per document.
5. Extensibility: add a document type with a YAML file only.

---

## 17. Open questions (design so answers don't cause rework)

- **Real dataset format and ADO process are unknown.** Keep adapters swappable and all ADO mapping in config.
- **No real ADO org yet.** The mock must stay contract-faithful so M11 is only a config change plus the seeder.
- **"SUTR" vs "SSTR":** the problem statement uses both. Build SSTR; AB7 adds SUTR via spec.
- **"Change tracking" may mean Word tracked changes specifically.** AB4 covers it; the PR diff covers the rest.
- **Copilot Studio sandbox capabilities** (Dataverse, premium connectors, custom connectors, Azure Functions, model choice) are unconfirmed. The port pack documents fallbacks for each.
