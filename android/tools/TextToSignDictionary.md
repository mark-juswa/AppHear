# Text-to-Sign dictionary and playback

This change runs in the existing Text-to-Sign screen. It uses the bundled model-viewer GLB player through the existing Android WebViewAssetLoader. It does not install CWASA, change navigation, or alter recognition. No dependencies or UI layouts changed.

## Selected avatar and available vocabulary

The existing **Original** character selection now exposes the 203 human Wolf3D word-batch clips, plus a neutral pose sampled at time zero of that batch's HELLO clip. HELLO and BEAUTIFUL both exist for this avatar. All 203 batch models have the same geometry/texture fingerprint; the legacy 54-node character is excluded. The unchanged source animation files remain previews pending qualified ASL review. The initial HELLO frame is an engineering resting pose, not a newly authored sign; verify it visually on devices.

The existing **New** selection exposes only compatible FemaleASL assets: 27 signs and its neutral pose, with 24 additional explicit letter entries when the alphabet flag is enabled. There is no compatible HELLO in this catalog. Typing HELLO while New is selected reports it unsupported. Neither automatic legacy fallback nor unverified retargeting is allowed. Assets excluded for rig consistency remain on disk and in Git.

ASL is the current language. English word-sequence playback is not a grammatically validated ASL sentence. Existing built-in clips have UNREVIEWED metadata; hashes and animation names establish file identity, not sign meaning, licensing, handshape quality, or non-manual accuracy.

## Matching and completion

Input is normalized for capitalization, punctuation, apostrophes and spacing. A declared complete phrase alias wins. Otherwise the planner greedily selects the longest declared alias at each word boundary. Unknown complete tokens are reported individually; they never trigger random actions or automatic spelling. Internal asset IDs are not implicitly treated as aliases. The runtime prioritizes phrase dictionary entries, but their current preview status is still shown.

Each clip finishes through the player's actual animation timeline/finished event and a matching request token. The next clip starts only after that completion. A safety timeout stops playback with an error; it never advances the queue. New input, Repeat, Clear, and lifecycle pause invalidate old callbacks. The two bounded viewers reuse resident assets and show one character; they are not separate translation engines. Final completion returns to the selected neutral asset. Changing the existing explicit character setting intentionally rebuilds the engine; entering text does not.

## Adding licensed and reviewed signs

The optional bundled manifest is `app/src/main/assets/asl_animations/dictionary_extensions_asl.json`. It intentionally has zero new entries: no licensed, independently reviewed new assets were supplied. Add only a genuinely compatible GLB and a documented review record; never label repository previews reviewed simply because they render.

Each entry requires these fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique lowercase identifier matching `[a-z][a-z0-9_]*` |
| `text` | Word or phrase presented to users |
| `alternativeTextForms` | Optional additional text aliases |
| `signLanguage` | `ASL`; FSL requires a separate catalog and explicit selection |
| `avatarProfile` | `ORIGINAL_HUMAN` or `NEW_HUMAN`, after actual rig/appearance compatibility review |
| `format` | `glb` for the implemented engine |
| `asset` | Bundled secure path under `asl_animations/` ending in `.glb` |
| `type` | `word` or `phrase` |
| `animationName` | Exact existing animation name within the GLB |
| `durationMs` | Actual clip duration, 1–60000 ms; used for failure timeout, not sequencing |
| `sha256` | Lowercase SHA-256 of the complete GLB |
| `validationStatus` | `reviewed` only after documented qualified ASL evaluation |
| `source` | Authoritative provenance/reference and asset provider |
| `license` | Actual license/permission permitting bundled redistribution |
| `reviewer`, `reviewedOn`, `reviewEvidence` | Qualified reviewer, date (`YYYY-MM-DD`), and evidence location/results |
| `category` | Optional vocabulary category |

The loader checks schema/language/profile, required review/license records, secure paths, file hash, GLB header and expected action, durations, ID collisions and normalized alias collisions. Invalid additions are skipped with a diagnostic. A developer-supplied profile/review declaration is not an independent proof: inspect skeleton, mesh, handshape, movement, wrist orientation, face/body tracks and compatibility before authoring it. The loader is not a motion retargeter or linguistic validator.

Keep root `schemaVersion: 1`, `signLanguage: "ASL"`, and the `entries` array. Add exact phrase aliases only for reviewed phrase assets; do not alias an unrelated single-word clip to a whole sentence. The current adapter does not accept SiGML. A future CWASA adapter needs its own licensed engine assets and reviewed ASL dictionary.

## Checks and building

Use the existing working-baseline build helper with `-Configuration fake -OriginalWords`, and tasks `testDebugUnitTest`, `assembleDebug`, `assembleDebugAndroidTest`. The workspace also provides `outputs/Build-AppHear-PhraseQueue.ps1` to run those tasks, verify the signature and export a distinct APK. It uses the existing pinned toolchain and model packages. Public fake configuration leaves private connected services unconfigured, as before; use existing private configuration for a fully connected build.

From the Android directory, `node tools/test-text-to-sign-player.cjs` runs deterministic playback lifecycle tests against the actual player. Android unit tests cover normalized matching, whole/embedded phrases, individual unsupported words, compatible catalogs, manifest hashes and legacy flag-off behavior. Device instrumentation includes `TextToAslSequenceInstrumentedTest`, `OriginalWordBatchInstrumentedTest`, and `AslCharacterSettingsInstrumentedTest`; run `connectedDebugAndroidTest` with the same feature flags after starting an emulator or attaching a test phone. The screen test temporarily selects Original and restores the prior setting.

Device tests require WebGL and adequate storage. Inspect the real hands/fingers and transitions, exercise unsupported input and rapid Repeat, then test with networking disabled. Record real loading times and device performance; do not infer measurements from deterministic unit tests. Qualified Deaf ASL users must assess comprehension, sentence grammar and non-manual signing separately.

CWASA's official [event documentation](https://vh.cmp.uea.ac.uk/index.php/Logging_and_Event_Hooks) describes `animactive` and `animidle`; those events belong to CWASA, not the installed GLB engine. Its [conditions of use](https://vh.cmp.uea.ac.uk/index.php/CWASA_Conditions_of_Use) distinguish example-page licensing from unmodified underlying software. A renderer change alone cannot supply missing validated ASL signs. This patch retains the existing offline player to address the reported matching and avatar-switching defects without replacing the application.
