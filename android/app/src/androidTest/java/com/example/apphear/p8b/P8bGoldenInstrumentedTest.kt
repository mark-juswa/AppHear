package com.example.apphear.p8b

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/** Device gates in the required P8B-1 then P8B-2 order. */
@RunWith(AndroidJUnit4::class)
class P8bGoldenInstrumentedTest {
    @Test
    fun p8b01_modelDecoderThenPreprocessingParity() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val runtime = P8bGoldenVerifier.verifyModelAndDecoder(context)
        assertEquals(runtime.toString(2), "PASS", runtime.getString("status"))

        val preprocessing = P8bGoldenVerifier.verifyPreprocessing(context)
        assertEquals(preprocessing.toString(2), "PASS", preprocessing.getString("status"))
    }
}
