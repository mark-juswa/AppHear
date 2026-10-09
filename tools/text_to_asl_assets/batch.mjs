// Offline derivative builder. No Android catalog edits, network access, or source writes.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {parseGLB, serializeGLB, structuralSnapshot} from './verification.mjs';

const args = process.argv.slice(2);
const option = name => {const i=args.indexOf(name); return i<0?undefined:args[i+1];};
const repo = path.resolve(import.meta.dirname, '../..');
const runtime = path.resolve(option('--runtime') || path.join(repo, 'artifacts/text_to_asl_asset_optimization_20260928/tools'));
const output = path.resolve(option('--output') || 'G:/3d Characters/optimized_apphear3_batch');
const inventory = JSON.parse(await fs.readFile(path.join(repo, 'artifacts/text_to_asl_asset_assessment_20260928/inventory.json'), 'utf8'));
const templatePath = path.join(runtime, '../work/candidates/A.balanced.ktx2mixed.glb');
const sourceRoot = path.resolve('G:/3d Characters/glb');
assert.ok(output !== sourceRoot && !output.startsWith(sourceRoot + path.sep), 'Output must be outside original glb directory');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const pilotOriginal = inventory.new.find(x => path.resolve(x.path) === path.join(sourceRoot, 'A.glb'));
assert.ok(pilotOriginal, 'Assessed pilot A missing');
const signature = item => JSON.stringify(item.images.map(i=>[i.name, i.sha256]));
const wanted = option('--signs')?.split(',').map(x=>x.trim().toUpperCase());
const rejected = [], groups = new Map();
for (const item of inventory.new) {
  const id = path.basename(item.path, '.glb').toUpperCase();
  if (wanted && !wanted.includes(id)) continue;
  let reason;
  if (id === 'SORRY') reason = 'Production-ineligible/recovery candidates excluded';
  else if (signature(item) !== signature(pilotOriginal)) reason = 'Older/different texture generation: needs separate review';
  else if (item.external_uris.length) reason = 'External resources unsupported';
  if (reason) {rejected.push({id, source:item.path, reason}); continue;}
  if (!groups.has(id)) groups.set(id, []);
  groups.get(id).push(item);
}
const selected = [];
for (const [id, items] of groups) {
  const hashes = new Set(items.map(x=>x.sha256));
  if (hashes.size > 1) {rejected.push({id, reason:'Ambiguous corrected candidates: select explicitly before conversion', sources:items.map(x=>x.path)}); continue;}
  items.sort((a,b)=>a.path.localeCompare(b.path));
  selected.push({id, source:items[0], equivalentCopies:items.slice(1).map(x=>x.path)});
}
selected.sort((a,b)=>a.id.localeCompare(b.id));
if (wanted) for (const id of wanted) assert.ok(selected.some(x=>x.id===id), `Requested sign ${id} is missing or excluded`);
const plan = {schema:'apphear.text_to_asl.asset_batch.v1', output, selected:selected.map(x=>({id:x.id,source:x.source.path,sha256:x.source.sha256})), rejected};
if (args.includes('--plan')) {console.log(JSON.stringify(plan,null,2)); process.exit(0);}
assert.ok(selected.length, 'No eligible signs');
const require = createRequire(path.join(runtime,'package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const [{NodeIO}, {ALL_EXTENSIONS,EXTMeshoptCompression}, {MeshoptEncoder,MeshoptDecoder}, validatorModule] = await Promise.all([
  load('@gltf-transform/core'),load('@gltf-transform/extensions'),load('meshoptimizer'),load('gltf-validator')]);
