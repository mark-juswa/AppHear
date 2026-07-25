package com.example.apphear.pipeline.features

/**
 * Named MediaPipe pose landmark indices + the mirror permutation — a direct port of
 * `pipeline/topology.py`. Fixed properties of the pose model; never configurable. Part of the
 * S4↔F parity surface (see context/feature-schema.md).
 */
object Topology {
    const val LEFT_SHOULDER = 11
    const val RIGHT_SHOULDER = 12
    const val LEFT_ELBOW = 13
    const val RIGHT_ELBOW = 14
    const val LEFT_WRIST = 15
    const val RIGHT_WRIST = 16
    const val LEFT_HIP = 23
    const val RIGHT_HIP = 24

    const val NUM_POSE = 33
    const val NUM_HAND = 21

    // Left/right symmetric pose-landmark pairs, swapped when mirroring (N3 handedness).
    private val MIRROR_PAIRS = arrayOf(
        1 to 4, 2 to 5, 3 to 6, 7 to 8, 9 to 10,
        11 to 12, 13 to 14, 15 to 16, 17 to 18, 19 to 20, 21 to 22,
        23 to 24, 25 to 26, 27 to 28, 29 to 30, 31 to 32,
    )

    /** Index permutation that swaps every left/right pose pair (nose stays put). */
    val POSE_MIRROR_PERM: IntArray = IntArray(NUM_POSE) { it }.also { perm ->
        for ((a, b) in MIRROR_PAIRS) {
            val tmp = perm[a]; perm[a] = perm[b]; perm[b] = tmp
        }
    }
}
