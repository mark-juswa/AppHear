package com.example.apphear.p7e

/** Raw full-window counts; no rounding or reciprocal-latency substitute. */
internal object P7eGate {
    fun cameraPass(capture:Long,analyzer:Long,seconds:Double):Boolean =
        seconds>0 && capture/seconds>=15.0 && analyzer/seconds>=15.0
    fun integratedPass(capture:Long,analyzer:Long,completed:Long,seconds:Double,p95:Double):Boolean =
        cameraPass(capture,analyzer,seconds) && completed/seconds>=15.0 && p95.isFinite() && p95<=62.7532812
}
