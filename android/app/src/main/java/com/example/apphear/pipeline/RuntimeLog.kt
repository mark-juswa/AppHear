package com.example.apphear.pipeline

import android.util.Log

/** Android Log wrapper that becomes a no-op under local JVM tests where android.util.Log is unmocked. */
object RuntimeLog {
    fun i(tag: String, message: String) {
        runCatching { Log.i(tag, message) }
    }

    fun w(tag: String, message: String) {
        runCatching { Log.w(tag, message) }
    }
}
