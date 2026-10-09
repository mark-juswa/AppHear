"""Preregister the post-Stage-1B variant-density causal pilot.

Design-only: no data collection, inference, training, checkpoint creation,
dataset mutation, protected-test access, or context modification.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/recognition_upgrade/p5_representation_v2"
STAGE1A = BASE / "stage1a_rcab_root_cause_evidence_01"
CORR = BASE / "stage1a_correction_01"
STAGE1B = BASE / "stage1b_root_cause_synthesis_01"
OUT = BASE / "variant_density_pilot_design_01"
DATA = BASE / "p5b_migration_01/dataset"
CHECKPOINT = BASE / "p5b_rcab_horizon_01/best.keras"
MANIFEST = ROOT / "artifacts/recognition_upgrade/phase1_full_vocab/manifest_01/canonical_manifest.csv"
VOCAB = DATA / "vocab.json"
SOURCES = {"train": DATA / "train.npz", "val": DATA / "val.npz", "stress": DATA / "diagnostic_validation_stress.npz"}
LATENTS = {"train": STAGE1A / "stage1a_train_latents.npz", "val": STAGE1A / "stage1a_val_latents.npz", "stress": STAGE1A / "stage1a_stress_latents.npz"}
EXPECTED_CHECKPOINT_SHA = "3b858ca530b616c0d02ca2eee1d30678d092a039c36e9da38ec5f3d491a94a4c"
SEED = 101
EXCLUDED = {"KNOW", "GOOD", "HAVE", "SORRY", "HELLO"}
REGIME_A = "TRAIN_PAIR_ALREADY_CONFUSED"
REGIME_B = "TRAIN_PAIR_RELATIVELY_SEPARABLE_BUT_VAL_FAILS"


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
    rows = list(rows); fields = fields or (list(rows[0]) if rows else [])
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    os.replace(tmp, path)


def verify_manifest(directory: Path) -> int:
    payload = json.loads((directory / "artifact_hash_manifest.json").read_text(encoding="utf-8"))
    for row in payload["artifacts"]:
        path = Path(row["path"])
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"PILOT_DESIGN_SOURCE_ARTIFACT_MISMATCH:{path.name}")
    return len(payload["artifacts"])


def build_candidates(pair_df: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
    by = data.set_index("gloss")
    def sole_source(gloss: str) -> str:
        source_counts = json.loads(str(by.loc[gloss, "clips_per_source_json"]))
        if len(source_counts) == 1:
            return next(iter(source_counts))
        return "MULTI:" + "|".join(sorted(source_counts))

    rows = []
    for row in pair_df.itertuples(index=False):
        a, b = str(row.class_a_gloss), str(row.class_b_gloss)
        reasons = []
        if a in EXCLUDED or b in EXCLUDED: reasons.append("SUPPLEMENTED_CLASS_EXCLUDED")
        if int(by.loc[a, "unique_sources"]) != 1 or int(by.loc[b, "unique_sources"]) != 1: reasons.append("NOT_SINGLE_SOURCE_TRAIN")
        if min(int(row.class_a_signer_representatives), int(row.class_b_signer_representatives)) < 5: reasons.append("INADEQUATE_TRAIN_SIGNER_SUPPORT")
        if row.regime not in {REGIME_A, REGIME_B, "HEALTHY_CONTROL"}: reasons.append("REGIME_NOT_ELIGIBLE")
        eligible = not reasons
        rows.append({
            "pair_id": f"{a}__{b}", "class_a": a, "class_b": b, "regime": row.regime,
            "eligible": int(eligible), "exclusion_reason": "|".join(reasons),
            "class_a_raw_clips": int(by.loc[a, "raw_training_clips"]), "class_b_raw_clips": int(by.loc[b, "raw_training_clips"]),
            "mean_raw_clips": float((by.loc[a, "raw_training_clips"] + by.loc[b, "raw_training_clips"]) / 2),
            "class_a_unique_signers": int(by.loc[a, "unique_signer_groups"]), "class_b_unique_signers": int(by.loc[b, "unique_signer_groups"]),
            "mean_unique_signers": float((by.loc[a, "unique_signer_groups"] + by.loc[b, "unique_signer_groups"]) / 2),
            "class_a_effective_signers": float(by.loc[a, "effective_signer_count"]), "class_b_effective_signers": float(by.loc[b, "effective_signer_count"]),
            "mean_effective_signers": float((by.loc[a, "effective_signer_count"] + by.loc[b, "effective_signer_count"]) / 2),
            "mean_largest_signer_share": float((by.loc[a, "largest_signer_share"] + by.loc[b, "largest_signer_share"]) / 2),
            "pair_loso_confusion": float(row.pairwise_nearest_centroid_confusion_rate),
            "centroid_to_pooled_dispersion": float(row.centroid_distance_to_pooled_dispersion_ratio),
            "primary_val_support_total": int(row.validation_support_a + row.validation_support_b),
            "source_a": sole_source(a), "source_b": sole_source(b),
            "manifest_label_lineage_warning": "NONE_DOCUMENTED_IN_GOVERNED_STAGE1_ARTIFACTS",
            "uses_protected_test_evidence": 0,
        })
    return pd.DataFrame(rows)


def matching_options(candidates: pd.DataFrame, regime: str) -> list[dict[str, Any]]:
    part = candidates[(candidates.regime == regime) & (candidates.eligible == 1)].reset_index(drop=True)
    features = ["mean_raw_clips", "mean_unique_signers", "mean_effective_signers", "mean_largest_signer_share", "pair_loso_confusion", "centroid_to_pooled_dispersion", "primary_val_support_total"]
    scale = part[features].std(ddof=0).replace(0, 1.0)
    z = (part[features] - part[features].mean()) / scale
    options = []
    for i, j in itertools.combinations(range(len(part)), 2):
        left, right = part.iloc[i], part.iloc[j]
        if {left.class_a, left.class_b} & {right.class_a, right.class_b}: continue
        diffs = np.abs(z.iloc[i] - z.iloc[j])
        options.append({
            "regime": regime, "candidate_pair_1": left.pair_id, "candidate_pair_2": right.pair_id,
            "matching_score_mean_absolute_z": float(diffs.mean()),
            **{f"abs_z_difference_{feature}": float(diffs[feature]) for feature in features},
            "selected_best_match": 0,
        })
    return sorted(options, key=lambda x: (x["matching_score_mean_absolute_z"], x["candidate_pair_1"], x["candidate_pair_2"]))


def recording_seed(pool: str, slot: str) -> int:
    digest = hashlib.sha256(f"APPHEAR_VARIANT_DENSITY_PILOT_01|101|{pool}|{slot}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)
    context_before = {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "context").rglob("*")) if p.is_file()}
    stage1b_before = {p.name: sha256(p) for p in sorted(STAGE1B.iterdir(), key=lambda item: item.name) if p.is_file()}
    verified_counts = {"stage1a": verify_manifest(STAGE1A), "correction": verify_manifest(CORR), "stage1b": verify_manifest(STAGE1B)}
    stage1b_integrity = json.loads((STAGE1B / "stage1b_integrity.json").read_text(encoding="utf-8"))
    if not stage1b_integrity.get("passed"):
        raise RuntimeError("PILOT_DESIGN_STAGE1B_INTEGRITY_FAILURE")
    source_before = {"checkpoint": sha256(CHECKPOINT), "manifest": sha256(MANIFEST), "vocabulary": sha256(VOCAB), **{n: sha256(p) for n,p in SOURCES.items()}, **{f"latent_{n}": sha256(p) for n,p in LATENTS.items()}}
    if source_before["checkpoint"] != EXPECTED_CHECKPOINT_SHA:
        raise RuntimeError("PILOT_DESIGN_CHECKPOINT_MISMATCH")
    for key, value in source_before.items():
        if stage1b_integrity["source_hashes_after"].get(key) != value:
            raise RuntimeError(f"PILOT_DESIGN_SOURCE_MISMATCH:{key}")

    pair_df = pd.read_csv(STAGE1B / "stage1b_pairwise_failure_regimes.csv")
    data = pd.read_csv(STAGE1B / "stage1b_data_coverage_assessment.csv")
    candidates = build_candidates(pair_df, data)
    candidates.to_csv(OUT / "pilot_candidate_pairs.csv", index=False)

    options_a, options_b = matching_options(candidates, REGIME_A), matching_options(candidates, REGIME_B)
    healthy_candidates = candidates[(candidates.regime == "HEALTHY_CONTROL") & (candidates.eligible == 1)].copy()
    healthy_median = float(healthy_candidates.pair_loso_confusion.median())
    healthy_candidates["distance_to_healthy_median"] = np.abs(healthy_candidates.pair_loso_confusion - healthy_median)
    healthy = healthy_candidates.sort_values(["distance_to_healthy_median", "pair_id"]).iloc[0]
    # Globally choose the closest within-regime matches while preserving 10 unique classes.
    joint = []
    healthy_classes = {healthy.class_a, healthy.class_b}
    for a in options_a:
        a_classes = set(a["candidate_pair_1"].split("__") + a["candidate_pair_2"].split("__"))
        for b in options_b:
            b_classes = set(b["candidate_pair_1"].split("__") + b["candidate_pair_2"].split("__"))
            if a_classes & b_classes or (a_classes | b_classes) & healthy_classes: continue
            joint.append((a["matching_score_mean_absolute_z"] + b["matching_score_mean_absolute_z"], a, b))
    if not joint:
        raise RuntimeError("PILOT_DESIGN_NO_NONOVERLAPPING_MATCH")
    _, match_a, match_b = sorted(joint, key=lambda x: (x[0], x[1]["candidate_pair_1"], x[2]["candidate_pair_1"]))[0]
    match_a["selected_best_match"] = 1; match_b["selected_best_match"] = 1
    matching_rows = [match_a, match_b]
    write_csv(OUT / "pilot_pair_matching.csv", matching_rows)

    rng = np.random.Generator(np.random.PCG64(SEED))
    assignments: dict[str, dict[str, Any]] = {}
    selected_rows = []
    for label, match in [("REGIME_A", match_a), ("REGIME_B", match_b)]:
        pair_ids = sorted([match["candidate_pair_1"], match["candidate_pair_2"]])
        permutation = rng.permutation(2).tolist()
        treatment, control = pair_ids[permutation[0]], pair_ids[permutation[1]]
        assignments[label] = {"sorted_candidate_pair_ids": pair_ids, "pcg64_permutation": permutation, "treatment_pair_id": treatment, "unchanged_control_pair_id": control}
        for role, pair_id in [("TREATMENT", treatment), ("UNCHANGED_CONTROL", control)]:
            row = candidates[candidates.pair_id == pair_id].iloc[0]
            selected_rows.append({"regime": row.regime, "assignment": role, "pair_id": pair_id, "class_a": row.class_a, "class_b": row.class_b, "pair_loso_confusion": row.pair_loso_confusion, "centroid_to_pooled_dispersion": row.centroid_to_pooled_dispersion, "mean_raw_clips": row.mean_raw_clips, "mean_unique_signers": row.mean_unique_signers, "mean_effective_signers": row.mean_effective_signers, "primary_val_support_total": row.primary_val_support_total, "new_training_clips_authorized_now": 0})
    selected_rows.append({"regime":"HEALTHY_CONTROL", "assignment":"HEALTHY_EVAL_ONLY_CONTROL", "pair_id":healthy.pair_id, "class_a":healthy.class_a, "class_b":healthy.class_b, "pair_loso_confusion":healthy.pair_loso_confusion, "centroid_to_pooled_dispersion":healthy.centroid_to_pooled_dispersion, "mean_raw_clips":healthy.mean_raw_clips, "mean_unique_signers":healthy.mean_unique_signers, "mean_effective_signers":healthy.mean_effective_signers, "primary_val_support_total":healthy.primary_val_support_total, "new_training_clips_authorized_now":0})
    selected = pd.DataFrame(selected_rows)
    selected.to_csv(OUT / "pilot_selected_pairs.csv", index=False)
    randomization = {"seed":SEED,"generator":"numpy.random.Generator(PCG64)","regime_order":["REGIME_A","REGIME_B"],"procedure":"Sort the two matched pair IDs lexicographically within each regime; draw rng.permutation(2); first permuted pair=TREATMENT, second=UNCHANGED_CONTROL.","assignments":assignments,"post_randomization_pcg64_state":rng.bit_generator.state,"manual_override":False}
    atomic_json(OUT / "pilot_randomization_record.json", randomization)

    treatment_classes = sorted(selected[selected.assignment == "TREATMENT"][["class_a","class_b"]].to_numpy().ravel().tolist())
    control_classes = sorted(selected[selected.assignment == "UNCHANGED_CONTROL"][["class_a","class_b"]].to_numpy().ravel().tolist())
    healthy_classes_list = sorted([healthy.class_a, healthy.class_b])
    core_classes = sorted(treatment_classes + control_classes)
    all_eval_classes = sorted(core_classes + healthy_classes_list)
    if len(set(core_classes)) != 8 or set(core_classes) & EXCLUDED:
        raise RuntimeError("PILOT_DESIGN_CORE_CLASS_CONTRACT_FAILURE")

    by = data.set_index("gloss")
    profile_rows = []
    for gloss in all_eval_classes:
        pair_row = selected[(selected.class_a == gloss) | (selected.class_b == gloss)].iloc[0]
        profile_rows.append({
            "gloss":gloss,"class_id":int(by.loc[gloss,"class_id"]),"pilot_assignment":pair_row.assignment,"failure_regime":pair_row.regime,
            "current_train_clips":int(by.loc[gloss,"raw_training_clips"]),"current_unique_signers":int(by.loc[gloss,"unique_signer_groups"]),"current_effective_signers":float(by.loc[gloss,"effective_signer_count"]),"largest_signer_share":float(by.loc[gloss,"largest_signer_share"]),"top3_signer_share":float(by.loc[gloss,"top3_signer_share"]),"train_sources":int(by.loc[gloss,"unique_sources"]),"primary_val_support":int(by.loc[gloss,"support"]),"primary_val_recall_exploratory":float(by.loc[gloss,"recall"]),"validation_support_tier":by.loc[gloss,"validation_support_tier"],"supplemented_class":0,
        })
    profile = pd.DataFrame(profile_rows)
    profile.to_csv(OUT / "pilot_class_baseline_profile.csv", index=False)

    tiers = {
        "PREFERRED": {"train_signers":6,"train_reps":4,"eval_signers":6,"eval_reps":3},
        "MINIMUM": {"train_signers":4,"train_reps":3,"eval_signers":5,"eval_reps":2},
    }
    collection_rows = []
    for tier, cfg in tiers.items():
        for gloss in all_eval_classes:
            assignment = profile.set_index("gloss").loc[gloss,"pilot_assignment"]
            new_train = cfg["train_signers"] * cfg["train_reps"] if assignment == "TREATMENT" else 0
            new_eval = cfg["eval_signers"] * cfg["eval_reps"]
            current = int(by.loc[gloss,"raw_training_clips"])
            collection_rows.append({"tier":tier,"gloss":gloss,"assignment":assignment,"new_training_signers":cfg["train_signers"] if assignment=="TREATMENT" else 0,"training_repetitions_per_signer":cfg["train_reps"] if assignment=="TREATMENT" else 0,"planned_new_train_clips":new_train,"current_train_clips":current,"post_pilot_train_clips":current+new_train,"current_effective_signer_count":float(by.loc[gloss,"effective_signer_count"]),"current_effective_plus_new_independent_signers_arithmetic":float(by.loc[gloss,"effective_signer_count"])+(cfg["train_signers"] if assignment=="TREATMENT" else 0),"post_pilot_hhi_effective_count_note":"Arithmetic planning indicator only; actual post-pilot effective signer count must be recomputed from accepted clips.","new_evaluation_signers":cfg["eval_signers"],"evaluation_repetitions_per_signer":cfg["eval_reps"],"planned_new_eval_clips":new_eval,"future_train_role":"pilot_variant_train" if assignment=="TREATMENT" else "NONE","future_eval_role":"pilot_fresh_unseen_eval","authorized_now":0})
    collection = pd.DataFrame(collection_rows)
    collection.to_csv(OUT / "pilot_collection_plan.csv", index=False)

    workload_rows = []
    for tier,cfg in tiers.items():
        train_total = 4*cfg["train_signers"]*cfg["train_reps"]
        for design, classes in [("CORE_8",8),("CORE_PLUS_HEALTHY_10",10)]:
            eval_total = classes*cfg["eval_signers"]*cfg["eval_reps"]
            workload_rows.append({"tier":tier,"design":design,"new_training_signers":cfg["train_signers"],"new_evaluation_signers":cfg["eval_signers"],"treatment_classes":4,"unchanged_control_classes":4,"healthy_classes":2 if classes==10 else 0,"training_repetitions_per_class_per_signer":cfg["train_reps"],"evaluation_repetitions_per_class_per_signer":cfg["eval_reps"],"clips_per_training_signer":4*cfg["train_reps"],"clips_per_evaluation_signer":classes*cfg["eval_reps"],"total_new_train_clips":train_total,"total_new_eval_clips":eval_total,"total_recordings":train_total+eval_total,"recommended":int(tier=="PREFERRED" and design=="CORE_PLUS_HEALTHY_10")})
    pd.DataFrame(workload_rows).to_csv(OUT / "pilot_workload_analysis.csv", index=False)

    signer_rows = []
    for tier,cfg in tiers.items():
        for pool,count in [("TRAIN_NEW",cfg["train_signers"]),("EVAL_NEW",cfg["eval_signers"])]:
            for index in range(1,count+1):
                slot=f"{pool[0]}{index:02d}"
                signer_rows.append({"tier":tier,"signer_slot":slot,"signer_group_id":"","signer_pool":pool,"must_be_absent_from_existing_train":1,"must_be_absent_from_primary_val":1,"must_be_absent_from_diagnostic_stress":1,"must_be_absent_from_previous_pilots":1,"mutually_disjoint_pool_check_required":1,"recording_order_seed":recording_seed(pool,slot),"assigned_device_id":"","identity_verified_disjoint":"","status":"NOT_RECRUITED_DESIGN_ONLY"})
    pd.DataFrame(signer_rows).to_csv(OUT / "pilot_signer_assignment_template.csv", index=False)

    manifest_fields = ["sample_id","gloss","class_id","signer_group_id","signer_pool","repetition_index","recording_order_index","recording_order_seed","capture_date","source","device_identifier","device_category","resolution","nominal_fps","orientation","capture_application_version","label_confirmed","capture_quality_pass","rejection_reason","raw_video_path","raw_video_sha256","role"]
    write_csv(OUT / "pilot_manifest_template.csv", [], manifest_fields)

    recording_md = f"""# Variant-Density Pilot Recording Protocol

