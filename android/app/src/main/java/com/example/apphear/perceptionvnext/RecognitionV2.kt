package com.example.apphear.perceptionvnext

import kotlin.math.abs
import kotlin.math.sqrt
import kotlin.math.tanh

/**
 * Frozen Android port of pipeline/perception_vnext/recognition_schema_v2.py.
 *
 * This class is deliberately debug-only during Phase 4A Gate 1. It consumes current-frame
 * Candidate 01 raw-v1 observations and emits recognition-v2 [96,350] plus its frame mask.
 * Feature derivation happens after temporal selection so sparse motion always uses adjacent
 * selected observations and their real timestamps.
 */
object RecognitionV2 {
    const val RAW_SCHEMA = "apphear.perception_vnext.raw.v1"
    const val FEATURE_SCHEMA = "apphear.perception_vnext.recognition.v2"
    const val FEATURE_WIDTH = 350
    const val MAX_SEQUENCE_LENGTH = 96
    const val PHONE_COMPLETED_FPS = 5.606840672873506
    const val FLOAT_TOLERANCE = 1.0e-5

    data class FeatureGroup(val name: String, val start: Int, val endExclusive: Int)

    val FEATURE_GROUPS = listOf(
        FeatureGroup("left_hand", 0, 130),
        FeatureGroup("right_hand", 130, 260),
        FeatureGroup("body", 260, 296),
        FeatureGroup("inter_hand", 296, 303),
        FeatureGroup("left_hand_motion", 303, 324),
        FeatureGroup("right_hand_motion", 324, 345),
        FeatureGroup("inter_hand_motion", 345, 348),
        FeatureGroup("time", 348, 350),
    )

    enum class TemporalCondition { DENSE, PHONE_01_SPARSE }

    data class RawSequence(
        val schema: String,
        val imageSemantics: String,
        val frameIndex: IntArray,
        val timestampMs: DoubleArray,
        val sourceSize: IntArray, // [T,2]
        val handXy: FloatArray, // [T,2,21,2]
        val handProposalSupport: FloatArray, // [T,2,21]
        val handJointValid: BooleanArray, // [T,2,21]
        val handPresence: FloatArray, // [T,2]
        val handObserved: BooleanArray, // [T,2]
        val bodyXy: FloatArray, // [T,8,2]
        val bodySupport: FloatArray, // [T,8]
        val bodyValid: BooleanArray, // [T,8]
        val bodyAvailable: BooleanArray, // [T]
    ) {
        val length: Int get() = frameIndex.size

        fun validate() {
            require(schema == RAW_SCHEMA) { "raw schema identity mismatch" }
            require(imageSemantics == "UPRIGHT_UNMIRRORED_SOURCE_RGB") {
                "raw image semantics mismatch"
            }
            val t = length
            require(t > 0)
            require(timestampMs.size == t && sourceSize.size == t * 2)
            require(handXy.size == t * 2 * 21 * 2)
            require(handProposalSupport.size == t * 2 * 21)
            require(handJointValid.size == t * 2 * 21)
            require(handPresence.size == t * 2 && handObserved.size == t * 2)
            require(bodyXy.size == t * 8 * 2 && bodySupport.size == t * 8)
            require(bodyValid.size == t * 8 && bodyAvailable.size == t)
            for (index in 1 until t) {
                require(frameIndex[index] > frameIndex[index - 1]) { "frame order is invalid" }
                require(timestampMs[index] > timestampMs[index - 1]) {
                    "timestamp order is invalid"
                }
            }
            for (frame in 0 until t) {
                for (side in 0..1) for (joint in 0 until 21) {
                    if (handValid(frame, side, joint)) {
                        require(handX(frame, side, joint).isFinite())
                        require(handY(frame, side, joint).isFinite())
                    }
                }
                for (point in 0 until 8) if (bodyIsValid(frame, point)) {
                    require(bodyX(frame, point).isFinite())
                    require(bodyY(frame, point).isFinite())
                }
            }
        }

        fun width(frame: Int) = sourceSize[frame * 2]
        fun height(frame: Int) = sourceSize[frame * 2 + 1]
        fun handX(frame: Int, side: Int, joint: Int) =
            handXy[(((frame * 2 + side) * 21 + joint) * 2)]
        fun handY(frame: Int, side: Int, joint: Int) =
            handXy[(((frame * 2 + side) * 21 + joint) * 2) + 1]
        fun handSupport(frame: Int, side: Int, joint: Int) =
            handProposalSupport[(frame * 2 + side) * 21 + joint]
        fun handValid(frame: Int, side: Int, joint: Int) =
            handJointValid[(frame * 2 + side) * 21 + joint]
        fun presence(frame: Int, side: Int) = handPresence[frame * 2 + side]
        fun observed(frame: Int, side: Int) = handObserved[frame * 2 + side]
        fun bodyX(frame: Int, point: Int) = bodyXy[(frame * 8 + point) * 2]
        fun bodyY(frame: Int, point: Int) = bodyXy[(frame * 8 + point) * 2 + 1]
        fun bodyPointSupport(frame: Int, point: Int) = bodySupport[frame * 8 + point]
        fun bodyIsValid(frame: Int, point: Int) = bodyValid[frame * 8 + point]
    }

