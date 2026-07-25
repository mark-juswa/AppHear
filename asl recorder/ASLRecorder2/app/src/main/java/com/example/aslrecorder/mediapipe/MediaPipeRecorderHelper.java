package com.example.aslrecorder.mediapipe;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.util.Log;

import androidx.camera.core.ImageProxy;

import java.nio.ByteBuffer;

import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.core.Delegate;
import com.google.mediapipe.tasks.vision.core.RunningMode;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker;
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult;
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker;
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult;

/**
 * Hand + pose landmarkers for the recorder's LIVE OVERLAY and quality feedback only.
 *
 * <p><b>AppHear 3 parity (context/feature-schema.md, F01):</b> configured to MATCH the AppHear 3
 * runtime exactly — MediaPipe <b>IMAGE mode</b> (stateless per-frame, NOT VIDEO tracking),
 * <b>face OFF</b>, hand+pose only, det/presence/tracking confidence 0.5, using the byte-identical
 * {@code hand_landmarker.task} + {@code pose_landmarker_lite.task} the pipeline extracted ASL
 * Citizen with. These on-device landmarks drive the preview overlay + a non-destructive "hands
 * present" hint; they are NOT the dataset of record. The dataset is the recorded VIDEO, which the
 * offline Python pipeline re-extracts with the same IMAGE-mode extractor → guaranteed same landmark
 * dialect as ASL Citizen. (The removed AppHear 2 recorder used VIDEO mode + face + a baked 258
 * feature vector — all incompatible with our pipeline.)
 *
 * Called from the CameraX background executor — never the main thread.
 */
public class MediaPipeRecorderHelper {

    private static final String TAG = "MPRecorderHelper";

    // Byte-identical to android/app/src/main/assets/mediapipe/ in the AppHear 3 runtime app.
    private static final String HAND_MODEL = "hand_landmarker.task";
    private static final String POSE_MODEL = "pose_landmarker_lite.task";

    // AppHear 3 LandmarkerConfig values (parity — do not tune here in isolation).
    private static final int   NUM_HANDS = 2;
    private static final int   NUM_POSES = 1;
    private static final float CONF = 0.5f;

    public interface LandmarkResultListener {
        void onLandmarkResult(ResultBundle result);
        void onLandmarkError(String error);
    }

    private HandLandmarker handLandmarker;
    private PoseLandmarker poseLandmarker;

    private final LandmarkResultListener listener;
    private boolean initialized = false;
    private boolean closed = false;

    public MediaPipeRecorderHelper(Context context, LandmarkResultListener listener) {
        this.listener = listener;
        init(context);
    }

    private void init(Context context) {
        try {
            handLandmarker = HandLandmarker.createFromOptions(context,
                    HandLandmarker.HandLandmarkerOptions.builder()
                            .setBaseOptions(BaseOptions.builder()
                                    .setModelAssetPath(HAND_MODEL)
                                    .setDelegate(Delegate.CPU) // CPU/XNNPACK — matches pipeline extraction
                                    .build())
                            .setRunningMode(RunningMode.IMAGE)   // stateless per-frame (F01 parity)
                            .setNumHands(NUM_HANDS)
                            .setMinHandDetectionConfidence(CONF)
                            .setMinHandPresenceConfidence(CONF)
                            .setMinTrackingConfidence(CONF)
                            .build());

            poseLandmarker = PoseLandmarker.createFromOptions(context,
                    PoseLandmarker.PoseLandmarkerOptions.builder()
                            .setBaseOptions(BaseOptions.builder()
                                    .setModelAssetPath(POSE_MODEL)
                                    .setDelegate(Delegate.CPU)
                                    .build())
                            .setRunningMode(RunningMode.IMAGE)
                            .setNumPoses(NUM_POSES)
                            .setMinPoseDetectionConfidence(CONF)
                            .setMinPosePresenceConfidence(CONF)
                            .setMinTrackingConfidence(CONF)
                            .build());

            initialized = true;
            Log.d(TAG, "Landmarkers initialized (IMAGE mode, hand+pose, face off).");
        } catch (Exception e) {
            Log.e(TAG, "MediaPipe init failed: " + e.getMessage());
            if (listener != null) {
                listener.onLandmarkError("MediaPipe init failed: " + e.getMessage()
                        + "\nEnsure hand_landmarker.task + pose_landmarker_lite.task are in assets/");
            }
        }
    }

