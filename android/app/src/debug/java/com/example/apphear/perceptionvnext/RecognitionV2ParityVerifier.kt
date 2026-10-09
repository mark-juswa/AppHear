package com.example.apphear.perceptionvnext

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.abs

/** Runs the frozen Python-golden Recognition V2 comparison on the Android device. */
object RecognitionV2ParityVerifier {
    private const val MANIFEST = "phase4a_v2_parity/manifest.json"

    private data class ErrorAccumulator(
        val values: MutableList<Double> = ArrayList(),
        var maximum: Double = 0.0,
        var worstSample: String = "",
        var worstTimestep: Int = -1,
        var worstChannel: Int = -1,
    ) {
        fun add(value: Double, sample: String, timestep: Int, channel: Int) {
            values.add(value)
            if (value > maximum) {
                maximum = value
                worstSample = sample
                worstTimestep = timestep
                worstChannel = channel
            }
        }

        fun json(): JSONObject {
            val sorted = values.sorted()
            val p95 = if (sorted.isEmpty()) 0.0 else sorted[
                ((sorted.size - 1) * 0.95).toInt()
            ]
            val mean = if (values.isEmpty()) 0.0 else values.sum() / values.size
            return JSONObject()
                .put("count", values.size)
                .put("maximum_absolute", maximum)
                .put("p95_absolute", p95)
                .put("mean_absolute", mean)
                .put("worst_sample", worstSample)
                .put("worst_timestep", worstTimestep)
                .put("worst_channel", worstChannel)
        }
    }

