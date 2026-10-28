# Kestrel DHF Automation — a simple local guide

Updated 28 October 2026. These instructions are for the existing project on your Mac.

## 1. What is the project goal?

**Help software teams create evidence-backed documentation, find missing evidence, and update the right document sections when engineering work changes.**

Imagine a team building software for an infusion pump. A requirement says that the pump must detect blocked tubing, stop delivery and raise an alarm. The team needs to show which code implements that requirement, which test checks it, and what the test result was.

Today, requirements, code, tests, bugs and risk records can be spread across different places. People manually collect that information into documents. It takes time, connections may be missing, and the documents can become outdated.

A **DHF**, or **Design History File**, is the collection of records explaining a product's design and development. Our project helps prepare and maintain those records for human review.

**Kestrel is a fictional pump project used to demonstrate this workflow. We are building the documentation/evidence tool.**

## 2. What have we implemented?

| Feature | What it means in everyday language |
|---|---|
| Evidence collection | Read requirements, code, test results, defects and risk records. The local demonstration uses a simulated Azure DevOps system containing fictional data. |
| Traceability | Follow the recorded connections between a requirement, its implementation, its tests and related risks. Missing connections stay visible. |
| Gap checks | Flag issues such as a requirement without a linked test or a risk control without a linked requirement. A missing link is a finding to investigate. |
| Document generation | Produce Word and Markdown drafts from the evidence, using reusable document templates. |
| Controlled AI drafting | Let AI draft explanations from supplied evidence. Code calculates counts and results. Statements are labelled as sourced, inferred or suggested and checked before rendering. Humans review their meaning and correctness. |
| Change impact | Identify document sections that are outdated after evidence changes, with recorded reasons. Distinguish directly outdated sections from potentially affected sections. |
| Selective updates | Regenerate affected sections while retaining untouched sections. |
| Review workflow | Produce Word tracked changes and document-repository review requests. Human decisions and approvals remain with reviewers. This workflow runs against the local mock in the demonstration. |
| Audit package | Export documents, source snapshots, source/version records and file-integrity checks together in a ZIP. |
| Evaluation and cost controls | Check outputs against the fictional dataset's known answers and record generation time, model usage and budget information. Estimated effort savings are labelled assumptions. |
| Copilot Studio adapter | Implement HTTP and OneDrive exchange methods for company-approved AI drafting. Both are tested offline; actual company sandbox execution is pending. |

The browser workspace has six views:

| View | What to look at |
|---|---|
| Overview | Evidence coverage, test results, documents and work needing attention. |
| Documents | Generated draft sections, their claim labels and source references. |
| Findings | Missing evidence and consistency problems, with recommended actions. |
| Change impact | Outdated or potentially affected sections and the evidence causing each finding. |
| Traceability | Connected evidence, search, source inspection and the complete evidence table. |
| Risk evidence | Recorded hazards, controls, requirements and tests. Human risk assessment remains explicit. |

An **artifact** in the workspace means one record, such as a requirement, code unit, test result or risk control.

These are the document names you will see:

| Name | Meaning |
|---|---|
| SAD — Software Architecture Document | The main software parts and how they fit together. |
| SDD — Software Detailed Design | How individual software parts work. |
| SSTR — Software System Test Report | The system tests and their recorded results. |
| RTM — Requirements Traceability Matrix | A table connecting requirements with implementation and verification evidence. |
| DRR — Design Review Record | Recorded review information, actions and outstanding human inputs. |
| sFMEA — Software Failure Modes and Effects Analysis | A draft organizing possible failures, effects, recorded controls and verification. AI suggestions require human review. |
| SUTR — Software Unit Test Report | A template for explicitly recorded unit-test results. The current demonstration reports their absence rather than presenting system tests as unit tests. |

## 3. Understand the two parts of the project

1. **The browser workspace** lets you explore one saved evidence snapshot. It opens as an HTML file, works offline and is read-only.
2. **The Python engine** collects evidence, runs checks and generates documents. Run it from Terminal when you want a fresh demonstration.

Opening or refreshing the HTML file displays saved results. It does not run document generation. You can explore the prepared demonstration without starting a server or using AI credentials.

## 4. Open the existing demo — easiest option

1. Open **Finder**.
2. Press **Command + Shift + G**.
3. Paste this folder path and press Enter:

   ```text
   /Users/yazhinigopalakrishnan/Desktop/A&C/data/demo/fallback
   ```

4. Double-click **explorer.html**. If necessary, right-click it and choose **Open With → Safari** or your preferred browser.
5. The page should say **Kestrel / DHF workspace**. Start on **Overview**.
6. You should see the recorded updated demonstration with **251 artifacts and seven document drafts**.

Keep these three files in mind:

| File | What it contains |
|---|---|
| `explorer-baseline.html` | Before the recorded change: 248 records, four documents, zero directly stale sections. |
| `explorer-stale.html` | After the recorded change, before regeneration: 251 records, four documents, 40 directly stale sections. |
| `explorer.html` | The saved regenerated demonstration: 251 records, seven documents, zero directly stale sections. |

The baseline and regenerated snapshots come from different stages of the same demonstration. Additional document types are generated as the demonstration proceeds.

You can also open the saved demo from **Terminal** by pasting these two lines:

