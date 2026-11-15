import os
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton
from creatorsave.app import Window
from creatorsave.group_dialogs import GroupManager,MembershipDialog

class GroupAndProfileGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    @contextmanager
    def window(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp') as folder:
            window=Window(folder);window.show();self.app.processEvents()
            try:yield window,Path(folder)
            finally:
                if window.path_dialog:window.path_dialog.reject()
                if window.worker:window.worker.requestInterruption();window.worker.wait(3000);self.app.processEvents()
                window.close();self.app.processEvents()
    def test_150_creators_group_and_search_filters_never_leak_results(self):
        with self.window() as (window,folder):
            ids=['UC'+str(i).zfill(22) for i in range(150)]
            window.history.db.executemany('INSERT INTO channels(id,name) VALUES(?,?)',[(identity,f'Studio {index:03}') for index,identity in enumerate(ids)]);window.history.db.commit()
            group=window.monitor.create_group('ASMR');other=window.monitor.create_group('其他')
            window.monitor.set_channel_groups(ids[:100],[group]);window.monitor.set_channel_groups(ids[100:],[other])
            for index,identity in enumerate(ids):window.monitor.apply_feed(identity,f'Studio {index:03}',[dict(id='v'+str(index).zfill(10),title=f'Video {index}',published='2026-11-01')])
            window.refresh_following();window.navigate(4)
            self.assertEqual(window.discovery_table.rowCount(),150)
            window.group_filter.setCurrentIndex(window.group_filter.findData(group))
            self.assertEqual(window.channels_list.count(),101);self.assertEqual(window.discovery_table.rowCount(),100)
            window.creator_search.setText('STUDIO 09')
            self.assertEqual(window.channels_list.count(),11);self.assertEqual(window.discovery_table.rowCount(),10)
            self.assertEqual(window.creator_count.text(),'10/150')
            window.creator_search.setText(ids[140]);self.assertEqual(window.discovery_table.rowCount(),0)
            window.creator_search.clear();window.group_filter.setCurrentIndex(window.group_filter.findData(-1))
            self.assertEqual(window.discovery_table.rowCount(),0)
            window.monitor.delete_group(group);window.refresh_following()
            self.assertEqual(window.channels_list.count(),101);self.assertEqual(len(window.monitor.channels()),150)
    def test_manager_create_and_mixed_batch_assignments(self):
        with self.window() as (window,folder):
            ids=['UC'+'a'*22,'UC'+'b'*22]
            for identity in ids:window.monitor.follow(identity,identity)
            dialog=GroupManager(window.monitor,window.t,window);dialog.show();dialog.name.setText('阅读')
            next(button for button in dialog.findChildren(QPushButton) if button.text()==window.t('create_group')).click()
            self.assertEqual(window.monitor.groups()[0][1],'阅读');a=window.monitor.groups()[0][0];b=window.monitor.create_group('夜间')
            window.monitor.set_channel_groups([ids[0]],[a,b]);window.monitor.set_channel_groups([ids[1]],[b])
            mixed=MembershipDialog(window.monitor,ids,window.t,window)
            row=next(mixed.list.item(i) for i in range(mixed.list.count()) if mixed.list.item(i).data(Qt.ItemDataRole.UserRole)==a)
            self.assertEqual(row.checkState(),Qt.CheckState.PartiallyChecked)
            before=window.monitor.membership_map();mixed.apply();self.assertEqual(window.monitor.membership_map(),before)
            assigned=MembershipDialog(window.monitor,ids,window.t,window)
            for index in range(assigned.list.count()):assigned.list.item(index).setCheckState(Qt.CheckState.Checked)
            assigned.apply();self.assertEqual(window.monitor.membership_map()[ids[1]],{a,b})
            dialog.close()
    def test_video_format_is_independent_persisted_and_used_by_retry(self):
        with self.window() as (window,folder):
            window.quality.setCurrentIndex(1);window.video_format.setCurrentText('MKV')
            window.on_parsed(dict(id='TestVideo02',url='https://youtu.be/TestVideo02',title='Video',heights=[1080]))
            with patch.object(window,'launch'):
                window.begin()
            task=window.history.tasks()[0][0]
            self.assertEqual(window.history.task_options(task),{'video_format':'mkv'})
            window.save_settings();restored=Window(folder)
            try:self.assertEqual(restored.video_format.currentText(),'MKV');self.assertEqual(restored.quality.currentIndex(),1)
            finally:restored.close()
            window.video_format.setCurrentText('MP4');window.queue.selectRow(0)
            result={'id':'TestVideo02','path':str(folder/'video.mkv'),'warnings':[],'probe':{'streams':[]}}
            with patch('creatorsave.app.download',return_value=result) as download:
                window.retry_task();until=time.monotonic()+3
                while (window.busy() or not download.called) and time.monotonic()<until:QTest.qWait(20)
                self.app.processEvents();self.assertEqual(download.call_args.kwargs['video_format'],'mkv')
