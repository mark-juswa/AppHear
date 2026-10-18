package com.example.apphear.domain.texttoasl

/** Same-rig motion packaging only. Original clips remain available for rollback/review. */
object AslResidentAvatarBundle {
    const val PATH = "asl_animations/original_words_v1/resident-avatar.glb"
    const val MANIFEST = "asl_animations/original_words_v1/resident-avatar.json"
    const val SHA256 = "4af1e10c9448d33db03cede4705dd2e7f851f12bb8394669b77d847bf885d3bf"

    data class Motion(val id: String, val animationName: String, val durationMs: Long, val sourceAsset: String)

    fun map(base: List<AslAnimationAsset>, motions: List<Motion>): List<AslAnimationAsset> {
        require(motions.size == 203 && motions.map { it.id }.distinct().size == motions.size)
        require(motions.map { it.animationName }.distinct().size == motions.size)
        val byId = motions.associateBy { it.id }
        return base.map { asset ->
            require(AslSingleAvatarPolicy.permits(asset))
            val motion = requireNotNull(byId[if (asset.type == AslAnimationAsset.Type.POSE) "hello" else asset.id])
            val replacement = requireNotNull(asset.replacement)
            require(asset.assetPath == motion.sourceAsset && replacement.animationName == motion.animationName)
            require(replacement.durationMs == motion.durationMs && motion.durationMs in 1..10_000)
            asset.copy(assetPath = PATH, replacement = AslAnimationAsset.Replacement(null, motion.animationName, motion.durationMs))
        }
    }
}
