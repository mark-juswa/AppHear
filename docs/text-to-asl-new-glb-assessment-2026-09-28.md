# Text-to-ASL new GLB assessment and proposed replacement plan

Date: 2026-09-28. Status: **inspection complete; implementation not started**.

## Decision

The new characters can plausibly be used by the existing local WebView/model-viewer player,
without rewriting text planning, speech input/output, navigation, or recognition. They are
complete animated glTF 2.0 scenes, so the player does not need to retarget the old skeleton.
**Do not replace the bundled clips with the raw exports.** Static format compatibility is
supported; acceptable phone performance and visual/ASL equivalence are not yet established.

Recommend a default-off, three-clip **A/B/FAMILY** replacement pilot with optimized,
self-contained GLBs and the original clips retained as rollback. Optimize textures first;
bound renderer residency and make load/animation completion reliable before device rollout.
Shared character plus separate animation clips is a later option only if this pilot cannot
meet size/memory gates. No runtime implementation or source GLB modification occurred.

## Evidence and scope

- Inspected the current working checkout `dev/continuous-transition-diagnostics`, current
  Kotlin/XML/HTML/catalog, vendored model-viewer 4.3.1, existing tests, project contracts,
  and all loose GLBs under `G:/3d Characters/`.
- Machine inventory and standard-library-only audit script:
  `artifacts/text_to_asl_asset_assessment_20260928/inventory.json` and `audit.py`.
  Inventory records full-file SHA-256, image SHA-256, geometry payload SHA-256, sizes,
  meshes, local bounds, skins/joints, animation names/times/channels, materials and extensions.
- The script reads input assets; it does not optimize them. Checks cover GLB header/version/
  declared length, JSON/BIN chunk types, structural inventory and animation time extraction.
  This is **not** a complete Khronos glTF Validator run, rendered-animation test, or phone benchmark.
- ZIP central-directory inspection: `glb-003.zip` contains the same 68 GLB paths and sizes
  as the loose tree. No additional vocabulary was found in that archive; ZIP payload equality
  was not checked. `baked-002.zip` and `baked_words.zip` contain no GLBs. No archives were extracted.
- Original source files, app assets, recognition code/config/models, and UI remain unchanged.
  Existing dirty files and untracked work were preserved.
- Baseline command: `android/gradlew.bat :app:testDebugUnitTest --tests
  com.example.apphear.TextToAslPlannerTest --tests
  com.example.apphear.TextToAslAssetManifestTest --console=plain --no-daemon --max-workers=2`.
  Result: **11 tests passed, zero failures/errors/skips**. This validates the current baseline,
  not the new assets. No device was attached to ADB. No APK installation occurred.

## How the current system works

1. `TextToAslFragment` loads `AndroidAssetAslCatalogLoader`, constructs `AslPhrasePlanner`,
   resolves idle, and owns the queue/progress/replay/clear UI. Speech transcripts and the
   recognition-screen reply handoff enter the same `submitInput()` path.
2. `assets/asl_animations/manifest.json` has 102 entries. Each supplies `id`, `displayText`,
   `asset`, `type`, and `aliases`; it has no explicit animation name, duration, rig ID, or
   per-clip camera configuration. Loader opens each referenced path to check existence.
   `AslAnimationCatalog` requires an `asl_animations/...glb` path and rejects duplicate IDs
   and conflicting aliases.
3. Normalization lowercases text, removes apostrophes/question marks, strips unsupported
   punctuation, and maps whole-input hi/hey to hello. Planner takes longest alias first;
   otherwise it consumes characters with letter fallback. The bundled catalog only includes
   dedicated A/B letter clips. It does not provide full alphabet fingerspelling. The alias `i`
   means the pronoun I/ME, **not letter I**.
4. `TextToAslPlaybackController` hosts local `model_viewer.html` in a WebView. AndroidX
   `WebViewAssetLoader` serves the HTTPS appassets origin. JavaScript is enabled; file/content
   access is disabled; network loads are blocked. The renderer script is bundled locally.
5. HTML alternates two model-viewer elements and fades their opacity. `playSign(url)` loads
   the inactive viewer and chooses the first available animation; `preloadSign(url)` loads
   the next queued GLB. Each GLB supplies its own mesh, materials, skeleton and animation.
   There is no shared old character, animation retargeting, or bone-name mapping in Kotlin.
