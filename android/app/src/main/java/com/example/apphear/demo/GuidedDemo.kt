package com.example.apphear.demo

/**
 * Where a guided demo is: the scenario, the current step, and whether the current signer step's
 * message has been put on screen yet. Pure; the Android controller reacts to it.
 */
data class DemoRun(
    val scenario: DemoScenario,
    val index: Int = 0,
    /** Signer step: its scripted message is on screen (waiting to be said, or being said). */
    val shown: Boolean = false,
) {
    val step: DemoStep? get() = scenario.steps.getOrNull(index)
    val finished: Boolean get() = index >= scenario.steps.size
    val nextStep: DemoStep? get() = scenario.steps.getOrNull(index + 1)

    /** The signer's message for this step went on screen. */
    fun showing(): DemoRun = if (step?.speaker == DemoSpeaker.SIGNER) copy(shown = true) else this

    /** The current step is complete; move to the next one (or finish). */
    fun advance(): DemoRun = if (finished) this else copy(index = index + 1, shown = false)

    /** Do the current step again (the presenter's "again" key). */
    fun again(): DemoRun = copy(shown = false)

    /** Position for the card, e.g. "3 of 8". */
    val progress: Pair<Int, Int> get() = (index + 1).coerceAtMost(scenario.steps.size) to scenario.steps.size
}
