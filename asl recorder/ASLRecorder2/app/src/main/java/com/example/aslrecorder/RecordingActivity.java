package com.example.aslrecorder;

import android.Manifest;
import android.animation.ObjectAnimator;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.util.Log;
import android.util.Size;
import android.view.View;
import android.view.WindowManager;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.video.FileOutputOptions;
import androidx.camera.video.Quality;
import androidx.camera.video.QualitySelector;
import androidx.camera.video.Recorder;
import androidx.camera.video.Recording;
import androidx.camera.video.VideoCapture;
import androidx.camera.video.VideoRecordEvent;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.example.aslrecorder.data.DatasetFileManager;
import com.example.aslrecorder.data.LabelsRepository;
import com.example.aslrecorder.data.MetadataManager;
import com.example.aslrecorder.databinding.ActivityRecordingBinding;
import com.example.aslrecorder.mediapipe.MediaPipeRecorderHelper;
import com.example.aslrecorder.mediapipe.ResultBundle;
import com.example.aslrecorder.model.QualityResult;
import com.example.aslrecorder.model.SampleData;
import com.example.aslrecorder.model.SessionConfig;
import com.example.aslrecorder.model.SessionSummary;
import com.example.aslrecorder.model.SignerProfile;
import com.example.aslrecorder.recording.RecordingState;
import com.example.aslrecorder.recording.RecordingStateMachine;
import com.google.common.util.concurrent.ListenableFuture;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * AppHear 3 Stage-E VIDEO recorder. Each attempt captures a fixed-duration upright ASL video
 * (the dataset artifact) + a metadata sidecar. The offline pipeline re-extracts landmarks from the
 * video with the SAME IMAGE-mode extractor used for ASL Citizen. On-device MediaPipe (hand+pose,
 * face-off) drives the live overlay + advisory coverage only — nothing is normalized, baked, or
 * auto-rejected here.
 */
