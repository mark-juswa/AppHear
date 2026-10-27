package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import org.junit.Assert.*
import org.junit.Test

/** Technical placement/protection checks, not qualified ASL validation. */
class AslFourSignPlacementTest {
    private val evidence=JsonParser.parseString(javaClass.getResource("/texttoasl/four-placement-gates.json")!!.readText()).asJsonObject
    private val bytes=Files.readAllBytes(Path.of("src/aslOriginalWords/assets").resolve(AslFingerspellingBundle.PATH))
    private val buffer=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    private val g=JsonParser.parseString(String(bytes,20,buffer.getInt(12))).asJsonObject
    private fun raw(index:Int):ByteArray {
        val a=g.getAsJsonArray("accessors")[index].asJsonObject
        val view=g.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
        val width=when(a.get("type").asString) { "SCALAR"->1;"VEC3"->3;"VEC4"->4;else->error("Unexpected animation type") }
        val start=28+buffer.getInt(12)+(view.get("byteOffset")?.asInt?:0)+(a.get("byteOffset")?.asInt?:0)
        return bytes.copyOfRange(start,start+a.get("count").asInt*width*4)
    }
    @Test fun correctionProtectsUnchangedFingersAndAllAlphabetActions() {
        val digest=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        assertEquals(AslFingerspellingBundle.SHA256,digest)
        val wrists=JsonParser.parseString(javaClass.getResource("/texttoasl/three-wrist-gates.json")!!.readText()).asJsonObject
        assertEquals(AslFingerspellingBundle.BEFORE_INTEGRATION_SHA256,wrists.get("candidateSha256").asString)
        assertEquals(evidence.get("candidateSha256").asString,wrists.get("sourceSha256").asString)
        assertEquals("c95446529cbad8e7d411b0dba558f111a9d90e4a6a23acfe6d58608883f05569",evidence.get("sourceSha256").asString)
        assertEquals(280,evidence.get("preservedActions").asInt)
        assertEquals(27,evidence.get("alphabetAndNeutralActionsUnchanged").asInt)
        assertTrue(evidence.get("allOtherFingerChannelsAndAllFingerClocksUnchanged").asBoolean)
        val arms=listOf("Left","Right").flatMap { s->listOf("Arm","ForeArm","Hand").map { s+it } }.toSet()
        val protected=evidence.getAsJsonObject("protectedNonArmChannelSha256")
        assertEquals(4,protected.size())
        for((name,expected) in protected.entrySet()) {
            val action=g.getAsJsonArray("animations").single { it.asJsonObject.get("name").asString==name }.asJsonObject
            val hash=MessageDigest.getInstance("SHA-256")
            for(entry in action.getAsJsonArray("channels")) {
                val channel=entry.asJsonObject;val target=channel.getAsJsonObject("target")
                val node=target.get("node").asInt;val path=target.get("path").asString
                val nodeName=g.getAsJsonArray("nodes")[node].asJsonObject.get("name").asString
                val indexRepair=name in setOf("SIGN_MILK_HUMAN_AUTHORED_PREVIEW","SIGN_ORANGE_HUMAN_AUTHORED_PREVIEW") && nodeName in setOf("RightHandIndex1","RightHandIndex2","RightHandIndex3")
                if(path=="rotation" && (nodeName in arms || indexRepair))continue
                hash.update("$node:$path\u0000".toByteArray(Charsets.UTF_8))
                val sampler=action.getAsJsonArray("samplers")[channel.get("sampler").asInt].asJsonObject
                hash.update(raw(sampler.get("input").asInt));hash.update(raw(sampler.get("output").asInt))
            }
            assertEquals(name,expected.asString,hash.digest().joinToString("") { "%02x".format(it) })
        }
    }
    @Test fun milkAndOrangeCloseTheIndexIntoAFistRatherThanPinchingTheThumb() {
        for(word in listOf("milk","orange")) {
            val anchors=evidence.getAsJsonObject("anchors").getAsJsonObject(word)
            val opened=anchors.getAsJsonObject("openIndex");val closed=anchors.getAsJsonObject("closedIndex")
            assertTrue(word,opened.get("reachMeters").asDouble-closed.get("reachMeters").asDouble>.015)
            assertTrue(word,closed.get("pipDegrees").asDouble in 85.0..115.0)
            assertTrue(word,closed.get("dipDegrees").asDouble in 45.0..80.0)
            assertTrue(word,closed.get("thumbIndexTipGapMeters").asDouble>.025)
        }
    }
    @Test fun fourDistinctActionsHaveScreenedPlacementsAndRetainReviewRequirements() {
        assertEquals(AslFingerspellingBundle.ACTION_COUNT,g.getAsJsonArray("animations").size())
        assertEquals(setOf("explain","understand","milk","orange"),evidence.getAsJsonArray("rows").map { it.asJsonObject.get("word").asString }.toSet())
        assertTrue(evidence.getAsJsonArray("rows").all { it.asJsonObject.get("technicallyPassed").asBoolean })
        assertFalse(evidence.get("qualifiedAslValidation").asBoolean)
        assertTrue(evidence.get("orangeMilkPalmHeightDifferenceMeters").asDouble>.18)
        val anchors=evidence.getAsJsonObject("anchors")
        assertTrue(anchors.getAsJsonObject("explain").get("opposedDepthCorrelation").asDouble<-.99)
        assertTrue(anchors.getAsJsonObject("understand").get("indexFlickRiseMeters").asDouble>.04)
    }
}
