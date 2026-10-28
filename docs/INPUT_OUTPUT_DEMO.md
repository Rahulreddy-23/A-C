# Project inputs, outputs and the demonstration flow

Updated 28 October 2026. A plain-language companion to [LOCAL_DEMO_GUIDE.md](LOCAL_DEMO_GUIDE.md).

## 1. The whole flow in one sentence

**Project evidence → collect and connect records → check for gaps → generate document drafts → human review → export documents and evidence.**

When the evidence changes, the next flow is:

**Read changed evidence → identify outdated document sections → update those sections → show Word tracked changes → human review.**

The input is engineering evidence. The output is documentation and review information derived from that evidence.

## 2. How do we upload a project or document?

**The current browser workspace has no project/document upload button. It is a read-only view of a saved run.**

The engine currently receives evidence in two ways:

1. **Bundled local demo data:** read the structured fictional records and Python code already in this repository.
2. **Azure DevOps connection:** read records from a configured project and its source repository. The adapter is implemented; real company access and process mapping still need verification.

**There is no general importer that takes any PDF, Word file or ZIP and automatically understands it as a project.** A drag-and-drop upload screen and general document parsing would be additional work. Copying a company PDF into this folder does not make it an input to the engine.

The existing file inputs have specific purposes:

| Input | How the current version uses it |
|---|---|
| Structured local demo records | `data/synthetic/evidence.yaml` supplies fictional requirements, risks, tests, results, defects and links. |
| Demo source code | `data/synthetic/code/` supplies Python code and dependency files; extraction identifies software units and recorded implementation references. |
| Review details | `data/synthetic/review_input.json` provides structured review information, such as date and participants, for the design-review workflow. |
| Previous design baseline | `data/synthetic/sad_v1.md` is a supported legacy Markdown baseline used for specific consistency checks. It is not a general-purpose document-import feature. |
| Document templates | `specs/documents/` defines which sections to generate and what evidence they use. These are output instructions, rather than project evidence. |

The local fixture command is wired to the bundled dataset. A different project's local files would need a reviewed mapping/import path; the CLI does not currently expose a universal folder-upload option.

For a company project, the intended onboarding sequence is:

1. Obtain approved read access to the Azure DevOps organization, project, tests and code repository.
2. Configure the project connection in ignored `.env`; credentials stay out of source control.
3. Run discovery to inspect the project's work-item types, fields and relationships.
4. Have someone confirm how those fields map to our requirements, tests, risks and other record types.
5. Read the evidence into the local store and check the counts and missing links.
6. Generate and review drafts using the permitted processing/model path.

That company sequence is pending actual environment verification. Current code extraction supports Python; other source languages would need an appropriate extractor. See [REAL_DATA_ONBOARDING.md](REAL_DATA_ONBOARDING.md) for the technical procedure.

## 3. What is the input?

Use the fictional pump as your example:

| Input information | Simple example |
|---|---|
| Requirement | “Detect blocked tubing, stop delivery and raise an alarm.” |
| Code and recorded implementation references | The sensor-monitoring code and its references to the requirement. |
| Test case | A procedure that checks the blockage behaviour. |
| Test result | The recorded pass or fail from a test run. |
| Risk and control | A recorded hazard and the control intended to address it. |
| Defect | A recorded issue associated with a failure, where a link exists. |
| Source/version information | Where each record came from and which revision was read. |

The system follows existing recorded links. It flags missing links for investigation; it does not silently treat an AI-suggested connection as confirmed evidence.

## 4. What happens to the input?

1. **Collect:** read the configured source records.
2. **Store:** save the evidence and its revisions in a local database file.
3. **Connect:** follow the recorded requirement, implementation, test and risk relationships.
4. **Check:** calculate coverage and results, and flag missing or inconsistent evidence.
5. **Draft:** fill document templates with calculated facts and validated, labelled AI prose. The offline demonstration uses structural mock AI responses.
6. **Review:** expose source references, human placeholders and suggestions. Generate Word files and, when configured, submit drafts to the documents repository for review.
7. **Export:** save the workspace, reports, documents and audit package.

The product reads the engineering source systems. It does not repair requirements, change source code or add missing source links on its own. People investigate findings and make those decisions.

## 5. What is the output?

| Output | What the audience sees |
|---|---|
| `explorer.html` | A browser workspace containing the evidence, findings, documents and recorded relationships for that run. |
| `.docx` files | Word drafts, including architecture, detailed-design and test-report documents. |
| `.md` files | Text versions of the generated documents. |
| `.manifest.json` files | Companion records of sources, revisions, generation settings and validation information. |
| Gap report and RTM | Missing-evidence findings and a requirement-to-implementation/test table. |
| Impact report | Which sections are directly outdated or potentially affected, and why. |
| Redline Word document | Changes to review after regeneration. |
| Metrics report | Evaluation results, timing, usage and explicitly labelled effort assumptions. |
| `audit-pack.zip` | Documents and supporting evidence bundled with integrity checks. |

Outputs are drafts and review evidence. Approval and risk-acceptance decisions remain with people.

