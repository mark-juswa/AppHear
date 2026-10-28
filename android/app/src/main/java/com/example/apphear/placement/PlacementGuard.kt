package com.example.apphear.placement

/**
 * Signing-placement check for the recognition screen. Pure logic, no Android types, so it can be
 * unit-tested; the camera thread feeds it one frame at a time.
 *
 * Coordinates are normalized to the camera image (0..1, x to the right in image space). [Region] is
 * the part of the image visible on screen, inset by the guide margins. Only the left, right and top
 * edges count: hands below the guide are treated as resting, not as an error.
 *
 * The word model reads hand shape and position relative to the shoulders, so the hard check is only
 * "a raised hand is cut off by the edge of the view". Distance and shoulder visibility are hints,
 * never blocking: a governed test found correct words even with no body reference in view.
 */
class PlacementGuard(
    private val config: Config = Config(),
) {
    data class Config(
        /** Consecutive out-of-guide frames before recognition pauses (~0.4-0.6 s at phone cadence). */
        val enterFrames: Int = 3,
        /** Consecutive good or hands-down frames before recognition resumes. */
        val exitFrames: Int = 3,
        /** Valid joints a hand needs before it counts as present. */
        val minValidJoints: Int = 8,
        /** Shoulder width above this fraction of the visible width means the signer is too close. */
        val tooCloseShoulderFraction: Float = 0.62f,
    ) {
        init { require(enterFrames >= 1 && exitFrames >= 1 && minValidJoints in 1..21) }
    }

    data class Region(val left: Float, val top: Float, val right: Float, val bottom: Float) {
        init { require(left < right && top < bottom) }
        val width: Float get() = right - left
    }

    /** One hand: normalized x,y pairs of its valid joints only. */
    class Hand(val joints: FloatArray) {
        val count: Int get() = joints.size / 2
    }

    class Frame(
        val hands: List<Hand>,
        /** Normalized left and right shoulder (x, y), or null when either is not visible. */
        val shoulders: FloatArray?,
    )

    enum class Status { HANDS_DOWN, OK, HAND_OUT, TOO_CLOSE, NO_SHOULDERS }

    data class Decision(
        val status: Status,
        /** True while recognition should ignore frames. */
        val paused: Boolean,
        /** True on the frame where the pause ends: the caller restarts the word session once here. */
        val resumeNow: Boolean,
        val changed: Boolean,
    )

    private var paused = false
    private var outRun = 0
    private var goodRun = 0
    private var lastStatus: Status? = null

    fun reset() {
        paused = false; outRun = 0; goodRun = 0; lastStatus = null
    }

    fun evaluate(frame: Frame, region: Region): Status {
        val hands = frame.hands.filter { it.count >= config.minValidJoints }
        if (hands.isEmpty()) return Status.HANDS_DOWN
        val out = hands.any { hand ->
            (0 until hand.count).any { joint ->
                val x = hand.joints[joint * 2]
                val y = hand.joints[joint * 2 + 1]
                x < region.left || x > region.right || y < region.top
            }
        }
        if (out) return Status.HAND_OUT
        val shoulders = frame.shoulders ?: return Status.NO_SHOULDERS
        val width = kotlin.math.abs(shoulders[0] - shoulders[2])
        return if (width / region.width > config.tooCloseShoulderFraction) Status.TOO_CLOSE else Status.OK
    }

    /** Hysteresis over [evaluate]: only a sustained HAND_OUT pauses; anything else resumes. */
    fun update(status: Status): Decision {
        var resume = false
        if (status == Status.HAND_OUT) {
            outRun++; goodRun = 0
            if (!paused && outRun >= config.enterFrames) paused = true
        } else {
            goodRun++; outRun = 0
            if (paused && goodRun >= config.exitFrames) { paused = false; resume = true }
        }
        val changed = status != lastStatus || resume
        lastStatus = status
        return Decision(status, paused || resume, resume, changed)
    }
}
