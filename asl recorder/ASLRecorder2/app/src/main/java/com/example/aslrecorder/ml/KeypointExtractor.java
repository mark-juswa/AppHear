package com.example.aslrecorder.ml;

/**
 * REMOVED in the AppHear 3 Stage-E rewrite. The recorder no longer bakes a normalized 258-vector
 * on-device — it records VIDEO and the offline Python pipeline extracts + normalizes it (the same
 * path as ASL Citizen). This empty placeholder exists only because the file could not be deleted
 * in-tool; safe to delete the file.
 */
@Deprecated
public final class KeypointExtractor {
    private KeypointExtractor() {}
}
