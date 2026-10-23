package com.example.apphear.fingerspelling

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * FINGERSPELL practical v1 decision layer. Synthetic observations here only drive hand
 * usability and timing; no accuracy is claimed by these unit checks.
 */
class FingerspellPracticalPolicyTest {
    private val baseline = HeldLetterConfig(4000.0, 1000.0, 4, 500.0, 3, 1000.0, 800.0, 3, 64)
    private val practical = baseline.copy(acceptWhileHandMissing = true)

    private fun common(t: Double, hand: Boolean = true) = CommonObservation(t, 480, 640,
        Array(2) { FloatArray(42) { 100f } }, Array(2) { BooleanArray(21) { hand } }, Array(2) { FloatArray(21) { 1f } },
        floatArrayOf(if (hand) 1f else 0f, 0f), booleanArrayOf(hand, false), BooleanArray(2), Array(2) { FloatArray(3) },
        FloatArray(16), FloatArray(8), BooleanArray(8), false)

    /** Three matching decodes over 1 s with the hand visible: the baseline acceptance path. */
    private fun hold(p: HeldLetterPolicy, letter: String, start: Double): Boolean {
        val e = p.epoch
        p.observe(common(start - 10)); assertFalse(p.accept(e, start, letter))
        p.observe(common(start + 490)); assertFalse(p.accept(e, start + 500, letter))
        p.observe(common(start + 990)); return p.accept(e, start + 1000, letter)
    }

    @Test fun defaultConfigIsTheLockedBaseline() {
        assertFalse(baseline.acceptWhileHandMissing)
        val snapshot = FingerspellSnapshot(RecognitionMode.FINGERSPELL, FingerspellPhase.CAPTURING, "", "", 0, "")
        assertFalse(snapshot.practical); assertFalse(snapshot.reviewing)
    }

    @Test fun oneFrameDropoutAtCallbackLosesTheLetterOnlyInBaseline() {
        for ((config, expected) in listOf(baseline to "", practical to "E")) {
            val p = HeldLetterPolicy(config); val e = p.epoch
            p.observe(common(0.0)); p.accept(e, 0.0, "E")
            p.observe(common(490.0)); p.accept(e, 500.0, "E")
            p.observe(common(990.0)); p.observe(common(1050.0, hand = false)) // result returns during a 1-frame dropout
            val added = p.accept(e, 1000.0, "E")
            assertEquals(expected, p.preview)
            assertEquals(expected.isNotEmpty(), added)
            assertEquals(if (expected.isEmpty()) HeldLetterAcceptanceReason.HAND_CURRENTLY_MISSING
                else HeldLetterAcceptanceReason.APPENDED, p.lastAcceptanceReason)
        }
    }

    @Test fun sustainedAbsenceStillRearmsAndInvalidatesInFlightResultsInPractical() {
        val p = HeldLetterPolicy(practical); val e = p.epoch
        p.observe(common(0.0)); p.accept(e, 0.0, "L"); p.accept(e, 500.0, "L")
        p.observe(common(1100.0, false)); p.observe(common(1500.0, false)); p.observe(common(2000.0, false))
        assertTrue(p.epoch > e)
        assertFalse(p.accept(e, 1000.0, "L"))
        assertEquals(HeldLetterAcceptanceReason.STALE_EPOCH, p.lastAcceptanceReason)
        assertEquals("", p.preview)
    }

    @Test fun letterAddedWhileHandAlreadyGoneIsNotDoubledByThatSameAbsence() {
        val p = HeldLetterPolicy(practical); val e = p.epoch
        p.observe(common(0.0)); p.accept(e, 0.0, "M")
        p.observe(common(490.0)); p.accept(e, 500.0, "M")
        p.observe(common(990.0)); p.observe(common(1050.0, false))
        assertTrue(p.accept(e, 1000.0, "M")) // added while the hand is already leaving
        p.observe(common(1400.0, false)); p.observe(common(2000.0, false)) // same absence reaches rearm
        assertEquals("M", p.latch)
        assertFalse("Re-showing M after that absence does not double it", hold(p, "M", 3000.0))
        assertEquals("M", p.preview)
        // A deliberate lowering AFTER the letter was visible still allows the double.
        p.observe(common(4100.0, false)); p.observe(common(4500.0, false)); p.observe(common(5000.0, false))
        assertEquals("", p.latch)
        assertTrue(hold(p, "M", 6000.0)); assertEquals("MM", p.preview)
    }

    @Test fun deleteLastRemovesOneLetterKeepsLatchAndDropsInFlightResults() {
        val p = HeldLetterPolicy(practical)
        assertFalse(p.deleteLast())
        assertTrue(hold(p, "M", 0.0)); assertTrue(hold(p, "A", 2000.0)); assertTrue(hold(p, "X", 4000.0))
        val inFlight = p.epoch
        assertTrue(p.deleteLast()); assertEquals("MA", p.preview)
        assertFalse("A result requested before Delete cannot append", p.accept(inFlight, 5500.0, "X"))
        assertFalse("The still-held deleted pose does not re-append", hold(p, "X", 6000.0))
        assertEquals("MA", p.preview)
        assertTrue(hold(p, "R", 8000.0)); assertEquals("MAR", p.preview)
    }

    @Test fun repeatLastAddsExactlyOneDoubleWithoutLoweringTheHand() {
        val p = HeldLetterPolicy(practical)
        assertFalse(p.repeatLast())
        assertTrue(hold(p, "H", 0.0)); assertTrue(hold(p, "E", 2000.0)); assertTrue(hold(p, "L", 4000.0))
        assertTrue(p.repeatLast()); assertEquals("HELL", p.preview)
        assertFalse("Holding L after Repeat never adds a third L", hold(p, "L", 6000.0))
        assertTrue(hold(p, "O", 8000.0)); assertEquals("HELLO", p.preview)
    }