    fun verify(context: Context): JSONObject {
        val manifest = JSONObject(context.assets.open(MANIFEST).bufferedReader().readText())
        require(manifest.getString("raw_schema") == RecognitionV2.RAW_SCHEMA)
        require(manifest.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA)
        val tolerance = manifest.getDouble("preregistered_max_abs_tolerance")
        require(tolerance == RecognitionV2.FLOAT_TOLERANCE)
        val fixtures = manifest.getJSONArray("fixtures")
        val conditionStats = linkedMapOf(
            "dense" to ErrorAccumulator(),
            "phone_01_sparse" to ErrorAccumulator(),
        )
        val groupStats = linkedMapOf<String, ErrorAccumulator>()
        for (condition in conditionStats.keys) for (group in RecognitionV2.FEATURE_GROUPS) {
            groupStats["$condition:${group.name}"] = ErrorAccumulator()
        }
        var discreteMismatchCount = 0
        var selectionMismatchCount = 0
        var timestampMismatchCount = 0
        var maskMismatchCount = 0
        var paddedFramesChecked = 0
        var missingHandReferenceChecked = 0
        var unavailableBodyReferenceChecked = 0
        var invalidMotionEndpointChecked = 0
        var sparseDtChecks = 0
        val perFixture = JSONArray()

        for (fixtureIndex in 0 until fixtures.length()) {
            val fixture = fixtures.getJSONObject(fixtureIndex)
            val fixtureId = fixture.getString("fixture_id")
            val sampleId = fixture.getString("sample_id")
            val raw = readRaw(
                readVerified(context, fixture.getString("raw_asset"), fixture.getString("raw_sha256"))
                    .toString(Charsets.UTF_8),
            )
            val fixtureResult = JSONObject().put("fixture_id", fixtureId).put("sample_id", sampleId)
            val views = fixture.getJSONObject("views")
            for (conditionName in conditionStats.keys) {
                val expectedView = views.getJSONObject(conditionName)
                val condition = if (conditionName == "dense") {
                    RecognitionV2.TemporalCondition.DENSE
                } else RecognitionV2.TemporalCondition.PHONE_01_SPARSE
                val actual = RecognitionV2.temporalView(
                    raw, condition, manifest.getDouble("phone_completed_fps"),
                )
                val expectedIndices = intArray(expectedView.getJSONArray("source_indices"))
                val expectedTimestamps = doubleArray(expectedView.getJSONArray("source_timestamps_ms"))
                val expectedMask = booleanArray(expectedView.getJSONArray("mask"))
                if (!actual.sourceIndices.contentEquals(expectedIndices)) selectionMismatchCount++
                if (actual.sourceTimestampsMs.size != expectedTimestamps.size ||
                    actual.sourceTimestampsMs.indices.any {
                        actual.sourceTimestampsMs[it] != expectedTimestamps[it]
                    }
                ) timestampMismatchCount++
                if (!actual.mask.contentEquals(expectedMask)) maskMismatchCount++
                val expected = readFloatArray(
                    readVerified(
                        context,
                        expectedView.getString("tensor_asset"),
                        expectedView.getString("tensor_sha256"),
                    ),
                )
                require(expected.size == RecognitionV2.MAX_SEQUENCE_LENGTH * RecognitionV2.FEATURE_WIDTH)
                val local = ErrorAccumulator()
                for (element in expected.indices) {
                    val timestep = element / RecognitionV2.FEATURE_WIDTH
                    val channel = element % RecognitionV2.FEATURE_WIDTH
                    val difference = abs(actual.features[element] - expected[element]).toDouble()
                    local.add(difference, sampleId, timestep, channel)
                    require(actual.features[element].isFinite())
                    conditionStats.getValue(conditionName).add(difference, sampleId, timestep, channel)
                    val group = RecognitionV2.FEATURE_GROUPS.first {
                        channel >= it.start && channel < it.endExclusive
                    }
                    groupStats.getValue("$conditionName:${group.name}")
                        .add(difference, sampleId, timestep, channel)
                    if (channel in discreteChannels && actual.features[element] != expected[element]) {
                        discreteMismatchCount++
                    }
                }
                for (row in actual.realLength until RecognitionV2.MAX_SEQUENCE_LENGTH) {
                    paddedFramesChecked++
                    if (actual.mask[row]) maskMismatchCount++
                    val start = row * RecognitionV2.FEATURE_WIDTH
                    if ((start until start + RecognitionV2.FEATURE_WIDTH).any {
                            actual.features[it] != 0f
                        }
                    ) discreteMismatchCount++
                }
                auditInvalidSemantics(actual).also {
                    missingHandReferenceChecked += it[0]
                    unavailableBodyReferenceChecked += it[1]
                    invalidMotionEndpointChecked += it[2]
                }
                if (conditionName == "phone_01_sparse") {
                    for (row in actual.sourceTimestampsMs.indices) {
                        val expectedDt = if (row == 0) 0f else (
                            (actual.sourceTimestampsMs[row] - actual.sourceTimestampsMs[row - 1]) / 1000.0
                        ).coerceIn(0.0, 1.0).toFloat()
                        val actualDt = actual.features[row * RecognitionV2.FEATURE_WIDTH + 348]
                        if (actualDt == expectedDt) sparseDtChecks++ else timestampMismatchCount++
                    }
                }
                fixtureResult.put(conditionName, local.json())
            }
            perFixture.put(fixtureResult)
        }

        // Raw TRAIN has no observed hand whose four palm reference joints are invalid. Exercise
        // that allowed raw-v1 state explicitly without adding a non-TRAIN item to the parity corpus.
        val syntheticInvalid = auditInvalidSemantics(syntheticInvalidView())
        missingHandReferenceChecked += syntheticInvalid[0]
        unavailableBodyReferenceChecked += syntheticInvalid[1]
        invalidMotionEndpointChecked += syntheticInvalid[2]

        val coveragePass = paddedFramesChecked > 0 && missingHandReferenceChecked > 0 &&
            unavailableBodyReferenceChecked > 0 && invalidMotionEndpointChecked > 0 && sparseDtChecks > 0
        val floatPass = conditionStats.values.all { it.maximum <= tolerance }
        val discretePass = discreteMismatchCount == 0 && selectionMismatchCount == 0 &&
            timestampMismatchCount == 0 && maskMismatchCount == 0
        val groupJson = JSONObject()
        for ((key, stats) in groupStats) {
            groupJson.put(key, stats.json().put("pass", stats.maximum <= tolerance))
        }
        val result = JSONObject()
            .put("milestone", "PHASE_4A_ANDROID_V2_PARITY_01")
            .put("status", if (floatPass && discretePass && coveragePass) "PASS" else "FAIL")
            .put("raw_schema", RecognitionV2.RAW_SCHEMA)
            .put("feature_schema", RecognitionV2.FEATURE_SCHEMA)
            .put("shape", JSONArray(listOf(96, 350)))
            .put("fixtures", fixtures.length())
            .put("dense_views", fixtures.length())
            .put("sparse_views", fixtures.length())
            .put("preregistered_max_abs_tolerance", tolerance)
            .put("discrete_parity", if (discretePass) "PASS" else "FAIL")
            .put("selection_mismatches", selectionMismatchCount)
            .put("timestamp_mismatches", timestampMismatchCount)
            .put("mask_mismatches", maskMismatchCount)
            .put("discrete_feature_mismatches", discreteMismatchCount)
            .put("dense", conditionStats.getValue("dense").json())
            .put("sparse", conditionStats.getValue("phone_01_sparse").json())
            .put("feature_groups", groupJson)
            .put("padding_mask", if (paddedFramesChecked > 0 && maskMismatchCount == 0) "PASS" else "FAIL")
            .put("padded_frames_checked", paddedFramesChecked)
            .put("invalid_state_semantics", if (coveragePass && discreteMismatchCount == 0) "PASS" else "FAIL")
            .put("synthetic_invalid_contract_test", "PASS")
            .put("missing_hand_reference_frames_checked", missingHandReferenceChecked)
            .put("unavailable_body_reference_frames_checked", unavailableBodyReferenceChecked)
            .put("invalid_motion_endpoints_checked", invalidMotionEndpointChecked)
            .put("sparse_selected_timestamp_motion", if (sparseDtChecks > 0 && timestampMismatchCount == 0) "PASS" else "FAIL")
            .put("sparse_dt_checks", sparseDtChecks)
            .put("dev_accessed", false)
            .put("protected_test_accessed", false)
            .put("per_fixture", perFixture)
        val root = File(
            requireNotNull(context.getExternalFilesDir(null)),
            "phase4a_android_v2_parity_01",
        ).also { it.mkdirs() }
        File(root, "android_v2_parity.json").writeText(result.toString(2))
        return result
    }

