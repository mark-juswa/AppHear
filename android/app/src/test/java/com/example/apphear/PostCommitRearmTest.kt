package com.example.apphear

import com.example.apphear.pipeline.recognition.Confirmation
import com.example.apphear.pipeline.recognition.PostCommitRearm
import com.example.apphear.pipeline.recognition.RecognitionConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PostCommitRearmTest {
    @Test
    fun heldCommittedClassNeverRearms() {
        val rearm = PostCommitRearm(departureFrames = 1)
        rearm.onCommit(2)

        repeat(20) {
            assertEquals(PostCommitRearm.DepartureUpdate.None, rearm.observe(2))
        }

        assertFalse(rearm.isVerifying)
    }

    @Test
    fun departureDurationIsIndependentAndConfigurable() {
        val rearm = PostCommitRearm(departureFrames = 3)
        rearm.onCommit(2)

        assertEquals(PostCommitRearm.DepartureUpdate.CandidateStarted(4), rearm.observe(4))
        assertEquals(PostCommitRearm.DepartureUpdate.None, rearm.observe(4))
        assertEquals(PostCommitRearm.DepartureUpdate.Armed(4, 3), rearm.observe(4))
        assertTrue(rearm.isVerifying)
        assertEquals(4, rearm.armedClass)
    }

    @Test
    fun unstableTransitionCannotAccumulateAcrossClasses() {
        val rearm = PostCommitRearm(departureFrames = 2)
        rearm.onCommit(1)

        assertEquals(PostCommitRearm.DepartureUpdate.CandidateStarted(3), rearm.observe(3))
        assertEquals(PostCommitRearm.DepartureUpdate.CandidateStarted(4), rearm.observe(4))
        assertFalse(rearm.isVerifying)
        assertEquals(PostCommitRearm.DepartureUpdate.Armed(4, 2), rearm.observe(4))
    }

    @Test
    fun returningToCommittedClassCancelsDeparture() {
        val rearm = PostCommitRearm(departureFrames = 2)
        rearm.onCommit(1)

        rearm.observe(4)
        assertEquals(PostCommitRearm.DepartureUpdate.CandidateCancelled(4), rearm.observe(1))
        assertFalse(rearm.isVerifying)
    }

    @Test
    fun fullS7MustMatchArmedCandidateBeforeCommitIsEligible() {
        val rearm = PostCommitRearm(departureFrames = 1)
        rearm.onCommit(1)
        rearm.observe(3)

        assertFalse(rearm.matchesVerifiedClass(4))
        assertTrue(rearm.matchesVerifiedClass(3))

        rearm.verificationFailed()
        assertFalse(rearm.isVerifying)
        assertEquals(PostCommitRearm.DepartureUpdate.Armed(4, 1), rearm.observe(4))
    }

    @Test
    fun rearmDoesNotShortenExistingLowFpsS7Criteria() {
        val rearm = PostCommitRearm(departureFrames = 2)
        rearm.onCommit(1)
        rearm.observe(3)
        rearm.observe(3)

        val confirmation = Confirmation(strictLowFpsConfig(), numClasses = 5)
        val frame = dominantProbs(numClasses = 5, classId = 3)
        repeat(4) { index ->
            assertEquals("S7 must not commit on verification update $index", null, confirmation.update(frame, true))
        }
        val commit = confirmation.update(frame, true)

        assertNotNull("the unchanged min_commit_frame permits the fifth update", commit)
        assertEquals(4, commit!!.frame)
        assertTrue("candidate-matched S7 result is eligible", rearm.matchesVerifiedClass(commit.classId))
    }

    private fun strictLowFpsConfig() = RecognitionConfig(
        thetaConf = -5.0,
        thetaMargin = 0.0,
        kStability = 3,
        temperature = 1.0,
        enableLowFpsConfirmation = true,
        lowFpsKStability = 3,
        lowFpsThetaConf = -5.0,
        lowFpsThetaMargin = 0.0,
        lowFpsMinCommitFrame = 4,
    )

    private fun dominantProbs(numClasses: Int, classId: Int): FloatArray {
        val probs = FloatArray(numClasses) { 0.025f }
        probs[classId] = 0.9f
        return probs
    }
}
