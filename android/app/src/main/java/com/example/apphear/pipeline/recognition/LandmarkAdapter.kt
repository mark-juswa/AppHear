package com.example.apphear.pipeline.recognition

import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult

/**
 * Converts MediaPipe landmarker results into the EXACT flat layout the offline extractor stored
 * (`pipeline/extract/landmarks.py`): pose = 33x(x,y,z,visibility); hands = 2 slots x 21 x (x,y,z),
 * slotted by handedness label (Left=0, Right=1). Absent landmarks are NaN. This is the first link
 * of the S4 parity chain — the numbers must match how training features were built.
 */
object LandmarkAdapter {
    private const val POSE = 33
    private const val HAND = 21

    /**
     * True if the hand landmarker actually saw a hand this frame. Absent hands are NaN (see [hands]),
     * so we test the two slots' wrist (landmark 0) x. Used to gate S5 signing on real hand presence
     * — pose wrists exist even with no hands, so pose motion alone would false-trigger onsets.
     */
    fun handsPresent(hands: FloatArray): Boolean {
        val slot0Wrist = 0 // (0*HAND + 0)*3
        val slot1Wrist = HAND * 3 // (1*HAND + 0)*3
        return !hands[slot0Wrist].isNaN() || !hands[slot1Wrist].isNaN()
    }

    /** PoseLandmarkerResult -> FloatArray(132) [33 x (x,y,z,visibility)]; all-NaN if no pose. */
    fun pose(result: PoseLandmarkerResult?): FloatArray {
        val out = FloatArray(POSE * 4) { Float.NaN }
        val lms = result?.landmarks()?.firstOrNull() ?: return out
        val n = minOf(POSE, lms.size)
        for (k in 0 until n) {
            val lm = lms[k]
            out[k * 4] = lm.x()
            out[k * 4 + 1] = lm.y()
            out[k * 4 + 2] = lm.z()
            out[k * 4 + 3] = lm.visibility().orElse(0f)
        }
        return out
    }

    /** HandLandmarkerResult -> FloatArray(126) [2 slots x 21 x (x,y,z)]; slot by handedness. */
    @Suppress("DEPRECATION") // handednesses() is the working accessor in tasks-vision 0.10.14
    fun hands(result: HandLandmarkerResult?): FloatArray {
        val out = FloatArray(2 * HAND * 3) { Float.NaN }
        if (result == null) return out
        val handed = result.handednesses()
        val lmsList = result.landmarks()
        for (i in lmsList.indices) {
            val label = handed.getOrNull(i)?.firstOrNull()?.categoryName()
            val slot = when (label) {
                "Left" -> 0
                "Right" -> 1
                else -> i % 2
            }
            val lms = lmsList[i]
            val n = minOf(HAND, lms.size)
            for (l in 0 until n) {
                val base = (slot * HAND + l) * 3
                out[base] = lms[l].x()
                out[base + 1] = lms[l].y()
                out[base + 2] = lms[l].z()
            }
        }
        return out
    }
}
