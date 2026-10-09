# Shared-character Text-to-ASL experiment

Status: user explicitly approved the experiment; offline bundle passed exact-data gates; Android/device validation in progress.

## Scope and terminology

Presentation-only optimization of the existing seven-sign pilot (Text-to-ASL T6 derivative).
No S0–S8 recognition, model, dataset, inference, feature schema or vocabulary change.
“Shared character” means one geometry/texture/rig instance with seven separate named clips.
“Exact animation” means original interpolation, channel targets, times and values survive
decoded-byte comparison. “Improved performance” requires measured phone memory and transitions,
plus human confirmation that signs finish and controls/lifecycle behave normally.

## Evidence and decision

Pinned local glTF Transform/Meshopt decoded audit found identical mesh accessors (including
indices, attributes and morph targets), textures, joints/inverse bind matrices and hierarchy
for A/B/ALL/BROTHER/CHILD/CITY/FAMILY. Each clip has 4,674 channels; decoded sampler data
is only 190,152–273,032 bytes. Character geometry/textures dominate repeated file loads.
Report: artifacts/text_to_asl_shared_character_20260928/compatibility.json.

One unanimated hair node (1230) has rest-transform differences ≤1.1920928955078125e-7
between A/B and the five words. Preserve each source transform using constant tracks for
that node in all seven clips, including A/B resets, rather than a tolerance-based deletion.
One material display name differs; rendering material parameters are identical.

Use a single compressed GLB bundle, keeping the current model-viewer API and named playback.
Do not introduce an external animation loader, private renderer API or vendor modifications.
Do not prune channels, quantize, decimate or resample. Copy compressed resource data and remap
references, then decode and compare the complete resulting clips/resources.

## Flag, fallback and boundaries

New default-off debug property aslSharedCharacter requires aslAssetPilot=true. Existing
aslAssetPilot alone remains the phone-tested seven-file baseline. The shared build packages
one GLB and schema-1 exact-ID overrides plus the same pilot player/decoders; excludes redundant
seven full derivatives. Default/release exclude both experimental payloads.

Loader accepts only the explicitly flagged shared path/profile, checks hashes once per unique
path off-thread, and retains per-sign original fallback. Planner, aliases, UI, original102
assets and recognition restrictions remain intact. Preserve earlier tested APKs and installed
app data. Never claim semantic ASL or recognition accuracy from playback checks.

## Steps and gates

1. Build a reproducible offline bundle command. Validate every source checksum against audit,
   exact mesh/texture/skin/hierarchy equality, and only the known hair rest difference.
2. Decode output: all original channel target/path/interpolation/input/output bytes match;
   added constant hair tracks exactly reconstruct source rest transforms. Validate GLB
   references and buffer ranges; retain unsupported compression-extension validator caveat.
3. Stage separately, add flag and narrowly permit shared metadata. Hash verification is once
   per unique file in each catalog load. No cache enlargement or extra resident models.
4. Run player regressions including same-source animation switching, full JVM gate and APK
   preservation checks for shared/baseline/default; check original102 and baseline unchanged.
5. Only after offline gates pass install-r on the already authorized attached phone. Capture
   completion/watchdog/fallback counts, cold and transition latency p50/p95 with sample size,
   paired app/WebView PSS and qualified frame diagnostics; human runs play/replay/Clear/navigation.
6. Retain shared experimental status if initial latency, memory or visual/control behavior
   regresses. Deliver evidence and rollback; broader activation remains separately gated.

## Open validation

Memory benefit is unproven until device testing: seven decoded AnimationClips add JS metadata
despite tiny sampler buffers. One-time combined decode may lengthen first load. Per-frame
4,674-channel workload remains; this experiment chiefly removes repeated character loading
and duplicate resource residency. Actual WebGL frame pacing, low-RAM/thermal stability,
semantic approval and full recognition F22 remain pending.
