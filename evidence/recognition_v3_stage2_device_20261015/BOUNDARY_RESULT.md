# RECOGNITION_V3_STAGE2_TRANSITION_CAPTURE_01 — captured evidence

EVIDENCE_FOR_PROJECT_LEAD_REVIEW_ONLY

Diagnostic evidence only. No behavioral fix is authorized by this evaluator.

| Condition/sign | Intended | Classification | ACTIVE observations | Associated events |
|---|---|---|---|---|
| A_HANDS_DOWN/1 | HELLO | C_S2_ACTIVE_REACQUISITION_FAILURE | 0 | 0 |
| A_HANDS_DOWN/2 | HOME | UNCERTAIN_OR_NOT_PERFORMED | unknown | unknown |
| B_HANDS_UP/1 | HELLO | C_S2_ACTIVE_REACQUISITION_FAILURE | 0 | 0 |
| B_HANDS_UP/2 | HOME | UNCERTAIN_OR_NOT_PERFORMED | unknown | unknown |
| C_REPEAT_HANDS_UP/1 | HELLO | D_EVENT_DELIVERY_OK_DOWNSTREAM | 3 | 1 |
| C_REPEAT_HANDS_UP/2 | HELLO | UNCERTAIN_OR_NOT_PERFORMED | unknown | unknown |
| D_SIGN_THEN_HOLD/1 | HELLO | C_S2_ACTIVE_REACQUISITION_FAILURE | 0 | 0 |

Shared events can appear against both physical signs; this is not two delivered events.

## Transition response intervals (milliseconds)

| Transition | End→commit | Commit→rearm | Next start→rearm (signed) | Next start→open | Next start→debug UI |
|---|---|---|---|---|---|
| A_HANDS_DOWN 1→2 | unknown | unknown | unknown | unknown | unknown |
| B_HANDS_UP 1→2 | unknown | unknown | unknown | unknown | unknown |
| C_REPEAT_HANDS_UP 1→2 | unknown | unknown | unknown | unknown | unknown |

## Compact event/lexical outcomes

| Block/sign | Outcome | Event IDs |
|---|---|---|
| A_HANDS_DOWN/1 | NO_COMPLETED_EVENT | [] |
| A_HANDS_DOWN/2 | UNCERTAIN_OR_NOT_PERFORMED | [] |
| B_HANDS_UP/1 | NO_COMPLETED_EVENT | [] |
| B_HANDS_UP/2 | UNCERTAIN_OR_NOT_PERFORMED | [] |
| C_REPEAT_HANDS_UP/1 | DISTINCT_EVENT_EXPECTED_GLOSS | [2] |
| C_REPEAT_HANDS_UP/2 | UNCERTAIN_OR_NOT_PERFORMED | [] |
| D_SIGN_THEN_HOLD/1 | NO_COMPLETED_EVENT | [] |

Normal-app sentence delivery is NOT MEASURED by this diagnostic Activity.
This single design cohort is not an accuracy claim.

Human boundaries have observation resolution; missing metrics stay null. These are response/transition intervals, not inference latency.

UI timings belong to the diagnostic Activity; normal app sentence delivery is not measured by this capture.

Detailed source-linked probabilities, recovery resets, windows, recognition results and reviewed negatives are in result.json.
