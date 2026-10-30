package com.example.apphear.placement

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.os.SystemClock
import android.util.AttributeSet
import android.view.View
import com.example.apphear.R
import com.example.apphear.placement.PositionGuide.Status
import kotlin.math.max
import kotlin.math.min

/**
 * Augmented signing-position guide over the camera preview. Corner brackets follow the signer's
 * signing space (from their shoulders and hips), teal when they are centered at a comfortable
 * distance, tan when they should adjust and red while placementGate pauses recognition. When they
 * are off-center or not in view, a faint target shows where to stand, and a dark-glass pill (the
 * RECOGNIZED card's colour) says what to do. It never takes touches.
 *
 * [mapping] converts camera-image coordinates into this view's normalized coordinates with the same
 * FILL_CENTER crop and front-camera mirroring as the preview, so the guide sits on the signer.
 */
class PlacementGuideView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null,
) : View(context, attrs) {
    /** Image-normalized (0..1) to view-normalized (0..1), mirrored for the front camera. */
    class Mapping(
        private val viewWidth: Float,
        private val viewHeight: Float,
        private val scale: Float,
        private val dx: Float,
        private val dy: Float,
        private val imageWidth: Int,
        private val imageHeight: Int,
        private val front: Boolean,
    ) {
        fun toView(nx: Float, ny: Float): PositionGuide.Point {
            val x = dx + nx * imageWidth * scale
            val y = dy + ny * imageHeight * scale
            return PositionGuide.Point((if (front) viewWidth - x else x) / viewWidth, y / viewHeight)
        }
    }

    private val density = resources.displayMetrics.density
    private val bracketPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 3.5f * density; strokeCap = Paint.Cap.ROUND
    }
    private val targetPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 2f * density; color = 0x66FFFFFF
        pathEffect = DashPathEffect(floatArrayOf(8f * density, 7f * density), 0f)
    }
    private val pillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x9C303738.toInt() }
    private val pillText = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt(); textSize = 14f * density; textAlign = Paint.Align.CENTER
        typeface = runCatching { resources.getFont(R.font.inter_semibold) }.getOrNull()
    }
    private val subText = Paint(pillText).apply { textSize = 11.5f * density; color = 0xD9FFFFFF.toInt() }
    private val path = Path()
    private val target = RectF()
    private val smooth = RectF()
    private var hasSmooth = false

    private var imageWidth = 0
    private var imageHeight = 0
    private var frontCamera = true
    private var assessment: PositionGuide.Assessment? = null
    private var paused = false
    private var centeredSinceMs = 0L

    /** Top of the bottom panel in this view's coordinates; the guide stays above it. */
    var bottomLimit: Float = Float.NaN
        set(value) { field = value; invalidate() }

    /** Text for each status; set by the screen from string resources. */
    var hints: Map<Status, String> = emptyMap()
    var inPositionText: String = ""
    var pausedText: String = ""

    @Volatile var mapping: Mapping? = null
        private set

    fun setImage(width: Int, height: Int, front: Boolean) {
        if (width == imageWidth && height == imageHeight && front == frontCamera) return
        imageWidth = width; imageHeight = height; frontCamera = front
        updateMapping()
    }

    /** The latest assessment of the signer; [paused] while placementGate holds recognition. */
    fun show(newAssessment: PositionGuide.Assessment, newPaused: Boolean) {
        val wasCentered = assessment?.status == Status.CENTERED
        if (newAssessment.status == Status.CENTERED && !wasCentered) centeredSinceMs = SystemClock.uptimeMillis()
        assessment = newAssessment
        paused = newPaused
        if (newAssessment.anchor == null) hasSmooth = false
        invalidate()
    }

    /** Nothing to show (fingerspelling owns the camera, the screen stopped, or a conversation hold). */
    fun clear() {
        assessment = null
        paused = false
        hasSmooth = false
        invalidate()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        updateMapping()
    }

    private fun updateMapping() {
        if (width == 0 || height == 0 || imageWidth == 0 || imageHeight == 0) return
        val scale = max(width.toFloat() / imageWidth, height.toFloat() / imageHeight)
        mapping = Mapping(width.toFloat(), height.toFloat(), scale,
            (width - imageWidth * scale) / 2f, (height - imageHeight * scale) / 2f, imageWidth, imageHeight, frontCamera)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val current = assessment ?: return
        val anchor = current.anchor
        val floor = if (bottomLimit.isNaN() || bottomLimit <= 0f) height.toFloat() else bottomLimit - 8f * density
        if (anchor != null) {
            spaceAround(anchor.centerX, anchor, floor, target)
            // Ease toward the new position so the brackets glide with the signer instead of jittering.
            if (!hasSmooth) { smooth.set(target); hasSmooth = true } else {
                smooth.left += (target.left - smooth.left) * EASE; smooth.top += (target.top - smooth.top) * EASE
                smooth.right += (target.right - smooth.right) * EASE; smooth.bottom += (target.bottom - smooth.bottom) * EASE
            }
            bracketPaint.color = when {
                paused || current.status == Status.HAND_OUT -> 0xFFFF4455.toInt()
                current.status == Status.CENTERED -> 0xFF2AA897.toInt()
                else -> 0xFFE9D8B8.toInt()
            }
            if (current.status == Status.MOVE_LEFT || current.status == Status.MOVE_RIGHT) {
                spaceAround(0.5f, anchor, floor, target)
                drawBrackets(canvas, target, targetPaint)
            }
            drawBrackets(canvas, smooth, bracketPaint)
        } else {
            drawStandHere(canvas, floor)
        }
        val label = when {
            current.status == Status.CENTERED ->
                inPositionText.takeIf { SystemClock.uptimeMillis() - centeredSinceMs < IN_POSITION_SHOW_MS }
                    .also { if (it != null) postInvalidateDelayed(IN_POSITION_SHOW_MS) }
            else -> hints[current.status]
        }
        if (label != null) drawPill(canvas, label, pausedText.takeIf { paused })
    }

    /** The signing space for a torso centered at [centerX]: room above the head for raised signs. */
    private fun spaceAround(centerX: Float, anchor: PositionGuide.Anchor, floor: Float, out: RectF) {
        val shoulderPx = anchor.shoulderWidth * width
        val cx = centerX * width
        val shoulderY = anchor.shoulderY * height
        val bottom = anchor.hipY?.let { it * height + shoulderPx * 0.15f } ?: (shoulderY + shoulderPx * 1.6f)
        out.set(cx - shoulderPx * 1.5f, max(shoulderY - shoulderPx * 1.35f, TOP_CLEARANCE_DP * density),
            cx + shoulderPx * 1.5f, min(bottom, floor))
    }

    /** No one in view: a faint head-and-shoulders target in the center. */
    private fun drawStandHere(canvas: Canvas, floor: Float) {
        val cx = width / 2f
        val headRadius = width * 0.1f
        val headCy = max(height * 0.3f, TOP_CLEARANCE_DP * density + headRadius * 1.6f)
        if (headCy + headRadius * 3f > floor) return
        canvas.drawCircle(cx, headCy, headRadius, targetPaint)
        val shoulderY = headCy + headRadius * 1.75f
        val half = width * 0.26f
        path.reset()
        path.moveTo(cx - half, shoulderY + headRadius * 1.1f)
        path.quadTo(cx - half, shoulderY, cx - headRadius * 1.1f, shoulderY)
        path.lineTo(cx + headRadius * 1.1f, shoulderY)
        path.quadTo(cx + half, shoulderY, cx + half, shoulderY + headRadius * 1.1f)
        canvas.drawPath(path, targetPaint)
    }

    private fun drawBrackets(canvas: Canvas, box: RectF, paint: Paint) {
        if (box.width() <= 0f || box.height() <= 0f) return
        val len = min(box.width(), box.height()) * 0.16f
        val r = 14f * density
        path.reset()
        path.moveTo(box.left, box.top + len); path.lineTo(box.left, box.top + r)
        path.quadTo(box.left, box.top, box.left + r, box.top); path.lineTo(box.left + len, box.top)
        path.moveTo(box.right - len, box.top); path.lineTo(box.right - r, box.top)
        path.quadTo(box.right, box.top, box.right, box.top + r); path.lineTo(box.right, box.top + len)
        path.moveTo(box.right, box.bottom - len); path.lineTo(box.right, box.bottom - r)
        path.quadTo(box.right, box.bottom, box.right - r, box.bottom); path.lineTo(box.right - len, box.bottom)
        path.moveTo(box.left + len, box.bottom); path.lineTo(box.left + r, box.bottom)
        path.quadTo(box.left, box.bottom, box.left, box.bottom - r); path.lineTo(box.left, box.bottom - len)
        canvas.drawPath(path, paint)
    }

    /** Below the top row of buttons (back, mode label, camera flip) so it never covers them. */
    private fun drawPill(canvas: Canvas, text: String, sub: String?) {
        val padX = 16f * density
        val padY = 9f * density
        val textWidth = max(pillText.measureText(text), sub?.let(subText::measureText) ?: 0f)
        val lineGap = 4f * density
        val textHeight = pillText.textSize + (sub?.let { subText.textSize + lineGap } ?: 0f)
        val top = PILL_TOP_DP * density
        val rect = RectF(width / 2f - textWidth / 2 - padX, top, width / 2f + textWidth / 2 + padX, top + textHeight + padY * 2)
        canvas.drawRoundRect(rect, 22f * density, 22f * density, pillPaint)
        val baseline = rect.top + padY + pillText.textSize * 0.85f
        canvas.drawText(text, width / 2f, baseline, pillText)
        if (sub != null) canvas.drawText(sub, width / 2f, baseline + lineGap + subText.textSize, subText)
    }

    private companion object {
        const val EASE = 0.45f
        const val IN_POSITION_SHOW_MS = 1_500L
        const val PILL_TOP_DP = 120f
        const val TOP_CLEARANCE_DP = 112f
    }
}
