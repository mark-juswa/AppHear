package com.example.apphear.conversation.flow2

import android.Manifest
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognizerIntent
import android.util.Log
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.contextassist.ConversationPhraseAssist
import com.example.apphear.contextassist.ConversationSource
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.databinding.ActivityRecognitionBinding
import com.example.apphear.ui.speech.SpeechInputHelper

/**
 * conversationFlowV2 on the recognition screen: runs [ConversationFlow], owns in-app listening,
 * the microphone permission and the system-dialog fallback, and draws the sheet. Speech output,
 * clearing the signed words and avatar playback stay with the screen's existing owners ([Host]).
 * Create in onCreate (it registers activity-result launchers and saved state).
 */
class ConversationFlowController(
    private val activity: ComponentActivity,
    private val binding: ActivityRecognitionBinding,
    private val host: Host,
) : InAppSpeechListener.Callback {
    interface Host {
        /** Runs the existing Hear path, which ends in [sayText] with the final wording. */
        fun sayIt()
        fun speak(text: String, onDone: () -> Unit)
        fun stopSpeaking()
        fun clearSignedWords()
        /** A hearing turn was just recorded for Context Assist while this screen is open. */
        fun hearingRecorded()
        /**
         * True while the hearing person replies (listening or typing), the phone speaks the message or
         * the avatar signs: recognition skips frames so the signer's resting hands cannot commit a word.
         */
        fun detectionHold(held: Boolean)
    }

    private val main = Handler(Looper.getMainLooper())
    private val binder = ConversationSheetBinder(binding) { reply -> apply(ConversationFlow.signIt(state, reply)) }
    private val listener = InAppSpeechListener(AndroidSpeechBackend(activity)) { micPermitted() }
    private var state = FlowState()
    private var editorOpen = false
    private var lastWords: String? = null
    /** The current message came from fingerspelling, which keeps its confirm step (never auto-said). */
    private var messageIsSpelling = false
    /** Latest suggestion from sentence assist, kept so it survives arriving before its words do. */
    private var lastSuggestion: Pair<String, String?>? = null
    private var permissionTicket: Long? = null
    private var systemDialogTicket: Long? = null
    private var stopped = false
    private var avatarNote: String? = null
    private var autoSaySeconds: Int? = null
    private var detectionHeld = false
    /** conversationAutoSay: says the message after the signer stops; null when the flag is off. */
    private val autoSayPolicy: AutoSayPolicy? = if (!BuildConfig.CONVERSATION_AUTO_SAY_ENABLED) null else
        runCatching { AutoSayPolicy.load(activity) }
            .onFailure { Log.w(TAG, "[conversation/flow2] auto-say policy unavailable; SAY IT stays manual", it) }
            .getOrNull()
    private val autoSay: AutoSay? = autoSayPolicy?.let { policy ->
                AutoSay(policy, { delayMs, task -> main.postDelayed(task, delayMs) }, main::removeCallbacks,
                    onCountdown = { seconds ->
                        autoSaySeconds = seconds
                        draw()
                    },
                    onFire = ::autoSayNow,
                )
            }
    private val avatar = ReplyAvatarStage(activity, binding.conversationAvatarStage, object : ReplyAvatarStage.Listener {
        override fun note(ticket: Long, text: String) {
            if (ticket != state.ticket || state.phase != FlowPhase.AVATAR) return
            avatarNote = text
            render()
        }

        override fun finished(ticket: Long) = apply(ConversationFlow.avatarFinished(state, ticket))
    })

    private val permissionLauncher = activity.registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) {
        val ticket = permissionTicket ?: return@registerForActivityResult
        permissionTicket = null
        // Denied: the listener reports NO_PERMISSION and the flow falls back to the system dialog.
        if (ticket == state.ticket && state.phase == FlowPhase.LISTENING) listener.start(ticket, this)
    }

    private val systemDialog = activity.registerForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        val ticket = systemDialogTicket ?: return@registerForActivityResult
        systemDialogTicket = null
        val text = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
        apply(if (result.resultCode == Activity.RESULT_OK) ConversationFlow.replyHeard(state, ticket, text)
            else ConversationFlow.listenFailed(state, ticket, ListenFailure.NOT_HEARD))
    }

    private val back = object : OnBackPressedCallback(false) {
        override fun handleOnBackPressed() {
            if (editorOpen) closeEditor() else ConversationFlow.back(state)?.let(::apply)
        }
    }

    init {
        activity.onBackPressedDispatcher.addCallback(activity, back)
        activity.savedStateRegistry.consumeRestoredStateForKey(SAVED_KEY)?.let { state = ConversationFlow.restored(restore(it)) }
        activity.savedStateRegistry.registerSavedStateProvider(SAVED_KEY) { save(state) }
        binding.speakButton.setOnClickListener { onPrimary() }
        binding.conversationSecondaryA.setOnClickListener { onSecondary(binder.secondaryA) }
        binding.conversationSecondaryB.setOnClickListener { onSecondary(binder.secondaryB) }
        binding.conversationSuggestion.setOnClickListener {
            val use = state.message?.useSuggestion != true
            ConversationTimeline.mark("suggestion_choice", "use" to use)
            apply(ConversationFlow.chooseSuggestion(state, use))
        }
        binding.conversationTypeReplyExpanded.setOnClickListener { onSecondary(ConversationSheetBinder.Secondary.TYPE_REPLY) }
        binding.conversationEditor.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) { sendTyped(); true } else false
        }
        render()
    }

    /** Raw signed words as displayed (S8 sentence or [spelling]); called every frame, so cheap. */
    fun signedWordsChanged(words: String, spelling: Boolean = false) {
        if (spelling != messageIsSpelling) {
            messageIsSpelling = spelling
            render()
        }
        if (words == lastWords) return
        lastWords = words
        apply(ConversationFlow.signedWordsChanged(state, words))
        lastSuggestion?.takeIf { it.first == words }?.let { apply(ConversationFlow.suggestionReady(state, it.first, it.second)) }
    }

    /** An accepted sentence-assist rendering for [words], or null; called every frame, so cheap. */
    fun suggestionFor(words: String, suggestion: String?) {
        val next = words.trim() to suggestion
        if (next == lastSuggestion) return
        lastSuggestion = next
        apply(ConversationFlow.suggestionReady(state, next.first, suggestion))
    }

    /** What SAY IT should speak for [words]: the chosen wording, or null if [words] are not the message. */
    fun chosenFor(words: String): String? = state.message?.takeIf { it.signedWords == words.trim() }?.chosen

    /** Camera-height fraction above which a hand counts as raised for auto-say; null when auto-say is off. */
    val autoSayRaisedHandMaxY: Float? get() = autoSay?.let { autoSayPolicy?.raisedHandMaxY }

    /** The signer is mid-sign or has a hand raised: auto-say waits for them to stop again. */
    fun signingActivity() {
        autoSay?.activity()
    }

    /** Final wording from the existing Hear path. */
    fun sayText(text: String) {
        // Said now (by tap, Hear or auto-say): never say these words again automatically.
        autoSay?.hold()
        ConversationTimeline.mark("say_it", "chars" to text.length)
        apply(ConversationFlow.sayText(state, text))
    }

    fun onStop() {
        stopped = true
        autoSay?.cancel()
        // The permission prompt and the system speech dialog pause this screen; their results return here.
        if (permissionTicket != null || systemDialogTicket != null) return
        if (editorOpen) closeEditor()
        ConversationFlow.back(state)?.let(::apply)
    }

    fun onStart() {
        stopped = false
        render()
    }

    fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        listener.destroy()
        avatar.destroy()
    }

    private fun onPrimary() {
        if (editorOpen) { sendTyped(); return }
        when (ConversationFlow.primaryAction(state)) {
            PrimaryAction.SAY_IT -> host.sayIt()
            PrimaryAction.LISTEN -> apply(ConversationFlow.listen(state))
            PrimaryAction.STOP -> apply(ConversationFlow.stop(state))
            PrimaryAction.SIGN_IT -> apply(ConversationFlow.signIt(state))
            PrimaryAction.REPLAY -> apply(ConversationFlow.replay(state))
        }
    }

    private fun onSecondary(which: ConversationSheetBinder.Secondary?) {
        when (which) {
            ConversationSheetBinder.Secondary.LISTEN -> apply(ConversationFlow.listen(state))
            ConversationSheetBinder.Secondary.TYPE_REPLY, ConversationSheetBinder.Secondary.TYPE_INSTEAD -> openEditor()
            ConversationSheetBinder.Secondary.CANCEL -> closeEditor()
            ConversationSheetBinder.Secondary.CLOSE -> apply(ConversationFlow.stop(state))
            ConversationSheetBinder.Secondary.WAIT -> {
                ConversationTimeline.mark("auto_say_wait")
                autoSay?.hold()
                render()
            }
            null -> Unit
        }
    }

    private fun openEditor() {
        // Typing replaces listening; nothing keeps the microphone open behind the keyboard.
        if (state.phase == FlowPhase.LISTENING) apply(ConversationFlow.stop(state))
        editorOpen = true
        render()
        binding.conversationEditor.requestFocus()
        imm().showSoftInput(binding.conversationEditor, InputMethodManager.SHOW_IMPLICIT)
    }

    private fun closeEditor() {
        editorOpen = false
        imm().hideSoftInputFromWindow(binding.conversationEditor.windowToken, 0)
        binding.conversationEditor.text = null
        render()
    }

    private fun sendTyped() {
        val text = binding.conversationEditor.text?.toString().orEmpty()
        if (text.isBlank()) return
        closeEditor()
        apply(ConversationFlow.typedReply(state, text))
    }

    private fun apply(transition: Transition) {
        state = transition.state
        transition.effects.forEach(::run)
        render()
    }

    private fun run(effect: FlowEffect) {
        when (effect) {
            is FlowEffect.Speak -> host.speak(effect.text) {
                main.post { apply(ConversationFlow.sayingDone(state, effect.ticket)) }
            }
            FlowEffect.StopSpeaking -> host.stopSpeaking()
            is FlowEffect.StartListening -> startListening(effect.ticket)
            FlowEffect.StopListening -> {
                listener.cancel()
                systemDialogTicket = null
            }
            is FlowEffect.OpenSystemListening -> openSystemDialog(effect.ticket)
            is FlowEffect.RecordHearing -> {
                ConversationTimeline.mark("reply_ready", "source" to effect.source.name, "chars" to effect.text.length)
                ConversationPhraseAssist.recordHearingMessage(activity.applicationContext, effect.text,
                    if (effect.source == ReplySource.SPEECH) ConversationSource.SPEECH else ConversationSource.TYPED_TEXT)
                host.hearingRecorded()
            }
            FlowEffect.ClearSignedWords -> {
                lastWords = null
                host.clearSignedWords()
            }
            is FlowEffect.PlayAvatar -> {
                ConversationTimeline.mark("sign_it", "chars" to effect.text.length)
                avatarNote = null
                avatar.play(effect.text, effect.ticket)
            }
            FlowEffect.StopAvatar -> {
                avatarNote = null
                avatar.stop()
            }
        }
    }

    private fun startListening(ticket: Long) {
        ConversationTimeline.mark("listen_start")
        if (!micPermitted() && permissionTicket == null && !stopped) {
            permissionTicket = ticket
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        listener.start(ticket, this)
    }

    private fun openSystemDialog(ticket: Long) {
        ConversationTimeline.mark("listen_fallback")
        val launched = SpeechInputHelper.isAvailable(activity) && try {
            systemDialogTicket = ticket
            systemDialog.launch(SpeechInputHelper.createSpeechIntent(activity.getString(R.string.reply_speech_prompt)))
            true
        } catch (failure: ActivityNotFoundException) {
            Log.w(TAG, "[conversation/flow2] system speech dialog unavailable", failure)
            systemDialogTicket = null
            false
        }
        if (!launched) main.post { apply(ConversationFlow.listenFailed(state, ticket, ListenFailure.UNAVAILABLE)) }
    }

    // Listener callbacks arrive on the main thread, possibly inside start(); post to avoid re-entry.
    override fun partial(ticket: Long, text: String) {
        main.post { apply(ConversationFlow.partialReply(state, ticket, text)) }
    }

    override fun level(ticket: Long, rmsDb: Float) {
        if (ticket == state.ticket) binder.level(rmsDb)
    }

    override fun heard(ticket: Long, text: String) {
        main.post { apply(ConversationFlow.replyHeard(state, ticket, text)) }
    }

    override fun failed(ticket: Long, failure: ListenFailure) {
        ConversationTimeline.mark("listen_failed", "reason" to failure.name)
        main.post { apply(ConversationFlow.listenFailed(state, ticket, failure)) }
    }

    private fun render() {
        autoSay?.update(state.message?.signedWords, canSay = state.phase == FlowPhase.READY && !editorOpen &&
            !messageIsSpelling && !stopped)
        draw()
    }

    private fun draw() {
        val held = editorOpen || state.phase in setOf(FlowPhase.SAYING, FlowPhase.LISTENING, FlowPhase.AVATAR)
        if (held != detectionHeld) {
            detectionHeld = held
            ConversationTimeline.mark("detection_hold", "held" to held)
            host.detectionHold(held)
        }
        binder.render(state, editorOpen, avatarNote, autoSaySeconds, detectionHeld)
        back.isEnabled = editorOpen ||
            state.phase in setOf(FlowPhase.SAYING, FlowPhase.LISTENING, FlowPhase.AVATAR)
    }

    /** The auto-say countdown ran out: the same path as tapping SAY IT. */
    private fun autoSayNow() {
        if (state.phase != FlowPhase.READY || state.message == null || editorOpen || stopped) return
        ConversationTimeline.mark("auto_say")
        host.sayIt()
    }

    private fun micPermitted() = ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) ==
        PackageManager.PERMISSION_GRANTED

    private fun imm() = activity.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager

    private companion object {
        const val TAG = "ConversationFlowV2"
        const val SAVED_KEY = "conversationFlowV2"

        /** Only what a rebuilt screen shows: the latest reply, history and the ticket. */
        fun save(s: FlowState): Bundle = Bundle().apply {
            putString("reply", s.reply)
            putStringArray("signed", s.history.map { it.signed.orEmpty() }.toTypedArray())
            putStringArray("replies", s.history.map { it.reply.orEmpty() }.toTypedArray())
            putLong("ticket", s.ticket)
        }

        fun restore(b: Bundle): FlowState {
            val signed = b.getStringArray("signed").orEmpty()
            val replies = b.getStringArray("replies").orEmpty()
            val history = signed.indices.map { i ->
                Exchange(signed[i].ifEmpty { null }, replies.getOrNull(i)?.ifEmpty { null })
            }
            return FlowState(reply = b.getString("reply"), history = history, ticket = b.getLong("ticket"))
        }
    }
}
