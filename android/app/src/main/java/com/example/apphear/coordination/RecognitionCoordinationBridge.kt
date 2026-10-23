package com.example.apphear.coordination

import android.content.Context
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.constraintlayout.widget.ConstraintLayout
import com.example.apphear.R
import com.example.apphear.contextassist.ConversationPhraseAssist
import com.example.apphear.contextassist.PhraseAssistUiState
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.fingerspelling.FingerspellRuntime
import com.example.apphear.fingerspelling.RecognitionMode
import org.json.JSONObject

/** UI/lifecycle adapter around the pure policy and EXISTING exclusive recognition owner. */
internal class RecognitionCoordinationBridge(
    private val context: Context, parent: ConstraintLayout,
    private val runtime: () -> FingerspellRuntime?,
    private val dispatch: (() -> Unit) -> Unit,
    private val main: (() -> Unit) -> Unit,
    private val selected: (RecognitionMode) -> Unit,
    private val speak: (String) -> Unit,
    initial: RecognitionMode,
) {
    private val policy: RecognitionCoordinator
    @Volatile private var active = false
    @Volatile private var generation = 0
    private var lastContext: Pair<Long?,String>? = null // main-thread input cache only
    private val label = TextView(context).apply {
        id=R.id.coordinationStatus; textSize=12f; setTextColor(0xFFFFFFFF.toInt())
        gravity=Gravity.CENTER; setSingleLine(true)
        typeface=context.resources.getFont(R.font.inter_semibold)
    }
    init {
        val config = context.assets.open("recognition_coordination_policy.json").bufferedReader().use { JSONObject(it.readText()) }
        require(config.getString("schema_version")=="apphear.recognition.coordination.v2")
        require(config.getString("matching")=="WHOLE_QUESTION_WITH_FILLERS")
        require(config.getString("automatic_entry")=="IDLE_BEFORE_RESPONSE_WITHOUT_USABLE_HAND")
        require(config.getString("completion")=="EXPLICIT_CONFIRMATION")
        val rules=config.getJSONArray("rules")
        policy=RecognitionCoordinator((0 until rules.length()).map {
            val r=rules.getJSONObject(it); ContextModeRule(SpellingIntent.valueOf(r.getString("kind")),Regex(r.getString("pattern")))
        },initial,QuestionFillers(strings(config.getJSONArray("leading_fillers")),
            strings(config.getJSONArray("trailing_fillers"))))
        val density=context.resources.displayMetrics.density
        fun dp(n:Int)=(n*density).toInt()
        val panel=LinearLayout(context).apply {
            id=R.id.coordinationPanel; orientation=LinearLayout.VERTICAL
            gravity=Gravity.CENTER
            setPadding(dp(12),dp(6),dp(12),dp(6)); setBackgroundResource(R.drawable.bg_glass_pill)
            addView(label)

        }
        parent.addView(panel,ConstraintLayout.LayoutParams(ConstraintLayout.LayoutParams.WRAP_CONTENT,ConstraintLayout.LayoutParams.WRAP_CONTENT).apply {
            startToEnd=R.id.btnBack; endToStart=R.id.cameraToggle
            topToTop=R.id.btnBack; bottomToBottom=R.id.btnBack
            marginStart=dp(8); marginEnd=dp(8)
        })
        render()
    }

    fun started(preferred: RecognitionMode) {
        generation++; active=true; lastContext=null
        dispatch {
            if(!active) return@dispatch
            if(policy.state.mode!=preferred) policy.manual(preferred)
            render()
        }
        context(ConversationPhraseAssist.presentationState.value)
    }
    /** True when the current mode came from a hearing question, not from the user. */
    val automaticSwitch: Boolean get() = policy.state.automatic
    /** The question kind behind the current automatic switch (NAME, PLACE or SPELL). */
    val switchReason: String? get() = policy.state.hint?.name

    private fun strings(array: org.json.JSONArray) = (0 until array.length()).map { array.getString(it) }

    fun stopped() { generation++; active=false; lastContext=null; dispatch { policy.pause() } }
    fun context(state: PhraseAssistUiState) {
        if(!active) return
        val id=if(ConversationPhraseAssist.enabled) ConversationPhraseAssist.activeHearingTurnId() else null
        val text=if(id!=null && state.hearingTurnId==id) state.hearingText else ""
        val key=id to text
        if(key==lastContext) return
        lastContext=key; val ticket=generation
        dispatch {
            if(!active || ticket!=generation || id!=ConversationPhraseAssist.activeHearingTurnId()) return@dispatch
            policy.context(id,text)
            // Which rule the hearing question matched; the words themselves are never logged.
            if(id!=null) ConversationTimeline.mark("question_rule","hearing_turn" to id,
                "rule" to (policy.state.hint?.name ?: "NONE"),"chars" to text.length)
            render()
        }
    }

    /** Invoked on the existing camera executor before either recognizer consumes the frame. */
    fun observation(wordIdle: Boolean, usableHand: Boolean) {
        if(!active || runtime()?.snapshot?.mode!=RecognitionMode.WORD) return
        policy.observation(wordIdle,usableHand)?.let(::apply)
        render()
    }
    fun wordActivity(committed: Boolean = false) { dispatch { if(active) { policy.wordActivity(committed); render() } } }
    fun recognitionChanged() { render() }

    private fun apply(mode: RecognitionMode) {
        val engine=runtime() ?: return
        if(engine.snapshot.mode!=mode) {
            engine.select(mode)
            if(mode==RecognitionMode.FINGERSPELL) engine.clear() // New response, existing API; previous confirmed text stays in coordinator.
        }
        selected(mode)
        render()
    }
    /** A mode the user picked on screen (mode toolbar); stops automatic switching for this turn. */
    fun manual(mode: RecognitionMode) {
        val ticket=generation
        dispatch { if(active && ticket==generation && runtime()!=null) { policy.manual(mode); apply(mode) } }
    }
    fun hear(): Boolean {
        if(runtime()?.snapshot?.mode!=RecognitionMode.FINGERSPELL) return false
        review(true,false); return true
    }

    private fun review(withSpeech: Boolean, offerDiscard: Boolean) {
        val before=runtime()?.snapshot ?: return
        if(before.mode!=RecognitionMode.FINGERSPELL) return
        val text=before.confirmed+before.preview
        if(text.isBlank()) { Toast.makeText(context,"No spelling to confirm",Toast.LENGTH_SHORT).show(); return }
        val ticket=generation
        // FINGERSPELL practical v1 only: no letter may append while the user reviews this draft.
        val practical=runtime()?.practicalMode==true
        if(practical) dispatch { runtime()?.holdForReview() }
        val dialog=AlertDialog.Builder(context).setTitle("Confirm spelling and return to WORD")
            .setMessage(text)
            .setPositiveButton(if(withSpeech) "Confirm and hear" else "Confirm") { _,_ ->
                dispatch {
                    val engine=runtime() ?: return@dispatch
                    val now=engine.snapshot
                    if(!active || ticket!=generation || now.mode!=RecognitionMode.FINGERSPELL ||
                        now.preview!=before.preview || now.confirmed!=before.confirmed) {
                        main { Toast.makeText(context,"Spelling changed. Review it again.",Toast.LENGTH_SHORT).show() }
                        return@dispatch
                    }
                    val bound=policy.state.boundHearingTurnId
                    if(now.preview.isNotBlank()) engine.confirm()
                    val raw=engine.snapshot.confirmed
                    policy.complete(raw); apply(RecognitionMode.WORD)
                    main {
                        if(active && ticket==generation) {
                            val recorded=ConversationPhraseAssist.recordConfirmedSpelling(raw,bound)
                            if(!recorded && ConversationPhraseAssist.enabled)
                                Toast.makeText(context,"Spelling kept; the newer question was left unchanged.",Toast.LENGTH_SHORT).show()
                            if(withSpeech) speak(raw)
                        }
                    }
                }
            }
            .setNegativeButton(android.R.string.cancel,null)
        if(practical) dialog.setOnDismissListener { dispatch { runtime()?.resumeAfterReview() } }
        if(offerDiscard) dialog.setNeutralButton("Discard draft") { _,_ ->
            dispatch {
                val engine=runtime() ?: return@dispatch
                if(active && ticket==generation && engine.snapshot.mode==before.mode &&
                    engine.snapshot.preview==before.preview && engine.snapshot.confirmed==before.confirmed) {
                    engine.retry(); policy.manual(RecognitionMode.WORD); apply(RecognitionMode.WORD)
                } else main { Toast.makeText(context,"Spelling changed. Review it again.",Toast.LENGTH_SHORT).show() }
            }
        }
        dialog.show()
    }

    private fun render() {
        val state=policy.state
        main {
            val engine=runtime(); val current=engine?.snapshot?.mode ?: state.mode
            label.setText(if(current==RecognitionMode.FINGERSPELL)
                R.string.recognition_mode_fingerspell_label else R.string.recognition_mode_word_label)
        }
    }
}
