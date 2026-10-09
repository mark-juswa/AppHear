# Text-to-ASL repeatable optimization batch

User accepted the pilot appearance and authorized further optimization with a repeatable command.
Implemented `tools/text_to_asl_assets/Optimize-Characters.ps1`, `batch.mjs`, and shared
`verification.mjs`. Convenient machine-local launcher: `G:\3d Characters\Optimize-Characters.ps1`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "G:\3d Characters\Optimize-Characters.ps1"
```

Default output is `G:\3d Characters\optimized_apphear3_batch`. This command has already run:
51 corrected signs completed, zero failures, 2,502.69 MiB original → 605.16 MiB optimized
(75.82% reduction); individual files 11.85–11.92 MiB. Includes 26 letters and 25 word signs.
All 51 then passed a launcher resume run with unchanged source/output checksums; no GLB regenerated.

## Safeguards and scope

Reuses the hash-pinned approved pilot's eight encoded KTX2 textures. No repeated texture encoding,
cloud processing, package installation or network access occurs during the batch. Source inventory
hashes must match. Originals are read-only. Distinct output folders, exclusive process lock,
write-once GLBs, atomic summary updates and checksum-verified resume preserve completed work.
Processing is sequential. Each generation checks nontexture bytes, decoded node/rig/animation and
non-index accessor data, oriented triangle topology, zero glTF-validator errors, and written hashes.
Shared encoded textures pass official Khronos KTX validation. No mesh decimation or quantization.

17 source variants were excluded, including older normal-map exports and all SORRY recovery
candidates. The only unique signs not converted are HELLO, THEM and SORRY. Old textures need separate
review; SORRY remains production-ineligible. No automatic choice between conflicting corrected
exports is allowed. Source identifiers are not new UI vocabulary or catalog semantic mappings.

Node 24 and the existing machine-local pilot artifacts/dependencies are required; scripts fail if
they are missing. The tracked README explains source selection, subset/plan commands, report paths,
lock recovery and reproduction limits. This is a local reusable command, not a standalone portable
installer. No app/recognition runtime source or assets changed. No feature schema version changed;
the offline utility is documented in the component registry for continuity.

## Validation / review

- Node syntax checks pass; generated A matches the accepted pilot SHA-256 exactly.
- A resume test passes. Full 51-sign generation and full resume pass; zero failures.
- Explicit HELLO selection is refused as expected, before output writes.
- Android main source/assets have no diff. Documentation whitespace check passes.
- Old GLB validator lacks full new-extension coverage; separate KTX/data checks are not a runtime proof.
- /review plan alignment: PASS; system integrity for offline scope: PASS; production readiness: PENDING.
- Critical findings: 0. Important: 2 (additional signs need visual/semantic animation review;
  decoder WebView loading, phone peak memory, frame pacing and load p50/p95 remain unmeasured).
  Minor: 1 (command depends on machine-local generated pilot artifacts).
- Recommendation: retain offline derivatives and command; continue focused flagged integration only
  after those checks. The entire 605 MiB set is not a recommendation to bundle everything in the app.

Machine-readable results and warnings: `G:\3d Characters\optimized_apphear3_batch\reports\batch-summary.json`
and per-file validation reports. Existing pilot decoder/license assets remain in its delivery folder.
No further browser connector access was attempted; user supplied the pilot appearance acceptance.
