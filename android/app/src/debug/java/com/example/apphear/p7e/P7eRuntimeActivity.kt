package com.example.apphear.p7e

import com.example.apphear.p7dr2.P7dr2Path
import com.example.apphear.p7dr2.P7dr2Parity

import android.Manifest
import android.content.pm.PackageManager
import android.hardware.camera2.*
import android.os.*
import android.util.Log
import android.util.Size
import android.util.Range
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
import java.util.concurrent.Executors
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** Isolated explicit ADB entry. No production pipeline, recognition, validity policy or recording. */
@androidx.annotation.OptIn(ExperimentalCamera2Interop::class)
class P7eRuntimeActivity : AppCompatActivity() {
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
    private var path: P7dr2Path? = null
    private val variant = 3
    private lateinit var runName: String
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
    private val arrivalRows = LongArray(CAPACITY * 8)
    private val smokeRows = JSONArray()
    private var selectedCameraId = ""
    private var count = 0
    private var arrivals = 0
    private var captureRowsCount = 0
    private var frameInfo = JSONObject()
    private var cameraInfo = JSONObject()
    private var realTimeClock = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply { text = "P7E disabled; diagnostics only" }
        setContentView(status)
        if (!intent.getBooleanExtra("p7e_enabled",false)) return
        root = File(getExternalFilesDir(null),"p7e")
        phase = intent.getStringExtra("phase") ?: ""
        runName = phase
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        worker.execute {
            try {
                require(phase in listOf("parity","smoke","camera","integrated"))
                require(!File(root,"${runName}_result.json").exists()) { "NO_RESULT_OVERWRITE" }
                val gate = JSONObject(File(root,"host_gate.json").readText())
                require(gate.getBoolean("jvm_tests_pass"))
                require(gate.getString("authorized_run")==runName)
                require(fileHash(File(applicationInfo.sourceDir))==gate.getString("apk_sha256"))
                require(gate.getString("model_sha256") == MODEL_SHA)
                require(fileHash(File(root,"random_skeleton.tflite"))==MODEL_SHA)
                require(Build.MODEL == "M2101K7AG" && Build.SOC_MODEL == "SM6150" && Build.VERSION.RELEASE == "12")
                if(phase=="parity"){runParity();return@execute}
                require(JSONObject(File(root,"parity_result.json").readText()).getBoolean("passed"))
                require(gate.getBoolean("native_parity_verified"))
                if(phase!="smoke"){
                    require(gate.getBoolean("candidate_frozen"))
                    require(JSONObject(File(root,"smoke_result.json").readText()).getBoolean("passed"))
                }
                if(phase=="integrated"){
                    val prior=JSONObject(File(root,"camera_result.json").readText())
                    require(prior.getBoolean("camera_screen_pass")){"CAMERA_SCREEN_NOT_PASSED"}
                    require(gate.getBoolean("camera_pass_verified"))
                }
                require((getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus==0) {"THERMAL_NOT_NONE"}
                warm = if(phase=="integrated")30_000_000_000L else 0L
                measure = if(phase=="integrated")180_000_000_000L else if(phase=="camera")60_000_000_000L else 0L
                if(phase=="integrated"){
                    loadModel()
                    Log.i("P7E","READY run=$runName waiting_for_host_delegation_verification")
                    val deadline=System.nanoTime()+60_000_000_000L
                    while(!File(root,"go_integrated.json").exists() && System.nanoTime()<deadline) Thread.sleep(100)
                    val go=JSONObject(File(root,"go_integrated.json").readText())
                    require(go.getBoolean("delegation_44_of_44") && go.getString("apk_sha256")==gate.getString("apk_sha256"))
                }
                monitor.scheduleAtFixedRate({ sampleMemory() },0,5,TimeUnit.SECONDS)
                runOnUiThread { bindCamera() }
            } catch (e: Throwable) { fail(e) }
        }
    }

    private fun loadModel() {
        val model = File(root,"random_skeleton.tflite")
        val digest = fileHash(model)
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
        Log.i("P7E","MODEL_LOADED FP32 XNNPACK threads=2 sha=$digest")
    }

    private fun configure(w: Int,h: Int,row: Int,pixel: Int,rotation: Int) {
        val old=path
        if(old!=null && old.width==w && old.height==h && old.rowStride==row && old.pixelStride==pixel && old.rotation==rotation)return
        old?.close()
        path=P7dr2Path(variant,w,h,row,pixel,rotation)
        arguments[0]=path!!.input
    }

