package com.example.apphear.p7d

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.exp

class P7dMathTest {
    @Test fun rotationStrideAndNoMirror() {
        val b=ByteBuffer.allocate(40)
        for(y in 0..1) for(x in 0..2) for(c in 0..2) b.put(y*20+x*5+c,(y*3+x+1).toByte())
        val expected=mapOf(0 to listOf(1,2,3,4,5,6),90 to listOf(4,1,5,2,6,3),180 to listOf(6,5,4,3,2,1),270 to listOf(3,6,2,5,1,4))
        for((r,e) in expected) assertEquals(e,P7dMath.uprightRgb(b,3,2,20,5,r).filterIndexed {i,_->i%3==0}.map {it.toInt()})
    }
    @Test fun transformsRoundTrip() {
        for((w,h) in listOf(480 to 360,360 to 480,101 to 79,1 to 1)) {
            val t=P7dMath.Transform(w,h)
            for(x in listOf(0.0,(w-1)*.37,(w-1).toDouble())) assertEquals(x,t.inverseX(t.forwardX(x)),1e-10)
            for(y in listOf(0.0,(h-1)*.61,(h-1).toDouble())) assertEquals(y,t.inverseY(t.forwardY(y)),1e-10)
        }
    }
    @Test fun bilinearAndPadding() {
        val t=P7dMath.Transform(2,1)
        val out=ByteBuffer.allocate(384*384*3*4).order(ByteOrder.nativeOrder())
        P7dMath.letterbox(byteArrayOf(0,0,0,-1,-1,-1),t,out)
        assertEquals(0f,out.getFloat(0),0f)
        assertEquals(-1f,out.getFloat((96*384)*12),0f)
        val sx=(191+.5)/192-.5
        assertEquals(((sx*255-127.5)/127.5).toFloat(),out.getFloat((100*384+191)*12),1e-6f)
    }
    @Test fun deterministicTieLocal3AndPaddingExclusion() {
        val t=P7dMath.Transform(384,384)
        val heat=FloatArray(96*96*50)
        val d=P7dMath.decode(heat,floatArrayOf(0f,0f),t)
        assertEquals(3.5f,d.inputXY[0],0f); assertEquals(.5f,d.confidence[0],0f)
        val wide=P7dMath.Transform(480,360)
        for(p in 0 until 50) heat[p]=100f
        val e=P7dMath.decode(heat,floatArrayOf(0f,0f),wide)
        assertEquals(.5f,e.confidence[0],0f)
        assertTrue(P7dMath.restore(e,wide).all {it>=0})
    }
    @Test fun localCentroidMath() {
        val heat=FloatArray(96*96*50) {-20f}
        for(p in 0 until 50) {heat[(10*96+10)*50+p]=2f;heat[(10*96+11)*50+p]=1f}
        val d=P7dMath.decode(heat,floatArrayOf(0f,0f),P7dMath.Transform(384,384))
        val sum=1+exp(-1.0)+7*exp(-22.0)
        val center=(10+11*exp(-1.0)+69*exp(-22.0))/sum
        assertEquals((4*(center+.5)-.5).toFloat(),d.inputXY[0],1e-5f)
    }
    @Test fun nonFiniteRejected() {
        for(bad in listOf(Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY)) {
            val h=FloatArray(96*96*50);h[17]=bad
            assertThrows(IllegalArgumentException::class.java) {P7dMath.decode(h,FloatArray(2),P7dMath.Transform(480,360))}
        }
    }
    @Test fun bodyIndependentAndPolicyUnconfigured() {
        val v=P7dMath.effectiveValidity(BooleanArray(50) {true},false,false)
        assertFalse(v.take(42).any {it}); assertTrue(v.drop(42).all {it})
        assertEquals("POLICY_UNCONFIGURED",P7dMath.POLICY)
    }
}
