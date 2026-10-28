package com.example.apphear.conversation.flow2

import android.graphics.drawable.Drawable
import android.text.TextUtils
import android.util.TypedValue
import android.view.View
import androidx.core.content.ContextCompat
import com.example.apphear.R
import com.example.apphear.databinding.ActivityRecognitionBinding

/**
 * Draws a [FlowState] into the recognition screen's existing bottom sheet. Only established
 * resources are used: the CURRENT SIGN overline style, the coffee start pill, the red stop pill
 * and the tan outlined pills. With the flag off this class is never created.
 */
class ConversationSheetBinder(private val binding: ActivityRecognitionBinding) {
    enum class Secondary { LISTEN, TYPE_REPLY, TYPE_INSTEAD, CANCEL }

    /** What the two tan pills currently mean; read by the click handlers. */
    var secondaryA: Secondary? = null
        private set
    var secondaryB: Secondary? = null
        private set

    private val context = binding.root.context
    private val wave: Drawable? = ContextCompat.getDrawable(context, R.drawable.soundwaves)?.mutate()?.apply {
        val size = (28 * context.resources.displayMetrics.density).toInt()
        setBounds(0, 0, size, size)
        setTint(ContextCompat.getColor(context, R.color.color_brand_primary))
    }

    fun render(s: FlowState, editorOpen: Boolean) {
        val action = ConversationFlow.primaryAction(s)
        renderOverline(s, editorOpen)
        renderLine(s, editorOpen)
        renderPill(action, editorOpen)
        renderSecondary(s, editorOpen)
        binding.conversationEditor.visibility = if (editorOpen) View.VISIBLE else View.GONE
        binding.conversationTypeReplyExpanded.visibility =
            if (!editorOpen && s.phase == FlowPhase.READY) View.VISIBLE else View.GONE
        // The live word stays the main text only while it is the signer's turn.
        binding.glossText.visibility =
            if (!editorOpen && s.phase == FlowPhase.READY) View.VISIBLE else View.GONE
    }

    /** Listening level from the recognizer, roughly -2..10 dB; drives the wave's opacity. */
    fun level(rmsDb: Float) {
        val amount = ((rmsDb + 2f) / 12f).coerceIn(0f, 1f)
        wave?.alpha = (90 + 165 * amount).toInt()
    }

    private fun renderOverline(s: FlowState, editorOpen: Boolean) {
        binding.currentSignLabel.setText(when {
            editorOpen -> R.string.conversation_v2_typing
            s.phase == FlowPhase.SAYING -> R.string.conversation_v2_saying
            s.phase == FlowPhase.LISTENING -> R.string.conversation_v2_listening
            s.phase == FlowPhase.NOT_HEARD -> when (s.failure) {
                ListenFailure.NO_PERMISSION -> R.string.conversation_v2_no_permission_title
                ListenFailure.ERROR, ListenFailure.UNAVAILABLE -> R.string.conversation_v2_listen_error_title
                else -> R.string.conversation_v2_not_heard_title
            }
            s.phase == FlowPhase.REPLY || s.phase == FlowPhase.AVATAR -> R.string.conversation_v2_their_reply
            else -> R.string.conversation_v2_current_sign
        })
    }

    private fun renderLine(s: FlowState, editorOpen: Boolean) {
        val line = binding.conversationLine
        val (text, notice) = when {
            editorOpen -> null to false
            s.phase == FlowPhase.SAYING -> s.speaking to false
            s.phase == FlowPhase.LISTENING ->
                if (s.partialReply.isEmpty()) context.getString(R.string.conversation_v2_listening_waiting) to true
                else caption(s.partialReply) to false
            s.phase == FlowPhase.NOT_HEARD -> context.getString(when (s.failure) {
                ListenFailure.NO_PERMISSION -> R.string.conversation_v2_no_permission
                ListenFailure.ERROR, ListenFailure.UNAVAILABLE -> R.string.conversation_v2_listen_error
                else -> R.string.conversation_v2_not_heard
            }) to true
            s.phase == FlowPhase.REPLY -> s.reply?.let(::caption) to false
            s.phase == FlowPhase.AVATAR -> s.avatarText?.let(::caption) to false
            else -> null to false
        }
        if (text.isNullOrBlank()) {
            line.visibility = View.GONE
            return
        }
        line.visibility = View.VISIBLE
        line.text = text
        // Notices read as quiet body text; spoken words read as the main content.
        line.setTypeface(context.resources.getFont(if (notice) R.font.inter_regular else R.font.inter_black))
        line.setTextSize(TypedValue.COMPLEX_UNIT_SP, if (notice) 16f else 24f)
        line.setTextColor(ContextCompat.getColor(context,
            if (notice) R.color.color_text_secondary else R.color.color_text_primary))
        // While words arrive, keep the newest ones in view.
        line.ellipsize = if (s.phase == FlowPhase.LISTENING) TextUtils.TruncateAt.START else TextUtils.TruncateAt.END
        line.setCompoundDrawablesRelative(if (s.phase == FlowPhase.LISTENING) wave else null, null, null, null)
    }

