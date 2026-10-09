# Repeatable Text-to-ASL asset batch

From the AppHear3 project root, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\text_to_asl_assets\Optimize-Characters.ps1
```

Default output: `G:\3d Characters\optimized_apphear3_batch`. Run the same command again to
resume completed files. Completed source/output hashes must match; unknown existing outputs
are never overwritten. Processing is sequential to limit peak RAM. No app integration occurs.

Optional commands:

```powershell
# Inspect selection without generating files.
.\tools\text_to_asl_assets\Optimize-Characters.ps1 -PlanOnly
# Process a smaller subset.
.\tools\text_to_asl_assets\Optimize-Characters.ps1 -Signs C,D,E
```

The existing assessment inventory pins input hashes. Only corrected exports with identical
approved pilot texture hashes are accepted. Old normal-map generations, ambiguous distinct
duplicates, and all SORRY recovery files are excluded with reasons. Unknown/new exports need
an assessment update first. Sign names are source identifiers, not new app catalog mappings.

Eight validated KTX2 textures are reused from the approved pilot; no repeated texture encoding
or network service is needed. Each GLB independently preserves nontexture bytes during repacking,
passes exact decoded rig/animation/non-index data and oriented triangle topology comparisons,
passes zero-error GLB validation, and verifies source/output checksums. The old validator's
extension warnings remain; runtime compatibility and phone performance are separate gates.

Reports: `reports/batch-summary.json` plus per-file validation reports. Shared KTX2 payloads
are retained there to document and validate the texture bank. On a crash the exclusive
`batch.lock` may remain; confirm its PID is no longer running before removing that exact lock.
Concurrent runs into the same output are refused.

Requires Node and the existing pinned pilot dependencies/tools under
`artifacts/text_to_asl_asset_optimization_20260928/tools`, plus assessment inventory and
`work/candidates/A.balanced.ktx2mixed.glb`. These generated artifacts are machine-local;
the scripts do not silently download or install anything. If missing, restore the original
pilot artifacts before running. Broader portability/bootstrap remains separate work.

User accepted pilot appearance on 2026-09-28. Additional signs still need animation/semantic
review. No production eligibility, catalog replacement, or phone performance is implied.

## Stage existing catalog replacements

```powershell
python .\tools\text_to_asl_assets\stage_pilot.py --plan
python .\tools\text_to_asl_assets\stage_pilot.py
```

Stages only optimized source IDs that exactly match existing LETTER/WORD catalog IDs. Original
catalog/aliases remain unchanged. Currently seven match: A, B, ALL, BROTHER, CHILD, CITY, FAMILY.
It verifies source/output hashes and decoded-data validation, refuses differing GLB overwrites,
and updates only the pilot override manifest. Unmatched vocabulary and semantic near-matches are
excluded. This command requires the existing pinned assessment/batch artifacts; it does not build,
install or activate the app. Debug build activation still requires `-PaslAssetPilot=true`.

## Shared-character experiment

```powershell
node .\tools\text_to_asl_assets\shared-character.mjs
# From android/:
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug -PaslAssetPilot=true -PaslSharedCharacter=true
```

The builder preserves source GLBs and generates `src/aslShared/assets` separately. It refuses
a differing existing bundle; original channels/times/values/interpolation and rendering resources
must match exactly after decoding. Only the known unanimated hair rest-transform variation is
permitted and is preserved with three constant tracks in every clip. Seven signs share one
17.43 MiB character bundle instead of83.14 MiB of full models. No vocabulary is added.

The shared flag requires the asset-pilot flag. Without `aslSharedCharacter`, the existing
separate pilot remains available; with both false the ordinary app excludes experimental assets.
The generated shared package reuses the same player/local decoders and excludes the seven
redundant pilot GLBs. All102 original assets remain for fallback. Offline validation reports
live under `artifacts/text_to_asl_shared_character_20260928`; APK verification accepts `--shared`.
Same pinned machine-local dependencies as the batch command; no downloads. Physical testing
and performance evidence are documented separately, not inferred from reduced file bytes.

## Twenty more word signs (experimental)

```powershell
# From the project root, with the existing pinned batch artifacts on G:.
node .\tools\text_to_asl_assets\more-words.mjs
# From android/:
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug -PaslAssetPilot=true -PaslSharedCharacter=true -PaslMoreWords=true
```

This builds a separate 27-clip shared GLB (seven established replacements plus 20 approved
new Text-to-ASL word phrases) under `src/aslWords/assets`; it refuses to overwrite differing
outputs. It checks raw and optimized source hashes, exact decoded meshes/textures/skins,
all 4,674 original channels per clip and three constant hair-transform tracks. The 20 new
phrases, especially “big horizontally”, “call by phone”, “call someone’s name” and “pay me”,
are explicit; plain “big”, “call” and “pay” are not mapped.

`aslMoreWords` requires both prior pilot flags and defaults false. Existing seven-sign and
ordinary builds exclude the 27-clip package. New signs have no older original GLB fallback:
if the experimental bundle fails, the app reports/skips that new sign; existing signs still
fall back to their originals. APK checks use `verify_pilot_apks.py --words`. See
`docs/text-to-asl-more-words-plan-2026-09-28.md` for the review and device gates.

## New-character neutral idle (experimental)

```powershell
node .\tools\text_to_asl_assets\new-idle.mjs
node --test --test-isolation=none .\tools\text_to_asl_assets\pilot-player.test.mjs
# From android/, preserving your locally configured app backend values:
.\gradlew.bat testDebugUnitTest assembleDebug -PaslAssetPilot=true -PaslSharedCharacter=true -PaslMoreWords=true -PaslCharacterSelection=true -PaslNewIdle=true
```

Appends `IDLE_NEUTRAL_FEMALEASL` to a separate `src/aslIdle/assets` derivative. It uses
the exact neutral first frame of A and a six-second 0.2% chest expansion on two spine
bones in each of three skins. All 4,677 properties reset; root/feet stay stationary.
The 27 signs, rendering metadata and existing compressed binary prefix stay exact.
The builder shares identical new accessors/samplers and refuses differing overwrites.
Reports are under `artifacts/text_to_asl_idle_20260928`; APK verification uses `--idle`.

## Complete New-character alphabet fallback (experimental)

```powershell
node .\tools\text_to_asl_assets\alphabet-fallback.mjs
node --test --test-isolation=none .\tools\text_to_asl_assets\pilot-player.test.mjs
# From android/, preserving locally configured app backend values:
.\gradlew.bat testDebugUnitTest assembleDebug -PaslAssetPilot=true -PaslSharedCharacter=true -PaslMoreWords=true -PaslCharacterSelection=true -PaslNewIdle=true -PaslAlphabetFallback=true
```

The builder appends C–Z to the existing 27-sign-plus-idle derivative. It pins all 24
optimized source hashes, verifies decoded resources and tracks, preserves the existing
28 animations and compressed binary prefix, and refuses to overwrite a differing
output. The one shared 52-animation GLB and schema-3 manifest live under
`src/aslAlphabet/assets`; originals and the earlier New idle pilot stay untouched.
APK verification uses `verify_pilot_apks.py --alphabet`. Only the default-off debug
flag activates token-atomic fingerspelling. Known signs still win, including Original
HELLO under New. Original has only A/B letter assets and never borrows New letters.
The phone pilot and results are under `artifacts/text_to_asl_alphabet_20260928` and
`docs/text-to-asl-alphabet-fallback-results-2026-09-29.md`; cold load remains a gate.

`aslNewIdle` requires the expanded pilot, defaults OFF and remains false in release.
Original remains unchanged. New uses the derivative for both idle and all 27 signs,
so warm transitions reuse one model; the cold shared load now occurs on opening New.
No extra vocabulary or third-party runtime dependency. Phone appearance/performance
requires separate validation. Optional local preview:
`python artifacts/text_to_asl_idle_20260928/preview_server.py` (localhost:8787).
