package com.example.apphear.conversation.flow2

import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.view.Gravity
import android.view.ViewOutlineProvider
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.core.content.ContextCompat
import android.webkit.WebView
import android.widget.FrameLayout
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslPhrasePlanner
import com.example.apphear.domain.texttoasl.AslResidentAvatarBundle
import com.example.apphear.domain.texttoasl.AslSingleAvatarPolicy
import com.example.apphear.domain.texttoasl.AslTranslationPlanner
import com.example.apphear.ui.texttoasl.AndroidAssetAslCatalogLoader
import com.example.apphear.ui.texttoasl.AndroidAslGrammarLoader
import com.example.apphear.ui.texttoasl.TextToAslPlaybackController
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Plays a reply on the existing Text-to-ASL avatar inside the recognition screen, over the camera
 * area. Owns one lazily created WebView + [TextToAslPlaybackController] and reuses the existing
 * catalog, grammar and planners with the Text-to-ASL screen's own settings. No assets are copied.
 *
 * Completion is the renderer's genuine onFinished for the last sign, never a timer: a stalled sign
 * stops with a notice (as on the Text-to-ASL screen) and a reply with unsupported words stays on
 * screen for review. Adapted from the conversation UX V2/V3 experiment's inline avatar owner.
 */
class ReplyAvatarStage(
    private val activity: ComponentActivity,
    private val stage: FrameLayout,
    private val listener: Listener,
) {
    interface Listener {
        /** Sheet note for [ticket]: progress, completion or a problem. */
        fun note(ticket: Long, text: String)
        /** Every sign played and nothing was left out: return to the camera. */
        fun finished(ticket: Long)
    }

    private val handler = Handler(Looper.getMainLooper())
    private var webView: WebView? = null
    private var player: TextToAslPlaybackController? = null
    private var catalog: AslAnimationCatalog? = null
    private var planner: AslTranslationPlanner? = null
    private var loadJob: Job? = null
    private var ticket = 0L
    private var active = false
    private var visible = false
    private var avatarReady = false
    private var destroyed = false
    private var pending: String? = null
    private var queue: List<AslAnimationAsset> = emptyList()
    private var unsupported: List<String> = emptyList()
    private var index = 0
    private var playing = false

    /** Shown in the card until the first sign plays, so the first (slow) load is not an empty box. */
    private val loading = LinearLayout(activity).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER
        addView(ProgressBar(activity).apply {
            isIndeterminate = true
            indeterminateTintList = ContextCompat.getColorStateList(activity, R.color.color_brand_primary)
        })
        addView(TextView(activity).apply {
            setText(R.string.conversation_v2_avatar_loading)
            setTextColor(0xFFF6EBDD.toInt())
            textSize = 14f
            typeface = runCatching { activity.resources.getFont(R.font.inter_semibold) }.getOrNull()
            setPadding(0, (12 * activity.resources.displayMetrics.density).toInt(), 0, 0)
        })
    }

    init {
        // Keep the avatar inside the card's rounded corners.
        stage.outlineProvider = ViewOutlineProvider.BACKGROUND
        stage.clipToOutline = true
        stage.addView(loading, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
        loading.visibility = View.GONE
    }

    fun play(text: String, ticket: Long) {
        if (destroyed || text.isBlank()) return
        this.ticket = ticket
        active = true
        visible = false
        playing = false
        pending = text
        queue = emptyList()
        player?.pause()
        handler.removeCallbacksAndMessages(null)
        stage.visibility = View.VISIBLE
        loading.visibility = if (avatarReady) View.GONE else View.VISIBLE
        loading.bringToFront()
        listener.note(ticket, activity.getString(R.string.conversation_v2_avatar_loading))
        ensureEngine()
        webView?.onResume()
        awaitVisibleFrame(ticket)
    }

    /** CLOSE, Back or leaving the screen: stop and hide. Nothing resumes on its own. */
    fun stop() {
        handler.removeCallbacksAndMessages(null)
        active = false
        pending = null
        visible = false
        playing = false
        player?.pause()
        webView?.onPause()
        stage.visibility = View.GONE
    }

    fun destroy() {
        stop()
        destroyed = true
        loadJob?.cancel()
        player?.destroy()
        player = null
        webView = null
        stage.removeAllViews()
    }

    private fun ensureEngine() {
        if (player == null) {
            val web = WebView(activity)
            stage.addView(web, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT))
            webView = web
            avatarReady = false
            val controller = TextToAslPlaybackController(activity, web, AslSingleAvatarPolicy.profile)
            player = controller
            controller.onRendererGone = {
                // The renderer process died: drop only this WebView; REPLAY builds a fresh one.
                if (player === controller) {
                    handler.removeCallbacksAndMessages(null)
                    controller.abandonAfterRendererGone()
                    stage.removeView(web)
                    web.destroy()
                    player = null
                    webView = null
                    avatarReady = false
                    playing = false
                    loading.visibility = View.GONE
                    if (active) listener.note(ticket, activity.getString(R.string.conversation_v2_avatar_failed))
                }
            }
            controller.setReadyCallback(object : TextToAslPlaybackController.ReadyCallback {
                override fun onReady() { if (player === controller) tryPlay() }
            })
            controller.setPlaybackCallback(object : TextToAslPlaybackController.PlaybackCallback {
                override fun onStarted(asset: AslAnimationAsset) {
                    if (!active || player !== controller) return
                    if (asset.id == "idle") {
                        if (!avatarReady) {
                            avatarReady = true
                            loading.visibility = View.GONE
                            tryPlay()
                        }
                        return
                    }
                    if (queue.getOrNull(index)?.id != asset.id) return
                    playing = true
                    listener.note(ticket, progress("${asset.displayText} · ${index + 1} / ${queue.size}"))
                    val expected = index
                    val started = ticket
                    handler.postDelayed({
                        if (active && started == ticket && expected == index && playing) {
                            controller.pause()
                            playing = false
                            listener.note(ticket, progress(activity.getString(R.string.conversation_v2_avatar_stalled)))
                        }
                    }, asset.replacement?.durationMs?.plus(2_000L) ?: PLAYBACK_SAFETY_TIMEOUT_MS)
                }

                override fun onFinished(asset: AslAnimationAsset) {
                    if (!active || !visible || !playing || player !== controller ||
                        queue.getOrNull(index)?.id != asset.id) return
                    handler.removeCallbacksAndMessages(null)
                    index++
                    if (index < queue.size) { playCurrent(); return }
                    playing = false
                    ConversationTimeline.mark("avatar_done", "signs" to queue.size, "unsupported" to unsupported.size)
                    if (unsupported.isEmpty()) {
                        listener.finished(ticket)
                    } else {
                        listener.note(ticket, progress(activity.getString(R.string.conversation_v2_avatar_complete)))
                        catalog?.findByAlias("idle")?.let(controller::play)
                    }
                }

                override fun onFailed(asset: AslAnimationAsset) {
                    if (!active || player !== controller) return
                    handler.removeCallbacksAndMessages(null)
                    playing = false
                    listener.note(ticket, activity.getString(R.string.conversation_v2_avatar_failed))
                }
            })
            // Same warm-up as the Text-to-ASL screen.
            controller.warmUp(if (BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED) AslFingerspellingBundle.PATH
                else AslResidentAvatarBundle.PATH)
        }
        if (planner == null && loadJob?.isActive != true) {
            loadJob = activity.lifecycleScope.launch {
                try {
                    require(BuildConfig.ASL_ASSET_PILOT_ENABLED && BuildConfig.ASL_ORIGINAL_WORDS_ENABLED) {
                        "Single human avatar requires the existing OriginalWords build configuration"
                    }
                    val appContext = activity.applicationContext
                    val (loaded, grammar) = withContext(Dispatchers.IO) {
                        AndroidAssetAslCatalogLoader(appContext, false).load() to AndroidAslGrammarLoader(appContext).load()
                    }
                    if (destroyed) return@launch
                    catalog = loaded
                    planner = AslTranslationPlanner(loaded, grammar, AslPhrasePlanner(loaded,
                        completeWordFallback = BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED,
                        dictionarySequenceMode = BuildConfig.ASL_ASSET_PILOT_ENABLED))
                    tryPlay()
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (error: Exception) {
                    Log.w(TAG, "[conversation/flow2] avatar assets unavailable", error)
                    if (!destroyed && active) listener.note(ticket, activity.getString(R.string.conversation_v2_avatar_failed))
                }
            }
        }
    }

    /** Playback starts only once the stage has actually drawn, so the first sign is never missed. */
    private fun awaitVisibleFrame(forTicket: Long) {
        val drawn = Runnable {
            if (!active || destroyed || forTicket != ticket || visible) return@Runnable
            visible = true
            tryPlay()
        }
        webView?.postVisualStateCallback(forTicket, object : WebView.VisualStateCallback() {
            override fun onComplete(requestId: Long) { handler.post(drawn) }
        })
        handler.postDelayed(drawn, VISIBLE_FRAME_FALLBACK_MS)
    }

    private fun tryPlay() {
        val controller = player ?: return
        if (!active || !visible || destroyed || !controller.isReady) return
        val currentPlanner = planner ?: return
        if (!avatarReady) {
            catalog?.findByAlias("idle")?.let(controller::play)
                ?: listener.note(ticket, activity.getString(R.string.conversation_v2_avatar_failed))
            return
        }
        val text = pending ?: return
        pending = null
        val plan = currentPlanner.plan(text)
        queue = plan.queue
        unsupported = plan.unsupportedTokens
        index = 0
        if (queue.isEmpty()) {
            listener.note(ticket, progress(activity.getString(R.string.conversation_v2_avatar_nothing)))
            return
        }
        playCurrent()
    }

    private fun playCurrent() {
        val controller = player ?: return
        if (!active || !visible) return
        queue.getOrNull(index)?.let(controller::play)
        queue.getOrNull(index + 1)?.let(controller::preload)
    }

    /** Text-to-ASL's own progress wording: "1 / 3 • Unsupported: …". */
    private fun progress(text: String): String = if (unsupported.isEmpty()) text
        else activity.getString(R.string.conversation_v2_avatar_unsupported, text, unsupported.joinToString(", "))

    private companion object {
        const val TAG = "ConversationFlowV2"
        // Same per-sign safety as the Text-to-ASL screen; a timeout stops, it never counts as done.
        const val PLAYBACK_SAFETY_TIMEOUT_MS = 7_000L
        const val VISIBLE_FRAME_FALLBACK_MS = 1_000L
    }
}
