package com.example.apphear

import com.example.apphear.domain.texttoasl.*
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path
import org.junit.Assert.*
import org.junit.Test

/** Technical scope/integrity checks; these are not linguistic validation. */
class AslLoveContactTest {
    private val root = Path.of("src/aslOriginalWords/assets")
    private fun document(path: String): JsonObject {
        val b = Files.readAllBytes(root.resolve(path))
        return JsonParser.parseString(String(b, 20, ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getInt(12))).asJsonObject
    }

    @Test fun correctionChangesOnlyAuditedLoveArmAndFingerRotations() {
        val old = document(AslResidentAvatarBundle.PATH)
        val new = document(AslFingerspellingBundle.PATH)
        fun love(g: JsonObject) = g.getAsJsonArray("animations").single {
            it.asJsonObject.get("name").asString == "SIGN_LOVE"
        }.asJsonObject
        val a = love(old); val b = love(new)
        val originalSamplers = a.getAsJsonArray("samplers")
        assertEquals(originalSamplers.toList(), b.getAsJsonArray("samplers").take(originalSamplers.size()))
        val ac = a.getAsJsonArray("channels"); val bc = b.getAsJsonArray("channels")
        assertEquals(ac.size(), bc.size())
        val changed = mutableSetOf<String>()
        ac.zip(bc).forEach { (x, y) ->
            val xt = x.asJsonObject.getAsJsonObject("target")
            assertEquals(xt, y.asJsonObject.get("target"))
            if (x != y) {
                assertEquals("rotation", xt.get("path").asString)
                changed += new.getAsJsonArray("nodes")[xt.get("node").asInt].asJsonObject.get("name").asString
                assertTrue(y.asJsonObject.get("sampler").asInt >= originalSamplers.size())
            }
        }
        val arms=setOf("LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand")
        val fingers=listOf("Left","Right").flatMap { side -> listOf("Thumb","Index","Middle","Ring","Pinky").flatMap { f ->
            (1..3).map { j -> side+"Hand"+f+j }
        } }.toSet()
        assertEquals(arms+fingers, changed)
        for (key in listOf("nodes", "skins", "meshes", "materials", "textures", "images", "scenes")) {
            assertEquals(key, old.get(key), new.get(key))
        }
        val manifest = JsonParser.parseString(String(Files.readAllBytes(root.resolve(AslFingerspellingBundle.MANIFEST)))).asJsonObject
        val correction = manifest.getAsJsonObject("loveCorrection")
        assertEquals("UNREVIEWED_CONTACT_CORRECTION", correction.get("status").asString)
        assertTrue(correction.getAsJsonObject("afterDepthMeters").get("hand").asDouble < .002)
    }

    @Test fun correctiveRotationsHaveStrictTimesUnitQuaternionsAndSourceEndpoints() {
        val bytes = Files.readAllBytes(root.resolve(AslFingerspellingBundle.PATH))
        val g = document(AslFingerspellingBundle.PATH)
        val bb = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val binaryOffset = 20 + bb.getInt(12) + 8
        fun values(index: Int): List<Float> {
            val accessor = g.getAsJsonArray("accessors")[index].asJsonObject
            val view = g.getAsJsonArray("bufferViews")[accessor.get("bufferView").asInt].asJsonObject
            assertEquals(5126, accessor.get("componentType").asInt)
            val width = if (accessor.get("type").asString == "SCALAR") 1 else 4
            val offset = binaryOffset + (view.get("byteOffset")?.asInt ?: 0) + (accessor.get("byteOffset")?.asInt ?: 0)
            return (0 until accessor.get("count").asInt * width).map { bb.getFloat(offset + it * 4) }
        }
        val a = g.getAsJsonArray("animations").single { it.asJsonObject.get("name").asString == "SIGN_LOVE" }.asJsonObject
        val original = document(AslResidentAvatarBundle.PATH).getAsJsonArray("animations").single {
            it.asJsonObject.get("name").asString == "SIGN_LOVE"
        }.asJsonObject
        // Finger corrections append after the six preserved contact tracks.
        val samplers = a.getAsJsonArray("samplers").toList().drop(original.getAsJsonArray("samplers").size()).take(6)
        for (sampler in samplers) {
            val s = sampler.asJsonObject
            val times = values(s.get("input").asInt)
            assertTrue(times.zipWithNext().all { (x, y) -> y > x })
            assertEquals(0f, times.first(), 0f)
            assertEquals(2.1666667f, times.last(), .00001f)
            for (q in values(s.get("output").asInt).chunked(4)) {
                assertEquals(1.0, q.sumOf { it.toDouble() * it }, .00001)
            }
            val index = a.getAsJsonArray("samplers").indexOf(sampler)
            val channelIndex = a.getAsJsonArray("channels").indexOfFirst { it.asJsonObject.get("sampler").asInt == index }
            val oldSamplerIndex = original.getAsJsonArray("channels")[channelIndex].asJsonObject.get("sampler").asInt
            val oldSampler = original.getAsJsonArray("samplers")[oldSamplerIndex].asJsonObject
            val oldQ = values(oldSampler.get("output").asInt).chunked(4)
            val newQ = values(s.get("output").asInt).chunked(4)
            for ((x, y) in listOf(oldQ.first() to newQ.first(), oldQ.last() to newQ.last())) {
                assertEquals(1.0, kotlin.math.abs(x.zip(y).sumOf { (u, v) -> u.toDouble() * v }), .00001)
            }
        }
    }
}
