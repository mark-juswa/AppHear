package com.example.apphear.perceptionvnext

/** Navigation blocks only; none of these markers resets the inference stream. */
internal object PhoneTransitionDiagnosticCohort {
    const val MILESTONE = "APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01"
    const val BASELINE_SHA = "76d93cecd85bf9f76064d320aa4a5791b5f0704a"
    val blocks = listOf(
        "A_HANDS_DOWN",
        "B_HANDS_UP",
        "NEG_OPEN_HAND_HOLD",
        "NEG_SEAT_BODY_REPOSITION",
        "NEG_STANDING_MOVING",
        "NEG_GROOMING_ADJUSTMENT",
        "NEG_PHONE_INTERACTION",
    )
    val instructions = listOf(
        "HELLO → hands down → HOME → hands down → TABLE → hands down → HELLO. No deliberate READY wait within the sequence.",
        "HELLO → HOME → TABLE → HELLO. Keep hands in signing space; no deliberate READY wait or hands-down reset.",
        "Raise and hold an open hand without a lexical sign, then return naturally.",
        "Adjust your seat/body normally, without signing.",
        "Stand/move normally, without signing.",
        "One ordinary grooming/clothing adjustment, without signing.",
        "One ordinary phone interaction, without signing.",
    )
}
