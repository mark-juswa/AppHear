package com.example.apphear

import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.ui.recognition.RecognitionUiSnapshot
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RecognitionUiSnapshotTest {
    @Test
    fun idleUsesPlaceholderWithoutCandidates() {
        val snapshot = RecognitionUiSnapshot.from(
            state = RecognitionState.Idle,
            sentence = "",
            idleText = "…",
            signingText = "…signing…",
            sentencePlaceholder = "…",
        )

        assertEquals("…", snapshot.primaryText)
        assertEquals("READY", snapshot.stateLabel)
        assertFalse(snapshot.showCandidates)
        assertFalse(snapshot.showSentence)
    }

    @Test
    fun signingShowsTopCandidateAndAlternatives() {
        val snapshot = RecognitionUiSnapshot.from(
            state = RecognitionState.Signing(listOf("HELLO", "HI", "HEY")),
            sentence = "",
            idleText = "…",
            signingText = "…signing…",
            sentencePlaceholder = "…",
        )

        assertEquals("HELLO", snapshot.primaryText)
        assertEquals("HI      HEY", snapshot.candidatesText)
        assertEquals("SIGNING", snapshot.stateLabel)
        assertTrue(snapshot.showCandidates)
    }

    @Test
    fun committedPreservesSentenceFromPipeline() {
        val snapshot = RecognitionUiSnapshot.from(
            state = RecognitionState.Committed("THANK_YOU", 12, listOf("THANK_YOU", "THANKS")),
            sentence = "THANK_YOU",
            idleText = "…",
            signingText = "…signing…",
            sentencePlaceholder = "…",
        )

        assertEquals("THANK_YOU", snapshot.primaryText)
        assertEquals("THANKS", snapshot.candidatesText)
        assertEquals("THANK_YOU", snapshot.sentenceText)
        assertEquals("COMMITTED", snapshot.stateLabel)
        assertTrue(snapshot.showSentence)
    }
}
