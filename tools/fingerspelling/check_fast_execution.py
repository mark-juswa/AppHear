"""Bounded speed/parity diagnostics: gradients only, never optimizer updates or epochs."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_fast_execution import CompiledSteps, FeatureCache, evaluate_batched
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO


def run(output: Path, evidence: Path) -> dict[str, Any]:
    config = reference.configuration(reference.CONFIG_PATH)
    manifest = json.loads((output / "tranche_manifest.json").read_text())
    pinned = json.loads((REPO / "pipeline/config/fingerspelling_execution_v1.json").read_text())
    if sha256(output / "tranche_manifest.json") != pinned["frozen_manifest_sha256"]:
        raise ValueError("[fingerspelling/speed-check] Manifest changed")
    validation = json.loads((output / "validation.json").read_text())
    if (
        not validation["ready_to_train"]
        or validation["manifest_sha256"] != pinned["frozen_manifest_sha256"]
    ):
        raise ValueError("[fingerspelling/speed-check] Previously validated full tranche required")
    # Reverify bounded feature bytes without recomputing all 1,280 raw sequences during a live run.
    rows = reference.records(output)
    train = [r for r in rows if r["split_role"] == "TRAIN" and r["native_ctc_feasible"]][:2]
    all_dev = [r for r in rows if r["split_role"] == "DEV"]
    dev = all_dev[:14]
    for row in all_dev:
        if not row["phone_ctc_feasible"] and row not in dev:
            dev.append(row)
    assert len(train) == 2 and len(dev) <= 16
    cache = FeatureCache()
    x, mask, y, lengths, target_lengths = cache.batch(train, "native")
    uncached = reference.padded_batch(train, "native")
    for cached, baseline in zip((x, mask, y, lengths, target_lengths), uncached, strict=True):
        np.testing.assert_array_equal(cached, baseline)
    tf = reference.tensorflow(config)
    model = reference.build_model(tf, config)
    optimizer = tf.keras.optimizers.Adam(
        config["learning_rate"], clipnorm=config["gradient_clip_norm"]
    )
    optimizer.build(model.trainable_variables)
    epoch = tf.Variable(0, trainable=False, dtype=tf.int64)
    checkpoint = tf.train.Checkpoint(model=model, optimizer=optimizer, epoch=epoch)
    parent = REPO / "runs/fingerspelling_ctc_baseline_01"
    state_bytes = (parent / "committed_epoch.json").read_bytes()
    state = json.loads(state_bytes)
    prefix = Path(state["checkpoint"])
    copied = evidence / "checkpoint_snapshot"
    copied.mkdir(parents=True, exist_ok=True)
    files = sorted(prefix.parent.glob(prefix.name + ".*"))
    hashes = {str(p): sha256(p) for p in files}
    if not files:
        raise ValueError("[fingerspelling/speed-check] Committed checkpoint unavailable")
    for path in files:
        shutil.copyfile(path, copied / path.name)
        if sha256(copied / path.name) != hashes[str(path)]:
            raise ValueError("[fingerspelling/speed-check] Concurrent checkpoint change")
    checkpoint.restore(str(copied / prefix.name)).assert_existing_objects_matched()
    assert int(epoch.numpy()) == state["epoch"]
    weights_before = [a.numpy().copy() for a in model.trainable_variables]
    optimizer_before = [a.numpy().copy() for a in optimizer.variables]
    steps = CompiledSteps(tf, model, optimizer)
    # Trace the actual update graph without executing it or applying gradients.
    assert steps.update is not None
    steps.update.get_concrete_function()
    start = time.perf_counter()
    compiled_logits = steps.infer(x, mask).numpy()
    trace_seconds = time.perf_counter() - start
    eager_logits = model([x, mask], training=False).numpy()
    np.testing.assert_allclose(compiled_logits, eager_logits, atol=1e-5, rtol=1e-5)
    assert not np.any(compiled_logits[mask[:, :, 0] == 0])
    with tf.GradientTape() as tape:
        eager_loss = reference.ctc_loss(
            tf, model([x, mask], training=False), y, lengths, target_lengths
        )
    eager_gradients = tape.gradient(eager_loss, model.trainable_variables)
    graph_loss, graph_gradients = steps.gradients_without_dropout(
        x, mask, y, lengths, target_lengths
    )
    np.testing.assert_allclose(graph_loss.numpy(), eager_loss.numpy(), atol=1e-4, rtol=1e-4)
    maximum_gradient_difference = 0.0
    for eager, graph in zip(eager_gradients, graph_gradients, strict=True):
        np.testing.assert_allclose(eager.numpy(), graph.numpy(), atol=1e-4, rtol=1e-4)
        maximum_gradient_difference = max(
            maximum_gradient_difference, float(np.max(np.abs(eager.numpy() - graph.numpy())))
        )
    # Exercise training=True dropout graph and finite gradients without changing weights.
    dropout_loss, _ = steps.gradients_training(x, mask, y, lengths, target_lengths)
    assert np.isfinite(dropout_loss.numpy())
    timings, checks = {}, {}
    for view in ["native", "phone"]:
        for row in dev:
            cache.load(row, view)
        first = cache.batch(dev[: config["batch_size"]], view)
        steps.infer(first[0], first[1]).numpy()  # warm graph, no weight update
        start = time.perf_counter()
        baseline = reference.evaluate(tf, model, dev, view, config)
        eager_seconds = time.perf_counter() - start
        start = time.perf_counter()
        batched = evaluate_batched(tf, steps, cache, dev, view, config)
        fast_seconds = time.perf_counter() - start
        for key in [
            "metrics",
            "predictions",
            "ctc_loss_sequence_count",
            "ctc_infeasible_retained_ids",
            "all_sequences_greedy_evaluated",
        ]:
            assert baseline[key] == batched[key], key
        np.testing.assert_allclose(
            baseline["ctc_mean_loss_eligible_only"],
            batched["ctc_mean_loss_eligible_only"],
            atol=1e-4,
            rtol=1e-4,
        )
        checks[view] = {
            "sequences": len(dev),
            "eligible_loss_count": batched["ctc_loss_sequence_count"],
            "infeasible_retained_count": len(batched["ctc_infeasible_retained_ids"]),
            "exact_text_and_metrics": True,
        }
        timings[view] = {
            "scalar_seconds": eager_seconds,
            "cached_batched_seconds": fast_seconds,
            "ratio": eager_seconds / fast_seconds,
        }
    for before, variable in zip(weights_before, model.trainable_variables, strict=True):
        np.testing.assert_array_equal(before, variable.numpy())
    for before, variable in zip(optimizer_before, optimizer.variables, strict=True):
        np.testing.assert_array_equal(before, variable.numpy())
    clone = reference.build_model(tf, config)
    clone_optimizer = tf.keras.optimizers.Adam(
        config["learning_rate"], clipnorm=config["gradient_clip_norm"]
    )
    clone_optimizer.build(clone.trainable_variables)
    clone_epoch = tf.Variable(0, trainable=False, dtype=tf.int64)
    tf.train.Checkpoint(model=clone, optimizer=clone_optimizer, epoch=clone_epoch).restore(
        str(copied / prefix.name)
    ).assert_existing_objects_matched()
    for before, variable in zip(weights_before, clone.trainable_variables, strict=True):
        np.testing.assert_array_equal(before, variable.numpy())
    for before, variable in zip(optimizer_before, clone_optimizer.variables, strict=True):
        np.testing.assert_array_equal(before, variable.numpy())
    result = {
        "status": "FAST_EXECUTION_BOUNDED_PARITY_PASSED",
        "training_updates": 0,
        "compiled_optimizer_graph_traced_not_executed": True,
        "checkpoint_epoch": state["epoch"],
        "checkpoint_sha256": hashes,
        "checkpoint_model_optimizer_state_equal": True,
        "original_weights_optimizer_unchanged": True,
        "manifest_sha256": pinned["frozen_manifest_sha256"],
        "adapter": manifest["adapter"],
        "cache_bytes": cache.bytes,
        "cache_file_loads": cache.file_loads,
        "maximum_gradient_absolute_difference": maximum_gradient_difference,
        "inference_initial_trace_seconds": trace_seconds,
        "dev_checks": checks,
        "dev_microbenchmark": timings,
        "scope": "Bounded 2 TRAIN / up to 16 DEV; no training or full-epoch speed/quality claim",
    }
    write_json_atomic(evidence / "check.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=REPO / "datasets/fingerspelling/foundation_01"
    )
    parser.add_argument("--evidence", type=Path, default=REPO / "artifacts/fingerspelling_speed_01")
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(args.dataset, args.evidence), indent=2))


if __name__ == "__main__":
    main()
