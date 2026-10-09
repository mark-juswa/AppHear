# Shared-character Text-to-ASL results

## Change and exact-data gate

User approved the [experiment plan](text-to-asl-shared-character-plan-2026-09-28.md).
One GLB now contains the same character and seven named sign animations: A, B, ALL, BROTHER,
CHILD, CITY, FAMILY. Original catalog, aliases, UI/planner,102 fallback GLBs and recognition
remain unchanged. The original seven-file phone-tested pilot remains a separate rollback.

`tools/text_to_asl_assets/shared-character.mjs` compares decoded geometry, textures, skins,
hierarchy and rendering materials, copies existing compressed data, and verifies every
original target/path/interpolation/time/value byte after bundling. All4,674 channels in each
clip pass. A tiny unanimated hair-node rest-transform variation is preserved using3 constant
tracks per clip, including resets for A/B. Material display names differ between exports;
rendering parameters match. No pruning, decimation, quantization, resampling or retargeting.

All source derivatives are checksum checked and stay read-only. Output is separate under
`android/app/src/aslShared/assets/`. The existing pinned glTF validator returns0 errors and32
warnings; its unsupported Meshopt/Basis/KTX2 coverage remains a caveat. Independent decoded
comparison and actual phone rendering supply additional evidence.

## Android integration and rollback

Debug `-PaslAssetPilot=true -PaslSharedCharacter=true` selects a generated asset package:
same pilot HTML/JS/local decoders, shared manifest/bundle, no redundant separate GLBs.
Default and release exclude both experimental payloads. Shared alone is rejected at build
configuration. Loader permits only the flag-selected path/profile and verifies SHA-256 once
per unique path per off-thread catalog load; per-sign original fallback remains.

The existing player changes named animations on the same loaded source. No custom external
animation loader, private renderer API, vendor modification, expanded cache or additional
resident model was introduced. Existing completion timeline, cancellation and lifecycle rules
remain. Shared bundle failure rejects that path for the session and uses original per-sign assets.

Eight player regressions pass, including same-source named clips and exactly-once completion;
full99-test JVM gates pass for shared, separate and ordinary builds. APK inspection confirms
102 originals unchanged, shared packages1 character GLB, separate packages7, default excludes
both. Current APK sizes: shared318.97 MiB, separate380.70 MiB, ordinary307.56 MiB. The prior
delivered phone-tested pilot was379.86 MiB; build compression variation does not alter the
verified GLB payloads. Final ordinary build output remains OFF; phone runs the shared experiment.

## Physical phone observations

Same M2101K7AG/Android12/~6GB/WebView153 device as the previous pilot. Installed with `adb
install -r`, preserving data. User ran the requested sequence/control check and reported
**faster signs, working controls, smooth playback, approved**. Initial logs capture A/B/ALL/
BROTHER/CITY/FAMILY; CHILD/repeated-identical-clip coverage is requested separately because it
was absent from that captured input. Full details/raw app-scoped logs and paired memory samples:
`artifacts/text_to_asl_shared_character_20260928/`.

| Measurement | Separate pilot earlier run | Shared initial capture |
|---|---:|---:|
| Seven-character asset payload |83.14 MiB|17.43 MiB|
| First sign request to start |4,227 ms|5,749 ms|
| Sampled app+WebView peak PSS |719.02 MiB|435.80 MiB|
| Subsequent transition times |41–1,547 ms|64–80 ms|

Payload is79.03% smaller. Shared first load is slower by1,522 ms; it loads all seven clip
definitions once. Subsequent shared transitions avoid character decoding: n=5, nearest-rank
p50=69 ms,p95=80 ms. This small capture provides diagnostic evidence, not a universal benchmark.
Combined sampled PSS is about39% lower than the earlier719.02 MiB capture; earlier repeated
separate playback also reached998.61 MiB. Sampling intervals, phrase/control timing and warm
state differ, so no controlled memory ceiling or leak/thermal conclusion follows. Sampling
can miss transient peaks and itself affect playback. UI gfxinfo includes input/navigation;
no isolated WebGL FPS claim. The captured UI window reports288 frames,92.01% jank,
p50=57ms/p95=65ms. This is a frame-pacing concern requiring a controlled active-playback
measurement; reduced memory and favorable human feedback do not establish a UI frame-rate
gate pass. Per-frame4,674-channel workload remains unchanged.

## Review

Plan alignment PASS; system integrity PASS; experimental functional/performance result
favorable with explicit cold-load tradeoff. Critical:0 known. Important:2 (cold load remains
~5.7s; low-RAM/thermal/semantic and physical fault-injection/fullF22 gates remain incomplete).
Minor:1 (old idle/unreplaced signs yield mixed characters). Recommendation: retain this
default-off, user-approved seven-sign experiment and measured rollback. Do not infer approval
for all51 signs, semantic near-matches, production-default activation or recognition changes.

Repeatable command and packaging directions are in tools/text_to_asl_assets/README.md.
The next optimization should target first-load cost and measured frame pacing without
sacrificing finger deformation or animation data; broad preload/cache enlargement is unnecessary.
