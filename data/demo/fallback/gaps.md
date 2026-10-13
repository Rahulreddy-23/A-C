# Evidence gaps

| Rule | Count | Why it matters | Recommended action |
|---|---:|---|---|
| G01 | 4 | SRS has no verifying test | Add or link a verifying test for the requirement. |
| G02 | 2 | SRS has no implementing change | Link an implementing change or record a justified implementation gap. |
| G03 | 2 | Orphan code or PR | Link existing requirements or propose a requirement for human review. |
| G04 | 1 | Test case has no requirement | Link the test to its verified requirement or justify its standalone scope. |
| G05 | 2 | Failed result has no defect | Raise or link a defect for the failed result, or record a justified anomaly assessment. |
| G06 | 1 | Risk control has no realizing requirement | Trace the risk control to its realizing requirement. |
| G07 | 1 | Risk-control requirement has no verification | Add verification evidence for the risk-control requirement. |
| G08 | 1 | System requirement has no derived SRS | Derive software requirements or justify non-software realization. |
| G09 | 1 | SRS has no parent system requirement | Link the parent system requirement or justify the requirement origin. |
| G10 | 1 | Open defect omitted from residual anomalies | Include the open defect in residual anomalies with human-reviewed rationale. |
| G11 | 2 | Test passed against an older requirement revision | Rerun verification against the current requirement revision. |
| G12 | 5 | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |

| Rule | Artifact revision | Finding | Recommended action |
|---|---|---|---|
| G01 | [SRS-012@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/33?rev=1) | SRS has no verifying test | Add or link a verifying test for the requirement. |
| G01 | [SRS-032@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/53?rev=1) | SRS has no verifying test | Add or link a verifying test for the requirement. |
| G01 | [SRS-034@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/55?rev=1) | SRS has no verifying test | Add or link a verifying test for the requirement. |
| G01 | [SRS-035@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/56?rev=1) | SRS has no verifying test | Add or link a verifying test for the requirement. |
| G02 | [SRS-034@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/55?rev=1) | SRS has no implementing change | Link an implementing change or record a justified implementation gap. |
| G02 | [SRS-035@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/56?rev=1) | SRS has no implementing change | Link an implementing change or record a justified implementation gap. |
| G03 | [PR-7@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw/pullrequest/7) | Orphan code or PR | Link existing requirements or propose a requirement for human review. |
| G03 | [UNIT-diagnostics_trace@r0e5431996712b618e28322558a25dd5a99cf1cbc](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/kestrel/diagnostics_trace.py&version=GCc97b66528e09945be2a3fc3d2934dcdaaca42be7) | Orphan code or PR | Link existing requirements or propose a requirement for human review. |
| G04 | [TC-040@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/116?rev=1) | Test case has no requirement | Link the test to its verified requirement or justify its standalone scope. |
| G05 | [RES-1-021@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_apis/test/runs/1/results/21) | Failed result has no defect | Raise or link a defect for the failed result, or record a justified anomaly assessment. |
| G05 | [RES-3-021@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_apis/test/runs/3/results/21) | Failed result has no defect | Raise or link a defect for the failed result, or record a justified anomaly assessment. |
| G06 | [RC-12@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/76?rev=1) | Risk control has no realizing requirement | Trace the risk control to its realizing requirement. |
| G07 | [SRS-012@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/33?rev=1) | Risk-control requirement has no verification | Add verification evidence for the risk-control requirement. |
| G08 | [SYS-015@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/21?rev=1) | System requirement has no derived SRS | Derive software requirements or justify non-software realization. |
| G09 | [SRS-035@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/56?rev=1) | SRS has no parent system requirement | Link the parent system requirement or justify the requirement origin. |
| G10 | [BUG-03@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/119?rev=1) | Open defect omitted from residual anomalies | Include the open defect in residual anomalies with human-reviewed rationale. |
| G11 | [TC-021@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/97?rev=1) | Test passed against an older requirement revision | Rerun verification against the current requirement revision. |
| G11 | [TC-030@r1](http://127.0.0.1:56251/kestrel-org/Kestrel/_workitems/edit/106?rev=1) | Test passed against an older requirement revision | Rerun verification against the current requirement revision. |
| G12 | [SOUP-01@r39d9f63e0d040c5928935c2088ebc6545697e42fa9592d6d92acc8532909c333](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/requirements.txt) | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |
| G12 | [SOUP-02@rcf7f5c7e57940eca8daf7ceda97e8eceba4638570149037b782c99f3908d6768](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/requirements.txt) | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |
| G12 | [SOUP-03@r6881c7421278b505269dab5dfe0692b1f6a771f6a92d40abbe9e9ef7bfbe9d4d](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/requirements.txt) | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |
| G12 | [SOUP-04@rd50d45cea7f1617acc23207dee76c75e1f34ef1ea3c082181d5e735a0fd0db04](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/requirements.txt) | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |
| G12 | [SOUP-05@rdc66ace98f87b2a9e854a8405333271956950383d766ac4fc8805a0d91f39b37](http://127.0.0.1:56251/kestrel-org/Kestrel/_git/kestrel-device-sw?path=/requirements.txt) | SOUP requirements or known-anomaly evaluation not recorded | Record SOUP functional/performance requirements and evaluate its known anomaly list. |
