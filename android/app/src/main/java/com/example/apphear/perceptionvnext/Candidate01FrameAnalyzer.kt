package com.example.apphear.perceptionvnext

import android.content.Context
import android.os.SystemClock
import android.util.Log
import androidx.camera.core.ImageProxy
import com.example.apphear.pipeline.CloseableFrameAnalyzer
import com.example.apphear.pipeline.FpsTracker
import com.example.apphear.pipeline.FrameResult
import com.example.apphear.ui.PhoneOverlayFrame

/** Production CameraX bridge for the same current-frame Candidate01 path as the validated capture. */
internal class Candidate01FrameAnalyzer(
    context: Context,
    private val session: PhoneProductionSession,
    private val onResult: (FrameResult) -> Unit,
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
    )

    private val poseRunner = DWPoseTRunner(context)
    private val handRunner = HandRefinerRunner(context)
    private val fps = FpsTracker()
    private var preprocessor: PerceptionVNextNativePreprocessor? = null
    private var lastTimestampNs = Long.MIN_VALUE
    private var sourceIndex = 0
    private var lastDecoderState: PhoneDecoderState? = null
    private var closed = false
    private var failed = false

    @Synchronized
    override fun analyze(image: ImageProxy) {
        try {
            if (closed || failed) return
            val timestampNs = image.imageInfo.timestamp
            require(timestampNs > lastTimestampNs) { "APP_PHONE_NON_CHRONOLOGICAL_SOURCE_TIMESTAMP" }
            lastTimestampNs = timestampNs
            val started = SystemClock.elapsedRealtimeNanos()
            val prepared = preprocessor?.takeIf { it.compatible(image) }
                ?: PerceptionVNextNativePreprocessor(image).also { replacement ->
                    preprocessor?.close()
                    preprocessor = replacement
                }
            prepared.preprocess(image)
            val pose = poseRunner.run(prepared.poseInput, prepared.transform)
            val left = runHand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START)
            val right = runHand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START)
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
                candidatePoseInferenceMs = pose.inferenceMs,
                candidatePoseDecodeMs = pose.decodeMs,
                candidateTotalMs = (SystemClock.elapsedRealtimeNanos() - started) / 1_000_000.0,
            )
            val update = session.consume(observation)
            val processedFps = fps.tick()
            if (update.decoderState != lastDecoderState) {
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
                qualityLabel = session.packageId.name,
                poseEveryN = 1,
                recognition = update.state,
                phoneOverlay = overlay,
                phoneReady = sourceIndex >= 4 && session.isReady,
                phoneSentence = session.sentenceText,
            ))
        } catch (error: Throwable) {
            failed = true
            Log.e(TAG, "Causal recognition stopped; legacy fallback is disabled", error)
            onFailure(error)
        } finally {
            image.close()
        }
    }

    private fun runHand(
        prepared: PerceptionVNextNativePreprocessor,
        decoded: PerceptionVNextMath.Decoded,
        start: Int,
    ): HandFrame {
        val support = FloatArray(21) { decoded.support[start + it] }
        val roi = PerceptionVNextMath.handRoi(decoded, start, prepared.transform)
            ?: return HandFrame(FloatArray(42), BooleanArray(21), false,
                Float.NaN, false, support, null)
        val result = handRunner.run(prepared.crop(roi), roi)
        return HandFrame(result.xySource, result.valid, result.observed, result.presence,
            true, support, roi)
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
        preprocessor?.close()
        handRunner.close()
        poseRunner.close()
    }

    private companion object { const val TAG = "AppHearPhone" }
}
