"""Apply an independently verified stage to its exact checkpoint only."""
import argparse,hashlib,importlib.util,json,re
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def encode(v):return (json.dumps(v,indent=2,ensure_ascii=True)+'\n').encode('utf-8')
def replace(path,pattern,value):
    text=path.read_text(encoding='utf-8');text,n=re.subn(pattern,value,text);assert n==1
    path.write_text(text,encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('staged',type=Path);a=p.parse_args()
    android=Path(__file__).resolve().parents[1];folder=android/'app/src/aslOriginalWords/assets/asl_animations/original_words_v1'
    report=json.loads((a.staged/'report.json').read_text(encoding='utf-8'))
    checks=json.loads((a.staged/'verification.json').read_text(encoding='utf-8'))
    assert checks['status']=='PASS' and report['selectedCount']==485
    assert len(report['changed'])==465 and len(report['skipped'])==20
    before=(folder/'fingerspelling-avatar.glb').read_bytes();after=(a.staged/'avatar.glb').read_bytes()
    assert sha(before)==report['baselineSha256'] and sha(after)==report['sha256']
    m=json.loads((folder/'integration-manifest.json').read_text(encoding='utf-8'))
    f=json.loads((folder/'fingerspelling-avatar.json').read_text(encoding='utf-8'))
    assert m['sha256']==f['sha256']==sha(before) and m['totalLexicalEntries']==743 and m['totalActions']==821
    correction=dict(version=1,baselineBundleSha256=sha(before),correctedBundleSha256=sha(after),
        method=report['correction'],affectedBoneNames=[s+n for s in ['Left','Right'] for n in ['Shoulder','Arm','ForeArm','Hand']],
        changedIds=[e['id'] for e in report['changed']],preservedPrerollExceptions=report['skipped'],
        handAndFingerPoseVerification=checks,sourceRetargetMotionHashesPreserved=True,
        qualifiedAslValidations=0,notes='Original per-entry motionSha256 identifies the raw retarget stage; this postprocess is separately pinned by the corrected bundle hash. See shoulder repair report for Android evidence.')
    m['shoulderCalibration']=correction;f['shoulderCalibration']=correction
    m['sha256']=f['sha256']=sha(after);manifest=encode(m)
    (folder/'fingerspelling-avatar.glb').write_bytes(after)
    (folder/'integration-manifest.json').write_bytes(manifest)
    (folder/'fingerspelling-avatar.json').write_bytes(encode(f))
    domain=android/'app/src/main/java/com/example/apphear/domain/texttoasl'
    replace(domain/'AslFingerspellingBundle.kt',r'const val SHA256 = "[a-f0-9]+"',f'const val SHA256 = "{sha(after)}"')
    replace(domain/'AslIntegratedVocabulary.kt',r'const val MANIFEST_SHA256 = "[a-f0-9]+"',f'const val MANIFEST_SHA256 = "{sha(manifest)}"')
    print(json.dumps(dict(entries=743,actions=821,changed=465,retainedOriginalExceptions=20,sha256=sha(after),manifestSha256=sha(manifest))))
if __name__=='__main__':main()
