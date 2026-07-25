package com.example.apphear.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import com.example.apphear.pipeline.FrameResult
import kotlin.math.max

/**
 * Draws hand + pose landmarks over the camera preview (visual confirmation for F17 — S1/S2 are
 * working). Maps MediaPipe normalized coords (relative to the upright detection image) into view
 * space with the same FILL_CENTER transform PreviewView uses, and mirrors X for the front camera
 * (PreviewView mirrors the front preview, so the overlay must too).
 */
class OverlayView(context: Context, attrs: AttributeSet?) : View(context, attrs) {

    private var result: FrameResult? = null

    private val handPaint = Paint().apply {
        color = Color.CYAN
        style = Paint.Style.FILL
        isAntiAlias = true
    }
    private val posePaint = Paint().apply {
        color = Color.YELLOW
        style = Paint.Style.FILL
        isAntiAlias = true
    }

    fun setResult(r: FrameResult) {
        result = r
        postInvalidate()
    }

    fun clear() {
        result = null
        postInvalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val r = result ?: return
        if (r.imageWidth == 0 || r.imageHeight == 0) return

        val scale = max(width.toFloat() / r.imageWidth, height.toFloat() / r.imageHeight)
        val dx = (width - r.imageWidth * scale) / 2f
        val dy = (height - r.imageHeight * scale) / 2f

        fun mapX(nx: Float): Float {
            val x = nx * r.imageWidth * scale + dx
            return if (r.isFrontCamera) width - x else x
        }
        fun mapY(ny: Float): Float = ny * r.imageHeight * scale + dy

        r.pose?.landmarks()?.forEach { pose ->
            pose.forEach { lm -> canvas.drawCircle(mapX(lm.x()), mapY(lm.y()), 6f, posePaint) }
        }
        r.hands?.landmarks()?.forEach { hand ->
            hand.forEach { lm -> canvas.drawCircle(mapX(lm.x()), mapY(lm.y()), 9f, handPaint) }
        }
    }
}