    data class TemporalView(
        val features: FloatArray, // flattened [96,350]
        val mask: BooleanArray,
        val sourceIndices: IntArray,
        val sourceTimestampsMs: DoubleArray,
        val realLength: Int,
    )

    private data class Vec2(val x: Float, val y: Float)
    private data class UnitResult(val value: Vec2, val valid: Boolean)
    private data class BodyFrame(
        val center: Vec2,
        val axisX: Vec2,
        val axisY: Vec2,
        val scale: Float,
        val valid: Boolean,
    )

    private data class HandState(
        val boneUnit: FloatArray,
        val boneValid: BooleanArray,
        val angleSinCos: FloatArray,
        val angleValid: BooleanArray,
        val fingertipLocal: FloatArray,
        val fingertipValid: BooleanArray,
        val wristBody: Vec2,
        val centerBody: Vec2,
        val palmAxisBody: Vec2,
        val observed: Boolean,
        val referenceValid: Boolean,
        val wristBodyValid: Boolean,
        val centerBodyValid: Boolean,
    )

    private val handEdges = arrayOf(
        0 to 1, 1 to 2, 2 to 3, 3 to 4,
        0 to 5, 5 to 6, 6 to 7, 7 to 8,
        0 to 9, 9 to 10, 10 to 11, 11 to 12,
        0 to 13, 13 to 14, 14 to 15, 15 to 16,
        0 to 17, 17 to 18, 18 to 19, 19 to 20,
    )
    private val angleTriplets = arrayOf(
        intArrayOf(0, 1, 2), intArrayOf(1, 2, 3), intArrayOf(2, 3, 4),
        intArrayOf(0, 5, 6), intArrayOf(5, 6, 7), intArrayOf(6, 7, 8),
        intArrayOf(0, 9, 10), intArrayOf(9, 10, 11), intArrayOf(10, 11, 12),
        intArrayOf(0, 13, 14), intArrayOf(13, 14, 15), intArrayOf(14, 15, 16),
        intArrayOf(0, 17, 18), intArrayOf(17, 18, 19), intArrayOf(18, 19, 20),
    )
    private val fingertips = intArrayOf(4, 8, 12, 16, 20)
    private val palmPoints = intArrayOf(0, 5, 9, 13, 17)
    private val bodyEdges = arrayOf(0 to 2, 2 to 4, 1 to 3, 3 to 5, 0 to 6, 1 to 7)

