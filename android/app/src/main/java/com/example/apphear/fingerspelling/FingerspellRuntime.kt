package com.example.apphear.fingerspelling

import android.content.Context
import android.os.SystemClock
import android.util.Log
import androidx.camera.core.ImageProxy
import com.example.apphear.perceptionvnext.PhoneRawObservation
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class FingerspellSnapshot(val mode: RecognitionMode, val phase: FingerspellPhase,
    val preview: String, val confirmed: String, val observations: Int, val message: String,
    val currentLetter: String = "")

/** Camera executor confined. Captures embeddings, not RGB; Done runs bounded full CTC off-main. */
internal class FingerspellRuntime(
    private val context: Context, private val models: FingerspellModels,
    resetWord: () -> Unit, private val publish: (FingerspellSnapshot) -> Unit,
    continuousEnabled: Boolean = false, dispatch: ((() -> Unit) -> Unit) = { it() },
) : AutoCloseable {
    val singleLetterMode = FingerspellCapturePolicy.SINGLE_LETTER_ENABLED &&
        models.manifest.optString("candidate_id")==FingerspellCapturePolicy.CANDIDATE
    private val inputEvidence=FingerspellInputEvidence()
    private val usableEvidence=mutableListOf<Boolean>()
    private val captureTimestamps=mutableListOf<Double>()
    private var singleLetterDecodeCalls=0
    private fun readyMessage()=if(singleLetterMode) "One letter at a time: Start, show the letter, Done" else "Ready to fingerspell"
    private val owner=RecognitionModeController(resetWord)
    private val session=FingerspellSession(models.manifest.getJSONObject("session_limits").getInt("maximum_frames"),
        models.manifest.getJSONObject("session_limits").getDouble("maximum_seconds"), models.inputWidth)
    private val quality=if(models.visualEnabled) CropQualityFilterV1(models.rules) else null
    private val gaps=mutableListOf<Double>(); private val crops=mutableListOf<Double>(); private val encoder=mutableListOf<Double>()
    private val candidate=mutableListOf<Double>(); private val total=mutableListOf<Double>()
    private var previousTimestamp:Double?=null
    private var trustedSlots=0; private var duplicateFrames=0
    private var noCropFrames=0; private var observedFrames=0
    private var firstSourceIndex:Int?=null; private var lastSourceIndex:Int?=null
    private val wordTimestamps=mutableListOf<Double>()
    private val wordCandidate=mutableListOf<Double>()
    private var acceptedObservations=0
    private var captureFinishedNs=0L
    private var captureStartedNs=0L
    private val decoderMode=FingerspellDecoderMode.PREFIX_BEAM_TOP1
    private var beamDecodeCalls=0
    private var greedyDecodeCalls=0
    @Volatile var snapshot=FingerspellSnapshot(RecognitionMode.WORD,FingerspellPhase.READY,"","",0,""); private set
    private val continuous = if (continuousEnabled) ContinuousFingerspell(context,models,resetWord,dispatch) {
        snapshot = it; publish(it)
    } else null
    val continuousMode get() = continuous != null
    val fingerspellOwnsFrames get() = continuous?.ownsFrames ?: (owner.mode == RecognitionMode.FINGERSPELL)
    fun select(mode: RecognitionMode) {
        continuous?.let { it.select(mode); return }
        if(mode==RecognitionMode.FINGERSPELL) writeWordProfile()
        wordTimestamps.clear(); wordCandidate.clear()
        session.cancel(); models.adapter.reset(); owner.select(mode); emit(readyMessage())
    }
    fun recordWordCadence(observation:PhoneRawObservation) {
        if(fingerspellOwnsFrames) return
        wordTimestamps.add(observation.timestampMs)
        observation.candidateTotalMs?.let { wordCandidate.add(it) }
        if(wordTimestamps.size>256) wordTimestamps.removeAt(0)
        if(wordCandidate.size>256) wordCandidate.removeAt(0)
    }
    private fun writeWordProfile() {
        if(wordTimestamps.size<2) return
        val gaps=wordTimestamps.zipWithNext { a,b -> b-a }.sorted()
        val span=(wordTimestamps.last()-wordTimestamps.first())/1000.0
        if(span<=0) return
        val times=wordCandidate.sorted()
        val report=JSONObject().put("schema_version","apphear.fingerspelling.word_cadence.v1")
            .put("delivered_observations",wordTimestamps.size).put("span_seconds",span)
            .put("observations_per_second",(wordTimestamps.size-1)/span)
            .put("gap_p50_ms",gaps[(gaps.size-1)/2]).put("gap_p95_ms",gaps[((gaps.size-1)*.95).toInt()])
            .put("gap_max_ms",gaps.last()).put("candidate_p50_ms",if(times.isEmpty()) JSONObject.NULL else times[(times.size-1)/2])
            .put("candidate_p95_ms",if(times.isEmpty()) JSONObject.NULL else times[((times.size-1)*.95).toInt()])
            .put("keep_only_latest",true).put("dropped_frame_count","NOT_MEASURED").put("training",false)
        File(context.filesDir,"fingerspell_word_cadence.json").writeText(report.toString(2))
    }
    fun start() {
        if (continuousMode) return
        check(fingerspellOwnsFrames)
        if (session.phase == FingerspellPhase.CAPTURING || session.phase == FingerspellPhase.DECODING) return
        session.start(); models.adapter.reset(); previousTimestamp=null
        gaps.clear(); crops.clear(); encoder.clear(); candidate.clear(); total.clear(); trustedSlots=0; duplicateFrames=0
        noCropFrames=0; observedFrames=0; firstSourceIndex=null; lastSourceIndex=null
        acceptedObservations=0
        inputEvidence.reset(); usableEvidence.clear(); captureTimestamps.clear()
        captureStartedNs=SystemClock.elapsedRealtimeNanos()
        emit(if(singleLetterMode) "Show ONE letter, then tap Done" else "Fingerspelling…")
    }
    fun consume(observation: PhoneRawObservation, image: ImageProxy) {
        continuous?.let { it.consume(observation); return }
        if (!fingerspellOwnsFrames || session.phase != FingerspellPhase.CAPTURING) return
        try {
            val started=SystemClock.elapsedRealtimeNanos()
            val common=observation.fingerspellObservation()
            val packed=FloatArray(models.inputWidth)
            models.adapter.derive(common).copyInto(packed)
            if(common.observed.any { it }) observedFrames++
            val usable=inputEvidence.record(common)
            usableEvidence.add(usable); captureTimestamps.add(common.timestampMs)
            if(firstSourceIndex==null) firstSourceIndex=observation.sourceIndex
            lastSourceIndex=observation.sourceIndex
            if(models.visualEnabled) {
            val evidence=checkNotNull(quality).evaluate(common)
            if(evidence.weights.none { it>0f }) noCropFrames++
            if (evidence.duplicate) duplicateFrames++
            val source=PhoneRgbSource(image)
            require(source.width==common.width && source.height==common.height)
            for(s in 0..1) if(evidence.weights[s]>0f) {
                val cropStart=SystemClock.elapsedRealtimeNanos()
                val pixels=HandCropExtractorV1.crop(source,evidence.rois[s],models.rules.cropSize)
                crops.add((SystemClock.elapsedRealtimeNanos()-cropStart)/1e6)
                val encoderStart=SystemClock.elapsedRealtimeNanos()
                models.encode(pixels).copyInto(packed,405+s*576)
                encoder.add((SystemClock.elapsedRealtimeNanos()-encoderStart)/1e6)
                packed[1557+s]=evidence.weights[s]; trustedSlots++
            }
            }
            session.consume(common.timestampMs,packed)
            acceptedObservations=session.count
            previousTimestamp?.let { gaps.add(common.timestampMs-it) }; previousTimestamp=common.timestampMs
            observation.candidateTotalMs?.let { candidate.add(it) }
            total.add((SystemClock.elapsedRealtimeNanos()-started)/1e6)
            // UI refresh at observation cadence, no image or profiling fields in model input.
            emit(if(!singleLetterMode) "Fingerspelling…" else if(usable)
                "Hand evidence present. Show ONE letter, then Done"
                else "Hand not detected. Bring your full hand into view")
        } catch(error:Throwable) { writeFailure("CAPTURE",error); session.fail(); emit("Capture failed: ${error.message.orEmpty()}"); Log.e(TAG,"capture failed",error) }
    }
    fun finish() {
        if (continuousMode) return
        if(!fingerspellOwnsFrames || session.phase != FingerspellPhase.CAPTURING) return
        try {
            captureFinishedNs=SystemClock.elapsedRealtimeNanos()
            if(singleLetterMode) inputEvidence.refusal()?.let { reason ->
                writeFailure("INPUT_EVIDENCE",IllegalStateException(reason))
                session.fail(); emit("No usable hand detected. Retry with your full hand visible.")
                return
            }
            val (token,frames)=session.finish(); emit("Decoding…")
            val start=SystemClock.elapsedRealtimeNanos()
            val logits=models.logits(frames)
            val modelMs=(SystemClock.elapsedRealtimeNanos()-start)/1e6
            val greedyStart=SystemClock.elapsedRealtimeNanos()
            greedyDecodeCalls++
            val greedyRaw=FingerspellCtcDecoder.decode(logits,models.blankPenalty)
            val greedyMs=(SystemClock.elapsedRealtimeNanos()-greedyStart)/1e6
            val beamStart=SystemClock.elapsedRealtimeNanos()
            beamDecodeCalls++
            val beamRaw=FingerspellPrefixBeamDecoder.decode(logits,models.blankPenalty).text
            val beamMs=(SystemClock.elapsedRealtimeNanos()-beamStart)/1e6
            val letterStart=SystemClock.elapsedRealtimeNanos()
            val letterResult=if(singleLetterMode) {
                singleLetterDecodeCalls++
                FingerspellSingleLetterDecoder.decode(logits,models.blankPenalty)
            } else null
            val letterMs=(SystemClock.elapsedRealtimeNanos()-letterStart)/1e6
            val text=letterResult?.text ?: if(decoderMode==FingerspellDecoderMode.PREFIX_BEAM_TOP1) beamRaw else greedyRaw
            val elapsed=(SystemClock.elapsedRealtimeNanos()-start)/1e6
            if(session.complete(token,text)) {
                writeProfile(frames.size,elapsed,text,greedyRaw,beamRaw,modelMs,greedyMs,beamMs,letterResult,letterMs,logits)
                emit(if(text.isBlank()) "No letter recognized. Retry." else if(singleLetterMode)
                    "Check the letter. Use adds it; Retry captures again."
                    else "Review spelling before using it")
            }
        } catch(error:Throwable) { writeFailure("DECODE",error); session.fail(); emit("Decode failed: ${error.message.orEmpty()}"); Log.e(TAG,"decode failed",error) }
    }
    fun confirm() {
        continuous?.let { it.confirm(); return }
        if(session.phase==FingerspellPhase.PREVIEW && session.buffer.preview.isNotBlank()) {
            if(singleLetterMode) session.buffer.confirmLetter() else session.buffer.confirm()
            session.cancel(); emit(if(singleLetterMode) "Letter added. Start for the next letter." else "Spelling confirmed")
        }
    }
    fun retry() {
        continuous?.let { it.retry(); return }
        session.cancel(); models.adapter.reset(); emit(readyMessage()) }
    fun clear() {
        continuous?.let { it.clear(); return }
        session.clear(); models.adapter.reset(); emit(readyMessage()) }
    fun pause() {
        continuous?.let { it.pause(); return }
        wordTimestamps.clear(); wordCandidate.clear(); session.cancel(); models.adapter.reset(); owner.pause(); emit("Session cancelled") }
    private fun emit(message:String) {
        snapshot=FingerspellSnapshot(owner.mode,session.phase,session.buffer.preview,session.buffer.confirmed,session.count,message)
        publish(snapshot)
    }
    private fun writeFailure(stage:String,error:Throwable) {
        runCatching {
            val report=JSONObject().put("schema_version","apphear.fingerspelling.failed_session.v1")
                .put("stage",stage).put("error",error.message.orEmpty())
                .put("accepted_observations",acceptedObservations)
                .put("usable_hand_observations",inputEvidence.usable)
                .put("input_refusal",inputEvidence.refusal() ?: JSONObject.NULL)
                .put("single_letter_mode",singleLetterMode)
                .put("elapsed_seconds",(SystemClock.elapsedRealtimeNanos()-captureStartedNs)/1e9)
                .put("session_limits",models.manifest.getJSONObject("session_limits"))
                .put("retained_slots_seen",trustedSlots).put("no_crop_frames_seen",noCropFrames)
                .put("inference_completed",false).put("training",false)
            val dir=File(context.filesDir,"fingerspelling_sessions").apply { mkdirs() }
            File(dir,"failed_session_${System.currentTimeMillis()}.json").writeText(report.toString(2))
        }.onFailure { Log.e(TAG,"failure diagnostic unavailable",it) }
    }
    private fun writeProfile(n:Int,finishMs:Double,text:String,greedyRaw:String,beamRaw:String,modelMs:Double,greedyMs:Double,beamMs:Double,
                             letterResult:FingerspellSingleLetterDecoder.Result?,letterMs:Double,logits:Array<FloatArray>) {
        fun summary(values:List<Double>):JSONObject {
            val sorted=values.sorted()
            fun percentile(p:Double)=if(sorted.isEmpty()) JSONObject.NULL else sorted[((sorted.size-1)*p).toInt()]
            return JSONObject().put("count",sorted.size).put("p50",percentile(.5)).put("p95",percentile(.95)).put("max",sorted.lastOrNull() ?: JSONObject.NULL)
        }
        val seconds=if(gaps.isEmpty()) 0.0 else gaps.sum()/1000
        val report=JSONObject().put("schema_version","apphear.fingerspelling.phone_session.v1").put("observations",n)
            .put("capture_wall_seconds",(captureFinishedNs-captureStartedNs)/1e9)
            .put("timestamp_span_seconds",seconds).put("observations_per_second",if(seconds>0) (n-1)/seconds else JSONObject.NULL)
            .put("gap_ms",summary(gaps)).put("candidate_ms",summary(candidate)).put("crop_ms",summary(crops))
            .put("appearance_ms",summary(encoder)).put("added_visual_ms",summary(total)).put("finish_ms",finishMs)
            .put("retained_slots",trustedSlots).put("duplicate_frames",duplicateFrames).put("raw_prediction",text)
            .put("greedyRaw",greedyRaw).put("beamRaw",beamRaw).put("previewRaw",text)
            .put("decoder",if(singleLetterMode) "SINGLE_LETTER_CTC_V1" else decoderMode.name).put("beam_width",FingerspellPrefixBeamDecoder.BEAM_WIDTH)
            .put("blank_penalty",models.blankPenalty.toDouble())
            .put("model_ms",modelMs).put("greedy_decode_ms",greedyMs).put("beam_decode_ms",beamMs)
            .put("finish_worker_to_report_ms",(SystemClock.elapsedRealtimeNanos()-captureFinishedNs)/1e6)
            .put("finish_latency_scope","MODEL_AND_BOTH_DECODERS_NOT_BUTTON_QUEUE_OR_UI_RENDER")
            .put("beam_decode_calls",beamDecodeCalls).put("greedy_decode_calls",greedyDecodeCalls)
            .put("single_letter_decode_calls",singleLetterDecodeCalls)
            .put("single_letter_decode_ms",letterMs).put("usable_hand_observations",inputEvidence.usable)
            .put("single_letter_mode",singleLetterMode)
            .put("no_crop_frames",noCropFrames).put("any_hand_observed_frames",observedFrames)
            .put("first_source_index",firstSourceIndex).put("last_source_index",lastSourceIndex)
            .put("reflection","UPRIGHT_UNMIRRORED_SOURCE_RGB").put("backend","CPU_2_THREADS")
            .put("java_heap_bytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())
            .put("native_heap_bytes",android.os.Debug.getNativeHeapAllocatedSize())
            .put("model_manifest",models.manifest).put("training",false)
            .put("visual_branch_enabled",models.visualEnabled).put("model_input_width",models.inputWidth)
        if(letterResult!=null) {
            report.put("single_letter_ctc",JSONObject().put("schema_version",FingerspellSingleLetterDecoder.VERSION)
                .put("text",letterResult.text).put("best_letter",letterResult.bestLetter)
                .put("letter_log_masses",JSONArray(letterResult.letterLogMasses.toList()))
                .put("empty_log_mass",letterResult.emptyLogMass).put("space_log_mass",letterResult.spaceLogMass)
                .put("correctness_confidence","NOT_CALIBRATED_OR_ESTIMATED"))
                .put("logits_unadjusted",JSONArray(logits.map { row -> JSONArray(row.map { it.toDouble() }) }))
                .put("usable_hand_evidence",JSONArray(usableEvidence))
                .put("timestamp_ms",JSONArray(captureTimestamps))
                .put("retained_rgb_or_landmarks",false)
        }
        val dir=File(context.filesDir,"fingerspelling_sessions").apply { mkdirs() }
        File(dir,"session_${System.currentTimeMillis()}.json").writeText(report.toString(2))
        Log.i(TAG,"finish frames=$n cadence=${if(seconds>0) (n-1)/seconds else 0.0} finish_ms=$finishMs")
    }
    override fun close() { if (continuous != null) continuous.close() else { session.cancel(); models.close() } }
    private companion object { const val TAG="AppHearFingerspell" }
}
