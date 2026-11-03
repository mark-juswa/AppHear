package com.example.apphear.placement

import android.content.Context
import android.graphics.Canvas
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.graphics.RectF
import android.os.SystemClock
import android.util.AttributeSet
import android.view.View
import com.example.apphear.R
import com.example.apphear.placement.PositionGuide.Status
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * Augmented signing-position guide over the camera preview, for whoever sets the phone up.
 *
 * A person-shaped placeholder (head, shoulders, torso, arms in a signing pose) marks where the signer
 * should stand, sized for a comfortable distance. The detected signer is drawn as a soft body shape
 * on top of them, built only from the body and hand points the recognizer already tracks (no extra
 * model, so recognition speed is untouched). Both turn teal when they line up; otherwise chevrons
 * point toward the placeholder and a pill says what to adjust. It never takes touches.
 *
 * [mapping] converts camera-image coordinates into this view's normalized coordinates with the same
 * FILL_CENTER crop and front-camera mirroring as the preview, so the overlay sits on the signer.
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
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val outline = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 2.5f * density; strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND
    }
    private val dashed = DashPathEffect(floatArrayOf(10f * density, 8f * density), 0f)
    private val limb = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND }
    private val pillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x9C303738.toInt() }
    private val pillText = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFFFFFFF.toInt(); textSize = 14f * density; textAlign = Paint.Align.CENTER
        typeface = runCatching { resources.getFont(R.font.inter_semibold) }.getOrNull()
    }
    private val subText = Paint(pillText).apply { textSize = 11.5f * density; color = 0xD9FFFFFF.toInt() }
    private val path = Path()

    private var imageWidth = 0
    private var imageHeight = 0
    private var frontCamera = true
    private var assessment: PositionGuide.Assessment? = null
    private var body: PositionGuide.Body? = null
    private var paused = false
    private var centeredSinceMs = 0L
    /** Eased screen positions of the drawn body points, keyed by part, so the overlay glides. */
    private val eased = HashMap<String, PointF>()

    /** Top of the bottom panel in this view's coordinates; the guide stays above it. */
    var bottomLimit: Float = Float.NaN
        set(value) { field = value; invalidate() }

    /** Shoulder width (fraction of view width) the placeholder is drawn at: the comfortable distance. */
    var targetShoulderWidth: Float = 0.36f

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

    /** The latest assessment and body points (view-normalized); [paused] while placementGate holds recognition. */
    fun show(newAssessment: PositionGuide.Assessment, newPaused: Boolean, newBody: PositionGuide.Body?) {
        val wasCentered = assessment?.status == Status.CENTERED
        if (newAssessment.status == Status.CENTERED && !wasCentered) centeredSinceMs = SystemClock.uptimeMillis()
        assessment = newAssessment
        paused = newPaused
        body = newBody
        if (newAssessment.anchor == null) eased.clear()
        invalidate()
    }

    /** Nothing to show (the screen stopped, or a conversation hold). */
    fun clear() {
        assessment = null
        body = null
        paused = false
        eased.clear()
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
        val top = TOP_CLEARANCE_DP * density
        val floor = if (bottomLimit.isNaN() || bottomLimit <= 0f) height.toFloat() else bottomLimit - 8f * density
        if (floor - top < 120f * density) return
        val centered = current.status == Status.CENTERED
        val person = current.anchor != null

        // The placeholder: where the signer should stand. Shown only when it helps (nobody detected, or
        // off to one side), so it is never drawn over a signer who is already roughly in place.
        val target = placeholder(top, floor)
        val offCenter = current.status == Status.MOVE_LEFT || current.status == Status.MOVE_RIGHT
        val pulse = if (person) 1f else (0.65f + 0.35f * sin(SystemClock.uptimeMillis() / 420.0).toFloat())
        if (!person || offCenter) drawPlaceholder(canvas, target, false, pulse)

        // The detected signer, drawn on top of them.
        val shape = if (person) personShape() else null
        if (shape != null) {
            val color = when {
                paused || current.status == Status.HAND_OUT -> RED
                centered -> TEAL
                else -> CREAM
            }
            drawPerson(canvas, shape, color, floor)
            if (offCenter) {
                drawChevrons(canvas, shape.center, target.center, shape.shoulderY)
            }
        }

        val label = when {
            centered -> inPositionText.takeIf { SystemClock.uptimeMillis() - centeredSinceMs < IN_POSITION_SHOW_MS }
                ?.also { postInvalidateDelayed(IN_POSITION_SHOW_MS) }
            else -> hints[current.status]
        }
        if (label != null) drawPill(canvas, label, pausedText.takeIf { paused })
        // Keep the placeholder breathing, and the chevrons moving, only while they are shown.
        // ~20 frames a second is smooth enough here and keeps the UI thread light.
        if (!person || current.status == Status.MOVE_LEFT || current.status == Status.MOVE_RIGHT) {
            postInvalidateDelayed(ANIMATION_FRAME_MS)
        }
    }

    /** Geometry shared by the placeholder and the detected person. */
    private class Figure(val center: PointF, val shoulderY: Float, val shoulderWidth: Float)

    private class PersonShape(
        val center: PointF, val shoulderY: Float, val shoulderWidth: Float,
        val leftShoulder: PointF, val rightShoulder: PointF, val leftHip: PointF, val rightHip: PointF,
        val leftElbow: PointF?, val rightElbow: PointF?, val leftWrist: PointF?, val rightWrist: PointF?,
        val hands: List<List<PointF>>,
    )

    private fun placeholder(top: Float, floor: Float): Figure {
        // Head top to hips is about 2.6 shoulder widths; keep the figure inside the visible camera area.
        val shoulderWidth = min(targetShoulderWidth * width, (floor - top) * 0.92f / FIGURE_HEIGHT)
        val shoulderY = top + (floor - top - FIGURE_HEIGHT * shoulderWidth) / 2f + HEAD_ABOVE * shoulderWidth
        return Figure(PointF(width / 2f, shoulderY), shoulderY, shoulderWidth)
    }

    private fun drawPlaceholder(canvas: Canvas, f: Figure, centered: Boolean, pulse: Float) {
        val sw = f.shoulderWidth
        val cx = f.center.x
        val y = f.shoulderY
        val color = if (centered) TEAL else 0xFFFFFFFF.toInt()
        // Arms in a signing pose: elbows out, hands in front of the chest.
        limb.strokeWidth = 0.17f * sw
        limb.color = withAlpha(color, (if (centered) 0x40 else 0x26) * pulse * SHAPE_OPACITY)
        for (side in listOf(-1f, 1f)) {
            path.reset()
            path.moveTo(cx + side * 0.5f * sw, y + 0.12f * sw)
            path.lineTo(cx + side * 0.66f * sw, y + 0.82f * sw)
            path.lineTo(cx + side * 0.2f * sw, y + (if (side < 0) 0.55f else 0.45f) * sw)
            canvas.drawPath(path, limb)
        }
        // Head and torso: a light fill with a dashed outline (solid teal once the signer lines up).
        buildBust(cx, y, sw, y + HIP_BELOW * sw)
        fill.color = withAlpha(color, (if (centered) 0x33 else 0x1A) * pulse * SHAPE_OPACITY)
        canvas.drawPath(path, fill)
        canvas.drawCircle(cx, y - HEAD_ABOVE_CENTER * sw, HEAD_RADIUS * sw, fill)
        outline.color = withAlpha(color, 0xD9 * pulse * SHAPE_OPACITY)
        outline.pathEffect = if (centered) null else dashed
        canvas.drawPath(path, outline)
        canvas.drawCircle(cx, y - HEAD_ABOVE_CENTER * sw, HEAD_RADIUS * sw, outline)
        outline.pathEffect = null
    }

    /** Neck, rounded shoulders and torso down to [hipY], into [path]. */
    private fun buildBust(cx: Float, y: Float, sw: Float, hipY: Float) {
        val neck = 0.13f * sw
        path.reset()
        path.moveTo(cx - neck, y - 0.16f * sw)
        path.quadTo(cx - 0.44f * sw, y - 0.12f * sw, cx - 0.5f * sw, y + 0.08f * sw)
        path.cubicTo(cx - 0.56f * sw, y + 0.5f * sw, cx - 0.44f * sw, hipY - 0.35f * sw, cx - 0.42f * sw, hipY)
        path.lineTo(cx + 0.42f * sw, hipY)
        path.cubicTo(cx + 0.44f * sw, hipY - 0.35f * sw, cx + 0.56f * sw, y + 0.5f * sw, cx + 0.5f * sw, y + 0.08f * sw)
        path.quadTo(cx + 0.44f * sw, y - 0.12f * sw, cx + neck, y - 0.16f * sw)
        path.close()
    }

    private fun personShape(): PersonShape? {
        val b = body ?: return null
        val ls = ease("ls", b.leftShoulder) ?: return null
        val rs = ease("rs", b.rightShoulder) ?: return null
        val sw = hypot(rs.x - ls.x, rs.y - ls.y)
        if (sw < 12f * density) return null
        val shoulderY = (ls.y + rs.y) / 2f
        val center = PointF((ls.x + rs.x) / 2f, shoulderY)
        val left = if (ls.x <= rs.x) ls else rs
        val right = if (left === ls) rs else ls
        // Hips when seen; otherwise straight down from the shoulders, as far as a torso usually reaches.
        val lh = ease("lh", b.leftHip) ?: PointF(center.x - 0.42f * sw, shoulderY + HIP_BELOW * sw)
        val rh = ease("rh", b.rightHip) ?: PointF(center.x + 0.42f * sw, shoulderY + HIP_BELOW * sw)
        val leftHip = if (lh.x <= rh.x) lh else rh
        val rightHip = if (leftHip === lh) rh else lh
        val hands = b.hands.map { joints -> joints.map { PointF(it.x * width, it.y * height) } }
        return PersonShape(center, shoulderY, sw, left, right, leftHip, rightHip,
            ease("le", b.leftElbow), ease("re", b.rightElbow), ease("lw", b.leftWrist), ease("rw", b.rightWrist), hands)
    }

    private fun drawPerson(canvas: Canvas, s: PersonShape, color: Int, floor: Float) {
        val sw = s.shoulderWidth
        // Sides run down to the hips when they are seen, otherwise to the bottom of the camera area,
        // left open there so nothing is invented below the frame.
        val bottom = min(max(s.leftHip.y, s.rightHip.y), floor)
        val hipsSeen = body?.leftHip != null && body?.rightHip != null && bottom < floor
        path.reset()
        path.moveTo(s.leftHip.x, bottom)
        path.quadTo(s.leftShoulder.x - 0.04f * sw, (s.leftShoulder.y + bottom) / 2f, s.leftShoulder.x, s.leftShoulder.y + 0.08f * sw)
        path.quadTo(s.leftShoulder.x + 0.06f * sw, s.leftShoulder.y - 0.12f * sw, s.center.x - 0.13f * sw, s.shoulderY - 0.16f * sw)
        path.lineTo(s.center.x + 0.13f * sw, s.shoulderY - 0.16f * sw)
        path.quadTo(s.rightShoulder.x - 0.06f * sw, s.rightShoulder.y - 0.12f * sw, s.rightShoulder.x, s.rightShoulder.y + 0.08f * sw)
        path.quadTo(s.rightShoulder.x + 0.04f * sw, (s.rightShoulder.y + bottom) / 2f, s.rightHip.x, bottom)
        if (hipsSeen) path.close()
        fill.color = withAlpha(color, 0x33 * SHAPE_OPACITY)
        canvas.drawPath(path, fill)
        outline.color = withAlpha(color, 0xE6 * SHAPE_OPACITY)
        canvas.drawPath(path, outline)
        // The head is not tracked: drawn where it sits above the shoulders.
        val headY = s.shoulderY - HEAD_ABOVE_CENTER * sw
        canvas.drawCircle(s.center.x, headY, HEAD_RADIUS * sw, fill)
        canvas.drawCircle(s.center.x, headY, HEAD_RADIUS * sw, outline)
    }

    /** Three chevrons from the signer toward the placeholder, drifting in that direction. */
    private fun drawChevrons(canvas: Canvas, from: PointF, to: PointF, y: Float) {
        val gap = to.x - from.x
        if (abs(gap) < 24f * density) return
        val direction = if (gap > 0) 1f else -1f
        val size = 9f * density
        val drift = ((SystemClock.uptimeMillis() % 900L) / 900f) * size * 1.6f
        outline.color = withAlpha(CREAM, 0xE6 * SHAPE_OPACITY)
        outline.pathEffect = null
        val start = from.x + direction * (abs(gap) * 0.25f)
        for (i in 0 until 3) {
            val x = start + direction * (i * size * 1.6f + drift)
            path.reset()
            path.moveTo(x - direction * size * 0.6f, y - size)
            path.lineTo(x + direction * size * 0.4f, y)
            path.lineTo(x - direction * size * 0.6f, y + size)
            canvas.drawPath(path, outline)
        }
    }

    private fun ease(key: String, point: PositionGuide.Point?): PointF? {
        if (point == null) {
            eased.remove(key)
            return null
        }
        val x = point.x * width
        val y = point.y * height
        val previous = eased[key]
        val next = if (previous == null) PointF(x, y)
            else PointF(previous.x + (x - previous.x) * EASE, previous.y + (y - previous.y) * EASE)
        eased[key] = next
        return next
    }

    /** Below the top row of buttons (back, mode label, camera flip) so it never covers them. */
    private fun drawPill(canvas: Canvas, text: String, sub: String?) {
        val padX = 16f * density
        val padY = 9f * density
        val textWidth = max(pillText.measureText(text), sub?.let(subText::measureText) ?: 0f)
        val lineGap = 4f * density
        val textHeight = pillText.textSize + (sub?.let { subText.textSize + lineGap } ?: 0f)
        val pillTop = PILL_TOP_DP * density
        val rect = RectF(width / 2f - textWidth / 2 - padX, pillTop, width / 2f + textWidth / 2 + padX,
            pillTop + textHeight + padY * 2)
        canvas.drawRoundRect(rect, 22f * density, 22f * density, pillPaint)
        val baseline = rect.top + padY + pillText.textSize * 0.85f
        canvas.drawText(text, width / 2f, baseline, pillText)
        if (sub != null) canvas.drawText(sub, width / 2f, baseline + lineGap + subText.textSize, subText)
    }

    private fun withAlpha(color: Int, alpha: Float): Int = withAlpha(color, alpha.toInt())
    private fun withAlpha(color: Int, alpha: Int): Int = (alpha.coerceIn(0, 255) shl 24) or (color and 0xFFFFFF)

    private companion object {
        /** The placeholder, the person outline and the chevrons are drawn faint so they do not distract. */
        const val SHAPE_OPACITY = 0.35f
        const val TEAL = 0xFF2AA897.toInt()
        const val CREAM = 0xFFF6EBDD.toInt()
        const val RED = 0xFFFF4455.toInt()
        const val EASE = 0.45f
        const val HEAD_RADIUS = 0.3f
        const val HEAD_ABOVE_CENTER = 0.78f
        const val HEAD_ABOVE = HEAD_ABOVE_CENTER + HEAD_RADIUS
        const val HIP_BELOW = 1.35f
        const val FIGURE_HEIGHT = HEAD_ABOVE + HIP_BELOW
        const val IN_POSITION_SHOW_MS = 1_500L
        const val ANIMATION_FRAME_MS = 50L
        const val PILL_TOP_DP = 120f
        const val TOP_CLEARANCE_DP = 168f
    }
}
