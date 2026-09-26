package com.example.apphear.p7dr1

import com.example.apphear.p7d.P7dMath
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Random
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs

/** Synthetic only. Stdout is retained in Gradle XML as measured parity evidence. */
class P7dr1ParityTest {
    @Test fun preprocessParity() {
        var worst = 0.0; var cases = 0
        val reference = ByteBuffer.allocateDirect(384*384*3*4).order(ByteOrder.nativeOrder())
        for ((w,h) in listOf(7 to 5, 5 to 7, 640 to 480, 480 to 640, 1 to 1, 101 to 79)) {
            for (rotation in intArrayOf(0,90,180,270)) {
                val row = w*4+12
                val opt = P7dr1Preprocess(w,h,row,4,rotation)
                for (pattern in 0..5) {
                    val src = ByteBuffer.allocateDirect(17+row*h)
                    val random = Random(707)
                    for (y in 0 until h) for (x in 0 until w) for(c in 0..3) {
                        val v = when(pattern) {
                            0 -> 0; 1 -> 255
                            2 -> (x*31+y*17+c*67) and 255
                            3 -> if ((x+y)%2 == 0) 0 else 255
                            4 -> random.nextInt(256)
                            else -> if(x==0 || y==0 || x==w-1 || y==h-1) 255-c*31 else 0
                        }
                        src.put(17+y*row+x*4+c,v.toByte())
                    }
                    src.position(17)
                    val rgb = P7dMath.uprightRgb(src,w,h,row,4,rotation)
                    P7dMath.letterbox(rgb,opt.transform,reference)
                    opt.run(src)
                    assertEquals(17,src.position())
                    for (k in 0 until 384*384*3) {
                        val expected = reference.getFloat(k*4); val actual = opt.input.getFloat(k*4)
                        assertTrue(actual.isFinite())
                        val difference = abs(expected.toDouble()-actual)
                        worst = maxOf(worst,difference)
                        assertTrue("tensor $w $h $rotation $pattern $k $expected $actual",difference<=1e-5+1e-6*abs(expected))
                    }
                    cases++
                }
                val t=opt.transform
                for (y in 0 until 384) for (x in 0 until 384) {
                    assertEquals(x in t.left until t.left+t.rw && y in t.top until t.top+t.rh,opt.content(x,y))
                }
                // Verify anatomical source orientation by independent sensor->upright mapping.
                for (y in 0 until h) for (x in 0 until w) {
                    val ux=when(rotation) {90->h-1-y;180->w-1-x;270->y;else->x}
                    val uy=when(rotation) {90->x;180->h-1-y;270->w-1-x;else->y}
                    assertEquals(ux.toDouble(),t.inverseX(t.forwardX(ux.toDouble())),1e-10)
                    assertEquals(uy.toDouble(),t.inverseY(t.forwardY(uy.toDouble())),1e-10)
                }
            }
        }
        println("P7DR1_PREPROCESS cases=$cases max_abs=$worst finite=true mapping_exact=true")
    }

    @Test fun decoderParity() {
        var worstXY=0.0;var worstConfidence=0.0;var cases=0
        for ((w,h) in listOf(384 to 384,480 to 640,640 to 480,101 to 79)) {
            val t=P7dMath.Transform(w,h);val opt=P7dr1Decoder(t)
            val admissible=(0 until 9216).filter {t.admissible(it%96,it/96)}
            for(pattern in 0..7) {
                val heat=FloatArray(460800) {-10f};val rng=Random(707)
                val first=admissible.first();val last=admissible.last()
                for (p in 0 until 50) {
                    when(pattern) {
                        0 -> heat[admissible[admissible.size/2]*50+p]=8f
                        1 -> heat[first*50+p]=8f
                        2 -> heat[last*50+p]=8f
                        3 -> {heat[first*50+p]=8f;heat[last*50+p]=8f}
                        4 -> {heat[admissible[admissible.size/2]*50+p]=2f;heat[admissible[admissible.size/2+1]*50+p]=1f}
                    }
                }
                if(pattern==5)heat.fill(0f)
                if(pattern==6)for(k in heat.indices)heat[k]=if(k%2==0)Float.MAX_VALUE else -Float.MAX_VALUE
                if(pattern==7)for(k in heat.indices)heat[k]=rng.nextFloat()*30-15
                // Padding maxima must not win, but must still be finite-checked.
                for(cell in 0 until 9216)if(!opt.allowed[cell])for(p in 0 until 50)heat[cell*50+p]=Float.MAX_VALUE
                val identity=floatArrayOf(-1000f,1000f)
                val ref=P7dMath.decode(heat,identity,t);val restored=P7dMath.restore(ref,t)
                opt.decode(heat,identity);opt.restore()
                for(p in 0 until 50) {
                    var best=-1;var max=Float.NEGATIVE_INFINITY
                    for(cell in admissible)if(heat[cell*50+p]>max){best=cell;max=heat[cell*50+p]}
                    assertEquals(best,opt.peaks[p])
                    worstConfidence=maxOf(worstConfidence,abs(ref.confidence[p].toDouble()-opt.confidence[p]))
                }
                for(k in 0 until 100) {
                    worstXY=maxOf(worstXY,abs(ref.inputXY[k].toDouble()-opt.inputXY[k]),abs(restored[k].toDouble()-opt.sourceXY[k]))
                }
                assertArrayEquals(ref.identity,opt.identity,0f)
                assertTrue(worstXY<=1e-5);assertTrue(worstConfidence<=1e-5)
                cases++
            }
        }
        println("P7DR1_DECODER cases=$cases max_xy=$worstXY max_confidence=$worstConfidence winners_exact=true")
    }

    @Test fun nonfiniteAndBodyIndependence() {
        val t=P7dMath.Transform(480,640);val opt=P7dr1Decoder(t)
        var cases=0
        for (bad in floatArrayOf(Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY)) {
            for(index in intArrayOf(0,460799,230400)) {
                val heat=FloatArray(460800);val id=FloatArray(2);heat[index]=bad
                assertThrows(IllegalArgumentException::class.java){P7dMath.decode(heat,id,t)}
                assertThrows(IllegalArgumentException::class.java){opt.decode(heat,id)};cases++
            }
            val heat=FloatArray(460800);val id=floatArrayOf(bad,0f)
            assertThrows(IllegalArgumentException::class.java){P7dMath.decode(heat,id,t)}
            assertThrows(IllegalArgumentException::class.java){opt.decode(heat,id)};cases++
        }
        val mask=P7dMath.effectiveValidity(BooleanArray(50){true},false,false)
        for(p in 0 until 50)assertEquals(p>=42,mask[p])
        assertEquals("POLICY_UNCONFIGURED",P7dMath.POLICY)
        println("P7DR1_NONFINITE cases=$cases rejection_exact=true body_independent=true")
    }
}
