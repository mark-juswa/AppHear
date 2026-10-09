// Append C-Z to the phone-tested shared sign/idle rig without changing its 28 clips.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {parseGLB, serializeGLB} from './verification.mjs';

const repo = path.resolve(import.meta.dirname, '../..');
const source = path.join(repo, 'android/app/src/aslIdle/assets/asl_animations/vnext');
const output = path.resolve(process.argv[2] || path.join(repo, 'android/app/src/aslAlphabet/assets'));
assert.notEqual(output, path.join(repo, 'android/app/src/aslIdle/assets'));
const runtime = path.join(repo, 'artifacts/text_to_asl_asset_optimization_20260928/tools');
const require = createRequire(path.join(runtime, 'package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const [{NodeIO}, {ALL_EXTENSIONS}, {MeshoptDecoder}, validatorModule] = await Promise.all([
  load('@gltf-transform/core'), load('@gltf-transform/extensions'), load('meshoptimizer'), load('gltf-validator')]);
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const clone = value => structuredClone(value);
const hashAccessor = a => ({type: a.getType(), component: a.getComponentType(), normalized: a.getNormalized(),
  count: a.getCount(), hash: sha(Buffer.from(a.getArray().buffer, a.getArray().byteOffset, a.getArray().byteLength))});
const manifest = JSON.parse(await fs.readFile(path.join(source, 'manifest.json'), 'utf8'));
const originalBytes = await fs.readFile(path.join(source, 'shared-words-idle.glb'));
assert.equal(manifest.schemaVersion, 2);
assert.equal(manifest.clips.length, 7);
assert.equal(manifest.newClips.length, 20);
assert.equal(manifest.idle.sha256, sha(originalBytes));
const parsed = parseGLB(originalBytes), base = clone(parsed.doc);
assert.equal(base.animations.length, 28);
const originalDocument = await io.readBinary(originalBytes);
const batch = JSON.parse(await fs.readFile('G:/3d Characters/optimized_apphear3_batch/reports/batch-summary.json', 'utf8'));
assert.equal(batch.status, 'COMPLETE');
const records = new Map(batch.completed.map(record => [record.id, record]));
const alphabet = 'CDEFGHIJKLMNOPQRSTUVWXYZ';
const HAIR_NODE = 1230;
assert.equal(base.nodes[HAIR_NODE].name, 'Hair_M_BobCurly_Helmet_LOD7');

