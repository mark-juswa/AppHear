package com.example.apphear.perceptionvnext

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class RecognitionV2ParityInstrumentedTest {
    @Test
    fun frozenPythonRecognitionV2MatchesAndroidDevice() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val result = RecognitionV2ParityVerifier.verify(context)
        assertEquals(result.toString(2), "PASS", result.getString("status"))
    }
}
