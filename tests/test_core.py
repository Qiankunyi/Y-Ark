import tempfile
import unittest
from pathlib import Path
from creatorsave.core import video_id, History, redact

class CoreTests(unittest.TestCase):
    def test_urls(self):
        for url in ['https://youtu.be/TestVideo02', 'https://www.youtube.com/watch?v=TestVideo02&list=abc']:
            self.assertEqual(video_id(url), 'TestVideo02')
        for url in ['https://youtube.com/playlist?list=x', 'https://evil.com/watch?v=TestVideo02', 'https://youtu.be/short']:
            with self.assertRaises(ValueError): video_id(url)
    def test_history_survives_move(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'
            path.touch()
            history = History(Path(directory) / 'history.db')
            history.save('TestVideo02', path)
            path.rename(Path(directory) / 'moved.mp4')
            self.assertTrue(history.contains('TestVideo02'))
            history.db.close()
    def test_redaction(self):
        self.assertNotIn('secret', redact('Cookie: secret\nAuthorization: secret\nhttps://example.com/?token=secret'))

if __name__ == '__main__': unittest.main()
