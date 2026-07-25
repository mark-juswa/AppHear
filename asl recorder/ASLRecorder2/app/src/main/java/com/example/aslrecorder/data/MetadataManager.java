package com.example.aslrecorder.data;

import android.content.Context;
import android.util.Log;

import com.example.aslrecorder.model.SessionConfig;
import com.example.aslrecorder.model.SessionSummary;
import com.example.aslrecorder.model.SignerProfile;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * Reads and writes metadata files in AppHearDataset/metadata/:
 *   signers.json    — signer profiles and split assignments
 *   sessions.json   — session records
 *   dataset_summary.json — total counts
 */
public class MetadataManager {

    private static final String TAG = "MetadataManager";

    private final File metadataDir;

    public MetadataManager(Context context) {
        DatasetFileManager dfm = new DatasetFileManager(context);
        metadataDir = new File(dfm.getDatasetRoot(), "metadata");
        metadataDir.mkdirs();
    }

    // ── Signers ───────────────────────────────────────────────────────────────

    public List<SignerProfile> loadSigners() {
        List<SignerProfile> list = new ArrayList<>();
        File file = new File(metadataDir, "signers.json");
        if (!file.exists()) return list;
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("signers");
            if (arr != null) {
                for (int i = 0; i < arr.length(); i++) {
                    list.add(SignerProfile.fromJson(arr.getJSONObject(i)));
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "loadSigners failed: " + e.getMessage());
        }
        return list;
    }

