# Review Log

Written by Claude (PM and reviewer). Codex reads this file at the start of every milestone.

**Item format:** `R-NNN [blocking|non-blocking] M<N> — finding (file:line) — expected fix`

**Codex:**
- Fix every `[blocking]` item before starting new work.
- Append `Resolved in <sha>: <note>` under each item you fix.
- Don't edit or delete the reviewer's text.
- If you disagree with an item, write your reasoning under it.

## Open

**R-030 [non-blocking, by M10 — demo impact] M6 — The architecture diagram is Mermaid source only, so the Word SAD shows a code listing, not a diagram** (`out/documents/sad.architecture.mmd`, SAD `architecture` section)
- No local Mermaid or Graphviz renderer exists, so the DOCX gets a monospace block of `flowchart LR …`. A rendered architecture figure is one of the most visible parts of a SAD for reviewers and judges.
- **Expected fix:**
  - Render a PNG locally and deterministically: components as columns or boxes, their units listed inside or below, external interfaces at the edge. Pillow is enough for a grid layout; record the dependency in an ADR.
  - Embed the PNG in the DOCX with a caption and a figure number.
  - Keep the Mermaid source in the Markdown (ADO's markdown preview can render it) and the checksum in the manifest.
  - Never use an online renderer.

### M8 review (tag `m8-done`, de780a7) — verdict: **approved with one blocking-before-M10 data fix**

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

**R-038 [non-blocking] M8 — DRR pre-review findings skip the most review-relevant items** (`specs/documents/drr.yaml`, `src/dhf/graph/queries.py`)
- The 5-claim cap shows only G01×4 and G02×1. It omits **C01/C04 for the very baseline under review (`sad-v1`)**, G05 (a failed result with no defect) and the risk-control gaps G06/G07.
- **Expected fix:**
  - Start with a deterministic findings table: every rule, with count and links.
  - Order the AI suggestions by safety relevance: stale baseline and risk-control gaps first, then failed tests, then coverage.
  - The empty "Changed evidence since baseline" section should say "No changes since sad-v1 (snapshot 1)" instead of rendering blank.
  - ACT-01–04 descriptions are placeholders ("Review action N"); give them real content.

Resolved in 450b11d: Complete deterministic G/C/F findings table, approved-baseline C01/C04 inputs, safety-first suggestions, named empty-diff notice and specific prior actions.

**R-039 [non-blocking] M8 — L01 produces 35 identical "review whether…" proposals** (`src/dhf/cli.py` propose, `specs/prompts`)
- The planted SRS-034/035 (not implemented) look the same as the implemented requirements, so the proposals file is noise.
- **Expected fix:**
  - Pre-screen deterministically: G02 requirements are reported as "no implementing change" without the LLM.
  - Send only requirements *with* linked code to the model, comparing acceptance criteria to the unit code.
  - Emit a proposal only when a likely gap is found, with its confidence.


## Resolved

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

Resolved in 450b11d: G02 is pre-screened without model calls; linked code is compared to criteria, agreement emits no proposal, and the fixture flags the missing checksum guard with confidence.

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
