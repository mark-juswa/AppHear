package com.example.apphear.remote

import com.example.apphear.remote.RemoteMessage.Status
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RemoteStateTest {
    private val host = RemoteState(RemoteRole.HOST, RemotePhase.Connected, "conv")

    @Test
    fun outgoingMessageIsConfirmedOnceEvenIfTheServerEchoesIt() {
        val sending = host.withOutgoing("a", "hello")
        assertEquals(Status.SENDING, sending.messages.single().status)
        assertEquals(listOf("a"), sending.pendingOutgoing.map { it.id })

        // The send reply and the live event both report the same row.
        val sent = sending.withServerMessage("a", 1, "hello", fromMe = true)
            .withServerMessage("a", 1, "hello", fromMe = true)
        assertEquals(1, sent.messages.size)
        assertEquals(Status.SENT, sent.messages.single().status)
        assertTrue(sent.pendingOutgoing.isEmpty())
        assertEquals(1L, sent.lastSeq)
    }

    @Test
    fun messagesFollowServerOrderAndUnsentStayLast() {
        val state = host.withOutgoing("c", "third")
            .withServerMessage("b", 2, "second", fromMe = true)
            .withServerMessage("a", 1, "first", fromMe = true)
        assertEquals(listOf("a", "b", "c"), state.messages.map { it.id })
    }

    @Test
    fun failedSendIsRetriedWithTheSameId() {
        val failed = host.withOutgoing("a", "hello").withSendFailed("a")
        assertEquals(Status.FAILED, failed.messages.single().status)
        assertEquals(listOf("a"), failed.pendingOutgoing.map { it.id })
        val sent = failed.withServerMessage("a", 5, "hello", fromMe = true)
        assertEquals(Status.SENT, sent.messages.single().status)
    }

    @Test
    fun seenMarksOnlyConfirmedMessagesUpToTheSequence() {
        val state = host.withServerMessage("a", 1, "one", true)
            .withServerMessage("b", 2, "two", true)
            .withOutgoing("c", "three")
            .withSeenUpTo(1)
        assertEquals(listOf(Status.SEEN, Status.SENT, Status.SENDING), state.messages.map { it.status })
        // A late duplicate event does not undo "seen".
        assertEquals(Status.SEEN, state.withServerMessage("a", 1, "one", true).messages.first().status)
    }

    @Test
    fun historyIsCappedWithoutDroppingUnsentMessages() {
        var state = host.withOutgoing("pending", "not sent yet")
        for (i in 1..(RemoteState.MAX_MESSAGES + 10)) state = state.withServerMessage("m$i", i.toLong(), "m$i", true)
        assertEquals(RemoteState.MAX_MESSAGES, state.messages.size)
        assertTrue(state.messages.any { it.id == "pending" })
        assertEquals("m${RemoteState.MAX_MESSAGES + 10}", state.messages.last { it.seq != null }.id)
    }

    @Test
    fun viewerSeesIncomingMessages() {
        val viewer = RemoteState(RemoteRole.VIEWER, RemotePhase.Connected, "conv")
            .withServerMessage("a", 3, "hi", fromMe = false)
        assertEquals(false, viewer.messages.single().fromMe)
        assertTrue(viewer.pendingOutgoing.isEmpty())
    }
}
