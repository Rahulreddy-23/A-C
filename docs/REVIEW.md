# Review Log

Written by Claude. Since 2026-11-03 Claude is engineer as well as PM and reviewer (AGENTS.md); Codex reads this file at the start of every milestone if re-engaged.

## PR #1 — fresh-perspective review (2026-11-03)

**How it was reviewed:**
- Nine independent reviewers, one per angle: line-by-line, removed behaviour, cross-file callers, Python pitfalls, guard routing, reuse, simplification, efficiency and altitude.
- About 45 deduplicated candidates.
- One independent verifier per candidate, quoting the triggering line or refuting it; most confirmations include a reproduction script.
- A final gap sweep of the committed head.
- Refuted: the document-rule scoping (already guarded) and the seeder ignoring `ADO_READ_ONLY` (by design: it is a separate tool for writing synthetic data).

**Fixed on `claude/m17-real-data`:**

*Read-only and data safety*
- `dhf baseline` pushed tags in read-only mode. Every docs push now goes through `DocsReview.push`, and the git channel itself refuses pushes to read-only organizations. A failed tag push deletes the local tag.
- git ignores configured credential helpers (`-c credential.helper=`), so a stored write-capable credential is never used and the PAT is never saved to a keychain.
- The synthetic-only LLM guard missed packs with no evidence items. It now checks the whole graph for generation, regeneration, `copilot-request` and the support verifier.
- The synthetic tag now counts only when the mapping names one explicitly.

*Assessability*
- "Not assessable" is now declared by sources (`provides_links` / `link_classes`) inside the rule engine. An ADO project with nothing linked reports every gap.
- All gap consumers now agree: the CLI, explorer, audit pack, generation facts, DRR and PR bodies (ADR-041 revised).

*ADO ingest*
- Seed lines accept every URL form, and a scope whose seeds yield nothing is an error instead of a whole-project read.
- Seeded scopes read runs only for `test_plans`; other scopes read every run.
- Out-of-scope code links are filtered.
- Results without a test case are counted, not a crash.
- Duplicate document IDs become `ADO-<id>` and are reported.
- Revisions are fetched only for requirements.
- `discover` accepts minimal mapping profiles.
- One reciprocal-link map is shared with the mock.
- `*.localhost` no longer disables read-only mode.

*Document import*
- Tracked insertions are read as accepted; deletions are dropped.
- Content controls are read.
- Cells keep one line per paragraph, so one-item-per-line matrices split.
- Name matching uses whole words, never substrings.
- Blank or punctuation-only cells are not "N/A".
- Globs ignore case, and Office lock files are excluded.
- Dotted versions and "Rev N" order correctly.
- The matrix `header` is honoured.
- Preamble text no longer creates an empty design section.

*Text, IDs and templates*
- Test steps are decoded once, so literal `<…>` text survives.
- HTML with omitted `</td>`/`</tr>`, nested tables and block-level `<li>` content keeps its text.
- The ID grammar covers real shapes (`PREQ-KS-1670`, `SPEC-…`, `SI-…`, `UNIT-Item.Unit`, `ADO-n`), so provenance links and the invented-ID check work for them.
- Template sets are overlays that may only re-present shared sections (ADR-042 revised).
- Manifests without a recorded template keep the default.
- Overlay hashes include their base.

*Explorer, audit pack and docs*
- Element IDs instead of `querySelector`, which the explorer harness requires.
- Audit README and diagram labels follow the evidence (synthetic or confidential) and the product name.
- The docs clone mirrors remote tags.
- The watch test asserts the interval and the cycle order.
- The onboarding guide gives the right `explore` option and states the SAD/SDD limit.

**Gap sweep, also fixed:**
- `dhf discover` works with a PAT that has no Code (Read) scope; repositories are reported as not readable.
- Associated bugs outside the scope are read, so failed results are not reported as having no defect.
- Mappings cannot overwrite reserved attributes such as `synthetic`.
- `pick: all` keeps the latest issue of each per-item document.
- Imported artifacts get content-based revisions, so re-issuing or re-saving an unchanged document changes nothing.
- Subfolders are imported, and older issues are listed in the report.
- Eval goldens always use the default templates; the demo pins the new settings.
- The port check validates template overlays, and flow 05 describes heading levels and recorded templates.

**Not changed:**
- Merged-cell (vMerge) table reading is still quadratic. It is noticeable only for very large merged tables.
- `extract_document` was not split into smaller functions.
- No CLI report-writing helper was added.
- SAD/SDD drafting from document baselines alone is not supported: they need code-derived architecture (R-061). This is now documented rather than half-supported.

## M17 — Real-data readiness (owner dataset trial, 2026-11-03)

The owner supplied the hackathon dataset (`Hackathon_2026/`, gitignored, company data) and a read-only PAT for the real project. Dataset-specific results stay local in `out/real-docs/` and are not quoted here.

**R-055 [blocking] M17 — The ADO adapter could not run on a real project** (`src/dhf/ingest/ado.py`)
- It read the whole project (WIQL caps at 20,000 items; there were no scope or limits), required the Kestrel code repository, crashed on test results and bugs outside the ingest, passed ADO HTML fields through as text, and had no read-only guarantee beyond convention.
- Resolved in 6449ab5: read-only by default for real organizations, enforced at the transport. Added `ADO_SCOPE` (seeds, WIQL, link expansion, `max_items`, test plans, optional repository and history), rich-text conversion, `id_fields`/`id_formats`/`attribute_fields`, a clear expired-PAT reason, and Retry-After handling. The mock now shows reciprocal links. 8 tests.

**R-056 [blocking] M17 — Nothing in a real DHF dataset could be ingested** (no document or CSV adapter)
- Resolved in e9ab449: `dhf import-docs` with a YAML extraction profile, baseline rules D01–D05, and personal CSV columns dropped. Two real-data parser bugs were found and fixed before commit (record bodies running into the next record; descriptions sharing a line with their label). One false finding was fixed by qualifying unit IDs with their software item.

**R-057 [blocking] M17 — Reports and the explorer misread absent link classes as gaps and were branded Kestrel**
- Resolved in e9ab449 and 75c4c3f: rules are marked "not assessable" (ADR-041), product, subject and release are now settings, and the evidence label reads synthetic or confidential.

**R-058 [blocking, owner] M17 — The supplied PAT has expired**
- ADO answered 401 with "The Personal Access Token used has expired." No request reached project data.
- **Needed:** a new PAT with **Work Items (Read)** and **Test Management (Read)** only. Add **Code (Read)** only if R-061 is approved.
- If the organization enforces conditional access, a valid PAT may still be refused off-network; the error text will say so.
- Resolved 2026-11-03 by the owner (no code change): a new read-only PAT was issued and the live trial ran read-only (ADR-043).

**R-059 [owner decision] M17 — Company evidence and the BD-approved drafting path**
- `LLM.generate` refuses non-synthetic evidence for every provider except `mock`, including `copilotstudio`. So the official BD tenant path cannot draft from the real dataset today; deterministic import, gaps and the explorer work locally.
- Relaxing the guard was attempted and correctly blocked as a safety weakening, so it stays strict.
- **Proposed design if the owner and BD clear the dataset for the sandbox (SANDBOX_QUESTIONS 4.1):** an explicit clearance reference (e.g. `DHF_REAL_DATA_APPROVAL`) that unlocks the BD tenant transport only and is recorded in every manifest. Personal OpenAI/Anthropic keys never receive company evidence.
- **Owner (2026-11-03):** AI drafting for the official path runs in the Copilot agents, and the ChatGPT/Claude keys serve development. The folder-exchange path was rehearsed end to end on synthetic data with a local stand-in for the tenant flow. Whether this dataset is cleared for the tenant transport is still open, so the guard is unchanged.

**R-060 [open] M17 — Real mapping profile pending discovery**
- The documents show the human IDs and custom properties (feature, spec type, release, requirement type) that the mapping must name.
- One sample work item's text appears in the specification under a different document ID than its ADO ID. The document ID therefore lives in a field, which `id_fields` supports and discovery's `id_field_candidates` will find.
- Run `dhf discover` with the trial scope once R-058 is resolved.
- In progress (2026-11-03): discovery found the document-ID field automatically; a reviewed mapping profile is kept locally under `out/real/`.

**R-061 [owner decision] M17 — Code evidence for the SDD**
- The real designs describe .NET and web units; the code extractor handles Python only, and source repositories are out of the trial scope.
- Code-derived SDD content needs the owner's approval to read a source repository, plus a C#/TypeScript extractor.
- **Owner decision (2026-11-03):** no source-code evidence is needed for the hackathon.
- Resolved in c94bdcb (ADR-044): SAD and SDD draft from the design documents, which a real-project scope names with `documents:`; ADO stays the source for requirements and tests.

**R-062 [non-blocking] M17 — Generated documents use generic IEC 62304 section structures, not the owner's DHF template structure**
- The owner's SAD, SDD, SSTR and design-review documents follow their own headings and tables.
- A template set mirroring those headings, mapped to existing queries, would make drafts directly comparable to the documents reviewers know.
- Resolved in the template-set commit (`DHF_TEMPLATE_SET=bd`, ADR-042): the SAD, SDD and SSTR follow the owner's headings, grouping and order, with software items and units nested as in the owner's documents.
  - Shared sections keep the default IDs, queries, prompts and validators, so their content is identical to the default drafts.
  - Owner-only headings that need records outside the evidence graph (readiness reviews, tools analysis, version history and so on) are human sections.
  - Regeneration uses the template recorded in the manifest.

**Item format:** `R-NNN [blocking|non-blocking] M<N> — finding (file:line) — expected fix`

**Codex:**
- Fix every `[blocking]` item before starting new work.
- Append `Resolved in <sha>: <note>` under each item you fix.
- Don't edit or delete the reviewer's text.
- If you disagree with an item, write your reasoning under it.

## Open

- **SAD `architecture_overview` is good.** Each component has a distinct responsibility and named collaborators, so R-033 works.

The sections tested were `sstr/release_conclusion`, `sstr/anomaly_assessment`, `sad/architecture_overview`, `sdd/behavior.UNIT-sensor_pressure` and `sfmea/function_modes.UNIT-sensor_pressure`. Prices are from OpenAI's pricing page as of 2026-10-13.

