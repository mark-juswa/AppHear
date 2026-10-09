package com.example.apphear.p7d

import android.Manifest
import android.content.pm.PackageManager
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.TotalCaptureResult
import android.hardware.camera2.CameraCharacteristics
import android.os.*
import android.util.Log
import android.util.Size
import android.view.WindowManager
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.*
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.TensorFlowLite
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** No production-pipeline references. Explicit ADB opt-in plus host graph/test gate required. */
@androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
class P7dRuntimeActivity : AppCompatActivity() {
    private val worker=Executors.newSingleThreadExecutor()
    private val monitor=Executors.newSingleThreadScheduledExecutor()
    private val stopping=AtomicBoolean(false)
    private val written=AtomicBoolean(false)
    private val epoch=AtomicLong(0)
    private val captures=AtomicLong(0)
    private val arrivals=AtomicLong(0)
    private val memory=ConcurrentLinkedQueue<JSONObject>()
    private val rows=mutableListOf<JSONObject>()
    private val errors=mutableListOf<String>()
    private var provider: ProcessCameraProvider?=null
    private var interpreter: Interpreter?=null
    private var realTimeSource=false
    private var loadMs=0.0
    private var heatIndex=0
    private var identityIndex=1
    private var firstFrame=JSONObject()
    private var lastArrival=0L
    private var lastCaptureStamp=0L
    private var gaps=mutableListOf<Double>()
    private var modelHash=""
    private val input=buffer(384*384*3)
    private val heat=buffer(96*96*50)
    private val identity=buffer(2)
    private val heatArray=FloatArray(96*96*50)
    private val identityArray=FloatArray(2)
    private lateinit var root: File
    private lateinit var status: TextView
    private val handler=Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status=TextView(this).apply {text="P7-D disabled unless explicitly enabled"}
        setContentView(status)
        if(!intent.getBooleanExtra("p7d_enabled",false)) return
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        root=File(getExternalFilesDir(null),"p7d")
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) {
            status.text="P7-D requires camera permission; grant before launch";return
        }
        worker.execute {
            try {
                require(!File(root,"device_result.json").exists()) {"P7D_NO_RESULT_OVERWRITE"}
                val marker=JSONObject(File(root,"host_gate.json").readText())
                require(marker.getBoolean("export_pass") && marker.getBoolean("unit_tests_pass"))
                val model=File(root,"random_skeleton.tflite")
                modelHash=MessageDigest.getInstance("SHA-256").digest(model.readBytes()).joinToString("") {"%02x".format(it)}
                require(modelHash==marker.getString("sha256")) {"P7D_MODEL_HASH_MISMATCH"}
                val started=System.nanoTime()
                interpreter=Interpreter(model,Interpreter.Options().setNumThreads(2).setUseXNNPACK(true).setUseNNAPI(false))
                interpreter!!.allocateTensors()
                require(TensorFlowLite.runtimeVersion().startsWith("2.16.1")) {"P7D_RUNTIME_VERSION_MISMATCH"}
                require(Build.MODEL=="M2101K7AG" && Build.SOC_MODEL=="SM6150" && Build.VERSION.RELEASE=="12") {"P7D_DEVICE_MISMATCH"}
                loadMs=(System.nanoTime()-started)/1e6
                require(interpreter!!.getInputTensor(0).shape().contentEquals(intArrayOf(1,384,384,3)))
                require(interpreter!!.getInputTensor(0).dataType().toString()=="FLOAT32")
                require(interpreter!!.inputTensorCount==1 && interpreter!!.outputTensorCount==2)
                for(i in 0..1) {
                    val t=interpreter!!.getOutputTensor(i)
                    require(t.dataType().toString()=="FLOAT32")
                    when {
                        t.shape().contentEquals(intArrayOf(1,96,96,50))->heatIndex=i
                        t.shape().contentEquals(intArrayOf(1,1,1,2))->identityIndex=i
                        else->error("P7D_OUTPUT_BINDING_MISMATCH")
                    }
                }
                Log.i("P7D","MODEL_LOADED runtime=${TensorFlowLite.runtimeVersion()} XNNPACK_requested=true threads=2 sha=$modelHash")
                monitor.scheduleAtFixedRate({ sampleMemory() },0,5,TimeUnit.SECONDS)
                runOnUiThread {bind()}
            } catch(e: Throwable) {fail(e)}
        }
    }

    private fun bind() {
        val future=ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                provider=future.get()
                val builder=ImageAnalysis.Builder().setTargetResolution(Size(480,360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder).setSessionCaptureCallback(object: CameraCaptureSession.CaptureCallback() {
                    override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) {
                        val t=System.nanoTime();val start=epoch.get()
                        if(start>0 && t>=start+WARM && t<start+WARM+MEASURE) captures.incrementAndGet()
                    }
                })
                val analysis=builder.build()
                analysis.setAnalyzer(worker) {analyze(it)}
                val camera=provider!!.bindToLifecycle(this,CameraSelector.DEFAULT_FRONT_CAMERA,analysis)
                realTimeSource=Camera2CameraInfo.from(camera.cameraInfo).getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)==CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME
                status.text="P7-D: waiting for camera; no recording or recognition"
                handler.postDelayed({if(epoch.get()==0L && !stopping.get()) fail(IllegalStateException("CAMERA_NO_FRAMES"))},30000)
            } catch(e: Throwable) {fail(e)}
        },ContextCompat.getMainExecutor(this))
    }

    private fun analyze(image: ImageProxy) {
        if(stopping.get()) {image.close();return}
        val start=System.nanoTime()
        if(epoch.compareAndSet(0,start)) {
            firstFrame=JSONObject().put("raw_width",image.width).put("raw_height",image.height)
                .put("rotation",image.imageInfo.rotationDegrees).put("row_stride",image.planes[0].rowStride)
                .put("pixel_stride",image.planes[0].pixelStride).put("sensor_realtime_clock",realTimeSource)
            handler.postDelayed({stop()},210000)
            sampleMemory()
            Log.i("P7D","WARMUP_START")
        }
        val e=epoch.get(); val measured=start>=e+WARM && start<e+WARM+MEASURE
        if(measured) {
            arrivals.incrementAndGet()
            if(lastArrival>0) gaps.add((start-lastArrival)/1e6)
            lastArrival=start
        }
        try {
            val handoff=if(realTimeSource) (SystemClock.elapsedRealtimeNanos()-image.imageInfo.timestamp)/1e6 else null
            val a=System.nanoTime()
            val plane=image.planes[0]
            val rgb=P7dMath.uprightRgb(plane.buffer.duplicate(),image.width,image.height,plane.rowStride,plane.pixelStride,image.imageInfo.rotationDegrees)
            val b=System.nanoTime()
            val rotated=image.imageInfo.rotationDegrees in listOf(90,270)
            val transform=P7dMath.Transform(if(rotated) image.height else image.width,if(rotated) image.width else image.height)
            P7dMath.letterbox(rgb,transform,input)
            val c=System.nanoTime()
            heat.rewind();identity.rewind()
            interpreter!!.runForMultipleInputsOutputs(arrayOf(input),mapOf(heatIndex to heat,identityIndex to identity))
            val d=System.nanoTime()
            val native=interpreter!!.lastNativeInferenceDurationNanoseconds
            heat.rewind();heat.asFloatBuffer().get(heatArray)
            identity.rewind();identity.asFloatBuffer().get(identityArray)
            val f=System.nanoTime()
            val decoded=P7dMath.decode(heatArray,identityArray,transform)
            val g=System.nanoTime()
            val source=P7dMath.restore(decoded,transform)
            require(source.all {it.isFinite()}) {"SOURCE_OUTPUT_NONFINITE"}
            val rawEvidence=RawEvidence(image.imageInfo.timestamp,transform.width,transform.height,source,decoded.confidence,decoded.identity,P7dMath.POLICY)
            require(rawEvidence.policy=="POLICY_UNCONFIGURED")
            val end=System.nanoTime()
            if(measured && end<=e+WARM+MEASURE) {
                rows.add(JSONObject().put("start_ns",start).put("end_ns",end).put("capture_ns",image.imageInfo.timestamp)
                    .put("camera_handoff_ms",handoff ?: JSONObject.NULL)
                    .put("rgba_rgb_ms",(b-a)/1e6).put("letterbox_ms",(c-b)/1e6)
                    .put("backend_native_ms",(native ?: (d-c))/1e6).put("invoke_wall_ms",(d-c)/1e6)
                    .put("jni_input_output_overhead_ms",if(native!=null) ((d-c)-native)/1e6 else JSONObject.NULL)
                    .put("output_read_ms",(f-d)/1e6).put("decoder_ms",(g-f)/1e6).put("restore_ms",(end-g)/1e6)
                    .put("perception_ms",(end-start)/1e6)
                    .put("source_frame_gap_ms",if(lastCaptureStamp>0)(image.imageInfo.timestamp-lastCaptureStamp)/1e6 else JSONObject.NULL))
                lastCaptureStamp=image.imageInfo.timestamp
            }
            if(start>=e+WARM+MEASURE) stop()
        } catch(error: Throwable) {fail(error)} finally {image.close()}
    }

    private data class RawEvidence(val timestamp: Long,val width: Int,val height: Int,val xy: FloatArray,val confidence: FloatArray,val identity: FloatArray,val policy: String)

    private fun sampleMemory() {
        try {
            val rt=Runtime.getRuntime()
            val now=System.nanoTime();val start=epoch.get()
            memory.add(JSONObject().put("nano_time",now).put("elapsed_seconds",if(start>0)(now-start)/1e9 else -1)
                .put("pss_kib",Debug.getPss()).put("native_heap_bytes",Debug.getNativeHeapAllocatedSize())
                .put("java_heap_bytes",rt.totalMemory()-rt.freeMemory())
                .put("thermal",(getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus))
        } catch(e: Throwable) {
            synchronized(errors) {errors.add("MEMORY_SAMPLER: $e")}
            Log.e("P7D","Memory sampler error",e)
        }
    }

    private fun fail(e: Throwable) {
        synchronized(errors) {errors.add(e.stackTraceToString())}
        Log.e("P7D","RUNTIME_BLOCKED",e)
        stop()
    }

    private fun stop() {
        if(!stopping.compareAndSet(false,true))return
        runOnUiThread {
            provider?.unbindAll()
            worker.execute {finishResult()}
        }
    }

    private fun finishResult() {
        if(!written.compareAndSet(false,true))return
        sampleMemory();monitor.shutdown()
        interpreter?.close();interpreter=null
        val result=JSONObject().put("device",Build.MODEL).put("soc",Build.SOC_MODEL).put("android",Build.VERSION.RELEASE)
            .put("runtime_version",TensorFlowLite.runtimeVersion()).put("xnnpack_requested",true).put("threads",2)
            .put("model_sha256",modelHash).put("load_ms",loadMs).put("warmup_seconds",30).put("measurement_seconds",180)
            .put("measurement_start_ns",epoch.get()+WARM).put("measurement_end_ns",epoch.get()+WARM+MEASURE)
            .put("processed_frames",rows.size).put("completed_fps",rows.size/180.0)
            .put("camera_capture_completions",captures.get()).put("camera_capture_completion_fps",captures.get()/180.0)
            .put("analyzer_arrivals",arrivals.get()).put("analyzer_arrival_fps",arrivals.get()/180.0)
            .put("camera_overwrite_estimate",maxOf(0,captures.get()-arrivals.get()))
            .put("drop_count_caveat","Capture-completion minus analyzer-arrival estimate; not exact CameraX internal overwrite count")
            .put("frame_metadata",firstFrame).put("samples",JSONArray(rows)).put("memory",JSONArray(memory.toList()))
            .put("errors",JSONArray(errors.toList())).put("policy",P7dMath.POLICY)
            .put("tensor_arena_bytes","NOT_EXPOSED_BY_JAVA_API").put("recognizer_used",false)
        root.mkdirs()
        File(root,"device_result.json").writeText(result.toString(2))
        Log.i("P7D","COMPLETE frames=${rows.size} fps=${rows.size/180.0} errors=${errors.size}")
        runOnUiThread {status.text="P7-D finished. POLICY_UNCONFIGURED; no recognition. Pull device_result.json."}
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if(::root.isInitialized && !written.get()) {
            synchronized(errors) {errors.add("ACTIVITY_DESTROYED_BEFORE_COMPLETION")}
            stop()
        }
        worker.shutdown();monitor.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val WARM=30_000_000_000L
        private const val MEASURE=180_000_000_000L
        private fun buffer(floats: Int): ByteBuffer=ByteBuffer.allocateDirect(floats*4).order(ByteOrder.nativeOrder())
    }
}
