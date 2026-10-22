package com.example.apphear.conversation

import android.app.Activity
import android.content.Intent
import com.example.apphear.BuildConfig
import java.lang.ref.WeakReference

/**
 * Phase 1 conversation flow (`conversationFlowV1`, debug only): one-tap Talk, and instead of starting a new
 * Text-to-ASL shell and a new Recognition screen on every turn (the Phase 0 baseline measured
 * about 400 MB of growth per round trip), both screens are brought back to the front with
 * FLAG_ACTIVITY_REORDER_TO_FRONT, and a transcript for an already-open Text-to-ASL screen is
 * delivered to that live screen. With the flag off every method is a no-op.
 */
object ConversationScreens {
    /** Fragment result carrying a spoken reply to the live Text-to-ASL screen. */
    const val INCOMING_TRANSCRIPT_RESULT = "conversation/incoming_transcript"
    const val INCOMING_TRANSCRIPT_TEXT = "text"

    private var recognition: WeakReference<Activity>? = null

    val reuseScreens: Boolean get() = BuildConfig.CONVERSATION_FLOW_V1_ENABLED

    /** Tapping Talk opens speech-to-text at once instead of waiting for a separate mic tap. */
    val oneTapTalk: Boolean get() = BuildConfig.CONVERSATION_FLOW_V1_ENABLED

    /** Extra intent flags that bring an existing screen forward instead of stacking a copy. */
    fun reuseFlags(): Int = if (reuseScreens) Intent.FLAG_ACTIVITY_REORDER_TO_FRONT else 0

    fun recognitionCreated(activity: Activity) {
        recognition = WeakReference(activity)
    }

    fun recognitionDestroyed(activity: Activity) {
        if (recognition?.get() === activity) recognition = null
    }

    /**
     * The shell is closing (Back from Home): also close the Recognition screen parked behind it,
     * so Back never reveals a camera screen the user did not open.
     */
    fun finishParkedRecognition() {
        if (!reuseScreens) return
        recognition?.get()?.takeIf { !it.isFinishing }?.finish()
    }
}
