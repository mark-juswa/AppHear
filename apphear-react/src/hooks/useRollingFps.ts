import {useCallback, useMemo, useRef, useState} from 'react';
import {RN01_SAMPLE_PERIOD_MS} from '../app/constants';

export interface RollingFpsState {
  frameCallbacks: number;
  droppedFrames: number;
  callbackFps: number;
  elapsedMs: number;
}

export interface RollingFpsController extends RollingFpsState {
  reset: () => void;
  recordFrame: (timestampMs: number) => void;
  recordDrop: () => void;
}

const initialState: RollingFpsState = {
  frameCallbacks: 0,
  droppedFrames: 0,
  callbackFps: 0,
  elapsedMs: 0,
};

export function useRollingFps(): RollingFpsController {
  const startedAtRef = useRef<number | null>(null);
  const lastPublishAtRef = useRef<number | null>(null);
  const lastPublishFrameCountRef = useRef(0);
  const frameCountRef = useRef(0);
  const droppedFrameCountRef = useRef(0);
  const [state, setState] = useState<RollingFpsState>(initialState);

  const reset = useCallback(() => {
    startedAtRef.current = null;
    lastPublishAtRef.current = null;
    lastPublishFrameCountRef.current = 0;
    frameCountRef.current = 0;
    droppedFrameCountRef.current = 0;
    setState(initialState);
  }, []);

  const publish = useCallback((timestampMs: number) => {
    const startedAt = startedAtRef.current ?? timestampMs;
    const lastPublishAt = lastPublishAtRef.current ?? timestampMs;
    const elapsedSincePublish = timestampMs - lastPublishAt;
    if (elapsedSincePublish < RN01_SAMPLE_PERIOD_MS) return;

    const frameDelta = frameCountRef.current - lastPublishFrameCountRef.current;
    const callbackFps = frameDelta / (elapsedSincePublish / 1000);
    lastPublishAtRef.current = timestampMs;
    lastPublishFrameCountRef.current = frameCountRef.current;

    setState({
      frameCallbacks: frameCountRef.current,
      droppedFrames: droppedFrameCountRef.current,
      callbackFps,
      elapsedMs: timestampMs - startedAt,
    });
  }, []);

  const recordFrame = useCallback((timestampMs: number) => {
    if (startedAtRef.current == null) {
      startedAtRef.current = timestampMs;
      lastPublishAtRef.current = timestampMs;
    }
    frameCountRef.current += 1;
    publish(timestampMs);
  }, [publish]);

  const recordDrop = useCallback(() => {
    droppedFrameCountRef.current += 1;
    const now = Date.now();
    if (startedAtRef.current == null) {
      startedAtRef.current = now;
      lastPublishAtRef.current = now;
    }
    publish(now);
  }, [publish]);

  return useMemo(() => ({...state, reset, recordFrame, recordDrop}), [state, reset, recordFrame, recordDrop]);
}
