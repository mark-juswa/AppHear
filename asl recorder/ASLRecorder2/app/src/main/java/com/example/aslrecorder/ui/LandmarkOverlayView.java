package com.example.aslrecorder.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.View;

import com.example.aslrecorder.mediapipe.ResultBundle;
import com.google.mediapipe.tasks.components.containers.NormalizedLandmark;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult;
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult;

import java.util.List;

/**
 * Transparent overlay drawn on top of the CameraX PreviewView.
 *
 * Draws:
 *   - Hand skeleton: 21 landmarks + MediaPipe hand connections
 *   - Shoulder line: left shoulder → right shoulder
 *   - Nose dot: small yellow circle at nose position
 *
 * Coordinate system:
 *   MediaPipe returns normalized [0,1] coordinates.
 *   For front camera, X is mirrored (landmarkX → 1 - landmarkX) to match the mirrored preview.
 *   Y is not mirrored.
 */
public class LandmarkOverlayView extends View {

    // ── Hand connections (MediaPipe hand topology) ────────────────────────────
    private static final int[][] HAND_CONNECTIONS = {
            {0, 1}, {1, 2}, {2, 3}, {3, 4},       // Thumb
            {0, 5}, {5, 6}, {6, 7}, {7, 8},         // Index
            {5, 9}, {9, 10}, {10, 11}, {11, 12},    // Middle
            {9, 13}, {13, 14}, {14, 15}, {15, 16},  // Ring
            {13, 17}, {17, 18}, {18, 19}, {19, 20}, // Pinky
            {0, 17}                                  // Palm base
    };

    // ── Pose landmark indices ─────────────────────────────────────────────────
    private static final int NOSE_IDX           = 0;
    private static final int LEFT_SHOULDER_IDX  = 11;
    private static final int RIGHT_SHOULDER_IDX = 12;
    private static final int LEFT_ELBOW_IDX     = 13;
    private static final int RIGHT_ELBOW_IDX    = 14;
    private static final int LEFT_WRIST_IDX     = 15;
    private static final int RIGHT_WRIST_IDX    = 16;

    // ── Paints ────────────────────────────────────────────────────────────────
    private final Paint handLinePaint;
    private final Paint handDotPaint;
    private final Paint wristDotPaint;
    private final Paint shoulderLinePaint;
    private final Paint shoulderDotPaint;
    private final Paint noseDotPaint;

    // ── State ─────────────────────────────────────────────────────────────────
    private ResultBundle latestResult;
    private boolean isFrontCamera = true;

    public LandmarkOverlayView(Context context) {
        this(context, null);
    }

    public LandmarkOverlayView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setWillNotDraw(false);

        handLinePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        handLinePaint.setColor(Color.WHITE);
        handLinePaint.setStrokeWidth(3f);
        handLinePaint.setStyle(Paint.Style.STROKE);

        handDotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        handDotPaint.setColor(Color.parseColor("#A7F3D0")); // mint green
        handDotPaint.setStyle(Paint.Style.FILL);

        wristDotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        wristDotPaint.setColor(Color.parseColor("#22C55E")); // bright green
        wristDotPaint.setStyle(Paint.Style.FILL);

        shoulderLinePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        shoulderLinePaint.setColor(Color.parseColor("#60A5FA")); // blue
        shoulderLinePaint.setStrokeWidth(4f);
        shoulderLinePaint.setStyle(Paint.Style.STROKE);

        shoulderDotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        shoulderDotPaint.setColor(Color.parseColor("#93C5FD")); // light blue
        shoulderDotPaint.setStyle(Paint.Style.FILL);

        noseDotPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        noseDotPaint.setColor(Color.parseColor("#FDE68A")); // yellow
        noseDotPaint.setStyle(Paint.Style.FILL);
    }

    /** Called from the MediaPipe callback (background thread). Triggers a redraw on the main thread. */
    public void updateResults(ResultBundle result, boolean frontCamera) {
        this.latestResult  = result;
        this.isFrontCamera = frontCamera;
        postInvalidate(); // thread-safe invalidate
    }

    public void clearResults() {
        latestResult = null;
        postInvalidate();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (latestResult == null) return;

        drawPose(canvas, latestResult);
        drawHands(canvas, latestResult);
    }

    // ── Drawing ───────────────────────────────────────────────────────────────

    private void drawHands(Canvas canvas, ResultBundle bundle) {
        HandLandmarkerResult handResult = bundle.handLandmarkerResult;
        if (handResult == null || handResult.landmarks().isEmpty()) return;

        for (List<NormalizedLandmark> hand : handResult.landmarks()) {
            drawHandSkeleton(canvas, hand);
        }
    }

    private void drawHandSkeleton(Canvas canvas, List<NormalizedLandmark> landmarks) {
        if (landmarks == null || landmarks.isEmpty()) return;
        float w = getWidth(), h = getHeight();

        // Draw connections
        for (int[] conn : HAND_CONNECTIONS) {
            if (conn[0] >= landmarks.size() || conn[1] >= landmarks.size()) continue;
            NormalizedLandmark a = landmarks.get(conn[0]);
            NormalizedLandmark b = landmarks.get(conn[1]);
            canvas.drawLine(
                    toPixelX(a.x(), w), toPixelY(a.y(), h),
                    toPixelX(b.x(), w), toPixelY(b.y(), h),
                    handLinePaint);
        }

        // Draw landmark dots
        for (int i = 0; i < landmarks.size(); i++) {
            NormalizedLandmark lm = landmarks.get(i);
            float px = toPixelX(lm.x(), w);
            float py = toPixelY(lm.y(), h);
            Paint dotPaint = (i == 0) ? wristDotPaint : handDotPaint;
            float radius   = (i == 0) ? 8f : 5f;
            canvas.drawCircle(px, py, radius, dotPaint);
        }
    }

    private void drawPose(Canvas canvas, ResultBundle bundle) {
        PoseLandmarkerResult poseResult = bundle.poseLandmarkerResult;
        if (poseResult == null || poseResult.landmarks().isEmpty()) return;

        List<NormalizedLandmark> landmarks = poseResult.landmarks().get(0);
        if (landmarks.size() <= RIGHT_WRIST_IDX) return;

        float w = getWidth(), h = getHeight();

        // Shoulder line
        NormalizedLandmark ls = landmarks.get(LEFT_SHOULDER_IDX);
        NormalizedLandmark rs = landmarks.get(RIGHT_SHOULDER_IDX);
        float lsVis = ls.visibility().isPresent() ? ls.visibility().get() : 0f;
        float rsVis = rs.visibility().isPresent() ? rs.visibility().get() : 0f;

        if (lsVis > 0.3f && rsVis > 0.3f) {
            canvas.drawLine(
                    toPixelX(ls.x(), w), toPixelY(ls.y(), h),
                    toPixelX(rs.x(), w), toPixelY(rs.y(), h),
                    shoulderLinePaint);
            canvas.drawCircle(toPixelX(ls.x(), w), toPixelY(ls.y(), h), 8f, shoulderDotPaint);
            canvas.drawCircle(toPixelX(rs.x(), w), toPixelY(rs.y(), h), 8f, shoulderDotPaint);
        }

        // Elbow and wrist dots
        int[] upperBodyDots = {LEFT_ELBOW_IDX, RIGHT_ELBOW_IDX, LEFT_WRIST_IDX, RIGHT_WRIST_IDX};
        for (int idx : upperBodyDots) {
            if (idx >= landmarks.size()) continue;
            NormalizedLandmark lm = landmarks.get(idx);
            float vis = lm.visibility().isPresent() ? lm.visibility().get() : 0f;
            if (vis > 0.3f) {
                canvas.drawCircle(toPixelX(lm.x(), w), toPixelY(lm.y(), h), 6f, shoulderDotPaint);
            }
        }

        // Nose dot
        NormalizedLandmark nose = landmarks.get(NOSE_IDX);
        float noseVis = nose.visibility().isPresent() ? nose.visibility().get() : 0f;
        if (noseVis > 0.3f) {
            canvas.drawCircle(toPixelX(nose.x(), w), toPixelY(nose.y(), h), 7f, noseDotPaint);
        }
    }

    // ── Coordinate helpers ────────────────────────────────────────────────────

    private float toPixelX(float normalizedX, float viewWidth) {
        // Mirror X for front camera — MediaPipe raw coords are not yet mirrored
        return isFrontCamera
                ? (1f - normalizedX) * viewWidth
                : normalizedX * viewWidth;
    }

    private float toPixelY(float normalizedY, float viewHeight) {
        return normalizedY * viewHeight;
    }
}
