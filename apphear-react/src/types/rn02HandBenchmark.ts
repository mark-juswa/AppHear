export const RN02_HAND_SCHEMA = 'apphear.rn02.hand_landmarker.v1' as const;

export type Rn02RunningMode = 'image' | 'video' | 'liveStream';
export type Rn02DevicePlatform = 'ios' | 'android';
export type Rn02Mode = 'rn02_ios_hand_only' | 'rn02_android_hand_only';

export interface Rn02HandSample {
  elapsedMs: number;
  processedFrames: number;
  skippedFrames: number;
  handLatencyMsP50: number;
  handLatencyMsP95: number;
  processedFps: number;
  handHitRate: number;
  twoHandHitRate: number;
  frameWidth?: number;
  frameHeight?: number;
}

export interface Rn02HandBenchmarkSession {
  schema: typeof RN02_HAND_SCHEMA | 'apphear.rn02.ios_hand_landmarker.v1';
  mode: Rn02Mode;
  startedAtIso: string;
  endedAtIso?: string;
  devicePlatform: Rn02DevicePlatform;
  deviceModel?: string;
  runningMode: Rn02RunningMode;
  modelAsset: 'hand_landmarker.task';
  samples: Rn02HandSample[];
  notes: string[];
}