    fun temporalView(
        raw: RawSequence,
        condition: TemporalCondition,
        phoneCompletedFps: Double = PHONE_COMPLETED_FPS,
        maxLength: Int = MAX_SEQUENCE_LENGTH,
    ): TemporalView {
        raw.validate()
        var indices = when (condition) {
            TemporalCondition.DENSE -> IntArray(raw.length) { it }
            TemporalCondition.PHONE_01_SPARSE -> {
                require(phoneCompletedFps.isFinite() && phoneCompletedFps > 0.0)
                val stepMs = 1000.0 / phoneCompletedFps
                val end = raw.timestampMs.last() + stepMs * 0.25
                val targetCount = if (end < raw.timestampMs.first()) 0 else
                    kotlin.math.ceil((end - raw.timestampMs.first()) / stepMs).toInt()
                val targets = DoubleArray(targetCount) { raw.timestampMs.first() + it * stepMs }
                val selected = selectNearestUnique(raw.timestampMs, targets)
                if (selected.isEmpty()) intArrayOf(0) else selected
            }
        }
        if (indices.size > maxLength) {
            val first = raw.timestampMs[indices.first()]
            val last = raw.timestampMs[indices.last()]
            val targets = DoubleArray(maxLength) { position ->
                if (maxLength == 1) first else first + (last - first) * position / (maxLength - 1)
            }
            val subsetTimestamps = DoubleArray(indices.size) { raw.timestampMs[indices[it]] }
            val local = selectNearestUnique(subsetTimestamps, targets)
            indices = IntArray(local.size) { indices[local[it]] }
        }
        val selected = deriveSelectedFeatures(raw, indices)
        val tensor = FloatArray(maxLength * FEATURE_WIDTH)
        selected.copyInto(tensor)
        val mask = BooleanArray(maxLength) { it < indices.size }
        return TemporalView(
            features = tensor,
            mask = mask,
            sourceIndices = indices,
            sourceTimestampsMs = DoubleArray(indices.size) { raw.timestampMs[indices[it]] },
            realLength = indices.size,
        )
    }

    fun deriveSelectedFeatures(raw: RawSequence, indices: IntArray): FloatArray {
        raw.validate()
        require(indices.isNotEmpty())
        for (index in 1 until indices.size) require(indices[index] > indices[index - 1])
        val output = FloatArray(indices.size * FEATURE_WIDTH)
        val previousStates = arrayOfNulls<HandState>(2)
        var previousInter = Vec2(0f, 0f)
        var previousInterValid = false
        var previousTimestamp: Double? = null
        val clipStart = raw.timestampMs.first()
        val clipDuration = maxOf(raw.timestampMs.last() - clipStart, 0.0)

        for ((row, frame) in indices.withIndex()) {
            var offset = row * FEATURE_WIDTH
            val bodyFrame = bodyFrame(raw, frame)
            val states = arrayOfNulls<HandState>(2)
            for (side in 0..1) {
                val effective = BooleanArray(21) {
                    raw.handValid(frame, side, it) && raw.observed(frame, side)
                }
                val state = handState(raw, frame, side, effective, bodyFrame)
                states[side] = state
                offset = writeHandStatic(
                    output, offset, state, raw.presence(frame, side), raw, frame, side, effective,
                )
            }
            offset = writeBody(output, offset, raw, frame, bodyFrame)
            val left = requireNotNull(states[0])
            val right = requireNotNull(states[1])
            val bothWrist = left.wristBodyValid && right.wristBodyValid
            val bothCenter = left.centerBodyValid && right.centerBodyValid
            val wristDelta = if (bothWrist) right.wristBody - left.wristBody else Vec2(0f, 0f)
            val centerDelta = if (bothCenter) right.centerBody - left.centerBody else Vec2(0f, 0f)
            output[offset++] = wristDelta.x
            output[offset++] = wristDelta.y
            output[offset++] = centerDelta.x
            output[offset++] = centerDelta.y
            output[offset++] = if (bothWrist) norm(wristDelta) else 0f
            output[offset++] = if (bothCenter) norm(centerDelta) else 0f
            output[offset++] = if (left.observed && right.observed) 1f else 0f

            val timestamp = raw.timestampMs[frame]
            val dtSeconds = previousTimestamp?.let { (timestamp - it) / 1000.0 } ?: 0.0
            for (side in 0..1) {
                offset = writeMotion(
                    output, offset, requireNotNull(states[side]), previousStates[side], dtSeconds,
                )
            }
            val interValid = previousTimestamp != null && bothCenter && previousInterValid && dtSeconds > 0
            if (interValid) {
                output[offset++] = squash((centerDelta.x - previousInter.x) / dtSeconds.toFloat())
                output[offset++] = squash((centerDelta.y - previousInter.y) / dtSeconds.toFloat())
            } else {
                output[offset++] = 0f
                output[offset++] = 0f
            }
            output[offset++] = if (interValid) 1f else 0f
            output[offset++] = dtSeconds.coerceIn(0.0, 1.0).toFloat()
            output[offset++] = if (clipDuration > 0.0) {
                ((timestamp - clipStart) / clipDuration).toFloat()
            } else 0f
            check(offset == (row + 1) * FEATURE_WIDTH) { "V2 width construction mismatch" }
            previousStates[0] = left
            previousStates[1] = right
            previousInter = centerDelta
            previousInterValid = bothCenter
            previousTimestamp = timestamp
        }
        require(output.all { it.isFinite() }) { "V2 feature tensor contains NaN/Inf" }
        return output
    }

