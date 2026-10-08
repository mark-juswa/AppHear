package com.example.apphear.fingerspelling

import android.content.Context
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** One owner thread for both interpreters. No delegates, training or weight mutation. */
internal class FingerspellModels(context: Context) : AutoCloseable {
    private val assets = context.assets
    private val manifestBytes = assets.open("fingerspelling/model_manifest.json").use { it.readBytes() }
    val manifest = JSONObject(String(manifestBytes, Charsets.UTF_8))
    private val visualRules: VisualRules?
    val rules: VisualRules get() = checkNotNull(visualRules) { "Geometry-only package has no visual branch" }
    val visualEnabled: Boolean
    val inputWidth: Int
    val adapter: FingerspellingFeatureAdapterV1
    val blankPenalty: Float
    private val appearance: Interpreter?
    private val sequence: Interpreter
    private val packedIndex: Int
    private val maskIndex: Int
    init {
        val manifestHash = MessageDigest.getInstance("SHA-256").digest(manifestBytes).joinToString("") { "%02x".format(it) }
        visualEnabled = when (manifestHash) {
            "09680096117f4d34eb86e0b71fc8681bfe3d4101082c4e0db2c8f7e9b1a1e57b" -> true
            "11d4236c9d75f0b8c98a2637998764ec2819fec5c89e492fc0f1455f1c0b2b6d" -> false
            "8edc998728fa41883abacbc8382359d6d61621bc259da78ca7c2ab6f8126d01e" -> false
            else -> error("Frozen model/config manifest changed")
        }
        require(manifest.getString("schema_version") == if (visualEnabled)
            "apphear.fingerspelling.android.v1" else "apphear.fingerspelling.android.geometry.v1")
        inputWidth = if (visualEnabled) 1559 else 405
        if (!visualEnabled) {
            when (manifest.getString("candidate_id")) {
                "TRAIN4096_EPOCH038_GEOMETRY_ONLY" -> {
                    require(manifest.getInt("checkpoint_epoch") == 38)
                    require(manifest.getString("checkpoint_sha256") == "b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886")
                }
                "SEQUENCE_V2_1_EPOCH034_GEOMETRY_ONLY" -> {
                    require(manifest.getInt("checkpoint_epoch") == 34)
                    require(manifest.getString("checkpoint_sha256") == "3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638")
                    require(!manifest.getBoolean("causal") && !manifest.getBoolean("auxiliary_head_exported"))
                    require(manifest.getInt("parameter_count") == 292956)
                }
                else -> error("Unknown pinned geometry candidate")
            }
            require(!manifest.getBoolean("visual_branch_enabled") && !manifest.getBoolean("quantized"))
            require(manifest.getInt("blank_index") == 27 && manifest.getInt("beam_width") == 10)
        }
        val a = manifest.getJSONObject("adapter")
        require(a.getString("schema_version") == "FingerspellingFeatureAdapter.v1" && a.getInt("feature_width") == 405)
        require(a.getString("config_sha256") == "5ed7f766154b558ea2bebd095804ca788dc7ee5b91cc001ca96a40133edb9b67")
        require(a.getString("implementation_sha256") == "256d8e82301fa9e6dd039a1c6d94dc5cc717b22c27e7b8bd9661ba32ee4394cd")
        require(a.getString("columns_sha256") == "f3f5f93cd590111e60a1078c032ada7a756be72d633ff53900ae9a353f084fcb")
        require(manifest.getInt("packed_width") == inputWidth)
        val vocabulary = manifest.getJSONArray("vocabulary")
        require(vocabulary.length() == 28 && (0..25).all { vocabulary.getString(it) == ('A'.code+it).toChar().toString() } &&
            vocabulary.getString(26) == "SPACE" && vocabulary.getString(27) == "BLANK")
        blankPenalty = manifest.getDouble("blank_penalty").toFloat()
        require(blankPenalty == .5f)
        visualRules = if (visualEnabled) {
        val cfg = manifest.getJSONObject("quality_config"); val crop = manifest.getJSONObject("crop_config")
        VisualRules(crop.getDouble("roi_expansion").toFloat(), crop.getDouble("minimum_roi_side_pixels").toFloat(),
            crop.getDouble("minimum_source_intersection_fraction"), cfg.getDouble("minimum_presence").toFloat(),
            cfg.getInt("minimum_valid_joints"), cfg.getDouble("proposal_support_threshold").toFloat(),
            cfg.getInt("minimum_supported_joints"), cfg.getDouble("minimum_source_intersection"), cfg.getDouble("minimum_joint_containment"),
            cfg.getDouble("duplicate_min_iou"), cfg.getDouble("duplicate_max_center_distance").toFloat(),
            cfg.getDouble("duplicate_max_landmark_distance").toFloat(), cfg.getDouble("duplicate_max_side_ratio").toFloat(),
            cfg.getInt("duplicate_min_common_joints"), crop.getInt("crop_size"))
        } else null
        val feature = manifest.getJSONObject("feature_config")
        adapter = FingerspellingFeatureAdapterV1(feature.getDouble("minimum_scale_short_side_ratio").toFloat(),
            feature.getDouble("maximum_motion_gap_seconds").toFloat())
        appearance = if (visualEnabled) load("appearance.tflite") else null
        try { sequence = load(if (visualEnabled) "residual_sequence.tflite" else "geometry_sequence.tflite") }
        catch (error: Throwable) { appearance?.close(); throw error }
        packedIndex = (0 until sequence.inputTensorCount).single { sequence.getInputTensor(it).shape().last() == inputWidth }
        maskIndex = (0 until sequence.inputTensorCount).single { sequence.getInputTensor(it).shape().last() == 1 }
        require(sequence.outputTensorCount == 1 && sequence.getOutputTensor(0).shape().last() == 28)
        if (appearance != null) require(appearance.getOutputTensor(0).shape().last() == 576)
    }
    private fun load(name: String): Interpreter {
        val bytes = assets.open("fingerspelling/$name").use { it.readBytes() }
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        require(hash == manifest.getJSONObject("models").getJSONObject(name).getString("sha256")) { "Fingerspelling model hash mismatch" }
        val data = ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).apply { put(bytes); rewind() }
        return Interpreter(data, Interpreter.Options().setNumThreads(2)).also { interpreter ->
            require((0 until interpreter.inputTensorCount).all { interpreter.getInputTensor(it).dataType() == DataType.FLOAT32 })
        }
    }
    fun encode(crop: FloatArray): FloatArray {
        require(crop.size == 128*128*3 && crop.all { it.isFinite() })
        val input = floats(crop)
        val out = arrayOf(FloatArray(576))
        checkNotNull(appearance) { "Appearance is disabled for geometry-only inference" }.run(input, out)
        require(out[0].all { it.isFinite() })
        return out[0]
    }
    fun logits(frames: List<FloatArray>, mask: FloatArray? = null): Array<FloatArray> {
        require(frames.isNotEmpty() && frames.all { it.size == inputWidth && it.all { v -> v.isFinite() } })
        require(mask == null || (mask.size == frames.size && mask.all { it == 0f || it == 1f }))
        sequence.resizeInput(packedIndex, intArrayOf(1, frames.size, inputWidth), true)
        sequence.resizeInput(maskIndex, intArrayOf(1, frames.size, 1), true)
        // Let run allocate after resize. In pinned 2.16.1 the post-invoke Java
        // output-shape refresh happens only when run performed the allocation.
        val inputs = arrayOfNulls<Any>(2)
        inputs[packedIndex] = floats(frames.flatMap { it.asIterable() }.toFloatArray())
        inputs[maskIndex] = floats(mask ?: FloatArray(frames.size) { 1f })
        // Dynamic Conv1D output shape is resolved only after invocation in 2.16.
        // A pre-sized Java array is rejected against the stale allocation-time shape.
        sequence.runForMultipleInputsOutputs(inputs, mutableMapOf<Int, Any?>())
        val tensor = sequence.getOutputTensor(0)
        require(tensor.shape().contentEquals(intArrayOf(1, frames.size, 28))) {
            "Sequence runtime shape=${tensor.shape().joinToString()} expected=1,${frames.size},28 " +
                "inputs=${sequence.getInputTensor(packedIndex).shape().joinToString()};${sequence.getInputTensor(maskIndex).shape().joinToString()}"
        }
        val values = tensor.asReadOnlyBuffer().order(ByteOrder.nativeOrder()).asFloatBuffer()
        val out = Array(frames.size) { FloatArray(28).also { values.get(it) } }
        require(out.all { row -> row.all { it.isFinite() } })
        return out
    }
    private fun floats(values: FloatArray) = ByteBuffer.allocateDirect(values.size*4).order(ByteOrder.nativeOrder()).apply {
        asFloatBuffer().put(values); rewind()
    }
    override fun close() { sequence.close(); appearance?.close() }
}
