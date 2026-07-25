import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

interface MetricTileProps {
  label: string;
  value: string;
  tone?: 'normal' | 'good' | 'warn';
}

export function MetricTile({label, value, tone = 'normal'}: MetricTileProps): React.JSX.Element {
  return (
    <View style={[styles.tile, styles[tone]]}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value} numberOfLines={1} adjustsFontSizeToFit>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tile: {
    minWidth: '30%',
    flex: 1,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2f343a',
    backgroundColor: '#171a1f',
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  normal: {
    borderColor: '#2f343a',
  },
  good: {
    borderColor: '#327a56',
  },
  warn: {
    borderColor: '#9a6a2e',
  },
  label: {
    color: '#aab1ba',
    fontSize: 11,
    letterSpacing: 0,
  },
  value: {
    color: '#f1f5f9',
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: 0,
    marginTop: 2,
  },
});
