// Development-only CDP inspection of the existing Android WebView. Never bundled.
// Requires an authorized debug phone, adb forward, and Text-to-Sign already open.
const fs=require('node:fs'),path=require('node:path');
async function main(){
 const out=process.argv[2],serial=process.argv[3],port=process.argv[4]||'9227',letters=process.argv[5]||'NICOLEABCDEFGHIJKLMNOPQRSTUVWXYZ'; if(!out||!serial)throw Error('Usage: node tools/inspect-text-to-sign-phone.cjs OUTPUT SERIAL [PORT] [LETTERS]');fs.mkdirSync(out,{recursive:true});
 const targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();const target=targets.find(t=>t.url==='https://appassets.androidplatform.net/assets/model_viewer_pilot.html');if(!target)throw Error('AppHear Text-to-Sign not open');
 const ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.j(m.error):p.r(m.result)}};
 const call=(method,params={})=>new Promise((r,j)=>{const k=++id;pending.set(k,{r,j});ws.send(JSON.stringify({id:k,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 const camera=await evaluate(`(()=>{const v=viewers[activeIndex];return {target:v.cameraTarget,orbit:v.cameraOrbit,fov:v.fieldOfView,min:v.minCameraOrbit,max:v.maxCameraOrbit}})()`);
 const report={mode:'installed-player',renderer:'Actual Android WebView on connected phone',samples:[]};
 let token=1000000;
 async function letter(c,label){
   await evaluate(`playSign(viewers[activeIndex].src,{requestId:${++token},animationName:'SIGN_LETTER_${c}_WOLF3D_PREVIEW',fingerspelling:true})`);
   const snap=await evaluate(`new Promise((resolve,reject)=>{const start=performance.now();const check=()=>{const v=viewers[activeIndex];if(v.currentTime>=v.duration*.65){v.pause();const s=v[Object.getOwnPropertySymbols(v).find(k=>k.description==='scene')],bones=[];let hand;s.traverse(o=>{if(o.name.startsWith('RightHand'))bones.push({name:o.name,q:o.quaternion.toArray()});if(o.name==='RightHandMiddle2')hand=o;});const p=hand.position.clone();hand.getWorldPosition(p);s.target.worldToLocal(p);v.cameraTarget=p.x+'m '+p.y+'m '+p.z+'m';v.minCameraOrbit='auto auto 0.1m';v.cameraOrbit='0deg 85deg 0.7m';v.fieldOfView='40deg';v.jumpCameraToGoal?.();resolve({name:v.animationName,time:v.currentTime,duration:v.duration,bones,actions:s.mixers.flatMap(m=>m._actions.filter(a=>a.isScheduled()).map(a=>({name:a._clip.name,enabled:a.enabled,weight:a.getEffectiveWeight(),timeScale:a.timeScale,time:a.time})))})}else if(performance.now()-start>20000)reject('Letter did not advance');else requestAnimationFrame(check)};check()})`);
   await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
   const image=require('node:child_process').execFileSync(process.env.APPHEAR_ADB || 'adb',['-s',serial,'exec-out','screencap','-p'],{maxBuffer:10000000});fs.writeFileSync(path.join(out,label+'.png'),image);
   report.samples.push({...snap,label});
   await evaluate('viewers[activeIndex].play({repetitions:1})');
   await evaluate(`new Promise((resolve,reject)=>{const start=performance.now();const check=()=>{if(viewers[activeIndex].playRequest==null)resolve(true);else if(performance.now()-start>20000)reject('No completion callback');else requestAnimationFrame(check)};check()})`);
 }
 try{
   for(const [n,c] of [...letters].entries()) { if(!/^[A-Z]$/.test(c))throw Error('Only A-Z supported by this diagnostic');await letter(c,'letter-'+n+'-'+c); }
 }finally{
   fs.writeFileSync(path.join(out,'runtime-poses.json'),JSON.stringify(report,null,2));
   await evaluate(`(()=>{const v=viewers[activeIndex],c=${JSON.stringify(camera)};v.cameraTarget=c.target;v.cameraOrbit=c.orbit;v.fieldOfView=c.fov;v.minCameraOrbit=c.min;v.maxCameraOrbit=c.max;v.jumpCameraToGoal?.();})()`);
   await evaluate('playSign(viewers[activeIndex].src,{requestId:lastRequest+1,neutralFrame:0,animationName:"SIGN_RELAXED_NEUTRAL"})');ws.close();
 }
 console.log(JSON.stringify({mode:'installed-player',samples:report.samples.length,zeroWeight:report.samples.filter(s=>!s.actions.some(a=>a.name===s.name&&a.weight>.99)).length,out}));
}
main().catch(e=>{console.error(e);process.exitCode=1});
