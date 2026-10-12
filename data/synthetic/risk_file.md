# Synthetic Kestrel risk analysis

This is an invented hazard analysis for the hackathon fixture. Severity values are assigned here and copied by the DHF pipeline; AI never scores or accepts risk.

| Severity | Fictional harm category |
|---|---|
| 1 | Transient inconvenience with no injury |
| 2 | Temporary minor injury or reversible disruption |
| 3 | Injury or evidence loss requiring professional intervention |
| 4 | Serious injury or substantial deterioration |
| 5 | Life-threatening injury or death |

## HAZ-01 — Over infusion
Hazardous situation: over infusion during commanded delivery. Cause sequence: Rate or accumulated-volume limits bypassed. Foreseeable harm: Life-threatening fluid overdose. Severity 5 is assigned in the synthetic risk file because the consequence is life-threatening fluid overdose. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-02 — Under infusion
Hazardous situation: under infusion during commanded delivery. Cause sequence: Motor stops without a sustained operator alert. Foreseeable harm: Interrupted therapy requiring intervention. Severity 4 is assigned in the synthetic risk file because the consequence is interrupted therapy requiring intervention. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-03 — Air delivery
Hazardous situation: air delivery during commanded delivery. Cause sequence: Air sensor fault or threshold not enforced. Foreseeable harm: Air embolism with serious injury. Severity 5 is assigned in the synthetic risk file because the consequence is air embolism with serious injury. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-04 — Undetected occlusion
Hazardous situation: undetected occlusion during commanded delivery. Cause sequence: Pressure sampling or alarm latency exceeds control limits. Foreseeable harm: Delayed therapy and potential serious deterioration. Severity 4 is assigned in the synthetic risk file because the consequence is delayed therapy and potential serious deterioration. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-05 — Alarm unavailable
Hazardous situation: alarm unavailable during commanded delivery. Cause sequence: Alarm output unavailable during a critical fault. Foreseeable harm: Unsafe delivery continuing without operator warning. Severity 5 is assigned in the synthetic risk file because the consequence is unsafe delivery continuing without operator warning. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-06 — Incorrect drug limit
Hazardous situation: incorrect drug limit during commanded delivery. Cause sequence: Library corruption or invalid dose limits accepted. Foreseeable harm: Incorrect medication delivery causing serious injury. Severity 4 is assigned in the synthetic risk file because the consequence is incorrect medication delivery causing serious injury. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-07 — Lost audit evidence
Hazardous situation: lost audit evidence during commanded delivery. Cause sequence: Event storage is lost or its ordering is corrupted. Foreseeable harm: Unavailable event evidence delays corrective action. Severity 3 is assigned in the synthetic risk file because the consequence is unavailable event evidence delays corrective action. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.

## HAZ-08 — Unintended restart
Hazardous situation: unintended restart during commanded delivery. Cause sequence: Unvalidated stored configuration is resumed automatically. Foreseeable harm: Unexpected delivery after restart causes overdose. Severity 5 is assigned in the synthetic risk file because the consequence is unexpected delivery after restart causes overdose. Existing controls require explicit trace and verification; no residual-risk acceptance is asserted.
