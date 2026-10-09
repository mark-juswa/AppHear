# New-character idle for Text-to-ASL

Status: user approved “okay lets proceed”; implementation and offline/APK gates passed.
Phone installation and visual/performance acceptance remain pending (ADB has no device).

## Overview and verified findings

Presentation-only follow-up to the Text-to-ASL T6 character pilot. No recognition,
training, camera, feature-vector, account or navigation change.

The current catalog still maps `idle` to `asl_animations/asl_idle.glb` even when New
is selected. TextToAslFragment requests this asset on initial readiness, completion,
Clear and idle resume. The controller already loops POSE assets indefinitely.

The original idle is a 2.074 MiB GLB with a six-second animation, 54 channels and
67 joints in its first skin. The new 36.05 MiB shared bundle has 27 named signs,
4,677 channels per clip and 341 joints in its first skin (three skins overall).
The two skeletons have different bone names, hierarchy and local axes. Copying
the old animation channels directly would not produce a compatible idle.

The first and last frames of the new A clip contain a relaxed hands-down pose,
including fingers and face. This is a suitable baseline for authoring a new idle.
Read-only decoded evidence: artifacts/text_to_asl_idle_assessment_20260928/idle-audit.json.
No new idle export was found among the loose source assets.

## Terminology and recommended decisions

- Idle: relaxed hands-down standing with subtle breathing/body motion, matching
  the old character's behavior rather than copying its incompatible skeleton data.
- Seamless: the first and last transforms are identical, with smooth periodic motion.
- Preserved signs: all 27 existing clips retain their targets, interpolation and
  decoded times/values; rendering resources retain their existing payloads.
- Device accepted: visual appearance and idle/sign/control transitions are confirmed
  on the phone, separately from offline structural correctness.

Author a six-second loop from the verified new-character neutral pose. Use small,
periodic upper-body motion; keep root and feet stationary and avoid invented facial
expressions or blinking. Include baseline tracks for every animated node/property,
including fingers, face, corrective bones and hair, so the previous sign cannot
leave residual transforms. Motion amplitude must stay conservative and can be
adjusted following visual review.

Append one named idle to a separate derivative shared GLB. This keeps one character
and one set of textures loaded for idle and the 27 signs. Retain the existing
27-sign bundle and prior APK for rollback. Do not decimate, re-encode textures,
retarget existing signs or introduce a runtime dependency.

## Flag, integration and fallback

Add default-off debug `aslNewIdle`, requiring the expanded shared-character pilot.
Release remains OFF. Its manifest uses the existing vocabulary plus a guarded POSE
override for idle; catalog counts remain Original 102 and New 122. All 27 New sign
entries point to the same derivative bundle as idle. Original remains unchanged.

Reuse the current named-animation player and looping behavior. Extend manifest
validation only as necessary for the explicit idle entry and variant path/hash.
Missing or invalid derivative/idle metadata retains the original idle fallback.
No Text-to-ASL UI, planner, queue or Settings redesign is needed.

Cold loading the 36 MiB bundle will move to the first New idle display. Existing
phone observations show a roughly seven-second first shared-model request; this is
not a new measured idle result. Preloading remains asynchronous, and warm idle/sign
transitions should reuse the same source. Do not claim reduced cold-load time or
phone performance before measurement. The added animation should be small relative
to the shared resources; measure its exact byte cost in the report.

## Contract and evaluation

No recognition schema_version or S4/F parity change; no recognition accuracy claim.
Record the new presentation flag, manifest validation and idle pattern in the
existing feature/component documentation after implementation.

Before any device rollout, require:

1. Exact comparison of the 27 existing animations and shared rendering resources.
2. A finite, valid six-second new idle with normalized rotations, exact loop seam,
   neutral hands/face baseline, stationary root/feet and complete reset tracks.
3. glTF validation with zero errors; investigate any warning drift from the existing
   bundle. Report compressed size and decoded animation cost.
4. Meaningful loader/manifest tests for New idle, Original preservation, flag OFF
   and malformed/missing override fallback; player idle → sign → idle, Clear and
   replay/lifecycle regression checks using the existing test harness.
5. Pilot/default builds and payload checks; preserve original assets and working
   account/profile configuration. No unrelated feature activation.

After the gate, install the pilot on the attached phone with data retained. Check
initial idle, complete phrase, Replay, Clear mid-sign, leave/reopen and Original/New
choice. Collect scoped load/error/memory diagnostics. Ask the user to confirm that
the motion looks natural and signs/controls still work; broader F22, thermal and
low-RAM gates remain separate and pending.

## Ordered build steps and rollback

1. Confirm this concrete plan.
2. Implement a repeatable idle derivative builder and exact-data verification report.
3. Add the isolated flag, manifest/loader integration and targeted tests.
4. Pass offline checks and build pilot/default APKs while preserving current flags.
5. Deliver derivative GLB, APK, reports and rollback under
   `G:\3d Characters\optimized_apphear3_idle_20260928`; never overwrite source GLBs.
6. Install/measure the pilot, obtain visual acceptance, imprint/review and save state.

Rollback: select Original, disable aslNewIdle, or reinstall the saved currently
working profile/character pilot APK with data retained. Current source bundles and
all original assets remain available. No default/release promotion is included.

## Deferred decisions

The exact visual amplitude is subject to phone acceptance after generation. A
dedicated source-authored idle can replace this procedural derivative later if
provided. No new idle source is required for the conservative six-second loop.
