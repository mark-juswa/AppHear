package com.example.apphear.p7d

import java.nio.ByteBuffer
import kotlin.math.exp
import kotlin.math.floor

/** Frozen P7-C math, debug diagnostics only. No calibrated Family-A payload is produced. */
object P7dMath {
    const val SIZE = 384
    const val GRID = 96
    const val POINTS = 50
    const val POLICY = "POLICY_UNCONFIGURED"

    data class Transform(val width: Int, val height: Int) {
        init { require(width > 0 && height > 0) }
        private val scale = minOf(SIZE.toDouble()/width, SIZE.toDouble()/height)
        val rw = maxOf(1, floor(width*scale+.5).toInt())
        val rh = maxOf(1, floor(height*scale+.5).toInt())
        val left = (SIZE-rw)/2
        val top = (SIZE-rh)/2
        fun forwardX(x: Double) = (x+.5)*rw/width-.5+left
        fun forwardY(y: Double) = (y+.5)*rh/height-.5+top
        fun inverseX(x: Double) = (x-left+.5)*width/rw-.5
        fun inverseY(y: Double) = (y-top+.5)*height/rh-.5
        fun admissible(j: Int, i: Int): Boolean = inverseX(4*(j+.5)-.5) in 0.0..(width-1).toDouble() &&
            inverseY(4*(i+.5)-.5) in 0.0..(height-1).toDouble()
    }

    /** Read channel bytes directly with stride; CameraX analysis is not preview-mirrored. */
    fun uprightRgb(buffer: ByteBuffer, w: Int, h: Int, row: Int, pixel: Int, rotation: Int): ByteArray {
        require(rotation in listOf(0,90,180,270) && pixel >= 4)
        val ow = if (rotation == 90 || rotation == 270) h else w
        val oh = if (rotation == 90 || rotation == 270) w else h
        val out = ByteArray(ow*oh*3)
        val base=buffer.position()
        for (y in 0 until oh) for (x in 0 until ow) {
            val sx: Int; val sy: Int
            when(rotation) {
                90 -> { sx=y; sy=h-1-x }
                180 -> { sx=w-1-x; sy=h-1-y }
                270 -> { sx=w-1-y; sy=x }
                else -> { sx=x; sy=y }
            }
            val source=base+sy*row+sx*pixel
            val dest=(y*ow+x)*3
            for (c in 0..2) out[dest+c]=buffer.get(source+c)
        }
        return out
    }

    fun letterbox(rgb: ByteArray, t: Transform, output: ByteBuffer) {
        require(rgb.size==t.width*t.height*3)
        output.clear()
        for (y in 0 until SIZE) for (x in 0 until SIZE) {
            if (x !in t.left until t.left+t.rw || y !in t.top until t.top+t.rh) {
                repeat(3) { output.putFloat(0f) }; continue
            }
            val sx=t.inverseX(x.toDouble()).coerceIn(0.0,(t.width-1).toDouble())
            val sy=t.inverseY(y.toDouble()).coerceIn(0.0,(t.height-1).toDouble())
            val x0=floor(sx).toInt(); val y0=floor(sy).toInt()
            val x1=minOf(x0+1,t.width-1); val y1=minOf(y0+1,t.height-1)
            val wx=(sx-x0).toFloat(); val wy=(sy-y0).toFloat()
            for (c in 0..2) {
                val a=(rgb[(y0*t.width+x0)*3+c].toInt() and 255).toFloat()
                val b=(rgb[(y0*t.width+x1)*3+c].toInt() and 255).toFloat()
                val d=(rgb[(y1*t.width+x0)*3+c].toInt() and 255).toFloat()
                val e=(rgb[(y1*t.width+x1)*3+c].toInt() and 255).toFloat()
                val v=(a*(1-wx)+b*wx)*(1-wy)+(d*(1-wx)+e*wx)*wy
                output.putFloat((v-127.5f)/127.5f)
            }
        }
        output.rewind()
    }

    fun sigmoid(v: Double): Float = (if(v>=0) 1/(1+exp(-v)) else exp(v)/(1+exp(v))).toFloat()
    data class Decoded(val inputXY: FloatArray, val confidence: FloatArray, val identity: FloatArray)

    fun decode(heat: FloatArray, identity: FloatArray, t: Transform): Decoded {
        require(heat.size==GRID*GRID*POINTS && identity.size==2)
        require(heat.all { it.isFinite() } && identity.all { it.isFinite() }) { "NATIVE_OUTPUT_INVALID" }
        val allowed=BooleanArray(GRID*GRID) { t.admissible(it%GRID,it/GRID) }
        require(allowed.any {it}) { "INPUT_TRANSFORM_INVALID" }
        val peaks=IntArray(POINTS) {-1}; val max=FloatArray(POINTS) {Float.NEGATIVE_INFINITY}
        for (cell in allowed.indices) if(allowed[cell]) {
            for (p in 0 until POINTS) {
                val v=heat[cell*POINTS+p]
                if(v>max[p]) { max[p]=v; peaks[p]=cell }
            }
        }
        val xy=FloatArray(POINTS*2); val confidence=FloatArray(POINTS)
        for (p in 0 until POINTS) {
            val px=peaks[p]%GRID; val py=peaks[p]/GRID
            var sum=0.0; var sx=0.0; var sy=0.0
            for (i in maxOf(0,py-1)..minOf(GRID-1,py+1)) for (j in maxOf(0,px-1)..minOf(GRID-1,px+1)) {
                if(!allowed[i*GRID+j]) continue
                val weight=exp(heat[(i*GRID+j)*POINTS+p].toDouble()-max[p])
                sum+=weight; sx+=j*weight; sy+=i*weight
            }
            xy[p*2]=(4*(sx/sum+.5)-.5).toFloat(); xy[p*2+1]=(4*(sy/sum+.5)-.5).toFloat()
            confidence[p]=sigmoid(max[p].toDouble())
        }
        return Decoded(xy,confidence,FloatArray(2) {sigmoid(identity[it].toDouble())})
    }

    fun restore(decoded: Decoded, t: Transform): FloatArray = FloatArray(POINTS*2) { k ->
        (if(k%2==0) t.inverseX(decoded.inputXY[k].toDouble()) else t.inverseY(decoded.inputXY[k].toDouble())).toFloat()
    }

    /** Synthetic interface test helper only; not a validity policy or runtime payload builder. */
    fun effectiveValidity(provisional: BooleanArray, lhObserved: Boolean, rhObserved: Boolean): BooleanArray {
        require(provisional.size==POINTS)
        return BooleanArray(POINTS) { p -> provisional[p] && when(p) { in 0..20->lhObserved; in 21..41->rhObserved; else->true } }
    }
}
