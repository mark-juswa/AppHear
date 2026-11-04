package com.example.apphear.demo

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import androidx.core.view.isVisible
import com.example.apphear.R
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.conversation.flow2.FlowPhase
import com.example.apphear.conversation.flow2.FlowState
import com.example.apphear.databinding.ActivityRecognitionBinding
import kotlinx.coroutines.Job
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Plays a scripted conversation through the Recognition screen's existing conversation flow
 * (guidedDemo flag + Settings switch). The script supplies every signed message and every reply;
 * the recognizer's words are ignored and its inference is paused while a scenario runs, so a
 * prediction can never choose or change what is shown. The camera's "hands up" signal only paces
 * the signer's turns, and NEXT (primary pill, volume-down, clicker) always works.
 */
class GuidedDemoController(
    private val context: Context,
    private val binding: ActivityRecognitionBinding,
    private val flow: Flow,
) {
    /** What the demo asks of the conversation flow. */
    interface Flow {
        val state: FlowState
        /** The reply editor (keyboard) is open. */
        val typing: Boolean
        /** Shows [sentence] as the message for [words], as if sentence assist had built it. */
        fun showMessage(words: String, sentence: String)
        /** Says the message on screen now. */
        fun sayNow()
        fun listen()
        /** Delivers [text] as the hearing person's reply (ends listening if needed). */
        fun deliverReply(text: String)
        /** Stops speaking/listening/avatar and starts a fresh, empty conversation. */
        fun reset()
        /** Stops speaking/listening/avatar; the conversation so far stays. */
        fun stop()
        /** Removes the message on screen (not yet said). */
        fun clearMessage()
        /** Redraws the sheet (cue, labels). */
        fun redraw()
        /** Switches recognition to fingerspelling (true) or back to words. */
        fun setSpelling(on: Boolean)
    }

    private val settings = GuidedDemoSettings(context)
    private val handler = Handler(Looper.getMainLooper())
    private var run: DemoRun? = null
    private var values: Map<String, String> = emptyMap()
    private var cardOpen = false
    private var firstActivityMs = 0L
    private var lastActivityMs = 0L
    /** Signer turn: how many scripted signs are on screen, and the recognizer's word count they follow. */
    private var revealed = 0
    /** When the current step began; the first moments are ignored (hands still on the phone). */
    private var turnStartMs = 0L
    private var baselineWords = -1
    /** Scripted reply text -> the avatar wording for it (SIGN IT). */
    private val avatarFor = mutableMapOf<String, String>()
    private val card = binding.demoCard
    private val scope = MainScope()

    /** Question-based demo: the topic whose questions may be asked in any order (null for a sequential scenario). */
    private var topic: DemoTopic? = null
    private var answered = 0
    /** Shown in the sheet while it matters: "not in this conversation", "matching...". */
    var notice: String? = null
        private set
    private var matching: Job? = null
    /** Signer turn of a spelled answer: the fingerspelling model's latest reading. */
    private var spelled = ""

    /** A scenario is running (or just finished): real recognition output is ignored. */
    val active: Boolean get() = run != null

    init {
        binding.btnGuidedDemo.setOnClickListener {
            cardOpen = !cardOpen
            renderCard()
        }
    }

    // ---- what the conversation flow asks ----

    /** It is the signer's turn and their message is not on screen yet. (No cue is shown: it would give the answer away.) */
    private val signerWaiting: Boolean
        get() {
            val current = run ?: return false
            return current.step?.speaker == DemoSpeaker.SIGNER && !current.shown &&
                flow.state.phase in setOf(FlowPhase.READY, FlowPhase.REPLY)
        }

    /** The primary pill says the scripted message (one tap shows and says it) during the signer's turn. */
    val primaryShowsSayIt: Boolean get() = signerWaiting && flow.state.phase == FlowPhase.READY

    /** The scripted line for the current hearing step, replacing whatever speech recognition heard. */
    fun scriptedReply(): String? {
        val step = run?.step?.takeIf { it.speaker == DemoSpeaker.HEARING && !it.open } ?: return null
        val text = DemoValues.fill(step.text, values)
        step.avatar?.let { avatarFor[text] = DemoValues.fill(it, values) }
        return text
    }

    /** SIGN IT for a scripted reply uses its avatar wording when the script gives one. */
    fun avatarText(reply: String?): String? = reply?.let { avatarFor[it] ?: it }

    /**
     * The hearing person's turn ended with [heard] on screen. Sequential scenario: the scripted line is
     * done. Question-based topic: [heard] decides which answer the signer gives.
     */
    fun replyDelivered(heard: String = "") {
        val current = run ?: return
        val step = current.step ?: return
        if (step.speaker != DemoSpeaker.HEARING) return
        if (step.open) answer(heard) else moveOn(current.advance())
    }

    /** Question-based: finds the asked question (on the phone first, the AI helper only when unsure). */
    private fun answer(heard: String) {
        val bank = topic ?: return
        matching?.cancel()
        when (val match = DemoQuestionMatcher.match(heard, bank)) {
            is QuestionMatch.Confident -> useAnswer(match.question, "phone")
            is QuestionMatch.Unsure -> if (GeminiQuestionPicker.available && heard.isNotBlank()) {
                notice = context.getString(R.string.guided_demo_matching)
                renderAll()
                val asked = run
                matching = scope.launch {
                    val id = GeminiQuestionPicker.pick(heard, bank)
                    if (run !== asked) return@launch
                    val question = bank.questions.firstOrNull { it.id == id }
                    when {
                        question != null -> useAnswer(question, "ai")
                        id == "none" -> notInConversation()
                        match.best != null -> useAnswer(match.best, "phone_fallback") // helper unavailable
                        else -> notInConversation()
                    }
                }
            } else match.best?.let { useAnswer(it, "phone_unsure") } ?: notInConversation()
        }
    }

    private fun useAnswer(question: DemoQuestion, by: String) {
        val current = run ?: return
        notice = null
        answered++
        ConversationTimeline.mark("demo_question", "id" to question.id, "by" to by)
        val step = DemoStep(DemoSpeaker.SIGNER, question.answer, question.gloss, spell = question.spell)
        run = current.copy(scenario = current.scenario.copy(steps = current.scenario.steps + step)).advance()
        resetPacing()
        if (question.spell != null) flow.setSpelling(true)
        renderAll()
    }

    private fun notInConversation() {
        val current = run ?: return
        notice = context.getString(R.string.guided_demo_not_in_conversation)
        ConversationTimeline.mark("demo_question", "id" to "none")
        renderAll()
        handler.postDelayed({
            if (run === current && flow.state.phase in setOf(FlowPhase.REPLY, FlowPhase.NOT_HEARD) && !flow.typing) {
                notice = null
                flow.listen()
            }
        }, NOT_IN_CONVERSATION_MS)
    }

    /** Question-based: after an answer, the next question may be any of them again. */
    private fun withNextQuestion(current: DemoRun): DemoRun =
        current.copy(scenario = current.scenario.copy(steps = current.scenario.steps + OPEN_QUESTION))

    /** Primary pill pressed while [primaryShowsSayIt]: show the scripted message and say it at once. */
    fun sayScripted() {
        showSignerMessage("say_it")
        flow.sayNow()
    }

    fun onFlowChanged(old: FlowState, new: FlowState) {
        val current = run ?: return
        // Nothing heard during a hearing turn: listen again, so the demo never needs a tap.
        if (new.phase == FlowPhase.NOT_HEARD && old.phase != FlowPhase.NOT_HEARD &&
            current.step?.speaker == DemoSpeaker.HEARING) {
            handler.postDelayed({
                if (run === current && flow.state.phase == FlowPhase.NOT_HEARD && !flow.typing) flow.listen()
            }, 600)
        }
        // The signer's scripted message was said: their step is done.
        if (old.phase == FlowPhase.SAYING && new.phase == FlowPhase.LISTENING &&
            current.step?.speaker == DemoSpeaker.SIGNER && current.shown) {
            if (current.step?.spell != null) flow.setSpelling(false)
            val next = (if (topic != null) withNextQuestion(current) else current).advance()
            run = next
            resetPacing()
            // Listening only belongs to a hearing step; otherwise stop it again.
            if (next.step?.speaker != DemoSpeaker.HEARING) handler.post { flow.stop(); renderAll() }
            if (next.finished) cardOpen = true
            renderAll()
        }
    }

    /**
     * The recognizer's sentence changed. Its words are never shown: each newly recognized sign only
     * reveals the next scripted sign (timing), so the screen follows the signer sign by sign.
     * Returns true when the demo drew the live area.
     */
    fun recognizerUpdate(words: String, signing: Boolean): Boolean {
        val current = run ?: return false
        val step = current.step
        val count = if (words.isBlank()) 0 else words.trim().split(Regex("\\s+")).size
        val signerTurn = step?.speaker == DemoSpeaker.SIGNER &&
            flow.state.phase in setOf(FlowPhase.READY, FlowPhase.REPLY)
        if (!signerTurn) {
            baselineWords = count
            binding.glossText.setText(R.string.gloss_placeholder)
            binding.altText.visibility = View.GONE
            return true
        }
        val signs = scriptedSigns(step!!)
        // Words finished during the first moments of the turn belong to whatever came before it.
        if (baselineWords < 0 || count < baselineWords || inGrace()) baselineWords = count
        if (count > baselineWords) {
            revealed = (revealed + count - baselineWords).coerceAtMost(signs.size)
            baselineWords = count
            markActivity()
        }
        // "...signing..." on screen means the signer has not finished: keep waiting.
        if (signing) markActivity()
        binding.altText.visibility = View.GONE
        binding.glossText.text = when {
            signing -> context.getString(R.string.signing)
            revealed > 0 -> signs[revealed - 1]
            else -> context.getString(R.string.gloss_placeholder)
        }
        return true
    }

    private fun scriptedSigns(step: DemoStep): List<String> =
        DemoValues.cue(step.gloss ?: step.text, values).split(Regex("\\s+")).filter { it.isNotBlank() }

    /**
     * Fingerspelling reading changed. Used only during a spelled answer; its letters become the name or
     * place in the answer when the signer finishes.
     */
    fun spellingUpdate(reading: String) {
        val current = run ?: return
        val step = current.step ?: return
        if (step.speaker != DemoSpeaker.SIGNER || step.spell == null || current.shown || inGrace()) return
        if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return
        val clean = reading.trim()
        if (clean.isEmpty() || clean == spelled) return
        spelled = clean
        markActivity()
    }

    /** Camera thread posts: a hand is up. Paces the signer's turn only; the content is the script's. */
    fun signingActivity() {
        val current = run ?: return
        if (settings.presenterOnly || current.shown || current.step?.speaker != DemoSpeaker.SIGNER) return
        if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return
        markActivity()
    }

    private fun markActivity() {
        if (settings.presenterOnly || inGrace()) return
        val now = System.currentTimeMillis()
        if (firstActivityMs == 0L || now - lastActivityMs > RESTART_GAP_MS) firstActivityMs = now
        lastActivityMs = now
        handler.removeCallbacks(handsDownCheck)
        handler.postDelayed(handsDownCheck, HANDS_DOWN_MS)
    }

    private val handsDownCheck = Runnable {
        val current = run ?: return@Runnable
        if (current.shown || current.step?.speaker != DemoSpeaker.SIGNER) return@Runnable
        // Hands down after the recognizer noticed real signing: the full scripted sentence appears.
        // Hands near the camera alone (holding or typing on the phone) never count.
        if (revealed > 0 || spelled.isNotEmpty()) showSignerMessage("signed")
    }

    /** NEXT: whatever completes the current step. */
    fun next() {
        val current = run ?: return
        val step = current.step ?: return
        when (step.speaker) {
            DemoSpeaker.SIGNER -> when {
                !current.shown -> showSignerMessage("next")
                flow.state.phase == FlowPhase.READY -> flow.sayNow()
            }
            DemoSpeaker.HEARING -> if (!step.open && flow.state.phase != FlowPhase.SAYING) {
                scriptedReply()?.let(flow::deliverReply)
            }
        }
    }

    /** AGAIN: repeat the current step. */
    fun again() {
        val current = run ?: return
        if (current.finished) return
        flow.stop()
        if (current.step?.speaker == DemoSpeaker.SIGNER && current.shown) flow.clearMessage()
        run = current.again()
        resetPacing()
        notice = null
        if (current.step?.speaker == DemoSpeaker.HEARING) flow.listen()
        renderAll()
    }

    /** Volume-down / Page Down / right = NEXT; volume-up / Page Up / left = AGAIN. Only while a scenario runs. */
    fun onKey(event: KeyEvent): Boolean {
        val current = run ?: return false
        if (current.finished || flow.typing) return false // never take keys from the keyboard
        val action: (() -> Unit)? = when (event.keyCode) {
            KeyEvent.KEYCODE_VOLUME_DOWN, KeyEvent.KEYCODE_PAGE_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT -> ::next
            KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.KEYCODE_PAGE_UP, KeyEvent.KEYCODE_DPAD_LEFT -> ::again
            else -> null
        }
        if (action == null) return false
        if (event.action == KeyEvent.ACTION_UP) action()
        return true // consume the down event too, so the volume does not change
    }

    /** Screen became visible: the Settings switch may have changed. */
    fun onStart() {
        binding.btnGuidedDemo.isVisible = settings.enabled || active
        values = settings.values
        renderAll()
    }

    fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        scope.cancel()
    }

    // ---- running a scenario ----

    private fun start(scenario: DemoScenario) {
        clearRun()
        values = settings.values
        avatarFor.clear()
        flow.reset()
        run = DemoRun(scenario)
        cardOpen = false
        resetPacing()
        if (scenario.steps.firstOrNull()?.speaker == DemoSpeaker.HEARING) flow.listen()
        renderAll()
    }

    /** Question-based topic: open-ended; each answer is followed by another open question. */
    private fun start(bank: DemoTopic) {
        start(DemoScenario(bank.id, bank.title, "topic", listOf(OPEN_QUESTION)))
        topic = bank
    }

    /** Forgets the current run's matching, spelling mode and notices. */
    private fun clearRun() {
        matching?.cancel()
        if (run?.step?.spell != null) flow.setSpelling(false)
        topic = null
        answered = 0
        notice = null
    }

    private fun chooseAnother() {
        clearRun()
        run = null
        flow.reset()
        renderAll()
    }

    private fun stopDemo() {
        clearRun()
        run = null
        cardOpen = false
        handler.removeCallbacks(handsDownCheck)
        flow.reset()
        binding.btnGuidedDemo.isVisible = settings.enabled
        renderAll()
    }

    private fun showSignerMessage(reason: String) {
        val current = run ?: return
        val step = current.step?.takeIf { it.speaker == DemoSpeaker.SIGNER && !current.shown } ?: return
        handler.removeCallbacks(handsDownCheck)
        ConversationTimeline.mark("demo_message", "reason" to reason, "signs_seen" to revealed,
            "turn_ms" to (System.currentTimeMillis() - turnStartMs))
        run = current.showing()
        // A spelled answer uses what the fingerspelling model read; if it read nothing, the detail from Script details.
        val reading = DemoQuestionMatcher.spelledWords(spelled)
        val spelledValue = reading.ifEmpty { step.spell?.let { values[it]?.trim() }.orEmpty() }
            .ifEmpty { step.spell?.let { "[$it]" }.orEmpty() }
        val sentence = DemoValues.fill(step.text, values + ("spelled" to spelledValue))
        // The "words" key is the cue text: never shown in demo mode, only used to tie sentence to message.
        flow.showMessage(DemoValues.cue(step.gloss ?: step.text, values), sentence)
        renderAll()
    }

    private fun moveOn(next: DemoRun) {
        run = next
        resetPacing()
        if (next.finished) cardOpen = true
        // Two hearing lines in a row: keep listening for the second.
        if (next.step?.speaker == DemoSpeaker.HEARING) handler.postDelayed({ if (run === next) flow.listen() }, 400)
        renderAll()
    }

    private fun inGrace() = System.currentTimeMillis() - turnStartMs < TURN_GRACE_MS

    private fun resetPacing() {
        turnStartMs = System.currentTimeMillis()
        firstActivityMs = 0L
        lastActivityMs = 0L
        revealed = 0
        baselineWords = -1
        spelled = ""
        handler.removeCallbacks(handsDownCheck)
    }

    // ---- drawing ----

    private fun renderAll() {
        renderChips()
        renderCard()
        flow.redraw()
    }

    /** The suggestion row stays hidden: showing the scripted answer early would give it away. */
    private fun renderChips() {
        if (active) binding.possibleRepliesGroup.visibility = View.GONE
    }

    private fun renderCard() {
        card.root.isVisible = cardOpen
        if (!cardOpen) return
        val current = run
        val bank = topic
        val list = card.demoScenarioList
        list.removeAllViews()
        val details = { list.addView(pill(context.getString(R.string.guided_demo_edit_details)) {
            GuidedDemoDetailsDialog.show(context) { values = settings.values }
        }) }
        when {
            current == null -> {
                card.demoOverline.setText(R.string.guided_demo_pick_overline)
                card.demoTitle.setText(R.string.guided_demo_pick_title)
                card.demoBody.setText(R.string.guided_demo_pick_body)
                settings.topics().forEach { t -> list.addView(pill(t.title) { start(t) }) }
                settings.scenarios().forEach { scenario -> list.addView(pill(scenario.title) { start(scenario) }) }
                details()
                list.addView(pill(context.getString(R.string.guided_demo_close)) { cardOpen = false; renderCard() })
            }
            bank != null -> {
                card.demoOverline.text = context.getString(R.string.guided_demo_topic_overline, answered)
                card.demoTitle.text = bank.title
                card.demoBody.text = context.getString(R.string.guided_demo_topic_body,
                    bank.questions.joinToString("\n") { "\u2022 " + it.phrasings.first() })
                details()
                list.addView(pill(context.getString(R.string.guided_demo_restart)) { start(bank) })
                list.addView(pill(context.getString(R.string.guided_demo_another)) { chooseAnother() })
                list.addView(pill(context.getString(R.string.guided_demo_stop)) { stopDemo() })
                list.addView(pill(context.getString(R.string.guided_demo_close)) { cardOpen = false; renderCard() })
            }
            current.finished -> {
                card.demoOverline.setText(R.string.guided_demo_done_overline)
                card.demoTitle.text = current.scenario.title
                card.demoBody.setText(R.string.guided_demo_done_body)
                list.addView(pill(context.getString(R.string.guided_demo_restart)) { start(current.scenario) })
                list.addView(pill(context.getString(R.string.guided_demo_another)) { chooseAnother() })
                list.addView(pill(context.getString(R.string.guided_demo_stop)) { stopDemo() })
            }
            else -> {
                val (at, of) = current.progress
                card.demoOverline.text = context.getString(R.string.guided_demo_running_overline, at, of)
                card.demoTitle.text = current.scenario.title
                card.demoBody.setText(R.string.guided_demo_running_body)
                list.addView(pill(context.getString(R.string.guided_demo_next)) { next() })
                list.addView(pill(context.getString(R.string.guided_demo_again)) { again() })
                list.addView(pill(context.getString(R.string.guided_demo_restart)) { start(current.scenario) })
                list.addView(pill(context.getString(R.string.guided_demo_another)) { chooseAnother() })
                list.addView(pill(context.getString(R.string.guided_demo_stop)) { stopDemo() })
                list.addView(pill(context.getString(R.string.guided_demo_close)) { cardOpen = false; renderCard() })
            }
        }
    }

    private fun pill(label: String, onTap: () -> Unit): View {
        val view = LayoutInflater.from(context).inflate(R.layout.item_guided_demo_pill, card.demoScenarioList, false) as FrameLayout
        view.findViewById<TextView>(R.id.demoPillLabel).text = label
        view.contentDescription = label
        view.setOnClickListener { onTap() }
        return view
    }


    private companion object {
        /** Hands down this long after signing = the signer finished; only then does MESSAGE show the sentence. */
        const val HANDS_DOWN_MS = 2_000L
        /** After a turn starts, hands and words are ignored this long (closing the keyboard, putting the phone down). */
        const val TURN_GRACE_MS = 1_500L
        /** How long "not in this conversation" shows before listening again. */
        const val NOT_IN_CONVERSATION_MS = 2_500L
        /** Question-based: the hearing person may ask any of the topic's questions. */
        val OPEN_QUESTION = DemoStep(DemoSpeaker.HEARING, "", open = true)
        /** A pause longer than this starts a new burst. */
        const val RESTART_GAP_MS = 2_500L
    }
}
