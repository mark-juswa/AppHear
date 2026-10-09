"""Stage 1B corrected root-cause synthesis.

Reads only frozen Stage-1A/Stage-1A-C artifacts and governed source hashes.
It performs no inference, training, dataset mutation, or protected-test access.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
OLD = BASE / "stage1a_rcab_root_cause_evidence_01"
CORR = BASE / "stage1a_correction_01"
OUT = BASE / "stage1b_root_cause_synthesis_01"
DATA = BASE / "p5b_migration_01/dataset"
CHECKPOINT = BASE / "p5b_rcab_horizon_01/best.keras"
MANIFEST = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
VOCAB = DATA / "vocab.json"
SOURCES = {
    "train": DATA / "train.npz",
    "val": DATA / "val.npz",
    "stress": DATA / "diagnostic_validation_stress.npz",
}
LATENTS = {
    "train": OLD / "stage1a_train_latents.npz",
    "val": OLD / "stage1a_val_latents.npz",
    "stress": OLD / "stage1a_stress_latents.npz",
}
EXPECTED_CHECKPOINT_SHA = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
ROOT_CLASSIFICATION = "INSUFFICIENT_EVIDENCE_TO_SEPARATE_DATA_VS_REPRESENTATION"
NEXT_CATEGORY = "NEXT_DATA_VS_REPRESENTATION_DISCRIMINATION_EXPERIMENT"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    os.replace(tmp, path)


def verify_artifact_manifest(directory: Path) -> dict[str, str]:
    manifest = json.loads((directory / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    verified: dict[str, str] = {}
    for row in manifest["artifacts"]:
        path = Path(row["path"])
        actual = sha256(path)
        if actual != row["sha256"]:
            raise RuntimeError(f"STAGE1B_ARTIFACT_HASH_MISMATCH:{path.name}")
        verified[path.name] = actual
    return verified


def evidence_reconciliation() -> pd.DataFrame:
    rows = [
        ("Same-signer/different-signer ratio = 0.4959", "CORRECTED", "NO", "104 unsupported classes contributed zeros; governed supported-only medians are 0.7334 sample-weighted and 0.7593 signer-balanced."),
        ("TRUE_AND_WRONG_CLASS_OVERLAP for 350/351 errors", "DEPRECATED_OVERPERMISSIVE_DIAGNOSTIC", "NO", "The summed-p75-radius rule was too permissive; Stage 1B uses continuous TRAIN-derived margins and LOSO pair evidence."),
        ("233/236 within/nearest-between ratio >= 1", "VALID_DESCRIPTIVE_ONLY", "YES_WITH_CAUTION", "Healthy controls can also exceed one with low LOSO confusion; the ratio is continuous context, never a failure threshold."),
        ("Classifier-versus-centroid relationships", "CORRECTED_AND_RETAINED", "YES", "Corrected five-way taxonomy preserves 168 same-wrong, 138 third-class, 45 geometry-true errors and 111 RCA-B-correct/geometry-other clips."),
        ("Temporal diagnostics", "CORRECTION_GOVERNS", "YES", "Direct frozen final-projection evidence covers all 351 validation errors and distinguishes persistent from phase-dependent failures."),
        ("Full-vocabulary coverage metrics", "UNCHANGED", "YES", "236-class signer/source/clip counts and concentration measures survive correction."),
        ("Source metrics", "VALID_BUT_GLOBALLY_UNDERSUPPORTED", "LIMITED", "Only five classes have multi-source TRAIN coverage."),
        ("KNOW/HELLO", "CORRECTED_ONE_SIGNER_DIAGNOSTIC", "YES_WITH_CAUTION", "TRAIN LOSO pair evidence is relatively clean, while 29/30 stress KNOW clips favor HELLO geometrically and temporally."),
        ("Primary-validation metrics and confusion matrix", "UNCHANGED", "YES_WITH_SUPPORT_WARNING", "Aggregate metrics are valid, but 222/236 classes have fewer than five validation clips."),
        ("Stage-1A latent arrays", "HASH_VERIFIED_REUSED", "YES", "Deterministic tcn3_add [T,64] latents remain immutable and correction-probe exact."),
    ]
    return pd.DataFrame(rows, columns=["ORIGINAL_STAGE1A_CLAIM", "CORRECTED_STATUS", "USE_IN_STAGE1B", "REASON"])


def classify_failure_taxonomy(temporal: pd.DataFrame, coverage: pd.DataFrame, class_geom: pd.DataFrame) -> pd.DataFrame:
    errors = temporal[(temporal.split == "PRIMARY_VAL") & (temporal.rcab_predicted_class_id != temporal.true_class_id)].copy()
    thirds = errors[["first_third_mean_margin", "middle_third_mean_margin", "final_third_mean_margin"]].to_numpy(float)
    true_majority = errors.fraction_true_logit_gt_competitor.to_numpy(float) > .5
    all_wrong = (thirds < 0).all(axis=1)
    mixed = (thirds < 0).any(axis=1) & (thirds > 0).any(axis=1)
    taxonomy = np.full(len(errors), "TIED_OR_OTHER", dtype=object)
    taxonomy[all_wrong] = "PERSISTENT_WRONG_CLASS"
    taxonomy[mixed] = "PHASE_DEPENDENT_CONFUSION"
    taxonomy[true_majority] = "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG"
    errors["taxonomy"] = taxonomy
    merged = errors.merge(
        coverage[["class_id", "raw_training_clips", "unique_signer_groups", "effective_signer_count"]],
        left_on="true_class_id", right_on="class_id", how="left",
    ).merge(
        class_geom[["class_id", "within_to_nearest_between_ratio"]],
        left_on="true_class_id", right_on="class_id", how="left", suffixes=("", "_geom"),
    )
    rows = []
    for category in ["PERSISTENT_WRONG_CLASS", "PHASE_DEPENDENT_CONFUSION", "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG", "TIED_OR_OTHER"]:
        part = merged[merged.taxonomy == category]
        rows.append({
            "taxonomy": category, "count": len(part), "fraction_of_351_errors": len(part) / 351,
            "median_raw_training_clips": float(part.raw_training_clips.median()) if len(part) else None,
            "median_unique_signers": float(part.unique_signer_groups.median()) if len(part) else None,
            "median_effective_signers": float(part.effective_signer_count.median()) if len(part) else None,
            "median_within_to_nearest_between_ratio": float(part.within_to_nearest_between_ratio.median()) if len(part) else None,
            "higher_support_error_count": int((part.validation_class_support >= 5).sum()) if len(part) else 0,
            "low_support_error_count": int((part.validation_class_support < 5).sum()) if len(part) else 0,
            "median_true_minus_predicted_logit_margin": float(part.true_minus_competitor_logit_p50.median()) if len(part) else None,
        })
    return pd.DataFrame(rows)


def classify_pair_regimes(pair_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    healthy = pair_df[pair_df.selection_reason.str.contains("HEALTHY_COMPARISON", na=False)]
    healthy_max = float(healthy.pairwise_nearest_centroid_confusion_rate.max())
    healthy_median = float(healthy.pairwise_nearest_centroid_confusion_rate.median())
    rows = []
    for row in pair_df.itertuples(index=False):
        min_signers = min(int(row.class_a_signer_representatives), int(row.class_b_signer_representatives))
        direct_failure = int(row.validation_a_to_b_count) + int(row.validation_b_to_a_count) > 0 or "KNOWN_KNOW_HELLO" in row.selection_reason or "POOR_PERFORMANCE" in row.selection_reason
        if min_signers < 5:
            regime = "INSUFFICIENT_PAIR_SUPPORT"
        elif "HEALTHY_COMPARISON" in row.selection_reason:
            regime = "HEALTHY_CONTROL"
        elif float(row.pairwise_nearest_centroid_confusion_rate) > healthy_max:
            regime = "TRAIN_PAIR_ALREADY_CONFUSED"
        elif direct_failure:
            regime = "TRAIN_PAIR_RELATIVELY_SEPARABLE_BUT_VAL_FAILS"
        else:
            regime = "INSUFFICIENT_PAIR_SUPPORT"
        item = row._asdict(); item["regime"] = regime
        item["healthy_control_median_confusion_rate"] = healthy_median
        item["healthy_control_max_confusion_rate"] = healthy_max
        item["regime_rule"] = "TRAIN confused only when LOSO rate exceeds empirical healthy-control maximum; support requires >=5 signer representatives per class."
        rows.append(item)
    frame = pd.DataFrame(rows)
    return frame, {
        "healthy_control_count": len(healthy), "healthy_control_median": healthy_median,
        "healthy_control_max": healthy_max, "regime_counts": frame.regime.value_counts().to_dict(),
    }


def data_assessment(coverage: pd.DataFrame, per_class: pd.DataFrame, class_geom: pd.DataFrame) -> pd.DataFrame:
    frame = coverage.merge(per_class, on="class_id", suffixes=("", "_val")).merge(
        class_geom[["class_id", "nearest_other_class_gloss", "nearest_other_class_centroid_distance", "within_to_nearest_between_ratio"]], on="class_id"
    )
    frame["validation_support_tier"] = np.where(frame.support >= 5, "HIGHER_SUPPORT_DESCRIPTIVE", "LOW_SUPPORT_EXPLORATORY")
    frame["coverage_regime"] = "TYPICAL_SPARSE_MULTI_SIGNER"
    frame.loc[frame.gloss.isin(["KNOW", "GOOD", "HAVE", "SORRY", "HELLO"]), "coverage_regime"] = "SUPPLEMENTED_HIGH_VOLUME_LOW_EFFECTIVE_DIVERSITY"
    frame["descriptive_counterexample_tags"] = ""
    low = frame.raw_training_clips <= frame.raw_training_clips.quantile(.25)
    high_div = frame.effective_signer_count >= frame.effective_signer_count.quantile(.75)
    high_raw = frame.raw_training_clips >= frame.raw_training_clips.quantile(.75)
    frame.loc[low & (frame.recall >= .8), "descriptive_counterexample_tags"] += "LOW_SAMPLE_GOOD_RECALL|"
    frame.loc[high_div & (frame.recall <= .25), "descriptive_counterexample_tags"] += "HIGH_SIGNER_DIVERSITY_POOR_RECALL|"
    frame.loc[high_raw & (frame.recall <= .25), "descriptive_counterexample_tags"] += "HIGH_RAW_COVERAGE_POOR_RECALL|"
    frame.descriptive_counterexample_tags = frame.descriptive_counterexample_tags.str.rstrip("|")
    return frame


def supplemented_assessment(data: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for gloss in ["KNOW", "GOOD", "HAVE", "SORRY", "HELLO"]:
        row = data[data.gloss == gloss].iloc[0]
        related = pairs[(pairs.class_a_gloss == gloss) | (pairs.class_b_gloss == gloss)]
        rows.append({
            "gloss": gloss, "raw_training_clips": int(row.raw_training_clips),
            "nominal_signers": int(row.unique_signer_groups), "effective_signers": float(row.effective_signer_count),
            "largest_signer_share": float(row.largest_signer_share), "top3_signer_share": float(row.top3_signer_share),
            "sources": int(row.unique_sources), "validation_support": int(row.support),
            "validation_recall": float(row.recall), "validation_f1": float(row.f1),
            "within_to_nearest_between_ratio": float(row.within_to_nearest_between_ratio),
            "pairwise_rows_available": len(related),
            "pairwise_loso_confusion_median": float(related.pairwise_nearest_centroid_confusion_rate.median()) if len(related) else None,
            "pairwise_loso_confusion_max": float(related.pairwise_nearest_centroid_confusion_rate.max()) if len(related) else None,
            "stress_behavior": "29/30 stress KNOW predicted/favored HELLO; one signer only" if gloss == "KNOW" else "NO_GOVERNED_STAGE1A_C_STRESS_CLASS_SUMMARY",
            "interpretation": "HIGH_VOLUME_LOW_EFFECTIVE_DIVERSITY_CLASS_SPECIFIC; validation behavior is mixed across the five and does not establish a vocabulary-wide cause.",
        })
    return pd.DataFrame(rows)


def hypothesis_rows() -> list[dict[str, Any]]:
    return [
        {"hypothesis":"INSUFFICIENT_VARIANT_DENSITY","what_would_support_it":"Sparse clips/class despite many signers; density tracks generalization; held-out errors outside/away from true geometry.","what_we_observe":"Median 14 clips and 13 signers; modest recall correlations (clips rho .232, unique signers .289); 306/351 errors nearest geometry not true; mixed TRAIN pair regimes.","what_expected_if_false":"Low-density classes would generalize broadly and coverage would show no relation.","contradictory_evidence":"Several 11-13 clip classes have recall 1.0; several 14-18 clip/high-diversity classes have recall 0-.25; most per-class validation support is only 3-4.","evidence_strength":"MODERATE","status":"SUPPORTED_AS_PLAUSIBLE_NOT_PRIMARY_PROVEN"},
        {"hypothesis":"SUPPLEMENTED_SIGNER_CONCENTRATION","what_would_support_it":"Large clip counts but low effective signer count and poor held-out behavior in supplemented classes.","what_we_observe":"Five supplemented classes have 120-190 clips but 2.93-4.03 effective signers; KNOW recall 0 and stress failure, but SORRY recall 1.0 and others mixed.","what_expected_if_false":"Concentration would not coexist with systematic class-specific failures.","contradictory_evidence":"Mixed outcomes among the five; not representative of the other 231 classes.","evidence_strength":"STRONG_FOR_SUBSET_MODERATE_FOR_EFFECT","status":"CLASS_SPECIFIC_SUPPORTED_NOT_GLOBAL"},
        {"hypothesis":"V2_INPUT_INFORMATION_LIMITATION","what_would_support_it":"Persistent pair confusion across independent TRAIN signers and failures consistent across temporal phases despite adequate data.","what_we_observe":"Some TRAIN pairs are heavily confused and 229 errors persist across all thirds; other pairs/healthy controls separate, and KNOW/HELLO TRAIN is relatively clean.","what_expected_if_false":"Input would support clean separation when data/learning are adequate.","contradictory_evidence":"No input-level counterfactual or alternate justified DWPose channel; bad tcn3_add is downstream of both input and learning.","evidence_strength":"INSUFFICIENT","status":"V2_INPUT_LIMITATION_UNRESOLVED"},
        {"hypothesis":"TEMPORAL_LEARNING_OBJECTIVE_LIMITATION","what_would_support_it":"Input plausibly discriminative but learned temporal logits consistently favor wrong class; centroid/classifier patterns show learned-boundary issues.","what_we_observe":"333/351 errors favor wrong on most frames and 229 across all thirds; 111 correct clips beat centroid simplification; no alternate objective control exists.","what_expected_if_false":"Learned temporal behavior would preserve true-class evidence when input/data suffice.","contradictory_evidence":"Persistent wrong latents can also result from sparse variants or insufficient input information.","evidence_strength":"MODERATE","status":"V2_VS_TEMPORAL_LEARNING_CAUSE_NOT_SEPARATED"},
        {"hypothesis":"FINAL_CLASSIFIER_BOUNDARY","what_would_support_it":"Most errors nearest true geometry but final projection wrong; true temporal evidence present but aggregation/boundary fails.","what_we_observe":"Only 45/351 errors nearest true centroid; 333/351 favor predicted on most frames; classifier is correct on 111 clips where centroid is wrong.","what_expected_if_false":"Errors would already be encoded toward wrong classes before final decision.","contradictory_evidence":"Temporal logits are already persistently wrong for most errors.","evidence_strength":"MODERATE_DIRECT","status":"SECONDARY"},
        {"hypothesis":"SIGNER_NUISANCE","what_would_support_it":"Same-class same-signer representations much closer than cross-signer across broad support.","what_we_observe":"Corrected ratios .733 sample-weighted/.759 signer-balanced over 132 classes; p90 >1; signer effect exists but is moderate and heterogeneous.","what_expected_if_false":"Ratio near one with little supported difference.","contradictory_evidence":"104 classes lack repeat-signer support; ratio is much less extreme than original biased .496.","evidence_strength":"MODERATE","status":"PRESENT_NOT_SUFFICIENTLY_GLOBAL_CAUSE"},
        {"hypothesis":"SOURCE_DOMAIN","what_would_support_it":"Broad same-class multi-source separation tied to errors.","what_we_observe":"Only five classes have multi-source TRAIN coverage; one stress signer/source is diagnostic only.","what_expected_if_false":"Cross-source distances similar or source-independent across broad vocabulary.","contradictory_evidence":"Coverage cannot support a global test.","evidence_strength":"INSUFFICIENT","status":"SOURCE_EFFECT_GLOBAL_INSUFFICIENT_EVIDENCE"},
        {"hypothesis":"MISSINGNESS_OR_PERCEPTION","what_would_support_it":"Errors concentrate in severe observed-mask/dropout strata and persist after representation/training controls.","what_we_observe":"Historical missingness is secondary; strong/moderate observation strata also perform poorly; Stage 1A did not establish error causality.","what_expected_if_false":"Failures remain broad outside missingness-heavy clips.","contradictory_evidence":"RCA-B generalization gap is not confined to weak observation; P4 remains frozen.","evidence_strength":"WEAK","status":"SECONDARY_NOT_PRIMARY"},
        {"hypothesis":"OPTIMIZATION_HORIZON","what_would_support_it":"Metrics materially improve with governed longer training and remain underconverged.","what_we_observe":"RCA-B already completed the controlled 100-epoch extension and became viable; remaining gap persisted.","what_expected_if_false":"Adequate horizon would leave a residual generalization issue.","contradictory_evidence":"Another automatic extension was explicitly closed.","evidence_strength":"STRONG","status":"RULED_OUT_AS_PRIMARY"},
        {"hypothesis":"TCN_CAPACITY","what_would_support_it":"Both train and validation remain poorly fit after convergence, with evidence larger capacity is needed.","what_we_observe":"TCN learns V2 and fits training substantially better than unseen signers; no capacity ablation supports this cause.","what_expected_if_false":"Generalization gap can persist despite adequate fit.","contradictory_evidence":"Evidence points to generalization, not inability to fit.","evidence_strength":"WEAK","status":"LOW_NOT_ESTABLISHED"},
        {"hypothesis":"HISTORICAL_AUGMENTATION_ABSENCE","what_would_support_it":"Restored compatible package improves clean validation/generalization.","what_we_observe":"RCA-C materially harmed validation; full transfer rejected; no compensating stress benefit.","what_expected_if_false":"Package would fail or overregularize.","contradictory_evidence":"RCA-C3 isolated temporal distortion and closed package as primary solution.","evidence_strength":"STRONG","status":"RULED_OUT_AS_PRIMARY"},
        {"hypothesis":"HISTORICAL_CANONICALIZATION_ABSENCE","what_would_support_it":"Canonicalization broadly reduces signer variation without semantic damage.","what_we_observe":"Roll effect ~0.7%; dominance worsened signer variation and changed semantics.","what_expected_if_false":"Little benefit or semantic instability.","contradictory_evidence":"RCA-C3 rejected it as next intervention.","evidence_strength":"STRONG","status":"RULED_OUT_AS_PRIMARY"},
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)
    context_before = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    old_verified = verify_artifact_manifest(OLD)
    corr_verified = verify_artifact_manifest(CORR)
    corr_integrity = json.loads((CORR / "stage1a_correction_integrity.json").read_text(encoding="utf-8"))
    if not corr_integrity.get("passed") or not corr_integrity.get("latents_unchanged"):
        raise RuntimeError("STAGE1B_CORRECTION_INTEGRITY_FAILURE")
    source_before = {
        "checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB),
        **{name: sha256(path) for name, path in SOURCES.items()},
        **{f"latent_{name}": sha256(path) for name, path in LATENTS.items()},
    }
    if source_before["checkpoint"] != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("STAGE1B_CHECKPOINT_MISMATCH")
    if any(source_before[k] != corr_integrity["source_hashes_after"][k] for k in source_before):
        raise RuntimeError("STAGE1B_SOURCE_HASH_CONFLICT")

    reconciliation = evidence_reconciliation()
    reconciliation.to_csv(OUT / "stage1b_evidence_reconciliation.csv", index=False)
    coverage = pd.read_csv(OLD / "stage1a_class_coverage_summary.csv")
    per_class = pd.read_csv(OLD / "stage1a_primary_val_per_class.csv")
    associations = pd.read_csv(OLD / "stage1a_coverage_performance_associations.csv")
    class_geom = pd.read_csv(CORR / "stage1a_class_geometry_corrected.csv")
    signer_bias = json.loads((CORR / "stage1a_signer_geometry_bias_audit.json").read_text(encoding="utf-8"))
    classifier = pd.read_csv(CORR / "stage1a_classifier_geometry_corrected.csv")
    temporal = pd.read_csv(CORR / "stage1a_temporal_classifier_diagnostics.csv")
    pairs = pd.read_csv(CORR / "stage1a_pairwise_separation.csv")
    know = pd.read_csv(CORR / "stage1a_know_hello_temporal_diagnostic.csv")

    data = data_assessment(coverage, per_class, class_geom)
    data.to_csv(OUT / "stage1b_data_coverage_assessment.csv", index=False)
    taxonomy = classify_failure_taxonomy(temporal, coverage, class_geom)
    taxonomy.to_csv(OUT / "stage1b_failure_taxonomy.csv", index=False)
    pair_regimes, pair_summary = classify_pair_regimes(pairs)
    pair_regimes.to_csv(OUT / "stage1b_pairwise_failure_regimes.csv", index=False)
    supplemented = supplemented_assessment(data, pairs)
    supplemented.to_csv(OUT / "stage1b_supplemented_class_assessment.csv", index=False)

    hypotheses = pd.DataFrame(hypothesis_rows())
    hypotheses.to_csv(OUT / "stage1b_hypothesis_evidence_matrix.csv", index=False)
    hypotheses.to_csv(OUT / "stage1b_counterfactual_evidence.csv", index=False)

    ranking_rows = [
        ("sparse variant density", "MEDIUM-HIGH", "Median 14 clips/class despite 13 signers; modest positive coverage correlations and many geometry-away errors, but strong counterexamples and weak per-class validation support."),
        ("supplemented signer concentration", "HIGH", "High only for the five-class subset: 120-190 clips but 2.93-4.03 effective signers; outcomes are mixed and the regime is not vocabulary-wide."),
        ("V2 input sufficiency", "INSUFFICIENT", "Some TRAIN pairs confuse, others separate; no input-level counterfactual distinguishes V2 information from data or learning."),
        ("temporal learning/objective", "MEDIUM-HIGH", "333/351 errors favor wrong on most frames and 229 persist across thirds, but this downstream symptom is confounded with data and V2 input."),
        ("signer nuisance", "MEDIUM", "Corrected ratios .733/.759 across 132 supported classes show moderate heterogeneous signer encoding."),
        ("source/domain", "INSUFFICIENT", "Only five multi-source TRAIN classes; one stress signer cannot establish a global effect."),
        ("final classifier", "LOW", "Only 45/351 errors have nearest geometry true; most temporal logits already favor wrong, while RCA-B beats centroid on 111 correct clips."),
        ("missingness", "LOW", "Historical strata show a secondary penalty, not the majority explanation."),
        ("perception limitation", "LOW", "P4 limitations exist but Stage 1A does not tie them to the broad generalization gap."),
        ("optimization horizon", "RULED_OUT", "Controlled 100-epoch RCA-B addressed underconvergence; residual gap remained."),
        ("TCN capacity", "LOW", "Model fits training and no capacity comparison implicates size."),
        ("historical augmentation absence", "RULED_OUT", "RCA-C transfer harmed primary validation and yielded no meaningful stress gain."),
        ("historical canonicalization absence", "RULED_OUT", "Roll benefit was tiny and dominance canonicalization worsened variation/semantics."),
        ("representation corruption", "RULED_OUT", "V2 and Stage-1A hashes, masks, deterministic conversion, and latent extraction all pass."),
    ]
    ranking = pd.DataFrame(ranking_rows, columns=["hypothesis", "rank", "evidence"])
    ranking.to_csv(OUT / "stage1b_hypothesis_ranking.csv", index=False)

    persistent = int(taxonomy.loc[taxonomy.taxonomy == "PERSISTENT_WRONG_CLASS", "count"].iloc[0])
    phase = int(taxonomy.loc[taxonomy.taxonomy == "PHASE_DEPENDENT_CONFUSION", "count"].iloc[0])
    true_majority = int(taxonomy.loc[taxonomy.taxonomy == "TRUE_TEMPORAL_MAJORITY_BUT_FINAL_WRONG", "count"].iloc[0])
    tied = int(taxonomy.loc[taxonomy.taxonomy == "TIED_OR_OTHER", "count"].iloc[0])
    know_geom_hello = int((know.geometry_pairwise_favor == "HELLO").sum())
    know_temporal_hello = int((know.temporal_pairwise_favor == "HELLO").sum())
    know_pair = pairs[((pairs.class_a_gloss == "HELLO") & (pairs.class_b_gloss == "KNOW")) | ((pairs.class_a_gloss == "KNOW") & (pairs.class_b_gloss == "HELLO"))].iloc[0]

    v2_md = f"""# Stage 1B — V2 Input Representation Assessment

