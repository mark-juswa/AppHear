package com.example.apphear.ui.texttoasl

import android.Manifest
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.TextView
import androidx.activity.result.ActivityResultLauncher
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.apphear.R
import com.example.apphear.data.profile.AccountServices
import com.example.apphear.databinding.FragmentTextToAslBinding
import com.example.apphear.remote.RemoteConversations
import com.example.apphear.remote.RemoteEndReason
import com.example.apphear.remote.RemoteInvite
import com.example.apphear.remote.RemoteIssue
import com.example.apphear.remote.RemoteMessage
import com.example.apphear.remote.RemotePhase
import com.example.apphear.remote.RemoteQr
import com.example.apphear.remote.RemoteRole
import com.example.apphear.remote.RemoteSession
import com.example.apphear.remote.RemoteState
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Remote conversation on the Text-to-ASL screen (remoteConversation flag). The host keeps the normal
 * screen and every message it signs is also sent to the other phone; the viewer's screen hides the
 * input panel and signs each received message in turn. Owns only views; the conversation itself
 * lives in [RemoteSession] and survives this screen.
 */
class RemoteConversationBinder(
    private val fragment: Fragment,
    private val binding: FragmentTextToAslBinding,
    private val player: Player,
    private val cameraPermission: ActivityResultLauncher<String>,
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

    private enum class Card { NONE, CHOOSE, JOIN_CODE, JOIN_SCAN, INVITATION, SESSION }

    private val context = fragment.requireContext()
    private val card = binding.remoteCard
    private val handler = Handler(Looper.getMainLooper())
    private var session: RemoteSession? = RemoteConversations.current(context)
    private var cardMode = Card.NONE
    private var link: RemoteInvite.Link? = null
    private var scanner: RemoteQr.Scanner? = null
    private var qrFor: String? = null
    private var viewerMode = false
    private var observer: Job? = null
    private var lastPhase: RemotePhase? = null
    private val tick = object : Runnable {
        override fun run() {
            render()
            if ((session?.state?.value?.phase as? RemotePhase.Inviting) != null) handler.postDelayed(this, 1_000)
        }
    }

    init {
        binding.btnConnect.isVisible = true
        binding.btnConnect.setOnClickListener { openCard() }
        binding.remoteEndButton.setOnClickListener { session?.end() }
        card.remoteCodeInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) { joinTypedCode(); true } else false
        }
        if (session?.state?.value?.phase.let { it is RemotePhase.Inviting }) cardMode = Card.SESSION
        observeSession()
        render()
    }

    // ---- fragment hooks ----

    fun attach() {
        session?.attach()
        checkPendingLink()
    }

    fun detach() {
        session?.detach()
        stopScanner()
    }

    /** An invite link may arrive while this screen is already open. */
    fun checkPendingLink() {
        val pending = RemoteConversations.pendingLink ?: return
        RemoteConversations.pendingLink = null
        link = pending
        cardMode = Card.INVITATION
        render()
    }

    /** Host: the screen signed text the user typed or said; send it to the other phone. */
    fun hostSubmitted(text: String) {
        val current = session ?: return
        if (current.state.value.role == RemoteRole.HOST) current.send(text)
    }

    /** The avatar finished (or could not sign) the current message. */
    fun signingIdle() {
        playNext()
    }

    val viewerActive: Boolean get() = viewerMode

    fun cameraPermissionResult(granted: Boolean) {
        if (cardMode != Card.JOIN_SCAN) return
        if (granted) startScanner() else {
            card.remoteBody.setText(R.string.remote_camera_needed)
        }
    }

    fun destroy() {
        handler.removeCallbacksAndMessages(null)
        stopScanner()
    }

    // ---- state ----

    private fun observeSession() {
        observer?.cancel()
        val current = session ?: return
        observer = fragment.viewLifecycleOwner.lifecycleScope.launch {
            fragment.viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                current.state.collect { state ->
                    if (state.phase == RemotePhase.Connected && lastPhase != RemotePhase.Connected && cardMode == Card.SESSION) {
                        // Show "connected" briefly, then get out of the avatar's way.
                        handler.postDelayed({
                            if (cardMode == Card.SESSION && session?.state?.value?.phase == RemotePhase.Connected) {
                                cardMode = Card.NONE
                                render()
                            }
                        }, CONNECTED_CARD_MS)
                    }
                    lastPhase = state.phase
                    render()
                    playNext()
                }
            }
        }
    }

    /** Viewer: signs the oldest received message not signed yet, one at a time. */
    private fun playNext() {
        val current = session ?: return
        val state = current.state.value
        if (state.role != RemoteRole.VIEWER || state.phase != RemotePhase.Connected || player.busySigning) return
        val next = state.messages.firstOrNull { !it.fromMe && (it.seq ?: 0) > current.playedSeq } ?: return
        current.playedSeq = next.seq ?: return
        player.playRemote(next.text)
        current.markSeen(current.playedSeq)
        renderHistory(state)
    }

    // ---- actions ----

    private fun openCard() {
        cardMode = when {
            session?.state?.value?.phase.let { it is RemotePhase.Inviting || it is RemotePhase.Connected ||
                it is RemotePhase.Working } -> Card.SESSION
            cardMode == Card.NONE -> Card.CHOOSE
            else -> Card.NONE
        }
        if (cardMode == Card.NONE) stopScanner()
        render()
    }

    private fun startSession(role: RemoteRole): RemoteSession =
        RemoteConversations.start(context, role).also {
            session = it
            lastPhase = null
            it.attach()
            observeSession()
        }

    private fun host() {
        val name = AccountServices.takeIf { it.enabled }?.repository(context)?.profile?.value?.username.orEmpty()
        startSession(RemoteRole.HOST).host(name)
        cardMode = Card.SESSION
        render()
    }

    private fun join(code: String, secret: String?) {
        hideKeyboard()
        stopScanner()
        startSession(RemoteRole.VIEWER).join(code, secret)
        cardMode = Card.SESSION
        render()
    }

    private fun joinTypedCode() {
        val code = RemoteInvite.normalizeCode(card.remoteCodeInput.text?.toString().orEmpty())
        if (code == null) {
            card.remoteBody.setText(R.string.remote_code_incomplete)
            return
        }
        join(code, null)
    }

    private fun closeFinished() {
        observer?.cancel()
        RemoteConversations.clear()
        session = null
        cardMode = Card.NONE
        render()
    }

    // ---- rendering ----

    private fun render() {
        val state = session?.state?.value
        val phase = state?.phase
        renderViewerMode(state)
        renderStatus(state)
        binding.remoteEndButton.isVisible = phase == RemotePhase.Connected
        when {
            phase is RemotePhase.Ended -> showEnded(phase.reason)
            phase is RemotePhase.Failed -> showFailed(phase.issue)
            cardMode == Card.SESSION && phase != null -> showSession(state)
            cardMode == Card.CHOOSE -> showChoose()
            cardMode == Card.JOIN_CODE -> showJoinCode()
            cardMode == Card.JOIN_SCAN -> showScan()
            cardMode == Card.INVITATION -> showInvitation()
            else -> hideCard()
        }
    }

    private fun renderViewerMode(state: RemoteState?) {
        val viewing = state?.role == RemoteRole.VIEWER && state.phase == RemotePhase.Connected
        if (viewing == viewerMode) {
            if (viewing) renderHistory(state!!)
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
            renderHistory(state!!)
        } else {
            binding.remoteHistory.isVisible = false
            player.restoreInputPanel()
        }
    }

    /** Viewer: earlier messages (not the one on screen), newest last; tap to sign again. */
    private fun renderHistory(state: RemoteState) {
        val current = session ?: return
        val earlier = state.messages.filter { !it.fromMe && (it.seq ?: 0) < current.playedSeq }.takeLast(HISTORY_ITEMS)
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

    private fun renderStatus(state: RemoteState?) {
        val pill = binding.remoteStatusPill
        val phase = state?.phase
        val text = when {
            state == null || phase is RemotePhase.Ended || phase is RemotePhase.Failed || phase == RemotePhase.Idle -> null
            phase == RemotePhase.Working -> context.getString(R.string.remote_working_overline)
            phase is RemotePhase.Inviting -> context.getString(R.string.remote_status_waiting)
            !state.linkUp -> context.getString(R.string.remote_status_reconnecting)
            !state.peerOnline -> context.getString(R.string.remote_status_away)
            state.role == RemoteRole.VIEWER -> context.getString(R.string.remote_status_connected_to, peerName(state).uppercase())
            else -> context.getString(R.string.remote_status_connected) + deliveryText(state)
        }
        pill.isVisible = text != null
        pill.text = text
    }

    private fun deliveryText(state: RemoteState): String {
        val last = state.messages.lastOrNull { it.fromMe } ?: return ""
        val words = context.getString(when (last.status) {
            RemoteMessage.Status.SENDING -> R.string.remote_status_sending
            RemoteMessage.Status.SENT -> R.string.remote_status_sent
            RemoteMessage.Status.SEEN -> R.string.remote_status_seen
            RemoteMessage.Status.FAILED -> R.string.remote_status_not_sent
        })
        return " · $words"
    }

    private fun showChoose() = showCard(
        R.string.remote_choose_overline, context.getString(R.string.remote_choose_title),
        context.getString(R.string.remote_choose_body),
        primary = R.string.remote_show_code to ::host,
        secondary = R.string.remote_join_with_code to { cardMode = Card.JOIN_CODE; render() },
        tertiary = R.string.remote_cancel to { cardMode = Card.NONE; render() },
    )

    private fun showJoinCode() {
        showCard(
            R.string.remote_join_overline, context.getString(R.string.remote_join_title),
            context.getString(R.string.remote_join_body),
            primary = R.string.remote_join to ::joinTypedCode,
            secondary = R.string.remote_scan_qr to { cardMode = Card.JOIN_SCAN; render() },
            tertiary = R.string.remote_cancel to { hideKeyboard(); cardMode = Card.NONE; render() },
        )
        card.remoteCodeInput.isVisible = true
    }

    private fun showScan() {
        showCard(
            R.string.remote_join_overline, context.getString(R.string.remote_scan_title),
            context.getString(R.string.remote_scan_body),
            primary = R.string.remote_type_code to { stopScanner(); cardMode = Card.JOIN_CODE; render() },
            secondary = R.string.remote_cancel to { stopScanner(); cardMode = Card.NONE; render() },
        )
        card.remoteScanner.isVisible = true
        if (scanner == null) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                startScanner()
            } else cameraPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun showInvitation() {
        val invite = link ?: return hideCard()
        showCard(
            R.string.remote_invitation_overline, context.getString(R.string.remote_invitation_title),
            context.getString(R.string.remote_invitation_body, RemoteInvite.display(invite.code)),
            primary = R.string.remote_join to { join(invite.code, invite.secret) },
            secondary = R.string.remote_not_now to { link = null; cardMode = Card.NONE; render() },
        )
    }

    private fun showSession(state: RemoteState) {
        when (val phase = state.phase) {
            RemotePhase.Working, RemotePhase.Idle -> {
                showCard(R.string.remote_working_overline, context.getString(R.string.remote_working_title), "",
                    secondary = R.string.remote_cancel to { session?.end(); closeFinished() })
                card.remoteSpinner.isVisible = true
            }
            is RemotePhase.Inviting -> showInvite(phase)
            RemotePhase.Connected -> showCard(
                R.string.remote_connected_overline,
                if (state.role == RemoteRole.HOST) context.getString(R.string.remote_connected_title_host)
                else context.getString(R.string.remote_connected_title_viewer, peerName(state)),
                context.getString(if (state.role == RemoteRole.HOST) R.string.remote_connected_body_host
                    else R.string.remote_connected_body_viewer),
                primary = R.string.remote_close to { cardMode = Card.NONE; render() },
                secondary = R.string.remote_end_conversation to { session?.end() },
            )
            else -> hideCard()
        }
    }

    private fun showInvite(invite: RemotePhase.Inviting) {
        val remainingMs = invite.expiresAtMs - System.currentTimeMillis()
        if (remainingMs <= 0) {
            showCard(R.string.remote_invite_overline, context.getString(R.string.remote_invite_expired_title),
                context.getString(R.string.remote_invite_expired_body),
                primary = R.string.remote_new_code to { session?.renewInvite() },
                secondary = R.string.remote_stop_inviting to { session?.end() })
            return
        }
        val seconds = remainingMs / 1000
        showCard(R.string.remote_invite_overline, context.getString(R.string.remote_invite_title),
            context.getString(R.string.remote_invite_body, "%d:%02d".format(seconds / 60, seconds % 60)),
            primary = R.string.remote_close to { cardMode = Card.NONE; render() },
            secondary = R.string.remote_stop_inviting to { session?.end() })
        val content = RemoteInvite.link(invite.code, invite.secret)
        if (qrFor != content) {
            qrFor = content
            card.remoteQr.setImageBitmap(RemoteQr.bitmap(content, (220 * context.resources.displayMetrics.density).toInt()))
        }
        card.remoteQr.isVisible = true
        card.remoteCode.text = RemoteInvite.display(invite.code)
        card.remoteCode.isVisible = true
        handler.removeCallbacks(tick)
        handler.postDelayed(tick, 1_000)
    }

    private fun showEnded(reason: RemoteEndReason) = showCard(
        R.string.remote_ended_overline, context.getString(R.string.remote_ended_title),
        context.getString(when (reason) {
            RemoteEndReason.YOU_ENDED -> R.string.remote_ended_you
            RemoteEndReason.OTHER_ENDED -> R.string.remote_ended_other
            RemoteEndReason.TIMED_OUT -> R.string.remote_ended_timeout
        }),
        primary = R.string.remote_ok to ::closeFinished,
    )

    private fun showFailed(issue: RemoteIssue) = showCard(
        R.string.remote_failed_overline, context.getString(R.string.remote_failed_title),
        context.getString(when (issue) {
            RemoteIssue.OFFLINE -> R.string.remote_issue_offline
            RemoteIssue.NOT_CONFIGURED -> R.string.remote_issue_not_configured
            RemoteIssue.GUEST_SIGN_IN_OFF -> R.string.remote_issue_guest_off
            RemoteIssue.SERVER_NOT_READY -> R.string.remote_issue_server_not_ready
            RemoteIssue.INVITE_INVALID -> R.string.remote_issue_invite_invalid
            RemoteIssue.RATE_LIMITED -> R.string.remote_issue_rate_limited
            RemoteIssue.OWN_INVITE -> R.string.remote_issue_own_invite
            RemoteIssue.SERVER -> R.string.remote_issue_server
        }),
        primary = R.string.remote_try_again to { closeFinished(); cardMode = Card.CHOOSE; render() },
        secondary = R.string.remote_close to ::closeFinished,
    )

    private fun showCard(
        overline: Int, title: String, body: String,
        primary: Pair<Int, () -> Unit>? = null,
        secondary: Pair<Int, () -> Unit>? = null,
        tertiary: Pair<Int, () -> Unit>? = null,
    ) {
        card.root.isVisible = true
        card.remoteOverline.setText(overline)
        card.remoteTitle.text = title
        card.remoteBody.text = body
        card.remoteBody.isVisible = body.isNotEmpty()
        card.remoteSpinner.isVisible = false
        card.remoteQr.isVisible = false
        card.remoteCode.isVisible = false
        card.remoteCodeInput.isVisible = false
        card.remoteScanner.isVisible = false
        bindButton(card.remotePrimary, card.remotePrimaryLabel, primary)
        bindButton(card.remoteSecondary, card.remoteSecondaryLabel, secondary)
        bindButton(card.remoteTertiary, card.remoteTertiaryLabel, tertiary)
    }

    private fun bindButton(button: View, label: TextView, action: Pair<Int, () -> Unit>?) {
        button.isVisible = action != null
        if (action == null) return
        label.setText(action.first)
        button.contentDescription = label.text
        button.setOnClickListener { action.second() }
    }

    private fun hideCard() {
        card.root.isVisible = false
        handler.removeCallbacks(tick)
    }

    private fun peerName(state: RemoteState): String =
        state.peerName.ifBlank { context.getString(R.string.remote_the_host) }

    private fun startScanner() {
        if (scanner != null || cardMode != Card.JOIN_SCAN) return
        scanner = RemoteQr.Scanner(context, fragment.viewLifecycleOwner, card.remoteScanner) { text ->
            scanner?.stop()
            scanner = null
            val scanned = RemoteInvite.parse(text)
            if (scanned != null) join(scanned.code, scanned.secret) else {
                card.remoteBody.setText(R.string.remote_issue_invite_invalid)
                startScanner()
            }
        }.also { it.start() }
    }

    private fun stopScanner() {
        scanner?.stop()
        scanner = null
    }

    private fun hideKeyboard() {
        val input = card.remoteCodeInput
        context.getSystemService(InputMethodManager::class.java)?.hideSoftInputFromWindow(input.windowToken, 0)
    }

    companion object {
        private const val HISTORY_ITEMS = 4
        private const val CONNECTED_CARD_MS = 2_500L
        val enabled: Boolean get() = RemoteSession.enabled
    }
}
