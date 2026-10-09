"""Small integration safeguards, confined to the experimental owner."""
from tools.fingerspelling.android_oct04_port import DEST

def main():
    activity = DEST / "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt"
    text = activity.read_text()
    anchor = "    private fun renderPhraseAssist(state: PhraseAssistUiState) {\n"
    text = text.replace(anchor, anchor + '''        if (fingerspellRuntime?.snapshot?.mode == RecognitionMode.FINGERSPELL) {
            // WORD advisory remains cached; spelling never feeds its matcher/provider.
            binding.possibleRepliesGroup.visibility = View.GONE
            binding.contextSupportedGroup.visibility = View.GONE
            return
        }
''')
    text = text.replace("                                } else false\n", """                                } else {
                                    spelling?.recordWordCadence(observation)
                                    false
                                }
""")
    text = text.replace("            renderFingerspell(snapshot)\n", "            renderFingerspell(snapshot)\n            renderPhraseAssist(ConversationPhraseAssist.presentationState.value)\n")
    text = text.replace('            binding.sentenceText.text = s.confirmed.ifBlank { "Confirm spelling with Use" }\n', '            binding.sentenceText.text = s.confirmed.ifBlank { "Confirm spelling with Use" }\n            updateSentenceCardVisibility()\n')
    # Already handled at the beginning, before WORD sidecar processing.
    block = '''            fingerspellRuntime?.snapshot?.takeIf { it.mode == RecognitionMode.FINGERSPELL }?.let {
                renderFingerspell(it)
                return@runOnUiThread
            }
'''
    assert text.count(block) == 1
    text = text.replace(block, "")
    activity.write_text(text, newline="\n")
    runtime = DEST / "android/app/src/main/java/com/example/apphear/fingerspelling/FingerspellRuntime.kt"
    text = runtime.read_text()
    text = text.replace("    private var captureStartedNs=0L", """    private val wordTimestamps=mutableListOf<Double>()
    private val wordCandidate=mutableListOf<Double>()
    private var captureFinishedNs=0L
    private var captureStartedNs=0L""")
    text = text.replace("        session.cancel(); models.adapter.reset(); owner.select(mode);", "        if(mode==RecognitionMode.FINGERSPELL) writeWordProfile()\n        wordTimestamps.clear(); wordCandidate.clear()\n        session.cancel(); models.adapter.reset(); owner.select(mode);")
    text = text.replace("    fun start() {", """    fun recordWordCadence(observation:PhoneRawObservation) {
        if(owner.mode!=RecognitionMode.WORD) return
        wordTimestamps.add(observation.timestampMs)
        observation.candidateTotalMs?.let { wordCandidate.add(it) }
        if(wordTimestamps.size>256) wordTimestamps.removeAt(0)
        if(wordCandidate.size>256) wordCandidate.removeAt(0)
    }
    private fun writeWordProfile() {
        if(wordTimestamps.size<2) return
        val gaps=wordTimestamps.zipWithNext { a,b -> b-a }.sorted()
        val span=(wordTimestamps.last()-wordTimestamps.first())/1000.0
        if(span<=0) return
        val times=wordCandidate.sorted()
        val report=JSONObject().put("schema_version","apphear.fingerspelling.word_cadence.v1")
            .put("delivered_observations",wordTimestamps.size).put("span_seconds",span)
            .put("observations_per_second",(wordTimestamps.size-1)/span)
            .put("gap_p50_ms",gaps[(gaps.size-1)/2]).put("gap_p95_ms",gaps[((gaps.size-1)*.95).toInt()])
            .put("gap_max_ms",gaps.last()).put("candidate_p50_ms",if(times.isEmpty()) JSONObject.NULL else times[(times.size-1)/2])
            .put("candidate_p95_ms",if(times.isEmpty()) JSONObject.NULL else times[((times.size-1)*.95).toInt()])
            .put("keep_only_latest",true).put("dropped_frame_count","NOT_MEASURED").put("training",false)
        File(context.filesDir,"fingerspell_word_cadence.json").writeText(report.toString(2))
    }
    fun start() {""")
    text = text.replace("            val (token,frames)=session.finish();", "            captureFinishedNs=SystemClock.elapsedRealtimeNanos()\n            val (token,frames)=session.finish();")
    text = text.replace("    fun pause() { session.cancel();", "    fun pause() { wordTimestamps.clear(); wordCandidate.clear(); session.cancel();")
    text = text.replace("(SystemClock.elapsedRealtimeNanos()-captureStartedNs)/1e9", "(captureFinishedNs-captureStartedNs)/1e9")
    runtime.write_text(text, newline="\n")
    print("WORD-only sidecar presentation isolated; confirmed spelling visible; cadence reporting added without model-input changes.")

if __name__ == "__main__":
    main()
