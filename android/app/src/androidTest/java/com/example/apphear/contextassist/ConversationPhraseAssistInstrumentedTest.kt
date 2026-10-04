package com.example.apphear.contextassist

import android.content.Intent
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.navigation.fragment.NavHostFragment
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.MainActivity
import com.example.apphear.RecognitionActivity
import com.example.apphear.ui.texttoasl.TextToAslFragment
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.SentenceBuilder
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeFalse
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.lang.reflect.InvocationTargetException

/** Exercises the Android seams; only the explicit Gemini test uses synthetic remote input. */
@RunWith(AndroidJUnit4::class)
class ConversationPhraseAssistInstrumentedTest {
    @Test fun textToAslCachesPredictionsWithoutDisplayingThem() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER == "fake")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        val beforeTurnId = ConversationPhraseAssist.presentationState.value.hearingTurnId ?: 0L
        val activity = instrumentation.startActivitySync(
            Intent(appContext, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as MainActivity
        try {
            instrumentation.runOnMainSync {
                activity.findViewById<View>(R.id.navAsl).performClick()
            }
            instrumentation.waitForIdleSync()
            // The preserved Text-to-ASL baseline loads its catalog/avatar asynchronously.
            val avatarReadyField = TextToAslFragment::class.java
                .getDeclaredField("avatarReady").apply { isAccessible = true }
            val avatarReady = withTimeoutOrNull(60_000) {
                var ready = false
                while (!ready) {
                    instrumentation.runOnMainSync {
                        val navHost = activity.supportFragmentManager
                            .findFragmentById(R.id.app_shell_nav_host) as NavHostFragment
                        val textToAsl = navHost.childFragmentManager.primaryNavigationFragment
                            as? TextToAslFragment
                        ready = textToAsl != null && avatarReadyField.getBoolean(textToAsl)
                    }
                    if (!ready) delay(50)
                }
                true
            }
            assertTrue("Text-to-ASL avatar did not finish cold idle loading", avatarReady == true)
            instrumentation.runOnMainSync {
                activity.findViewById<EditText>(R.id.input_text).setText("Where are you going?")
                activity.findViewById<View>(R.id.sign_it_button).performClick()
            }
            val cached = withTimeoutOrNull(30_000) {
                ConversationPhraseAssist.presentationState.first {
                    it.hearingTurnId != null && it.hearingTurnId > beforeTurnId &&
                        it.possibleReplies.isNotEmpty()
                }
            }
            checkNotNull(cached) { "Text-to-ASL submission did not cache fake reply predictions" }
            assertEquals("Where are you going?", cached.hearingText)
            assertTrue(cached.possibleReplies.contains("I'm going home."))
            assertEquals("Where are you going?", ConversationPhraseAssist.recentTurns().last().text)
            instrumentation.runOnMainSync {
                assertEquals("Where are you going?",
                    activity.findViewById<TextView>(R.id.signed_text).text.toString())
                assertFalse(visibleTexts(activity.window.decorView).any {
                    it.contains("Possible replies") || it.contains("I'm going home.")
                })
                activity.findViewById<View>(R.id.clear_button).performClick()
                assertTrue(ConversationPhraseAssist.presentationState.value.possibleReplies.isEmpty())
            }
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun geminiStructuredParserAndVocabularyValidationFailClosed() = runBlocking {
        val parse = GeminiContextPredictionProvider::class.java
            .getDeclaredMethod("parseCandidates", String::class.java)
            .apply { isAccessible = true }
        val provider = GeminiContextPredictionProvider("")
        @Suppress("UNCHECKED_CAST")
        val parsed = parse.invoke(provider,
            """{"candidates":[{"naturalText":"I'm going home.","expectedConcepts":["GO","HOME"]},""" +
                """{"naturalText":"I'm going to market.","expectedConcepts":["GO","MARKET"]}]}""")
            as List<ReplyCandidate>
        assertEquals(listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME"))),
            ReplyCandidateValidator.validate(parsed, setOf("GO", "HOME")))
        assertTrue(provider.predict(PredictionRequest(1, emptyList(), setOf("GO"))).isEmpty())
        try {
            parse.invoke(provider, """{"candidates":[{"naturalText":"Broken"}]}""")
            throw AssertionError("Malformed structured result should fail parsing")
        } catch (error: InvocationTargetException) {
            assertTrue(error.cause is org.json.JSONException)
        }
        try {
            parse.invoke(provider,
                """{"candidates":[{"naturalText":"Old wire field","concepts":["GO"]}]}""")
            throw AssertionError("Gemini must require the new expectedConcepts contract")
        } catch (error: InvocationTargetException) {
            assertTrue(error.cause is org.json.JSONException)
        }
    }

    @Test fun geminiRequestSuppliesFrozenAnchorsWithoutConfiningNaturalEnglish() {
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        val labels = org.json.JSONObject(appContext.assets
            .open("phase4a_gate2_recognizer_parity/manifest.json")
            .bufferedReader().use { it.readText() }).getJSONArray("class_index_to_gloss")
        val allowed = (0 until labels.length()).mapTo(LinkedHashSet()) { labels.getString(it) }
        val bodyMethod = GeminiContextPredictionProvider::class.java
            .getDeclaredMethod("requestBody", PredictionRequest::class.java)
            .apply { isAccessible = true }
        val turn = ConversationTurn(1, ConversationSpeaker.HEARING, ConversationSource.TYPED_TEXT,
            "Where are you going?", 1)
        val body = bodyMethod.invoke(GeminiContextPredictionProvider(""),
            PredictionRequest(1, listOf(turn), allowed)) as org.json.JSONObject
        assertEquals("gemini-3.5-flash-lite", body.getString("model"))
        assertFalse(body.getBoolean("store"))
        assertTrue(body.getString("input").contains("HEARING: Where are you going?"))
        val schema = body.getJSONObject("response_format").getJSONObject("schema")
        val candidates = schema.getJSONObject("properties").getJSONObject("candidates")
        val properties = candidates.getJSONObject("items").getJSONObject("properties")
        val anchors = properties.getJSONObject("expectedConcepts")
        assertEquals(236, allowed.size)
        assertTrue(body.getString("input").contains("Allowed anchor labels: " + allowed.sorted().joinToString(",")))
        assertEquals("string", anchors.getJSONObject("items").getString("type"))
        assertFalse(properties.getJSONObject("naturalText").has("enum"))
    }

    @Test fun geminiSyntheticHearingTurnCachesValidatedPredictionsInShadowOnly() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER == "gemini" &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_GEMINI_API_KEY.isNotBlank())
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
            "Where are you going?", ConversationSource.TYPED_TEXT)).join()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val activity = instrumentation.startActivitySync(
            Intent(appContext, RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as RecognitionActivity
        try {
            val onFrame = RecognitionActivity::class.java.getDeclaredMethod("onFrame", FrameResult::class.java)
                .apply { isAccessible = true }
            val speaker = RecognitionActivity::class.java.getDeclaredField("speakSentence")
                .apply { isAccessible = true }
            val spoken = mutableListOf<String>()
            instrumentation.runOnMainSync {
                speaker.set(activity, { text: String -> spoken.add(text); Unit })
                onFrame.invoke(activity, frame(101, "GO", "GO", 0.72f))
                onFrame.invoke(activity, frame(102, "THINK", "THINK", 0.35f,
                    alternative = SignScore("HOME", 0.33f), sentence = "GO THINK"))
                activity.findViewById<View>(R.id.hearButton).performClick()
                assertEquals(listOf("GO THINK"), spoken)
                assertEquals("GO THINK", activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                val evaluation = ConversationPhraseAssist.recentShadowEvaluations().last()
                assertTrue(evaluation.predictions.isNotEmpty())
                assertTrue(evaluation.predictions.all { it.concepts.isNotEmpty() })
                assertEquals("GO THINK", evaluation.rawSentence)
                assertEquals(listOf(101, 102), evaluation.evidence.map { it.eventId })
                assertEquals("GO THINK", ConversationPhraseAssist.recentTurns().last().text)
            }
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun remoteStructuredParserAndVocabularyValidationFailClosed() {
        val parse = RemoteContextPredictionProvider::class.java
            .getDeclaredMethod("parseCandidates", String::class.java)
            .apply { isAccessible = true }
        val provider = RemoteContextPredictionProvider("")
        @Suppress("UNCHECKED_CAST")
        val parsed = parse.invoke(provider,
            """{"candidates":[{"naturalText":"I'm going home.","concepts":["GO","HOME"]},""" +
                """{"naturalText":"I'm going to market.","concepts":["GO","MARKET"]}]}""")
            as List<ReplyCandidate>
        assertEquals(2, parsed.size)
        assertEquals(listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME"))),
            ReplyCandidateValidator.validate(parsed, setOf("GO", "HOME")))
        @Suppress("UNCHECKED_CAST")
        val empty = parse.invoke(provider, """{"candidates":[]}""") as List<ReplyCandidate>
        assertTrue(ReplyCandidateValidator.validate(empty, setOf("GO", "HOME")).isEmpty())
        try {
            parse.invoke(provider, """{"candidates":[{"naturalText":"Broken"}]}""")
            throw AssertionError("Malformed structured result should fail parsing")
        } catch (error: InvocationTargetException) {
            assertTrue(error.cause is org.json.JSONException)
        }
    }

    @Test fun hearingTurnToVisualMatchToDeafTurn() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled)
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        val prediction = ConversationPhraseAssist.recordHearingMessage(appContext,
            "Where are you going?", ConversationSource.TYPED_TEXT)
        checkNotNull(prediction).join()
        val evidence = listOf(
            RecognitionEvidence(1, 100L, "GO", listOf(SignScore("GO", 0.72f))),
            RecognitionEvidence(2, 200L, "THINK", listOf(
                SignScore("THINK", 0.35f), SignScore("HOME", 0.33f))))
        val result = ConversationPhraseAssist.evaluateShadowTurn(evidence, "GO THINK")
        assertEquals(ShadowReason.MATCH, result.reason)
        assertEquals("I'm going home.", result.assistedCandidate?.naturalText)
        assertEquals(listOf("GO", "THINK"), result.rawEventGlosses)
        assertEquals(listOf("GO", "HOME"), result.assistedCandidate?.assistedGlosses)
        assertTrue(result.wouldChangeRaw)
        assertEquals(evidence, ConversationPhraseAssist.recentShadowEvaluations().last().evidence)
        assertEquals(listOf(ConversationSpeaker.HEARING, ConversationSpeaker.DEAF),
            ConversationPhraseAssist.recentTurns().takeLast(2).map { it.speaker })
        assertEquals("GO THINK", ConversationPhraseAssist.recentTurns().last().text)
    }

    @Test fun deafHistoryUsesCommunicatedSentenceWhileKeepingDuplicateEvents() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled)
        val appContext = InstrumentationRegistry.getInstrumentation().targetContext
        checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
            "Where are you going?", ConversationSource.TYPED_TEXT)).join()
        val sentence = SentenceBuilder()
        listOf("GO", "GO", "HOME").forEach { sentence.add(it) }
        val evidence = listOf(
            RecognitionEvidence(11, 100L, "GO", listOf(SignScore("GO", 0.72f))),
            RecognitionEvidence(12, 200L, "GO", listOf(SignScore("GO", 0.68f))),
            RecognitionEvidence(13, 300L, "HOME", listOf(
                SignScore("HOME", 0.61f), SignScore("THINK", 0.25f))),
        )
        val result = ConversationPhraseAssist.evaluateShadowTurn(evidence, sentence.text())
        assertEquals("GO HOME", sentence.text())
        assertEquals("GO HOME", ConversationPhraseAssist.recentTurns().last().text)
        assertEquals("GO HOME", result.rawSentence)
        assertEquals(listOf("GO", "GO", "HOME"), result.rawEventGlosses)
        assertEquals(listOf(11, 12, 13), result.evidence.map { it.eventId })
        assertEquals("THINK", result.evidence.last().topK[1].gloss)
        assertEquals(ShadowReason.NO_MATCH_OR_AMBIGUOUS, result.reason)
    }

    @Test fun cappedSentenceFeedsHistoryWithoutTruncatingEvidence() {
        assumeTrue(ConversationPhraseAssist.enabled)
        val sentence = SentenceBuilder(maxGlosses = 2)
        listOf("GO", "HOME", "WORK").forEach { sentence.add(it) }
        val evidence = listOf(
            RecognitionEvidence(21, 100L, "GO", listOf(SignScore("GO", 0.7f))),
            RecognitionEvidence(22, 200L, "HOME", listOf(SignScore("HOME", 0.6f))),
            RecognitionEvidence(23, 300L, "WORK", listOf(SignScore("WORK", 0.5f))),
        )
        val result = ConversationPhraseAssist.evaluateShadowTurn(evidence, sentence.text())
        assertEquals("HOME WORK", ConversationPhraseAssist.recentTurns().last().text)
        assertEquals("HOME WORK", result.rawSentence)
        assertEquals(listOf("GO", "HOME", "WORK"), result.rawEventGlosses)
    }

    @Test fun interruptedTurnStillRecordsTheRawSentenceThatHearCommunicated() {
        assumeTrue(ConversationPhraseAssist.enabled)
        val result = ConversationPhraseAssist.evaluateShadowTurn(emptyList(), "GO HOME", incomplete = true)
        assertEquals(ShadowReason.INCOMPLETE_EVIDENCE, result.reason)
        assertEquals(null, result.assistedCandidate)
        assertTrue(result.evidence.isEmpty())
        assertEquals("GO HOME", ConversationPhraseAssist.recentTurns().last().text)
    }

    @Test fun hearSpeaksAndDisplaysRawWhileShadowRecordsDifferentCandidate() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled)
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
            "Where are you going?", ConversationSource.TYPED_TEXT)).join()
        val activity = instrumentation.startActivitySync(
            Intent(appContext, RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as RecognitionActivity
        try {
            val onFrame = RecognitionActivity::class.java.getDeclaredMethod("onFrame", FrameResult::class.java)
                .apply { isAccessible = true }
            val speaker = RecognitionActivity::class.java.getDeclaredField("speakSentence")
                .apply { isAccessible = true }
            val spoken = mutableListOf<String>()
            instrumentation.runOnMainSync {
                speaker.set(activity, { text: String -> spoken.add(text); Unit })
                val shadowBefore = ConversationPhraseAssist.recentShadowEvaluations().size
                assertEquals(View.GONE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.GONE, activity.findViewById<View>(R.id.sentenceCard).visibility)
                onFrame.invoke(activity, frame(0, "", "", 0f).copy(
                    recognition = RecognitionState.Signing(emptyList()),
                    recognitionEvidence = null, phoneSentence = ""))
                assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.GONE, activity.findViewById<View>(R.id.sentenceCard).visibility)
                onFrame.invoke(activity, frame(1, "GO", "GO", 0.72f))
                assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.VISIBLE, activity.findViewById<View>(R.id.sentenceCard).visibility)
                assertEquals(3, activity.findViewById<ViewGroup>(R.id.replyChipContainer).childCount)
                onFrame.invoke(activity, frame(2, "THINK", "THINK", 0.35f,
                    alternative = SignScore("HOME", 0.33f), sentence = "GO THINK"))
                // Re-delivery must not create another evidence/logging event.
                onFrame.invoke(activity, frame(2, "THINK", "THINK", 0.35f,
                    alternative = SignScore("HOME", 0.33f), sentence = "GO THINK"))
                assertEquals("GO THINK",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals("RECOGNIZED",
                    activity.findViewById<TextView>(R.id.recognizedLabel).text.toString())
                assertTrue(ConversationPhraseAssist.presentationState.value.possibleReplies.isNotEmpty())
                assertEquals("I'm going home.",
                    activity.findViewById<TextView>(R.id.contextSupportedText).text.toString())
                assertEquals(View.VISIBLE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                assertTrue(visibleTexts(activity.window.decorView).any {
                    it.contains("POSSIBLE REPLIES")
                })
                val chips = activity.findViewById<ViewGroup>(R.id.replyChipContainer)
                assertEquals(3, chips.childCount)
                assertEquals("I'm going home.", (chips.getChildAt(0) as TextView).text.toString())
                val rawText = activity.findViewById<TextView>(R.id.sentenceText)
                assertEquals(null, rawText.ellipsize)
                assertTrue(rawText.maxLines >= 5)
                assertEquals(shadowBefore, ConversationPhraseAssist.recentShadowEvaluations().size)
                activity.findViewById<View>(R.id.hearButton).performClick()
                assertEquals("GO THINK", spoken.last())
                assertEquals("GO THINK",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals("I'm going home.",
                    activity.findViewById<TextView>(R.id.contextSupportedText).text.toString())
                assertEquals(View.VISIBLE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                assertEquals(View.GONE,
                    activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                val evaluation = ConversationPhraseAssist.recentShadowEvaluations().last()
                assertEquals(ShadowReason.MATCH, evaluation.reason)
                assertEquals(listOf("GO", "THINK"), evaluation.rawEventGlosses)
                assertEquals(listOf(1, 2), evaluation.evidence.map { it.eventId })
                assertEquals(listOf("GO", "HOME"), evaluation.assistedCandidate?.assistedGlosses)
                assertTrue(evaluation.wouldChangeRaw)
                activity.findViewById<View>(R.id.hearButton).performClick()
                assertEquals(listOf("GO THINK", "GO THINK"), spoken)
                assertSame(evaluation, ConversationPhraseAssist.recentShadowEvaluations().last())
                onFrame.invoke(activity, frame(3, "GIFT", "GIFT", 0.6f, sentence = "GIFT HOME"))
                assertEquals(View.GONE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                onFrame.invoke(activity, frame(4, "HOME", "HOME", 0.7f, sentence = "GIFT HOME"))
                assertEquals(null, ConversationPhraseAssist.presentationState.value.contextSupported)
                activity.findViewById<View>(R.id.hearButton).performClick()
                assertEquals("GIFT HOME", spoken.last())
                assertEquals("GIFT HOME", activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.GONE, activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                // finish() schedules teardown; call the lifecycle boundary directly so this
                // assertion cannot race the window manager's asynchronous stop transition.
                instrumentation.callActivityOnStop(activity)
                assertEquals("GIFT HOME",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.GONE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                assertTrue(ConversationPhraseAssist.presentationState.value.possibleReplies.isEmpty())
            }
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun disabledModeKeepsRawHearAndDoesNotRecordShadowEvaluation() {
        assumeFalse(ConversationPhraseAssist.enabled)
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        val activity = instrumentation.startActivitySync(
            Intent(appContext, RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as RecognitionActivity
        try {
            val onFrame = RecognitionActivity::class.java.getDeclaredMethod("onFrame", FrameResult::class.java)
                .apply { isAccessible = true }
            val speaker = RecognitionActivity::class.java.getDeclaredField("speakSentence")
                .apply { isAccessible = true }
            val spoken = mutableListOf<String>()
            val before = ConversationPhraseAssist.recentShadowEvaluations().size
            instrumentation.runOnMainSync {
                speaker.set(activity, { text: String -> spoken.add(text); Unit })
                onFrame.invoke(activity, frame(1, "GO", "GO", 0.72f))
                onFrame.invoke(activity, frame(2, "THINK", "THINK", 0.35f,
                    alternative = SignScore("HOME", 0.33f), sentence = "GO THINK"))
                activity.findViewById<View>(R.id.hearButton).performClick()
                assertEquals(listOf("GO THINK"), spoken)
                assertEquals("GO THINK",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(before, ConversationPhraseAssist.recentShadowEvaluations().size)
                assertEquals("RECOGNIZED",
                    activity.findViewById<TextView>(R.id.recognizedLabel).text.toString())
                assertFalse(visibleTexts(activity.window.decorView).any { it.contains("Possible replies") })
                assertEquals(View.GONE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.GONE, activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
            }
            assertFalse(ConversationPhraseAssist.enabled)
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun newHearingTurnHidesOldAdvisoryWithoutClearingRawSentence() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER == "fake")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        val activity = instrumentation.startActivitySync(
            Intent(appContext, RecognitionActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as RecognitionActivity
        try {
            checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
                "Where are you going?", ConversationSource.TYPED_TEXT)).join()
            instrumentation.waitForIdleSync()
            val firstTurnId = ConversationPhraseAssist.presentationState.value.hearingTurnId
            val onFrame = RecognitionActivity::class.java.getDeclaredMethod("onFrame", FrameResult::class.java)
                .apply { isAccessible = true }
            instrumentation.runOnMainSync {
                onFrame.invoke(activity, frame(1, "GO", "GO", 0.72f))
                onFrame.invoke(activity, frame(2, "THINK", "THINK", 0.35f,
                    alternative = SignScore("HOME", 0.33f), sentence = "GO THINK"))
                assertEquals(View.VISIBLE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
            }
            checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
                "How are you?", ConversationSource.TYPED_TEXT)).join()
            instrumentation.waitForIdleSync()
            ConversationPhraseAssist.recognitionScreenStopped(firstTurnId)
            assertTrue(ConversationPhraseAssist.visibleRepliesForEvidence(emptyList()).contains("I'm good."))
            instrumentation.runOnMainSync {
                assertEquals("GO THINK",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                assertEquals(View.GONE, activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.GONE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                onFrame.invoke(activity, frame(3, "GOOD", "GOOD", 0.7f,
                    sentence = "GO THINK GOOD"))
                assertEquals(View.VISIBLE,
                    activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                assertEquals(View.GONE,
                    activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                assertEquals("GO THINK GOOD",
                    activity.findViewById<TextView>(R.id.sentenceText).text.toString())
            }
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun leavingRecognitionClosesReplyWindowWithoutChangingRawSentence() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER == "fake")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        val hearingActivity = instrumentation.startActivitySync(
            Intent(appContext, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as MainActivity
        try {
            // The Hearing turn exists before Reply opens Sign Detection, while another
            // app Activity keeps the session foregrounded during the transition.
            checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
                "Where are you going?", ConversationSource.TYPED_TEXT)).join()
            val activity = instrumentation.startActivitySync(
                Intent(appContext, RecognitionActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            ) as RecognitionActivity
            try {
                val onFrame = RecognitionActivity::class.java
                    .getDeclaredMethod("onFrame", FrameResult::class.java)
                    .apply { isAccessible = true }
                instrumentation.runOnMainSync {
                    onFrame.invoke(activity, frame(1, "GO", "GO", 0.72f))
                    assertEquals(View.VISIBLE,
                        activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                    instrumentation.callActivityOnStop(activity)
                    assertEquals(View.GONE,
                        activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                    assertEquals("GO",
                        activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                    assertTrue(ConversationPhraseAssist.visibleRepliesForEvidence(emptyList()).isEmpty())
                }
            } finally {
                instrumentation.runOnMainSync { activity.finish() }
                instrumentation.waitForIdleSync()
            }
        } finally {
            instrumentation.runOnMainSync { hearingActivity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun unsupportedTwoSignEvidenceKeepsConversationPredictionsVisible() = runBlocking {
        assumeTrue(ConversationPhraseAssist.enabled &&
            BuildConfig.CONTEXT_PHRASE_ASSIST_PROVIDER == "fake")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val appContext = instrumentation.targetContext
        val hearingActivity = instrumentation.startActivitySync(
            Intent(appContext, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        ) as MainActivity
        try {
            checkNotNull(ConversationPhraseAssist.recordHearingMessage(appContext,
                "Where are you going?", ConversationSource.TYPED_TEXT)).join()
            val activity = instrumentation.startActivitySync(
                Intent(appContext, RecognitionActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            ) as RecognitionActivity
            try {
                val onFrame = RecognitionActivity::class.java
                    .getDeclaredMethod("onFrame", FrameResult::class.java)
                    .apply { isAccessible = true }
                instrumentation.runOnMainSync {
                    onFrame.invoke(activity, frame(1, "GO", "GO", 0.72f))
                    onFrame.invoke(activity, frame(2, "GIFT", "GIFT", 0.91f,
                        sentence = "GO GIFT"))
                    assertEquals("GO GIFT",
                        activity.findViewById<TextView>(R.id.sentenceText).text.toString())
                    assertEquals(View.VISIBLE,
                        activity.findViewById<View>(R.id.possibleRepliesGroup).visibility)
                    assertEquals(3,
                        activity.findViewById<ViewGroup>(R.id.replyChipContainer).childCount)
                    assertEquals(View.GONE,
                        activity.findViewById<View>(R.id.contextSupportedGroup).visibility)
                }
            } finally {
                instrumentation.runOnMainSync { activity.finish() }
                instrumentation.waitForIdleSync()
            }
        } finally {
            instrumentation.runOnMainSync { hearingActivity.finish() }
            instrumentation.waitForIdleSync()
        }
    }

    @Test fun diagnosticExportPreservesEvidenceAndCannotWriteProductOrConversationState() {
        val scores = listOf(SignScore("THINK", 0.35f), SignScore("HOME", 0.33f),
            SignScore("KNOW", 0.12f), SignScore("GO", 0.08f), SignScore("WORK", 0.04f))
        val event = RecognitionEvidence(777, 9876L, "THINK", scores)
        val raw = SentenceBuilder().apply { add("GO"); add("THINK") }
        val candidates = listOf(ReplyCandidate("I'm going home.", listOf("GO", "HOME")))
        val hypothetical = AssistedInterpretation(listOf("GO", "THINK"), listOf("GO", "HOME"),
            "I'm going home.", listOf(776, 777), true, listOf(event))
        val evaluation = ShadowEvaluation(raw.text(), listOf(event), candidates,
            hypothetical, true, ShadowReason.MATCH)
        val turnsBefore = ConversationPhraseAssist.recentTurns()
        val historyBefore = ConversationPhraseAssist.recentShadowEvaluations()
        Stage3Diagnostics.cached(888, emptyList(), candidates)
        Stage3Diagnostics.committed(event)
        Stage3Diagnostics.evaluated(evaluation, false)
        // JSONObject rejects non-finite values. Diagnostics must fail open.
        Stage3Diagnostics.committed(event.copy(topK = listOf(SignScore("THINK", Float.NaN))))
        assertEquals("GO THINK", raw.text())
        assertEquals("GO THINK", evaluation.rawSentence)
        assertEquals(listOf("GO", "HOME"), evaluation.assistedCandidate?.assistedGlosses)
        assertEquals(scores, event.topK)
        assertEquals(turnsBefore, ConversationPhraseAssist.recentTurns())
        assertEquals(historyBefore, ConversationPhraseAssist.recentShadowEvaluations())
    }

    private fun frame(eventId: Int, original: String, primary: String, score: Float,
                      alternative: SignScore? = null, sentence: String = original): FrameResult {
        val topK = listOf(SignScore(primary, score)) + listOfNotNull(alternative)
        return FrameResult(
            hands = null, pose = null, imageWidth = 480, imageHeight = 360, fps = 5.0,
            isFrontCamera = true, qualityLabel = "TEST", poseEveryN = 1,
            recognition = RecognitionState.Committed(original, 0, topK.map { it.gloss }),
            phoneReady = true, phoneSentence = sentence,
            recognitionEvidence = RecognitionEvidence(eventId, eventId.toLong(), original, topK),
        )
    }

    private fun visibleTexts(view: View): List<String> {
        if (view.visibility != View.VISIBLE) return emptyList()
        return when (view) {
            is TextView -> listOf(view.text.toString())
            is ViewGroup -> (0 until view.childCount).flatMap { visibleTexts(view.getChildAt(it)) }
            else -> emptyList()
        }
    }
}
