package com.example.apphear.conversation.flow2

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversationFlowTest {
    private val f = ConversationFlow

    private fun signed(words: String, from: FlowState = FlowState()) = f.signedWordsChanged(from, words).state

    /** Signs [words], says them and returns the state once listening for the reply. */
    private fun saidAndListening(words: String, from: FlowState = FlowState()): FlowState {
        val saying = f.sayIt(signed(words, from)).state
        return f.sayingDone(saying, saying.ticket).state
    }

    @Test fun `full turn says the message, listens, shows the reply and clears the said words`() {
        val ready = signed("ME WANT WATER")
        assertEquals(PrimaryAction.SAY_IT, f.primaryAction(ready))

        val say = f.sayIt(ready)
        assertEquals(FlowPhase.SAYING, say.state.phase)
        assertEquals(listOf(FlowEffect.Speak("ME WANT WATER", say.state.ticket)), say.effects)
        assertEquals(PrimaryAction.STOP, f.primaryAction(say.state))

        val listening = f.sayingDone(say.state, say.state.ticket)
        assertEquals(FlowPhase.LISTENING, listening.state.phase)
        assertEquals(listOf(FlowEffect.StartListening(listening.state.ticket)), listening.effects)
        assertEquals(listOf(Exchange("ME WANT WATER", null)), listening.state.history)

        val partial = f.partialReply(listening.state, listening.state.ticket, "here you")
        assertEquals("here you", partial.state.partialReply)

        val reply = f.replyHeard(partial.state, listening.state.ticket, " Here you go. ")
        assertEquals(FlowPhase.REPLY, reply.state.phase)
        assertEquals("Here you go.", reply.state.reply)
        assertNull(reply.state.message)
        assertEquals(listOf(FlowEffect.ClearSignedWords, FlowEffect.RecordHearing("Here you go.", ReplySource.SPEECH)),
            reply.effects)
        assertEquals(listOf(Exchange("ME WANT WATER", "Here you go.")), reply.state.history)
        assertEquals(PrimaryAction.SIGN_IT, f.primaryAction(reply.state))
    }

    @Test fun `signing again after a reply returns to the signer's turn with the reply kept in history`() {
        val listening = saidAndListening("HELLO")
        val reply = f.replyHeard(listening, listening.ticket, "Hi there").state
        val cleared = signed("", reply)
        assertEquals(FlowPhase.REPLY, cleared.phase)

        val next = signed("THANK YOU", cleared)
        assertEquals(FlowPhase.READY, next.phase)
        assertNull(next.reply)
        assertEquals(listOf(Exchange("HELLO", "Hi there")), next.history)
        assertEquals(PrimaryAction.SAY_IT, f.primaryAction(next))
    }

    @Test fun `stale callbacks from an earlier ticket are ignored`() {
        val say = f.sayIt(signed("HELLO")).state
        val stopped = f.stop(say).state
        assertSame(stopped, f.sayingDone(stopped, say.ticket).state)

        val listening = saidAndListening("HELLO")
        val stoppedListening = f.stop(listening).state
        assertSame(stoppedListening, f.replyHeard(stoppedListening, listening.ticket, "late").state)
        assertSame(stoppedListening, f.partialReply(stoppedListening, listening.ticket, "late").state)
        assertSame(stoppedListening, f.listenFailed(stoppedListening, listening.ticket, ListenFailure.ERROR).state)
    }

    @Test fun `stop while saying keeps the message so it can be said again`() {
        val say = f.sayIt(signed("HELLO")).state
        val stop = f.stop(say)
        assertEquals(listOf(FlowEffect.StopSpeaking), stop.effects)
        assertEquals(FlowPhase.READY, stop.state.phase)
        assertEquals("HELLO", stop.state.message?.signedWords)
        assertTrue(stop.state.history.isEmpty())
    }

    @Test fun `stop while listening returns to the resting state`() {
        val listening = f.listen(FlowState()).state
        val stop = f.stop(listening)
        assertEquals(listOf(FlowEffect.StopListening), stop.effects)
        assertEquals(FlowPhase.READY, stop.state.phase)

        val withReply = f.typedReply(FlowState(), "Earlier reply").state
        val again = f.stop(f.listen(withReply).state).state
        assertEquals(FlowPhase.REPLY, again.phase)
        assertEquals("Earlier reply", again.reply)
    }

    @Test fun `failed speech output returns to the message without listening`() {
        val say = f.sayIt(signed("HELLO")).state
        val failed = f.sayingFailed(say, say.ticket)
        assertEquals(FlowPhase.READY, failed.state.phase)
        assertTrue(failed.effects.isEmpty())
        assertEquals("HELLO", failed.state.message?.signedWords)
    }

    @Test fun `nothing heard shows not heard and offers listen again`() {
        val listening = saidAndListening("HELLO")
        val blank = f.replyHeard(listening, listening.ticket, "   ").state
        assertEquals(FlowPhase.NOT_HEARD, blank.phase)
        assertEquals(ListenFailure.NOT_HEARD, blank.failure)
        assertEquals(PrimaryAction.LISTEN, f.primaryAction(blank))

        val retry = f.listen(blank)
        assertEquals(FlowPhase.LISTENING, retry.state.phase)
        val reply = f.replyHeard(retry.state, retry.state.ticket, "Sorry, hello").state
        // The retried reply still belongs to the message that was said.
        assertEquals(listOf(Exchange("HELLO", "Sorry, hello")), reply.history)
    }

    @Test fun `unavailable or denied listening falls back to the system dialog once`() {
        for (failure in listOf(ListenFailure.UNAVAILABLE, ListenFailure.NO_PERMISSION)) {
            val listening = f.listen(FlowState()).state
            val fallback = f.listenFailed(listening, listening.ticket, failure)
            assertEquals(listOf(FlowEffect.OpenSystemListening(listening.ticket)), fallback.effects)
            assertEquals(FlowPhase.LISTENING, fallback.state.phase)

            val dialogReply = f.replyHeard(fallback.state, listening.ticket, "From the dialog").state
            assertEquals("From the dialog", dialogReply.reply)

            val secondFailure = f.listenFailed(fallback.state, listening.ticket, failure)
            assertEquals(FlowPhase.NOT_HEARD, secondFailure.state.phase)
            assertTrue(secondFailure.effects.isEmpty())
        }
    }

    @Test fun `errors do not fall back`() {
        val listening = f.listen(FlowState()).state
        val error = f.listenFailed(listening, listening.ticket, ListenFailure.ERROR)
        assertTrue(error.effects.isEmpty())
        assertEquals(FlowPhase.NOT_HEARD, error.state.phase)
        assertEquals(ListenFailure.ERROR, error.state.failure)
    }

    @Test fun `hearing person speaking first does not clear unsaid signed words`() {
        val partway = signed("ME")
        val listening = f.listen(partway).state
        val reply = f.replyHeard(listening, listening.ticket, "What do you need?")
        assertEquals(listOf(FlowEffect.RecordHearing("What do you need?", ReplySource.SPEECH)), reply.effects)
        assertEquals("ME", reply.state.message?.signedWords)
        assertEquals(listOf(Exchange(null, "What do you need?")), reply.state.history)
    }

    @Test fun `words signed after saying survive the reply`() {
        val listening = saidAndListening("HELLO")
        val stopped = f.stop(listening).state
        val more = signed("HELLO FRIEND", stopped)
        val relisten = f.listen(more).state
        val reply = f.replyHeard(relisten, relisten.ticket, "Hi")
        assertFalse(FlowEffect.ClearSignedWords in reply.effects)
        assertEquals("HELLO FRIEND", reply.state.message?.signedWords)
        assertEquals(listOf(Exchange("HELLO", "Hi")), reply.state.history)
    }

    @Test fun `typed reply stops listening and is recorded as typed`() {
        val listening = saidAndListening("HELLO")
        val typed = f.typedReply(listening, " Please wait ")
        assertEquals(listOf(FlowEffect.StopListening, FlowEffect.ClearSignedWords,
            FlowEffect.RecordHearing("Please wait", ReplySource.TYPED)), typed.effects)
        assertEquals("Please wait", typed.state.reply)
        assertSame(listening, f.typedReply(listening, "   ").state)
    }

    @Test fun `suggestion is optional, chosen explicitly and reset when the signed words change`() {
        val ready = signed("ME WANT WATER")
        val suggested = f.suggestionReady(ready, "ME WANT WATER", "I want water.").state
        assertEquals("ME WANT WATER", suggested.message?.chosen)

        val chosen = f.chooseSuggestion(suggested, true).state
        assertEquals("I want water.", chosen.message?.chosen)
        assertEquals(FlowEffect.Speak("I want water.", 1), f.sayIt(chosen).effects.single())

        val changed = signed("ME WANT WATER NOW", chosen)
        assertNull(changed.message?.suggestion)
        assertEquals("ME WANT WATER NOW", changed.message?.chosen)
    }

    @Test fun `stale or useless suggestions are ignored`() {
        val ready = signed("HELLO")
        assertSame(ready, f.suggestionReady(ready, "GOODBYE", "Goodbye.").state)
        assertNull(f.suggestionReady(ready, "HELLO", "HELLO").state.message?.suggestion)
        assertNull(f.suggestionReady(ready, "HELLO", "  ").state.message?.suggestion)
        assertSame(ready, f.chooseSuggestion(ready, true).state)
    }

    @Test fun `history keeps the six most recent exchanges`() {
        var s = FlowState()
        for (i in 1..8) {
            val listening = saidAndListening("WORD$i", s)
            s = f.replyHeard(listening, listening.ticket, "reply $i").state
            s = signed("", s)
        }
        assertEquals(ConversationFlow.MAX_EXCHANGES, s.history.size)
        assertEquals(Exchange("WORD3", "reply 3"), s.history.first())
        assertEquals(Exchange("WORD8", "reply 8"), s.history.last())
    }

    @Test fun `avatar plays the reply, returns on genuine completion and supports replay and close`() {
        val reply = f.typedReply(FlowState(), "Nice to meet you").state
        val play = f.signIt(reply)
        assertEquals(FlowPhase.AVATAR, play.state.phase)
        assertEquals(listOf(FlowEffect.PlayAvatar("Nice to meet you", play.state.ticket)), play.effects)
        assertEquals(PrimaryAction.REPLAY, f.primaryAction(play.state))

        val replay = f.replay(play.state)
        assertEquals(listOf(FlowEffect.PlayAvatar("Nice to meet you", replay.state.ticket)), replay.effects)
        assertSame(replay.state, f.avatarFinished(replay.state, play.state.ticket).state)

        val done = f.avatarFinished(replay.state, replay.state.ticket).state
        assertEquals(FlowPhase.REPLY, done.phase)

        val closed = f.stop(f.signIt(reply).state)
        assertEquals(listOf(FlowEffect.StopAvatar), closed.effects)
        assertEquals(FlowPhase.REPLY, closed.state.phase)
    }

    @Test fun `avatar can replay an older reply from history`() {
        val reply = f.typedReply(FlowState(), "Latest").state
        val play = f.signIt(reply, "Older one")
        assertEquals(listOf(FlowEffect.PlayAvatar("Older one", play.state.ticket)), play.effects)
    }

    @Test fun `signing during avatar playback is kept and becomes the signer's turn afterwards`() {
        val playing = f.signIt(f.typedReply(FlowState(), "Hi").state).state
        val stray = signed("HELLO", playing)
        assertEquals(FlowPhase.AVATAR, stray.phase)
        assertEquals(FlowPhase.READY, f.avatarFinished(stray, stray.ticket).state.phase)
    }

    @Test fun `actions are refused in the wrong phase`() {
        val listening = f.listen(signed("HELLO")).state
        assertSame(listening, f.sayIt(listening).state)
        assertSame(listening, f.listen(listening).state)
        assertSame(listening, f.signIt(listening, "x").state)

        val idle = FlowState()
        assertSame(idle, f.sayIt(idle).state)
        assertSame(idle, f.signIt(idle).state)
        assertSame(idle, f.stop(idle).state)
        assertNull(f.back(idle))
    }

    @Test fun `back stops what is in progress`() {
        val say = f.sayIt(signed("HELLO")).state
        assertEquals(listOf(FlowEffect.StopSpeaking), f.back(say)?.effects)
        val playing = f.signIt(f.typedReply(FlowState(), "Hi").state).state
        assertEquals(listOf(FlowEffect.StopAvatar), f.back(playing)?.effects)
    }

    @Test fun `restoring after recreation resumes nothing`() {
        val listening = saidAndListening("HELLO")
        val restored = f.restored(listening)
        assertEquals(FlowPhase.READY, restored.phase)
        assertTrue(restored.ticket > listening.ticket)
        assertSame(restored, f.replyHeard(restored, listening.ticket, "late").state)

        val playing = f.signIt(f.typedReply(FlowState(), "Hi").state).state
        assertEquals(FlowPhase.REPLY, f.restored(playing).phase)
    }

    @Test fun `clear drops the message and clears the signed words`() {
        val cleared = f.clear(signed("HELLO"))
        assertNull(cleared.state.message)
        assertEquals(listOf(FlowEffect.ClearSignedWords), cleared.effects)
    }

    @Test fun `sayText says the Hear path's text and clears only the signed words it came from`() {
        val ready = signed("ME WANT WATER")
        val say = f.sayText(ready, " I want water. ")
        assertEquals(listOf(FlowEffect.Speak("I want water.", say.state.ticket)), say.effects)
        val listening = f.sayingDone(say.state, say.state.ticket).state
        assertEquals(listOf(Exchange("I want water.", null)), listening.history)
        val reply = f.replyHeard(listening, listening.ticket, "Sure")
        assertTrue(FlowEffect.ClearSignedWords in reply.effects)

        assertSame(ready, f.sayText(ready, "  ").state)
        assertSame(listening, f.sayText(listening, "again").state)
        // Confirmed spelling can be said with no WORD message on screen.
        assertEquals(FlowPhase.SAYING, f.sayText(FlowState(), "AMY").state.phase)
    }
}
