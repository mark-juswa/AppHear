package com.example.apphear.ui.texttoasl

import android.content.Context
import android.util.Log
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAnimationCatalog
import com.example.apphear.domain.texttoasl.AslTextNormalizer
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/** Optional reviewed additions. Built-in previews retain UNREVIEWED status. */
class AslDictionaryExtensions(private val context: Context) {
    fun load(base: List<AslAnimationAsset>, profile: SignDictionaryMetadata.AvatarProfile): List<AslAnimationAsset> {
        val root = JSONObject(context.assets.open(PATH).bufferedReader().use { it.readText() })
        require(root.getInt("schemaVersion") in 1..2 && root.getString("signLanguage") == "ASL")
        val result = base.toMutableList()
        val entries = root.getJSONArray("entries")
        for (index in 0 until entries.length()) {
            val entry = entries.getJSONObject(index)
            try {
                if (entry.getString("avatarProfile") != profile.name) continue
                require(entry.getString("signLanguage") == "ASL") // FSL needs its own catalog.
                require(entry.getString("format") == "glb") // SiGML needs a separate engine adapter.
                require(entry.getString("validationStatus") == "reviewed")
                require(entry.getString("status") == "LINGUISTICALLY_VALIDATED")
                val source = entry.getString("source").also { require(it.isNotBlank()) }
                val license = entry.getString("license").also { require(it.isNotBlank()) }
                val evidence = entry.getString("reviewEvidence").also { require(it.isNotBlank()) }
                val reviewer = entry.getString("reviewer").also { require(it.isNotBlank()) }
                val reviewedOn = entry.getString("reviewedOn").also { java.time.LocalDate.parse(it) }
                val playbackEvidence = entry.getString("playbackEvidence").also { require(it.isNotBlank()) }
                val meaning = entry.getString("meaning").also { require(it.isNotBlank()) }
                fun strings(key: String): List<String> = entry.optJSONArray(key)?.let { values ->
                    (0 until values.length()).map { values.getString(it) }
                }.orEmpty()
                val gloss = strings("gloss").also { require(it.isNotEmpty() && it.all(String::isNotBlank)) }
                val id = entry.getString("id").also { require(it.matches(Regex("[a-z][a-z0-9_]*"))) }
                val path = entry.getString("asset").also {
                    require(it.matches(Regex("asl_animations/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+\\.glb")))
                }
                val animation = entry.getString("animationName").also { require(it.isNotBlank()) }
                val digest = MessageDigest.getInstance("SHA-256")
                context.assets.open(path).use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) { val n = input.read(buffer); if (n < 0) break; digest.update(buffer, 0, n) }
                }
                val actualHash = digest.digest().joinToString("") { "%02x".format(it) }
                require(actualHash == entry.getString("sha256"))
                context.assets.open(path).use { input ->
                    val header = ByteArray(20)
                    java.io.DataInputStream(input).readFully(header)
                    val ints = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)
                    require(ints.getInt(0) == 0x46546c67 && ints.getInt(4) == 2 && ints.getInt(16) == 0x4e4f534a)
                    val length = ints.getInt(12).also { require(it in 1..4_194_304) }
                    val json = ByteArray(length)
                    java.io.DataInputStream(input).readFully(json)
                    val gltf = JSONObject(String(json, Charsets.UTF_8))
                    val names = gltf.getJSONArray("animations")
                    require((0 until names.length()).any { names.getJSONObject(it).optString("name") == animation })
                }
                val normalizer = AslTextNormalizer()
                val aliases = mutableListOf(normalizer.normalizeSequence(entry.getString("text")))
                entry.optJSONArray("alternativeTextForms")?.let { forms ->
                    for (i in 0 until forms.length()) aliases += normalizer.normalizeSequence(forms.getString(i))
                }
                require(aliases.all { it.isNotBlank() })
                val knownAliases = result.flatMap { it.aliases }.map(normalizer::normalizeSequence).toSet()
                require(aliases.none { it in knownAliases })
                val type = when (entry.getString("type")) {
                    "word" -> AslAnimationAsset.Type.WORD
                    "phrase" -> AslAnimationAsset.Type.PHRASE
                    else -> error("Only reviewed word/phrase additions are allowed")
                }
                val duration = entry.getLong("durationMs").also { require(it in 1..60_000) }
                val asset = AslAnimationAsset(id, entry.getString("text"), path, type, aliases.distinct(),
                    AslAnimationAsset.Replacement(null, animation, duration),
                    SignDictionaryMetadata(SignDictionaryMetadata.Language.ASL,
                        SignDictionaryMetadata.ValidationStatus.REVIEWED, profile,
                        entry.optString("category").takeIf { it.isNotBlank() }, source, license, evidence,
                        status = SignDictionaryMetadata.Status.LINGUISTICALLY_VALIDATED,
                        gloss = gloss, meaning = meaning, usageNotes = entry.optString("usageNotes").takeIf { it.isNotBlank() },
                        lexicalVariant = entry.optString("lexicalVariant").takeIf { it.isNotBlank() },
                        references = strings("references"), embeddedNonManualMarkers = strings("embeddedNonManualMarkers").toSet(),
                        reviewer = reviewer, reviewedOn = reviewedOn, playbackEvidence = playbackEvidence))
                AslAnimationCatalog.fromAssets(result + asset) // Reject ID/alias collisions atomically.
                result += asset
            } catch (error: Exception) {
                Log.w("TextToAslAssets", "Dictionary addition $index rejected: ${error.message}")
            }
        }
        return result
    }
    companion object { const val PATH = "asl_animations/dictionary_extensions_asl.json" }
}