```sh
cd "/Users/yazhinigopalakrishnan/Desktop/A&C"
open "data/demo/fallback/explorer.html"
```

The quotes around the project path matter because its name contains `&`.

**Open generated demo files under `data/demo/fallback` or `out/`. The file `specs/render/explorer.html` is a source template with no embedded evidence.**

## 5. Open the project folder itself

In Finder, press **Command + Shift + G**, paste the following and press Enter:

```text
/Users/yazhinigopalakrishnan/Desktop/A&C
```

Or use Terminal:

```sh
open "/Users/yazhinigopalakrishnan/Desktop/A&C"
```

Useful folders:

- `docs/`: explanations, the product brief and demo instructions.
- `src/dhf/`: the Python engine's source code.
- `specs/`: document templates, prompts and checking rules.
- `data/demo/fallback/`: prepared demonstration pages and Word files.
- `out/`: generated files from local runs.

## 6. Run a fresh offline demonstration

The existing Mac setup has Python 3.12 and the local `uv` runner installed. The script finds the runner automatically.

1. Open **Terminal** using Spotlight: **Command + Space**, type **Terminal**, then press Enter.
2. Paste this command and press Enter:

   ```sh
   cd "/Users/yazhinigopalakrishnan/Desktop/A&C"
   ```

3. Start the existing offline demonstration:

   ```sh
   ./scripts/demo.sh
   ```

4. Wait until it finishes and the Terminal prompt returns. It creates its own temporary local Azure DevOps mock, generates drafts, applies the fictional change, updates affected sections and exports the results. It uses mock AI responses and makes no paid model call. Some human-review checks intentionally show a blocked result; the script expects those checks.
5. At the end, Terminal prints paths for the workspace, documents, tracked-change document and audit ZIP. It also saves them in `out/demo-latest.json`.
6. Copy and paste this command to open the newly generated workspace:

   ```sh
   open "$(.venv/bin/python -c 'import json; print(json.load(open("out/demo-latest.json"))["explorer"])')"
   ```

7. To open the newly generated Word documents folder, use:

   ```sh
   open "$(.venv/bin/python -c 'import json; print(json.load(open("out/demo-latest.json"))["documents"])')"
   ```

The script stops its temporary source server when it finishes. Saved pages still work; recorded source URLs may no longer respond. Use the embedded source inspector for evidence excerpts and revisions.

For this local walkthrough, use the plain command above. The separate `--live` option requires provider configuration and can invoke AI services; company sandbox execution is still pending.

## 7. A simple five-step presentation

1. **Show Overview in `explorer-baseline.html`.** Say: “We bring requirements, implementation, tests and risk evidence into one review workspace.”
2. **Open Traceability → Find artifact → search `SRS-021`.** Say: “This is the blockage-detection requirement. We can inspect its recorded connections and source revision.” Click a node for details; double-click to focus its relationships. Use Full trace for wider context, and pan/zoom to explore it.
3. **Open Findings and select `G07`.** Say: “This flags a safety-related requirement without a linked verification test, so a reviewer can investigate.”
4. **Open `explorer-stale.html` → Change impact.** Say: “In this recorded scenario, the requirement threshold changes from 80 to 75 kPa, the code changes, and a new test result fails. The system identifies 40 directly outdated document sections and their causes.”
5. **Open `redline-sstr.docx` from the same fallback folder in Word.** Select **Review → All Markup**. Say: “Reviewers see the changed report text and can decide whether to accept it.”

Opening the saved pages demonstrates the recorded workflow. Running the script performs a fresh local simulation. The browser itself does not apply the engineering change.

## 8. What is ready, and what is pending?

**Ready locally:** evidence collection against the simulated source, traceability, checks, document generation, source references, change detection, selective updates, Word tracked changes, review workflow, the browser workspace and audit export.

**Pending company verification:** real Azure DevOps access, company connector permissions, approved model configuration and a successful Copilot Studio/Power Automate run. The adapter and flow instructions are prepared and tested offline. Company execution awaits sandbox answers.

Prepared fallback documents use fictional data and structural mock AI responses. Describe them that way. The product prepares review drafts; people retain approval and risk decisions.

## 9. A short explanation you can read aloud

“Our project helps software teams turn scattered engineering evidence into reviewable documentation. It connects requirements, code, tests and risks, flags missing evidence, and identifies which document sections need updating when engineering work changes. Reviewers get source references and Word tracked changes. Today we can demonstrate the complete local workflow with fictional data; company Copilot Studio execution is awaiting sandbox access and confirmation.”

## 10. If something is confusing

- **The page says evidence has not loaded:** open `data/demo/fallback/explorer.html`, rather than the source template, and allow JavaScript in the browser.
- **You want to see all seven document types:** use the regenerated `explorer.html`; the baseline and stale snapshots contain four.
- **A source link does not open:** the temporary source server may have stopped. Select the artifact and read its embedded source excerpt and revision in the inspector.
- **Fresh generation fails:** keep the Terminal error text and use the prepared fallback files for the walkthrough. Do not overwrite `.env` or add paid API keys to troubleshoot this offline demo.
- **You want the exact technical talk track:** see [DEMO_SCRIPT.md](DEMO_SCRIPT.md). For the product specification, see [BRIEF.md](BRIEF.md).
