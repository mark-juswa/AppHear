import React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import type {CameraLens} from '../types/benchmark';

interface BenchmarkControlsProps {
  isRunning: boolean;
  lens: CameraLens;
  canExport: boolean;
  canToggleLens: boolean;
  onToggleRun: () => void;
  onToggleLens: () => void;
  onReset: () => void;
  onExport: () => void;
}

export function BenchmarkControls({
  isRunning,
  lens,
  canExport,
  canToggleLens,
  onToggleRun,
  onToggleLens,
  onReset,
  onExport,
}: BenchmarkControlsProps): React.JSX.Element {
  const lensLabel = lens === 'front' ? 'Front' : lens === 'back' ? 'Back' : 'Camera';

  return (
    <View style={styles.row}>
      <Pressable style={[styles.button, isRunning ? styles.stop : styles.start]} onPress={onToggleRun}>
        <Text style={styles.buttonText}>{isRunning ? 'Stop' : 'Start'}</Text>
      </Pressable>
      <Pressable style={[styles.button, !canToggleLens && styles.disabled]} onPress={onToggleLens} disabled={!canToggleLens}>
        <Text style={styles.buttonText}>{lensLabel}</Text>
      </Pressable>
      <Pressable style={styles.button} onPress={onReset}>
        <Text style={styles.buttonText}>Reset</Text>
      </Pressable>
      <Pressable style={[styles.button, !canExport && styles.disabled]} onPress={onExport} disabled={!canExport}>
        <Text style={styles.buttonText}>Export</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: 8,
  },
  button: {
    flex: 1,
    minHeight: 44,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#26313d',
  },
  start: {
    backgroundColor: '#166534',
  },
  stop: {
    backgroundColor: '#7f1d1d',
  },
  disabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: '#f8fafc',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0,
  },
});