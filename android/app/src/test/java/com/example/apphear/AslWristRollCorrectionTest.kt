package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.math.*
import org.junit.Assert.*
import org.junit.Test

/** Mechanical regression checks. No linguistic accuracy is inferred. */
class AslWristRollCorrectionTest {
    private val root=Path.of("src/aslOriginalWords/assets")
    private val bytes=Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
    private val buffer=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    private val g=JsonParser.parseString(String(bytes,20,buffer.getInt(12))).asJsonObject
    private val registry=JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
    private val actions=g.getAsJsonArray("animations").associate { it.asJsonObject.let { a -> a.get("name").asString to a } }
    private val armNames=listOf("Left","Right").flatMap { side -> listOf("Arm","ForeArm","Hand").map { side+it } }.toSet()
    private fun raw(index:Int):ByteArray {
        val a=g.getAsJsonArray("accessors")[index].asJsonObject
        val v=g.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
        assertEquals(5126,a.get("componentType").asInt)
        val width=when(a.get("type").asString) { "SCALAR"->1;"VEC3"->3;"VEC4"->4;else->error("Unexpected animation accessor") }
        val start=28+buffer.getInt(12)+(v.get("byteOffset")?.asInt?:0)+(a.get("byteOffset")?.asInt?:0)
        return bytes.copyOfRange(start,start+a.get("count").asInt*width*4)
    }
    private fun floats(index:Int):List<Double> {
        val b=ByteBuffer.wrap(raw(index)).order(ByteOrder.LITTLE_ENDIAN)
        return (0 until b.capacity()/4).map { b.getFloat(it*4).toDouble() }
    }
    private fun hashAction(a:JsonObject,includeTimes:Boolean):String {
        val digest=MessageDigest.getInstance("SHA-256")
        for(channel in a.getAsJsonArray("channels")) {
            val c=channel.asJsonObject;val target=c.getAsJsonObject("target")
            val node=target.get("node").asInt;val path=target.get("path").asString
            val name=g.getAsJsonArray("nodes")[node].asJsonObject.get("name").asString
            if(!includeTimes && path=="rotation" && name in armNames) continue
            digest.update("$node:$path\u0000".toByteArray(Charsets.UTF_8))
            val sampler=a.getAsJsonArray("samplers")[c.get("sampler").asInt].asJsonObject
            if(includeTimes) digest.update(raw(sampler.get("input").asInt))
            digest.update(raw(sampler.get("output").asInt))
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
    @Test fun unchangedFingerOutputsAndAllAlphabetClocksMatchPinnedPreRepairEvidence() {
        val fixture=JsonParser.parseString(javaClass.getResource("/texttoasl/hand-twist-baseline.json")!!.readText()).asJsonObject
        assertEquals("cb94d0dad112b371347a17035cbb34095d0906443de7115e776b56d31ceb057e",fixture.get("sourceSha256").asString)
        assertEquals(274,fixture.getAsJsonArray("actions").size())
        var untouched=0
        for(entry in fixture.getAsJsonArray("actions")) {
            val e=entry.asJsonObject;val name=e.get("name").asString;val include=e.get("includeTimes").asBoolean
            // Later, explicitly scoped index closure repair: its unchanged
            // channels and new targets are pinned independently. SCHOOL also has
            // explicit flat-finger keys checked by AslThreeWristRepairTest.
            if(name in setOf("SIGN_MILK_HUMAN_AUTHORED_PREVIEW","SIGN_ORANGE_HUMAN_AUTHORED_PREVIEW","SIGN_SCHOOL")) continue
            if (WordHandRepairEvidence.accepts(name, g, bytes)) continue
            assertEquals(name,e.get("sha256").asString,hashAction(actions.getValue(name),include))
            if(include) untouched++
        }
        assertEquals(27,untouched)
        assertFalse(registry.getAsJsonObject("handWristCorrection").get("qualifiedAslValidation").asBoolean)
    }
    @Test fun everyReferencedSamplerHasFiniteValuesStrictTimesAndCorrectControllerDuration() {
        val clocks=registry.getAsJsonObject("durationOverridesMs")
        assertEquals(247,clocks.size())
        for((name,a) in actions) {
            var end=0.0
            for(channel in a.getAsJsonArray("channels")) {
                val c=channel.asJsonObject;val s=a.getAsJsonArray("samplers")[c.get("sampler").asInt].asJsonObject
                val times=floats(s.get("input").asInt)
                assertTrue(name,times.all { it.isFinite() } && times.zipWithNext().all { (x,y)->y>x })
                end=max(end,times.last())
                val values=floats(s.get("output").asInt);assertTrue(name,values.all { it.isFinite() })
                if(c.getAsJsonObject("target").get("path").asString=="rotation") {
                    for(q in values.chunked(4)) assertEquals(name,1.0,q.sumOf { it*it },.0001)
                }
            }
            if(clocks.has(name)) assertEquals(name,round(end*1000).toLong(),clocks.get(name).asLong)
        }
    }
    @Test fun finishForearmsReturnWithoutACompleteAxialTurn() {
        val a=actions.getValue("SIGN_FINISH_HUMAN_AUTHORED_PREVIEW")
        for(side in listOf("Left","Right")) {
            val channel=a.getAsJsonArray("channels").single {
                val t=it.asJsonObject.getAsJsonObject("target")
                t.get("path").asString=="rotation" && g.getAsJsonArray("nodes")[t.get("node").asInt].asJsonObject.get("name").asString==side+"ForeArm"
            }.asJsonObject
            val s=a.getAsJsonArray("samplers")[channel.get("sampler").asInt].asJsonObject
            val q=floats(s.get("output").asInt).chunked(4)
            // Exported tracks use continuous quaternion hemispheres. An odd
            // 360-degree return ended on the opposite quaternion previously.
            assertTrue(side,q.first().zip(q.last()).sumOf { (x,y)->x*y }>.99)
        }
    }
    @Test fun durationOverridesApplyToSharedAliasesAndRejectUnknownActions() {
        fun asset(id:String)=AslAnimationAsset(id,id,AslFingerspellingBundle.PATH,AslAnimationAsset.Type.WORD,emptyList(),AslAnimationAsset.Replacement(null,"SHARED",1500))
        val result=AslFingerspellingBundle.withDurations(listOf(asset("call"),asset("name")),mapOf("SHARED" to 3007L))
        assertTrue(result.all { it.replacement!!.durationMs==3007L })
        assertThrows(IllegalArgumentException::class.java) { AslFingerspellingBundle.withDurations(result,mapOf("MISSING" to 1000L)) }
        assertThrows(IllegalArgumentException::class.java) { AslFingerspellingBundle.withDurations(result,mapOf("SHARED" to -1L)) }
    }
}
