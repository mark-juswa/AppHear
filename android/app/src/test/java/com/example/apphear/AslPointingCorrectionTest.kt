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

/** Technical pointer/repair boundaries, never a linguistic accuracy claim. */
class AslPointingCorrectionTest {
    private val root=Path.of("src/aslOriginalWords/assets")
    private val bytes=Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
    private val buffer=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    private val document=JsonParser.parseString(String(bytes,20,buffer.getInt(12))).asJsonObject
    private val repair=JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST))))
        .asJsonObject.getAsJsonObject("pointingCorrection")
    private fun values(index:Int):List<Double> {
        val a=document.getAsJsonArray("accessors")[index].asJsonObject
        val v=document.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
        assertEquals(5126,a.get("componentType").asInt)
        val width=if(a.get("type").asString=="SCALAR") 1 else 4
        val offset=28+buffer.getInt(12)+(v.get("byteOffset")?.asInt?:0)+(a.get("byteOffset")?.asInt?:0)
        return (0 until a.get("count").asInt*width).map {buffer.getFloat(offset+it*4).toDouble()}
    }

    @Test fun repairIsLimitedToTheTwoUnvalidatedPointers() {
        assertEquals("c04f873aa44d7c31fdf688d423d18100843535067acab0223418ea9340fa34b5",repair.get("sourceSha256").asString)
        assertFalse(repair.get("qualifiedASLValidation").asBoolean)
        assertEquals(230,repair.get("unchangedActions").asInt)
        val profiles=repair.getAsJsonArray("profiles")
        assertEquals(setOf("SIGN_I","SIGN_YOU_HUMAN_RETARGETED_PREVIEW"),profiles.map {it.asJsonObject.get("animationName").asString}.toSet())
        val right=setOf("RightArm","RightForeArm","RightHand")+listOf("Thumb","Index","Middle","Ring","Pinky")
            .flatMap {f->(1..3).map {j->"RightHand$f$j"}}
        for(raw in profiles) {
            val p=raw.asJsonObject
            val extra=if(p.get("animationName").asString=="SIGN_I") emptySet() else setOf("LeftShoulder","LeftArm","LeftForeArm","LeftHand")
            assertEquals(right+extra,p.getAsJsonArray("changedNodes").map {it.asString}.toSet())
            assertTrue(p.get("technicallyPassed").asBoolean)
            assertTrue(p.get("heldDirectionCosine").asDouble>.999)
        }
    }

    @Test fun pointingIndexExtendsWhileOtherFingersRemainArticulated() {
        for(name in listOf("SIGN_I","SIGN_YOU_HUMAN_RETARGETED_PREVIEW")) {
            val animation=document.getAsJsonArray("animations").single {it.asJsonObject.get("name").asString==name}.asJsonObject
            for(raw in animation.getAsJsonArray("channels")) {
                val channel=raw.asJsonObject
                val target=channel.getAsJsonObject("target")
                val node=document.getAsJsonArray("nodes")[target.get("node").asInt].asJsonObject
                val bone=node.get("name").asString
                if(target.get("path").asString!="rotation" || !bone.matches(Regex("RightHand(Index|Middle|Ring|Pinky)[123]")))continue
                val sampler=animation.getAsJsonArray("samplers")[channel.get("sampler").asInt].asJsonObject
                val times=values(sampler.get("input").asInt)
                val poses=values(sampler.get("output").asInt).chunked(4)
                assertTrue(times.zipWithNext().all {(a,b)->b>a})
                assertTrue(poses.all {q->kotlin.math.abs(q.sumOf {it*it}-1)<.00001})
                val key=times.indices.minBy {kotlin.math.abs(times[it]-times.last()*.5)}
                val bind=node.getAsJsonArray("rotation")?.map {it.asDouble}?:listOf(0.0,0.0,0.0,1.0)
                val dot=kotlin.math.abs(poses[key].zip(bind).sumOf {(a,b)->a*b})
                if(bone.contains("Index"))assertTrue("Index reaches open bind articulation: $bone",dot>.99999)
                else assertTrue("Folded fingers aren't frozen at bind: $bone",dot<.96)
            }
        }
    }

    @Test fun loveYesHelpAndAllAlphabetActionsArePreserved() {
        val protected=repair.getAsJsonObject("preservedAnimationHashes")
        // The prefix also matches lexical LETTER (mail); it is not a 27th letter.
        val expected=setOf("SIGN_LOVE","SIGN_YES","SIGN_HELP","SIGN_LETTER__MAIL")+
            ('A'..'Z').map {"SIGN_LETTER_${it}_WOLF3D_PREVIEW"}
        assertEquals(expected,protected.keySet())
        for((name,hash) in protected.entrySet()) {
            val animation=document.getAsJsonArray("animations").single {it.asJsonObject.get("name").asString==name}
            val actual=MessageDigest.getInstance("SHA-256").digest(animation.toString().toByteArray()).joinToString(""){"%02x".format(it)}
            assertEquals("Preserved action $name",hash.asString,actual)
        }
    }
}
