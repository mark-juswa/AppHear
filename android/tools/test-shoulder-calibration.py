"""Geometry regression tests: no guessed ASL poses or generic finger constraints."""
import importlib.util,unittest
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('correction',Path(__file__).with_name('correct-imported-shoulder-baselines.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)

class ShoulderCalibrationTest(unittest.TestCase):
    def test_elbow_preserves_both_segment_lengths_and_bend_side(self):
        start=np.array([.04,1.4,0]);target=np.array([.2,1.0,.1]);pole=np.array([.3,1.3,.2])
        e=c.elbow_position(start,target,pole,.3,.28)
        self.assertAlmostEqual(.3,float(np.linalg.norm(e-start)),places=10)
        self.assertAlmostEqual(.28,float(np.linalg.norm(e-target)),places=10)
        axis=(target-start)/np.linalg.norm(target-start)
        self.assertGreater(float((e-start-axis*((e-start)@axis))@(pole-start)),0)
    def test_unreachable_wrist_is_rejected_instead_of_pushing_the_hand(self):
        with self.assertRaisesRegex(ValueError,'unreachable'):
            c.elbow_position(np.zeros(3),np.array([2.,0,0]),np.array([0,1.,0]),.3,.3)
    def test_bend_ambiguity_is_rejected_instead_of_twisting_the_arm(self):
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            c.elbow_position(np.zeros(3),np.array([.4,0,0]),np.array([.2,0,0]),.3,.3)
    def test_swing_preserves_a_rigid_orientation_and_target_direction(self):
        a=np.array([0.,1,0]);b=np.array([1.,1,1]);rotation=c.swing(a,b)
        np.testing.assert_allclose(rotation@a,b/np.linalg.norm(b),atol=1e-12)
        np.testing.assert_allclose(rotation.T@rotation,np.eye(3),atol=1e-12)
        self.assertAlmostEqual(1,float(np.linalg.det(rotation)),places=12)
    def test_antiparallel_segment_is_not_resolved_with_an_arbitrary_twist(self):
        with self.assertRaisesRegex(ValueError,'Antiparallel'):
            c.swing(np.array([1.,0,0]),np.array([-1.,0,0]))

if __name__=='__main__':unittest.main()
