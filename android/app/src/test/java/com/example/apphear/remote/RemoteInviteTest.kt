package com.example.apphear.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RemoteInviteTest {
    private val secret = "0123456789abcdef0123456789abcdef"

    @Test
    fun codesAreNormalizedAndValidated() {
        assertEquals("K7P4QM", RemoteInvite.normalizeCode("k7p-4qm"))
        assertEquals("K7P4QM", RemoteInvite.normalizeCode(" K7P 4QM "))
        assertNull(RemoteInvite.normalizeCode("K7P4Q"))       // too short
        assertNull(RemoteInvite.normalizeCode("K7P4QMX"))     // too long
        assertNull(RemoteInvite.normalizeCode("K7P4Q0"))      // 0 is not in the alphabet (looks like O)
        assertNull(RemoteInvite.normalizeCode("K7P4QI"))      // I is not in the alphabet (looks like 1)
        assertEquals("K7P-4QM", RemoteInvite.display("K7P4QM"))
    }

    @Test
    fun appLinkRoundTrips() {
        val link = RemoteInvite.link("K7P4QM", secret)
        assertEquals("apphear://join?c=K7P4QM&s=$secret", link)
        assertEquals(RemoteInvite.Link("K7P4QM", secret), RemoteInvite.parse(link))
    }

    @Test
    fun nearbyLinkRoundTrips() {
        val link = RemoteInvite.link("K7P4QM", secret, nearby = true)
        assertEquals("apphear://join?n=K7P4QM&s=$secret", link)
        assertEquals(RemoteInvite.Link("K7P4QM", secret, nearby = true), RemoteInvite.parse(link))
    }

    @Test
    fun randomCodesAndSecretsAreWellFormed() {
        repeat(50) {
            val code = RemoteInvite.randomCode()
            assertEquals(code, RemoteInvite.normalizeCode(code))
            val made = RemoteInvite.link(code, RemoteInvite.randomSecret(), nearby = true)
            assertEquals(code, RemoteInvite.parse(made)?.code)
        }
    }

    @Test
    fun invitePageKeepsTheSecretInTheFragment() {
        val page = "https://apphear.example.org/join"
        val link = RemoteInvite.link("K7P4QM", secret, page)
        assertEquals("$page#c=K7P4QM&s=$secret", link)
        assertEquals(RemoteInvite.Link("K7P4QM", secret), RemoteInvite.parse(link, page))
        assertNull(RemoteInvite.parse(link)) // https links are only trusted when that page is configured
        assertNull(RemoteInvite.parse("https://evil.example.org/join#c=K7P4QM&s=$secret", page))
    }

    @Test
    fun rejectsAnythingElse() {
        assertNull(RemoteInvite.parse("hello"))
        assertNull(RemoteInvite.parse("apphear://join?c=K7P4QM"))               // no secret
        assertNull(RemoteInvite.parse("apphear://join?c=K7P4QM&s=short"))       // bad secret
        assertNull(RemoteInvite.parse("apphear://other?c=K7P4QM&s=$secret"))    // wrong host
        assertNull(RemoteInvite.parse("apphear://join?c=BAD&s=$secret"))        // bad code
        assertEquals(RemoteInvite.Link("K7P4QM", secret),
            RemoteInvite.parse("APPHEAR://JOIN?c=k7p4qm&s=${secret.uppercase()}"))
    }
}
