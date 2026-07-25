export interface RecognitionSnapshot {
  processedFps: number;
  captureFps: number;
  droppedFrames: number;
  lowFps: boolean;
  handMsP50?: number;
  handMsP95?: number;
  poseMsP50?: number;
  poseMsP95?: number;
  wallMsP50?: number;
  wallMsP95?: number;
  topCandidates: string[];
  committedGloss?: string;
  sentenceText: string;
}
