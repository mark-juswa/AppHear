package com.example.apphear.conversation.flow2

import android.text.Spanned
import android.text.style.ClickableSpan
import android.view.ContextThemeWrapper
import android.view.LayoutInflater
import android.view.View
import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.R
import com.example.apphear.databinding.ActivityRecognitionBinding
import org.junit.Assert.*
import org.junit.Test

/** Rendering/interaction smoke only: no camera, service request, TTS or accuracy claim. */
class SentenceBuilderConversationUiInstrumentedTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()

    @Test fun sentenceAndSignedWordLinksFollowTheExactSpeechChoice() {
        instrumentation.runOnMainSync {
            val context = ContextThemeWrapper(instrumentation.targetContext, R.style.Theme_AppHear)
            val binding = ActivityRecognitionBinding.inflate(LayoutInflater.from(context))
            val tapped = mutableListOf<Pair<Int, String>>()
            val binder = ConversationSheetBinder(binding, {}, { index, word -> tapped += index to word })
            val raw = ConversationFlow.signedWordsChanged(FlowState(), "ME WANT WATER").state
            val pending = ConversationFlow.suggestionReady(raw, "ME WANT WATER", null,
                plain = "Me want water.", building = true).state
            binder.render(pending, false)
            assertEquals("Me want water.", binding.sentenceText.text.toString())
            assertTrue(binding.conversationSignedLine.text.contains(context.getString(R.string.sentence_assist_improving)))
            assertEquals(View.GONE, binding.conversationSuggestion.visibility)
            val spans = binding.conversationSignedLine.text as Spanned
            val links = spans.getSpans(0, spans.length, ClickableSpan::class.java)
            assertEquals(3, links.size)
            links[1].onClick(binding.conversationSignedLine)
            assertEquals(listOf(1 to "WANT"), tapped)

            val built = ConversationFlow.suggestionReady(pending, "ME WANT WATER", "I want water.",
                plain = "Me want water.").state
            binder.render(built, false)
            assertEquals("I want water.", binding.sentenceText.text.toString())
            assertFalse(binding.conversationSignedLine.text.contains(context.getString(R.string.sentence_assist_improving)))
            assertEquals(context.getString(R.string.conversation_v2_use_signed), binding.conversationSuggestion.text.toString())
            val signed = ConversationFlow.chooseSuggestion(built, false).state
            binder.render(signed, false)
            assertEquals("Me want water.", binding.sentenceText.text.toString())
            assertEquals(context.getString(R.string.conversation_v2_use_sentence), binding.conversationSuggestion.text.toString())

            val saying = ConversationFlow.sayIt(signed).state
            val late = ConversationFlow.suggestionReady(saying, "ME WANT WATER", "I want water now.").state
            binder.render(late, false)
            assertEquals("Me want water.", binding.sentenceText.text.toString())
            assertFalse(binding.conversationSuggestion.isEnabled)
            val locked = binding.conversationSignedLine.text as Spanned
            assertTrue(locked.getSpans(0, locked.length, ClickableSpan::class.java).isEmpty())
        }
    }

    @Test fun spellingAndEmptyMessagesCannotLeaveWordRemovalLinksVisible() {
        instrumentation.runOnMainSync {
            val context = ContextThemeWrapper(instrumentation.targetContext, R.style.Theme_AppHear)
            val binding = ActivityRecognitionBinding.inflate(LayoutInflater.from(context))
            val binder = ConversationSheetBinder(binding, {}, { _, _ -> fail("Spelling must not expose removal") })
            val word = FlowState(message = SignedMessage("HELLO"))
            binder.render(word, false)
            assertEquals(View.VISIBLE, binding.conversationSignedLine.visibility)
            binding.sentenceText.text = "AMY"
            binder.render(FlowState(message = SignedMessage("AMY")), false, spelling = true)
            assertEquals("AMY", binding.sentenceText.text.toString())
            assertEquals(View.GONE, binding.conversationSignedLine.visibility)
            assertEquals(View.GONE, binding.conversationSuggestion.visibility)
            binder.render(FlowState(), false)
            assertEquals(View.GONE, binding.conversationSignedLine.visibility)
        }
    }
}
