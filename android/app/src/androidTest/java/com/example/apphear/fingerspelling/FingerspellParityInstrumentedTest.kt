package com.example.apphear.fingerspelling

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import java.io.DataInputStream
import kotlin.math.abs

class FingerspellParityInstrumentedTest {
    @Test fun frozenReferenceParity() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        // The preserved visual fixtures apply only to the pinned rollback package.
        // Geometry candidate transfer is tested independently in Train4096ParityInstrumentedTest.
        FingerspellModels(context).use { org.junit.Assume.assumeTrue(it.visualEnabled) }
        val assets = instrumentation.context.assets
        fun read(name: String) = DataInputStream(assets.open("fingerspelling_fixtures/$name").buffered())
        val cases = JSONObject(assets.open("fingerspelling_fixtures/cases.json").bufferedReader().use { it.readText() })
        var featureError = 0f; var qualityError = 0f; var cropError = 0f; var embeddingError = 0f; var logitError = 0f
        var observationCount = 0
        val started = System.nanoTime()
        FingerspellModels(context).use { models ->
            val names = cases.getJSONArray("observation_cases")
            for (k in 0 until names.length()) {
                val name = names.getString(k)
                read("$name.input.bin").use { input ->
                    assertEquals("FingerspellingFeatureAdapter.v1", input.readUTF())
                    val adapter = FingerspellingFeatureAdapterV1(input.readFloat(), input.readFloat())
                    val n = input.readInt()
                    read("$name.features.bin").use { features -> read("$name.quality.bin").use { quality ->
                        read("$name.rejection.bin").use { rejection -> read("$name.duplicate.bin").use { duplicate ->
                            repeat(n) {
                                val c = common(input)
                                val actual = adapter.derive(c)
                                for (value in actual) { val reference = features.readFloat(); featureError = maxOf(featureError, abs(value-reference)); assertEquals(reference,value,1e-6f) }
                                val q = CropQualityFilterV1(models.rules).evaluate(c)
                                for (s in 0..1) { val reference = quality.readFloat(); qualityError = maxOf(qualityError,abs(q.weights[s]-reference)); assertEquals(reference,q.weights[s],1e-6f); assertEquals(rejection.readInt(),q.rejectionBits[s]) }
                                assertEquals(duplicate.readBoolean(), q.duplicate)
                                observationCount++
                            }
                        }}
                    }}
                }
            }
            read("crop.bin").use { input ->
                val w = input.readInt(); val h = input.readInt(); val rgb = ByteArray(w*h*3).also { input.readFully(it) }
                val roi = FloatArray(3) { input.readFloat() }.also { it[2] *= models.rules.expansion }
                val source = object: RgbSource {
                    override val width=w; override val height=h
                    override fun channel(x:Int,y:Int,channel:Int) = (rgb[(y*w+x)*3+channel].toInt() and 255).toFloat()
                }
                val crop = HandCropExtractorV1.crop(source, roi, models.rules.cropSize)
                for (value in crop) { val reference = input.readFloat(); cropError=maxOf(cropError,abs(value-reference)); assertEquals(reference,value,2e-6f) }
                val emb = models.encode(crop)
                for (value in emb) { val reference=input.readFloat(); embeddingError=maxOf(embeddingError,abs(value-reference)); assertEquals(reference,value,2e-4f) }
            }
            val sequenceCases = cases.getJSONArray("sequence_cases")
            for (k in 0 until sequenceCases.length()) {
                val case = sequenceCases.getJSONObject(k)
                read(case.getString("fixture")+".bin").use { input ->
                    val n = input.readInt()
                    val packed = List(n) { FloatArray(1559) { input.readFloat() } }
                    val reference = Array(n) { FloatArray(28) { input.readFloat() } }
                    val actual = models.logits(packed)
                    for (t in 0 until n) for (c in 0..27) { logitError=maxOf(logitError,abs(actual[t][c]-reference[t][c])); assertEquals(reference[t][c],actual[t][c],2e-4f) }
                    assertEquals(FingerspellCtcDecoder.decode(reference,models.blankPenalty), FingerspellCtcDecoder.decode(actual,models.blankPenalty))
                    val prefix = models.logits(packed.take(n/2))
                    for(t in prefix.indices) for(c in 0..27) assertEquals(actual[t][c],prefix[t][c],2e-4f)
                }
                read(case.getString("fixture")+".b2.bin").use { input ->
                    val n = input.readInt()
                    val packed = List(n) { FloatArray(1559) { input.readFloat() } }
                    val actual = models.logits(packed)
                    for(t in 0 until n) for(c in 0..27) assertEquals(input.readFloat(),actual[t][c],2e-4f)
                }
            }
        }
        val report = JSONObject().put("status","ANDROID_NUMERICAL_PARITY_PASS").put("observation_count",observationCount)
            .put("feature_max_error",featureError).put("quality_max_error",qualityError).put("crop_max_error",cropError)
            .put("embedding_max_error",embeddingError).put("logit_max_error",logitError)
            .put("causal_prefix_cases",6).put("frozen_b2_zero_visual_cases",6)
            .put("seconds",(System.nanoTime()-started)/1e9).put("test_accessed",false)
        context.filesDir.resolve("fingerspell_parity.json").writeText(report.toString(2))
        android.util.Log.i("AppHearFingerspellParity",report.toString())
    }

    internal fun common(input: DataInputStream): CommonObservation {
        val t=input.readDouble(); val w=input.readInt(); val h=input.readInt()
        val xy=Array(2){FloatArray(42)}; val valid=Array(2){BooleanArray(21)}; val support=Array(2){FloatArray(21)}
        val presence=FloatArray(2); val observed=BooleanArray(2); val proposal=BooleanArray(2); val roi=Array(2){FloatArray(3)}
        for(s in 0..1) { for(j in 0..20) { xy[s][2*j]=input.readFloat(); xy[s][2*j+1]=input.readFloat(); valid[s][j]=input.readBoolean(); support[s][j]=input.readFloat() }
            presence[s]=input.readFloat(); observed[s]=input.readBoolean(); proposal[s]=input.readBoolean(); for(a in 0..2) roi[s][a]=input.readFloat() }
        val body=FloatArray(16); val bodySupport=FloatArray(8); val bodyValid=BooleanArray(8)
        for(p in 0..7) { body[2*p]=input.readFloat(); body[2*p+1]=input.readFloat(); bodySupport[p]=input.readFloat(); bodyValid[p]=input.readBoolean() }
        return CommonObservation(t,w,h,xy,valid,support,presence,observed,proposal,roi,body,bodySupport,bodyValid,input.readBoolean())
    }
}
