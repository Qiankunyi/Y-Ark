"""Scalable creator UI examples, isolated from personal subscriptions."""
import os,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from creatorsave.app import Window
from creatorsave.group_dialogs import MembershipDialog
root=Path(__file__).resolve().parents[1];app=QApplication([])
for font in ('msyh.ttc','YuGothR.ttc','segoeui.ttf'):QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
app.setFont(QFont('Microsoft YaHei UI',10))
with tempfile.TemporaryDirectory(dir=root/'.tmp') as folder:
    w=Window(folder);w.resize(1280,920)
    ids=['UC'+str(i).zfill(22) for i in range(200)]
    w.history.db.executemany('INSERT INTO channels(id,name) VALUES(?,?)',[(identity,f'示例作者 {index:03} · '+('ASMR' if index<100 else 'Music')) for index,identity in enumerate(ids)]);w.history.db.commit()
    groups={name:w.monitor.create_group(name) for name in ('ASMR','音乐','日语频道','常看')}
    w.monitor.set_channel_groups(ids[:100],[groups['ASMR']]);w.monitor.set_channel_groups(ids[100:150],[groups['音乐']]);w.monitor.change_memberships(ids[40:60],[groups['日语频道']]);w.monitor.change_memberships(ids[42:45],[groups['常看']])
    for index in range(40,50):w.monitor.apply_feed(ids[index],f'示例作者 {index:03} · ASMR',[dict(id='v'+str(index).zfill(10),title=f'雨夜声音日记 · 示例作品 {index}',published='2026-11-04')])
    w.refresh_following();w.navigate(4);w.group_filter.setCurrentIndex(w.group_filter.findData(groups['ASMR']));w.creator_search.setText('示例作者 04');w.show();app.processEvents()
    w.grab().save(str(root/'docs/interface-groups.png'))
    dialog=MembershipDialog(w.monitor,ids[42:45],w.t,w);dialog.show();app.processEvents();dialog.grab().save(str(root/'docs/interface-group-memberships.png'));dialog.close()
    w.language.setCurrentIndex(1);app.processEvents();w.grab().save(str(root/'docs/interface-groups-en.png'))
    w.language.setCurrentIndex(2);app.processEvents();w.grab().save(str(root/'docs/interface-groups-ja.png'))
    w.close()
