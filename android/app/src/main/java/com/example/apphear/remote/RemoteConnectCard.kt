package com.example.apphear.remote

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.isVisible
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.apphear.R
import com.example.apphear.databinding.RemoteConnectCardBinding
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

/**
 * The connect / invite / join card plus the connect button and status pill, shared by the
 * Text-to-ASL and Recognition screens (remoteConversation flag). [hostOnly] screens (Recognition)
 * only offer to show a code; joining happens on the Text-to-ASL screen.
 */
class RemoteConnectCard(
    private val context: Context,
    private val owner: LifecycleOwner,
    private val card: RemoteConnectCardBinding,
    connectButton: View,
    private val statusPill: TextView,
    private val permissions: Permissions,
    private val hostOnly: Boolean = false,
    /** Called with every state change (after the card has drawn), for screen-specific views. */
    private val onState: (RemoteLink?, RemoteState?) -> Unit = { _, _ -> },
) {
    /** Asks for runtime permissions; [done] gets true when all were granted. */
    fun interface Permissions {
        fun request(permissions: Array<String>, done: (Boolean) -> Unit)
    }

    private enum class Mode { NONE, CHOOSE, JOIN_CODE, JOIN_SCAN, INVITATION, SESSION }

    private val handler = Handler(Looper.getMainLooper())
    private var mode = Mode.NONE
    private var link: RemoteInvite.Link? = null
    private var scanner: RemoteQr.Scanner? = null
    private var qrFor: String? = null
    private var lastPhase: RemotePhase? = null
    private var attached: RemoteLink? = null
    private val tick = object : Runnable {
        override fun run() {
            render()
            if (current?.state?.value?.phase is RemotePhase.Inviting) handler.postDelayed(this, 1_000)
        }
    }

    private val current: RemoteLink? get() = RemoteConversations.active.value

    init {
        RemoteConversations.restore(context)
        connectButton.isVisible = true
        connectButton.setOnClickListener { toggle() }
        card.remoteCodeInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) { joinTypedCode(); true } else false
        }
        if (current?.state?.value?.phase is RemotePhase.Inviting) mode = Mode.SESSION
        observe()
        render()
    }

    // ---- screen hooks ----

    /** The screen became visible. */
    fun start() {
        attachTo(current)
        checkPendingLink()
    }

    /** The screen was hidden. */
    fun stop() {
        attachTo(null)
        stopScanner()
    }

    fun destroy() {
        handler.removeCallbacksAndMessages(null)
        stopScanner()
    }

    /** Opens the card on its first page (Settings' "Connect a device"). */
    fun open() {
        if (mode == Mode.NONE) toggle()
    }

    /** An invite link may arrive while the screen is already open. */
    fun checkPendingLink() {
        if (hostOnly) return
        val pending = RemoteConversations.pendingLink ?: return
        RemoteConversations.pendingLink = null
        link = pending
        mode = Mode.INVITATION
        render()
    }

    // ---- state ----

    @OptIn(ExperimentalCoroutinesApi::class)
    private fun observe() {
        owner.lifecycleScope.launch {
            owner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                RemoteConversations.active.flatMapLatest { link -> link?.state ?: flowOf(null) }.collect { state ->
                    attachTo(current)
                    val phase = state?.phase
                    if (phase == RemotePhase.Connected && lastPhase != RemotePhase.Connected && mode == Mode.SESSION) {
                        // Show "connected" briefly, then get out of the way.
                        handler.postDelayed({
                            if (mode == Mode.SESSION && current?.state?.value?.phase == RemotePhase.Connected) {
                                mode = Mode.NONE
                                render()
                            }
                        }, CONNECTED_CARD_MS)
                    }
                    lastPhase = phase
                    render()
                }
            }
        }
    }

    /** Keeps exactly one visible-screen attachment on the active conversation. */
    private fun attachTo(next: RemoteLink?) {
        val visible = owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
        val target = if (visible) next else null
        if (target === attached) return
        attached?.detach()
        attached = target
        target?.attach()
    }

    // ---- actions ----

    private fun toggle() {
        val phase = current?.state?.value?.phase
        mode = when {
            phase is RemotePhase.Inviting || phase == RemotePhase.Connected || phase == RemotePhase.Working -> Mode.SESSION
            mode == Mode.NONE -> Mode.CHOOSE
            else -> Mode.NONE
        }
        if (mode == Mode.NONE) stopScanner()
        render()
    }

    /** Phone-to-phone may be needed (no internet, Settings, or as a fallback), so ask for it first. */
    private fun withNearbyPermission(action: () -> Unit) {
        val needed = RemoteConversations.nearbyPermissions().filter {
            ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED
        }
        if (needed.isEmpty()) action() else permissions.request(needed.toTypedArray()) { action() }
    }

    private fun host() = withNearbyPermission {
        RemoteConversations.host(context)
        mode = Mode.SESSION
        render()
    }

    private fun joinLink(invite: RemoteInvite.Link) = withNearbyPermission {
        RemoteConversations.join(context, invite)
        mode = Mode.SESSION
        render()
    }

    private fun joinTypedCode() {
        val code = RemoteInvite.normalizeCode(card.remoteCodeInput.text?.toString().orEmpty())
        if (code == null) {
            card.remoteBody.setText(R.string.remote_code_incomplete)
            return
        }
        hideKeyboard()
        withNearbyPermission {
            RemoteConversations.join(context, code)
            mode = Mode.SESSION
            render()
        }
    }

    private fun closeFinished() {
        RemoteConversations.clear()
        mode = Mode.NONE
        render()
    }

    // ---- rendering ----

    private fun render() {
        val link = current
        val state = link?.state?.value
        val phase = state?.phase
        renderStatus(state)
        when {
            phase is RemotePhase.Ended -> showEnded(phase.reason)
            phase is RemotePhase.Failed -> showFailed(phase.issue)
            mode == Mode.SESSION && phase != null -> showSession(state)
            mode == Mode.CHOOSE -> showChoose()
            mode == Mode.JOIN_CODE -> showJoinCode()
            mode == Mode.JOIN_SCAN -> showScan()
            mode == Mode.INVITATION -> showInvitation()
            else -> hideCard()
        }
        onState(link, state)
    }

    private fun renderStatus(state: RemoteState?) {
        val phase = state?.phase
        val text = when {
            state == null || phase is RemotePhase.Ended || phase is RemotePhase.Failed || phase == RemotePhase.Idle -> null
            phase == RemotePhase.Working -> context.getString(R.string.remote_working_overline)
            phase is RemotePhase.Inviting -> context.getString(R.string.remote_status_waiting)
            !state.linkUp -> context.getString(R.string.remote_status_reconnecting)
            !state.peerOnline -> context.getString(R.string.remote_status_away)
            state.peerName.isNotBlank() -> context.getString(R.string.remote_status_connected_to, state.peerName.uppercase()) +
                deliveryText(state)
            else -> context.getString(R.string.remote_status_connected) + deliveryText(state)
        }
        statusPill.isVisible = text != null
        statusPill.text = text
    }

    private fun deliveryText(state: RemoteState): String {
        if (state.role != RemoteRole.HOST) return ""
        val last = state.messages.lastOrNull { it.fromMe } ?: return ""
        return " · " + context.getString(when (last.status) {
            RemoteMessage.Status.SENDING -> R.string.remote_status_sending
            RemoteMessage.Status.SENT -> R.string.remote_status_sent
            RemoteMessage.Status.SEEN -> R.string.remote_status_seen
            RemoteMessage.Status.FAILED -> R.string.remote_status_not_sent
        })
    }

    private fun showChoose() = if (hostOnly) showCard(
        R.string.remote_choose_overline, context.getString(R.string.remote_choose_title),
        context.getString(R.string.remote_choose_body_host),
        primary = R.string.remote_show_code to ::host,
        secondary = R.string.remote_cancel to { mode = Mode.NONE; render() },
    ) else showCard(
        R.string.remote_choose_overline, context.getString(R.string.remote_choose_title),
        context.getString(R.string.remote_choose_body),
        primary = R.string.remote_show_code to ::host,
        secondary = R.string.remote_join_with_code to { mode = Mode.JOIN_CODE; render() },
        tertiary = R.string.remote_cancel to { mode = Mode.NONE; render() },
    )

    private fun showJoinCode() {
        showCard(
            R.string.remote_join_overline, context.getString(R.string.remote_join_title),
            context.getString(R.string.remote_join_body),
            primary = R.string.remote_join to ::joinTypedCode,
            secondary = R.string.remote_scan_qr to { mode = Mode.JOIN_SCAN; render() },
            tertiary = R.string.remote_cancel to { hideKeyboard(); mode = Mode.NONE; render() },
        )
        card.remoteCodeInput.isVisible = true
    }

    private fun showScan() {
        showCard(
            R.string.remote_join_overline, context.getString(R.string.remote_scan_title),
            context.getString(R.string.remote_scan_body),
            primary = R.string.remote_type_code to { stopScanner(); mode = Mode.JOIN_CODE; render() },
            secondary = R.string.remote_cancel to { stopScanner(); mode = Mode.NONE; render() },
        )
        card.remoteScanner.isVisible = true
        if (scanner != null) return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startScanner()
        } else permissions.request(arrayOf(Manifest.permission.CAMERA)) { granted ->
            if (granted) startScanner() else if (mode == Mode.JOIN_SCAN) card.remoteBody.setText(R.string.remote_camera_needed)
        }
    }

    private fun showInvitation() {
        val invite = link ?: return hideCard()
        showCard(
            R.string.remote_invitation_overline, context.getString(R.string.remote_invitation_title),
            context.getString(R.string.remote_invitation_body, RemoteInvite.display(invite.code)),
            primary = R.string.remote_join to { link = null; joinLink(invite) },
            secondary = R.string.remote_not_now to { link = null; mode = Mode.NONE; render() },
        )
    }

    private fun showSession(state: RemoteState) {
        when (val phase = state.phase) {
            RemotePhase.Working, RemotePhase.Idle -> {
                showCard(R.string.remote_working_overline, context.getString(R.string.remote_working_title), "",
                    secondary = R.string.remote_cancel to { current?.end(); closeFinished() })
                card.remoteSpinner.isVisible = true
            }
            is RemotePhase.Inviting -> showInvite(phase)
            RemotePhase.Connected -> showCard(
                R.string.remote_connected_overline,
                if (state.peerName.isBlank()) context.getString(R.string.remote_connected_title_host)
                else context.getString(R.string.remote_connected_title_viewer, state.peerName),
                context.getString(if (state.role == RemoteRole.HOST) R.string.remote_connected_body_host
                    else R.string.remote_connected_body_viewer),
                primary = R.string.remote_close to { mode = Mode.NONE; render() },
                secondary = R.string.remote_end_conversation to { current?.end() },
            )
            else -> hideCard()
        }
    }

    private fun showInvite(invite: RemotePhase.Inviting) {
        val remainingMs = invite.expiresAtMs - System.currentTimeMillis()
        if (remainingMs <= 0) {
            showCard(R.string.remote_invite_overline, context.getString(R.string.remote_invite_expired_title),
                context.getString(R.string.remote_invite_expired_body),
                primary = R.string.remote_new_code to { current?.renewInvite() },
                secondary = R.string.remote_stop_inviting to { current?.end() })
            return
        }
        val seconds = remainingMs / 1000
        val body = context.getString(if (invite.nearby) R.string.remote_invite_body_nearby else R.string.remote_invite_body,
            "%d:%02d".format(seconds / 60, seconds % 60))
        showCard(R.string.remote_invite_overline, context.getString(R.string.remote_invite_title), body,
            primary = R.string.remote_close to { mode = Mode.NONE; render() },
            secondary = R.string.remote_stop_inviting to { current?.end() })
        val content = RemoteInvite.link(invite.code, invite.secret, nearby = invite.nearby)
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
            RemoteIssue.NEARBY_PERMISSION -> R.string.remote_issue_nearby_permission
            RemoteIssue.NEARBY_UNAVAILABLE -> R.string.remote_issue_nearby_unavailable
            RemoteIssue.NOT_FOUND_NEARBY -> R.string.remote_issue_not_found_nearby
        }),
        primary = R.string.remote_try_again to { RemoteConversations.clear(); mode = Mode.CHOOSE; render() },
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

    private fun startScanner() {
        if (scanner != null || mode != Mode.JOIN_SCAN) return
        scanner = RemoteQr.Scanner(context, owner, card.remoteScanner) { text ->
            scanner?.stop()
            scanner = null
            val scanned = RemoteInvite.parse(text)
            if (scanned != null) joinLink(scanned) else {
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
        context.getSystemService(InputMethodManager::class.java)
            ?.hideSoftInputFromWindow(card.remoteCodeInput.windowToken, 0)
    }

    companion object {
        private const val CONNECTED_CARD_MS = 2_500L
        val enabled: Boolean get() = RemoteSession.enabled
    }
}