6. JavaScript sends ready/load/finished callbacks to Kotlin. Fragment advances on finished
   or a seven-second watchdog; UI displays clip text and index/total, then returns to old idle.
   WebView is destroyed in `onDestroyView`. The feature does not own camera/recognition.

Source: `android/app/src/main/java/com/example/apphear/domain/texttoasl/`,
`android/app/src/main/java/com/example/apphear/ui/texttoasl/`,
`android/app/src/main/assets/model_viewer.html`,
`android/app/src/main/res/layout/fragment_text_to_asl.xml`.

## Measured asset comparison

All values below are host inventory measurements, except explicitly marked memory estimates.

| Property | Current bundled clips | New loose exports |
|---|---:|---:|
| GLB count | 102 | 68, including experiment variants |
| Total uncompressed GLB bytes | 194,368,244 (185.36 MiB) | 3,508,288,288 (3,345.76 MiB) |
| Individual GLB size | 1.75–3.61 MiB | 49.05–50.03 MiB |
| Distinct full-file hashes | 102 | 65 |
| Distinct filename stems | 102 | 54: 26 letters and 28 word labels |
| Triangles per scene | 5,493–30,350 | 150,216 |
| Vertices in mesh definitions | representative HELLO: 19,079 | 81,018 |
| Mesh primitives per scene | 1 | 13 across 12 meshes |
| Nodes per scene | 54–70 | 1,575; one candidate has 2,011 |
| Skin joint counts | usually one skin with 52 | usually three skins: 341 + 875 + 342 |
| Animation clips per file | 1 | 1 |
| Animation channel counts | representative HELLO: 156 | 2,049–4,674 |
| Animation time span | 1.0–6.0 seconds | 1.30–3.30 seconds |
| Embedded images | usually one 4096-square JPEG/PNG | eight 2048-square PNGs |
| RGBA8 texture estimate, no mipmaps | 32–64 MiB | 128 MiB |
| External image/buffer URIs | 0 | 0 |

The new files have no geometry/texture compression extensions. Optional material extensions
are `KHR_materials_clearcoat`, `KHR_materials_specular`, and `KHR_materials_ior`;
the bundled renderer contains support for these. No required extensions are declared.
All 170 audited GLBs passed the basic container/time-inventory checks with zero script errors.

### What makes the new files large

For the corrected SORRY file: embedded PNGs = **38.46 MiB**, geometry buffer views = **9.14 MiB**,
animation views = **0.128 MiB**, inverse-bind data = **0.095 MiB**, plus JSON and alignment.
Textures comprise **78.51%** of the aggregate new GLB bytes. All 68 exports have identical
geometry buffer-view payload hashes. This supports future reuse, but is not proof that every
scene hierarchy, bind pose, or animation target is interchangeable.

Eight RGBA8 2048-square textures = 128 MiB; with a complete mip chain, approximately **171 MiB**
per asset. Two independently resident scenes could therefore need roughly **342 MiB for
textures alone**. This excludes file/decoder buffers, geometry, bones, materials, framebuffers,
WebView, app Java/native memory and cache entries. These are conservative allocation estimates,
not measured RSS/PSS/VRAM; actual texture formats and resource sharing affect allocations.
The current clips also have substantial decoded texture cost despite their small files.

PNG/JPEG/WebP file compression, ZIP/APK compression, lazy loading and downloads do not by
themselves reduce skinned-geometry complexity or decoded texture residency.

## Compatibility and performance findings

**Important — export generations differ.** Thirteen earlier pilot/checkpoint files embed the
older head/body normal-map hashes; 55 embed corrected normal-map hashes. The corrected SORRY
report documents DirectX-to-OpenGL green-channel conversion and multi-skin constraint baking.
Old and corrected generations must not be selected solely by shortest filename or directory order.
HELLO exists only in the older pilot representative set in this supplied tree, so it is not the
first recommended replacement. Verify its materials before using it.

