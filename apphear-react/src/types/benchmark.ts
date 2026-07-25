export type CameraLens = 'front' | 'back' | 'unspecified';

export type BenchmarkMode = 'rn01_camera_frame_output';

export interface BenchmarkSample {
  elapsedMs: number;
  frameCallbacks: number;
  droppedFrames: number;
  callbackFps: number;
  requestedFps: number;
  frameWidth?: number;
  frameHeight?: number;
}

export interface BenchmarkSession {
  schema: 'apphear.rn01.camera_fps.v1';
  mode: BenchmarkMode;
  startedAtIso: string;
  endedAtIso?: string;
  devicePlatform: string;
  lens: CameraLens;
  requestedFps: number;
  targetResolution: {
    width: number;
    height: number;
  };
  samples: BenchmarkSample[];
  notes: string[];
}
