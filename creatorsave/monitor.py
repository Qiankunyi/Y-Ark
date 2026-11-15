"""Explicit subscriptions and conservative public-access observations."""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from .core import redact

def now(): return datetime.now(timezone.utc).isoformat()

def channel_feed(identity):
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',identity): raise ValueError('Invalid channel ID')
    url='https://www.youtube.com/feeds/videos.xml?channel_id='+identity
    with urllib.request.urlopen(url,timeout=25) as response:
        raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024: raise ValueError('Feed too large')
    root=ET.fromstring(raw)
    ns={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015'}
    entries=[]
    for item in root.findall('a:entry',ns):
        video=item.findtext('yt:videoId',namespaces=ns)
        if video and re.fullmatch(r'[A-Za-z0-9_-]{11}',video):
            entries.append({'id':video,'title':item.findtext('a:title',default='',namespaces=ns),'published':item.findtext('a:published',default='',namespaces=ns)})
    return root.findtext('a:title',default=identity,namespaces=ns),entries

class Monitor:
    def __init__(self,db):
        self.db=db
        db.executescript('''CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY,name TEXT,checked TEXT,baseline INTEGER DEFAULT 0,error TEXT);
        CREATE TABLE IF NOT EXISTS discoveries(channel TEXT,video TEXT,title TEXT,published TEXT,is_new INTEGER,PRIMARY KEY(channel,video));
        CREATE TABLE IF NOT EXISTS watched(video TEXT PRIMARY KEY,state TEXT,checked TEXT,last_ok TEXT,failures INTEGER DEFAULT 0,detail TEXT);''')
        db.commit()
        self.ensure_groups()
    def follow(self,identity,name):
        if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',identity): raise ValueError('Invalid channel ID')
        self.db.execute("INSERT INTO channels(id,name) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",(identity,name)); self.db.commit()
    def channels(self): return self.db.execute('SELECT id,name,checked,baseline,error FROM channels ORDER BY name').fetchall()
    def apply_feed(self,identity,name,entries,error=''):
        if error:
            self.db.execute('UPDATE channels SET error=? WHERE id=?',(redact(error),identity)); self.db.commit(); return
        row=self.db.execute('SELECT baseline FROM channels WHERE id=?',(identity,)).fetchone()
        if not row:return
        for item in entries:
            self.db.execute('INSERT OR IGNORE INTO discoveries VALUES(?,?,?,?,?)',(identity,item['id'],item['title'],item['published'],int(bool(row[0]))))
        self.db.execute('UPDATE channels SET name=?,checked=?,baseline=1,error=NULL WHERE id=?',(name,now(),identity)); self.db.commit()
    def discoveries(self): return self.db.execute('SELECT video,title,published,is_new FROM discoveries ORDER BY published DESC').fetchall()
    def watch(self,identity):
        self.db.execute("INSERT OR IGNORE INTO watched(video,state) VALUES(?,'recheck')",(identity,)); self.db.commit()
    def watched(self): return self.db.execute('SELECT video,state,checked,last_ok,failures,detail FROM watched').fetchall()
    def apply_status(self,identity,ok,error='',explicit_unavailable=False):
        previous=self.db.execute('SELECT checked,failures FROM watched WHERE video=?',(identity,)).fetchone()
        if not previous:return
        failures=0 if ok else previous[1]
        # Require observations at least 30 minutes apart; rapid manual clicks do not confirm.
        spaced=not previous[0] or (datetime.now(timezone.utc)-datetime.fromisoformat(previous[0])).total_seconds()>=1800
        if not ok and explicit_unavailable and spaced: failures+=1
        if not ok and not explicit_unavailable: failures=0
        state='normal' if ok else ('public_unavailable' if explicit_unavailable and failures>=2 else 'recheck')
        timestamp=now()
        self.db.execute('UPDATE watched SET state=?,checked=?,last_ok=CASE WHEN ? THEN ? ELSE last_ok END,failures=?,detail=? WHERE video=?',(state,timestamp,int(ok),timestamp,failures,redact(error),identity)); self.db.commit()

    def ensure_groups(self):
        self.db.executescript('''CREATE TABLE IF NOT EXISTS creator_groups(id INTEGER PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS creator_group_members(channel TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,group_id INTEGER NOT NULL REFERENCES creator_groups(id) ON DELETE CASCADE,PRIMARY KEY(channel,group_id));
        CREATE INDEX IF NOT EXISTS creator_group_members_by_group ON creator_group_members(group_id,channel);''')
        self.db.commit()

    def normalized_group(self,name):
        import unicodedata
        value=name.strip()
        if not value or len(value)>50 or any(ord(ch)<32 for ch in value):raise ValueError('group_name_invalid')
        return value,unicodedata.normalize('NFKC',value).casefold()

    def create_group(self,name):
        import sqlite3
        value,key=self.normalized_group(name)
        try:
            with self.db:
                cursor=self.db.execute('INSERT INTO creator_groups(name,name_key) VALUES(?,?)',(value,key))
            return cursor.lastrowid
        except sqlite3.IntegrityError as exc:raise ValueError('group_name_exists') from exc

    def rename_group(self,identity,name):
        import sqlite3
        value,key=self.normalized_group(name)
        try:
            with self.db:
                cursor=self.db.execute('UPDATE creator_groups SET name=?,name_key=? WHERE id=?',(value,key,identity))
                if not cursor.rowcount:raise ValueError('group_not_found')
        except sqlite3.IntegrityError as exc:raise ValueError('group_name_exists') from exc

    def delete_group(self,identity):
        with self.db:
            self.db.execute('DELETE FROM creator_group_members WHERE group_id=?',(identity,))
            self.db.execute('DELETE FROM creator_groups WHERE id=?',(identity,))

    def groups(self):
        return self.db.execute('SELECT g.id,g.name,count(m.channel) FROM creator_groups g LEFT JOIN creator_group_members m ON m.group_id=g.id GROUP BY g.id ORDER BY g.name COLLATE NOCASE,g.id').fetchall()

    def membership_map(self):
        result={}
        for channel,group in self.db.execute('SELECT channel,group_id FROM creator_group_members'):
            result.setdefault(channel,set()).add(group)
        return result

    def change_memberships(self,channels,add=(),remove=()):
        channels=set(channels);add=set(add);remove=set(remove)
        known={row[0] for row in self.channels()};groups={row[0] for row in self.groups()}
        if not channels<=known:raise ValueError('Unknown creator')
        if not (add|remove)<=groups:raise ValueError('group_not_found')
        if add&remove:raise ValueError('Conflicting membership changes')
        with self.db:
            self.db.executemany('DELETE FROM creator_group_members WHERE channel=? AND group_id=?',[(channel,group) for channel in channels for group in remove])
            self.db.executemany('INSERT OR IGNORE INTO creator_group_members VALUES(?,?)',[(channel,group) for channel in channels for group in add])

    def set_channel_groups(self,channels,group_ids):
        all_groups={row[0] for row in self.groups()}
        selected=set(group_ids)
        self.change_memberships(channels,selected,all_groups-selected)

    def filtered_channels(self,group=None,query=''):
        rows=self.channels();members=self.membership_map()
        query=query.strip().casefold()
        return [row for row in rows if (group is None or (group==-1 and not members.get(row[0])) or group in members.get(row[0],set())) and (not query or query in row[1].casefold() or query in row[0].casefold())]
