# Text-to-Sign fingertip correction (2026-10-10)

Existing branch: `apphear/text-to-sign-redesign`. Pre-edit checkpoint: `346fa2a`.
No new clone, dependency upgrade, UI change, push or original-repository edit.

## Diagnosis and correction

The resident Wolf3D human has a consistent bind pose: the largest joint-world ×
inverse-bind deviation from identity is 7.2023e-7. Skin weights are finite,
nonnegative and sum to one within 1.1921e-7. This does not establish that every
possible pose is correct, but did not support replacing this rig or its weights.

The alphabet converter used anatomical segment/palm frames for finger joints 1
and 2, then switched to arbitrary source-Y/target-Z axes for joint 3. Those rigs
have different bone orientations. The resulting distal roll visibly pinched
and twisted the fingertip skin even when the finger centerline looked plausible.
The old alphabet mesh renders reproduce the separated-looking fingertip caps.

Joint 3 now uses the same palm-normal calibration as the preceding joints. Its
source direction continues the preceding phalanx because the source has no tip
node; the target direction uses its actual fingertip child. World orientations
are orthogonalized with a proper rotation decomposition to remove scale/shear.
No generic rotation clamp, invented ASL handshape, skin-weight modification or
new word sign was applied. Target meshes, bones, lengths, weights and all 203
original word animations and their binary payload remain unchanged.

All 26 alphabet actions were regenerated. The manifest records retarget version
2 and the application pins the new bundle checksum. One resident model URL is
still used for lexical signs and automatic word-level fingerspelling.
Cancellation, completion-driven sequencing, neutral endpoints and original
clip timing remain intact. No alternate avatar or robotic fallback was added.

## Files changed

All paths below are within this Android project:

| File | Purpose |
| --- | --- |
| `tools/retarget-text-to-sign-alphabet.py` | Correct distal anatomical calibration and orthogonal rotation frames. |
| `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb` | Regenerated same-human A–Z animations; original word clips retained. |
| `app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.json` | Updated checksum, conversion version and numerical audit. |
| `app/src/main/java/com/example/apphear/domain/texttoasl/AslFingerspellingBundle.kt` | Pin the corrected bundle checksum. |
| `tools/audit-text-to-sign-hands.py` | Development CPU skinning regression and front/side views of both hands with real joint overlays. |
| `tools/hand_pose_inspector.html` | Development-only before/after browser viewer with letter/word, time and camera controls. |
| `tools/serve-hand-inspector.py` | Serve that viewer and existing local vendor assets on localhost. |
| `tools/TextToSignHandFix.md` | Diagnosis, testing, review and reproduction instructions. |

## Actual checks

- Android debug APK and instrumentation APK built successfully in 2m 44s.
- 231 JVM tests passed; zero failures, errors or skips. Includes word/name
  fallback, mixed sequences, repeated letters and existing regression tests.
- Real-player JavaScript exercised with mocked viewer events: ten mixed/repeated
  actions retained one viewer/load; early, duplicate, stale completion,
  cancellation and missing/ambiguous animation handling passed. This is not a
  browser/device playback test.
- CPU rendering of the actual skinned glTF mesh produced A–Z views for both
  hands from front/side, with joint overlays. HELLO, BEAUTIFUL, THANK YOU
  (`SIGN_THANKS`), HELP, YES and NO were also rendered. Original word actions
  are unchanged; NAME remains N-A-M-E fallback, not a new lexical sign.
- J/Z have nine sampled motion views and moving wrist trajectories. Their
  motion is retained; their precise linguistic path is not yet validated.
- A fixture regression bounds the 99th-percentile hand-mesh edge stretch at
  the midpoint of each alphabet clip. All corrected letters pass (<1.70);
  the old bundle fails. Previous values were 1.870–2.018; corrected values
  1.361–1.634. These are deformation diagnostics, not ASL accuracy scores or
  universal anatomical limits. They do not test every frame/contact condition.
- Pixel_3a could not launch with usable acceleration. Medium_Phone_API_36
  attempted software rendering but crashed before boot with access denied
  (0xc0000022). No emulator instrumentation ran and no phone was connected.
- The in-app browser could not reach the sandbox-local development server;
  WebGL screenshots/playback could not be captured. Review images are CPU
  mesh renders, not screenshots from an Android device.

## Development-only inspection

From the Android project, with development NumPy and Pillow installed:

```powershell
python tools/audit-text-to-sign-hands.py BEFORE.glb app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb HAND_REVIEW
python tools/serve-hand-inspector.py --before BEFORE.glb
```

Open `http://127.0.0.1:9042/` in a WebGL-enabled browser. Select a letter or word,
sample a time or play once, and inspect front/side/back and each hand. The audit
images provide actual joint overlays. None of these controls/files is packaged
in the normal app UI. This session preserved the old bundle at the workspace's
`work/finger-fix-before.glb`; keep it for comparison. Stop the server with Ctrl+C.
The optional `--recording` argument displays a local recording without copying
or uploading it. Do not publish that recording or research assets automatically.

## Remaining review

These animations remain UNREVIEWED previews. Finger contact, thumb placement,
M/N/T and other similar shapes, R crossing, palm orientation, J/Z trajectories,
speed and repeated-letter transitions need qualified ASL review on a device.
The correction removes the demonstrated distal skin defect in sampled renders;
it does not certify every animation or rule out all intersections. Existing
source-motion provenance/redistribution rights remain unresolved. No new
linguistically validated signs or phrases have been added.

Reviewer checklist: A–Z singly; NAME, NICOLE, ANNA, JAZZ, ACTION; HELLO NICOLE;
WHAT IS YOUR NAME? (labeled English preview, not validated ASL grammar). Check
handshape/contact/palm/motion, both hands, full clip and between-clip transitions,
pause/repeat/cancel, same avatar, readable view and device performance. Record
reviewer, sign variant, reference, device, timestamp, verdict and corrections.

References: [ASL University fingerspelling](https://www.lifeprint.com/asl101/fingerspelling/fingerspelling.htm)
and [glTF animation specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#animations).
No reference media was copied into the APK.
