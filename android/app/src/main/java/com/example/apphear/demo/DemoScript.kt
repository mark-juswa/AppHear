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

/**
 * The values the scenarios fill in (name, city, ...). Nothing is built in: every value comes from the
 * script details window, and an empty one shows as `[name]` so it is easy to spot.
 */
object DemoValues {
    /** Every value a scenario may use, in the order the script details window lists them. */
    val keys: List<String> = listOf(
        "name", "age", "city", "province", "school", "school_short", "course", "year_level", "occupation",
        "destination", "hearing_name",
    )

    const val MAX_VALUE = 60
    private val PLACEHOLDER = Regex("\\{([a-z_]+)\\}")

    /** Every `{key}` the text uses. */
    fun keysIn(text: String): Set<String> = PLACEHOLDER.findAll(text).map { it.groupValues[1] }.toSet()

    /** Replaces `{key}` with its value; an empty value shows as `[key]`, an unknown key stays as `{key}`. */
    fun fill(text: String, values: Map<String, String>): String = PLACEHOLDER.replace(text) { match ->
        val key = match.groupValues[1]
        values[key]?.trim()?.takeIf { it.isNotEmpty() }?.take(MAX_VALUE)
            ?: if (key in keys) "[$key]" else match.value
    }

    /**
     * The signer's cue: fills values, then shows fingerspelled words letter by letter
     * (`FS:Juan` -> `J-U-A-N`, `FS:{city}` with city "Naga City" -> `N-A-G-A C-I-T-Y`).
     */
    fun cue(gloss: String, values: Map<String, String>): String =
        gloss.trim().split(Regex("\\s+")).joinToString(" ") { token ->
            val filled = fill(token.removePrefix("FS:"), values)
            if (!token.startsWith("FS:") || filled.startsWith("[")) filled
            else filled.split(Regex("\\s+")).joinToString(" ") { word ->
                word.filter { it.isLetterOrDigit() }.uppercase().toCharArray().joinToString("-")
            }
        }
}
