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
        /** The signer began their answer: the reply moves to history and CURRENT SIGN shows. */
        fun signerStarted()
    }

    private val settings = GuidedDemoSettings(context)
    private val handler = Handler(Looper.getMainLooper())
    private var run: DemoRun? = null
    private var cardOpen = false
    /** Signer turn: the recognizer currently shows a sign in progress. */
    private var recognizerSigning = false
    /** Signer turn: camera frames in a row with the signer's hands down (at rest or out of view). */
    private var restFrames = 0
    /** Signer turn: frames with a hand or forearm raised (after the start-of-turn grace). */
    private var activeFrames = 0
    /** Signer turn: the signs the recognizer caught, in order (its own labels). */
    private val caught = mutableListOf<String>()
    /** Spelled answer: the listed name or place the letters picked (shown exactly as listed). */
    private var knownPick: String? = null
    /** The answer sentence on screen (after the signer finished), before the spelled part is filled. */
    private var shownSentence: String? = null
    /** The signs of the answer on screen (after the signer finished). */
    private var shownGloss: String? = null
    /** An answer is being chosen by the AI helper. */
    private var choosing = false
    /** The question last asked (for the AI helper's answer choice). */
    private var lastQuestion = ""
    /** Signer turn diagnostics: analysed frames, and how many had a raised hand / any hand / a raised forearm. */
    private val frameCounts = IntArray(4)
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

    /** STOP while listening means "they finished their scripted line" (sequential scripts only). */
    val stopEndsHearingTurn: Boolean
        get() = run?.step?.let { it.speaker == DemoSpeaker.HEARING && !it.open } == true

    /** The primary pill says the scripted message (one tap shows and says it) during the signer's turn. */
    val primaryShowsSayIt: Boolean get() = signerWaiting && flow.state.phase == FlowPhase.READY

    /** The scripted line for the current hearing step, replacing whatever speech recognition heard. */
    fun scriptedReply(): String? {
        val step = run?.step?.takeIf { it.speaker == DemoSpeaker.HEARING && !it.open } ?: return null
        val text = step.text
        step.avatar?.let { avatarFor[text] = it }
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
        lastQuestion = heard
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
        val step = DemoStep(DemoSpeaker.SIGNER, question.answer, question.gloss, spell = question.spell,
            answers = if (question.spell) emptyList() else question.answers, question = lastQuestion, known = question.known)
        run = current.copy(scenario = current.scenario.copy(steps = current.scenario.steps + step)).advance()
        resetPacing()
        enterSignerStep()
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
            val next = (if (topic != null) withNextQuestion(current) else current).advance()
            run = next
            resetPacing()
            enterSignerStep()
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
            // While the answer is being said, CURRENT SIGN keeps its words.
            val said = shownWords()
            if (said != null) binding.glossText.text = said
            else binding.glossText.setText(R.string.gloss_placeholder)
            binding.altText.visibility = View.GONE
            return true
        }
        val tokens = if (words.isBlank()) emptyList() else words.trim().split(Regex("\\s+"))
        // Words finished during the first moments of the turn belong to whatever came before it.
        if (baselineWords < 0 || count < baselineWords || inGrace()) baselineWords = count
        if (count > baselineWords) {
            caught += tokens.drop(baselineWords)
            revealed = caught.size
            baselineWords = count
            ConversationTimeline.mark("demo_sign_seen", "revealed" to revealed)
        }
        // "...signing..." means the signer has not finished; it never ends the turn on its own.
        recognizerSigning = signing && !inGrace()
        if (recognizerSigning || revealed > 0) startSignerTurn()
        checkFinished()
        binding.altText.visibility = View.GONE
        // CURRENT SIGN is the MESSAGE sentence word for word (never the recognizer's raw labels), revealed at
        // the pace of the signer's hands: the more signing (raised-arm frames, noticed signs) the more words.
        // Words the model's vocabulary lacks are supplied with the answer, so the whole sentence appears
        // by the time the signer finishes.
        val sentence = sentenceWords(shownSentence ?: step!!.text)
        val signs = scriptedSigns(step!!).size.coerceAtLeast(1)
        val byHands = activeFrames * sentence.size / (signs * FRAMES_PER_SIGN)
        val bySigns = caught.size * sentence.size / signs
        val visible = if (current.shown) sentence.size else maxOf(byHands, bySigns).coerceAtMost(sentence.size)
        binding.glossText.text = when {
            visible > 0 -> sentence.take(visible).joinToString(" ")
            signing || activeFrames > 0 -> context.getString(R.string.signing)
            else -> context.getString(R.string.gloss_placeholder)
        }
        return true
    }

    private fun scriptedSigns(step: DemoStep): List<String> = DemoGloss.signs(step.gloss ?: step.text)

    /** The answer's signs; a spelled part ("FS") shows the letters the fingerspelling model read. */
    private fun answerSigns(gloss: String): List<String> = DemoGloss.signs(gloss).map { sign ->
        if (sign == "FS" && (knownPick ?: spelled).isNotBlank()) (knownPick ?: spelled).filter { it.isLetterOrDigit() }.uppercase().toCharArray().joinToString("-")
        else sign
    }

    /** The sentence as CURRENT SIGN words: "I am taking IT." -> I AM TAKING IT; a spelled part is the name read. */
    private fun sentenceWords(text: String): List<String> {
        val reading = knownPick ?: DemoQuestionMatcher.spelledWords(spelled)
        return text.replace(DemoGloss.SPELLED, reading).split(Regex("\\s+"))
            .map { word -> word.trim { !it.isLetterOrDigit() }.uppercase() }.filter { it.isNotEmpty() }
    }

    /** After the signer finished: the whole MESSAGE sentence as CURRENT SIGN words, else null. */
    fun shownWords(): String? {
        val current = run ?: return null
        if (current.step?.speaker != DemoSpeaker.SIGNER || !current.shown) return null
        return shownSentence?.let { sentenceWords(it).joinToString(" ") }
    }

    /**
     * Fingerspelling reading changed. Used only during a spelled answer; its letters become the name or
     * place in the answer when the signer finishes.
     */
    fun spellingUpdate(reading: String) {
        val current = run ?: return
        val step = current.step ?: return
        if (step.speaker != DemoSpeaker.SIGNER || !step.spell || current.shown || inGrace()) return
        if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return
        val clean = reading.trim()
        if (clean.isEmpty() || clean == spelled) return
        spelled = clean
        ConversationTimeline.mark("demo_letters", "count" to clean.length)
        startSignerTurn()
        checkFinished()
    }

    /**
     * Each analysed camera frame: whether the signer's hands are up ([up]) and whether any hand is in view
     * ([seen]). The turn ends from what the camera sees, not a stopwatch: once real signing was noticed, the
     * sentence completes when the recognizer no longer shows a sign in progress and the hands have been at
     * rest for a few frames in a row. Signs: hands below the raised-hand line. Fingerspelling happens low
     * (chest height), so a spelled answer rests only when no hand is in view.
     */
    fun handsObserved(up: Boolean, seen: Boolean, armRaised: Boolean = false) {
        val current = run ?: return
        if (current.shown || current.step?.speaker != DemoSpeaker.SIGNER) return
        // Hands up: it is the signer's turn now, so CURRENT SIGN ("...signing...", letters) is on screen.
        if ((up || armRaised) && !inGrace()) startSignerTurn()
        // Still signing while any hand is detected or a forearm is raised (body pose: wrist above elbow).
        // Hand detection drops out during fast signs; the body pose does not, so a dropout is not a rest.
        val resting = !up && !seen && !armRaised
        // The first moments of the turn (putting the phone down) never count as rest.
        restFrames = if (resting && !inGrace()) restFrames + 1 else 0
        frameCounts[0]++
        if (up) frameCounts[1]++
        if (seen) frameCounts[2]++
        if (armRaised) frameCounts[3]++
        if ((up || armRaised) && !inGrace()) activeFrames++
        checkFinished()
    }

    /**
     * Of the speech recognizer's alternatives (most likely first), the one that best matches a question
     * in the running topic; the first when none matches better or no topic runs.
     */
    fun bestHeard(alternatives: List<String>): String {
        val bank = topic ?: return alternatives.first()
        fun score(text: String): Double {
            val asked = DemoQuestionMatcher.words(text)
            return bank.questions.maxOf { q -> q.phrasings.maxOf { DemoQuestionMatcher.score(asked, it) } }
        }
        val first = alternatives.first()
        val best = alternatives.maxByOrNull(::score) ?: first
        return if (score(best) > score(first)) best else first
    }

    private fun checkFinished() {
        val current = run ?: return
        val step = current.step ?: return
        if (settings.presenterOnly || current.shown || step.speaker != DemoSpeaker.SIGNER) return
        if (flow.state.phase !in setOf(FlowPhase.READY, FlowPhase.REPLY)) return
        if (recognizerSigning) return
        // A spelled answer: letters were read, then the hand left the view.
        if (spelled.isNotEmpty() && restFrames >= REST_FRAMES) return showSignerMessage("spelled")
        // A signed answer ends when the signer stops (no hand in view, arms down), however many signs the
        // recognizer caught: fast signing at the phone's frame rate catches only some. Real signing must
        // have happened: a caught sign, or arms raised for a while.
        if ((revealed > 0 || activeFrames >= MIN_ACTIVE_FRAMES) && restFrames >= REST_FRAMES) showSignerMessage("signed")
    }

    /** The first real sign of the answer: show the signer's turn (CURRENT SIGN) instead of the question. */
    private fun startSignerTurn() {
        if (flow.state.phase != FlowPhase.REPLY) return
        ConversationTimeline.mark("demo_signer_turn", "spell" to (run?.step?.spell == true))
        flow.signerStarted()
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
        renderAll()
    }

    fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        scope.cancel()
    }

    // ---- running a scenario ----

    private fun start(scenario: DemoScenario) {
        clearRun()
        avatarFor.clear()
        flow.reset()
        run = DemoRun(scenario)
        cardOpen = false
        resetPacing()
        enterSignerStep()
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
        if (run?.step?.spell == true) flow.setSpelling(false)
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
        flow.reset()
        binding.btnGuidedDemo.isVisible = settings.enabled
        renderAll()
    }

    private fun showSignerMessage(reason: String) {
        val current = run ?: return
        val step = current.step?.takeIf { it.speaker == DemoSpeaker.SIGNER && !current.shown } ?: return
        if (choosing) return
        if (step.answers.size > 1) return chooseAnswer(current, step, reason)
        if (step.spell && step.known.isNotEmpty()) return chooseSpelled(current, step, reason)
        display(current, step, reason, step.text, step.gloss ?: step.text, "only")
    }

    /**
     * Which listed answer the signer gave: the one the caught signs single out (phone), else the AI helper
     * (online) from the question and the caught signs, else the default answer. Never a new answer.
     */
    private fun chooseAnswer(current: DemoRun, step: DemoStep, reason: String) {
        val local = DemoAnswerChooser.choose(step.answers, caught)
        if (local != null || caught.isEmpty() || !GeminiQuestionPicker.available) {
            val answer = step.answers[local ?: 0]
            return display(current, step, reason, answer.text, answer.gloss, if (local != null) "phone" else "default")
        }
        choosing = true
        notice = context.getString(R.string.guided_demo_completing)
        renderAll()
        val signs = caught.toList()
        scope.launch {
            val picked = GeminiQuestionPicker.pickAnswer(step.question, signs, step.answers)
            choosing = false
            notice = null
            if (run !== current) return@launch
            val answer = step.answers[picked ?: 0]
            display(current, step, reason, answer.text, answer.gloss, if (picked != null) "ai" else "default")
        }
    }

    /**
     * A spelled answer with expected names or places: the letters read pick the listed one (phone); several
     * fits go to the AI helper (it may only pick a listed one); no fit shows the letters themselves.
     */
    private fun chooseSpelled(current: DemoRun, step: DemoStep, reason: String) {
        val fits = DemoSpelledChooser.matches(step.known, spelled)
        val gloss = step.gloss ?: step.text
        fun show(index: Int?, by: String) {
            knownPick = index?.let { step.known[it] }
            display(current, step, reason, step.text, gloss, by)
        }
        if (fits.size == 1) return show(fits[0], "phone")
        if (fits.isEmpty() || !GeminiQuestionPicker.available) return show(fits.firstOrNull(), if (fits.isEmpty()) "letters" else "first")
        choosing = true
        notice = context.getString(R.string.guided_demo_completing)
        renderAll()
        val options = fits.map { DemoAnswer(step.known[it], "FS:" + step.known[it]) }
        val read = "fingerspelled letters read: " + spelled.uppercase().filter { it.isLetterOrDigit() }.toCharArray().joinToString("-")
        scope.launch {
            val picked = GeminiQuestionPicker.pickAnswer(step.question, listOf(read), options)
            choosing = false
            notice = null
            if (run !== current) return@launch
            show(fits[picked ?: 0], if (picked != null) "ai" else "first")
        }
    }

    private fun display(current: DemoRun, step: DemoStep, reason: String, text: String, gloss: String, by: String) {
        shownGloss = gloss
        shownSentence = text
        binding.glossText.text = sentenceWords(text).joinToString(" ")
        ConversationTimeline.mark("demo_answer", "by" to by, "caught" to caught.size, "options" to step.answers.size)
        ConversationTimeline.mark("demo_message", "reason" to reason, "signs_seen" to revealed,
            "signs_expected" to scriptedSigns(step).size, "spelled" to spelled.length, "rest" to restFrames,
            "frames" to frameCounts[0], "up" to frameCounts[1], "seen" to frameCounts[2], "arm" to frameCounts[3],
            "turn_ms" to (System.currentTimeMillis() - turnStartMs))
        run = current.showing()
        // A spelled answer's name or place is exactly what the fingerspelling model read.
        val reading = knownPick ?: DemoQuestionMatcher.spelledWords(spelled).ifEmpty { "\u2026" }
        val sentence = text.replace(DemoGloss.SPELLED, reading)
        // The "words" key ties the sentence to the message; it is never shown in demo mode.
        flow.showMessage(gloss, sentence)
        renderAll()
    }

    private fun moveOn(next: DemoRun) {
        run = next
        resetPacing()
        enterSignerStep()
        if (next.finished) cardOpen = true
        // Two hearing lines in a row: keep listening for the second.
        if (next.step?.speaker == DemoSpeaker.HEARING) handler.postDelayed({ if (run === next) flow.listen() }, 400)
        renderAll()
    }

    /**
     * A signer step begins: fingerspelling for a name or place answer, words for every other answer
     * (so a mode left over from earlier never decides how the signer is read).
     */
    private fun enterSignerStep() {
        val step = run?.step?.takeIf { it.speaker == DemoSpeaker.SIGNER } ?: return
        flow.setSpelling(step.spell)
    }

    private fun inGrace() = System.currentTimeMillis() - turnStartMs < TURN_GRACE_MS

    private fun resetPacing() {
        turnStartMs = System.currentTimeMillis()
        recognizerSigning = false
        restFrames = 0
        activeFrames = 0
        caught.clear()
        shownGloss = null
        shownSentence = null
        knownPick = null
        frameCounts.fill(0)
        revealed = 0
        baselineWords = -1
        spelled = ""
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
        when {
            current == null -> {
                card.demoOverline.setText(R.string.guided_demo_pick_overline)
                card.demoTitle.setText(R.string.guided_demo_pick_title)
                card.demoBody.setText(R.string.guided_demo_pick_body)
                settings.topics().forEach { t -> list.addView(pill(t.title) { start(t) }) }
                settings.scenarios().forEach { scenario -> list.addView(pill(scenario.title) { start(scenario) }) }
                list.addView(pill(context.getString(R.string.guided_demo_close)) { cardOpen = false; renderCard() })
            }
            bank != null -> {
                card.demoOverline.text = context.getString(R.string.guided_demo_topic_overline, answered)
                card.demoTitle.text = bank.title
                card.demoBody.text = context.getString(R.string.guided_demo_topic_body,
                    bank.questions.joinToString("\n") { "\u2022 " + it.phrasings.first() })
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
        /** Analysed camera frames in a row with arms down and no hand in view that end the signer's answer. */
        const val REST_FRAMES = 5
        /** Frames with arms raised that count as real signing when the recognizer caught no sign. */
        const val MIN_ACTIVE_FRAMES = 6
        /** Analysed frames one sign takes (about a second at the phone's ~4 fps): paces CURRENT SIGN's words. */
        const val FRAMES_PER_SIGN = 4
        /** After a turn starts, hands and words are ignored this long (closing the keyboard, putting the phone down). */
        const val TURN_GRACE_MS = 1_500L
        /** How long "not in this conversation" shows before listening again. */
        const val NOT_IN_CONVERSATION_MS = 2_500L
        /** Question-based: the hearing person may ask any of the topic's questions. */
        val OPEN_QUESTION = DemoStep(DemoSpeaker.HEARING, "", open = true)
    }
}
