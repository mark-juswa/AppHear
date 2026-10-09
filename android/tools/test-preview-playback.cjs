'use strict';
// Executes the actual bundled page script against a deterministic viewer double.
// These are control-flow regression tests, not WebGL or linguistic validation.
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('app/src/main/assets/model_viewer.html', 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
function setup() {
  const events = new Map(), callbacks = [], timers = new Map();
  let timerId = 0;
  const viewer = {
    _src: '', loaded: false, availableAnimations: [], duration: 2, currentTime: 0,
    updateComplete: Promise.resolve(), calls: [], paused: true,
    get src() { return this._src; },
    set src(value) { this._src = value; this.loaded = false; },
    addEventListener(name, fn) { if (!events.has(name)) events.set(name, new Set()); events.get(name).add(fn); },
    removeEventListener(name, fn) { events.get(name)?.delete(fn); },
    pause() { this.paused = true; },
    play(options) { this.calls.push(options); this.paused = false; },
    emit(name) { for (const fn of [...(events.get(name) || [])]) fn(); },
    load(name = 'hello') { this.loaded = true; this.availableAnimations = [name]; this.emit('load'); }
  };
  const status = {};
  const window = { Android: new Proxy({}, { get: (_, method) => (...args) => callbacks.push([method, ...args]) }) };
  const context = {
    window, document: {getElementById: id => id === 'viewer' ? viewer : status, createElement: () => ({getContext: () => ({})})},
    customElements: {whenDefined: () => Promise.resolve()},
    setTimeout: (fn, ms) => { const id = ++timerId; timers.set(id, {fn, ms}); return id; },
    clearTimeout: id => timers.delete(id), console
  };
  vm.runInNewContext(source, context);
  return {viewer, window, callbacks, timers, events, status};
}
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
(async () => {
  let s = setup(); await flush();
  let p = s.window.playSign('hello.glb', 1, 'hello', false); await flush(); s.viewer.load(); await p;
  assert.equal(s.viewer.calls.at(-1).repetitions, 1, 'sign must play once');
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackStarted').length, 1);
  s.window.pauseSign(true); assert.equal(s.viewer.paused, true); assert.equal(s.timers.size, 0);
  s.window.setSignSpeed(0.5); assert.equal(s.viewer.timeScale, 0.5);
  s.window.pauseSign(false); assert.equal(s.viewer.calls.at(-1).repetitions, 1);
  assert.equal(s.timers.size, 2);
  s.viewer.currentTime = s.viewer.duration; s.viewer.emit('finished'); s.viewer.emit('finished');
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackFinished').length, 1, 'advance only once');
  assert.equal(s.timers.size, 0);

  s = setup(); await flush();
  p = s.window.playSign('no-event.glb', 9, 'hello', false); await flush(); s.viewer.load(); await p;
  s.viewer.currentTime = 1;
  let poll = [...s.timers.entries()].find(([, t]) => t.ms === 100);
  s.timers.delete(poll[0]); poll[1].fn();
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackFinished').length, 0);
  s.viewer.currentTime = s.viewer.duration;
  poll = [...s.timers.entries()].find(([, t]) => t.ms === 100);
  s.timers.delete(poll[0]); poll[1].fn();
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackFinished').length, 1, 'timeline completion without renderer event');
  assert.equal(s.timers.size, 0);

  s = setup(); await flush();
  s.window.playSign('old.glb', 1, 'old', false); await flush();
  p = s.window.playSign('new.glb', 2, 'new', false); await flush(); s.viewer.load('new'); await p;
  assert.deepEqual(s.callbacks.filter(c => c[0] === 'onPlaybackStarted').map(c => c[1]), [2]);
  s.window.stopSign(3); s.viewer.currentTime = 2; s.viewer.emit('finished');
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackFinished').length, 0);
  assert.equal(s.viewer.paused, true); assert.equal(s.timers.size, 0);

  s = setup(); await flush();
  p = s.window.playSign('missing.glb', 5, 'requested', false); await flush(); s.viewer.load('different'); await p;
  assert.equal(s.callbacks.at(-1)[0], 'onPlaybackError');
  assert.equal(s.viewer.calls.length, 0, 'wrong animation must not play');

  s = setup(); await flush();
  p = s.window.playSign('broken.glb', 6, 'hello', false); await flush(); s.viewer.emit('error'); await p;
  assert.equal(s.callbacks.at(-1)[0], 'onPlaybackError');
  assert.equal(s.timers.size, 0, 'failed load cleans up timers');
  assert.equal(s.events.get('load').size, 0, 'failed load removes listeners');

  s = setup(); await flush();
  p = s.window.playSign('idle.glb', 7, 'idle', true); await flush(); s.viewer.load('idle'); await p;
  assert.equal(s.viewer.calls.at(-1).repetitions, Infinity);
  s.viewer.currentTime = 2; s.viewer.emit('finished');
  assert.equal(s.callbacks.filter(c => c[0] === 'onPlaybackFinished').length, 0);
  s.window.stopSign(8); assert.equal(s.timers.size, 0);
  console.log('PASS: once-only playback, pause/speed/resume, cancellation, duplicate completion, animation identity, load failure and idle behavior.');
})().catch(error => { console.error(error); process.exitCode = 1; });

