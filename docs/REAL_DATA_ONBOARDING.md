# Onboard a real project

Company evidence stays on the machine:
- **Locally:** the deterministic steps (import, gaps, RTM, explorer) run with `DHF_PROVIDER=mock`.
- **Personal OpenAI/Anthropic keys:** never receive non-synthetic evidence. The LLM layer refuses it.
- **The BD tenant transport:** requires the owner and BD clearance reference and the fingerprint of the approved destination. See the [office-laptop guide](OFFICE_LAPTOP_GUIDE.md).
- **Outputs and the dataset folder:** gitignored.

## A. Existing DHF documents (works offline today)

```sh
uv run dhf import-docs <dataset-folder> --db out/real-docs/evidence.sqlite --output-dir out/real-docs
uv run dhf gaps --db out/real-docs/evidence.sqlite --output-dir out/real-docs
DHF_PRODUCT_NAME="<product>" DHF_RELEASE=<release> uv run dhf explore \
  --db out/real-docs/evidence.sqlite --documents out/real-docs/none --output out/real-docs/explorer.html
```

- **What is read:** `specs/doc_import/dhf_documents.yaml` decides this:
  - requirement tables, specification records, architecture items, the requirements-to-items matrix, design units and their template sections, and CSV test cases;
  - latest issue only; redlines and reference copies are excluded;
  - personal CSV columns are dropped before rows are read.
- **What it reports:** `import-report.md` lists imported, excluded and unread files, then the D01–D05 consistency findings.
- **Rules it can't assess:** imported artifacts declare the only link class documents carry (`provides_links: [allocated_to]`). Rules that need ADO links (Tested By, Parent/Child) therefore show as **not assessable** for them, not as thousands of gaps.
  - ADO evidence is always assessed, so an ADO project with nothing linked still reports every gap.
- **Reading Word files:** tracked insertions are read as accepted and deletions are dropped. Content controls are read, and cells keep one line per paragraph. Office lock files (`~$…`) and redlines are excluded whatever their case.

## B. The live ADO project (read-only)

1. **Credentials.** Use a PAT with **Work Items (Read)** and **Test Management (Read)**. Add Code (Read) only when the owner approves code evidence. Keep the PAT out of the repo; pass `APP_ADO_PAT` in the environment for the run.
2. **Settings.** Put `ADO_BASE_URL`, `ADO_PROJECT` and `ADO_SCOPE` in an untracked env file (`DHF_ENV_FILE`).
   - A non-local organization is read-only automatically (`ADO_READ_ONLY=auto`).
     - **HTTP:** only GET and the WIQL/batch read POSTs leave the process, enforced at the transport.
     - **git:** pushes and tags to the organization are refused in the git channel itself.
     - **Credentials:** git ignores stored credential helpers, so the read-only PAT is the only credential used and it is never saved to a keychain.
3. **Scope.** Copy `specs/ado_scope.example.yaml` outside git and set:
   - seed files or IDs (for example the provided requirement and specification URL lists);
   - link-follow depth and relation types;
   - `max_items`;
   - the test plans whose runs to read;
   - an optional repository.

   Without a scope, a project larger than `ADO_MAX_ITEMS` is refused.
   - **Seeded scope** (seeds or WIQL): reads only those items. It reads no test runs unless `test_plans` is set, and the ingest report says so.
   - **Other scopes** (for example only `max_items`): read the whole project and all runs.
   - **Default links followed:** Parent/Child, Tested By and both ends of the mapping's trace link types, such as Dependency between requirements and specifications. Leave `follow.relations` unset to get this; a list replaces it, and `[]` reads the seeds alone.
   - **Runs:** in a seeded scope only runs holding an in-scope result are kept. Set a quoted `release:` (for example `"1.0"`) when run names carry no "Release x.y". It labels every such run of the listed test plans, so list only plans run for that release; the ingest report counts the runs it labelled.
   - **What the scope did not read:** a scope without a repository or test plans declares that, so code and result rules read "not assessable" rather than as gaps or as zero. A seeded scope assesses only the link types it follows (Related links are not followed by default).
   - **Seed lines:** ADO URLs in any form, or a leading ID. Lines that hold no ID are counted. A scope whose seeds yield no IDs is an error, never a silent whole-project read.
4. **Discover.** `uv run dhf discover` reads the scoped items, field and relation metadata, plan-filtered runs and the repository list. It writes a draft mapping and `.discovery.json`.
   - Check `id_field_candidates` (the field holding document IDs such as specification IDs).
   - Check `custom_fields`, work-item types, area paths and unknowns.