`V2_INPUT_LIMITATION_UNRESOLVED`.

The corrected evidence proves that many frozen `tcn3_add` sequences favor wrong classes, but `tcn3_add` is downstream of data coverage, `[96,238]`, and the temporal learning process. Selected TRAIN pairs show both high and low LOSO confusion, and healthy controls demonstrate that the continuous within/between ratio is not a failure threshold. KNOW/HELLO is relatively clean in TRAIN (LOSO pair confusion `{know_pair.pairwise_nearest_centroid_confusion_rate:.4f}`) while the held-out stress realization shifts toward HELLO. No governed input-level counterfactual establishes missing DWPose information. Therefore V2 sufficiency is neither confirmed nor falsified.
"""
    atomic_text(OUT / "stage1b_v2_representation_assessment.md", v2_md)
    temporal_md = f"""# Stage 1B — Temporal Learning/Objective Assessment

`V2_VS_TEMPORAL_LEARNING_CAUSE_NOT_SEPARATED`.

The learned temporal symptom is direct and strong: `{persistent}` persistent wrong-class errors, `{phase}` phase-dependent errors, and `{true_majority}` true-majority/final-wrong errors. Across the original corrected summary, 333/351 errors favor the predicted class on most real frames. This is consistent with insufficient signer-invariant/discriminative temporal learning, but the same pattern can arise when natural variants are sparse or the input omits discriminative information. No alternative objective/model control exists, so temporal learning cannot be selected as the primary cause.
"""
    atomic_text(OUT / "stage1b_temporal_learning_assessment.md", temporal_md)
    classifier_md = """# Stage 1B — Final Classifier Assessment

