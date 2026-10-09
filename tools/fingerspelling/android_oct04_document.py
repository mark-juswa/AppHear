"""Imprint the additive runtime contract in the isolated application worktree."""
from tools.fingerspelling.android_oct04_port import DEST, ROOT

ENTRY = '''

### Experimental bounded fingerspelling Android runtime — 2026-10-04

Application base: `cee71d9f181695847936eb5f3605ea37eab82a95` (October 4 Text-to-ASL +
Context Assist UI preservation tag). WORD/raw-v1/S2/Recognition V2 contracts remain
unchanged. This separate debug opt-in component is not a production model promotion.

| Component | Source | Contract / behavior |
|---|---|---|
| FingerspellingFeatureAdapterV1 | `android/app/src/main/java/com/example/apphear/fingerspelling/FeatureAdapterV1.kt` | Common Candidate01 observation → 405 features, stateful dt/motion; Python parity fixtures; no handedness/Z/world or profiling inputs |
| CropQualityFilterV1 / HandCropExtractorV1 | `.../fingerspelling/VisualEvidence.kt` | Frozen quality/dedup rules, upright unmirrored RGB, endpoint bilinear 128 crop, zero visual weight for rejected crops; geometry untouched |
| FingerspellModels | `.../fingerspelling/FingerspellModels.kt` | SHA/schema/config/order-pinned FP32 CPU models, frozen B2 epoch076 + residual epoch035; 1559 packed inputs=405+576+576+2 quality; 28 CTC logits; zero-quality frozen-B2 fallback |
| RecognitionModeController / FingerspellSession / FingerspellBuffer | `.../fingerspelling/FingerspellCore.kt` | Exclusive explicit owner before WORD consume; one bounded Start/Done sequence; separate preview/confirmed text, repeated letters preserved; stale cancellation tokens rejected |
| FingerspellRuntime | `.../fingerspelling/FingerspellRuntime.kt` | Camera-worker serialization, off-main load/inference, borrowed RGB only, lifecycle cancellation, diagnostic timing JSON; no new detector or training recordings |

`-Pfingerspell=true` is debug-only. `fingerspellArtifactDir` locates separately
exported pinned assets; defaults/release do not package them. Model manifest SHA
`09680096117f4d34eb86e0b71fc8681bfe3d4101082c4e0db2c8f7e9b1a1e57b`.
Android 523-observation geometry/crop parity has error 0; embedding/logit errors
within 2e-4. Six causal-prefix and six actual-checkpoint zero-visual cases pass.
TF Lite 2.16.1 dynamic shape handling invokes after resize without explicit
allocateTensors, then reads the refreshed output buffer. No model-math change.
See `docs/apphear-fingerspelling-android-oct04-integration-2026-10-04.md` for
preservation/build/phone evidence and the distinct outstanding live-domain gate.
'''

def main():
    for relative in ("docs/apphear-fingerspelling-android-oct04-integration-2026-10-04.md", "docs/apphear-fingerspelling-next-session-handoff-2026-10-05.md"):
        (DEST/relative).write_text((ROOT/relative).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    schema=DEST/"context/feature-schema.md"
    if "### Experimental bounded fingerspelling Android runtime" not in schema.read_text(encoding="utf-8"):
        with schema.open("a",encoding="utf-8") as output: output.write(ENTRY)
    progress=DEST/"context/progress-tracker.md"
    note='''

### 2026-10-04 — Additive fingerspelling integration on current baseline

- [x] Isolated worktree from cee71d9; preserves October 4 compact prediction UI,
  Context Assist provider/matcher, WORD internals and all pre-existing worktrees.
- [x] Frozen B2/residual export + 405D adapter/crop/model Android parity, explicit
  ownership before WORD consume, bounded session, preview/Use/Retry/Clear.
- [x] 154 JVM tests and focused connected prediction, raw Hear, exit and synthetic
  spelling ownership/confirmation checks pass. Default model assets absent;
  credential-free release build passed after relocating only generated files.
- [ ] Private phone-only build and controlled fresh cadence/latency/live spelling
  evidence; see the separate integration report. No production accuracy promotion.
'''
    if "Additive fingerspelling integration on current baseline" not in progress.read_text(encoding="utf-8"):
        with progress.open("a",encoding="utf-8") as output: output.write(note)
    print("Report, component registry and progress imprinted in isolated baseline worktree.")

if __name__=="__main__": main()
