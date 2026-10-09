"""Refresh auditable one-letter gate evidence and append operational registry once."""

# ruff: noqa: E501 -- literal Markdown registry tables preserve document layout.

from __future__ import annotations

import json

from tools.fingerspelling.android_export import write_json
from tools.fingerspelling.single_letter_port import OUT, REPO


def run() -> None:
    parity = json.loads((OUT / "xiaomi_fingerspell_single_letter_parity.json").read_text())
    identity = json.loads((OUT / "apk_identities.json").read_text())
    preservation = json.loads((OUT / "preservation.json").read_text())
    physical_path = OUT / "physical_smoke.json"
    physical = json.loads(physical_path.read_text()) if physical_path.is_file() else None
    write_json(
        OUT / "engineering_gate.json",
        {
            "status": (
                "SINGLE_LETTER_ENGINEERING_PASS_PHYSICAL_CHECK_RECORDED"
                if physical else "SINGLE_LETTER_ENGINEERING_PASS_PHYSICAL_IDENTIFICATION_PENDING"
            ),
            "decoder": "apphear.fingerspelling.single_letter_ctc.v1",
            "candidate": "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY",
            "blank_penalty": 0.5,
            "beam_reference_width": 10,
            "parity": {k: v for k, v in parity.items() if k != "rows"},
            "host_tests": identity["host_unit_tests"],
            "preservation": preservation,
            "all_application_assets_identical": identity["identical_application_assets"],
            "retrained": False,
            "reliable_alphabet_claim": False,
            "test_accessed": False,
            "physical_gate": physical or "PENDING_USER_INDIVIDUAL_A_M_Y_CAPTURES",
            "report": "docs/apphear-fingerspelling-single-letter-gate-2026-10-08.md",
        },
    )
    blocks = {
        "context/feature-schema.md": """

## One-letter inference contract — 2026-10-08

Adapter.v1 [T,405] unchanged. Operational contract: context/fingerspelling-single-letter-v1.md.

| Component | Source | Input -> output | Contract / preservation |
|---|---|---|---|
| Exact singleton CTC | model/fingerspelling_single_letter.py; authoritative October4 worktree FingerspellSingleLetterDecoder.kt | unadjusted[T,28] ->oneA–Z orRetry | apphear.fingerspelling.single_letter_ctc.v1;blank27/.5once;exactalignment sum;empty/SPACE refusal;no confidence guarantee or language prior |
| Exact no-input guard | pipeline/fingerspelling/input_evidence.py; FingerspellInputEvidence | observed-slot ANDvalidjoint ->usable/refusal | no fraction threshold;partial missingness retained;no temporal/feature edits;Fingerspell only |
| Confirmed-letter buffer | FingerspellCore.confirmLetter/FingerspellRuntime | one-letter preview+Use ->concatenated spelling | repeats preserved;Retry retains/Clear removes;internal candidate-restricted flag;WORD sentence path unchanged |

54Python/JVM/Xiaomi fixtures exact,66Python/161Android host checks,14modelparity
cases and ownership/Context Assist checks pass.1756existing hashes/237APK assets
preserved. Interaction constraint is not a repaired alphabet classifier. Bounded
human identification gate pending; no all26 accuracy claim or retraining.
""",
        "context/progress-tracker.md": """

### 2026-10-08 — one-letter Fingerspell inference gate

- [x] Supervisor approved one capture per letter plus confirmation.
- [x] Exact singleton CTC reference/Kotlin port; frozen V2.1/Adapter/Candidate01 unchanged.
- [x] No-usable-hand refusal, repeated-letter confirm buffer, old beam/greedy rollback.
- [x]66Python/161Android host tests;54JVM/Xiaomi exactfixtures;14frozen-modelparity;
  ownership/exclusion/no-input and3local Context Assist checks.
- [x]1756existingfile inventory and237byte-identical app assets;WORD/UI/Context untouched.
- [ ] Bounded intended A/M/Y individual-capture check; reliable isolated A–Z not established.

No training/model/data change. Engineering gate passes, recognition gate pending.
Report docs/apphear-fingerspelling-single-letter-gate-2026-10-08.md; new private
APK/evidence artifacts/fingerspelling_single_letter_01. No automatic fallback to
another training or heuristic cycle if it still chooses wrong letters.
""",
        "memory.md": """

### 2026-10-08 — one-letter inference, latest work

User defense tomorrow; no retraining permitted. User explicitly accepts one
capture per letter + confirmation. Implemented exact singleton CTC using frozen
V2.1 epoch034:blank27/.5once;A–Z score;empty/SPACE refusal;no LM/confidence cutoff.
New no-usable-hand guard plus live evidence feedback;new confirmLetter appends
without spaces and preserves repeats;old whole-sequence/beam/greedy rollback.
Only isolated FingerspellCore/Runtime/ownership fixture changed;new decoder/tests.
Private newAPKeb629845aa3c859cc7e9ed375d3ed22414fe01db1a4345ca75f815e084fe5e4e;
oldV2.1APK/epoch038 packages and model/adapter/perception/WORD/Context untouched.
66Python/161hosttests;54JVM/Xiaomi fixtures exact(maxscoreerror4.55e-13),14model
parity and ownership/no-input/repeat/Context checks pass;1756hashes237assets pass.
New logs save bounded logits/timestamps/usable flags,notRGB/landmarks/trainingdata.
Engineering pass only; individual A/M/Y human request pending. Do not claim this
fixes actual class confusion: it only prohibits extra letters within eachcapture.
Next action: retrieve those new diagnostics and evaluate actual practical result,
then report honestly without another training/decoder tuning cycle. All26/proficient
signer validation unavailable. Report/evidence: single-letter-gate doc/artifacts.
""",
    }
    for relative, block in blocks.items():
        path = REPO / relative
        value = path.read_text(encoding="utf-8")
        if block.strip().splitlines()[0] not in value:
            path.write_text(value + block, encoding="utf-8")
    print("SINGLE_LETTER_ENGINEERING_PASS; " + (
        "bounded physical check recorded" if physical else "physical identification pending"
    ))


if __name__ == "__main__":
    run()
