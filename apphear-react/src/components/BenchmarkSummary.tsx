import React from 'react';
import {ScrollView, StyleSheet, Text, View} from 'react-native';
import type {BenchmarkSession} from '../types/benchmark';

interface BenchmarkSummaryProps {
  session: BenchmarkSession | null;
  exportedJson: string;
}

export function BenchmarkSummary({session, exportedJson}: BenchmarkSummaryProps): React.JSX.Element {
  const latest = session != null && session.samples.length > 0 ? session.samples[session.samples.length - 1] : undefined;
  return (
    <View style={styles.panel}>
      <Text style={styles.title}>Benchmark Log</Text>
      <Text style={styles.line}>Samples: {session?.samples.length ?? 0}</Text>
      <Text style={styles.line}>Latest FPS: {latest ? latest.callbackFps.toFixed(1) : 'n/a'}</Text>
      <Text style={styles.line}>Dropped: {latest ? latest.droppedFrames : 0}</Text>
      <ScrollView style={styles.preview} contentContainerStyle={styles.previewContent}>
        <Text style={styles.json}>{exportedJson || 'Exported JSON will appear here.'}</Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2f343a',
    backgroundColor: '#12161b',
    padding: 12,
    gap: 4,
    maxHeight: 230,
  },
  title: {
    color: '#f8fafc',
    fontWeight: '800',
    fontSize: 14,
    letterSpacing: 0,
  },
  line: {
    color: '#cbd5e1',
    fontSize: 12,
    letterSpacing: 0,
  },
  preview: {
    marginTop: 8,
    borderRadius: 6,
    backgroundColor: '#0b0d10',
  },
  previewContent: {
    padding: 8,
  },
  json: {
    color: '#94a3b8',
    fontFamily: 'monospace',
    fontSize: 11,
    letterSpacing: 0,
  },
});