Final-classifier limitation is `LOW/SECONDARY`, not primary. Only 45/351 errors have the true class as nearest signer-balanced centroid, whereas 168 match RCA-B's wrong class and 138 favor a third class. Temporal projection behavior already favors the wrong class on most frames. Conversely, RCA-B correctly classifies 111 clips whose nearest centroid is another class, showing useful structure beyond centroid geometry. The 45 disagreements remain descriptive and are not automatically classifier failures.
"""
    atomic_text(OUT / "stage1b_classifier_assessment.md", classifier_md)
    signer_md = f"""# Stage 1B — Signer and Source Assessment

Signer/style structure is present but moderate and heterogeneous: `{signer_bias['supported_classes']}/236` classes support the comparison; corrected sample-weighted median ratio `{signer_bias['corrected_supported_only_median_ratio']:.4f}`, signer-balanced `{signer_bias['corrected_supported_only_signer_balanced_median_ratio']:.4f}`, with p25/p50/p75/p90 `{signer_bias['supported_ratio_percentiles']['p25']:.4f}/{signer_bias['supported_ratio_percentiles']['p50']:.4f}/{signer_bias['supported_ratio_percentiles']['p75']:.4f}/{signer_bias['supported_ratio_percentiles']['p90']:.4f}`. This establishes signer encoding, not vocabulary-wide causality.

