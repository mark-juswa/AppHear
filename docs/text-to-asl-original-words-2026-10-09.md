# Original Character word batch — 2026-10-09

## Decision and implementation

Technical integration/playback PASS. This is a flagged Text-to-ASL vocabulary extension,
not a recognition/model change. Installed on Xiaomi M2101K7AG (3ab64582) in the approved
private debug configuration. Baseline remains frozen at
34f24ab6d7aea8179decb1688a82fc5734f6d370. Work is on
codex/original-character-word-batch-2026-10-09, not committed/pushed as a new baseline.

32 overlapping signs now use ZIP clips; 171 new signs bring Original to 273 entries.
15 extra pilot variants were omitted: BABY, BIG, COOK, PAY__TO_PAY_SOMEONE,
SHOP__GOING_TO_STORE_TO_BUY_GOODS each had four ZIP versions. One top-level clip per
sign was selected. STAND was excluded; stand remains the established idle alias.
RIGHT -> right.glb; RIGHT DIRECTION -> right__direction.glb (longest alias wins).
Father/Dad, Mother/Mom, Big/Large and Go/Go To remain separate identities.
Existing New Character catalog remains 122 entries, with its established alphabet path.

New manifest SHA-256: 4c08af4d1257ebb0b85258cd52c99cd54f0c66233b095cab28174f8296d88717
Private phone APK SHA-256: 152dacceb5eb07a561d79f93d4a9620523d9de47e0fe97393cef7dabd8589933
Rollback APK SHA-256: cd92a856a86a078f79e6b1a40182587e1737a213dba6c0d3baa754c25d36d4c0
New payload: 772,889,620 bytes (~737 MiB); installed private APK: 827,340,540 bytes.

## Files

- android/app/build.gradle.kts: debug aslOriginalWords flag, separate assets source set;
  default/release disabled.
- AndroidAssetAslCatalogLoader.kt: Original-only verified manifest overlay, atomic
  fallback to baseline on invalid data, existing asynchronous IO call site retained.
- domain/texttoasl/OriginalWordBatchCatalog.kt: pure validated merge, exact existing
  aliases/fallbacks/idle retained, no rig conversion.
- android/app/src/aslOriginalWords/assets/asl_animations/original_words_v1/:
  manifest plus 203 SHA-verified standalone ZIP GLBs.
- OriginalWordBatchTest.kt and OriginalWordBatchInstrumentedTest.kt: mapping, hashes,
  validation rejection, real device playback.
- AslCharacterSettingsInstrumentedTest.kt: old catalog-count test excludes this flagged
  expanded catalog; other tests untouched.
- tools/text_to_asl_assets/import_original_word_batch.py: reproducible Windows importer.
- tools/android/build_working_baseline.ps1: optional -OriginalWords switch.
- .gitattributes: preserve manifest/payload bytes without text normalization.
- context/text-to-asl-original-words-v1.md, feature-schema component registry,
  progress tracker/memory append and this report.

## Validation

186 host unit tests passed (zero errors/failures), including 5 new focused tests.
Importer Ruff and mypy passed. Both fake and private builds succeeded.
All 203 packaged ZIP files match the manifest hashes. All 239 assets in the reviewed
baseline APK remain byte-identical. All original source assets remain unchanged.
667 of 670 inventoried existing Android source/config files remain byte-identical;
the only three existing changes are Gradle, the catalog loader, and the old catalog-count
instrumented test. WORD, fingerspelling, Candidate01, Context Assist and model code/assets
were not modified.

Xiaomi: 2 new instrumented tests passed in fake configuration; both passed again in
private configuration. Existing ownership/Context Assist preservation test passed
alone (3.832 seconds). Combined private run had one Espresso window-focus timeout
after playback, not an assertion failure; the separate retry passed without code changes.
Seven clips loaded, started, completed and released: hello, father, dad, right,
right direction, baby, what rhetorical. Screenshots visually inspected: upright,
hands in frame in sampled images. This does not establish all-frames/all-clips framing
or ASL correctness. Some sampled transition screenshots include faint prior-character
silhouettes; no viewer/rendering behavior was changed in this task.

First Original catalog hash verification: 5,115.07 ms off UI thread.
Sample first-start latency: 354.42–1,209.47 ms; playback including animation:
2,479.33–3,723.39 ms (seven samples, not a sustained benchmark).
ZIP avatar is a clothed human; some retained assets such as Dad and idle use the old rig.
Thus character appearance changes across mixed old/new clips. Assets were not retargeted.
No qualified ASL linguistic review was performed; file labels supply mappings.

## Build and rollback

From the authoritative app checkout, using the existing local private build configuration:

```powershell
& .\tools\android\build_working_baseline.ps1 -Configuration private -OriginalWords
```

This private APK stays local and must not be distributed. To disable the expansion,
build with the same wrapper without -OriginalWords. The old catalog/payload remains intact.
Pre-install device APK is preserved at artifacts/text_to_asl_original_words_01/pre-install-private.apk
under the F: research workspace. No app data was cleared during installation.

## Evidence

F:/ASL DATASET/5. Apphear3/artifacts/text_to_asl_original_words_01/
contains import_receipt.json, host_validation.json, final_validation.json, build logs,
device_playback_fake.log, device_private_tests.log, device_ownership_retry.log,
device/original_word_batch_catalog.json, device/original_word_batch_playback.json,
seven representative screenshots and local APKs.
Full vocabulary/mapping/hashes: new manifest; previous exhaustive comparison:
artifacts/text_to_asl_zip_audit_20261009/report.md and comparison.json.

## Review (/review)

Plan alignment PASS; system boundary integrity PASS; flagged device-engineering gate PASS.
Critical issues: 0. Important limitations: mixed avatar appearance and no linguistic
review of all clips. Minor limitations: initial verification cost, large payload and
sample-only timing/framing evidence. Retain as approved experimental debug extension;
do not claim uniform character appearance or linguistic validation. No recognition
feature schema changed; /imprint records the presentation catalog component only.
