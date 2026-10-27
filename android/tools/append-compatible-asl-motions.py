"""Append same-rig actions without copying a source avatar or changing old actions.

Inputs are verified local GLBs: latest working, licensed external, primary rollback.
This does not retarget rigs, infer signs, select linguistic variants or edit hands.
"""
import argparse,copy,hashlib,importlib.util,json,struct
from pathlib import Path

spec=importlib.util.spec_from_file_location('verify',Path(__file__).with_name('verify-integrated-vocabulary.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def main():
    p=argparse.ArgumentParser();p.add_argument('working',type=Path);p.add_argument('external',type=Path)
    p.add_argument('primary',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert not a.output.exists(),'Choose a new output file; never overwrite source assets implicitly'
    inputs=[x.read_bytes() for x in [a.working,a.external,a.primary]]
    expected=['99dbd596f53c89a561cc517e8bc2f436dc737b3cc2001f4cfefaf89cc8a12963',
        '7840f979713d878f273a71975c38e1d12dbf3856151af531cbed8daf70fd0024',
        'e9079308b6780e180528e4b893e64bdb77e46b33b6ad2cd99355bec03df57b18']
    assert [v.sha(b) for b in inputs]==expected
    parsed=[v.glb(b) for b in inputs];base,old=parsed[0];g=copy.deepcopy(base)
    for sg,sb in parsed[1:]:
        for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert g[key]==sg[key],key
        assert old[:19_000_000]==sb[:19_000_000]
    binary=bytearray(old[:base['buffers'][0]['byteLength']]);views={};accessors={}
    def accessor(sg,sb,index,label):
        key=(label,index)
        if key in accessors:return accessors[key]
        acc=copy.deepcopy(sg['accessors'][index]);assert 'sparse' not in acc
        vi=acc['bufferView'];vk=(label,vi)
        if vk not in views:
            view=copy.deepcopy(sg['bufferViews'][vi]);start=view.get('byteOffset',0)
            binary.extend(b'\0'*((-len(binary))%4));view['byteOffset']=len(binary);view['buffer']=0
            binary.extend(sb[start:start+view['byteLength']]);views[vk]=len(g['bufferViews']);g['bufferViews'].append(view)
        acc['bufferView']=views[vk];accessors[key]=len(g['accessors']);g['accessors'].append(acc);return accessors[key]
    def append(sg,sb,action,label,name=None):
        action=copy.deepcopy(action)
        if name:action['name']=name
        for sample in action['samplers']:
            for kind in ['input','output']:sample[kind]=accessor(sg,sb,sample[kind],label)
        g['animations'].append(action)
    current={x['name']:x for x in base['animations']}
    sg,sb=parsed[1]
    for action in sg['animations']:
        if action['name'] not in current:append(sg,sb,action,'C')
    sg,sb=parsed[2]
    for action in sg['animations']:
        name=action['name']
        if v.actionhash(sg,sb,action)!=v.actionhash(base,old,current[name]):
            append(sg,sb,action,'B','REVIEW_PRIMARY__'+name)
    assert len(g['animations'])==740
    g['buffers'][0]['byteLength']=len(binary)
    metadata=json.dumps(g,separators=(',',':')).encode();metadata+=b' '*((-len(metadata))%4)
    binary.extend(b'\0'*((-len(binary))%4))
    result=struct.pack('<III',0x46546c67,2,28+len(metadata)+len(binary))+struct.pack('<II',len(metadata),0x4e4f534a)+metadata+struct.pack('<II',len(binary),0x004e4942)+binary
    assert v.sha(result)=='7975abceb4c75e09cab995600d6b852edbd608a44e4e4a07550746544f7e7aec'
    a.output.write_bytes(result);print(json.dumps(dict(bytes=len(result),sha256=v.sha(result),actions=740)))
if __name__=='__main__':main()
