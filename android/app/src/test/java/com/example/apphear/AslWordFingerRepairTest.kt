package com.example.apphear

import com.example.apphear.domain.texttoasl.AslFingerspellingBundle
import com.example.apphear.domain.texttoasl.AslResidentAvatarBundle
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Integrity and coordinate checks, not sign-language validation. */
class AslWordFingerRepairTest {
    private val root=Path.of("src/aslOriginalWords/assets")
    private val bytes=Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
    private val bb=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    private fun document(b:ByteArray)=JsonParser.parseString(String(b,20,ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
    private val g=document(bytes)
    private val old=document(Files.readAllBytes(root.resolve(AslResidentAvatarBundle.PATH)))
    private val manifest=JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
    private fun animation(g:JsonObject,name:String)=g.getAsJsonArray("animations").single { it.asJsonObject.get("name").asString==name }.asJsonObject
    private fun values(index:Int):List<List<Double>> {
        val a=g.getAsJsonArray("accessors")[index].asJsonObject
        val view=g.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
        val width=if(a.get("type").asString=="SCALAR") 1 else 4
        val offset=28+bb.getInt(12)+(view.get("byteOffset")?.asInt?:0)+(a.get("byteOffset")?.asInt?:0)
        return (0 until a.get("count").asInt).map { n -> (0 until width).map { j -> bb.getFloat(offset+4*(n*width+j)).toDouble() } }
    }
    private fun delta(base:List<Double>,q:List<Double>):List<Double> {
        val a=listOf(-base[0],-base[1],-base[2],base[3]); val b=q
        val r=listOf(a[3]*b[0]+b[3]*a[0]+a[1]*b[2]-a[2]*b[1],
            a[3]*b[1]+b[3]*a[1]+a[2]*b[0]-a[0]*b[2],
            a[3]*b[2]+b[3]*a[2]+a[0]*b[1]-a[1]*b[0],
            a[3]*b[3]-a[0]*b[0]-a[1]*b[1]-a[2]*b[2])
        return if(r[3]<0) r.map { -it } else r
    }

    @Test fun onlyExplicitFingerProfilesChangeAndThumbsBodyTimesAndEndpointsArePreserved() {
        val correction=manifest.getAsJsonObject("wordFingerCorrection")
        assertFalse(correction.get("qualifiedASLValidation").asBoolean)
        assertEquals("UNREVIEWED_FLEXION_AXIS_CORRECTION",correction.get("status").asString)
        val profiles=mapOf("SIGN_LOVE" to listOf("Left","Right"),"SIGN_HUSBAND" to listOf("Left"),"SIGN_WIFE" to listOf("Left"))
        assertEquals(profiles.keys,correction.getAsJsonArray("profiles").map { it.asJsonObject.get("animationName").asString }.toSet())
        var repaired=0
        for((name,sides) in profiles.filterKeys {it!="SIGN_LOVE"}) {
            val before=animation(old,name);val after=animation(g,name)
            val expected=sides.flatMap { side -> listOf("Index","Middle","Ring","Pinky").flatMap { f -> (1..3).map { j -> side+"Hand"+f+j } } }.toSet()
            before.getAsJsonArray("channels").zip(after.getAsJsonArray("channels")).forEach { (x,y) ->
                val target=x.asJsonObject.getAsJsonObject("target");assertEquals(target,y.asJsonObject.get("target"))
                val node=g.getAsJsonArray("nodes")[target.get("node").asInt].asJsonObject
                val nodeName=node.get("name").asString
                val finger=target.get("path").asString=="rotation" && nodeName in expected
                if(!finger) {
                    val contact=name=="SIGN_LOVE" && target.get("path").asString=="rotation" && nodeName in setOf("LeftArm","LeftForeArm","LeftHand","RightArm","RightForeArm","RightHand")
                    if(!contact) assertEquals(x,y)
                } else {
                    repaired++
                    val os=before.getAsJsonArray("samplers")[x.asJsonObject.get("sampler").asInt].asJsonObject
                    val ns=after.getAsJsonArray("samplers")[y.asJsonObject.get("sampler").asInt].asJsonObject
                    assertEquals(os.get("input"),ns.get("input"))
                    val oq=values(os.get("output").asInt);val nq=values(ns.get("output").asInt)
                    for((a,b) in listOf(oq.first() to nq.first(),oq.last() to nq.last())) {
                        assertEquals(1.0,kotlin.math.abs(a.zip(b).sumOf { (u,v)->u*v }),.00001)
                    }
                }
            }
        }
        assertEquals(24,repaired)
    }

    @Test fun retainedWifeAndHusbandRepairsReflectOnlyBindRelativeFlexionAndKeepQuaternionsValid() {
        // LOVE's former reflection has been superseded by the scoped YES-pose
        // repair; its donor and preservation boundary have a separate test.
        for(name in listOf("SIGN_HUSBAND","SIGN_WIFE")) {
            val before=animation(old,name);val after=animation(g,name)
            before.getAsJsonArray("channels").zip(after.getAsJsonArray("channels")).forEach { (x,y) ->
                val target=x.asJsonObject.getAsJsonObject("target")
                val node=g.getAsJsonArray("nodes")[target.get("node").asInt].asJsonObject
                if(x!=y && node.get("name").asString.contains("Hand") && node.get("name").asString.last().isDigit()) {
                    val os=before.getAsJsonArray("samplers")[x.asJsonObject.get("sampler").asInt].asJsonObject
                    val ns=after.getAsJsonArray("samplers")[y.asJsonObject.get("sampler").asInt].asJsonObject
                    val times=values(os.get("input").asInt).map { it.single() }
                    val oq=values(os.get("output").asInt);val nq=values(ns.get("output").asInt)
                    val base=node.getAsJsonArray("rotation").map { it.asDouble }
                    for(i in times.indices) {
                        assertEquals(1.0,nq[i].sumOf { it*it },.00001)
                        if(times[i]>=.18 && times[i]<=times.last()-.18) {
                            val a=delta(base,oq[i]);val b=delta(base,nq[i])
                            assertEquals(kotlin.math.abs(a[0]),b[0],.00001)
                            for(j in 1..3) assertEquals(a[j],b[j],.00001)
                        }
                    }
                }
            }
        }
    }
}
