# RN02 iOS Native Scaffold

This folder contains the planned native iOS hand-only benchmark surface for RN02.

Current status: scaffold only. It is intentionally not wired into Xcode until the project is opened
on macOS with CocoaPods and a physical iPhone available.

Key rule: React Native receives compact benchmark sessions only. Raw frames and per-frame landmark
arrays stay native.

Required iOS dependency: `MediaPipeTasksVision` in `ios/Podfile`.
Required model asset: `assets/mediapipe/hand_landmarker.task` copied from the repo's canonical
MediaPipe assets.