    /**
     * Process one preview frame for the live overlay + quality hint. IMAGE mode → each frame is
     * detected independently (no cross-frame tracking). Always closes the ImageProxy.
     */
    public synchronized void processFrame(ImageProxy imageProxy) {
        if (!initialized || closed) {
            imageProxy.close();
            return;
        }
        int rotation = imageProxy.getImageInfo().getRotationDegrees();
        Bitmap bitmap = rotateBitmapIfNeeded(imageProxyToBitmap(imageProxy), rotation);
        imageProxy.close();
        if (bitmap == null) return;

        try {
            // separate MPImage per landmarker so the two detect() calls never share state
            MPImage poseImg = new BitmapImageBuilder(bitmap).build();
            MPImage handImg = new BitmapImageBuilder(bitmap).build();
            PoseLandmarkerResult poseResult = poseLandmarker.detect(poseImg);
            HandLandmarkerResult handResult = handLandmarker.detect(handImg);
            if (listener != null) listener.onLandmarkResult(new ResultBundle(handResult, poseResult));
        } catch (Exception e) {
            Log.e(TAG, "Landmark detection failed: " + e.getMessage());
        }
    }

    // ── Image conversion ──────────────────────────────────────────────────────

    private Bitmap imageProxyToBitmap(ImageProxy imageProxy) {
        try {
            ImageProxy.PlaneProxy plane = imageProxy.getPlanes()[0];
            ByteBuffer buffer = plane.getBuffer();
            int width = imageProxy.getWidth();
            int height = imageProxy.getHeight();
            int rowStride = plane.getRowStride();
            int pixelStride = plane.getPixelStride();

            Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            if (pixelStride == 4 && rowStride == width * 4) {
                bitmap.copyPixelsFromBuffer(buffer);
                return bitmap;
            }
            byte[] row = new byte[rowStride];
            int[] pixels = new int[width * height];
            for (int y = 0; y < height; y++) {
                buffer.position(y * rowStride);
                buffer.get(row, 0, Math.min(rowStride, buffer.remaining()));
                for (int x = 0; x < width; x++) {
                    int offset = x * pixelStride;
                    int r = row[offset] & 0xFF;
                    int g = row[offset + 1] & 0xFF;
                    int b = row[offset + 2] & 0xFF;
                    int a = row[offset + 3] & 0xFF;
                    pixels[y * width + x] = (a << 24) | (r << 16) | (g << 8) | b;
                }
            }
            bitmap.setPixels(pixels, 0, width, 0, 0, width, height);
            return bitmap;
        } catch (Exception e) {
            Log.e(TAG, "Unable to convert ImageProxy to Bitmap.", e);
            return null;
        }
    }

    private Bitmap rotateBitmapIfNeeded(Bitmap bitmap, int rotationDegrees) {
        if (bitmap == null || rotationDegrees == 0) return bitmap;
        Matrix matrix = new Matrix();
        matrix.postRotate(rotationDegrees);
        Bitmap rotated = Bitmap.createBitmap(
                bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), matrix, true);
        if (rotated != bitmap) bitmap.recycle();
        return rotated;
    }

    public boolean isInitialized() { return initialized; }

    public synchronized void close() {
        if (closed) return;
        closed = true;
        initialized = false;
        try {
            if (handLandmarker != null) handLandmarker.close();
            if (poseLandmarker != null) poseLandmarker.close();
        } catch (Exception e) {
            Log.e(TAG, "Error closing landmarkers: " + e.getMessage());
        }
    }
}
