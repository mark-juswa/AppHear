# Text-to-ASL GLB optimization pilot — 2026-09-28

User authorized offline optimization and delivery under `G:\3d Characters`. The assessment's
A/B/FAMILY pilot has been prepared. This is asset preparation only; no production catalog,
Android source, decoder configuration, or runtime behavior has changed.

Delivered package: `G:\3d Characters\optimized_apphear3_20260928`.
Workspace reproduction: `artifacts/text_to_asl_asset_optimization_20260928` (ignored artifacts).
The package README, manifest, validation reports, texture comparisons and local preview are included.

| Clip | Original MiB | Compact candidate MiB | Reduction |
|---|---:|---:|---:|
| A | 49.05 | 11.85 | 75.8% |
| B | 49.05 | 11.85 | 75.8% |
| FAMILY | 49.12 | 11.90 | 75.8% |

Compact total: 37,328,448 bytes, approximately 35.6 MiB for three clips. This is not the complete
feature delivery size. Decoders, idle, catalog and other required signs add to the shipping budget.
The package contains fifteen GLBs for comparisons, not fifteen assets intended to ship together.

## Approach and measured checks

Retained 2048-pixel head textures; resized body to 1024 and eyes/teeth to 512, with normal-map
renormalization and preserved alpha. Compact candidates use ETC1S color textures and UASTC
normal textures in mipmapped KTX2, plus Meshopt buffer compression without quantization,
mesh simplification, bone pruning, or animation resampling. Larger UASTC color controls and
lossless WebP/PNG controls are included to compare quality and loader support.

All three originals match their assessed SHA-256 hashes. All 54 delivered files match workspace
checksums. Decoded nodes/transforms/skins/animation and non-index accessor data pass exact checks.
Meshopt may cyclically rotate each triangle's index order; oriented topology/winding remains exact.
The glTF writer initially removed near-identity node transforms; original node JSON was restored
and strict decoded comparisons then passed. No numeric tolerance was used to accept that drift.

The glTF validator reports zero errors. It predates full KTX2/Meshopt validation and reports
unsupported-extension/image-format diagnostics; zero errors alone is not loader compatibility proof.
Khronos `ktx validate` separately passes all eight encoded textures, and decode/image comparisons pass.
Original generated-tangent/non-root skinned-mesh warnings remain. Lossless WebP matches resized PNG
pixels exactly. KTX2 preserves alpha. Compact color PSNR is approximately 39–41 dB versus 51–54 dB
for UASTC color controls. Normal mean angular errors are 0.49–0.84 degrees relative to resized PNG.
These do not establish rendered equivalence to full-resolution originals.

An experimental normal-mode encoding inverted decoded normals and was rejected. Files named
`balanced.ktx2` from that experiment remain only in workspace diagnostics and are excluded from
delivery. Accepted `balanced.ktx2rgba`/`balanced.ktx2mixed` variants encode ordinary RGBA normals.

Estimated compressed GPU texture allocation including mipmaps is approximately 14.7 MiB, compared
with approximately 171 MiB for original RGBA textures with mipmaps. RGBA fallback is approximately
58.7 MiB. These are texture estimates; peak memory, decode time, GPU format selection, total
WebView memory and phone frame pacing have not been measured. Geometry remains 150,216 triangles.

## Tooling and scope

Pinned local Node dependencies: glTF Transform 4.3.0, meshoptimizer 1.3.0, sharp 0.35.5,
gltf-validator 2.0.0-dev.3.10. Official KTX-Software 4.4.2 portable binaries were extracted
without running its installer. No cloud asset processing service was used. Local preview includes
the existing model-viewer 4.3.1 bundle and local Basis/Meshopt decoders with attribution/licenses.
Offline asset tooling allowances are documented in code-standards/library-docs; none enter recognition.

Android main source/assets have no diff. Existing unrelated dirty work was preserved. No Android
build/device rollout or recognition accuracy claim is made. Prior assessment JVM results are baseline
evidence, not proof of integration. New decoder actual WebView loading is still unverified.

## Review using /review

- Layer 1, plan alignment: PASS for authorized offline A/B/FAMILY preparation. Broader integration pending.
- Layer 2, system integrity: PASS for this offline scope; originals/runtime/recognition contract unchanged.
- Layer 3, production readiness: FAIL / pending. No production rollout is recommended.
- Critical findings: 0 within offline preparation scope.
- Important findings: 2. (1) Rendered sign comparison/current renderer decoder loading unverified;
  (2) supported-phone load p50/p95, memory and frame pacing unmeasured, including two-viewer overlap.
- Minor findings: 1. The old glTF validator cannot cover new extensions; separate codec and decoded
  checks mitigate format/data risk but do not replace runtime testing.
- Recommendation: retain offline candidates; validate before integrating behind a default-off flag.

Static texture sheets were inspected locally. Browser-connector visual review was rejected by automatic
approval review because it might expose proprietary GLB/rendered content beyond the local machine.
Explicit permission was requested; no browser render or alternate connector bypass was performed.

## Next concrete step

Obtain permission for the pending browser-connector visual check, or arrange local human comparison.
Compare A/B/FAMILY at matching animation times, especially fingers, face, normals, alpha and completion.
Choose compact vs higher-fidelity control based on that evidence. Then implement the focused
default-off pilot with local decoders, existing-asset fallback, bounded preload/cache, error handling,
and measured cold/warm loads before target-phone rollout. Do not bulk replace the catalog.
