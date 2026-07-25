package com.example.aslrecorder.model;

import java.util.ArrayList;
import java.util.List;

/**
 * On-device coverage summary for one recorded clip — ADVISORY only (video-primary, non-destructive).
 * Every clip is kept; the offline Q stage + human review are the real gate. Low hand/pose coverage
 * is surfaced as a warning so the operator can choose to re-record, but nothing auto-rejects.
 */
public class QualityResult {

    public final int handFrames;
    public final int poseFrames;
    public final int totalFrames;
    public final List<String> warnings;

    public QualityResult(int handFrames, int poseFrames, int totalFrames, List<String> warnings) {
        this.handFrames  = handFrames;
        this.poseFrames  = poseFrames;
        this.totalFrames = totalFrames;
        this.warnings    = warnings != null ? warnings : new ArrayList<>();
    }

    public float handHitRate() { return totalFrames > 0 ? (float) handFrames / totalFrames : 0f; }
    public float poseHitRate() { return totalFrames > 0 ? (float) poseFrames / totalFrames : 0f; }

    /** Advisory: is coverage good enough that a re-record is probably unnecessary? */
    public boolean coverageOk() {
        return totalFrames > 0 && handHitRate() >= 0.5f && poseHitRate() >= 0.7f;
    }
}
