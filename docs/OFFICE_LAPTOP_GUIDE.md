# Office laptop guide: run DHF Automation on the real project

This guide takes you from a fresh office laptop to Word drafts, a gap list and a checked score for the real product. Follow the parts in order. Commands are for **Windows PowerShell**; run them from the `A-C` folder unless a step says otherwise.

How the pieces fit:

```
Office laptop (this tool)                          BD tenant (Power Automate)
ADO --read-only--> snapshot -> trace -> gaps
                   section evidence ---HTTPS--->  When an HTTP request is received
                                                    -> Run a prompt (approved Basic GPT)
                   validator <--- claims JSON ---   -> Response
                   -> Word drafts + manifests
```

- Only the **AI writing step** leaves the laptop, and only to the BD tenant flow.
- The tool never writes to ADO. It reads with a read-only PAT, and the code also blocks writes.
- Personal Claude/OpenAI keys never receive company data. The code refuses this whatever the settings say.

## Part 0. Have these ready

| Item | Where it comes from |
|---|---|
| Git and uv installed | Part 1 |
| Read-only ADO PAT: **Work Items (Read)** and **Test Management (Read)** | ADO → User settings → Personal access tokens |
| Organization URL and project name | The ADO address bar: `https://dev.azure.com/<org>/<project>` |
| Which work items are in scope | A list of requirement/specification URLs or IDs, or an area path |
| Test plan IDs and the release label (e.g. `1.0`) | ADO → Test Plans |
| Folder of the current design documents (SAD/SDD Word files) | Your DHF library, copied locally |
| BD sandbox access to Power Automate with AI Builder **Run a prompt** | Part 6 |
| The clearance reference for using this dataset in the sandbox | The BD approval (email subject and date, or ticket number) |

## Part 1. Install the tools (once)

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Close PowerShell and open a new one so the commands are found. Check:

```powershell
git --version
uv --version
```

## Part 2. Get the code

```powershell
cd $HOME
git clone https://github.com/Rahulreddy-23/A-C.git
cd A-C
uv sync
uv run dhf --help
```

`uv sync` installs Python 3.12 and every library the project needs. The last command should list commands such as `ingest`, `gaps` and `generate`.

Prove the install works offline (no keys and no network needed):

```powershell
uv run pytest -q
```

Expect every test to pass.

## Part 3. The settings file

Create it from the template:

```powershell
Copy-Item .env.example .env
notepad .env
```

Change these lines and leave the rest as they are. `.env` is ignored by git, so it never leaves the laptop.

```ini
# Azure DevOps, read-only
ADO_BASE_URL=https://dev.azure.com/<organization>
ADO_PROJECT=<project name>
APP_ADO_PAT=<read-only PAT>
ADO_READ_ONLY=auto
ADO_SCOPE=out/real/scope.yaml
# After Part 4 point this at the reviewed real mapping:
ADO_MAPPING=out/real/ado_mapping.yaml

# Labels and document structure
DHF_PRODUCT_NAME=<product>
DHF_PRODUCT_SUBJECT=<one-line subject>
DHF_RELEASE=<release, e.g. 1.0>
DHF_TEMPLATE_SET=bd

# AI drafting through the BD tenant only
DHF_PROVIDER=copilotstudio
DHF_COPILOT_MODE=http
DHF_COPILOT_FLOW_URL=<filled in Part 6>
DHF_COPILOT_USAGE=estimated
DHF_REAL_DATA_APPROVAL=<clearance reference, e.g. "BD approval email 2026-11-17">
```

- `DHF_REAL_DATA_APPROVAL` is what lets company evidence reach the Copilot flow. Every manifest records it, so an auditor can see under which approval a draft was written. Leave it empty and the tool refuses to draft from real data.
- Do **not** put `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` on this laptop.

## Part 4. Tell the tool what to read (scope and mapping)

**4a. Scope.** This file lists which work items, test plans and documents belong to the release.

