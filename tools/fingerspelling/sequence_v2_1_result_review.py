"""Verify and summarize saved V2.1 evidence; never run inference or training."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from model.fingerspelling_metrics import summarize
from tools.fingerspelling.pre_v2_1_quality_audit import ROOT, digest, read, score

RUN = ROOT / "runs/fingerspelling_sequence_v2_1_01"
OUT = ROOT / "artifacts/fingerspelling_sequence_v2_1_review_01"
NAMES = ("epoch038_reference", "v2_epoch046_reference", "candidate")
VIEWS = ("native", "phone", "stress_moderate", "stress_heavy", "stress_contiguous")


def close(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        for key, value in expected.items():
            close(actual[key], value)
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12), (actual, expected)
    else:
        assert actual == expected, (actual, expected)


def verify_metrics(rows: list[dict[str, Any]], saved: dict[str, Any]) -> dict[str, Any]:
    independent = score(rows)
    close(saved, summarize(rows, 10))
    for key in (
        "sequences",
        "reference_characters",
        "substitutions",
        "deletions",
        "insertions",
        "cer",
    ):
        close(saved[key], independent[key])
    if "character_recall" in saved:
        for character, value in independent["recall"].items():
            close(
                saved["character_recall"][character],
                {k: value[k] for k in ("reference", "correct")},
            )
        close(saved["correct_aligned_reference_characters"], independent["correct"])
        close(saved["predicted_characters"], independent["predicted_characters"])
        close(saved["correct_predicted_precision"], independent["precision"] or 0)
        close(saved["exact_sequences"], independent["exact"])
        close(saved["empty_predictions"], sum(not r["prediction"] for r in rows))
        close(saved["macro_signer_cer"], mean(m["cer"] for m in saved["signers"].values()))
    return independent


def without_spaces(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(
            r,
            reference=r["reference"].replace(" ", ""),
            prediction=r["prediction"].replace(" ", ""),
        )
        for r in rows
    ]


def direction(values: list[float]) -> dict[str, int]:
    return dict(
        improve=sum(v < 0 for v in values),
        regress=sum(v > 0 for v in values),
        unchanged=sum(v == 0 for v in values),
    )


def main() -> None:
    final_path = RUN / "final_evaluation.json"
    final_sha = digest(final_path)
    final = json.loads(final_path.read_text())
    completion = json.loads((RUN / "completion.json").read_text())
    identity = json.loads((RUN / "run_identity.json").read_text())
    config = identity["configuration"]
    lock = json.loads((RUN / "confirmation_lock.json").read_text())
    assert final["confirmation_lock"] == lock
    assert digest(RUN / "completion.json") == lock["completion_sha256"]
    assert (
        digest(Path(completion["best_model_path"]))
        == lock["selected_model_sha256"]
        == completion["best_model_sha256"]
    )
    assert (
        digest(Path(completion["best_training_model_path"]))
        == completion["best_training_model_sha256"]
    )
    assert (
        digest(ROOT / "model/config/fingerspelling_sequence_v2_1_01.json")
        == identity["configuration_sha256"]
        == lock["configuration_sha256"]
    )
    assert (
        config["final_decoder"]
        == lock["decoder"]
        == dict(blank_index=27, blank_penalty=0.5, beam_width=10, top_paths=1)
    )
    changed_code = [p for p, value in identity["code_sha256"].items() if digest(ROOT / p) != value]
    assert not changed_code, changed_code
    assert identity["checkpoint_selection_cohort"] == "DEV_A"
    assert not identity["dev_b_loaded_for_selection"] and not identity["test_accessed"]
    assert not final["test_accessed"] and not final["production_promoted"]
    assert digest(ROOT / config["warmstart_model"]) == lock["v2_reference_sha256"]
    assert (
        digest(ROOT / "runs/fingerspelling_train4096_01/best_candidates/epoch_038.keras")
        == lock["reference_sha256"]
    )

    foundation = read("datasets/fingerspelling/foundation_01/tranche_manifest.json")["samples"]
    train = read("datasets/fingerspelling/train4096_plan_01/train4096_manifest.json")["samples"]
    dev_b = read("datasets/fingerspelling/train4096_plan_01/dev_b/tranche_manifest.json")["samples"]
    dev_a = [r for r in foundation if r["split_role"] == "DEV"]
    groups = dict(train=train, dev_a=dev_a, dev_b=dev_b)
    ids = {k: {r["sample_id"] for r in v} for k, v in groups.items()}
    assert [len(ids[k]) for k in ("train", "dev_a", "dev_b")] == [4096, 256, 256]
    assert not ids["train"] & (ids["dev_a"] | ids["dev_b"]) and not ids["dev_a"] & ids["dev_b"]
    signers = {k: {r["official_signer_id"] for r in v} for k, v in groups.items()}
    assert not signers["train"] & (signers["dev_a"] | signers["dev_b"])
    assert [len(signers[k]) for k in ("train", "dev_a", "dev_b")] == [117, 15, 15]
    assert all(r["split_role"] == "TRAIN" for r in train)
    assert all(r["split_role"] == "DEV" for r in dev_a + dev_b)
    historical = read("runs/fingerspelling_sequence_v2_01/final_evaluation.json")
    assert final["stress_lineage"] == historical["stress_lineage"]
    assert len(final["stress_lineage"]) == 1536
    for stress in final["stress_lineage"]:
        assert stress["timesteps_deleted"] == 0
        assert stress["frames"] == stress["temporal_lineage"]["frames"]
        assert stress["withdrawn_slots"] <= stress["withdrawal_budget"]
    review: dict[str, Any] = dict(
        schema_version="apphear.fingerspelling.v2_1_saved_result_review.v1",
        final_report_sha256=final_sha,
        confirmation_lock=lock,
        inference_run=False,
        training_run=False,
        cohorts={},
        pooled_phone={},
        history=[],
        test_accessed=False,
        production_promoted=False,
    )
    verified_records = 0
    for cohort in ("dev_a", "dev_b"):
        review["cohorts"][cohort] = {}
        metadata = {r["sample_id"]: r for r in groups[cohort]}
        for view in VIEWS:
            results = {}
            for name in NAMES:
                record = final[cohort][name][view]
                rows = record["predictions"]
                assert len(rows) == len({r["sample_id"] for r in rows}) == 256
                assert {r["sample_id"] for r in rows} == ids[cohort]
                for row in rows:
                    source = metadata[row["sample_id"]]
                    assert row["reference"] == source["normalized_transcript"]
                    assert row["signer_id"] == source["official_signer_id"]
                    repeats = sum(
                        a == b for a, b in zip(row["reference"], row["reference"][1:], strict=False)
                    )
                    assert row["headroom"] == row["input_length"] - len(row["reference"]) - repeats
                result = verify_metrics(rows, record["metrics"])
                result.update(
                    no_space=verify_metrics(without_spaces(rows), record["no_space_metrics"]),
                    single_word=verify_metrics(
                        [r for r in rows if " " not in r["reference"]],
                        record["single_word_metrics"],
                    ),
                    signers=record["metrics"]["signers"],
                    subgroups=record["metrics"]["subgroups"],
                    macro_signer_cer=record["metrics"]["macro_signer_cer"],
                    ctc_infeasible=record["ctc_infeasible_retained"],
                    ctc_mean_loss=record["ctc_mean_loss_eligible_only"],
                )
                assert result["ctc_infeasible"] == sum(r["headroom"] < 0 for r in rows)
                results[name] = result
                verified_records += 3
                if name != "candidate":
                    prior_name = "candidate" if name == "v2_epoch046_reference" else name
                    prior = historical[cohort][prior_name][view]["predictions"]
                    assert rows == prior, ("Historical prediction mismatch", cohort, name, view)
            for name in NAMES[:-1]:
                old = final[cohort][name][view]["predictions"]
                new = final[cohort]["candidate"][view]["predictions"]
                assert [
                    {
                        k: r[k]
                        for k in ("sample_id", "signer_id", "reference", "input_length", "headroom")
                    }
                    for r in old
                ] == [
                    {
                        k: r[k]
                        for k in ("sample_id", "signer_id", "reference", "input_length", "headroom")
                    }
                    for r in new
                ]
                delta = [
                    sum(
                        score([b])[k] - score([a])[k]
                        for k in ("substitutions", "deletions", "insertions")
                    )
                    for a, b in zip(old, new, strict=True)
                ]
                results["candidate"]["versus_" + name] = dict(
                    sequence_direction=direction(delta),
                    signer_direction=direction(
                        [
                            results["candidate"]["signers"][s]["cer"]
                            - results[name]["signers"][s]["cer"]
                            for s in signers[cohort]
                        ]
                    ),
                )
            review["cohorts"][cohort][view] = results
    for name in NAMES:
        rows = [r for c in ("dev_a", "dev_b") for r in final[c][name]["phone"]["predictions"]]
        full = score(rows)
        full["letter_recall"] = full["letter_correct"] / full["letter_references"]
        full["no_space"] = score(without_spaces(rows))
        single = [r for r in rows if " " not in r["reference"]]
        full["single_word"] = score(single)
        review["pooled_phone"][name] = full
        saved = final["letter_discrimination_diagnostics"]["pooled_phone"][name]
        close(full["letter_recall"], saved["letter_recall"])
        close(full["letter_correct"], saved["correct_aligned_letters"])
        assert sorted(r["sample_id"] for r in single) == saved["single_word_sample_ids"]
    prior_ids = read("artifacts/fingerspelling_sequence_v2_review_01/analysis.json")
    # The previous review records membership; additionally reconstruct it directly
    # from its authoritative saved phone predictions, independent of key layout.
    previous_single = sorted(
        r["sample_id"]
        for c in ("dev_a", "dev_b")
        for r in historical[c]["candidate"]["phone"]["predictions"]
        if " " not in r["reference"]
    )
    assert len(previous_single) == 42
    assert (
        previous_single
        == final["letter_discrimination_diagnostics"]["pooled_phone"]["candidate"][
            "single_word_sample_ids"
        ]
    )
    review["previous_review_artifact_available"] = bool(prior_ids)
    recalls = review["pooled_phone"]
    flags = []
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        a, b = recalls["epoch038_reference"]["recall"][c], recalls["candidate"]["recall"][c]
        if a["reference"] >= 100 and b["recall"] - a["recall"] < -0.10:
            flags.append(c)
    assert flags == [
        r["character"]
        for r in final["letter_discrimination_diagnostics"]["common_character_safeguard_flags"]
    ]
    review["common_character_safeguard_flags"] = flags

    for path in sorted((RUN / "epochs").glob("epoch_*.json")):
        epoch = json.loads(path.read_text())
        assert (
            epoch["evaluation_cohort"] == "DEV_A"
            and not epoch["dev_b_inference"]
            and not epoch["test_accessed"]
            and not epoch["smoke_only"]
        )
        choices = epoch["temporal_choices"]
        assert len(choices) == len({r["sample_id"] for r in choices}) == 4096
        assert {r["sample_id"] for r in choices} == ids["train"]
        assert epoch["all_training_sources_retained"]
        for choice in choices:
            temporal = choice.get("temporal_lineage", choice)
            assert temporal["adapter"] == identity["adapter"]
            assert temporal["feasible"] and temporal["headroom"] >= 0
            if "temporal_lineage" in choice:
                assert choice["timesteps_deleted"] == 0
                assert choice["frames"] == temporal["frames"]
                assert choice["withdrawn_slots"] <= choice["withdrawal_budget"]
                assert (
                    choice["remaining_observed_slots"]
                    == choice["original_observed_slots"] - choice["withdrawn_slots"]
                )
        terms: list[float] = []
        for view in ("native", "phone"):
            rows = epoch["views"][view]["predictions"]
            assert {r["sample_id"] for r in rows} == ids["dev_a"]
            full = verify_metrics(rows, epoch["views"][view]["metrics"])
            no_space = verify_metrics(
                without_spaces(rows), epoch["views"][view]["no_space_metrics"]
            )
            terms.extend((full["cer"], no_space["cer"]))
        close(mean(terms), epoch["combined_raw_greedy_selection_cer"])
        loss_roundoff = abs(
            epoch["train_total_loss"]
            - epoch["train_mean_ctc"]
            - config["auxiliary_weight"] * epoch["train_local_letter_ctc"]
        )
        # Batch totals are added in FP32 before their independent epoch means;
        # edit counts/selection retain the stricter 1e-12 check above.
        assert loss_roundoff < 1e-5, loss_roundoff
        assert all(
            math.isfinite(epoch[k])
            for k in ("train_total_loss", "train_mean_ctc", "train_local_letter_ctc")
        )
        review["history"].append(
            dict(
                epoch=epoch["epoch"],
                score=mean(terms),
                main_ctc=epoch["train_mean_ctc"],
                local_ctc=epoch["train_local_letter_ctc"],
                total_loss=epoch["train_total_loss"],
                loss_combination_roundoff=loss_roundoff,
                train_seconds=epoch["train_seconds"],
                requested=epoch["requested_regimes"],
                actual=epoch["actual_regimes"],
            )
        )
    history = review["history"]
    assert [r["epoch"] for r in history] == list(range(1, completion["epoch"] + 1))
    best = min(history, key=lambda r: r["score"])
    assert best["epoch"] == completion["best_epoch"] == 34
    close(best["score"], completion["best_combined_cer"])
    anchor, non_improving = None, 0
    for row in history:
        if anchor is None or row["score"] < anchor - config["minimum_improvement"]:
            anchor, non_improving = row["score"], 0
        else:
            non_improving += 1
    close(anchor, completion["patience_anchor"])
    assert non_improving == completion["non_improving_epochs"] == 15
    assert completion["optimizer_iterations"] == completion["epoch"] * (
        4096 // config["batch_size"]
    )
    inventory = read("artifacts/fingerspelling_sequence_v2_1_gate_01/preservation_before.json")
    changed = [
        p
        for p, value in inventory.items()
        if not Path(p).is_file() or digest(Path(p)) != value["sha256"]
    ]
    assert not changed, changed
    review.update(
        verified_metric_records=verified_records,
        checked_training_epochs=len(history),
        selected_epoch=completion["best_epoch"],
        selected_model_sha256=completion["best_model_sha256"],
        protected_inventory=dict(files=len(inventory), changed=changed),
        code_identity_changed=changed_code,
        stress_lineage_records=1536,
        stress_lineage_matches_v2=True,
        single_word_membership_count=42,
        governance=dict(
            train=4096,
            dev_a=256,
            dev_b=256,
            train_signers=117,
            dev_signers=15,
            dev_b_selection=False,
            test_accessed=False,
        ),
        limitations=final["limitations"],
    )
    assert digest(final_path) == final_sha
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "analysis.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            dict(
                status="V2_1_SAVED_EVIDENCE_VERIFIED",
                report=str(OUT / "analysis.json"),
                metric_records=verified_records,
                training_epochs=len(history),
                protected_files=len(inventory),
                protected_changes=len(changed),
                inference_or_training_run=False,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
