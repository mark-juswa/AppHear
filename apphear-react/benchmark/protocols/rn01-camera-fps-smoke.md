# RN01 Camera + FPS Smoke Protocol

Purpose: verify the React Native prototype can open camera preview and collect comparable frame
callback FPS logs before any MediaPipe or model work.

## Devices

Run on:

- one physical iPhone;
- one Android phone used for current AppHear baseline comparisons.

## Runs

For each device and lens:

1. Cool-start app.
2. Start benchmark with requested 60 FPS and 640x480 target frame output.
3. Run 1 minute.
4. Export JSON.
5. Repeat for 3 minutes.
6. Repeat for 5 minutes.

## Record Manually

- device model;
- OS version;
- lens used;
- lighting;
- distance from signer/camera target;
- whether the device warmed or throttled;
- any camera interruptions.

## Pass Criteria

- App opens camera preview without crash.
- Frame callbacks are counted.
- Dropped-frame count is visible.
- Exported JSON uses `apphear.rn01.camera_fps.v1`.
- No MediaPipe, TFLite, feature extraction, or recognition code is present.
