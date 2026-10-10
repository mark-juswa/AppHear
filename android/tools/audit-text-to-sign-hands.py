"""Development-only CPU skinning audit of real glTF meshes, not ASL validation.

Usage: python tools/audit-text-to-sign-hands.py BEFORE.glb AFTER.glb OUTPUT_DIR
Requires development NumPy/Pillow. No libraries or controls are added to the APK.
Samples both hands and real bone locations; produces before/after front/side
views and numeric skin/mesh checks. Android/WebGL testing is still required.
"""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw

spec=importlib.util.spec_from_file_location('retarget',Path(__file__).with_name('retarget-text-to-sign-alphabet.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class Model:
    def __init__(self,path):
        _,self.g,self.binary=r.packer.read(Path(path))
        self.nodes=self.g['nodes'];self.parents,self.order=r.skeleton(self.nodes)
        self.names={n.get('name'):i for i,n in enumerate(self.nodes)}
        self.animations={a['name']:a for a in self.g['animations']}
        self.meshes=[];self.bind_error=0.;self.weight_error=0.
        rest=r.world(self.nodes,self.parents,self.order)
        for node in self.nodes:
            if 'skin' not in node or 'mesh' not in node:continue
            skin=self.g['skins'][node['skin']];jids=skin['joints']
            ibm=self.data(skin['inverseBindMatrices']).reshape((-1,4,4)).transpose(0,2,1)
            self.bind_error=max(self.bind_error,max(float(np.max(np.abs(rest[j]@ibm[k]-np.eye(4)))) for k,j in enumerate(jids)))
            for p in self.g['meshes'][node['mesh']]['primitives']:
                at=p['attributes'];pos=self.data(at['POSITION']);weights=self.data(at['WEIGHTS_0']);joints=self.data(at['JOINTS_0']).astype(int)
                assert np.isfinite(weights).all() and (weights>=0).all()
                self.weight_error=max(self.weight_error,float(np.max(np.abs(weights.sum(1)-1))))
                triangles=self.data(p['indices']).reshape((-1,3)).astype(int)
                self.meshes.append((np.c_[pos,np.ones(len(pos))],weights,joints,triangles,jids,ibm))
    def data(self,index):
        a=self.g['accessors'][index];v=self.g['bufferViews'][a['bufferView']]
        dtype={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]
        n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        stride=v.get('byteStride',np.dtype(dtype).itemsize*n)
        out=np.ndarray((a['count'],n),dtype=dtype,buffer=self.binary,
            offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(stride,np.dtype(dtype).itemsize)).copy()
        return out/np.iinfo(dtype).max if a.get('normalized') else out
    def tracks(self,name):
        a=self.animations[name];out=[]
        for c in a['channels']:
            s=a['samplers'][c['sampler']]
            out.append(dict(node=c['target']['node'],path=c['target']['path'],times=self.data(s['input']).flatten().tolist(),values=self.data(s['output']).tolist(),interpolation=s.get('interpolation','LINEAR')))
        return out
    def pose(self,tracks,time):
        return r.world(self.nodes,self.parents,self.order,{(c['node'],c['path']):r.sample(c,time) for c in tracks})
    def hand(self,world,side):
        out=[]
        for pos,weights,joints,triangles,jids,ibm in self.meshes:
            matrices=np.array([world[j]@ibm[k] for k,j in enumerate(jids)])
            vertices=sum(np.einsum('nij,nj->ni',matrices[joints[:,i]],pos)*weights[:,i,None] for i in range(4))[:,:3]
            indices=[k for k,j in enumerate(jids) if side+'Hand' in self.nodes[j].get('name','')]
            mask=np.sum(weights*np.isin(joints,indices),axis=1)>.65
            # Include boundary triangles, so fingers aren't visually cut at a weight threshold.
            tris=triangles[np.any(mask[triangles],axis=1)]
            if len(tris):out.append((vertices,tris,pos[:,:3]))
        return out

def render(draw,model,world,side,cell,axes=(0,1),bones=False):
    meshes=model.hand(world,side);points=np.concatenate([v[t.flatten()] for v,t,_ in meshes])
    low=points.min(0);high=points.max(0);center=(low+high)/2
    scale=180/max(high[axes[0]]-low[axes[0]],high[axes[1]]-low[axes[1]])
    def project(v):return (cell[0]+110+(v[axes[0]]-center[axes[0]])*scale,cell[1]+135-(v[axes[1]]-center[axes[1]])*scale)
    depth=next(a for a in range(3) if a not in axes)
    for vertices,tris,_ in meshes:
        polygons=vertices[tris]
        for poly in polygons[np.argsort(polygons[:,:,depth].mean(1))]:
            normal=np.cross(poly[1]-poly[0],poly[2]-poly[0]);shade=int(130+65*abs(normal[depth])/(np.linalg.norm(normal)+1e-9))
            draw.polygon([project(v) for v in poly],fill=(shade,shade-15,shade-25))
    if bones:
        for name,i in model.names.items():
            if side+'Hand' not in (name or ''):continue
            parent=model.parents.get(i)
            if parent is not None and side+'Hand' in model.nodes[parent].get('name',''):
                draw.line([project(world[parent][:3,3]),project(world[i][:3,3])],fill='#02c5ff',width=2)
            x,y=project(world[i][:3,3]);draw.ellipse((x-2,y-2,x+2,y+2),fill='red')
    ratios=[]
    for vertices,tris,rest in meshes:
        edges=np.unique(np.sort(np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]]),axis=1),axis=0)
        lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
        valid=lengths>1e-6
        ratios.extend((np.linalg.norm(vertices[edges[valid,0]]-vertices[edges[valid,1]],axis=1)/lengths[valid]).tolist())
    return dict(edgeStretch99=float(np.percentile(ratios,99)),edgeStretchMax=float(max(ratios)))

