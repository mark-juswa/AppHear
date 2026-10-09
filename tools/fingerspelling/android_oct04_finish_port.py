"""Resolve three reviewed additive conflicts; preserve October 4 WORD evidence."""
from tools.fingerspelling.android_oct04_port import DEST, ROOT
import re

def main():
    activity = DEST / "android/app/src/main/java/com/example/apphear/RecognitionActivity.kt"
    text = activity.read_text()
    def resolve(match):
        ours, theirs = match.group(1), match.group(2)
        if "import android.widget.LinearLayout" in ours:
            return ours
        if "private var fingerspellRuntime" in ours:
            return ours + theirs
        assert "val spelling = fingerspellRuntime" in ours
        return theirs.replace("        phoneAnalyzer?.resetTemporalSession()\n", ours)
    text, count = re.subn(r"^<<<<<<<[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n", resolve, text, flags=re.M | re.S)
    assert count == 3
    # Reject stale WORD UI callbacks and bypass WORD-only evidence consumers while
    # the exclusive session owns observations. Default WORD branch is unchanged.
    anchor = "            if (isFinishing || isDestroyed) return@runOnUiThread\n"
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor + """            val spelling = fingerspellRuntime?.snapshot
            if (spelling?.mode == RecognitionMode.FINGERSPELL) {
                frameCount++
                binding.overlayView.setResult(r)
                binding.fpsText.text = getString(R.string.fps_hud, r.fps, r.qualityLabel)
                renderFingerspell(spelling)
                return@runOnUiThread
            }
            if (r.qualityLabel == "FINGERSPELL") return@runOnUiThread
""")
    activity.write_text(text, newline="\n")
    analyzer = DEST / "android/app/src/main/java/com/example/apphear/perceptionvnext/Candidate01FrameAnalyzer.kt"
    analyzer.write_text(analyzer.read_text().replace("recognitionEvidence = update.evidence", "recognitionEvidence = update?.evidence"), newline="\n")
    gradle = DEST / "android/app/build.gradle.kts"
    text = gradle.read_text()
    text = text.replace('    if (fingerspellDebug) {\n', '''    if (fingerspellDebug) {
        val fingerspellArtifacts = providers.gradleProperty("fingerspellArtifactDir")
            .getOrElse("../../artifacts/fingerspelling_android_01")
''')
    text = text.replace('"../../artifacts/fingerspelling_android_01/android_assets"', '"$fingerspellArtifacts/android_assets"')
    text = text.replace('"../../artifacts/fingerspelling_android_01/parity_assets"', '"$fingerspellArtifacts/parity_assets"')
    gradle.write_text(text, newline="\n")
    print("Resolved additive conflicts; preserved nullable WORD evidence and explicit asset location.")

if __name__ == "__main__":
    main()
