import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Alert, Platform, ScrollView, Share, StyleSheet, Text, View} from 'react-native';
import {
  Camera,
  CommonResolutions,
  useCameraDevices,
  useCameraPermission,
  useFrameOutput,
  type CameraDevice,
  type FrameDroppedReason,
} from 'react-native-vision-camera';
import {scheduleOnRN} from 'react-native-worklets';
import {RN01_REQUESTED_FPS, RN01_TARGET_RESOLUTION} from '../app/constants';
import {BenchmarkControls} from '../components/BenchmarkControls';
import {BenchmarkSummary} from '../components/BenchmarkSummary';
import {MetricTile} from '../components/MetricTile';
import {useRollingFps} from '../hooks/useRollingFps';
import {
  appendSample,
  createBenchmarkSession,
  serializeBenchmarkSession,
} from '../stores/benchmarkSession';
import type {BenchmarkSession, CameraLens} from '../types/benchmark';

const RESOLUTION = CommonResolutions?.VGA_16_9 ?? RN01_TARGET_RESOLUTION;

export function Rn01CameraSmokeScreen(): React.JSX.Element {
  const permission = useCameraPermission();
  const devices = useCameraDevices();
  const fps = useRollingFps();
  const [lens, setLens] = useState<CameraLens>('front');
  const [isRunning, setIsRunning] = useState(false);
  const [session, setSession] = useState<BenchmarkSession | null>(null);
  const [exportedJson, setExportedJson] = useState('');
  const frameSizeRef = useRef<{width?: number; height?: number}>({});
  const lastSampleFrameCountRef = useRef(0);

  const frontDevice = devices.find((device: CameraDevice) => device.position === 'front');
  const backDevice = devices.find((device: CameraDevice) => device.position === 'back');
  const selectedDevice = useMemo<CameraDevice | undefined>(() => {
    if (lens === 'front') return frontDevice ?? backDevice ?? devices[0];
    if (lens === 'back') return backDevice ?? frontDevice ?? devices[0];
    return devices[0];
  }, [backDevice, devices, frontDevice, lens]);
  const actualLens: CameraLens = selectedDevice?.position === 'front' || selectedDevice?.position === 'back'
    ? selectedDevice.position
    : 'unspecified';
  const canToggleLens = frontDevice != null && backDevice != null;
  const detectedCameras = devices
    .map((device: CameraDevice) => `${device.position}:${device.localizedName}`)
    .join(', ') || 'none';

  useEffect(() => {
    if (!permission.hasPermission) {
      permission.requestPermission().catch(() => undefined);
    }
  }, [permission]);

  useEffect(() => {
    if (selectedDevice == null) return;
    if ((selectedDevice.position === 'front' || selectedDevice.position === 'back') && selectedDevice.position !== lens) {
      setLens(selectedDevice.position);
    }
  }, [lens, selectedDevice]);

  useEffect(() => {
    if (!isRunning || fps.elapsedMs === 0 || fps.frameCallbacks === lastSampleFrameCountRef.current) return;
    lastSampleFrameCountRef.current = fps.frameCallbacks;
    setSession(prev => {
      if (prev == null) return prev;
      return appendSample(prev, {
        elapsedMs: fps.elapsedMs,
        frameCallbacks: fps.frameCallbacks,
        droppedFrames: fps.droppedFrames,
        callbackFps: fps.callbackFps,
        requestedFps: RN01_REQUESTED_FPS,
        frameWidth: frameSizeRef.current.width,
        frameHeight: frameSizeRef.current.height,
      });
    });
  }, [fps.callbackFps, fps.droppedFrames, fps.elapsedMs, fps.frameCallbacks, isRunning]);

  const recordFrameFromWorklet = useCallback((timestampMs: number, width: number, height: number) => {
    frameSizeRef.current = {width, height};
    fps.recordFrame(timestampMs);
  }, [fps]);

  const recordDropFromWorklet = useCallback((_reason: FrameDroppedReason) => {
    fps.recordDrop();
  }, [fps]);

  const frameOutput = useFrameOutput({
    targetResolution: RESOLUTION,
    pixelFormat: 'yuv',
    dropFramesWhileBusy: true,
    allowDeferredStart: true,
    onFrameDropped(reason) {
      'worklet';
      scheduleOnRN(recordDropFromWorklet, reason);
    },
    onFrame(frame) {
      'worklet';
      try {
        scheduleOnRN(recordFrameFromWorklet, Date.now(), frame.width, frame.height);
      } finally {
        frame.dispose();
      }
    },
  });

  const constraints = useMemo(() => [{fps: RN01_REQUESTED_FPS}], []);

  const start = useCallback(() => {
    fps.reset();
    frameSizeRef.current = {};
    lastSampleFrameCountRef.current = 0;
    setExportedJson('');
    setSession(createBenchmarkSession(actualLens));
    setIsRunning(true);
  }, [actualLens, fps]);

  const stop = useCallback(() => {
    setIsRunning(false);
  }, []);

  const reset = useCallback(() => {
    stop();
    fps.reset();
    frameSizeRef.current = {};
    lastSampleFrameCountRef.current = 0;
    setSession(null);
    setExportedJson('');
  }, [fps, stop]);

  const toggleRun = useCallback(() => {
    if (isRunning) stop(); else start();
  }, [isRunning, start, stop]);

  const toggleLens = useCallback(() => {
    if (isRunning || !canToggleLens) return;
    setLens(current => (current === 'front' ? 'back' : 'front'));
  }, [canToggleLens, isRunning]);

  const exportSession = useCallback(async () => {
    if (session == null) return;
    const json = serializeBenchmarkSession(session);
    setExportedJson(json);
    try {
      await Share.share({message: json, title: 'AppHear RN01 camera benchmark'});
    } catch (error) {
      Alert.alert('Export failed', error instanceof Error ? error.message : 'Unknown export error');
    }
  }, [session]);

  if (!permission.hasPermission) {
    return (
      <View style={styles.centered}>
        <Text style={styles.title}>Camera permission required</Text>
        <Text style={styles.body}>Grant camera access to run the RN01 FPS smoke test.</Text>
      </View>
    );
  }

  if (selectedDevice == null) {
    return (
      <View style={styles.centered}>
        <Text style={styles.title}>No camera found</Text>
        <Text style={styles.body}>VisionCamera did not report an available camera device on this phone.</Text>
      </View>
    );
  }

  const frameSize = frameSizeRef.current.width && frameSizeRef.current.height
    ? `${frameSizeRef.current.width}x${frameSizeRef.current.height}`
    : 'pending';
  const fpsTone = fps.callbackFps >= 50 ? 'good' : fps.callbackFps > 0 && fps.callbackFps < 30 ? 'warn' : 'normal';

  return (
    <View style={styles.root}>
      <View style={styles.cameraWrap}>
        <Camera
          style={StyleSheet.absoluteFill}
          device={selectedDevice}
          isActive={isRunning}
          outputs={[frameOutput]}
          constraints={constraints}
          onInterruptionStarted={(reason: unknown) => {
            setSession(prev => prev == null ? prev : {...prev, notes: [...prev.notes, `interruption_started:${String(reason)}`]});
          }}
          onInterruptionEnded={() => {
            setSession(prev => prev == null ? prev : {...prev, notes: [...prev.notes, 'interruption_ended']});
          }}
        />
        {!isRunning && (
          <View style={styles.pausedOverlay}>
            <Text style={styles.pausedText}>Camera paused</Text>
          </View>
        )}
      </View>

      <ScrollView style={styles.panel} contentContainerStyle={styles.panelContent}>
        <View>
          <Text style={styles.kicker}>RN01</Text>
          <Text style={styles.heading}>Camera FPS Smoke</Text>
          <Text style={styles.body}>No MediaPipe, no TFLite, no recognition. Frames are counted and disposed.</Text>
        </View>

        <BenchmarkControls
          isRunning={isRunning}
          lens={actualLens}
          canExport={session != null && session.samples.length > 0}
          canToggleLens={canToggleLens}
          onToggleRun={toggleRun}
          onToggleLens={toggleLens}
          onReset={reset}
          onExport={exportSession}
        />

        <View style={styles.metricsGrid}>
          <MetricTile label="Callback FPS" value={fps.callbackFps.toFixed(1)} tone={fpsTone} />
          <MetricTile label="Frames" value={String(fps.frameCallbacks)} />
          <MetricTile label="Dropped" value={String(fps.droppedFrames)} tone={fps.droppedFrames > 0 ? 'warn' : 'normal'} />
          <MetricTile label="Elapsed" value={`${Math.floor(fps.elapsedMs / 1000)}s`} />
          <MetricTile label="Lens" value={actualLens} />
          <MetricTile label="Frame" value={frameSize} />
        </View>

        <View style={styles.metaPanel}>
          <Text style={styles.metaText}>Platform: {Platform.OS}</Text>
          <Text style={styles.metaText}>Requested FPS: {RN01_REQUESTED_FPS}</Text>
          <Text style={styles.metaText}>Target frame output: {RN01_TARGET_RESOLUTION.width}x{RN01_TARGET_RESOLUTION.height}</Text>
          <Text style={styles.metaText}>Detected cameras: {detectedCameras}</Text>
        </View>

        <BenchmarkSummary session={session} exportedJson={exportedJson} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#101214',
  },
  cameraWrap: {
    height: '42%',
    minHeight: 260,
    backgroundColor: '#050607',
    overflow: 'hidden',
  },
  panel: {
    flex: 1,
  },
  panelContent: {
    padding: 14,
    gap: 12,
  },
  kicker: {
    color: '#38bdf8',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0,
  },
  heading: {
    color: '#f8fafc',
    fontSize: 24,
    fontWeight: '900',
    letterSpacing: 0,
  },
  title: {
    color: '#f8fafc',
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: 0,
  },
  body: {
    color: '#cbd5e1',
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0,
  },
  metricsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  metaPanel: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2f343a',
    backgroundColor: '#12161b',
    padding: 10,
    gap: 2,
  },
  metaText: {
    color: '#aab1ba',
    fontSize: 12,
    letterSpacing: 0,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 8,
    backgroundColor: '#101214',
  },
  pausedOverlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.64)',
  },
  pausedText: {
    color: '#f8fafc',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0,
  },
});