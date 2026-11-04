package com.example.apphear.demo

import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class GuidedDemoTest {
    @Test
    fun glossSplitsIntoSignsAndSpellsFsWords() {
        assertEquals(listOf("ONE", "TICKET", "N-A-G-A", "PLEASE"), DemoGloss.signs("ONE TICKET FS:NAGA PLEASE"))
        assertEquals(listOf("ME", "LEARN", "I-T"), DemoGloss.signs(" ME  LEARN FS:IT "))
    }

    @Test
    fun runWalksTheStepsInOrder() {
        val scenario = DemoScenario("s", "S", "c", listOf(
            DemoStep(DemoSpeaker.HEARING, "Hello! What is your name?"),
            DemoStep(DemoSpeaker.SIGNER, "My name is {spelled}.", "MY NAME FS", spell = true),
        ))
        var run = DemoRun(scenario)
        assertEquals(DemoSpeaker.HEARING, run.step?.speaker)
        run = run.showing() // hearing steps have nothing to show
        assertFalse(run.shown)
        run = run.advance()
        assertEquals(DemoSpeaker.SIGNER, run.step?.speaker)
        run = run.showing()
        assertTrue(run.shown)
        assertFalse(run.again().shown)
        run = run.advance()
        assertTrue(run.finished)
        assertEquals(run, run.advance())
        assertEquals(2 to 2, run.progress)
    }

    /** The shipped scenarios are well formed: known placeholders, glosses for signer steps, alternating turns. */
    @Test
    fun shippedScenariosAreValid() {
        val root = JsonParser.parseString(File("src/main/assets/guided_demo/scenarios_v1.json").readText()).asJsonObject
        assertEquals(1, root["schemaVersion"].asInt)
        val scenarios = root["scenarios"].asJsonArray.map { it.asJsonObject }
        assertTrue(scenarios.size >= 6)
        assertEquals(scenarios.size, scenarios.map { it["id"].asString }.toSet().size)
        for (scenario in scenarios) {
            val id = scenario["id"].asString
            val steps = scenario["steps"].asJsonArray.map { it.asJsonObject }
            assertTrue("$id has too few steps", steps.size >= 4)
            for (step in steps) {
                val who = step["who"].asString
                assertTrue("$id: who=$who", who == "hearing" || who == "signer")
                val spell = step["spell"]?.asBoolean == true
                for (text in listOfNotNull(step["text"]?.asString, step["gloss"]?.asString, step["avatar"]?.asString)) {
                    // No setting-filled values: only a spelled answer's {spelled} part, read by fingerspelling.
                    val slots = Regex("""\{[a-z_]+}""").findAll(text).map { it.value }.toSet()
                    assertTrue("$id has unexpected slots $slots in \"$text\"", slots.isEmpty() || (spell && slots == setOf("{spelled}")))
                }
                if (who == "signer") assertNotNull("$id signer step needs a gloss", step["gloss"])
                assertEquals("$id: {spelled} only with spell", spell, step["text"].asString.contains("{spelled}"))
            }
        }
    }
}
