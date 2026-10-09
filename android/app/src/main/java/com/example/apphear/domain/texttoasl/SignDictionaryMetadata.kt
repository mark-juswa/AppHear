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
) {
    enum class Language { ASL, FSL }
    enum class ValidationStatus { UNREVIEWED, REVIEWED }
    enum class AvatarProfile { LEGACY, ORIGINAL_HUMAN, NEW_HUMAN }
}
