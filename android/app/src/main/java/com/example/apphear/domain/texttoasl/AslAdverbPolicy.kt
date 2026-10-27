package com.example.apphear.domain.texttoasl

/** English meaning inventory, not a dictionary of certified ASL translations.
 * Missing lexical motions retain whole-word fingerspelling. References describe
 * concepts only: their videos/illustrations are not bundled animation assets.
 */
object AslAdverbPolicy {
    enum class Category { TIME, FREQUENCY, MANNER, DEGREE, PLACE, CERTAINTY, POSSIBILITY, FOCUS }

    data class Entry(
        val english: String,
        val category: Category,
        val meaning: String,
        val reference: String,
        val previewSignId: String? = null,
        val limitation: String,
    )

    private fun entry(word: String, category: Category, meaning: String, page: String = word,
                      sign: String? = null, limitation: String) = Entry(word, category, meaning,
        "https://www.lifeprint.com/asl101/pages-signs/${page.first()}/$page.htm", sign, limitation)

    val entries = listOf(
        entry("just", Category.FOCUS, "Only/merely, recently, or exactly; context selects the sense",
            limitation = "Do not substitute SINGLE for recent completion or exactness"),
        entry("already", Category.TIME, "Completion before the relevant time",
            limitation = "FINISH is not an unconditional substitute; temporal scope needs review"),
        entry("still", Category.TIME, "Continuation; also immobility or contrast in other contexts",
            limitation = "Continuative Y-hand motion is missing; STAY is not an automatic substitute"),
        entry("always", Category.FREQUENCY, "At all relevant times",
            limitation = "Large elbow-driven index circle; do not reuse the small SINGLE circle"),
        entry("never", Category.FREQUENCY, "At no relevant time; negation must be preserved",
            limitation = "Dedicated downward flat-hand path and negative expression need review"),
        entry("sometimes", Category.FREQUENCY, "Occasionally",
            limitation = "Specific narrow oval motion is missing; not interchangeable with OFTEN"),
        entry("often", Category.FREQUENCY, "Frequently",
            limitation = "Repeated bent-hand contact with base palm is missing"),
        entry("only", Category.FOCUS, "Restriction to the focused person, object, action or quantity",
            limitation = "Scope is unresolved; do not apply the existing SINGLE variant indiscriminately"),
        entry("even", Category.FOCUS, "Unexpected inclusion; also level/equal in other contexts",
            limitation = "No reviewed scalar-focus translation; the reference page could not be decoded"),
        entry("maybe", Category.POSSIBILITY, "An uncertain possibility",
            limitation = "Alternating palms-up motion and appropriate facial expression are missing"),
        entry("probably", Category.CERTAINTY, "Likely, with less than complete certainty", page = "maybe",
            limitation = "Research candidate only; MAYBE does not establish the same degree of likelihood"),
        entry("really", Category.DEGREE, "Intensification, truth assertion, or a surprised question",
            limitation = "Do not automatically substitute SURE, NEED or TRUE across senses"),
        entry("very", Category.DEGREE, "A high degree of the modified property",
            limitation = "Often expressed through inflection/non-manuals; do not silently remove it"),
        entry("quickly", Category.MANNER, "At high speed; promptness is a separate contextual reading",
            page = "fast", sign = "fast",
            limitation = "Existing FAST speed-sense preview only; no automatic temporal/aspect translation"),
        entry("slowly", Category.MANNER, "At low speed", page = "slow", sign = "slow",
            limitation = "Existing SLOW speed-sense preview only; do not change animation playback speed"),
        entry("here", Category.PLACE, "At this location", sign = "here",
            limitation = "Existing HERE preview; discourse location still needs ASL review"),
        entry("there", Category.PLACE, "At a referenced location; existential THERE is a different construction",
            limitation = "No resolved spatial locus; do not substitute second-person YOU"),
        entry("now", Category.TIME, "At the present time", sign = "now",
            limitation = "Existing NOW preview; discourse use such as 'now then' needs review"),
        entry("later", Category.TIME, "After the relevant time",
            limitation = "No dedicated L-hand motion; do not substitute LATE or TOMORROW"),
    )
    private val byEnglish = entries.associateBy { it.english }

    fun presentIn(normalized: String): List<Entry> = normalized.split(' ').mapNotNull(byEnglish::get).distinct()

    fun speedReplacements(normalized: String, catalog: AslAnimationCatalog): Map<Int, String> = buildMap {
        normalized.split(' ').forEachIndexed { index, token ->
            // These are input alternatives to existing motions, never new signs.
            // Other adverbs stay in the ordinary dictionary/fingerspelling path.
            if ((token == "quickly" || token == "slowly") && catalog.findByAlias(token) == null) {
                val id = byEnglish.getValue(token).previewSignId!!
                val asset = catalog.getAssets().singleOrNull { it.id == id }
                if (asset != null && asset.type == AslAnimationAsset.Type.WORD &&
                    asset.replacement != null && AslSingleAvatarPolicy.permits(asset)) put(index, id)
            }
        }
    }

    fun annotate(plan: TextToAslPlan): TextToAslPlan {
        val adverbs = presentIn(plan.normalizedText)
        if (adverbs.isEmpty() || plan.mode == TextToAslPlan.Mode.VALIDATED_PHRASE ||
            plan.mode == TextToAslPlan.Mode.BLOCKED_MEANING) return plan
        val speed = adverbs.filter { it.english in setOf("quickly", "slowly") &&
            it.english !in plan.fingerspelledWords && plan.queue.any { asset -> asset.id == it.previewSignId } }
            .joinToString(", ") { "${it.english}=${it.previewSignId!!.uppercase(java.util.Locale.US)} (speed sense)" }
        return plan.copy(translationNotice = listOfNotNull(
            plan.translationNotice,
            speed.takeIf(String::isNotEmpty)?.let { "Preview: $it" },
            "Adverb meaning, scope and non-manual features require ASL review; not a validated ASL sentence",
        ).joinToString("; "))
    }
}
