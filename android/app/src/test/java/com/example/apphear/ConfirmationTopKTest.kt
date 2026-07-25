package com.example.apphear

import com.example.apphear.pipeline.recognition.Confirmation
import com.example.apphear.pipeline.recognition.RecognitionConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * F21 top-3 display logic. The candidate list is DISPLAY-ONLY: it must rank by the same accumulated
 * evidence the commit gate uses, and exposing it must NOT change whether/what commits. These are
 * pure-JVM unit tests (run on `gradlew testDebugUnitTest`, no device).
 */
class ConfirmationTopKTest {

    // Loose gates so a clearly-dominant class commits quickly in the test.
    private fun cfg() = RecognitionConfig(
        thetaConf = -5.0, thetaMargin = 0.0, kStability = 1, temperature = 1.0,
        enableLowFpsConfirmation = false, lowFpsKStability = 1,
        lowFpsThetaConf = -5.0, lowFpsThetaMargin = 0.0, lowFpsMinCommitFrame = 0,
    )

    private fun probs(n: Int, weights: Map<Int, Float>): FloatArray {
        val p = FloatArray(n) { 1e-4f }
        weights.forEach { (i, w) -> p[i] = w }
        val s = p.sum()
        for (i in p.indices) p[i] /= s
        return p
    }

    @Test
    fun topCandidatesRankByAccumulatedEvidenceBestFirst() {
        val n = 6
        val c = Confirmation(cfg(), n)
        // Class 3 strongest, then 1, then 5 — held steady over a few frames.
        val frame = probs(n, mapOf(3 to 0.6f, 1 to 0.25f, 5 to 0.1f))
        repeat(3) { c.update(frame) }
        val cand = c.topCandidates
        assertEquals("top-3 length", 3, cand.size)
        assertEquals("best is the strongest class", 3, cand[0])
        assertEquals("2nd is next strongest", 1, cand[1])
        assertEquals("3rd is third strongest", 5, cand[2])
    }

    @Test
    fun candidatesAreEmptyBeforeFirstUpdateAndAfterReset() {
        val c = Confirmation(cfg(), 6)
        assertEquals(0, c.topCandidates.size)
        c.update(probs(6, mapOf(2 to 0.9f)))
        assertTrue(c.topCandidates.isNotEmpty())
        c.reset()
        assertEquals("reset clears the candidate list", 0, c.topCandidates.size)
    }

    @Test
    fun exposingTopKDoesNotChangeCommitTop1() {
        val n = 6
        val c = Confirmation(cfg(), n)
        val frame = probs(n, mapOf(4 to 0.7f, 0 to 0.2f))
        var commit = c.update(frame)
        // kStability=1 → commits on the first frame the gates pass.
        assertNotNull("a dominant class commits", commit)
        assertEquals("committed class == top-1 candidate", 4, commit!!.classId)
        assertEquals("committed class is candidates[0]", c.topCandidates[0], commit.classId)
    }

    @Test
    fun lowFpsMinCommitFrameDelaysEarlyCommit() {
        val cfg = RecognitionConfig(
            thetaConf = -5.0, thetaMargin = 0.0, kStability = 1, temperature = 1.0,
            enableLowFpsConfirmation = true, lowFpsKStability = 2,
            lowFpsThetaConf = -5.0, lowFpsThetaMargin = 0.0, lowFpsMinCommitFrame = 2,
        )
        val c = Confirmation(cfg, 6)
        val frame = probs(6, mapOf(4 to 0.9f, 0 to 0.05f))

        assertEquals(null, c.update(frame, lowFps = true))
        assertEquals("streak 1 < need 2", c.lastSnapshot.reason)
        assertEquals(null, c.update(frame, lowFps = true))
        assertEquals("frame 1 < min_commit_frame 2", c.lastSnapshot.reason)

        val commit = c.update(frame, lowFps = true)
        assertNotNull("commit fires once min frame is reached", commit)
        assertEquals(2, commit!!.frame)
    }
}

