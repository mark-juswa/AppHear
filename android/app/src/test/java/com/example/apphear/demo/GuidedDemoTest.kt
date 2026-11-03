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
    fun valuesFillTemplatesAndEmptyOnesShowAsBrackets() {
        val values = mapOf("name" to "Joshua", "city" to "Naga City", "province" to " ")
        assertEquals("My name is Joshua.", DemoValues.fill("My name is {name}.", values))
        assertEquals("I live in Naga City, [province].", DemoValues.fill("I live in {city}, {province}.", values))
        assertEquals("My name is [name].", DemoValues.fill("My name is {name}.", emptyMap()))
        assertEquals("Hi {unknown}", DemoValues.fill("Hi {unknown}", values)) // left visible so tests catch typos
    }

    @Test
    fun cueSpellsFingerspelledWordsLetterByLetter() {
        val values = mapOf("name" to "Joshua", "city" to "Naga City")
        assertEquals("MY NAME J-O-S-H-U-A", DemoValues.cue("MY NAME FS:{name}", values))
        assertEquals("ME LIVE2 N-A-G-A C-I-T-Y", DemoValues.cue("ME LIVE2 FS:{city}", values))
        assertEquals("ONE TICKET N-A-G-A PLEASE", DemoValues.cue("ONE TICKET FS:NAGA PLEASE", values))
        assertEquals("MY NAME [name]", DemoValues.cue("MY NAME FS:{name}", emptyMap()))
    }

    @Test
    fun runWalksTheStepsInOrder() {
        val scenario = DemoScenario("s", "S", "c", listOf(
            DemoStep(DemoSpeaker.HEARING, "Hello! What is your name?"),
            DemoStep(DemoSpeaker.SIGNER, "My name is {name}.", "MY NAME FS:{name}"),
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
                val texts = listOfNotNull(step["text"]?.asString, step["gloss"]?.asString, step["avatar"]?.asString)
                for (text in texts) {
                    val unknown = DemoValues.keysIn(text) - DemoValues.keys.toSet()
                    assertTrue("$id uses unknown values $unknown", unknown.isEmpty())
                }
                if (who == "signer") assertNotNull("$id signer step needs a gloss", step["gloss"])
            }
        }
    }
}
