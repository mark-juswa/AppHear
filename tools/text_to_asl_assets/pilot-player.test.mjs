import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const script = await fs.readFile(new URL('../../android/app/src/aslPilot/assets/pilot_player.js',import.meta.url),'utf8');
function harness() {
  const timers=new Map(),frames=new Map(),calls=[];let counter=0;
  class Viewer {
    src='';loaded=false;duration=2;currentTime=0;availableAnimations=['SIGN'];listeners=new Map();plays=[];
    classList={add:()=>{},remove:()=>{}};
    set animationName(value){this.name=value;this.updateComplete=Promise.resolve().then(()=>{this.effectiveRepetitions=Infinity;});}
    addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn);}
    removeEventListener(name,fn){this.listeners.get(name)?.delete(fn);}
    emit(name){for(const fn of [...(this.listeners.get(name)||[])])fn();}
    pause(){this.paused=true;}
    play(options){this.paused=false;this.plays.push(options);this.effectiveRepetitions=options.repetitions;}
    removeAttribute(name){if(name==='src'){this.src='';this.loaded=false;}}
    load(url){this.src=url;this.loaded=true;this.emit('load');}
  }
  const views=[new Viewer(),new Viewer()];
  const bridge=new Proxy({}, {get:(_,name)=>(...args)=>calls.push([name,...args])});
  const window={Android:bridge};
  const context={window,Android:bridge,document:{getElementById:id=>views[id==='viewerA'?0:1]},
    customElements:{whenDefined:()=>Promise.resolve(),get:()=>Viewer},console:{warn:()=>{}},
    requestAnimationFrame:fn=>{const id=++counter;frames.set(id,fn);return id;},cancelAnimationFrame:id=>frames.delete(id),
    setTimeout:(fn,ms)=>{const id=++counter;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(script,context);
  const expire=ms=>{for(const [id,t] of [...timers])if(t.ms===ms){timers.delete(id);t.fn();}};
  const frame=()=>{const pending=[...frames];frames.clear();for(const [,fn] of pending)fn();};
  return {window,views,calls,expire,frame};
}

test('public timeline completes without renderer event, exactly once; pause cancels monitor',async()=>{
  const h=harness();const pending=h.window.playSign('family',{requestId:1});h.views[1].load('family');await pending;
  h.views[1].currentTime=1.9;h.frame();assert.equal(h.calls.some(x=>x[0]==='onPilotFinished'),false);
  h.views[1].currentTime=2;h.frame();h.frame();h.views[1].emit('finished');
  assert.equal(h.calls.filter(x=>x[0]==='onPilotFinished').length,1);
  const next=h.window.playSign('b',{requestId:2});h.views[0].load('b');await next;
  h.window.pausePlayback();h.views[0].currentTime=2;h.frame();
  assert.equal(h.calls.filter(x=>x[0]==='onPilotFinished').length,1);
});

test('shared source switches named clips without loading another character',async()=>{
  const h=harness();h.views[1].availableAnimations=['A','B'];
  const a=h.window.playSign('shared',{requestId:1,animationName:'A'});h.views[1].load('shared');await a;
  h.views[1].currentTime=2;h.frame();
  h.window.preloadSign('shared');
  await h.window.playSign('shared',{requestId:2,animationName:'B'});
  assert.equal(h.views[1].name,'B');assert.equal(h.views[1].currentTime,0);
  assert.equal(h.views[1].effectiveRepetitions,1);assert.equal(h.views[0].src,'');
  h.views[1].currentTime=2;h.frame();
  assert.deepEqual(h.calls.filter(x=>x[0]==='onPilotFinished').map(x=>x[2]),[1,2]);
});

test('shared idle loops, switches to a complete sign, then loops again without model reload',async()=>{
  const h=harness();h.views[1].availableAnimations=['IDLE','SIGN'];
  const idle=h.window.playSign('shared-idle',{requestId:1,animationName:'IDLE',loop:true});
  h.views[1].load('shared-idle');await idle;
  assert.equal(h.views[1].effectiveRepetitions,Infinity);
  h.views[1].currentTime=2;h.frame();h.views[1].emit('finished');
  assert.equal(h.calls.some(x=>x[0]==='onPilotFinished'),false);
  await h.window.playSign('shared-idle',{requestId:2,animationName:'SIGN',loop:false});
  assert.equal(h.views[1].currentTime,0);assert.equal(h.views[1].effectiveRepetitions,1);
  h.views[1].currentTime=2;h.frame();
  await h.window.playSign('shared-idle',{requestId:3,animationName:'IDLE',loop:true});
  assert.equal(h.views[1].name,'IDLE');assert.equal(h.views[1].currentTime,0);
  assert.equal(h.views[1].effectiveRepetitions,Infinity);assert.equal(h.views[0].src,'');
  assert.deepEqual(h.calls.filter(x=>x[0]==='onPilotFinished').map(x=>x[2]),[2]);
});

test('Clear-style idle replacement cancels a mid-sign completion and stale callbacks',async()=>{
  const h=harness();h.views[1].availableAnimations=['IDLE','SIGN'];
  const pending=h.window.playSign('shared-idle',{requestId:1,animationName:'SIGN'});
  h.views[1].load('shared-idle');await pending;
  h.views[1].currentTime=1;
  await h.window.playSign('shared-idle',{requestId:2,animationName:'IDLE',loop:true});
  h.views[1].currentTime=2;h.frame();h.views[1].emit('finished');
  assert.equal(h.calls.some(x=>x[0]==='onPilotFinished'),false);
  h.window.pausePlayback();assert.deepEqual(h.views.map(v=>v.src),['','']);
  h.views[0].availableAnimations=['IDLE','SIGN'];
  const reopen=h.window.playSign('shared-idle',{requestId:3,animationName:'IDLE',loop:true});
  h.views[0].load('shared-idle');await reopen;
  assert.equal(h.views[0].name,'IDLE');assert.equal(h.views[0].effectiveRepetitions,Infinity);
});

test('new shared character stays loaded through original-only signs and returns to idle',async()=>{
  const h=harness();h.views[1].availableAnimations=['IDLE','SIGN'];
  const idle=h.window.playSign('new-shared',{requestId:1,animationName:'IDLE',loop:true,pinSource:true});
  h.views[1].load('new-shared');await idle;
  const original=h.window.playSign('hello',{requestId:2});
  h.views[0].load('hello');await original;
  h.expire(280);
  assert.equal(h.views[1].src,'new-shared');
  h.window.preloadSign('another-original');
  assert.equal(h.views[1].src,'new-shared');
  const other=h.window.playSign('another-original',{requestId:3});
  assert.equal(h.views[0].src,'another-original');
  h.views[0].load('another-original');await other;
  h.expire(280);
  assert.equal(h.views[1].src,'new-shared');
  const sign=h.window.playSign('new-shared',{requestId:4,animationName:'SIGN',pinSource:true});
  await sign;
  assert.equal(h.views[1].src,'new-shared');
  assert.equal(h.views[1].name,'SIGN');
  h.views[1].currentTime=2;h.frame();
  await h.window.playSign('new-shared',{requestId:5,animationName:'IDLE',loop:true,pinSource:true});
  assert.equal(h.views[1].name,'IDLE');
  assert.equal(h.views[1].effectiveRepetitions,Infinity);
  h.expire(280);
  assert.equal(h.views[0].src,'another-original');
  assert.equal(h.views[0].loadedSource,'another-original');
  await h.window.playSign('another-original',{requestId:6});
  assert.equal(h.views[0].plays.length,3);
  assert.equal(h.views[1].src,'new-shared');
  assert.equal(h.calls.some(x=>x[0]==='onModelFailed'),false);
});

test('one-shot starts only after load, completes once, and idle loops',async()=>{
  const h=harness();const play=h.window.playSign('family',{requestId:1,animationName:'SIGN',loop:false});
  assert.equal(h.calls.some(x=>x[0]==='onPlaybackStarted'),false);
  h.views[1].load('family');await play;
  assert.equal(h.views[1].plays[0].repetitions,1);
  assert.equal(h.views[1].effectiveRepetitions,1);
  h.views[1].emit('finished');
  assert.equal(h.calls.filter(x=>x[0]==='onPilotFinished').length,1);
  const idle=h.window.playSign('idle',{requestId:2,loop:true});h.views[0].load('idle');await idle;
  assert.equal(h.views[0].plays[0].repetitions,Infinity);
});

test('repeated sign waits for current viewer load rather than historical URL',async()=>{
  const h=harness();const first=h.window.playSign('a',{requestId:1});h.views[1].load('a');await first;
  h.expire(280);
  await h.window.playSign('a',{requestId:2});
  assert.equal(h.views[1].plays.length,2);
  h.window.pausePlayback();
  const third=h.window.playSign('a',{requestId:3});
  assert.equal(h.calls.filter(x=>x[0]==='onPlaybackStarted').length,2);
  h.views[0].load('a');await third;
  assert.equal(h.calls.filter(x=>x[0]==='onPlaybackStarted').length,3);
});

test('new request cancels old wait and ignores stale completion',async()=>{
  const h=harness();const old=h.window.playSign('a',{requestId:1});
  const fresh=h.window.playSign('b',{requestId:2});h.views[1].load('b');
  await Promise.all([old,fresh]);
  assert.deepEqual(h.calls.filter(x=>x[0]==='onPlaybackStarted').map(x=>x[2]),[2]);
  h.views[0].playRequest=1;h.views[0].emit('finished');
  assert.equal(h.calls.some(x=>x[0]==='onPilotFinished'),false);
  assert.equal(h.calls.some(x=>x[0]==='onModelFailed'),false);
});

test('load error, timeout and missing named animation report matching request',async()=>{
  for(const mode of ['error','timeout','missing']) {
    const h=harness();const pending=h.window.playSign('bad',{requestId:9,animationName:'EXPECTED'});
    if(mode==='error')h.views[1].emit('error');
    if(mode==='timeout')h.expire(20_000);
    if(mode==='missing')h.views[1].load('bad');
    await pending;
    assert.deepEqual(h.calls.filter(x=>x[0]==='onModelFailed'),[['onModelFailed','bad',9]]);
  }
});

test('preload retains only latest next sign after releasing old model, pause clears both',async()=>{
  const h=harness();h.views[0].load('idle');
  const current=h.window.playSign('family',{requestId:1});
  h.window.preloadSign('a');h.window.preloadSign('b');h.views[1].load('family');await current;
  h.expire(280);assert.equal(h.views[0].src,'b');
  h.views[0].load('b');assert.equal(h.views[0].plays.length,0);
  h.window.pausePlayback();assert.deepEqual(h.views.map(x=>x.src),['','']);
  h.views[1].emit('finished');assert.equal(h.calls.some(x=>x[0]==='onPilotFinished'),false);
});

test('preload source switch cannot treat previous loaded model as new source',async()=>{
  const h=harness();h.views[0].load('idle');
  const first=h.window.playSign('a',{requestId:1});h.views[1].load('a');await first;
  h.expire(280);
  h.views[0].load('old');h.window.preloadSign('b');
  // Simulate the renderer retaining loaded=true until its asynchronous source update.
  const next=h.window.playSign('b',{requestId:2});
  assert.equal(h.calls.filter(x=>x[0]==='onPlaybackStarted').length,1);
  h.views[0].load('b');await next;
  assert.equal(h.calls.filter(x=>x[0]==='onPlaybackStarted').length,2);
});

test('empty-animation load event does not settle a cold model request',async()=>{
  const h=harness();h.views[1].availableAnimations=[];
  const pending=h.window.playSign('alphabet',{requestId:1,animationName:'LETTER_C'});
  h.views[1].load('alphabet');
  await Promise.resolve();
  assert.equal(h.calls.some(x=>x[0]==='onPlaybackStarted'||x[0]==='onModelFailed'),false);
  h.views[1].availableAnimations=['LETTER_C'];
  h.views[1].load('alphabet');await pending;
  assert.equal(h.calls.filter(x=>x[0]==='onPlaybackStarted').length,1);
  assert.equal(h.calls.some(x=>x[0]==='onModelFailed'),false);
});
