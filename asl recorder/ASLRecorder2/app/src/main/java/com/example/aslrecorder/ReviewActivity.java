package com.example.aslrecorder;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.aslrecorder.data.DatasetFileManager;
import com.example.aslrecorder.data.MetadataManager;
import com.example.aslrecorder.databinding.ActivityReviewBinding;
import com.example.aslrecorder.databinding.ItemSampleReviewBinding;
import com.example.aslrecorder.model.SessionConfig;
import com.example.aslrecorder.model.SessionSummary;
import com.example.aslrecorder.model.SignerProfile;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class ReviewActivity extends AppCompatActivity {

    public static final String EXTRA_SUMMARY    = "extra_summary";
    public static final String EXTRA_SAVE_DIR   = "extra_save_dir";
    public static final String EXTRA_SESSION_ID = "extra_session_id";
    public static final String EXTRA_SIGNER     = "extra_signer";
    public static final String EXTRA_CONFIG     = "extra_config";

    private static final int FILTER_ALL      = 0;
    private static final int FILTER_ACCEPTED = 1;
    private static final int FILTER_REJECTED = 2;

    private ActivityReviewBinding binding;
    private DatasetFileManager fileManager;
    private MetadataManager metadataManager;
    private SessionSummary summary;
    private SampleAdapter adapter;
    private final List<SampleEntry> allSamples = new ArrayList<>();
    private String saveDir;
    private int currentFilter = FILTER_ALL;
    private SignerProfile signerProfile;
    private SessionConfig sessionConfig;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityReviewBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        fileManager       = new DatasetFileManager(this);
        metadataManager   = new MetadataManager(this);
        saveDir           = getIntent().getStringExtra(EXTRA_SAVE_DIR);
        String sessionId  = getIntent().getStringExtra(EXTRA_SESSION_ID);
        signerProfile     = (SignerProfile) getIntent().getSerializableExtra(EXTRA_SIGNER);
        sessionConfig     = (SessionConfig) getIntent().getSerializableExtra(EXTRA_CONFIG);
        summary           = (SessionSummary) getIntent().getSerializableExtra(EXTRA_SUMMARY);

        if (summary == null && sessionConfig != null) {
            summary = metadataManager.getSummaryForSession(sessionConfig);
        }
        if (summary == null) {
            summary = new SessionSummary();
            summary.sessionId = sessionId;
        }
        binding.tvReviewAccepted.setText(String.valueOf(summary.acceptedCount));
        binding.tvReviewRejected.setText(String.valueOf(summary.rejectedCount));
        binding.tvReviewTotal.setText(String.valueOf(summary.totalAttempts));
        binding.tvReviewSessionId.setText(sessionId != null ? sessionId : "");
        binding.tvReviewSavePath.setText(saveDir != null ? saveDir : "");

        loadSamples();
        setupRecycler();
        setupFilterButtons();

        binding.btnRedoAll.setOnClickListener(v -> redoAllRejected());
        binding.btnFinishSession.setOnClickListener(v -> finish());

        updateRedoVisibility();
    }

    private void loadSamples() {
        allSamples.clear();
        if (saveDir == null) return;
        addFilesFromDir(new File(saveDir, "accepted"), true);
        addFilesFromDir(new File(saveDir, "rejected"), false);
    }

    private void addFilesFromDir(File dir, boolean accepted) {
        if (!dir.exists()) return;
        File[] files = dir.listFiles(f -> f.getName().endsWith(".json"));
        if (files == null) return;
        for (File f : files) allSamples.add(new SampleEntry(f, accepted));
    }

    private void setupRecycler() {
        adapter = new SampleAdapter(getFilteredList());
        binding.recyclerSamples.setLayoutManager(new LinearLayoutManager(this));
        binding.recyclerSamples.setAdapter(adapter);
    }

    private List<SampleEntry> getFilteredList() {
        if (currentFilter == FILTER_ALL) return new ArrayList<>(allSamples);
        List<SampleEntry> filtered = new ArrayList<>();
        for (SampleEntry e : allSamples) {
            if (currentFilter == FILTER_ACCEPTED &&  e.accepted) filtered.add(e);
            if (currentFilter == FILTER_REJECTED && !e.accepted) filtered.add(e);
        }
        return filtered;
    }

    private void setupFilterButtons() {
        binding.btnFilterAll.setOnClickListener(v      -> applyFilter(FILTER_ALL));
        binding.btnFilterAccepted.setOnClickListener(v -> applyFilter(FILTER_ACCEPTED));
        binding.btnFilterRejected.setOnClickListener(v -> applyFilter(FILTER_REJECTED));
    }

    private void applyFilter(int filter) {
        currentFilter = filter;
        int primary   = getColor(R.color.color_primary);
        int secondary = getColor(R.color.text_secondary);
        binding.btnFilterAll.setTextColor(      filter == FILTER_ALL      ? primary : secondary);
        binding.btnFilterAccepted.setTextColor( filter == FILTER_ACCEPTED ? primary : secondary);
        binding.btnFilterRejected.setTextColor( filter == FILTER_REJECTED ? primary : secondary);
        adapter.updateData(getFilteredList());
    }

    private void promoteToAccepted(SampleEntry entry) {
        fileManager.overrideToAccepted(entry.file, null, newFile -> runOnUiThread(() -> {
            entry.file     = newFile;
            entry.accepted = true;
            summary.acceptedCount++;
            summary.rejectedCount = Math.max(0, summary.rejectedCount - 1);
            binding.tvReviewAccepted.setText(String.valueOf(summary.acceptedCount));
            binding.tvReviewRejected.setText(String.valueOf(summary.rejectedCount));
            updateRedoVisibility();
            adapter.updateData(getFilteredList());
        }));
    }

    private void deleteRejectedSample(SampleEntry entry) {
        if (entry.accepted) return;

        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Delete rejected sample?")
                .setMessage(entry.file.getName())
                .setPositiveButton(getString(R.string.btn_delete_sample), (dialog, which) -> {
                    if (fileManager.deleteSample(entry.file)) {
                        allSamples.remove(entry);
                        summary.rejectedCount = Math.max(0, summary.rejectedCount - 1);
                        summary.totalAttempts = Math.max(0, summary.totalAttempts - 1);
                        binding.tvReviewRejected.setText(String.valueOf(summary.rejectedCount));
                        binding.tvReviewTotal.setText(String.valueOf(summary.totalAttempts));
                        updateRedoVisibility();
                        adapter.updateData(getFilteredList());
                    }
                })
                .setNegativeButton(android.R.string.cancel, null)
                .show();
    }

    private void updateRedoVisibility() {
        binding.btnRedoAll.setVisibility(
                sessionConfig != null && signerProfile != null && summary.rejectedCount > 0
                        ? View.VISIBLE : View.GONE);
    }

    private void redoAllRejected() {
        if (signerProfile == null || sessionConfig == null || summary == null) {
            finish();
            return;
        }

        Intent intent = new Intent(this, RecordingActivity.class);
        intent.putExtra(RecordingActivity.EXTRA_SIGNER, signerProfile);
        intent.putExtra(RecordingActivity.EXTRA_CONFIG, sessionConfig);
        intent.putExtra(RecordingActivity.EXTRA_SUMMARY, summary);
        startActivity(intent);
        finish();
    }

    // ── Data + Adapter ────────────────────────────────────────────────────────

    static class SampleEntry {
        File    file;
        boolean accepted;
        SampleEntry(File file, boolean accepted) {
            this.file     = file;
            this.accepted = accepted;
        }
    }

    private class SampleAdapter extends RecyclerView.Adapter<SampleAdapter.VH> {
        private List<SampleEntry> items;

        SampleAdapter(List<SampleEntry> items) { this.items = items; }

        void updateData(List<SampleEntry> newItems) {
            items = newItems;
            notifyDataSetChanged();
        }

        @NonNull @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            return new VH(ItemSampleReviewBinding.inflate(
                    LayoutInflater.from(parent.getContext()), parent, false));
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int pos) { holder.bind(items.get(pos)); }

        @Override public int getItemCount() { return items.size(); }

        class VH extends RecyclerView.ViewHolder {
            final ItemSampleReviewBinding b;
            VH(ItemSampleReviewBinding b) { super(b.getRoot()); this.b = b; }

            void bind(SampleEntry entry) {
                b.tvItemFilename.setText(entry.file.getName());
                if (entry.accepted) {
                    b.tvItemStatus.setText("OK");
                    b.tvItemStatus.setBackgroundResource(R.drawable.bg_badge_green);
                    b.tvItemStatus.setTextColor(getColor(R.color.color_accepted));
                    b.tvItemDetail.setText("");
                    b.btnPromoteToAccepted.setVisibility(View.GONE);
                    b.btnDeleteSample.setVisibility(View.GONE);
                } else {
                    b.tvItemStatus.setText("REJ");
                    b.tvItemStatus.setBackgroundResource(R.drawable.bg_badge_red);
                    b.tvItemStatus.setTextColor(getColor(R.color.color_rejected));
                    String name   = entry.file.getName();
                    int    idx    = name.indexOf("REJECTED_");
                    String reason = idx >= 0
                            ? name.substring(idx + 9).replace(".json", "") : "rejected";
                    b.tvItemDetail.setText(reason.replace("_", " ").toLowerCase());
                    b.btnPromoteToAccepted.setVisibility(View.VISIBLE);
                    b.btnPromoteToAccepted.setOnClickListener(v -> promoteToAccepted(entry));
                    b.btnDeleteSample.setVisibility(View.VISIBLE);
                    b.btnDeleteSample.setOnClickListener(v -> deleteRejectedSample(entry));
                }
            }
        }
    }
}