def main():
    before,after=Model(sys.argv[1]),Model(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:
        assert before.g[key]==after.g[key],key+' changed'
    if '--love-corrected' in sys.argv[4:]:
        assert [a for a in before.g['animations'][:203] if a['name']!='SIGN_LOVE']==[a for a in after.g['animations'][:203] if a['name']!='SIGN_LOVE']
        assert before.g['animations'][203:]==after.g['animations'][203:], 'Alphabet actions changed'
        assert before.binary[:before.g['buffers'][0]['byteLength']]==after.binary[:before.g['buffers'][0]['byteLength']], 'Preserved source bytes changed'
    else:
        assert before.g['animations'][:203]==after.g['animations'][:203], 'Word actions changed'
    first_letter_accessor=before.g['animations'][203]['samplers'][0]['input']
    original_end=before.g['bufferViews'][before.g['accessors'][first_letter_accessor]['bufferView']]['byteOffset']
    assert before.binary[:original_end]==after.binary[:original_end], 'Original mesh/word bytes changed'
    names=[f'SIGN_LETTER_{c}_WOLF3D_PREVIEW' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    names += [n for n in ['SIGN_LOVE','SIGN_HELLO','SIGN_BEAUTIFUL','SIGN_THANKS','SIGN_HELP','SIGN_YES','SIGN_NO'] if n in after.animations]
    report=dict(bindMatrixError=after.bind_error,weightSumError=after.weight_error,actions=[],qualifiedASLValidation=False,renderer='CPU glTF skinning, not Android/WebGL')
    assert after.bind_error<1e-5 and after.weight_error<1e-5
    for side in ['Right','Left']:
        for axes,label in [((0,1),'front'),((2,1),'side')]:
            image=Image.new('RGB',(880,len(names)*270),'#eef2f2');draw=ImageDraw.Draw(image)
            for row,name in enumerate(names):
                metrics=[]
                for column,model in enumerate([before,after]):
                    tracks=model.tracks(name);duration=max(max(c['times']) for c in tracks)
                    for c in tracks:
                        assert np.isfinite(c['values']).all()
                        if c['path']=='rotation':assert np.max(np.abs(np.linalg.norm(c['values'],axis=1)-1))<1e-5
                    pose=model.pose(tracks,duration*.5)
                    cell=(column*440,row*270)
                    metrics.append(render(draw,model,pose,side,cell,axes))
                    render(draw,model,pose,side,(cell[0]+220,cell[1]),axes,bones=True)
                    draw.text((cell[0]+8,cell[1]+6),('BEFORE ' if column==0 else 'AFTER ')+name.replace('SIGN_LETTER_','').replace('_WOLF3D_PREVIEW',''),fill='black')
                if side=='Right' and label=='front':
                    report['actions'].append(dict(name=name,before=metrics[0],after=metrics[1]))
                    if name.startswith('SIGN_LETTER_'):
                        # Regression bound for THESE asset/pose fixtures, not a generic
                        # anatomical rotation clamp or a linguistic accuracy score.
                        # The faulty distal calibration exceeds this for all 26 letters.
                        assert metrics[1]['edgeStretch99']<1.70, name+' distal skin regression'
            image.save(out/f'{side.lower()}-{label}-before-after.png')
    # Motion samples, not a still-pose claim for moving letters.
    for letter in 'JZ':
        name=f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW';tracks=after.tracks(name);duration=max(max(c['times']) for c in tracks)
        image=Image.new('RGB',(9*220,270),'#eef2f2');draw=ImageDraw.Draw(image);positions=[]
        for i,t in enumerate(np.linspace(.25,duration-.25,9)):
            w=after.pose(tracks,float(t));render(draw,after,w,'Right',(i*220,0),bones=True)
            positions.append(w[after.names['RightHand']][:3,3].tolist());draw.text((i*220+8,8),f'{letter} t={t:.2f}',fill='black')
        image.save(out/f'{letter}-motion.png')
        report[letter+'WristSpan']=np.ptp(positions,axis=0).tolist()
        assert max(report[letter+'WristSpan'])>.01
    (out/'hand-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(actions=len(names),bindMatrixError=after.bind_error,weightSumError=after.weight_error,output=str(out)),indent=2))

if __name__=='__main__':main()
