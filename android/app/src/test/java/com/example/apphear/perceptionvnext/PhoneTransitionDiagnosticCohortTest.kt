package com.example.apphear.perceptionvnext

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PhoneTransitionDiagnosticCohortTest {
    @Test fun navigationBlocksDoNotSubstituteForPhysicalSignBoundaries() {
        assertEquals("76d93cecd85bf9f76064d320aa4a5791b5f0704a", PhoneTransitionDiagnosticCohort.BASELINE_SHA)
        assertEquals(listOf("A_HANDS_DOWN", "B_HANDS_UP"), PhoneTransitionDiagnosticCohort.blocks.take(2))
        assertEquals(7, PhoneTransitionDiagnosticCohort.blocks.size)
        assertEquals(7, PhoneTransitionDiagnosticCohort.instructions.size)
        assertTrue(PhoneTransitionDiagnosticCohort.instructions[0].contains("No deliberate READY wait"))
        assertTrue(PhoneTransitionDiagnosticCohort.instructions[1].contains("no deliberate READY wait"))
    }
}
