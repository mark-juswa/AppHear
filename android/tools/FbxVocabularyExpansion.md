# 3D-LEX FBX vocabulary expansion — 2026-10-25

Target: 1,000 distinct lexical entries. Current source catalog: **784 entries** (743 existing + 41 new), **916 accepted English input forms**, **862 animation actions**. Forms and fingerspelling are not counted as additional lexical entries. The target is not achieved. All added signs remain unreviewed ASL previews.

## Scope and preservation
Only Text-to-Sign assets, catalog hash/count pins, offline tools and tests change. The same human rig, mesh, materials, alphabet, idle, playback controller, interface and all 821 previous actions are preserved. Packaging verifies every original buffer-view payload, accessor and animation object before writing. Identical storage is deduplicated; no animation values are quantized or clamped. Sign-to-Text, recognition assets, navigation, UI and dependencies are unchanged. Git checkpoint: checkpoint/before-1000-word-expansion-20261025. Existing untracked work was separately backed up with checksums.

## New previews
ACTOR, ANGEL, ASIA, BACON, BODY, CERTIFICATE, CHANCE, CHINA, CIRCLE, COLOR, DELICIOUS, DISCONNECT, DROP, DUMB, ERASER, EXAMPLE, FARM, FAT, FIRST, FLAG, FOOL, FRONT, GIFT, HELICOPTER, MAGIC, MOUNTAIN, PIG, REST, SATURDAY, SCIENCE, SCIENTIST, SECRET, SEQUENCE, SHAPE, SHOWER, SHRIMP, SWEEP, TEETH, THAT, TREE, VACATION.

## Source audit and exclusions
Official 3D-LEX v1.0 ASL data: https://osf.io/mqzyk/ ; CC BY 4.0 license record: https://www.sign-lang.uni-hamburg.de/lrec/data/3dlexv10.html . Original FBX ZIP SHA256: 6ee2bd5b7ead8f601d2d77345cc6fcfe0b9a323970ca6a9ec316c408298336eb. Source member hashes and transformed-motion hashes are recorded in the integration manifest. No third-party video, source avatar mesh or texture is packaged.

The archive has 938 named ASL files. Of 262 names absent from the existing input forms, 166 have empty/static animation curves; 16 more fail interior bone-length, motion or rotation-step gates. The remaining 80 underwent 21-pose actual-mesh screening. Of 40 contact-proxy warnings, one had no triangle crossings (HELICOPTER); the other 39 were held. Intersections alone do not establish a linguistically wrong sign, but their intent and extent are unresolved. These excluded words retain automatic fingerspelling where possible. See 3dlex-fbx-expansion-audit.csv for all 262 decisions.

## Conversion safeguards
Three.js 0.180.0 FBXLoader and GLTFExporter are development tools (MIT), not new Android dependencies. Original large FBX clock origins are subtracted before float32 conversion; original skeletal key times are preserved. Export sampling uses LoopOnce and clampWhenFinished, avoiding an artificial final wrap. Existing exact terminal bind/reset detection is reused; interior corruption is rejected. Existing anatomical conversion is tried first. The optional minimal-swing adapter preserves source bone direction and transferred twist, rejects ambiguous antiparallel directions or adaptation over 10 degrees, and retains the independent direction and 90-degree-per-24-Hz mechanical gates. These are import rejection gates, not joint clamps. Stable-preroll shoulder calibration preserves world wrist positions and finger orientations.

## Reproduction and tests
The ignored staging folder is .tmp/vocabulary-1000-20261025 and retains the checksum-verified original archive, CRC-verified members, probe-clocks.json, normalized skeleton exports, NPZ candidates, selection.json, contact witnesses and test logs. No duplicate project was created.

Offline tools: normalize-3dlex-fbx.mjs STAGING_DIRECTORY requires a local pinned Three.js 0.180.0 installation under that directory; stage-3dlex-fbx-vocabulary.py STAGING_DIRECTORY PINNED_CONVERTER_SOURCE --baseline-sha256 HASH checks source and baseline hashes; review its results before package-3dlex-expansion.py STAGED --baseline-sha256 HASH --compact-buffer-views. Do not rerun the old-baseline package on the expanded asset. The original publisher FBX parsing/extraction and prepared clocks are retained in the ignored staging folder for reproducibility.

Mechanical adapter tests: python android/tools/test-3dlex-fbx-directions.py (4 passed). JVM tests retain the original 821-action repair gate and separately pin all 41 new actions, provenance, validation status and exclusions. Build/native results are recorded in the delivered update report. CPU mesh renders are not Android screenshots. All signs require qualified ASL review; facial grammar is not supplied by these files.

## Remaining gap
216 further genuinely distinct lexical entries are needed. Re-labeling static files, duplicates, aliases or fingerspelling would not fill that gap. Other motion sources investigated require access/permission or noncommercial licenses and cannot simply be redistributed in this app.

## Original-capture recovery study

The publisher also exposes ASL-only handshape captures (1,000 folders across three archives, approximately 10.6 GB) and body-marker CSV captures (990 files, 370.6 MB). These are additional research inputs, not ready avatar animations. Public components: https://osf.io/pxkv8/ and https://osf.io/p2cth/ . Selective official ZIP ranges were checked for content range/length; extracted sample members passed ZIP CRC checks and have local SHA256 records. Their entire multi-gigabyte archives have not been downloaded or checksum-verified; advertised archive hashes are recorded separately.

ACTION has genuine raw left/right hand motion even though its combined FBX is static. Its hand FBX spans 4.2 seconds, while the body CSV has 525 numbered frames. ADULT control hand motion spans 3.666667 seconds and its body CSV has 455 frames. The hand metadata identifies Vicon as master timecode with 120 FPS; body CSVs contain numbered marker positions without absolute timecode or frame-rate metadata. Hand FBXs also contain explicit timecode channels and dropped/irregular samples. Equal gloss names alone do not establish exact temporal or rig calibration alignment. The publisher's small capture-control archive was checksum-verified and read as reference; no third-party control code or source avatar meshes were copied into the app.

A future reconstruction must demonstrate synchronization and joint-frame/marker calibration against working control exports, then pass the same hand/contact/rendering gates before registration. No guessed arm/body movement, timing alignment or calibration has been enabled. ACTION therefore remains fingerspelling-only. The release catalog count remains 784; raw recordings are excluded from that count.

## Completed build gates (2026-10-26)

The application and instrumentation APKs assembled successfully. The corrected fresh JVM suite passed all 372 tests with zero failures, errors or skips. Four offline adapter tests passed. APK verification confirmed the existing signing certificate, unchanged manifest/resources, and 1,665 unchanged unrelated decoded files. The standard output is AppHear-Update-11.apk. Native playback could not be tested because the emulator reported QEMU main-loop/CPU-thread hangs before AppHear launch; software-renderer startup did not resolve it. New signs remain unreviewed previews. The integration manifest is the authoritative current catalog; older dated inventories describe their original snapshots.
