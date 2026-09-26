package com.example.apphear.perceptionvnext

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import androidx.camera.core.ImageProxy
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import kotlin.math.max
import kotlin.math.min

/** Bounded visual evidence writer for Gate 4A-1B. It never participates in inference. */
internal object Gate4A1bVisualDiagnostics {
    data class Pixels(
        val width: Int,
        val height: Int,
        val rowStride: Int,
        val pixelStride: Int,
        val rotationDegrees: Int,
        val bytes: ByteArray,
    )

    data class Hand(
        val refinedXy: FloatArray,
        val refinedValid: BooleanArray,
        val observed: Boolean,
        val presence: Float,
        val proposalPresent: Boolean,
        val proposalSupport: FloatArray,
        val roi: PerceptionVNextMath.HandRoi?,
    )

    data class Frame(
        val pixels: Pixels,
        val sourceTimestampNs: Long,
        val completionTimestampNs: Long,
        val sourceWidth: Int,
        val sourceHeight: Int,
        val dwposeXy: FloatArray,
        val dwposeSupport: FloatArray,
        val bodyXy: FloatArray,
        val bodySupport: FloatArray,
        val left: Hand,
        val right: Hand,
    )

    data class Saved(
        val acceptedOrdinal: Int,
        val samplingReasons: List<String>,
        val json: JSONObject,
    )

