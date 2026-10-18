// Development tool only: decode existing animation buffers using the vendored MIT decoder.
const fs = require('fs');
const path = require('path');
const android = path.resolve(__dirname, '..');
const decoder = require(path.join(android, 'app/src/aslPilot/assets/vendor/asl-decoders/meshopt_decoder.js'));
(async () => {
  await decoder.ready;
  const source = path.join(android, 'app/src/aslAlphabet/assets/asl_animations/vnext/shared-alphabet.glb');
  const bytes = fs.readFileSync(source), length = bytes.readUInt32LE(12);
  const gltf = JSON.parse(bytes.subarray(20, 20 + length));
  const bin = bytes.subarray(28 + length), views = new Map();
  function accessor(index) {
    const a = gltf.accessors[index], v = gltf.bufferViews[a.bufferView];
    if (!views.has(a.bufferView)) {
      const e = v.extensions?.EXT_meshopt_compression;
      if (e) {
        const output = new Uint8Array(e.count * e.byteStride);
        decoder.decodeGltfBuffer(output, e.count, e.byteStride,
          bin.subarray(e.byteOffset, e.byteOffset + e.byteLength), e.mode, e.filter);
        views.set(a.bufferView, Buffer.from(output));
      } else views.set(a.bufferView, bin.subarray(v.byteOffset || 0, (v.byteOffset || 0) + v.byteLength));
    }
    if (a.componentType !== 5126 || a.sparse) throw Error('Unsupported animation accessor');
    const n = {SCALAR: 1, VEC3: 3, VEC4: 4}[a.type], data = views.get(a.bufferView);
    const stride = v.byteStride || n * 4, offset = a.byteOffset || 0;
    return Array.from({length: a.count}, (_, i) => Array.from({length: n}, (_, k) => data.readFloatLE(offset + i * stride + k * 4)));
  }
  const animations = gltf.animations.filter(a => /^SIGN_LETTER_[A-Z]_FEMALEASL$/.test(a.name)).map(a => ({
    name: a.name,
    channels: a.channels.filter(c => c.target.node <= 341).map(c => {
      const s = a.samplers[c.sampler];
      if (!['LINEAR', 'STEP'].includes(s.interpolation || 'LINEAR')) throw Error('Unsupported interpolation');
      return {node: c.target.node, path: c.target.path, interpolation: s.interpolation || 'LINEAR', times: accessor(s.input).flat(), values: accessor(s.output)};
    })
  }));
  if (animations.length !== 26) throw Error('Incomplete source alphabet');
  fs.writeFileSync(process.argv[2], JSON.stringify({sourceSha256: require('crypto').createHash('sha256').update(bytes).digest('hex'), nodes: gltf.nodes, animations}));
  process.stdout.write('Decoded 26 existing alphabet clips; no motion generated.\n');
})();