public class RecordingActivity extends AppCompatActivity
        implements MediaPipeRecorderHelper.LandmarkResultListener,
        RecordingStateMachine.RecordingStateListener {

    public static final String EXTRA_SIGNER  = "extra_signer";
    public static final String EXTRA_CONFIG  = "extra_config";
    public static final String EXTRA_SUMMARY = "extra_summary";

    private static final String TAG            = "RecordingActivity";
    private static final int    REQUEST_CAMERA = 100;

    private ActivityRecordingBinding binding;
    private SignerProfile  signerProfile;
    private SessionConfig  sessionConfig;
    private SessionSummary sessionSummary;

    private MediaPipeRecorderHelper mediaPipeHelper;
    private RecordingStateMachine   stateMachine;
    private DatasetFileManager      fileManager;
    private MetadataManager         metadataManager;
    private LabelsRepository        labels;
    private String                  gloss; // resolved ASL Citizen gloss for this session's word

    private ExecutorService cameraExecutor;
    private ProcessCameraProvider cameraProvider;
    private ImageAnalysis imageAnalysis;
    private VideoCapture<Recorder> videoCapture;
    private Recording activeRecording;
    private File      pendingVideoTempFile;
    private SampleData pendingSample;
    private final boolean isFrontCamera = true;

    private boolean handsVisible    = false;
    private boolean poseVisible     = false;
    private boolean sessionFinished = false;
    private boolean firstFrameSeen  = false;
    private volatile boolean captureActive = false;
    private volatile boolean collecting    = false;   // true only during RECORDING

    // Advisory coverage counters for the current attempt (from IMAGE-mode preview detections)
    private int totalFrames = 0, handFrames = 0, poseFrames = 0;
    private int consecutiveNoHandFrames = 0;
    private volatile int frameW = 0, frameH = 0;      // analysis frame dims (hint; ingest reads video)
    private ObjectAnimator redoPulseAnimator;

    private static final int   HOLD_WARNING_FRAMES = 3;
    private static final float COVERAGE_BAR_GREEN   = 0.70f;
    private static final float COVERAGE_BAR_YELLOW  = 0.40f;

    private boolean isBackgroundMode = false;
    private int     backgroundPromptIndex = -1;
    private static final String[] BACKGROUND_PROMPTS = {
            "Rest your hands in your lap", "Cross your arms", "Adjust your clothing",
            "Look away from the camera", "Nod your head", "Rest your hands on the table"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        binding = ActivityRecordingBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());

        signerProfile = (SignerProfile) getIntent().getSerializableExtra(EXTRA_SIGNER);
        sessionConfig = (SessionConfig)  getIntent().getSerializableExtra(EXTRA_CONFIG);
        if (signerProfile == null || sessionConfig == null) { finish(); return; }

        sessionSummary = (SessionSummary) getIntent().getSerializableExtra(EXTRA_SUMMARY);
        if (sessionSummary == null) sessionSummary = new SessionSummary();
        sessionSummary.signLabel     = sessionConfig.signLabel;
        sessionSummary.signerId      = signerProfile.signerId;
        sessionSummary.sessionId     = sessionConfig.getSessionId();
        sessionSummary.targetCount   = sessionConfig.targetReps;
        sessionSummary.recordingDate = sessionConfig.recordingDate;

        fileManager     = new DatasetFileManager(this);
        metadataManager = new MetadataManager(this);
        labels          = new LabelsRepository(this);
        cameraExecutor  = Executors.newSingleThreadExecutor();
        gloss           = sessionConfig.isBackground ? null : labels.glossFor(sessionConfig.signLabel);

        stateMachine = new RecordingStateMachine(sessionConfig.targetReps, this, sessionSummary);

        isBackgroundMode = sessionConfig.isBackground;
        if (isBackgroundMode) {
            binding.tvTopSignLabel.setText(getString(R.string.mode_background_recording));
            binding.tvTopSignLabel.setTextColor(ContextCompat.getColor(this, R.color.color_warning));
        } else {
            String top = sessionConfig.signLabel + (gloss != null ? "  (" + gloss + ")" : "  (no gloss)");
            binding.tvTopSignLabel.setText(top);
        }
        binding.tvSpeedInfo.setText("Speed: " + sessionConfig.speed);
        binding.badgeFace.setVisibility(View.GONE); // face landmarker removed
        updateSessionCounters();
        setStartEnabled(false, "Loading camera...");

        binding.btnBack.setOnClickListener(v -> confirmStop());
        binding.btnPauseRecording.setOnClickListener(v -> togglePause());
        binding.btnStopSession.setOnClickListener(v -> confirmStop());
        binding.btnStartSession.setOnClickListener(v -> {
            if (mediaPipeHelper == null || !mediaPipeHelper.isInitialized()) {
                showBlockingCaptureError(getString(R.string.error_models_missing));
                return;
            }
            binding.btnStartSession.setVisibility(View.GONE);
            binding.btnPauseRecording.setVisibility(View.VISIBLE);
            binding.btnStopSession.setVisibility(View.VISIBLE);
            stateMachine.start();
        });
        binding.btnRedoRejected.setOnClickListener(v -> stopAndOpenReview());

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            initMediaPipeAndCamera();
        } else {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, REQUEST_CAMERA);
        }
    }

    private void initMediaPipeAndCamera() {
        mediaPipeHelper = new MediaPipeRecorderHelper(this, this);
        if (!mediaPipeHelper.isInitialized()) {
            showBlockingCaptureError(getString(R.string.error_models_missing));
            return;
        }
        setStartEnabled(true, getString(R.string.btn_start_session));
        startCamera();
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try { bindCamera(future.get()); }
            catch (ExecutionException | InterruptedException e) { Log.e(TAG, "Camera provider error", e); }
        }, ContextCompat.getMainExecutor(this));
    }

    private void bindCamera(ProcessCameraProvider provider) {
        cameraProvider = provider;
        provider.unbindAll();
        captureActive = true;

        Preview preview = new Preview.Builder().build();
        preview.setSurfaceProvider(binding.previewView.getSurfaceProvider());

        imageAnalysis = new ImageAnalysis.Builder()
                .setTargetResolution(new Size(640, 480)) // matches AppHear 3 analysis res
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .build();
        imageAnalysis.setAnalyzer(cameraExecutor, imageProxy -> {
            MediaPipeRecorderHelper helper = mediaPipeHelper;
            if (!captureActive || helper == null || !helper.isInitialized()) { imageProxy.close(); return; }
            frameW = imageProxy.getHeight(); // upright dims after rotation (portrait preview)
            frameH = imageProxy.getWidth();
            helper.processFrame(imageProxy);
        });

        Recorder recorder = new Recorder.Builder()
                .setQualitySelector(QualitySelector.from(Quality.HD,
                        androidx.camera.video.FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)))
                .build();
        videoCapture = VideoCapture.withOutput(recorder);

        CameraSelector front = new CameraSelector.Builder()
                .requireLensFacing(CameraSelector.LENS_FACING_FRONT).build();
        try {
            provider.bindToLifecycle(this, front, preview, imageAnalysis, videoCapture);
        } catch (Exception e) {
            Log.w(TAG, "3-use-case bind failed, no video on this device: " + e.getMessage());
            videoCapture = null;
            provider.bindToLifecycle(this, front, preview, imageAnalysis);
        }
    }

    // ── MediaPipe callback (background thread) ────────────────────────────────

    @Override
    public void onLandmarkResult(ResultBundle bundle) {
        binding.landmarkOverlay.updateResults(bundle, isFrontCamera);

        boolean newHands = bundle.hasHands();
        boolean newPose  = bundle.hasPose();
        if (newHands != handsVisible || newPose != poseVisible) {
            handsVisible = newHands;
            poseVisible  = newPose;
            stateMachine.onTrackingStateUpdate(handsVisible, poseVisible);
        }
        firstFrameSeen = true;
        runOnUiThread(() -> updateTrackingBadges(newHands, newPose));

        if (collecting) {
            totalFrames++;
            if (newHands) { handFrames++; consecutiveNoHandFrames = 0; }
            else if (handFrames > 0) consecutiveNoHandFrames++;
            if (newPose) poseFrames++;

            final int hf = handFrames, tf = totalFrames;
            final boolean holdWarn = !isBackgroundMode && handFrames > 0
                    && consecutiveNoHandFrames >= HOLD_WARNING_FRAMES;
            runOnUiThread(() -> updateRecordingCoverage(hf, tf, holdWarn));
        }
    }

    @Override
    public void onLandmarkError(String error) {
        Log.e(TAG, "MediaPipe: " + error);
        runOnUiThread(() -> showBlockingCaptureError(error));
    }

    // ── State machine callbacks (main thread) ─────────────────────────────────

    @Override
    public void onStateChanged(RecordingState state) {
        switch (state) {
            case PREPARE:
                if (isBackgroundMode) backgroundPromptIndex++;
                collecting = false;
                hideRecordingCoverageUi();
                binding.tvQualityGateResult.setVisibility(View.GONE);
                binding.tvCountdownInstruction.setVisibility(View.GONE);
                updateGuidanceForTracking();
                break;
            case RECORDING:
                totalFrames = handFrames = poseFrames = 0;
                consecutiveNoHandFrames = 0;
                stopRedoPulse();
                binding.tvQualityGateResult.setVisibility(View.GONE);
                binding.tvCountdownInstruction.setVisibility(View.GONE);
                showRecordingCoverageUi();
                clearGuidance();
                startVideoRecording();
                collecting = true;
                binding.tvCountdown.setText("●");
                binding.tvCountdown.setTextColor(ContextCompat.getColor(this, R.color.color_rejected));
                binding.tvCountdownSubtext.setText(getString(R.string.status_recording));
                break;
            case ANALYZING:
                collecting = false;
                stopVideoRecording();
                hideRecordingCoverageUi();
                binding.tvCountdownSubtext.setText(getString(R.string.status_analyzing));
                List<String> warns = new ArrayList<>();
                if (handHitRate() < 0.5f) warns.add("low_hand_coverage");
                if (poseHitRate() < 0.7f) warns.add("low_pose_coverage");
                stateMachine.onQualityResult(new QualityResult(handFrames, poseFrames, totalFrames, warns));
                break;
            case ACCEPTED:
                flashOverlay(true);
                break;
            case REJECTED:
                flashOverlay(false);
                break;
            case REST:
                binding.tvCountdown.setText("—");
                binding.tvCountdown.setTextColor(ContextCompat.getColor(this, R.color.countdown_normal));
                binding.tvCountdownSubtext.setText(getString(R.string.status_rest));
                clearGuidance();
                break;
            case COMPLETE:
                finishSession();
                break;
        }
    }

    @Override
    public void onCountdownTick(int secondsRemaining) {
        if (secondsRemaining == 0) {
            binding.tvCountdownInstruction.setVisibility(View.GONE);
            binding.tvCountdown.setText(getString(R.string.countdown_sign));
            binding.tvCountdown.setTextColor(ContextCompat.getColor(this, R.color.color_accepted));
            binding.tvCountdownSubtext.setText(getString(R.string.status_recording));
        } else {
            binding.tvCountdownInstruction.setText(isBackgroundMode
                    ? currentBackgroundPrompt() : getString(R.string.countdown_hold_instruction));
            binding.tvCountdownInstruction.setVisibility(View.VISIBLE);
            binding.tvCountdown.setText(String.valueOf(secondsRemaining));
            binding.tvCountdown.setTextColor(ContextCompat.getColor(this, R.color.countdown_normal));
            binding.tvCountdownSubtext.setText(getString(R.string.countdown_get_ready));
        }
    }

    @Override
    public void onSampleResult(QualityResult result) {
        updateSessionCounters();
        binding.tvRejectionReason.setVisibility(View.GONE);
        showCoverageReadout(result);
        saveSample(result);
    }

    @Override
    public void onSessionComplete(SessionSummary summary) { finishSession(); }

    // ── Save (video-primary, non-destructive) ─────────────────────────────────

    private void saveSample(QualityResult coverage) {
        SampleData sample = SampleData.build(sessionConfig, signerProfile, gloss, sessionSummary.totalAttempts);
        sample.totalFrames = coverage.totalFrames;
        sample.handFrames  = coverage.handFrames;
        sample.poseFrames  = coverage.poseFrames;
        sample.qualityWarnings = coverage.warnings;
        sample.frameWidth  = frameW;
        sample.frameHeight = frameH;
        sample.nativeFps   = 30.0; // nominal; the Python ingest reads the true fps from the .mp4

        if (pendingVideoTempFile != null) {
            sample.videoFilename = sample.buildVideoFilename() + ".mp4";
            pendingSample = sample; // moved on CameraX Finalize
        }
        fileManager.saveSampleAsync(sample, f -> { /* sidecar saved */ });
    }

    // ── Video recording ───────────────────────────────────────────────────────

    private void startVideoRecording() {
        if (videoCapture == null) return;
        pendingVideoTempFile = new File(getCacheDir(), "rec_temp.mp4");
        if (pendingVideoTempFile.exists()) pendingVideoTempFile.delete();
        FileOutputOptions opts = new FileOutputOptions.Builder(pendingVideoTempFile).build();
        try {
            activeRecording = videoCapture.getOutput()
                    .prepareRecording(this, opts)
                    .start(ContextCompat.getMainExecutor(this), this::onVideoEvent);
        } catch (Exception e) {
            Log.e(TAG, "Failed to start video recording: " + e.getMessage());
            pendingVideoTempFile = null;
        }
    }

    private void stopVideoRecording() {
        if (activeRecording != null) activeRecording.stop();
    }

    private void onVideoEvent(VideoRecordEvent event) {
        if (!(event instanceof VideoRecordEvent.Finalize)) return;
        VideoRecordEvent.Finalize fin = (VideoRecordEvent.Finalize) event;
        activeRecording = null;
        if (fin.hasError()) {
            Log.w(TAG, "Video error " + fin.getError() + " — dropping clip");
            if (pendingVideoTempFile != null) { pendingVideoTempFile.delete(); pendingVideoTempFile = null; }
            pendingSample = null;
            return;
        }
        final File temp = pendingVideoTempFile;
        final SampleData s = pendingSample;
        pendingVideoTempFile = null;
        pendingSample = null;
        if (temp != null && temp.exists() && s != null) fileManager.moveVideoToFinalLocation(temp, s);
        else if (temp != null) temp.delete();
    }

    // ── Coverage UI ────────────────────────────────────────────────────────────

    private float handHitRate() { return totalFrames > 0 ? (float) handFrames / totalFrames : 0f; }
    private float poseHitRate() { return totalFrames > 0 ? (float) poseFrames / totalFrames : 0f; }

    private String currentBackgroundPrompt() {
        int i = backgroundPromptIndex < 0 ? 0 : backgroundPromptIndex;
        return "Vary your rest: " + BACKGROUND_PROMPTS[i % BACKGROUND_PROMPTS.length];
    }

    private void showRecordingCoverageUi() {
        if (isBackgroundMode) { hideRecordingCoverageUi(); return; }
        binding.tvHandCoverageLabel.setText(getString(R.string.hand_coverage_label_default));
        binding.progressHandCoverage.setProgress(0);
        binding.progressHandCoverage.setProgressTintList(
                ColorStateList.valueOf(ContextCompat.getColor(this, R.color.color_rejected)));
        binding.tvHandCoverageLabel.setVisibility(View.VISIBLE);
        binding.progressHandCoverage.setVisibility(View.VISIBLE);
        binding.tvHoldHandsWarning.setVisibility(View.GONE);
    }

    private void hideRecordingCoverageUi() {
        binding.tvHandCoverageLabel.setVisibility(View.GONE);
        binding.progressHandCoverage.setVisibility(View.GONE);
        binding.tvHoldHandsWarning.setVisibility(View.GONE);
    }

    private void updateRecordingCoverage(int handF, int frameCount, boolean showHoldWarning) {
        binding.tvCountdownSubtext.setText("Recording… " + frameCount + " frames seen");
        if (isBackgroundMode) return;
        int pct = frameCount > 0 ? Math.round(100f * handF / frameCount) : 0;
        binding.tvHandCoverageLabel.setText("Hand coverage  " + pct + "%");
        binding.progressHandCoverage.setProgress(pct);
        float ratio = frameCount > 0 ? (float) handF / frameCount : 0f;
        int tint = ratio >= COVERAGE_BAR_GREEN ? R.color.color_accepted
                : ratio >= COVERAGE_BAR_YELLOW ? R.color.color_warning : R.color.color_rejected;
        binding.progressHandCoverage.setProgressTintList(
                ColorStateList.valueOf(ContextCompat.getColor(this, tint)));
        binding.tvHoldHandsWarning.setVisibility(showHoldWarning ? View.VISIBLE : View.GONE);
    }

    /** Advisory post-capture readout — NEVER auto-rejects; the clip is always saved. */
    private void showCoverageReadout(QualityResult result) {
        int handPct = Math.round(100f * result.handHitRate());
        int posePct = Math.round(100f * result.poseHitRate());
        boolean ok = result.coverageOk();
        String text = "Saved ✓  (offline pipeline will trim + quality-check)\n"
                + "Hand coverage:  " + handPct + "%\n"
                + "Pose coverage:  " + posePct + "%\n"
                + (ok ? "Coverage looks good" : "Low coverage — a re-record is recommended");
        binding.tvQualityGateResult.setText(text);
        binding.tvQualityGateResult.setBackgroundResource(ok ? R.drawable.bg_badge_green : R.drawable.bg_badge_red);
        binding.tvQualityGateResult.setTextColor(ContextCompat.getColor(this,
                ok ? R.color.color_accepted : R.color.color_warning));
        binding.tvQualityGateResult.setVisibility(View.VISIBLE);
        if (!ok) { binding.btnRedoRejected.setVisibility(View.VISIBLE); pulseRedoButton(); }
        else stopRedoPulse();
    }

    private void pulseRedoButton() {
        stopRedoPulse();
        redoPulseAnimator = ObjectAnimator.ofFloat(binding.btnRedoRejected, "alpha", 1f, 0.3f);
        redoPulseAnimator.setDuration(500);
        redoPulseAnimator.setRepeatMode(ObjectAnimator.REVERSE);
        redoPulseAnimator.setRepeatCount(ObjectAnimator.INFINITE);
        redoPulseAnimator.start();
    }

    private void stopRedoPulse() {
        if (redoPulseAnimator != null) { redoPulseAnimator.cancel(); redoPulseAnimator = null; }
        binding.btnRedoRejected.setAlpha(1f);
    }

    private void updateSessionCounters() {
        int captured  = sessionSummary.acceptedCount;
        int remaining = Math.max(0, sessionConfig.targetReps - captured);
        binding.tvAcceptedFraction.setText(captured + " / " + sessionConfig.targetReps + " captured");
        binding.tvRejectedCount.setText("Re-records: " + sessionSummary.rejectedCount);
        binding.tvRemainingCount.setText("Remaining: " + remaining);
        binding.progressBarAccepted.setProgress((int) ((float) captured / sessionConfig.targetReps * 100));
    }

    private void updateTrackingBadges(boolean hasHands, boolean hasPose) {
        setBadgeActive(binding.badgeHands, hasHands, "HANDS");
        setBadgeActive(binding.badgePose,  hasPose,  "POSE");
    }

    private void setBadgeActive(android.widget.TextView badge, boolean active, String label) {
        badge.setText(label);
        badge.setBackgroundResource(active ? R.drawable.bg_badge_green : R.drawable.bg_badge_gray);
        badge.setTextColor(ContextCompat.getColor(this,
                active ? R.color.color_accepted : R.color.color_badge_gray));
    }

    private void updateGuidanceForTracking() {
        if (!firstFrameSeen) { clearGuidance(); return; }
        if (!handsVisible && !poseVisible) showGuidance(getString(R.string.guidance_no_tracking));
        else if (!handsVisible) showGuidance(getString(R.string.guidance_no_hands));
        else if (!poseVisible) showGuidance(getString(R.string.guidance_no_pose));
        else clearGuidance();
    }

    private void showGuidance(String msg) {
        binding.tvGuidanceMessage.setText(msg);
        binding.tvGuidanceMessage.setVisibility(View.VISIBLE);
    }

    private void clearGuidance() { binding.tvGuidanceMessage.setVisibility(View.GONE); }

    private void setStartEnabled(boolean enabled, String text) {
        binding.btnStartSession.setEnabled(enabled);
        binding.btnStartSession.setAlpha(enabled ? 1f : 0.5f);
        binding.btnStartSession.setText(text);
    }

    private void showBlockingCaptureError(String message) {
        setStartEnabled(false, getString(R.string.btn_start_session));
        binding.tvCountdown.setText("!");
        binding.tvCountdown.setTextColor(ContextCompat.getColor(this, R.color.color_rejected));
        binding.tvCountdownSubtext.setText("Camera tracking is not ready");
        showGuidance(message);
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    private void flashOverlay(boolean accepted) {
        int color = ContextCompat.getColor(this, accepted ? R.color.color_accepted : R.color.color_rejected);
        binding.flashOverlay.setBackgroundColor(color);
        binding.tvResultOnCamera.setText(accepted ? getString(R.string.result_accepted) : getString(R.string.result_rejected));
        binding.tvResultOnCamera.setAlpha(1f);
        ObjectAnimator.ofFloat(binding.flashOverlay, "alpha", 0.35f, 0f).setDuration(500).start();
        ObjectAnimator labelFade = ObjectAnimator.ofFloat(binding.tvResultOnCamera, "alpha", 1f, 0f);
        labelFade.setStartDelay(300);
        labelFade.setDuration(400);
        labelFade.start();
    }

    private void togglePause() {
        if (stateMachine.getCurrentState() == RecordingState.PAUSED) {
            stateMachine.resume();
            binding.btnPauseRecording.setText(getString(R.string.btn_pause));
        } else {
            stateMachine.requestPause();
            binding.btnPauseRecording.setText(getString(R.string.btn_resume));
        }
    }

    private void confirmStop() {
        new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle(getString(R.string.dialog_stop_title))
                .setMessage(getString(R.string.dialog_stop_message))
                .setPositiveButton(getString(R.string.dialog_stop_confirm), (d, w) -> stopAndOpenReview())
                .setNegativeButton(android.R.string.cancel, null)
                .show();
    }

    private void stopAndOpenReview() {
        if (stateMachine != null) stateMachine.stop();
        finishSession();
    }

    private void finishSession() {
        if (sessionFinished) return;
        sessionFinished = true;
        stopRedoPulse();
        stopCameraAnalysis();
        metadataManager.saveSession(sessionConfig, sessionSummary);

        String saveDir = fileManager.getSampleDir(sessionConfig).getAbsolutePath();
        Intent intent = new Intent(this, ReviewActivity.class);
        intent.putExtra(ReviewActivity.EXTRA_SUMMARY,    sessionSummary);
        intent.putExtra(ReviewActivity.EXTRA_SAVE_DIR,   saveDir);
        intent.putExtra(ReviewActivity.EXTRA_SESSION_ID, sessionConfig.getSessionId());
        intent.putExtra(ReviewActivity.EXTRA_SIGNER,     signerProfile);
        intent.putExtra(ReviewActivity.EXTRA_CONFIG,     sessionConfig);
        intent.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
        if (mediaPipeHelper != null) mediaPipeHelper.close();
        finish();
    }

    private void stopCameraAnalysis() {
        captureActive = false;
        collecting = false;
        if (activeRecording != null) { activeRecording.stop(); activeRecording = null; }
        if (imageAnalysis != null) { imageAnalysis.clearAnalyzer(); imageAnalysis = null; }
        if (cameraProvider != null) { cameraProvider.unbindAll(); cameraProvider = null; }
        videoCapture = null;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        stopRedoPulse();
        stopCameraAnalysis();
        if (mediaPipeHelper != null) mediaPipeHelper.close();
        cameraExecutor.shutdown();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_CAMERA && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            initMediaPipeAndCamera();
        } else {
            finish();
        }
    }
}
