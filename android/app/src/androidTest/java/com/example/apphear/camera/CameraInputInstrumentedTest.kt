package com.example.apphear.camera

import androidx.test.platform.app.InstrumentationRegistry
import com.example.apphear.perceptionvnext.PerceptionVNextNative
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Same asymmetric upright scene encoded in every sensor orientation/stride. No recognition tuning. */
class CameraInputInstrumentedTest {
    @Test fun allSensorRotationsProduceIdenticalUnmirroredPoseAndHandInputs() {
        val w=240; val h=320
        var referencePose:ByteArray?=null; var referenceCrop:ByteArray?=null
        var cases=0
        for(rotation in intArrayOf(0,90,180,270)) for(pixelStride in intArrayOf(4,8)) {
            val rw=if(rotation==90 || rotation==270) h else w
            val rh=if(rotation==90 || rotation==270) w else h
            val rowStride=rw*pixelStride+16
            val source=ByteBuffer.allocateDirect(rowStride*rh).order(ByteOrder.nativeOrder())
            for(y in 0 until h) for(x in 0 until w) {
                val (rx,ry)=when(rotation) {
                    90 -> y to rh-1-x
                    180 -> rw-1-x to rh-1-y
                    270 -> rw-1-y to x
                    else -> x to y
                }
                val offset=ry*rowStride+rx*pixelStride
                source.put(offset,((x*3+y)%256).toByte())
                source.put(offset+1,((y*5+x/7)%256).toByte())
                source.put(offset+2,(if(x < w/3 && y < h/2) 250 else 13).toByte())
                source.put(offset+3,255.toByte())
            }
            val handle=PerceptionVNextNative.create(rw,rh,rowStride,pixelStride,rotation)
            try {
                assertArrayEquals(intArrayOf(w,h),PerceptionVNextNative.geometry(handle))
                val pose=ByteBuffer.allocateDirect(3*256*192*4).order(ByteOrder.nativeOrder())
                PerceptionVNextNative.preprocess(handle,source,0,source.remaining(),pose)
                val crop=ByteBuffer.allocateDirect(224*224*3*4).order(ByteOrder.nativeOrder())
                PerceptionVNextNative.crop(handle,83f,171f,143f,crop)
                val poseBytes=ByteArray(pose.capacity()); pose.rewind(); pose.get(poseBytes)
                val cropBytes=ByteArray(crop.capacity()); crop.rewind(); crop.get(cropBytes)
                if(referencePose==null) { referencePose=poseBytes; referenceCrop=cropBytes }
                else {
                    assertArrayEquals("pose rotation=$rotation stride=$pixelStride",referencePose,poseBytes)
                    assertArrayEquals("crop rotation=$rotation stride=$pixelStride",referenceCrop,cropBytes)
                }
                cases++
            } finally { PerceptionVNextNative.destroy(handle) }
        }
        InstrumentationRegistry.getInstrumentation().targetContext.filesDir.resolve("camera_rotation_parity.json")
            .writeText(JSONObject().put("status","PASS").put("cases",cases)
                .put("pose_tensor_byte_identical",true).put("hand_tensor_byte_identical",true)
                .put("rotation_degrees","0,90,180,270").put("horizontal_flip",false)
                .put("accuracy_claim","NONE").toString(2))
    }
}
