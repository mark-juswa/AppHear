package com.example.apphear.demo

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.view.isVisible
import com.example.apphear.R
import com.example.apphear.conversation.flow2.FlowPhase
import com.example.apphear.conversation.flow2.FlowState
import com.example.apphear.databinding.ActivityRecognitionBinding

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
    private var baselineWords = -1
    /** Scripted reply text -> the avatar wording for it (SIGN IT). */
    private val avatarFor = mutableMapOf<String, String>()
    private val card = binding.demoCard

    /** A scenario is running (or just finished): real recognition output is ignored. */
    val active: Boolean get() = run != null

    init {
        binding.btnGuidedDemo.setOnClickListener {
            cardOpen = !cardOpen
            renderCard()
        }
    }

    // ---- what the conversation flow asks ----

    /** The signer's cue for the sheet, while it is their turn and the message is not on screen yet. */
    val cue: String?
        get() {
            val current = run ?: return null
            val step = current.step ?: return null
            if (step.speaker != DemoSpeaker.SIGNER || current.shown) return null
            if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return null
            return context.getString(R.string.guided_demo_cue, DemoValues.cue(step.gloss ?: step.text, values))
        }

    /** The primary pill says the scripted message (one tap shows and says it) during the signer's cue. */
    val primaryShowsSayIt: Boolean get() = cue != null && flow.state.phase == FlowPhase.READY

    /** The scripted line for the current hearing step, replacing whatever speech recognition heard. */
    fun scriptedReply(): String? {
        val step = run?.step?.takeIf { it.speaker == DemoSpeaker.HEARING } ?: return null
        val text = DemoValues.fill(step.text, values)
        step.avatar?.let { avatarFor[text] = DemoValues.fill(it, values) }
        return text
    }

    /** SIGN IT for a scripted reply uses its avatar wording when the script gives one. */
    fun avatarText(reply: String?): String? = reply?.let { avatarFor[it] ?: it }

    /** The scripted reply is on screen: the hearing step is done. */
    fun replyDelivered() {
        val current = run ?: return
        if (current.step?.speaker != DemoSpeaker.HEARING) return
        moveOn(current.advance())
    }

    /** Primary pill pressed while [primaryShowsSayIt]: show the scripted message and say it at once. */
    fun sayScripted() {
        showSignerMessage()
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
            val next = current.advance()
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
        if (baselineWords < 0 || count < baselineWords) baselineWords = count
        if (count > baselineWords) {
            revealed = (revealed + count - baselineWords).coerceAtMost(signs.size)
            baselineWords = count
            markActivity()
        }
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

    /** Camera thread posts: a hand is up. Paces the signer's turn only; the content is the script's. */
    fun signingActivity() {
        val current = run ?: return
        if (settings.presenterOnly || current.shown || current.step?.speaker != DemoSpeaker.SIGNER) return
        if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return
        markActivity()
    }

    private fun markActivity() {
        if (settings.presenterOnly) return
        val now = System.currentTimeMillis()
        if (firstActivityMs == 0L || now - lastActivityMs > RESTART_GAP_MS) firstActivityMs = now
        lastActivityMs = now
        handler.removeCallbacks(handsDownCheck)
        handler.postDelayed(handsDownCheck, HANDS_DOWN_MS)
    }

    private val handsDownCheck = Runnable {
        val current = run ?: return@Runnable
        if (current.shown || current.step?.speaker != DemoSpeaker.SIGNER) return@Runnable
        // Hands down after signing: the rest of the scripted signs and the full sentence appear.
        if (revealed > 0 || lastActivityMs - firstActivityMs >= MIN_SIGNING_MS) showSignerMessage()
    }

    /** NEXT: whatever completes the current step. */
    fun next() {
        val current = run ?: return
        val step = current.step ?: return
        when (step.speaker) {
            DemoSpeaker.SIGNER -> when {
                !current.shown -> showSignerMessage()
                flow.state.phase == FlowPhase.READY -> flow.sayNow()
            }
            DemoSpeaker.HEARING -> if (flow.state.phase != FlowPhase.SAYING) {
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
    }

    // ---- running a scenario ----

    private fun start(scenario: DemoScenario) {
        values = settings.values
        avatarFor.clear()
        flow.reset()
        run = DemoRun(scenario)
        cardOpen = false
        resetPacing()
        if (scenario.steps.firstOrNull()?.speaker == DemoSpeaker.HEARING) flow.listen()
        renderAll()
    }

    private fun stopDemo() {
        run = null
        cardOpen = false
        handler.removeCallbacks(handsDownCheck)
        flow.reset()
        binding.btnGuidedDemo.isVisible = settings.enabled
        renderAll()
    }

    private fun showSignerMessage() {
        val current = run ?: return
        val step = current.step?.takeIf { it.speaker == DemoSpeaker.SIGNER && !current.shown } ?: return
        handler.removeCallbacks(handsDownCheck)
        run = current.showing()
        val sentence = DemoValues.fill(step.text, values)
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

    private fun resetPacing() {
        firstActivityMs = 0L
        lastActivityMs = 0L
        revealed = 0
        baselineWords = -1
        handler.removeCallbacks(handsDownCheck)
    }

    // ---- drawing ----

    private fun renderAll() {
        renderChips()
        renderCard()
        flow.redraw()
    }

    /** The AI Helper's suggestion row shows the scripted answer for the signer's turn (deterministic). */
    private fun renderChips() {
        val sentence = run?.takeIf { !it.shown }?.step?.takeIf { it.speaker == DemoSpeaker.SIGNER }?.text
            ?.let { DemoValues.fill(it, values) }
        if (sentence == null || flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) {
            if (active) binding.possibleRepliesGroup.visibility = View.GONE
            return
        }
        val container = binding.replyChipContainer
        container.removeAllViews()
        container.addView(TextView(context).apply {
            text = sentence
            setTextColor(context.getColor(R.color.white))
            textSize = 15f
            typeface = context.resources.getFont(R.font.inter_semibold)
            gravity = android.view.Gravity.CENTER
            minHeight = dp(40)
            setPadding(dp(6), dp(3), dp(6), dp(3))
            setOnClickListener { showSignerMessage() }
        }, LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        binding.possibleRepliesGroup.visibility = View.VISIBLE
    }

    private fun renderCard() {
        card.root.isVisible = cardOpen
        if (!cardOpen) return
        val current = run
        val list = card.demoScenarioList
        list.removeAllViews()
        when {
            current == null -> {
                card.demoOverline.setText(R.string.guided_demo_pick_overline)
                card.demoTitle.setText(R.string.guided_demo_pick_title)
                card.demoBody.setText(R.string.guided_demo_pick_body)
                settings.scenarios().forEach { scenario -> list.addView(pill(scenario.title) { start(scenario) }) }
                list.addView(pill(context.getString(R.string.guided_demo_close)) { cardOpen = false; renderCard() })
            }
            current.finished -> {
                card.demoOverline.setText(R.string.guided_demo_done_overline)
                card.demoTitle.text = current.scenario.title
                card.demoBody.setText(R.string.guided_demo_done_body)
                list.addView(pill(context.getString(R.string.guided_demo_restart)) { start(current.scenario) })
                list.addView(pill(context.getString(R.string.guided_demo_another)) { run = null; flow.reset(); renderCard() })
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
                list.addView(pill(context.getString(R.string.guided_demo_another)) { run = null; flow.reset(); renderCard() })
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

    private fun dp(value: Int) = (value * context.resources.displayMetrics.density).toInt()

    private companion object {
        /** Hands down this long after signing = the signer finished; only then does MESSAGE show the sentence. */
        const val HANDS_DOWN_MS = 1_500L
        /** Shorter bursts (a hand passing the camera) do not count as signing. */
        const val MIN_SIGNING_MS = 600L
        /** A pause longer than this starts a new burst. */
        const val RESTART_GAP_MS = 2_500L
    }
}
