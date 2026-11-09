# Recognition experiments

Every experiment that informs a recognition decision is recorded here with the same eleven fields, so results are
comparable and reproducible. Nothing in this directory trains, tunes or replaces a production model.

## Required fields (per experiment file)
1. **ID** (`EXP-P3-NNN`; planned, not-yet-run work is `EXP-P3-1NN`)
2. **Hypothesis** (falsifiable, stated before looking)
3. **Baseline model** (name + SHA-256 of the packaged file)
4. **Dataset and signer split** (population, signers, roles; which data is development-exposed)
5. **Configuration** (tool, command, inputs with hashes)
6. **Training parameters** (or "none: analysis only")
7. **Evaluation metrics** (definitions)
8. **Results** (numbers with their evidence label)
9. **Model size**
10. **Inference latency** (with provenance: repo-reported device / measured emulator / host)
11. **Conclusion** (including "not supported" and "cannot be decided with this data")

## Evidence labels (used everywhere)
| Label | Meaning |
|---|---|
| **REPRODUCED** | published by the repo's audit; recomputed here from the tracked files |
| **COMPUTED** | new analysis computed here from tracked files; script and result JSON in this repo |
| **REPO-REPORTED** | published by the repo; not reproduced (needs external artifacts or a device) |
| **MEASURED-EMU** | measured here on an arm64 emulator: relative cost and contract checks only, never phone speed |
| **NOT AVAILABLE** | the data does not exist in this repository |

## Rules
- One change per experiment; compare candidates on **identical** held-out inputs.
- Calibrate on calibration signers, evaluate on other signers, never touch protected TEST.
- No threshold, margin, entropy or temporal rule is adopted unless an experiment shows a gain on signer-disjoint data and its
  latency cost is stated.
- Candidates live in the debug source set only; production assets are never overwritten. Every candidate states its rollback.
- Offline, emulator and physical-device results are never merged into one number.

## Reproduce
```bash
python -m eval.recognition_experiments.model_contract_check --write-json docs/recognition_experiments/results/model_contract_check.json
python -m eval.recognition_experiments.error_analysis       --write-json docs/recognition_experiments/results/error_analysis.json
python -m eval.recognition_experiments.gate_study           --write-json docs/recognition_experiments/results/gate_study.json
python -m unittest tests.test_recognition_experiments       # needs only the standard library
```
Tools use the standard library only (no numpy/TensorFlow), read only tracked files, and are deterministic.
