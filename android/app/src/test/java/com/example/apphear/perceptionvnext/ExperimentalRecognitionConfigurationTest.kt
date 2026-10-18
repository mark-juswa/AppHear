package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Experimental live recognition (Arm A e10 + confirm-boundary): the Kotlin lifecycle must
 * reproduce the Python research decoder event for event, and STABLE must stay the production
 * lifecycle. Passing is decoder parity, not evidence of recognition accuracy.
 */
class ExperimentalRecognitionConfigurationTest {
    private data class Row(val timestampMs: Double, val argmax: Int, val postProbability: Double)
    private data class Event(val start: Int, val end: Int, val terminalPost: Int, val commit: Int)

    private val fixture: Pair<Map<String, List<Row>>, Map<Pair<String, String>, List<Event>>> by lazy {
        val rows = linkedMapOf<String, MutableList<Row>>()
        val events = linkedMapOf<Pair<String, String>, MutableList<Event>>()
        val input = checkNotNull(javaClass.classLoader?.getResourceAsStream(
            "recognition_v3_experimental/confirm_boundary_parity.tsv",
        ))
        input.bufferedReader().useLines { lines ->
            lines.filter { it.isNotBlank() && !it.startsWith("#") }.forEach { line ->
                val f = line.split('\t')
                when (f[0]) {
                    "O" -> {
                        val list = rows.getOrPut(f[1]) { mutableListOf() }
                        assertEquals(list.size, f[2].toInt())
                        list.add(Row(f[3].toDouble(), f[4].toInt(), f[5].toDouble()))
                    }
                    "E" -> events.getOrPut(f[1] to f[2]) { mutableListOf() }
                        .add(Event(f[4].toInt(), f[5].toInt(), f[6].toInt(), f[7].toInt()))
                    else -> error("unknown fixture row $line")
                }
            }
        }
        rows to events
    }

    private fun replay(rows: List<Row>, config: PhoneDecoderConfig): List<Event> {
        val producer = PhoneCausalEventProducer(config)
        return rows.mapNotNull { row ->
            producer.consume(row.timestampMs, row.argmax, row.postProbability).event?.let {
                Event(it.logicalActiveStartIndex, it.logicalActiveEndIndex, it.terminalPostIndex, it.commitIndex)
            }
        }
    }

    @Test fun stableLifecycleReproducesThePythonProductionReplayOnRecordedArmAStreams() {
        val (rows, events) = fixture
        assertEquals(46, rows.size)
        var total = 0
        rows.forEach { (stream, observations) ->
            val expected = events[stream to "BASELINE"].orEmpty()
            assertEquals(stream, expected, replay(observations, PhoneRecognitionConfiguration.STABLE.decoderConfig()))
            total += expected.size
        }
        assertEquals(303, total)
    }

    @Test fun experimentalLifecycleReproducesThePythonConfirmBoundaryDecoder() {
        val (rows, events) = fixture
        var total = 0
        var differFromStable = 0
        rows.forEach { (stream, observations) ->
            val expected = events[stream to "CONFIRM_BOUNDARY_70"].orEmpty()
            assertEquals(stream, expected, replay(observations, PhoneRecognitionConfiguration.EXPERIMENTAL.decoderConfig()))
            total += expected.size
            if (expected != events[stream to "BASELINE"].orEmpty()) differFromStable++
        }
        assertEquals(320, total)
        assertTrue("confirm-boundary must change at least one recorded stream", differFromStable > 0)
    }

    @Test fun stableIsTheProductionLifecycleAndTheDefault() {
        val stable = PhoneRecognitionConfiguration.STABLE.decoderConfig()
        assertEquals(PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL, stable.rearmPolicy)
        assertEquals(PhoneSignAdmissionPolicy.PASS_THROUGH, stable.admissionPolicy)
        assertNull(stable.confirmBoundaryPostPeak)
        assertEquals(PhoneDecoderConfig(rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL), stable)
        assertEquals(0.7, PhoneRecognitionConfiguration.EXPERIMENTAL.decoderConfig().confirmBoundaryPostPeak!!, 0.0)
        assertEquals(PhoneS2Package.ARM_A_E10_CANDIDATE, PhoneRecognitionConfiguration.EXPERIMENTAL.s2Package())
    }

    @Test fun unknownStaleOrUnavailableChoicesResolveToStable() {
        val resolve = PhoneRecognitionConfiguration::resolve
        assertEquals(PhoneRecognitionConfiguration.STABLE, resolve(null, true))
        assertEquals(PhoneRecognitionConfiguration.STABLE, resolve("SOMETHING_ELSE", true))
        assertEquals(PhoneRecognitionConfiguration.STABLE, resolve("EXPERIMENTAL", false))
        assertEquals(PhoneRecognitionConfiguration.EXPERIMENTAL, resolve("EXPERIMENTAL", true))
        assertEquals(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND, resolve("EXPERIMENTAL_WORD_BLEND", true))
        assertEquals(PhoneRecognitionConfiguration.STABLE, resolve("EXPERIMENTAL_WORD_BLEND", false))
        assertEquals(PhoneRecognitionConfiguration.STABLE, resolve("STABLE", true))
    }

    @Test fun wordBlendChangesOnlyTheWordStage() {
        val experimental = PhoneRecognitionConfiguration.EXPERIMENTAL
        val blend = PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND
        assertEquals(experimental.s2Package(), blend.s2Package())
        assertEquals(experimental.decoderConfig(), blend.decoderConfig())
        assertEquals(RecognitionV2LiveRecognizer.FROZEN_GATE2, experimental.wordPackage())
        assertEquals(RecognitionV2LiveRecognizer.FROZEN_GATE2, PhoneRecognitionConfiguration.STABLE.wordPackage())
        assertNull(experimental.pairedWordPackage())
        assertNull(PhoneRecognitionConfiguration.STABLE.pairedWordPackage())
        assertEquals("WORD_BLEND_01", blend.wordPackage().packageId)
        assertEquals("bc8a6c91659eb0c12d3e4a486d6583e4ed7053abff9c7f72611138700e4ea4f1", blend.wordPackage().modelSha256)
        assertEquals(RecognitionV2LiveRecognizer.FROZEN_GATE2, blend.pairedWordPackage())
    }

    @Test fun wordBlend02ChangesOnlyTheWordStageAndIsComparedAgainstBlend01() {
        val experimental = PhoneRecognitionConfiguration.EXPERIMENTAL
        val blend02 = PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02
        assertEquals(experimental.s2Package(), blend02.s2Package())
        assertEquals(experimental.decoderConfig(), blend02.decoderConfig())
        assertEquals("WORD_BLEND_02", blend02.wordPackage().packageId)
        assertEquals("40533bc38c2c416ae2f48e4955029dbdd11d16325765df7aea66db278aaafb30", blend02.wordPackage().modelSha256)
        assertEquals(PhoneRecognitionConfiguration.WORD_BLEND_01, blend02.pairedWordPackage())
        assertEquals(PhoneRecognitionConfiguration.EXPERIMENTAL_WORD_BLEND_02, PhoneRecognitionConfiguration.resolve("EXPERIMENTAL_WORD_BLEND_02", true))
        assertEquals(PhoneRecognitionConfiguration.STABLE, PhoneRecognitionConfiguration.resolve("EXPERIMENTAL_WORD_BLEND_02", false))
    }

    @Test fun confirmBoundaryRefusesToRunWithoutPostProbability() {
        val producer = PhoneCausalEventProducer(PhoneRecognitionConfiguration.EXPERIMENTAL.decoderConfig())
        assertThrows(IllegalArgumentException::class.java) { producer.consume(0.0, 0) }
    }
}
