import {Platform} from 'react-native';
import {RN01_LOG_SCHEMA, RN01_REQUESTED_FPS, RN01_TARGET_RESOLUTION} from '../app/constants';
import type {BenchmarkSample, BenchmarkSession, CameraLens} from '../types/benchmark';

export function createBenchmarkSession(lens: CameraLens): BenchmarkSession {
  return {
    schema: RN01_LOG_SCHEMA,
    mode: 'rn01_camera_frame_output',
    startedAtIso: new Date().toISOString(),
    devicePlatform: Platform.OS,
    lens,
    requestedFps: RN01_REQUESTED_FPS,
    targetResolution: RN01_TARGET_RESOLUTION,
    samples: [],
    notes: [
      'RN01 only: VisionCamera frame callback count; no MediaPipe, no TFLite, no recognition.',
      'Frames are disposed immediately. Do not interpret this as landmark FPS.',
    ],
  };
}

export function appendSample(session: BenchmarkSession, sample: BenchmarkSample): BenchmarkSession {
  return {
    ...session,
    samples: [...session.samples, sample],
  };
}

export function closeBenchmarkSession(session: BenchmarkSession): BenchmarkSession {
  return {
    ...session,
    endedAtIso: new Date().toISOString(),
  };
}

export function serializeBenchmarkSession(session: BenchmarkSession): string {
  return JSON.stringify(closeBenchmarkSession(session), null, 2);
}
