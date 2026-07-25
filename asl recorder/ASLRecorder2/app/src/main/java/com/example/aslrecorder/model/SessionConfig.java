package com.example.aslrecorder.model;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.Serializable;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class SessionConfig implements Serializable {

    public String signLanguage;   // "FSL" | "ASL"
    public String signLabel;      // e.g. "Hello"
    public int    labelIndex;     // e.g. 0
    public int    targetReps;     // e.g. 60
    public String speed;          // "normal" | "slow" | "fast"
    public String posture;        // "seated" | "standing"
    public int    distanceCm;     // 40 | 60 | 70 | 90
    public String lighting;       // "indoor_good" | "indoor_dim" | "outdoor" | "side_lighting"
    public String backgroundType; // "plain_white" | "plain_dark" | "natural_busy" | "other"
    public String shirtColor;     // free text
    public int    sessionNumber;  // auto-incremented per signer
    public String signerId;       // reference to signer ID
    public String recordingDate;  // "YYYY-MM-DD"
    public boolean isBackground;  // false for signs, true for background class
    public String bgScenario;     // null for signs; see background scenario keys

    // Derived session ID: "{signerId}_Session{sessionNumber:03d}"
    public String getSessionId() {
        return String.format(Locale.US, "%s_Session%03d", signerId, sessionNumber);
    }

    public SessionConfig() {
        recordingDate = new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date());
        signLanguage  = "ASL";
        targetReps    = 60;
        speed         = "normal";
        posture       = "seated";
        distanceCm    = 70;
        lighting      = "indoor_good";
        backgroundType = "plain_white";
        shirtColor    = "";
        sessionNumber = 1;
        isBackground  = false;
    }

    public boolean isValid() {
        if (signerId == null || signerId.isEmpty()) return false;
        if (signLabel == null || signLabel.isEmpty()) return false;
        if (targetReps < 1) return false;
        return true;
    }

    public JSONObject toJson() throws JSONException {
        JSONObject obj = new JSONObject();
        obj.put("sign_language", signLanguage);
        obj.put("sign_label", signLabel);
        obj.put("label_index", labelIndex);
        obj.put("target_reps", targetReps);
        obj.put("speed", speed);
        obj.put("posture", posture);
        obj.put("distance_cm", distanceCm);
        obj.put("lighting", lighting);
        obj.put("background_type", backgroundType);
        obj.put("shirt_color", shirtColor != null ? shirtColor : "");
        obj.put("session_number", sessionNumber);
        obj.put("signer_id", signerId);
        obj.put("recording_date", recordingDate);
        obj.put("is_background", isBackground);
        if (bgScenario != null) obj.put("bg_scenario", bgScenario);
        return obj;
    }

    public static SessionConfig fromJson(JSONObject obj) {
        SessionConfig config = new SessionConfig();
        config.signLanguage = obj.optString("sign_language", "ASL");
        config.signLabel = obj.optString("sign_label", "");
        config.labelIndex = obj.optInt("label_index", 0);
        config.targetReps = obj.optInt("target_reps", 60);
        config.speed = obj.optString("speed", "normal");
        config.posture = obj.optString("posture", "seated");
        config.distanceCm = obj.optInt("distance_cm", 70);
        config.lighting = obj.optString("lighting", "indoor_good");
        config.backgroundType = obj.optString("background_type", "plain_white");
        config.shirtColor = obj.optString("shirt_color", "");
        config.sessionNumber = obj.optInt("session_number", 1);
        config.signerId = obj.optString("signer_id", "");
        config.recordingDate = obj.optString("recording_date", config.recordingDate);
        config.isBackground = obj.optBoolean("is_background", false);
        config.bgScenario = obj.optString("bg_scenario", null);
        return config;
    }
}
