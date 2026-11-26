import unittest

from redstone_music.camera_rail import camera_target, check_camera_clearance, compile_camera_rail


class CameraRailTests(unittest.TestCase):
    def test_keyframes_keep_physical_z_clock_and_require_route_clearance(self):
        camera = {'x':37.5, 'eyeY':113, 'targetLeadBlocks':2, 'keyframes':[
            {'atGT':-20, 'x':32, 'eyeY':111, 'yaw':7, 'pitch':0},
            {'atGT':20, 'x':40, 'eyeY':115, 'yaw':-7, 'pitch':4},
            {'atGT':60, 'x':36, 'eyeY':111, 'yaw':0, 'pitch':0},
        ]}
        compile_camera_rail(camera,40)
        self.assertEqual(camera_target(camera,0),(36,113,70.5))
        self.assertEqual(camera['rail']['frames'][20],[36,113,0,2])
        check_camera_clearance(camera,[{'x':37,'y':108,'z':71,'state':'minecraft:stone'}])
        with self.assertRaisesRegex(ValueError,'Camera clearance conflict'):
            check_camera_clearance(camera,[{'x':36,'y':113,'z':71,'state':'minecraft:stone'}])

    def test_route_cannot_omit_preroll(self):
        camera = {'keyframes':[
            {'atGT':0, 'x':32, 'eyeY':111, 'yaw':7, 'pitch':0},
            {'atGT':60, 'x':36, 'eyeY':111, 'yaw':0, 'pitch':0},
        ]}
        with self.assertRaisesRegex(ValueError,'cover -20'):
            compile_camera_rail(camera,40)
