"""Training-only local letter supervision on the unchanged V2 inference graph."""

from __future__ import annotations

from typing import Any

from model.fingerspelling_sequence_v2_encoder import build_model as v2_model
from model.fingerspelling_sequence_v2_encoder import configuration as v2_configuration
from pipeline.fingerspelling.adapter import sha256
from pipeline.fingerspelling.expanded_training import read_json
from pipeline.fingerspelling.sequence_manifest import REPO

CONFIG = REPO / "model/config/fingerspelling_sequence_v2_1_01.json"


def configuration() -> dict[str, Any]:
    p, frozen = read_json(CONFIG), v2_configuration()
    exceptions = {"schema_version", "initialization", "selection"}
    if any(p.get(k) != v for k, v in frozen.items() if k not in exceptions):
        raise ValueError("[sequence-v2.1/config] Frozen V2 backbone/policy changed")
    if (
        p["schema_version"] != "apphear.fingerspelling.sequence_encoder_v2_1.v1"
        or p["auxiliary_block"] != 4
        or p["auxiliary_logits"] != 27
        or p["auxiliary_blank_index"] != 26
        or p["auxiliary_weight"] != 0.5
        or p["selection"]
        != "MEAN_UNCALIBRATED_NATIVE_PHONE_FULL_NOSPACE_DEV_A_GREEDY_CER_FIRST_TIE"
    ):
        raise ValueError("[sequence-v2.1/config] Fixed local/selection contract changed")
    return p


def build_model(tf: Any, config: dict[str, Any], *, warmstart: bool = True) -> Any:
    main = v2_model(tf, config)
    if warmstart:
        path = REPO / config["warmstart_model"]
        if sha256(path) != config["warmstart_sha256"]:
            raise ValueError("[sequence-v2.1/init] V2 epoch046 hash mismatch")
        frozen = tf.keras.models.load_model(path, compile=False)
        main.set_weights(frozen.get_weights())
    local = tf.keras.layers.Dense(27, name="local_letter_logits")(
        main.get_layer("v2_block3_mask").output
    )
    local = tf.keras.layers.Multiply(name="local_output_mask")([local, main.inputs[1]])
    return tf.keras.Model(
        main.inputs,
        {"main": main.output, "local": local},
        name="fingerspell_sequence_encoder_v2_1_training",
    )


def inference_model(tf: Any, training_model: Any) -> Any:
    return tf.keras.Model(
        training_model.inputs,
        training_model.output["main"],
        name="fingerspell_sequence_encoder_v2_1_inference",
    )
