// Append a neutral idle without re-encoding any existing sign or rendering resource.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {parseGLB, serializeGLB} from './verification.mjs';

const repo = path.resolve(import.meta.dirname, '../..');
const source = path.join(repo, 'android/app/src/aslWords/assets/asl_animations/vnext');
const output = path.resolve(process.argv[2] || path.join(repo, 'android/app/src/aslIdle/assets'));
assert.notEqual(output, path.join(repo, 'android/app/src/aslWords/assets'));
const runtime = path.join(repo, 'artifacts/text_to_asl_asset_optimization_20260928/tools');
const require = createRequire(path.join(runtime, 'package.json'));
const load = name => import(pathToFileURL(require.resolve(name)).href);
const [{NodeIO}, {ALL_EXTENSIONS}, {MeshoptDecoder}, validatorModule] = await Promise.all([
  load('@gltf-transform/core'), load('@gltf-transform/extensions'), load('meshoptimizer'), load('gltf-validator')]);
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder': MeshoptDecoder});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const sourceBytes = await fs.readFile(path.join(source, 'shared-words.glb'));
const manifest = JSON.parse(await fs.readFile(path.join(source, 'manifest.json'), 'utf8'));
for (const clip of [...manifest.clips, ...manifest.newClips]) assert.equal(clip.sha256, sha(sourceBytes));
const parsed = parseGLB(sourceBytes), base = structuredClone(parsed.doc);
assert.equal(base.animations.length, 27);
const document = await io.readBinary(sourceBytes), root = document.getRoot();
const reference = root.listAnimations()[0];
assert.equal(reference.getName(), 'SIGN_LETTER_A_FEMALEASL');
assert.equal(reference.listChannels().length, 4677);
const chunks = [parsed.bin];
let length = parsed.bin.length;
const accessorPool = new Map();
function accessor(values, type, count, min, max) {
  const bytes = Buffer.from(new Float32Array(values).buffer);
  const key = JSON.stringify([type, count, min, max, sha(bytes)]);
  if (accessorPool.has(key)) return accessorPool.get(key);
  const padding = (4 - length % 4) % 4;
  if (padding) {chunks.push(Buffer.alloc(padding)); length += padding;}
  const bufferView = base.bufferViews.length;
  base.bufferViews.push({buffer: 0, byteOffset: length, byteLength: bytes.length});
  chunks.push(bytes); length += bytes.length;
  const index = base.accessors.length;
  base.accessors.push({bufferView, componentType: 5126, count, type, ...(min ? {min, max} : {})});
  accessorPool.set(key, index);
  return index;
}
const duration = 6, name = 'IDLE_NEUTRAL_FEMALEASL';
const constantTime = accessor([0, duration], 'SCALAR', 2, [0], [duration]);
const times = Array.from({length: 49}, (_, i) => i * duration / 48);
const breathingTime = accessor(times, 'SCALAR', times.length, [0], [duration]);
// Uniform scale is independent of skeleton local-axis conventions. A 0.2% chest
// expansion moves the upper body only a few millimetres while leaving feet/root fixed.
const breathingNodes = new Set(['spine_03', 'spine_04']);
const animation = {name, channels: [], samplers: []}, baselines = [];
const samplerPool = new Map();
for (const channel of reference.listChannels()) {
  const sampler = channel.getSampler(), outputAccessor = sampler.getOutput();
  assert.notEqual(sampler.getInterpolation(), 'CUBICSPLINE', 'Re-audit cubic neutral extraction');
  const size = outputAccessor.getElementSize();
  const neutral = Array.from(outputAccessor.getArray().slice(0, size));
  assert.ok(neutral.every(Number.isFinite));
  const node = channel.getTargetNode(), nodeIndex = root.listNodes().indexOf(node), targetPath = channel.getTargetPath();
  assert.ok(['translation', 'rotation', 'scale'].includes(targetPath), 'Re-audit non-TRS track');
  if (targetPath === 'rotation') assert.ok(Math.abs(Math.hypot(...neutral) - 1) < 0.0001);
  const breath = targetPath === 'scale' && breathingNodes.has(node.getName());
  const values = breath ? times.flatMap((t, i) => {
    const expansion = i === 0 || i === times.length - 1 ? 0 : 0.002 * (1 - Math.cos(2 * Math.PI * t / duration)) / 2;
    return neutral.map(v => v * (1 + expansion));
  }) : [...neutral, ...neutral];
  const outputIndex = accessor(values, outputAccessor.getType(), breath ? times.length : 2);
  const newSampler = {input: breath ? breathingTime : constantTime, output: outputIndex, interpolation: breath ? 'LINEAR' : 'STEP'};
  const samplerKey = JSON.stringify(newSampler);
  if (!samplerPool.has(samplerKey)) {
    samplerPool.set(samplerKey, animation.samplers.length);
    animation.samplers.push(newSampler);
  }
  animation.channels.push({sampler: samplerPool.get(samplerKey), target: {node: nodeIndex, path: targetPath}});
  baselines.push({node: nodeIndex, path: targetPath, neutral, breath});
}
assert.equal(baselines.filter(b => b.breath).length, 6);
for (const skin of root.listSkins()) {
  assert.equal(skin.listJoints().filter(n => breathingNodes.has(n.getName())).length, 2,
    'Each body/clothing/hair skeleton must breathe together');
}
base.animations.push(animation);
base.buffers[0].byteLength = length;
const bytes = serializeGLB(base, Buffer.concat(chunks)), result = parseGLB(bytes);
assert.deepEqual(result.bin.subarray(0, parsed.bin.length), parsed.bin, 'Existing compressed bytes changed');
for (const [key, value] of Object.entries(parsed.doc)) {
  if (key === 'animations') assert.deepEqual(result.doc[key].slice(0, 27), value);
  else if (['accessors', 'bufferViews'].includes(key)) assert.deepEqual(result.doc[key].slice(0, value.length), value);
  else if (key === 'buffers') assert.deepEqual(result.doc[key].slice(1), value.slice(1));
  else assert.deepEqual(result.doc[key], value, `Rendering/hierarchy change: ${key}`);
}
const decoded = await io.readBinary(bytes), decodedRoot = decoded.getRoot();
function channelSignature(r, channel) {
  const sampler = channel.getSampler();
  const hash = a => ({type: a.getType(), count: a.getCount(), component: a.getComponentType(), normalized: a.getNormalized(),
    hash: sha(Buffer.from(a.getArray().buffer, a.getArray().byteOffset, a.getArray().byteLength))});
  return {node: r.listNodes().indexOf(channel.getTargetNode()), path: channel.getTargetPath(),
    interpolation: sampler.getInterpolation(), input: hash(sampler.getInput()), output: hash(sampler.getOutput())};
}
const signChecks = root.listAnimations().map((original, i) => {
  const added = decodedRoot.listAnimations()[i];
  assert.equal(added.getName(), original.getName());
  assert.deepEqual(added.listChannels().map(c => channelSignature(decodedRoot, c)),
    original.listChannels().map(c => channelSignature(root, c)));
  return {name: original.getName(), exactChannels: original.listChannels().length};
});
const idle = decodedRoot.listAnimations().at(-1);
assert.equal(idle.getName(), name);
const footNames = ['root', 'pelvis', 'foot_l', 'foot_r', 'ball_l', 'ball_r'];
const fixedNodes = decodedRoot.listNodes().filter(n => footNames.includes(n.getName()));
assert.ok(footNames.every(name => fixedNodes.some(n => n.getName() === name)));
const footPositions = [];
for (let frame = 0; frame < 49; frame++) {
  for (const [i, channel] of idle.listChannels().entries()) {
    const baseline = baselines[i], a = channel.getSampler().getOutput(), size = a.getElementSize();
    const values = a.getArray(), first = Array.from(values.slice(0, size)), last = Array.from(values.slice(-size));
    assert.deepEqual(first, baseline.neutral, 'Neutral reset changed');
    assert.deepEqual(last, first, 'Loop seam differs');
    assert.ok(values.every(Number.isFinite));
    if (!baseline.breath) assert.deepEqual(Array.from(values), [...first, ...first]);
    if (baseline.path === 'rotation') assert.ok(Math.abs(Math.hypot(...first) - 1) < 0.0001);
    const pose = Array.from(values.slice((baseline.breath ? frame : 0) * size, (baseline.breath ? frame + 1 : 1) * size));
    const node = channel.getTargetNode();
    node[{translation: 'setTranslation', rotation: 'setRotation', scale: 'setScale'}[baseline.path]](pose);
  }
  const positions = fixedNodes.map(n => n.getWorldTranslation());
  if (!frame) footPositions.push(...positions);
  else assert.deepEqual(positions, footPositions, 'Root/feet moved');
}
const validator = validatorModule.default || validatorModule;
const validation = await validator.validateBytes(new Uint8Array(bytes), {uri: 'shared-words-idle.glb', maxIssues: 100});
assert.equal(validation.issues.numErrors, 0, JSON.stringify(validation.issues));
const asset = 'asl_animations/vnext/shared-words-idle.glb', profile = 'balanced-ktx2mixed-meshopt-shared-idle-v1';
const patch = c => ({...c, asset, profile, sha256: sha(bytes)});
const resultManifest = {...manifest, clips: manifest.clips.map(patch), newClips: manifest.newClips.map(patch),
  idle: {id: 'idle', sourceId: 'IDLE', type: 'pose', asset, profile, sha256: sha(bytes),
    rigProfile: 'FemaleASL-full-rig-341-875-342', animationName: name, durationMs: duration * 1000,
    fallbackAsset: 'asl_animations/asl_idle.glb'}};
