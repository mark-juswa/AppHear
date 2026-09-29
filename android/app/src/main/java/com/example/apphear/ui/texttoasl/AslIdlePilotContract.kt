package com.example.apphear.ui.texttoasl

import com.example.apphear.domain.texttoasl.AslAnimationAsset

/** The sole permitted pose replacement; unrelated poses cannot opt into the pilot. */
internal object AslIdlePilotContract {
    const val ASSET = "asl_animations/vnext/shared-words-idle.glb"
    const val PROFILE = "balanced-ktx2mixed-meshopt-shared-idle-v1"
    const val ANIMATION = "IDLE_NEUTRAL_FEMALEASL"

    fun validate(
        enabled: Boolean,
        original: AslAnimationAsset,
        id: String,
        sourceId: String,
        type: String,
        asset: String,
        profile: String,
        rigProfile: String,
        animation: String,
        durationMs: Long,
        fallbackAsset: String,
        declaredHash: String,
        actualHash: String,
        alphabetVariant: Boolean = false,
    ) {
        require(enabled)
        require(original.id == "idle" && original.type == AslAnimationAsset.Type.POSE)
        require(original.assetPath == "asl_animations/asl_idle.glb")
        require(id == "idle" && sourceId == "IDLE" && type == "pose")
        require(asset == (if (alphabetVariant) AslAlphabetPilotContract.ASSET else ASSET))
        require(profile == (if (alphabetVariant) AslAlphabetPilotContract.PROFILE else PROFILE))
        require(rigProfile == "FemaleASL-full-rig-341-875-342")
        require(animation == ANIMATION && durationMs == 6_000L)
        require(fallbackAsset == original.assetPath)
        require(declaredHash.matches(Regex("[0-9a-f]{64}")) && declaredHash == actualHash)
    }
}
