package com.example.apphear.perceptionvnext

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.nio.ByteBuffer
import java.nio.ByteOrder

@RunWith(AndroidJUnit4::class)
class PhoneSegmentationFeatureParityInstrumentedTest {
    @Test
    fun androidFeatureRowsMatchFrozenPythonFixture() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val fixture = JSONObject(context.assets.open(RAW_ASSET).bufferedReader().readText())
        val expected = context.assets.open(EXPECTED_ASSET).use { it.readBytes() }.floats()
        val rows = fixture.getJSONArray("observations")
        val builder = PhoneSegmentationFeatureBuilder()
        assertTrue(fixture.getString("feature_schema") == PhoneSegmentationFeatureBuilder.SCHEMA)
        repeat(rows.length()) { row ->
            val actual = builder.derive(rows.getJSONObject(row).observation())
            repeat(PhoneSegmentationFeatureBuilder.FEATURE_WIDTH) { column ->
                val target = expected[row * PhoneSegmentationFeatureBuilder.FEATURE_WIDTH + column]
                val difference = kotlin.math.abs(actual[column] - target)
                assertTrue("row=$row column=$column diff=$difference", difference <= 1e-6f)
            }
        }
    }

    private fun JSONObject.observation(): PhoneRawObservation {
        val size = getJSONArray("source_size")
        val presence = getJSONArray("hand_presence")
        val presenceFinite = getJSONArray("hand_presence_finite")
        return PhoneRawObservation(
            sourceIndex = getInt("source_index"),
            timestampMs = getDouble("timestamp_ms"),
            sourceWidth = size.getInt(0),
            sourceHeight = size.getInt(1),
            handXy = getJSONArray("hand_xy").floatArrays(2, 42),
            handJointValid = getJSONArray("hand_joint_valid").booleanArrays(2, 21),
            handProposalSupport = getJSONArray("hand_proposal_support").floatArrays(2, 21),
            handPresence = FloatArray(2) { index ->
                if (presenceFinite.getBoolean(index)) presence.getDouble(index).toFloat() else Float.NaN
            },
            handObserved = getJSONArray("hand_observed").booleanArray(),
            handProposalPresent = getJSONArray("hand_proposal_present").booleanArray(),
            handRoiCenterSide = getJSONArray("hand_roi_center_side").floatArrays(2, 3),
            bodyXy = getJSONArray("body_xy").flattenFloats(),
            bodySupport = getJSONArray("body_support").floatArray(),
            bodyValid = getJSONArray("body_valid").booleanArray(),
            bodyAvailable = getBoolean("body_available"),
        )
    }

    private fun JSONArray.floatArrays(rows: Int, width: Int): Array<FloatArray> =
        Array(rows) { row ->
            val source = getJSONArray(row)
            if (source.length() == width) FloatArray(width) { source.getDouble(it).toFloat() }
            else source.flattenFloats().also { require(it.size == width) }
        }

    private fun JSONArray.flattenFloats(): FloatArray {
        val output = ArrayList<Float>()
        fun visit(value: Any) {
            if (value is JSONArray) repeat(value.length()) { visit(value.get(it)) }
            else output += (value as Number).toFloat()
        }
        visit(this)
        return output.toFloatArray()
    }

    private fun JSONArray.floatArray() = FloatArray(length()) { getDouble(it).toFloat() }
    private fun JSONArray.booleanArray() = BooleanArray(length()) { getBoolean(it) }
    private fun JSONArray.booleanArrays(rows: Int, width: Int) = Array(rows) { row ->
        getJSONArray(row).booleanArray().also { require(it.size == width) }
    }

    private fun ByteArray.floats(): FloatArray {
        require(size % 4 == 0)
        val source = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        return FloatArray(size / 4).also(source::get)
    }

    companion object {
        private const val ROOT = "phone_causal_recognition_01"
        private const val RAW_ASSET = "$ROOT/segmentation_feature_parity_raw.json"
        private const val EXPECTED_ASSET = "$ROOT/segmentation_feature_parity_expected.f32"
    }
}