    private fun syntheticInvalidView(): RecognitionV2.TemporalView {
        val frames = 2
        val handXy = FloatArray(frames * 2 * 21 * 2)
        val handSupport = FloatArray(frames * 2 * 21) { 0.8f }
        val handValid = BooleanArray(frames * 2 * 21)
        val handPresence = FloatArray(frames * 2)
        val handObserved = BooleanArray(frames * 2)
        for (frame in 0 until frames) {
            handObserved[frame * 2] = true
            handPresence[frame * 2] = 0.9f
            for (joint in 0 until 21) {
                val validOffset = (frame * 2) * 21 + joint
                handValid[validOffset] = joint != 9
                val xyOffset = validOffset * 2
                handXy[xyOffset] = 100f + joint * 2f
                handXy[xyOffset + 1] = 150f + joint * 3f
            }
        }
        val raw = RecognitionV2.RawSequence(
            schema = RecognitionV2.RAW_SCHEMA,
            imageSemantics = "UPRIGHT_UNMIRRORED_SOURCE_RGB",
            frameIndex = intArrayOf(0, 1),
            timestampMs = doubleArrayOf(0.0, 200.0),
            sourceSize = intArrayOf(480, 640, 480, 640),
            handXy = handXy,
            handProposalSupport = handSupport,
            handJointValid = handValid,
            handPresence = handPresence,
            handObserved = handObserved,
            bodyXy = FloatArray(frames * 8 * 2),
            bodySupport = FloatArray(frames * 8),
            bodyValid = BooleanArray(frames * 8),
            bodyAvailable = BooleanArray(frames),
        )
        return RecognitionV2.temporalView(raw, RecognitionV2.TemporalCondition.DENSE)
    }

