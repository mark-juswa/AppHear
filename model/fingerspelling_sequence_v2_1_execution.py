"""Dual CTC steps. SPACE is removed from targets only in the local objective."""

from __future__ import annotations

from typing import Any

from model.fingerspelling_sequence_v2_1_encoder import inference_model


def letters(text: str) -> str:
    if not text or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ " for c in text):
        raise ValueError("[sequence-v2.1/target] Authoritative alphabet transcript required")
    result = text.replace(" ", "")
    if not result:
        raise ValueError("[sequence-v2.1/target] Empty letter target refused")
    return result


def loss_values(tf: Any, outputs: Any, y: Any, lengths: Any, targets: Any, weight: float) -> Any:
    main = tf.nn.ctc_loss(
        labels=y,
        logits=outputs["main"],
        label_length=targets,
        logit_length=lengths,
        logits_time_major=False,
        blank_index=27,
    )
    valid = tf.sequence_mask(targets, tf.shape(y)[1]) & (y != 26)
    local_y = tf.ragged.boolean_mask(y, valid).to_tensor(default_value=0)
    local_lengths = tf.reduce_sum(tf.cast(valid, tf.int32), axis=1)
    tf.debugging.assert_positive(local_lengths)
    local = tf.nn.ctc_loss(
        labels=local_y,
        logits=outputs["local"],
        label_length=local_lengths,
        logit_length=lengths,
        logits_time_major=False,
        blank_index=26,
    )
    main, local = tf.reduce_mean(main), tf.reduce_mean(local)
    total = main + weight * local
    for value in [main, local, total]:
        tf.debugging.assert_all_finite(value, "Non-finite V2.1 CTC")
    return total, main, local


class DualSteps:
    def __init__(self, tf: Any, model: Any, config: dict[str, Any], optimizer: Any = None):
        normal = inference_model(tf, model)
        inputs = [
            tf.TensorSpec([None, None, 405], tf.float32),
            tf.TensorSpec([None, None, 1], tf.float32),
        ]
        signature = inputs + [
            tf.TensorSpec([None, None], tf.int32),
            tf.TensorSpec([None], tf.int32),
            tf.TensorSpec([None], tf.int32),
        ]

        @tf.function(input_signature=inputs, jit_compile=False)
        def infer(x: Any, mask: Any) -> Any:
            return normal([x, mask], training=False)

        def gradient_function(training: bool) -> Any:
            @tf.function(input_signature=signature, jit_compile=False)
            def gradient(x: Any, mask: Any, y: Any, lengths: Any, targets: Any) -> Any:
                with tf.GradientTape() as tape:
                    losses = loss_values(
                        tf,
                        model([x, mask], training=training),
                        y,
                        lengths,
                        targets,
                        config["auxiliary_weight"],
                    )
                values = tape.gradient(losses[0], model.trainable_variables)
                for value in values:
                    if value is None:
                        raise ValueError("[sequence-v2.1/gradient] Missing trainable gradient")
                    tf.debugging.assert_all_finite(value, "Non-finite V2.1 gradient")
                return losses, values

            return gradient

        self.infer = infer
        self.gradients_without_dropout = gradient_function(False)
        self.gradients_training = gradient_function(True)
        self.update = None
        if optimizer is not None:

            @tf.function(input_signature=signature, jit_compile=False)
            def update(x: Any, mask: Any, y: Any, lengths: Any, targets: Any) -> Any:
                losses, values = self.gradients_training(x, mask, y, lengths, targets)
                optimizer.apply_gradients(zip(values, model.trainable_variables, strict=True))
                return losses

            self.update = update
