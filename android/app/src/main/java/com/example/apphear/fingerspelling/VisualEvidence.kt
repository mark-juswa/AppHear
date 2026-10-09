package com.example.apphear.fingerspelling

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.sqrt
import java.nio.ByteBuffer

/** Frozen experimental quality/crop contract; values loaded from pinned export manifest. */
data class VisualRules(
    val expansion: Float, val minimumSide: Float, val cropIntersection: Double,
    val presence: Float, val validJoints: Int, val supportThreshold: Float,
    val supportedJoints: Int, val intersection: Double, val containment: Double,
    val duplicateIou: Double, val duplicateCenter: Float, val duplicateLandmark: Float,
    val duplicateRatio: Float, val duplicateJoints: Int, val cropSize: Int,
)

data class VisualQuality(val weights: FloatArray, val rois: Array<FloatArray>,
                         val rejectionBits: IntArray, val duplicate: Boolean)

class CropQualityFilterV1(private val rules: VisualRules) {
    fun evaluate(c: CommonObservation): VisualQuality {
        val q = FloatArray(2); val rois = Array(2) { FloatArray(3) }; val rejected = IntArray(2)
        for (s in 0..1) {
            val original = c.roi[s]
            val basic = c.proposal[s] && original.all { it.isFinite() } && original[2] >= rules.minimumSide
            val r = original.copyOf(); r[2] *= rules.expansion
            val half = r[2] * .5f
            val border = if (basic) {
                val width = maxOf(0.0, minOf((r[0]+half).toDouble(), c.width.toDouble()) - maxOf((r[0]-half).toDouble(), 0.0))
                val height = maxOf(0.0, minOf((r[1]+half).toDouble(), c.height.toDouble()) - maxOf((r[1]-half).toDouble(), 0.0))
                width * height / (r[2].toDouble() * r[2])
            } else 0.0
            val cropValid = basic && border >= rules.cropIntersection
            val joints = c.valid[s].count { it }
            val supported = c.support[s].count { it >= rules.supportThreshold }
            val inside = if (cropValid && joints > 0) (0 until 21).count {
                c.valid[s][it] && abs(c.xy[s][2*it]-r[0]) <= half && abs(c.xy[s][2*it+1]-r[1]) <= half
            }.toDouble() / joints else 0.0
            val failures = booleanArrayOf(!cropValid, !c.observed[s],
                !c.presence[s].isFinite() || c.presence[s] < rules.presence,
                joints < rules.validJoints, supported < rules.supportedJoints,
                border < rules.intersection, inside < rules.containment)
            for (k in failures.indices) if (failures[k]) rejected[s] = rejected[s] or (1 shl k)
            if (rejected[s] == 0) {
                q[s] = (minOf(1.0, c.presence[s].toDouble()) * joints / 21.0 * supported / 21.0 * border * inside).toFloat()
                rois[s] = r
            }
        }
        var duplicate = false
        if (q.all { it > 0f }) {
            val a = rois[0]; val b = rois[1]; val side = minOf(a[2], b[2])
            val widths = FloatArray(2) { axis -> maxOf(0f, minOf(a[axis]+a[2]/2f,b[axis]+b[2]/2f)-maxOf(a[axis]-a[2]/2f,b[axis]-b[2]/2f)) }
            val overlap = widths[0] * widths[1]
            val iou = overlap.toDouble() / (a[2].toDouble()*a[2] + b[2].toDouble()*b[2] - overlap)
            val distances = (0 until 21).filter { c.valid[0][it] && c.valid[1][it] }.map {
                val x = c.xy[0][2*it]-c.xy[1][2*it]; val y = c.xy[0][2*it+1]-c.xy[1][2*it+1]
                sqrt((x*x+y*y).toDouble()).toFloat()
            }.sorted()
            val median = if (distances.isEmpty()) Float.POSITIVE_INFINITY else if (distances.size % 2 == 1)
                distances[distances.size/2] else (distances[distances.size/2-1]+distances[distances.size/2])/2f
            val dx = a[0]-b[0]; val dy = a[1]-b[1]
            duplicate = iou >= rules.duplicateIou && sqrt((dx*dx+dy*dy).toDouble()).toFloat()/side <= rules.duplicateCenter &&
                median/side <= rules.duplicateLandmark && distances.size >= rules.duplicateJoints && maxOf(a[2],b[2])/side <= rules.duplicateRatio
            if (duplicate) q[if (q[0] >= q[1]) 1 else 0] = 0f
        }
        return VisualQuality(q, rois, rejected, duplicate)
    }
}

/** Read-only upright, unreflected source RGB. Out-of-source pixels are zero RGB. */
interface RgbSource { val width: Int; val height: Int; fun channel(x: Int, y: Int, channel: Int): Float }

/** Same inverse rotation/addressing as Candidate01 native preprocessing, without reflection. */
class UprightRgbaSource(private val rawWidth: Int, private val rawHeight: Int,
    private val rowStride: Int, private val pixelStride: Int, private val rotation: Int,
    buffer: ByteBuffer): RgbSource {
    private val bytes=buffer.duplicate(); private val base=bytes.position()
    override val width=if(rotation==90 || rotation==270) rawHeight else rawWidth
    override val height=if(rotation==90 || rotation==270) rawWidth else rawHeight
    init { require(rawWidth>0 && rawHeight>0 && rotation in intArrayOf(0,90,180,270) && pixelStride>=4)
        require(rowStride >= (rawWidth-1)*pixelStride+4 && bytes.remaining() >= (rawHeight-1)*rowStride+(rawWidth-1)*pixelStride+4) }
    override fun channel(x:Int,y:Int,channel:Int):Float {
        require(x in 0 until width && y in 0 until height && channel in 0..2)
        val rx:Int; val ry:Int
        when(rotation) {
            90 -> { rx=y; ry=rawHeight-1-x }
            180 -> { rx=rawWidth-1-x; ry=rawHeight-1-y }
            270 -> { rx=rawWidth-1-y; ry=x }
            else -> { rx=x; ry=y }
        }
        return (bytes.get(base+ry*rowStride+rx*pixelStride+channel).toInt() and 255).toFloat()
    }
}

object HandCropExtractorV1 {
    /** ROI already expanded by quality. Endpoint-aligned float32 arithmetic matches Python. */
    fun crop(source: RgbSource, roi: FloatArray, size: Int): FloatArray {
        val out = FloatArray(size*size*3)
        fun read(x: Int, y: Int, c: Int) = if (x < 0 || y < 0 || x >= source.width || y >= source.height) 0f else source.channel(x,y,c)
        for (y in 0 until size) for (x in 0 until size) {
            val sx = (roi[0]-roi[2]*.5f) + x.toFloat()/(size-1).toFloat()*roi[2]
            val sy = (roi[1]-roi[2]*.5f) + y.toFloat()/(size-1).toFloat()*roi[2]
            val x0 = floor(sx.toDouble()).toInt(); val y0 = floor(sy.toDouble()).toInt()
            val wx = sx-x0.toFloat(); val wy = sy-y0.toFloat()
            for (c in 0..2) {
                val top = read(x0,y0,c)*(1f-wx)+read(x0+1,y0,c)*wx
                val bottom = read(x0,y0+1,c)*(1f-wx)+read(x0+1,y0+1,c)*wx
                out[(y*size+x)*3+c] = (top*(1f-wy)+bottom*wy)/127.5f-1f
            }
        }
        return out
    }
}