const report = {schema: 'apphear.text_to_asl.new_idle.v1', sourceSha256: sha(sourceBytes), sha256: sha(bytes),
  sourceMiB: sourceBytes.length / 1048576, bundleMiB: bytes.length / 1048576, addedBytes: bytes.length - sourceBytes.length,
  originalBinaryPrefixExact: true, renderingResourcesExact: true, signChecks, idle: {name, durationSeconds: duration,
    resetChannels: baselines.length, breathingNodes: [...breathingNodes], breathingTracksAcrossThreeSkins: 6, peakScaleExpansion: 0.002,
    neutralResetsExact: true, loopSeamExact: true, rootFeetStationary: true},
  validationErrors: validation.issues.numErrors, validationWarnings: validation.issues.numWarnings, deviceGate: 'PENDING'};
await fs.mkdir(path.join(output, 'asl_animations/vnext'), {recursive: true});
const target = path.join(output, asset);
try {assert.deepEqual(await fs.readFile(target), bytes, 'Refusing to overwrite a different derivative');}
catch (error) {if (error.code !== 'ENOENT') throw error; await fs.writeFile(target, bytes);}
await fs.writeFile(path.join(output, 'asl_animations/vnext/manifest.json'), JSON.stringify(resultManifest, null, 2));
const reports = path.join(repo, 'artifacts/text_to_asl_idle_20260928');
await fs.mkdir(reports, {recursive: true});
await fs.writeFile(path.join(reports, 'bundle-verification.json'), JSON.stringify(report, null, 2));
await fs.writeFile(path.join(reports, 'gltf-validation.json'), JSON.stringify(validation, null, 2));
console.log(JSON.stringify({...report, signChecks: `${signChecks.length} signs exact`}, null, 2));