    fun selectNearestUnique(timestamps: DoubleArray, targets: DoubleArray): IntArray {
        val selected = ArrayList<Int>()
        for (target in targets) {
            val candidate = lowerBound(timestamps, target)
            var best = -1
            var bestDistance = Double.POSITIVE_INFINITY
            for (option in intArrayOf(candidate - 1, candidate)) {
                if (option !in timestamps.indices) continue
                val distance = abs(timestamps[option] - target)
                if (distance < bestDistance || (distance == bestDistance && option < best)) {
                    best = option
                    bestDistance = distance
                }
            }
            if (best >= 0 && (selected.isEmpty() || best > selected.last())) selected.add(best)
        }
        return selected.toIntArray()
    }

    private fun bodyFrame(raw: RawSequence, frame: Int): BodyFrame {
        for ((left, right) in arrayOf(0 to 1, 6 to 7)) {
            if (!raw.bodyIsValid(frame, left) || !raw.bodyIsValid(frame, right)) continue
            val delta = Vec2(
                raw.bodyX(frame, left) - raw.bodyX(frame, right),
                raw.bodyY(frame, left) - raw.bodyY(frame, right),
            )
            val axis = unit(delta, 8f)
            if (axis.valid) {
                return BodyFrame(
                    center = Vec2(
                        (raw.bodyX(frame, left) + raw.bodyX(frame, right)) * 0.5f,
                        (raw.bodyY(frame, left) + raw.bodyY(frame, right)) * 0.5f,
                    ),
                    axisX = axis.value,
                    axisY = Vec2(-axis.value.y, axis.value.x),
                    scale = norm(delta),
                    valid = true,
                )
            }
        }
        return BodyFrame(
            center = Vec2(raw.width(frame) * 0.5f, raw.height(frame) * 0.5f),
            axisX = Vec2(1f, 0f), axisY = Vec2(0f, 1f),
            scale = maxOf(minOf(raw.width(frame), raw.height(frame)).toFloat(), 1f),
            valid = false,
        )
    }