```powershell
New-Item -ItemType Directory -Force out/real
Copy-Item specs/ado_scope.example.yaml out/real/scope.yaml
notepad out/real/scope.yaml
```

Fill in:
- `seed_ids` or `seed_files` with the requirement and specification work items. A `wiql` query on an area path also works.
- `test_plans` with the test plan IDs, and `release: "<release>"` if run names don't contain "Release x.y".
- `documents:` with the design document folder, relative to `out/real/`. For example, `documents: ../../../dhf-documents` if the folder sits next to `A-C`.
- Leave `repository: ""`, because code evidence is out of scope for the hackathon.

**4b. Check the settings.**

```powershell
uv run python tools/office_check.py --online
```

Every line should say `OK`. A `FIX` line says what to change. `--online` makes one read-only request to prove the PAT and project are right.

**4c. Discover the field names.** Real ADO projects name their fields differently from the example data. Discovery reads the scoped items and drafts a mapping:

```powershell
uv run dhf discover --output out/real/ado_mapping.yaml
```

Open `out/real/ado_mapping.yaml` together with `out/real/ado_mapping.discovery.json` and check:
- `id_fields`: the field that holds the document IDs (for example the specification ID that differs from the ADO number). Discovery lists candidates under `id_field_candidates`.
- Work-item types: which ADO type is a requirement, a specification, a test case or a bug.
- `unknowns`: every unknown needs a decision. Ask Rahul if one is unclear.

## Part 5. First real run, no AI

```powershell
uv run python tools/real_run.py --no-ai
```

This reads ADO, finds gaps, builds the trace matrix and the explorer, and makes the review sheet. Open:

| File | What it shows |
|---|---|
| `out/real/gaps.md` | Every gap found, with the rule and the suggested action |
| `out/real/rtm.md` | Requirement → test → latest result rows |
| `out/real/explorer.html` | Clickable map of all evidence; double-click to open in a browser |
| `out/real/findings_review.csv` | The sheet for Part 9 |

If step 1 prints skipped classes (unmapped types, out-of-scope results), fix the mapping or scope and run again.

## Part 6. Build the Copilot flow (in the BD sandbox)

**6a. The prompt.** In the Citizen Development Sandbox, create one AI Builder prompt named `DHF section drafter`:
1. Choose the approved **Basic GPT** model.
2. Paste the instructions: everything in `specs/prompts/copilot.generic_drafter.md` **after** the second `---` line, unchanged.
3. Add eight **Text** inputs: `request_id`, `prompt_id`, `prompt_version`, `instructions`, `facts_json`, `evidence_json`, `output_schema_json`, `max_claims`.
4. Set the output to **JSON**, using the `claims_json` contents of `tests/fixtures/copilot_response.json` as the example shape.

**6b. The flow.** In Power Automate, create an instant cloud flow:
1. Trigger **When an HTTP request is received**. Use `tests/fixtures/copilot_request.json` to generate its schema.
2. **Run a prompt**: pick `DHF section drafter` and bind each of the eight inputs to the trigger field with the same name.
3. **Response**, status 200, body:
   ```json
   {
     "request_id": "@{triggerBody()?['request_id']}",
     "claims_json": "@{string(<Run a prompt output JSON>)}",
     "model": "<the model name shown in the tenant>"
   }
   ```
   If the prompt fails or refuses, respond with `{"request_id": "...", "status": "failed"}` (or `"refused"`). The tool then puts a "write this section by hand" placeholder in the draft instead of crashing.
4. Save, then copy the trigger's **HTTP URL** into `.env` as `DHF_COPILOT_FLOW_URL`. That URL is a secret: never put it in chat, screenshots or git.

If your tenant blocks the HTTP trigger, use the OneDrive folder mode instead: set `DHF_COPILOT_MODE=folder` and `DHF_COPILOT_EXCHANGE_DIR`, and ask Rahul for the folder-flow recipe.

## Part 7. Test one section before the whole document

**7a. Preview a request** (sends nothing):

```powershell
uv run dhf copilot-request sstr anomaly_assessment --release <release> --db out/real/evidence.sqlite
```

