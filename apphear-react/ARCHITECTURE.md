# RN01 Architecture

RN01 is deliberately small:

```text
VisionCamera Camera View
  -> CameraFrameOutput worklet
  -> dispose frame immediately
  -> schedule tiny counter update on RN runtime
  -> FPS dashboard + JSON export
```

It does not read pixel buffers, run MediaPipe, run TFLite, construct 258 features, or recognize ASL.

## Boundaries

React Native can measure frame callback cadence for RN01. It cannot become the real-time vision path.
RN02+ must move MediaPipe and all model-facing work into native Swift/Kotlin modules.

## Why Frame Output Exists in RN01

A plain camera preview can show whether the app opens, but it does not tell us whether frames are
available to a future native processing path. The Frame Output callback gives a lightweight cadence
signal. Frames are disposed immediately to avoid stalling the camera pipeline.

## Metrics

- callback FPS;
- dropped frame count;
- elapsed time;
- active lens;
- selected frame size;
- requested FPS and target resolution.

These are not landmark FPS and must not be reported as recognition performance.