| Model | $ per 5 sections | ≈ $ per full doc set (~120 AI sections) | Quality notes |
|---|---|---|---|
| gpt-5-nano | 0.0024 | 0.06 | Thin: 1 FMEA claim kept; leaks meta-language ("synthetic fixture") |
| gpt-5.4-nano | 0.0064 | 0.15 | **All 5 FMEA claims rejected**; unreliable |
| **gpt-4.1-mini** | 0.0084 | **0.20** | Consistent, fast (~3 s), correct FMEA system effect; best value |
| gpt-5-mini | 0.0129 | 0.31 | Deeper code detail (dwell timer, 3 s boundary); slower (5–10 s) |
| **gpt-5.4-mini** | 0.0234 | **0.56** | **Best FMEA semantics** (local effect "returns SAFE…", system effect → HAZ-04); good review questions |
| gpt-4.1 | 0.0399 | 0.96 | No better than 4.1-mini |
| gpt-5.5 | 0.1334 | 3.20 | Best overall (noticed BUG-03 isn't listed as residual), but too expensive to run routinely |

**Rejections don't separate the models.** Every model's rejections were `unknown_ids`, mostly `UNIT-alarm_latch`, `UNIT-sensor_pressure`, SRS-012/034/035 and fact keys like `gap_findings`/`summary`/`G01`. That's the R-041(b) pack problem, not model quality.

- **0 `ai_unavailable` sections and no refusals.** 14 claims were rejected out of roughly 440.
- The analytical tier was routed correctly (sFMEA, DRR and SSTR conclusion on `gpt-5.4-mini`), and model and tier are recorded per section.
- The live samples were judged review-ready drafts. The owner has the outputs as Word files.

  - SSTR 5 supported / 1 partial / 1 unavailable (83%)
  - SAD 34 / 1 / 7 (97%)
  - SDD sample of 40: 36 supported / 1 partial / **1 unsupported** / 2 unavailable (95%)
- **A genuine catch, worth showing in the demo:** `sdd/errors.UNIT-alarm_latch` claimed explicit invalid-input rejection, but the verifier found that "the provided code in UNIT-alarm_latch does not show handling of invalid input". The model had carried the requirement's wording into the code description.
- R-046 helped: SAD generation rejections dropped from 6 to 2.

**R-054 [non-blocking — fix before the first tenant run] M16 — Make the official path survive if "Run a prompt" doesn't expose token usage** (`src/dhf/llm/adapters/copilotstudio.py:139-141`, `src/dhf/llm/__init__.py:~438`, `day1/http_prompt_flow.md` step 4)
- The adapter **rejects every response** without integer `input_tokens`/`output_tokens` (`invalid_usage`). It's not certain that the AI Builder "Run a prompt" action exposes token usage in its dynamic outputs; the docs only describe the text and JSON outputs. If it doesn't, the whole BD-approved path fails on day 1, even though generation works.
- **Expected fix:**
  - Add `DHF_COPILOT_USAGE=reported|estimated` (default `reported`).
  - In `estimated` mode, missing usage is computed locally: input = the existing conservative bytes÷3 estimate of the request text inputs, output = the same estimate of `claims_json`. Ledger and manifest entries are marked `usage_source: estimated`, metrics show "estimated credits", and the tenant Monitor tab stays the authoritative billing figure.
  - The flow spec says: return usage if the action exposes it, otherwise omit the fields and set `estimated` mode.
  - Add tests for both modes.


Resolved in b1bf140: added strict reported/default and explicit estimated missing-usage fallback for HTTP and OneDrive; shared rounded-up UTF-8 bytes ÷ 3 estimates, persistent cache/ledger/section/document/metrics usage_source (including mixed), source-separated cumulative credits and labelled estimated-credit metrics. Supplied invalid usage remains rejected; cache hits remain free. Updated flow guidance, both-mode cap/cache/manifest/metrics/regeneration tests and legacy-ledger coverage. Full offline suite: 126 passed; lint/format and port/demo checks green. No tenant or paid calls. PROGRESS now credits the reviewer's completed M13 visual check and records M16 done offline; development stopped for owner sandbox answers.


## Resolved

### M16 (commit f8964e6) — verdict: **approved; R-054 before the first tenant run**

**R-052 [DECIDED 2026-10-13: owner chose option B, the hybrid approved-model adapter; build it as M16, BRIEF §18.1] M14 — The official demo must use BD-approved AI only; the demo pack's AI paths don't meet that** (`docs/DEMO_SCRIPT.md`, `tools/demo.py`, port pack)
- The problem statement says to *"leverage only BD approved AI tools"*. BD's sandbox rules say GPT models through Copilot Studio.
- In the demo pack, the offline mode uses the **mock** provider, so every AI-written section in the fallback Word files is structural mock prose that judges will read. `--live` uses the owner's **personal OpenAI API key**, which is fine for development testing but is not a BD-approved tool for the official demo.
- **Proposed direction (the PM recommends B, with A as the fallback):**
  - **A — Native MVP only.** Build the BUILD_PLAN slice in the sandbox. Copilot Studio generates 1–2 sections live with an approved GPT model. Everything else is shown from the reference engine and clearly labelled "structural/mock AI".
  - **B — Approved-model adapter (hybrid).** Add a `copilotstudio` provider to the dhf LLM layer:
    - It sends each section's prompt, the facts JSON and the evidence JSON to a **Power Automate cloud flow in the BD sandbox**. The flow runs AI Builder **"Run a prompt"** with an approved GPT model (Basic tier) and returns claims JSON.
    - Our tested engine still does ingest, validation, rendering, redlines, impact and the audit pack, but **all AI text comes from BD-approved models in the BD tenant**.
    - The Copilot Studio agent is the conversational front door (start generation, show gaps and status) and calls the same flows.
    - Cost: about 120 sections × about 4K tokens × 0.1 credits per 1K ≈ **50 credits per full five-document run**, well inside 600 per month.
    - It depends on: an HTTP-request trigger, or a request queue (SharePoint list or Dataverse row) if HTTP triggers are DLP-blocked, plus the "Run a prompt" action and a GPT model listed in the prompt builder.
- **Expected once the owner chooses:**
  - (1) The adapter, offline-tested against a stub HTTP endpoint, with the same budget, cache and validator path. The `--live` demo then uses `DHF_LIVE_PROVIDER=copilotstudio`.
  - (2) A flow spec and day-1 kit entry for the prompt-runner flow.
  - (3) The demo script states which provider produced each AI section and never presents mock prose or personal-API output as the official path.
  - (4) A **Copilot Studio beat** in the 6:40 script (agent in the test pane or Teams: "Draft the release test report" → status → PR or SharePoint link), with a screenshot fallback.

Resolved in f8964e6: M16 adds the `copilotstudio` Basic-GPT provider with signed-URL HTTP flow and one-document OneDrive folder exchange, common cache/credit ledger/claims validator/human-placeholder paths, a dry-run exact payload, stubbed offline tests, and tenant flow kit. The official script names the approved provider, orders HTTP → folder → native MVP, labels mock/personal-API prose as development output, and requires a real owner-captured tenant screenshot rather than inventing one. BD tenant operation remains pending and is not claimed.
- *Implemented in M16 (f8964e6) and reviewer-verified:
  - The `copilotstudio` adapter has an HTTP mode (HTTPS-only, signed URL never logged, exception text suppressed) and an atomic folder-exchange mode with timeout.
  - It enforces request-ID echo and validates the model name and usage, with refusal/empty/malformed output mapped to distinct reasons.
  - One generic tenant prompt takes versioned instructions as text; `dhf copilot-request` previews the payload.
  - `DEMO_SCRIPT.md` labels the offline run "structural rehearsal, outside the official AI evidence path", states the official path (BD Basic GPT via the tenant prompt; HTTP first, then folder, then native A), adds the Copilot Studio agent beat with a real-tenant screenshot fallback, and forbids presenting personal-API output as official.
  - 109 tests pass. Follow-up: R-054.*

**R-053 [non-blocking — fix before the owner's first sandbox session] M15 — Day-1 validator cards: say where each formula runs; cloud flows can't run Power Fx** (`port/copilot_studio/day1/validator_powerfx.md`, `click_path_tier_b.md` step 5)
- The cards present the citation-subset, kind and confidence checks as **Power Fx** "after Parse JSON and Select in flow 04". Flow 04 is a **Power Automate cloud flow**, and cloud flows use workflow expressions (WDL), not Power Fx. Pasting these into flow 04 will fail on day 1.
- `native_validator.md` does say "a Power Fx extraction step in a topic or supported Dataverse low-code plug-in", but the day-1 card and the click path don't make the split clear.
- **Expected fix:**
  - (a) For flow 04, give **paste-ready WDL**:
    - citation subset: `Filter array` (From: citations; condition `@not(contains(variables('EvidenceIds'), item()))`) then `@equals(length(body('Filter_array')), 0)`
    - kind: `@contains(createArray('sourced','inferred','suggested'), items('Apply_to_each')?['kind'])`
    - confidence: a range check with `greaterOrEquals`/`lessOrEquals` and an `empty()` check
  - (b) State that **only the `MatchAll` ID/number extraction** needs Power Fx, and give the host options with how flow 04 calls each:
    - a Dataverse low-code (instant) plug-in, called through "Perform an unbound action", or
    - a Copilot Studio topic formula
  - (c) Add "Are Dataverse low-code plug-ins available?" to `SANDBOX_QUESTIONS.md`.
  - (d) Keep the `numeric_unverified` compensation as the documented fallback.

Resolved in f8964e6: `validator_flow_wdl.md` provides cloud-flow WDL for citation, kind and confidence; the click path now sends only `MatchAll` extraction to a Dataverse instant plug-in or agent-topic handoff. `validator_powerfx.md` names those hosts, `SANDBOX_QUESTIONS.md` asks about plug-in availability, and the blocked `numeric_unverified` compensation remains documented. Native expressions still require tenant testing.
- *Resolved in f8964e6: `day1/validator_flow_wdl.md` gives paste-ready WDL for citation, kind and confidence in cloud flow 04. Power Fx is limited to the `MatchAll` extraction, hosted in a Dataverse low-code plug-in through "Perform an unbound action", or in a topic.*

### M15 (tag `m15-done`, 5a88eb9; kit in 6c1d7cd) — verdict: **approved; R-053 before the first sandbox session**

Verified independently:
- 93 tests pass; ruff is clean.
- `port/copilot_studio/day1/` has:
  - paste-ready SSTR-anomaly and SAD-component prompts, each with four **Text** inputs (`facts_json`, `evidence_json`, `max_claims`, `preferred_kind`) and fixed JSON output
  - literal sample inputs and expected validated outputs
  - validator cards with reference cases
  - an `mvp_columns.csv` worksheet for 4 Dataverse tables
  - a 9-step Tier B click path (flows 01→07 as cloud flows, then the thin agent)
- It's honest throughout ("offline construction guide; no tenant step executed").
- Follow-up: R-053, where the validator expressions run.

**R-050 [non-blocking — include in M15; required before the sandbox build] PM — Adapt BUILD_PLAN and the day-1 kit to BD's sandbox guardrails** (`port/copilot_studio/BUILD_PLAN.md`, `day1/`, `agent.md`, `governance.md`)
- The owner supplied BD's Citizen Developer guardrails. They're summarised at the top of `docs/SANDBOX_QUESTIONS.md`. Fold them in:
  1. **Credit-aware architecture.** There's a hard limit of **600 Copilot credits per agent per month**.
     - Run ingest, gaps, assembly, PR and impact as **Power Automate cloud flows**. These are billed by Power Automate licensing, not Copilot credits. Avoid agent flows for loops: 13 credits per 100 actions means looping over 126 work items alone could cost 100+ credits.
     - Keep the agent thin: one topic, one action to start a request (≈5 credits) and one to check status. Avoid unnecessary generative answers and knowledge grounding.
     - Use **Basic-tier** prompt models only, at 0.1 credits per 1K tokens: a 4K-token section costs about 0.4 credits. **No reasoning/Premium models in the sandbox** (10 per 1K, about 40 credits per section). At most Standard (1.5 per 1K) for one showcase section.
     - Map our tiers: `default` → Basic, `analytical` → Standard only if budgeted, otherwise Basic.
     - Add a **credit budget table** to BUILD_PLAN: per MVP run, per rehearsal, and for a total of about 20 rehearsals plus the demo, with headroom kept under 600 per month. Add a "check the Monitor tab" step.
  2. **Agent creation path.** Use the original experience → Agent (or New experience → Other ways to build → Agent, Standard). **Never** the GitHub Copilot agent/workflow options. Put the mandatory **agent description** text in `day1/` (business problem, audience, value, data sources), using the DHF problem statement and synthetic data sources.
  3. **Models.** GPT only. Remove Claude from every Copilot Studio instruction. Anthropic stays a reference-implementation-only provider.
  4. **Connectors.** The sandbox is "base access, some restricted connectors". Add a **Tier C′ "no ADO connector"**:
     - the reference implementation exports a canonical snapshot (JSON/CSV) from ADO or the mock
     - it's uploaded to SharePoint or imported into Dataverse
     - cloud flows read it; documents go to a SharePoint library with version history as the review/change record
     - the impact demo works by uploading the post-`change_1` snapshot
     - ADO integration is demonstrated live by the reference implementation, and the agent shows generation, governance and impact

     Mention the Digital Innovation Request route to a Prototype environment with premium connectors as the path, not a demo dependency.
  5. **Data.** Synthetic only. Load the real hackathon dataset into the sandbox only if the owner confirms it's cleared.
  6. **Sharing and demo channel.** Test pane plus a Teams channel after publishing. At most 5 named individuals, no groups. Re-publish after every change.
- Keep the honesty rules: nothing claims tenant execution.

Resolved in 6c1d7cd: Basic-tier GPT and thin-agent cloud-flow plan with 600-credit Monitor/400-credit guard estimates, mandatory Standard-agent description/path, synthetic-only and five-person sharing gates, and Tier C-prime reviewed JSON/CSV snapshot import with a working `dhf export-snapshot` command. Day-1 files include prompts, validator cards, CSV columns and flow click path; tenant checks remain pending.
- *Reviewer verified at m15-done: the day-1 README covers the sandbox name, original-experience Agent creation path, never the GitHub Copilot options, the mandatory agent description (paste-ready), one thin topic with StartGeneration/GetRunStatus, loops in cloud flows (not agent flows), Basic-tier GPT only, no Anthropic/Premium, Monitor checks, Teams with at most 5 named users, and synthetic-only data. BUILD_PLAN has a credit plan with a 400-credit local guard under BD's 600 and a Tier C-prime (no ADO connector) path with a snapshot export (`src/dhf/graph/export.py`).*

**R-051 [non-blocking, polish before the demo] M13 — Explorer details from the reviewer's second visual check (c6795b4)**
- **Truncated labels.** Text like "UNIT-sensor_pr…" and "RES-3-021 · Fa…" is cut off. Widen lane boxes slightly or wrap to two lines, and add a `title` tooltip with the full ID and outcome.
- **Stale inspector selection.** When a search or filter hides the selected node, the inspector keeps showing it (SRS-010 stayed selected after searching "occlusion"). Select the first match, or clear the inspector with a hint.
- **Size for projection.** The focused trace chain is small inside a large canvas. Add a "fit / zoom" control, or scale the focused chain to fill the lane area, so it reads on a projector.

Resolved in 6c1d7cd: node IDs/outcomes wrap to two lines with full SVG tooltips, filtering selects a matching inspector record, and Expand graph makes the lane board full width for projection. The refreshed offline fallback and DOM regressions pass; final projector/browser viewing is an owner check.
- *Reviewer verified at m15-done through tests and `tools/check_explorer.cjs`; the explorer HTML was updated. A visual re-check is optional before the demo.*

### M14 (commit c49b24b) — verdict: **approved as a rehearsal pack; R-052 decides the official-demo AI path**

Verified independently:
- 88 tests pass; ruff is clean.
- `tools/check_demo_pack.py` passes: fallback index, checksums and tracked redline.
- `docs/DEMO_SCRIPT.md` is a 6:40 talk track with one beat per criterion (25/25/20/10/10/10), exact commands, a `--pause-before-change` stage mode, and a fallback for every beat with honest wording ("This is the recorded offline rehearsal").
- `docs/JUDGING_MAP.md` links each criterion to its evidence.
- `--live` respects the owner's caps and stops rather than retrying on a refusal.
- **Credit given:** the script attributes the alarm-latch unsupported-claim finding to the reviewer's live run, and labels fallback support metrics as mock lexical checks.

**R-048 [non-blocking, before M14 demo pack] M12 — 11% of support checks are silently "unavailable", and the rate hides them** (`src/dhf/generate/support.py:92-104`, metrics/CLI)
- 10 of 89 checks came back `unavailable`. The reason recorded is `type(error).__name__`, which is always "ValueError", so the real cause is lost.
  - The reviewer patched a scratch copy to record `str(error)`. All 7 SAD failures were `invalid_verification_rationale`: the verdict's *rationale* text goes through `validate_claims`, and it fails when the explanation mentions an ID or number that isn't in the pack. A valid supported/partial/unsupported verdict is then thrown away.
- The support rate excludes unavailable checks from the denominator. The SAD's "97%" really covers only 35 of 42 claims.
- **Expected fix:**
  - (a) Record the specific reason string.
  - (b) Keep the verdict when only the rationale fails validation. Store the rationale flagged `rationale_unverified`, or strip the offending tokens, and count it separately.
  - (c) The CLI and `out/metrics.md` report **coverage**, `verified / eligible`, next to the support rate, with the denominator stated explicitly.
  - (d) Add one retry for the rationale with the allowed IDs listed, inside the ledger cap.

Resolved in 8233c49: exact unavailable reasons, one ledger-protected rationale repair, retained flagged verdicts and explicit support/coverage denominators. Invalid rationale is stored as unverified audit data but never reaches Word; safe warning comments remain. Offline regression covers repeated invalid rationale and missing revisions.
- *Reviewer verified at 8233c49 by code and tests: a single rationale retry with the allowed IDs keeps the verdict, specific reasons are recorded, and coverage (verified/eligible) is reported. A live re-check is planned in the M14 `--live` demo run.*

**R-049 [non-blocking, before the M14 demo pack — demo impact] M13 — Explorer usability in a real browser (reviewer visual check at 1440×900 in the built-in browser)**
- **What works:**
  - The page renders cleanly, with lanes for need → system → SRS → component/unit → change → test → …
  - The legend shows gap finding, stale-section cause and latest result.
  - The inspector shows type, revision, source, gap rules and stale cause, plus clickable recorded links.
  - Search works ("occlusion" gives 7 chips: SRS-021, HAZ-04, RC-04, TC-021, PR-8, RUN-3, BUG-02).
  - The stale filter gives the 5 causes.
  - It works fully offline.
- **(a) Filtered views don't compact.** After a search or filter, matching nodes keep their full-layout positions. The panel looks empty (PR-8 floating mid-panel, other matches off-screen) and a judge will read it as broken. Re-lay out the lanes to show only matches and their direct neighbours, starting at the top.
- **(b) There's no "trace chain" focus.** This is the key traceability moment in the demo: click SRS-021 and see *only* its connected chain, compacted lane by lane: need → SYS-007 → SRS-021 → COMP-03/UNIT-sensor_pressure → PR-3/PR-8 → TC-021 → RES-3-021 (Failed) → RC-04 → HAZ-04. Make that the default when a node is selected, with "show all" to go back.
- **(c) Source links die after the demo.** "Open source · revision 2" points at the demo's ephemeral mock port (`http://127.0.0.1:58602/…`), which stops when the demo exits. Either take a stable base URL for presentations (e.g. `--source-base http://127.0.0.1:8089`, with the demo keeping the mock up), or show the source record (title, body excerpt, revision, retrieved time) inline in the inspector so the walk-through doesn't depend on a live server.
- **(d) The full view is a dense tangle of edges.** Dim all edges by default and draw them strongly only for the selected node's chain.
- **(e) Minor:**
  - The gap-rule dropdown omits the baseline findings C01/C04, which are central to the stale-documentation story; add them as a "baseline" filter.
  - "Reset filters" may not clear the search text; please check.
- The reviewer's copy for the owner: `out/review-samples/explorer-stale-m13.html`.

Resolved in c6795b4: compact lane layout and viewport for filtered/focused nodes, actual SRS-021 trace chain on selection, inline source excerpt, subdued non-chain edges, baseline C01/C04 filter, and reset clearing text and focus. Automated graph/DOM regressions pass; the owner-provided screenshot prompted the final inspector and canvas tightening. Browser repaint still requires owner visual confirmation.
- *Reviewer verified visually at c6795b4 (1440×900, built-in browser): selecting SRS-021 shows the compact chain UN-001 → SYS-007 → SRS-021 → COMP-03/UNIT-sensor_pressure → PR-3/PR-8 → TC-021 → RES-3-021 (failed) → HAZ-04/RC-04, with stale markers and the revision-2 source text inline ("above 75 kPa"). The inspector lists the document sections each change made stale. Searching "occlusion" compacts to 7 matches plus 18 neighbours. Polish follow-ups are in R-051.*

### M13 (tag `m13-done`, 2ae290c) — verdict: **approved; usability fixes R-049 before the demo pack**

Verified independently:
- 84 tests pass; ruff is clean.
- The demo produces `explorer.html` and `explorer-stale.html` (231 KB, 251 artifacts, 416 links), with no external URL literals.
- The reviewer completed the visual check Codex couldn't run, in the built-in browser via a local static server: it renders, search, filters and the inspector work, and it's offline.

### M12 (tag `m12-done`, 58c2c19; code cbf0a85) — verdict: **approved**

Verified independently in a clean worktree:
- 82 tests pass; ruff is clean.
- `dhf verify-support` is advisory only (manifest `claim_support.advisory_only=true`), records the prompt and model per result, flags rather than removes unsupported claims, and never touches readiness.
- `dhf eval` adds effort telemetry: AI/deterministic/human section counts, assumed authoring hours from YAML (labelled as assumptions) and measured cost and time.
- R-046 and R-047 are fixed:
  - the default seeder mode no longer writes system dates and preserves chronology, so G11 flags only TC-030
  - the mock rejects read-only dates unless `bypassRules=true`
  - non-empty projects are refused unless `--allow-nonempty`
- Follow-up: R-048.

**R-046 [non-blocking] M10 — Small leftovers from the live run** (`src/dhf/graph/design.py`, `specs/prompts/sstr.conclusion.md`)
- **(a)** 9 of the 14 rejections are collaborator component IDs (`COMP-01..05`) cited in SAD component and runtime prose. Collaborators named in a component's record should join its evidence pack as compact records, the same treatment R-041 gave to fact references.
- **(b)** The SSTR conclusion had 5 kind coercions, where the model labelled claims `sourced` in a suggested-only section. State "every claim in this section is `suggested`" in the prompt to cut audit noise.
- **(c)** One numeric rejection each for "3" and "256" in narrative. Check that unit-bearing values quoted from evidence ("3 s") reach `source_numbers`.

Resolved in cbf0a85: compact collaborator evidence, suggested-only conclusion v3 and unit-bearing quantity parsing are covered by regressions; unsupported SHA digits stay rejected.
- *Reviewer verified at cbf0a85.*

**R-047 [blocking before any real-ADO seeding — fix within Phase 2, before M15] M11 — The seeder will probably fail on a real ADO org, and it doesn't refuse non-empty projects** (`tools/seed_ado/__init__.py:175-211, 330-346`)
- **(a) Read-only system dates.** The seeder writes `System.ChangedDate` (the mapped `changed_at` field) on create and on the SRS-030 revision update. On real Azure DevOps, `System.ChangedDate`/`CreatedDate` are read-only unless the request uses `bypassRules=true` **and** the identity has "Bypass rules on work item updates". So the first create will most likely return HTTP 400, and the seeder aborts on any error.
  - Even if dates are dropped, G11 depends on chronology. Work items created "now" would postdate the fixture's October test results, so **every** passed test would look outdated and the answer key would break.
  - **Expected fix:**
    - Default real-org mode that never writes system dates.
    - **Preserve relative order instead.** Create work items first, then post runs/results with `completedDate` set to seeding time plus an increasing offset in fixture order, then apply the planted revision-2 updates (SRS-030) **after** their tests' passes, so G11 still flags exactly TC-030.
    - An opt-in `--bypass-rules` flag for orgs that grant the permission, with `bypassRules=true` and the original historical dates.
    - Make the mock reject `System.ChangedDate` writes unless `bypassRules=true` is sent, so the tests reflect real behaviour.
- **(b) No non-empty-project guard.** The docs say "never seed an existing production project", but the code doesn't enforce it.
  - **Expected fix:** refuse to seed if the project contains any work items without `DHF:` identity tags, or any repos or runs not created by the seeder, unless `--allow-nonempty` is passed explicitly. Print what was found.

Resolved in cbf0a85: default readonly-date-free chronology preserves exact gaps including only TC-030 G11; historical dates require --bypass-rules. Foreign work-item/repo/run inventory refuses before writes unless --allow-nonempty. Both modes, idempotence and guards pass offline; real tenant checks remain pending.
- *Reviewer verified at cbf0a85.*

### M11 (tag `m11-done`, 279debf) — verdict: **approved; R-047 must be fixed before seeding a real org**

Verified independently in a clean worktree:
- 77 tests pass; ruff is clean.
- **Seeder guards:**
  - `--confirm-org` must match the org parsed from `ADO_BASE_URL` (dev.azure.com and visualstudio.com forms).
  - It refuses to run if the seed token equals the app token.
  - `--dry-run` writes nothing.
  - Idempotency comes from `DHF:` tags, and duplicate identities abort.
- **Mock write routes** are seed-token-only; the app token gets 403, and the product's write allowlist is unchanged.
- **`dhf discover`** is read-only, drafts into `out/` without overwriting the active mapping, and flags renamed fields as unknowns needing confirmation.
- **`docs/REAL_DATA_ONBOARDING.md`** walks through discover → review → ingest → validate → generate, and is honest that tenant verification is pending.

### M10 (tag `m10-done`, ecac18b; implementation e707d9a) — verdict: **approved — core build complete (M0–M10)**

Verified independently in a clean worktree:
- 74 tests pass; ruff check and format are clean.
- **`./scripts/demo.sh` exits 0 offline in 33 s.** It runs native HTTP ingest, docs PRs, readiness failures, labelled test-tool merge and baseline, watch plus `change_1`, selective regeneration, SUTR and RTM from YAML only, `dhf eval` and the audit pack.
- **`out/metrics.md`:**
  - 0 unknown IDs.
  - Gaps precision/recall 1.00 (21 findings).
  - Impact 1.00, correctly labelled "regression against a reviewer-audited expectation".
  - Historical C01/C04 2/2.
  - Deterministic goldens match.
  - Coverage: SRS→test 31/35, SRS→code 33/35, hazard→control→verification 8/8.
- **The clause appendix is honest:** 62304 §5.5 and §5.6, 14971 §6 and §8, and the release review are marked UNCOVERED or human-pending.
- **The audit pack** has 32 verified files.
- **The SAD figure** is a locally rendered PNG (6 components, 20 units, declared interfaces, and the extracted COMP-03→COMP-04 `alarm_latch` call), embedded and numbered in the DOCX.
- **`BUILD_PLAN.md`** has an ordered MVP (~20–33 h), day-1 capability gates with fallbacks, and Tier A/B/C storylines.
- Remaining: P2 items (AB9–AB13), optional M11, and the Copilot Studio build, which waits on the owner's sandbox answers (`docs/SANDBOX_QUESTIONS.md`).

**R-030 [non-blocking, by M10 — demo impact] M6 — The architecture diagram is Mermaid source only, so the Word SAD shows a code listing, not a diagram** (`out/documents/sad.architecture.mmd`, SAD `architecture` section)
- No local Mermaid or Graphviz renderer exists, so the DOCX gets a monospace block of `flowchart LR …`. A rendered architecture figure is one of the most visible parts of a SAD for reviewers and judges.
- **Expected fix:**
  - Render a PNG locally and deterministically: components as columns or boxes, their units listed inside or below, external interfaces at the edge. Pillow is enough for a grid layout; record the dependency in an ADR.
  - Embed the PNG in the DOCX with a caption and a figure number.
  - Keep the Mermaid source in the Markdown (ADO's markdown preview can render it) and the checksum in the manifest.
  - Never use an online renderer.

Resolved in e707d9a: local deterministic PNG and Mermaid assets are checksummed and committed to docs PRs; Word embeds a numbered figure. Figure/Word and repeatability tests pass.
- *Reviewer verified at m10-done.*

**R-041 [non-blocking, before M10] M8 — Live findings: FMEA "effects" describe the control, not the failure; SAD packs drop the units their facts reference**
- **(a) FMEA semantics.**
  - HAZ-03's "Local effect" and "System effect" describe what happens when the control *works* ("inhibited delivery… prevention of air embolism"), not what the failure *causes* (air delivered → embolism risk).
  - HAZ-04's "System effect" describes an Alarm Manager failure rather than the patient-level outcome. Controls are called "requirements RC-04…".
  - **Fix:** in the sFMEA prompt and the R-037 row design, define each cell explicitly:
    - failure mode = how the function fails
    - cause = why
    - local effect = immediate consequence *with the failure present*
    - system effect = device or patient consequence
    - controls and detection come only from sourced tables

    Add one worked example row.
- **(b) Evidence/fact mismatch.** In `component_responsibility.COMP-03` and `runtime`, **2 of 4 claims were rejected** for citing `UNIT-sensor_pressure`, `UNIT-alarm_latch`, `COMP-02` and `COMP-04`. The structural facts mention these, but the evidence pack doesn't include them.
  - **Fix:** every ID referenced in a section's facts must be present in its evidence pack, as compact records. Add a test asserting `ids(facts) ⊆ ids(evidence)` for every AI section.

Resolved in e707d9a: FMEA v2 prompts define failure-present local/system effects and a worked example; all AI fact IDs have source context, including compact synthesis records, with subset/reduction regressions.
- *Reviewer verified at m10-done.*

**R-042 [non-blocking — high priority before the sandbox build starts] M9 — The port pack describes the full build but has no realistic plan or cut line for it** (`port/copilot_studio/README.md`)
- The pack maps everything: 7 flows, 11 Dataverse tables, 21 prompt tools, AST/hash/validator/DOCX function boundaries and the parity cases. Building **all** of that in an unfamiliar sandbox before the Oct 27 demo is not realistic, and the official submission must run in Copilot Studio.
- **Expected:** add `port/copilot_studio/BUILD_PLAN.md` with:
  1. **The MVP vertical slice to build first**, in order:
     - agent with a "Draft the release test report" topic
     - flow 01/02 ingest into Dataverse
     - flow 03 gaps for G01/G05/G07/G11
     - flow 04 for **one** SSTR synthesis section and **one** SAD/SDD section through the prompt tool, with the native validator (R-043)
     - flow 05 Markdown assembly
     - flow 06 docs PR plus the readiness status
     - flow 07 work-item-update trigger showing "SRS-021 changed → these sections stale"
  2. **Hour estimates** per step and a **cut line**: what gets dropped first if the sandbox lacks Dataverse, premium connectors or a function endpoint.
  3. **A demo split.** State explicitly what judges will see running natively in Copilot Studio versus what is shown from the reference implementation as "the same specs, executed offline" (DOCX redline, full SDD, audit pack).
  4. **A capability-check checklist for day 1 in the sandbox**, with a fallback for each gap.
- **PM update (owner instruction):** the sandbox details aren't known yet, so don't wait for them. Write the plan with **three capability tiers** and finish everything that doesn't depend on the tier:
  - **Tier A:** Dataverse + premium ADO connector + an approved Azure Function/custom connector. That gives the full slice: AST, hash, validator and DOCX run as functions.
  - **Tier B:** Dataverse + premium ADO connector, **no** functions. The validator runs natively (R-043). AST is replaced by a reviewed unit inventory imported from the reference implementation. DOCX redlines use Word Compare. Hashes come from the reference implementation.
  - **Tier C:** **no** Dataverse. Use SharePoint lists for Artifact, Link, Section and Run (state the row and size limits), keep the scope to the SSTR plus the impact demo, and show the rest from the reference implementation.
  - For each tier, list which flows and prompt tools are built, the hour estimates, the demo storyline, and which parity cases can pass. The owner's answers to `docs/SANDBOX_QUESTIONS.md` will pick the tier, so make the plan easy to collapse to one tier quickly.

Resolved in e707d9a: BUILD_PLAN contains ordered MVP, estimates/cut line, A/B/C capability tiers, SharePoint row/file limits, fallback gates and scoped parity/native-offline storylines. Tenant execution is explicitly pending.
- *Reviewer verified at m10-done.*

**R-043 [non-blocking — before the sandbox build] M9 — Keep the core governance native, and pass prompt-tool inputs as text** (`port/copilot_studio/flows/04-generate-section.md`, `deterministic_logic.md`, `prompts/*.md`)
- **The validator.** The pack makes the validator an "approved function", falling back to "manual drafting boundary" when none exists. But source-backed vs inferred governance is worth 20% of the score, so the MVP slice must validate claims **natively**:
  - citations ⊆ evidence IDs and IDs found in the text ⊆ evidence IDs (Power Automate `Filter array` / `contains` / `intersection`)
  - `kind` in the allowed list
  - confidence present for inferred/suggested
  - downgrade and coerce rules
  - **The numeric check:** use Power Fx `MatchAll` (in a topic or a Dataverse low-code plug-in) to extract numbers and compare them against facts. If that's impossible in the tenant, document a compensating control: numbers only in deterministic tables, and AI claims containing digits get `[Suggested]`. Don't silently drop the check.
- **Prompt-tool inputs.** The converted prompt tools declare named inputs typed `object`/`array`. Copilot Studio prompt inputs are text (plus files/images), so pass `facts` and `evidence` as **JSON strings**. Note that the tenant's prompt input/output size limits must be checked against the 6k/12k-token budgets on day 1.

Resolved in e707d9a: native validator recipe covers IDs, kinds, confidence, downgrade/coercion and numeric checks or blocked compensation; all prompt tools take text JSON. Actual tenant limits remain a day-1 gate.
- *Reviewer verified at m10-done.*

**R-044 [non-blocking — do with the next commit] Owner budget cap: $2.50 per provider, enforced in code** (`src/dhf/llm/__init__.py`, `.env.example`, `AGENTS.md` rule 7)
- On 2026-10-13 the owner set a hard cap of **$2.50 per API for the whole hackathon**, counting all spend. The current cap logic is `min(build_cap 1.50, 0.8 × DHF_PROVIDER_BUDGET_USD 5.00 = 4.00)`. That keeps Codex's own build-time calls under 1.50, but it doesn't encode the owner's ceiling for demo and reviewer runs.
- **Expected fix:**
  - Add per-provider hard caps `DHF_HARD_CAP_USD_ANTHROPIC` (2.50) and `DHF_HARD_CAP_USD_OPENAI` (4.00; the owner added $1.50 for model comparisons), enforced as `actual_usd + reserved_usd + this_call_reservation ≤ DHF_HARD_CAP_USD` for every provider and every command, on top of the build cap.
  - Show the remaining headroom in `dhf` output when a paid provider is used.
  - Add a test.
- The reviewer's live checks currently copy `out/ledger.json` into a scratch worktree, run against it, and write it back. That way the cumulative cap already applies to reviewer spend.

Resolved in e707d9a: provider hard caps enforce actual plus reserved spend (Anthropic 2.50/OpenAI 4.00), despite legacy higher config; paid CLI shows headroom. Both provider-cap regressions pass.
- *Reviewer verified at m10-done.*

**R-045 [non-blocking, before the M10 demo run] M9 — Support per-section model tiers and GPT-5-family parameters** (`src/dhf/llm/adapters/openai.py`, `specs/documents/*.yaml`, `.env.example`, port pack)
- **Decision (PM):**
  - Keep **`gpt-4.1-mini` as the default** for all sections.
  - Use **`gpt-5.4-mini` for analytical sections** only: sFMEA function/hazard modes, the SSTR conclusion, DRR suggestions and L01–L03.
  - Never use nano models.
  - Keep `gpt-5.5` only as an optional reference run.
- **Expected:**
  - (a) A section-spec field `model_tier: default|analytical`, with the model per tier set in config (`DHF_MODEL_OPENAI`, `DHF_MODEL_OPENAI_ANALYTICAL`) and prices per model.
  - (b) For `gpt-5*` models, send no `temperature` and set `reasoning_effort` (default `low`). Reasoning tokens are billed as output, so include them in the reservation estimate.
  - (c) In the port pack, a Copilot Studio Prompt tool picks its model per prompt, so map the tiers to the tenant's prompt model options (sandbox question 3.2).
  - (d) Add the model ID and tier to each section's manifest entry.


Resolved in e707d9a: section/rule data routes default/analytical models, with per-model prices/cache identity and section provenance. GPT-5 omits temperature, sets reasoning effort and reserves inclusive completion tokens; SDK/ledger/routing tests pass.
- *Reviewer verified at m10-done.*

### M9 (tag `m9-done`, e972cb5) — verdict: **approved**

Verified independently in a clean worktree:
- 62 tests pass.
- `tools/check_port.py` reports `flows: 7, rules: 22, queries: 46, prompt_tools: 21, reference_contracts: pass, tenant_parity: pending`.
- The pack has a README mapping table, `agent.md` (tools, topics, an async job pattern with a status-polling fallback, and accurate channel caveats), `dataverse_schema.md`, flows 01–07 written step by step so they can be followed without reading Python, `deterministic_logic.md` (every G/C/F/L rule with its operation and parameters, plus function boundaries and fallbacks), `governance.md` (DLP, separate reader/writer connections, no PATs on the ADO connector, web grounding off) and frozen parity cases.
- **It's honest:** it claims no tenant deployment, residency guarantee or parity result.
- Follow-ups: R-042 (build plan and cut line) and R-043 (native validator, text inputs).

**R-037 [non-blocking, strongly recommended before M10] M8 — The sFMEA runs top-down from hazards, one guessed failure mode per hazard; reviewers expect bottom-up rows** (`specs/documents/sfmea.yaml`, `src/dhf/graph/design.py`)
- Today each hazard gets one `[Suggested]` "Failure mode: <hazard name>". That's a hazard analysis, not an FMEA. With the mock, "Local effect" also repeats "Cause".
- A software FMEA is expected to work **per safety-relevant unit function**, using the extracted interfaces (e.g. `PressureMonitor.evaluate`):
  - 1–3 failure modes each (fails to detect, false detection, delayed detection)
  - local effect → system effect → hazard
  - **severity from the source**
  - existing controls and detection (requirements, tests)
  - residual risk left for a human
- **Expected fix:** add that row table for Class C units, which bounds the cost, and keep the hazard-level view as a summary that links back to the rows. Make the mock emit distinct cells.

Resolved in 450b11d: Class C primary functions have bottom-up source traces and distinct suggested analysis cells; hazard summaries link to unit rows. Source-only severity and human residual risk are tested.
- *Reviewer verified at m9-done:* the sFMEA now has per-unit sections with a "Safety-relevant function source trace" table (extracted function, e.g. `AlertScheduler.tick`, hazard with source severity, controls, requirements, verification, residual risk) and a proposed-analysis table. Bottom-up structure is achieved. The live FMEA-semantics finding remains open as R-041.

**R-038 [non-blocking] M8 — DRR pre-review findings skip the most review-relevant items** (`specs/documents/drr.yaml`, `src/dhf/graph/queries.py`)
- The 5-claim cap shows only G01×4 and G02×1. It omits **C01/C04 for the very baseline under review (`sad-v1`)**, G05 (a failed result with no defect) and the risk-control gaps G06/G07.
- **Expected fix:**
  - Start with a deterministic findings table: every rule, with count and links.
  - Order the AI suggestions by safety relevance: stale baseline and risk-control gaps first, then failed tests, then coverage.
  - The empty "Changed evidence since baseline" section should say "No changes since sad-v1 (snapshot 1)" instead of rendering blank.
  - ACT-01–04 descriptions are placeholders ("Review action N"); give them real content.

Resolved in 450b11d: Complete deterministic G/C/F findings table, approved-baseline C01/C04 inputs, safety-first suggestions, named empty-diff notice and specific prior actions.
- *Reviewer verified at m9-done:* the DRR has a complete deterministic G/C/F findings table, safety-first ordering and an empty-diff notice (450b11d).

**R-039 [non-blocking] M8 — L01 produces 35 identical "review whether…" proposals** (`src/dhf/cli.py` propose, `specs/prompts`)
- The planted SRS-034/035 (not implemented) look the same as the implemented requirements, so the proposals file is noise.
- **Expected fix:**
  - Pre-screen deterministically: G02 requirements are reported as "no implementing change" without the LLM.
  - Send only requirements *with* linked code to the model, comparing acceptance criteria to the unit code.
  - Emit a proposal only when a likely gap is found, with its confidence.
Resolved in 450b11d: G02 is pre-screened without model calls; linked code is compared to criteria, agreement emits no proposal, and the fixture flags the missing checksum guard with confidence.
- *Reviewer verified at m9-done:* L01 pre-screens G02 deterministically and emits proposals only for suspected gaps (450b11d).

**R-040 [blocking — fix now; the suite must be green on every commit] M8 — A test fails at 212e688** (`tests/test_design.py`)
- At 212e688 the suite is **1 failed, 59 passed**. `test_design` still expects the old `UNIT-sensor_pressure` allocation (8 SRS), but the corrected R-036 traces give `{SRS-009, SRS-021}`.
- The commit message claimed the regressions pass. Update the expectation to the corrected allocation, which looks right: SRS-022 → `sensor_filter`, SRS-023 → `sensor_calibration`.
- Run the **full** suite before every commit.
- *Reviewer verified at m9-done:* the suite is green at `m9-done`: 62 passed (fixed in 450b11d).

Resolved in 450b11d: corrected the pressure allocation assertion to SRS-009/SRS-021; the full m9-done suite passes (62 tests), independently verified by the reviewer.

**R-036 [blocking — fix before starting M10] M8 — Hazard → risk control → requirement links are paired by index, so the risk traceability is clinically wrong** (`data/synthetic/evidence.yaml` hazards, risk_control and `mitigates`/`implements` links)
- Each `HAZ-0n` is paired with `RC-0n`, and each `RC-0n` is just "Control n: <title of SRS-00n>":

  | Hazard | Control (requirement) |
  |---|---|
  | HAZ-03 Air delivery | Start interlock, Alarm priority |
  | HAZ-04 **Undetected occlusion** | **Pause control** (SRS-004), plus the unrealised Alarm latch |
  | HAZ-05 Alarm unavailable | Stop control |
  | HAZ-06 Incorrect drug limit | Rate conversion |
  | HAZ-07 Lost audit evidence | Dose calculation |
  | HAZ-08 Unintended restart | Air detection |
  | HAZ-01 Over infusion | Flow bounds, but also Pressure sampling |

- So the occlusion hazard is allocated to the **Alarm Manager** (COMP-04, `alarm_*` units) and never reaches SRS-021 (occlusion threshold), `UNIT-sensor_pressure` or TC-021. The bad mapping flows into the sFMEA, the SAD's "Architectural risk-control measures" and the new structural facts (`hazard_controls`) that feed SAD prose.
- QA/RA judges will spot this immediately, and a wrong hazard–control trace is worse than none.
- It also weakens the main demo: `change_1` edits the occlusion requirement, but the sFMEA occlusion block doesn't depend on it.
- **Expected fix:** re-map controls to the requirements and units that actually implement them, and give controls real names:

  | Hazard | Requirements | Units |
  |---|---|---|
  | Over infusion | SRS-001/002/028 | `infusion_bounds/volume` |
  | Under infusion | SRS-006/008 | as appropriate |
  | Air delivery | SRS-008 | `sensor_air` |
  | **Undetected occlusion** | **SRS-021/022 + SRS-012 latch** | **`sensor_pressure/filter`, `alarm_latch`** |
  | Alarm unavailable | SRS-011–014 | `alarm_*` |
  | Incorrect drug limit | SRS-018–020 | `drug_*` |
  | Lost audit evidence | SRS-024/025/033 | `log_*` |
  | Unintended restart | SRS-029/030 | watchdog / power-loss |

  - Use real control names, e.g. "Sustained-pressure occlusion detection with latched critical alarm", not "Control n: …".
  - Set `risk_control: true` on the realising SRS.
  - Keep the planted G06 (one unrealised control) and G07 (one unverified risk-control requirement), reassigning them if needed.
  - Update `expected_gaps.yaml` and the `change_1` impact expectations. After the fix, `change_1` should correctly make the **occlusion sFMEA block** stale, which strengthens the demo.
  - Re-run the validator, goldens and the change regression.

Resolved in 212e688: controls, requirement/component/unit annotations and PR links follow actual functions; exact answer key and native watch/redline regression pass. Occlusion HAZ-04 is stale under change_1.
- *Reviewer verified at 212e688:* hazards now map by meaning: occlusion → RC-04 "Sustained-pressure occlusion detection with latched critical alarm" ← SRS-012/021/022; air → SRS-008; drug → SRS-018–020; audit → SRS-024/025/033; restart → SRS-029/030. RC-12 stays unrealised (G06). The answer key is exact (413 links).

### M8 (tag `m8-done`, de780a7; R-033 in fd91a5c) — verdict: **approved; R-036 must be fixed before M10**

Verified independently in a clean worktree:
- 59 tests pass; ruff is clean.
- `generate sfmea` produced 27 sections, `generate drr --input-file …` 9 sections and `propose` 42 checks, all with 0 validation events.
- **sFMEA governance is correct:**
  - Severity is copied only from the risk file.
  - All AI cells are `[Suggested]` with confidence.
  - Residual risk is "Human assessment required".
  - A regression rejects risk-rating text in AI cells.
  - Gaps F01–F03 are listed.
- **The DRR invents nothing:** identity comes exactly from `review_input.json`, and discussion, decisions, new actions and approvals are human placeholders.
- G12 for SOUP is added (`rules: 12`), and the answer key is still exact.
- Content problems: R-036 (blocking before M10) and R-037–R-039.


**R-013 [non-blocking, by M10] M2 — Test-case steps are one template repeated across all cases** (`data/synthetic/evidence.yaml`, test_case entries)
- Every case has the same four generic steps ("exercise … with nominal input; challenge its boundary; repeat with invalid input"), and titles end in "— case 0NN".
- That's acceptable for the SSTR tables. The demo will open a few cases, though, so give 5–6 safety-critical cases specific stimuli and values: TC-021 occlusion, the air-in-line case, the over-infusion bound, the alarm latch/acknowledge case and the drug-limit case.
- Keep IDs and links unchanged.

Resolved in b82108b: six safety-critical cases have distinct stimuli/boundaries/recovery steps; IDs and links retained and exact dataset validation passes.
- *Reviewer verified at m8-done:* TC-021 is now titled "Verify occlusion threshold" and safety cases carry explicit stimuli.

**R-031 [non-blocking, by M10] M6 — SAD and SDD readability** (`specs/documents/sad.yaml`, `sdd.yaml`, `specs/templates/section.md.j2`)
- **Headings.** The SDD has 162 flat H2 headings ("Purpose — UNIT-x", "Behavior — UNIT-x"…). Use one H2 per unit with H3 subsections, so the Word navigation pane and table of contents stay usable. Do the same for SAD component sections.
- **Data-structure table.** Each cell is a key-sorted blob ("bases: StrEnum; fields: …; name: PressureState"). Use columns: Name | Kind/bases | Fields.
- **IDs without names.** The risk-control and SOUP tables show bare IDs (`HAZ-01`, `RC-01`). Add title columns (hazard name, control name) so a reviewer can read them without clicking through.
- **Missing SOUP requirements.** Every SOUP row says "Recorded requirements: —". Make that a finding rather than a silent dash: add a gap rule, e.g. **G12 "SOUP item has no recorded functional/performance requirements or anomaly-list evaluation"** (IEC 62304 §5.3.3–5.3.4, §7.1.3), and render it in "Open design and verification gaps".

Resolved in b82108b: H2 entity groups/H3 subsections, structured data columns, hazard/control names and G12 SOUP gaps appear in the design documents; golden/coverage tests pass.
- *Reviewer verified at m8-done:* the SDD now has 22 H2 and 160 H3 headings, structure tables have columns, and risk tables include names. *Minor:* the sFMEA controls cell still renders as an "id: …; title: …" blob.

**R-033 [non-blocking, before M8] M6 — SAD synthesis sections just restate component boilerplate** (`data/synthetic/evidence.yaml` components, `src/dhf/graph/design.py`, `specs/prompts/design.*.md`)
- `architecture_overview`, `component_responsibility.*` and `runtime` mostly repeat one sentence per component: "owns X, exposes explicit inputs and outputs, reports faults to the control path, must retain validated state…".
- The cause is the data and the evidence pack, not the model:
  - (a) All six component bodies in the dataset are the same templated three sentences.
  - (b) The architecture packs carry no structural facts: which units belong to which component, which component calls which, the interfaces, and the ADRs and hazards per component.
- **Expected fix:**
  - Give each component a distinct responsibility, collaborators, safety mechanisms and interfaces, in both the dataset and `architecture.yaml`.
  - **Extract inter-component dependencies from the code deterministically**, via AST imports and calls, e.g. `COMP-03 → COMP-04: sensor_pressure requests alarm_latch.latch()`. Feed them into the overview and runtime packs, and draw them in the R-030 diagram.
  - Make the SDD purpose, behavior and errors prompts distinct (why/what · algorithm · invalid input/recovery). In the live sample, all three repeated the dwell-latch explanation.

Resolved in fd91a5c: distinct component records feed architecture.yaml; AST resolves the pressure-to-alarm latch call; bounded structural facts, ADRs and traced hazard/control context feed design synthesis. Unit purpose/behavior/errors prompts have distinct v2 instructions.
- *Reviewer verified at m8-done:* SAD packs now carry `hazard_controls`, `unit_allocation` and dependency facts. The hazard–control facts inherit the R-036 data error.

**R-035 [non-blocking, by M10 — demo readability] M7 — "Possibly affected" is noisy: changing one unit flags every sibling unit's sections** (`src/dhf/impact/__init__.py`)
- After `change_1`, SDD reports **12 stale and 21 possibly affected** sections. All 21 belong to `UNIT-sensor_air`, `sensor_calibration` and `sensor_filter`, reached one hop through `COMP-03`. A reviewer has to clear 21 review flags for code that didn't change.
- **Expected fix:**
  - Don't propagate one-hop impact through a **component** node into sibling units' narrative sections. Keep one-hop along requirement ↔ unit/test/control links.
  - Or collapse siblings in the report: "possibly affected: 3 sibling units of COMP-03 — review optional".
  - Put a per-document summary (stale / possibly affected counts) at the top of `out/impact.md`. The demo will show this report.


Resolved in b82108b: impact Markdown starts with document counts and collapses sibling subsection flags into three optional unit groups; these do not block readiness.
- *Reviewer verified at m8-done:* `impact.md` starts with per-document counts, and sibling units are grouped as optional.

### M7 (tag `m7-done` → 3bde3d8; code at e42e8cb) — verdict: **approved**

Verified independently by running the demo flow end to end on the mock ADO in a clean worktree:
- 55 tests pass; ruff is clean.
- Steps: generate SSTR, SAD and SDD → `apply-scenario change_1` → re-ingest (3 added, 2 changed) → `dhf impact --since 1` → `dhf regenerate --stale`.
- **Impact:** SAD 6 stale / 3 possibly affected; SDD 12 / 21; SSTR 9 / 0. **Every section lists its causing artifact and reason** (`cited_revision_changed`, `query_facts_changed`, `one_hop_neighbor via COMP-03`). That's strong, explainable evidence for the demo.
- **Selective regeneration:** only stale sections were regenerated. Section-level diff against v1:
  - SSTR: 7 changed.
  - SAD: 4 changed.
  - SDD: 10 changed, all inside the `sensor_pressure` unit plus allocation rows that show SRS-021's revision.
  - All other sections are **byte-identical**.
  - Stale sections that rendered identically, such as the diagram and risk-control table, are conservative flags, not errors.
- **Consistency now catches the planted stale baseline:** C01 (`sad-v1` misses COMP-06) and C04 (`sad-v1` names COMP-03 "Pressure Monitoring"). Fresh documents pass.
- The expanded `generate-section` works.
- `dhf watch --cycles 1` reports "Evidence unchanged" on a stable graph.
- *Note on R-012:* the expected-impact fixture is annotated with causing artifacts, and I audited it against the impact rule; each stale entry is justified. It's still derived from the implementation's output, though. In M10, call the impact metric "regression against a reviewer-audited expectation", not independent accuracy.

**R-012 [non-blocking, revisit in M7] M1 — Expected impacted sections in `change_1` are guesses** (`data/synthetic/scenarios/change_1.yaml`)
- For example, SAD `interfaces` and `architecture` are listed for a threshold change in one unit.
- In M7, derive the expected list from the impact rule (sections whose cited revisions include a changed artifact, plus labelled 1-hop "possibly affected"). Annotate each expected section with the artifact that makes it stale, so the impact precision/recall metric is honest.

Resolved in e42e8cb: frozen section/status/cause expectations distinguish cited changes, query-fact changes and one-hop possible impact; watch regression checks exact membership.
- *Reviewer verified at e42e8cb.*

**R-032 [non-blocking — required in M7] M6 — The consistency check can't find the planted stale-SAD issues** (`src/dhf/trace/consistency.py`)
- `dhf consistency` reports 0 findings because `component_consistency` only compares the graph with **freshly generated** documents, which are consistent by construction.
- The planted stale-documentation issues sit in the **approved baseline**: C01, where COMP-06 is missing from SAD v1.0, and C04, where SAD v1.0 calls COMP-03 "Pressure Monitoring". These are in `expected_gaps.yaml` but are never detected.
- **Expected fix (M7):**
  - Run C01–C04 against the latest approved baseline of each document in the docs repo (tag `sad-v1`, later `<doc>-vN`), as well as the generated drafts.
  - Score them against the C entries in `expected_gaps.yaml`, alongside G01–G11.
  - This is the "stale documentation" problem from the brief, so it needs to show up in the demo.

Resolved in e42e8cb: all four consistency checks inspect current drafts and latest approved docs-repo tags; sad-v1 emits C01/COMP-06 and C04/COMP-03. Evaluation scoring follows in M10.
- *Reviewer verified at e42e8cb.*

**R-034 [non-blocking] M6 — `dhf generate-section` can't target expanded sections** (`src/dhf/cli.py:220-245`)
- `dhf generate-section sdd purpose.UNIT-sensor_pressure` and `sad component_responsibility.COMP-03` fail with "Unknown section", because the lookup uses `spec["sections"]` instead of `expand_sections(spec, graph)`.
- That breaks the owner-facing cross-provider check for every per-component and per-unit section. Look the section up after expansion.


Resolved in e42e8cb: generate-section resolves IDs after graph-driven expansion.
- *Reviewer verified at e42e8cb.*

### M6 (tag `m6-done` → c98915a; code at 6922f61) — verdict: **approved**

Verified independently in a clean worktree:
- 53 tests pass; ruff check and format are clean.
- `dhf generate sad` produced 28 sections and `dhf generate sdd` 162 sections, both with 0 validation events.
- The SAD follows BRIEF §10.2: context, safety classes from source, allocation diagram, per-component design plus allocated requirements, extracted interfaces, SOUP inventory with parsed pinned versions, risk-control measures with source severities, requirements-to-architecture matrix, ADRs and open gaps.
- The SDD extracts signatures and data structures deterministically through AST, for example the `PressureMonitor` interfaces and the `PressureState`/`PressureSample`/`PressureDecision` structures. Per-unit allocations are deterministic. The absence of unit-level tests is stated honestly.
- All 6 components and 20 units appear.
- The AI narrative sections were checked structurally only. With the mock, Purpose, Behavior and Error handling repeat the same text, so prose quality still needs a live sample.
- Follow-ups: R-030, R-031, R-032.

**R-018 [non-blocking, by M10] M4 — The dataset text gives away the answer key** (`data/synthetic/evidence.yaml:1976`, `data/synthetic/code/kestrel/diagnostics_orphan.py`)
- BUG-03's body says "residual-anomaly listing is intentionally missing", and a unit is named `diagnostics_orphan`. Both appear in generated documents the judges will read.
- Rewrite them as natural engineering text and rename the module (e.g. `diagnostics_trace.py`). Update the answer key and IDs consistently, and re-run the validator.

Resolved in 6922f61: natural BUG-03 wording and diagnostics_trace naming retain exact graph/answer-key parity.
- *Reviewer verified at 6922f61.*

**R-029 [non-blocking, before M10 demo script] M5 — The anomaly section's completeness depends on the model; offline, the demo's new failure is missing** (`specs/documents/sstr.yaml` anomaly_assessment, `src/dhf/llm/adapters/mock.py`)
- After `change_1`, release 1.1 has two failures: `RES-2-008` and `RES-3-021` (the occlusion test, with no linked defect). The query facts list both correctly.
- With the mock adapter, though, "Failed tests and anomaly assessment" only discusses TC-008/BUG-01, because the mock emits the first three evidence bodies. So the offline `scripts/demo.sh` won't show the key new failure there.
- **Expected fix:**
  - Open the section with a **deterministic table of every failed or blocked result**: result, test case, requirement, linked defect, or "none — see G05". Completeness then never depends on the model, and the AI narrative follows the table.
  - Also make the mock produce one claim per `facts.failed_results` entry, so the offline narrative is representative.

Resolved in 6922f61: all failed/blocked results render in a deterministic table even on AI failure; mock claims cover both change_1 failures and the regression verifies them.
- *Reviewer verified at 6922f61.*

### M5 re-review (tag `m5-done` → 0b01407; fixes in 18ee5e8) — verdict: **approved**

I re-ran the identical end-to-end scenario on the mock ADO in a clean worktree:
- 52 tests pass; ruff check and format are clean.
- Steps: generate v1 → `apply-scenario change_1` → re-ingest (3 added, 2 changed) → regenerate v2 → `render_docx(v2, baseline=v1)`.
- **Redline: 46/737 paragraphs and 15/175 rows changed**, down from 1,376/1,401 and 342/344. Every changed row is a real change:
  - SRS-021 r1 → r2.
  - RUN-3 and RES-3-021 added.
  - Results summary 39/1 → 38/2.
  - TC-021 Passed → Failed.
  - A new G11 finding for TC-021.
  - The eight requirement rows that list `UNIT-sensor_pressure` change, now visibly, because unit revisions show as `UNIT-…@<sha>`.
- 30 insertions, 16 deletions, **7 comments** (previously 377).
- After the change, **no `ai_unavailable` sections**; the conclusion regenerates under the 12k synthesis budget.
- `dhf gaps` correctly adds G05 for RES-3-021 and G11 for TC-021, giving 18 findings in total.

**R-025 [blocking — fix before more M6 work; M7 builds on it] M5 — The redline marks almost the whole document as changed** (`src/dhf/render/__init__.py:21-68`)
- The change touched one requirement (SRS-021 r1→r2), one unit, one new PR and one failed run. The rendered redline had **694 insertions and 682 deletions, with 342 of 344 table rows and 1,376 of 1,401 paragraphs marked as changed**.
- A reviewer would see the entire SSTR struck through and re-inserted. That defeats the "change tracking for human review" must-have and the AB1 demo moment.
- Likely causes:
  - (a) Tables are diffed as whole blocks, so one changed row redlines the whole table.
  - (b) A row whose only change is a hyperlink target (e.g. `UNIT-sensor_pressure` link `version=GC6d75a2b…` → `GCc1ee4f6…`) counts as changed although its visible text is identical.
- **Expected fix:**
  - Diff tables **row by row** (and cell by cell where practical), keyed by the row's first-column ID.
  - Diff paragraphs by visible text. A link-target-only change gets no tracked change, or a single small one on the revision marker.
  - Show unit and code revisions visibly (`UNIT-sensor_pressure@c1ee4f6`) so real changes are readable.
  - Add a regression test that runs this exact scenario (generate → `change_1` → regenerate → redline) and asserts the changes are confined to the expected rows and sections: SRS-021 rows, RUN-3/RES-3-021, results summary 39/1 → 38/2, and the AI sections whose evidence changed. Use a small threshold, e.g. < 10% of paragraphs.

Resolved in 18ee5e8: visible-text paragraph matching and source-keyed row/cell diffs; Git revisions are displayed. Exact change_1 HTTP regression confines edits to 46/744 paragraphs and 15/175 rows (under 10%), with 30 insertions/16 deletions; target-only link updates have no redline. All 12 local-render pages checked, including visible tracked hyperlinks.

**R-026 [blocking — fix before more M6 work] M5 — The conclusion fails as soon as evidence grows: bytes are compared against a token budget** (`src/dhf/generate/__init__.py:186-193,215-220`)
- `budget = prompt["max_input_tokens"] - len(prompt["body"].encode())`, which is then compared with `len(canonical(model_pack).encode())`. A "6000-token" budget is really about 6,000 **bytes** (≈1,500 tokens).
- After `change_1`, the release-1.1 `release_conclusion` pack exceeds it. That raises `ValueError("Synthesis evidence exceeds its single-call budget")`, which is caught as the generic `invalid_output_or_budget`, so the conclusion renders "AI drafting unavailable" **even with the mock provider**, on the main demo path.
- The same bug caused the earlier over-chunking: 13 calls and 85 claims for the conclusion in the live check.
- **Expected fix:**
  - Use one unit consistently. Estimate tokens conservatively (e.g. bytes ÷ 3) against `max_input_tokens`, or rename the setting to `max_input_bytes`.
  - Raise synthesis budgets to about 12k tokens. That's still well under $0.01 per call on Haiku 5.5 or gpt-4.1-mini.
  - When a synthesis pack is still too large, **reduce it deterministically**: keep failed and blocked results, open defects, residual anomalies and gap facts, and summarise the rest as counts in `facts`. Don't fail.
  - Split the generic error into separate reasons (`evidence_over_budget`, `invalid_output`, `budget_exceeded`) and record the internal message in the manifest. These messages contain no secrets.
  - Add a regression test: after `change_1`, regenerating the SSTR with the mock provider produces **no `ai_unavailable` sections**.

Resolved in 18ee5e8: consistent token estimates (ceil bytes/3), 12k synthesis budgets, deterministic context counts and critical narrative excerpts with audit metadata. Distinct evidence_over_budget/invalid_output/budget_exceeded reasons include safe internal messages. change_1 regeneration has zero ai_unavailable sections; summary changes 39/1 to 38/2. 52 tests pass; ruff clean.

**R-027 [non-blocking, before M7] M5 — The fresh DOCX has 377 Word comments, one per citation** (`src/dhf/render/__init__.py`)
- That floods Word's comment pane and hides the comments reviewers actually need to act on.
- Citations are already hyperlinks (507 of them). Keep comments for review-relevant items only: `[Inferred]` (basis and confidence), `[Suggested — review required]`, `ai_unavailable` and human placeholders.

Resolved in 18ee5e8: comments restricted to inferred/suggested/manual review items; source citations remain hyperlinks. Inferred comments include basis/confidence. The scenario redline has seven comments; regression proves sourced citations create none.

**R-028 [non-blocking] M5 — A conclusion-only instruction was pasted into every prompt's shared footer** (`specs/prompts/sstr.*.md:15`)
- All four SSTR prompts end with "For a conclusion, discuss only verification outcomes, unresolved anomalies and coverage gaps…". In the purpose, anomaly and residual prompts it misdirects the model.
- Keep the shared footer generic, move section-specific instructions into each prompt body, and bump the prompt versions so the cache invalidates.

Resolved in 18ee5e8: conclusion-only instructions moved to the conclusion body; shared footer is generic. All four SSTR prompts bumped to version 2 and document prompt references updated.

### Pre-M6 fixes (resolved in 4c29a5f, checked during the M5 review)

- *Reviewer verified:*
  - Tables link IDs to sources with readable labels.
  - The evidence walls are gone.
  - Claim caps and synthesis prompts are present.
  - Provider errors print as one sanitised line (`provider, section, reason, http, type, request`).
  - URL-citation normalisation emits `normalized` audit events.
- *Caveat:* R-016's bounded single-call synthesis is defeated by the byte/token mix-up in R-026.

**R-016 [non-blocking, before M6] M4 — AI-section evidence packs are too broad, so the conclusion becomes a list of 30 "suggestions"** (`src/dhf/graph/queries.py:93-101`)
- `release_readiness_facts` puts every failed result **plus all 35 software requirements** into the pack, and referenced components get pulled in too.
- With the mock, the conclusion renders as about 30 `[Suggested]` paragraphs restating requirements. With a real model it costs more and still invites a restatement instead of a conclusion.
- **Expected fix:**
  - Scope each AI query to the evidence the section reasons about. For the conclusion: failed and blocked results, linked defects, open residual anomalies and G-rule findings (as facts), plus coverage.
  - Add `max_claims` to section specs (conclusion 5–6, purpose 3–4), enforced by the validator. Drop the excess and log it in the manifest.
  - Tell prompts to synthesise one claim per point rather than restate each evidence item.

Resolved in 4c29a5f: scoped readiness evidence, deterministic gap/coverage facts, global claim caps and synthesis prompts.

**R-017 [non-blocking, before M6 — every document reuses this renderer] M4 — Generated documents are hard for a human reviewer to read** (`specs/templates/section.md.j2`, `src/dhf/generate/__init__.py`)
- **Evidence wall.** Every deterministic section ends with an "Evidence:" line of 40+ links; `references` has 42. Link IDs inside the table cells instead, as `rtm.md` already does, and drop the trailing wall. The manifest keeps the complete list.
- **Unreadable revisions.** Git-sourced artifacts render as `COMP-01@r14fb1b4f…` (a 64-hex hash). Show a short commit SHA or hash (7–8 characters) and keep the full value in the manifest.
- **Raw column names.** Headers are dict keys (`not_run`, `artifact_id`, `source_url`). Add a `columns:` label mapping to each section in the spec.
- **Plain-text URLs.** `verification_gaps` shows `source_url` as a text column. Link the artifact ID instead.
- **"References" isn't references.** That section lists requirements, not controlled documents. Either rename it "Requirements baseline under test", or make it a real references table: SRS baseline, RTM version, test runs, and SAD/SDD versions once they exist.

Resolved in 4c29a5f: linked table IDs, spec column labels, short displayed revisions, renamed baseline section and no evidence walls; 11-page local render visually checked.

**R-021 [non-blocking, before M6] M4 — The validator's ID regex rejects good claims, and chunking prevents cross-chunk citations** (`src/dhf/generate/validator.py:8-10`, `src/dhf/generate/__init__.py` chunking)
- The live conclusion run had 26 claims rejected as `unknown_ids`, mostly for `SRS-to-test` and `SRS-to-code`. Those are the model's wording for the coverage facts; the pattern treats any `SRS-<anything>` as an ID.
- `RUN-2` was also rejected because the conclusion was split across about 13 chunked calls, so `RUN-2` wasn't in that chunk's evidence.
- **Expected fix:**
  - Count a token as an ID only if it matches a real ID shape (`(UN|SYS|SRS|HAZ|RC|COMP|TC|BUG|PR|RUN|RES|ACT|REV|ADR|SOUP)-\d[\w.-]*` or `UNIT-[a-z_]+`) or exists in the graph.
  - Avoid chunking for synthesis sections (conclusion, purpose). R-016's scoped packs make them fit in one call.

Resolved in 4c29a5f: numeric artifact-ID shapes avoid coverage false positives; purpose/conclusion each use one bounded call.

**R-022 [non-blocking, before M6] M4 — Real-model prose reads like a data dump, not a document** (`specs/prompts/*.md`, evidence-pack construction)
- Live samples:
  - "The evidence pack contains six synthetic user needs…"
  - Six near-identical claims, one per user need.
  - "BUG-01 is recorded with … residual_listed true."
- The anomaly assessment was accurate and well cited, though; the content is right, the voice is wrong.
- **Expected fix:**
  - Prompts tell the model to write as the document itself. No references to "the evidence pack", "synthetic" or field names.
  - Merge related points into one claim with several citations.
  - Present attributes to the model with human labels ("Listed as residual anomaly: yes"; "Severity: 4 (serious)") instead of raw keys.
  - Put one good example claim per section type in the prompt.
- Related: with chunking, the conclusion produced **85 claims across ~13 calls** and accounted for ~90% of the live spend, which is more evidence for R-016.

Resolved in 4c29a5f: document-voice instructions, per-section examples, merged-point guidance and human-labelled properties; guarded live Mini check reviewed.

**R-023 [non-blocking] M4 — Provider errors are printed raw, and the ledger token counts are overwritten instead of summed** (`src/dhf/cli.py`, `src/dhf/llm/__init__.py`)
- An `invalid_api_key` from OpenAI printed the full provider error, including a masked key fragment, inside a rich traceback.
  - Catch provider SDK errors at the CLI boundary.
  - Print one sanitised line (provider, HTTP status, error type, request id) with no echo of the key.
  - Show the full traceback only with `--debug`.
- After 18 calls, `ledger.json` showed `input_tokens: 2250, output_tokens: 992`. Those are only the last call's numbers, while `actual_usd` was accumulated. Sum the token counts too.

Resolved in 4c29a5f: SDK errors become sanitized CLI metadata; debug excludes provider messages; ledger token counters accumulate across calls.

**R-024 [non-blocking, before M6] M4 — The OpenAI path works but its output is weak; citation handling and model choice need adjusting** (live check with the owner's new key; spend $0.0003)
- **What works.** Authentication is good, and `gpt-4.1-nano`, `gpt-4.1-mini` and `gpt-4o-mini` are available. OpenAI accepts the strict claims schema unchanged, so R-019 affects Anthropic only.
- **Problem 1: the model cites URLs instead of IDs.** For `anomaly_assessment`, nano returned one claim citing `fixture://RES-2-008`, the source **URL**, so the validator correctly rejected it and 0 claims survived.
  - Before validating, normalise a citation that exactly equals an evidence item's `source.url` to that item's ID. Log the normalisation.
  - Tell prompts to "cite IDs such as RES-2-008, never URLs".
  - Consider leaving URLs out of the pack the model sees; the renderer adds links afterwards.
- **Problem 2: the output is thin.** Each section got one terse claim. The anomaly claim stated an inferred defect link as `sourced` and cited only the result. R-022's prompt changes and examples apply here too.
- **Problem 3: the default model is too weak.** Copilot Studio runs larger GPT-4.1/GPT-5-class models, so nano is a poor stand-in. Set `DHF_MODEL_OPENAI=gpt-4.1-mini` as the OpenAI dev default, update its price variables from OpenAI's pricing page, and keep nano as an optional cheap smoke test.

Resolved in 4c29a5f: unique exact source URLs normalize to IDs with audit events; prompt inputs omit URLs; Mini defaults/prices verified; explicit defect-link facts prevent false missing-link prose.

### Live-check blockers (fixed in adfd507, recorded in 79d44fe) — verdict: **approved**

**R-019 [blocking] M4 — Every live Anthropic call fails with HTTP 400 because of the schema** (`src/dhf/models/__init__.py:25-34`)
- `dhf generate sstr --provider anthropic` returned: `output_config.format.schema: For 'number' type, properties maximum, minimum are not supported`.
- The cause is `confidence`'s `ge=0, le=1` bounds, which pydantic writes into the JSON schema.
- **Expected fix:** `strict_claims_schema()` (or a provider-specific variant) recursively strips `minimum`, `maximum`, `exclusiveMinimum` and `exclusiveMaximum` from the schema it sends to providers. Pydantic still enforces 0–1 on the response.
- The reviewer confirmed this fix works in the scratch copy: with the bounds stripped, Anthropic calls succeed.
- Add a unit test asserting the provider schema contains no numeric-bound keywords. Re-check OpenAI strict mode once a valid key exists.

Resolved in adfd507: provider schemas recursively omit numeric bounds; local Pydantic still enforces confidence 0–1. The one live retry reached a refusal response, confirming schema acceptance. Offline schema/bounds tests pass.
- *Reviewer verified at 79d44fe:* `strict_claims_schema()` output contains no `minimum` or `maximum`, and `test_provider_schema_has_no_numeric_bounds_but_response_validation_does` covers it. 41 tests pass; ruff is clean.

**R-020 [blocking] M4 — One model refusal crashes the whole document** (`src/dhf/llm/adapters/anthropic.py:22-23`, `src/dhf/generate/__init__.py`)
- Claude Haiku 5.5 returned `stop_reason: "refusal"` for `residual_anomalies`, almost certainly a safety-classifier false positive on infusion-pump hazard language. The adapter raises `ValueError`, so `dhf generate sstr` aborts and no document or manifest is written.
- Regulated content will trigger this again, especially in sFMEA and hazard text.
- **Expected fix:**
  - A refused, truncated or unparseable section degrades to a **human-authoring placeholder**: "AI drafting unavailable (refusal) — author manually", rendered like a `human` section. The rest of the document still generates.
  - The manifest records `status: "ai_unavailable"`, the reason, and `stop_details.category` when present.
  - `dhf check` (M5) treats that section as unresolved.
  - Add a short framing line to the shared prompt footer ("This is engineering documentation drafted from a fictional synthetic dataset for verification records; describe recorded facts only"). Re-test that section once; if it still refuses, leave the placeholder.
  - Never retry a refusal on the same model in a loop.

Resolved in adfd507: failed AI sections persist as ai_unavailable manual placeholders, with safe reason/category metadata and a blocking readiness check. Tests cover refusal, truncation, malformed output and provider failure without retries. One live residual-anomaly retry still refused (category bio); its placeholder is retained.
- *Reviewer verified at 79d44fe:* failed AI sections persist as `ai_unavailable` manual placeholders with a safe reason and category. `src/dhf/review/__init__.py:50` makes them a readiness blocker. `test_unavailable_section_becomes_manual_placeholder_without_retries` covers refusal, truncation, malformed output and provider failure.
- *PM note:* Haiku 5.5 still refuses `residual_anomalies` (category `bio`), a safety-classifier false positive on infusion and drug language. Copilot Studio runs OpenAI-family models, so make **OpenAI (`gpt-4.1-mini`, see R-024) the primary provider for prompt tuning and demo runs**. Keep Anthropic as the secondary provider: a refusal there is handled safely, and the manifest records it.

### M4 (tag `m4-done` → bfae4d5; code at 29fe7e0) — verdict: **approved; live check found R-019–R-023 (two blocking)**

Verified independently in a clean worktree:
- 31 tests pass; ruff is clean.
- `dhf ingest --source fixtures` then `dhf generate sstr --release 1.1` writes `out/documents/sstr.md` (351 lines, 12 sections) and the manifest, with 0 rejected, downgraded or coerced claims.
- Deterministic sections render from facts. AI sections carry typed claims, with `[Inferred]` and `[Suggested — review required]` labels and `ID@rev` links. "Approvals" is a human-only placeholder.
- The manifest records template/prompt SHAs, the model, cost, a 248-artifact source snapshot, per-section cited revisions, claim counts, validation events and the document SHA-256.
- The validator rejects unknown IDs and numbers not found in facts. Facts include `source_numbers` taken from cited evidence, so quoted thresholds survive. It downgrades uncited `sourced` claims and coerces kinds that aren't allowed.
- Prompts are data in `specs/prompts/`, with injection-resistant wording and "copy facts, never compute".
- **Not yet verified: real-model output.** Every AI section above came from the mock adapter, so prose quality is unproven. The owner-run live check in PROGRESS is still pending.
- Follow-ups: R-016, R-017, R-018.

**R-014 [non-blocking] M3 — RTM and gap reports were bare.**
- Resolved in 29fe7e0.
- *Reviewer verified:* `rtm.md` now has Rev and Units columns with linked IDs; `gaps.md` has per-rule counts and actions from YAML.

**R-015 [non-blocking] M3 — `dhf ingest` printed every artifact ID.**
- Resolved in 29fe7e0.
- *Reviewer verified:* it prints per-type counts.

### M3 (tag `m3-done`, eb0f00c) — verdict: **approved**

Verified independently in a clean worktree of `m3-done`:
- 28 tests pass; ruff check and format are clean.
- `dhf ingest --source fixtures`, then `dhf gaps` and `dhf rtm`, ran successfully, producing 16 findings and 35 RTM rows.
- The findings match the answer key exactly (G01–G11): precision = recall = 1.0.
- The rules are declarative (`missing_link`, `match`, `outdated_verification` in `specs/rules/gaps.yaml`), and only `explicit` and `human_confirmed` links count, per BRIEF §4.
- G11 compares the requirement's latest revision time with the last passing result's `completedDate`, using native history rather than metadata. Every finding carries `source_url` and `revision`.
- Presentation follow-ups: R-014 and R-015.

### M2 (tag `m2-done` → cfed7c3) — verdict: **approved**

Verified independently in a clean worktree of the re-tagged `m2-done`:
- 25 tests pass; ruff check and format are clean.
- `test_metadata_stripped_equivalent_graph` removes every `DHF-META` blob from work items, runs and results, re-ingests, and asserts the semantic graph is identical. It also checks that SRS-021's component, the "80 kPa" acceptance criterion and HAZ-01's severity of 5 still come through.
- In `src/`, the metadata blob is read only for the `synthetic` marker (`src/dhf/ingest/native.py:8-16`), as required.

**R-009 [blocking] M1/M2 — The product only worked against our mock, by parsing mock-only metadata.**
- Resolved in b74d84b: native fields and revision history, AreaPath, severity, acceptance criteria, residual-anomaly tags, native result fields, and Related-link types inferred from endpoint types. Unit traces come from `# Implements:` annotations. `verified_revision` is removed.
- *Reviewer verified:* the stripped-metadata equivalence test passes, and `src/` doesn't read the blob beyond the synthetic marker.

**R-010 [blocking] M1 — The synthetic dataset was too thin and unrealistic.**
- Resolved in b74d84b.
- *Reviewer verified, by spot check:*
  - Hazard severities now follow clinical harm (over-infusion, air delivery, alarm unavailable and unintended restart are 5; lost audit evidence is 3), with a scale in `risk_file.md`.
  - SRS-021 has a what/why body and measurable acceptance criteria (80 kPa, 3 s dwell, exact-boundary behaviour).
  - BUG-01 has a description, impact assessment, severity and state.
  - ADR-01 has context, decision and consequences.
  - `sad_v1.md` is now 32 lines.
  - `sensor_pressure.py` has state enums, dataclasses and validation, and carries an `# Implements:` trace header.
  - Follow-up: R-013.

**R-011 [non-blocking] M1 — Mock REST details differed from real ADO.**
- Resolved in b74d84b: `/revisions/N`, `$expand` honoured, public PR shape, 404 for unknown run/PR. All contract-tested.

### M0–M1

**R-001 [blocking] M0 — The cache key could collide and ignored prompt text.**
- Resolved in 9cbfcc0. *Reviewer verified.*

**R-002 [blocking] M0 — Tests read the developer's real `.env` and weren't blocked from the network.**
- Resolved in 9cbfcc0. *Reviewer verified.*

**R-003 [non-blocking] M0 — Anthropic adapter.**
- Resolved in 688a1c3. *Reviewer verified at `m1-done`.*
- *Minor:* `LLM.generate` still defaults `max_output_tokens=1000`. Raise it to about 4000 for Anthropic, because thinking counts toward the cap.

**R-004 [non-blocking] M0 — OpenAI adapter.**
- Resolved in 688a1c3. *Reviewer verified.*

**R-005 [non-blocking] M0 — The ledger only recorded reservations.**
- Resolved in 688a1c3.

**R-006 [non-blocking] M0 — An empty evidence pack blocked real-provider calls.**
- Resolved in 688a1c3.

**R-007 [non-blocking] M0 — PROGRESS.md was stale.**
- Resolved in 9cbfcc0.

**R-008 [non-blocking] M0 — The adapters couldn't see the API keys.**
- Resolved in 4064754. *Reviewer verified.*
