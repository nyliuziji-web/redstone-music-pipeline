import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from redstone_music import core
from redstone_music.media_tools import inspect_media, clip_media, capture_evidence


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg tools not available')
class MediaTests(unittest.TestCase):
    def setUp(self):
        root=core.REPO_ROOT/'.runtime';root.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='media_',dir=root)
        self.root=Path(self.tmp.name)
        self.media=self.root/'test.mp4'
        subprocess.run([shutil.which('ffmpeg'),'-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=160x90:r=20:d=2',
                        '-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p',
                        '-c:a','aac','-shortest',str(self.media)],check=True,capture_output=True)

    def tearDown(self):self.tmp.cleanup()

    def test_decoded_media_and_clip_are_real_without_approval(self):
        media=inspect_media(self.media)
        self.assertTrue(media['hasVideo'] and media['hasAudio'])
        self.assertEqual(media['sha256'],core.hash_file(self.media))
        clip=clip_media(self.media,self.root/'clip.mp4',.5,1.5)
        self.assertAlmostEqual(clip['durationSeconds'],1,delta=.12)
        self.assertEqual(clip['sourceSha256'],media['sha256'])
        self.assertFalse(clip['actualGameSourceVerified'])
        with self.assertRaises(ValueError):clip_media(self.media,self.root/'clip.mp4',0,1)

    def test_capture_manifest_does_not_certify_game_or_user_review(self):
        project=self.root/'song';core.initialize(project)
        evidence=capture_evidence(project,self.media,project/'evidence/capture.json')
        self.assertEqual(evidence['status'],'media_inspected')
        self.assertEqual(evidence['userReview'],'not_performed')
        self.assertEqual(evidence['candidateBindings'],[])
        self.assertFalse(evidence['media']['artisticPassGranted'])
        with self.assertRaises(ValueError):capture_evidence(project,self.media,self.root/'outside.json')
        with self.assertRaises(ValueError):clip_media(self.media,self.root/'bad.mp4',1,5)


if __name__=='__main__':unittest.main()
