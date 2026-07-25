package com.example.aslrecorder.data;

import android.content.Context;
import android.util.Log;

import com.example.aslrecorder.model.SampleData;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Manages all file I/O for the dataset.
 *
 * Root: getExternalFilesDir(null)/AppHearDataset/
 * Fallback if external storage unavailable: getFilesDir()/AppHearDataset/
 *
 * All file writes happen on a single-thread background executor.
 * Callers receive callbacks on completion.
 */
public class DatasetFileManager {

    private static final String TAG        = "DatasetFileManager";
    public  static final String DATASET_FOLDER = "AppHearDataset";

    public interface SaveCallback {
        void onSaved(File savedFile);
        default void onError(String message) { /* no-op by default */ }
    }

    private final File datasetRoot;
    private final ExecutorService ioExecutor = Executors.newSingleThreadExecutor();

    public DatasetFileManager(Context context) {
        File external = context.getExternalFilesDir(null);
        File base     = (external != null) ? external : context.getFilesDir();
        datasetRoot   = new File(base, DATASET_FOLDER);
        ensureRootStructure();
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /**
     * Save a SampleData to the correct subfolder (accepted or rejected) asynchronously.
     * The sample's frames must be populated before calling this.
     */
    public void saveSampleAsync(SampleData sample, SaveCallback callback) {
        ioExecutor.execute(() -> {
            try {
                File savedFile = saveSample(sample);
                if (callback != null) callback.onSaved(savedFile);
            } catch (Exception e) {
                Log.e(TAG, "Save failed: " + e.getMessage());
                if (callback != null) callback.onError(e.getMessage());
            }
        });
    }

    /** Synchronous version — call only from a background thread. */
    public File saveSample(SampleData sample) throws IOException {
        File dir = getSampleDir(sample);
        dir.mkdirs();

        String filename = sample.buildFilename() + ".json";
        File file = new File(dir, filename);

        try (FileWriter writer = new FileWriter(file)) {
            writer.write(sample.toJson().toString(2));
        } catch (org.json.JSONException e) {
            throw new IOException("JSON serialization failed: " + e.getMessage());
        }

        Log.d(TAG, "Saved: " + file.getAbsolutePath());
        return file;
    }

    /** Mark a sidecar accepted=true in place (non-destructive layout — no file move). */
    public void overrideToAccepted(File sampleFile, String reviewerNotes, SaveCallback callback) {
        ioExecutor.execute(() -> {
            try {
                org.json.JSONObject json = new org.json.JSONObject(readFileToString(sampleFile));
                json.put("accepted", true);
                if (reviewerNotes != null) json.put("reviewer_notes", reviewerNotes);
                try (FileWriter writer = new FileWriter(sampleFile)) { writer.write(json.toString(2)); }
                if (callback != null) callback.onSaved(sampleFile);
            } catch (Exception e) {
                Log.e(TAG, "Override failed: " + e.getMessage());
                if (callback != null) callback.onError(e.getMessage());
            }
        });
    }

    public boolean deleteSample(File sampleFile) {
        return sampleFile.exists() && sampleFile.delete();
    }

    // ── Folder helpers ────────────────────────────────────────────────────────

    // Non-destructive flat layout: samples/signs/<word>/ holds the paired <clip>.mp4 + <clip>.json.
    // No accepted/rejected split — the offline Q stage + review are the gate.
    private File getSampleDir(SampleData sample) {
        if (sample.isBackground) return new File(datasetRoot, "samples/background");
        String wordFolder = (sample.word != null ? sample.word : "unknown").replace(" ", "_");
        return new File(datasetRoot, "samples/signs/" + wordFolder);
    }

    /** Public variant — determines the accepted/rejected folder from a SessionConfig. */
    public File getSampleDir(com.example.aslrecorder.model.SessionConfig config) {
        if (config.isBackground) {
            return new File(datasetRoot, "samples/background");
        }
        String labelFolder = config.signLabel.replace(" ", "_");
        return new File(datasetRoot, "samples/signs/" + labelFolder);
    }

    /** Video sits in the SAME word dir as its sidecar (mp4 + json paired by filename stem). */
    public File getVideoDir(SampleData sample) {
        return getSampleDir(sample);
    }

    /** Final destination file for a sample's video clip. */
    public File getVideoFile(SampleData sample) {
        return new File(getVideoDir(sample), sample.buildVideoFilename() + ".mp4");
    }

    /**
     * Move a temporary video file to its final location alongside the JSON sample.
     * Called from RecordingActivity once the CameraX Finalize event fires.
     * Fire-and-forget — errors are logged but not surfaced to the caller.
     */
    public void moveVideoToFinalLocation(File tempVideo, SampleData sample) {
        ioExecutor.execute(() -> {
            try {
                File destDir = getVideoDir(sample);
                destDir.mkdirs();
                File dest = new File(destDir, sample.buildVideoFilename() + ".mp4");
                if (dest.exists()) dest.delete();
                boolean moved = tempVideo.renameTo(dest);
                if (!moved) {
                    // Cross-partition fallback: copy then delete source
                    copyFile(tempVideo, dest);
                    tempVideo.delete();
                }
                Log.d(TAG, "Video saved: " + dest.getAbsolutePath());
            } catch (Exception e) {
                Log.e(TAG, "Video move failed: " + e.getMessage());
            }
        });
    }

    /** Flat layout: the word's dir holds all its clips (there is no accepted/rejected split). */
    public File getAcceptedDir(String word) {
        return new File(datasetRoot, "samples/signs/" + word.replace(" ", "_"));
    }

    /** No rejected split in the non-destructive layout — returns an empty (nonexistent) dir. */
    public File getRejectedDir(String word) {
        return new File(datasetRoot, "samples/signs/" + word.replace(" ", "_") + "/_none");
    }

    public File getBackgroundAcceptedDir() {
        return new File(datasetRoot, "samples/background");
    }

    public File getDatasetRoot() { return datasetRoot; }

    public String getDatasetRootDisplayPath() {
        // Returns a user-friendly path like "Android/data/.../AppHearDataset"
        String abs = datasetRoot.getAbsolutePath();
        int idx = abs.indexOf("Android/data");
        return idx >= 0 ? abs.substring(idx) : abs;
    }

    /** Count accepted Background/rest samples (samples/background/accepted). */
    public int countBackgroundAccepted() {
        File dir = getBackgroundAcceptedDir();
        if (!dir.exists()) return 0;
        File[] files = dir.listFiles(f -> f.getName().endsWith(".json"));
        return files != null ? files.length : 0;
    }

    /** Count accepted samples for a given sign label. */
    public int countAccepted(String label) {
        File dir = getAcceptedDir(label);
        if (!dir.exists()) return 0;
        File[] files = dir.listFiles(f -> f.getName().endsWith(".json"));
        return files != null ? files.length : 0;
    }

    /** List accepted sample files for a sign label. */
    public List<File> listAccepted(String label) {
        List<File> result = new ArrayList<>();
        File dir = getAcceptedDir(label);
        if (!dir.exists()) return result;
        File[] files = dir.listFiles(f -> f.getName().endsWith(".json"));
        if (files != null) for (File f : files) result.add(f);
        return result;
    }

    /** List rejected sample files for a sign label. */
    public List<File> listRejected(String label) {
        List<File> result = new ArrayList<>();
        File dir = getRejectedDir(label);
        if (!dir.exists()) return result;
        File[] files = dir.listFiles(f -> f.getName().endsWith(".json"));
        if (files != null) for (File f : files) result.add(f);
        return result;
    }

    // ── Internal ──────────────────────────────────────────────────────────────

    private void ensureRootStructure() {
        new File(datasetRoot, "metadata").mkdirs();
        new File(datasetRoot, "exports").mkdirs();
        new File(datasetRoot, "samples/background").mkdirs();
    }

    public void ensureSignFolders(List<String> signLabels) {
        ioExecutor.execute(() -> {
            for (String label : signLabels) {
                new File(datasetRoot, "samples/signs/" + label.replace(" ", "_")).mkdirs();
            }
        });
    }

    private void copyFile(File src, File dst) throws IOException {
        try (java.io.InputStream  in  = new java.io.FileInputStream(src);
             java.io.OutputStream out = new java.io.FileOutputStream(dst)) {
            byte[] buf = new byte[64 * 1024];
            int len;
            while ((len = in.read(buf)) > 0) out.write(buf, 0, len);
        }
    }

    private String readFileToString(File file) throws IOException {
        StringBuilder sb = new StringBuilder();
        try (java.io.BufferedReader reader = new java.io.BufferedReader(
                new java.io.FileReader(file))) {
            String line;
            while ((line = reader.readLine()) != null) sb.append(line).append("\n");
        }
        return sb.toString();
    }
}