    /** Lightweight synchronized source-frame evidence for continuous phone diagnostics. */
    fun writeOriginal(
        directory: File,
        ordinal: Int,
        frame: Frame,
    ): JSONObject {
        require(directory.exists() || directory.mkdirs())
        val stem = "frame_${ordinal.toString().padStart(6, '0')}"
        val original = uprightBitmap(frame.pixels, frame.sourceWidth, frame.sourceHeight)
        val originalFile = File(directory, "${stem}_original.jpg")
        originalFile.outputStream().use { output ->
            check(original.compress(Bitmap.CompressFormat.JPEG, 82, output))
        }
        val value = JSONObject()
            .put("ordinal", ordinal)
            .put("source_timestamp_ns", frame.sourceTimestampNs)
            .put("completion_timestamp_ns", frame.completionTimestampNs)
            .put("image_semantics", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("original_file", originalFile.name)
            .put("original_sha256", sha256(originalFile))
        File(directory, "${stem}_evidence.json").writeText(value.toString(2))
        original.recycle()
        return value
    }

    fun capture(image: ImageProxy): Pixels {
        val plane = image.planes[0]
        val source = plane.buffer.duplicate()
        return Pixels(
            width = image.width,
            height = image.height,
            rowStride = plane.rowStride,
            pixelStride = plane.pixelStride,
            rotationDegrees = image.imageInfo.rotationDegrees,
            bytes = ByteArray(source.remaining()).also { source.get(it) },
        )
    }

    fun write(
        directory: File,
        acceptedOrdinal: Int,
        samplingReasons: List<String>,
        frame: Frame,
    ): Saved {
        require(frame.sourceWidth > 0 && frame.sourceHeight > 0)
        val stem = "frame_${acceptedOrdinal.toString().padStart(3, '0')}"
        val original = uprightBitmap(frame.pixels, frame.sourceWidth, frame.sourceHeight)
        val annotated = original.copy(Bitmap.Config.ARGB_8888, true)
        drawDiagnostics(Canvas(annotated), frame)

        val originalFile = File(directory, "${stem}_original.jpg")
        val annotatedFile = File(directory, "${stem}_diagnostic.jpg")
        originalFile.outputStream().use { output ->
            check(original.compress(Bitmap.CompressFormat.JPEG, 90, output))
        }
        annotatedFile.outputStream().use { output ->
            check(annotated.compress(Bitmap.CompressFormat.JPEG, 92, output))
        }

        val fullLuminance = luminance(original, null)
        val leftLuminance = frame.left.roi?.let { luminance(original, it) }
        val rightLuminance = frame.right.roi?.let { luminance(original, it) }
        val bodyIndices = PerceptionVNextMath.bodyIndices
        val value = JSONObject()
            .put("accepted_ordinal", acceptedOrdinal)
            .put("sampling_reasons", JSONArray(samplingReasons))
            .put("source_timestamp_ns", frame.sourceTimestampNs)
            .put("completion_timestamp_ns", frame.completionTimestampNs)
            .put("source_width", frame.sourceWidth)
            .put("source_height", frame.sourceHeight)
            .put("image_semantics", "UPRIGHT_UNMIRRORED_SOURCE_RGB")
            .put("original_file", originalFile.name)
            .put("original_sha256", sha256(originalFile))
            .put("diagnostic_file", annotatedFile.name)
            .put("diagnostic_sha256", sha256(annotatedFile))
            .put("full_frame_luminance_mean", fullLuminance)
            .put("sharpness_laplacian_variance", sharpness(original))
            .put("body_support", JSONArray(bodyIndices.map { finiteOrNull(frame.dwposeSupport[it]) }))
            .put("left", handJson(frame.left, leftLuminance, frame.sourceWidth, frame.sourceHeight))
            .put("right", handJson(frame.right, rightLuminance, frame.sourceWidth, frame.sourceHeight))
        val jsonFile = File(directory, "${stem}_diagnostic.json")
        jsonFile.writeText(value.toString(2))
        value.put("metadata_file", jsonFile.name).put("metadata_sha256", sha256(jsonFile))

        original.recycle()
        annotated.recycle()
        return Saved(acceptedOrdinal, samplingReasons, value)
    }

    private fun handJson(
        hand: Hand,
        roiLuminance: Double?,
        sourceWidth: Int,
        sourceHeight: Int,
    ): JSONObject {
        val roi = hand.roi
        return JSONObject()
            .put("proposal_present", hand.proposalPresent)
            .put("proposal_support_mean", finiteMean(hand.proposalSupport))
            .put("refiner_observed", hand.observed)
            .put("refiner_presence", finiteOrNull(hand.presence))
            .put("valid_refined_joints", hand.refinedValid.count { it })
            .put("roi_luminance_mean", roiLuminance ?: JSONObject.NULL)
            .put("roi_center_x", roi?.centerX ?: JSONObject.NULL)
            .put("roi_center_y", roi?.centerY ?: JSONObject.NULL)
            .put("roi_width_fraction", roi?.let { it.side / sourceWidth } ?: JSONObject.NULL)
            .put("roi_height_fraction", roi?.let { it.side / sourceHeight } ?: JSONObject.NULL)
            .put(
                "roi_area_fraction",
                roi?.let { it.side * it.side / (sourceWidth.toFloat() * sourceHeight.toFloat()) }
                    ?: JSONObject.NULL,
            )
    }

    private fun uprightBitmap(pixels: Pixels, sourceWidth: Int, sourceHeight: Int): Bitmap {
        val colors = IntArray(sourceWidth * sourceHeight)
        for (sourceY in 0 until sourceHeight) {
            for (sourceX in 0 until sourceWidth) {
                val rawX: Int
                val rawY: Int
                when (pixels.rotationDegrees) {
                    90 -> {
                        rawX = sourceY
                        rawY = pixels.height - 1 - sourceX
                    }
                    180 -> {
                        rawX = pixels.width - 1 - sourceX
                        rawY = pixels.height - 1 - sourceY
                    }
                    270 -> {
                        rawX = pixels.width - 1 - sourceY
                        rawY = sourceX
                    }
                    else -> {
                        rawX = sourceX
                        rawY = sourceY
                    }
                }
                val offset = rawY * pixels.rowStride + rawX * pixels.pixelStride
                val red = pixels.bytes[offset].toInt() and 0xff
                val green = pixels.bytes[offset + 1].toInt() and 0xff
                val blue = pixels.bytes[offset + 2].toInt() and 0xff
                colors[sourceY * sourceWidth + sourceX] = Color.rgb(red, green, blue)
            }
        }
        return Bitmap.createBitmap(colors, sourceWidth, sourceHeight, Bitmap.Config.ARGB_8888)
    }

    private fun drawDiagnostics(canvas: Canvas, frame: Frame) {
        val bodyPaint = pointPaint(Color.GREEN, 8f)
        val leftProposalPaint = pointPaint(Color.YELLOW, 5f)
        val rightProposalPaint = pointPaint(Color.MAGENTA, 5f)
        val leftRefinedPaint = pointPaint(Color.CYAN, 7f)
        val rightRefinedPaint = pointPaint(Color.rgb(255, 128, 0), 7f)
        val leftRoiPaint = strokePaint(Color.CYAN)
        val rightRoiPaint = strokePaint(Color.rgb(255, 128, 0))

        for (index in PerceptionVNextMath.bodyIndices) {
            drawPoint(canvas, frame.dwposeXy, frame.dwposeSupport, index, 0.0f, bodyPaint)
        }
        for (local in 0 until PerceptionVNextMath.HAND_POINTS) {
            drawPoint(
                canvas,
                frame.dwposeXy,
                frame.dwposeSupport,
                PerceptionVNextMath.LEFT_HAND_START + local,
                0.10f,
                leftProposalPaint,
            )
            drawPoint(
                canvas,
                frame.dwposeXy,
                frame.dwposeSupport,
                PerceptionVNextMath.RIGHT_HAND_START + local,
                0.10f,
                rightProposalPaint,
            )
        }
        drawHand(canvas, frame.left, leftRefinedPaint, leftRoiPaint)
        drawHand(canvas, frame.right, rightRefinedPaint, rightRoiPaint)
    }

    private fun drawPoint(
        canvas: Canvas,
        xy: FloatArray,
        support: FloatArray,
        point: Int,
        minimumSupport: Float,
        paint: Paint,
    ) {
        val x = xy[point * 2]
        val y = xy[point * 2 + 1]
        if (x.isFinite() && y.isFinite() && support[point].isFinite() && support[point] >= minimumSupport) {
            canvas.drawCircle(x, y, paint.strokeWidth, paint)
        }
    }

    private fun drawHand(canvas: Canvas, hand: Hand, pointPaint: Paint, roiPaint: Paint) {
        hand.roi?.let { roi -> canvas.drawRect(RectF(roi.left, roi.top, roi.right, roi.bottom), roiPaint) }
        for (joint in 0 until 21) {
            if (hand.refinedValid[joint]) {
                canvas.drawCircle(
                    hand.refinedXy[joint * 2],
                    hand.refinedXy[joint * 2 + 1],
                    pointPaint.strokeWidth,
                    pointPaint,
                )
            }
        }
    }

    private fun luminance(bitmap: Bitmap, roi: PerceptionVNextMath.HandRoi?): Double {
        val left = max(0, roi?.left?.toInt() ?: 0)
        val top = max(0, roi?.top?.toInt() ?: 0)
        val right = min(bitmap.width, roi?.right?.toInt() ?: bitmap.width)
        val bottom = min(bitmap.height, roi?.bottom?.toInt() ?: bitmap.height)
        if (left >= right || top >= bottom) return Double.NaN
        var sum = 0.0
        var count = 0
        for (y in top until bottom step 2) {
            for (x in left until right step 2) {
                val color = bitmap.getPixel(x, y)
                sum += 0.2126 * Color.red(color) + 0.7152 * Color.green(color) + 0.0722 * Color.blue(color)
                count++
            }
        }
        return if (count > 0) sum / count else Double.NaN
    }

    private fun sharpness(bitmap: Bitmap): Double {
        var count = 0
        var sum = 0.0
        var sumSquared = 0.0
        fun gray(x: Int, y: Int): Double {
            val color = bitmap.getPixel(x, y)
            return 0.2126 * Color.red(color) + 0.7152 * Color.green(color) + 0.0722 * Color.blue(color)
        }
        for (y in 2 until bitmap.height - 2 step 2) {
            for (x in 2 until bitmap.width - 2 step 2) {
                val laplacian = gray(x - 1, y) + gray(x + 1, y) + gray(x, y - 1) + gray(x, y + 1) - 4.0 * gray(x, y)
                sum += laplacian
                sumSquared += laplacian * laplacian
                count++
            }
        }
        if (count == 0) return Double.NaN
        val mean = sum / count
        return sumSquared / count - mean * mean
    }

    private fun pointPaint(color: Int, radius: Float) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color
        style = Paint.Style.FILL
        strokeWidth = radius
    }

    private fun strokePaint(color: Int) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color
        style = Paint.Style.STROKE
        strokeWidth = 4f
    }

    private fun finiteMean(values: FloatArray): Any {
        val finite = values.filter { it.isFinite() }
        return if (finite.isEmpty()) JSONObject.NULL else finite.average()
    }

    private fun finiteOrNull(value: Float): Any = if (value.isFinite()) value else JSONObject.NULL

    private fun sha256(file: File): String = MessageDigest.getInstance("SHA-256").let { digest ->
        file.inputStream().use { input ->
            val block = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(block)
                if (count < 0) break
                digest.update(block, 0, count)
            }
        }
        digest.digest().joinToString("") { "%02x".format(it) }
    }
}