## Scope

Design only. Do not record until separately authorized. Treatment classes: `{', '.join(treatment_classes)}`. Unchanged controls: `{', '.join(control_classes)}`. Healthy evaluation-only classes: `{', '.join(healthy_classes_list)}`.

## Signer pools

- `TRAIN_NEW` and `EVAL_NEW` must be mutually exclusive and absent from every existing TRAIN, primary-validation, stress, and prior-pilot signer identity.
- Failure to verify a signer ID stops ingestion. Physical device identifiers must also be recorded; prefer disjoint physical devices between pools within the same device category/settings when feasible.

## Natural repetitions

- Perform the requested lexical sign correctly using natural motion. Reset to a neutral posture between independent repetitions.
- Do not imitate the preceding repetition or another signer, and do not coach toward RCA-B behavior.
- Training signers record treatment classes only. Evaluation signers record all core classes and, for the recommended plan, both healthy classes.

## Controlled capture domain

- Freeze one capture application/version before the first recording and use the same workflow, orientation, resolution, nominal-FPS target, framing guidance, general lighting envelope, and background expectations across both pools.
- Use stable front-camera placement with the target signer centered and upper body/hands visible throughout the complete sign. Do not mirror stored analysis video.
- Natural signer/motion variation is desired; large device/workflow/domain changes are not. Record device identity/category so residual domain effects remain auditable.

