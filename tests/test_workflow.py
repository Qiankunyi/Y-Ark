import json
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from creatorsave.engine import verify, embed_cover, deliver, download, Cancelled
from creatorsave.core import History, import_candidates

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent / '.tmp')
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_collision_never_overwrites(self):
        source=self.root/'source'; target=self.root/'target'; source.mkdir(); target.mkdir()
        a=source/'video.mp4'; a.write_bytes(b'new'); (target/a.name).write_bytes(b'old')
        with self.assertRaises(FileExistsError): deliver([a],target)
        self.assertEqual((target/a.name).read_bytes(),b'old')
    def test_failed_delivery_rolls_back(self):
        source=self.root/'source'; target=self.root/'target'; source.mkdir(); target.mkdir()
        a=source/'a'; a.write_bytes(b'first'); b=source/'missing'
        with self.assertRaises(FileNotFoundError): deliver([a,b],target)
        self.assertEqual(list(target.iterdir()),[])
        self.assertTrue(a.exists())
    def test_readonly_import_nonrecursive(self):
        (self.root/'test [TestVideo02].mp4').write_bytes(b'x')
        sub=self.root/'sub'; sub.mkdir(); (sub/'test [TestVideo03].mp4').touch()
        self.assertEqual(list(import_candidates(self.root)),['TestVideo02'])
    def test_task_recovery(self):
        history=History(self.root/'history.db')
        task=history.create_task('TestVideo02','url','folder','best')
        history.update_task(task,'merging')
        self.assertEqual(history.tasks()[0][5],'interrupted'); history.db.close()
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Requires ffmpeg')
    def test_media_pipeline(self):
        source=self.root/'fixture.mp4'; cover=self.root/'fixture.jpg'
        def ffmpeg(args):
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args],check=True,capture_output=True)
        ffmpeg(['-f','lavfi','-i','color=c=blue:s=160x90:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(source)])
        ffmpeg(['-f','lavfi','-i','color=c=red:s=160x90','-frames:v','1',str(cover)])
        verify(source)
        self.assertTrue(embed_cover(source,cover))
        self.assertTrue(any(s.get('disposition',{}).get('attached_pic') for s in verify(source)['streams']))
        class FakeYDL:
            def __init__(inner,opts): inner.opts=opts
            def __enter__(inner): return inner
            def __exit__(inner,*args): pass
            def extract_info(inner,url,download):
                work=Path(inner.opts['paths']['home']); base=work/'2026-01-01 中文.title [TestVideo02]'
                shutil.copy2(source,Path(str(base)+'.mp4')); shutil.copy2(cover,Path(str(base)+'.jpg'))
                inner.path=Path(str(base)+'.mp4')
                return dict(id='TestVideo02',channel_id='UC-fixture',title='中文.title',ext='mp4')
            def prepare_filename(inner,info): return str(inner.path)
        output=self.root/'outputs'
        with patch.dict('sys.modules',{'yt_dlp':types.SimpleNamespace(YoutubeDL=FakeYDL)}):
            result=download('https://youtu.be/TestVideo02',output,'best','',lambda e:None,lambda:False)
        self.assertTrue(Path(result['path']).is_file())
        meta=json.loads(next(output.glob('*.info.json')).read_text(encoding='utf-8'))
        self.assertEqual(meta['channel_id'],'UC-fixture')
        self.assertEqual(len(list(output.glob('*.jpg'))),1)
        self.assertTrue(list((output/'.creatorsave').rglob('*.mp4')))
        # Audio-less inputs must never pass as success.
        silent=self.root/'silent.mp4'
        ffmpeg(['-f','lavfi','-i','color=c=black:s=160x90:d=1','-c:v','libx264',str(silent)])
        with self.assertRaisesRegex(RuntimeError,'audio'): verify(silent)

if __name__=='__main__': unittest.main()