5. **Map.** Write a reviewed mapping profile outside git and point `ADO_MAPPING` at it. Set:
   - work-item types;
   - `id_fields` and `attribute_fields`;
   - relation directions;
   - area-path components.
6. **Ingest.** Run `uv run dhf ingest --source ado --db out/real/evidence.sqlite`. It prints the read-only mode, the scope and every skipped class (unmapped types, out-of-scope results or bugs, unavailable IDs). Then run `dhf gaps --db out/real/evidence.sqlite --output-dir out/real`, `dhf rtm` with the same options, and `dhf explore --db out/real/evidence.sqlite --output out/real/explorer.html`.
7. **Architecture without code.** Add `documents: <folder of DHF documents>` to the scope (ADR-044). Every ingest then reads the SAD's software items and allocation matrix and the SDDs' units locally, and adds them to the ADO evidence. ADO stays the source for requirements, specifications and tests; matrix rows for ADO requirements link even when no document lists the requirement. The ingest report counts the documents read, the items added and the matrix rows outside the scope, plus everything `dhf import-docs` would report (unreadable files, duplicate IDs, older issues). The folder and profile are checked before any ADO read. Adding the folder changes what the ADO artifacts can be assessed for, so the first ingest after it reports their changes as configuration-only and re-flags drafts for review.
8. **Draft locally.** Set `DHF_TEMPLATE_SET=bd` for drafts in the owner's SAD/SDD/SSTR structure.
   Then run `uv run dhf generate <sstr|sad|sdd> --release <release> --db out/real/evidence.sqlite --documents out/real/docs`. Pass `--provider mock` for a local structural rehearsal. In the SAD and SDD, signatures, structures and safety class read "not recorded" with the source section named, because no code is in scope. Opening PRs requires a docs repository the owner controls and `ADO_READ_ONLY=0` for that run only. Human approvals remain in the eQMS.

## Seed the synthetic sandbox

Use a dedicated empty project and an inherited process containing Requirement, Risk, Bug, Test Case, Review and Task, with the field names in specs/ado_mapping.yaml. Configure a separate seed identity with work-item/test/Git create and PR completion permissions. No policy bypass is requested. Default seeding never writes read-only System.ChangedDate/CreatedDate. Work items precede runs/results, whose completion times use the native seed epoch plus increasing offsets. The planted SRS-030 revision is applied after those passes, retaining exactly the TC-030 outdated-verification gap. Native timestamps are preserved. Use --bypass-rules only with the explicit work-item bypass permission to reproduce original historical dates; it sends bypassRules=true. This is not PR policy bypass. Process states and PR completion still require a tenant contract check; never claim one from a mock test.

```sh
uv run mock-ado init --empty --root out/seed-sandbox
uv run mock-ado serve --root out/seed-sandbox --port 8089
# In another terminal, using .env mock defaults:
uv run seed-ado --confirm-org kestrel-org --dry-run
uv run seed-ado --confirm-org kestrel-org
uv run seed-ado --confirm-org kestrel-org  # creates zero new items/runs/results/PRs/pushes
uv run dhf discover
uv run dhf ingest --source ado
```

Before writes, the seeder inventories the entire project. Work items without DHF identity tags, repositories without the exact .kestrel-seed.json marker, or runs without a SEED-RUN marker cause refusal with IDs/names. --allow-nonempty is an explicit exception for a reviewed dedicated sandbox, never a production default. An empty mock now has no repositories.

The seeder creates linked work items in dependency order, so links are present in the first revision. Stable DHF tags identify existing seeded work items; duplicate identities are an error. Existing matching seed identities are preserved, not overwritten. Runs match their synthetic names and results match test-case references. Interrupted incomplete PRs can be resumed; completed seed PRs are reused. Source files are compared exactly before native Git pushes. Repositories must be dedicated to this fixture; IDs assigned by a nonempty real project will differ from fixture IDs, so perform semantic trace checks rather than assuming RUN/PR numbers.

Native REST contracts: [work-item JSON Patch](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1), [Git pushes](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pushes/create?view=azure-devops-rest-7.1), [PRs and workItemRefs](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-requests/create?view=azure-devops-rest-7.1), [test results](https://learn.microsoft.com/en-us/rest/api/azure/devops/test/results/add?view=azure-devops-rest-7.1).
