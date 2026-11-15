import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QLabel,QFileDialog
    from creatorsave.app import Window
except ImportError:
    QApplication=None

@unittest.skipUnless(QApplication,'Requires installed Qt')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    @contextmanager
    def window(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp') as folder:
            window=Window(folder)
            window.show(); self.app.processEvents()
            try: yield window,Path(folder)
            finally:
                if window.path_dialog: window.path_dialog.reject()
                window.close(); self.app.processEvents()
    def test_languages_and_persistence(self):
        with self.window() as (window,folder):
            for index,label in enumerate(('加入下载队列','Add to queue','キューに追加')):
                window.language.setCurrentIndex(index); self.app.processEvents()
                self.assertEqual(window.start.text(),label)
            window.folder.setText(str(folder/'staging')); window.save_settings()
            restored=Window(folder)
            try:
                self.assertEqual(restored.language.currentIndex(),2)
                self.assertEqual(restored.folder.text(),str(folder/'staging'))
            finally:restored.close()
    def test_preview_and_queue(self):
        with self.window() as (window,folder):
            self.assertFalse(window.start.isEnabled())
            window.on_parsed(dict(id='TestVideo02',title='中文 <title>',channel='作者',channel_id='UC'+'a'*22,heights=[720,1080],duration=60,upload_date='20261101'))
            titles=[label.text() for label in window.preview_cards[0].findChildren(QLabel) if label.objectName()=='videoTitle']
            self.assertIn('中文 <title>',titles)
            self.assertTrue(window.start.isEnabled())
            task=window.history.create_task('TestVideo02','url',str(folder),'best')
            window.add_task(task,'TestVideo02','url',str(folder),'best','waiting','')
            window.on_event(task,{'state':'video','done':100,'total':None})
            self.assertNotIn('%',window.queue.item(0,3).text())
            self.assertEqual(window.queue_stack.currentWidget(),window.queue)
    def test_primary_navigation_and_creator_filter(self):
        with self.window() as (window,folder):
            self.assertTrue(window.nav_buttons[0].property('primaryNav'))
            self.assertTrue(window.nav_buttons[4].property('primaryNav'))
            self.assertFalse(bool(window.nav_buttons[2].property('primaryNav')))
            QTest.mouseClick(window.nav_buttons[4],Qt.MouseButton.LeftButton)
            self.assertEqual(window.tabs.currentIndex(),4)
            self.assertTrue(window.nav_buttons[4].isChecked())
            self.assertFalse(window.nav_buttons[0].isChecked())
            for suffix in ('a','b'):
                identity='UC'+suffix*22
                window.monitor.follow(identity,suffix)
                window.monitor.apply_feed(identity,suffix,[dict(id=suffix*11,title=suffix,published='2026-11-01')])
            window.refresh_following()
            self.assertEqual(window.discovery_table.rowCount(),2)
            window.channels_list.setCurrentRow(1)
            self.assertEqual(window.discovery_table.rowCount(),1)
    def test_language_switch_replaces_preview_and_updates_quality(self):
        with self.window() as (window,folder):
            window.on_parsed(dict(id='TestVideo02',title='Sample',channel='Creator',channel_id='UC'+'a'*22,heights=[1080]))
            previous=window.preview_cards[0]
            task=window.history.create_task('TestVideo02','url',str(folder),'best')
            window.add_task(task,'TestVideo02','url',str(folder),'best','waiting','')
            window.language.setCurrentIndex(1)
            self.assertTrue(previous.isHidden())
            self.assertEqual(window.queue.item(0,1).text(),'Best quality')
            self.assertEqual(len(window.preview_cards),1)
    def test_audio_format_is_explicit_and_mp3_preset_survives_restart(self):
        with self.window() as (window,folder):
            self.assertFalse(window.audio_options.isVisible())
            window.quality.setCurrentIndex(3)
            self.assertTrue(window.audio_options.isVisible())
            window.audio_format.setCurrentIndex(1)
            self.assertIn('重新编码',window.audio_format_hint.text())
            window.on_parsed(dict(id='TestVideo01',url='https://youtu.be/TestVideo01',title='Audio',channel_id='UC'+'a'*22,heights=[]))
            with patch.object(window,'launch') as launch:
                window.begin()
            self.assertEqual(launch.call_args.args[0][0][3],'audio_mp3')
            window.save_settings()
            restored=Window(folder)
            try:self.assertEqual(restored.audio_format.currentIndex(),1)
            finally:restored.close()
    def test_existing_audio_export_routes_to_local_worker(self):
        with self.window() as (window,folder):
            source=folder/'sample [TestVideo01].webm';source.write_bytes(b'fixture')
            output=folder/'converted.mp3'
            window.history.save('TestVideo01',source);window.refresh_history();window.navigate(1);window.records.selectRow(0)
            result={'id':'TestVideo01','path':str(output),'warnings':[],'probe':{'streams':[]}}
            with patch('creatorsave.app.export_audio_file',return_value=result) as export,patch('creatorsave.app.download') as download:
                QTest.mouseClick(window.export_mp3_button,Qt.MouseButton.LeftButton);self.app.processEvents()
                self.assertTrue(window.path_dialog.isVisible())
                window.path_dialog.setDirectory(str(folder));window.path_dialog.accept()
                until=time.monotonic()+3
                while (window.busy() or not export.called) and time.monotonic()<until:QTest.qWait(20)
                self.app.processEvents()
                self.assertEqual(Path(export.call_args.args[0]),source)
                download.assert_not_called()
                self.assertEqual(window.history.tasks()[0][4],'local_mp3')
                self.assertEqual(window.history.tasks()[0][5],'completed')
    def test_folder_button_opens_selects_and_persists(self):
        with self.window() as (window,folder):
            chosen=folder/'selected'; chosen.mkdir()
            window.folder.setText(str(folder))
            window.navigate(2); self.app.processEvents()
            QTest.mouseClick(window.folder_browse,Qt.MouseButton.LeftButton); self.app.processEvents()
            dialog=window.path_dialog
            self.assertIsNotNone(dialog)
            self.assertTrue(dialog.isVisible())
            self.assertTrue(dialog.testOption(QFileDialog.Option.DontUseNativeDialog))
            dialog.setDirectory(str(chosen)); dialog.accept(); self.app.processEvents()
            self.assertEqual(Path(window.folder.text()),chosen)
            self.assertEqual(Path(json.loads((folder/'settings.json').read_text(encoding='utf-8'))['folder']),chosen)
            self.assertEqual(Path(window.destination.text()),chosen)
    def test_folder_cancel_and_download_page_button(self):
        with self.window() as (window,folder):
            original=window.folder.text()
            QTest.mouseClick(window.destination_button,Qt.MouseButton.LeftButton); self.app.processEvents()
            dialog=window.path_dialog
            self.assertTrue(dialog.isVisible())
            dialog.reject(); self.app.processEvents()
            self.assertEqual(window.folder.text(),original)
            self.assertIsNone(window.path_dialog)

if __name__=='__main__': unittest.main()
