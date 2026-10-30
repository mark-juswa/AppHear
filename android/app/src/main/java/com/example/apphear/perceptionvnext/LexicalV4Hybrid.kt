package com.example.apphear.perceptionvnext

import android.content.Context
import org.json.JSONObject
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel

/**
 * Recognition V4 M3 continuous hybrid (branch v4/recognition, context/recognition_v4/M3_HYBRID_PLAN.md,
 * causal spec eval/v4/hybrid_causal.py). Debug engine only.
 *
 * Every observation, the lexical model C2 reads the last [W] observations (Recognition V2 features,
 * computed exactly as for WORD) and emits per-row CTC posteriors over {blank, 236 glosses, OTHER}.
 * [LexicalMarkerDecoder] turns them into sign-position markers. [HybridResolver] then splits S2 events
 * that hold two or more markers and adds segments for in-vocabulary markers that no event covers;
 * WORD (V4) names every resulting segment. Decisions wait [HybridConstants.D] observations after an
 * event's ACTIVE end, and a marker waits until no open decoder candidate started at or before
 * pos + [HybridConstants.B], so the phone makes the same decisions as the scored Python version.
 */
internal object HybridConstants {
    const val W = 24
    const val CLASSES = 238
    const val OTHER = 237
    const val MIN_PROB = 0.5f
    const val DEDUP = 2
    const val A = 2
    const val B = 2
    const val D = 4
}

/** Hash-pinned identity of the C2 lexical package (debug assets). */
internal data class LexicalPackageSpec(val packageId: String, val manifestAsset: String, val manifestSha256: String, val modelSha256: String)

/** One committed C2 marker: [token] 1..236 gloss or [HybridConstants.OTHER]; [pos] absolute observation index. */
internal data class LexicalMarker(val token: Int, val pos: Int, val start: Int, val end: Int, val commit: Int, val peak: Float)

/** A logical segment to name: ACTIVE [start, end], terminal post, and the causal commit its window ends at. */
internal data class HybridSegment(
    val start: Int,
    val end: Int,
    val terminalPost: Int,
    val commit: Int,
    /** Observation index at which the decision was made (the word is committed from here). */
    val emit: Int,
    val origin: String,
)

/** Port of model/v4/lexical.decode_stream(window_probs, keep_other=True), one window per call. */
internal class LexicalMarkerDecoder {
    private var previous: List<Pair<Int, Int>> = emptyList()
    private val committed = ArrayList<LexicalMarker>()

    /**
     * [t] index of the window's last observation, [windowStart] its first; [argmax]/[maxProb] per valid
     * row (row argmax of the softmax and its probability). Returns the markers committed at [t].
     */
    fun consume(t: Int, windowStart: Int, argmax: IntArray, maxProb: FloatArray): List<LexicalMarker> {
        require(argmax.size == maxProb.size && argmax.isNotEmpty())
        val current = ArrayList<Pair<Int, Int>>()
        val out = ArrayList<LexicalMarker>()
        var r = 0
        while (r < argmax.size) {
            val c = argmax[r]
            val s = r
            while (r + 1 < argmax.size && argmax[r + 1] == c) r++
            if (c != 0) {
                var best = s
                for (k in s..r) if (maxProb[k] > maxProb[best]) best = k
                val peak = maxProb[best]
                val pos = windowStart + best
                current.add(c to pos)
                val stable = previous.any { (pt, pp) -> pt == c && kotlin.math.abs(pp - pos) <= 1 }
                if (stable && peak >= HybridConstants.MIN_PROB &&
                    committed.none { kotlin.math.abs(it.pos - pos) <= HybridConstants.DEDUP }
                ) {
                    val m = LexicalMarker(c, pos, windowStart + s, windowStart + r, t, peak)
                    committed.add(m)
                    out.add(m)
                }
            }
            r++
        }
        previous = current
        // committed markers far behind the window can never conflict again
        committed.removeAll { it.pos < t - HybridConstants.W - HybridConstants.DEDUP - 2 }
        return out
    }

