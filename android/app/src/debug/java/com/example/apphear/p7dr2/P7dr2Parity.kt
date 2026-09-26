package com.example.apphear.p7dr2

import com.example.apphear.p7d.P7dMath
import com.example.apphear.p7dr1.P7dr1Preprocess
import com.example.apphear.p7dr1.P7dr1Decoder
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Random
import kotlin.math.abs
import org.json.JSONObject
import org.json.JSONArray
import org.tensorflow.lite.Interpreter

/** Untimed device tests of the actual ARM64 library. Synthetic data only. */
internal object P7dr2Parity {
    private fun rgba(w:Int,h:Int,row:Int,pattern:Int):ByteBuffer {
        val src=ByteBuffer.allocateDirect(17+row*h);val random=Random(707)
        for(y in 0 until h)for(x in 0 until w)for(c in 0..3){
            val v=when(pattern){0->0;1->255;2->(x*31+y*17+c*67)and 255
                3->if((x+y)%2==0)0 else 255;4->random.nextInt(256)
                else->if(x==0||y==0||x==w-1||y==h-1)255-c*31 else 0}
            src.put(17+y*row+x*4+c,v.toByte())
        }
        src.position(17);return src
    }
    private fun diff(a:Float,b:Float,atol:Double=1e-5,rtol:Double=0.0):Double {
        check(a.isFinite()&&b.isFinite()){"NONFINITE_PARITY"}
        val d=abs(a.toDouble()-b);check(d<=atol+rtol*abs(a)){"PARITY_DIFFERENCE $a $b $d"};return d
    }
    private fun rejected(block:()->Unit):String {
        try{block()}catch(e:IllegalArgumentException){return e.message ?: ""}
        error("EXPECTED_REJECTION")
    }
    fun preprocessing():JSONObject {
        var cases=0;var max=0.0;var relative=0.0
        for((w,h)in listOf(7 to 5,5 to 7,640 to 480,480 to 640,1 to 1,101 to 79))for(rot in intArrayOf(0,90,180,270)){
            val row=w*4+12;val jvm=P7dr1Preprocess(w,h,row,4,rot)
            P7dr2Kernel(w,h,row,4,rot).use {native->
                val t=jvm.transform
                check(native.geometry().contentEquals(intArrayOf(t.width,t.height,t.rw,t.rh,t.left,t.top)))
                val allowed=native.allowed()
                for(k in 0 until 9216)check((allowed[k].toInt()!=0)==t.admissible(k%96,k/96))
                for(pattern in 0..5){
                    val src=rgba(w,h,row,pattern);jvm.run(src);native.preprocess(src);check(src.position()==17)
                    for(k in 0 until 384*384*3){val a=jvm.input.getFloat(k*4);val b=native.input.getFloat(k*4)
                        val d=diff(a,b,1e-5,1e-6);max=maxOf(max,d);if(a!=0f)relative=maxOf(relative,d/abs(a))}
                    cases++
                }
            }
        }
        return JSONObject().put("passed",true).put("cases",cases).put("max_abs",max).put("max_relative_nonzero",relative)
            .put("outside_tolerance",0).put("mapping_exact",true).put("finite",true).put("atol",1e-5).put("rtol",1e-6)
    }
    fun decoding():JSONObject {
        var cases=0;var maxXY=0.0;var maxConfidence=0.0;var maxIdentity=0.0
        for((w,h)in listOf(384 to 384,480 to 640,640 to 480,101 to 79)){
            val t=P7dMath.Transform(w,h);val ref=P7dr1Decoder(t);val admissible=(0 until 9216).filter{ref.allowed[it]}
            P7dr2Kernel(w,h,w*4,4,0).use {native->
                for(pattern in 0..7){
                    val heat=FloatArray(460800){-10f};val rng=Random(707);val first=admissible.first();val last=admissible.last()
                    for(p in 0 until 50)when(pattern){
                        0->heat[admissible[admissible.size/2]*50+p]=8f
                        1->heat[first*50+p]=8f;2->heat[last*50+p]=8f
                        3->{heat[first*50+p]=8f;heat[last*50+p]=8f}
                        4->{heat[admissible[admissible.size/2]*50+p]=2f;heat[admissible[admissible.size/2+1]*50+p]=1f}
                    }
                    if(pattern==5)heat.fill(0f)
                    if(pattern==6)for(k in heat.indices)heat[k]=if(k%2==0)Float.MAX_VALUE else -Float.MAX_VALUE
                    if(pattern==7)for(k in heat.indices)heat[k]=rng.nextFloat()*30-15
                    for(cell in 0 until 9216)if(!ref.allowed[cell])for(p in 0 until 50)heat[cell*50+p]=Float.MAX_VALUE
                    val ids=floatArrayOf(-1000f,1000f);ref.decode(heat,ids);ref.restore();native.decode(heat,ids);native.restore()
                    check(ref.peaks.contentEquals(native.peaks)){"PEAK_MISMATCH"}
                    for(k in 0 until 100)maxXY=maxOf(maxXY,diff(ref.inputXY[k],native.xy[k]),diff(ref.sourceXY[k],native.sourceXY[k]))
                    for(k in 0 until 50)maxConfidence=maxOf(maxConfidence,diff(ref.confidence[k],native.confidence[k]))
                    for(k in 0..1)maxIdentity=maxOf(maxIdentity,diff(ref.identity[k],native.identity[k]))
                    cases++
                }
            }
        }
        var nonfinite=0
        P7dr2Kernel(480,640,1920,4,0).use {native->
            val ref=P7dr1Decoder(P7dMath.Transform(480,640))
            for(bad in floatArrayOf(Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY)){
                for(index in intArrayOf(0,460799,230400)){
                    val heat=FloatArray(460800);heat[index]=bad;val ids=FloatArray(2)
                    check(rejected{ref.decode(heat,ids)}==rejected{native.decode(heat,ids)});nonfinite++
                }
                val heat=FloatArray(460800);val ids=floatArrayOf(bad,0f)
                check(rejected{ref.decode(heat,ids)}==rejected{native.decode(heat,ids)});nonfinite++
            }
        }
        val body=P7dMath.effectiveValidity(BooleanArray(50){true},false,false)
        for(p in 0 until 50)check(body[p]==(p>=42))
        return JSONObject().put("passed",true).put("cases",cases).put("nonfinite_cases",nonfinite)
            .put("max_coordinate_abs",maxXY).put("max_confidence_abs",maxConfidence).put("max_identity_abs",maxIdentity)
            .put("winners_ties_content_exact",true).put("nonfinite_rejection_exact",true).put("body_independence",true)
    }
    fun combined(model:File):JSONObject {
        val runtime=Interpreter(model,Interpreter.Options().setNumThreads(2).setUseXNNPACK(true).setUseNNAPI(false))
        runtime.use {
            runtime.allocateTensors()
            val heat=ByteBuffer.allocateDirect(460800*4).order(ByteOrder.nativeOrder())
            val ids=ByteBuffer.allocateDirect(8).order(ByteOrder.nativeOrder())
            val out=HashMap<Int,Any>();for(i in 0..1){val shape=runtime.getOutputTensor(i).shape()
                when{shape.contentEquals(intArrayOf(1,96,96,50))->out[i]=heat
                     shape.contentEquals(intArrayOf(1,1,1,2))->out[i]=ids;else->error("OUTPUT_SHAPE")}}
            check(out.size==2)
            val rows=JSONArray()
            for(rot in intArrayOf(0,90,180,270))for(pattern in intArrayOf(2,4)){
                val jvm=P7dr1Preprocess(640,480,2572,4,rot);val ref=P7dr1Decoder(jvm.transform)
                P7dr2Kernel(640,480,2572,4,rot).use {native->
                    val source=rgba(640,480,2572,pattern);jvm.run(source);native.preprocess(source)
                    var inputDiff=0.0;for(k in 0 until 442368)inputDiff=maxOf(inputDiff,diff(jvm.input.getFloat(k*4),native.input.getFloat(k*4),1e-5,1e-6))
                    runtime.runForMultipleInputsOutputs(arrayOf(jvm.input),out)
                    val a=FloatArray(460800);heat.rewind();heat.asFloatBuffer().get(a)
                    val ia=FloatArray(2);ids.rewind();ids.asFloatBuffer().get(ia)
                    ref.decode(a,ia);ref.restore()
                    heat.rewind();ids.rewind();runtime.runForMultipleInputsOutputs(arrayOf(native.input),out)
                    val b=FloatArray(460800);heat.rewind();heat.asFloatBuffer().get(b)
                    val ib=FloatArray(2);ids.rewind();ids.asFloatBuffer().get(ib)
                    native.decode(b,ib);native.restore()
                    var raw=0.0;for(k in a.indices)raw=maxOf(raw,diff(a[k],b[k],1e-5,1e-6))
                    for(k in 0..1)raw=maxOf(raw,diff(ia[k],ib[k],1e-5,1e-6))
                    check(ref.peaks.contentEquals(native.peaks)){"COMBINED_PEAK_MISMATCH"}
                    var xy=0.0;var conf=0.0;var identity=0.0
                    for(k in 0 until 100)xy=maxOf(xy,diff(ref.inputXY[k],native.xy[k]),diff(ref.sourceXY[k],native.sourceXY[k]))
                    for(k in 0 until 50)conf=maxOf(conf,diff(ref.confidence[k],native.confidence[k]))
                    for(k in 0..1)identity=maxOf(identity,diff(ref.identity[k],native.identity[k]))
                    rows.put(JSONObject().put("rotation",rot).put("pattern",pattern).put("input_max_abs",inputDiff)
                        .put("raw_output_max_abs",raw).put("coordinate_max_abs",xy).put("confidence_max_abs",conf)
                        .put("identity_max_abs",identity).put("winners_exact",true).put("rejection_differences",0))
                }
            }
            return JSONObject().put("passed",true).put("cases",8).put("rows",rows).put("timing_collected",false)
        }
    }
}
