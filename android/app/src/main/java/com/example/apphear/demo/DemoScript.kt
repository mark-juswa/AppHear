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
)

data class DemoScenario(val id: String, val title: String, val category: String, val steps: List<DemoStep>)

/** The values the scenarios fill in (name, city, ...), with defaults so a demo runs with no setup. */
object DemoValues {
    val defaults: Map<String, String> = linkedMapOf(
        "name" to "Mark",
        "age" to "21",
        "city" to "Daet",
        "province" to "Camarines Norte",
        "school" to "Camarines Norte State College",
        "school_short" to "CNSC",
        "course" to "Information Technology",
        "year_level" to "third year",
        "occupation" to "student",
        "destination" to "the public market",
        "hearing_name" to "Ana",
    )

    const val MAX_VALUE = 60
    private val PLACEHOLDER = Regex("\\{([a-z_]+)\\}")

    /** Every `{key}` the text uses. */
    fun keysIn(text: String): Set<String> = PLACEHOLDER.findAll(text).map { it.groupValues[1] }.toSet()

    /** Replaces `{key}` with the value (or its default); unknown keys stay visible so a test catches them. */
    fun fill(text: String, values: Map<String, String>): String = PLACEHOLDER.replace(text) { match ->
        val key = match.groupValues[1]
        values[key]?.trim()?.takeIf { it.isNotEmpty() }?.take(MAX_VALUE) ?: defaults[key] ?: match.value
    }

    /**
     * The signer's cue: fills values, then shows fingerspelled words letter by letter
     * (`FS:Mark` -> `M-A-R-K`, `FS:{city}` with city "Naga City" -> `N-A-G-A C-I-T-Y`).
     */
    fun cue(gloss: String, values: Map<String, String>): String =
        gloss.trim().split(Regex("\\s+")).joinToString(" ") { token ->
            if (!token.startsWith("FS:")) fill(token, values)
            else fill(token.removePrefix("FS:"), values).split(Regex("\\s+")).joinToString(" ") { word ->
                word.filter { it.isLetterOrDigit() }.uppercase().toCharArray().joinToString("-")
            }
        }
}
