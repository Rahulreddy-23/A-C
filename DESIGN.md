---
name: Kestrel DHF workspace
colors:
  primary: '#315cbb'
  ink: '#22262e'
  secondary: '#535c6c'
  paper: '#fafbfc'
  surface: '#ffffff'
  chrome: '#f0f2f5'
  line: '#d8dde5'
  nav: '#f0f2f5'
  nav-active: '#e1e7f0'
  warning: '#935015'
  gap: '#a54420'
  stale: '#704a93'
  success: '#28634e'
  selection: '#edf2ff'
typography:
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif'
    fontSize: 13px
    lineHeight: 1.5
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif'
    fontSize: 22px
    fontWeight: 650
    letterSpacing: '-0.025em'
  artifact:
    fontFamily: 'ui-monospace, SFMono-Regular, Consolas, monospace'
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.5
rounded:
  control: 5px
  node: 6px
  summary: 8px
spacing:
  compact: 8px
  group: 12px
  section: 24px
---
## Overview
Operate mode. A read-only review workspace exposes evidence, generated drafts, rule findings, change impact and risk paths. Overview is the entry point; the graph is a dedicated tool. Product truth remains in BRIEF.md and PRODUCT.md. The owner's rejection of graph-first layouts governs this replacement.

## Colors
The app opens in light mode with a neutral navigation rail and a plain canvas. Dark appearance is an explicit user choice. Blue marks selection and trace focus; amber marks gaps and authoring work, red recorded failures, green recorded passes, and violet directly stale evidence. Each state has text. Light/dark variables preserve roles; no gradient hero, neon glow or decorative status dots.

## Typography
System sans for controls and reading, monospace only for IDs, source hashes and numeric measurements. The header is compact. Artifact titles wrap fully at 14px/20px; IDs are 13px. No text ellipsis or line clamp is used to force uniform nodes or result rows.

## Layout
A 52px header, 184px workspace navigation rail, flexible main view, optional 292px inspector and 30px status bar. Overview divides coverage/verification/documents from review work/risk/provenance. Documents use a picker and section reader. Findings, risk and impact have semantic tables. Traceability has an artifact-search drawer, a canvas and an evidence-index alternative. Navigation collapses below 760px; the inspector overlays only on narrow screens. Graph nodes are 184px wide with 140px gutters; actual rendered height controls placement. Default scope is direct links: only relationships incident to the selected artifact are drawn, with ports ordered by peer position and relation types in peer footers. Full trace retains every scoped relationship; skip edges use distinct top tracks and labels avoid other labels and nodes. Fit keeps the selected artifact onscreen vertically and horizontally. Fit preserves at least 90% scale, so larger diagrams use pan rather than illegible automatic shrinking.

## Elevation & Depth
Structural panes are flat and separated by tonal surfaces. Nodes use flat borders; only the viewport controls have a slight shadow. Drawers cast a directional shadow on narrow views. Report rows use subtle boundaries without floating dashboard cards.

## Shapes
Controls use 5px radii, graph nodes and small data groups 6px, and the release summary 8px. No pill-heavy scaffold. Arrows and curved/orthogonal routes are graph geometry, not decoration.

## Components
Overview, Documents, Findings, Change impact, Traceability and Risk evidence are working snapshot views. Native inputs/selects filter records; tables and claim citation buttons open the source inspector. Graph click inspects, double-click focuses, and Back restores the previous focus. Pointer drag and keyboard arrows pan; zoom and actual-size/fit controls are labelled. Repeated selection and keyboard actions do not animate. Pointer-triggered fit uses a 180ms transform transition; reduced motion removes it. Document prose retains its recorded claim kind and source revision. Mock drafts remain labelled.

## Do's and Don'ts
Use real deterministic outputs and safe DOM text. Keep full names accessible and unknown artifact types visible. Preserve recorded edge direction, source provenance and directly stale versus possibly affected states. Never add invented links, approval badges, decorative metric cards, AI-writing controls that do nothing, runtime CDN resources or source-system writes. Browser paint and projector legibility remain owner checks until actually observed.
