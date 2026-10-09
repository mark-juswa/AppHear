package com.example.apphear.perceptionvnext

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/** Host-side preflight for the same debug-source Kotlin implementation used by device test. */
class RecognitionV2JvmParityTest {
    @Test
    fun frozenPythonRecognitionV2MatchesKotlin() {
        val root = listOf(
            File("app/src/debug/assets/phase4a_v2_parity"),
            File("src/debug/assets/phase4a_v2_parity"),
        ).first { File(it, "manifest.json").isFile }
        val manifest = JsonParser.parseString(File(root, "manifest.json").readText()).asJsonObject
        val errors = ArrayList<Double>()
        val conditionErrors = linkedMapOf(
            "dense" to ArrayList<Double>(),
            "phone_01_sparse" to ArrayList<Double>(),
        )
        val groupErrors = buildMap<String, ArrayList<Double>> {
            for (condition in conditionErrors.keys) for (group in RecognitionV2.FEATURE_GROUPS) {
                put("$condition:${group.name}", ArrayList())
            }
        }
        var worst = 0.0
        var worstSample = ""
        var worstTimestep = -1
        var worstChannel = -1
        var discreteMismatches = 0
        for (fixtureElement in manifest.getAsJsonArray("fixtures")) {
            val fixture = fixtureElement.asJsonObject
            val sampleId = fixture.get("sample_id").asString
            val raw = parseRaw(
                JsonParser.parseString(
                    File(root, File(fixture.get("raw_asset").asString).name).readText(),
                ).asJsonObject,
            )
            val views = fixture.getAsJsonObject("views")
            for ((conditionName, condition) in listOf(
                "dense" to RecognitionV2.TemporalCondition.DENSE,
                "phone_01_sparse" to RecognitionV2.TemporalCondition.PHONE_01_SPARSE,
            )) {
                val expectedView = views.getAsJsonObject(conditionName)
                val actual = RecognitionV2.temporalView(
                    raw, condition, manifest.get("phone_completed_fps").asDouble,
                )
                assertArrayEquals(ints(expectedView.getAsJsonArray("source_indices")), actual.sourceIndices)
                assertArrayEquals(
                    doubles(expectedView.getAsJsonArray("source_timestamps_ms")),
                    actual.sourceTimestampsMs,
                    0.0,
                )
                assertTrue(booleans(expectedView.getAsJsonArray("mask")).contentEquals(actual.mask))
                for (row in actual.sourceTimestampsMs.indices) {
                    val expectedDt = if (row == 0) 0f else (
                        (actual.sourceTimestampsMs[row] - actual.sourceTimestampsMs[row - 1]) / 1000.0
                    ).coerceIn(0.0, 1.0).toFloat()
                    assertEquals(expectedDt, actual.features[row * RecognitionV2.FEATURE_WIDTH + 348])
                }
                val expected = floats(
                    File(root, File(expectedView.get("tensor_asset").asString).name).readBytes(),
                )
                for (element in expected.indices) {
                    val timestep = element / RecognitionV2.FEATURE_WIDTH
                    val channel = element % RecognitionV2.FEATURE_WIDTH
                    val error = abs(actual.features[element] - expected[element]).toDouble()
                    errors.add(error)
                    conditionErrors.getValue(conditionName).add(error)
                    val group = RecognitionV2.FEATURE_GROUPS.first {
                        channel >= it.start && channel < it.endExclusive
                    }
                    groupErrors.getValue("$conditionName:${group.name}").add(error)
                    if (error > worst) {
                        worst = error
                        worstSample = sampleId
                        worstTimestep = timestep
                        worstChannel = channel
                    }
                    if (channel in discreteChannels && actual.features[element] != expected[element]) {
                        discreteMismatches++
                    }
                }
            }
        }
        val report = JsonObject().apply {
            addProperty("milestone", "PHASE_4A_ANDROID_V2_PARITY_01")
            addProperty("runtime", "JVM_PREFLIGHT_SAME_ANDROID_DEBUG_SOURCE")
            addProperty("status", if (worst <= RecognitionV2.FLOAT_TOLERANCE && discreteMismatches == 0) "PASS" else "FAIL")
            addProperty("maximum_absolute", worst)
            addProperty("p95_absolute", percentile(errors, 0.95))
            addProperty("mean_absolute", errors.average())
            addProperty("worst_sample", worstSample)
            addProperty("worst_timestep", worstTimestep)
            addProperty("worst_channel", worstChannel)
            addProperty("discrete_mismatches", discreteMismatches)
            for ((condition, values) in conditionErrors) add(condition, summary(values))
            add("groups", JsonObject().apply {
                for ((name, values) in groupErrors) add(name, JsonObject().apply {
                    addProperty("maximum_absolute", values.maxOrNull() ?: 0.0)
                    addProperty("p95_absolute", percentile(values, 0.95))
                    addProperty("mean_absolute", values.average())
                })
            })
        }
        val output = File("build/reports/phase4a_android_v2_parity_jvm.json")
        output.parentFile?.mkdirs()
        output.writeText(report.toString())
        assertEquals(report.toString(), "PASS", report.get("status").asString)
    }

