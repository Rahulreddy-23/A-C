# DHF workspace design research

2026-10-14. Scope: a read-only offline app for engineering authors, reviewers and the hackathon board. The owner's latest feedback replaces the graph-first brief: show the wider product, improve all three of graph composition, visual style and pane arrangement, and use purposeful colour.

## Sources and decisions

| Primary reference | Finding applied to this app |
|---|---|
| [Shneiderman, The Eyes Have It](https://www.cs.umd.edu/users/ben/papers/Shneiderman1996eyes.pdf) | Give reviewers an overview, filtering and access to detail. Overview now leads; individual source provenance is disclosed in an inspector. |
| [yWorks layered layouts](https://www.yworks.com/pages/layered-graph-layout) | Layered placement suits directed relationships. The full trace uses deterministic topological ranks where acyclic, with barycenter sweeps to reduce crossings. Cycles retain every edge and use evidence-type groups. This is a small local algorithm, not yFiles. |
| [yWorks label placement](https://www.yworks.com/pages/automatic-label-placement-in-diagrams) | Labels need their own space. Node titles wrap fully; rendered node height determines row spacing. Direct-link types live in peer footers so they do not interrupt arrows. Full-trace labels are placed separately in wider gutters/top tracks and checked against labels and nodes. |
| [yWorks force-directed layouts](https://www.yworks.com/pages/force-directed-graph-layout) | A force layout does not inherently express relationship direction. A stable directed layout was chosen over an animated physics network. |
| [React Flow viewport conventions](https://reactflow.dev/learn/concepts/the-viewport) | Familiar canvas interaction matters. Pointer drag pans, ordinary wheel pans, control/command-wheel zooms, and labeled zoom/fit controls remain visible. This borrows interaction conventions, not a runtime dependency. |
| [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility) | Graph navigation needs keyboard access, focus visibility and full accessible names. Native buttons select nodes; focusing an offscreen node pans it into view. An evidence table provides an alternate route to every artifact. |
| [Apple HIG layout](https://developer.apple.com/design/human-interface-guidelines/layout), [toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars) and the installed Apple-design reference summaries | Use familiar navigation, compact toolbars, clear selection and optional details. This web app borrows those qualitative patterns; it does not claim to be a native Apple app or Liquid Glass implementation. Official page bodies were not available from text browsing; the local reference summaries supplied component guidance. |

The UI/UX Pro search returned a relevant relationship-graph result and an essential-text-truncation rule. Its design-system search offered data-dense product styling but also marketing page patterns, so the hero/CTA recommendations were rejected as unrelated. Taste-skill explicitly excludes dense product apps: its redesign/anti-pattern audit is used, while Impeccable's Operate guidance governs composition. Emil's frequency-based animation guidance keeps repeated selection and keyboard navigation immediate; pointer-triggered fit uses a short transform transition, with reduced-motion support. System fonts are deliberate for this desktop review surface.

## Incumbent audit

| Before | After | Why |
|---|---|---|
| A graph page represented the whole product | Overview plus five distinct review views | Authors need documents, findings, risk and change evidence as well as a graph. |
| Large rounded cards, numbered eyebrows and decorative hierarchy | Compact toolbar, persistent navigation and data-led sections | The work and its state carry hierarchy. |
| Single-line clipped artifact titles | Fully wrapped titles, actual DOM-height placement and complete inspector text | Essential names must remain distinguishable. |
| Connection stubs or long unlabelled routes | Arrowheads, visible relationship types, separated ports and wider gutters | Reviewers must identify the recorded direction and meaning. |
| A dense full trace on every selection | Direct-link default, optional full trace, single-click inspection and explicit refocusing | Preserve context while keeping the default graph bounded. |
| Grey presentation with a single selection colour | Neutral light navigation; blue selection, amber findings, red failures, green recorded passes and violet staleness | Colour carries actual navigation or evidence state, with text equivalents. |
| Dark-blue rail, dot grid and crossed direct fan in the rejected workspace screenshot | Light default, flat neutral chrome, anchor-only direct relationships and ordered ports | Remove visual weight and the unrelated UNIT-to-COMP roof from direct views. |
| Large trace opens with selection offscreen | Fit frames the selected artifact on both axes | Keep the record being reviewed visible without shrinking text. |
| Graph data only | Existing coverage, latest results, rule actions, manifest sections/claims, impact reports and native risk paths | Every view reads existing deterministic or already validated output. |

## Apple principles audit of the replacement

| Principle | Verdict | Evidence |
|---|---|---|
| Purpose | Conforms in implementation | Review views follow real DHF tasks and existing pipeline outputs. |
| Agency | Conforms in implementation | Filters reset, graph traversal has back navigation, panes close and zoom/pan are controllable. |
| Responsibility | Conforms in implementation | Read-only source navigation; mock/development drafts are labelled; risk acceptance is not inferred. |
| Familiarity | Conforms in implementation | Persistent navigation, native controls, document picker, tables and optional source inspector. |
| Flexibility | Implemented; visual device check pending | Keyboard controls, full evidence table, responsive navigation and theme/reduced-motion modes. |
| Simplicity | Improved; owner visual verdict pending | Overview leads; the graph is one review tool; filters and provenance are disclosed where needed. |
| Craft | Functional checks pass; browser visual check pending | No label clamping, measured layout, explicit link directions and real content; no browser paint claim. |
| Delight | Task appropriate | Selection feedback and a short fit transition; no decorative page-load sequence. |

## Data and honesty boundaries

- Coverage and verification counts call existing Python queries. Risk paths call `risk_rows`; relationship diagrams use only confirmed links.
- Documents expose generated manifest sections, typed claims, cited revisions and deterministic section text. Structural mock and personal-provider output are labelled; no tenant run is inferred.
- Impact displays saved section states and cause records. Human-authoring section and suggested-claim counts describe content, not approval or unresolved-readiness decisions.
- Controls navigate and inspect the embedded snapshot. Source edits, generation, publishing and approvals remain in the existing CLI/review workflow; the static UI does not pretend to perform them.
- One HTML artifact, no runtime dependency or resource fetch, no analytics, inert base64 payload and DOM text rendering. The optional Impeccable design engine was loaded into ignored `out/`; it is not a product dependency.

## Verification scope

The browser tool rejects local file URLs and forbids alternate access routes. The supplied owner screenshots are the visual evidence for the rejected layouts. New automation checks graph geometry and interactions but is not a browser layout/paint benchmark. The first new graph-only canvas was rejected by the owner, so that rejection is not recorded as approval. The owner also rejected the broader workspace's dark palette and SRS-012 routing in the 11:52 PM screenshot. The current implementation corrects those defects; it is not recorded as visually approved. A fresh read-only reviewer inspected the supplied image and code/contracts, identified offscreen initial selection in large traces, and that camera issue was corrected with a sweep assertion. All artifact IDs are checked in direct/full scopes; automated geometry is not browser-rendered appearance.

## Owner feedback — 2026-10-14

The owner viewed the replacement and reported “looking much better now” and “rest looks good”, requesting only smaller arrows. That is owner acceptance of the wider layout and colour direction. Arrow markers are reduced from 8 to 6 units on each axis (25%); routes, line weights, content and layout remain unchanged. No true browser paint timing is inferred from that feedback.