    fun reset() {
        previous = emptyList()
        committed.clear()
    }

    companion object {
        /** Row-wise softmax argmax and probability of [W] x [CLASSES] logits, float32 like the Python path. */
        fun rowArgmax(logits: FloatArray, rows: Int): Pair<IntArray, FloatArray> {
            val idx = IntArray(rows)
            val prob = FloatArray(rows)
            for (row in 0 until rows) {
                val base = row * HybridConstants.CLASSES
                var top = 0
                var max = logits[base]
                for (k in 1 until HybridConstants.CLASSES) if (logits[base + k] > max) { max = logits[base + k]; top = k }
                var sum = 0f
                for (k in 0 until HybridConstants.CLASSES) sum += kotlin.math.exp(logits[base + k] - max)
                idx[row] = top
                prob[row] = 1f / sum
            }
            return idx to prob
        }
    }
}

/** Causal split/add resolver; same rules as eval/v4/hybrid_causal.causal_segments. */
internal class HybridResolver(
    private val a: Int = HybridConstants.A,
    private val b: Int = HybridConstants.B,
    private val d: Int = HybridConstants.D,
    /** Only for host replays of finite streams: the last observation index (segments end before it). */
    private val streamLength: Int? = null,
) {
    data class Event(val start: Int, val end: Int, val terminalPost: Int, val commit: Int)

    private val knownEvents = ArrayList<Event>()
    private val knownMarkers = ArrayList<LexicalMarker>()
    private val pendingEvents = ArrayList<Event>()
    private val pendingMarkers = ArrayList<LexicalMarker>()
    private var prevHi = -1

    /**
     * Call once per observation [t], after the decoder and C2 consumed it. [openCandidateStart] is the
     * decoder's open candidate start index (null when no candidate is open). Returns decided segments.
     */
    fun step(t: Int, event: Event?, markers: List<LexicalMarker>, openCandidateStart: Int?): List<HybridSegment> {
        if (event != null) { knownEvents.add(event); pendingEvents.add(event) }
        knownMarkers.addAll(markers)
        pendingMarkers.addAll(markers.filter { it.token != HybridConstants.OTHER })
        val out = ArrayList<HybridSegment>()
        val dueEvents = pendingEvents.filter { maxOf(it.commit, it.end + d) <= t }
        for (e in dueEvents) { out.addAll(split(e, t)); pendingEvents.remove(e) }
        val dueMarkers = pendingMarkers.filter { m ->
            maxOf(m.commit, m.pos + b + 1) <= t && (openCandidateStart == null || openCandidateStart > m.pos + b)
        }.sortedBy { it.pos }
        for (m in dueMarkers) {
            pendingMarkers.remove(m)
            add(m, t)?.let { out.add(it) }
        }
        prune(t)
        return out
    }

    private fun split(e: Event, t: Int): List<HybridSegment> {
        val inside = knownMarkers.filter { it.pos in e.start..e.end }.sortedBy { it.pos }
        if (inside.size < 2) return listOf(HybridSegment(e.start, e.end, e.terminalPost, e.commit, t, "event"))
        val commit = maxOf(e.commit, inside.maxOf { it.commit })
        val bounds = ArrayList<Int>().apply {
            add(e.start)
            for (k in 0 until inside.size - 1) add(Math.floorDiv(inside[k].pos + inside[k + 1].pos, 2) + 1)
            add(e.end + 1)
        }
        return (0 until bounds.size - 1).map { k ->
            val hi = bounds[k + 1] - 1
            val last = k == bounds.size - 2
            HybridSegment(bounds[k], hi, if (last) e.terminalPost else hi + 1, commit, t, "split")
        }
    }

    private fun add(m: LexicalMarker, t: Int): HybridSegment? {
        val pos = m.pos
        if (knownEvents.any { pos in it.start - 1..it.end + 1 }) return null
        var lo = maxOf(0, pos - a, prevHi + 1)
        var hi = pos + b
        streamLength?.let { hi = minOf(hi, it - 2) }
        for (x in knownEvents) {
            if (x.end < pos) lo = maxOf(lo, x.end + 1)
            if (x.start > pos) hi = minOf(hi, x.start - 1)
        }
        if (lo > hi) return null
        prevHi = hi
        return HybridSegment(lo, hi, hi + 1, maxOf(m.commit, hi + 1), t, "add")
    }

    /** Old events/markers can no longer affect a pending decision. */
    private fun prune(t: Int) {
        val horizon = t - 4 * HybridConstants.W
        knownEvents.removeAll { it.end < horizon && it.commit < horizon }
        knownMarkers.removeAll { it.pos < horizon }
    }

    fun reset() {
        knownEvents.clear(); knownMarkers.clear(); pendingEvents.clear(); pendingMarkers.clear(); prevHi = -1
    }
}