    @Test
    fun invalidEvidenceAndPaddingStayExplicitlyMasked() {
        val frames = 2
        val handXy = FloatArray(frames * 2 * 21 * 2)
        val handValid = BooleanArray(frames * 2 * 21)
        for (frame in 0 until frames) for (joint in 0 until 21) {
            val validOffset = frame * 2 * 21 + joint
            handValid[validOffset] = joint != 9
            handXy[validOffset * 2] = 100f + joint * 2f
            handXy[validOffset * 2 + 1] = 150f + joint * 3f
        }
        val raw = RecognitionV2.RawSequence(
            schema = RecognitionV2.RAW_SCHEMA,
            imageSemantics = "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            frameIndex = intArrayOf(0, 1),
            timestampMs = doubleArrayOf(0.0, 200.0),
            sourceSize = intArrayOf(480, 640, 480, 640),
            handXy = handXy,
            handProposalSupport = FloatArray(frames * 2 * 21) { 0.8f },
            handJointValid = handValid,
            handPresence = floatArrayOf(0.9f, 0f, 0.9f, 0f),
            handObserved = booleanArrayOf(true, false, true, false),
            bodyXy = FloatArray(frames * 8 * 2),
            bodySupport = FloatArray(frames * 8),
            bodyValid = BooleanArray(frames * 8),
            bodyAvailable = BooleanArray(frames),
        )
        val view = RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
        for (row in 0 until frames) {
            val base = row * RecognitionV2.FEATURE_WIDTH
            assertEquals(0f, view.features[base + 129]) // missing LH palm reference
            assertTrue((0 until 120).all { view.features[base + it] == 0f })
            assertEquals(0f, view.features[base + 295]) // body frame unavailable
            assertTrue((120..125).all { view.features[base + it] == 0f })
            assertTrue((296..301).all { view.features[base + it] == 0f })
            assertTrue((303 until 348).all { view.features[base + it] == 0f })
        }
        for (row in frames until RecognitionV2.MAX_SEQUENCE_LENGTH) {
            assertTrue(!view.mask[row])
            val base = row * RecognitionV2.FEATURE_WIDTH
            assertTrue((0 until RecognitionV2.FEATURE_WIDTH).all { view.features[base + it] == 0f })
        }
    }

    private fun parseRaw(value: JsonObject) = RecognitionV2.RawSequence(
        schema = value.get("schema").asString,
        imageSemantics = value.get("image_semantics").asString,
        frameIndex = ints(value.getAsJsonArray("frame_index")),
        timestampMs = doubles(value.getAsJsonArray("timestamp_ms")),
        sourceSize = ints(value.getAsJsonArray("source_size")),
        handXy = floats(value.getAsJsonArray("hand_xy")),
        handProposalSupport = floats(value.getAsJsonArray("hand_proposal_support")),
        handJointValid = booleans(value.getAsJsonArray("hand_joint_valid")),
        handPresence = floats(value.getAsJsonArray("hand_presence")),
        handObserved = booleans(value.getAsJsonArray("hand_observed")),
        bodyXy = floats(value.getAsJsonArray("body_xy")),
        bodySupport = floats(value.getAsJsonArray("body_support")),
        bodyValid = booleans(value.getAsJsonArray("body_valid")),
        bodyAvailable = booleans(value.getAsJsonArray("body_available")),
    )

    private fun ints(value: JsonArray) = IntArray(value.size()) { value[it].asInt }
    private fun doubles(value: JsonArray) = DoubleArray(value.size()) { value[it].asDouble }
    private fun floats(value: JsonArray) = FloatArray(value.size()) { value[it].asFloat }
    private fun booleans(value: JsonArray) = BooleanArray(value.size()) { value[it].asBoolean }
    private fun floats(bytes: ByteArray): FloatArray {
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun percentile(values: List<Double>, quantile: Double): Double {
        if (values.isEmpty()) return 0.0
        val sorted = values.sorted()
        return sorted[((sorted.size - 1) * quantile).toInt()]
    }

    private fun summary(values: List<Double>) = JsonObject().apply {
        addProperty("maximum_absolute", values.maxOrNull() ?: 0.0)
        addProperty("p95_absolute", percentile(values, 0.95))
        addProperty("mean_absolute", values.average())
    }

    private val discreteChannels: Set<Int> = buildSet {
        for (handStart in intArrayOf(0, 130)) {
            addAll((handStart + 40 until handStart + 60).toList())
            addAll((handStart + 90 until handStart + 105).toList())
            addAll((handStart + 115 until handStart + 120).toList())
            add(handStart + 127)
            add(handStart + 129)
        }
        addAll((272 until 278).toList())
        addAll((286 until 296).toList())
        add(302)
        addAll((317 until 324).toList())
        addAll((338 until 345).toList())
        add(347)
    }
}
