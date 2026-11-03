package com.example.apphear.demo

import android.content.Context
import com.example.apphear.BuildConfig
import org.json.JSONObject

/** Guided demo choices from Settings, and the scenario library from assets. */
class GuidedDemoSettings(context: Context) {
    private val app = context.applicationContext
    private val preferences = app.getSharedPreferences("apphear_guided_demo", Context.MODE_PRIVATE)

    /** Shows the demo button on the Recognition screen. Off unless turned on in Settings. */
    var enabled: Boolean
        get() = available && preferences.getBoolean(KEY_ENABLED, false)
        set(value) { preferences.edit().putBoolean(KEY_ENABLED, value).apply() }

    /** Only NEXT / volume keys / clicker move the demo on; the camera does not pace it. */
    var presenterOnly: Boolean
        get() = preferences.getBoolean(KEY_PRESENTER, false)
        set(value) { preferences.edit().putBoolean(KEY_PRESENTER, value).apply() }

    /** The details scenarios fill in; blank means "use the default". */
    var values: Map<String, String>
        get() = DemoValues.defaults.keys.associateWith { preferences.getString("value_$it", "").orEmpty() }
        set(value) {
            val edit = preferences.edit()
            DemoValues.defaults.keys.forEach { key -> edit.putString("value_$key", value[key].orEmpty().trim().take(DemoValues.MAX_VALUE)) }
            edit.apply()
        }

    fun scenarios(): List<DemoScenario> = load(app)

    companion object {
        val available: Boolean get() = BuildConfig.GUIDED_DEMO_ENABLED
        private const val KEY_ENABLED = "enabled"
        private const val KEY_PRESENTER = "presenter_only"
        private const val ASSET = "guided_demo/scenarios_v1.json"
        @Volatile private var cached: List<DemoScenario>? = null

        fun load(context: Context): List<DemoScenario> = cached ?: synchronized(this) {
            cached ?: parse(context.assets.open(ASSET).bufferedReader().use { it.readText() }).also { cached = it }
        }

        private fun parse(text: String): List<DemoScenario> {
            val root = JSONObject(text)
            check(root.getInt("schemaVersion") == 1) { "guided demo: unknown scenario schema" }
            val list = root.getJSONArray("scenarios")
            return (0 until list.length()).map { i ->
                val scenario = list.getJSONObject(i)
                val steps = scenario.getJSONArray("steps")
                DemoScenario(
                    id = scenario.getString("id"), title = scenario.getString("title"),
                    category = scenario.optString("category"),
                    steps = (0 until steps.length()).map { j ->
                        val step = steps.getJSONObject(j)
                        DemoStep(
                            speaker = if (step.getString("who") == "signer") DemoSpeaker.SIGNER else DemoSpeaker.HEARING,
                            text = step.getString("text"),
                            gloss = step.optString("gloss").takeIf { it.isNotBlank() },
                            avatar = step.optString("avatar").takeIf { it.isNotBlank() },
                        )
                    },
                )
            }
        }
    }
}
