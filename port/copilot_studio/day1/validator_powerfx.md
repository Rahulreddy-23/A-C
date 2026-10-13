# Day-1 native claim validator cards

These are Power Fx formulas for **typed** values after `Parse JSON` and `Select` in flow 04. `ClaimCitations`, `EvidenceIds`, `ClaimNumbers`, and `FactNumbers` are single-column tables named `Value`; `ClaimKind` is text and `ClaimConfidence` is number or blank. Keep the flow's rejection/downgrade event arrays and render only accepted claims. Paste/test each card in the actual tenant before enabling unattended generation. The offline cases below exercise the reference validator, not Power Fx execution.

## Citation subset and kind

```powerfx
CountRows(Filter(ClaimCitations As citation,
    IsBlank(LookUp(EvidenceIds, Value = citation.Value)))) = 0
```

Apply the same membership check to IDs extracted from claim text. Exact array membership is required; substring matching would incorrectly accept `SRS-02` as `SRS-021`. A sourced claim with no citations is downgraded to inferred with confidence 0.5 and an audit event, not treated as directly supported.

```powerfx
Or(ClaimKind = "sourced", ClaimKind = "inferred", ClaimKind = "suggested")
```

## Confidence

```powerfx
If(ClaimKind = "sourced",
    Or(IsBlank(ClaimConfidence), And(ClaimConfidence >= 0, ClaimConfidence <= 1)),
    And(Not(IsBlank(ClaimConfidence)), ClaimConfidence >= 0, ClaimConfidence <= 1))
```

`Parse JSON` must reject a nonnumeric confidence. A missing inferred/suggested confidence is invalid; only the explicit sourced-without-citation downgrade or allowed-kind coercion may supply 0.5. Do not rely on provider schema bounds.

## Numeric extraction and subset

First remove **known artifact-ID spans** from a separate working copy of claim text in the cloud flow. Preserve the original text for rendering. Flatten numeric leaf values of computed `facts_json` into `FactNumbers`; exclude booleans. The pattern is an authoring-time constant in Power Fx. `MatchAll` produces `FullMatch`; `Value(..., "en-US")` normalizes 39 and 39.0 to the same decimal value.

```powerfx
ForAll(
    MatchAll(CleanClaimText, "(?<![A-Za-z0-9_])[\-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_])"),
    {Value: Value(FullMatch, "en-US")}
)
```

```powerfx
CountRows(Filter(ClaimNumbers As claimNumber,
    IsBlank(LookUp(FactNumbers, Value = claimNumber.Value)))) = 0
```

The first formula is a **tenant capability probe**: Power Fx hosts differ in regex support and decimal precision. If the pattern or `Value` conversion fails, use the blocked `numeric_unverified` compensation in [native_validator.md](../native_validator.md); do not claim numeric parity. The reference rejects 40 when facts permit only 39 and ignores digits inside `SRS-021`.

| Case | Expected reference result |
|---|---|
| `SRS-021` cited and present | accepted |
| `SRS-999` citation or text ID | `unknown_ids` rejection |
| `39` versus fact `39.0` | accepted |
| `40` versus fact `39` | `numbers_match_facts` rejection |
| inferred confidence missing or outside 0–1 | schema rejection |
| sourced without citation | inferred, confidence 0.5, downgrade event |

Run `uv run pytest tests/test_day1.py -q` for the reference cases. The decisive native test is to paste these cards into the sandbox and record their actual outputs in `port/copilot_studio/parity_tests.md`.

[Microsoft MatchAll result shape and FullMatch](https://learn.microsoft.com/en-us/power-platform/power-fx/reference/function-ismatch) · [Power Fx regex dialect and constant-pattern rule](https://learn.microsoft.com/en-us/power-platform/power-fx/regular-expressions)
