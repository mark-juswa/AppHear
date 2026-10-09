package com.example.apphear.domain.texttoasl

/** Engineering hash checks do not constitute linguistic or licensing review. */
data class SignDictionaryMetadata(
    val language: Language = Language.ASL,
    val validationStatus: ValidationStatus = ValidationStatus.UNREVIEWED,
    val avatarProfile: AvatarProfile = AvatarProfile.LEGACY,
    val category: String? = null,
    val source: String? = null,
    val license: String? = null,
    val reviewEvidence: String? = null,
    val status: Status = Status.MAPPED,
    val gloss: List<String> = emptyList(),
    val meaning: String? = null,
    val usageNotes: String? = null,
    val lexicalVariant: String? = null,
    val references: List<String> = emptyList(),
    val embeddedNonManualMarkers: Set<String> = emptySet(),
    val reviewer: String? = null,
    val reviewedOn: String? = null,
    val playbackEvidence: String? = null,
) {
    // Neither dataset presence nor a file checksum is sufficient for this predicate.
    val isLinguisticallyValidated: Boolean get() = status == Status.LINGUISTICALLY_VALIDATED &&
        validationStatus == ValidationStatus.REVIEWED && language == Language.ASL &&
        listOf(source, license, reviewEvidence, meaning, reviewer, playbackEvidence).all { !it.isNullOrBlank() } &&
        runCatching { java.time.LocalDate.parse(reviewedOn) }.isSuccess && gloss.isNotEmpty() && gloss.all { it.isNotBlank() }
    enum class Status { CANDIDATE, MAPPED, PLAYABLE, LINGUISTICALLY_VALIDATED, UNSUPPORTED }
    enum class Language { ASL, FSL }
    enum class ValidationStatus { UNREVIEWED, REVIEWED }
    enum class AvatarProfile { LEGACY, ORIGINAL_HUMAN, NEW_HUMAN }
}
