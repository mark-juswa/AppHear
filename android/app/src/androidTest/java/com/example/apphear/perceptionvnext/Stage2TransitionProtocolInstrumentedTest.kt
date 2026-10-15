package com.example.apphear.perceptionvnext

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Test

/** Packaged parser check only; not sign-recognition evidence. */
class Stage2TransitionProtocolInstrumentedTest {
    @Test fun parsesTheActualPackagedCompactContract() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val protocol = context.assets.open(PhoneStage2TransitionProtocol.ASSET).use {
            PhoneStage2TransitionProtocol.parse(it.readBytes())
        }
        assertEquals(PhoneStage2TransitionProtocol.PROFILE_ID, protocol.profileId)
        assertEquals(5, protocol.blocks.size)
        assertEquals(7, protocol.blocks.sumOf { it.glosses.size })
    }
}
