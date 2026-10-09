package com.example.apphear.ui.texttoasl

import android.content.Context
import android.util.Log
import com.example.apphear.BuildConfig
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.OriginalWordBatchCatalog
import com.example.apphear.domain.texttoasl.AslAvatarCatalogPolicy
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import com.example.apphear.domain.texttoasl.AslResidentAvatarBundle
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.Locale
import java.security.MessageDigest

class AndroidAssetAslCatalogLoader(
    private val context: Context,
    private val useNewCharacter: Boolean = true,
) {
    fun load(): AslAnimationCatalog {
        val manifest = readAssetText(MANIFEST_PATH)
        val root = JSONObject(manifest)
        val clips = root.getJSONArray("clips")
        val assets = buildList {
            for (index in 0 until clips.length()) {
                val clip = clips.getJSONObject(index)
                val assetPath = clip.getString("asset")
                validateAssetExists(assetPath)
                val aliases = clip.getJSONArray("aliases")
                add(
                    AslAnimationAsset(
                        id = clip.getString("id"),
                        displayText = clip.getString("displayText"),
                        assetPath = assetPath,
                        type = parseType(clip.getString("type")),
                        aliases = buildList {
                            for (aliasIndex in 0 until aliases.length()) {
                                add(aliases.getString(aliasIndex))
                            }
                        },
                    ),
                )
            }
        }
        val selected = if (BuildConfig.ASL_ORIGINAL_WORDS_ENABLED && !useNewCharacter) {
            PilotCatalog(applyOriginalWordBatch(assets))
        } else if (BuildConfig.ASL_ASSET_PILOT_ENABLED && useNewCharacter) {
            applyPilot(assets)
        } else {
            PilotCatalog(assets)
        }
        if (!BuildConfig.ASL_ASSET_PILOT_ENABLED) return AslAnimationCatalog.fromAssets(selected.assets, selected.letters)
        val compatible = if (useNewCharacter) AslAvatarCatalogPolicy.newHuman(selected.assets)
            else AslAvatarCatalogPolicy.originalHuman(selected.assets)
        val profile = if (useNewCharacter) SignDictionaryMetadata.AvatarProfile.NEW_HUMAN
            else SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN
        val letters = selected.letters.mapValues { (_, asset) -> asset.copy(
            metadata = asset.metadata.copy(avatarProfile = profile,
                source = "asl_animations/vnext/manifest.json")) }
        // Catalog errors fail visibly; they must never silently change character.
        val expanded = AslDictionaryExtensions(context).load(compatible, profile)
        val resident = if (profile == SignDictionaryMetadata.AvatarProfile.ORIGINAL_HUMAN) loadResidentBundle(expanded) else expanded
        return AslAnimationCatalog.fromAssets(resident, letters)
    }

    private fun loadResidentBundle(base: List<AslAnimationAsset>): List<AslAnimationAsset> {
        val root = JSONObject(readAssetText(AslResidentAvatarBundle.MANIFEST))
        require(root.getInt("schemaVersion") == 1 && root.getString("language") == "ASL" &&
            root.getString("avatarProfile") == "ORIGINAL_HUMAN" && root.getString("asset") == AslResidentAvatarBundle.PATH)
        require(root.getString("sha256") == AslResidentAvatarBundle.SHA256)
        val digest = MessageDigest.getInstance("SHA-256")
        context.assets.open(AslResidentAvatarBundle.PATH).use { input ->
            val bytes = ByteArray(64 * 1024)
            while (true) { val n = input.read(bytes); if (n < 0) break; digest.update(bytes, 0, n) }
        }
        require(digest.digest().joinToString("") { "%02x".format(it) } == AslResidentAvatarBundle.SHA256)
        val entries = root.getJSONArray("animations")
        val motions = (0 until entries.length()).map {
            val e = entries.getJSONObject(it)
            AslResidentAvatarBundle.Motion(e.getString("id"), e.getString("animationName"),
                e.getLong("durationMs"), e.getString("sourceAsset"))
        }
        // Missing/corrupt bundle fails visibly; never switch to individual legacy models.
        return AslResidentAvatarBundle.map(base, motions)
    }

    private data class PilotCatalog(
        val assets: List<AslAnimationAsset>,
        val letters: Map<Char, AslAnimationAsset> = emptyMap(),
    )

    private fun applyPilot(assets: List<AslAnimationAsset>): PilotCatalog {
        val root = try {
            val root = JSONObject(readAssetText("asl_animations/vnext/manifest.json"))
            require(root.getInt("schemaVersion") == when {
                BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED -> 3
                BuildConfig.ASL_MORE_WORDS_ENABLED -> 2
                else -> 1
            })
            root.getJSONArray("clips")
            root
        } catch (exception: Exception) {
            Log.w("TextToAslAssets", "Pilot manifest unavailable; using original catalog", exception)
            return PilotCatalog(assets)
        }
        val overrides = root.getJSONArray("clips")
        val verifiedHashes = mutableMapOf<String, String>()
        fun verifiedHash(path: String): String = verifiedHashes.getOrPut(path) {
            val digest = MessageDigest.getInstance("SHA-256")
            context.assets.open(path).use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    digest.update(buffer, 0, count)
                }
            }
            digest.digest().joinToString("") { "%02x".format(it) }
        }
        val expectedPath = when {
            BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED -> AslAlphabetPilotContract.ASSET
            BuildConfig.ASL_NEW_IDLE_ENABLED -> AslIdlePilotContract.ASSET
            BuildConfig.ASL_MORE_WORDS_ENABLED -> "asl_animations/vnext/shared-words.glb"
            BuildConfig.ASL_SHARED_CHARACTER_ENABLED -> "asl_animations/vnext/shared-character.glb"
            else -> null
        }
        val expectedProfile = when {
            BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED -> AslAlphabetPilotContract.PROFILE
            BuildConfig.ASL_NEW_IDLE_ENABLED -> AslIdlePilotContract.PROFILE
            BuildConfig.ASL_MORE_WORDS_ENABLED -> "balanced-ktx2mixed-meshopt-shared-words-v1"
            BuildConfig.ASL_SHARED_CHARACTER_ENABLED -> "balanced-ktx2mixed-meshopt-shared-v1"
            else -> "balanced-ktx2mixed-meshopt-v1"
        }
        val replaced = assets.map { original ->
            try {
                if (original.id == "idle" && BuildConfig.ASL_NEW_IDLE_ENABLED) {
                    val idle = root.optJSONObject("idle") ?: return@map original
                    val path = idle.getString("asset")
                    // Check the allowed path before opening an untrusted manifest path.
                    require(path == expectedPath)
                    AslIdlePilotContract.validate(
                        enabled = BuildConfig.ASL_NEW_IDLE_ENABLED,
                        original = original,
                        id = idle.getString("id"), sourceId = idle.getString("sourceId"),
                        type = idle.getString("type"), asset = path,
                        profile = idle.getString("profile"), rigProfile = idle.getString("rigProfile"),
                        animation = idle.getString("animationName"), durationMs = idle.getLong("durationMs"),
                        fallbackAsset = idle.getString("fallbackAsset"), declaredHash = idle.getString("sha256"),
                        actualHash = verifiedHash(path),
                        alphabetVariant = BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED,
                    )
                    return@map original.copy(
                        assetPath = path,
                        replacement = AslAnimationAsset.Replacement(
                            original.assetPath, AslIdlePilotContract.ANIMATION, 6_000L,
                        ),
                    )
                }
                val matches = (0 until overrides.length()).map { overrides.getJSONObject(it) }
                    .filter { it.getString("id") == original.id }
                if (matches.isEmpty()) return@map original
                require(matches.size == 1)
                val clip = matches.single()
                require(original.type in setOf(AslAnimationAsset.Type.LETTER, AslAnimationAsset.Type.WORD))
                require(clip.getString("sourceId") == original.id.uppercase(Locale.US))
                val path = clip.getString("asset")
                val name = clip.getString("animationName")
                val duration = clip.getLong("durationMs")
                require(path == (expectedPath ?: "asl_animations/vnext/${original.id}.glb"))
                require(clip.getString("fallbackAsset") == original.assetPath)
                require(clip.getString("profile") == expectedProfile)
                require(clip.getString("rigProfile") == "FemaleASL-full-rig-341-875-342")
                require(name.isNotBlank() && duration in 1..10_000)
                require(verifiedHash(path) == clip.getString("sha256"))
                original.copy(
                    assetPath = path,
                    replacement = AslAnimationAsset.Replacement(original.assetPath, name, duration),
                )
            } catch (exception: Exception) {
                Log.w("TextToAslAssets", "Pilot ${original.id} rejected; using original", exception)
                original
            }
        }
        if (!BuildConfig.ASL_MORE_WORDS_ENABLED) return PilotCatalog(replaced)
        val newClips = try {
            root.getJSONArray("newClips").also { require(it.length() == APPROVED_NEW_WORDS.size) }
        } catch (exception: Exception) {
            Log.w("TextToAslAssets", "New-word manifest rejected; using original catalog", exception)
            return PilotCatalog(assets)
        }
        val added = buildList {
            for (index in 0 until newClips.length()) {
                try {
                    val clip = newClips.getJSONObject(index)
                    val id = clip.getString("id")
                    val approved = APPROVED_NEW_WORDS[id] ?: error("Unapproved word: $id")
                    require(clip.getString("sourceId") == approved.first)
                    val aliases = clip.getJSONArray("aliases")
                    require(aliases.length() == 1 && aliases.getString(0) == approved.second)
                    require(clip.getString("type") == "word")
                    val path = clip.getString("asset")
                    require(path == expectedPath && clip.getString("profile") == expectedProfile)
                    require(clip.getString("rigProfile") == "FemaleASL-full-rig-341-875-342")
                    require(verifiedHash(path) == clip.getString("sha256"))
                    val name = clip.getString("animationName")
                    require(name == "SIGN_${approved.first}_FEMALEASL")
                    val duration = clip.getLong("durationMs")
                    require(duration in 1..10_000)
                    add(AslAnimationAsset(
                        id = id,
                        displayText = clip.getString("displayText"),
                        assetPath = path,
                        type = AslAnimationAsset.Type.WORD,
                        aliases = listOf(approved.second),
                        replacement = AslAnimationAsset.Replacement(null, name, duration),
                    ))
                } catch (exception: Exception) {
                    Log.w("TextToAslAssets", "New pilot word rejected at index $index", exception)
                }
            }
        }
        if (!BuildConfig.ASL_ALPHABET_FALLBACK_ENABLED) return PilotCatalog(replaced + added)
        return try {
            require(added.size == APPROVED_NEW_WORDS.size)
            val letters = root.getJSONArray("letters")
            require(letters.length() == 24)
            val mapped = buildMap {
                for (index in 0 until letters.length()) {
                    val clip = letters.getJSONObject(index)
                    val letter = ('c' + index)
                    val path = clip.getString("asset")
                    AslAlphabetPilotContract.validateLetter(
                        letter = letter,
                        id = clip.getString("id"),
                        sourceId = clip.getString("sourceId"),
                        type = clip.getString("type"),
                        path = path,
                        profile = clip.getString("profile"),
                        rigProfile = clip.getString("rigProfile"),
                        animation = clip.getString("animationName"),
                        durationMs = clip.getLong("durationMs"),
                        declaredHash = clip.getString("sha256"),
                        actualHash = verifiedHash(path),
                    )
                    require(clip.getString("displayText") == letter.uppercaseChar().toString())
                    put(letter, AslAnimationAsset(
                        id = clip.getString("id"),
                        displayText = letter.uppercaseChar().toString(),
                        assetPath = path,
                        type = AslAnimationAsset.Type.LETTER,
                        aliases = emptyList(),
                        replacement = AslAnimationAsset.Replacement(null, clip.getString("animationName"),
                            clip.getLong("durationMs")),
                    ))
                }
            }
            PilotCatalog(replaced + added, mapped)
        } catch (exception: Exception) {
            Log.w("TextToAslAssets", "Alphabet manifest rejected; using original catalog", exception)
            PilotCatalog(assets)
        }
    }

    private fun applyOriginalWordBatch(base: List<AslAnimationAsset>): List<AslAnimationAsset> {
        return try {
            val bytes = context.assets.open(OriginalWordBatchCatalog.MANIFEST).use { it.readBytes() }
            fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
                .joinToString("") { "%02x".format(it) }
            require(hash(bytes) == OriginalWordBatchCatalog.MANIFEST_SHA256)
            val root = JSONObject(String(bytes, Charsets.UTF_8))
            require(root.getInt("schemaVersion") == 1 && root.getString("packageId") == "original-word-batch-v1")
            require(root.getBoolean("standExcluded"))
            fun verify(clip: JSONObject) {
                val path = clip.getString("asset")
                OriginalWordBatchCatalog.validatePath(path)
                val digest = MessageDigest.getInstance("SHA-256")
                var total = 0L
                context.assets.open(path).use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        digest.update(buffer, 0, count)
                        total += count
                    }
                }
                require(total == clip.getLong("bytes"))
                require(digest.digest().joinToString("") { "%02x".format(it) } == clip.getString("sha256"))
            }
            val rawOverrides = root.getJSONArray("replacements")
            val rawAdditions = root.getJSONArray("newClips")
            require(rawOverrides.length() == OriginalWordBatchCatalog.REPLACEMENTS)
            require(rawAdditions.length() == OriginalWordBatchCatalog.ADDITIONS)
            val overrides = (0 until rawOverrides.length()).map { index ->
                val clip = rawOverrides.getJSONObject(index)
                verify(clip)
                OriginalWordBatchCatalog.Override(clip.getString("id"), clip.getString("asset"),
                    clip.getString("fallbackAsset"), clip.getString("animationName"), clip.getLong("durationMs"))
            }
            val additions = (0 until rawAdditions.length()).map { index ->
                val clip = rawAdditions.getJSONObject(index)
                verify(clip)
                require(clip.getString("type") == "word")
                val aliases = clip.getJSONArray("aliases")
                AslAnimationAsset(clip.getString("id"), clip.getString("displayText"),
                    clip.getString("asset"), AslAnimationAsset.Type.WORD,
                    (0 until aliases.length()).map { aliases.getString(it) },
                    AslAnimationAsset.Replacement(null, clip.getString("animationName"), clip.getLong("durationMs")))
            }
            OriginalWordBatchCatalog.merge(base, overrides, additions)
        } catch (exception: Exception) {
            Log.w("TextToAslAssets", "Original word batch rejected; using frozen Original catalog", exception)
            base
        }
    }

    private fun readAssetText(path: String): String {
        return context.assets.open(path).use { input ->
            BufferedReader(InputStreamReader(input)).use { reader ->
                reader.readText()
            }
        }
    }

    private fun validateAssetExists(path: String) {
        context.assets.open(path).use { }
    }

    private fun parseType(rawType: String): AslAnimationAsset.Type {
        return when (rawType.lowercase(Locale.US)) {
            "phrase" -> AslAnimationAsset.Type.PHRASE
            "word" -> AslAnimationAsset.Type.WORD
            "letter" -> AslAnimationAsset.Type.LETTER
            "pose" -> AslAnimationAsset.Type.POSE
            else -> AslAnimationAsset.Type.PHRASE
        }
    }

    private companion object {
        const val MANIFEST_PATH = "asl_animations/manifest.json"
        val APPROVED_NEW_WORDS = mapOf(
            "afternoon" to ("AFTERNOON" to "afternoon"),
            "any" to ("ANY" to "any"),
            "ask" to ("ASK" to "ask"),
            "baby" to ("BABY" to "baby"),
            "bag" to ("BAG" to "bag"),
            "be" to ("BE" to "be"),
            "beautiful" to ("BEAUTIFUL" to "beautiful"),
            "become" to ("BECOME" to "become"),
            "begin" to ("BEGIN" to "begin"),
            "big_horizontally" to ("BIG_AS_IN_LARGE_OR_BIG_HORIZONTALLY" to "big horizontally"),
            "boss" to ("BOSS" to "boss"),
            "busy" to ("BUSY" to "busy"),
            "bye" to ("BYE" to "bye"),
            "call_by_phone" to ("CALL_CALL_BY_PHONE" to "call by phone"),
            "call_someones_name" to ("CALL_TO_CALL_SOMEONE_S_NAME" to "call someones name"),
            "car" to ("CAR" to "car"),
            "cold" to ("COLD" to "cold"),
            "come" to ("COME" to "come"),
            "fast" to ("FAST" to "fast"),
            "pay_me" to ("PAY_TO_PAY_ME" to "pay me"),
        )
    }
}
