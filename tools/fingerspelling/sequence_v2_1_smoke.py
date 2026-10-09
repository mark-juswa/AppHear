"""TRAIN-only dual-objective engineering gate. Never evaluates DEV or TEST."""

from __future__ import annotations

import json
import time

import numpy as np

from model import fingerspelling_ctc as reference
from model.fingerspelling_baseline2 import state_digest
from model.fingerspelling_metrics import greedy_decode
from model.fingerspelling_prefix_beam import decode_greedy
from model.fingerspelling_sequence_v2_1 import GATE, RUN, code_identity
from model.fingerspelling_sequence_v2_1_encoder import (
    CONFIG,
    build_model,
    configuration,
    inference_model,
)
from model.fingerspelling_sequence_v2_1_execution import DualSteps, letters, loss_values
from model.fingerspelling_sequence_v2_execution import RobustTemporalCache
from pipeline.fingerspelling.adapter import identity, sha256
from pipeline.fingerspelling.package_io import write_json_atomic
from pipeline.fingerspelling.sequence_manifest import REPO
from tools.fingerspelling.sequence_v2_evidence import receipts
from tools.fingerspelling.sequence_v2_smoke import choose_tiny


def main() -> None:
    p = configuration()
    tf = reference.tensorflow(p)
    rows = choose_tiny(receipts())
    root = RUN.with_name(RUN.name + "_smoke")
    if root.exists() and any(root.iterdir()):
        raise ValueError("[sequence-v2.1/smoke] Nonempty smoke directory refused")
    root.mkdir(parents=True, exist_ok=True)
    GATE.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(
        (REPO / "artifacts/fingerspelling_sequence_v2_gate_01/preservation_before.json").read_text()
    )
    for name in [
        "model/fingerspelling_sequence_v2.py",
        "model/config/fingerspelling_sequence_v2_01.json",
        p["warmstart_model"],
        "runs/fingerspelling_sequence_v2_01/final_evaluation.json",
    ]:
        path = REPO / name
        inventory[str(path)] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    write_json_atomic(GATE / "preservation_before.json", inventory)
    write_json_atomic(
        GATE / "tiny_subset.json",
        {"samples": rows, "dev_accessed": False, "test_accessed": False, "accuracy_claim": "NONE"},
    )
    model = build_model(tf, p)
    normal = inference_model(tf, model)
    frozen = tf.keras.models.load_model(REPO / p["warmstart_model"], compile=False)
    optimizer = tf.keras.optimizers.Adam(p["learning_rate"], clipnorm=p["gradient_clip_norm"])
    optimizer.build(model.trainable_variables)
    cache, steps = RobustTemporalCache(p), DualSteps(tf, model, p, optimizer)
    batch = cache.batch(rows, "native")
    initial_parity = float(
        np.max(
            np.abs(
                normal(list(batch[:2]), training=False).numpy()
                - frozen(list(batch[:2]), training=False).numpy()
            )
        )
    )
    if initial_parity != 0:
        raise ValueError("[sequence-v2.1/init] Warm-start normal logits changed")
    initial_losses, grads = steps.gradients_without_dropout(*batch)
    initial_norm = float(tf.linalg.global_norm(grads).numpy())
    head_norms = {}
    for head in ["character_logits", "local_letter_logits"]:
        values = [
            g for v, g in zip(model.trainable_variables, grads, strict=True) if head in v.path
        ]
        head_norms[head] = float(tf.linalg.global_norm(values).numpy())
        if not np.isfinite(head_norms[head]) or head_norms[head] <= 0:
            raise ValueError("[sequence-v2.1/smoke] Head gradient missing")
    # Late blocks cannot influence the graph ancestor of the local tap.
    before = model(list(batch[:2]), training=False)
    changed = []
    for layer in model.layers:
        if any(layer.name.startswith(f"v2_block{i}_") for i in range(4, 8)) and layer.weights:
            weights = layer.get_weights()
            changed.append((layer, weights))
            layer.set_weights([a + np.float32(0.1) for a in weights])
    after = model(list(batch[:2]), training=False)
    local_independence = np.array_equal(before["local"].numpy(), after["local"].numpy())
    for layer, weights in changed:
        layer.set_weights(weights)
    if not local_independence:
        raise ValueError("[sequence-v2.1/local] Later blocks influence local head")
    rng = np.random.default_rng(p["seed"])
    x = tf.Variable(rng.normal(size=(1, 129, 405)).astype(np.float32))
    mask = tf.ones((1, 129, 1), tf.float32)
    with tf.GradientTape() as tape:
        local = model([x, mask], training=False)["local"][0, 64, 0]
    context_gradient = tape.gradient(local, x).numpy()[0]
    outside = np.r_[context_gradient[:34].flatten(), context_gradient[95:].flatten()]
    if np.any(outside != 0) or not np.any(context_gradient[34:95] != 0):
        raise ValueError("[sequence-v2.1/local] Receptive field differs from61")
    refs = [r["normalized_transcript"] for r in rows]
    letter_refs = [letters(s) for s in refs]
    for a, b in zip(refs, letter_refs, strict=True):
        assert b == "".join(c for c in a if c != " ")
        minimum = len(b) + sum(a == b for a, b in zip(b, b[1:], strict=False))
        assert minimum <= len(a) + sum(a == b for a, b in zip(a, a[1:], strict=False))
    started, history, fitted = time.perf_counter(), [], False
    for update in range(1, p["smoke"]["maximum_updates"] + 1):
        if steps.update is None:
            raise RuntimeError("[sequence-v2.1/smoke] Update unavailable")
        train_losses = [float(v.numpy()) for v in steps.update(*batch)]
        if update % p["smoke"]["check_interval"] == 0:
            outputs = model(list(batch[:2]), training=False)
            values = [
                float(v.numpy())
                for v in loss_values(
                    tf, outputs, batch[2], batch[3], batch[4], p["auxiliary_weight"]
                )
            ]
            main = [
                decode_greedy(a[:n], 0.5)
                for a, n in zip(outputs["main"].numpy(), batch[3], strict=True)
            ]
            local = [
                greedy_decode(np.argmax(a[:n], axis=1).tolist(), blank=26)
                for a, n in zip(outputs["local"].numpy(), batch[3], strict=True)
            ]
            fitted = main == refs and local == letter_refs and max(values[1:]) < 1
            row = dict(
                updates=update,
                train_losses=train_losses,
                evaluation_losses=values,
                main_predictions=main,
                local_predictions=local,
                main_exact=sum(a == b for a, b in zip(main, refs, strict=True)),
                local_exact=sum(a == b for a, b in zip(local, letter_refs, strict=True)),
                seconds=time.perf_counter() - started,
            )
            history.append(row)
            print(json.dumps(row), flush=True)
            write_json_atomic(GATE / "learnability_progress.json", history)
            if fitted:
                break
        if time.perf_counter() - started >= p["smoke"]["maximum_seconds"]:
            break
    if not fitted:
        write_json_atomic(
            GATE / "failed_smoke.json", dict(history=history, reason="DUAL_OVERFIT_NOT_ESTABLISHED")
        )
        raise ValueError(
            "[sequence-v2.1/smoke] Dual tiny overfit not established; full run prohibited"
        )
    padding_errors = []
    for rec in rows:
        a, _ = cache.load(rec, "phone")
        n = len(a)
        original = model([a[None], np.ones((1, n, 1), np.float32)], training=False)
        padded = np.r_[a, rng.normal(size=(37, 405)).astype(np.float32)]
        m = np.r_[np.ones(n), np.zeros(37)].astype(np.float32)[None, :, None]
        extended = model([padded[None], m], training=False)
        for h in ["main", "local"]:
            error = float(np.max(np.abs(original[h].numpy() - extended[h].numpy()[:, :n])))
            padding_errors.append(error)
            if error > 1e-4 or np.any(extended[h].numpy()[:, n:] != 0):
                raise ValueError("[sequence-v2.1/mask] Padding invariance failed")
    regimes = []
    for epoch in range(4):
        tensors, choices = cache.training_batch(rows, epoch)
        values, g = steps.gradients_without_dropout(*tensors)
        again, again_choices = cache.training_batch(rows, epoch)
        assert choices == again_choices and all(
            np.array_equal(a, b) for a, b in zip(tensors, again, strict=True)
        )
        regimes.append(
            dict(epoch_index=epoch, losses=[float(v.numpy()) for v in values], choices=choices)
        )
    model.save(root / "training_smoke.keras")
    normal.save(root / "inference_smoke.keras")
    reload = tf.keras.models.load_model(root / "inference_smoke.keras", compile=False)
    error = float(
        np.max(
            np.abs(
                reload(list(batch[:2]), training=False).numpy() - steps.infer(*batch[:2]).numpy()
            )
        )
    )
    if (
        error > 1e-4
        or any("local" in layer.name for layer in reload.layers)
        or reload.output_shape[-1] != 28
    ):
        raise ValueError("[sequence-v2.1/inference] Auxiliary leaked into normal view")
    saved = tf.train.Checkpoint(model=model, optimizer=optimizer).save(str(root / "checkpoint"))
    restored = build_model(tf, p)
    opt2 = tf.keras.optimizers.Adam(p["learning_rate"], clipnorm=p["gradient_clip_norm"])
    opt2.build(restored.trainable_variables)
    tf.train.Checkpoint(model=restored, optimizer=opt2).restore(
        saved
    ).assert_existing_objects_matched()
    assert state_digest(model, optimizer) == state_digest(restored, opt2)
    # Inference graph topology matches existing V2; no new operators/Android work.
    assert [(layer.name, layer.__class__.__name__) for layer in normal.layers] == [
        (layer.name, layer.__class__.__name__) for layer in frozen.layers
    ]
    for name, info in inventory.items():
        assert sha256(REPO / name) == info["sha256"]
    output = dict(
        status="V2_1_ENGINEERING_SMOKE_PASS",
        parameters=model.count_params(),
        inference_parameters=normal.count_params(),
        auxiliary_parameters=model.count_params() - normal.count_params(),
        local_receptive_field=61,
        auxiliary_weight=p["auxiliary_weight"],
        initial_losses=[float(v.numpy()) for v in initial_losses],
        initial_gradient_norm=initial_norm,
        head_gradient_norms=head_norms,
        history=history,
        updates=update,
        both_objectives_exact_overfit=True,
        maximum_padding_difference=max(padding_errors),
        local_independent_of_late_blocks=local_independence,
        normal_warmstart_logit_error=initial_parity,
        inference_reload_error=error,
        inference_topology_unchanged=True,
        inference_output=[None, None, 28],
        checkpoint_optimizer_restore_exact=True,
        train_regimes=regimes,
        configuration_sha256=sha256(CONFIG),
        code_sha256=code_identity(),
        adapter=identity(),
        protected_files=len(inventory),
        protected_changed=[],
        dev_accessed=False,
        test_accessed=False,
        accuracy_claim="NONE_TRAIN_ONLY_ENGINEERING",
        android_exported=False,
    )
    write_json_atomic(GATE / "architecture_gate.json", output)
    print(
        json.dumps(
            {
                k: v
                for k, v in output.items()
                if k not in ["history", "train_regimes", "code_sha256"]
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
