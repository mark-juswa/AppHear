# P2-A DWPose-L Frozen Perception Result

Status: `BLOCKED_BEFORE_INFERENCE`  
Primary classification: `INCONCLUSIVE_P2A`

This is the fourth preregistered interpretation case: an environment/runtime failure prevented
valid inference. It is not a poor model-quality result and it is not evidence for or against
DWPose hand localization.

## 1. Experiment identity

Approved lane: **Candidate A — DWPose-L 256x192 whole-body**, offline native-perception
evaluation only. The attempted package is
`artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01`.

Repository state at the attempt:

- branch: `codex/recognition-stable-ru-d10`;
- HEAD: `7dd4fa05f2e7dffd3f06a2fdc88f90b1ea66836f`;
- the already-dirty worktree was preserved;
- no production environment or production source file was modified.

## 2. Checkpoint and config verification

The requested artifacts were obtained and verified without substitution.

| Artifact | Identity | Size | SHA-256 | Result |
|---|---|---:|---|---|
| DWPose checkpoint | `dw-ll_ucoco.pth` | 404,734,742 bytes | `e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7` | exact expected hash, PASS |
| Exact config | `rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py` | 7,503 bytes | `b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032` | pinned official source |
| Referenced base runtime | `default_runtime.py` | 1,278 bytes | `ee312fa38881570117466e80a6325977d22062cc782f6a2f447b26a1db0687a0` | pinned official source |

Official source snapshot: IDEA-Research/DWPose commit
`0232d66f420f411451d277905a08ff8d541dc78e` dated 2023-08-17 UTC. The config preserves 133
COCO-WholeBody outputs, left hand indices 91..111, right hand indices 112..132, input
`(192,256)` width/height, padding supplied by the standard top-down pipeline, BGR-to-RGB,
the requested mean/std, SimCC split ratio 2.0, and `flip_test=True`.

## 3. Isolated environment

The environment was created at
`artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/environment/venv`.
The production `.venv` was not changed.

| Component | Frozen attempted version |
|---|---|
| Python | 3.9.13 |
| PyTorch | 2.0.1+cpu |
| torchvision | 0.15.2+cpu |
| MMEngine | 0.9.1 |
| MMCV | unavailable after failed full build |
| MMDetection | 3.1.0 |
| MMPose | 1.1.0 |
| OpenCV | 4.8.1 |
| NumPy | 1.24.4 |
| Runtime | CPU; CUDA unavailable |

`pip check` reports no declared broken requirements, but that does not make the runtime valid:
MMDetection requires the compiled `mmcv._ext` path during its normal module registration.

## 4. Exact blocker and stop decision

The first untouched model-load smoke used the official MMPose initialization path. With
`mmcv-lite==2.0.1`, MMDetection registration imported `mmcv.ops.roi_align` and failed with:

```text
ModuleNotFoundError: No module named 'mmcv._ext'
```

One surgical corrective action was attempted: replace `mmcv-lite==2.0.1` with the official full
`mmcv==2.0.1` CPU source package. That build failed before installation with:

```text
Microsoft Visual C++ 14.0 or greater is required.
```

The machine does not currently have the required compiler toolchain, and no compatible prebuilt
full-MMCV CPU wheel was obtained through the normal package path. The approved protocol says to
stop when package compatibility cannot be achieved cleanly and forbids rewriting model code to
force execution. The run therefore stopped here.

Not attempted:

- installing a large system compiler/build-tool workload;
- bypassing normal MMDetection registration;
- copying/reimplementing CSPNeXt outside the official stack;
- substituting the 384 ONNX model or another DWPose checkpoint;
- disabling flip testing or changing preprocessing/decoding;
- changing any presence threshold, joint count, ROI, or matcher.

## 5. Benchmark execution status

Valid inference never started.

| Required item | Status |
|---|---|
| Immutable 350-row input manifest | not created after stop boundary |
| Source images processed | 0/350 |
| Positive hand rows scored | 0/184 |
| NEGATIVE_GOLD forced-ROI rows scored | 0/200 |
| Native per-image model outputs | none |
| Ungated/gated metrics | not available |
| Pairwise MediaPipe comparison | not available |
| HARD_CORE_46 / COMPLEMENTARY_16 / REGRESSION_25 | not evaluated |
| Latency / memory | not measured; model did not load |

Consequently Gates A, B, C, and D are all `NOT_EVALUATED`. No numeric placeholder, partial
output, or failed-load timing is reported as perception evidence.

## 6. Final classification

**`INCONCLUSIVE_P2A` — environment/runtime failure prevented valid inference.**

This classification does not reject DWPose-L. It preserves the exact verified checkpoint/config
and records that this Windows CPU host lacks the compiled full-MMCV runtime needed by the normal
official stack.

The smallest eligible next action, requiring separate approval, is to make the same frozen lane
executable without changing the model experiment: either install the Microsoft C++ build tools
needed to compile full MMCV 2.0.1 on this host, or move the already-frozen checkpoint/config and
future evaluator to an isolated Linux/OpenMMLab CPU environment with a compatible official MMCV
build. Do not substitute ONNX or another DWPose model under this P2-A identity.

## 7. Scope confirmation

No Sapiens, MediaPipe rerun, other detector/model, training, fine-tuning, threshold sweep,
Android test/change, S4/S5/S6/S7 change, or benchmark reconstruction occurred.

Machine-readable result:
`artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/p2a_dwpose_blocker_result.json`.
