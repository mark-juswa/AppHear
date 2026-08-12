package com.example.apphear.pipeline.recognition

/**
 * Tracks evidence that the signer has departed from the last committed class. This component never
 * decides that a word is valid enough to commit; a freshly reset [Confirmation] remains solely
 * responsible for that decision.
 */
class PostCommitRearm(private val departureFrames: Int) {
    init {
        require(departureFrames > 0) { "departureFrames must be measured and set to > 0" }
    }

    sealed interface DepartureUpdate {
        data object None : DepartureUpdate
        data class CandidateStarted(val classId: Int) : DepartureUpdate
        data class CandidateCancelled(val classId: Int) : DepartureUpdate
        data class Armed(val classId: Int, val frames: Int) : DepartureUpdate
    }

    data class Snapshot(
        val lastCommittedClass: Int,
        val departureCandidate: Int?,
        val departureStreak: Int,
        val armedClass: Int?,
    )

    private var lastCommittedClass = -1
    private var departureCandidate = -1
    private var departureCount = 0

    var armedClass: Int? = null
        private set

    val isVerifying: Boolean get() = armedClass != null

    val snapshot: Snapshot
        get() = Snapshot(
            lastCommittedClass = lastCommittedClass,
            departureCandidate = departureCandidate.takeIf { it >= 0 },
            departureStreak = departureCount,
            armedClass = armedClass,
        )

    fun onCommit(classId: Int) {
        lastCommittedClass = classId
        clearDeparture()
        armedClass = null
    }

    fun observe(top1Class: Int): DepartureUpdate {
        check(lastCommittedClass >= 0) { "onCommit must be called before observing departure" }
        check(!isVerifying) { "departure cannot be observed while verification is active" }

        if (top1Class == lastCommittedClass) {
            if (departureCandidate < 0) return DepartureUpdate.None
            val cancelled = departureCandidate
            clearDeparture()
            return DepartureUpdate.CandidateCancelled(cancelled)
        }

        if (top1Class != departureCandidate) {
            departureCandidate = top1Class
            departureCount = 1
            if (departureCount >= departureFrames) return arm(top1Class)
            return DepartureUpdate.CandidateStarted(top1Class)
        }

        departureCount++
        return if (departureCount >= departureFrames) arm(top1Class) else DepartureUpdate.None
    }

    /** Returns true only when full S7 confirmation agrees with the independently armed class. */
    fun matchesVerifiedClass(classId: Int): Boolean = armedClass == classId

    /** Keep the prior commit locked and require a new departure observation after a mismatch. */
    fun verificationFailed() {
        clearDeparture()
        armedClass = null
    }

    fun reset() {
        lastCommittedClass = -1
        clearDeparture()
        armedClass = null
    }

    private fun arm(classId: Int): DepartureUpdate.Armed {
        armedClass = classId
        val observed = departureCount
        clearDeparture()
        return DepartureUpdate.Armed(classId, observed)
    }

    private fun clearDeparture() {
        departureCandidate = -1
        departureCount = 0
    }
}
