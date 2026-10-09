"""Direct MediaPipe hand-landmark submodel adapter for proposed hand ROIs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.perception_vnext.hand_roi import HandRoi, restore_crop_xy


@dataclass(frozen=True)
class RefinedHand:
    xy_source: np.ndarray
    xy_crop: np.ndarray
    raw_z: np.ndarray
    world_xyz: np.ndarray
    presence: float
    handedness: float
    valid: np.ndarray


class MediaPipeHandRefiner:
    """TFLite adapter that never promotes the model's Z to global depth."""

    INPUT_SIZE = 224

    def __init__(self, model_path: Path, num_threads: int = 2):
        import tensorflow as tf

        self._interpreter = tf.lite.Interpreter(
            model_path=str(model_path), num_threads=num_threads
        )
        self._interpreter.allocate_tensors()
        inputs = self._interpreter.get_input_details()
        outputs = self._interpreter.get_output_details()
        if len(inputs) != 1 or tuple(inputs[0]["shape"]) != (1, 224, 224, 3):
            raise RuntimeError("unexpected MediaPipe hand-refiner input contract")
        by_name: dict[str, dict[str, Any]] = {value["name"]: value for value in outputs}
        required = {
            "Identity": (1, 63),
            "Identity_1": (1, 1),
            "Identity_2": (1, 1),
            "Identity_3": (1, 63),
        }
        for name, shape in required.items():
            if name not in by_name or tuple(by_name[name]["shape"]) != shape:
                raise RuntimeError(f"unexpected MediaPipe hand-refiner output: {name}")
        self._input_index = int(inputs[0]["index"])
        self._outputs = {name: int(by_name[name]["index"]) for name in required}

    def refine(self, crop_bgr: np.ndarray, roi: HandRoi) -> RefinedHand:
        crop = np.asarray(crop_bgr)
        if crop.shape != (self.INPUT_SIZE, self.INPUT_SIZE, 3):
            raise ValueError("hand refiner expects a 224x224 BGR crop")
        input_rgb = crop[:, :, ::-1].astype(np.float32) / np.float32(255.0)
        return self.refine_input(input_rgb, roi)

    def refine_input(self, input_rgb: np.ndarray, roi: HandRoi) -> RefinedHand:
        """Run an already normalized RGB crop (the Android runtime input contract)."""

        value = np.asarray(input_rgb, np.float32)
        if value.shape != (self.INPUT_SIZE, self.INPUT_SIZE, 3):
            raise ValueError("hand refiner expects a [224,224,3] normalized RGB tensor")
        if not np.all(np.isfinite(value)):
            raise ValueError("hand refiner input contains non-finite values")
        self._interpreter.set_tensor(self._input_index, value[None])
        self._interpreter.invoke()
        landmarks = self._interpreter.get_tensor(self._outputs["Identity"]).reshape(21, 3)
        presence = float(
            self._interpreter.get_tensor(self._outputs["Identity_1"]).reshape(-1)[0]
        )
        handedness = float(
            self._interpreter.get_tensor(self._outputs["Identity_2"]).reshape(-1)[0]
        )
        world = self._interpreter.get_tensor(self._outputs["Identity_3"]).reshape(21, 3)
        xy_crop = np.asarray(landmarks[:, :2], np.float32)
        xy_source = restore_crop_xy(xy_crop, roi, self.INPUT_SIZE)
        valid = (
            np.all(np.isfinite(xy_source), axis=1)
            & (xy_crop[:, 0] >= 0)
            & (xy_crop[:, 0] < self.INPUT_SIZE)
            & (xy_crop[:, 1] >= 0)
            & (xy_crop[:, 1] < self.INPUT_SIZE)
        )
        return RefinedHand(
            xy_source=xy_source,
            xy_crop=xy_crop,
            raw_z=np.asarray(landmarks[:, 2], np.float32),
            world_xyz=np.asarray(world, np.float32),
            presence=presence,
            handedness=handedness,
            valid=valid,
        )

    def close(self) -> None:
        self._interpreter = None
