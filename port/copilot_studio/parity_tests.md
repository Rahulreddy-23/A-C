# Parity execution

Run these cases in a synthetic tenant after capability gates pass. Load the canonical fixture JSON and native examples from contracts/; use the unchanged specs/ files for normalization and queries. Inputs and expected outputs are frozen files, not outputs recalculated from the tenant under test. Compare sorted IDs and exact values; URLs/native IDs differ between fixture and tenant, retrieval times are ignored. Record run ID, environment/model/config hashes, actual output, pass/fail and reviewer in a separate parity log. This pack defines cases; it does not claim tenant execution.

| Case | Input / action | Expected |
|---|---|---|
| Native ingest | native_examples.json; full fixture/native ADO export | Same canonical semantics, no DHF-META dependency; full provenance and 248 artifacts/413 links |
| Trace/gaps | canonical_graph.json and answer_key.yaml | Exact G01–G12 IDs, 21 findings; all link endpoints valid |
| Latest results | graph, release 1.1 | total 40, passed 39, failed 1, blocked/not_run 0; unique cases |
| Validator | validator_cases.json | Exact accepted and audited outcomes, no unknown ID admitted |
| Historical consistency | legacy SAD inventory (missing COMP-06, Pressure Monitoring) | C01 COMP-06 and C04 COMP-03 |
| Impact | change_1.yaml applied to a frozen generation baseline | Exact expected section statuses and causal IDs; occlusion HAZ-04 source and function blocks stale |
| Selective regen | Saved pre-change source and edited sections | Unchanged section bytes identical; new PR metadata contains only stale sections; manual edits persist |
| Review readiness | unresolved suggested/human section; then explicit human resolution | First fails, second can pass; no product merge/approval |
| Source guard | writer calls a source work-item PATCH | Refused by source permission boundary; docs PR permitted |
| Budget/cache | same prompt/version/model/canonical pack twice; cap edge | One call then free cache hit; run/build/total cap denies excess; concurrent reservations cannot overspend |
| Refusal/limits | refused, truncated, over-budget evidence/output and malformed JSON | Distinct safe reasons, manual placeholder; deterministic failed-result table remains |
| DRR/risk | supplied review_input.json; sfmea spec | Exact participants; human decisions/approval fields; severity only source; all analysis cells suggested, distinct effects |
| Extensibility/export | add SUTR/RTM YAML; audit ZIP | No engine edits; actual unit results or explicit absence; checksum verifier rejects tampering |

Reference command: `uv run python tools/check_port.py`. Local pack checks verify coverage, exact prompt bodies and fixture expectations. End-to-end reference tests: `uv run pytest`. Tenant parity remains pending until the cases above have recorded actual tenant results.
