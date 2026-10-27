package com.example.apphear

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import org.junit.Assert.*

/** Supersedes historical pins only after checking an explicitly reviewed action. */
internal object WordHandRepairEvidence {
    val fixture: JsonObject = JsonParser.parseString(
        javaClass.getResource("/texttoasl/word-hand-repair-gates.json")!!.readText()
    ).asJsonObject
    val actions = fixture.getAsJsonArray("actions").associate { it.asJsonObject.let { e -> e.get("name").asString to e } }

    fun digest(g: JsonObject, bytes: ByteArray, action: JsonObject,
               mode: String = "full", excluded: Set<String> = emptySet()): String {
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val hash = MessageDigest.getInstance("SHA-256")
        fun raw(index: Int): ByteArray {
            val a = g.getAsJsonArray("accessors")[index].asJsonObject
            val v = g.getAsJsonArray("bufferViews")[a.get("bufferView").asInt].asJsonObject
            val width = when (a.get("type").asString) { "SCALAR" -> 1; "VEC3" -> 3; "VEC4" -> 4; else -> error("Animation accessor") }
            val start = 28 + buffer.getInt(12) + (v.get("byteOffset")?.asInt ?: 0) + (a.get("byteOffset")?.asInt ?: 0)
            val stride = v.get("byteStride")?.asInt ?: width * 4
            return ByteArray(a.get("count").asInt * width * 4).also { out ->
                for (i in 0 until a.get("count").asInt)
                    bytes.copyInto(out, i * width * 4, start + i * stride, start + i * stride + width * 4)
            }
        }
        for (channel in action.getAsJsonArray("channels")) {
            val ch = channel.asJsonObject
            val target = ch.getAsJsonObject("target")
            val node = target.get("node").asInt
            val path = target.get("path").asString
            val bone = g.getAsJsonArray("nodes")[node].asJsonObject.get("name").asString
            if (mode == "protected" && path == "rotation" && bone in excluded) continue
            hash.update("$node:$path\u0000".toByteArray(Charsets.UTF_8))
            val sampler = action.getAsJsonArray("samplers")[ch.get("sampler").asInt].asJsonObject
            hash.update(raw(sampler.get("input").asInt))
            if (mode != "clock") hash.update(raw(sampler.get("output").asInt))
        }
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    fun accepts(name: String, g: JsonObject, bytes: ByteArray): Boolean {
        val e = actions[name] ?: return false
        if (!e.get("changed").asBoolean) return false
        assertFalse("Alphabet cannot be exempted", name.startsWith("SIGN_LETTER_"))
        assertNotEquals("SIGN_RELAXED_NEUTRAL", name)
        val action = g.getAsJsonArray("animations").single { it.asJsonObject.get("name").asString == name }.asJsonObject
        assertEquals("Explicit repair hash: $name", e.get("sha256").asString, digest(g, bytes, action))
        return true
    }
}
