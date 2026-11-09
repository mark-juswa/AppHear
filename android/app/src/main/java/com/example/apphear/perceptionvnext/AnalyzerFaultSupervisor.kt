package com.example.apphear.perceptionvnext

/**
 * Phase 2 fault recovery for the live Candidate01 analyzer.
 *
 * Before this, `Candidate01FrameAnalyzer.analyze` caught every Throwable, latched `failed = true` and stopped
 * the camera: one transient frame problem ended recognition for the session. This class decides, per failure,
 * between three outcomes, without ever looping forever:
 *
 *  1. RECOVERED, frame skipped   - the failure happened in PERCEPTION (preprocess / pose / hands), before the
 *     frame became an observation. No temporal state was touched, so it is simply a dropped frame; the decoder
 *     already tolerates observation gaps (its re-arm guard resets above 533 ms).
 *  2. RECOVERED, session reset   - the failure happened in the SESSION phase (observation built, S2 / decoder /
 *     recognizer / publish). Analyzer and session counters may now disagree (`APP_PHONE_SOURCE_INDEX_DISCONTINUITY`
 *     would then fail every later frame), so the temporal session is reset via the existing
 *     `resetTemporalSession`. An in-progress sign is lost; the models and native resources are kept.
 *  3. FATAL                      - model/contract/resource failures, `Error`s, a failed recovery, or an exhausted
 *     fault budget. The analyzer stops and reports once, exactly like the old behaviour.
 *
 * The recovery budget (more than [SupervisorConfig.maxFaultsInWindow] faults inside
 * [SupervisorConfig.windowMs]) is what prevents infinite recovery loops. Its two constants are RELIABILITY
 * POLICY, not recognition thresholds: they are NOT calibrated on field data (none exists); the diagnostics
 * added in this phase are what will allow tuning them.
 *
 * Not thread-safe by itself on purpose: the analyzer already serialises everything under its own monitor
 * (`@Synchronized analyze`/`close`/`resetTemporalSession`), and `runFrame` is additionally `@Synchronized` so a
 * future caller cannot interleave two frames.
 */
internal enum class FaultClass { RECOVERABLE_FRAME, FATAL }

/** Where in the frame the failure happened; decides the recovery action. */
internal enum class AnalyzerPhase { PERCEPTION, SESSION }

internal enum class RecoveryAction { SKIP_FRAME, RESET_TEMPORAL_SESSION, NONE }

internal class FrameContext {
    @JvmField var phase: AnalyzerPhase = AnalyzerPhase.PERCEPTION
}

internal data class FaultReport(
    val code: String,
    val errorType: String,
    val faultClass: FaultClass,
    val phase: AnalyzerPhase,
    val action: RecoveryAction,
    val faultsInWindow: Int,
    /** Why a would-be-recoverable fault became fatal (budget exhausted / recovery failed), else null. */
    val escalation: String? = null,
)

internal sealed interface FrameOutcome {
    data object Ok : FrameOutcome
    data class Recovered(val report: FaultReport) : FrameOutcome
    data class Fatal(val report: FaultReport, val cause: Throwable) : FrameOutcome
    /** The supervisor is already fatal; the frame was not run. */
    data object Rejected : FrameOutcome
}

/** The exception handed to `onFailure` for a fatal analyzer stop (message is what the screen shows). */
internal class AnalyzerFatalException(val report: FaultReport, cause: Throwable) :
    RuntimeException("ANALYZER_FATAL ${report.escalation ?: report.code} (${report.errorType}): ${cause.message.orEmpty().take(120)}", cause)

internal data class SupervisorConfig(
    val maxFaultsInWindow: Int = 5,
    val windowMs: Long = 10_000L,
) {
    init {
        require(maxFaultsInWindow >= 1 && windowMs > 0)
    }
}

internal object AnalyzerFaultClassifier {
    /**
     * Stable error codes thrown by the live path's own guards (`require` messages in `PhoneCausalCore`,
     * `PhoneProductionSession`, `PerceptionVNextNativePreprocessor` and the JNI kernel). Each describes ONE bad
     * frame/observation, never a broken model. Used for documentation and for diagnostics ("known" vs "unknown").
     */
    val KNOWN_FRAME_CODES: Set<String> = setOf(
        "APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP",
        "APP_PHONE_SOURCE_INDEX_DISCONTINUITY",
        "APP_PHONE_DUPLICATE_EVENT_ID",
        "PHONE_SEGMENTATION_NON_CHRONOLOGICAL_TIMESTAMP",
        "PHONE_SEGMENTATION_NONFINITE_FEATURE",
        "VNEXT_NATIVE_CAMERA_GEOMETRY_CHANGED",
        "VNEXT_NATIVE_SOURCE_GEOMETRY_MISMATCH",
        "VNEXT_NATIVE_DIRECT_BUFFER_BOUNDS",
        "VNEXT_NATIVE_CROP_BUFFER_BOUNDS",
        "VNEXT_NATIVE_ROI_INVALID",
        "VNEXT_NATIVE_GEOMETRY_INVALID",
        "VNEXT_NATIVE_SOURCE_SIZE_INVALID",
        "VNEXT_NATIVE_CREATE_FAILED",
    )

