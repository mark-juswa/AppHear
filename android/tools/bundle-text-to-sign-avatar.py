"""Pack existing identical-rig GLBs; copy motion bytes, never synthesize/retarget signs."""
import copy
import hashlib
import json
from pathlib import Path
import struct

IDENTITY_KEYS = ['nodes', 'skins', 'meshes', 'materials', 'textures', 'images', 'samplers', 'scenes', 'scene']

def read(path):
    payload = path.read_bytes()
    assert struct.unpack_from('<III', payload) == (0x46546c67, 2, len(payload))
    length, kind = struct.unpack_from('<II', payload, 12)
    assert kind == 0x4e4f534a
    document = json.loads(payload[20:20+length])
    binary_length, binary_kind = struct.unpack_from('<II', payload, 20+length)
    assert binary_kind == 0x004e4942 and len(document['buffers']) == 1
    binary = payload[28+length:28+length+binary_length]
    return payload, document, binary

def identity(gltf):
    return {key: gltf.get(key) for key in IDENTITY_KEYS}

def geometry(gltf, binary):
    indices = {image['bufferView'] for image in gltf.get('images', []) if 'bufferView' in image}
    for mesh in gltf['meshes']:
        for primitive in mesh['primitives']:
            accessors = list(primitive['attributes'].values()) + ([primitive['indices']] if 'indices' in primitive else [])
            for target in primitive.get('targets', []): accessors.extend(target.values())
            for i in accessors:
                accessor=gltf['accessors'][i]
                if 'bufferView' in accessor: indices.add(accessor['bufferView'])
                if 'sparse' in accessor:
                    indices.add(accessor['sparse']['indices']['bufferView'])
                    indices.add(accessor['sparse']['values']['bufferView'])
    indices.update(gltf['accessors'][skin['inverseBindMatrices']]['bufferView'] for skin in gltf['skins'])
    return [binary[gltf['bufferViews'][i].get('byteOffset',0):gltf['bufferViews'][i].get('byteOffset',0)+gltf['bufferViews'][i]['byteLength']] for i in sorted(indices)]

def main():
    android = Path(__file__).resolve().parents[1]
    assets = android / 'app/src/aslOriginalWords/assets'
    source = json.loads((assets/'asl_animations/original_words_v1/manifest.json').read_text())
    entries = source['replacements'] + source['newClips']
    hello = next(e for e in entries if e['id']=='hello')
    _, base, base_bin = read(assets/hello['asset'])
    expected_identity, expected_geometry = identity(base), geometry(base,base_bin)
    output = copy.deepcopy(base)
    output['animations'] = []
    binary = bytearray(base_bin[:base['buffers'][0]['byteLength']])
    for entry in entries:
        payload, gltf, clip_bin = read(assets/entry['asset'])
        assert hashlib.sha256(payload).hexdigest()==entry['sha256']
        assert identity(gltf)==expected_identity and geometry(gltf,clip_bin)==expected_geometry, entry['id']
        assert gltf.get('extensionsUsed',[])==base.get('extensionsUsed',[])
        assert len(gltf['animations'])==1 and gltf['animations'][0]['name']==entry['animationName']
        animation = copy.deepcopy(gltf['animations'][0])
        accessors, views = {}, {}
        for sampler in animation['samplers']:
            for key in ['input','output']:
                index = sampler[key]
                if index not in accessors:
                    accessor = copy.deepcopy(gltf['accessors'][index])
                    assert 'sparse' not in accessor
                    view_index = accessor['bufferView']
                    if view_index not in views:
                        view = copy.deepcopy(gltf['bufferViews'][view_index])
                        assert view['buffer']==0 and 'extensions' not in view
                        start = view.get('byteOffset',0)
                        while len(binary)%4: binary.append(0)
                        view['byteOffset'] = len(binary)
                        binary.extend(clip_bin[start:start+view['byteLength']])
                        views[view_index] = len(output['bufferViews'])
                        output['bufferViews'].append(view)
                    accessor['bufferView']=views[view_index]
                    accessors[index]=len(output['accessors'])
                    output['accessors'].append(accessor)
                sampler[key]=accessors[index]
        output['animations'].append(animation)
    assert len({a['name'] for a in output['animations']})==203
    output['buffers'][0]['byteLength']=len(binary)
    encoded=json.dumps(output,separators=(',',':')).encode()
    encoded+=b' '*(-len(encoded)%4)
    binary+=b'\0'*(-len(binary)%4)
    result=struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))
    result+=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
    target=assets/'asl_animations/original_words_v1/resident-avatar.glb'
    target.write_bytes(result)
    registry=dict(schemaVersion=1,language='ASL',avatarProfile='ORIGINAL_HUMAN',asset='asl_animations/original_words_v1/resident-avatar.glb',
        sha256=hashlib.sha256(result).hexdigest(),bytes=len(result),animations=[dict(id=e['id'],animationName=e['animationName'],
        durationMs=e['durationMs'],sourceAsset=e['asset'],sourceSha256=e['sha256']) for e in entries])
    target.with_suffix('.json').write_text(json.dumps(registry,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in registry.items() if k!='animations'},indent=2))

if __name__=='__main__': main()
