package com.example.apphear.perceptionvnext

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import com.example.apphear.p8b.P8bOverlayContract

/** Display-only overlay; stored observations remain upright/unmirrored source coordinates. */
internal class PerceptionVNextOverlayView(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    data class Hand(
        val xy: FloatArray,
        val valid: BooleanArray,
        val observed: Boolean,
        val presence: Float?,
        val roi: PerceptionVNextMath.HandRoi?,
    )

    data class Snapshot(
        val sourceWidth: Int,
        val sourceHeight: Int,
        val left: Hand,
        val right: Hand,
        val bodyXY: FloatArray,
        val bodySupport: FloatArray,
    )

    @Volatile private var snapshot: Snapshot? = null

    fun setSnapshot(value: Snapshot) {
        snapshot = value
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        snapshot?.let { PerceptionVNextOverlayRenderer.draw(canvas, width, height, it) }
    }
}

/** Shared presentation-only renderer for both the validated debug view and the real app view. */
internal object PerceptionVNextOverlayRenderer {
    private val handEdges = listOf(
        0 to 1,
        1 to 2,
        2 to 3,
        3 to 4,
        0 to 5,
        5 to 6,
        6 to 7,
        7 to 8,
        0 to 9,
        9 to 10,
        10 to 11,
        11 to 12,
        0 to 13,
        13 to 14,
        14 to 15,
        15 to 16,
        0 to 17,
        17 to 18,
        18 to 19,
        19 to 20,
    )
    private val bodyEdges = listOf(0 to 1, 0 to 2, 2 to 4, 1 to 3, 3 to 5, 0 to 6, 1 to 7, 6 to 7)
    private val leftPaint = paint(Color.YELLOW, 5f)
    private val rightPaint = paint(Color.MAGENTA, 5f)
    private val bodyPaint = paint(Color.rgb(0, 255, 110), 4f)
    private val rejectedPaint = paint(Color.argb(160, 180, 180, 180), 2f)
    private val labelPaint = Paint().apply {
        color = Color.WHITE
        textSize = 28f
        isAntiAlias = true
        setShadowLayer(4f, 1f, 1f, Color.BLACK)
    }
    fun draw(canvas: Canvas, width: Int, height: Int, value: PerceptionVNextOverlayView.Snapshot) {
        if (width <= 0 || height <= 0) return
        val display = P8bOverlayContract.displayTransform(
            value.sourceWidth,
            value.sourceHeight,
            width,
            height,
            true,
        )
        fun x(source: Float) = display.x(source)
        fun y(source: Float) = display.y(source)

        fun drawRoi(hand: PerceptionVNextOverlayView.Hand, acceptedPaint: Paint) {
            val roi = hand.roi ?: return
            val paint = if (hand.observed) acceptedPaint else rejectedPaint
            val left = x(roi.right)
            val right = x(roi.left)
            canvas.drawRect(left, y(roi.top), right, y(roi.bottom), paint)
        }
        fun drawHand(hand: PerceptionVNextOverlayView.Hand, acceptedPaint: Paint, label: String) {
            drawRoi(hand, acceptedPaint)
            if (!hand.observed) return
            fun px(point: Int) = x(hand.xy[point * 2])
            fun py(point: Int) = y(hand.xy[point * 2 + 1])
            for ((start, end) in handEdges) {
                if (hand.valid[start] && hand.valid[end]) {
                    canvas.drawLine(px(start), py(start), px(end), py(end), acceptedPaint)
                }
            }
            for (point in 0 until 21) {
                if (hand.valid[point]) canvas.drawCircle(px(point), py(point), 6f, acceptedPaint)
            }
            canvas.drawText(
                "$label ${"%.2f".format(hand.presence ?: 0f)}",
                px(0),
                py(0) - 12f,
                labelPaint,
            )
        }
        fun bodyValid(point: Int): Boolean {
            val sourceX = value.bodyXY[point * 2]
            val sourceY = value.bodyXY[point * 2 + 1]
            return value.bodySupport[point] >= 0.30f && sourceX.isFinite() && sourceY.isFinite() &&
                sourceX >= 0f && sourceX < value.sourceWidth &&
                sourceY >= 0f && sourceY < value.sourceHeight
        }
        for ((start, end) in bodyEdges) {
            if (bodyValid(start) && bodyValid(end)) {
                canvas.drawLine(
                    x(value.bodyXY[start * 2]),
                    y(value.bodyXY[start * 2 + 1]),
                    x(value.bodyXY[end * 2]),
                    y(value.bodyXY[end * 2 + 1]),
                    bodyPaint,
                )
            }
        }
        for (point in 0 until PerceptionVNextMath.BODY_POINTS) {
            if (bodyValid(point)) {
                canvas.drawCircle(
                    x(value.bodyXY[point * 2]),
                    y(value.bodyXY[point * 2 + 1]),
                    6f,
                    bodyPaint,
                )
            }
        }
        drawHand(value.left, leftPaint, "LH")
        drawHand(value.right, rightPaint, "RH")
    }

    private fun paint(color: Int, width: Float) = Paint().apply {
        this.color = color
        strokeWidth = width
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        isAntiAlias = true
    }
}
