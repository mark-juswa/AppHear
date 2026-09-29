import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function parseGLB(bytes) {
  assert.equal(bytes.readUInt32LE(0),0x46546c67);
  assert.equal(bytes.readUInt32LE(4),2);
  assert.equal(bytes.readUInt32LE(8),bytes.length);
  const jsonLength=bytes.readUInt32LE(12);
  assert.equal(bytes.readUInt32LE(16),0x4e4f534a);
  const doc=JSON.parse(bytes.subarray(20,20+jsonLength).toString());
  const binStart=28+jsonLength;
  assert.equal(bytes.readUInt32LE(24+jsonLength),0x004e4942);
  return {doc,bin:bytes.subarray(binStart)};
}
function serializeGLB(doc,bin) {
  const raw=Buffer.from(JSON.stringify(doc));
  const json=Buffer.alloc(Math.ceil(raw.length/4)*4,0x20);raw.copy(json);
  const padded=Buffer.alloc(Math.ceil(bin.length/4)*4);bin.copy(padded);
  const bytes=Buffer.alloc(12+8+json.length+8+padded.length);
  bytes.writeUInt32LE(0x46546c67,0);bytes.writeUInt32LE(2,4);bytes.writeUInt32LE(bytes.length,8);
  bytes.writeUInt32LE(json.length,12);bytes.writeUInt32LE(0x4e4f534a,16);json.copy(bytes,20);
  bytes.writeUInt32LE(padded.length,20+json.length);bytes.writeUInt32LE(0x004e4942,24+json.length);padded.copy(bytes,28+json.length);
  return bytes;
}function structuralSnapshot(document) {
  const root=document.getRoot(),nodes=root.listNodes();
  const nodeIndex=n=>nodes.indexOf(n);
  const indexAccessors=new Set(root.listMeshes().flatMap(m=>m.listPrimitives().map(p=>p.getIndices())).filter(Boolean));
  function numericHash(a) {
    if(!indexAccessors.has(a))return sha(Buffer.from(a.getArray().buffer,a.getArray().byteOffset,a.getArray().byteLength));
    const indices=a.getArray(),canonical=[];
    // Meshopt triangle mode may rotate (a,b,c) to (b,c,a); preserve triangle order and winding.
    for(let i=0;i<indices.length;i+=3) {
      const rotations=[[indices[i],indices[i+1],indices[i+2]],[indices[i+1],indices[i+2],indices[i]],[indices[i+2],indices[i],indices[i+1]]];
      rotations.sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2]);canonical.push(...rotations[0]);
    }
    return sha(Buffer.from(new Uint32Array(canonical).buffer));
  }
  return {
    nodes:nodes.map(n=>({name:n.getName(),t:n.getTranslation(),r:n.getRotation(),s:n.getScale(),children:n.listChildren().map(nodeIndex),skin:root.listSkins().indexOf(n.getSkin()),mesh:root.listMeshes().indexOf(n.getMesh())})),
    skins:root.listSkins().map(s=>({name:s.getName(),joints:s.listJoints().map(nodeIndex),ibm:sha(Buffer.from(s.getInverseBindMatrices().getArray().buffer,s.getInverseBindMatrices().getArray().byteOffset,s.getInverseBindMatrices().getArray().byteLength))})),
    accessors:root.listAccessors().map(a=>({type:a.getType(),component:a.getComponentType(),normalized:a.getNormalized(),count:a.getCount(),hash:numericHash(a),isTriangleIndex:indexAccessors.has(a)})),
    animations:root.listAnimations().map(a=>({name:a.getName(),channels:a.listChannels().map(c=>({node:nodeIndex(c.getTargetNode()),path:c.getTargetPath(),sampler:a.listSamplers().indexOf(c.getSampler())})),samplers:a.listSamplers().map(s=>({interpolation:s.getInterpolation(),input:root.listAccessors().indexOf(s.getInput()),output:root.listAccessors().indexOf(s.getOutput())}))})),
  };
}
export {parseGLB,serializeGLB,structuralSnapshot};
