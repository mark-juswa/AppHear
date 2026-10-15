'use strict';
// Exercises the real pilot player with deterministic event ordering. Not sign validation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function setup(){
 const calls=[],frames=new Map(),timers=new Map();let next=0;
 const makeViewer=()=>({src:'',loaded:false,loadedSource:null,availableAnimations:[],duration:2,_time:0,operations:[],
  get currentTime(){return this._time},set currentTime(time){this._time=time;this.operations.push(['seek',time])},
  updateComplete:Promise.resolve(),playRequest:null,events:new Map(),classList:{add(){},remove(){}},
  addEventListener(n,f){if(!this.events.has(n))this.events.set(n,new Set());this.events.get(n).add(f)},
  removeEventListener(n,f){this.events.get(n)?.delete(f)},emit(n){for(const f of [...(this.events.get(n)||[])])f()},
  pause(){this.paused=true},play(opts){this.paused=false;this.options=opts},
  appendAnimation(name,options){this.operations.push(['append',name,options]);this.appended={name,options}},
  detachAnimation(name,options){this.operations.push(['detach',name,options]);this.detached={name,options}},
  removeAttribute(n){if(n==='src')this.src=''},
  load(names=['hello']){this.loaded=true;this.availableAnimations=names;this.emit('load')}
 });
 const viewers=[makeViewer(),makeViewer()];
 const Android=new Proxy({}, {get:(_,n)=>(...args)=>calls.push([n,...args])});const window={Android};
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
 s=setup();await flush();
 const bundle=fs.readFileSync('app/src/aslOriginalWords/assets/asl_animations/original_words_v1/fingerspelling-avatar.glb');
 const gltf=JSON.parse(bundle.subarray(20,20+bundle.readUInt32LE(12)).toString());
 const names=gltf.animations.map(a=>a.name);assert.equal(names.length,248);
 for(const name of ['SIGN_CALL__TO_CALL_SOMEONE_S_NAME','SIGN_YOU_HUMAN_RETARGETED_PREVIEW','SIGN_YOU_ALL_HUMAN_RETARGETED_PREVIEW']) assert.ok(names.includes(name));
 const first=s.window.playSign('resident.glb',{requestId:10,animationName:'SIGN_HELLO',neutralFrame:0,pinSource:true});await flush();
 v=s.viewers.find(x=>x.src==='resident.glb');let loads=0;const originalLoad=v.load;
 v.load=function(n){loads++;originalLoad.call(this,n)};v.load(names);await first;
 const resident=v;
 const letters=text=>[...text].map(c=>'SIGN_LETTER_'+c+'_WOLF3D_PREVIEW');
 // Exercise every actual action plus the reported regression sequences. The
 // planner has separate Kotlin tests; this verifies named controller playback.
 const sequence=[...names.filter(n=>n!=='SIGN_RELAXED_NEUTRAL'),
   ...letters('NICOLENAMEANNAJAZZACTION'),
   'SIGN_HELLO','SIGN_LOVE','SIGN_MY','SIGN_CALL__TO_CALL_SOMEONE_S_NAME',
   'SIGN_YOUR','SIGN_CALL__TO_CALL_SOMEONE_S_NAME','SIGN_HELLO',...letters('NICOLE'),
   'SIGN_I','SIGN_LOVE','SIGN_YOU_HUMAN_RETARGETED_PREVIEW','SIGN_HELP',...letters('NICOLE')];
 for(const [index,name] of sequence.entries()){
   const fingerspelling=name.startsWith('SIGN_LETTER_');
   const previous=resident.animationName;resident.operations=[];
   await s.window.playSign('resident.glb',{requestId:11+index,animationName:name,loop:false,fingerspelling});
   assert.equal(s.viewers.filter(x=>x.src==='resident.glb').length,1);
   assert.equal(resident.animationName,name);assert.equal(loads,1,'resident model must not load again');
   assert.equal(resident.animationCrossfadeDuration,0,'never schedule a built-in fade before a mixer seek');
   if(fingerspelling&&previous!==name){
     const seek=resident.operations.findIndex(o=>o[0]==='seek');
     const append=resident.operations.findIndex(o=>o[0]==='append');
     assert.ok(seek>=0&&append>seek,'seek must happen before scheduling outgoing pose fade');
     assert.equal(resident.detached.options.fade,.12);
     assert.equal(resident.appended.options.timeScale,1,'cached letters must not be frozen');
   }else assert.equal(resident.operations.filter(o=>o[0]==='append').length,0,'lexical/same-letter actions cannot inherit a pose overlay');
   resident.currentTime=2;resident.emit('finished');
 }
 assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,sequence.length);
 await s.window.playSign('resident.glb',{requestId:1000,animationName:'SIGN_HELLO',neutralFrame:0,pinSource:true});
 assert.equal(resident.animationName,'SIGN_RELAXED_NEUTRAL');
 assert.equal(resident.animationCrossfadeDuration,0);
 assert.equal(resident.detached.options.fade,.22);
 assert.equal(resident.options.repetitions,Infinity);
 assert.equal(resident.playRequest,null,'idle must not advance the queue');
 assert.equal(loads,1);
 assert.equal(s.calls.filter(c=>c[0]==='onPilotFinished').length,sequence.length);
 console.log('PASS: one resident viewer, one model load, '+sequence.length+' word/letter clips and completion callbacks; every actual action covered.');
 console.log('PASS: early/duplicate/stale completion, named clip identity, ambiguous clip rejection and timeline completion.');
})().catch(e=>{console.error(e);process.exitCode=1});
