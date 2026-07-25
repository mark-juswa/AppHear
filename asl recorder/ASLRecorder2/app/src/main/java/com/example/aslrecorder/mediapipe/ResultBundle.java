package com.example.aslrecorder.mediapipe;

import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult;
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult;

/**
 * One preview frame's hand + pose results (IMAGE mode). Face removed — AppHear 3 runs face OFF
 * (feature-schema.md / v2 lesson a). Used for the live overlay + quality hint only.
 */
public class ResultBundle {

    public final HandLandmarkerResult handLandmarkerResult;
    public final PoseLandmarkerResult poseLandmarkerResult;

    public ResultBundle(HandLandmarkerResult hand, PoseLandmarkerResult pose) {
        this.handLandmarkerResult = hand;
        this.poseLandmarkerResult = pose;
    }

    public boolean hasHands() {
        return handLandmarkerResult != null && !handLandmarkerResult.landmarks().isEmpty();
    }

    public boolean hasPose() {
        return poseLandmarkerResult != null && !poseLandmarkerResult.landmarks().isEmpty();
    }
}
