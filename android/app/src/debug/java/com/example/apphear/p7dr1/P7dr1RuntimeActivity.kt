package com.example.apphear.p7dr1

import android.Manifest
import android.content.pm.PackageManager
import android.hardware.camera2.*
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
import com.example.apphear.p7d.P7dMath
import org.json.JSONArray
import org.json.JSONObject
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.TensorFlowLite
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Random
import java.util.concurrent.Executors
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Isolated explicit ADB entry. No production pipeline, recognition, validity policy or recording. */
@androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
class P7dr1RuntimeActivity : AppCompatActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private val monitor = Executors.newSingleThreadScheduledExecutor()
    private val stopping = AtomicBoolean(false)
    private val epoch = AtomicLong(0)
    private val captureCount = AtomicLong(0)
    private val memory = ConcurrentLinkedQueue<JSONObject>()
    private val errors = ConcurrentLinkedQueue<String>()
    private val handler = Handler(Looper.getMainLooper())
    private var camera: ProcessCameraProvider? = null
    private var interpreter: Interpreter? = null
    private lateinit var root: File
    private lateinit var phase: String
    private lateinit var status: TextView
    private var warm = 0L
    private var measure = 0L
    private var loadMs = 0.0
    private var prep: P7dr1Preprocess? = null
    private var decoder: P7dr1Decoder? = null
    private val heat = buffer(460800)
    private val identities = buffer(2)
    private val heatView = heat.asFloatBuffer()
    private val identityView = identities.asFloatBuffer()
    private val heatArray = FloatArray(460800)
    private val identityArray = FloatArray(2)
    private val arguments = arrayOfNulls<Any>(1)
    private val outputs = HashMap<Int,Any>()
    // No per-frame JSON/collections on timed path. Capacity is a safety limit, never a FPS cap.
    private val samples = LongArray(CAPACITY * 10)
    private val cameraRows = LongArray(CAPACITY * 9)
    private val arrivalRows = LongArray(CAPACITY * 2)
    private var count = 0
    private var arrivals = 0
    private var captureRowsCount = 0
    private var frameInfo = JSONObject()
    private var cameraInfo = JSONObject()
    private var realTimeClock = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply { text = "P7D-R1 disabled; diagnostics only" }
        setContentView(status)
        if (!intent.getBooleanExtra("p7dr1_enabled",false)) return
        root = File(getExternalFilesDir(null),"p7dr1")
        phase = intent.getStringExtra("phase") ?: ""
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        worker.execute {
            try {
                require(phase == "compute" || phase == "camera" || phase == "integrated")
                require(!File(root,"${phase}_result.json").exists()) { "NO_RESULT_OVERWRITE" }
                val gate = JSONObject(File(root,"host_gate.json").readText())
                require(gate.getBoolean("preprocess_pass") && gate.getBoolean("decoder_pass"))
                require(gate.getString("model_sha256") == MODEL_SHA)
                require(Build.MODEL == "M2101K7AG" && Build.SOC_MODEL == "SM6150" && Build.VERSION.RELEASE == "12")
                if (phase != "compute") {
                    val prior = JSONObject(File(root,"compute_result.json").readText())
                    require(prior.getBoolean("compute_screen_pass")) { "COMPUTE_SCREEN_NOT_PASSED" }
                    require(gate.getBoolean("compute_pass_verified"))
                }
                if (phase == "integrated") require(File(root,"camera_result.json").exists())
                warm = when(phase) { "compute" -> 10_000_000_000L; "integrated" -> 30_000_000_000L; else -> 0 }
                measure = when(phase) { "compute" -> 30_000_000_000L; "integrated" -> 180_000_000_000L; else -> 60_000_000_000L }
                if (phase != "camera") loadModel()
                monitor.scheduleAtFixedRate({ sampleMemory() },0,5,TimeUnit.SECONDS)
                if (phase == "compute") compute() else runOnUiThread { bindCamera() }
            } catch (e: Throwable) { fail(e) }
        }
    }

    private fun loadModel() {
        val model = File(root,"random_skeleton.tflite")
        val digest = MessageDigest.getInstance("SHA-256").digest(model.readBytes()).joinToString("") { "%02x".format(it) }
        require(digest == MODEL_SHA) { "MODEL_IDENTITY_MISMATCH" }
        val start = System.nanoTime()
        val runtime = Interpreter(model,Interpreter.Options().setNumThreads(2).setUseXNNPACK(true).setUseNNAPI(false))
        interpreter = runtime
        runtime.allocateTensors()
        require(TensorFlowLite.runtimeVersion() == "2.16.1")
        require(runtime.inputTensorCount == 1 && runtime.outputTensorCount == 2)
        require(runtime.getInputTensor(0).shape().contentEquals(intArrayOf(1,384,384,3)))
        require(runtime.getInputTensor(0).dataType().toString() == "FLOAT32")
        for (i in 0..1) {
            val tensor=runtime.getOutputTensor(i)
            require(tensor.dataType().toString() == "FLOAT32")
            when {
                tensor.shape().contentEquals(intArrayOf(1,96,96,50)) -> outputs[i]=heat
                tensor.shape().contentEquals(intArrayOf(1,1,1,2)) -> outputs[i]=identities
                else -> error("BINDING_MISMATCH")
            }
        }
        require(outputs.values.toSet().size == 2)
        loadMs = (System.nanoTime()-start)/1e6
        Log.i("P7DR1","MODEL_LOADED FP32 XNNPACK threads=2 sha=$digest")
    }

    private fun configure(w: Int,h: Int,row: Int,pixel: Int,rotation: Int) {
        val old=prep
        if (old!=null && old.width==w && old.height==h && old.rowStride==row && old.pixelStride==pixel && old.rotation==rotation) return
        prep=P7dr1Preprocess(w,h,row,pixel,rotation)
        decoder=P7dr1Decoder(prep!!.transform)
        arguments[0]=prep!!.input
    }

    private fun process(source: ByteBuffer,start: Long,capture: Long) {
        val a=System.nanoTime()
        prep!!.run(source)
        val b=System.nanoTime()
        heat.rewind();identities.rewind()
        interpreter!!.runForMultipleInputsOutputs(arguments,outputs)
        val c=System.nanoTime()
        val native=interpreter!!.lastNativeInferenceDurationNanoseconds ?: (c-b)
        heatView.rewind();heatView.get(heatArray)
        identityView.rewind();identityView.get(identityArray)
        val d=System.nanoTime()
        decoder!!.decode(heatArray,identityArray)
        val e=System.nanoTime()
        decoder!!.restore()
        val end=System.nanoTime()
        val origin=epoch.get()
        if (start>=origin+warm && end<=origin+warm+measure) {
            require(count<CAPACITY) { "TIMING_CAPACITY_EXCEEDED" }
            val k=count*10
            samples[k]=start;samples[k+1]=end;samples[k+2]=capture
            samples[k+3]=b-a;samples[k+4]=native;samples[k+5]=c-b
            samples[k+6]=d-c;samples[k+7]=e-d;samples[k+8]=end-e;samples[k+9]=end-start
            count++
        }
    }

    private fun compute() {
        configure(640,480,2560,4,270)
        val source=ByteBuffer.allocateDirect(640*480*4)
        val bytes=ByteArray(source.capacity());Random(707).nextBytes(bytes);source.put(bytes);source.rewind()
        frameInfo=JSONObject().put("width",640).put("height",480).put("row_stride",2560).put("pixel_stride",4).put("rotation",270).put("synthetic",true)
        epoch.set(System.nanoTime());sampleMemory()
        Log.i("P7DR1","COMPUTE_START warmup=10 measured=30")
        while (!stopping.get() && System.nanoTime()<epoch.get()+warm+measure) {
            val start=System.nanoTime();process(source,start,0)
        }
        stop()
    }

    private fun bindCamera() {
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) {
            fail(IllegalStateException("CAMERA_PERMISSION_REQUIRED"));return
        }
        val future=ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                camera=future.get()
                val builder=ImageAnalysis.Builder().setTargetResolution(Size(480,360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder).setSessionCaptureCallback(object: CameraCaptureSession.CaptureCallback() {
                    override fun onCaptureCompleted(session: CameraCaptureSession,request: CaptureRequest,result: TotalCaptureResult) {
                        val now=System.nanoTime();val origin=epoch.get()
                        if(origin==0L || now<origin+warm || now>=origin+warm+measure || stopping.get())return
                        captureCount.incrementAndGet()
                        synchronized(cameraRows) {
                            if(captureRowsCount>=CAPACITY){errors.add("CAPTURE_CAPACITY_EXCEEDED");return}
                            val k=captureRowsCount*9
                            val active=result.get(CaptureResult.CONTROL_AE_TARGET_FPS_RANGE)
                            val requested=request.get(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE)
                            cameraRows[k]=now;cameraRows[k+1]=result.get(CaptureResult.SENSOR_TIMESTAMP) ?: -1
                            cameraRows[k+2]=result.get(CaptureResult.SENSOR_FRAME_DURATION) ?: -1
                            cameraRows[k+3]=result.get(CaptureResult.SENSOR_EXPOSURE_TIME) ?: -1
                            cameraRows[k+4]=active?.lower?.toLong() ?: -1;cameraRows[k+5]=active?.upper?.toLong() ?: -1
                            cameraRows[k+6]=requested?.lower?.toLong() ?: -1;cameraRows[k+7]=requested?.upper?.toLong() ?: -1
                            cameraRows[k+8]=result.frameNumber;captureRowsCount++
                        }
                    }
                })
                val analysis=builder.build();analysis.setAnalyzer(worker) { analyze(it) }
                val bound=camera!!.bindToLifecycle(this,CameraSelector.DEFAULT_FRONT_CAMERA,analysis)
                val info=Camera2CameraInfo.from(bound.cameraInfo)
                realTimeClock=info.getCameraCharacteristic(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)==CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME
                cameraInfo=JSONObject().put("available_AE_FPS_ranges",info.getCameraCharacteristic(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)?.joinToString() ?: "UNKNOWN")
                    .put("sensor_realtime_clock",realTimeClock).put("settings_changed",false)
                status.text="P7D-R1 $phase: diagnostics only; no recording"
                handler.postDelayed({if(epoch.get()==0L && !stopping.get())fail(IllegalStateException("CAMERA_NO_FRAMES"))},30000)
            } catch(e: Throwable){fail(e)}
        },ContextCompat.getMainExecutor(this))
    }

    private fun analyze(image: ImageProxy) {
        if(stopping.get()){image.close();return}
        val start=System.nanoTime()
        try {
            val plane=image.planes[0]
            if(epoch.compareAndSet(0,start)) {
                frameInfo=JSONObject().put("width",image.width).put("height",image.height).put("row_stride",plane.rowStride)
                    .put("pixel_stride",plane.pixelStride).put("rotation",image.imageInfo.rotationDegrees).put("synthetic",false)
                handler.postDelayed({stop()},(warm+measure)/1_000_000)
                Log.i("P7DR1","${phase}_START warmup_ns=$warm measured_ns=$measure")
            }
            val origin=epoch.get()
            if(start>=origin+warm && start<origin+warm+measure) {
                require(arrivals<CAPACITY)
                arrivalRows[arrivals*2]=start;arrivalRows[arrivals*2+1]=image.imageInfo.timestamp;arrivals++
            }
            if(phase!="camera") {
                configure(image.width,image.height,plane.rowStride,plane.pixelStride,image.imageInfo.rotationDegrees)
                process(plane.buffer,start,image.imageInfo.timestamp)
            }
        } catch(e: Throwable){fail(e)} finally {image.close()}
    }

    private fun sampleMemory() {
        try {
            val runtime=Runtime.getRuntime();val now=System.nanoTime();val start=epoch.get()
            memory.add(JSONObject().put("nano_time",now).put("elapsed_seconds",if(start>0)(now-start)/1e9 else -1)
                .put("pss_kib",Debug.getPss()).put("native_heap_bytes",Debug.getNativeHeapAllocatedSize())
                .put("java_heap_bytes",runtime.totalMemory()-runtime.freeMemory())
                .put("thermal",(getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus))
        }catch(e: Throwable){errors.add("MEMORY: $e");Log.e("P7DR1","Memory sampling failed",e)}
    }

    private fun fail(e: Throwable) {errors.add(e.stackTraceToString());Log.e("P7DR1","FAILED",e);stop()}
    private fun stop() {
        if(!stopping.compareAndSet(false,true))return
        runOnUiThread {camera?.unbindAll();worker.execute {finishResult()}}
    }

    private fun finishResult() {
        sampleMemory();monitor.shutdown();interpreter?.close();interpreter=null
        val rows=JSONArray()
        val latencies=DoubleArray(count)
        for(i in 0 until count) {
            val k=i*10;latencies[i]=samples[k+9]/1e6
            rows.put(JSONObject().put("start_ns",samples[k]).put("end_ns",samples[k+1]).put("capture_ns",samples[k+2])
                .put("preprocess_ms",samples[k+3]/1e6).put("backend_native_ms",samples[k+4]/1e6)
                .put("invoke_wall_ms",samples[k+5]/1e6).put("output_read_ms",samples[k+6]/1e6)
                .put("decoder_ms",samples[k+7]/1e6).put("restore_ms",samples[k+8]/1e6).put("perception_ms",latencies[i]))
        }
        latencies.sort();val q=.95*maxOf(0,count-1);val low=q.toInt()
        val p95=if(count>0)latencies[low]+(latencies[minOf(low+1,count-1)]-latencies[low])*(q-low) else null
        val fps=count/(measure/1e9)
        val capturesJson=JSONArray()
        synchronized(cameraRows){for(i in 0 until captureRowsCount){val row=JSONArray();for(c in 0..8)row.put(cameraRows[i*9+c]);capturesJson.put(row)}}
        val arrivalJson=JSONArray();for(i in 0 until arrivals)arrivalJson.put(JSONArray().put(arrivalRows[i*2]).put(arrivalRows[i*2+1]))
        val result=JSONObject().put("phase",phase).put("device",Build.MODEL).put("soc",Build.SOC_MODEL).put("android",Build.VERSION.RELEASE)
            .put("model_sha256",MODEL_SHA).put("runtime","2.16.1").put("provider","XNNPACK").put("threads",2).put("precision","FP32")
            .put("model_load_ms",if(phase=="camera")JSONObject.NULL else loadMs).put("warmup_seconds",warm/1e9).put("measured_seconds",measure/1e9)
            .put("measurement_start_ns",epoch.get()+warm).put("measurement_end_ns",epoch.get()+warm+measure)
            .put("completed",count).put("completed_fps",fps).put("perception_p95_ms",p95 ?: JSONObject.NULL)
            .put("compute_screen_pass",phase=="compute" && errors.isEmpty() && p95!=null && p95<=62.7532812 && fps>=15)
            .put("samples",rows).put("frame_metadata",frameInfo).put("camera_metadata",cameraInfo)
            .put("analyzer_callbacks",arrivals).put("analyzer_fps",arrivals/(measure/1e9))
            .put("capture_completions",captureCount.get()).put("capture_fps",captureCount.get()/(measure/1e9))
            .put("capture_columns",JSONArray(listOf("callback_ns","sensor_timestamp_ns","frame_duration_ns","exposure_ns","active_ae_min","active_ae_max","request_ae_min","request_ae_max","frame_number")))
            .put("capture_rows",capturesJson).put("arrival_rows",arrivalJson).put("memory",JSONArray(memory.toList()))
            .put("errors",JSONArray(errors.toList())).put("policy",P7dMath.POLICY).put("recognizer_used",false)
        root.mkdirs();val target=File(root,"${phase}_result.json")
        require(!target.exists());target.writeText(result.toString(2))
        Log.i("P7DR1","COMPLETE phase=$phase count=$count fps=$fps p95=$p95 errors=${errors.size}")
        runOnUiThread {status.text="P7D-R1 $phase complete. No recognition."}
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if(::root.isInitialized && !stopping.get()){errors.add("ACTIVITY_DESTROYED");stop()}
        // Queued teardown owns interpreter; never race-close it on the main thread.
        monitor.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val CAPACITY=20000
        private const val MODEL_SHA="d8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e"
        private fun buffer(count:Int)=ByteBuffer.allocateDirect(count*4).order(ByteOrder.nativeOrder())
    }
}
