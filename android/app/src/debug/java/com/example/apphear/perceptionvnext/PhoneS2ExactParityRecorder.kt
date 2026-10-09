package com.example.apphear.perceptionvnext

import java.io.BufferedOutputStream
import java.io.BufferedWriter
import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.io.FileWriter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Debug-only recorder of the exact, already-computed phone S2 path.
 *
 * It never derives features, normalizes inputs, or runs inference. Values are copied after the
 * production/debug path computed them, then serialized asynchronously in chronological order.
 */
internal class PhoneS2ExactParityRecorder(
    private val root: File,
    private val maximumObservations: Int = MAXIMUM_OBSERVATIONS,
) : Closeable {
    private data class Row(
        val observation: PhoneRawObservation,
        val features: FloatArray,
        val normalized: FloatArray,
        val probabilities: FloatArray,
        val historyLength: Int,
        val argmaxState: Int,
        val attemptId: Int?,
        val expectedGloss: String?,
    )

    private val executor = Executors.newSingleThreadExecutor()
    private val closed = AtomicBoolean(false)
    private var count = 0
    private val outputs = linkedMapOf(
        "source_index.i32" to output("source_index.i32"),
        "timestamp_ms.f64" to output("timestamp_ms.f64"),
        "source_size.i32" to output("source_size.i32"),
        "raw_hand_xy.f32" to output("raw_hand_xy.f32"),
        "raw_hand_joint_valid.u8" to output("raw_hand_joint_valid.u8"),
        "raw_hand_proposal_support.f32" to output("raw_hand_proposal_support.f32"),
        "raw_hand_presence.f32" to output("raw_hand_presence.f32"),
        "raw_hand_observed.u8" to output("raw_hand_observed.u8"),
        "raw_hand_proposal_present.u8" to output("raw_hand_proposal_present.u8"),
        "raw_hand_roi_center_side.f32" to output("raw_hand_roi_center_side.f32"),
        "raw_body_xy.f32" to output("raw_body_xy.f32"),
        "raw_body_support.f32" to output("raw_body_support.f32"),
        "raw_body_valid.u8" to output("raw_body_valid.u8"),
        "raw_body_available.u8" to output("raw_body_available.u8"),
        "android_features.f32" to output("android_features.f32"),
        "android_normalized.f32" to output("android_normalized.f32"),
        "android_probabilities.f32" to output("android_probabilities.f32"),
        "android_argmax.u8" to output("android_argmax.u8"),
        "history_length.i32" to output("history_length.i32"),
    )
    private val linkage = BufferedWriter(FileWriter(File(root, "linkage.csv"))).also {
        it.write("record_index,source_index,timestamp_ms,attempt_id,expected_gloss\n")
    }

    init {
        require(maximumObservations > 0)
        require(root.exists() || root.mkdirs())
    }

    fun record(
        observation: PhoneRawObservation,
        features: FloatArray,
        normalized: FloatArray,
        probabilities: FloatArray,
        historyLength: Int,
        argmaxState: Int,
        attemptId: Int?,
        expectedGloss: String?,
    ) {
        check(!closed.get()) { "PHONE_S2_EXACT_PARITY_RECORDER_CLOSED" }
        require(count < maximumObservations) { "PHONE_S2_EXACT_PARITY_CAPTURE_LIMIT_REACHED" }
        require(features.size == 378 && normalized.size == 378 && probabilities.size == 3)
        val row = Row(
            observation.deepCopy(),
            features.copyOf(),
            normalized.copyOf(),
            probabilities.copyOf(),
            historyLength,
            argmaxState,
            attemptId,
            expectedGloss,
        )
        val recordIndex = count++
        executor.execute { write(recordIndex, row) }
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        executor.shutdown()
        require(executor.awaitTermination(DRAIN_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
            "PHONE_S2_EXACT_PARITY_DRAIN_TIMEOUT"
        }
        outputs.values.forEach { it.close() }
        linkage.close()
        verifySizes()
        File(root, "manifest.json").writeText(manifest())
    }

    private fun write(recordIndex: Int, row: Row) {
        val raw = row.observation
        outputs.getValue("source_index.i32").writeInts(intArrayOf(raw.sourceIndex))
        outputs.getValue("timestamp_ms.f64").writeDoubles(doubleArrayOf(raw.timestampMs))
        outputs.getValue("source_size.i32").writeInts(intArrayOf(raw.sourceWidth, raw.sourceHeight))
        outputs.getValue("raw_hand_xy.f32").writeFloats(raw.handXy.flatten())
        outputs.getValue("raw_hand_joint_valid.u8").writeBooleans(raw.handJointValid.flatten())
        outputs.getValue("raw_hand_proposal_support.f32").writeFloats(raw.handProposalSupport.flatten())
        outputs.getValue("raw_hand_presence.f32").writeFloats(raw.handPresence)
        outputs.getValue("raw_hand_observed.u8").writeBooleans(raw.handObserved)
        outputs.getValue("raw_hand_proposal_present.u8").writeBooleans(raw.handProposalPresent)
        outputs.getValue("raw_hand_roi_center_side.f32").writeFloats(raw.handRoiCenterSide.flatten())
        outputs.getValue("raw_body_xy.f32").writeFloats(raw.bodyXy)
        outputs.getValue("raw_body_support.f32").writeFloats(raw.bodySupport)
        outputs.getValue("raw_body_valid.u8").writeBooleans(raw.bodyValid)
        outputs.getValue("raw_body_available.u8").writeBooleans(booleanArrayOf(raw.bodyAvailable))
        outputs.getValue("android_features.f32").writeFloats(row.features)
        outputs.getValue("android_normalized.f32").writeFloats(row.normalized)
        outputs.getValue("android_probabilities.f32").writeFloats(row.probabilities)
        outputs.getValue("android_argmax.u8").write(byteArrayOf(row.argmaxState.toByte()))
        outputs.getValue("history_length.i32").writeInts(intArrayOf(row.historyLength))
        linkage.write(
            listOf(
                recordIndex,
                raw.sourceIndex,
                raw.timestampMs,
                row.attemptId ?: "",
                csv(row.expectedGloss ?: ""),
            ).joinToString(",") + "\n",
        )
    }

    private fun verifySizes() {
        WIDTHS.forEach { (file, bytesPerObservation) ->
            val actual = File(root, file).length()
            val expected = count.toLong() * bytesPerObservation
            require(actual == expected) {
                "PHONE_S2_EXACT_PARITY_SIZE_MISMATCH:$file:$actual:$expected"
            }
        }
    }

    private fun manifest(): String {
        val files = WIDTHS.keys.joinToString(",\n") { name ->
            "    \"$name\": {\"bytes_per_observation\": ${WIDTHS.getValue(name)}, " +
                "\"sha256\": \"${sha256(File(root, name))}\"}"
        }
        return """{
  "schema": "apphear.phone_s2_exact_parity_capture.v1",
  "raw_schema": "${PhoneSegmentationFeatureBuilder.RAW_SCHEMA}",
  "feature_schema": "${PhoneSegmentationFeatureBuilder.SCHEMA}",
  "feature_width": 378,
  "state_order": ["PRE_IDLE", "ACTIVE_SIGN", "POST_RECOVERY"],
  "byte_order": "LITTLE_ENDIAN",
  "observation_count": $count,
  "maximum_observations": $maximumObservations,
  "files": {
$files
  },
  "linkage_sha256": "${sha256(File(root, "linkage.csv"))}"
}
"""
    }

    private fun output(name: String): BufferedOutputStream {
        require(root.exists() || root.mkdirs())
        return BufferedOutputStream(FileOutputStream(File(root, name)))
    }

    private fun PhoneRawObservation.deepCopy() = copy(
        handXy = Array(2) { handXy[it].copyOf() },
        handJointValid = Array(2) { handJointValid[it].copyOf() },
        handProposalSupport = Array(2) { handProposalSupport[it].copyOf() },
        handPresence = handPresence.copyOf(),
        handObserved = handObserved.copyOf(),
        handProposalPresent = handProposalPresent.copyOf(),
        handRoiCenterSide = Array(2) { handRoiCenterSide[it].copyOf() },
        bodyXy = bodyXy.copyOf(),
        bodySupport = bodySupport.copyOf(),
        bodyValid = bodyValid.copyOf(),
    )

    private fun Array<FloatArray>.flatten() = flatMap { it.asIterable() }.toFloatArray()
    private fun Array<BooleanArray>.flatten() = flatMap { it.asIterable() }.toBooleanArray()
    private fun BufferedOutputStream.writeFloats(values: FloatArray) =
        write(ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply {
            values.forEach(::putFloat)
        }.array())
    private fun BufferedOutputStream.writeDoubles(values: DoubleArray) =
        write(ByteBuffer.allocate(values.size * 8).order(ByteOrder.LITTLE_ENDIAN).apply {
            values.forEach(::putDouble)
        }.array())
    private fun BufferedOutputStream.writeInts(values: IntArray) =
        write(ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN).apply {
            values.forEach(::putInt)
        }.array())
    private fun BufferedOutputStream.writeBooleans(values: BooleanArray) =
        write(ByteArray(values.size) { if (values[it]) 1 else 0 })

    private fun csv(value: String) = "\"${value.replace("\"", "\"\"")}\""
    private fun sha256(path: File): String = MessageDigest.getInstance("SHA-256").let { digest ->
        path.inputStream().use { stream ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = stream.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        digest.digest().joinToString("") { "%02x".format(it) }
    }

    companion object {
        const val MAXIMUM_OBSERVATIONS = 3600
        private const val DRAIN_TIMEOUT_SECONDS = 120L
        private val WIDTHS = linkedMapOf(
            "source_index.i32" to 4L,
            "timestamp_ms.f64" to 8L,
            "source_size.i32" to 8L,
            "raw_hand_xy.f32" to 84L * 4,
            "raw_hand_joint_valid.u8" to 42L,
            "raw_hand_proposal_support.f32" to 42L * 4,
            "raw_hand_presence.f32" to 2L * 4,
            "raw_hand_observed.u8" to 2L,
            "raw_hand_proposal_present.u8" to 2L,
            "raw_hand_roi_center_side.f32" to 6L * 4,
            "raw_body_xy.f32" to 16L * 4,
            "raw_body_support.f32" to 8L * 4,
            "raw_body_valid.u8" to 8L,
            "raw_body_available.u8" to 1L,
            "android_features.f32" to 378L * 4,
            "android_normalized.f32" to 378L * 4,
            "android_probabilities.f32" to 3L * 4,
            "android_argmax.u8" to 1L,
            "history_length.i32" to 4L,
        )
    }
}