## Order

- Expand each sign into its required repetition tokens, then shuffle all tokens once per signer using that signer's frozen `recording_order_seed` and NumPy PCG64. Never record fixed AAAA/BBBB blocks.
- Save the realized `recording_order_index`; do not reshuffle after failures. A replacement recording receives the next index and links to the rejected attempt in the journal.
"""
    atomic_text(OUT / "pilot_recording_protocol.md", recording_md)
    quality_md = """# Pilot Label and Capture-Quality Protocol

Review occurs before any RCA-B/B1 predictions or latent diagnostics are exposed. A human reviewer records `LABEL_CONFIRMED` independently of model behavior.

Accept only when the requested lexical label is correct, the complete sign is recorded, the target signer is sufficiently visible for the governed perception pipeline, the file is readable and not truncated, and no obvious capture failure occurred. Record objective fields separately.

Never reject because RCA-B is wrong, confidence is low, geometry is unusual, or the example appears difficult. Rejected rows remain in the audit journal with `capture_quality_pass=0` and an objective `rejection_reason`; they are never silently deleted or replaced under the same sample ID.
"""
    atomic_text(OUT / "pilot_label_quality_protocol.md", quality_md)
    eval_md = """# Fresh Evaluation Governance

`pilot_fresh_unseen_eval` is an immutable signer-disjoint cohort. It is never training data, early-stopping data, preprocessing-tuning data, epoch-selection data, class-selection evidence, or a source for deciding which treatment worked.

