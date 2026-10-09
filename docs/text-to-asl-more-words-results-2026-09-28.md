# Text-to-ASL: 20 more word signs

Status: **built and offline-validated; phone installation and performance/visual testing deferred
at the user's request**. The project default remains flag OFF.

## What is available

The experimental catalog contains 122 entries: all 102 original entries, seven of those
replaced by the shared character, and 20 newly available Text-to-ASL word phrases. The 20 are:
AFTERNOON, ANY, ASK, BABY, BAG, BE, BEAUTIFUL, BECOME, BEGIN, BOSS, BUSY, BYE, CAR, COLD,
COME, FAST, plus BIG HORIZONTALLY, CALL BY PHONE, CALL SOMEONE'S NAME, and PAY ME.

The last four use source-specific meanings approved by the user. Plain **big**, **call** and
**pay** are not given guessed sign mappings. ASK and COME are separate from the original
REQUEST and COME TO HERE entries. Letter I still means the original pronoun I; no new letter
clips or recognition vocabulary were added. Input “call someone’s name” normalizes to
“call someones name” under the existing Text-to-ASL rules.

## Asset conversion and checks

`tools/text_to_asl_assets/more-words.mjs` generated a separate 27-animation GLB from the
phone-tested seven clips plus the 20 hash-pinned batch derivatives. It verifies the original
raw and optimized source hashes. Decoded geometry, textures, skins, hierarchy, material
rendering parameters and every one of each clip's 4,674 original channel targets, time/value
arrays and interpolation match its source. Three constant tracks per clip preserve the only
nonanimated hair rest-transform difference. No mesh/texture resampling, channel pruning or
retargeting was introduced. The local glTF validator reports zero errors; 32 warnings reflect
its unsupported Meshopt/KTX2 extension coverage, which is not equivalent to runtime approval.

The 27 separate optimized files total **320.71 MiB**; their shared-character GLB is
**36.05 MiB** (88.76% smaller). The experimental debug APK is **321.98 MiB**; the default-off
APK is **307.56 MiB**. APK inspection finds exactly one experimental GLB in the expanded build,
none in the default, and all 102 original GLBs byte-identical in both. All 224 shared
nonexperimental packaged assets are byte-identical, including recognition/model/config assets.

The new `aslMoreWords` Gradle property requires the two existing pilot flags. It packages
only the 27-clip bundle plus the existing local player/decoders; the seven-clip shared bundle
and 20 standalone optimized GLBs are excluded. A schema-2 manifest adds only the 20 approved
aliases; the loader validates source IDs, exact phrases, animation names, profile, rig and
SHA-256 on an IO dispatcher (one hash per unique bundle). If the bundle cannot load, the seven
existing replacements still retry their original clips. A new word has no matching old GLB:
the app reports its failure and advances rather than substituting an unrelated sign.

All three configurations (expanded, seven-sign shared rollback, default OFF) passed the full
**102-test JVM suite** and `assembleDebug`; eight deterministic player tests passed. Tests
cover approved phrase planning, non-mapping of plain ambiguous words, the original pronoun
and mappings, bundle names/hashes, and nullable fallback policy. The ordinary final build
output is default OFF. Raw checks: `artifacts/text_to_asl_more_words_20260928/`.

Delivery: `G:\3d Characters\optimized_apphear3_27sign_20260928` contains the expanded APK,
seven-sign and default rollback APKs, the GLB, manifest and reports. Copied APK, GLB and
manifest SHA-256 values match the workspace originals.

## Device gate and review

The phone was disconnected when the expanded build was ready; the user elected to test later.
**No 27-sign phone install, measured cold load, transition latency, frame pacing, memory,
thermal or semantic/visual approval is claimed.** The prior seven-clip bundle took about
5.7 seconds for the first sign on a 6 GB Android phone; 27 clips may take longer, potentially
exceeding the current 20-second model load guard. The much smaller GLB file does not guarantee
proportionately lower runtime work: 27 × 4,674 animation channels still need parsing and
binding. This build remains default-off until a physical test proves it practical.

Plan alignment: PASS for the approved 20 phrases and focused feature flag. System integrity:
PASS for preserved original catalog/recognition and rollback. Critical: none found offline.
Important open gates: phone load/memory/frame testing and per-sign visual/semantic review;
physical load-failure fallback and full F22 smoke remain pending. Recommendation: use the
saved APK only as a test pilot. If initial load is too slow or times out, keep the seven-sign
rollback on the phone and split/optimize the expanded payload using measured evidence.

When the phone is available, install the expanded APK over the current app with `adb install -r`
to retain data. Test the four explicit phrases, representative direct words, same-sign replay,
Clear during playback and leave/reopen. Capture app-scoped completion/watchdog/failure logs,
paired app/WebView memory, cold/warm p50 and p95 and controlled active-playback frame pacing.
The prior seven-sign and ordinary APKs are saved in the same G: delivery folder for rollback.
