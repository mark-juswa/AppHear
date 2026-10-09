package com.example.apphear.pipeline.diagnostics

import android.content.Context
import android.graphics.Bitmap
import android.os.Build
import com.example.apphear.BuildConfig
import com.example.apphear.pipeline.recognition.RuD1PipelineTrace
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.security.MessageDigest
import java.time.Instant
import java.time.format.DateTimeFormatter
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

data class RuD1Config(
    val enabled: Boolean,
    val maxEvidenceFrames: Int,
    val evidenceStride: Int,
    val evidenceWidth: Int,
    val jpegQuality: Int,
    val postReleaseFrames: Int,
) {
    companion object {
        fun load(context: Context): RuD1Config {
            val root = JSONObject(
                context.assets.open("recognition_config.json").bufferedReader().use { it.readText() },
            ).optJSONObject("runtime_diagnostics") ?: JSONObject()
            return RuD1Config(
                // RU-D1 is intentionally impossible to activate in a release build.
                enabled = BuildConfig.DEBUG &&
                    (BuildConfig.RU_D1_ENABLED || root.optBoolean("enabled", false)),
                maxEvidenceFrames = root.optInt("max_evidence_frames", 48).coerceIn(1, 96),
                evidenceStride = root.optInt("evidence_stride", 1).coerceAtLeast(1),
                evidenceWidth = root.optInt("evidence_width", 240).coerceIn(120, 480),
                jpegQuality = root.optInt("jpeg_quality", 70).coerceIn(40, 90),
                postReleaseFrames = root.optInt("post_release_frames", 8).coerceIn(1, 24),
            )
        }
    }
}

data class RuD1AttemptSpec(
    val gloss: String,
    val expectedHands: String,
    val signerId: String,
    val variant: String = "",
    val sessionId: String = "",
    val repetitionId: String = "",
    val captureOrder: Int = 0,
) {
    init {
        require(gloss.isNotBlank()) { "RU-D1 gloss is required" }
        require(expectedHands in EXPECTED_HANDS) {
            "RU-D1 expected_hands must be one, two, or variant-dependent"
        }
        require(signerId.isNotBlank()) { "RU-D1 signer_id is required" }
    }

    companion object {
        val EXPECTED_HANDS = setOf("one", "two", "variant-dependent")
    }
}

data class RuD1FrameObservation(
    val timestampNs: Long,
    val processedFps: Double,
    val lowFpsUsed: Boolean,
    val poseFresh: Boolean,
    val handCount: Int,
    val leftHandPresent: Boolean,
    val rightHandPresent: Boolean,
    val posePresent: Boolean,
    val leftWristVisibility: Float?,
    val rightWristVisibility: Float?,
    val leftElbowVisibility: Float?,
    val rightElbowVisibility: Float?,
    val leftShoulderVisibility: Float?,
    val rightShoulderVisibility: Float?,
    val pipeline: RuD1PipelineTrace,
)

/**
 * Minimal RU-D1 attempt controller and writer. It receives immutable observations after normal
 * recognition has completed; nothing in this class feeds back into S1-S7.
 */