    /** Substrings of a code that mean the MODEL / CONTRACT / RESOURCE is wrong: never retry those. */
    private val FATAL_MARKERS = listOf("ASSET_DRIFT", "CONTRACT", "CLOSED", "MODEL_DRIFT", "MANIFEST_DRIFT")
    private val CODE = Regex("[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

    fun code(t: Throwable): String {
        val fromMessage = t.message?.let { CODE.find(it)?.value }
        return (fromMessage ?: t.javaClass.simpleName.ifEmpty { "UNKNOWN" }).take(80)
    }

    fun classify(t: Throwable): FaultClass {
        // Errors (OOM, UnsatisfiedLinkError, StackOverflow, LinkageError, AssertionError...) and interrupts mean
        // the process/thread is not in a state to continue; do not paper over them.
        if (t is Error || t is InterruptedException) return FaultClass.FATAL
        val c = code(t)
        if (FATAL_MARKERS.any { c.contains(it) }) return FaultClass.FATAL
        // Everything else (IllegalArgument/IllegalState from the frame guards, JNI-mapped native errors, ORT /
        // TFLite runtime exceptions) is treated as ONE bad frame, bounded by the fault budget.
        return FaultClass.RECOVERABLE_FRAME
    }

    fun isKnown(code: String) = code in KNOWN_FRAME_CODES
}

internal class AnalyzerSupervisor(
    private val config: SupervisorConfig = SupervisorConfig(),
    private val nowMs: () -> Long = { System.nanoTime() / 1_000_000 },
    private val resetTemporalState: () -> Unit,
    private val metrics: DetectionMetrics,
    private val onFault: (FaultReport) -> Unit = {},
) {
    private val faultTimes = ArrayDeque<Long>()
    private val context = FrameContext()

    @Volatile var isFatal: Boolean = false
        private set

    @Synchronized
    fun runFrame(step: (FrameContext) -> Unit): FrameOutcome {
        if (isFatal) return FrameOutcome.Rejected
        context.phase = AnalyzerPhase.PERCEPTION
        return try {
            step(context)
            FrameOutcome.Ok
        } catch (t: Throwable) {
            handle(t, context.phase)
        }
    }

    private fun handle(t: Throwable, phase: AnalyzerPhase): FrameOutcome {
        val code = AnalyzerFaultClassifier.code(t)
        val type = t.javaClass.simpleName.ifEmpty { "Throwable" }
        if (AnalyzerFaultClassifier.classify(t) == FaultClass.FATAL) {
            return fatal(FaultReport(code, type, FaultClass.FATAL, phase, RecoveryAction.NONE, faultsInWindow()), t)
        }
        val now = nowMs()
        while (faultTimes.isNotEmpty() && now - faultTimes.first() > config.windowMs) faultTimes.removeFirst()
        faultTimes.addLast(now)
        val inWindow = faultTimes.size
        if (inWindow > config.maxFaultsInWindow) {
            return fatal(FaultReport(code, type, FaultClass.FATAL, phase, RecoveryAction.NONE, inWindow,
                escalation = "FAULT_BUDGET_EXHAUSTED"), t)
        }
        val action = if (phase == AnalyzerPhase.PERCEPTION) RecoveryAction.SKIP_FRAME else RecoveryAction.RESET_TEMPORAL_SESSION
        val report = FaultReport(code, type, FaultClass.RECOVERABLE_FRAME, phase, action, inWindow)
        metrics.fault(code, AnalyzerFaultClassifier.isKnown(code))
        if (action == RecoveryAction.RESET_TEMPORAL_SESSION) {
            try {
                resetTemporalState()
            } catch (recoveryFailure: Throwable) {
                t.addSuppressed(recoveryFailure)
                metrics.recoveryAttempt(success = false)
                return fatal(report.copy(faultClass = FaultClass.FATAL, action = RecoveryAction.NONE,
                    escalation = "RECOVERY_FAILED"), t, countFault = false)
            }
        }
        metrics.recoveryAttempt(success = true)
        safeNotify(report)
        return FrameOutcome.Recovered(report)
    }

    private fun fatal(report: FaultReport, cause: Throwable, countFault: Boolean = true): FrameOutcome {
        isFatal = true
        if (countFault) metrics.fault(report.code, AnalyzerFaultClassifier.isKnown(report.code))
        metrics.fatal()
        safeNotify(report)
        return FrameOutcome.Fatal(report, cause)
    }

    private fun faultsInWindow() = faultTimes.size

    /** Diagnostics must never break recovery. */
    private fun safeNotify(report: FaultReport) {
        try { onFault(report) } catch (_: Throwable) { }
    }
}
