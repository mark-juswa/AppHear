package com.example.apphear.perceptionvnext

import com.example.apphear.pipeline.recognition.SentenceBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** Regresses existing behavior. Passing is not evidence of accurate continuous ASL. */
class RecognitionV3Stage2RecordedTransitionTest {
    @Test fun currentProductionDecoderReproducesAllRecordedAndroidDecisions() {
        val decoder = PhoneCausalEventProducer(PhoneDecoderConfig(
            rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL,
        ))
        val input = checkNotNull(javaClass.classLoader?.getResourceAsStream(
            "recognition_v3_stage2/recorded_transition.tsv",
        ))
        var observations = 0
        val eventCommitIndices = mutableListOf<Int>()
        input.bufferedReader().useLines { lines ->
            lines.filter { !it.startsWith("#") && it.isNotBlank() }.forEach { line ->
                val fields = line.split('\t')
                assertEquals(7, fields.size)
                val index = fields[0].toInt()
                assertEquals(observations, index)
                val update = decoder.consume(fields[1].toDouble(), fields[2].toInt())
                assertEquals("before observation $index", fields[3], update.stateBefore.name)
                assertEquals("after observation $index", fields[4], update.stateAfter.name)
                assertEquals("action observation $index", fields[5], update.action)
                val expectedEventId = fields[6].toInt()
                assertEquals("event observation $index", expectedEventId, update.event?.eventId ?: 0)
                if (update.event != null) eventCommitIndices.add(update.event.commitIndex)
                observations++
            }
        }
        assertEquals(1364, observations)
        assertEquals(listOf(81, 359, 702, 832, 875, 973, 1057, 1097, 1223, 1297), eventCommitIndices)
    }

    @Test fun distinctRepeatedEventsStillCollapseAtCurrentSentenceBoundary() {
        val decoder = PhoneCausalEventProducer(PhoneDecoderConfig(
            rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL,
        ))
        val sentence = SentenceBuilder()
        // Deliberately separated decoder episodes: this is a mechanism test, not signed footage.
        val states = listOf(0, 1, 1, 2, 2, 2, 2, 2, 1, 1, 2, 2, 2)
        val events = states.mapIndexedNotNull { index, state ->
            decoder.consume(index * 200.0, state).event
        }
        assertEquals(listOf(1, 2), events.map { it.eventId })
        events.forEach { sentence.add("HELLO") }
        assertEquals("HELLO", sentence.text())
    }

    @Test fun waitingBlocksActiveButReadyDoesNotInventAbsentActiveEvidence() {
        val decoder = PhoneCausalEventProducer(PhoneDecoderConfig(
            rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL,
        ))
        listOf(0, 1, 1, 2, 2).forEachIndexed { index, state -> decoder.consume(index * 200.0, state) }
        assertNotNull(decoder.consume(1000.0, 2).event)
        val blocked = decoder.consume(1200.0, 1)
        assertEquals(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, blocked.stateAfter)
        assertNull(blocked.admissionDecision)
        decoder.consume(1400.0, 2)
        decoder.consume(1600.0, 2)
        assertEquals(PhoneDecoderState.IDLE, decoder.consume(1800.0, 2).stateAfter)
        val readyButPost = decoder.consume(2000.0, 2)
        assertEquals(PhoneDecoderState.IDLE, readyButPost.stateAfter)
        assertNull(readyButPost.event)
        assertNull(readyButPost.admissionDecision)
    }
}