**Important — technical export pass is not production approval.** The copied final SORRY file
hash matches `SORRY_final_export.json` exactly:
`410489cdb6be866d79be0077478332058c425f759ac0ae49b29b5a51e2c812a3`.
That report records HUMAN_PASS/technical passes, but explicitly `production_eligible: false`.
The numeric/reload/visual reports say PASS. One existing comparison image was visually inspected;
it is source/reimport evidence, not Android rendering or semantic sign verification.
No equivalent full candidate roster/provenance manifest was found for every export.

**Important — coverage differs.** No new idle GLB or full replacement for all 102 current entries
exists. Some new words overlap, some extend vocabulary, and variants repeat labels. Preserve
existing meanings and alias precedence. Do not automatically turn `I.glb` into alias `i`, or infer
BYE/COME/PAY/ALL semantics from filenames. A complete character switch requires an approved
neutral/idle and a coverage plan; the first mixed-avatar pilot is explicitly partial.

**Important — richer rig and materials cost compute.** New files have about five times the
triangles of current HELLO, 13 primitives, three skins with 1,558 joint slots, thousands of
animation channels, and alpha-masked eye/eyelash materials. Geometry compression saves bytes,
but does not remove these runtime costs. Bone/channel removal must preserve skin weights,
ancestor transforms, facial motion and hand articulation; do not flatten/rebind the rigs blindly.
All audited new meshes have zero morph targets; facial movement uses the rig.

**Important — current player issues become riskier with large assets.** These are code findings,
not newly observed device regressions:

- `viewer.play()` uses the bundled library's default infinite repetitions; the HTML never requests
  one repetition. Thus ordinary playback has no guaranteed `finished` event and can advance via
  the watchdog after looping. A passing string-presence JVM test does not establish one-shot playback.
- The seven-second watchdog starts when Kotlin requests playback, before model loading finishes.
  Slow loads consume the signing budget and can cause skipped/truncated clips. New clip spans
  fit within seven seconds individually, but load-plus-play time is unmeasured.
- `loadedUrls` is URL-global rather than per-viewer/per-load. A URL previously loaded elsewhere
  can make `waitForModel` resolve before the current viewer has loaded it again.
- Pending work is keyed only by URL. Repeated assets, clear/replay and late callbacks need request
  identity. Wait listeners are not cancelled on superseded requests; no JS GLB error callback or
  native `onRenderProcessGone` recovery exists.
- Both elements use autoplay. The inactive/preloaded element is not explicitly paused by the
  application. The library may suppress some invisible work; do not assume it releases resources.
- Vendored renderer has a model cache with default eviction threshold five. Two HTML elements
  therefore do not imply a strict two-model memory cap. Cache counts are not byte budgets.
- Cleanup is in `onDestroyView`; no explicit fragment pause/resume handling pauses this player
  when RecognitionActivity or another activity covers the fragment. Verify lifecycle residency.

**Important — compression requires local decoder resources.** Official model-viewer docs and
the exact bundled script show Draco/Basis-KTX2 default decoder URLs are remote; Meshopt needs
explicit decoder configuration. Since this WebView blocks network loads, compressed GLBs may
fail unless compatible JS/WASM decoder resources are bundled and configured on the appassets
origin before the first compressed model loads. Do not enable network as an asset-replacement fix.

## Proposed focused implementation

This is a proposed plan, not an implemented architecture or approved release budget.
Feature scope is Text-to-ASL T8 stabilization/asset replacement; no S0–S8, F, model or feature-schema
changes. No recognition accuracy claim is made. Existing held-out recognition evaluation remains
protected; baseline regression and F22 are required for a later runtime build.

1. **Freeze a pilot selection and baseline.** Keep current clips/catalog byte-identical. Record
   original hashes and the exact three new sources:
   - `G:/3d Characters/glb/A.glb`, SHA-256
     `1917a02086477cb94e31d41a05864af28fa275ad6a15dbc1c717f6c5a975196a`.
   - `G:/3d Characters/glb/B.glb`, SHA-256
     `c59bd292c1eff3b50aec03a08d34813922bbd2d9be616505f5caba1c879ce9ee`.
   - `G:/3d Characters/glb/checkpoint_4d_recovery/representatives/FAMILY.glb`, SHA-256
     `36310e92a5ab6460a2f81700eaf4612b11862db40abbcd52656785e086d2ce77`.
   All three have the corrected normal-map hash set. Human sign/material approval is still needed.

