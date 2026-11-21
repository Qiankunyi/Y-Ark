import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox

from creatorsave import doda
from creatorsave.app import Window


class DodaTests(unittest.TestCase):
    def test_course_links_share_one_page(self):
        lessons = doda.lessons(doda.PAGE + '#modalContent')
        self.assertEqual(len(lessons), len({lesson['id'] for lesson in lessons}))
        lesson = next(item for item in lessons if item['episode'] == 69)
        self.assertIn('今日の面接、相手は誰？', lesson['title'])
        self.assertEqual(lesson['url'], doda.PAGE)
        for invalid in ('https://youtu.be/TestVideo01', doda.PAGE.replace('doda.jp', 'doda.jp.example.org')):
            with self.assertRaises(ValueError):
                doda.lessons(invalid)

    def test_selection_queues_only_the_chosen_lesson_with_its_source(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1] / '.tmp') as folder:
            window = Window(folder)
            try:
                self.assertEqual(window.source_mode.currentText(), 'YouTube')
                window.source_mode.setCurrentIndex(1)
                window.urls.setPlainText(doda.PAGE + '#modalContent')
                window.analyze()
                deadline = time.monotonic() + 5
                while window.analysis_active and time.monotonic() < deadline:
                    QTest.qWait(20)
                self.assertFalse(window.analysis_active)
                self.assertFalse(window.start.isEnabled())
                index = next(i for i, lesson in enumerate(window.previews) if lesson['episode'] == 69)
                window.preview_cards[index].findChild(QCheckBox).click()
                self.assertTrue(window.start.isEnabled())
                with patch.object(window, 'launch') as launch:
                    window.begin()
                jobs = launch.call_args.args[0]
                self.assertEqual(len(jobs), 1)
                task, url, _, _ = jobs[0]
                self.assertEqual(url, doda.PAGE)
                window.source_mode.setCurrentIndex(0)
                self.assertFalse(window.previews)
                self.assertEqual(window.history.task_options(task)['source'], 'doda')
                self.assertEqual(window.history.task_options(task)['episode'], 69)
            finally:
                if window.worker and window.worker.isRunning():
                    window.worker.requestInterruption()
                    window.worker.wait(3000)
                window.close()
                app.processEvents()
