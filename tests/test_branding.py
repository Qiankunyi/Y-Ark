import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creatorsave.branding import data_directory


class BrandingTests(unittest.TestCase):
    def test_new_install_and_legacy_data_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'LOCALAPPDATA': folder}, clear=True):
                self.assertEqual(data_directory(), Path(folder) / 'Y-Ark')
                legacy = Path(folder) / 'CreatorSave'
                legacy.mkdir()
                database = legacy / 'history.sqlite3'
                database.write_bytes(b'existing history')
                self.assertEqual(data_directory(), legacy)
                self.assertEqual(database.read_bytes(), b'existing history')

    def test_overrides_have_explicit_precedence(self):
        with patch.dict(os.environ, {'Y_ARK_DATA': 'new-path', 'CREATORSAVE_DATA': 'old-path'}, clear=True):
            self.assertEqual(data_directory('explicit'), Path('explicit'))
            self.assertEqual(data_directory(), Path('new-path'))
        with patch.dict(os.environ, {'CREATORSAVE_DATA': 'old-path'}, clear=True):
            self.assertEqual(data_directory(), Path('old-path'))
