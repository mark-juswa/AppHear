from __future__ import annotations

from pipeline.rgb.e6_4_confusion_registry import _consensus, _pair_decisions


def test_consensus_requires_majority_and_preserves_signer() -> None:
    rows = []
    for seed, prediction in ((101, "HELLO"), (202, "HELLO"), (303, "GOOD")):
        rows.append(
            {
                "family": "v30_primary",
                "seed": seed,
                "view": "test_fresh",
                "sample_id": "sample-1",
                "signer_id": "local:s1",
                "source_id": "local",
                "true_label": "KNOW",
                "predicted_label": prediction,
            }
        )
    result = _consensus(rows)
    assert len(result) == 1
    assert result[0]["majority_prediction"] == "HELLO"
    assert result[0]["majority_votes"] == 2
    assert result[0]["unanimous"] == 0
    assert result[0]["wrong_majority"] == 1
    assert result[0]["signer_id"] == "local:s1"


def test_pair_registration_requires_two_views_signers_and_all_seeds() -> None:
    positive_rows = []
    consensus = []
    table = []
    for view, signer in (("test_fresh", "local:s1"), ("validation_variant_stress", "local:s2")):
        sample_ids = []
        for index in range(6):
            sample_id = f"{view}-{index}"
            sample_ids.append(sample_id)
            consensus.append(
                {
                    "family": "v30_primary",
                    "view": view,
                    "sample_id": sample_id,
                    "signer_id": signer,
                    "true_label": "KNOW",
                    "majority_prediction": "HELLO",
                }
            )
            for seed in (101, 202, 303):
                positive_rows.append(
                    {
                        "family": "v30_primary",
                        "view": view,
                        "seed": seed,
                        "true_label": "KNOW",
                        "predicted_label": "HELLO",
                    }
                )
        table.append(
            {
                "family": "v30_primary",
                "view": view,
                "true_label": "KNOW",
                "predicted_label": "HELLO",
                "majority_rate": 0.6,
            }
        )
        table.append(
            {
                "family": "geometry_corroboration",
                "view": view,
                "true_label": "KNOW",
                "predicted_label": "HELLO",
                "majority_rate": 0.5,
            }
        )
    decisions, registry = _pair_decisions(positive_rows, consensus, table)
    assert len(registry) == 1
    assert registry[0]["group_id"] == "KNOW__TO__HELLO"
    assert registry[0]["supporting_sample_count"] == 12
    assert registry[0]["supporting_signer_count"] == 2
    assert next(row for row in decisions if row["group_id"] == "KNOW__TO__HELLO")["status"] == "registered_provisional"
