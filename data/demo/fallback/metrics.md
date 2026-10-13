# DHF evaluation metrics

Unknown/invented IDs: **0**. Schema errors: 0.

Baseline gaps: precision 1.00, recall 1.00 (21 exact findings). Current gaps: 23.

Saved change_1 impact: precision 1.00, recall 1.00; 75 exact section/status/cause records. Regression against a reviewer-audited expectation; not independent accuracy.

Historical sad-v1 consistency: {"precision": 1.0, "recall": 1.0, "true_positive": 2, "false_positive": 0, "false_negative": 0}. Current draft findings: 0.

| Document | Claims | Sourced % | Inferred % | Suggested % | Reject / downgrade | USD | Seconds | Cache hit rate |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| drr | 7 | 0.0 | 0.0 | 100.0 | 0 / 0 | 0.000000 | 0.124 | 0.0 |
| rtm | 0 | 0.0 | 0.0 | 0.0 | 0 / 0 | 0.000000 | 0.040 | — |
| sad | 36 | 100.0 | 0.0 | 0.0 | 0 / 0 | 0.000000 | 0.118 | 0.0 |
| sdd | 180 | 100.0 | 0.0 | 0.0 | 0 / 0 | 0.000000 | 0.102 | 0.0 |
| sfmea | 125 | 0.0 | 0.0 | 100.0 | 0 / 0 | 0.000000 | 0.125 | 0.0 |
| sstr | 11 | 45.45 | 0.0 | 54.55 | 0 / 0 | 0.000000 | 0.223 | 0.0 |
| sutr | 0 | 0.0 | 0.0 | 0.0 | 0 / 0 | 0.000000 | 0.043 | — |

| Document | AI / deterministic / human sections | Assumed authoring hours | Estimated hours saved | Support rate | Supported / partial / unsupported | Coverage verified / sampled eligible (document eligible); unverified rationale | Verifier USD / seconds |
|---|---|---:|---:|---|---|---|---|
| drr | 2 / 4 / 4 | 1.0 | 1.0 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |
| rtm | 0 / 1 / 1 | 0.1 | 0.1 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |
| sad | 12 / 15 / 1 | 5.1 | 5.1 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |
| sdd | 61 / 101 / 0 | 28.4 | 28.4 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |
| sfmea | 25 / 35 / 1 | 11.0 | 11.0 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |
| sstr | 4 / 7 / 1 | 1.9 | 1.9 | 100.0% | 1 / 0 / 0 | 1 / 1 (5); 0 | 0.000000 / 0.001 |
| sutr | 0 / 2 / 1 | 0.2 | 0.2 | pending | 0 / 0 / 0 | 0 / 0 (pending); 0 | 0.000000 / 0.000 |

Assumed draft-authoring hours, not measured labor savings. Human review and approvals are excluded; unchanged human work is not counted as saved.
Hours per section type: `{"ai": 0.3, "deterministic": 0.1, "human": 0.0}`. Support rates use returned verdicts only; coverage states the sampled eligible denominator. Unavailable checks remain visible. Support assessments are advisory; mock rates are lexical fixture checks.

Coverage: `{"hazard_to_control_to_verification": {"covered": 8, "percent": 100.0, "total": 8}, "srs_to_code": {"covered": 33, "percent": 94.29, "total": 35}, "srs_to_test": {"covered": 31, "percent": 88.57, "total": 35}}`.

Deterministic baseline goldens: `{"sad": {"checked": 4, "mismatches": []}, "sdd": {"checked": 5, "mismatches": []}, "sstr": {"checked": 7, "mismatches": []}}`.

typed/cited structural checks; semantic support is pending live human verification. No approval is implied.
