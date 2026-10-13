# Named query flows

Each query returns `{facts,evidence}`; graph membership is fixed by SnapshotNumber. Evidence includes full provenance. Include every ID referenced by facts, then follow ID references in body until closure, deduplicate and sort IDs; source_numbers is a validation-only fact and never an impact cause. Entity and release inputs are named, not hidden state.

| Query | Construct and selection |
|---|---|
| architectural_decisions | Dataverse filtered view/child flow: ADR ID and exact source decision body. |
| architecture_diagram | Dataverse filtered view/child flow: Six source components and every extracted unit; unit→component confirmed allocation edges plus resolved imported function calls. Emit local Mermaid source. |
| architecture_matrix | Dataverse filtered view/child flow: Each SRS current revision and explicit component allocation. |
| architecture_risks | Dataverse filtered view/child flow: Hazard ID/name/source severity and mitigating control ID/name. |
| component_allocation | Dataverse filtered view/child flow: Incoming allocated_to requirements filtered software_req; sorted ID/revision/title. |
| component_design | Dataverse filtered view/child flow: One component plus ADRs and its traced hazards; responsibility/interfaces/collaborators are source attributes. Structure facts include allocated units and resolved imports. |
| components | Dataverse filtered view/child flow: Sorted component ID/title/responsibility/safety_class from architecture.yaml. |
| design_gaps | Dataverse filtered view/child flow: All G01–G12 findings including SOUP evidence gaps. |
| design_scope | Dataverse filtered view/child flow: User needs and requested release. |
| drr_actions | Dataverse filtered view/child flow: Source action_item ID/title/state only, all previous actions. |
| drr_checklist | Dataverse filtered view/child flow: Same prioritized review facts; draft questions only. |
| drr_findings | Dataverse filtered view/child flow: Prioritize stale baseline C01/C04/C02, risk G06/G07, failed results G05, then coverage; include bounded grouped impact facts. |
| drr_findings_table | Dataverse filtered view/child flow: Every G/C/F rule with exact count, cited artifact IDs and action, including zero-count rules. Include current drafts and approved baseline under review. |
| drr_identification | Dataverse filtered view/child flow: Require user review_input type/date/baseline/nonempty participants. Copy exactly; no evidence invention. |
| drr_scope | Dataverse filtered view/child flow: Diff explicit previous_snapshot membership/revisions/hashes/links. No changes notice names baseline and snapshot. Missing previous snapshot is a manual comparison notice. |
| evidence_index | Dataverse filtered view/child flow: Every release run/result ID/revision/content hash. |
| failed_results_with_defects | Dataverse filtered view/child flow: All latest Failed/Blocked results plus linked cases, runs, requirements, defects. Complete deterministic adverse table precedes narrative, including AI failure. |
| interfaces | Dataverse filtered view/child flow: All unit IDs/component/signatures from source AST. |
| proposal_pack | Dataverse filtered view/child flow: Subject + explicit linked unit source + design context only. Model cannot invent a trace link. |
| purpose_scope | Dataverse filtered view/child flow: User needs plus recorded release/run scope. AI copies injected facts. |
| references | Dataverse filtered view/child flow: Software requirements and release runs ID/revision/title. |
| release_readiness_facts | Dataverse filtered view/child flow: Deterministic result counts, coverage and gaps; no AI release approval. |
| residual_anomalies | Dataverse filtered view/child flow: All open defects and source residual_listed flag; draft disposition as suggested. |
| results_by_requirement | Dataverse filtered view/child flow: RTM rows for release with cases and latest outcomes; dates/IDs exact. |
| retest_results | Dataverse filtered view/child flow: Latest release results whose source run is a retest, exact cases/outcomes. |
| rtm | Dataverse filtered view/child flow: For every software requirement attach exact revision, component allocations, incoming implementing units/PRs and verifying cases with unique latest results. Compute coverage in code. |
| runtime_view | Dataverse filtered view/child flow: Components, ADRs, hazards and controls; deterministic unit allocation/signatures/imported call dependencies and per-component hazard controls. |
| sfmea_cells | Dataverse filtered view/child flow: Same bounded hazard context; revision map makes changed implementation/retest stale. Five labelled suggested cells. |
| sfmea_function_cells | Dataverse filtered view/child flow: Same function source trace plus exact revision dependencies and five authoring labels. Draft one failure mode per Class C primary function; all cells suggested. |
| sfmea_functions | Dataverse filtered view/child flow: Filter Class C units; primary safety function is configured in specs/risk/functions.yaml and verified against extracted source. Join unit→requirement→control→hazard, attach source severity and controls/tests. Untraced functions explicitly have empty hazard/control arrays. |
| sfmea_gaps | Dataverse filtered view/child flow: Evaluate F01–F03 across all hazards and each control; retain reviewer-confirmed mode distinction. |
| sfmea_rows | Dataverse filtered view/child flow: Filter hazard entity, join mitigating controls←realizing SRS←unit and component; attach tests/results and hazard-level links to function analysis rows. Source severity only. |
| soup_inventory | Dataverse filtered view/child flow: Pinned dependency ID/name/version plus recorded depends_on requirements; missing requirements retained. |
| soup_purpose | Dataverse filtered view/child flow: Same pinned source evidence, prompt describes only known purpose/constraints. |
| system_context | Dataverse filtered view/child flow: System requirements as external interface/context source, no invented physical integration. |
| test_environment | Dataverse filtered view/child flow: Distinct recorded environment values from release test runs. |
| test_results_summary | Dataverse filtered view/child flow: Unique latest results per test case, filtered release/optional test_level; count outcome categories. No unit results notice when unit filter empty. |
| unit_allocation | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Return requirement revision and traced realizing controls. |
| unit_behavior | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Draft algorithm from code and recorded allocations. |
| unit_errors | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Draft invalid-input, error and recovery behavior from code. |
| unit_identity | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Return ID/component/path. |
| unit_interfaces | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Return extracted callable signatures. |
| unit_purpose | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Draft role from source code, never verification claims. |
| unit_structures | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Return classes/bases/fields and module assignments. |
| unit_tests | Dataverse filtered view/child flow: For the entity unit use its extracted source, parent component and implementing requirements. Return explicitly traced unit-level cases, or explicit absence notice. |
| unit_trace | Dataverse filtered view/child flow: All unit/component IDs and implementing SRS traces/signatures. |
| verification_gaps | Dataverse filtered view/child flow: G findings scoped to verification rules; include source IDs/revisions/actions. |