## 6. Show the full recorded flow without using Terminal

Open this folder in Finder with **Command + Shift + G**:

```text
/Users/yazhinigopalakrishnan/Desktop/A&C/data/demo/fallback
```

Then present these steps in order:

| Step | Show this | Say this |
|---|---|---|
| 1 — Input | `explorer-baseline.html` → Traceability → Find artifact → `SRS-021` → Inspector | “This is an input requirement, with its recorded source and revision. Related code, tests and risk records are also inputs.” |
| 2 — Connections | Inspect the selected record's direct links, then Full trace | “We connect the evidence using recorded relationships.” |
| 3 — Checks | Findings → select `G07` | “Here is a requirement without a linked verification test. This becomes a finding for a person to investigate.” |
| 4 — Documents | Documents, then `sstr.docx` in Word | “The engine prepares report drafts from the evidence. Source references and review labels remain available.” |
| 5 — A change | `explorer-stale.html` → Change impact | “This recorded scenario changes the threshold from 80 to 75 kPa, updates code and adds a failed test result. Forty document sections become directly outdated.” |
| 6 — Updated output | `redline-sstr.docx` → Word → Review → All Markup | “The affected sections are updated, and the reviewer can see the changed text.” |
| 7 — Final package | `explorer.html`, then show `audit-pack.zip` in Finder | “We can explore the regenerated result and export the documents with their supporting evidence.” |

The baseline/stale pages contain four documents; the final page contains seven because additional document types are generated later in the demonstration. These files show stages from one recorded successful run. Switching between them does not apply a live change.

Keep this explanation ready if someone asks where the upload button is:

> “This prototype reads project evidence through its engine, using structured demo files or a configured Azure DevOps connection. The browser is the review workspace. A general file-upload and PDF/Word-import screen is not implemented.”

## 7. Run the input-to-output steps yourself

This is a small, offline **baseline** example using the bundled fictional data. It generates one test report and one workspace. It does not apply the change scenario or create a document-repository review request.

Run the following commands one at a time in Terminal. Continue after each command finishes successfully.

**Step 1 — Enter the project folder.**

```sh
cd "/Users/yazhinigopalakrishnan/Desktop/A&C"
```

**Step 2 — Read the bundled input data.**

```sh
.venv/bin/dhf ingest --source fixtures --db out/flow-demo/evidence.sqlite
```

The first snapshot should contain **248 records and 413 confirmed links**. The local `evidence.sqlite` database is the intermediate result used by later steps.

**Step 3 — Produce the gap and traceability reports.**

```sh
.venv/bin/dhf gaps --db out/flow-demo/evidence.sqlite
.venv/bin/dhf rtm --release 1.1 --db out/flow-demo/evidence.sqlite
```

These commands write the latest reports to `out/gaps.md`, `out/gaps.json`, `out/rtm.md` and `out/rtm.json`. They replace prior copies of those generated reports.

With the current bundled dataset, these steps report **21 deterministic gap findings** and **35 requirement-table rows**. The gaps are deliberately present in the fictional dataset.

**Step 4 — Generate a system-test report using mock AI.**

```sh
DHF_CACHE_ROOT=out/flow-demo/llm .venv/bin/dhf generate sstr --release 1.1 --provider mock --db out/flow-demo/evidence.sqlite --documents out/flow-demo/documents
```

Expected files: `sstr.docx`, `sstr.md` and `sstr.manifest.json` under `out/flow-demo/documents/`.

**Step 5 — Build the browser view of those results.**

```sh
.venv/bin/dhf explore --db out/flow-demo/evidence.sqlite --documents out/flow-demo/documents --output out/flow-demo/explorer.html
```

**Step 6 — Export the documents and evidence together.**

```sh
.venv/bin/dhf audit-pack --release 1.1 --db out/flow-demo/evidence.sqlite --documents out/flow-demo/documents --output out/flow-demo/audit-pack.zip
```

This one-report example exports **11 verified files**. The full demonstration has more documents and its recorded audit package contains 33 verified files.

**Step 7 — Open your outputs.**

```sh
open "out/flow-demo/explorer.html"
open "out/flow-demo/documents"
```

You should see a workspace with 248 records and one generated document. Double-click `sstr.docx` in the documents folder to read the Word output. This smaller example has no change scenario, so it will not show the 40 outdated sections from the full demonstration.

To perform the full simulated source-change and tracked-change workflow, use `./scripts/demo.sh`, as explained in [LOCAL_DEMO_GUIDE.md](LOCAL_DEMO_GUIDE.md).

## 8. Three command options that are easy to misunderstand

- **`generate --documents`** chooses where generated documents are saved. It does not upload source documents.
- **`explore --documents`** reads our generated `.manifest.json` files so the browser can display document sections. It is not an arbitrary Word/PDF reader.
- **`generate drr --input-file`** supplies structured review details in JSON. It is not a general document-upload parameter.

For a different real project or a collection of existing documents, first identify the source formats, required fields, relationship mappings and permitted processing environment. General document extraction and company integration should only be presented as working after they have actually been implemented and verified.
