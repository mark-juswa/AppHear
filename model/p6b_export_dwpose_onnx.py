"""Export the exact frozen FP32 DWPose-L inference graph for P6-B.

The graph accepts the already-affine-warped, RGB-normalized NCHW tensor and
returns the flip-test-averaged SimCC x/y vectors. Preprocessing, official
SimCC decoding, source-coordinate restoration, and V2 construction remain
explicit governed operations outside the neural graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/toolchain/source_snapshot/mmpose/configs/wholebody_2d_keypoint/rtmpose/ubody/rtmpose-l_8xb64-270e_coco-ubody-wholebody-256x192.py"
CHECKPOINT = ROOT / "artifacts/recognition_upgrade/perception_backend_replacement/p2a_dwpose_l_01/checkpoint/dw-ll_ucoco.pth"
EXPECTED_CONFIG_SHA = "b2e741d2428667c99e74218f5170a183337602755c76e5b4138546a9b59d5032"
EXPECTED_CHECKPOINT_SHA = "e9600664e7927229ed594197d552023e3be213f810beb38847a959ec8261e0f7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    identity = {"config_sha256": sha256(CONFIG), "checkpoint_sha256": sha256(CHECKPOINT)}
    if identity != {"config_sha256": EXPECTED_CONFIG_SHA, "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA}:
        raise RuntimeError(f"P6B_FROZEN_MODEL_IDENTITY_MISMATCH: {identity}")

    import torch
    from mmpose.apis import init_model
    from mmpose.utils import register_all_modules

    register_all_modules()
    model = init_model(str(CONFIG), str(CHECKPOINT), device="cpu")
    model.eval()
    if model.cfg.model.head.get("out_channels") != 133:
        raise RuntimeError("frozen output topology is not 133 points")
    if tuple(model.cfg.codec["input_size"]) != (192, 256):
        raise RuntimeError("frozen input size changed")
    if model.cfg.codec["simcc_split_ratio"] != 2.0:
        raise RuntimeError("frozen SimCC split ratio changed")
    if not model.cfg.model.test_cfg.get("flip_test", False):
        raise RuntimeError("frozen flip-test is disabled")

    flip_indices = model.dataset_meta["flip_indices"]
    if len(flip_indices) != 133:
        raise RuntimeError("frozen flip-index topology is not 133 points")

    class FrozenFlipTestGraph(torch.nn.Module):
        def __init__(self, pose_model, indices):
            super().__init__()
            self.backbone = pose_model.backbone
            self.neck = pose_model.neck if pose_model.with_neck else None
            self.head = pose_model.head
            self.register_buffer("flip_indices", torch.tensor(indices, dtype=torch.long))

        def branch(self, value):
            features = self.backbone(value)
            if self.neck is not None:
                features = self.neck(features)
            return self.head(features)

        def forward(self, value):
            pred_x, pred_y = self.branch(value)
            flip_x, flip_y = self.branch(torch.flip(value, dims=(-1,)))
            flip_x = torch.index_select(flip_x, 1, self.flip_indices)
            flip_y = torch.index_select(flip_y, 1, self.flip_indices)
            flip_x = torch.flip(flip_x, dims=(-1,))
            return (pred_x + flip_x) * 0.5, (pred_y + flip_y) * 0.5

    wrapper = FrozenFlipTestGraph(model, flip_indices).eval()
    example = torch.zeros((1, 3, 256, 192), dtype=torch.float32)
    with torch.no_grad():
        sample_x, sample_y = wrapper(example)
    if tuple(sample_x.shape) != (1, 133, 384) or tuple(sample_y.shape) != (1, 133, 512):
        raise RuntimeError(f"unexpected SimCC output shapes {sample_x.shape}/{sample_y.shape}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapper,
        example,
        str(args.output),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["simcc_x", "simcc_y"],
        dynamic_axes=None,
    )

    import onnx

    graph = onnx.load(str(args.output), load_external_data=True)
    onnx.checker.check_model(graph)
    ops = sorted({f"{node.domain or 'ai.onnx'}::{node.op_type}" for node in graph.graph.node})
    manifest = {
        "schema": "P6B_FROZEN_DWPOSE_ONNX_EXPORT_V1",
        "runtime_family": "ONNX_RUNTIME_MOBILE_ANDROID",
        "precision": "FP32",
        "input": {"name": "input", "shape": [1, 3, 256, 192], "dtype": "float32", "semantics": "affine-warped RGB normalized tensor"},
        "outputs": [
            {"name": "simcc_x", "shape": [1, 133, 384], "dtype": "float32"},
            {"name": "simcc_y", "shape": [1, 133, 512], "dtype": "float32"},
        ],
        "flip_test_inside_graph": True,
        "decoder_inside_graph": False,
        "source_coordinate_restore_inside_graph": False,
        "v2_builder_inside_graph": False,
        "opset": 17,
        "operators": ops,
        "node_count": len(graph.graph.node),
        "initializer_count": len(graph.graph.initializer),
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "config_sha256": identity["config_sha256"],
        "onnx_sha256": sha256(args.output),
        "onnx_bytes": args.output.stat().st_size,
        "architecture_changed": False,
        "quantization": False,
        "pruning": False,
        "distillation": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