    private fun process(source: ByteBuffer,start: Long,capture: Long) {
        val a=System.nanoTime()
        path!!.preprocess(source)
        val b=System.nanoTime()
        heat.rewind();identities.rewind()
        interpreter!!.runForMultipleInputsOutputs(arguments,outputs)
        val c=System.nanoTime()
        val native=interpreter!!.lastNativeInferenceDurationNanoseconds ?: (c-b)
        heatView.rewind();heatView.get(heatArray)
        identityView.rewind();identityView.get(identityArray)
        val d=System.nanoTime()
        path!!.decode(heatArray,identityArray)
        val e=System.nanoTime()
        path!!.restore()
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

    private fun bindCamera() {
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) {
            fail(IllegalStateException("CAMERA_PERMISSION_REQUIRED"));return
        }
        val future=ProcessCameraProvider.getInstance(this)
        future.addListener({
            try {
                camera=future.get()
                val selected=CameraSelector.DEFAULT_FRONT_CAMERA.filter(camera!!.availableCameraInfos).first()
                val preInfo=Camera2CameraInfo.from(selected)
                selectedCameraId=preInfo.cameraId
                val ranges=preInfo.getCameraCharacteristic(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)
                require(ranges?.contains(Range(15,15))==true){"FIXED_15_NOT_ADVERTISED"}
                cameraInfo=JSONObject().put("camera_id",selectedCameraId).put("lens","DEFAULT_FRONT_CAMERA")
                    .put("available_AE_FPS_ranges",ranges!!.joinToString()).put("requested_resolution",JSONArray(listOf(480,360)))
                    .put("only_setting_changed","CONTROL_AE_TARGET_FPS_RANGE").put("requested_AE",JSONArray(listOf(15,15)))
                val builder=ImageAnalysis.Builder().setTargetResolution(Size(480,360))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                Camera2Interop.Extender(builder)
                    .setCaptureRequestOption(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE,Range(15,15))
                    .setSessionCaptureCallback(object: CameraCaptureSession.CaptureCallback() {
                    override fun onCaptureCompleted(session: CameraCaptureSession,request: CaptureRequest,result: TotalCaptureResult) {
                        val now=System.nanoTime();val origin=epoch.get()
                        if(phase=="smoke"){
                            if(stopping.get())return
                            val active=result.get(CaptureResult.CONTROL_AE_TARGET_FPS_RANGE)
                            val requested=request.get(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE)
                            synchronized(smokeRows){
                                smokeRows.put(JSONObject().put("frame_number",result.frameNumber)
                                    .put("requested",JSONArray(listOf(requested?.lower ?: -1,requested?.upper ?: -1)))
                                    .put("active",JSONArray(listOf(active?.lower ?: -1,active?.upper ?: -1))))
                                if(smokeRows.length()>=12)stop()
                            }
                            return
                        }
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
                require(info.cameraId==selectedCameraId){"CAMERA_SELECTION_CHANGED"}
                cameraInfo.put("sensor_realtime_clock",realTimeClock)
                if(phase!="smoke"){
                    val smoke=JSONObject(File(root,"smoke_result.json").readText())
                    require(smoke.getJSONObject("camera_metadata").getString("camera_id")==selectedCameraId){"CAMERA_ID_NOT_FROZEN"}
                }
                Log.i("P7E","CAMERA_BOUND id=$selectedCameraId policy=C15_FIXED_AE request_resolution=480x360")
                if(phase=="smoke")handler.postDelayed({if(!stopping.get())fail(IllegalStateException("SMOKE_CALLBACK_TIMEOUT"))},30000)
                status.text="P7E $phase: diagnostics only; no recording"
                handler.postDelayed({if(epoch.get()==0L && !stopping.get())fail(IllegalStateException("CAMERA_NO_FRAMES"))},30000)
            } catch(e: Throwable){fail(e)}
        },ContextCompat.getMainExecutor(this))
    }

    private fun analyze(image: ImageProxy) {
        if(stopping.get()){image.close();return}
        val start=System.nanoTime()
        try {
            val plane=image.planes[0]
            if(phase=="smoke"){
                frameInfo=JSONObject().put("width",image.width).put("height",image.height).put("row_stride",plane.rowStride)
                    .put("pixel_stride",plane.pixelStride).put("rotation",image.imageInfo.rotationDegrees).put("synthetic",false)
                return
            }
            if(epoch.compareAndSet(0,start)) {
                frameInfo=JSONObject().put("width",image.width).put("height",image.height).put("row_stride",plane.rowStride)
                    .put("pixel_stride",plane.pixelStride).put("rotation",image.imageInfo.rotationDegrees).put("synthetic",false)
                handler.postDelayed({stop()},(warm+measure)/1_000_000)
                Log.i("P7E","${phase}_START warmup_ns=$warm measured_ns=$measure")
            }
            val origin=epoch.get()
            if(start>=origin+warm && start<origin+warm+measure) {
                require(arrivals<CAPACITY)
                val k=arrivals*8
                arrivalRows[k]=start;arrivalRows[k+1]=image.imageInfo.timestamp
                arrivalRows[k+2]=image.width.toLong();arrivalRows[k+3]=image.height.toLong()
                arrivalRows[k+4]=plane.rowStride.toLong();arrivalRows[k+5]=plane.pixelStride.toLong()
                arrivalRows[k+6]=image.imageInfo.rotationDegrees.toLong();arrivalRows[k+7]=0;arrivals++
            }
            if(phase=="integrated") {
                configure(image.width,image.height,plane.rowStride,plane.pixelStride,image.imageInfo.rotationDegrees)
                process(plane.buffer,start,image.imageInfo.timestamp)
            }
        } catch(e: Throwable){fail(e)} finally {image.close()}
    }

    private fun sampleMemory() {
        try {
            val thermal=(getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus
            if(thermal!=0 && !stopping.get()){fail(IllegalStateException("THERMAL_INVALIDATED_$thermal"));return}
            val runtime=Runtime.getRuntime();val now=System.nanoTime();val start=epoch.get()
            memory.add(JSONObject().put("nano_time",now).put("elapsed_seconds",if(start>0)(now-start)/1e9 else -1)
                .put("pss_kib",Debug.getPss()).put("native_heap_bytes",Debug.getNativeHeapAllocatedSize())
                .put("java_heap_bytes",runtime.totalMemory()-runtime.freeMemory())
                .put("thermal",(getSystemService(POWER_SERVICE) as PowerManager).currentThermalStatus))
        }catch(e: Throwable){errors.add("MEMORY: $e");Log.e("P7E","Memory sampling failed",e)}
    }

    private fun fail(e: Throwable) {errors.add(e.stackTraceToString());Log.e("P7E","FAILED",e);stop()}
    private fun stop() {
        if(!stopping.compareAndSet(false,true))return
        runOnUiThread {camera?.unbindAll();worker.execute {finishResult()}}
    }

    private fun finishResult() {
        sampleMemory();monitor.shutdown();interpreter?.close();interpreter=null;path?.close();path=null
        if(phase=="smoke"){
            val exact=synchronized(smokeRows){smokeRows.length()==12 && (0 until 12).all{
                val r=smokeRows.getJSONObject(it)
                r.getJSONArray("requested").toString()=="[15,15]" && r.getJSONArray("active").toString()=="[15,15]"
            }}
            val result=JSONObject().put("passed",exact && errors.isEmpty()).put("performance_evidence",false)
                .put("camera_metadata",cameraInfo).put("frame_metadata",frameInfo).put("capture_policy_rows",smokeRows)
                .put("errors",JSONArray(errors.toList())).put("memory",JSONArray(memory.toList()))
            File(root,"smoke_result.json").writeText(result.toString(2))
            Log.i("P7E","SMOKE_COMPLETE passed=${result.getBoolean("passed")}; no FPS calculation")
            worker.shutdown();return
        }
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
        val fps=if(measure>0)count/(measure/1e9) else 0.0
        val capturesJson=JSONArray()
        synchronized(cameraRows){for(i in 0 until captureRowsCount){val row=JSONArray();for(c in 0..8)row.put(cameraRows[i*9+c]);capturesJson.put(row)}}
        val arrivalJson=JSONArray();for(i in 0 until arrivals){val row=JSONArray();for(c in 0..7)row.put(arrivalRows[i*8+c]);arrivalJson.put(row)}
        val policyExact=captureRowsCount>0 && (0 until captureRowsCount).all{i->(4..7).all{cameraRows[i*9+it]==15L}}
        val thermalValid=memory.all{it.getInt("thermal")==0}
        val cameraPass=phase=="camera" && errors.isEmpty() && thermalValid && policyExact &&
            P7eGate.cameraPass(captureCount.get(),arrivals.toLong(),measure/1e9)
        val result=JSONObject().put("phase",phase).put("variant",variant).put("run",runName).put("device",Build.MODEL).put("soc",Build.SOC_MODEL).put("android",Build.VERSION.RELEASE)
            .put("model_sha256",MODEL_SHA).put("runtime","2.16.1").put("provider","XNNPACK").put("threads",2).put("precision","FP32")
            .put("model_load_ms",if(phase!="integrated")JSONObject.NULL else loadMs).put("warmup_seconds",warm/1e9).put("measured_seconds",measure/1e9)
            .put("measurement_start_ns",epoch.get()+warm).put("measurement_end_ns",epoch.get()+warm+measure)
            .put("completed",count).put("completed_fps",fps).put("perception_p95_ms",p95 ?: JSONObject.NULL)
            .put("camera_policy_exact",policyExact).put("camera_screen_pass",cameraPass)
            .put("thermal_valid",thermalValid).put("variant_name","C15_FIXED_AE")
            .put("arrival_columns",JSONArray(listOf("callback_ns","sensor_timestamp_ns","width","height","row_stride","pixel_stride","rotation","synthetic_zero")))
            .put("samples",rows).put("frame_metadata",frameInfo).put("camera_metadata",cameraInfo)
            .put("analyzer_callbacks",arrivals).put("analyzer_fps",if(measure>0)arrivals/(measure/1e9) else 0.0)
            .put("capture_completions",captureCount.get()).put("capture_fps",if(measure>0)captureCount.get()/(measure/1e9) else 0.0)
            .put("capture_columns",JSONArray(listOf("callback_ns","sensor_timestamp_ns","frame_duration_ns","exposure_ns","active_ae_min","active_ae_max","request_ae_min","request_ae_max","frame_number")))
            .put("capture_rows",capturesJson).put("arrival_rows",arrivalJson).put("memory",JSONArray(memory.toList()))
            .put("errors",JSONArray(errors.toList())).put("policy",P7dMath.POLICY).put("recognizer_used",false)
        root.mkdirs();val target=File(root,"${runName}_result.json")
        require(!target.exists());target.writeText(result.toString(2))
        Log.i("P7E","COMPLETE run=$runName count=$count fps=$fps p95=$p95 errors=${errors.size}")
        runOnUiThread {status.text="P7E $runName complete. No recognition."}
        worker.shutdown()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if(::root.isInitialized && !stopping.get()){errors.add("ACTIVITY_DESTROYED");stop()}
        // Queued teardown owns interpreter; never race-close it on the main thread.
        monitor.shutdown()
        super.onDestroy()
    }

    private fun fileHash(file:File):String {
        val digest=MessageDigest.getInstance("SHA-256")
        file.inputStream().use {stream->val bytes=ByteArray(65536);while(true){val n=stream.read(bytes);if(n<0)break;digest.update(bytes,0,n)}}
        return digest.digest().joinToString(""){"%02x".format(it)}
    }
    private fun runParity() {
        val result=JSONObject().put("timing_collected",false).put("model_sha256",MODEL_SHA)
        var stage="identity"
        try {
            require(fileHash(File(root,"random_skeleton.tflite"))==MODEL_SHA)
            stage="preprocess";result.put("preprocess",P7dr2Parity.preprocessing())
            Log.i("P7E","PARITY_PREPROCESS_PASS")
            stage="decoder";result.put("decoder",P7dr2Parity.decoding())
            Log.i("P7E","PARITY_DECODER_PASS")
            stage="combined";result.put("combined",P7dr2Parity.combined(File(root,"random_skeleton.tflite")))
            require(TensorFlowLite.runtimeVersion()=="2.16.1")
            result.put("passed",true)
        } catch(e:Throwable) {
            result.put("passed",false).put("failed_stage",stage).put("error",e.stackTraceToString())
            Log.e("P7E","PARITY_FAILED",e)
        }
        root.mkdirs();File(root,"parity_result.json").writeText(result.toString(2))
        stopping.set(true)
        Log.i("P7E","PARITY_COMPLETE passed="+result.getBoolean("passed"))
        runOnUiThread {status.text="R2 parity complete; no timing run."}
        worker.shutdown()
    }

    companion object {
        private const val CAPACITY=20000
        private const val MODEL_SHA="d8617516aa08b4827c7a75276c5de5c0d76a07620a07d212d323992c188ee42e"
        private fun buffer(count:Int)=ByteBuffer.allocateDirect(count*4).order(ByteOrder.nativeOrder())
    }
}
