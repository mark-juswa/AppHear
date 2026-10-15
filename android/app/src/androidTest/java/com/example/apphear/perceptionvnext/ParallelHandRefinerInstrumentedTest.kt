package com.example.apphear.perceptionvnext

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** Real recorded pixels; verifies native crop concurrency + real CPU interpreters on Android. */
class ParallelHandRefinerInstrumentedTest {
    @Test fun sameRecordedFramesPreserveCropsCoordinatesAndValidity() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val fixtures = instrumentation.context.assets
        val context = instrumentation.targetContext
        val manifest = JSONObject(fixtures.open("v3/manifest.json").bufferedReader().use { it.readText() })
        val rows = manifest.getJSONArray("fixtures")
        var comparisons = 0
        HandRefinerRunner(context).use { first -> HandRefinerRunner(context).use { second ->
            CurrentFrameHandPair().use { pair ->
                for (index in 0 until rows.length()) {
                    val row = rows.getJSONObject(index)
                    val width = row.getInt("width")
                    val height = row.getInt("height")
                    val bytes = fixtures.open("v3/${row.getString("asset")}").use { it.readBytes() }
                    val hash = MessageDigest.getInstance("SHA-256").digest(bytes)
                        .joinToString("") { "%02x".format(it) }
                    assertEquals(row.getString("sha256"), hash)
                    val source = buffer(bytes.size).put(bytes).apply { rewind() }
                    val handle = PerceptionVNextNative.create(width, height, width * 4, 4, 0)
                    try {
                        PerceptionVNextNative.preprocess(handle, source, 0, bytes.size, buffer(3 * 256 * 192 * 4))
                        val rois = row.getJSONArray("rois")
                        fun roi(side: Int): PerceptionVNextMath.HandRoi? {
                            if (rois.isNull(side)) return null
                            val p = rois.getJSONObject(side)
                            val xy = p.getJSONArray("center_xy_source")
                            return PerceptionVNextMath.HandRoi(xy.getDouble(0).toFloat(),
                                xy.getDouble(1).toFloat(), p.getDouble("side_source_px").toFloat(),
                                width, height, p.getInt("support_count_0p10"))
                        }
                        val leftRoi = roi(0)
                        val rightRoi = roi(1)
                        val leftBuffer = buffer(224 * 224 * 3 * 4)
                        val rightBuffer = buffer(leftBuffer.capacity())
                        fun crop(r: PerceptionVNextMath.HandRoi, b: ByteBuffer) {
                            PerceptionVNextNative.crop(handle, r.centerX, r.centerY, r.side, b)
                            b.rewind()
                        }
                        fun serial(r: PerceptionVNextMath.HandRoi?, b: ByteBuffer): HandRefinerRunner.Result? =
                            r?.let { crop(it, b); first.run(b, it) }
                        val serialLeft = serial(leftRoi, leftBuffer)
                        val serialRight = serial(rightRoi, rightBuffer)
                        val leftBytes = ByteArray(leftBuffer.capacity()).also { leftBuffer.duplicate().get(it) }
                        val rightBytes = ByteArray(rightBuffer.capacity()).also { rightBuffer.duplicate().get(it) }
                        val actual = if (leftRoi != null && rightRoi != null) pair.run({
                            crop(leftRoi, leftBuffer); first.run(leftBuffer, leftRoi)
                        }, {
                            crop(rightRoi, rightBuffer); second.run(rightBuffer, rightRoi)
                        }) else Pair(serial(leftRoi, leftBuffer), serial(rightRoi, rightBuffer))
                        for ((expected, value) in listOf(serialLeft to actual.first, serialRight to actual.second)) {
                            if (expected == null) assertNull(value) else {
                                val measured = requireNotNull(value)
                                assertArrayEquals(expected.xySource, measured.xySource, 0f)
                                assertTrue(expected.valid.contentEquals(measured.valid))
                                assertEquals(expected.presence, measured.presence, 0f)
                                assertEquals(expected.handednessDiagnostic, measured.handednessDiagnostic, 0f)
                                assertEquals(expected.observed, measured.observed)
                                comparisons++
                            }
                        }
                        assertArrayEquals(leftBytes, ByteArray(leftBuffer.capacity()).also { leftBuffer.duplicate().get(it) })
                        assertArrayEquals(rightBytes, ByteArray(rightBuffer.capacity()).also { rightBuffer.duplicate().get(it) })
                    } finally { PerceptionVNextNative.destroy(handle) }
                }
            }
        } }
        assertTrue(comparisons > 0)
        context.filesDir.resolve("recognition_v3_recorded_parity.json").writeText(JSONObject()
            .put("status", "PASS").put("frames", rows.length()).put("hand_outputs", comparisons)
            .put("accuracy_claim", "NONE").toString(2))
    }

    private fun buffer(bytes: Int): ByteBuffer = ByteBuffer.allocateDirect(bytes).order(ByteOrder.nativeOrder())
}
