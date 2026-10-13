# Deterministic logic and boundaries

All joins use one complete snapshot. Confirmed links have origin explicit or human_confirmed. Never add inferred links to metrics. Rules are loaded unchanged from specs/rules; configuration supplies types, attribute filters, peer types, direction and action. A Dataverse query must page all rows; delegable views or FetchXML anti-joins are preferable to unbounded client collections.

| Rule | Operation and implementation | Source parameters |
|---|---|---|
| C01 | For SAD/SDD/sFMEA compare component_set with distinct units.component from current code. Symmetric difference gives findings. Read latest numeric approved tag as well as drafts; legacy SAD parses its stated inventory. | `{"id": "C01", "op": "component_set"}` |
| C02 | For each cited_revisions map entry join current Artifact by canonical ID. Missing ID or unequal revision is C02. Do not compare retrieve timestamps. | `{"id": "C02", "op": "citation_revision"}` |
| C03 | Compare SSTR results_summary with LatestResults unique-case outcome counts for its release. Requirement rows cannot be counted directly because a case can verify multiple requirements. | `{"id": "C03", "op": "result_summary"}` |
| C04 | For each document component_names compare exact canonical component title; return ID and both names. | `{"id": "C04", "op": "component_name"}` |
| F01 | For each hazard analysis row, confirmed controls mitigating its hazard are empty. Do not let proposed links count. | `{"id": "F01", "op": "missing_control"}` |
| F02 | Evaluate each hazard AND each control separately. Control must have a realizing requirement with a verifying case; verified sibling controls cannot hide an unverified control. | `{"id": "F02", "op": "missing_verification"}` |
| F03 | A hazard lacks a reviewer-confirmed failure-mode claim citing it. Suggested AI rows do not close this gap. | `{"id": "F03", "op": "missing_confirmed_mode"}` |
| G01 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "in", "id": "G01", "link": "verifies", "op": "missing_link", "peer_types": ["test_case"], "types": ["software_req"]}` |
| G02 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "in", "id": "G02", "link": "implements", "op": "missing_link", "peer_types": ["code_change"], "types": ["software_req"]}` |
| G03 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "out", "id": "G03", "link": "implements", "op": "missing_link", "peer_types": ["software_req"], "types": ["code_change", "software_unit"]}` |
| G04 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "out", "id": "G04", "link": "verifies", "op": "missing_link", "peer_types": ["software_req"], "types": ["test_case"]}` |
| G05 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"attrs": {"outcome": "Failed"}, "direction": "out", "id": "G05", "link": "reports_defect", "op": "missing_link", "peer_types": ["defect"], "types": ["test_result"]}` |
| G06 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "in", "id": "G06", "link": "implements", "op": "missing_link", "peer_types": ["software_req"], "types": ["risk_control"]}` |
| G07 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"attrs": {"risk_control": true}, "direction": "in", "id": "G07", "link": "verifies", "op": "missing_link", "peer_types": ["test_case"], "types": ["software_req"]}` |
| G08 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "in", "id": "G08", "link": "derives_from", "op": "missing_link", "peer_types": ["software_req"], "types": ["system_req"]}` |
| G09 | Filter subjects by types and attrs/not_attrs. Filter confirmed links by type and direction. Join peer types. Return subjects with CountRows(join)=0. | `{"direction": "out", "id": "G09", "link": "derives_from", "op": "missing_link", "peer_types": ["system_req"], "types": ["software_req"]}` |
| G10 | Filter source attributes exactly; exclude not_attrs. No model call. | `{"attrs": {"residual_listed": false}, "id": "G10", "not_attrs": {"state": "Closed"}, "op": "match", "types": ["defect"]}` |
| G11 | Follow case→requirement verifies. Find latest Passed result across releases. Compare completed_at against requirement changed_at; flag case if older. A later Failed rerun does not close the prior-pass gap. | `{"id": "G11", "op": "outdated_verification", "types": ["test_case"]}` |
| G12 | SOUP without an incoming or outgoing depends_on requirement link OR missing known_anomaly_evaluation. | `{"id": "G12", "op": "soup_requirements", "types": ["soup"]}` |
| L01 | Pre-screen G02 into deterministic no-implementing-change findings. For other requirements with explicit linked units, compare acceptance criteria with actual code in proposal.implementation; empty claims means no suspected gap. Persist only positive suggestions with confidence. | `{"id": "L01", "model_tier": "analytical", "op": "requirement_implementation", "prompt": "proposal.implementation@1"}` |
| L02 | Units lacking confirmed implements links are sent to proposal.orphan for a draft shall-statement; create Proposal only, never ADO requirement. | `{"id": "L02", "model_tier": "analytical", "op": "orphan_requirement", "prompt": "proposal.orphan@1"}` |
| L03 | Group SAD component responsibility and SDD implementing unit behavior by component; include document hashes/citations; proposal.contradiction emits only likely contradictions, empty on agreement. | `{"id": "L03", "model_tier": "analytical", "op": "design_contradiction", "prompt": "proposal.contradiction@1"}` |

For missing_link the collection prototype is `Filter(Subjects As s, IsEmpty(Filter(ConfirmedLinks, If(Direction="in", dst=s.id, src=s.id) && type=LinkType)))`; production adds peer-type checks and joins in the Dataverse view. Counts and percentages use integer counts and `Round(100 * covered / total, 2)`, with zero denominator returning 0. Latest result uses completed_at then canonical ID to break ties.

## Code and hash boundaries

| Boundary | Approved function contract | Capability fallback |
|---|---|---|
| AST extraction | Git paths/blob revisions and architecture.yaml → JSON units, callable signatures/class fields/import calls/component allocation and pinned SOUP; no external calls | Human supplies and reviews the same canonical inventory with source URLs and hashes; mark AST parity pending |
| Canonical hashes | Sorted-key compact UTF-8 JSON; SHA256(body + canonical attributes) for Artifact content; SHA256(prompt identity/version/model/body hash/pack) for cache; SHA256 exact UTF-8 section Markdown | Verified local reference produces hashes; do not claim native Power Fx hash parity |
| Validator | Native flow membership/kind/confidence checks plus Power Fx MatchAll numeric extraction; native_validator.md → accepted claims and audit events | Numeric claims become Suggested and blocked as numeric_unverified when extraction is unavailable; no silent bypass |
| Local diagrams/DOCX | Markdown + approved baseline → locally rendered PNG, OOXML ins/del and review comments + SHA256 | Keep Mermaid source, use Word Compare manually and Git PR diff, record DOCX parity pending |
| Audit ZIP | Exact approved input files and SHA256SUMS → ZIP with safe relative paths | Download files plus checksums, ZIP locally and verify; tenant automated export pending |

Human input and availability fallbacks are explicit statuses, never fabricated approved output. Imported SharePoint config files remain data. There is no source write action in an ingest, generation or proposal flow.
