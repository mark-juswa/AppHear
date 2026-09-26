"""Export the first Perception vNext body/localization candidate to ONNX.

The candidate is the official 256x192 DWPose-t checkpoint.  The exported graph
contains one inference branch only: mobile execution must not silently pay the
2x flip-test cost used by the paper's evaluation configuration.  Affine
preprocessing, SimCC decoding, source-coordinate restoration, presence, and
the hand-crop adapter remain explicit runtime operations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / (
    "artifacts/recognition_upgrade/perception_vnext/phone_01/" "candidate_01_dwpose_t_mp_hand"
)
CONFIG = CANDIDATE / (
    "source/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/"
    "rtmpose-t_8xb64-270e_coco-ubody-wholebody-256x192.py"
)
CHECKPOINT = CANDIDATE / "checkpoint/dw-tt_ucoco.pth"
EXPECTED_CONFIG_SHA256 = "cab60495599afc8cd9eb299c4184fe09bf9c6134fcdb8567d0a9e3ca1712d3cc"
EXPECTED_CHECKPOINT_SHA256 = "7097f5af7f100609acffe58eb01734f02ffbfe22794fe029c2ea0a4d68d0f42d"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export(output: Path, manifest_path: Path) -> dict[str, Any]:
    identity = {
        "config_sha256": sha256(CONFIG),
        "checkpoint_sha256": sha256(CHECKPOINT),
    }
    expected = {
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
    }
    if identity != expected:
        raise RuntimeError(f"VNEXT_CANDIDATE_IDENTITY_MISMATCH: {identity}")

    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    model.eval()
    if tuple(model.cfg.codec["input_size"]) != (192, 256):
        raise RuntimeError("DWPose-t input contract changed")
    if model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("DWPose-t SimCC split ratio changed")
    if model.cfg.model.head.get("out_channels") != 133:
        raise RuntimeError("DWPose-t output topology changed")

    class SinglePassGraph(torch.nn.Module):
        def __init__(self, pose_model):
            super().__init__()
            self.backbone = pose_model.backbone
            self.neck = pose_model.neck if pose_model.with_neck else None
            self.head = pose_model.head

        def forward(self, value):
            features = self.backbone(value)
            if self.neck is not None:
                features = self.neck(features)
            return self.head(features)

    graph = SinglePassGraph(model).eval()
    example = torch.zeros((1, 3, 256, 192), dtype=torch.float32)
    with torch.no_grad():
        torch_x, torch_y = graph(example)
    if tuple(torch_x.shape) != (1, 133, 384):
        raise RuntimeError(f"unexpected SimCC-x shape: {tuple(torch_x.shape)}")
    if tuple(torch_y.shape) != (1, 133, 512):
        raise RuntimeError(f"unexpected SimCC-y shape: {tuple(torch_y.shape)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        graph,
        example,
        str(output),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["simcc_x", "simcc_y"],
        dynamic_axes=None,
    )

    onnx_graph = onnx.load(str(output), load_external_data=True)
    onnx.checker.check_model(onnx_graph)
    session = ort.InferenceSession(str(output), providers=["CPUExecutionProvider"])
    ort_x, ort_y = session.run(["simcc_x", "simcc_y"], {"input": example.numpy()})
    torch_x_np = torch_x.detach().numpy()
    torch_y_np = torch_y.detach().numpy()
    parity = {
        "simcc_x_max_abs_error": float(np.max(np.abs(ort_x - torch_x_np))),
        "simcc_y_max_abs_error": float(np.max(np.abs(ort_y - torch_y_np))),
    }
    if max(parity.values()) > 1e-4:
        raise RuntimeError(f"DWPose-t export parity failure: {parity}")

    operators = sorted(
        {f"{node.domain or 'ai.onnx'}::{node.op_type}" for node in onnx_graph.graph.node}
    )
    manifest = {
        "schema": "APPHEAR_PERCEPTION_VNEXT_MODEL_EXPORT_V1",
        "candidate_id": "dwpose_t_singlepass_256x192",
        "role": "CURRENT_FRAME_BODY_AND_ANATOMICAL_HAND_LOCALIZER",
        "production_recognizer_connected": False,
        "precision": "FP32",
        "input": {
            "name": "input",
            "shape": [1, 3, 256, 192],
            "dtype": "float32",
            "semantics": "affine-warped upright-unmirrored RGB, normalized NCHW",
        },
        "outputs": [
            {
                "name": "simcc_x",
                "shape": [1, 133, 384],
                "dtype": "float32",
            },
            {
                "name": "simcc_y",
                "shape": [1, 133, 512],
                "dtype": "float32",
            },
        ],
        "point_order": "COCO_WHOLEBODY_133",
        "body_indices": [0, 16],
        "left_hand_indices": [91, 111],
        "right_hand_indices": [112, 132],
        "simcc_split_ratio": 2.0,
        "test_time_flip_inside_graph": False,
        "reason_flip_disabled": "mobile single-pass candidate; no temporal or stale evidence",
        "decoder_inside_graph": False,
        "source_coordinate_restore_inside_graph": False,
        "hand_presence_inside_graph": False,
        "config_sha256": identity["config_sha256"],
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "onnx_sha256": sha256(output),
        "onnx_bytes": output.stat().st_size,
        "opset": 17,
        "operators": operators,
        "node_count": len(onnx_graph.graph.node),
        "initializer_count": len(onnx_graph.graph.initializer),
        "synthetic_zero_parity": parity,
        "training_performed": False,
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=CANDIDATE / "export/dwpose_t_singlepass.onnx"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=CANDIDATE / "export/model_manifest.json",
    )
    args = parser.parse_args()
    print(json.dumps(export(args.output, args.manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