Global source attribution is `SOURCE_EFFECT_GLOBAL_INSUFFICIENT_EVIDENCE`: only five classes have multi-source TRAIN coverage. The single AppHear stress signer is diagnostic only.
"""
    atomic_text(OUT / "stage1b_signer_source_assessment.md", signer_md)
    know_md = f"""# Stage 1B — KNOW/HELLO Case

KNOW/HELLO is one repeatedly inspected signer case, not a global cause. TRAIN pair LOSO confusion is `{know_pair.pairwise_nearest_centroid_confusion_rate:.4f}` (HELLO-to-KNOW `{know_pair.class_a_loso_closer_to_b_fraction:.4f}`, KNOW-to-HELLO `{know_pair.class_b_loso_closer_to_a_fraction:.4f}` in stored row order), below the empirical healthy-control maximum `{pair_summary['healthy_control_max']:.4f}`. Yet `{know_geom_hello}/30` stress KNOW clips are geometrically closer to HELLO and `{know_temporal_hello}/30` temporally favor HELLO, with 29/30 predicted HELLO. This is `UNSEEN_VARIANT_GENERALIZATION_FAILURE` for this realization, but it does not separate missing variant density, signer/source shift, V2 sensitivity, or temporal learning.
"""
    atomic_text(OUT / "stage1b_know_hello_case.md", know_md)

    reconciliation_counts = reconciliation.CORRECTED_STATUS.value_counts().to_dict()
    decision = {
        "classification": ROOT_CLASSIFICATION,
        "confidence": "HIGH",
        "confirmed_symptom": "LEARNED_TEMPORAL_GENERALIZATION_FAILURE",
        "rationale": "The wrong class is encoded across most error sequences, but mixed TRAIN pair regimes, sparse typical class density, class-specific concentration, healthy controls, and absence of an input/objective counterfactual prevent causal separation of data density, V2 input sufficiency, and temporal learning.",
        "next_intervention_category": NEXT_CATEGORY,
        "next_question": "Holding DWPOSE_REPRESENTATION_V2_238, the RCA-B causal TCN, objective, and evaluation protocol fixed, does increasing independent natural signer/variant density for a preregistered controlled class subset improve learned TRAIN pair separation and held-out generalization relative to matched unchanged classes?",
        "first_factor_to_isolate": "INDEPENDENT_NATURAL_VARIANT_DENSITY",
        "experiment_executed": False, "training_authorized": False, "data_collection_authorized": False,
        "v2_modification_authorized": False, "p4_reopened": False, "p5c_started": False,
    }
    atomic_json(OUT / "stage1b_decision.json", decision)
    atomic_json(OUT / "stage1b_next_intervention_contract.json", {
        "category": NEXT_CATEGORY,
        "status": "QUESTION_FROZEN_ONLY_NOT_AUTHORIZED",
        "question": decision["next_question"],
        "isolate_first": "INDEPENDENT_NATURAL_VARIANT_DENSITY",
        "held_fixed": ["DWPOSE_REPRESENTATION_V2_238", "RCA-B causal TCN", "per-frame CE objective", "optimizer/training contract", "splits/evaluation semantics"],
        "not_authorized": ["data collection", "training", "V2 modification", "architecture change", "P4 reopening", "P5-C", "Android modification"],
    })

    result = f"""# Stage 1B — Corrected Root-Cause Synthesis

