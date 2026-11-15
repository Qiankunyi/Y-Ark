import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from creatorsave.core import History
from creatorsave.engine import (download,prepare_video,embed_cover,cover_matches,has_embedded_cover,
    verify,export_video_file,export_audio_file)
from creatorsave.profiles import OutputProfile

@unittest.skipUnless(shutil.which('ffmpeg'),'Requires FFmpeg')
class OutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp');cls.root=Path(cls.temp.name)
        cls.cover=cls.root/'cover.jpg';cls.other=cls.root/'other.jpg'
        cls.ffmpeg(['-f','lavfi','-i','color=c=blue:s=320x180','-frames:v','1',str(cls.cover)])
        cls.ffmpeg(['-f','lavfi','-i','color=c=red:s=320x180','-frames:v','1',str(cls.other)])
        cls.sources={}
        for name,video,audio in (('h264','libx264','aac'),('vp9','libvpx-vp9','libopus'),('av1','libaom-av1','libopus')):
            path=cls.root/(name+'.mkv');args=['-f','lavfi','-i','color=c=black:s=256x144:r=4:d=0.5','-f','lavfi','-i','sine=duration=0.5','-c:v',video]
            if name=='h264':args+=['-preset','ultrafast']
            else:args+=['-cpu-used','8']
            cls.ffmpeg([*args,'-c:a',audio,'-shortest',str(path)]);cls.sources[name]=path
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    @staticmethod
    def ffmpeg(args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args],capture_output=True,check=True)
    def fake_downloader(self,source):
        cover=self.cover
        class FakeYDL:
            def __init__(inner,options):inner.options=options
            def __enter__(inner):return inner
            def __exit__(inner,*args):pass
            def extract_info(inner,url,download):
                inner.path=Path(inner.options['paths']['home'])/'sample [TestVideo02].mkv'
                shutil.copy2(source,inner.path);shutil.copy2(cover,inner.path.with_suffix('.jpg'))
                return dict(id='TestVideo02',title='Sample',channel_id='UC-test',ext='mkv')
            def prepare_filename(inner,info):return str(inner.path)
        return types.SimpleNamespace(YoutubeDL=FakeYDL)
    def test_quality_container_codec_matrix_has_exact_cover(self):
        for codec,source in self.sources.items():
            for quality in ('best','1080','720'):
                for container in ('mp4','mkv'):
                    with self.subTest(codec=codec,quality=quality,container=container),patch.dict('sys.modules',{'yt_dlp':self.fake_downloader(source)}):
                        folder=self.root/(codec+'-'+quality+'-'+container)
                        result=download('https://youtu.be/TestVideo02',folder,quality,'',lambda event:None,lambda:False,video_format=container)
                        media=Path(result['path']);self.assertEqual(media.suffix,'.'+container)
                        self.assertTrue(cover_matches(media,self.cover));self.assertTrue(result['cover_verified'])
                        info=verify(media);video=next(s for s in info['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
                        self.assertEqual(video['codec_name'],{'h264':'h264','vp9':'vp9','av1':'av1'}[codec]);self.assertEqual(video['height'],144)
                        meta=json.loads(media.with_suffix('.info.json').read_text(encoding='utf-8'))
                        self.assertEqual(meta['ext'],container);self.assertEqual(meta['output_profile'],OutputProfile(quality,container).to_dict())
    def test_selected_height_limit_is_verified_before_delivery(self):
        source=self.root/'too-tall.mkv'
        self.ffmpeg(['-f','lavfi','-i','color=c=black:s=160x900:r=2:d=0.5','-f','lavfi','-i','sine=duration=0.5','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',str(source)])
        folder=self.root/'height-limit'
        with patch.dict('sys.modules',{'yt_dlp':self.fake_downloader(source)}):
            with self.assertRaisesRegex(RuntimeError,'resolution exceeds'):
                download('https://youtu.be/TestVideo02',folder,'720','',lambda event:None,lambda:False,video_format='mp4')
        self.assertFalse(list(folder.glob('*.mp4')))
        self.assertTrue(list((folder/'.creatorsave').rglob('*.mkv')))
    def test_wrong_existing_picture_is_replaced_for_both_formats(self):
        for container in ('mp4','mkv'):
            folder=self.root/('replace-'+container);folder.mkdir()
            source=folder/'sample.mkv';shutil.copy2(self.sources['h264'],source)
            media=prepare_video(source,container)
            embed_cover(media,self.other)
            self.assertFalse(cover_matches(media,self.cover))
            embed_cover(media,self.cover)
            self.assertTrue(cover_matches(media,self.cover));self.assertFalse(cover_matches(media,self.other))
    def test_unrelated_mkv_attachment_is_not_a_cover(self):
        text=self.root/'notes.txt';text.write_text('not an image')
        media=self.root/'attachment.mkv'
        self.ffmpeg(['-i',str(self.sources['h264']),'-map','0','-c','copy','-attach',str(text),'-metadata:s:t:0','mimetype=text/plain',str(media)])
        self.assertFalse(has_embedded_cover(media))
    def test_no_silent_container_fallback_on_mux_failure(self):
        with patch('creatorsave.engine.run_ffmpeg',side_effect=RuntimeError('unsupported codec')):
            with self.assertRaisesRegex(RuntimeError,'Selected MP4'):prepare_video(self.sources['vp9'],'mp4')
        self.assertFalse(self.sources['vp9'].with_suffix('.mp4').exists())
    def test_local_video_preserves_source_and_avoids_download(self):
        folder=self.root/'local-video';folder.mkdir();source=folder/'sample [TestVideo02].mkv'
        shutil.copy2(self.sources['av1'],source);shutil.copy2(self.cover,source.with_suffix('.jpg'))
        previous=hashlib.sha256(source.read_bytes()).hexdigest()
        result=export_video_file(source,folder,'mp4')
        self.assertEqual(Path(result['path']).name,'sample (MP4) [TestVideo02].mp4')
        self.assertTrue(cover_matches(result['path'],self.cover))
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),previous)
    def test_missing_cover_does_not_produce_successful_audio(self):
        folder=self.root/'no-cover';folder.mkdir();source=folder/'plain.m4a'
        self.ffmpeg(['-f','lavfi','-i','sine=duration=0.2','-c:a','aac',str(source)])
        with self.assertRaisesRegex(RuntimeError,'cover'):export_audio_file(source,folder)
        self.assertFalse(list(folder.glob('*.mp3')))

class TaskProfileMigrationTests(unittest.TestCase):
    def test_legacy_rows_and_new_options_survive_reopen(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp') as folder:
            path=Path(folder)/'db.sqlite3';db=sqlite3.connect(path)
            db.execute('CREATE TABLE tasks(id INTEGER PRIMARY KEY,video_id TEXT,url TEXT,folder TEXT,preset TEXT,state TEXT,detail TEXT)')
            db.execute("INSERT INTO tasks VALUES(1,'TestVideo02','url','folder','1080','completed','legacy')");db.commit();db.close()
            history=History(path);self.assertEqual(history.tasks()[0][5],'completed');self.assertEqual(history.task_options(1),{})
            task=history.create_task('TestVideo03','url','folder','720',{'video_format':'mkv'});history.db.close()
            restored=History(path);self.assertEqual(restored.task_options(task),{'video_format':'mkv'});restored.db.close()
