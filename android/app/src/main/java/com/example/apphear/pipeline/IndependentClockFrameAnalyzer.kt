package com.example.apphear.pipeline

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.ImageProxy
import com.example.apphear.pipeline.diagnostics.A1Diagnostics
import com.example.apphear.pipeline.diagnostics.RuD1Diagnostics
import com.example.apphear.pipeline.diagnostics.RuD1FrameObservation
import com.example.apphear.pipeline.recognition.LandmarkAdapter
import com.example.apphear.pipeline.recognition.RecognitionPipeline
import com.example.apphear.pipeline.recognition.RecognitionState
import com.example.apphear.pipeline.recognition.RuntimeConfig
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import kotlin.system.measureNanoTime

/**
 * A1 experiment: hand, pose, and the stateful recognition consumer have independent capacity-one
 * latest-only clocks. This class is reachable only through a debug-only, default-off flag.
 *
 * Image ownership: ImageProxy belongs to analyze() and is closed after conversion. The upright
 * Bitmap is immutable and shared read-only through a reference-counted lease, matching the stable
 * analyzer's already-proven concurrent hand/pose reads. No Bitmap.recycle() or MPImage.close() is
 * performed. Each pending/in-flight packet owns one lease reference; replacement, completion, or
 * shutdown releases it. The final release merely drops the strong reference for normal GC.
 */