function renderingSignature(document) {
  const r = document.getRoot(), nodes = r.listNodes();
  return {
    geometry: r.listMeshes().map(m => m.listPrimitives().map(p => ({mode: p.getMode(),
      indices: p.getIndices() ? hashAccessor(p.getIndices()) : null,
      attributes: p.listSemantics().map(s => [s, hashAccessor(p.getAttribute(s))]),
      morph: p.listTargets().map(t => t.listSemantics().map(s => [s, hashAccessor(t.getAttribute(s))]))}))),
    skins: r.listSkins().map(s => ({joints: s.listJoints().map(n => nodes.indexOf(n)),
      skeleton: nodes.indexOf(s.getSkeleton()), ibm: hashAccessor(s.getInverseBindMatrices())})),
    textures: r.listTextures().map(t => sha(t.getImage())),
  };
}
const renderBase = renderingSignature(originalDocument);
const chunks = [parsed.bin];
let length = parsed.bin.length;
function appendBytes(bytes) {
  const pad = (4 - length % 4) % 4;
  if (pad) { chunks.push(Buffer.alloc(pad)); length += pad; }
  const offset = length; chunks.push(Buffer.from(bytes)); length += bytes.length; return offset;
}
function copyAnimation(model) {
  const accessorMap = new Map(), viewMap = new Map();
  function copyAccessor(index) {
    if (accessorMap.has(index)) return accessorMap.get(index);
    const a = clone(model.doc.accessors[index]); assert.ok(!a.sparse);
    if (!viewMap.has(a.bufferView)) {
      const v = clone(model.doc.bufferViews[a.bufferView]);
      const ext = v.extensions?.EXT_meshopt_compression;
      assert.ok(ext && ext.buffer === 0 && v.buffer === 1, 'Unexpected animation buffer format');
      const start = ext.byteOffset || 0;
      assert.ok(start + ext.byteLength <= model.bin.length);
      ext.byteOffset = appendBytes(model.bin.subarray(start, start + ext.byteLength));
      v.byteOffset = base.buffers[1].byteLength;
      base.buffers[1].byteLength += v.byteLength;
      viewMap.set(a.bufferView, base.bufferViews.length); base.bufferViews.push(v);
    }
    a.bufferView = viewMap.get(a.bufferView);
    accessorMap.set(index, base.accessors.length); base.accessors.push(a);
    return accessorMap.get(index);
  }
  const animation = clone(model.doc.animations[0]);
  for (const sampler of animation.samplers) {
    sampler.input = copyAccessor(sampler.input);
    sampler.output = copyAccessor(sampler.output);
  }
  return animation;
}
function constantAccessor(values, type, count, min, max) {
  const bytes = Buffer.from(new Float32Array(values).buffer);
  const view = base.bufferViews.length;
  base.bufferViews.push({buffer: 0, byteOffset: appendBytes(bytes), byteLength: bytes.length});
  const accessor = base.accessors.length;
  base.accessors.push({bufferView: view, componentType: 5126, count, type, ...(min ? {min, max} : {})});
  return accessor;
}
const checks = [];
for (const letter of alphabet) {
  const record = records.get(letter);
  assert.ok(record && record.decodedDataAndOrientedTopologyExact && record.validationErrors === 0,
    `Unverified letter ${letter}`);
  assert.equal(sha(await fs.readFile(record.source)), record.sourceSha256, `Raw ${letter} changed`);
  const bytes = await fs.readFile(record.file);
  assert.equal(sha(bytes), record.sha256, `Optimized ${letter} changed`);
  const model = parseGLB(bytes), decoded = await io.readBinary(bytes);
  assert.equal(model.doc.animations.length, 1);
  const name = `SIGN_LETTER_${letter}_FEMALEASL`;
  assert.equal(model.doc.animations[0].name, name);
  assert.deepEqual(renderingSignature(decoded), renderBase, `Rendering changed: ${letter}`);
  const current = clone(model.doc), reference = clone(parsed.doc);
  for (const d of [current, reference]) for (const m of d.materials) delete m.name;
  for (const key of ['scenes', 'skins', 'meshes', 'textures', 'samplers'])
    assert.deepEqual(current[key], reference[key], `${letter} ${key}`);
  assert.equal(current.nodes.length, reference.nodes.length);
  for (let i = 0; i < current.nodes.length; i++) {
    if (i === HAIR_NODE) {
      for (const key of ['translation', 'rotation', 'scale']) {
        assert.ok(current.nodes[i][key].every((v, j) => Math.abs(v - reference.nodes[i][key][j]) <= 1.1920928955078125e-7));
        delete current.nodes[i][key]; delete reference.nodes[i][key];
      }
    }
    assert.deepEqual(current.nodes[i], reference.nodes[i], `${letter} node ${i}`);
  }
  assert.ok(!model.doc.animations[0].channels.some(c => c.target.node === HAIR_NODE));
  const animation = copyAnimation(model);
  const sourceAnimation = decoded.getRoot().listAnimations()[0];
  const duration = Math.max(...sourceAnimation.listSamplers().map(s => s.getInput().getArray().at(-1)));
  const time = constantAccessor([0, duration], 'SCALAR', 2, [0], [duration]);
  for (const [key, type] of [['translation', 'VEC3'], ['rotation', 'VEC4'], ['scale', 'VEC3']]) {
    const values = model.doc.nodes[HAIR_NODE][key];
    const value = constantAccessor([...values, ...values], type, 2);
    const sampler = animation.samplers.length;
    animation.samplers.push({input: time, output: value, interpolation: 'STEP'});
    animation.channels.push({sampler, target: {node: HAIR_NODE, path: key}});
  }
  base.animations.push(animation);
  checks.push({letter, name, sourceSha256: record.sha256, durationMs: Math.ceil(duration * 1000),
    channels: sourceAnimation.listChannels().length});
  console.log(`Verified and appended ${letter}`);
}
assert.equal(base.animations.length, 52);
base.buffers[0].byteLength = length;
const bytes = serializeGLB(base, Buffer.concat(chunks));
const result = parseGLB(bytes);
assert.deepEqual(result.bin.subarray(0, parsed.bin.length), parsed.bin, 'Original binary changed');
assert.deepEqual(result.doc.animations.slice(0, 28), parsed.doc.animations, 'Existing animation changed');
for (const key of ['accessors', 'bufferViews'])
  assert.deepEqual(result.doc[key].slice(0, parsed.doc[key].length), parsed.doc[key], `${key} prefix changed`);
