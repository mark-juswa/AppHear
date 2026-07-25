package com.example.aslrecorder.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.List;
import java.util.UUID;

/**
 * One recorded ASL clip in the AppHear 3 Stage-E capture contract.
 *
 * <p><b>Video-primary:</b> the recorded {@code .mp4} is the dataset artifact (like ASL Citizen,
 * which IS a video dataset). The offline Python pipeline re-extracts landmarks from it with the
 * SAME IMAGE-mode extractor used for ASL Citizen → guaranteed identical landmark dialect. This
 * sidecar carries only <b>metadata</b> — NOT baked features. (The removed AppHear 2 version stored
 * a normalized {@code frames[30][258]} vector that was incompatible with our v3.0 contract.)
 *
 * <p><b>Non-destructive:</b> every recording is saved; on-device coverage stats are advisory (QC
 * only). The offline Q gate + human review decide what enters training.
 */
public class SampleData {

    public String sampleId;

    // Label: the English WORD the signer performed + its canonical ASL Citizen GLOSS (from
    // labels.json). The pipeline merges this clip into the `gloss` class. gloss may be null for
    // pointing/particle words with no lexical sign, or new words not in ASL Citizen.
    public String word;
    public String gloss;
    public String signLanguage = "ASL";

    // Provenance / split
    public String signerId;
    public String sessionId;
    public String recordingDate;
    public int    repetitionIndex;
    public String source = "aslrecorder2";   // sidecar `source` field the pipeline expects

    // Recording conditions (rich metadata → future condition ablations)
    public String cameraDirection = "front";
    public String speed;
    public String posture;
    public int    distanceCm;
    public String lighting;
    public String background;
    public String shirtColor;
    public String dominantHand;

    // Capture technicals (the pipeline reads native_fps + dims)
    public String videoFilename;             // primary artifact (relative to label's video/ dir)
    public double nativeFps;
    public int    frameWidth;
    public int    frameHeight;

    // On-device coverage — QC/advisory ONLY, never gates (offline Q stage is the real gate)
    public int    totalFrames;
    public int    handFrames;
    public int    poseFrames;
    public List<String> qualityWarnings;

    // Review (non-destructive: everything saved; reviewer can flag)
    public boolean accepted = true;          // default keep; human/offline review may override
    public String  reviewerNotes;

    // Background / rest class
    public boolean isBackground;
    public String  bgScenario;

    public String mediapipeVersion = "0.10.14";
    public String appVersion       = "asl_recorder_v2_stageE";

    public SampleData() {
        this.sampleId = UUID.randomUUID().toString();
    }

    public static SampleData build(SessionConfig config, SignerProfile signer,
                                   String gloss, int repetitionIndex) {
        SampleData s = new SampleData();
        s.word            = config.signLabel;
        s.gloss           = gloss;
        s.signLanguage    = config.signLanguage;
        s.signerId        = config.signerId;
        s.sessionId       = config.getSessionId();
        s.recordingDate   = config.recordingDate;
        s.repetitionIndex = repetitionIndex;
        s.speed           = config.speed;
        s.posture         = config.posture;
        s.distanceCm      = config.distanceCm;
        s.lighting        = config.lighting;
        s.background      = config.backgroundType;
        s.shirtColor      = config.shirtColor;
        s.dominantHand    = signer != null ? signer.dominantHand : null;
        s.isBackground    = config.isBackground;
        s.bgScenario      = config.bgScenario;
        return s;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject o = new JSONObject();
        o.put("schema_stage",     "E");        // AppHear 3 raw-capture stage
        o.put("schema_version",   "3.0");
        o.put("source",           source);     // "aslrecorder2"
        o.put("sample_id",        sampleId);

        o.put("word",             word);
        o.put("gloss",            gloss != null ? gloss : JSONObject.NULL);
        o.put("sign_language",    signLanguage);

        o.put("signer_id",        signerId);
        o.put("session_id",       sessionId);
        o.put("recording_date",   recordingDate);
        o.put("repetition_index", repetitionIndex);
        o.put("camera_direction", cameraDirection);

        o.put("speed",            speed);
        o.put("posture",          posture);
        o.put("distance_cm",      distanceCm);
        o.put("lighting",         lighting);
        o.put("background",       background);
        o.put("shirt_color",      shirtColor != null ? shirtColor : "");
        o.put("dominant_hand",    dominantHand != null ? dominantHand : JSONObject.NULL);

        o.put("video_file",       videoFilename != null ? videoFilename : JSONObject.NULL);
        o.put("native_fps",       nativeFps);
        o.put("frame_width",      frameWidth);
        o.put("frame_height",     frameHeight);

        // coverage (advisory)
        o.put("total_frames",     totalFrames);
        o.put("hand_hit_rate",    totalFrames > 0 ? (double) handFrames / totalFrames : 0.0);
        o.put("pose_hit_rate",    totalFrames > 0 ? (double) poseFrames / totalFrames : 0.0);
        JSONArray warns = new JSONArray();
        if (qualityWarnings != null) for (String w : qualityWarnings) warns.put(w);
        o.put("quality_warnings", warns);

        if (isBackground) o.put("bg_scenario", bgScenario != null ? bgScenario : "unknown");

        o.put("accepted",         accepted);
        o.put("reviewer_notes",   reviewerNotes != null ? reviewerNotes : JSONObject.NULL);
        o.put("mediapipe_version", mediapipeVersion);
        o.put("app_version",       appVersion);
        return o;
    }

    /** Video filename (no extension) — signer + session + word + rep. Stored under the word's
     *  video/ subfolder; the sidecar JSON sits alongside. */
    public String buildVideoFilename() {
        String wordPart = (word != null ? word : "unknown").replace(" ", "_");
        if (isBackground) {
            return String.format("%s_bg_%s_%04d", signerId,
                    bgScenario != null ? bgScenario : "unknown", repetitionIndex);
        }
        return String.format("%s_%03d_%s_%04d",
                signerId, extractSessionNumber(sessionId), wordPart, repetitionIndex);
    }

    /** Sidecar JSON filename (no extension) — same stem as the video so they pair up. */
    public String buildFilename() {
        return buildVideoFilename();
    }

    private int extractSessionNumber(String sessionId) {
        if (sessionId == null) return 0;
        int marker = sessionId.lastIndexOf("Session");
        if (marker < 0) return 0;
        String num = sessionId.substring(marker + "Session".length()).replaceAll("[^0-9]", "");
        if (num.isEmpty()) return 0;
        try { return Integer.parseInt(num); } catch (NumberFormatException e) { return 0; }
    }
}