class IndependentClockFrameAnalyzer(
    private val landmarkers: LandmarkerBundle,
    private val isFrontCamera: Boolean,
    private val recognizer: RecognitionPipeline?,
    private val runtime: RuntimeConfig,
    private val maxPoseAgeNs: Long,
    private val ruD1: RuD1Diagnostics? = null,
    private val diagnostics: A1Diagnostics,
    private val onResult: (FrameResult) -> Unit,
) : CloseableFrameAnalyzer {

    init {
        require(maxPoseAgeNs > 0L) { "A1 requires a positive Baseline-derived max pose age" }
    }

    private data class FrameLease(val bitmap: Bitmap) {
        private val references = AtomicInteger(1)

        fun retain(): FrameLease {
            check(references.incrementAndGet() > 1) { "retained a released frame lease" }
            return this
        }

        fun release() {
            check(references.decrementAndGet() >= 0) { "frame lease released more than owned" }
        }
    }

    private data class FramePacket(
        val sourceTimestampNs: Long,
        val analyzerArrivalNs: Long,
        val lease: FrameLease,
    )

    private data class HandObservation(
        val sourceTimestampNs: Long,
        val analyzerArrivalNs: Long,
        val inferenceEndNs: Long,
        val publicationNs: Long,
        val result: HandLandmarkerResult,
        val lease: FrameLease,
    )

    private val closed = AtomicBoolean(false)
    private val sourceSequence = AtomicLong(0L)
    private val processedFrames = AtomicLong(0L)
    private val discardedFrames = AtomicLong(0L)
    @Volatile private var cameraRate = 0.0
    private val cameraFps = FpsTracker()
    private val processedFps = FpsTracker()
    private val lowFps = LowFpsMonitor(
        runtime.lowFpsEnterBelow,
        runtime.lowFpsExitAbove,
        runtime.lowFpsConsecutiveFrames,
    )
    private val poseEveryN = (recognizer?.poseCadenceEveryN ?: 2).coerceAtLeast(1)
    private val poseStore = CausalPoseStore<PoseLandmarkerResult>()
    private val handExecutor = namedSingleThreadExecutor("apphear-a1-hand")
    private val poseExecutor = namedSingleThreadExecutor("apphear-a1-pose")
    private val consumerExecutor = namedSingleThreadExecutor("apphear-a1-consumer")

    private val handMailbox = LatestOnlyMailbox<FramePacket> { packet, reason ->
        discardedFrames.incrementAndGet()
        diagnostics.event(
            "HAND_MAILBOX_DISCARD",
            "source_ns" to packet.sourceTimestampNs,
            "reason" to reason.name,
        )
        packet.lease.release()
    }
    private val poseMailbox = LatestOnlyMailbox<FramePacket> { packet, reason ->
        discardedFrames.incrementAndGet()
        diagnostics.event(
            "POSE_MAILBOX_DISCARD",
            "source_ns" to packet.sourceTimestampNs,
            "reason" to reason.name,
        )
        packet.lease.release()
    }
    private val consumerMailbox = LatestOnlyMailbox<HandObservation> { observation, reason ->
        diagnostics.event(
            "JOIN_REJECTION",
            "hand_source_ns" to observation.sourceTimestampNs,
            "reason" to if (reason == A1DiscardReason.SUPERSEDED) {
                "SUPERSEDED_BY_FRESHER_HAND_RESULT"
            } else {
                "SHUTDOWN"
            },
        )
        observation.lease.release()
    }

    init {
        handExecutor.execute(::handLoop)
        poseExecutor.execute(::poseLoop)
        consumerExecutor.execute(::consumerLoop)
        diagnostics.event(
            "A1_START",
            "pose_every" to poseEveryN,
            "max_pose_age_ns" to maxPoseAgeNs,
            "image_ownership" to "IMMUTABLE_SHARED_LEASE_NO_EXPLICIT_RECYCLE",
        )
    }

    override fun analyze(image: ImageProxy) {
        val sourceNs = image.imageInfo.timestamp
        val arrivalNs = diagnostics.nowNs()
        diagnostics.event("CAMERA_DELIVERED", "source_ns" to sourceNs, "arrival_ns" to arrivalNs)
        cameraRate = cameraFps.tick()
        if (closed.get()) {
            diagnostics.event("ANALYZER_DROP", "source_ns" to sourceNs, "reason" to "SHUTDOWN")
            image.close()
            return
        }
        diagnostics.event("ANALYZER_ACCEPT", "source_ns" to sourceNs)

        val rotation = image.imageInfo.rotationDegrees
        val bitmap = try {
            diagnostics.event("CONVERSION_START", "source_ns" to sourceNs)
            lateinit var converted: Bitmap
            val conversionNs = measureNanoTime { converted = image.toBitmap() }
            diagnostics.event("CONVERSION_END", "source_ns" to sourceNs, "duration_ns" to conversionNs)
            diagnostics.event("ROTATION_START", "source_ns" to sourceNs)
            lateinit var upright: Bitmap
            val rotationNs = measureNanoTime { upright = rotate(converted, rotation) }
            diagnostics.event("ROTATION_END", "source_ns" to sourceNs, "duration_ns" to rotationNs)
            upright
        } catch (t: Throwable) {
            diagnostics.event(
                "ANALYZER_DROP",
                "source_ns" to sourceNs,
                "reason" to "CONVERSION_OR_ROTATION_EXCEPTION",
                "error" to t.javaClass.simpleName,
            )
            return
        } finally {
            image.close()
        }

        if (closed.get()) return
        val sequence = sourceSequence.getAndIncrement()
        val poseEligible = sequence % poseEveryN == 0L
        diagnostics.event(
            "POSE_ELIGIBILITY",
            "source_ns" to sourceNs,
            "eligible" to poseEligible,
            "pose_every" to poseEveryN,
        )

        val lease = FrameLease(bitmap)
        if (poseEligible) {
            val posePacket = FramePacket(sourceNs, arrivalNs, lease.retain())
            diagnostics.event("POSE_MAILBOX_ENQUEUE", "source_ns" to sourceNs)
            poseMailbox.offer(posePacket)
        }
        diagnostics.event("HAND_MAILBOX_ENQUEUE", "source_ns" to sourceNs)
        handMailbox.offer(FramePacket(sourceNs, arrivalNs, lease))
    }

    private fun handLoop() {
        while (!handMailbox.isClosed()) {
            val packet = takeOrNull(handMailbox) ?: break
            var ownershipTransferred = false
            try {
                diagnostics.event("HAND_WORKER_DEQUEUE", "source_ns" to packet.sourceTimestampNs)
                val image = BitmapImageBuilder(packet.lease.bitmap).build()
                val startNs = diagnostics.nowNs()
                diagnostics.event(
                    "HAND_INFERENCE_START",
                    "source_ns" to packet.sourceTimestampNs,
                    "start_ns" to startNs,
                )
                lateinit var result: HandLandmarkerResult
                val durationNs = measureNanoTime { result = landmarkers.detectHands(image) }
                val endNs = diagnostics.nowNs()
                diagnostics.event(
                    "HAND_INFERENCE_END",
                    "source_ns" to packet.sourceTimestampNs,
                    "start_ns" to startNs,
                    "end_ns" to endNs,
                    "duration_ns" to durationNs,
                )
                val publicationNs = diagnostics.nowNs()
                diagnostics.event(
                    "HAND_PUBLICATION",
                    "source_ns" to packet.sourceTimestampNs,
                    "publish_ns" to publicationNs,
                )
                val observation = HandObservation(
                    packet.sourceTimestampNs,
                    packet.analyzerArrivalNs,
                    endNs,
                    publicationNs,
                    result,
                    packet.lease,
                )
                consumerMailbox.offer(observation)
                // The mailbox callback owns rejection cleanup too, so ownership transfers even
                // when close races this offer.
                ownershipTransferred = true
            } catch (t: Throwable) {
                diagnostics.event(
                    "HAND_EXCEPTION",
                    "source_ns" to packet.sourceTimestampNs,
                    "error" to t.javaClass.simpleName,
                )
            } finally {
                if (!ownershipTransferred) packet.lease.release()
            }
        }
    }

    private fun poseLoop() {
        while (!poseMailbox.isClosed()) {
            val packet = takeOrNull(poseMailbox) ?: break
            try {
                diagnostics.event("POSE_WORKER_DEQUEUE", "source_ns" to packet.sourceTimestampNs)
                val image = BitmapImageBuilder(packet.lease.bitmap).build()
                val startNs = diagnostics.nowNs()
                diagnostics.event(
                    "POSE_INFERENCE_START",
                    "source_ns" to packet.sourceTimestampNs,
                    "start_ns" to startNs,
                )
                lateinit var result: PoseLandmarkerResult
                val durationNs = measureNanoTime { result = landmarkers.detectPose(image) }
                val endNs = diagnostics.nowNs()
                diagnostics.event(
                    "POSE_INFERENCE_END",
                    "source_ns" to packet.sourceTimestampNs,
                    "start_ns" to startNs,
                    "end_ns" to endNs,
                    "duration_ns" to durationNs,
                )
                poseStore.publish(TimestampedValue(packet.sourceTimestampNs, result))
                diagnostics.event(
                    "POSE_PUBLICATION",
                    "source_ns" to packet.sourceTimestampNs,
                    "publish_ns" to diagnostics.nowNs(),
                )
            } catch (t: Throwable) {
                diagnostics.event(
                    "POSE_EXCEPTION",
                    "source_ns" to packet.sourceTimestampNs,
                    "error" to t.javaClass.simpleName,
                )
            } finally {
                packet.lease.release()
            }
        }
    }

    private fun consumerLoop() {
        var lastConsumedSourceNs = Long.MIN_VALUE
        while (!consumerMailbox.isClosed()) {
            val observation = takeOrNull(consumerMailbox) ?: break
            try {
                if (observation.sourceTimestampNs <= lastConsumedSourceNs) {
                    diagnostics.event(
                        "JOIN_REJECTION",
                        "hand_source_ns" to observation.sourceTimestampNs,
                        "reason" to "ORDERING_VIOLATION",
                    )
                    continue
                }
                lastConsumedSourceNs = observation.sourceTimestampNs
                val join = poseStore.join(observation.sourceTimestampNs, maxPoseAgeNs)
                diagnostics.event(
                    "SYNCHRONIZER_JOIN",
                    "hand_source_ns" to observation.sourceTimestampNs,
                    "pose_source_ns" to join.pose?.sourceTimestampNs,
                    "pose_age_ns" to join.poseAgeNs,
                    "pose_fresh" to (join.pose?.sourceTimestampNs == observation.sourceTimestampNs),
                    "status" to join.status.name,
                )
                if (join.status != CausalJoinStatus.VALID) {
                    diagnostics.event(
                        "JOIN_REJECTION",
                        "hand_source_ns" to observation.sourceTimestampNs,
                        "reason" to join.status.name,
                    )
                    continue
                }
                consume(observation, checkNotNull(join.pose).value, checkNotNull(join.poseAgeNs))
            } catch (t: Throwable) {
                diagnostics.event(
                    "CONSUMER_EXCEPTION",
                    "source_ns" to observation.sourceTimestampNs,
                    "error" to t.javaClass.simpleName,
                )
            } finally {
                observation.lease.release()
            }
        }
    }

    private fun consume(
        observation: HandObservation,
        pose: PoseLandmarkerResult,
        poseAgeNs: Long,
    ) {
        val consumerStartNs = diagnostics.nowNs()
        diagnostics.event(
            "CONSUMER_START",
            "source_ns" to observation.sourceTimestampNs,
            "consumer_ns" to consumerStartNs,
            "hand_result_age_ns" to consumerStartNs - observation.inferenceEndNs,
            "source_to_s4_ns" to consumerStartNs - observation.analyzerArrivalNs,
            "pose_age_ns" to poseAgeNs,
        )
        val poseArray = LandmarkAdapter.pose(pose)
        val handsArray = LandmarkAdapter.hands(observation.result)
        val low = lowFps.active
        var recognition: RecognitionState? = null
        val recognitionNs = measureNanoTime {
            if (recognizer != null) recognition = recognizer.processFrame(poseArray, handsArray, low)
        }
        val fps = processedFps.tick()
        val count = processedFrames.incrementAndGet()
        val lowNow = lowFps.update(fps)
        diagnostics.event(
            "CONSUMER_END",
            "source_ns" to observation.sourceTimestampNs,
            "duration_ns" to recognitionNs,
            "s4_observation" to true,
            "processed_frames" to count,
        )

        val trace = recognizer?.lastRuD1Trace
        if (trace != null && ruD1?.isActive == true) {
            ruD1.record(
                RuD1FrameObservation(
                    timestampNs = observation.sourceTimestampNs,
                    processedFps = fps,
                    lowFpsUsed = low,
                    poseFresh = poseAgeNs == 0L,
                    handCount = detectedHandCount(handsArray),
                    leftHandPresent = slotPresent(handsArray, 0),
                    rightHandPresent = slotPresent(handsArray, 1),
                    posePresent = poseArray.any { !it.isNaN() },
                    leftWristVisibility = poseVisibility(poseArray, 15),
                    rightWristVisibility = poseVisibility(poseArray, 16),
                    leftElbowVisibility = poseVisibility(poseArray, 13),
                    rightElbowVisibility = poseVisibility(poseArray, 14),
                    leftShoulderVisibility = poseVisibility(poseArray, 11),
                    rightShoulderVisibility = poseVisibility(poseArray, 12),
                    pipeline = trace,
                ),
                observation.lease.bitmap,
            )
        }

        onResult(
            FrameResult(
                hands = observation.result,
                pose = pose,
                imageWidth = observation.lease.bitmap.width,
                imageHeight = observation.lease.bitmap.height,
                fps = fps,
                isFrontCamera = isFrontCamera,
                qualityLabel = if (poseEveryN == 1) "High" else "A1 Independent",
                poseEveryN = poseEveryN,
                recognition = recognition,
                cameraFps = cameraRate,
                droppedFrames = discardedFrames.get(),
                lowFpsActive = lowNow,
            ),
        )
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        diagnostics.event("A1_SHUTDOWN_START")
        handMailbox.close()
        poseMailbox.close()
        consumerMailbox.close()
        poseStore.clear()
        listOf(handExecutor, poseExecutor, consumerExecutor).forEach(ExecutorService::shutdown)
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(SHUTDOWN_TIMEOUT_SECONDS)
        listOf(handExecutor, poseExecutor, consumerExecutor).forEach { executor ->
            val remaining = (deadline - System.nanoTime()).coerceAtLeast(0L)
            if (!executor.awaitTermination(remaining, TimeUnit.NANOSECONDS)) {
                executor.shutdownNow()
                check(executor.awaitTermination(SHUTDOWN_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                    "A1 worker did not terminate; LandmarkerBundle must not be closed"
                }
            }
        }
        diagnostics.event("A1_SHUTDOWN_END")
    }

    private fun <T> takeOrNull(mailbox: LatestOnlyMailbox<T>): T? = try {
        mailbox.take()
    } catch (_: InterruptedException) {
        Thread.currentThread().interrupt()
        null
    }

    private fun rotate(bitmap: Bitmap, degrees: Int): Bitmap {
        if (degrees == 0) return bitmap
        val matrix = Matrix().apply { postRotate(degrees.toFloat()) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    private fun slotPresent(hands: FloatArray, slot: Int): Boolean = !hands[slot * 21 * 3].isNaN()

    private fun detectedHandCount(hands: FloatArray): Int =
        (if (slotPresent(hands, 0)) 1 else 0) + (if (slotPresent(hands, 1)) 1 else 0)

    private fun poseVisibility(pose: FloatArray, landmark: Int): Float? =
        pose[landmark * 4 + 3].takeIf { it.isFinite() }

    private companion object {
        const val SHUTDOWN_TIMEOUT_SECONDS = 5L

        fun namedSingleThreadExecutor(name: String): ExecutorService =
            Executors.newSingleThreadExecutor { runnable -> Thread(runnable, name) }
    }
}