After label/quality freeze, evaluate frozen B0 RCA-B first and hash its predictions. Only then may B1 training be separately authorized. Freeze B1 using existing primary validation only, then evaluate B0 and B1 once on exactly the same accepted fresh clips. Never open the protected primary test.

Uncertainty is signer-clustered: paired bootstrap resamples evaluation signers with replacement (10,000 replicates, PCG64 seed 101), preserving all clips/classes for each sampled signer. Report the class-balanced treatment delta, control delta, and difference-in-differences with a 95% percentile interval. Clips are not independent units.
"""
    atomic_text(OUT / "pilot_fresh_eval_governance.md", eval_md)

    future_training = {"status":"FROZEN_DESIGN_NOT_AUTHORIZED","model_b0":"existing frozen RCA-B","model_b1_change":"add accepted pilot_variant_train clips for treatment classes only","treatment_classes":treatment_classes,"unchanged_control_classes":control_classes,"healthy_eval_only_classes":healthy_classes_list,"held_fixed":{"representation":"DWPOSE_REPRESENTATION_V2_238 [96,238]","model":"causal TCN 4x64; dilations 1,2,4,8; kernel 3; dropout 0.3; 236 classes","objective":"per-frame cross entropy","optimizer":"AdamW","learning_rate":0.0005,"weight_decay":0.0001,"batch_size":32,"seed":101,"max_epochs":100,"early_stop_patience":8,"checkpoint_selection":"maximum existing primary-validation per-frame accuracy","augmentation":"NONE","warm_start":"NONE","missingness_augmentation":"NONE","source_balancing":"NONE","class_weighting":"NONE","splits":"existing RCA-B train/primary-val roles plus treatment pilot train only"},"fresh_eval_used_for_selection":False,"protected_test_access":False}
    atomic_json(OUT / "pilot_future_training_contract.json", future_training)
    evaluation_contract = {"status":"FROZEN_DESIGN_NOT_EXECUTED","models":{"B0":"frozen existing RCA-B","B1":"same contract plus treatment-class pilot_variant_train clips"},"populations":["existing primary validation","pilot_fresh_unseen_eval"],"primary_endpoint":"class-balanced clip-level recall across the four treatment classes on fresh unseen signers","primary_causal_comparison":"difference-in-differences = mean_class_recall_delta(B1-B0,treatment) - mean_class_recall_delta(B1-B0,matched unchanged controls)","uncertainty":"signer-blocked paired bootstrap; 10,000 PCG64 seed-101 replicates; 95% percentile interval","secondary_fresh_metrics":["Top1","Top5","per-class recall","true-class probability","within-selected-pair confusion","temporal true-vs-competitor margin","signer-level recall distribution"],"learned_space_metrics":["treatment-pair TRAIN LOSO separation before/after","treatment-pair fresh-eval geometry before/after","matched-control geometry before/after","governed temporal latent separation"],"existing_primary_val_metrics":["Top1","Top5","Macro F1","per-frame accuracy"],"test_access":False}
    atomic_json(OUT / "pilot_evaluation_contract.json", evaluation_contract)
    decision_rules = {"no_fixed_percentage_point_threshold":True,"evidence_inputs":["effect size","signer-blocked uncertainty","difference-in-differences","consistency across four treatment classes and both regimes","latent-separation direction","existing primary-validation regression check"],"categories":{"DATA_VARIANT_DENSITY_CAUSALLY_SUPPORTED":"Positive treatment-vs-control difference-in-differences with signer-blocked 95% interval excluding zero, directionally consistent gains across treatment classes/both regimes, corresponding learned-separation improvement, and no statistically clear broad primary-validation damage.","DATA_VARIANT_DENSITY_PARTIALLY_SUPPORTED":"Directionally favorable but mixed evidence: interval includes zero, one regime/class drives gains, or TRAIN separation improves without clear fresh-signer improvement.","DATA_VARIANT_DENSITY_NOT_SUPPORTED":"Meaningful accepted intervention yields no treatment advantage over controls and no directionally consistent fresh-generalization or separation improvement.","PILOT_INCONCLUSIVE":"Signer count, label/capture quality, disjointness, uncertainty, or protocol compliance is inadequate."},"interpretation_limits":{"supported":"Data variant density is a causal contributor; V2 is not declared perfect.","not_supported":"Do not collect substantially more by default; next unresolved branch is V2 input sufficiency vs temporal learning/objective."}}
    atomic_json(OUT / "pilot_decision_rules.json", decision_rules)

    design_md = f"""# AppHear Variant-Density Causal Pilot — Frozen Design

