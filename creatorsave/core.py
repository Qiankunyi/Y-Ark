import re
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def video_id(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http"):
        raise ValueError("请输入完整的 YouTube 单视频链接")
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        value = parsed.path.strip("/")
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com") and parsed.path == "/watch":
        value = parse_qs(parsed.query).get("v", [""])[0]
    else:
        raise ValueError("仅支持 YouTube 单视频链接")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        raise ValueError("视频 ID 无效")
    return value


def redact(text):
    text = re.sub(r"(?im)^.*(?:cookie|authorization|password|token).*$", "[REDACTED]", str(text))
    return re.sub(r"https?://\S+", "[URL]", text)


class History:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS history (video_id TEXT PRIMARY KEY, completed TEXT, path TEXT, status TEXT)")
        self.db.commit()

    def contains(self, identity):
        return self.db.execute("SELECT 1 FROM history WHERE video_id=?", (identity,)).fetchone() is not None

    def save(self, identity, path, status="completed"):
        self.db.execute("INSERT OR REPLACE INTO history VALUES (?, ?, ?, ?)", (identity, datetime.now(timezone.utc).isoformat(), str(path), status))
        self.db.commit()

    def rows(self):
        return self.db.execute("SELECT * FROM history ORDER BY completed DESC").fetchall()

    def save_details(self, identity, probe):
        self.db.execute('CREATE TABLE IF NOT EXISTS verified_details (video_id TEXT PRIMARY KEY, details TEXT)')
        self.db.execute('INSERT OR REPLACE INTO verified_details VALUES (?,?)', (identity, json.dumps(probe,ensure_ascii=False)))
        self.db.commit()

    def ensure_task_schema(self):
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, video_id TEXT, url TEXT, folder TEXT, preset TEXT, state TEXT, detail TEXT)')
        if 'options_json' not in {row[1] for row in self.db.execute('PRAGMA table_info(tasks)')}:
            self.db.execute("ALTER TABLE tasks ADD COLUMN options_json TEXT NOT NULL DEFAULT '{}'")
        self.db.commit()

    def task_options(self,task):
        self.ensure_task_schema()
        row=self.db.execute('SELECT options_json FROM tasks WHERE id=?',(task,)).fetchone()
        return json.loads(row[0]) if row else {}

    def create_task(self, identity, url, folder, preset, options=None):
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, video_id TEXT, url TEXT, folder TEXT, preset TEXT, state TEXT, detail TEXT)')
        self.ensure_task_schema()
        cursor = self.db.execute('INSERT INTO tasks(video_id,url,folder,preset,state,detail,options_json) VALUES(?,?,?,?,?,?,?)', (identity,url,folder,preset,'waiting','',json.dumps(options or {})))
        self.db.commit()
        return cursor.lastrowid

    def update_task(self, task, state, detail=''):
        self.db.execute('UPDATE tasks SET state=?,detail=? WHERE id=?', (state,redact(detail),task))
        self.db.commit()

    def tasks(self):
        self.ensure_task_schema()
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, video_id TEXT, url TEXT, folder TEXT, preset TEXT, state TEXT, detail TEXT)')
        self.db.execute("UPDATE tasks SET state='interrupted' WHERE state NOT IN ('waiting','completed','warning','failed','cancelled','interrupted')")
        self.db.commit()
        return self.db.execute('SELECT id,video_id,url,folder,preset,state,detail FROM tasks ORDER BY id').fetchall()


def import_candidates(folder):
    result = {}
    for path in Path(folder).iterdir():
        if path.is_file() and path.suffix.lower() in ('.mp4','.mkv','.webm','.m4a','.opus','.mp3','.ogg','.flac','.mka'):
            match = re.search(r'\[([A-Za-z0-9_-]{11})\](?:\.[^.]+)$', path.name)
            if match: result.setdefault(match[1], str(path))
    return result
