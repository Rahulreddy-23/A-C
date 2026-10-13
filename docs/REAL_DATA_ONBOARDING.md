# Onboard an ADO project

The product uses APP_ADO_PAT only for source reads and docs-repo writes. Keep company evidence local; external LLM providers accept synthetic evidence only. The seed tool is separate, writes synthetic sources only, and uses SEED_ADO_PAT. Never seed an existing production project. The real service/process contract is pending owner-provided sandbox access; local native API tests are not tenant verification.

1. Configure ADO_BASE_URL, ADO_PROJECT, source/docs repo names and APP_ADO_PAT in the ignored .env. Give the app source-read access and write/PR access only to the docs repo. Source write probes must be denied by permissions.
2. Run `uv run dhf discover`. It reads WIQL/work-item batches, native fields/relation metadata, test runs and repositories, writing `out/discovery/ado_mapping.yaml` and `.discovery.json`. It does not overwrite the active mapping. Inspect types/counts, tags, areas, fields used, relations and every unknown.
3. Confirm process-specific type/tag discriminators, field reference names, relationship directions, Related type pairs, severity values and AreaPath allocations with the owner. A renamed field is a suggestion requiring confirmation. Add explicit unit annotations/component inventory for the source code where needed; no AI-inferred link counts as verified. Copy the reviewed mapping to specs/ado_mapping.yaml only after that review; keep company evidence and inventories out of commits.
4. Run `uv run dhf ingest --source ado --db out/onboarding.sqlite`, then `uv run dhf gaps --db out/onboarding.sqlite` and `uv run dhf rtm --db out/onboarding.sqlite`. Inspect immutable provenance, skipped/unmapped types, quantities, latest-result totals and missing traces. Compare source counts from discovery; resolve unknown mappings before calling the ingest complete.
5. Generate a local mock-provider draft: `uv run dhf generate sstr --db out/onboarding.sqlite --documents out/onboarding-docs`. Review citations/revisions and deterministic facts. Add --open-pr only after confirming the docs connection and reviewer IDs. Human approvals remain in the eQMS.

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
