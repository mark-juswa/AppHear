from __future__ import annotations

from collections import Counter

from eval.runtime_diagnostics import s2_r2_continuous_domain_correction as r2


def test_main_config_preserves_contract_and_single_candidate() -> None:
    config = r2.load_main_config()

    assert config["feature_contract"] == {
        "schema": "apphear.perception_vnext.segmentation_features.v1",
        "width": 378,
        "semantics_changed": False,
    }
    assert config["training"]["main_training_runs"] == 1
    assert config["architecture"] == "UNCHANGED_PHASE7_CAUSAL_TCN_FROM_SCRATCH"


def test_exact_phone_rows_are_complete_and_disjoint() -> None:
    rows = r2._exact_phone_rows()

    assert len(rows) == 6
    assert Counter(row["role"] for row in rows) == {
        "FIT": 4,
        "INTERNAL_DEVELOPMENT": 2,
    }
    assert sum(len(row["labels"]) for row in rows) == 232
    assert {row["sample_id"] for row in rows} == {
        f"exact_phone:session_20260921T153138Z:attempt_{index:03d}"
        for index in range(1, 7)
    }
    assert all(row["features"].shape[1] == 378 for row in rows)


def test_frozen_main_design_preserves_validation_and_exact_phone() -> None:
    design = r2.freeze_main_design()

    assert design["status"] == "FROZEN_FOR_ONE_CANDIDATE_EXTRACTION"
    assert design["fit"]["phase7_fit_views"] == 213
    assert design["fit"]["enrichment_views"] == 51
    assert design["fit"]["p1_interval_count"] == 37
    assert design["fit"]["phone_exact_attempts"] == [2, 3, 4, 6]
    assert design["internal_development"]["phase7_cal_views"] == 54
    assert design["internal_development"]["p1_interval_count"] == 8
    assert design["internal_development"]["phone_exact_attempts"] == [1, 5]
    assert design["phone"]["rested_jpeg_rows_retired_from_main_candidate"] is True
    assert design["untouched"] == {
        "e6_0F747C_S001": True,
        "future_distinct_phone_signer_session": True,
        "protected_test": True,
    }


def test_enrichment_correction_excludes_only_unsupervised_sparse_sign() -> None:
    historical = r2.freeze_main_design()
    corrected = r2.freeze_corrected_main_design()
    zero_active = {
        row["sample_id"]
        for row in corrected["sparse_label_viability"]
        if any(count == 0 for count in row["active_count_by_view"].values())
    }

    assert zero_active == {"asl:train:27973404455034934-DRINK 2"}
    assert set(corrected["exclusion"]["sample_ids"]) == zero_active
    assert corrected["fit"]["enrichment_clips"] == 16
    assert corrected["fit"]["enrichment_views"] == 48
    assert len(historical["enrichment_rows"]) == 17
    assert len(corrected["enrichment_rows"]) == 16
    assert corrected["untouched"] == historical["untouched"]


def test_enrichment_correction_changes_no_training_or_decoder_setting() -> None:
    historical = r2.load_main_config(r2.MAIN_CONFIG)
    corrected = r2.load_main_config()

    for key in ("architecture", "cadence_views", "training", "checkpoint_gates", "decoder"):
        assert corrected[key] == historical[key]
    assert corrected["fit"]["enrichment_clips"] == 16
    assert corrected["fit"]["excluded_enrichment_sample_ids"] == [
        "asl:train:27973404455034934-DRINK 2"
    ]


def test_smoke_dataset_uses_exact_phone_not_jpeg_reprocessing() -> None:
    manifest = r2.read_json(r2.OUT / "main_smoke/dataset_manifest.json")

    assert manifest["purpose"] == "SMOKE_ONLY"
    assert manifest["exact_phone_features_used"] is True
    assert manifest["jpeg_phone_features_used"] is False
    assert manifest["row_count"] == 23
    assert manifest["fit_row_count"] == 14
    assert manifest["internal_development_row_count"] == 9


def test_smoke_run_does_not_consume_main_training_run() -> None:
    result = r2.read_json(r2.OUT / "main_smoke/smoke_result.json")

    assert result["status"] == "S2_R2_SMOKE_PASS"
    assert result["smoke"] is True
    assert result["main_training_run_consumed"] is False
    assert result["untouched_validation_consumed"] is False
    assert result["protected_test_accessed"] is False
