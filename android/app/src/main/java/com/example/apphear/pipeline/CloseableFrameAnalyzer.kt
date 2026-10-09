package com.example.apphear.pipeline

import androidx.camera.core.ImageAnalysis

/** CameraX analyzer whose workers are stopped before the shared landmarker bundle is closed. */
interface CloseableFrameAnalyzer : ImageAnalysis.Analyzer, AutoCloseable
