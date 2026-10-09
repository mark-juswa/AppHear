package com.example.apphear.perceptionvnext

import android.graphics.BitmapFactory
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.apphear.BuildConfig
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.Executors

/** Bounded exact-PNG Android/offline parity runner. It never loads a recognizer. */
class PerceptionVNextFixtureActivity : AppCompatActivity() {
    private data class Hand(
        val roi: PerceptionVNextMath.HandRoi?,
        val xy: FloatArray,
        val valid: BooleanArray,
        val presence: Float?,
        val handedness: Float?,
        val observed: Boolean,
    )

    private val worker = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!BuildConfig.PERCEPTION_VNEXT_ENABLED || !intent.getBooleanExtra(EXTRA_ENABLED, false)) {
            finishWithError("VNEXT_FIXTURE_DISABLED")
            return
        }
        worker.execute(::runFixture)
    }

    private fun runFixture() {
        val root = File(requireNotNull(getExternalFilesDir(null)), ROOT_NAME)
        val manifestFile = File(root, "fixture_manifest.json")
        val outputFile = File(root, "android_raw_frames.jsonl")
        try {
            require(manifestFile.isFile) { "VNEXT_FIXTURE_MANIFEST_MISSING" }
            val manifest = JSONObject(manifestFile.readText())
            require(manifest.getString("schema") == "APPHEAR_VNEXT_PARITY_FIXTURE_V1")
            val rows = manifest.getJSONArray("frames")
            require(rows.length() in 1..32) { "VNEXT_FIXTURE_BOUNDS" }
            val dwpose = DWPoseTRunner(this)
            val refiner = HandRefinerRunner(this)
            this.refiner = refiner
            try {
                outputFile.bufferedWriter().use { writer ->
                    for (index in 0 until rows.length()) {
                        val spec = rows.getJSONObject(index)
                        val image = File(root, spec.getString("filename"))
                        require(image.isFile && sha256(image) == spec.getString("sha256")) {
                            "VNEXT_FIXTURE_IMAGE_IDENTITY:${spec.getString("frame_id")}" 
                        }
                        val bitmap = requireNotNull(BitmapFactory.decodeFile(image.absolutePath)) {
                            "VNEXT_FIXTURE_DECODE:${spec.getString("frame_id")}" 
                        }
                        PerceptionVNextBitmapPreprocessor(bitmap).use { prepared ->
                            val pose = dwpose.run(prepared.poseInput, prepared.transform)
                            val left = hand(prepared, pose.decoded, PerceptionVNextMath.LEFT_HAND_START)
                            val right = hand(prepared, pose.decoded, PerceptionVNextMath.RIGHT_HAND_START)
                            writer.appendLine(
                                frameJson(spec, prepared.transform, pose.decoded, left, right).toString(),
                            )
                        }
                        bitmap.recycle()
                    }
                }
            } finally {
                dwpose.close()
                refiner.close()
                this.refiner = null
            }
            File(root, "android_status.json").writeText(
                JSONObject()
                    .put("status", "PASS")
                    .put("frames", rows.length())
                    .put("raw_schema", RAW_SCHEMA)
                    .put("recognizer_connected", false)
                    .toString(2),
            )
        } catch (error: Throwable) {
            File(root, "android_status.json").writeText(
                JSONObject().put("status", "FAIL").put("error", error.stackTraceToString()).toString(2),
            )
        } finally {
            runOnUiThread { finish() }
        }
    }

    private fun hand(
        prepared: PerceptionVNextBitmapPreprocessor,
        decoded: PerceptionVNextMath.Decoded,
        start: Int,
    ): Hand {
        val roi = PerceptionVNextMath.handRoi(decoded, start, prepared.transform)
            ?: return Hand(null, FloatArray(42) { Float.NaN }, BooleanArray(21), null, null, false)
        val result = requireNotNull(refiner).run(prepared.crop(roi), roi)
        return Hand(
            roi,
            result.xySource.copyOf(),
            result.valid.copyOf(),
            result.presence,
            result.handednessDiagnostic,
            result.observed,
        )
    }

    private var refiner: HandRefinerRunner? = null

    private fun frameJson(
        spec: JSONObject,
        transform: PerceptionVNextMath.Transform,
        decoded: PerceptionVNextMath.Decoded,
        left: Hand,
        right: Hand,
    ): JSONObject {
        val bodyXY = FloatArray(PerceptionVNextMath.BODY_POINTS * 2)
        val bodySupport = FloatArray(PerceptionVNextMath.BODY_POINTS)
        val bodyValid = BooleanArray(PerceptionVNextMath.BODY_POINTS)
        for ((local, point) in PerceptionVNextMath.bodyIndices.withIndex()) {
            bodyXY[local * 2] = decoded.xy[point * 2]
            bodyXY[local * 2 + 1] = decoded.xy[point * 2 + 1]
            bodySupport[local] = decoded.support[point]
            bodyValid[local] = PerceptionVNextMath.bodyPointValid(
                bodyXY[local * 2],
                bodyXY[local * 2 + 1],
                bodySupport[local],
                transform,
            )
        }
        return JSONObject()
            .put("schema", RAW_SCHEMA)
            .put("frame_id", spec.getString("frame_id"))
            .put("source_frame_identity", spec.getString("sha256"))
            .put("frame_index", spec.getInt("frame_index"))
            .put("timestamp_ms", spec.getDouble("timestamp_ms"))
            .put("timestamp_source", spec.optString("timestamp_source", "FIXTURE_MANIFEST"))
            .put("image_semantics", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("source_width", transform.sourceWidth)
            .put("source_height", transform.sourceHeight)
            .put("left_hand", handJson(left, decoded, PerceptionVNextMath.LEFT_HAND_START))
            .put("right_hand", handJson(right, decoded, PerceptionVNextMath.RIGHT_HAND_START))
            .put(
                "body",
                JSONObject()
                    .put("indices", JSONArray(PerceptionVNextMath.bodyIndices.toList()))
                    .put("xy_source", floats(bodyXY))
                    .put("support", floats(bodySupport))
                    .put("valid", booleans(bodyValid))
                    .put("available", bodyValid.count { it } >= 6),
            )
            .put("current_frame_only", true)
            .put("synthetic_depth", false)
    }

    private fun handJson(
        hand: Hand,
        decoded: PerceptionVNextMath.Decoded,
        start: Int,
    ): JSONObject = JSONObject()
        .put("anatomical_slot", if (start == PerceptionVNextMath.LEFT_HAND_START) "LEFT" else "RIGHT")
        .put("proposal_present", hand.roi != null)
        .put("roi_center_side_source", hand.roi?.let {
            floats(floatArrayOf(it.centerX, it.centerY, it.side))
        } ?: JSONObject.NULL)
        .put("proposal_support", floats(FloatArray(21) { decoded.support[start + it] }))
        .put("xy_source", floats(hand.xy))
        .put("joint_valid", booleans(hand.valid))
        .put("presence", hand.presence ?: JSONObject.NULL)
        .put("handedness_diagnostic", hand.handedness ?: JSONObject.NULL)
        .put("observed", hand.observed)

    private fun floats(values: FloatArray): JSONArray = JSONArray().also { output ->
        values.forEach { output.put(if (it.isFinite()) it.toDouble() else JSONObject.NULL) }
    }

    private fun booleans(values: BooleanArray): JSONArray = JSONArray().also { output ->
        values.forEach(output::put)
    }

    private fun finishWithError(message: String) {
        val root = File(requireNotNull(getExternalFilesDir(null)), ROOT_NAME).also { it.mkdirs() }
        File(root, "android_status.json").writeText(
            JSONObject().put("status", "FAIL").put("error", message).toString(2),
        )
        finish()
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_ENABLED = "perception_vnext_enabled"
        const val ROOT_NAME = "perception_vnext_recognition_utility_236_01"
        const val RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
    }
}

private fun sha256(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    file.inputStream().use { input ->
        val block = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(block)
            if (count < 0) break
            digest.update(block, 0, count)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
