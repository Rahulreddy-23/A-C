# Software Architecture Document — Kestrel v1.0

Synthetic approved baseline for the change demonstration. Approval represents fixture history, not a product decision made by the assistant.

## Purpose and scope
This architecture records the release 1.0 controller on the synthetic bench. It allocates operator configuration, bounded delivery, sensor monitoring, alarm latching and validated drug limits. The risk file classifies the software Class C overall; display-only responsibilities may be Class B where segregation is evidenced.

## Context and external interfaces
The operator supplies a proposed configuration through UI. The bench supplies pressure and air readings and consumes commanded motor output. A configured drug library provides dose boundaries. Invalid or absent inputs inhibit delivery and produce explicit fault evidence. Network services are not required for the stop path.

## Architecture overview
COMP-01: UI accepts entries, displays validated settings and shows mode and delivered volume. It sends proposals to Infusion Control and never clears an active unsafe alarm.

COMP-02: Infusion Control owns validated settings, delivery mode, target volume and motor command. Start requires complete valid configuration. Pause and stop inhibit output while preserving delivered volume. A fault transitions immediately to inhibited delivery.

COMP-03: Pressure Monitoring owns pressure and air sampling, calibration and threshold checks. Sustained pressure above the configured occlusion threshold routes a critical event to Alarm Manager and a stop request to Infusion Control. Invalid readings are faults, not safe readings.

COMP-04: Alarm Manager prioritizes unsafe events and retains a latch until acknowledgement and safe state. Critical audio follows the latch; UI acknowledgement cannot remove an active unsafe condition.

COMP-05: Drug Library supplies stable drug records and configured bounds. Lookup failure or invalid dose prevents configuration application. The library is validated before it is used.

## Interfaces and runtime behavior
Input proposals contain rate, target volume and optional dose settings. Sensor samples carry a measured value and timestamp. The control path checks validation and fault inputs before returning a motor command. Sensor processing and alarm state are independent of the UI refresh cadence. The pressure module initially uses the release 1.0 threshold; later edits must produce a revised design record and verification evidence.

## Segregation and risk controls
The UI is a view and configuration entry surface. The control and alarm paths remain responsible for unsafe-state decisions. Stored settings are treated as untrusted until validated, and restart begins with output inhibited. Alarm latching and validated configuration are recorded in ADR-01 and ADR-02.

## SOUP and deployment
Pinned dependency versions are recorded in the device repository. The synthetic bench package runs locally and records system-run evidence. This baseline must be reconciled with the current repository before release.

## Open architecture actions
Verify boundary and recovery traces, confirm interface descriptions against extracted signatures, and reconcile the complete component set with current code. This baseline records the component inventory and Pressure Monitoring name at its original design review; later implementation revisions require reconciliation.
