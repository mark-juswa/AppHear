# Epoch038 Android transfer plan

The user approved export/parity/isolated integration on 2026-10-07. No training or WORD change is authorized.

The October4 application worktree remains authoritative at cee71d9f181695847936eb5f3605ea37eab82a95. Research checkout HEAD is cc1f3949114d0ed1dab38d4428191151b37df358. Both contain preserved pre-existing work. Before editing, 1,199 protected inputs were hashed and the existing fingerspelling source was copied into the separate transfer evidence directory.

Export exact TRAIN4096 epoch038 (b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886) to a new FP32 builtin-only TFLite package. Input is [1,T,405] geometry plus [1,T,1] mask, output [1,T,28] logits. The package has its own schema/manifest pin. Do not attach appearance or residual models.

The existing debug artifact-directory property selects the package internally. The loader accepts exactly the pinned old visual package or pinned new geometry package. Old branch, assets, weights and decoder remain preserved. Session width becomes package-specific with the old 1559 default retained; new geometry runtime bypasses quality/crop/appearance work entirely. Existing ownership, UI and protected analyzer/activity remain unchanged.

Gate order: Keras/TFLite logits plus greedy/beam parity; focused unit and Context Assist regressions; Xiaomi numerical/causal/mask/text parity; bounded real CameraX session engineering validation and existing ownership tests. Fixed blank27 penalty0.5 and beam10 are preserved. Android and source/hash checks must pass before retention. Device timings are measured separately from host timings. Nonexpert human attempts establish wiring only, never accuracy.

Rollback: rebuild with the existing android_oct04_build.ps1 default artifact directory to load the original visual manifest. Default and release still have the pre-existing fingerspelling flag disabled. No new model selector is added.
