package com.example.apphear.remote

import java.net.URI

/**
 * Invite links and join codes for a remote conversation (remoteConversation flag).
 *
 * A QR holds `apphear://join?c=CODE&s=SECRET` (through the server), `apphear://join?n=CODE&s=SECRET`
 * (phone to phone with Nearby, no internet), or `https://<invite page>#c=...` when an invite page is
 * configured (the secret stays in the fragment, which browsers never send to a server).
 * A typed code alone also works; wrong guesses are limited.
 */
object RemoteInvite {
    const val SCHEME = "apphear"
    const val HOST = "join"
    const val CODE_LENGTH = 6
    private const val ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    private val SECRET = Regex("[0-9a-f]{32}")

    data class Link(val code: String, val secret: String?, val nearby: Boolean = false)

    /** Upper-cases and drops spaces/dashes; null unless it is a well-formed code. */
    fun normalizeCode(input: String): String? {
        val code = input.uppercase().filter { it.isLetterOrDigit() }
        return code.takeIf { it.length == CODE_LENGTH && it.all { char -> char in ALPHABET } }
    }

    /** "K7P4QM" -> "K7P-4QM" (easier to read aloud and type). */
    fun display(code: String): String = if (code.length == CODE_LENGTH) code.take(3) + "-" + code.drop(3) else code

    fun link(code: String, secret: String, invitePageUrl: String = "", nearby: Boolean = false): String {
        val page = invitePageUrl.trim()
        val key = if (nearby) "n" else "c"
        return if (page.startsWith("https://")) "${page.substringBefore('#')}#$key=$code&s=$secret"
        else "$SCHEME://$HOST?$key=$code&s=$secret"
    }

    /** A random code for a phone-to-phone (Nearby) invite, from the same alphabet as server codes. */
    fun randomCode(random: java.security.SecureRandom = java.security.SecureRandom()): String =
        String(CharArray(CODE_LENGTH) { ALPHABET[random.nextInt(ALPHABET.length)] })

    /** A random 128-bit invite secret as 32 hex characters. */
    fun randomSecret(random: java.security.SecureRandom = java.security.SecureRandom()): String =
        ByteArray(16).also(random::nextBytes).joinToString("") { "%02x".format(it) }

    /** Parses a scanned QR or an opened link. Returns null for anything that is not a valid invite. */
    fun parse(text: String, invitePageUrl: String = ""): Link? {
        val uri = try { URI(text.trim()) } catch (_: Exception) { return null }
        val parameters = when {
            uri.scheme.equals(SCHEME, ignoreCase = true) && uri.host.equals(HOST, ignoreCase = true) -> uri.rawQuery
            uri.scheme == "https" && invitePageUrl.startsWith("https://") &&
                sameInvitePage(uri, URI(invitePageUrl.substringBefore('#'))) -> uri.rawFragment
            else -> null
        } ?: return null
        val values = parameters.split('&').mapNotNull { part ->
            part.split('=', limit = 2).takeIf { it.size == 2 }?.let { it[0] to it[1] }
        }.toMap()
        val nearby = values["c"] == null && values["n"] != null
        val code = (values["c"] ?: values["n"])?.let(::normalizeCode) ?: return null
        val secret = values["s"]?.lowercase()
        return Link(code, secret?.takeIf { SECRET.matches(it) } ?: return null, nearby)
    }

    private fun sameInvitePage(link: URI, page: URI): Boolean =
        link.host.equals(page.host, ignoreCase = true) && link.port == page.port &&
            link.path.trimEnd('/') == page.path.trimEnd('/')
}