    @Test fun draftSurvivesPauseResumeResetButNotAFullReset() {
        val p = HeldLetterPolicy(practical)
        assertTrue(hold(p, "A", 0.0)); assertTrue(hold(p, "M", 2000.0))
        p.reset(clearPreview = false, keepLatch = true) // practical pause / same-owner reselect / review resume
        assertEquals("AM", p.preview); assertEquals("M", p.latch)
        assertNull(p.request())
        assertFalse("Still-held M is latched across resume", hold(p, "M", 10000.0))
        assertTrue(hold(p, "Y", 12000.0)); assertEquals("AMY", p.preview)
        p.reset() // owner change starts a fresh word
        assertEquals("", p.preview); assertEquals("", p.latch)
    }

    /**
     * Real phone decision logs (fingerspell_continuous_last_active.json). The acceptance layer is
     * replayed exactly: baseline must reproduce every logged reason and the logged preview; the
     * practical policy must keep the third E whose window was 12/12 usable but whose result came
     * back during a single missing observation.
     */
    @Test fun realPhoneDecisionLogsReplay() {
        val doc = JsonParser.parseString(resource("fingerspell_practical/device_decision_logs.json")).asJsonObject
        // MMARY_SESSION was recorded on the phone with practical v1 before the latch guard (intended MARY).
        val expectedPractical = mapOf("EY_SESSION" to "EY", "LOST_E_SESSION" to "E", "MMARY_SESSION" to "MARY")
        for (session in doc.getAsJsonArray("sessions").map { it.asJsonObject }) {
            val name = session.get("session").asString
            val recordedOnBaseline = !session.has("recorded_policy")
            val configs = if (recordedOnBaseline) listOf(baseline to session.get("logged_final_preview").asString)
                else emptyList()
            for ((config, expected) in configs + (practical to expectedPractical.getValue(name))) {
                val p = HeldLetterPolicy(config)
                var lastEpochAfter: Int? = null
                for (e in session.getAsJsonArray("events").map { it.asJsonObject }) {
                    val t = e.get("timestamp_ms").asDouble
                    if (lastEpochAfter != null && e.get("epoch_before").asInt != lastEpochAfter) {
                        // Logged epoch change without an append == sustained hand absence (rearm).
                        val before = p.epoch
                        p.observe(common(t - 1300, false)); p.observe(common(t - 1000, false)); p.observe(common(t - 400, false))
                        assertTrue("$name rearm reproduced", p.epoch > before)
                    }
                    p.observe(common(t - 100))
                    if (e.get("waiting_for_hand").asBoolean) repeat(e.get("missing_observations").asInt) { p.observe(common(t - 50 + it, false)) }
                    p.accept(p.epoch, t, e.get("raw_letter").asString)
                    if (config === baseline) {
                        assertEquals("$name @$t", e.get("acceptance_reason").asString, p.lastAcceptanceReason.name)
                        assertEquals("$name @$t", e.get("preview").asString, p.preview)
                    }
                    lastEpochAfter = e.get("epoch_after").asInt
                }
                assertEquals("$name ${if (config === baseline) "baseline" else "practical"}", expected, p.preview)
            }
        }
    }

    /**
     * Python replay port (tools/fingerspelling/practical_replay.py) == Kotlin HeldLetterPolicy on the exact
     * observe/request/accept sequences it produced from real DEV and IPN raw streams. This ties the offline
     * FSboard/IPN measurements to the Android decision code.
     */
    @Test fun pythonReplayPortMatchesKotlinPolicy() {
        val doc = JsonParser.parseString(resource("fingerspell_practical/parity_traces.json")).asJsonObject
        var checked = 0; var differs = 0
        for (trace in doc.getAsJsonArray("traces").map { it.asJsonObject }) {
            val p = HeldLetterPolicy(if (trace.get("accept_while_hand_missing").asBoolean) practical else baseline)
            val label = "${trace.get("source").asString}/${trace.get("variant").asString}"
            for (event in trace.getAsJsonArray("events").map { it as JsonArray }) {
                when (event[0].asString) {
                    "o" -> { p.observe(common(event[1].asDouble, event[2].asBoolean)); assertEquals(label, event[3].asInt, p.epoch) }
                    "r" -> assertEquals(label, if (event[2].isJsonNull) null else event[2].asInt, p.request()?.size)
                    "a" -> {
                        val added = p.accept(event[1].asInt, event[2].asDouble, event[3].asString)
                        assertEquals(label, event[4].asBoolean, added)
                        assertEquals(label, event[5].asString, p.lastAcceptanceReason.name)
                        assertEquals(label, event[6].asString, p.preview)
                    }
                }
                checked++
            }
        }
        val variants = doc.getAsJsonArray("traces").map { it.asJsonObject }.groupBy { it.get("source").asString }
        for ((_, pair) in variants) {
            fun final(o: JsonObject) = o.getAsJsonArray("events").map { it as JsonArray }.lastOrNull { it[0].asString == "a" }?.get(6)?.asString
            if (final(pair[0]) != final(pair[1])) differs++
        }
        assertTrue(checked > 4000)
        assertEquals("Fixture covers clips where baseline and practical differ", 2, differs)
    }

    private fun resource(path: String) =
        checkNotNull(javaClass.classLoader?.getResource(path)) { "missing $path" }.readText()
}
