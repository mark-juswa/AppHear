package com.example.aslrecorder.recording;

import android.os.Handler;
import android.os.Looper;

import com.example.aslrecorder.model.QualityResult;
import com.example.aslrecorder.model.SessionSummary;

/**
 * Controls the recording flow for one session.
 *
 * State transitions:
 *   IDLE → PREPARE → COUNTDOWN → RECORDING → ANALYZING
 *        → ACCEPTED or REJECTED → REST → NEXT_SAMPLE
 *        → COUNTDOWN (loop) or COMPLETE
 *
 * Threading: external callers (camera thread, UI thread) drive transitions via public methods.
 * All listener callbacks are dispatched on the main thread.
 */
public class RecordingStateMachine {

    public interface RecordingStateListener {
        /** Called on main thread whenever the state changes. */
        void onStateChanged(RecordingState newState);

        /** Called on main thread during COUNTDOWN — tick is 3, 2, 1. */
        void onCountdownTick(int secondsRemaining);

        /** Called on main thread with the quality result right after ANALYZING. */
        void onSampleResult(QualityResult result);

        /** Called on main thread when all target accepted samples have been collected. */
        void onSessionComplete(SessionSummary summary);
    }

    private static final long COUNTDOWN_TICK_MS = 900L;
    private static final long SIGN_FLASH_MS     = 300L;
    private static final long REST_DURATION_MS  = 1500L;
    private static final long NEXT_DELAY_MS     = 200L;
    // Video-primary capture: record a fixed window per attempt (native fps), then the offline
    // D1/D2 stage trims onset→release. A citation sign is ~0.85s; 3.0s comfortably contains it
    // plus lead-in/out, matching how ASL Citizen clips are recorded then trimmed.
    private static final long RECORDING_DURATION_MS = 3000L;

    private volatile RecordingState currentState = RecordingState.IDLE;
    private final int targetCount;
    private final RecordingStateListener listener;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private int acceptedCount = 0;
    private boolean trackingGood = false;
    private boolean pauseRequested = false;
    private SessionSummary sessionSummary;

    // Held while countdown is in progress so we can cancel it if tracking drops
    private Runnable pendingSignTrigger;

    public RecordingStateMachine(int targetCount,
                                 RecordingStateListener listener,
                                 SessionSummary sessionSummary) {
        this.targetCount    = targetCount;
        this.listener       = listener;
        this.sessionSummary = sessionSummary;
        this.acceptedCount  = sessionSummary != null ? sessionSummary.acceptedCount : 0;
    }

    // ── External driver methods (may be called from any thread) ──────────────

    /** User tapped START. Transitions IDLE → PREPARE → COUNTDOWN immediately. */
    public synchronized void start() {
        if (currentState != RecordingState.IDLE) return;
        pauseRequested = false;
        transitionTo(RecordingState.PREPARE);
        // Always start the countdown — don't wait for a tracking change event.
        mainHandler.post(this::startCountdown);
    }

    /** User tapped PAUSE. Gracefully pauses after the current REST period. */
    public synchronized void requestPause() {
        if (currentState == RecordingState.COMPLETE
                || currentState == RecordingState.IDLE) return;
        pauseRequested = true;
    }

    /** User tapped RESUME after a pause. */
    public synchronized void resume() {
        if (currentState != RecordingState.PAUSED) return;
        pauseRequested = false;
        transitionTo(RecordingState.PREPARE);
        mainHandler.post(this::startCountdown);
    }

    /**
     * Called every frame from the MediaPipe callback.
     * Only updates the tracking flag — guidance logic in RecordingActivity uses this.
     * No longer gates the countdown on tracking state.
     */
    public synchronized void onTrackingStateUpdate(boolean handsOk, boolean poseOk) {
        trackingGood = handsOk && poseOk;
    }

