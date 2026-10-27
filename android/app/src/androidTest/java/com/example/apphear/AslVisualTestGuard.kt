package com.example.apphear

import android.app.Instrumentation
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import android.webkit.WebView
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.junit.Assert.*

/** Refuse obscured evidence; only the emulator's System UI Wait is recoverable. */
internal object AslVisualTestGuard {
    fun awaitVisualCommit(i: Instrumentation, viewer: WebView) {
        val drawn = CountDownLatch(1)
        i.runOnMainSync {
            viewer.postVisualStateCallback(SystemClock.uptimeMillis(), object : WebView.VisualStateCallback() {
                override fun onComplete(requestId: Long) {
                    viewer.invalidate()
                    viewer.postOnAnimation { viewer.postOnAnimation { drawn.countDown() } }
                }
            })
        }
        assertTrue("WebView compositor committed the requested pose", drawn.await(30, TimeUnit.SECONDS))
    }
    fun requireUnobscuredApp(i: Instrumentation) {
        fun visibleRoot(): AccessibilityNodeInfo {
            val deadline=SystemClock.uptimeMillis()+5000
            do {
                i.uiAutomation.rootInActiveWindow?.let { return it }
                SystemClock.sleep(50)
            } while(SystemClock.uptimeMillis()<deadline)
            error("No visible window for capture")
        }
        var root=visibleRoot()
        if(root.packageName?.toString()=="android") {
            val titles=root.findAccessibilityNodeInfosByViewId("android:id/alertTitle")
            val title=titles.joinToString(" ") { it.text?.toString().orEmpty() }
            assertTrue("Unexpected system/app failure overlay: $title",title.contains("System UI") && title.contains("responding"))
            val wait=root.findAccessibilityNodeInfosByViewId("android:id/aerr_wait").singleOrNull()
                ?: error("System UI warning has no Wait action")
            assertTrue("Dismiss emulator warning with Wait",wait.performAction(AccessibilityNodeInfo.ACTION_CLICK))
            val deadline=SystemClock.uptimeMillis()+5000
            do {
                SystemClock.sleep(50)
                root=i.uiAutomation.rootInActiveWindow ?: continue
            } while(root.packageName?.toString()=="android" && SystemClock.uptimeMillis()<deadline)
        }
        assertEquals("Capture must show AppHear, not an obscuring window","com.example.apphear",root.packageName?.toString())
    }
}