    private fun auditInvalidSemantics(view: RecognitionV2.TemporalView): IntArray {
        var missingReference = 0
        var unavailableBody = 0
        var invalidMotion = 0
        for (row in 0 until view.realLength) {
            val base = row * RecognitionV2.FEATURE_WIDTH
            for (handStart in intArrayOf(0, 130)) {
                if (view.features[base + handStart + 127] == 1f &&
                    view.features[base + handStart + 129] == 0f
                ) {
                    missingReference++
                    require((handStart until handStart + 120).all { view.features[base + it] == 0f })
                }
            }
            if (view.features[base + 295] == 0f) {
                unavailableBody++
                for (handStart in intArrayOf(0, 130)) {
                    require((120..125).all { view.features[base + handStart + it] == 0f })
                }
                require((296..301).all { view.features[base + it] == 0f })
            }
            for (motionStart in intArrayOf(303, 324)) {
                for (slot in 0 until 7) {
                    if (view.features[base + motionStart + 14 + slot] == 0f) {
                        invalidMotion++
                        val pair = when (slot) {
                            0 -> 0
                            1 -> 2
                            else -> 4 + (slot - 2) * 2
                        }
                        require(view.features[base + motionStart + pair] == 0f)
                        require(view.features[base + motionStart + pair + 1] == 0f)
                    }
                }
            }
            if (view.features[base + 347] == 0f) {
                invalidMotion++
                require(view.features[base + 345] == 0f && view.features[base + 346] == 0f)
            }
        }
        return intArrayOf(missingReference, unavailableBody, invalidMotion)
    }

    private fun readRaw(text: String): RecognitionV2.RawSequence {
        val value = JSONObject(text)
        return RecognitionV2.RawSequence(
            schema = value.getString("schema"),
            imageSemantics = value.getString("image_semantics"),
            frameIndex = intArray(value.getJSONArray("frame_index")),
            timestampMs = doubleArray(value.getJSONArray("timestamp_ms")),
            sourceSize = intArray(value.getJSONArray("source_size")),
            handXy = floatArray(value.getJSONArray("hand_xy")),
            handProposalSupport = floatArray(value.getJSONArray("hand_proposal_support")),
            handJointValid = booleanArray(value.getJSONArray("hand_joint_valid")),
            handPresence = floatArray(value.getJSONArray("hand_presence")),
            handObserved = booleanArray(value.getJSONArray("hand_observed")),
            bodyXy = floatArray(value.getJSONArray("body_xy")),
            bodySupport = floatArray(value.getJSONArray("body_support")),
            bodyValid = booleanArray(value.getJSONArray("body_valid")),
            bodyAvailable = booleanArray(value.getJSONArray("body_available")),
        )
    }

    private fun readVerified(context: Context, asset: String, expectedSha: String): ByteArray {
        val bytes = context.assets.open(asset).use { it.readBytes() }
        val actual = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
        require(actual == expectedSha) { "PHASE4A_FIXTURE_HASH_MISMATCH:$asset" }
        return bytes
    }

    private fun readFloatArray(bytes: ByteArray): FloatArray {
        require(bytes.size % 4 == 0)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(buffer.remaining()).also { buffer.get(it) }
    }

    private fun intArray(value: JSONArray) = IntArray(value.length()) { value.getInt(it) }
    private fun doubleArray(value: JSONArray) = DoubleArray(value.length()) { value.getDouble(it) }
    private fun floatArray(value: JSONArray) = FloatArray(value.length()) { value.getDouble(it).toFloat() }
    private fun booleanArray(value: JSONArray) = BooleanArray(value.length()) { value.getBoolean(it) }

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
