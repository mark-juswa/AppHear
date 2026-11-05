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

    fun scenarios(): List<DemoScenario> = load(app)
    fun topics(): List<DemoTopic> = loadTopics(app)

    companion object {
        val available: Boolean get() = BuildConfig.GUIDED_DEMO_ENABLED
        private const val KEY_ENABLED = "enabled"
        private const val KEY_PRESENTER = "presenter_only"
        private const val ASSET = "guided_demo/scenarios_v1.json"
        @Volatile private var cached: List<DemoScenario>? = null
        @Volatile private var cachedTopics: List<DemoTopic>? = null
        private const val TOPICS_ASSET = "guided_demo/topics_v1.json"

        fun loadTopics(context: Context): List<DemoTopic> = cachedTopics ?: synchronized(this) {
            cachedTopics ?: parseTopics(context.assets.open(TOPICS_ASSET).bufferedReader().use { it.readText() })
                .also { cachedTopics = it }
        }

        private fun parseTopics(text: String): List<DemoTopic> {
            val root = JSONObject(text)
            check(root.getInt("schemaVersion") == 1) { "guided demo: unknown topics schema" }
            val list = root.getJSONArray("topics")
            return (0 until list.length()).map { i ->
                val topic = list.getJSONObject(i)
                val questions = topic.getJSONArray("questions")
                DemoTopic(topic.getString("id"), topic.getString("title"), (0 until questions.length()).map { j ->
                    val q = questions.getJSONObject(j)
                    val phrasings = q.getJSONArray("phrasings")
                    val alternatives = q.optJSONArray("alternatives")
                    DemoQuestion(q.getString("id"), (0 until phrasings.length()).map { phrasings.getString(it) },
                        q.getString("answer"), q.getString("gloss"), q.optBoolean("spell"),
                        (0 until (alternatives?.length() ?: 0)).map { k ->
                            alternatives!!.getJSONObject(k).let { DemoAnswer(it.getString("answer"), it.getString("gloss")) }
                        },
                        q.optJSONArray("known").let { list -> (0 until (list?.length() ?: 0)).map { list!!.getString(it) } })
                })
            }
        }

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
                            spell = step.optBoolean("spell"),
                        )
                    },
                )
            }
        }
    }
}
