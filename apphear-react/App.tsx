import React, {useState} from 'react';
import {SafeAreaView, StatusBar, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import {Rn01CameraSmokeScreen} from './src/screens/Rn01CameraSmokeScreen';
import {Rn02HandSmokeScreen} from './src/screens/Rn02HandSmokeScreen';

type PrototypeScreen = 'rn01' | 'rn02';

export default function App(): React.JSX.Element {
  const [screen, setScreen] = useState<PrototypeScreen>('rn01');

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" />
      <View style={styles.switcher}>
        <TouchableOpacity
          style={[styles.switchButton, screen === 'rn01' && styles.switchButtonActive]}
          onPress={() => setScreen('rn01')}
        >
          <Text style={[styles.switchText, screen === 'rn01' && styles.switchTextActive]}>RN01</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.switchButton, screen === 'rn02' && styles.switchButtonActive]}
          onPress={() => setScreen('rn02')}
        >
          <Text style={[styles.switchText, screen === 'rn02' && styles.switchTextActive]}>RN02</Text>
        </TouchableOpacity>
      </View>
      {screen === 'rn01' ? <Rn01CameraSmokeScreen /> : <Rn02HandSmokeScreen />}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#101214',
  },
  switcher: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: '#101214',
  },
  switchButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2f343a',
    minHeight: 38,
  },
  switchButtonActive: {
    borderColor: '#38bdf8',
    backgroundColor: '#123142',
  },
  switchText: {
    color: '#94a3b8',
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0,
  },
  switchTextActive: {
    color: '#e0f2fe',
  },
});
