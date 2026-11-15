import os
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QPoint,QThread
from PySide6.QtGui import QPalette,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from creatorsave.app import Window

class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    @contextmanager
    def window(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp') as folder:
            window=Window(folder);window.show();self.app.processEvents()
            try:yield window
            finally:
                if window.worker:
                    window.worker.requestInterruption();window.worker.wait(3000);self.app.processEvents()
                window.close();self.app.processEvents()
    def wait_done(self,window):
        until=time.monotonic()+4
        while window.analysis_active and time.monotonic()<until:QTest.qWait(15)
        self.assertFalse(window.analysis_active)
    def sample(self,url,cookie,emit):
        QThread.msleep(80)
        return dict(id=url[-11:],title='Visible result',channel='Creator',channel_id='UC'+'a'*22,heights=[1080])
    def test_click_starts_worker_and_shows_success(self):
        with self.window() as window,patch('creatorsave.app.extract',side_effect=self.sample) as mocked:
            window.urls.setPlainText('https://youtu.be/TestVideo01')
            QTest.mouseClick(window.parse_button,Qt.MouseButton.LeftButton)
            self.assertTrue(window.analysis_feedback.isVisible())
            self.assertTrue(window.analysis_active)
            self.assertIn('正在解析',window.analysis_message.text())
            self.assertFalse(window.parse_button.isEnabled())
            self.wait_done(window)
            mocked.assert_called_once()
            self.assertIn('已解析 1',window.analysis_message.text())
            self.assertTrue(window.start.isEnabled())
    def test_dns_failure_is_visible_without_opening_logs(self):
        with self.window() as window,patch('creatorsave.app.extract',side_effect=RuntimeError("Failed to resolve 'www.youtube.com': getaddrinfo failed")):
            window.urls.setPlainText('https://youtu.be/TestVideo01')
            QTest.mouseClick(window.parse_button,Qt.MouseButton.LeftButton)
            self.wait_done(window)
            self.assertTrue(window.analysis_feedback.isVisible())
            self.assertEqual(window.analysis_message.text(),'解析失败')
            self.assertIn('域名',window.analysis_detail.text())
            self.assertTrue(window.analysis_retry.isVisible())
            self.assertTrue(window.analysis_log.isVisible())
            self.assertTrue(window.parse_button.isEnabled())
            self.assertFalse(window.start.isEnabled())
            self.assertEqual(window.tabs.currentIndex(),0)
    def test_partial_failure_keeps_success_and_timeout_message(self):
        calls=0
        def extract(url,cookie,emit):
            nonlocal calls
            calls+=1
            if calls==1:raise TimeoutError('Connection timed out')
            return self.sample(url,cookie,emit)
        with self.window() as window,patch('creatorsave.app.extract',side_effect=extract):
            window.urls.setPlainText('https://youtu.be/TestVideo01\nhttps://youtu.be/TestVideo02')
            QTest.mouseClick(window.parse_button,Qt.MouseButton.LeftButton)
            self.wait_done(window)
            self.assertIn('1 条失败',window.analysis_message.text())
            self.assertIn('超时',window.analysis_detail.text())
            self.assertEqual(len(window.previews),1)
            self.assertTrue(window.start.isEnabled())
    def test_cancel_is_visible_and_discards_late_results(self):
        with self.window() as window,patch('creatorsave.app.extract',side_effect=self.sample):
            window.urls.setPlainText('https://youtu.be/TestVideo01')
            QTest.mouseClick(window.parse_button,Qt.MouseButton.LeftButton)
            QTest.mouseClick(window.analysis_cancel,Qt.MouseButton.LeftButton)
            self.assertIn('正在取消',window.analysis_message.text())
            self.wait_done(window)
            self.assertIn('已取消',window.analysis_message.text())
            self.assertFalse(window.previews)
    def test_invalid_link_has_inline_feedback(self):
        with self.window() as window,patch('creatorsave.app.extract') as mocked:
            window.urls.setPlainText('invalid link')
            QTest.mouseClick(window.parse_button,Qt.MouseButton.LeftButton)
            self.assertIn('链接格式',window.analysis_message.text())
            self.assertTrue(window.analysis_feedback.isVisible())
            mocked.assert_not_called()
    def test_context_menu_readable_with_dark_system_palette(self):
        dark=QPalette();dark.setColor(QPalette.ColorRole.Window,QColor('#121212'));dark.setColor(QPalette.ColorRole.Text,QColor('#eeeeee'))
        self.app.setPalette(dark)
        with self.window() as window:
            window.urls.setPlainText('https://youtu.be/TestVideo01')
            menu=window.urls.createStandardContextMenu()
            try:
                menu.popup(window.urls.mapToGlobal(QPoint(30,30)));self.app.processEvents()
                background=menu.palette().color(QPalette.ColorRole.Window)
                foreground=menu.palette().color(QPalette.ColorRole.WindowText)
                self.assertGreater(background.lightness(),220)
                self.assertLess(foreground.lightness(),100)
                enabled=[action for action in menu.actions() if action.isEnabled() and not action.isSeparator()]
                self.assertTrue(enabled)
                menu.setActiveAction(enabled[0]);self.app.processEvents()
                # The popup itself, including its selected item, must be renderable.
                self.assertFalse(menu.grab().isNull())
            finally:menu.close();menu.deleteLater()

if __name__=='__main__':unittest.main()
