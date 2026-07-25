package com.example.aslrecorder.ml;

/**
 * REMOVED in the AppHear 3 Stage-E rewrite. Clips are no longer a fixed 30-frame landmark buffer —
 * the recorder captures a full-duration VIDEO and the offline D1/D2 stage trims onset→release.
 * Empty placeholder (file could not be deleted in-tool); safe to delete.
 */
@Deprecated
public final class LandmarkFrameBuffer {
    private LandmarkFrameBuffer() {}
}