class RuD1Diagnostics private constructor(
    private val context: Context,
    val config: RuD1Config,
) {
    private val io = Executors.newSingleThreadExecutor()
    private val evidence = RollingEvidenceBuffer(
        capacity = config.maxEvidenceFrames,
        postReleaseFrames = config.postReleaseFrames,
        dispose = Bitmap::recycle,
    )
    private val lock = Any()
    private var writer: BufferedWriter? = null
    private var attemptDirectory: File? = null
    private var attemptId: String? = null
    private var frameRows = 0

    val isActive: Boolean
        get() = synchronized(lock) { writer != null }

    fun startAttempt(spec: RuD1AttemptSpec): File {
        check(config.enabled) { "RU-D1 is disabled" }
        synchronized(lock) { check(writer == null) { "RU-D1 attempt already active" } }
        io.submit { evidence.clear() }.get(10, TimeUnit.SECONDS)

        val id = buildAttemptId(spec.gloss)
        val root = File(context.getExternalFilesDir(null), "ru_d1/$id")
        check(root.mkdirs()) { "Could not create RU-D1 attempt directory: $root" }
        check(File(root, "evidence").mkdirs()) { "Could not create RU-D1 evidence directory" }
        val traceWriter = BufferedWriter(OutputStreamWriter(FileOutputStream(File(root, "trace.jsonl")), Charsets.UTF_8))
        val manifestText = context.assets.open("model_manifest.json").bufferedReader().use { it.readText() }
        val manifest = JSONObject(manifestText)
        val metadata = JSONObject()
            .put("format_version", 2)
            .put("attempt_id", id)
            .put("ground_truth", spec.gloss)
            .put("expected_hands", spec.expectedHands)
            .put("signer_id", spec.signerId)
            .put("variant", spec.variant)
            .put("session_id", spec.sessionId)
            .put("repetition_id", spec.repetitionId)
            .put("capture_order", spec.captureOrder)
            .put("started_utc", Instant.now().toString())
            .put("schema_version", manifest.getString("schema_version"))
            .put("time_window", manifest.getInt("time_window"))
            .put("feature_dim", manifest.getInt("feature_dim"))
            .put("model_manifest_sha256", assetSha256("model_manifest.json"))
            .put("model_sha256", assetSha256("streaming.tflite"))
            .put("recognition_config_sha256", assetSha256("recognition_config.json"))
            .put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
            .put("android_sdk", Build.VERSION.SDK_INT)
            .put("app_version", BuildConfig.VERSION_NAME)
            .put("evidence_stride", config.evidenceStride)
            .put("max_evidence_frames", config.maxEvidenceFrames)
            .put("evidence_mode", "rolling_sign_centered")
            .put("post_release_frames", config.postReleaseFrames)
        File(root, "metadata.json").writeText(metadata.toString(2), Charsets.UTF_8)

        synchronized(lock) {
            writer = traceWriter
            attemptDirectory = root
            attemptId = id
            frameRows = 0
        }
        return root
    }

    fun stopAttempt(): File? {
        val stoppedWriter: BufferedWriter
        val directory = synchronized(lock) {
            val current = attemptDirectory ?: return null
            stoppedWriter = writer ?: return null
            writer = null
            attemptDirectory = null
            attemptId = null
            current
        }
        io.submit {
            stoppedWriter.flush()
            stoppedWriter.close()
            val retained = evidence.drain()
            retained.forEach { frame ->
                FileOutputStream(
                    File(directory, "evidence/frame_%06d.jpg".format(frame.frameId)),
                ).use { output ->
                    frame.payload.compress(Bitmap.CompressFormat.JPEG, config.jpegQuality, output)
                }
                frame.payload.recycle()
            }
            File(directory, "capture_complete.json").writeText(
                JSONObject()
                    .put("completed_utc", Instant.now().toString())
                    .put("trace_rows", frameRows)
                    .put("evidence_frames", retained.size)
                    .put("evidence_first_frame", retained.firstOrNull()?.frameId ?: -1)
                    .put("evidence_last_frame", retained.lastOrNull()?.frameId ?: -1)
                    .put("evidence_frozen_after_release", evidence.frozen)
                    .toString(2),
                Charsets.UTF_8,
            )
        }.get(10, TimeUnit.SECONDS)
        return directory
    }

    fun record(observation: RuD1FrameObservation, upright: Bitmap) {
        val frameId = observation.pipeline.frameId
        synchronized(lock) {
            val activeWriter = writer ?: return
            val id = attemptId ?: return
            attemptDirectory ?: return
            val bitmapCopy = if (frameId % config.evidenceStride == 0L) {
                upright.copy(Bitmap.Config.ARGB_8888, false)
            } else {
                null
            }
            // Enqueue while holding the same lock used by stopAttempt. The close barrier therefore
            // cannot overtake an accepted trace row.
            io.execute {
                val json = observation.toJson(id)
                activeWriter.write(json.toString())
                activeWriter.newLine()
                frameRows++
                if (bitmapCopy != null) {
                    val height = (bitmapCopy.height * (config.evidenceWidth.toDouble() / bitmapCopy.width))
                        .toInt().coerceAtLeast(1)
                    val scaled = Bitmap.createScaledBitmap(bitmapCopy, config.evidenceWidth, height, true)
                    if (scaled !== bitmapCopy) bitmapCopy.recycle()
                    evidence.observe(
                        frameId,
                        observation.pipeline.signingEvent.name == "RELEASE",
                        scaled,
                    )
                } else {
                    evidence.observe(
                        frameId,
                        observation.pipeline.signingEvent.name == "RELEASE",
                        null,
                    )
                }
            }
        }
    }

    fun close() {
        val stoppedWriter = synchronized(lock) {
            val current = writer
            writer = null
            attemptDirectory = null
            attemptId = null
            current
        }
        if (stoppedWriter != null) {
            io.execute {
                stoppedWriter.flush()
                stoppedWriter.close()
                evidence.clear()
            }
        }
        io.shutdown()
    }

    private fun assetSha256(name: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        context.assets.open(name).use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun buildAttemptId(gloss: String): String {
        val stamp = DateTimeFormatter.ISO_INSTANT.format(Instant.now())
            .replace(Regex("[^0-9]"), "")
            .take(17)
        val safe = gloss.uppercase(Locale.US).replace(Regex("[^A-Z0-9_-]"), "_")
        return "${stamp}_$safe"
    }

    companion object {
        fun create(context: Context): RuD1Diagnostics = RuD1Diagnostics(context, RuD1Config.load(context))
    }
}

private fun RuD1FrameObservation.toJson(attemptId: String): JSONObject {
    val p = pipeline
    val s5 = p.s5
    val s7 = p.s7
    return JSONObject()
        .put("attempt_id", attemptId)
        .put("frame_id", p.frameId)
        .put("timestamp_ns", timestampNs)
        .put("processed_fps", processedFps)
        .put("low_fps", lowFpsUsed)
        .put("pose_fresh", poseFresh)
        .put("hand_count", handCount)
        .put("left_hand_present", leftHandPresent)
        .put("right_hand_present", rightHandPresent)
        .put("pose_present", posePresent)
        .put("pose_visibility", JSONObject()
            .putFinite("left_wrist", leftWristVisibility)
            .putFinite("right_wrist", rightWristVisibility)
            .putFinite("left_elbow", leftElbowVisibility)
            .putFinite("right_elbow", rightElbowVisibility)
            .putFinite("left_shoulder", leftShoulderVisibility)
            .putFinite("right_shoulder", rightShoulderVisibility))
        .put("feature", p.feature.toJson())
        .put("mirrored", p.mirrored)
        .put("feature_blocks", JSONObject()
            .put("left_nonzero", p.feature.anyNonZero(0, 63))
            .put("right_nonzero", p.feature.anyNonZero(63, 126))
            .put("pose_nonzero", p.feature.anyNonZero(126, 258))
            .put("all_finite", p.feature.all { it.isFinite() }))
        .put("s5", JSONObject()
            .put("event", p.signingEvent.name)
            .put("signing", p.signing)
            .put("motion", s5.motion)
            .put("hands_seen", s5.handsSeen)
            .put("raised_gate", s5.raisedGate)
            .put("onset_candidate", s5.onsetCandidate)
            .put("onset_gap_used", s5.onsetGapUsed)
            .put("onset_gap_bridged_this_frame", s5.onsetGapBridgedThisFrame)
            .put("on_count", s5.onCount)
            .put("off_count", s5.offCount)
            .put("active_hand_gap_frames", s5.activeHandGapFrames)
            .put("release_by_hand_dropout", s5.releaseCausedByHandDropout))
        .put("s6", if (p.probabilities == null) JSONObject.NULL else JSONObject()
            .put("inference_index", p.inferenceIndex)
            .put("window_source_frames", p.windowSourceFrames.toJson())
            .put("window_sha256", p.windowSha256)
            .put("probabilities", p.probabilities.toJson()))
        .put("s7", JSONObject()
            .put("top1", s7.top1)
            .putFinite("evidence", s7.evidence)
            .put("margin", s7.margin)
            .put("streak", s7.streak)
            .put("committed", s7.committed)
            .put("reason", s7.reason)
            .put("committed_class", p.committedClass ?: JSONObject.NULL))
}

private fun FloatArray.toJson(): JSONArray = JSONArray().also { out -> forEach { out.put(it.toDouble()) } }
private fun LongArray.toJson(): JSONArray = JSONArray().also { out -> forEach { out.put(it) } }
private fun FloatArray.anyNonZero(start: Int, end: Int): Boolean =
    (start until end).any { this[it].isFinite() && this[it] != 0f }

private fun JSONObject.putFinite(name: String, value: Number?): JSONObject {
    val number = value?.toDouble()
    return put(name, if (number != null && number.isFinite()) number else JSONObject.NULL)
}