const decodedResult = await io.readBinary(bytes);
assert.deepEqual(renderingSignature(decodedResult), renderBase);
function channelSignature(document, channel) {
  const r = document.getRoot(), s = channel.getSampler();
  return {node: r.listNodes().indexOf(channel.getTargetNode()), path: channel.getTargetPath(),
    interpolation: s.getInterpolation(), input: hashAccessor(s.getInput()), output: hashAccessor(s.getOutput())};
}
for (let i = 0; i < alphabet.length; i++) {
  const letter = alphabet[i], record = records.get(letter);
  const sourceDoc = await io.readBinary(await fs.readFile(record.file));
  const original = sourceDoc.getRoot().listAnimations()[0];
  const copied = decodedResult.getRoot().listAnimations()[28 + i];
  assert.equal(copied.getName(), original.getName());
  assert.equal(copied.listChannels().length, original.listChannels().length + 3);
  for (let c = 0; c < original.listChannels().length; c++) {
    assert.deepEqual(channelSignature(decodedResult, copied.listChannels()[c]),
      channelSignature(sourceDoc, original.listChannels()[c]));
  }
}
const validator = validatorModule.default || validatorModule;
const validation = await validator.validateBytes(new Uint8Array(bytes), {uri: 'shared-alphabet.glb', maxIssues: 100});
assert.equal(validation.issues.numErrors, 0, JSON.stringify(validation.issues));
const asset = 'asl_animations/vnext/shared-alphabet.glb';
const profile = 'balanced-ktx2mixed-meshopt-shared-alphabet-v1';
const hash = sha(bytes);
const adapt = clip => ({...clip, asset, profile, sha256: hash});
const outputManifest = {schemaVersion: 3, clips: manifest.clips.map(adapt),
  newClips: manifest.newClips.map(adapt), idle: adapt(manifest.idle),
  letters: checks.map(c => ({id: `letter_${c.letter.toLowerCase()}`, sourceId: c.letter,
    displayText: c.letter, type: 'letter', asset, animationName: c.name,
    durationMs: c.durationMs, profile, rigProfile: 'FemaleASL-full-rig-341-875-342', sha256: hash}))};
const dir = path.join(output, 'asl_animations/vnext'); await fs.mkdir(dir, {recursive: true});
const target = path.join(dir, 'shared-alphabet.glb');
try { assert.deepEqual(await fs.readFile(target), bytes, 'Refusing to overwrite a different bundle'); }
catch (error) { if (error.code !== 'ENOENT') throw error; await fs.writeFile(target, bytes); }
await fs.writeFile(path.join(dir, 'manifest.json'), JSON.stringify(outputManifest, null, 2));
const reports = path.join(repo, 'artifacts/text_to_asl_alphabet_20260928'); await fs.mkdir(reports, {recursive: true});
await fs.writeFile(path.join(reports, 'bundle-verification.json'), JSON.stringify({schema: 'apphear.text_to_asl.alphabet.v1',
  priorBundleSha256: sha(originalBytes), sha256: hash, bytes: bytes.length, existingAnimationsUnchanged: 28,
  addedLetters: checks, validationErrors: validation.issues.numErrors,
  validationWarnings: validation.issues.numWarnings}, null, 2));
await fs.writeFile(path.join(reports, 'gltf-validation.json'), JSON.stringify(validation, null, 2));
console.log(JSON.stringify({bytes: bytes.length, sha256: hash, animations: base.animations.length,
  validatorErrors: validation.issues.numErrors, validatorWarnings: validation.issues.numWarnings}));