    public void saveSigner(SignerProfile profile) {
        List<SignerProfile> signers = loadSigners();
        // Replace if exists, otherwise append
        boolean replaced = false;
        for (int i = 0; i < signers.size(); i++) {
            if (signers.get(i).signerId.equals(profile.signerId)) {
                signers.set(i, profile);
                replaced = true;
                break;
            }
        }
        if (!replaced) signers.add(profile);

        try {
            JSONArray arr = new JSONArray();
            for (SignerProfile s : signers) arr.put(s.toJson());

            // Build split_assignments block
            JSONObject splits = new JSONObject();
            JSONArray trainArr = new JSONArray(), valArr = new JSONArray(), testArr = new JSONArray();
            for (SignerProfile s : signers) {
                switch (s.splitAssignment) {
                    case "train": trainArr.put(s.signerId); break;
                    case "val":   valArr.put(s.signerId);   break;
                    case "test":  testArr.put(s.signerId);  break;
                }
            }
            splits.put("train", trainArr);
            splits.put("val",   valArr);
            splits.put("test",  testArr);

            JSONObject root = new JSONObject();
            root.put("signers",          arr);
            root.put("split_assignments", splits);
            root.put("last_updated", new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));

            writeJson(new File(metadataDir, "signers.json"), root);
        } catch (Exception e) {
            Log.e(TAG, "saveSigner failed: " + e.getMessage());
        }
    }

    /**
     * Returns a device-scoped signer ID in the form "AB12-S001".
     * The prefix is generated once per app install so datasets from different
     * phones do not collide when merged.
     */
    public String getNextSignerId() {
        String collectorId = getCollectorId();
        int maxLocalNumber = 0;
        for (SignerProfile signer : loadSigners()) {
            int number = parseLocalSignerNumber(signer.signerId);
            if (number > maxLocalNumber) maxLocalNumber = number;
        }
        return String.format(Locale.US, "%s-S%03d", collectorId, maxLocalNumber + 1);
    }

    public String getCollectorId() {
        File file = new File(metadataDir, "collector.json");
        try {
            if (file.exists()) {
                JSONObject root = readJson(file);
                String existing = root.optString("collector_id", "");
                if (!existing.trim().isEmpty()) return existing;
            }

            String id = UUID.randomUUID().toString()
                    .replace("-", "")
                    .substring(0, 6)
                    .toUpperCase(Locale.US);
            JSONObject root = new JSONObject();
            root.put("collector_id", id);
            root.put("created_at", new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));
            writeJson(file, root);
            return id;
        } catch (Exception e) {
            Log.e(TAG, "getCollectorId failed: " + e.getMessage());
            return "LOCAL";
        }
    }

    private int parseLocalSignerNumber(String signerId) {
        if (signerId == null) return 0;
        int marker = signerId.lastIndexOf('S');
        if (marker < 0 || marker + 1 >= signerId.length()) return 0;
        try {
            return Integer.parseInt(signerId.substring(marker + 1).replaceAll("[^0-9]", ""));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    public boolean testSignerExists() {
        for (SignerProfile p : loadSigners()) {
            if ("test".equals(p.splitAssignment)) return true;
        }
        return false;
    }

    // ── Sessions ──────────────────────────────────────────────────────────────

    public void saveSession(SessionConfig config) {
        File file = new File(metadataDir, "sessions.json");
        try {
            JSONObject root = file.exists() ? readJson(file) : new JSONObject();
            JSONArray arr = root.optJSONArray("sessions");
            if (arr == null) arr = new JSONArray();

            JSONObject session = config.toJson();
            session.put("session_id", config.getSessionId());
            arr.put(session);

            root.put("sessions", arr);
            root.put("last_updated", new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));
            writeJson(file, root);
        } catch (Exception e) {
            Log.e(TAG, "saveSession failed: " + e.getMessage());
        }
    }

    /** Returns the highest session number recorded for a given signer, or 0 if none. */
    public int getLastSessionNumber(String signerId) {
        File file = new File(metadataDir, "sessions.json");
        if (!file.exists()) return 0;
        int max = 0;
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("sessions");
            if (arr != null) {
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject s = arr.getJSONObject(i);
                    if (signerId.equals(s.optString("signer_id"))) {
                        int num = s.optInt("session_number", 0);
                        if (num > max) max = num;
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "getLastSessionNumber failed: " + e.getMessage());
        }
        return max;
    }

    // ── Sessions (with summary) ───────────────────────────────────────────────

    /** Overload that also persists summary counts alongside the session record. */
    public void saveSession(SessionConfig config,
                            SessionSummary summary) {
        File file = new File(metadataDir, "sessions.json");
        try {
            JSONObject root = file.exists() ? readJson(file) : new JSONObject();
            JSONArray arr = root.optJSONArray("sessions");
            if (arr == null) arr = new JSONArray();

            JSONObject session = config.toJson();
            session.put("session_id",       config.getSessionId());
            session.put("accepted_count",   summary.acceptedCount);
            session.put("rejected_count",   summary.rejectedCount);
            session.put("total_attempts",   summary.totalAttempts);

            String sessionId = config.getSessionId();
            boolean replaced = false;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject existing = arr.getJSONObject(i);
                if (sessionId.equals(existing.optString("session_id"))) {
                    arr.put(i, session);
                    replaced = true;
                    break;
                }
            }
            if (!replaced) arr.put(session);

            root.put("sessions", arr);
            root.put("last_updated",
                    new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));
            writeJson(file, root);
        } catch (Exception e) {
            Log.e(TAG, "saveSession(with summary) failed: " + e.getMessage());
        }
    }

    /** Returns the next session number for a given signer (last + 1). */
    public int getNextSessionNumber(String signerId, String label) {
        return getLastSessionNumber(signerId) + 1;
    }

    public SignerProfile getSignerById(String signerId) {
        for (SignerProfile signer : loadSigners()) {
            if (signer.signerId.equals(signerId)) return signer;
        }
        return null;
    }

    public SessionConfig getLastIncompleteSessionConfig() {
        JSONObject session = getLastIncompleteSessionJson();
        return session != null ? SessionConfig.fromJson(session) : null;
    }

    public SessionSummary getSummaryForSession(SessionConfig config) {
        if (config == null) return null;
        JSONObject session = getSessionJson(config.getSessionId());
        if (session == null) return null;

        SessionSummary summary = new SessionSummary();
        summary.signLabel = config.signLabel;
        summary.signerId = config.signerId;
        summary.sessionId = config.getSessionId();
        summary.targetCount = config.targetReps;
        summary.acceptedCount = session.optInt("accepted_count", 0);
        summary.rejectedCount = session.optInt("rejected_count", 0);
        summary.totalAttempts = session.optInt("total_attempts",
                summary.acceptedCount + summary.rejectedCount);
        summary.recordingDate = config.recordingDate;
        return summary;
    }

    /** Returns the last signer profile saved, or null if none. */
    public SignerProfile getLastSigner() {
        List<SignerProfile> signers = loadSigners();
        return signers.isEmpty() ? null : signers.get(signers.size() - 1);
    }

    /**
     * Returns [totalAccepted, signsWithData, totalSigns] for the home screen.
     * Pass a DatasetFileManager and label list for accurate counts;
     * this overload reads from sessions.json as a fast approximation.
     */
    public int[] getDatasetStats() {
        File file = new File(metadataDir, "sessions.json");
        if (!file.exists()) return new int[]{0, 0, 0};
        int totalAccepted = 0;
        java.util.Set<String> labelsWithData = new java.util.HashSet<>();
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("sessions");
            if (arr != null) {
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject s = arr.getJSONObject(i);
                    totalAccepted += s.optInt("accepted_count", 0);
                    String label = s.optString("sign_label", "");
                    if (!label.isEmpty()) labelsWithData.add(label);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "getDatasetStats failed: " + e.getMessage());
        }
        return new int[]{totalAccepted, labelsWithData.size(), 26};
    }

    /** Returns a one-line summary of the most recent session, or null. */
    public String getLastSessionSummary() {
        File file = new File(metadataDir, "sessions.json");
        if (!file.exists()) return null;
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("sessions");
            if (arr == null || arr.length() == 0) return null;
            JSONObject last = arr.getJSONObject(arr.length() - 1);
            String label    = last.optString("sign_label", "?");
            int accepted    = last.optInt("accepted_count", 0);
            String date     = last.optString("recording_date", "");
            return "Last: " + label + " — " + accepted + " accepted · " + date;
        } catch (Exception e) {
            Log.e(TAG, "getLastSessionSummary failed: " + e.getMessage());
        }
        return null;
    }

    private JSONObject getLastIncompleteSessionJson() {
        File file = new File(metadataDir, "sessions.json");
        if (!file.exists()) return null;
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("sessions");
            if (arr == null) return null;
            for (int i = arr.length() - 1; i >= 0; i--) {
                JSONObject session = arr.getJSONObject(i);
                int accepted = session.optInt("accepted_count", 0);
                int target = session.optInt("target_reps", 0);
                if (target > 0 && accepted < target) return session;
            }
        } catch (Exception e) {
            Log.e(TAG, "getLastIncompleteSessionJson failed: " + e.getMessage());
        }
        return null;
    }

    private JSONObject getSessionJson(String sessionId) {
        File file = new File(metadataDir, "sessions.json");
        if (!file.exists()) return null;
        try {
            JSONObject root = readJson(file);
            JSONArray arr = root.optJSONArray("sessions");
            if (arr == null) return null;
            for (int i = arr.length() - 1; i >= 0; i--) {
                JSONObject session = arr.getJSONObject(i);
                if (sessionId.equals(session.optString("session_id"))) return session;
            }
        } catch (Exception e) {
            Log.e(TAG, "getSessionJson failed: " + e.getMessage());
        }
        return null;
    }

    // ── Dataset summary ───────────────────────────────────────────────────────

    public int getTotalAcceptedSamples(DatasetFileManager fileManager,
                                        List<String> allLabels) {
        int total = 0;
        for (String label : allLabels) {
            total += fileManager.countAccepted(label);
        }
        return total;
    }

    // ── IO helpers ────────────────────────────────────────────────────────────

    private JSONObject readJson(File file) throws IOException, JSONException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
        }
        return new JSONObject(sb.toString());
    }

    private void writeJson(File file, JSONObject json) throws IOException, JSONException {
        try (FileWriter writer = new FileWriter(file)) {
            writer.write(json.toString(2));
        }
    }
}
