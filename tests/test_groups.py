import sqlite3
import unittest
import tempfile
from pathlib import Path
from creatorsave.monitor import Monitor

class GroupTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.monitor=Monitor(self.db)
        self.ids=['UC'+str(i).zfill(22) for i in range(200)]
        self.db.executemany('INSERT INTO channels(id,name) VALUES(?,?)',[(identity,f'Creator {i:03}') for i,identity in enumerate(self.ids)]);self.db.commit()
    def tearDown(self):self.db.close()
    def test_hundreds_group_search_intersection_and_ungrouped(self):
        music=self.monitor.create_group('ASMR');games=self.monitor.create_group('游戏')
        self.monitor.set_channel_groups(self.ids[:100],[music])
        self.monitor.change_memberships(self.ids[:10]+self.ids[100:150],[games])
        self.assertEqual(len(self.monitor.filtered_channels(music)),100)
        self.assertEqual(len(self.monitor.filtered_channels(games)),60)
        self.assertEqual(len(self.monitor.filtered_channels(-1)),50)
        self.assertEqual(len(self.monitor.filtered_channels(music,'CREATOR 09')),10)
        self.assertEqual(self.monitor.filtered_channels(games,self.ids[137])[0][0],self.ids[137])
        self.assertFalse(self.monitor.filtered_channels(music,'not present'))
    def test_rename_and_delete_preserve_creators_other_memberships_and_discoveries(self):
        a=self.monitor.create_group('A');b=self.monitor.create_group('B')
        self.monitor.set_channel_groups(self.ids[:2],[a,b])
        self.monitor.apply_feed(self.ids[0],'Creator renamed',[dict(id='TestVideo02',title='Video',published='2026-11-01')])
        self.monitor.rename_group(a,'夜间');self.monitor.follow(self.ids[0],'New creator name')
        self.assertEqual(self.monitor.membership_map()[self.ids[0]],{a,b})
        self.monitor.delete_group(a)
        self.assertEqual(len(self.monitor.channels()),200)
        self.assertEqual(self.monitor.membership_map()[self.ids[0]],{b})
        self.assertEqual(len(self.monitor.discoveries()),1)
    def test_names_validated_and_failed_assignment_is_atomic(self):
        group=self.monitor.create_group(' ASMR ')
        for name in ('asmr','ＡＳＭＲ'):
            with self.assertRaises(ValueError):self.monitor.create_group(name)
        for name in ('','   ','a'*51,'bad\nname'):
            with self.assertRaises(ValueError):self.monitor.create_group(name)
        self.monitor.set_channel_groups([self.ids[0]],[group])
        with self.assertRaises(ValueError):self.monitor.set_channel_groups([self.ids[0]],[999])
        self.assertEqual(self.monitor.membership_map()[self.ids[0]],{group})
    def test_legacy_following_schema_migrates_without_reset(self):
        old=sqlite3.connect(':memory:')
        old.execute('CREATE TABLE channels(id TEXT PRIMARY KEY,name TEXT,checked TEXT,baseline INTEGER DEFAULT 0,error TEXT)')
        old.execute('INSERT INTO channels(id,name,baseline) VALUES(?,?,1)',(self.ids[0],'Keep me'));old.commit()
        model=Monitor(old)
        self.assertEqual(model.channels()[0][1],'Keep me');self.assertEqual(model.channels()[0][3],1)
        self.assertEqual(model.groups(),[]);old.close()

    def test_groups_and_memberships_survive_database_reopen(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent.parent/'.tmp') as folder:
            path=Path(folder)/'groups.db';db=sqlite3.connect(path);model=Monitor(db)
            model.follow(self.ids[0],'Persistent creator');group=model.create_group('常看');model.set_channel_groups([self.ids[0]],[group]);db.close()
            db=sqlite3.connect(path);restored=Monitor(db)
            self.assertEqual(restored.groups()[0][1],'常看');self.assertEqual(restored.groups()[0][2],1)
            self.assertEqual(restored.membership_map()[self.ids[0]],{group});db.close()
