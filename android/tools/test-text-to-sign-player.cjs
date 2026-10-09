'use strict';
// Exercises the real pilot player with deterministic event ordering. Not sign validation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function setup(){
 const calls=[],frames=new Map(),timers=new Map();let next=0;
 const makeViewer=()=>{const classes=new Set();return {src:'',loaded:false,loadedSource:null,availableAnimations:[],duration:2,currentTime:0,
  updateComplete:Promise.resolve(),playRequest:null,events:new Map(),classes,classList:{add(n){classes.add(n)},remove(n){classes.delete(n)}},
  addEventListener(n,f){if(!this.events.has(n))this.events.set(n,new Set());this.events.get(n).add(f)},
  removeEventListener(n,f){this.events.get(n)?.delete(f)},emit(n){for(const f of [...(this.events.get(n)||[])])f()},
  plays:0,pause(){this.paused=true},play(opts){this.plays++;this.paused=false;this.options=opts},
  removeAttribute(n){if(n==='src')this.src=''},
  load(names=['hello']){this.loaded=true;this.availableAnimations=names;this.emit('load')}
 }};
 const viewers=[makeViewer(),makeViewer()];
 const Android=new Proxy({}, {get:(target,n)=>target[n] || ((...args)=>calls.push([n,...args]))});const window={Android};
 const context={window,Android,document:{getElementById:id=>viewers[id==='viewerA'?0:1]},console,
  customElements:{whenDefined:()=>Promise.resolve(),get:()=>({})},
  setTimeout:(f,ms)=>{const id=++next;timers.set(id,{f,ms});return id},clearTimeout:id=>timers.delete(id),
  requestAnimationFrame:f=>{const id=++next;frames.set(id,f);return id},cancelAnimationFrame:id=>frames.delete(id)};
 vm.runInNewContext(fs.readFileSync(process.argv[2] || 'app/src/aslPilot/assets/pilot_player.js','utf8'),context);
 return {window,viewers,calls,frames,timers};
}
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve()};
async function start(s,url,token,name='hello'){
 const p=s.window.playSign(url,{requestId:token,animationName:name,loop:false});await flush();
 const v=s.viewers.find(x=>x.src===url);v.load(['hello']);await p;return v;
}
(async()=>{
 let s=setup();await flush();let v=await start(s,'hello.glb',1);
 assert.equal(v.options.repetitions,1);
 v.emit('finished');assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,0,'early event must not finish');
 v.currentTime=2;v.emit('finished');v.emit('finished');assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,1,'no duplicate finish');
 s=setup();await flush();v=await start(s,'first.glb',2);s.window.pausePlayback();v.currentTime=2;v.emit('finished');
 assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,0,'canceled clip cannot finish');
 s=setup();await flush();v=await start(s,'named.glb',3,'missing');
 assert.equal(s.calls.filter(c=>c[0]==='onModelFailed').length,1,'wrong named clip fails');
 s=setup();await flush();const p=s.window.playSign('ambiguous.glb',{requestId:4,loop:false});await flush();
 s.viewers.find(x=>x.src==='ambiguous.glb').load(['hello','other']);await p;
 assert.equal(s.calls.filter(c=>c[0]==='onModelFailed').length,1,'ambiguous unnamed animation fails');
 s=setup();await flush();v=await start(s,'timeline.glb',5);v.currentTime=2;
 for(const [id,f] of [...s.frames]){s.frames.delete(id);f()}
 assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,1,'timeline ends without mixer event');
 s=setup();await flush();let step=0,second;
 s.window.Android.onPilotFinished=(src,token)=>{
  s.calls.push(['onPilotFinished',src,token]);
  if(step++===0) second=s.window.playSign('human.glb',{requestId:42,animationName:'beautiful',loop:false});
 };
 const first=s.window.playSign('human.glb',{requestId:41,animationName:'hello',loop:false});await flush();
 v=s.viewers.find(x=>x.src==='human.glb');v.load(['hello','beautiful']);await first;
 v.currentTime=1;v.emit('finished');assert.equal(v.animationName,'hello');assert.equal(step,0);
 v.currentTime=2;v.emit('finished');await flush();await second;
 assert.equal(v.animationName,'beautiful');assert.equal(v.currentTime,0);assert.equal(v.plays,2);
 assert.equal(s.viewers.filter(x=>!x.paused).length,1,'only one active animation');
 v.emit('finished');assert.equal(step,1,'early event cannot finish second clip');
 v.currentTime=2;v.emit('finished');assert.equal(step,2);
 const oldPlays=v.plays;
 await s.window.playSign('human.glb',{requestId:43,animationName:'hello',neutralFrame:0,pinSource:true});
 assert.equal(v.plays,oldPlays,'neutral must not play HELLO');assert.equal(v.paused,true);assert.equal(v.currentTime,0);
 const oldSrc=v.src;s.window.pausePlayback();assert.equal(v.src,oldSrc,'pause retains character');
 const bad=s.window.playSign('missing.glb',{requestId:44,animationName:'hello'});await flush();
 const other=s.viewers.find(x=>x.src==='missing.glb');other.emit('error');await bad;
 assert.equal(v.classes.has('active'),true);assert.equal(other.classes.has('active'),false);
 assert.equal(s.calls.filter(c=>c[0]==='onModelFailed').length,1);
 s=setup();await flush();const canceled=s.window.playSign('old.glb',{requestId:50,animationName:'hello'});await flush();
 const latest=s.window.playSign('new.glb',{requestId:51,animationName:'hello'});await flush();
 s.viewers.find(x=>x.src==='new.glb').load(['hello']);await Promise.all([canceled,latest]);
 assert.deepEqual(s.calls.filter(c=>c[0]==='onPlaybackStarted').map(c=>c[2]),[51]);
 assert.equal(s.calls.filter(c=>c[0]==='onModelFailed').length,0);
 console.log('PASS: completion-driven sequence, neutral sampling, retained avatar, load failure, rapid cancellation, clip identity and timeline completion.');
})().catch(e=>{console.error(e);process.exitCode=1});
