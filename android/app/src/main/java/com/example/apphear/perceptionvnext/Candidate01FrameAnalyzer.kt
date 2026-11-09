package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.SystemClock
import android.util.Log
import com.example.apphear.BuildConfig
import androidx.camera.core.ImageProxy
import com.example.apphear.pipeline.CloseableFrameAnalyzer
import com.example.apphear.pipeline.FpsTracker
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.ui.PhoneOverlayFrame
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

/** Production CameraX bridge for the same current-frame Candidate01 path as the validated capture. */
internal class Candidate01FrameAnalyzer(
    context: Context,
    private val session: PhoneProductionSession,
    private val onResult: (FrameResult) -> Unit,
    private val ownsObservation: ((PhoneRawObservation, ImageProxy) -> Boolean)? = null,
    private val onFailure: (Throwable) -> Unit,
) : CloseableFrameAnalyzer {
    private data class HandFrame(
        val xy: FloatArray,
        val valid: BooleanArray,
        val observed: Boolean,
        val presence: Float,
        val proposalPresent: Boolean,
        val proposalSupport: FloatArray,
        val roi: PerceptionVNextMath.HandRoi?,
        val cropMs: Double = 0.0,
        val inferenceMs: Double = 0.0,
    )

    private val poseRunner = DWPoseTRunner(context)
    private val handRunner = try {
        HandRefinerRunner(context)
    } catch (error: Throwable) {
        poseRunner.close() // Phase 2: do not leak the native pose session if the hand model fails to load
        throw error
    }
    private val parallelHands = BuildConfig.RECOGNITION_V3_PARALLEL_HANDS_ENABLED
    private val rightHandRunner = try {
        if (parallelHands) HandRefinerRunner(context) else null
    } catch (error: Throwable) {
        handRunner.close()
        poseRunner.close()
        throw error
    }
    private val handPair = if (parallelHands) CurrentFrameHandPair() else null
    private val rightHandInput = if (parallelHands) java.nio.ByteBuffer
        .allocateDirect(224 * 224 * 3 * 4).order(java.nio.ByteOrder.nativeOrder()) else null
    private val fps = FpsTracker()
    private var preprocessor: PerceptionVNextNativePreprocessor? = null
    private var lastTimestampNs = Long.MIN_VALUE
    private var sourceIndex = 0
    private var lastDecoderState: PhoneDecoderState? = null
    private var closed = false
    private var failed = false
    private var profileCount = 0

    /** Phase 2: counters + per-stage latency; also the source of the debug-only periodic log line. */
    val metrics = DetectionMetrics(nominalFps = NOMINAL_CAMERA_FPS)
    private val supervisor = AnalyzerSupervisor(
        resetTemporalState = { resetAfterFault() },
        metrics = metrics,
        onFault = ::logFault,
    )
    private val reporter: ScheduledExecutorService? = if (BuildConfig.DEBUG) {
        Executors.newSingleThreadScheduledExecutor { task -> Thread(task, "AppHearDetectReport").apply { isDaemon = true } }
            .also { it.scheduleAtFixedRate({ reportMetrics() }, REPORT_PERIOD_S, REPORT_PERIOD_S, TimeUnit.SECONDS) }
    } else null

    /**
     * Phase 2: one bad frame no longer ends the session. Everything that used to run directly in this method now
     * runs in [processFrame] under [supervisor], which skips the frame or resets the temporal session for
     * recoverable faults, and only reports fatal ones (`onFailure`, once) exactly as before.
     */
    @Synchronized
    override fun analyze(image: ImageProxy) {
        try {
            if (closed) return
            if (failed) {
                metrics.frameAfterFatal()
                return
            }
            metrics.inputFrame(image.imageInfo.timestamp)
            when (val outcome = supervisor.runFrame { context -> processFrame(image, context) }) {
                is FrameOutcome.Fatal -> {
                    failed = true
                    Log.e(TAG, "Causal recognition stopped (${outcome.report.escalation ?: outcome.report.code}); " +
                        "legacy fallback is disabled", outcome.cause)
                    try {
                        onFailure(AnalyzerFatalException(outcome.report, outcome.cause))
                    } catch (callbackFailure: Throwable) {
                        Log.e(TAG, "onFailure callback failed", callbackFailure)
                    }
                }
                else -> Unit
            }
        } finally {
            image.close()
        }
    }

    private fun processFrame(image: ImageProxy, context: FrameContext) {
        val timestampNs = image.imageInfo.timestamp
        require(timestampNs > lastTimestampNs) { "APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP" }
        lastTimestampNs = timestampNs
        val started = SystemClock.elapsedRealtimeNanos()
        DetectionMetrics.plausibleAgeMs((started - timestampNs) / 1_000_000.0)?.let { metrics.record(DetectionStage.FRAME_AGE, it) }
        val prepared = preprocessor?.takeIf { it.compatible(image) }
            ?: PerceptionVNextNativePreprocessor(image).also { replacement ->
                preprocessor?.close()
                preprocessor = replacement
            }
        prepared.preprocess(image)
        val preprocessEnded = SystemClock.elapsedRealtimeNanos()
        val pose = poseRunner.run(prepared.poseInput, prepared.transform)
        val handsStarted = SystemClock.elapsedRealtimeNanos()
        // Native crop is read-only on the current frame; each task writes its own buffer.
        // One-hand frames stay serial, without a task handoff or a second inference.
        val bothProposed = handPair != null && listOf(
            PerceptionVNextMath.LEFT_HAND_START, PerceptionVNextMath.RIGHT_HAND_START,
        ).all { PerceptionVNextMath.handRoi(pose.decoded, it, prepared.transform) != null }
        val (left, right) = if (bothProposed) requireNotNull(handPair).run(
            { runHand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START) },
            { runHand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START,
                requireNotNull(rightHandRunner), requireNotNull(rightHandInput)) },
        ) else Pair(
            runHand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START),
            runHand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START),
        )
        val handsEnded = SystemClock.elapsedRealtimeNanos()
        val bodyXy = FloatArray(16)
        val bodySupport = FloatArray(8)
        val bodyValid = BooleanArray(8)
        var supported = 0
        for ((local, point) in PerceptionVNextMath.bodyIndices.withIndex()) {
            val x = pose.decoded.xy[point * 2]
            val y = pose.decoded.xy[point * 2 + 1]
            bodyXy[local * 2] = x
            bodyXy[local * 2 + 1] = y
            bodySupport[local] = pose.decoded.support[point]
            bodyValid[local] = PerceptionVNextMath.bodyPointValid(
                x, y, bodySupport[local], prepared.transform,
            )
            if (bodyValid[local]) supported++
        }
        // Phase 2 fault boundary: from here on the frame becomes an observation and mutates temporal state
        // (`sourceIndex`, the session, the decoder), so a failure must reset the session instead of just
        // dropping the frame.
        context.phase = AnalyzerPhase.SESSION
        val observation = PhoneRawObservation(
            sourceIndex = sourceIndex++,
            timestampMs = timestampNs / 1_000_000.0,
            sourceWidth = prepared.transform.sourceWidth,
            sourceHeight = prepared.transform.sourceHeight,
            handXy = arrayOf(left.xy, right.xy),
            handJointValid = arrayOf(left.valid, right.valid),
            handProposalSupport = arrayOf(left.proposalSupport, right.proposalSupport),
            handPresence = floatArrayOf(left.presence, right.presence),
            handObserved = booleanArrayOf(left.observed, right.observed),
            handProposalPresent = booleanArrayOf(left.proposalPresent, right.proposalPresent),
            handRoiCenterSide = arrayOf(roiValues(left.roi), roiValues(right.roi)),
            bodyXy = bodyXy,
            bodySupport = bodySupport,
            bodyValid = bodyValid,
            bodyAvailable = supported >= 6,
            candidatePreprocessMs = (preprocessEnded - started) / 1_000_000.0,
            candidatePoseInferenceMs = pose.inferenceMs,
            candidatePoseDecodeMs = pose.decodeMs,
            candidateTotalMs = (SystemClock.elapsedRealtimeNanos() - started) / 1_000_000.0,
        )
        // Optional experimental owner taps the very same evidence/RGB before disposal.
        // WORD cannot commit while this owner is active; perception itself is unchanged.
        val spellingOwner = ownsObservation?.invoke(observation, image) == true
        val update = if (spellingOwner) null else session.consume(observation)
        val processedFps = fps.tick()
        if (update != null && update.decoderState != lastDecoderState) {
            Log.i(TAG, "state package=${session.packageId.name} index=${observation.sourceIndex} " +
                "decoder=${update.decoderState} fps=${"%.1f".format(processedFps)}")
            lastDecoderState = update.decoderState
        }
        val overlay = PhoneOverlayFrame(
            observation.sourceWidth, observation.sourceHeight,
            observation.handXy, observation.handJointValid, observation.handObserved,
            observation.handPresence, observation.handRoiCenterSide,
            observation.bodyXy, observation.bodySupport, observation.bodyValid,
        )
        onResult(FrameResult(
            hands = null,
            pose = null,
            imageWidth = observation.sourceWidth,
            imageHeight = observation.sourceHeight,
            fps = processedFps,
            isFrontCamera = true,
            qualityLabel = if (spellingOwner) "FINGERSPELL" else session.packageId.name,
            poseEveryN = 1,
            recognition = update?.state ?: com.example.apphear.pipeline.recognition.RecognitionState.Idle,
            phoneOverlay = overlay,
            phoneReady = sourceIndex >= 4 && session.isReadyForDisplay,
            phoneSentence = session.sentenceText,
            recognitionEvidence = update?.evidence,
        ))
        val completedNs = SystemClock.elapsedRealtimeNanos()
        recordStageTimings(preprocessEnded - started, pose, handsEnded - handsStarted, left, right, update, completedNs - started)
        if (BuildConfig.RECOGNITION_V3_PROFILE_ENABLED && profileCount++ < 240) {
            // Bounded opt-in trace, identical in both A/B arms. No arrays/tensors retained.
            Log.i("AppHearV3", org.json.JSONObject()
                .put("schema_version", "apphear.perception_v3_timing.v1")
                .put("v3_parallel_hands", parallelHands).put("hands_parallel_this_frame", bothProposed)
                .put("source_index", observation.sourceIndex)
                .put("capture_timestamp_ns", timestampNs)
                .put("completed_timestamp_ns", completedNs)
                .put("source_width", observation.sourceWidth).put("source_height", observation.sourceHeight)
                .put("rotation_degrees", image.imageInfo.rotationDegrees)
                .put("newly_measured", true).put("reused", false)
                .put("owner", if (spellingOwner) "FINGERSPELL" else "WORD")
                .put("preprocess_ms", observation.candidatePreprocessMs)
                .put("pose_inference_and_output_ms", pose.inferenceMs)
                .put("pose_decode_ms", pose.decodeMs)
                .put("hand_crop_ms", left.cropMs + right.cropMs)
                .put("hand_inference_ms", left.inferenceMs + right.inferenceMs)
                .put("hands_wall_ms", (handsEnded - handsStarted) / 1_000_000.0)
                .put("perception_ms", observation.candidateTotalMs)
                .put("analyzer_ms", (completedNs - started) / 1_000_000.0)
                .put("body_valid_points", supported)
                .put("hands_observed", listOf(left, right).count { it.observed })
                .put("hand_valid_points", left.valid.count { it } + right.valid.count { it })
                .put("java_heap_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
                .put("native_heap_bytes", android.os.Debug.getNativeHeapAllocatedSize())
                .toString())
        }
    }

    /** Phase 2 stage timings. Array writes only; hands that were not run are not sampled as zeros. */
    private fun recordStageTimings(
        preprocessNs: Long, pose: DWPoseTRunner.Result, handsWallNs: Long, left: HandFrame, right: HandFrame,
        update: PhoneProductionSession.Update?, totalNs: Long,
    ) {
        val m = metrics
        m.record(DetectionStage.PREPROCESS, preprocessNs / 1_000_000.0)
        m.record(DetectionStage.POSE, pose.inferenceMs)
        m.record(DetectionStage.POSE_DECODE, pose.decodeMs)
        m.record(DetectionStage.HANDS_WALL, handsWallNs / 1_000_000.0)
        if (left.proposalPresent) m.record(DetectionStage.LEFT_HAND, left.inferenceMs)
        if (right.proposalPresent) m.record(DetectionStage.RIGHT_HAND, right.inferenceMs)
        if (left.proposalPresent || right.proposalPresent) m.record(DetectionStage.HAND_CROP, left.cropMs + right.cropMs)
        if (update != null) {
            m.record(DetectionStage.SEGMENTER, update.s2InvocationMs)
            update.recognitionInvocationMs?.let { m.record(DetectionStage.RECOGNIZER, it) }
        }
        val totalMs = totalNs / 1_000_000.0
        m.record(DetectionStage.FRAME_TOTAL, totalMs)
        m.frameProcessed(totalMs)
    }

    private fun logFault(report: FaultReport) {
        // Codes and phases only: no frame content, no words, no free-form messages.
        Log.w(TAG, "analyzer_fault code=${report.code} type=${report.errorType} class=${report.faultClass} " +
            "phase=${report.phase} action=${report.action} inWindow=${report.faultsInWindow}" +
            (report.escalation?.let { " escalation=$it" } ?: ""))
    }

    private fun reportMetrics() {
        try {
            Log.i(TAG_DETECT, metrics.snapshot().toLogLine())
        } catch (_: Throwable) {
            // diagnostics only
        }
    }

    /** Recovery reset, run by the supervisor inside [analyze]: same state a camera generation change clears. */
    private fun resetAfterFault() {
        session.resetTemporalSession()
        sourceIndex = 0
        lastTimestampNs = Long.MIN_VALUE
        lastDecoderState = null
    }

    private fun runHand(
        prepared: PerceptionVNextNativePreprocessor,
        decoded: PerceptionVNextMath.Decoded,
        start: Int,
        runner: HandRefinerRunner = handRunner,
        output: java.nio.ByteBuffer = prepared.handInput,
    ): HandFrame {
        val support = FloatArray(21) { decoded.support[start + it] }
        val roi = PerceptionVNextMath.handRoi(decoded, start, prepared.transform)
            ?: return HandFrame(FloatArray(42), BooleanArray(21), false,
                Float.NaN, false, support, null)
        val cropStarted = SystemClock.elapsedRealtimeNanos()
        val crop = prepared.crop(roi, output)
        val cropMs = (SystemClock.elapsedRealtimeNanos() - cropStarted) / 1_000_000.0
        val result = runner.run(crop, roi)
        return HandFrame(result.xySource, result.valid, result.observed, result.presence,
            true, support, roi, cropMs, result.inferenceMs)
    }

    private fun roiValues(roi: PerceptionVNextMath.HandRoi?): FloatArray =
        roi?.let { floatArrayOf(it.centerX, it.centerY, it.side) } ?: FloatArray(3)

    @Synchronized
    fun resetTemporalSession() {
        if (closed) return
        session.resetTemporalSession()
        sourceIndex = 0
        lastTimestampNs = Long.MIN_VALUE
        lastDecoderState = null
    }

    @Synchronized
    override fun close() {
        if (closed) return
        closed = true
        reporter?.shutdownNow()
        handPair?.close()
        preprocessor?.close()
        rightHandRunner?.close()
        handRunner.close()
        poseRunner.close()
    }

    private companion object {
        const val TAG = "AppHearPhone"
        const val TAG_DETECT = "AppHearDetect"
        const val REPORT_PERIOD_S = 30L
        /** The AE rate RecognitionActivity requests for the front camera (the optional 30 fps rear path differs). */
        const val NOMINAL_CAMERA_FPS = 15.0
    }
}
