# Device Smoke + Rollout Checklist (F22)

The repeatable procedure to validate an AppHear 3 build on a physical phone before installing it
on other devices. The agent cannot drive the device — this is **developer-run**. Run the whole
list on every build that changes the runtime; log lines are under logcat tags `AppHear*`.

Set expectations first (these are known, accepted limits — NOT smoke failures):
- **~7-8 fps hardware ceiling** — landmarkers are ~95% of the frame (see `recognition-accuracy.md` /
  memory `project-fps-temporal-mismatch`). Below the 15 fps design floor; recognition is fps-limited.
- **~50-70% top-1** at this fps — the **top-3 list** is the mitigation (right answer often #2/#3).
- **Right-handed by default** — left-handed users flip the handedness toggle.

---

## 1. Pre-flight
- [ ] Fresh APK built (`gradlew assembleDebug`), all unit tests green (`gradlew testDebugUnitTest`).
- [ ] Uninstall the old build first (avoids stale assets), then install.
- [ ] `FeatureFlags`: `RECOGNITION_ENABLED = true`, `PROFILE_STAGES = false` (no perf spam), and the
      handedness/GPU flags as intended.

## 2. Startup (tag `AppHearRecog` / `AppHearLandmarker`)
- [ ] App launches to camera preview + live hand+pose overlay; no crash.
- [ ] `landmarkers on GPU delegate` (or `…falling back to CPU` — both acceptable).
- [ ] `recognizer loaded: window=96 classes=250`.
- [ ] fps HUD shows a number + quality tier; degraded banner only when maxed-out under the floor.

## 3. Recognition (sign 250-set glosses: DOG, CUT, MILK, BELT, …)
- [ ] Signing commits a gloss: `COMMIT '<gloss>' … candidates=[A, B, C]`.
- [ ] On-screen: big #1 + dimmed #2/#3; committed word == #1 and is among the three.
- [ ] **One** commit per sign (no repeated-spam of the held sign); `S5 RELEASE … after commit`.
- [ ] Candidates update live while signing, then freeze on commit.

## 4. Gates & UI
- [ ] **No-hands gate:** wave arms with hands DOWN / out of frame → **no** `S5 ONSET`, no commits.
- [ ] **Handedness toggle:** tap → label flips Right/Left and `mirrored=` flips in the log; a
      left-handed signer should start committing with it on Left.
- [ ] **Sentence (S8):** commits accumulate into the top band; consecutive repeats collapse; **Clear**
      empties it.

## 5. Cross-signer (the point of the app)
- [ ] At least **2-3 different people** sign the same known glosses. Confirm it commits for each,
      not only the developer (body size / handedness / camera distance vary). Note any signer it
      fails badly for.

## 6. Rollback path (must both work)
- [ ] **Disable recognition:** set `FeatureFlags.RECOGNITION_ENABLED = false`, rebuild → app runs as
      F17 (camera + landmark overlay + fps, no gloss/sentence), no crash. This is the kill-switch.
- [ ] **Load-failure fallback:** if the model/manifest is missing or mismatched, `RecognitionPipeline.load`
      throws → `MainActivity` catches it (Toast "Recognition load failed"), app still runs as F17.
      `ModelContract.validateOrThrow` refuses a schema/shape-mismatched model rather than mis-recognizing.

## 7. Sign-off
Build passes smoke when: launches + no crash on the target phone(s); commits real glosses for
≥2 signers; the four gates (no-hands, handedness, one-commit, sentence/clear) behave; and the
rollback kill-switch + load-failure fallback both degrade gracefully. Record the phone model, fps,
and any signer it struggled with in `progress-tracker.md`.
