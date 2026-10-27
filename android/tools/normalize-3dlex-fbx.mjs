// Development-only FBX normalization using Three.js 0.180.0 (MIT). No Android dependency.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
if(!process.argv[2])throw Error('Usage: node normalize-3dlex-fbx.mjs STAGING_DIRECTORY');
const root=pathToFileURL(path.resolve(process.argv[2])+path.sep);if(JSON.parse(fs.readFileSync(new URL('./node_modules/three/package.json',root),'utf8')).version!=='0.180.0')throw Error('Requires pinned Three.js 0.180.0');const loader=new URL('./node_modules/three/examples/jsm/loaders/FBXLoader.js',root);let text=fs.readFileSync(loader,'utf8');const needle='return time / 46186158000;';if(text.split(needle).length!==2)throw Error('Unexpected reader clock implementation');text=text.replace(needle,'return (time - globalThis.__apphearFBXOriginTicks) / 46186158000;');const patched=new URL('./node_modules/three/examples/jsm/loaders/AppHearFBXLoader.js',root);fs.writeFileSync(patched,text);
const {FBXLoader}=await import(patched.href);const {LoadingManager,Texture,AnimationMixer,LoopOnce,AnimationClip,QuaternionKeyframeTrack,VectorKeyframeTrack}=await import('./node_modules/three/build/three.module.js');const {GLTFExporter}=await import('./node_modules/three/examples/jsm/exporters/GLTFExporter.js');
globalThis.FileReader=class {readAsArrayBuffer(b){b.arrayBuffer().then(x=>{this.result=x;this.onloadend?.()})}};
const manager=new LoadingManager().addHandler(/.*/,{path:'',setPath(p){this.path=p;return this},load(){return new Texture()}});
for(const e of JSON.parse(fs.readFileSync(new URL('./probe-clocks.json',root),'utf8'))){
 globalThis.__apphearFBXOriginTicks=e.originTicks;const b=fs.readFileSync(e.path),s=new FBXLoader(manager).parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'');if(s.animations.length!==1)throw Error('Need exactly one source clip');
 const meshes=[];s.traverse(n=>{if(n.isMesh)meshes.push(n)});for(const n of meshes)n.removeFromParent();const nodes=[];s.traverse(n=>nodes.push(n));const rest=nodes.map(n=>({p:n.position.clone(),q:n.quaternion.clone(),s:n.scale.clone()}));const clip=s.animations[0];if(Math.abs(clip.duration-e.duration)>1e-5)throw Error('Clock mismatch');
 const mixer=new AnimationMixer(s);const action=mixer.clipAction(clip);action.setLoop(LoopOnce,1);action.clampWhenFinished=true;action.play();const times=e.sampleTimesSeconds;if(!times?.length||Math.abs(times.at(-1)-clip.duration)>1e-5)throw Error('Missing source skeletal timeline');const values=nodes.map(()=>({p:[],q:[],s:[]}));
 for(const t of times){mixer.setTime(t);nodes.forEach((n,i)=>{values[i].p.push(...n.position.toArray());values[i].q.push(...n.quaternion.toArray());values[i].s.push(...n.scale.toArray())})}
 mixer.stopAllAction();nodes.forEach((n,i)=>{n.position.copy(rest[i].p);n.quaternion.copy(rest[i].q);n.scale.copy(rest[i].s)});const tracks=[];
 nodes.forEach((n,i)=>{tracks.push(new VectorKeyframeTrack(n.name+'.position',times,values[i].p),new QuaternionKeyframeTrack(n.name+'.quaternion',times,values[i].q));if(n.name==='Hips')tracks.push(new VectorKeyframeTrack(n.name+'.scale',times,values[i].s));else if(values[i].s.some((x,k)=>Math.abs(x-rest[i].s.toArray()[k%3])>1e-5))throw Error('Unexpected scale '+n.name)});
 const data=await new GLTFExporter().parseAsync(s,{binary:true,animations:[new AnimationClip('ASL_'+e.word,clip.duration,tracks)],onlyVisible:false});fs.mkdirSync(new URL('./fbx-glb-normalized/',root),{recursive:true});fs.writeFileSync(new URL('./fbx-glb-normalized/'+e.word+'.glb',root),Buffer.from(data));console.log(e.word,'normalized',clip.duration,'seconds',nodes.length,'nodes',times.length,'frames',data.byteLength,'bytes');
}

