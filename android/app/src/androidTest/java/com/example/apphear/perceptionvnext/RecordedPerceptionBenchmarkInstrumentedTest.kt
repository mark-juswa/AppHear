package com.example.apphear.perceptionvnext

import android.os.Debug
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** Paired real-phone compute diagnostic. Replayed pixels are never called live observations. */
class RecordedPerceptionBenchmarkInstrumentedTest {
    @Test fun pairedCurrentFrameComputeAndOutputParity() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val assets = instrumentation.context.assets
        val fixtures = JSONObject(assets.open("v3/manifest.json").bufferedReader().use { it.readText() })
            .getJSONArray("fixtures")
        val width = fixtures.getJSONObject(0).getInt("width")
        val height = fixtures.getJSONObject(0).getInt("height")
        val source = buffer(width * height * 4)
        val poseInput = buffer(3 * 256 * 192 * 4)
        val leftInput = buffer(224 * 224 * 3 * 4)
        val rightInput = buffer(leftInput.capacity())
        val transform = PerceptionVNextMath.transform(width, height)
        val handle = PerceptionVNextNative.create(width, height, width * 4, 4, 0)
        val records = JSONArray()
        var compared = 0
        val beforePss = Debug.getPss()
        try {
            DWPoseTRunner(context).use { poseRunner ->
                HandRefinerRunner(context).use { first -> HandRefinerRunner(context).use { second ->
                    CurrentFrameHandPair().use { pair ->
                        // First full pass warms both interpreters. Alternate arm order thereafter.
                        repeat(4) { repetition ->
                            for (index in 0 until fixtures.length()) {
                                val fixture = fixtures.getJSONObject(index)
                                assertEquals(width, fixture.getInt("width"))
                                assertEquals(height, fixture.getInt("height"))
                                val bytes = assets.open("v3/${fixture.getString("asset")}").use { it.readBytes() }
                                val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
                                    .joinToString("") { "%02x".format(it) }
                                assertEquals(fixture.getString("sha256"), sha)
                                source.rewind(); source.put(bytes); source.rewind()
                                val preprocessStart = SystemClock.elapsedRealtimeNanos()
                                PerceptionVNextNative.preprocess(handle, source, 0, bytes.size, poseInput)
                                poseInput.rewind()
                                val preprocessMs = elapsed(preprocessStart)
                                val pose = poseRunner.run(poseInput, transform)
                                val left = PerceptionVNextMath.handRoi(pose.decoded,
                                    PerceptionVNextMath.LEFT_HAND_START, transform)
                                val right = PerceptionVNextMath.handRoi(pose.decoded,
                                    PerceptionVNextMath.RIGHT_HAND_START, transform)
                                val handCount = listOf(left, right).count { it != null }
                                fun refine(roi: PerceptionVNextMath.HandRoi?, runner: HandRefinerRunner,
                                    input: ByteBuffer): HandRefinerRunner.Result? = roi?.let {
                                    PerceptionVNextNative.crop(handle, it.centerX, it.centerY, it.side, input)
                                    input.rewind()
                                    runner.run(input, it)
                                }
                                val outputs = mutableMapOf<String,
                                    Pair<HandRefinerRunner.Result?, HandRefinerRunner.Result?>>()
                                val order = if (repetition % 2 == 0) listOf("baseline", "v3")
                                    else listOf("v3", "baseline")
                                for (arm in order) {
                                    val started = SystemClock.elapsedRealtimeNanos()
                                    val result = if (arm == "v3" && handCount == 2) pair.run(
                                        { refine(left, first, leftInput) },
                                        { refine(right, second, rightInput) },
                                    ) else Pair(refine(left, first, leftInput), refine(right, first, leftInput))
                                    val handWallMs = elapsed(started)
                                    outputs[arm] = result
                                    records.put(JSONObject().put("arm", arm).put("repetition", repetition)
                                        .put("warmup", repetition == 0).put("fixture", index)
                                        .put("recorded_capture_timestamp_ns", fixture.getLong("timestamp_ns"))
                                        .put("condition", fixture.getString("condition"))
                                        .put("proposals", handCount).put("preprocess_ms", preprocessMs)
                                        .put("pose_inference_and_output_ms", pose.inferenceMs)
                                        .put("pose_decode_ms", pose.decodeMs).put("hands_wall_ms", handWallMs)
                                        .put("hand_inference_sum_ms", (result.first?.inferenceMs ?: 0.0) +
                                            (result.second?.inferenceMs ?: 0.0))
                                        .put("hands_observed", listOf(result.first, result.second)
                                            .count { it?.observed == true }))
                                }
                                val a = requireNotNull(outputs["baseline"])
                                val b = requireNotNull(outputs["v3"])
                                for ((expected, actual) in listOf(a.first to b.first, a.second to b.second)) {
                                    if (expected == null) assertNull(actual) else {
                                        val value = requireNotNull(actual)
                                        assertArrayEquals(expected.xySource, value.xySource, 0f)
                                        assertTrue(expected.valid.contentEquals(value.valid))
                                        assertEquals(expected.presence, value.presence, 0f)
                                        assertEquals(expected.handednessDiagnostic, value.handednessDiagnostic, 0f)
                                        assertEquals(expected.observed, value.observed)
                                        compared++
                                    }
                                }
                            }
                        }
                    }
                } }
            }
        } finally { PerceptionVNextNative.destroy(handle) }
        context.filesDir.resolve("recognition_v3_recorded_benchmark.json").writeText(JSONObject()
            .put("schema_version", "apphear.v3.android_recorded_compute.v1")
            .put("status", "PASS").put("fixtures", fixtures.length()).put("compared_hand_outputs", compared)
            .put("scope", "paired hand scheduling; shared freshly inferred DWPose per recorded frame")
            .put("pss_before_kb", beforePss).put("pss_after_kb", Debug.getPss())
            .put("pss_is_not_incremental_production_cost", true)
            .put("live_observation_fps", "NOT_MEASURED").put("accuracy_claim", "NONE")
            .put("records", records).toString(2))
    }

    private fun buffer(bytes: Int): ByteBuffer = ByteBuffer.allocateDirect(bytes).order(ByteOrder.nativeOrder())
    private fun elapsed(start: Long): Double = (SystemClock.elapsedRealtimeNanos() - start) / 1e6
}
