import {NativeModules, Platform} from 'react-native';
import type {RecognitionSnapshot} from '../types/recognition';
import type {Rn02HandBenchmarkSession} from '../types/rn02HandBenchmark';

export interface AppHearVisionModuleContract {
  start(): Promise<void>;
  stop(): Promise<void>;
  getLatestSnapshot(): Promise<RecognitionSnapshot>;
}

export interface Rn02HandBenchmarkModuleContract {
  startHandBenchmark(): Promise<void>;
  stopHandBenchmark(): Promise<Rn02HandBenchmarkSession>;
  getLatestHandBenchmark(): Promise<Rn02HandBenchmarkSession | null>;
}

export const AppHearVisionModulePlaceholder: AppHearVisionModuleContract = {
  async start(): Promise<void> {
    throw new Error('Native vision is not part of RN01. Start RN02+ with a real native module.');
  },
  async stop(): Promise<void> {
    throw new Error('Native vision is not part of RN01. Start RN02+ with a real native module.');
  },
  async getLatestSnapshot(): Promise<RecognitionSnapshot> {
    throw new Error('Native vision is not part of RN01. Start RN02+ with a real native module.');
  },
};

export const Rn02HandBenchmarkModulePlaceholder: Rn02HandBenchmarkModuleContract = {
  async startHandBenchmark(): Promise<void> {
    throw new Error('RN02 hand benchmark requires a registered native module for this platform.');
  },
  async stopHandBenchmark(): Promise<Rn02HandBenchmarkSession> {
    throw new Error('RN02 hand benchmark requires a registered native module for this platform.');
  },
  async getLatestHandBenchmark(): Promise<Rn02HandBenchmarkSession | null> {
    throw new Error('RN02 hand benchmark requires a registered native module for this platform.');
  },
};

const nativeRn02Module = NativeModules.RN02HandBenchmarkModule as
  | Rn02HandBenchmarkModuleContract
  | undefined;

export const Rn02HandBenchmarkModule: Rn02HandBenchmarkModuleContract =
  (Platform.OS === 'ios' || Platform.OS === 'android') && nativeRn02Module != null
    ? nativeRn02Module
    : Rn02HandBenchmarkModulePlaceholder;
