package com.example.aslrecorder.ml;

/**
 * REMOVED in the AppHear 3 Stage-E rewrite. On-device quality is now ADVISORY only (hand/pose
 * coverage in RecordingActivity); the authoritative Q gate is the offline pipeline's Q stage, which
 * runs on the re-extracted video. Nothing is auto-rejected at capture (non-destructive). Empty
 * placeholder (file could not be deleted in-tool); safe to delete.
 */
@Deprecated
public final class SampleQualityAnalyzer {
    private SampleQualityAnalyzer() {}
}
