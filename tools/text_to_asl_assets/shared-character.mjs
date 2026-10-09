// Lossless seven-clip bundle. Sources and the phone-tested separate pilot stay read-only.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {parseGLB, serializeGLB} from './verification.mjs';

const repo = path.resolve(import.meta.dirname, '../..');
const source = path.join(repo, 'android/app/src/aslPilot/assets');
const output = path.resolve(process.argv[2] || path.join(repo, 'android/app/src/aslShared/assets'));
assert.notEqual(output, source);
const runtime = path.join(repo, 'artifacts/text_to_asl_asset_optimization_20260928/tools');
const require = createRequire(path.join(runtime, 'package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const [{NodeIO}, {ALL_EXTENSIONS}, {MeshoptDecoder}, validatorModule] = await Promise.all([
  load('@gltf-transform/core'), load('@gltf-transform/extensions'), load('meshoptimizer'), load('gltf-validator')]);
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder':MeshoptDecoder});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const clone = value => structuredClone(value);
const hashAccessor = a => ({type:a.getType(),component:a.getComponentType(),normalized:a.getNormalized(),
  count:a.getCount(),hash:sha(Buffer.from(a.getArray().buffer,a.getArray().byteOffset,a.getArray().byteLength))});
const manifest = JSON.parse(await fs.readFile(path.join(source, 'asl_animations/vnext/manifest.json'), 'utf8'));
assert.deepEqual(manifest.clips.map(c=>c.id), ['a','b','all','brother','child','city','family']);
const inputs = [];
for (const clip of manifest.clips) {
  const bytes = await fs.readFile(path.join(source, clip.asset));
  assert.equal(sha(bytes), clip.sha256, `Source checksum changed: ${clip.id}`);
  const model = parseGLB(bytes), decoded = await io.readBinary(bytes);
  assert.equal(model.doc.animations.length, 1);
  assert.equal(model.doc.animations[0].name, clip.animationName);
  inputs.push({clip,bytes,model,decoded});
}
const first = inputs[0], base = clone(first.model.doc), chunks = [first.model.bin];
let actualLength = first.model.bin.length;
const HAIR_NODE = 1230;
assert.equal(base.nodes[HAIR_NODE].name, 'Hair_M_BobCurly_Helmet_LOD7');

function renderingSignature(document) {
  const r=document.getRoot(),nodes=r.listNodes();
  return {
    geometry:r.listMeshes().map(m=>m.listPrimitives().map(p=>({mode:p.getMode(),indices:p.getIndices()?hashAccessor(p.getIndices()):null,
      attributes:p.listSemantics().map(s=>[s,hashAccessor(p.getAttribute(s))]),
      morph:p.listTargets().map(t=>t.listSemantics().map(s=>[s,hashAccessor(t.getAttribute(s))]))}))),
    skins:r.listSkins().map(s=>({joints:s.listJoints().map(n=>nodes.indexOf(n)),skeleton:nodes.indexOf(s.getSkeleton()),ibm:hashAccessor(s.getInverseBindMatrices())})),
    textures:r.listTextures().map(t=>sha(t.getImage())),
  };
}
const renderBase=renderingSignature(first.decoded);
for (const input of inputs) {
  assert.deepEqual(renderingSignature(input.decoded),renderBase, `Rendering data differs: ${input.clip.id}`);
  const current=clone(input.model.doc),reference=clone(first.model.doc);
  // Material display names do not participate in rendering; all other parameters must match.
  for(const d of [current,reference]) for(const m of d.materials) delete m.name;
  assert.deepEqual(current.materials,reference.materials);
  for(const key of ['scenes','skins','meshes','textures','samplers']) assert.deepEqual(current[key],reference[key],key);
  assert.equal(current.nodes.length,reference.nodes.length);
  for(let i=0;i<current.nodes.length;i++) {
    if(i===HAIR_NODE) {
      for(const key of ['translation','rotation','scale']) {
        const a=current.nodes[i][key],b=reference.nodes[i][key];
        assert.ok(a.every((v,j)=>Math.abs(v-b[j])<=1.1920928955078125e-7),'Unexpected hair transform drift');
        delete current.nodes[i][key];delete reference.nodes[i][key];
      }
    }
    assert.deepEqual(current.nodes[i],reference.nodes[i],`Hierarchy/rest transform differs at ${i}`);
  }
  assert.ok(!input.model.doc.animations[0].channels.some(c=>c.target.node===HAIR_NODE),'Hair now animated; re-audit required');
}

