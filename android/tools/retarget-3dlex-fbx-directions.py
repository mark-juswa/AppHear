"""Candidate-only direction-preserving anatomical retarget; never edits installed assets."""
import numpy as np

def align_swing(a,b):
    a=np.array(a,dtype=float,copy=True);a/=np.linalg.norm(a);b=np.array(b,dtype=float,copy=True);b/=np.linalg.norm(b)
    dot=float(np.clip(a@b,-1,1));assert dot>-.99999,'Ambiguous antiparallel source/target bone'
    v=np.cross(a,b);k=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return np.eye(3)+k+(k@k)/(1+dot),float(np.degrees(np.arccos(dot)))

def convert(converter,scene,H,body_frame):
    R=H.r;m=converter.m;initial=scene.pose(0);alignment=converter.neutral_body@body_frame(initial,scene.names).T
    bind=R.world(scene.calibration_nodes,scene.parents,scene.order)
    correction={name:R.orient(bind[scene.names[name]]).T@converter.frame(bind,scene.names,name,child)@converter.target_frame[name].T@R.orient(converter.rest[m.names[name]]) for name,child in converter.pairs.items()}
    times=np.linspace(0,scene.duration,max(3,int(np.ceil(scene.duration*24))+1));frames=[];wrists=[];max_error=0.;max_swing=0.
    for time_sec in times:
        sw=scene.pose(float(time_sec));desired={};wanted_directions={}
        for name,child in converter.pairs.items():
            direction=R.unit(alignment@(sw[scene.names[child]][:3,3]-sw[scene.names[name]][:3,3]))
            rotation=alignment@R.orient(sw[scene.names[name]])@correction[name]
            local=np.asarray(m.nodes[m.names[child]].get('translation',[0,0,0]))*np.asarray(m.nodes[m.names[name]].get('scale',[1,1,1]))
            swing,angle=align_swing(rotation@local,direction);max_swing=max(max_swing,angle)
            assert angle<=10.0,'Source articulation needs more than 10 degrees of swing adaptation; review required'
            desired[m.names[name]]=swing@rotation;wanted_directions[name]=direction
        current={};out={}
        for i in m.order:
            node=m.nodes[i];parent=current.get(m.parents.get(i),np.eye(4));q=converter.neutral.get((i,'rotation'),node.get('rotation',[0,0,0,1]))
            if i in desired:q=R.quaternion(R.orient(parent).T@desired[i])
            out[(i,'rotation')]=np.asarray(q);local=np.eye(4);local[:3,:3]=R.rotation(q)@np.diag(node.get('scale',[1,1,1]));local[:3,3]=node.get('translation',[0,0,0])
            if 'matrix' in node:local=np.array(node['matrix']).reshape(4,4,order='F')
            current[i]=parent@local
        for name,child in converter.pairs.items():
            got=R.unit(current[m.names[child]][:3,3]-current[m.names[name]][:3,3]);max_error=max(max_error,float(np.linalg.norm(got-wanted_directions[name])))
        assert all(np.isfinite(q).all() for q in out.values());wrists.append(np.r_[current[m.names['LeftHand']][:3,3],current[m.names['RightHand']][:3,3]]);frames.append(out)
    assert max_error<1e-5,('Independent source direction check failed',max_error)
    inner=np.asarray([[f[(i,'rotation')] for i in m.order] for f in frames]);steps=2*np.arccos(np.clip(abs(np.sum(inner[:-1]*inner[1:],axis=2)),0,1));max_step=float(np.degrees(steps.max()));assert max_step<90,('Abrupt source/retarget rotation exceeds 90 degrees per 24 Hz frame',max_step)
    span=float(np.ptp(wrists,axis=0).max());finger_variation=max(float(np.max(np.linalg.norm(np.asarray([f[(i,'rotation')] for f in frames])-frames[0][(i,'rotation')],axis=1))) for name,i in m.names.items() if 'Hand' in name and not name.endswith('4'))
    assert span>.015 or finger_variation>.12,'Static/placeholder source motion'
    neutral={(i,'rotation'):np.asarray(converter.neutral.get((i,'rotation'),m.nodes[i].get('rotation',[0,0,0,1]))) for i in m.order}
    return np.r_[0.,times+.2,scene.duration+.4].astype('<f4'),[neutral]+frames+[neutral],dict(source_full_duration_seconds=scene.full_duration,retained_source_duration_seconds=scene.duration,excluded_export_reset=scene.excluded_reset,sampled_source_frames=len(times),max_direction_error=max_error,max_minimal_swing_adaptation_degrees=max_swing,max_inner_rotation_step_degrees=max_step,wrist_span_m=span,finger_rotation_variation=finger_variation,source_translations='Source bone directions preserved; fixed target lengths; minimally adapted source orientation; no handshape clamp',facial_blendshapes='Not provided by this source; not invented')