## Decision

**Classification:** `{ROOT_CLASSIFICATION}`  
**Confidence:** HIGH  
**Confirmed symptom:** `LEARNED_TEMPORAL_GENERALIZATION_FAILURE`

The corrected evidence strongly establishes the downstream symptom but does not causally separate sparse natural variant density, V2 input sufficiency, and the temporal learning/objective. Mixed TRAIN pair regimes and falsifying counterexamples prevent a data-only, V2-only, or objective-only conclusion.

## Key synthesis

- Typical coverage is sparse but signer-broad: median 14 clips, 13 signers, 12.65 effective signers. Coverage correlations with recall are modest, and counterexamples run both directions.
- The five supplemented classes form a distinct high-volume/low-effective-diversity regime; their validation outcomes are mixed, so the regime is supported only as a subset issue.
- Corrected signer ratios `.7334/.7593` show moderate signer/style encoding over 132 supported classes, not the originally overstated `.4959` effect.
- Error taxonomy: persistent `{persistent}`, phase-dependent `{phase}`, true-temporal-majority/final-wrong `{true_majority}`, tied/other `{tied}`.
- Pair regimes: `{json.dumps(pair_summary['regime_counts'], sort_keys=True)}`. Healthy-control LOSO median/max are `{pair_summary['healthy_control_median']:.4f}/{pair_summary['healthy_control_max']:.4f}`.
- Final classifier is secondary: only 45 errors have geometry nearest the true class, while temporal logits already favor wrong classes in most errors.
- Global source evidence is insufficient; only five classes are multi-source in TRAIN.
- KNOW/HELLO is a held-out variant failure for one signer, not a global causal result.