## Primary question

Holding `DWPOSE_REPRESENTATION_V2_238`, RCA-B's causal TCN, objective, optimizer/training contract, splits, and evaluation semantics fixed, does increasing independent natural signer/variant density for a preregistered class subset improve learned separation and genuinely held-out signer generalization relative to matched unchanged classes?

## Frozen pair selection

- Regime A treatment (seed-101 randomized): `TALK1/WATER`; unchanged control: `FEEL/PLEASE`.
- Regime B treatment: `NO/US`; unchanged control: `AT/WORK`.
- Healthy evaluation-only calibration: `TOOMUCH/VISIT`, the healthy pair at the empirical median LOSO rate.
- KNOW/GOOD/HAVE/SORRY/HELLO are excluded from the core. KNOW/HELLO remains a secondary one-signer diagnostic only.

Pairs were matched before randomization using mean absolute standardized differences in TRAIN clips, nominal/effective signers, largest-signer share, LOSO pair confusion, centroid/pooled-dispersion ratio, and validation support. Treatment assignment used NumPy PCG64 seed 101 with no manual override.

## Recommended workload

`PREFERRED CORE_PLUS_HEALTHY_10`: six new training signers × four independent repetitions × four treatment classes = 96 TRAIN clips; six disjoint evaluation signers × three repetitions × ten classes = 180 fresh EVAL clips; total 276 recordings. The extra healthy calibration costs 36 evaluation clips and anchors pair-separation interpretation.

