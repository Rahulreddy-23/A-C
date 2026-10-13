---
name: Kestrel evidence explorer
colors:
  ink: '#172e38'
  muted: '#526570'
  paper: '#f5f7f8'
  line: '#cad5da'
  teal: '#006b65'
  gap: '#9c391f'
  stale: '#71358a'
typography:
  display:
    fontFamily: Georgia, serif
    fontSize: 32px
    lineHeight: 1.2
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif'
    fontSize: 15px
    lineHeight: 1.5
rounded:
  control: 4px
  board: 6px
spacing:
  field: 16px
  workspace: 24px
---
## Overview
Operate mode: reviewers search evidence, follow recorded links and inspect provenance. Source-derived design record; visual browser review is pending the local-file access limitation.
## Colors
Light reading surface with teal selection. Gap fill and dashed stale outlines have text equivalents; latest results are named and tinted. No color-only state.
## Typography
Georgia heading; system body for dense controls; tabular summary numerals. ID labels belong to data, not decoration.
## Layout
Filter row, scrollable nine-lane SVG graph, 300px provenance inspector. Below 760px the inspector stacks after the graph. Stale sections occupy a separate expandable list.
## Shapes
Small radii on controls and graph nodes; thin neutral boundaries; no shadows.
## Components
Search and rule/state filters combine. Reset clears every filter. Enter/Space selects SVG nodes; links show source revision; reciprocal inspector links state their actual direction and type.
## Do's and Don'ts
Keep unknown artifact types in Other evidence. Preserve confirmed edge direction and source provenance. Never fetch resources or use source strings as HTML. No approval or compliance badge.