You can paste this output into the prompt builder's test pane to see the prompt work.

**7b. One real call:**

```powershell
uv run dhf generate-section sstr anomaly_assessment --release <release> --db out/real/evidence.sqlite --debug
```

- `N validated claims` means the flow, prompt and validator all work.
- `reason=provider_error` means the flow URL is wrong or the flow failed. Check the run history in Power Automate.
- `reason=timeout` means the flow took over 120 seconds. Set `DHF_COPILOT_TIMEOUT_S=300` in `.env`.
- Compare the credit use with the tenant **Monitor** tab. The local credit count is an estimate.

## Part 8. Full run

```powershell
uv run python tools/real_run.py --docs sstr,sad,sdd
```

Drafts land in `out/real/docs/` as Word (`.docx`), Markdown and a manifest. Each manifest records the snapshot, model, cost and `real_data_approval`.

To rerun drafting without reading ADO again: `uv run python tools/real_run.py --skip-ingest --docs sstr`. Sections already drafted come from the cache and cost nothing.

Credits: the tool stops at `DHF_COPILOT_CREDIT_CAP` (400 by default) and at `DHF_COPILOT_CREDITS_PER_RUN` (250) per run. Watch the Monitor tab. The sandbox has a monthly limit.

## Part 9. Test the product data (is it right?)

**9a. Check the gaps by hand.** Open `out/real/findings_review.csv` in Excel. For 20–30 findings, ideally with someone who knows the product, open the ADO item and fill in:
- `verdict`: `TRUE` (a real gap), `FALSE ALARM` (the link exists, or the rule doesn't apply) or `UNSURE`
- `reviewer` and `notes`: who checked it, and why

Save as **CSV** (keep the name), then score it:

```powershell
uv run python tools/review_sheet.py score
```

This writes `out/real/findings_score.md` with the percentage correct per rule. That's the accuracy number for the demo. Each false alarm points at a mapping or scope fix (Part 4), so fix it, rerun, and your verdicts are kept.

**9b. Check the drafts.** Open each `.docx` and check:
- Every sentence has links to evidence. Click a few and confirm the item says what the sentence says.
- `[Inferred]` and `[Suggested — review required]` sentences are not stated as facts.
- In the manifest, `validation.rejected` lists sentences the checker removed for citing unknown IDs. A few are normal. Many in one section mean its prompt needs work.
- Sections saying `AI drafting unavailable` must be written by hand. The reason is in the run output.

## Part 10. The change story for the demo

The drafts remember the exact ADO revisions they cited. After real items change in ADO (they do every day), read ADO again and ask what went stale:

```powershell
uv run dhf ingest --source ado --db out/real/evidence.sqlite
uv run dhf impact --db out/real/evidence.sqlite --documents out/real/docs
```

`out/impact.md` lists the stale sections and which work items changed. Draft on Thursday and re-read on Monday, and you have a real change story.

## Troubleshooting

| Message | Meaning and fix |
|---|---|
| `ADO rejected APP_ADO_PAT` | PAT wrong, expired, or missing Work Items (Read) |
| `refused above max_items` | Scope too wide; add seeds or raise `max_items` in the scope |
| `External APIs require exclusively synthetic evidence` | `DHF_REAL_DATA_APPROVAL` is empty, or `DHF_PROVIDER` isn't `copilotstudio` |
| `Configure DHF_COPILOT_FLOW_URL` | Part 6 isn't finished |
| `Copilot credit cap reached` | Local cap reached; check Monitor before raising it |
| `dhf command not found` | Run through `uv run ...` from the `A-C` folder |

## Before the demo

- [ ] `tools/office_check.py --online` all OK
- [ ] Full run (Part 8) done; drafts open in Word
- [ ] Review sheet scored; numbers on one slide
- [ ] Change story ready (Part 10)
- [ ] Screen recording of a full run, as a backup if anything fails live
- [ ] `out/real/` stays on the laptop; company outputs are never committed
