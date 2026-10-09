package com.example.apphear.data.profile

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import com.example.apphear.domain.profile.AccountException
import com.example.apphear.domain.profile.AccountIssue
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL

object AccountAvatarImages {
    private const val MAX_SOURCE_BYTES = 8 * 1024 * 1024
    private const val MAX_EDGE = 1024

    fun prepare(context: Context, uri: Uri): ByteArray {
        try {
            val bytes = context.contentResolver.openInputStream(uri)?.use { boundedBytes(it, MAX_SOURCE_BYTES) }
                ?: throw AccountException(AccountIssue.AVATAR)
            val bitmap = decode(bytes)
            return try {
                ByteArrayOutputStream().use { out ->
                    if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)) throw AccountException(AccountIssue.AVATAR)
                    out.toByteArray().also { if (it.size > AccountRepository.MAX_AVATAR_BYTES) throw AccountException(AccountIssue.AVATAR) }
                }
            } finally { bitmap.recycle() }
        } catch (_: Exception) { throw AccountException(AccountIssue.AVATAR) }
    }

    fun fetch(url: String, backend: String): Bitmap? {
        if (!url.startsWith(backend.trimEnd('/') + "/storage/v1/object/public/profile-images/")) return null
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10_000
            connection.readTimeout = 15_000
            if (connection.responseCode != 200) throw AccountException(AccountIssue.AVATAR)
            return connection.inputStream.use { decode(boundedBytes(it, MAX_SOURCE_BYTES)) }
        } catch (_: Exception) { throw AccountException(AccountIssue.AVATAR) }
        finally { connection.disconnect() }
    }

    private fun decode(bytes: ByteArray): Bitmap {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        if (options.outWidth <= 0 || options.outHeight <= 0) throw AccountException(AccountIssue.AVATAR)
        options.inJustDecodeBounds = false
        options.inSampleSize = 1
        while (maxOf(options.outWidth, options.outHeight) / options.inSampleSize > MAX_EDGE) options.inSampleSize *= 2
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options) ?: throw AccountException(AccountIssue.AVATAR)
    }

    fun boundedBytes(input: java.io.InputStream, limit: Int): ByteArray {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            if (output.size() + count > limit) throw AccountException(AccountIssue.AVATAR)
            output.write(buffer, 0, count)
        }
        return output.toByteArray()
    }
}
