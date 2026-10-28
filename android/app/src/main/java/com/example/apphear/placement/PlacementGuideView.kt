package com.example.apphear.placement

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import com.example.apphear.placement.PlacementGuard.Status
import kotlin.math.max

/**
 * Signing-placement guide drawn over the camera preview: corner brackets around the area where
 * hands should stay, a faint head-and-shoulders outline, and a short hint when placement is off.
 * It also converts that area into camera-image coordinates ([imageRegion]) with the same
 * FILL_CENTER crop and front-camera mirroring as the preview, so the check matches what is on screen.
 */
class PlacementGuideView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {
    private val density = resources.displayMetrics.density
    private val bracketPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 3f * density; strokeCap = Paint.Cap.ROUND
    }
    private val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 2f * density; color = 0x59FFFFFF
        pathEffect = DashPathEffect(floatArrayOf(8f * density, 7f * density), 0f)
    }
    private val hintBackground = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xB3000000.toInt() }
    private val hintText = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt(); textSize = 13f * density; textAlign = Paint.Align.CENTER
    }
    private val guide = RectF()
    private val path = Path()

    private var imageWidth = 0
    private var imageHeight = 0
    private var frontCamera = true
    private var status: Status = Status.HANDS_DOWN
    private var paused = false

    /** Top of the bottom panel in this view's coordinates; the guide stops above it. */
    var bottomLimit: Float = Float.NaN
        set(value) { field = value; updateRegion(); invalidate() }

    /** Text for each hint status; set by the screen from string resources. */
    var hints: Map<Status, String> = emptyMap()

    /** The guide area in normalized camera-image coordinates; null until sizes are known. */
    @Volatile var imageRegion: PlacementGuard.Region? = null
        private set

    fun setImage(width: Int, height: Int, front: Boolean) {
        if (width == imageWidth && height == imageHeight && front == frontCamera) return
        imageWidth = width; imageHeight = height; frontCamera = front
        updateRegion()
    }

    fun setStatus(newStatus: Status, newPaused: Boolean) {
        if (newStatus == status && newPaused == paused) return
        status = newStatus; paused = newPaused
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        updateRegion()
    }

    private fun computeGuide() {
        val w = width.toFloat(); val h = height.toFloat()
        val bottom = if (bottomLimit.isNaN() || bottomLimit <= 0f) h * 0.78f else bottomLimit - 12f * density
        guide.set(w * SIDE_INSET, h * TOP_INSET, w * (1f - SIDE_INSET), max(bottom, h * 0.5f))
    }

    private fun updateRegion() {
        if (width == 0 || height == 0 || imageWidth == 0 || imageHeight == 0) return
        computeGuide()
        // Same mapping as PreviewView's FILL_CENTER: scale to cover, center, mirror the front camera.
        val scale = max(width.toFloat() / imageWidth, height.toFloat() / imageHeight)
        val dx = (width - imageWidth * scale) / 2f
        val dy = (height - imageHeight * scale) / 2f
        fun imageX(screenX: Float): Float {
            val x = if (frontCamera) width - screenX else screenX
            return (x - dx) / (imageWidth * scale)
        }
        fun imageY(screenY: Float): Float = (screenY - dy) / (imageHeight * scale)
        val a = imageX(guide.left); val b = imageX(guide.right)
        imageRegion = PlacementGuard.Region(minOf(a, b), imageY(guide.top), maxOf(a, b), imageY(guide.bottom))
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        computeGuide()
        bracketPaint.color = when {
            paused || status == Status.HAND_OUT -> 0xFFFF6B6B.toInt()
            status == Status.TOO_CLOSE || status == Status.NO_SHOULDERS -> 0xFFFFC857.toInt()
            status == Status.OK -> 0xFF35D9BE.toInt()
            else -> 0xCCFFFFFF.toInt()
        }
        drawBrackets(canvas)
        drawHeadAndShoulders(canvas)
        hints[status]?.takeIf { !paused }?.let { drawHint(canvas, it) }
    }

    private fun drawBrackets(canvas: Canvas) {
        val len = minOf(guide.width(), guide.height()) * 0.14f
        val r = 14f * density
        path.reset()
        // Four rounded corner brackets.
        path.moveTo(guide.left, guide.top + len); path.lineTo(guide.left, guide.top + r)
        path.quadTo(guide.left, guide.top, guide.left + r, guide.top); path.lineTo(guide.left + len, guide.top)
        path.moveTo(guide.right - len, guide.top); path.lineTo(guide.right - r, guide.top)
        path.quadTo(guide.right, guide.top, guide.right, guide.top + r); path.lineTo(guide.right, guide.top + len)
        path.moveTo(guide.right, guide.bottom - len); path.lineTo(guide.right, guide.bottom - r)
        path.quadTo(guide.right, guide.bottom, guide.right - r, guide.bottom); path.lineTo(guide.right - len, guide.bottom)
        path.moveTo(guide.left + len, guide.bottom); path.lineTo(guide.left + r, guide.bottom)
        path.quadTo(guide.left, guide.bottom, guide.left, guide.bottom - r); path.lineTo(guide.left, guide.bottom - len)
        canvas.drawPath(path, bracketPaint)
    }

    private fun drawHeadAndShoulders(canvas: Canvas) {
        val cx = guide.centerX()
        val headRadius = guide.width() * 0.13f
        val headCy = guide.top + guide.height() * 0.22f
        canvas.drawCircle(cx, headCy, headRadius, outlinePaint)
        val shoulderY = headCy + headRadius * 1.75f
        val half = guide.width() * 0.34f
        path.reset()
        path.moveTo(cx - half, shoulderY + headRadius * 1.1f)
        path.quadTo(cx - half, shoulderY, cx - headRadius * 1.1f, shoulderY)
        path.lineTo(cx + headRadius * 1.1f, shoulderY)
        path.quadTo(cx + half, shoulderY, cx + half, shoulderY + headRadius * 1.1f)
        canvas.drawPath(path, outlinePaint)
    }

    private fun drawHint(canvas: Canvas, text: String) {
        val pad = 10f * density
        val textWidth = hintText.measureText(text)
        // Below the top row of buttons (back, mode label, camera flip) so it never covers them.
        val y = max(guide.top + 22f * density, HINT_TOP_DP * density)
        val rect = RectF(guide.centerX() - textWidth / 2 - pad, y - hintText.textSize,
            guide.centerX() + textWidth / 2 + pad, y + hintText.textSize * 0.55f)
        canvas.drawRoundRect(rect, rect.height() / 2, rect.height() / 2, hintBackground)
        canvas.drawText(text, guide.centerX(), y, hintText)
    }

    private companion object {
        const val SIDE_INSET = 0.05f
        const val TOP_INSET = 0.035f
        const val HINT_TOP_DP = 128f
    }
}
