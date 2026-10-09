package com.example.apphear

import android.app.Activity
import android.app.Application
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import com.example.apphear.contextassist.ConversationPhraseAssist

/** Ends the in-memory conversation after the whole app leaves the foreground. */
class AppHearApplication : Application() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var startedActivities = 0
    private var hearingTurnAtStop: Long? = null
    private val clearBackgroundSession = Runnable {
        if (startedActivities == 0 &&
            ConversationPhraseAssist.presentationState.value.hearingTurnId == hearingTurnAtStop) {
            ConversationPhraseAssist.appBackgrounded()
        }
    }

    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(object : ActivityLifecycleCallbacks {
            override fun onActivityStarted(activity: Activity) {
                mainHandler.removeCallbacks(clearBackgroundSession)
                startedActivities++
            }

            override fun onActivityStopped(activity: Activity) {
                startedActivities = (startedActivities - 1).coerceAtLeast(0)
                if (startedActivities == 0) {
                    hearingTurnAtStop = ConversationPhraseAssist.presentationState.value.hearingTurnId
                    mainHandler.removeCallbacks(clearBackgroundSession)
                    mainHandler.postDelayed(clearBackgroundSession, 500L)
                }
            }

            override fun onActivityCreated(activity: Activity, state: Bundle?) = Unit
            override fun onActivityResumed(activity: Activity) = Unit
            override fun onActivityPaused(activity: Activity) = Unit
            override fun onActivitySaveInstanceState(activity: Activity, state: Bundle) = Unit
            override fun onActivityDestroyed(activity: Activity) = Unit
        })
    }
}
