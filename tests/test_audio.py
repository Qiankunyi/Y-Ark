import hashlib
import json
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from mutagen.id3 import ID3
from creatorsave.engine import (prepare_audio,embed_cover,has_embedded_cover,verify,download,export_audio_file,Cancelled)

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'Requires FFmpeg')
class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp');self.root=Path(self.temp.name)
        self.source=self.root/'2026-01-01 sample [TestVideo01].webm';self.cover=self.source.with_suffix('.jpg')
        self.ffmpeg(['-f','lavfi','-i','sine=frequency=440:duration=1','-c:a','libopus',str(self.source)])
        self.ffmpeg(['-f','lavfi','-i','color=c=blue:s=160x90','-frames:v','1',str(self.cover)])
        self.original_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
    def tearDown(self):self.temp.cleanup()
    def ffmpeg(self,args):return subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args],capture_output=True,check=True)
    def assert_source_unchanged(self):self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.original_hash)
    def packet_hashes(self,path):
        raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_packets','-show_data_hash','sha256','-show_entries','packet=data_hash','-of','json',str(path)])
        return [packet['data_hash'] for packet in json.loads(raw)['packets']]
    def test_original_opus_preserves_audio_and_embeds_cover(self):
        target=prepare_audio(self.source)
        self.assertEqual(target.suffix,'.opus')
        self.assertTrue(embed_cover(target,self.cover,True))
        self.assertTrue(has_embedded_cover(target))
        verify(target,True)
        self.assertEqual(self.packet_hashes(self.source),self.packet_hashes(target))
        # Matroska millisecond timestamps and Ogg sample timestamps can round differently.
        from creatorsave.engine import probe
        self.assertLess(abs(float(probe(self.source)['format']['duration'])-float(probe(target)['format']['duration'])),0.002)
        self.assert_source_unchanged()
    def test_mp3_audio_codec_bitrate_tags_and_real_cover(self):
        target=prepare_audio(self.source,True,{'title':'中文标题','channel':'日本語作者'})
        self.assertTrue(embed_cover(target,self.cover,True))
        info=verify(target,True)
        audio=next(s for s in info['streams'] if s['codec_type']=='audio')
        self.assertEqual(audio['codec_name'],'mp3')
        self.assertEqual(int(audio['bit_rate']),320000)
        tags=ID3(target)
        self.assertEqual(tags.version[:2],(2,3))
        self.assertEqual(tags.getall('APIC')[0].data,self.cover.read_bytes())
        self.assertEqual(str(tags['TIT2']),'中文标题')
        self.assertEqual(str(tags['TPE1']),'日本語作者')
        self.assert_source_unchanged()
    def test_m4a_cover_does_not_require_video_track(self):
        source=self.root/'aac.m4a'
        self.ffmpeg(['-f','lavfi','-i','sine=duration=1','-c:a','aac',str(source)])
        self.assertTrue(embed_cover(source,self.cover,True))
        verify(source,True);self.assertTrue(has_embedded_cover(source))
    def test_cancel_and_encoder_failure_keep_source(self):
        with self.assertRaises(Cancelled):prepare_audio(self.source,True,cancelled=lambda:True)
        self.assertFalse(self.source.with_suffix('.mp3').exists());self.assert_source_unchanged()
        with patch('creatorsave.engine.run_ffmpeg',side_effect=RuntimeError('encoder failed')):
            with self.assertRaisesRegex(RuntimeError,'encoder failed'):prepare_audio(self.source,True)
        self.assert_source_unchanged()
    def fake_downloader(self):
        source=self.source;cover=self.cover
        class FakeYDL:
            def __init__(inner,opts):inner.opts=opts
            def __enter__(inner):return inner
            def __exit__(inner,*args):pass
            def extract_info(inner,url,download):
                work=Path(inner.opts['paths']['home']);tag=' (MP3)' if '(MP3)' in inner.opts['outtmpl'] else ' (Audio)'
                base=work/('2026-01-01 sample'+tag+' [TestVideo01]')
                inner.path=Path(str(base)+'.webm');shutil.copy2(source,inner.path);shutil.copy2(cover,Path(str(base)+'.jpg'))
                return dict(id='TestVideo01',title='Sample',channel='Creator',channel_id='UC-fixture',ext='webm')
            def prepare_filename(inner,info):return str(inner.path)
        return types.SimpleNamespace(YoutubeDL=FakeYDL)
    def test_download_presets_deliver_embedded_audio_and_accurate_metadata(self):
        for preset,extension,codec in (('audio','.opus','opus'),('audio_mp3','.mp3','mp3')):
            with self.subTest(preset=preset),patch.dict('sys.modules',{'yt_dlp':self.fake_downloader()}):
                folder=self.root/preset
                result=download('https://youtu.be/TestVideo01',folder,preset,'',lambda event:None,lambda:False)
                output=Path(result['path']);self.assertEqual(output.suffix,extension)
                self.assertTrue(has_embedded_cover(output));self.assertEqual(result['warnings'],[])
                data=json.loads(next(folder.glob('*.info.json')).read_text(encoding='utf-8'))
                self.assertEqual(data['ext'],extension[1:]);self.assertTrue(data['cover_embedded'])
                self.assertEqual(data['verified_audio'][0]['codec_name'],codec)
                self.assertTrue(list((folder/'.creatorsave').rglob('*.webm')))
        self.assert_source_unchanged()
    def test_cover_failure_prevents_successful_delivery(self):
        folder=self.root/'failed-cover'
        with patch.dict('sys.modules',{'yt_dlp':self.fake_downloader()}),patch('creatorsave.engine.embed_cover',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'Cover embedding'):
                download('https://youtu.be/TestVideo01',folder,'audio_mp3','',lambda event:None,lambda:False)
        self.assertFalse(list(folder.glob('*.mp3')))
        self.assertTrue(list((folder/'.creatorsave').rglob('*.webm')))
    def test_local_export_needs_no_network_and_preserves_originals(self):
        cover_hash=hashlib.sha256(self.cover.read_bytes()).hexdigest()
        result=export_audio_file(self.source,self.root)
        output=Path(result['path'])
        self.assertEqual(output.name,'2026-01-01 sample (MP3) [TestVideo01].mp3')
        self.assertEqual(result['id'],'TestVideo01');self.assertTrue(has_embedded_cover(output))
        self.assertEqual(hashlib.sha256(self.cover.read_bytes()).hexdigest(),cover_hash)
        self.assert_source_unchanged()
        with self.assertRaises(FileExistsError):export_audio_file(self.source,self.root)
        self.assert_source_unchanged()

if __name__=='__main__':unittest.main()
