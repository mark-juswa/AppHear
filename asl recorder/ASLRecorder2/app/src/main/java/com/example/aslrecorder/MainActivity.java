package com.example.aslrecorder;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;

import androidx.appcompat.app.AppCompatActivity;

import com.example.aslrecorder.data.DatasetFileManager;
import com.example.aslrecorder.data.MetadataManager;
import com.example.aslrecorder.databinding.ActivityMainBinding;
import com.example.aslrecorder.model.SessionConfig;
import com.example.aslrecorder.model.SessionSummary;
import com.example.aslrecorder.model.SignerProfile;

import java.io.File;

public class MainActivity extends AppCompatActivity {

    private ActivityMainBinding binding;
    private MetadataManager metadataManager;
    private DatasetFileManager fileManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityMainBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        metadataManager = new MetadataManager(this);
        fileManager     = new DatasetFileManager(this);

        binding.btnStartNew.setOnClickListener(v ->
                startActivity(new Intent(this, SignerProfileActivity.class)));

        binding.btnContinue.setOnClickListener(v -> {
            SessionConfig lastSession = metadataManager.getLastIncompleteSessionConfig();
            if (lastSession != null) {
                SignerProfile signer = metadataManager.getSignerById(lastSession.signerId);
                SessionSummary summary = metadataManager.getSummaryForSession(lastSession);
                if (signer != null && summary != null) {
                    Intent intent = new Intent(this, RecordingActivity.class);
                    intent.putExtra(RecordingActivity.EXTRA_SIGNER, signer);
                    intent.putExtra(RecordingActivity.EXTRA_CONFIG, lastSession);
                    intent.putExtra(RecordingActivity.EXTRA_SUMMARY, summary);
                    startActivity(intent);
                    return;
                }
            }

            SignerProfile lastSigner = metadataManager.getLastSigner();
            if (lastSigner != null) {
                Intent intent = new Intent(this, SessionSetupActivity.class);
                intent.putExtra(SessionSetupActivity.EXTRA_SIGNER, lastSigner);
                startActivity(intent);
            } else {
                startActivity(new Intent(this, SignerProfileActivity.class));
            }
        });

        binding.cardBrowse.setOnClickListener(v -> {
            startActivity(new Intent(this, DatasetBrowserActivity.class));
        });

        binding.cardExport.setOnClickListener(v -> shareDatasetFolder());
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStats();
    }

    private void refreshStats() {
        int[] stats = metadataManager.getDatasetStats();
        binding.tvTotalAccepted.setText(String.valueOf(stats[0]));
        binding.tvSignsRecorded.setText(stats[1] + " / " + stats[2]);

        String lastSession = metadataManager.getLastSessionSummary();
        binding.tvLastSession.setText(
                lastSession != null ? lastSession : getString(R.string.no_sessions_yet));

        int backgroundCount = fileManager.countBackgroundAccepted();
        binding.tvBackgroundCount.setText(
                getString(R.string.label_background_count, backgroundCount, 100));

        File root = fileManager.getDatasetRoot();
        binding.tvSavePath.setText(root.getAbsolutePath());

        binding.btnContinue.setVisibility(
                metadataManager.getLastIncompleteSessionConfig() != null ? View.VISIBLE : View.GONE);
    }

    private void shareDatasetFolder() {
        File root = fileManager.getDatasetRoot();
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_TEXT, root.getAbsolutePath());
        startActivity(Intent.createChooser(intent, getString(R.string.btn_export)));
    }
}
