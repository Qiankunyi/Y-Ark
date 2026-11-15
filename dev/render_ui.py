"""Render UI review images with isolated, explicitly synthetic sample data."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import Qt,QBuffer,QIODevice
from PySide6.QtGui import QFont,QFontDatabase,QPixmap,QPainter,QColor,QLinearGradient
from PySide6.QtWidgets import QApplication
from creatorsave.app import Window

root=Path(__file__).resolve().parents[1]
app=QApplication([])
for font in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/segoeui.ttf','C:/Windows/Fonts/YuGothR.ttc'):
    if Path(font).is_file():QFontDatabase.addApplicationFont(font)
app.setFont(QFont('Microsoft YaHei UI',10))
demo_temp=tempfile.TemporaryDirectory(dir=root/'.tmp')
window=Window(demo_temp.name)
window.folder.setText('D:/Y-Ark/Downloads')
window.resize(1280,920);window.show();app.processEvents()
def save(name):
    for _ in range(4):app.processEvents()
    window.grab().save(str(root/'docs'/name))
window.language.setCurrentIndex(0);window.navigate(0);save('interface-empty.png')
def cover():
    pix=QPixmap(400,240); pix.fill(QColor('#1b414c'))
    p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient=QLinearGradient(0,0,400,240);gradient.setColorAt(0,QColor('#102f3c'));gradient.setColorAt(1,QColor('#548d86'));p.fillRect(pix.rect(),gradient)
    p.setPen(QColor('#90c3b1'))
    for x in range(25,400,30):p.drawLine(x,0,x-50,240)
    p.setPen(QColor('#f5f8ef'));p.setFont(QFont('Segoe UI',18));p.drawText(pix.rect(),Qt.AlignmentFlag.AlignCenter,'RAINY EVENING\nSAMPLE');p.end()
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);pix.save(buffer,'PNG');return bytes(buffer.data())
info=dict(id='TestVideo02',title='雨夜与轻声耳语 · Rainy evening ASMR',channel='示例作者 · Rain Studio',channel_id='UC'+'a'*22,heights=[720,1080,2160],duration=3620,upload_date='20261101',thumbnail_bytes=cover())
window.urls.setPlainText('https://www.youtube.com/watch?v=TestVideo02')
window.on_parsed(info)
window.add_task(-1,'TestVideo02','',window.folder.text(),'best','video','842 MB / ≈ 2.6 GB  ·  12.4 MB/s')
window.add_task(-2,'TestVideo03','',window.folder.text(),'1080','waiting','')
for language,name in enumerate(('zh','en','ja')):
    window.language.setCurrentIndex(language);save('interface-'+name+'.png')
window.language.setCurrentIndex(0)
for suffix,name in (('a','Rain Studio · 示例作者'),('b','夜の音 · 示例作者')):
    identity='UC'+suffix*22;window.monitor.follow(identity,name)
    window.monitor.apply_feed(identity,name,[dict(id=suffix*11,title='晚间声音日记 · 示例作品',published='2026-11-01')])
    window.monitor.apply_feed(identity,name,[dict(id=suffix*10+'1',title='雨后庭院的声音 · 示例新作品',published='2026-11-04')])
window.refresh_following();window.navigate(4);save('interface-creators.png')
window.navigate(2);save('interface-settings.png')
window.resize(1120,800);window.navigate(0);save('interface-compact.png')
window.close();demo_temp.cleanup()
