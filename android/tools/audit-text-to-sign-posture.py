"""Check all alphabet signing spans against their actual source and render sequences."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image,ImageDraw

spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-text-to-sign-contact.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a);c=a.c

def main():
    before=c.hands.Model(sys.argv[1]);after=c.hands.Model(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path(sys.argv[2]).with_suffix('.json').read_text())
    for key in ['nodes','skins','meshes','materials','textures','images','scenes']:assert before.g[key]==after.g[key]
    assert [x for x in before.g['animations'] if not x['name'].startswith('SIGN_LETTER_')]==[
        x for x in after.g['animations'] if not x['name'].startswith('SIGN_LETTER_') and x['name']!='SIGN_RELAXED_NEUTRAL']
    assert before.binary[:before.g['buffers'][0]['byteLength']]==after.binary[:before.g['buffers'][0]['byteLength']]
    report=dict(renderer='CPU skinning, not Android or qualified ASL review',letters=[],wordActionsUnchanged=203)
    for entry in manifest['signingPosture']['letters']:
        letter=entry['letter'];name=f'SIGN_LETTER_{letter.upper()}_WOLF3D_PREVIEW'
        tracks=after.tracks(name);oldtracks=before.tracks(name);span=entry['sourceEndSeconds']-.5
        max_error=0.;wrist=[];shoulders=[]
        for t in np.linspace(0,span,21):
            old=c.pose(before,oldtracks,float(t)+.5);new=c.pose(after,tracks,float(t))
            max_error=max(max_error,max(float(np.max(np.abs(old[n]-new[n]))) for n in old))
            wrist.append(new[after.names['RightHand']][:3,3]);shoulders.append(new[after.names['RightShoulder']])
        assert max_error<1e-5,(letter,max_error)
        shoulder_error=max(float(np.max(np.abs(x-shoulders[0]))) for x in shoulders)
        assert shoulder_error<1e-6
        motion=np.ptp(wrist,axis=0).tolist()
        if letter in 'jz':assert max(motion)>.01, 'Moving letter lost motion'
        report['letters'].append(dict(letter=letter,sourcePoseError=max_error,shoulderMatrixSpan=shoulder_error,wristMotionSpan=motion))
    oldmesh=c.ContactMesh(before);newmesh=c.ContactMesh(after)
    for word in ['A','B','J','Z','NAME','NICOLE','ANNA','JAZZ']:
        # Same front/side view, compare late-letter poses where the old clips
        # lower their arms. This is rendered source geometry, not screenshots.
        for angle,label in [(0,'front'),(75,'side')]:
            image=Image.new('RGB',(360*len(word),1200),'#dde3e4');draw=ImageDraw.Draw(image)
            for i,letter in enumerate(word):
                name=f'SIGN_LETTER_{letter}_WOLF3D_PREVIEW'
                for row,(model,mesh,title) in enumerate([(before,oldmesh,'BEFORE'),(after,newmesh,'AFTER')]):
                    tracks=model.tracks(name);duration=max(max(t['times']) for t in tracks)
                    panel=Image.new('RGB',(360,600),'#dde3e4');panel_draw=ImageDraw.Draw(panel)
                    a.render(model,mesh,c.pose(model,tracks,float(duration*.94)),panel_draw,(0,0),angle,word+' '+letter+' '+title)
                    image.paste(panel,(i*360,row*600))
            image.save(out/f'{word.lower()}-{label}.png')
    (out/'posture-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(letters=len(report['letters']),maxSourcePoseError=max(e['sourcePoseError'] for e in report['letters']),maxShoulderSpan=max(e['shoulderMatrixSpan'] for e in report['letters']),wordActionsUnchanged=203),indent=2))

if __name__=='__main__':main()
