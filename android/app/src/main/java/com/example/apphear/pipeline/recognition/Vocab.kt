package com.example.apphear.pipeline.recognition

import android.content.Context
import org.json.JSONObject

/** Gloss vocabulary — id -> gloss lookup, loaded from assets/vocab.json (the {gloss: id} map the
 * model was trained against). The class-index the model emits maps back to a human gloss here. */
class Vocab private constructor(private val idToGloss: Array<String>) {

    val size: Int get() = idToGloss.size

    fun gloss(id: Int): String = if (id in idToGloss.indices) idToGloss[id] else "?"

    companion object {
        fun load(context: Context): Vocab {
            val text = context.assets.open("vocab.json").bufferedReader().use { it.readText() }
            val obj = JSONObject(text)
            val keys = obj.keys()
            var maxId = -1
            val pairs = ArrayList<Pair<String, Int>>(obj.length())
            while (keys.hasNext()) {
                val g = keys.next()
                val id = obj.getInt(g)
                pairs.add(g to id)
                if (id > maxId) maxId = id
            }
            val arr = Array(maxId + 1) { "?" }
            for ((g, id) in pairs) arr[id] = g
            return Vocab(arr)
        }
    }
}
