package com.example.apphear.domain.texttoasl

/** English meaning inventory, not an executable ASL translation or a signing order. */
data class EverydayAslExpression(
    val id: String,
    val english: List<String>,
    val meaning: String,
    val requiredSigns: List<RequiredSign>,
    val references: List<String>,
    val nonManualReview: String,
    val previewSignId: String? = null,
    val namePrefixes: List<String> = emptyList(),
) {
    data class RequiredSign(val concept: String, val aliases: List<String>)

    companion object {
        /** Reject ambiguity before requests reach the playback engine. */
        fun validate(entries: List<EverydayAslExpression>, normalizer: AslTextNormalizer) {
            require(entries.map { it.id }.distinct().size == entries.size)
            val forms = mutableSetOf<String>()
            val prefixes = mutableSetOf<String>()
            for (entry in entries) {
                require(entry.id.matches(Regex("[a-z][a-z0-9_]*")) && entry.meaning.isNotBlank())
                require(entry.english.isNotEmpty() && entry.requiredSigns.isNotEmpty())
                require(entry.references.isNotEmpty() && entry.references.all { it.startsWith("https://") })
                require(entry.nonManualReview.isNotBlank())
                for (form in entry.english) {
                    val normalized = normalizer.normalizeSequence(form)
                    require(normalized.isNotBlank() && forms.add(normalized)) { "Ambiguous everyday expression" }
                }
                for (prefix in entry.namePrefixes) {
                    val normalized = normalizer.normalizeSequence(prefix)
                    require(normalized.isNotBlank() && prefixes.add(normalized))
                }
                require(entry.requiredSigns.all { it.concept.isNotBlank() && it.aliases.isNotEmpty() &&
                    it.aliases.all { alias -> normalizer.normalizeSequence(alias).isNotBlank() } })
                // A single complete dictionary clip may be previewed. Sentences never use this shortcut.
                require(entry.previewSignId == null || (entry.requiredSigns.size == 1 && entry.namePrefixes.isEmpty()))
            }
            require(prefixes.none { a -> prefixes.any { b -> a != b && a.startsWith("$b ") } })
            require(entries.none { entry -> entry.english.any { form ->
                val normalized = normalizer.normalizeSequence(form)
                entries.any { other -> other.id != entry.id && other.namePrefixes.any { prefix ->
                    val p = normalizer.normalizeSequence(prefix)
                    normalized == p || normalized.startsWith("$p ")
                } }
            } })
        }
    }
}
