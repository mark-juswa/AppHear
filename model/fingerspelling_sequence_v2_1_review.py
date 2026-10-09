"""Fixed final diagnostics for the local-letter correction. No model selection."""

from __future__ import annotations

from typing import Any

from model.fingerspelling_train4096 import score


def final_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    pooled: dict[str, Any] = {}
    names = ["candidate", "v2_epoch046_reference", "epoch038_reference"]
    for name in names:
        rows = [r for c in ["dev_a", "dev_b"] for r in result[c][name]["phone"]["predictions"]]
        full = score(rows)
        recalls = full["character_recall"]
        letters = sum(recalls[c]["correct"] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        references = sum(recalls[c]["reference"] for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        single = [r for r in rows if " " not in r["reference"]]
        pooled[name] = dict(
            full=full,
            correct_aligned_letters=letters,
            reference_letters=references,
            letter_recall=letters / references,
            space_correct=recalls[" "]["correct"],
            no_space=score(
                [
                    dict(
                        r,
                        reference=r["reference"].replace(" ", ""),
                        prediction=r["prediction"].replace(" ", ""),
                    )
                    for r in rows
                ]
            ),
            single_word=score(single),
            single_word_sample_ids=sorted(r["sample_id"] for r in single),
        )
    flags = []
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        old = pooled["epoch038_reference"]["full"]["character_recall"][c]
        new = pooled["candidate"]["full"]["character_recall"][c]
        assert old["reference"] == new["reference"]
        if old["reference"] >= 100:
            delta = (new["correct"] - old["correct"]) / old["reference"]
            if delta < -0.10:
                flags.append(
                    dict(
                        character=c,
                        reference_count=old["reference"],
                        old_recall=old["correct"] / old["reference"],
                        new_recall=new["correct"] / new["reference"],
                        delta=delta,
                    )
                )
    for name in names:
        assert (
            pooled[name]["single_word_sample_ids"] == pooled["candidate"]["single_word_sample_ids"]
        )
    assert len(pooled["candidate"]["single_word_sample_ids"]) == 42
    return dict(
        pooled_phone=pooled,
        common_character_safeguard_flags=flags,
        common_character_policy="REFERENCES_GE_100_AND_RECALL_REGRESSION_GT_10_ABSOLUTE_PP_VS_EPOCH038",
        decision="REQUIRES_SAVED_EVIDENCE_REVIEW_NOT_AUTOMATIC_CER_PROMOTION",
        no_dev_b_selection=True,
        test_accessed=False,
    )
