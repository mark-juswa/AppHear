package com.example.apphear.demo

import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class DemoQuestionMatcherTest {
    private val school: DemoTopic = run {
        val root = JsonParser.parseString(File("src/main/assets/guided_demo/topics_v1.json").readText()).asJsonObject
        assertEquals(1, root["schemaVersion"].asInt)
        val topic = root["topics"].asJsonArray.map { it.asJsonObject }.first { it["id"].asString == "school" }
        DemoTopic(topic["id"].asString, topic["title"].asString, topic["questions"].asJsonArray.map { it.asJsonObject }.map { q ->
            DemoQuestion(q["id"].asString, q["phrasings"].asJsonArray.map { it.asString }, q["answer"].asString,
                q["gloss"].asString, q["spell"]?.asString)
        })
    }

    private fun confidentId(spoken: String) = (DemoQuestionMatcher.match(spoken, school) as? QuestionMatch.Confident)?.question?.id

    @Test
    fun everyListedPhrasingMatchesItsOwnQuestion() {
        for (question in school.questions) for (phrasing in question.phrasings) {
            assertEquals("\"$phrasing\"", question.id, confidentId(phrasing))
        }
    }

    @Test
    fun naturalRewordingsStillMatch() {
        assertEquals("name", confidentId("Hey, what's your name?"))
        assertEquals("name", confidentId("ano pangalan mo"))
        assertEquals("year_level", confidentId("so what year are you in now"))
        assertEquals("course", confidentId("what course are you taking right now"))
        assertEquals("home", confidentId("where do you live po"))
        assertEquals("age", confidentId("how old are you"))
    }

    @Test
    fun unrelatedQuestionsAreNotConfident() {
        for (spoken in listOf("What's the weather like today?", "Do you like pizza?", "")) {
            assertFalse(spoken, DemoQuestionMatcher.match(spoken, school) is QuestionMatch.Confident)
        }
    }

    @Test
    fun bankIsWellFormed() {
        assertTrue(school.questions.size >= 12)
        assertEquals(school.questions.size, school.questions.map { it.id }.toSet().size)
        for (q in school.questions) {
            val unknown = (DemoValues.keysIn(q.answer) + DemoValues.keysIn(q.gloss)) - DemoValues.keys.toSet() - "spelled"
            assertTrue("${q.id} uses unknown values $unknown", unknown.isEmpty())
            assertEquals("${q.id}: {spelled} only with spell", q.spell != null, "{spelled}" in q.answer)
            q.spell?.let { assertTrue("${q.id} spells unknown key $it", it in DemoValues.keys) }
        }
    }

    @Test
    fun fingerspelledReadingsAreShownAsWords() {
        assertEquals("Nicole", DemoQuestionMatcher.spelledWords("NICOLE"))
        assertEquals("Naga City", DemoQuestionMatcher.spelledWords(" naga  city "))
        assertEquals("", DemoQuestionMatcher.spelledWords("  "))
    }
}
