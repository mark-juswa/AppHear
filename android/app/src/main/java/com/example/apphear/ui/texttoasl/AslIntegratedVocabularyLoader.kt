package com.example.apphear.ui.texttoasl

import android.content.Context
import com.example.apphear.domain.texttoasl.*
import org.json.JSONObject
import java.security.MessageDigest

/** Invoked only inside the existing debug original-human/alphabet path; no new viewer. */
class AslIntegratedVocabularyLoader(private val context: Context) {
    fun load(base: AslAnimationCatalog): AslAnimationCatalog {
        val bytes = context.assets.open(AslIntegratedVocabulary.MANIFEST).use { it.readBytes() }
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        require(hash == AslIntegratedVocabulary.MANIFEST_SHA256)
        val root = JSONObject(String(bytes, Charsets.UTF_8))
        require(root.getInt("schemaVersion") == 1 && root.getString("language") == "ASL")
        require(root.getString("avatarProfile") == "ORIGINAL_HUMAN")
        require(root.getString("asset") == AslFingerspellingBundle.PATH)
        require(root.getString("sha256") == AslFingerspellingBundle.SHA256)
        require(root.getInt("totalLexicalEntries") == AslIntegratedVocabulary.ENTRIES)
        require(root.getInt("qualifiedAslValidations") == 0)
        val raw = root.getJSONArray("entries")
        val words = (0 until raw.length()).map { i -> val e = raw.getJSONObject(i)
            require(e.getString("license") == "CC-BY-4.0" && e.getString("linguisticValidationStatus") == "UNREVIEWED")
            val forms = e.getJSONArray("english")
            AslIntegratedVocabulary.Word(e.getString("id"), (0 until forms.length()).map(forms::getString),
                e.getString("animationName"), e.getLong("durationMs"),
                e.getString("sourceSha256"), e.getString("motionSha256"))
        }
        val rawAliases = root.getJSONArray("aliases")
        val aliases = (0 until rawAliases.length()).map { i -> val e = rawAliases.getJSONObject(i)
            val forms = e.getJSONArray("english")
            AslIntegratedVocabulary.Alias(e.getString("signId"), (0 until forms.length()).map(forms::getString))
        }
        // The caller has already verified the actual combined GLB SHA. No network or fallback avatar.
        return AslIntegratedVocabulary.merge(base, words, aliases)
    }
}
