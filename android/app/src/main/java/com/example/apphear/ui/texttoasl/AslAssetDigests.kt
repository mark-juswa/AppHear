package com.example.apphear.ui.texttoasl

import android.content.Context
import android.os.Build
import java.security.MessageDigest
import java.util.concurrent.ConcurrentHashMap

/**
 * SHA-256 of packaged Text-to-ASL assets, computed once per installed APK.
 * Packaged assets cannot change without a reinstall, and a reinstall changes the install key,
 * so every integrity check still runs against the bytes of the current install.
 */
object AslAssetDigests {
    data class Digest(val sha256: String, val bytes: Long)

    private const val PREFS = "text_to_asl_asset_digests"
    private const val INSTALL_KEY = "install"
    private val memory = ConcurrentHashMap<String, Digest>()
    @Volatile private var memoryInstall: String? = null

    fun of(context: Context, path: String): Digest {
        val install = installKey(context)
        if (memoryInstall != install) {
            memory.clear()
            memoryInstall = install
        }
        memory[path]?.let { return it }
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(INSTALL_KEY, null) != install) {
            prefs.edit().clear().putString(INSTALL_KEY, install).apply()
        }
        val stored = prefs.getString(path, null)?.split('|')
            ?.takeIf { it.size == 2 && it[0].matches(Regex("[0-9a-f]{64}")) }
            ?.let { Digest(it[0], it[1].toLong()) }
        val digest = stored ?: compute(context, path).also {
            prefs.edit().putString(path, "${it.sha256}|${it.bytes}").apply()
        }
        memory[path] = digest
        return digest
    }

    private fun compute(context: Context, path: String): Digest {
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
        return Digest(digest.digest().joinToString("") { "%02x".format(it) }, total)
    }

    @Suppress("DEPRECATION")
    private fun installKey(context: Context): String {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        val version = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.longVersionCode else info.versionCode.toLong()
        return "${info.lastUpdateTime}:$version"
    }
}
