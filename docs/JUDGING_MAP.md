# Judging evidence map

All artifacts are synthetic review drafts. Links below are committed fallback evidence or reproducible definitions, not claims of tenant execution. The six weights total 100. The timed sequence is in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

| Criterion | Weight | Feature | Evidence |
|---|---:|---|---|
| Traceability | 25 | Confirmed requirement/unit/test/risk chains, revisions, G06/G07 gaps | [Explorer](../data/demo/fallback/explorer-baseline.html), [RTM](../data/demo/fallback/rtm.md), [Gaps](../data/demo/fallback/gaps.md), [Answer key](../data/synthetic/expected_gaps.yaml) |
| Workflow fit | 25 | Source-write 403, docs PRs, human readiness, Word drafts | [Transcript](../data/demo/fallback/transcript.txt), [SSTR](../data/demo/fallback/sstr.docx), [SAD](../data/demo/fallback/sad.docx), [Manifest](../data/demo/fallback/sstr.manifest.json), [Port workflow](../port/copilot_studio/flows/06-open-docs-pr.md) |
| Accuracy and governance | 20 | Exact change_1 impact, selective redline, typed/cited numeric checks | [Impact](../data/demo/fallback/impact.json), [Stale explorer](../data/demo/fallback/explorer-stale.html), [Tracked Word](../data/demo/fallback/redline-sstr.docx), [Validator regression](../tests/test_generate.py), [Metrics](../data/demo/fallback/metrics.md) |
| Effort reduction | 10 | Measured cost/time, explicit manual assumptions, YAML extensions | [Metrics](../data/demo/fallback/metrics.md), [Assumptions](../specs/metrics/manual_effort.yaml), [SUTR spec](../specs/documents/sutr.yaml), [RTM spec](../specs/documents/rtm.yaml) |
| Audit readiness | 10 | Complete source snapshots, manifests/checksums, uncovered clauses | [Audit ZIP](../data/demo/fallback/audit-pack.zip), [Checksums/index](../data/demo/fallback/index.json), [Clause coverage](../data/demo/fallback/clause_coverage.md), [DRR](../data/demo/fallback/drr.docx) |
| Good-to-have | 10 | Offline explorer, advisory support with coverage, port readiness | [Explorer](../data/demo/fallback/explorer.html), [Metrics](../data/demo/fallback/metrics.md), [Live reviewer observation](REVIEW.md), [Day-1 capability gates](../port/copilot_studio/BUILD_PLAN.md), [Native validator](../port/copilot_studio/native_validator.md) |