function appendBytes(bytes) {
  const padding=(4-actualLength%4)%4;
  if(padding){chunks.push(Buffer.alloc(padding));actualLength+=padding;}
  const offset=actualLength;chunks.push(Buffer.from(bytes));actualLength+=bytes.length;return offset;
}
function copyAnimation(input) {
  if(input===first) return clone(input.model.doc.animations[0]);
  const accessors=new Map(),views=new Map();
  const copyAccessor=index=>{
    if(accessors.has(index))return accessors.get(index);
    const a=clone(input.model.doc.accessors[index]);assert.ok(!a.sparse);
    if(!views.has(a.bufferView)) {
      const v=clone(input.model.doc.bufferViews[a.bufferView]);
      const ext=v.extensions?.EXT_meshopt_compression;
      assert.ok(ext&&ext.buffer===0&&v.buffer===1,'Unexpected animation buffer format');
      const start=ext.byteOffset||0;
      assert.ok(start+ext.byteLength<=input.model.bin.length);
      ext.byteOffset=appendBytes(input.model.bin.subarray(start,start+ext.byteLength));
      v.byteOffset=base.buffers[1].byteLength;
      base.buffers[1].byteLength+=v.byteLength;
      views.set(a.bufferView,base.bufferViews.length);base.bufferViews.push(v);
    }
    a.bufferView=views.get(a.bufferView);
    accessors.set(index,base.accessors.length);base.accessors.push(a);return accessors.get(index);
  };
  const animation=clone(input.model.doc.animations[0]);
  for(const s of animation.samplers){s.input=copyAccessor(s.input);s.output=copyAccessor(s.output);}
  return animation;
}
function constantAccessor(values,type,count,min,max) {
  const array=new Float32Array(values),bytes=Buffer.from(array.buffer);
  const view=base.bufferViews.length;
  base.bufferViews.push({buffer:0,byteOffset:appendBytes(bytes),byteLength:bytes.length});
  const accessor=base.accessors.length;
  base.accessors.push({bufferView:view,componentType:5126,count,type,...(min?{min,max}:{})});
  return accessor;
}
base.animations=[];
for(const input of inputs) {
  const animation=copyAnimation(input);
  const root=input.decoded.getRoot(),a=root.listAnimations()[0];
  const end=Math.max(...a.listSamplers().map(s=>s.getInput().getArray().at(-1)));
  const time=constantAccessor([0,end],'SCALAR',2,[0],[end]);
  // Each clip also resets the sole nonanimated source-specific hair transform.
  for(const [key,type] of [['translation','VEC3'],['rotation','VEC4'],['scale','VEC3']]) {
    const values=input.model.doc.nodes[HAIR_NODE][key];
    const value=constantAccessor([...values,...values],type,2);
    const sampler=animation.samplers.length;
    animation.samplers.push({input:time,output:value,interpolation:'STEP'});
    animation.channels.push({sampler,target:{node:HAIR_NODE,path:key}});
  }
  base.animations.push(animation);
}
base.buffers[0].byteLength=actualLength;
const bytes=serializeGLB(base,Buffer.concat(chunks));
const decoded=await io.readBinary(bytes);
assert.deepEqual(renderingSignature(decoded),renderBase,'Bundle changes rendering resources');
function channelSignature(document,channel) {
  const r=document.getRoot(),s=channel.getSampler();
  return {node:r.listNodes().indexOf(channel.getTargetNode()),path:channel.getTargetPath(),
    interpolation:s.getInterpolation(),input:hashAccessor(s.getInput()),output:hashAccessor(s.getOutput())};
}
const checks=[];
for(let i=0;i<inputs.length;i++) {
  const original=inputs[i].decoded.getRoot().listAnimations()[0],result=decoded.getRoot().listAnimations()[i];
  assert.equal(result.getName(),original.getName());
  assert.equal(result.listChannels().length,original.listChannels().length+3);
  for(let c=0;c<original.listChannels().length;c++) assert.deepEqual(
    channelSignature(decoded,result.listChannels()[c]),channelSignature(inputs[i].decoded,original.listChannels()[c]),
    `${inputs[i].clip.id} channel ${c} differs`);
  for(const channel of result.listChannels().slice(-3)) {
    assert.equal(decoded.getRoot().listNodes().indexOf(channel.getTargetNode()),HAIR_NODE);
    const key=channel.getTargetPath(),expected=inputs[i].model.doc.nodes[HAIR_NODE][key];
    assert.deepEqual(Array.from(channel.getSampler().getOutput().getArray()),[...expected,...expected]);
  }
  checks.push({id:inputs[i].clip.id,originalChannelsExact:original.listChannels().length,constantHairTracksExact:3});
}
const validator=validatorModule.default||validatorModule;
const validation=await validator.validateBytes(new Uint8Array(bytes),{uri:'shared-character.glb',maxIssues:100});
assert.equal(validation.issues.numErrors,0,JSON.stringify(validation.issues));
const asset='asl_animations/vnext/shared-character.glb';
const result={schemaVersion:1,clips:manifest.clips.map(c=>({...c,asset,sha256:sha(bytes),profile:'balanced-ktx2mixed-meshopt-shared-v1'}))};
const report={schema:'apphear.text_to_asl.shared_character.v1',sources:inputs.map(i=>({id:i.clip.id,sha256:sha(i.bytes)})),
  sourceMiB:inputs.reduce((n,i)=>n+i.bytes.length,0)/1048576,bundleMiB:bytes.length/1048576,sha256:sha(bytes),
  geometryTexturesSkinsExact:true,animationChecks:checks,validationErrors:validation.issues.numErrors,
  validationWarnings:validation.issues.numWarnings,deviceGate:'PENDING'};
await fs.mkdir(path.join(output,'asl_animations/vnext'),{recursive:true});
const target=path.join(output,asset);
try {assert.deepEqual(await fs.readFile(target),bytes,'Refusing to replace a different bundle');}
catch(error){if(error.code!=='ENOENT')throw error;await fs.writeFile(target,bytes);}
await fs.writeFile(path.join(output,'asl_animations/vnext/manifest.json'),JSON.stringify(result,null,2));
const reports=path.join(repo,'artifacts/text_to_asl_shared_character_20260928');await fs.mkdir(reports,{recursive:true});
await fs.writeFile(path.join(reports,'bundle-verification.json'),JSON.stringify(report,null,2));
await fs.writeFile(path.join(reports,'gltf-validation.json'),JSON.stringify(validation,null,2));
console.log(JSON.stringify(report,null,2));