2. **Produce offline optimized copies outside Android assets.** Record exact tool versions and
   transform settings. Run full glTF validation before and after. Start with explicit dedup/prune
   and conservative animation-track resampling; retain duration, interpolation semantics, bind
   transforms, joints, finger articulation, and corrected normal maps. Avoid an omnibus optimize
   preset that silently simplifies/restructures the rig.
   Trial smaller eye/teeth/body maps while retaining head/hand detail at the actual UI scale.
   Compare original/optimized synchronized full-body, face, and hand frames over each clip, with
   special attention to fingertips, self-contact, alpha masks, skin-tone and normal-map lighting.
   Preserve source exports. No geometric decimation or bone reduction in the initial variant.

3. **Choose compression based on both bytes and residency.** Evaluate Basis/KTX2 for GPU memory
   reduction with a high-quality normal-map setting; use PNG or appropriate WebP/JPEG variants as
   compatibility controls. Meshopt is a candidate for geometry and animation buffers; Draco is an
   alternative geometry experiment, not a rig-cost fix. Decoder startup/peak-memory cost must be
   measured. Bundle all chosen decoder dependencies with licenses; use the pinned existing renderer
   unless an evidenced compatibility problem forces a separately reviewed change.

4. **Add a small default-off replacement flag and validated override manifest.** Keep the existing
   102-entry catalog authoritative. Preserve IDs, aliases, display labels and planner order; overlay
   only A, B and FAMILY paths when the flag is on. Store new files under
   `asl_animations/vnext/` to retain current path validation. Override metadata should carry original
   fallback path, animation name, duration, content hash and profile/rig identity. Invalid/missing
   overrides fall back per clip rather than disabling the entire catalog. Add no new alphabet
   aliases in this replacement milestone. Flag off uses the current catalog/player behavior.

5. **Harden only the experimental playback path.** Track request IDs and per-viewer load state;
   distinguish component-defined, model-loaded and animation-started. Start load and playback
   watchdogs separately; play a sign once, loop only idle. Cancel superseded listeners/timers.
   Route load/decoder errors to the old clip without claiming a successful translation. Configure
   modelCacheSize conservatively, pause inactive/offscreen viewers and verify resources are released.
   Start the low-memory profile with one loaded new model and no simultaneous GLB prefetch; retain
   a poster/current frame during transitions. Enable one-next-model prefetch and the existing fade
   only if measured memory allows it. Do not load the entire vocabulary or raise largeHeap.

6. **Pass offline correctness and build checks before device tests.** Current planner plans must
   remain identical with the flag off. Test override validation/fallback, alias preservation,
   repeated signs, completion exactly once, clear/replay cancellation, delayed load, load error,
   stale completion and lifecycle release. Existing 11 baseline tests are insufficient for JS
   state-machine behavior; add a meaningful JS/browser harness or instrumentation for those cases.
   Run project required JVM/build checks and hash protected runtime/model assets.

7. **Benchmark the pilot on physical phones, then decide rollout.** Compare flag-off baseline and
   flag-on candidates on Xiaomi M2101K7AG and the low-memory itel A665L when available. Record actual
   WebView version, Android/RAM, APK size, cold/warm load p50/p95, animation-start time, frame-time
   p50/p95, delivered animation FPS, app plus renderer PSS/native/Java memory, renderer deaths,
   and five-minute playback thermal/memory behavior. Exercise A/B repeats, FAMILY, mixed old/new
   queues, replay/clear while loading, rapid submissions, offline launch, background/foreground,
   navigation away/back and recognition reply routes. Run F22 after runtime changes; do not open
   protected recognition evaluation populations for an avatar experiment.

### Proposed acceptance screens (not measured achievements)

- Exact original catalog/plans and normal working behavior with the flag off; zero unintended
  changes to protected recognition sources/assets and no recognizer/navigation regression.
- Semantic/visual sign approval; no finger/face/contact degradation or missing animation.
- Pilot target: <=12 MiB per optimized GLB, <=40 MiB total added pilot assets including decoder
  allowance, <=64 MiB estimated texture residency including mipmaps per loaded new model.
  If these cannot be met without visible degradation, stop and reassess delivery/scene reuse.