    /** Speech results arrive lowercase; show them as a sentence. Context Assist keeps the exact words. */
    private fun caption(text: String): String = text.replaceFirstChar { it.titlecase() }

    private fun renderPill(action: PrimaryAction, editorOpen: Boolean) {
        val (label, icon, description) = when {
            editorOpen -> Triple(R.string.conversation_v2_send, null, R.string.conversation_v2_send_description)
            action == PrimaryAction.SAY_IT ->
                Triple(R.string.conversation_v2_say_it, R.drawable.ic_volume, R.string.conversation_v2_say_it_description)
            action == PrimaryAction.LISTEN ->
                Triple(R.string.conversation_v2_listen, R.drawable.ic_mic, R.string.conversation_v2_listen_description)
            action == PrimaryAction.STOP ->
                Triple(R.string.conversation_v2_stop, null, R.string.conversation_v2_stop_description)
            action == PrimaryAction.SIGN_IT ->
                Triple(R.string.conversation_v2_sign_it, R.drawable.play, R.string.conversation_v2_sign_it_description)
            else -> Triple(R.string.conversation_v2_replay, R.drawable.ic_replay, R.string.conversation_v2_replay)
        }
        binding.speakButtonLabel.setText(label)
        binding.speakButton.contentDescription = context.getString(description)
        binding.speakButton.setBackgroundResource(
            if (!editorOpen && action == PrimaryAction.STOP) R.drawable.btn_stop_bg else R.drawable.btn_start_bg)
        if (icon == null) {
            binding.speakButtonIcon.visibility = View.GONE
        } else {
            binding.speakButtonIcon.visibility = View.VISIBLE
            binding.speakButtonIcon.setImageResource(icon)
        }
    }

    private fun renderSecondary(s: FlowState, editorOpen: Boolean) {
        val (a, b) = when {
            editorOpen -> null to Secondary.CANCEL
            s.phase == FlowPhase.LISTENING -> null to Secondary.TYPE_INSTEAD
            s.phase == FlowPhase.NOT_HEARD -> null to Secondary.TYPE_REPLY
            s.phase == FlowPhase.REPLY -> Secondary.LISTEN to Secondary.TYPE_REPLY
            else -> null to null
        }
        secondaryA = a
        secondaryB = b
        binding.conversationSecondaryRow.visibility = if (a == null && b == null) View.GONE else View.VISIBLE
        bindSecondary(binding.conversationSecondaryA, binding.conversationSecondaryALabel, a)
        bindSecondary(binding.conversationSecondaryB, binding.conversationSecondaryBLabel, b)
        binding.conversationSecondarySpacer.visibility = if (a != null && b != null) View.VISIBLE else View.GONE
    }

    private fun bindSecondary(button: View, label: android.widget.TextView, which: Secondary?) {
        button.visibility = if (which == null) View.GONE else View.VISIBLE
        if (which == null) return
        label.setText(when (which) {
            Secondary.LISTEN -> R.string.conversation_v2_listen
            Secondary.TYPE_REPLY -> R.string.conversation_v2_type_reply
            Secondary.TYPE_INSTEAD -> R.string.conversation_v2_type_instead
            Secondary.CANCEL -> R.string.conversation_v2_cancel
        })
        button.contentDescription = label.text
    }
}
