"""Negative and positive export-boundary tests; not linguistic validation."""
import copy,importlib.util,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

def module(name,file):
    s=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
e=module('expansion','expand-3dlex-vocabulary.py');h=module('hands','audit-text-to-sign-hands.py')

class Scene:
    def __init__(self,angles=(170,170,0),finger_end=0,step=1/24):
        self.nodes=[dict(name='Hips',children=[1]),dict(name='Finger',translation=[0,1,0])]
        self.names={'Hips':0,'Finger':1};self.parents,self.order=h.r.skeleton(self.nodes)
        self.duration=step*2;self.excluded_reset=None
        def q(degrees):return [0,float(np.sin(np.radians(degrees)/2)),0,float(np.cos(np.radians(degrees)/2))]
        self.tracks=[dict(node=0,path='rotation',times=[0,step,step*2],values=[q(a) for a in angles],interpolation='LINEAR'),
            dict(node=1,path='rotation',times=[0,step,step*2],values=[q(0),q(0),q(finger_end)],interpolation='LINEAR')]
    def pose(self,t):
        return h.r.world(self.nodes,self.parents,self.order,{(c['node'],c['path']):h.r.sample(c,t) for c in self.tracks})

class ExportResetTest(unittest.TestCase):
    def partial_reset(self,finger_end=1,signature=True):
        s=Scene(angles=(170,170,5),finger_end=finger_end)
        s.nodes.append(dict(name='Armature',children=[0]))
        s.names['Armature']=2;s.parents,s.order=h.r.skeleton(s.nodes)
        canonical=[.6898379325866699,0,0,.7239638566970825] if signature else [.7,0,0,.71414284]
        s.tracks.append(dict(node=2,path='rotation',times=[0,1/24,2/24],
            values=[[0,0,0,1],[0,0,0,1],canonical],interpolation='LINEAR'))
        return s
    def test_exact_publisher_partial_reset_signature_is_excluded(self):
        s=self.partial_reset();tracks=copy.deepcopy(s.tracks);e.exclude_terminal_hip_reset(s,h)
        self.assertAlmostEqual(s.duration,1/24);self.assertEqual(tracks,s.tracks)
        self.assertEqual('PARTIALLY_BAKED_CONTAINER_RESET',s.excluded_reset['terminalHipReset']['signature'])
    def test_partial_reset_never_discards_a_sign_specific_handshape(self):
        s=self.partial_reset(finger_end=70);e.exclude_terminal_hip_reset(s,h)
        self.assertIsNone(s.excluded_reset)
    def test_nonmatching_container_turn_is_not_an_export_reset(self):
        s=self.partial_reset(signature=False);e.exclude_terminal_hip_reset(s,h)
        self.assertIsNone(s.excluded_reset)
    def test_only_terminal_global_bind_reset_is_excluded(self):
        s=Scene();tracks=copy.deepcopy(s.tracks);e.exclude_terminal_hip_reset(s,h)
        self.assertAlmostEqual(s.duration,1/24);self.assertEqual(tracks,s.tracks)
        self.assertTrue(s.excluded_reset['sourceBytesUnchanged'])
    def test_natural_return_to_rest_is_retained(self):
        s=Scene(angles=(20,20,0));e.exclude_terminal_hip_reset(s,h)
        self.assertAlmostEqual(s.duration,2/24);self.assertIsNone(s.excluded_reset)
    def test_sign_specific_finger_pose_prevents_bind_reset_classification(self):
        s=Scene(finger_end=70);e.exclude_terminal_hip_reset(s,h)
        self.assertIsNone(s.excluded_reset)
    def test_interior_movement_and_slow_turn_are_never_trimmed(self):
        for s in [Scene(angles=(170,0,0)),Scene(step=.2)]:
            old=s.duration;e.exclude_terminal_hip_reset(s,h);self.assertEqual(old,s.duration)
if __name__=='__main__':unittest.main()
