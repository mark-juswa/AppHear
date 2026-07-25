package com.example.aslrecorder.data;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Loads labels.json (AppHear 3 Stage-E schema: an array of {word, category, gloss, ...}) from
 * assets. Single source of truth for the recordable word list and each word's canonical ASL
 * Citizen GLOSS — the gloss is written into every clip's sidecar so the offline pipeline merges
 * the clip into the right class.
 */
public class LabelsRepository {

    private static final String TAG = "LabelsRepository";
    public static final String BACKGROUND_LABEL = "Background";
    // Bump when the assets labels.json format changes — forces a re-copy over any stale on-disk
    // copy (e.g. the old AppHear 2 string-array labels.json left in external storage).
    private static final String EXPECTED_SCHEMA = "aslrecorder-stageE-v1";

    private final List<String> words = new ArrayList<>();
    private final Map<String, String> wordToGloss = new HashMap<>();   // gloss may be null (no sign)
    private final Map<String, String> wordToCategory = new HashMap<>();
    private boolean loaded = false;

    public LabelsRepository(Context context) {
        load(context);
    }

    private void load(Context context) {
        try {
            words.clear();
            wordToGloss.clear();
            wordToCategory.clear();

            File labelsFile = labelsFile(context);
            // Copy from assets if missing OR if the on-disk copy is a stale/old-format file
            // (the old AppHear 2 recorder left a string-array labels.json in external storage).
            if (!labelsFile.exists() || !schemaMatches(labelsFile)) {
                labelsFile.getParentFile().mkdirs();
                try (java.io.InputStream in = context.getAssets().open("labels.json");
                     java.io.OutputStream out = new java.io.FileOutputStream(labelsFile)) {
                    byte[] buf = new byte[4096];
                    int n;
                    while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
                }
                Log.d(TAG, "Copied labels.json from assets (stale/missing) -> " + labelsFile.getAbsolutePath());
            }

            JSONObject json = new JSONObject(readFile(labelsFile));
            JSONArray arr = json.getJSONArray("labels");
            for (int i = 0; i < arr.length(); i++) {
                JSONObject e = arr.getJSONObject(i);
                String word = e.getString("word");
                words.add(word);
                wordToGloss.put(word, e.isNull("gloss") ? null : e.optString("gloss", null));
                wordToCategory.put(word, e.optString("category", ""));
            }
            loaded = true;
        } catch (Exception e) {
            Log.e(TAG, "Failed to load labels.json: " + e.getMessage());
        }
    }

    private File labelsFile(Context context) {
        File external = context.getExternalFilesDir(null);
        File base = (external != null) ? external : context.getFilesDir();
        return new File(new File(base, "AppHearDataset"), "labels.json");
    }

    /** True only if the on-disk labels.json is the current AppHear 3 schema. Old/unreadable → false
     *  (so load() re-copies from assets), which is what fixes the empty-picker bug. */
    private boolean schemaMatches(File f) {
        try {
            return EXPECTED_SCHEMA.equals(new JSONObject(readFile(f)).optString("schema"));
        } catch (Exception e) {
            return false;
        }
    }

    private String readFile(File f) throws java.io.IOException {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new FileReader(f))) {
            String line;
            while ((line = r.readLine()) != null) sb.append(line).append("\n");
        }
        return sb.toString();
    }

    /** Canonical ASL Citizen gloss for a recorded word (null = pointing/particle or new class). */
    public String glossFor(String word) { return wordToGloss.get(word); }

    public String categoryFor(String word) { return wordToCategory.get(word); }

    public boolean isLoaded()             { return loaded; }
    public List<String> getLabels()       { return words; }
    public List<String> getSignLabels()   { return new ArrayList<>(words); }
    public List<String> getAllLabels()    { return new ArrayList<>(words); }
    public int getLabelCount()            { return words.size(); }
    public String getBackgroundLabel()    { return BACKGROUND_LABEL; }
    public int indexOf(String word)       { return words.indexOf(word); }
    public boolean isTwoHanded(String w)  { return false; } // not tracked in the new schema

    /** Append a custom word (gloss unknown → null; becomes a new class if recorded). */
    public synchronized boolean addCustomSign(Context context, String newWord, boolean twoHandedIgnored) {
        if (newWord == null || newWord.trim().isEmpty()) return false;
        newWord = newWord.trim();
        if (!newWord.matches("^[a-zA-Z0-9_\\s]+$") || wordToGloss.containsKey(newWord)) return false;
        try {
            File f = labelsFile(context);
            if (!f.exists()) load(context);
            StringBuilder sb = new StringBuilder();
            try (BufferedReader r = new BufferedReader(new FileReader(f))) {
                String line;
                while ((line = r.readLine()) != null) sb.append(line).append("\n");
            }
            JSONObject json = new JSONObject(sb.toString());
            JSONObject entry = new JSONObject();
            entry.put("word", newWord);
            entry.put("category", "Custom");
            entry.put("gloss", JSONObject.NULL);
            entry.put("status", "not_in_asl_citizen");
            json.getJSONArray("labels").put(entry);
            json.put("label_count", json.getJSONArray("labels").length());
            try (FileWriter w = new FileWriter(f)) { w.write(json.toString(2)); }
            load(context);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Failed to add custom word: " + e.getMessage());
            return false;
        }
    }
}
