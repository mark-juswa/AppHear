package com.example.apphear.demo

/**
 * Guided conversation demo (guidedDemo flag): a prepared conversation the Recognition screen plays
 * through. The script, never the recognizer, decides every message. Pure Kotlin, unit-tested.
 * Scenarios live in `assets/guided_demo/scenarios_v1.json`.
 */
enum class DemoSpeaker { HEARING, SIGNER }

data class DemoStep(
    val speaker: DemoSpeaker,
    /** English sentence: shown and spoken for the signer, shown as the reply for the hearing person. */
    val text: String,
    /** Signer steps: what the signer is cued to sign (draft gloss; `FS:` marks fingerspelling). */
    val gloss: String? = null,
    /** Hearing steps: a simpler wording for the avatar when [text] has words it cannot sign. */
    val avatar: String? = null,
    /** Question-based demo, hearing step: any question may be asked (no scripted line). */
    val open: Boolean = false,
    /** Signer step whose `{spelled}` part is the fingerspelling model's reading (a name or place). */
    val spell: Boolean = false,
)

data class DemoScenario(val id: String, val title: String, val category: String, val steps: List<DemoStep>)

/** Draft glosses as the signer's individual signs; `FS:WORD` is shown letter by letter. */
object DemoGloss {
    const val SPELLED = "{spelled}"

    fun signs(gloss: String): List<String> = gloss.trim().split(Regex("\\s+")).filter { it.isNotBlank() }.map { token ->
        if (!token.startsWith("FS:")) token
        else token.removePrefix("FS:").filter { it.isLetterOrDigit() }.uppercase().toCharArray().joinToString("-")
    }
}
