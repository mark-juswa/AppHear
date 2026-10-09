# New-character idle results

User approved the concrete plan with “okay lets proceed”. Implementation and offline
gates pass. The idle pilot is installed on M2101K7AG with data retained and two
isolated on-device catalog/preference tests pass. The user confirmed New idle, both
phrase runs including HELLO on Replay, and working controls. Controlled memory,
frame pacing and broad F22 smoke remain pending. No default/release promotion.

## What changed

New now has an optional relaxed hands-down six-second breathing loop, selected through
the existing idle POSE entry. Initial readiness, completed phrases, Clear and idle
resume use the existing Fragment/controller hooks. No UI or queue rewrite.

`new-idle.mjs` appends IDLE_NEUTRAL_FEMALEASL to a separate shared-words-idle.glb.
The baseline is the exact neutral first frame of A. All 4,677 animated TRS properties
reset, including hands, fingers, face/correctives and hair. Gentle 0.2% uniform expansion
on spine_03/spine_04 in each of three skins keeps their motion synchronized. Root,
pelvis, feet and toes remain stationary; first/last transform values match exactly.
Identical new accessors/samplers are shared. This is authored motion on the new rig;
the old 67-joint idle cannot be copied directly into the different skeletons.

The existing 27 sign clips, rendering metadata/resources, hierarchy and compressed
binary prefix remain exact. Original source bundle SHA-256:
9d05488ea21367ece141764722e9b5d40be86a089383fa486bff307bbd69a6ca.
New derivative SHA-256:
766bf2fba9578e1863cc81ee697a034cb8e71451cb6ca6d75b120a4e749a66dd.
Bundle grows from 36.04776 to 36.94350 MiB: 939,248 added bytes (about 0.896 MiB).

## Integration and safety

Default-off debug aslNewIdle requires aslMoreWords and its prior flags. Release OFF.
Only this variant packages the derivative. Its schema-2 manifest retains seven
overrides and 20 new word entries, adding a separate idle object. All 27 signs and
idle use one source, so warm changes reuse the loaded character. Counts remain
Original102/New122; Original has no overrides and retains asl_idle.glb.

AslIdlePilotContract accepts only the known pose/source identity, file/profile/rig,
named animation, 6,000 ms duration, original fallback and matching checksum. Missing
or malformed metadata retains the original idle; existing player load-failure
handling also retries the original idle. Catalog hash work stays on the existing IO
path. New idle is selected only when the existing New character choice is active.
One player correction ignores finished events for looping poses, avoiding false
sign completion during idle/Clear. Default player is untouched.

No runtime library, recognition feature/model/schema/vocabulary, account flow,
Profile ordering, backend configuration or camera change. The pilot keeps the current
account and character flags ON; all recognition experiment flags remain OFF.

## Validation

- All 27 clips' 4,677 channels match decoded targets/interpolation/times/values exactly.
- Neutral reset, unit rotations, finite values, exact loop seam and all sampled fixed
  root/feet positions pass. All three skins have the same two breathing bone names.
- glTF validator: zero errors, 32 warnings. Warning/message code counts match the
  existing 27-sign bundle; no warning drift.
- Eleven player tests pass, including shared idle → complete sign → idle, Clear mid-sign,
  stale completion suppression, pause/reopen, failure and bounded preload cases.
- Pilot and default each pass 128 JVM tests (four new contract/manifest cases).
- Pilot app and Android test companion build. Default app builds with idle/pilot flags OFF.
- On-device: `adb install -r` succeeded; two isolated character catalog/preference
  tests pass in 0.345 seconds on the final build. Test companion removed. Original102/New122 and the
  New idle POSE/name/path assertion passed without navigating or changing accounts.
- APK verification: only one experimental character GLB; source payload matches;
  all 102 original GLBs preserved in both variants; default excludes pilot assets.
- Local model-viewer preview renders the relaxed idle and breathing peak. The user
  separately accepted the corrected phone appearance and playback.

Two isolated test compile problems were diagnosed with /recover and corrected:
Android-compatible file reading and a missing instrumented-test import. No runtime
architecture change. See artifacts/text_to_asl_idle_20260928/recovery-note.md.

The first phone play exposed a mixed-catalog residency failure: New idle started
after 5,687 ms, then an original-only HELLO sign caused the player to release the
large New bundle. Reloading it for A timed out after 20 seconds; the session
fell back to original A/B and original idle. The user correctly reported that
New idle did not return. The corrected pilot keeps the shared New source in the
inactive viewer during original-only signs and avoids preloads that would evict
it. Eleven player tests pass, including this exact mixed-source progression.
The selected-character loading message stays visible until actual playback.
See initial-phone-failure.log and recovery-note.md.

The first pinning correction exposed the symmetric case on Replay: after New idle
returned, the player released HELLO and its reload timed out. The final correction
retains both New and the most recently used original model in the two existing
viewers; no third viewer or cache was added. The user confirmed that HELLO (expected
to use Original) plays again on Replay, A–FAMILY use New, and New idle returns.
The final scoped log shows two complete eight-sign runs and zero playback failures.
See phone-playback-evidence.log and recovery-note.md for both failure diagnoses.

Reports/APK checksums: artifacts/text_to_asl_idle_20260928/{bundle-verification,
gltf-validation,apk-verification,asset-parity,phone-test-summary}.json. Saved prior working profile/character pilot
is the primary rollback; the original bundles/assets remain intact. Saved ordinary
APK is the broader rollback. Generated standard app-debug.apk finishes with flags OFF.

## Device and performance gates

Cold shared loading now occurs on initial New idle instead of the first New sign.
The phone measured New idle cold loads of 5,687, 6,227 and 6,543 ms across pilot
iterations; the final run was 6,543 ms. New sign/idle warm switches in the first
final-run phrase were 52–88 ms; Replay warm switches were 22–71 ms. Original HELLO
first loaded in 696 ms and took 35 ms on Replay. These are
uncontrolled diagnostics, not a latency guarantee. Hashing/model loading remain
asynchronous. One sampled app PSS was 319,048 KiB plus WebView renderer
419,088 KiB (~721 MiB combined), while both models were resident. Memory/frame,
low-RAM and thermal suitability remain unverified beyond this phone.

The pilot is installed with `adb install -r`; existing profile/character data was
retained. The user accepted the corrected New idle and mixed-source phrase playback,
including HELLO on Replay. Logs confirm completion and idle return after both runs.
Clear worked in the user's check but was not separately instrumented. Controlled
frame, thermal, low-RAM and broad F22 checks remain outstanding.

Delivery target: G:\3d Characters\optimized_apphear3_idle_20260928, containing the
derivative, manifest, pilot, prior-working/default rollbacks and reports. Source GLBs
are not overwritten. The corrected pilot and final reports were checksum-verified
in this delivery after the user's phone acceptance.

## /review

Plan alignment: PASS for implementation/offline scope and targeted handset playback.
System integrity: PASS, presentation-only; no recognition contract or parity drift.
Offline readiness: PASS; production/device acceptance not claimed.

Critical: 0. Important: 2 — (1) broad F22 acceptance beyond the targeted phrase,
(2) cold loading, memory/frame/thermal/low-RAM characterization. Minor: 0 new findings.
Recommendation: deliver the flagged pilot and rollbacks; keep default/release OFF
until device gates pass. /imprint records the derivative/metadata guard and the
conditional supersession of the earlier “idle remains original” contract note.
