package com.example.apphear.conversation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class ConversationTimelineFormatTest {
    @Test
    fun formatsOneJsonObjectWithTypedFields() {
        val line = ConversationTimeline.format("tap", 12L, 34L,
            listOf("screen" to "recognition", "live" to 2, "fps" to 7.5f, "ok" to true, "none" to null))
        assertEquals(
            "{\"e\":\"tap\",\"t\":12,\"w\":34,\"screen\":\"recognition\",\"live\":2,\"fps\":7.5," +
                "\"ok\":true,\"none\":null}",
            line,
        )
    }

    @Test
    fun escapesQuotesBackslashesAndControlCharacters() {
        val line = ConversationTimeline.format("e", 0L, 0L, listOf("k" to "a\"b\\c\nd"))
        assertEquals("{\"e\":\"e\",\"t\":0,\"w\":0,\"k\":\"a\\\"b\\\\c\\u000ad\"}", line)
        assertFalse(line.contains('\n'))
    }

    @Test
    fun nonFiniteNumbersBecomeNull() {
        val line = ConversationTimeline.format("e", 0L, 0L, listOf("fps" to Float.NaN, "x" to Double.POSITIVE_INFINITY))
        assertEquals("{\"e\":\"e\",\"t\":0,\"w\":0,\"fps\":null,\"x\":null}", line)
    }
}