## Next category

`{NEXT_CATEGORY}`. Only the discrimination question is frozen; no intervention is executed or authorized.
"""
    atomic_text(OUT / "STAGE1B_ROOT_CAUSE_RESULT.md", result)

    source_after = {
        "checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB),
        **{name: sha256(path) for name, path in SOURCES.items()},
        **{f"latent_{name}": sha256(path) for name, path in LATENTS.items()},
    }
    context_after = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    integrity = {
        "passed": source_before == source_after and context_before == context_after,
        "original_stage1a_artifacts_verified": len(old_verified),
        "correction_artifacts_verified": len(corr_verified),
        "source_hashes_before": source_before, "source_hashes_after": source_after,
        "training_performed": False, "protected_primary_test_opened": False,
        "new_checkpoint_created": False, "rcab_changed": source_before["checkpoint"] != source_after["checkpoint"],
        "v2_changed": source_before["train"] != source_after["train"] or source_before["val"] != source_after["val"] or source_before["stress"] != source_after["stress"],
        "stage1a_latents_changed": any(source_before[f"latent_{n}"] != source_after[f"latent_{n}"] for n in LATENTS),
        "vocabulary_changed": source_before["vocabulary"] != source_after["vocabulary"],
        "manifest_changed": source_before["manifest"] != source_after["manifest"],
        "context_files_modified": context_before != context_after,
        "progress_tracker_untouched": context_before.get("context/progress-tracker.md") == context_after.get("context/progress-tracker.md"),
        "artifact_conflicts_beyond_documented_corrections": False,
        "reconciliation_status_counts": reconciliation_counts,
    }
    atomic_json(OUT / "stage1b_integrity.json", integrity)
    if not integrity["passed"]:
        raise RuntimeError("STAGE1B_INTEGRITY_FAILURE")

    artifacts = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            artifacts.append({"path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})
    atomic_json(OUT / "artifact_hash_manifest.json", {
        "artifacts": artifacts,
        "supporting_code": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        "training_performed": False, "protected_primary_test_opened": False,
    })
    print(json.dumps({"status":"APPHEAR_STAGE1B_ROOT_CAUSE_SYNTHESIS_COMPLETE","decision":decision,"taxonomy":taxonomy.to_dict("records"),"pair_summary":pair_summary,"integrity":integrity,"artifact_directory":str(OUT.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
