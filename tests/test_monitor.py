import sqlite3
import unittest
from creatorsave.monitor import Monitor

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); self.monitor=Monitor(self.db)
        self.identity='UC'+'a'*22
    def tearDown(self): self.db.close()
    def test_baseline_rename_new_video(self):
        m=self.monitor; m.follow(self.identity,'old')
        m.apply_feed(self.identity,'old',[dict(id='TestVideo02',title='one',published='2026-01-01')])
        self.assertEqual(m.discoveries()[0][3],0)
        m.follow(self.identity,'new'); self.assertEqual(len(m.channels()),1)
        m.apply_feed(self.identity,'new',[dict(id='TestVideo03',title='two',published='2026-01-02')])
        self.assertEqual(m.discoveries()[0][3],1)
        self.assertEqual(len(m.discoveries()),2)
    def test_network_error_never_means_deleted(self):
        m=self.monitor; m.watch('TestVideo02')
        for _ in range(3): m.apply_status('TestVideo02',False,'Network failure')
        self.assertEqual(m.watched()[0][1],'recheck')
    def test_fast_rechecks_do_not_confirm(self):
        m=self.monitor; m.watch('TestVideo02')
        for _ in range(3): m.apply_status('TestVideo02',False,'Private video',True)
        self.assertEqual(m.watched()[0][1],'recheck')
        m.apply_status('TestVideo02',True)
        self.assertEqual(m.watched()[0][1],'normal')
