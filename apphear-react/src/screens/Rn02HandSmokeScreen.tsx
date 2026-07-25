import React, {useCallback, useEffect, useState} from 'react';
import {Alert, Platform, ScrollView, Share, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import {MetricTile} from '../components/MetricTile';
import {Rn02HandBenchmarkModule} from '../native/AppHearVisionModule';
import type {Rn02HandBenchmarkSession} from '../types/rn02HandBenchmark';

export function Rn02HandSmokeScreen(): React.JSX.Element {
  const [isRunning, setIsRunning] = useState(false);
  const [session, setSession] = useState<Rn02HandBenchmarkSession | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setLastError(null);
    try {
      await Rn02HandBenchmarkModule.startHandBenchmark();
      setIsRunning(true);
      setSession(await Rn02HandBenchmarkModule.getLatestHandBenchmark());
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastError(message);
      Alert.alert('RN02 start failed', message);
    }
  }, []);

  const stop = useCallback(async () => {
    setLastError(null);
    try {
      setSession(await Rn02HandBenchmarkModule.stopHandBenchmark());
      setIsRunning(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastError(message);
      Alert.alert('RN02 stop failed', message);
    }
  }, []);

  const refresh = useCallback(async () => {
    setLastError(null);
    try {
      setSession(await Rn02HandBenchmarkModule.getLatestHandBenchmark());
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastError(message);
    }
  }, []);

  const exportSession = useCallback(async () => {
    if (session == null) return;
    await Share.share({
      title: 'AppHear RN02 hand benchmark',
      message: JSON.stringify(session, null, 2),
    });
  }, [session]);

  useEffect(() => {
    if (!isRunning) return undefined;
    const intervalId = setInterval(() => {
      Rn02HandBenchmarkModule.getLatestHandBenchmark()
        .then(setSession)
        .catch(error => {
          const message = error instanceof Error ? error.message : String(error);
          setLastError(message);
        });
    }, 1000);
    return () => clearInterval(intervalId);
  }, [isRunning]);

  const latestSample = session?.samples.at(-1);
  const canRunNative = Platform.OS === 'ios' || Platform.OS === 'android';

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.kicker}>RN02</Text>
      <Text style={styles.title}>Native Hand Landmarker</Text>
      <Text style={styles.subtitle}>Native hand-only MediaPipe benchmark. Frames stay off the React Native bridge.</Text>

      <View style={styles.controls}>
        <TouchableOpacity
          style={[styles.button, isRunning ? styles.stopButton : styles.startButton, !canRunNative && styles.disabled]}
          onPress={isRunning ? stop : start}
          disabled={!canRunNative}
        >
          <Text style={styles.buttonText}>{isRunning ? 'Stop' : 'Start'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.button, styles.secondaryButton]} onPress={refresh}>
          <Text style={styles.buttonText}>Refresh</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.button, styles.secondaryButton, session == null && styles.disabled]}
          onPress={exportSession}
          disabled={session == null}
        >
          <Text style={styles.buttonText}>Export</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.grid}>
        <MetricTile label="Platform" value={Platform.OS} tone={canRunNative ? 'good' : 'warn'} />
        <MetricTile label="Status" value={isRunning ? 'running' : 'idle'} />
        <MetricTile label="Samples" value={String(session?.samples.length ?? 0)} />
        <MetricTile label="FPS" value={latestSample?.processedFps.toFixed(1) ?? 'pending'} />
        <MetricTile label="P50" value={latestSample == null ? 'pending' : `${latestSample.handLatencyMsP50.toFixed(1)}ms`} />
        <MetricTile label="P95" value={latestSample == null ? 'pending' : `${latestSample.handLatencyMsP95.toFixed(1)}ms`} />
      </View>

      <View style={styles.panel}>
        <Text style={styles.panelLine}>Schema: {session?.schema ?? 'pending'}</Text>
        <Text style={styles.panelLine}>Model: {session?.modelAsset ?? 'hand_landmarker.task'}</Text>
        <Text style={styles.panelLine}>Running mode: {session?.runningMode ?? 'image'}</Text>
        <Text style={styles.panelLine}>Notes: {session?.notes.join(' ') ?? 'Awaiting native hand benchmark run.'}</Text>
        {lastError != null ? <Text style={styles.error}>Error: {lastError}</Text> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 14,
    padding: 16,
    paddingBottom: 32,
  },
  kicker: {
    color: '#38bdf8',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0,
  },
  title: {
    color: '#f8fafc',
    fontSize: 32,
    fontWeight: '900',
    letterSpacing: 0,
  },
  subtitle: {
    color: '#cbd5e1',
    fontSize: 15,
    lineHeight: 21,
    letterSpacing: 0,
  },
  controls: {
    flexDirection: 'row',
    gap: 10,
  },
  button: {
    flex: 1,
    minHeight: 54,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    paddingHorizontal: 10,
  },
  startButton: {
    backgroundColor: '#166534',
  },
  stopButton: {
    backgroundColor: '#991b1b',
  },
  secondaryButton: {
    backgroundColor: '#243140',
  },
  disabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: '#f8fafc',
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  panel: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2f343a',
    backgroundColor: '#171a1f',
    padding: 12,
    gap: 6,
  },
  panelLine: {
    color: '#cbd5e1',
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0,
  },
  error: {
    color: '#fca5a5',
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0,
  },
});

