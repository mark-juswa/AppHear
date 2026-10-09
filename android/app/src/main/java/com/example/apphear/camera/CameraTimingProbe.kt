package com.example.apphear.camera

import org.json.JSONArray
import org.json.JSONObject

/** Bounded camera-layer diagnostics only; never alters pixels, cadence or recognition. */
internal class CameraTimingProbe(private val front:Boolean, private val generation:Int, private val requestedFps:Int) {
    private val sensor=mutableListOf<Long>()
    private val exposures=mutableListOf<Long>()
    private val observations=mutableListOf<Long>()
    private val analysisMs=mutableListOf<Double>()
    @Synchronized fun capture(timestamp:Long?, exposure:Long?) {
        if(timestamp!=null && sensor.size<240) sensor.add(timestamp)
        if(exposure!=null && exposures.size<240) exposures.add(exposure)
    }
    @Synchronized fun analyzed(timestamp:Long, elapsedMs:Double):Boolean {
        if(observations.size>=48) return false
        observations.add(timestamp); analysisMs.add(elapsedMs)
        return observations.size==12 || observations.size==48
    }
    @Synchronized fun report(mode:String):JSONObject {
        fun rate(values:List<Long>):Double? = if(values.size<2 || values.last()<=values.first()) null
            else (values.size-1)*1e9/(values.last()-values.first())
        fun percentile(values:List<Double>,p:Double):Double? = values.sorted().let {
            if(it.isEmpty()) null else it[((it.size-1)*p).toInt()]
        }
        return JSONObject().put("schema_version","apphear.camera_layer_timing.v1")
            .put("front",front).put("generation",generation).put("mode",mode)
            .put("camera_sensor_frames",sensor.size).put("sensor_fps",rate(sensor) ?: JSONObject.NULL)
            .put("processed_observations",observations.size)
            .put("observation_fps",rate(observations) ?: JSONObject.NULL)
            .put("analysis_p50_ms",percentile(analysisMs,.5) ?: JSONObject.NULL)
            .put("analysis_p95_ms",percentile(analysisMs,.95) ?: JSONObject.NULL)
            .put("exposure_p50_ms",percentile(exposures.map { it/1e6 },.5) ?: JSONObject.NULL)
            .put("observation_timestamps_ns",JSONArray(observations))
            .put("analysis_ms",JSONArray(analysisMs))
            .put("requested_ae_fps","$requestedFps,$requestedFps").put("accuracy_claim","NONE")
            .put("sensor_fps_is_not_preview_presentation_fps",true)
    }
}
