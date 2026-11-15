"""Product identity and backwards-compatible local data location."""
import os
from pathlib import Path

APP_NAME = 'Y-Ark'
VERSION = '0.2.1'


def data_directory(explicit=None):
    override = explicit or os.getenv('Y_ARK_DATA') or os.getenv('CREATORSAVE_DATA')
    if override:
        return Path(override)
    base = Path(os.getenv('LOCALAPPDATA') or Path.home())
    # Reuse existing installations in place: no copying of live SQLite files.
    legacy = base / 'CreatorSave'
    return legacy if legacy.is_dir() else base / APP_NAME
