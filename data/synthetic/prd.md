# Kestrel Infusion Controller — synthetic product requirements

Kestrel is an entirely fictional volumetric infusion controller built only to exercise an evidence workflow. The demo bench simulates delivery, sensor readings, alarms and event storage; it is not intended for treatment or connected to any clinical system.

The primary operator configures a flow and target volume, confirms validated settings and monitors delivery state. The controller must expose the active configuration and delivered volume, inhibit output when limits or sensor checks fail, and retain the last validated configuration when an edit is rejected. A service role can inspect calibration and export evidence, but it cannot silently alter an active delivery session.

The system separates six responsibilities: UI, Infusion Control, Sensor Monitoring, Alarm Manager, Drug Library, and Logging & Comms. Unsafe conditions feed the control path and the alarm latch directly. UI refresh and communications are secondary views; their availability must not decide whether delivery stops. The synthetic hazard analysis assigns Class C overall, while display-only behavior may be allocated Class B with documented segregation.

Verification combines boundary and invalid-input trials with recorded system runs for releases 1.0 and 1.1. Trace evidence connects needs, system and software requirements, controls, code changes, cases, results and defects. Known residual anomalies require explicit review and listing. DHF drafts may summarize this evidence and propose gaps, but release authorization and risk acceptance stay with human review in the existing quality system.

The controlled change scenario edits the occlusion threshold, modifies Sensor Monitoring and reruns its pressure trial. The demo must show the affected evidence, stale document sections and review redlines without rewriting unrelated approved material.
