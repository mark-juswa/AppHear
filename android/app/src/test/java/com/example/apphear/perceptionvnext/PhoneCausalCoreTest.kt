package com.example.apphear.perceptionvnext

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PhoneCausalCoreTest {
    @Test
    fun featureBuilderUsesPreviousGenuineObservationAndExplicitValidity() {
        val builder = PhoneSegmentationFeatureBuilder()
        val first = observation(0, 1_000.0, x = 20f, proposal = true, observed = true)
        val second = observation(1, 1_200.0, x = 30f, proposal = true, observed = true)
        val firstFeatures = builder.derive(first)
        val secondFeatures = builder.derive(second)

        assertEquals(378, firstFeatures.size)
        assertEquals(0f, firstFeatures[215], 0f)
        assertEquals(0f, firstFeatures[216], 0f)
        assertEquals(0.2f, secondFeatures[215], 1e-6f)
        assertEquals(0.1f, secondFeatures[216], 1e-6f)
        assertEquals(1f, secondFeatures[300], 0f)
        assertEquals(0f, secondFeatures[374], 0f)
        assertTrue(secondFeatures.all { it.isFinite() })
    }

    @Test
    fun featureBuilderDoesNotCarryMissingHandEvidence() {
        val builder = PhoneSegmentationFeatureBuilder()
        builder.derive(observation(0, 0.0, x = 20f, proposal = true, observed = true))
        val missing = builder.derive(observation(1, 200.0, x = 90f, proposal = false, observed = false))
        assertEquals(0f, missing[0], 0f)
        assertEquals(0f, missing[84], 0f)
        assertEquals(0f, missing[176], 0f)
        assertEquals(0f, missing[216], 0f)
        assertEquals(0f, missing[300], 0f)
        assertEquals(-1f, missing[374], 0f)
        assertEquals(-1f, missing[376], 0f)
    }

    @Test
    fun segmentationEvidenceSummaryUsesExistingRawDeltaBlocks() {
        val builder = PhoneSegmentationFeatureBuilder()
        builder.derive(observation(0, 1_000.0, x = 20f, proposal = true, observed = true))
        val features = builder.derive(
            observation(1, 1_200.0, x = 30f, proposal = true, observed = true),
        )
        val summary = summarizePhoneSegmentationEvidence(features)

        assertEquals(1, summary.handDeltaValidCount)
        assertEquals(0.1, summary.handDeltaMeanMagnitude!!, 1e-6)
        assertEquals(1, summary.roiDeltaValidCount)
        assertEquals(0.1, summary.roiDeltaMaxMagnitude!!, 1e-6)
        assertEquals(0, summary.bodyDeltaValidCount)
        assertNull(summary.bodyDeltaMeanMagnitude)
        assertEquals(0, summary.observedTransitionCount)
        assertEquals(0, summary.proposalTransitionCount)
    }

    @Test
    fun config01EmitsOnlyAfterObservedPersistentPost() {
        val decoder = PhoneCausalEventProducer()
        assertNull(decoder.consume(0.0, 0).event)
        assertNull(decoder.consume(100.0, 1).event)
        assertNull(decoder.consume(250.0, 1).event)
        assertNull(decoder.consume(400.0, 2).event)
        val event = decoder.consume(670.0, 2).event
        assertNotNull(event)
        assertEquals(100.0, event!!.logicalActiveStartMs, 0.0)
        assertEquals(250.0, event.logicalActiveEndMs, 0.0)
        assertEquals(400.0, event.terminalPostMs, 0.0)
        assertEquals(670.0, event.commitMs, 0.0)
        assertEquals(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, decoder.state)
    }

    @Test
    fun config01ActiveToPreNeverDirectlyEmits() {
        val decoder = PhoneCausalEventProducer()
        decoder.consume(0.0, 1)
        val gap = decoder.consume(100.0, 0)
        val discard = decoder.consume(240.0, 0)
        assertNull(gap.event)
        assertNull(discard.event)
        assertEquals("DISCARD_SUSTAINED_PRE_GAP", discard.action)
        assertEquals(PhoneDecoderState.IDLE, decoder.state)
    }

    @Test
    fun config01BriefPostCancelledByActiveDoesNotCut() {
        val decoder = PhoneCausalEventProducer()
        decoder.consume(0.0, 1)
        decoder.consume(150.0, 1)
        decoder.consume(300.0, 2)
        val resumed = decoder.consume(400.0, 1)
        assertNull(resumed.event)
        assertEquals("CANCEL_POST_ACTIVE_RESUMED", resumed.action)
        assertEquals(PhoneDecoderState.ACTIVE_CANDIDATE, decoder.state)
    }

    @Test
    fun preOnlyControlDoesNotRearmOnPost() {
        val decoder = completedDecoder(PhoneRearmPolicy.PRE_ONLY)
        decoder.consume(900.0, PhoneCausalEventProducer.POST_RECOVERY)
        decoder.consume(1_100.0, PhoneCausalEventProducer.POST_RECOVERY)
        assertEquals(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, decoder.state)
        val begin = decoder.consume(1_300.0, PhoneCausalEventProducer.PRE_IDLE)
        val complete = decoder.consume(1_700.0, PhoneCausalEventProducer.PRE_IDLE)
        assertEquals("BEGIN_REARM_PRE", begin.action)
        assertEquals("REARM_COMPLETE", complete.action)
        assertEquals(PhoneDecoderState.IDLE, decoder.state)
    }

    @Test
    fun experimentalPolicyRearmsOnPersistentPost() {
        val decoder = completedDecoder(PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL)
        decoder.consume(900.0, PhoneCausalEventProducer.POST_RECOVERY)
        val complete = decoder.consume(1_070.0, PhoneCausalEventProducer.POST_RECOVERY)
        assertEquals("REARM_COMPLETE", complete.action)
        assertEquals("STABLE_NON_ACTIVE_COMPLETE", complete.rearmReason)
        assertEquals(400.0, complete.rearmElapsedMs!!, 0.0)
        assertEquals(PhoneDecoderState.IDLE, decoder.state)
    }

    @Test
    fun activeResetsExperimentalRecoveryPersistence() {
        val decoder = completedDecoder(PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL)
        decoder.consume(900.0, PhoneCausalEventProducer.POST_RECOVERY)
        val reset = decoder.consume(1_000.0, PhoneCausalEventProducer.ACTIVE_SIGN)
        decoder.consume(1_200.0, PhoneCausalEventProducer.POST_RECOVERY)
        val notYet = decoder.consume(1_500.0, PhoneCausalEventProducer.POST_RECOVERY)
        assertEquals("RESET_REARM_ACTIVE", reset.action)
        assertEquals(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, notYet.stateAfter)
    }

    @Test
    fun largeObservationGapCannotSatisfyRearm() {
        val decoder = completedDecoder(PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL)
        val gap = decoder.consume(1_300.0, PhoneCausalEventProducer.POST_RECOVERY)
        val notYet = decoder.consume(1_500.0, PhoneCausalEventProducer.POST_RECOVERY)
        val complete = decoder.consume(1_750.0, PhoneCausalEventProducer.POST_RECOVERY)
        assertEquals("RESET_REARM_GAP_AND_BEGIN", gap.action)
        assertEquals(PhoneDecoderState.EVENT_EMITTED_WAIT_REARM, notYet.stateAfter)
        assertEquals("REARM_COMPLETE", complete.action)
    }

    @Test
    fun admissionBoundaryIsPassThroughAndDoesNotChangeFirstEvent() {
        val control = PhoneCausalEventProducer(
            PhoneDecoderConfig(rearmPolicy = PhoneRearmPolicy.PRE_ONLY),
        )
        val experimental = PhoneCausalEventProducer(
            PhoneDecoderConfig(rearmPolicy = PhoneRearmPolicy.PRE_OR_POST_EXPERIMENTAL),
        )
        val times = listOf(0.0, 100.0, 250.0, 400.0, 670.0)
        val states = listOf(0, 1, 1, 2, 2)
        val controlUpdates = times.zip(states).map { (time, state) -> control.consume(time, state) }
        val experimentalUpdates = times.zip(states).map { (time, state) -> experimental.consume(time, state) }
        assertEquals("ADMIT", experimentalUpdates[1].admissionDecision)
        assertEquals("PASS_THROUGH_ACTIVE", experimentalUpdates[1].admissionReason)
        assertEquals(controlUpdates.last().event, experimentalUpdates.last().event)
    }

    @Test
    fun materializerBracketsSparseRequestedContextOutward() {
        val buffer = PhoneObservationRingBuffer()
        val observations = listOf(
            observation(0, 0.0), observation(1, 200.0), observation(2, 400.0),
            observation(3, 600.0), observation(4, 800.0), observation(5, 1_000.0),
        )
        observations.forEach(buffer::append)
        val event = PhoneLogicalSignEvent(1, 2, 3, 400.0, 600.0, 4, 800.0, 5, 1_000.0)
        val window = buffer.materialize(event)
        assertEquals(0, window.selectedStartIndex)
        assertEquals(5, window.selectedEndIndex)
        assertEquals(400.0, window.actualPreContextMs, 0.0)
        assertEquals(200.0, window.actualPostContextMs, 0.0)
        assertFalse(window.leftCensored)
        assertTrue(window.rightCensored)
        assertArrayEquals(intArrayOf(0, 1, 2, 3, 4, 5), window.observations.map { it.sourceIndex }.toIntArray())
    }

    @Test(expected = IllegalArgumentException::class)
    fun ringBufferRejectsDuplicateTimestamp() {
        val buffer = PhoneObservationRingBuffer()
        buffer.append(observation(0, 10.0))
        buffer.append(observation(1, 10.0))
    }

    private fun observation(
        index: Int,
        timestampMs: Double,
        x: Float = 20f,
        proposal: Boolean = false,
        observed: Boolean = false,
    ): PhoneRawObservation {
        val handXy = Array(2) { FloatArray(42) }
        handXy[0][0] = x
        val handValid = Array(2) { BooleanArray(21) }
        handValid[0][0] = true
        val support = Array(2) { FloatArray(21) }
        val roi = Array(2) { FloatArray(3) }
        roi[0] = floatArrayOf(x, 30f, 40f)
        return PhoneRawObservation(
            sourceIndex = index,
            timestampMs = timestampMs,
            sourceWidth = 100,
            sourceHeight = 200,
            handXy = handXy,
            handJointValid = handValid,
            handProposalSupport = support,
            handPresence = floatArrayOf(0.9f, Float.NaN),
            handObserved = booleanArrayOf(observed, false),
            handProposalPresent = booleanArrayOf(proposal, false),
            handRoiCenterSide = roi,
            bodyXy = FloatArray(16),
            bodySupport = FloatArray(8),
            bodyValid = BooleanArray(8),
            bodyAvailable = false,
        )
    }

    private fun completedDecoder(policy: PhoneRearmPolicy): PhoneCausalEventProducer {
        val decoder = PhoneCausalEventProducer(PhoneDecoderConfig(rearmPolicy = policy))
        decoder.consume(0.0, PhoneCausalEventProducer.PRE_IDLE)
        decoder.consume(100.0, PhoneCausalEventProducer.ACTIVE_SIGN)
        decoder.consume(250.0, PhoneCausalEventProducer.ACTIVE_SIGN)
        decoder.consume(400.0, PhoneCausalEventProducer.POST_RECOVERY)
        assertNotNull(decoder.consume(670.0, PhoneCausalEventProducer.POST_RECOVERY).event)
        return decoder
    }
}
