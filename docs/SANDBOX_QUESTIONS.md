# Copilot Studio Sandbox: Questions to Answer

Fill this in from the company sandbox, or forward it to the sandbox or Power Platform admin. The answers pick the build tier in `port/copilot_studio/BUILD_PLAN.md` (Tier A, B or C).

**Where to look**
- Copilot Studio (copilotstudio.microsoft.com)
- Power Automate (make.powerautomate.com)
- Power Platform admin center (admin.powerplatform.microsoft.com)

## 1. Environment and storage (decides Tier A/B vs C)

| # | Question | How to check | Answer |
|---|---|---|---|
| 1.1 | Environment name and type (Developer, Sandbox, Production)? | Copilot Studio → environment picker (top right) | |
| 1.2 | **Is Dataverse available in this environment?** Can you create a custom table? | make.powerapps.com → Tables → "+ New table" | |
| 1.3 | Is SharePoint available, with a site you can create lists and document libraries in? | SharePoint home | |
| 1.4 | Can you create a **solution** and add flows and agents to it? | make.powerapps.com → Solutions | |

## 2. Connectors and licensing (decides what the flows can do)

| # | Question | How to check | Answer |
|---|---|---|---|
| 2.1 | **Is the Azure DevOps connector available**, and can it sign in to an ADO organization you can reach? | Power Automate → new flow → add action → search "Azure DevOps" | |
| 2.2 | Does it offer **"Send an HTTP request to Azure DevOps"**? | Same action list | |
| 2.3 | Are **premium connectors** allowed (a premium label shows on the connector)? | Same | |
| 2.4 | Is there an ADO project with the hackathon dataset, or can we create a test project? Do we have Git repo create/push rights there? | dev.azure.com | |
| 2.5 | What do the **DLP policies** block? Are HTTP, custom connectors or Office Scripts blocked? | Admin center → Policies → Data policies, or ask the admin | |
| 2.6 | Can you create a **custom connector**? | Power Automate → Data → Custom connectors | |
| 2.7 | Is an **Azure Function, Azure subscription or other approved code endpoint** available to us? | Ask the admin | |

## 3. AI and agent features (decides how generation works)

| # | Question | How to check | Answer |
|---|---|---|---|
| 3.1 | Can you add a **Prompt** tool to an agent, and set its output to **JSON**? | Copilot Studio → agent → Tools → Add → Prompt → output format | |
| 3.2 | **Which models** can a Prompt use (e.g. GPT-4.1 / GPT-4o / GPT-5 / others)? Can you choose? | Prompt editor → model selector | |
| 3.3 | Are **AI Builder credits** or Copilot Studio message capacity allocated, and how much? | Admin center → Capacity / Licensing | |
| 3.4 | What's the **maximum prompt input size**? Paste a ~40 KB JSON text and see if it runs. | Prompt editor test | |
| 3.5 | Can an agent call a **flow** as a tool ("agent flow")? Are **asynchronous flow responses** available? | Agent → Tools → Add → Flow | |
| 3.6 | Are **event triggers** (autonomous agent triggers) available, e.g. "When a work item is updated" from ADO? | Agent → Overview → Triggers → Add | |
| 3.7 | Can **generative orchestration** be turned on? Can **web search / public knowledge** be turned **off**? | Agent → Settings → Generative AI | |
| 3.8 | Which **channels** can we publish to for the demo: Teams, the test pane only, or a web page? | Agent → Channels | |

## 4. Rules and constraints

| # | Question | Answer |
|---|---|---|
| 4.1 | Can the synthetic dataset and generated documents be stored in the sandbox? | |
| 4.2 | Are there rules on which models or data regions may be used? | |
| 4.3 | When does sandbox access start and end? Any usage caps? | |
| 4.4 | Can the reference implementation (Python CLI) run anywhere approved, e.g. a company laptop or an approved VM, to show the parts not built in Copilot Studio? | |

## Fastest way to answer

- **Must-haves:** 1.2, 2.1, 2.3, 2.7, 3.1 and 3.2. These six alone pick the tier.
- **Screenshots are fine.** Paste them, and Claude will read them and fill in the rest.