Minimum: four training signers × three repetitions × four treatment classes = 48 TRAIN clips; five evaluation signers × two repetitions × ten classes = 100 EVAL clips; total 148. Minimum is feasible but has materially wider signer-blocked uncertainty.

## Governance

No collection or training is authorized. Only treatment classes may later enter `pilot_variant_train`. Every core/healthy class enters `pilot_fresh_unseen_eval`, which is never used for training or selection. B0 fresh predictions freeze before any B1 training. The primary endpoint is signer-aware class-balanced treatment recall with matched-control difference-in-differences.
"""
    atomic_text(OUT / "VARIANT_DENSITY_PILOT_DESIGN.md", design_md)

    source_after = {"checkpoint":sha256(CHECKPOINT),"manifest":sha256(MANIFEST),"vocabulary":sha256(VOCAB),**{n:sha256(p) for n,p in SOURCES.items()},**{f"latent_{n}":sha256(p) for n,p in LATENTS.items()}}
    stage1b_after = {p.name:sha256(p) for p in sorted(STAGE1B.iterdir(), key=lambda item: item.name) if p.is_file()}
    context_after = {str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/"context").rglob("*")) if p.is_file()}
    integrity = {"passed":source_before==source_after and context_before==context_after and stage1b_before==stage1b_after,"source_packages_verified":verified_counts,"source_hashes_before":source_before,"source_hashes_after":source_after,"rcab_changed":source_before['checkpoint']!=source_after['checkpoint'],"v2_changed":any(source_before[n]!=source_after[n] for n in SOURCES),"datasets_changed":any(source_before[n]!=source_after[n] for n in SOURCES),"stage1a_latents_changed":any(source_before[f'latent_{n}']!=source_after[f'latent_{n}'] for n in LATENTS),"stage1b_artifacts_changed":stage1b_before!=stage1b_after,"training_performed":False,"experiment_executed":False,"data_collected":False,"new_checkpoint_created":False,"protected_primary_test_opened":False,"context_files_modified":context_before!=context_after,"progress_tracker_untouched":context_before.get('context/progress-tracker.md')==context_after.get('context/progress-tracker.md')}
    atomic_json(OUT / "pilot_integrity.json", integrity)
    if not integrity["passed"]: raise RuntimeError("PILOT_DESIGN_INTEGRITY_FAILURE")
    artifacts=[]
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name!="artifact_hash_manifest.json": artifacts.append({"path":str(path.resolve()),"sha256":sha256(path),"bytes":path.stat().st_size})
    atomic_json(OUT/"artifact_hash_manifest.json",{"artifacts":artifacts,"supporting_code":{"path":str(Path(__file__).resolve()),"sha256":sha256(Path(__file__).resolve())},"experiment_executed":False,"training_performed":False,"protected_primary_test_opened":False})
    print(json.dumps({"status":"APPHEAR_VARIANT_DENSITY_PILOT_DESIGN_COMPLETE","treatment_classes":treatment_classes,"control_classes":control_classes,"healthy_classes":healthy_classes_list,"assignments":assignments,"preferred":{"training_signers":6,"evaluation_signers":6,"train_clips":96,"eval_clips":180,"total":276},"minimum":{"training_signers":4,"evaluation_signers":5,"train_clips":48,"eval_clips":100,"total":148},"integrity":integrity,"artifact_directory":str(OUT.resolve())},indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