    private fun handState(
        raw: RawSequence,
        frame: Int,
        side: Int,
        usable: BooleanArray,
        body: BodyFrame,
    ): HandState {
        fun point(joint: Int) = Vec2(raw.handX(frame, side, joint), raw.handY(frame, side, joint))
        val required = usable[0] && usable[5] && usable[9] && usable[17]
        val axisY = if (required) unit(point(9) - point(0)) else UnitResult(Vec2(0f, 0f), false)
        var axisX = UnitResult(Vec2(0f, 0f), false)
        if (axisY.valid) {
            val candidate = point(5) - point(17)
            val projection = dot(candidate, axisY.value)
            axisX = unit(candidate - axisY.value * projection)
        }
        val palmLength = if (required) norm(point(9) - point(0)) else 0f
        val palmWidth = if (required) norm(point(5) - point(17)) else 0f
        val palmScale = (palmLength + palmWidth) * 0.5f
        val referenceValid = required && axisX.valid && palmScale.isFinite() && palmScale >= 4f
        val local = FloatArray(21 * 2)
        if (referenceValid) for (joint in 0 until 21) {
            if (!usable[joint]) continue
            val delta = point(joint) - point(0)
            local[joint * 2] = dot(delta, axisX.value) / palmScale
            local[joint * 2 + 1] = dot(delta, axisY.value) / palmScale
        }
        fun localPoint(joint: Int) = Vec2(local[joint * 2], local[joint * 2 + 1])
        val boneUnit = FloatArray(40)
        val boneValid = BooleanArray(20)
        if (referenceValid) for ((edgeIndex, edge) in handEdges.withIndex()) {
            if (!usable[edge.first] || !usable[edge.second]) continue
            val value = unit(localPoint(edge.second) - localPoint(edge.first))
            if (value.valid) {
                boneUnit[edgeIndex * 2] = value.value.x
                boneUnit[edgeIndex * 2 + 1] = value.value.y
                boneValid[edgeIndex] = true
            }
        }
        val angleSinCos = FloatArray(30)
        val angleValid = BooleanArray(15)
        for ((angleIndex, triplet) in angleTriplets.withIndex()) {
            val before = triplet[0]
            val joint = triplet[1]
            val after = triplet[2]
            if (!referenceValid || !usable[before] || !usable[joint] || !usable[after]) continue
            val first = unit(localPoint(before) - localPoint(joint))
            val second = unit(localPoint(after) - localPoint(joint))
            if (first.valid && second.valid) {
                angleSinCos[angleIndex * 2] =
                    first.value.x * second.value.y - first.value.y * second.value.x
                angleSinCos[angleIndex * 2 + 1] = dot(first.value, second.value)
                angleValid[angleIndex] = true
            }
        }
        val fingertipLocal = FloatArray(10)
        val fingertipValid = BooleanArray(5)
        for ((tipIndex, joint) in fingertips.withIndex()) {
            val valid = usable[joint] && referenceValid
            fingertipValid[tipIndex] = valid
            if (valid) {
                fingertipLocal[tipIndex * 2] = local[joint * 2]
                fingertipLocal[tipIndex * 2 + 1] = local[joint * 2 + 1]
            }
        }
        val wristBodyValid = raw.observed(frame, side) && usable[0] && body.valid
        val centerBodyValid = referenceValid && body.valid
        val wristBody = if (wristBodyValid) toBody(point(0), body) else Vec2(0f, 0f)
        var validPalmCount = 0
        var palmX = 0f
        var palmY = 0f
        if (referenceValid) for (joint in palmPoints) if (usable[joint]) {
            palmX += point(joint).x
            palmY += point(joint).y
            validPalmCount++
        }
        val palmCenter = if (referenceValid && validPalmCount >= 4) {
            Vec2(palmX / validPalmCount, palmY / validPalmCount)
        } else Vec2(0f, 0f)
        val centerBody = if (centerBodyValid) toBody(palmCenter, body) else Vec2(0f, 0f)
        val palmAxisBody = if (referenceValid && body.valid) {
            Vec2(dot(axisY.value, body.axisX), dot(axisY.value, body.axisY))
        } else Vec2(0f, 0f)
        return HandState(
            boneUnit, boneValid, angleSinCos, angleValid, fingertipLocal, fingertipValid,
            wristBody, centerBody, palmAxisBody, raw.observed(frame, side), referenceValid,
            wristBodyValid, centerBodyValid,
        )
    }

    private fun writeHandStatic(
        output: FloatArray,
        start: Int,
        state: HandState,
        presence: Float,
        raw: RawSequence,
        frame: Int,
        side: Int,
        effective: BooleanArray,
    ): Int {
        var offset = start
        state.boneUnit.copyInto(output, offset); offset += state.boneUnit.size
        for (value in state.boneValid) output[offset++] = if (value) 1f else 0f
        state.angleSinCos.copyInto(output, offset); offset += state.angleSinCos.size
        for (value in state.angleValid) output[offset++] = if (value) 1f else 0f
        state.fingertipLocal.copyInto(output, offset); offset += state.fingertipLocal.size
        for (value in state.fingertipValid) output[offset++] = if (value) 1f else 0f
        output[offset++] = state.wristBody.x
        output[offset++] = state.wristBody.y
        output[offset++] = state.centerBody.x
        output[offset++] = state.centerBody.y
        output[offset++] = state.palmAxisBody.x
        output[offset++] = state.palmAxisBody.y
        var supportSum = 0f
        var supportCount = 0
        for (joint in 0 until 21) {
            val support = raw.handSupport(frame, side, joint)
            if (effective[joint] && support.isFinite()) {
                supportSum += support
                supportCount++
            }
        }
        output[offset++] = if (presence.isFinite()) presence else 0f
        output[offset++] = if (state.observed) 1f else 0f
        output[offset++] = if (supportCount > 0) supportSum / supportCount else 0f
        output[offset++] = if (state.referenceValid) 1f else 0f
        check(offset == start + 130)
        return offset
    }

