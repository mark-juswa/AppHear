package com.example.apphear.ui.texttoasl

import android.view.LayoutInflater
import android.widget.TextView
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import com.example.apphear.R
import com.example.apphear.databinding.FragmentTextToAslBinding
import com.example.apphear.remote.RemoteConnectCard
import com.example.apphear.remote.RemoteConversations
import com.example.apphear.remote.RemoteLink
import com.example.apphear.remote.RemotePhase
import com.example.apphear.remote.RemoteRole
import com.example.apphear.remote.RemoteState

/**
 * Remote conversation on the Text-to-ASL screen (remoteConversation flag). The host keeps the normal
 * screen and every message it signs is also sent to the other phone; the viewer's screen hides the
 * input panel and signs each received message in turn. Owns only views; the conversation itself
 * lives in [RemoteConversations] and survives this screen.
 */
class RemoteConversationBinder(
    fragment: Fragment,
    private val binding: FragmentTextToAslBinding,
    private val player: Player,
    permissions: RemoteConnectCard.Permissions,
) {
    /** What the binder needs from the Text-to-ASL screen. */
    interface Player {
        /** True while a message is being signed or waits for the avatar. */
        val busySigning: Boolean
        /** Shows [text] as the current message and signs it, exactly like an incoming reply. */
        fun playRemote(text: String)
        /** Restores the normal input panel after viewing ends. */
        fun restoreInputPanel()
    }

    private val context = fragment.requireContext()
    private var viewerMode = false
    private val card = RemoteConnectCard(context, fragment.viewLifecycleOwner, binding.remoteCard, binding.btnConnect,
        binding.remoteStatusPill, permissions) { link, state -> onState(link, state) }

    init {
        binding.remoteEndButton.setOnClickListener { RemoteConversations.active.value?.end() }
    }

    // ---- fragment hooks ----

    fun attach() = card.start()
    fun detach() = card.stop()
    fun checkPendingLink() = card.checkPendingLink()
    fun openConnect() = card.open()
    fun destroy() = card.destroy()

    /** Host: the screen signed text the user typed or said; send it to the other phone. */
    fun hostSubmitted(text: String) = RemoteConversations.sendFromHost(text)

    /** The avatar finished (or could not sign) the current message. */
    fun signingIdle() = playNext()

    val viewerActive: Boolean get() = viewerMode

    // ---- state ----

    private fun onState(link: RemoteLink?, state: RemoteState?) {
        binding.remoteEndButton.isVisible = state?.phase == RemotePhase.Connected
        renderViewerMode(link, state)
        playNext()
    }

    /** Viewer: signs the oldest received message not signed yet, one at a time. */
    private fun playNext() {
        val link = RemoteConversations.active.value ?: return
        val state = link.state.value
        if (state.role != RemoteRole.VIEWER || state.phase != RemotePhase.Connected || player.busySigning) return
        val next = state.messages.firstOrNull { !it.fromMe && (it.seq ?: 0) > link.playedSeq } ?: return
        link.playedSeq = next.seq ?: return
        player.playRemote(next.text)
        link.markSeen(link.playedSeq)
        renderHistory(link, state)
    }

    private fun renderViewerMode(link: RemoteLink?, state: RemoteState?) {
        val viewing = link != null && state?.role == RemoteRole.VIEWER && state.phase == RemotePhase.Connected
        if (viewing == viewerMode) {
            if (viewing) renderHistory(link!!, state!!)
            return
        }
        viewerMode = viewing
        binding.modeSelector.isVisible = !viewing
        binding.expandableContent.isVisible = false
        binding.dragHandleWrapper.isVisible = !viewing
        binding.replyButton.isVisible = !viewing
        binding.btnSpeak.isVisible = !viewing
        if (viewing) {
            binding.translatorModeHeading.setText(R.string.remote_viewer_heading)
            if (!player.busySigning && state!!.messages.none { !it.fromMe }) binding.signedText.setText(R.string.remote_viewer_waiting)
            binding.signedText.isVisible = true
            renderHistory(link!!, state!!)
        } else {
            binding.remoteHistory.isVisible = false
            player.restoreInputPanel()
        }
    }

    /** Viewer: earlier messages (not the one on screen), newest last; tap to sign again. */
    private fun renderHistory(link: RemoteLink, state: RemoteState) {
        val earlier = state.messages.filter { !it.fromMe && (it.seq ?: 0) < link.playedSeq }.takeLast(HISTORY_ITEMS)
        val items = binding.remoteHistoryItems
        items.removeAllViews()
        val inflater = LayoutInflater.from(context)
        earlier.forEach { message ->
            val row = inflater.inflate(R.layout.item_conversation_bubble_reply, items, false)
            row.findViewById<TextView>(R.id.bubbleText).apply {
                text = message.text
                setOnClickListener { if (!player.busySigning) player.playRemote(message.text) }
            }
            items.addView(row)
        }
        binding.remoteHistory.isVisible = viewerMode && earlier.isNotEmpty()
    }

    companion object {
        private const val HISTORY_ITEMS = 4
        val enabled: Boolean get() = RemoteConnectCard.enabled
    }
}
