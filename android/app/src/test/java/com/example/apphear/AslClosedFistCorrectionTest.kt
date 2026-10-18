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

/** Scope and data regression gate; not linguistic validation. */
class AslClosedFistCorrectionTest {
    @Test fun yesAndPointingIndexBodyAndAlphabetAreNotReplacedByAFistConstraint() {
        val root=Path.of("src/aslOriginalWords/assets")
        fun doc(path:String):JsonObject {
            val bytes=Files.readAllBytes(root.resolve(path))
            return JsonParser.parseString(String(bytes,20,ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        }
        val original=doc(AslResidentAvatarBundle.PATH)
        val current=doc(AslFingerspellingBundle.PATH)
        val registry=JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
        val metadata=registry.getAsJsonObject("closedFistCorrection")
        // The later, separately tested pointing repair deliberately extends ME's
        // index and adjusts its right arm. Keep the older donor provenance check.
        val pointingNodes=registry.getAsJsonObject("pointingCorrection").getAsJsonArray("profiles")
            .single {it.asJsonObject.get("animationName").asString=="SIGN_I"}.asJsonObject
            .getAsJsonArray("changedNodes").map {it.asString}.toSet()
        assertFalse(metadata.get("qualifiedASLValidation").asBoolean)
        assertEquals("SIGN_YES",metadata.get("donorAnimation").asString)
        val profiles=metadata.getAsJsonArray("profiles").associate { it.asJsonObject.get("animationName").asString to it.asJsonObject.getAsJsonArray("correctedNodes").map { n->n.asString }.toSet() }
        assertEquals(setOf("SIGN_I","SIGN_LOVE"),profiles.keys)
        assertEquals(listOf("Thumb","Middle","Ring","Pinky").flatMap { f->(1..3).map {j->"RightHand$f$j"} }.toSet(),profiles["SIGN_I"])
        assertEquals(listOf("Left","Right").flatMap { s->listOf("Thumb","Index","Middle","Ring","Pinky").flatMap { f->(1..3).map {j->"${s}Hand$f$j"} } }.toSet(),profiles["SIGN_LOVE"])
        val old=original.getAsJsonArray("animations").associateBy {it.asJsonObject.get("name").asString}
        val now=current.getAsJsonArray("animations").associateBy {it.asJsonObject.get("name").asString}
        assertTrue("YES donor remains exact original",old["SIGN_YES"]==now["SIGN_YES"])
        assertEquals(26,now.keys.count {it.startsWith("SIGN_LETTER_") && it.endsWith("_WOLF3D_PREVIEW")})
        for((name,allowed) in profiles) {
            val a=old.getValue(name).asJsonObject;val b=now.getValue(name).asJsonObject
            for((oc,nc) in a.getAsJsonArray("channels").zip(b.getAsJsonArray("channels"))) {
                val target=oc.asJsonObject.getAsJsonObject("target")
                assertTrue(target==nc.asJsonObject.get("target"))
                val bone=current.getAsJsonArray("nodes")[target.get("node").asInt].asJsonObject.get("name").asString
                if(bone in allowed) {
                    val os=a.getAsJsonArray("samplers")[oc.asJsonObject.get("sampler").asInt].asJsonObject
                    val ns=b.getAsJsonArray("samplers")[nc.asJsonObject.get("sampler").asInt].asJsonObject
                    assertEquals("Original source times: $bone",os.get("input"),ns.get("input"))
                }else if(name=="SIGN_I") {
                    if(oc!=nc) {
                        assertTrue("Only audited ME bones change: $bone",bone in pointingNodes)
                        assertEquals("Only audited pointer rotations: $bone","rotation",target.get("path").asString)
                    }
                }
            }
        }
        for(key in listOf("nodes","skins","meshes","materials","textures","images","scenes"))assertTrue(original.get(key)==current.get(key))
    }
}