/** C2 lexical TFLite ([1,24,350] features + [1,24] mask -> [1,24,238] logits), FP32, XNNPACK, 1 thread. */
internal class LexicalV4Runner(context: Context, spec: LexicalPackageSpec) : AutoCloseable {
    private val manifestBytes = context.assets.open(spec.manifestAsset).use { it.readBytes() }
    private val manifest = JSONObject(manifestBytes.toString(Charsets.UTF_8))
    private val interpreter: Interpreter
    private val features = ByteBuffer.allocateDirect(HybridConstants.W * FEATURES * 4).order(ByteOrder.nativeOrder())
    private val mask = ByteBuffer.allocateDirect(HybridConstants.W).order(ByteOrder.nativeOrder())
    private val output = ByteBuffer.allocateDirect(HybridConstants.W * HybridConstants.CLASSES * 4).order(ByteOrder.nativeOrder())
    private val inputs: Array<Any>
    private var featureInput = -1
    private var maskInput = -1
    val manifestSha256: String = RecognitionV2LiveRecognizer.sha256(manifestBytes)

    init {
        require(manifestSha256 == spec.manifestSha256) { "LEXICAL_V4_MANIFEST_DRIFT" }
        require(manifest.getString("package_id") == spec.packageId)
        require(manifest.getString("feature_schema") == RecognitionV2.FEATURE_SCHEMA) { "LEXICAL_V4_SCHEMA_MISMATCH" }
        require(manifest.getString("model_sha256") == spec.modelSha256)
        val decode = manifest.getJSONObject("decode")
        require(decode.getInt("window") == HybridConstants.W && decode.getInt("classes") == HybridConstants.CLASSES &&
            decode.getInt("other_token") == HybridConstants.OTHER && decode.getDouble("min_prob") == 0.5 &&
            decode.getInt("dedup") == HybridConstants.DEDUP) { "LEXICAL_V4_DECODE_CONTRACT" }
        val hybrid = manifest.getJSONObject("hybrid")
        require(hybrid.getInt("a") == HybridConstants.A && hybrid.getInt("b") == HybridConstants.B &&
            hybrid.getInt("d") == HybridConstants.D) { "LEXICAL_V4_HYBRID_CONTRACT" }
        val asset = manifest.getString("model_asset")
        val bytes = context.assets.open(asset).use { it.readBytes() }
        require(RecognitionV2LiveRecognizer.sha256(bytes) == spec.modelSha256) { "LEXICAL_V4_MODEL_DRIFT" }
        val mapped = context.assets.openFd(asset).use { descriptor ->
            FileInputStream(descriptor.fileDescriptor).channel.use { channel ->
                channel.map(FileChannel.MapMode.READ_ONLY, descriptor.startOffset, descriptor.declaredLength)
            }
        }
        interpreter = Interpreter(mapped, Interpreter.Options().setNumThreads(1).setUseXNNPACK(true).setUseNNAPI(false))
        interpreter.allocateTensors()
        for (index in 0 until interpreter.inputTensorCount) {
            val tensor = interpreter.getInputTensor(index)
            if (tensor.dataType() == DataType.FLOAT32 && tensor.shape().contentEquals(intArrayOf(1, HybridConstants.W, FEATURES))) featureInput = index
            if (tensor.dataType() == DataType.BOOL && tensor.shape().contentEquals(intArrayOf(1, HybridConstants.W))) maskInput = index
        }
        require(featureInput >= 0 && maskInput >= 0 && interpreter.outputTensorCount == 1)
        val out = interpreter.getOutputTensor(0)
        require(out.dataType() == DataType.FLOAT32 && out.shape().contentEquals(intArrayOf(1, HybridConstants.W, HybridConstants.CLASSES)))
        inputs = Array(interpreter.inputTensorCount) { ByteBuffer.allocateDirect(0) }
    }