    /** Called by RecordingActivity with the on-device coverage result after ANALYZING. Video-
     *  primary + non-destructive: every recorded clip is KEPT (offline Q gate + review decide).
     *  Low coverage is surfaced as a warning, not an auto-reject. */
    public synchronized void onQualityResult(QualityResult result) {
        if (currentState != RecordingState.ANALYZING) return;
        acceptedCount++;
        sessionSummary.recordAcceptance();
        transitionTo(RecordingState.ACCEPTED);
        mainHandler.post(() -> listener.onSampleResult(result));
        scheduleRest();
    }

    /** User tapped STOP. Ends session immediately after current state finishes. */
    public synchronized void stop() {
        if (currentState == RecordingState.COMPLETE) return;
        cancelPendingTrigger();
        transitionTo(RecordingState.COMPLETE);
        mainHandler.post(() -> listener.onSessionComplete(sessionSummary));
    }

    // ── Internal state transitions ────────────────────────────────────────────

    private void startCountdown() {
        synchronized (this) {
            if (currentState != RecordingState.PREPARE) return;
            transitionTo(RecordingState.COUNTDOWN);
        }

        // 3
        mainHandler.post(() -> listener.onCountdownTick(3));

        // 2
        mainHandler.postDelayed(() -> {
            synchronized (this) { if (currentState != RecordingState.COUNTDOWN) return; }
            listener.onCountdownTick(2);
        }, COUNTDOWN_TICK_MS);

        // 1
        mainHandler.postDelayed(() -> {
            synchronized (this) { if (currentState != RecordingState.COUNTDOWN) return; }
            listener.onCountdownTick(1);
        }, COUNTDOWN_TICK_MS * 2);

        // SIGN! → trigger recording, then auto-stop after the fixed recording window.
        pendingSignTrigger = () -> {
            synchronized (this) {
                if (currentState != RecordingState.COUNTDOWN) return;
                listener.onCountdownTick(0); // 0 = "SIGN!"
                transitionTo(RecordingState.RECORDING);
            }
            // End RECORDING on a timer (video-primary; no fixed frame count).
            mainHandler.postDelayed(() -> {
                synchronized (this) {
                    if (currentState != RecordingState.RECORDING) return;
                    transitionTo(RecordingState.ANALYZING);
                }
            }, RECORDING_DURATION_MS);
        };
        mainHandler.postDelayed(pendingSignTrigger, COUNTDOWN_TICK_MS * 3);
    }

    private void scheduleRest() {
        mainHandler.postDelayed(() -> {
            synchronized (this) {
                if (currentState != RecordingState.ACCEPTED
                        && currentState != RecordingState.REJECTED) return;
                transitionTo(RecordingState.REST);
            }
        }, 500L); // small delay so the flash is visible

        mainHandler.postDelayed(() -> {
            synchronized (this) {
                if (currentState != RecordingState.REST) return;
                transitionToNextSample();
            }
        }, REST_DURATION_MS);
    }

    private void transitionToNextSample() {
        if (acceptedCount >= targetCount) {
            transitionTo(RecordingState.COMPLETE);
            listener.onSessionComplete(sessionSummary);
            return;
        }

        if (pauseRequested) {
            pauseRequested = false;
            transitionTo(RecordingState.PAUSED);
            return;
        }

        transitionTo(RecordingState.NEXT_SAMPLE);
        mainHandler.postDelayed(() -> {
            synchronized (this) {
                if (currentState != RecordingState.NEXT_SAMPLE) return;
                transitionTo(RecordingState.PREPARE);
                // Always start the next countdown — no tracking gate.
                mainHandler.post(this::startCountdown);
            }
        }, NEXT_DELAY_MS);
    }

    private void transitionTo(RecordingState newState) {
        currentState = newState;
        mainHandler.post(() -> listener.onStateChanged(newState));
    }

    private void cancelPendingTrigger() {
        if (pendingSignTrigger != null) {
            mainHandler.removeCallbacks(pendingSignTrigger);
            pendingSignTrigger = null;
        }
    }

    // ── Accessors ─────────────────────────────────────────────────────────────

    public RecordingState getCurrentState() { return currentState; }
    public int getAcceptedCount()           { return acceptedCount; }
    public boolean isTrackingGood()         { return trackingGood; }
}
