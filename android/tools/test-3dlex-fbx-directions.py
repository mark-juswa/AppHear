"""Mechanical orientation tests; these do not certify ASL handshapes."""
import importlib.util, unittest
from pathlib import Path
import numpy as np
p=Path(__file__).with_name('retarget-3dlex-fbx-directions.py')
s=importlib.util.spec_from_file_location('directional',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class DirectionTests(unittest.TestCase):
    def test_maps_directions_without_scale_reflection_or_input_mutation(self):
        rng=np.random.default_rng(20261025)
        for _ in range(100):
            a=rng.normal(size=3);b=rng.normal(size=3);aa=a.copy();bb=b.copy()
            R,angle=m.align_swing(a,b)
            np.testing.assert_allclose(R@(a/np.linalg.norm(a)),b/np.linalg.norm(b),atol=1e-12)
            np.testing.assert_allclose(R.T@R,np.eye(3),atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(R),1.,places=12)
            np.testing.assert_array_equal(a,aa);np.testing.assert_array_equal(b,bb)
    def test_parallel_directions_preserve_transferred_twist(self):
        R,angle=m.align_swing([0,0,2],[0,0,3])
        np.testing.assert_allclose(R,np.eye(3),atol=1e-15);self.assertEqual(angle,0.)
    def test_antiparallel_frame_is_rejected_instead_of_guessing_twist(self):
        with self.assertRaises(AssertionError):m.align_swing([1,0,0],[-1,0,0])
    def test_quarter_turn_does_not_add_rotation_around_direction(self):
        R,angle=m.align_swing([1,0,0],[0,1,0])
        np.testing.assert_allclose(R,[[0,-1,0],[1,0,0],[0,0,1]],atol=1e-15)
        self.assertAlmostEqual(angle,90.)
if __name__=='__main__':unittest.main()
