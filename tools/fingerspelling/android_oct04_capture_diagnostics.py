"""Clarify the bounded capture controls and retain failure diagnostics."""
from tools.fingerspelling.android_oct04_port import DEST

def main():
    activity=DEST/"android/app/src/main/java/com/example/apphear/RecognitionActivity.kt"
    text=activity.read_text(encoding="utf-8")
    text=text.replace('text = "Experimental fingerspelling • select a mode"; textSize = 14f', 'text = "Experimental fingerspelling • select a mode"; textSize = 14f; setTextColor(getColor(R.color.color_text_primary))')
    text=text.replace("        panel.addView(fingerspellStatus)\n", """        panel.addView(fingerspellStatus)
        panel.addView(TextView(this).apply {
            text = "One attempt: Start → spell → Done → review → Use"
            textSize = 12f; setTextColor(getColor(R.color.color_text_secondary))
        })
""")
    text=text.replace('val button = MaterialButton(this).apply { text = label;', '''val button = MaterialButton(this).apply {
                    setTextColor(android.content.res.ColorStateList(
                        arrayOf(intArrayOf(android.R.attr.state_enabled), intArrayOf()),
                        intArrayOf(getColor(R.color.color_text_on_brand), getColor(R.color.color_text_secondary))))
                    text = label;''')
    text=text.replace('FingerspellPhase.DECODING -> "Decoding…"; else -> "Ready"', 'FingerspellPhase.DECODING -> "Decoding…"; FingerspellPhase.ERROR -> "Retry needed"; else -> "Ready"')
    activity.write_text(text,encoding="utf-8",newline="\n")
    runtime=DEST/"android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellRuntime.kt"
    text=runtime.read_text(encoding="utf-8")
    text=text.replace('    private var captureFinishedNs=0L', '    private var acceptedObservations=0\n    private var captureFinishedNs=0L')
    text=text.replace('        captureStartedNs=SystemClock.elapsedRealtimeNanos()', '        acceptedObservations=0\n        captureStartedNs=SystemClock.elapsedRealtimeNanos()')
    text=text.replace('            session.consume(common.timestampMs,packed)', '            session.consume(common.timestampMs,packed)\n            acceptedObservations=session.count')
    text=text.replace('} catch(error:Throwable) { session.fail(); emit("Capture failed:', '} catch(error:Throwable) { writeFailure("CAPTURE",error); session.fail(); emit("Capture failed:')
    text=text.replace('} catch(error:Throwable) { session.fail(); emit("Decode failed:', '} catch(error:Throwable) { writeFailure("DECODE",error); session.fail(); emit("Decode failed:')
    text=text.replace('    private fun writeProfile(n:Int,finishMs:Double,text:String) {', '''    private fun writeFailure(stage:String,error:Throwable) {
        runCatching {
            val report=JSONObject().put("schema_version","apphear.fingerspelling.failed_session.v1")
                .put("stage",stage).put("error",error.message.orEmpty())
                .put("accepted_observations",acceptedObservations)
                .put("elapsed_seconds",(SystemClock.elapsedRealtimeNanos()-captureStartedNs)/1e9)
                .put("session_limits",models.manifest.getJSONObject("session_limits"))
                .put("retained_slots_seen",trustedSlots).put("no_crop_frames_seen",noCropFrames)
                .put("inference_completed",false).put("training",false)
            val dir=File(context.filesDir,"fingerspelling_sessions").apply { mkdirs() }
            File(dir,"failed_session_${System.currentTimeMillis()}.json").writeText(report.toString(2))
        }.onFailure { Log.e(TAG,"failure diagnostic unavailable",it) }
    }
    private fun writeProfile(n:Int,finishMs:Double,text:String) {''')
    runtime.write_text(text,encoding="utf-8",newline="\n")
    print("Experimental capture guidance/contrast fixed; future failures retained separately. No model or limit change.")

if __name__=="__main__": main()
