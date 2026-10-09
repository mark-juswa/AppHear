package com.example.apphear.p8b

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.max

/** Debug-rendering contract only. It never mutates model/anatomical coordinates. */
object P8bOverlayContract {
    enum class RenderMode { FULL_TOPOLOGY, POINTS_ONLY }

    data class Edge(val a: Int, val b: Int, val group: String)
    data class DisplayPoint(val x: Float, val y: Float)
    data class DisplayTransform(
        val scale: Float,
        val dx: Float,
        val dy: Float,
        val viewWidth: Int,
        val mirrorPreview: Boolean,
    ) {
        fun x(sourceX: Float): Float {
            val mapped = sourceX * scale + dx
            return if (mirrorPreview) viewWidth - mapped else mapped
        }
        fun y(sourceY: Float): Float = sourceY * scale + dy
    }

    val HAND_EDGES: List<Pair<Int, Int>> = listOf(
        0 to 1, 1 to 2, 2 to 3, 3 to 4,
        0 to 5, 5 to 6, 6 to 7, 7 to 8,
        0 to 9, 9 to 10, 10 to 11, 11 to 12,
        0 to 13, 13 to 14, 14 to 15, 15 to 16,
        0 to 17, 17 to 18, 18 to 19, 19 to 20,
        5 to 9, 9 to 13, 13 to 17,
    )
    val BODY_EDGES: List<Pair<Int, Int>> = listOf(
        42 to 43, 42 to 44, 44 to 46, 43 to 45, 45 to 47,
        42 to 48, 43 to 49, 48 to 49,
    )

    private val FULL_EDGES = buildList {
        HAND_EDGES.forEach { (a, b) -> add(Edge(a, b, "LH")) }
        HAND_EDGES.forEach { (a, b) -> add(Edge(a + 21, b + 21, "RH")) }
        BODY_EDGES.forEach { (a, b) -> add(Edge(a, b, "BODY")) }
    }

    fun edges(mode: RenderMode): List<Edge> =
        if (mode == RenderMode.POINTS_ONLY) emptyList() else FULL_EDGES

    fun displayTransform(
        sourceWidth: Int,
        sourceHeight: Int,
        viewWidth: Int,
        viewHeight: Int,
        mirrorPreview: Boolean,
    ): DisplayTransform {
        require(sourceWidth > 0 && sourceHeight > 0 && viewWidth > 0 && viewHeight > 0)
        val scale = max(viewWidth.toFloat() / sourceWidth, viewHeight.toFloat() / sourceHeight)
        return DisplayTransform(
            scale = scale,
            dx = (viewWidth - sourceWidth * scale) / 2f,
            dy = (viewHeight - sourceHeight * scale) / 2f,
            viewWidth = viewWidth,
            mirrorPreview = mirrorPreview,
        )
    }

    fun mapPoint(
        sourceX: Float,
        sourceY: Float,
        sourceWidth: Int,
        sourceHeight: Int,
        viewWidth: Int,
        viewHeight: Int,
        mirrorPreview: Boolean,
    ): DisplayPoint {
        val transform = displayTransform(sourceWidth, sourceHeight, viewWidth, viewHeight, mirrorPreview)
        return DisplayPoint(transform.x(sourceX), transform.y(sourceY))
    }
}

/** Display-only projection. The stored anatomical/source coordinates are never mirrored. */
class P8bOverlayView(context: Context, attrs: AttributeSet? = null) : View(context, attrs) {
    data class Snapshot(
        val sourceXY: FloatArray,
        val sourceWidth: Int,
        val sourceHeight: Int,
        val mirrorPreview: Boolean,
        val renderMode: P8bOverlayContract.RenderMode = P8bOverlayContract.RenderMode.FULL_TOPOLOGY,
    )

    private var snapshot: Snapshot? = null
    private val leftPaint = paint(Color.rgb(0, 255, 120), 4f)
    private val rightPaint = paint(Color.MAGENTA, 4f)
    private val bodyPaint = paint(Color.YELLOW, 4f)
    private val labelPaint = Paint().apply {
        color = Color.WHITE
        textSize = 30f
        isAntiAlias = true
        setShadowLayer(4f, 1f, 1f, Color.BLACK)
    }
    private val indexPaint = Paint(labelPaint).apply { textSize = 18f }

    fun setSnapshot(value: Snapshot) {
        require(value.sourceXY.size == 100)
        snapshot = value
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val value = snapshot ?: return
        if (value.sourceWidth <= 0 || value.sourceHeight <= 0) return
        val transform = P8bOverlayContract.displayTransform(
            value.sourceWidth, value.sourceHeight, width, height, value.mirrorPreview,
        )
        fun x(point: Int): Float = transform.x(value.sourceXY[point * 2])
        fun y(point: Int): Float = transform.y(value.sourceXY[point * 2 + 1])
        fun line(a: Int, b: Int, paint: Paint) {
            canvas.drawLine(x(a), y(a), x(b), y(b), paint)
        }
        fun point(index: Int, paint: Paint) {
            canvas.drawCircle(x(index), y(index), 7f, paint)
        }
        for (edge in P8bOverlayContract.edges(value.renderMode)) {
            val paint = when (edge.group) { "LH" -> leftPaint; "RH" -> rightPaint; else -> bodyPaint }
            line(edge.a, edge.b, paint)
        }
        for (index in 0..20) point(index, leftPaint)
        for (index in 21..41) point(index, rightPaint)
        for (index in 42..49) point(index, bodyPaint)
        if (value.renderMode == P8bOverlayContract.RenderMode.POINTS_ONLY) {
            for (index in 0..20) canvas.drawText("LH$index", x(index) + 7f, y(index) - 7f, indexPaint)
            for (index in 21..41) canvas.drawText("RH${index - 21}", x(index) + 7f, y(index) - 7f, indexPaint)
            for (index in 42..49) canvas.drawText("B${index - 42}", x(index) + 7f, y(index) - 7f, indexPaint)
        } else {
            canvas.drawText("LH", x(0), y(0) - 12f, labelPaint)
            canvas.drawText("RH", x(21), y(21) - 12f, labelPaint)
        }
    }

    private fun paint(color: Int, width: Float) = Paint().apply {
        this.color = color
        strokeWidth = width
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        isAntiAlias = true
    }

}