    /** [rowFeatures]: rows x 350 Recognition V2 features of the window (rows <= W, left-aligned). */
    fun logits(rowFeatures: FloatArray, rows: Int): FloatArray {
        require(rows in 1..HybridConstants.W && rowFeatures.size == rows * FEATURES)
        features.clear()
        val fb = features.asFloatBuffer()
        fb.put(rowFeatures)
        fb.put(FloatArray((HybridConstants.W - rows) * FEATURES))
        features.position(0); features.limit(features.capacity())
        mask.clear()
        for (i in 0 until HybridConstants.W) mask.put(if (i < rows) 1 else 0)
        mask.flip()
        output.clear()
        inputs[featureInput] = features
        inputs[maskInput] = mask
        interpreter.runForMultipleInputsOutputs(inputs, mutableMapOf<Int, Any>(0 to output))
        output.position(0)
        return FloatArray(HybridConstants.W * HybridConstants.CLASSES).also { output.asFloatBuffer().get(it) }
    }

    override fun close() = interpreter.close()

    companion object {
        const val FEATURES = 350
    }
}

/** Per-session lexical path: windows, C2, marker decoding, resolver. */
internal class LexicalV4HybridPath(context: Context, spec: LexicalPackageSpec) : AutoCloseable {
    private val runner = LexicalV4Runner(context, spec)
    private val decoder = LexicalMarkerDecoder()
    private val resolver = HybridResolver()
    val manifestSha256: String get() = runner.manifestSha256
    var lastLexicalMs = 0.0
        private set

    /** [recent]: the observations ending at index [t] (at most W are used). */
    fun observe(t: Int, recent: List<PhoneRawObservation>, event: PhoneLogicalSignEvent?, openCandidateStart: Int?): List<HybridSegment> {
        val started = System.nanoTime()
        require(recent.isNotEmpty() && recent.last().sourceIndex == t) { "LEXICAL_V4_WINDOW_NOT_CURRENT" }
        // Python windows are the last W consecutive observations; keep only the gap-free tail (the ring
        // buffer can age out old observations after a long stall) rather than failing on the camera thread.
        val tail = recent.takeLast(HybridConstants.W)
        val firstContiguous = tail.indices.last { k -> k == 0 || tail[k].sourceIndex != tail[k - 1].sourceIndex + 1 }
        val window = tail.subList(firstContiguous, tail.size)
        val raw = phoneRecognitionRawSequence(window)
        val rows = window.size
        val features = RecognitionV2.deriveSelectedFeatures(raw, IntArray(rows) { it })
        val (argmax, prob) = LexicalMarkerDecoder.rowArgmax(runner.logits(features, rows), rows)
        val markers = decoder.consume(t, window.first().sourceIndex, argmax, prob)
        lastLexicalMs = (System.nanoTime() - started) / 1_000_000.0
        val e = event?.let { HybridResolver.Event(it.logicalActiveStartIndex, it.logicalActiveEndIndex, it.terminalPostIndex, it.commitIndex) }
        return resolver.step(t, e, markers, openCandidateStart)
    }

    fun reset() {
        decoder.reset(); resolver.reset()
    }

    override fun close() = runner.close()
}
