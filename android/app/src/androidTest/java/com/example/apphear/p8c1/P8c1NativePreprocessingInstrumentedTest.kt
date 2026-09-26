package com.example.apphear.p8c1

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class P8c1NativePreprocessingInstrumentedTest {
    @Test
    fun p8c1StaticNativePreprocessingMatchesFrozenP8bFixtures() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val result = P8c1StaticVerifier.verify(context)
        assertEquals(result.toString(2), "PASS", result.getString("status"))
    }
}
