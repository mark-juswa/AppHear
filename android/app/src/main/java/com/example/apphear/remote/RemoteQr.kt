package com.example.apphear.remote

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.EncodeHintType
import com.google.zxing.NotFoundException
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** QR codes for remote conversation invites: drawing one, and reading one with the back camera. */
object RemoteQr {
    fun bitmap(content: String, sizePx: Int): Bitmap {
        val matrix = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, sizePx, sizePx,
            mapOf(EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M, EncodeHintType.MARGIN to 1))
        val pixels = IntArray(matrix.width * matrix.height) { index ->
            if (matrix.get(index % matrix.width, index / matrix.width)) DARK else Color.WHITE
        }
        return Bitmap.createBitmap(pixels, matrix.width, matrix.height, Bitmap.Config.ARGB_8888)
    }

    private val DARK = Color.parseColor("#0D1B1E")

    /** Back-camera QR reader shown in [preview]; [onText] is called once, on the main thread. */
    class Scanner(
        private val context: Context,
        private val owner: LifecycleOwner,
        private val preview: PreviewView,
        private val onText: (String) -> Unit,
    ) {
        private val executor: ExecutorService = Executors.newSingleThreadExecutor()
        private val reader = QRCodeReader()
        private var provider: ProcessCameraProvider? = null
        @Volatile private var done = false

        fun start() {
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                if (done) return@addListener
                val cameraProvider = try { future.get() } catch (error: Exception) {
                    Log.w("AppHearRemote", "[remote] camera unavailable", error); return@addListener
                }
                provider = cameraProvider
                val previewUseCase = Preview.Builder().build().also { it.setSurfaceProvider(preview.surfaceProvider) }
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { it.setAnalyzer(executor, ::analyze) }
                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, previewUseCase, analysis)
                } catch (error: Exception) {
                    Log.w("AppHearRemote", "[remote] camera bind failed", error)
                }
            }, ContextCompat.getMainExecutor(context))
        }

        fun stop() {
            done = true
            provider?.unbindAll()
            provider = null
            executor.shutdown()
        }

        private fun analyze(image: ImageProxy) {
            try {
                if (done) return
                val plane = image.planes[0]
                val buffer = plane.buffer
                val data = ByteArray(buffer.remaining()).also { buffer.get(it) }
                val source = PlanarYUVLuminanceSource(data, plane.rowStride, image.height, 0, 0,
                    image.width, image.height, false)
                val text = try {
                    reader.decode(BinaryBitmap(HybridBinarizer(source)), mapOf(DecodeHintType.TRY_HARDER to true)).text
                } catch (_: NotFoundException) { null } catch (_: Exception) { null } finally { reader.reset() }
                if (text != null && !done) {
                    done = true
                    ContextCompat.getMainExecutor(context).execute { onText(text) }
                }
            } finally {
                image.close()
            }
        }
    }
}
