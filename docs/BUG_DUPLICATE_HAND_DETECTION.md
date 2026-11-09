# Bug investigation — duplicate hand skeletons on one physical hand

Status: **root cause NOT yet confirmed by measurement.** Code analysis gives one precise candidate mechanism; a debug-only
diagnostic was added so the first phone run settles it. No behaviour was changed. Nothing committed.

## Reported symptom
One hand in view → two overlapping skeletons (yellow `LH`, magenta `RH`), possibly wrong handedness.

## What the code does (CONFIRMED-CODE)
| Stage | File | Behaviour |
|---|---|---|
| Hand proposal | `PerceptionVNextMath.handRoi` | DWPose-t emits **both** a left group (keypoints 91–111) and a right group (112–132) for every frame. A group becomes an ROI when ≥ 5 of its 21 points have support ≥ 0.10 and lie in the frame. |
| Refinement | `Candidate01FrameAnalyzer.runHand` ×2, `HandRefinerRunner.run` | Each ROI is refined independently. `observed = presence ≥ 0.50 && ≥ 18 valid joints`. |
| Cross-check between hands | — | **None.** No overlap test, no de-duplication, no mutual exclusion. |
| Handedness | `LEFT_HAND_START`/`RIGHT_HAND_START` | Slot identity comes only from which DWPose keypoint group a hand came from. The refiner's own handedness output is stored (`handednessDiagnostic`) and **never read**. |
| Rendering | `PerceptionVNextOverlayRenderer` | Draws the current frame only (yellow = slot 0, magenta = slot 1), no tracker, no stale state. Each slot is drawn if `observed`. |
| Mirroring | `P8bOverlayContract.displayTransform` | Display-only X mirror for the front camera; stored coordinates stay unmirrored. Consistent; not a cause. |

## Candidate root cause (HYPOTHESIS, not measured)
A one-hand frame can make **both** DWPose groups place their keypoints on the same physical hand. Both pass ROI creation,
the refiner finds a hand in both crops, both pass `observed`, so two skeletons are drawn on one hand, and both slots are fed
to Recognition-v2 as if two hands were signing. Eliminated by reading the code: overlay persistence/stale data, and mirroring.

## Why I did not fix it yet
No device is attached and the host has no ONNX/TFLite runtime or any hand imagery, so the model behaviour cannot be
reproduced here. A fix chosen without the measurement could suppress genuine two-hand signs (many ASL signs use two
hands near each other and touching), which would damage recognition. Evidence first.

## Diagnostic added (observation only; no behaviour change)
`HandPairDiagnostics.kt` + 3 lines in `Candidate01FrameAnalyzer.kt`. Every 30 s the existing debug `AppHearDetect` log line now
ends with e.g. `hands[n=450 none=40 L=120 R=95 both=195 same=170 part=15 sep=10 na=0]`:

- `L`/`R`: exactly one slot observed.
- `both`: both slots observed. Split by IoU of the two skeletons' boxes: `same` (≥ 0.5), `part` (0.1–0.5), `sep` (< 0.1).
- The bins are descriptive labels, not a decision rule.

### Test protocol (physical phone, debug build)
1. One hand only, held still, then moving, 30–60 s. `adb logcat -s AppHearDetect`.
2. Two hands apart, 30–60 s.
3. Two hands together (clapping/touching signs such as THANK-YOU / HELLO transitions), 30–60 s.

**Reading the result.** One-hand run with `both` large and mostly `same` ⇒ hypothesis confirmed (duplicate on one hand).
`both` small ⇒ hypothesis rejected; the next suspect is the overlay/UI path (re-investigate). Two-hand run with `sep` high ⇒
the two-hand case is healthy and a fix must keep it. Two-hands-together `same`/`part` shows how much a fix could harm real signs.

## Next step after confirmation
Design a fix from the measured distributions, e.g. dropping the lower-presence duplicate when the two skeletons coincide, and
re-assign handedness from the DWPose group/side evidence. Needs: tests with one-hand, two-hand-apart and two-hands-touching
fixtures, and an offline recognition-regression check on the 236-class set (the pair feeds the recognizer and the segmenter).

## Tests
`HandPairDiagnosticsTest` (8): identical / shifted / separated skeletons, invalid and non-finite points, counter bins, log
format. Full JVM suite 423 pass; `:app:compileReleaseKotlin` OK.

## Files
Added: `android/app/src/main/java/com/example/apphear/perceptionvnext/HandPairDiagnostics.kt`,
`android/app/src/test/java/com/example/apphear/perceptionvnext/HandPairDiagnosticsTest.kt`, this document.
Modified: `Candidate01FrameAnalyzer.kt` (counter field, one `record` call, log line), `context/progress-tracker.md`.
