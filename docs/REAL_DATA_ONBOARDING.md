# Onboard a real project

Company evidence stays on the machine:
- **Locally:** the deterministic steps (import, gaps, RTM, explorer) run with `DHF_PROVIDER=mock`.
- **Personal OpenAI/Anthropic keys:** never receive non-synthetic evidence. The LLM layer refuses it.
- **The BD tenant transport:** also refuses company evidence until the owner and BD clear the dataset (REVIEW R-059).
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
- **Rules it can't assess:** rules that need ADO links (Tested By, Parent/Child) show as **not assessable** rather than as thousands of gaps.

## B. The live ADO project (read-only)

1. **Credentials.** Use a PAT with **Work Items (Read)** and **Test Management (Read)**. Add Code (Read) only when the owner approves code evidence. Keep the PAT out of the repo; pass `APP_ADO_PAT` in the environment for the run.
2. **Settings.** Put `ADO_BASE_URL`, `ADO_PROJECT` and `ADO_SCOPE` in an untracked env file (`DHF_ENV_FILE`).
   - A non-local organization is read-only automatically (`ADO_READ_ONLY=auto`). Only GET and the WIQL/batch read POSTs leave the process, enforced at the transport. Docs-repo PRs and pushes are refused.
3. **Scope.** Copy `specs/ado_scope.example.yaml` outside git and set:
   - seed files or IDs (for example the provided requirement and specification URL lists);
   - link-follow depth and relation types;
   - `max_items`;
   - the test plans whose runs to read;
   - an optional repository.

   Without a scope, a project larger than `ADO_MAX_ITEMS` is refused.
4. **Discover.** `uv run dhf discover` reads the scoped items, field and relation metadata, plan-filtered runs and the repository list. It writes a draft mapping and `.discovery.json`.
   - Check `id_field_candidates` (the field holding document IDs such as specification IDs).
   - Check `custom_fields`, work-item types, area paths and unknowns.
5. **Map.** Write a reviewed mapping profile outside git and point `ADO_MAPPING` at it. Set:
   - work-item types;
   - `id_fields` and `attribute_fields`;
   - relation directions;
   - area-path components.
6. **Ingest.** Run `uv run dhf ingest --source ado --db out/real/evidence.sqlite`. It prints the read-only mode, the scope and every skipped class (unmapped types, out-of-scope results or bugs, unavailable IDs). Then run `dhf gaps`, `dhf rtm` and `dhf explore` against that database with `--output-dir out/real`.
7. **Draft locally.** `uv run dhf generate sstr --release <release> --db out/real/evidence.sqlite --documents out/real/docs` uses the mock provider. Opening PRs requires a docs repository the owner controls and `ADO_READ_ONLY=0` for that run only. Human approvals remain in the eQMS.

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
