package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Technical correction boundary; does not validate ASL meaning or contact. */
class AslFlatBaseHandCorrectionTest {
    @Test fun onlySixFlatSupportingHandsChangeWhileThumbsBodyAndTimingRemainOriginal() {
        val root=Path.of("src/aslOriginalWords/assets")
        fun document(path:String):com.google.gson.JsonObject {
            val bytes=Files.readAllBytes(root.resolve(path))
            return JsonParser.parseString(String(bytes,20,ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
        }
        val original=document(AslResidentAvatarBundle.PATH)
        val current=document(AslFingerspellingBundle.PATH)
        val expected=setOf("SIGN_COOK","SIGN_BECOME","SIGN_MONEY","SIGN_NEW","SIGN_SOME","SIGN_DAY")
        val registry=JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
        val correction=registry.getAsJsonObject("flatBaseHandCorrection")
        assertFalse(correction.get("qualifiedASLValidation").asBoolean)
        assertEquals(expected,correction.getAsJsonArray("profiles").map { it.asJsonObject.get("animationName").asString }.toSet())
        val allowed=listOf("Index","Middle","Ring","Pinky").flatMap { f -> (1..3).map { j -> "LeftHand$f$j" } }.toSet()
        val originals=original.getAsJsonArray("animations").associateBy { it.asJsonObject.get("name").asString }
        for(action in current.getAsJsonArray("animations").filter { it.asJsonObject.get("name").asString in expected }) {
            val new=action.asJsonObject;val old=originals.getValue(new.get("name").asString).asJsonObject
            val oldSamplers=old.getAsJsonArray("samplers")
            assertTrue("Original samplers preserved",oldSamplers.toList()==new.getAsJsonArray("samplers").take(oldSamplers.size()))
            val changed=mutableSetOf<String>()
            old.getAsJsonArray("channels").zip(new.getAsJsonArray("channels")).forEach { (a,b) ->
                val target=a.asJsonObject.getAsJsonObject("target")
                assertTrue("Target mapping preserved",target==b.asJsonObject.get("target"))
                if(a!=b) {
                    val name=current.getAsJsonArray("nodes")[target.get("node").asInt].asJsonObject.get("name").asString
                    changed+=name;assertEquals("rotation",target.get("path").asString)
                    val os=oldSamplers[a.asJsonObject.get("sampler").asInt].asJsonObject
                    val ns=new.getAsJsonArray("samplers")[b.asJsonObject.get("sampler").asInt].asJsonObject
                    assertEquals("Source times unchanged",os.get("input"),ns.get("input"))
                }
            }
            assertEquals(allowed,changed)
        }
        for(key in listOf("nodes","skins","meshes","materials","textures","images","scenes"))
            assertTrue("Unchanged rig/mesh: $key",original.get(key)==current.get(key))
    }
}