    private fun writeBody(
        output: FloatArray,
        start: Int,
        raw: RawSequence,
        frame: Int,
        body: BodyFrame,
    ): Int {
        var offset = start
        val edgeVectors = FloatArray(12)
        val edgeValid = BooleanArray(6)
        for ((index, edge) in bodyEdges.withIndex()) {
            if (!raw.bodyIsValid(frame, edge.first) || !raw.bodyIsValid(frame, edge.second)) continue
            val source = unit(
                Vec2(
                    raw.bodyX(frame, edge.second) - raw.bodyX(frame, edge.first),
                    raw.bodyY(frame, edge.second) - raw.bodyY(frame, edge.first),
                ),
            )
            if (source.valid) {
                edgeVectors[index * 2] = dot(source.value, body.axisX)
                edgeVectors[index * 2 + 1] = dot(source.value, body.axisY)
                edgeValid[index] = true
            }
        }
        edgeVectors.copyInto(output, offset); offset += edgeVectors.size
        for (valid in edgeValid) output[offset++] = if (valid) 1f else 0f
        for (point in 0 until 8) {
            val support = raw.bodyPointSupport(frame, point)
            output[offset++] = if (support.isFinite()) support else 0f
        }
        for (point in 0 until 8) output[offset++] = if (raw.bodyIsValid(frame, point)) 1f else 0f
        output[offset++] = if (raw.bodyAvailable[frame]) 1f else 0f
        output[offset++] = if (body.valid) 1f else 0f
        check(offset == start + 36)
        return offset
    }

    private fun writeMotion(
        output: FloatArray,
        start: Int,
        current: HandState,
        previous: HandState?,
        dtSeconds: Double,
    ): Int {
        val values = FloatArray(14)
        val validity = BooleanArray(7)
        if (previous != null && dtSeconds.isFinite() && dtSeconds > 0.0) {
            fun addPair(offset: Int, validIndex: Int, now: Vec2, old: Vec2, valid: Boolean) {
                if (!valid) return
                values[offset] = squash((now.x - old.x) / dtSeconds.toFloat())
                values[offset + 1] = squash((now.y - old.y) / dtSeconds.toFloat())
                validity[validIndex] = true
            }
            addPair(
                0, 0, current.wristBody, previous.wristBody,
                current.wristBodyValid && previous.wristBodyValid,
            )
            addPair(
                2, 1, current.centerBody, previous.centerBody,
                current.centerBodyValid && previous.centerBodyValid,
            )
            for (tip in 0 until 5) {
                addPair(
                    4 + tip * 2,
                    2 + tip,
                    Vec2(current.fingertipLocal[tip * 2], current.fingertipLocal[tip * 2 + 1]),
                    Vec2(previous.fingertipLocal[tip * 2], previous.fingertipLocal[tip * 2 + 1]),
                    current.fingertipValid[tip] && previous.fingertipValid[tip],
                )
            }
        }
        var offset = start
        values.copyInto(output, offset); offset += values.size
        for (valid in validity) output[offset++] = if (valid) 1f else 0f
        check(offset == start + 21)
        return offset
    }

    private fun toBody(point: Vec2, body: BodyFrame): Vec2 {
        val delta = point - body.center
        return Vec2(dot(delta, body.axisX) / body.scale, dot(delta, body.axisY) / body.scale)
    }

    private fun unit(value: Vec2, minimum: Float = 1.0e-6f): UnitResult {
        val length = norm(value)
        if (!length.isFinite() || length < minimum) return UnitResult(Vec2(0f, 0f), false)
        return UnitResult(Vec2(value.x / length, value.y / length), true)
    }

    private fun norm(value: Vec2): Float = sqrt(value.x * value.x + value.y * value.y)
    private fun dot(left: Vec2, right: Vec2): Float = left.x * right.x + left.y * right.y
    private fun squash(valuePerSecond: Float): Float = tanh((valuePerSecond / 4f).toDouble()).toFloat()
    private operator fun Vec2.minus(other: Vec2) = Vec2(x - other.x, y - other.y)
    private operator fun Vec2.times(scale: Float) = Vec2(x * scale, y * scale)

    private fun lowerBound(values: DoubleArray, target: Double): Int {
        var low = 0
        var high = values.size
        while (low < high) {
            val middle = (low + high) ushr 1
            if (values[middle] < target) low = middle + 1 else high = middle
        }
        return low
    }
}
