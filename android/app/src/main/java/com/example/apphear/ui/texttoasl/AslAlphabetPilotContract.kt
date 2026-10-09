package com.example.apphear.ui.texttoasl

/** Only C-Z in the exact shared alphabet derivative may supply fallback letters. */
internal object AslAlphabetPilotContract {
    const val ASSET = "asl_animations/vnext/shared-alphabet.glb"
    const val PROFILE = "balanced-ktx2mixed-meshopt-shared-alphabet-v1"

    fun validateLetter(
        letter: Char,
        id: String,
        sourceId: String,
        type: String,
        path: String,
        profile: String,
        rigProfile: String,
        animation: String,
        durationMs: Long,
        declaredHash: String,
        actualHash: String,
    ) {
        require(letter in 'c'..'z')
        require(id == "letter_$letter" && sourceId == letter.uppercaseChar().toString())
        require(type == "letter" && path == ASSET && profile == PROFILE)
        require(rigProfile == "FemaleASL-full-rig-341-875-342")
        require(animation == "SIGN_LETTER_${sourceId}_FEMALEASL")
        require(durationMs in 1..10_000)
        require(declaredHash.matches(Regex("[0-9a-f]{64}")) && declaredHash == actualHash)
    }
}
