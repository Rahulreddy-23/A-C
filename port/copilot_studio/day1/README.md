# Day-1 sandbox kit — synthetic Kestrel only

Start in **Copilot Studio Citizen Development Sandbox** (Experiment stage), not BD (Default). Use the original Copilot Studio experience → **Agent**, or the new experience → **Other ways to build → Agent, Standard**. Do not choose a GitHub Copilot agent or workflow. The owner-supplied sandbox guidance permits GPT models only. This kit is an offline construction guide; no tenant step has been executed here.

Paste this required agent description:

> Kestrel DHF Draft Assistant helps design assurance and verification reviewers turn synthetic Azure DevOps requirements, test results, risk records and reviewed code inventories into cited draft documentation. It reduces manual trace compilation while preserving source revisions, missing links and human approval. It reads only the selected synthetic Kestrel evidence snapshot and writes governed drafts to the docs review location; it never changes engineering source records.

Use one topic, **Draft the release test report**. Its two actions are `StartGeneration` and `GetRunStatus`; both return deterministic run state and a draft link. Do not invoke an agent flow for each artifact or add generative answers/grounding to routine status replies. Run the evidence and document loops in Power Automate cloud flows. Model selection: approved **Basic-tier GPT** for both MVP prompts; the reference `analytical` tier maps to Basic unless one Standard showcase section is explicitly budgeted. No reasoning/Premium model or Anthropic provider is part of this sandbox build. Watch the **Monitor** tab after each rehearsal and stop before the 600-credit monthly limit.

Files in this folder:

- [SSTR anomaly prompt](sstr_anomaly_prompt.md) and [SAD component prompt](sad_component_prompt.md): ready-to-paste instructions, four text inputs, fixed JSON output and [sample inputs/outputs](samples/).
- [Flow WDL validator cards](validator_flow_wdl.md) for citation/kind/confidence and [Power Fx cards](validator_powerfx.md) for hosted `MatchAll` number/ID extraction, with reference cases and a blocked compensation.
- [Dataverse columns CSV](mvp_columns.csv): four MVP tables. It is a column worksheet for table creation/import, not an exported solution.
- [Tier B click path](click_path_tier_b.md): agent and flows 01→07, including the source-write boundary and day-1 capability gates.

First answer the starred questions in [SANDBOX_QUESTIONS.md](../../../docs/SANDBOX_QUESTIONS.md). If the ADO connector is restricted, use the [Tier C′ reviewed snapshot path](../BUILD_PLAN.md#tier-c-prime-no-ado-connector) while seeking a Digital Innovation Request for the Prototype environment; do not treat that request as a demo dependency. Use only synthetic data until the owner confirms the real hackathon dataset is cleared. Test in the agent pane; after publishing, share through a Teams channel with at most five named individuals, no groups, and republish after each change.

M16 adds the [generic BD-approved model runner](generic_prompt.md), [HTTP flow](http_prompt_flow.md) and [OneDrive folder flow](onedrive_prompt_flow.md). These two MVP prompt files remain useful for native Option A only if both model-runner modes are unavailable.
