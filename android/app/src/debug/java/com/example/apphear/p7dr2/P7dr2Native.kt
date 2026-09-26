package com.example.apphear.p7dr2

import java.nio.ByteBuffer
import java.nio.ByteOrder
import com.example.apphear.p7dr1.P7dr1Preprocess
import com.example.apphear.p7dr1.P7dr1Decoder

internal object P7dr2Native {
    init { System.loadLibrary("p7dr2") } // No fallback if unavailable.
    external fun create(w:Int,h:Int,row:Int,pixel:Int,rotation:Int):Long
    external fun destroy(handle:Long)
    external fun preprocess(handle:Long,source:ByteBuffer,base:Int,remaining:Int,input:ByteBuffer)
    external fun decode(handle:Long,heat:FloatArray,ids:FloatArray,xy:FloatArray,confidence:FloatArray,identity:FloatArray,peaks:IntArray)
    external fun restore(handle:Long,source:FloatArray)
    external fun geometry(handle:Long):IntArray
    external fun allowed(handle:Long):ByteArray
}

/** Owns one native context; never stores JNI pointers across calls or supplies calibrated payloads. */
internal class P7dr2Kernel(w:Int,h:Int,row:Int,pixel:Int,rotation:Int):AutoCloseable {
    private var handle=P7dr2Native.create(w,h,row,pixel,rotation)
    val input=ByteBuffer.allocateDirect(384*384*3*4).order(ByteOrder.nativeOrder())
    val xy=FloatArray(100);val confidence=FloatArray(50);val identity=FloatArray(2)
    val peaks=IntArray(50);val sourceXY=FloatArray(100)
    fun preprocess(source:ByteBuffer){check(handle!=0L);P7dr2Native.preprocess(handle,source,source.position(),source.remaining(),input);input.rewind()}
    fun decode(heat:FloatArray,ids:FloatArray){check(handle!=0L);P7dr2Native.decode(handle,heat,ids,xy,confidence,identity,peaks)}
    fun restore(){check(handle!=0L);P7dr2Native.restore(handle,sourceXY)}
    fun geometry()=P7dr2Native.geometry(handle)
    fun allowed()=P7dr2Native.allowed(handle)
    override fun close(){if(handle!=0L){P7dr2Native.destroy(handle);handle=0}}
}

/** Same coarse operations for all variants; V0 invokes the immutable R1 classes unchanged. */
internal class P7dr2Path(val variant:Int,val width:Int,val height:Int,val rowStride:Int,val pixelStride:Int,val rotation:Int):AutoCloseable {
    init { require(variant in 0..3) }
    private val jvmPre=P7dr1Preprocess(width,height,rowStride,pixelStride,rotation)
    private val jvmDecode=P7dr1Decoder(jvmPre.transform)
    private val native=if(variant==0)null else P7dr2Kernel(width,height,rowStride,pixelStride,rotation)
    val input=if(variant==1||variant==3)native!!.input else jvmPre.input
    fun preprocess(source:ByteBuffer){if(variant==1||variant==3)native!!.preprocess(source)else jvmPre.run(source)}
    fun decode(heat:FloatArray,identity:FloatArray){if(variant>=2)native!!.decode(heat,identity)else jvmDecode.decode(heat,identity)}
    fun restore(){if(variant>=2)native!!.restore()else jvmDecode.restore()}
    override fun close(){native?.close()}
}