- Proposed UX targets: cold request-to-visible-sign p95 <=2 seconds, warm p95 <=500 ms;
  sustained visible animation >=30 FPS on supported phone profiles. Measure complete playback,
  not reciprocal inference/frame-time alone. These are new reviewable targets, not project facts.
- No ANR/OOM/renderer death, missing/skipped/repeated sign, or steadily increasing memory across
  five minutes/repeated navigation. Residency must settle after clear/navigation. A numeric total
  PSS ceiling is deliberately open until baseline and per-phone process headroom are measured;
  Java heap size alone is not WebView GPU/process memory. No claim of device suitability yet.

## Delivery alternatives and escalation order

| Approach | Benefit | Cost/limit | Recommendation |
|---|---|---|---|
| Optimized per-sign GLBs, selected bundling | Existing URLs/player/catalog largely retained; offline | Repeats mesh/textures; total size grows with vocabulary | First pilot |
| Small offline core + optional downloadable packs | Reduces base install size; local verified cache after download | Adds server/storage/downloader/quota/offline/error contracts; no rendering-cost reduction | Only if measured full-vocabulary install budget requires it |
| Shared external textures in glTF resources | Can reduce stored duplication | Alters packaged URL/dependency validation; resource identity/sharing must be measured | Intermediate option after pilot |
| One shared avatar with multiple named animations, small packs | Loads character once per pack; first-animation limitation needs explicit selection | Large pack startup; rig/track equivalence and reset between signs need validation | Consider if per-sign delivery remains impractical |
| Persistent avatar plus separate animation data | Best long-term redundancy reduction | Requires a real mixer/track-binding interface, scene/rig identity, state reset; not supported by current player bridge | Separate bounded change only after evidence justifies it |
| Network streaming of raw 50 MiB GLBs | Smaller APK | Still downloads/parses large complete buffers and holds same costly scene; network dependence | Do not use as primary performance fix |
| Aggressive decimation/bone pruning | Potential CPU/GPU reduction | Risks handshape, face, self-contact and multi-skin behavior | Last, quality-gated experiment |

GLB loading is not progressive geometry/animation streaming in the current implementation.
Download caches need hashes, atomic install, size quotas, pinned active resources, eviction and
offline fallback if introduced later. Disk caching and the model-viewer decoded-scene cache are
different systems; each needs its own bound. No backend is needed for the initial pilot.

## Rollback and open decisions

Rollback: disable the new asset/profile flag and rebuild; original paths/catalog/player remain
available. Do not delete old clips until the larger rollout is independently verified. Do not
replace the idle with a random signing frame; mixed-avatar transitions are an acknowledged pilot
limitation. If a consistent new avatar is required before pilot review, first create and approve
a compatible neutral idle and sufficient coverage as a separate asset preparation step.

Open decisions before implementation: approve pilot plan and source candidates despite non-production
export status; confirm primary supported phone(s); accept proposed size/UX targets after baseline
measurement; choose optimized texture/decoder variant from offline comparisons. Larger-vocabulary
install budget, neutral idle and candidate roster remain rollout decisions. No new feature-schema
version or S4/F parity change is required. Capture reusable runtime patterns with /imprint and run
/review after a later implementation, then update progress.

Some older context sections still describe a placeholder Text-to-ASL screen, missing WebKit or
remote-only rendering. Later T1–T6/August rollout entries and actual source/tests establish that
the feature is implemented and locally vendored. This report flags that documentation drift;
it does not re-open the old shell migration or rewrite the working feature.

## Primary references

- [model-viewer loading/compression documentation](https://modelviewer.dev/examples/loading/):
  decoder configuration and optional lazy-loading behavior. Exact local 4.3.1 bundle was also
  inspected for extension support, cache defaults and infinite animation repetition defaults.
- [glTF Transform official documentation](https://gltf-transform.dev/): explicit dedup/prune,
  animation resampling and texture/geometry transforms. This session installed/used no optimizer.
- [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator): proposed complete
  pre/post optimization format check, not yet run.
- Project contracts: `context/text-to-asl-architecture-plan.md`, Android redesign linked documents,
  runtime constraints, feature/evaluation contracts, `context/device-smoke.md` and current tracker.