const validator = validatorModule.default || validatorModule;
await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder,'meshopt.decoder':MeshoptDecoder});
const templateBytes = await fs.readFile(templatePath);
assert.equal(sha(templateBytes), 'a20ac50a9f754e8c464710ed3a180548482c38484b2b01861d88226e40ed3a06', 'Approved texture template changed');
const template = parseGLB(templateBytes);
const textureBank = new Map();
const view = (model,index) => {const v=model.doc.bufferViews[index]; assert.equal(v.buffer,0); return model.bin.subarray(v.byteOffset||0,(v.byteOffset||0)+v.byteLength);};
await fs.mkdir(path.join(output, 'reports'), {recursive:true});
await fs.mkdir(path.join(output, 'candidates'), {recursive:true});
const reportPath=path.join(output,'reports/batch-summary.json');
let prior;
try {prior=JSON.parse(await fs.readFile(reportPath,'utf8'));} catch(e) {if(e.code!=='ENOENT')throw e;}
const lockPath=path.join(output,'batch.lock');
const lock=await fs.open(lockPath,'wx');
const selectedIds=new Set(selected.map(x=>x.id));
const summary={...plan,started:new Date().toISOString(),status:'RUNNING',originalsChanged:false,appChanged:false,visualReview:'User accepted pilot appearance; additional signs not visually reviewed',deviceValidation:'PENDING',completed:(prior?.completed||[]).filter(x=>!selectedIds.has(x.id)),failed:[]};
const save=async()=>{const temporary=reportPath+`.${process.pid}.tmp`;await fs.writeFile(temporary,JSON.stringify(summary,null,2));await fs.rename(temporary,reportPath);};
try {
  await lock.writeFile(JSON.stringify({pid:process.pid,started:new Date().toISOString()}));
  const execute=promisify(execFile);
  for(let i=0;i<template.doc.images.length;i++) {
    const image=template.doc.images[i],original=pilotOriginal.images[i];
    assert.equal(image.name,original.name);
    const bytes=view(template,image.bufferView);
    const file=path.join(output,'reports',`shared-texture-${i}.ktx2`);
    await fs.writeFile(file,bytes);
    await execute(path.join(runtime,'ktx-portable/bin/ktx.exe'),['validate',file],{windowsHide:true});
    textureBank.set(original.sha256,bytes);
  }
  await save();
  for(const item of selected) {
    const filename=`${item.id}.balanced.ktx2mixed.meshopt_lossless.glb`;
    const target=path.join(output,'candidates',filename);
    try {
      const source=await fs.readFile(item.source.path);
      assert.equal(sha(source),item.source.sha256,'Source differs from assessed hash');
      const previous=prior?.completed.find(x=>x.id===item.id && x.sourceSha256===item.source.sha256);
      try {
        const existing=await fs.readFile(target);
        assert.ok(previous,'Existing output has no trusted completion record; refusing overwrite');
        assert.equal(sha(existing),previous.sha256,'Existing output checksum mismatch');
        summary.completed.push({...previous,resumed:true});
        await save(); console.log(`[assets] RESUME ${item.id}`); continue;
      } catch(e) {if(e.code!=='ENOENT')throw e;}
      const model=parseGLB(source),doc=structuredClone(model.doc),replacements=new Map();
      assert.equal(doc.images.length,pilotOriginal.images.length);
      for(const image of doc.images) {
        assert.ok(image.bufferView!==undefined && !image.uri);
        const encoded=textureBank.get(sha(view(model,image.bufferView)));
        assert.ok(encoded,`Unapproved texture: ${image.name}`);
        replacements.set(image.bufferView,encoded); image.mimeType='image/ktx2';
      }
      for(const mesh of doc.meshes) for(const p of mesh.primitives) assert.equal(p.mode??4,4,'Nontriangle mesh unsupported');
      const chunks=[];let offset=0;
      for(let i=0;i<doc.bufferViews.length;i++) {
        const bytes=replacements.get(i)||view(model,i),padding=(4-offset%4)%4;
        if(padding){chunks.push(Buffer.alloc(padding));offset+=padding;}
        doc.bufferViews[i].byteOffset=offset;doc.bufferViews[i].byteLength=bytes.length;
        chunks.push(bytes);offset+=bytes.length;
      }
      doc.buffers[0].byteLength=offset;
      doc.extensionsUsed=[...new Set([...(doc.extensionsUsed||[]),'KHR_texture_basisu'])];
      doc.extensionsRequired=[...new Set([...(doc.extensionsRequired||[]),'KHR_texture_basisu'])];
      for(const texture of doc.textures){assert.ok(texture.source!==undefined);texture.extensions={...(texture.extensions||{}),KHR_texture_basisu:{source:texture.source}};delete texture.source;}
      const intermediate=serializeGLB(doc,Buffer.concat(chunks)),repacked=parseGLB(intermediate);
      for(let i=0;i<doc.bufferViews.length;i++) if(!replacements.has(i)) assert.ok(view(model,i).equals(view(repacked,i)),'Nontexture buffer changed');
      for(const key of ['nodes','skins','animations','meshes','accessors','materials','scenes','samplers']) assert.deepEqual(model.doc[key],repacked.doc[key]);
      const document=await io.readBinary(new Uint8Array(intermediate));
      const baseline=structuralSnapshot(await io.readBinary(new Uint8Array(source)));
      assert.deepEqual(structuralSnapshot(document),baseline,'Texture replacement changed animation/rig');
      document.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.QUANTIZE});
      const packed=parseGLB(Buffer.from(await io.writeBinary(document)));
      packed.doc.nodes=structuredClone(doc.nodes);
      const bytes=serializeGLB(packed.doc,packed.bin);
      assert.deepEqual(structuralSnapshot(await io.readBinary(new Uint8Array(bytes))),baseline,'Compressed output changed rig/animation/numeric data/topology');
      const validation=await validator.validateBytes(new Uint8Array(bytes),{uri:filename,maxIssues:10000,writeTimestamp:false});
      await fs.writeFile(path.join(output,'reports',filename+'.validation.json'),JSON.stringify(validation,null,2));
      assert.equal(validation.issues.numErrors,0,'GLB validation errors');
      assert.equal(sha(await fs.readFile(item.source.path)),item.source.sha256,'Original changed during processing');
      await fs.writeFile(target,bytes,{flag:'wx'});
      assert.equal(sha(await fs.readFile(target)),sha(bytes),'Output write checksum failed');
      summary.completed.push({id:item.id,source:item.source.path,sourceSha256:item.source.sha256,originalBytes:source.length,file:target,bytes:bytes.length,sha256:sha(bytes),reductionPercent:100*(1-bytes.length/source.length),decodedDataAndOrientedTopologyExact:true,validationErrors:0,validationWarnings:validation.issues.numWarnings,resumed:false});
      await save(); console.log(`[assets] OK ${item.id}: ${(bytes.length/1048576).toFixed(2)} MiB`);
    } catch(e) {
      summary.failed.push({id:item.id,source:item.source.path,error:e.message});
      await save();console.error(`[assets] FAILED ${item.id}: ${e.message}`);
      // Persist unrelated completed work; continue collecting actionable per-file failures.
    }
  }
  summary.finished=new Date().toISOString();summary.status=summary.failed.length?'COMPLETED_WITH_FAILURES':'COMPLETE';
  summary.originalBytes=summary.completed.reduce((s,x)=>s+x.originalBytes,0);
  summary.optimizedBytes=summary.completed.reduce((s,x)=>s+x.bytes,0);
  await save();
  console.log(`[assets] ${summary.status}: ${summary.completed.length} completed, ${summary.failed.length} failed; ${(summary.optimizedBytes/1048576).toFixed(1)} MiB. Report: ${reportPath}`);
  if(summary.failed.length)process.exitCode=1;
} finally {await lock.close();await fs.unlink(lockPath);}
