import json
import os
import sys
import time
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QUrl, QTimer, Qt, QTranslator, QLibraryInfo
from PySide6.QtGui import QDesktopServices, QPixmap, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTextEdit, QLineEdit, QPushButton, QComboBox, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QListWidgetItem, QFrame, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,QInputDialog)
from .core import History, video_id, redact, import_candidates
from .engine import download, extract, dependencies, Cancelled, export_audio_file, export_video_file
from . import doda
from .i18n import tr, LANGUAGES
from .monitor import Monitor, channel_feed
from .ui import build
from .group_dialogs import GroupManager,MembershipDialog
from .branding import APP_NAME, VERSION, data_directory

class Worker(QThread):
    event = Signal(int, dict)
    parsed = Signal(dict)
    success = Signal(int, dict)
    def __init__(self, jobs, cookie, analyzing=False, profiles=None, web=False):
        super().__init__()
        self.jobs, self.cookie, self.analyzing = jobs, cookie, analyzing
        self.profiles=profiles or {}
        self.web = web
    def run(self):
        for task, url, folder, preset in self.jobs:
            if self.isInterruptionRequested():
                self.event.emit(task, {'state': 'cancelled'}); continue
            try:
                if preset not in ('local_mp3','local_video'):self.event.emit(task, {'state': 'extracting'})
                emit = lambda event, task=task: self.event.emit(task, event)
                if self.analyzing:
                    if self.web:
                        for lesson in doda.lessons(url):
                            if self.isInterruptionRequested():
                                break
                            self.parsed.emit(lesson)
                        continue
                    info = extract(url, self.cookie, emit)
                    info['url'] = url
                    thumbnail=info.get('thumbnail') or ''
                    if urlparse(thumbnail).scheme=='https' and (urlparse(thumbnail).hostname or '').endswith('.ytimg.com'):
                        try:
                            with urllib.request.urlopen(thumbnail,timeout=10) as response: image=response.read(2*1024*1024+1)
                            if len(image)<=2*1024*1024: info['thumbnail_bytes']=image
                        except Exception: pass
                    if not self.isInterruptionRequested(): self.parsed.emit(info)
                else:
                    video_format=self.profiles.get(task,{}).get('video_format','mp4')
                    if preset=='local_mp3':result=export_audio_file(url,folder,emit,self.isInterruptionRequested)
                    elif preset=='local_video':result=export_video_file(url,folder,video_format,emit,self.isInterruptionRequested)
                    elif self.profiles.get(task, {}).get('source') == 'doda':
                        result = doda.download(url, self.profiles[task]['episode'], folder, preset, emit,
                                               self.isInterruptionRequested, video_format)
                    else:result=download(url,folder,preset,self.cookie,emit,self.isInterruptionRequested,video_format=video_format)
                    self.success.emit(task, result)
            except Exception as exc:
                state = 'cancelled' if self.isInterruptionRequested() or isinstance(exc, Cancelled) else 'failed'
                self.event.emit(task, {'state': state, 'detail': redact(exc)})

class MonitorWorker(QThread):
    feed = Signal(str,str,list,str)
    status = Signal(str,bool,str,bool)
    def __init__(self,channels,videos,cookie):
        super().__init__(); self.channels=channels; self.videos=videos; self.cookie=cookie
    def run(self):
        for identity in self.channels:
            if self.isInterruptionRequested(): return
            try:
                name,entries=channel_feed(identity); self.feed.emit(identity,name,entries,'')
            except Exception as exc: self.feed.emit(identity,'',[],redact(exc))
        for identity in self.videos:
            if self.isInterruptionRequested(): return
            try:
                extract('https://www.youtube.com/watch?v='+identity,self.cookie)
                self.status.emit(identity,True,'',False)
            except Exception as exc:
                detail=redact(exc); lowered=str(exc).lower()
                explicit=any(term in lowered for term in ('private video','video has been removed','video has been deleted'))
                self.status.emit(identity,False,detail,explicit)

class Window(QMainWindow):
    def __init__(self, data_dir=None):
        super().__init__()
        self.setWindowTitle(f'{APP_NAME} · {VERSION}')
        self.resize(1260, 900)
        self.setMinimumSize(1120,800)
        self.data = data_directory(data_dir)
        self.data.mkdir(parents=True, exist_ok=True)
        self.history = History(self.data / 'history.sqlite3')
        try: self.config = json.loads((self.data / 'settings.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): self.config = {}
        self.worker = None; self.previews = []; self.task_rows = {}; self.job_data = {}; self.task_states = {}; self.last_progress = {}; self.job_options={}; self.group_dialog=None
        self.preview_cards=[]; self.path_dialog=None
        self.analysis_active=False; self.analysis_total=0; self.analysis_current=0; self.analysis_failed=0
        self.analysis_started=0.0; self.analysis_errors=[]; self.analysis_tone=''; self.analysis_cancelled=False
        self.qt_translator=QTranslator(self)
        QApplication.setStyle('Fusion')
        palette=QPalette()
        for role,color in ((QPalette.ColorRole.Window,'#f4f6fa'),(QPalette.ColorRole.WindowText,'#27364b'),(QPalette.ColorRole.Base,'#ffffff'),(QPalette.ColorRole.AlternateBase,'#fafcfd'),(QPalette.ColorRole.Text,'#27364b'),(QPalette.ColorRole.Button,'#ffffff'),(QPalette.ColorRole.ButtonText,'#27364b'),(QPalette.ColorRole.Highlight,'#d5eee6'),(QPalette.ColorRole.HighlightedText,'#163f35')):palette.setColor(role,QColor(color))
        palette.setColor(QPalette.ColorRole.ToolTipBase,QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.ToolTipText,QColor('#27364b'))
        for role in (QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText,QPalette.ColorRole.WindowText):palette.setColor(QPalette.ColorGroup.Disabled,role,QColor('#8796a6'))
        QApplication.instance().setPalette(palette)
        self.setPalette(palette)
        self.monitor=Monitor(self.history.db); self.monitor_worker=None
        build(self)
        self.video_format.setCurrentIndex(1 if self.config.get('video_format')=='mkv' else 0)
        self.video_format.currentIndexChanged.connect(self.update_audio_options)
        self.audio_format.setCurrentIndex(self.config.get('audio_format',0))
        self.quality.currentIndexChanged.connect(self.update_audio_options)
        self.audio_format.currentIndexChanged.connect(self.update_audio_options)
        self.parse_button.clicked.connect(self.analyze)
        self.paste_button.clicked.connect(self.paste_links)
        self.analysis_cancel.clicked.connect(self.stop)
        self.analysis_retry.clicked.connect(self.analyze)
        self.analysis_log.clicked.connect(lambda:self.navigate(3))
        self.analysis_clock=QTimer(self); self.analysis_clock.setInterval(1000); self.analysis_clock.timeout.connect(self.refresh_analysis_feedback)
        self.start.clicked.connect(self.begin); self.cancel.clicked.connect(self.stop)
        self.export_mp3_button.clicked.connect(self.export_selected_audio)
        self.export_video_button.clicked.connect(self.export_selected_video)
        self.retry.clicked.connect(self.retry_task); self.import_button.clicked.connect(self.import_history)
        self.open_button.clicked.connect(lambda: self.open_history(False))
        self.folder_button.clicked.connect(lambda: self.open_history(True))
        self.folder_browse.clicked.connect(lambda: self.choose(self.folder,'folder'))
        self.destination_button.clicked.connect(lambda: self.choose(self.folder,'folder'))
        for key,button in self.file_browse_buttons.items():
            field=self.cookie if key=='cookie' else self.deno
            button.clicked.connect(lambda checked=False,field=field,key=key:self.choose(field,key))
        for field in (self.folder,self.cookie,self.deno): field.editingFinished.connect(self.save_settings)
        self.folder.textChanged.connect(self.update_destination)
        self.check_button.clicked.connect(self.check_dependencies)
        self.copy_button.clicked.connect(lambda: QApplication.clipboard().setText(redact(self.log.toPlainText())))
        self.language.currentIndexChanged.connect(self.translate)
        self.urls.textChanged.connect(self.invalidate)
        self.source_mode.currentIndexChanged.connect(self.source_changed)
        self.daily.toggled.connect(self.save_settings)
        self.check_follow.clicked.connect(self.check_monitor)
        self.watch_button.clicked.connect(self.watch_selected)
        self.discovery_button.clicked.connect(self.analyze_discovery)
        self.channels_list.itemSelectionChanged.connect(self.refresh_discoveries)
        self.group_filter.currentIndexChanged.connect(self.refresh_following)
        self.creator_search.textChanged.connect(self.refresh_following)
        self.group_manager_button.clicked.connect(self.manage_groups)
        self.group_assign_button.clicked.connect(self.assign_groups)
        self.discovery_table.itemSelectionChanged.connect(self.update_discovery_action)
        self.queue.itemSelectionChanged.connect(self.update_actions)
        self.discovery_table.setColumnHidden(3,True)
        self.discovery_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in (1,2): self.discovery_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        for column in (1,2): self.queue.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.timer=QTimer(self); self.timer.setInterval(24*60*60*1000)
        self.timer.timeout.connect(lambda:self.check_monitor() if self.daily.isChecked() else None); self.timer.start()
        self.translate(); self.refresh_history(); self.check_dependencies(); self.update_destination()
        for task, identity, url, folder, preset, state, detail in self.history.tasks():
            self.add_task(task, identity, url, folder, preset, state, detail)
        self.update_actions()
    def t(self,key): return tr(key,self.language.currentIndex())
    def table(self,columns):
        table = QTableWidget(0,columns); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().hide(); table.setShowGrid(False); table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(52); table.setWordWrap(False)
        return table
    def navigate(self,index):
        self.tabs.setCurrentIndex(index)
        for page,button in self.nav_buttons.items(): button.setChecked(page==index)
        titles=('download_page','history','settings','logs','creators_page')
        subtitles=('download_subtitle','history_subtitle','settings_subtitle','logs_subtitle','creator_subtitle')
        self.page_title.setText(self.t(titles[index])); self.page_subtitle.setText(self.t(subtitles[index]))
    def translate(self):
        application=QApplication.instance()
        application.removeTranslator(self.qt_translator)
        locale=('zh_CN','en','ja')[self.language.currentIndex()]
        if locale!='en' and self.qt_translator.load('qtbase_'+locale,QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            application.installTranslator(self.qt_translator)
        for widget,key in self.text_bindings: widget.setText(self.t(key))
        self.creator_search.setPlaceholderText(self.t('search_creators'))
        self.source_mode.setAccessibleName(self.t('video_source'))
        self.source_mode.setItemText(1, self.t('web_video'))
        self.update_source_prompt()
        self.daily.setText(self.t('daily'))
        self.parse_button.setText(self.t('extracting' if self.analysis_active else 'parse'))
        selected=max(0,self.quality.currentIndex()) if self.quality.count() else min(3,max(0,self.config.get('quality',0))); self.quality.clear()
        self.quality.addItems([self.t(key) for key in ('best','1080','720','audio')]); self.quality.setCurrentIndex(selected)
        audio_selected=max(0,self.audio_format.currentIndex()) if self.audio_format.count() else self.config.get('audio_format',0)
        self.audio_format.blockSignals(True); self.audio_format.clear()
        self.audio_format.addItems([self.t('audio_original'),self.t('audio_mp3')]); self.audio_format.setCurrentIndex(audio_selected); self.audio_format.blockSignals(False)
        self.update_audio_options()
        self.queue.setHorizontalHeaderLabels([self.t('title'),self.t('quality'),self.t('state'),self.t('detail')])
        self.records.setHorizontalHeaderLabels(['ID',self.t('completed'),self.t('state'),self.t('folder')])
        self.discovery_table.setHorizontalHeaderLabels([self.t('title'),self.t('published'),self.t('state'),'ID'])
        self.watch_table.setHorizontalHeaderLabels(['ID',self.t('state'),self.t('last_ok'),self.t('detail')])
        self.activity_tabs.setTabText(0,self.t('recent')); self.activity_tabs.setTabText(1,self.t('status_monitoring'))
        for task,(state,detail) in self.task_states.items(): self.paint_task(task,state,detail)
        self.render_previews(); self.refresh_following(); self.refresh_history()
        self.navigate(self.tabs.currentIndex()); self.check_dependencies(); self.save_settings()
        if self.analysis_tone:self.refresh_analysis_feedback()
    def update_audio_options(self,*args):
        audio_only=self.quality.currentIndex()==3
        self.audio_options.setVisible(audio_only)
        self.video_options.setVisible(not audio_only)
        hint=self.t('video_format_hint')
        if self.video_format.currentText()=='MKV':hint+=' '+self.t('mkv_cover_hint')
        self.video_format_hint.setText(hint)
        self.audio_format_hint.setText(self.t('audio_mp3_hint' if self.audio_format.currentIndex()==1 else 'audio_original_hint'))
        parent=self.quality.parentWidget()
        parent.setMinimumHeight(430 if audio_only else 440 if self.video_format.currentText()=='MKV' else 390)
    def update_destination(self):
        self.destination.setText(self.folder.text()); self.destination.setToolTip(self.folder.text())
    def update_actions(self):
        busy=self.busy()
        self.parse_button.setEnabled(bool(self.urls.toPlainText().strip()) and not busy)
        self.start.setEnabled(bool(self.selected_previews()) and not busy)
        self.export_mp3_button.setEnabled(not busy)
        self.export_video_button.setEnabled(not busy)
        selected=next((task for task,row in self.task_rows.items() if row==self.queue.currentRow()),None)
        retryable=selected is not None and self.task_states[selected][0] in ('failed','cancelled','interrupted','waiting')
        self.retry.setEnabled(not busy and retryable)
    def paste_links(self):
        value=QApplication.clipboard().text().strip()
        if value:
            existing=self.urls.toPlainText().strip()
            self.urls.setPlainText((existing+'\n' if existing else '')+value)
    def save_settings(self):
        if not hasattr(self,'deno'): return
        self.config = dict(language=self.language.currentIndex(),folder=self.folder.text(),cookie=self.cookie.text(),deno=self.deno.text(),video_format=self.video_format.currentText().lower(),quality=max(0,self.quality.currentIndex()),audio_format=max(0,self.audio_format.currentIndex()),daily=self.daily.isChecked() if hasattr(self,'daily') else False)
        temp = self.data / 'settings.tmp'; temp.write_text(json.dumps(self.config,ensure_ascii=False),encoding='utf-8'); temp.replace(self.data / 'settings.json')
    def pick_path(self,kind,initial,selected):
        # Explicit in-process dialog avoids Windows shell/COM dialog hangs.
        if self.path_dialog is not None:
            self.path_dialog.raise_(); self.path_dialog.activateWindow(); return self.path_dialog
        dialog=QFileDialog(self)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog,True)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setWindowTitle(self.t('choose_folder' if kind=='folder' else 'choose_file'))
        if kind=='folder':
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly,True)
        else: dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        candidate=Path(initial).expanduser() if initial.strip() else Path.home()
        if candidate.is_file(): candidate=candidate.parent
        while not candidate.is_dir() and candidate!=candidate.parent: candidate=candidate.parent
        dialog.setDirectory(str(candidate if candidate.is_dir() else Path.home()))
        dialog.setLabelText(QFileDialog.DialogLabel.LookIn,self.t('location'))
        dialog.setLabelText(QFileDialog.DialogLabel.FileType,self.t('file_type'))
        dialog.setLabelText(QFileDialog.DialogLabel.Reject,self.t('dismiss'))
        if kind=='folder':
            dialog.setLabelText(QFileDialog.DialogLabel.FileName,self.t('folder_name'))
            dialog.setLabelText(QFileDialog.DialogLabel.Accept,self.t('choose_folder'))
        dialog.setMinimumSize(760,500)
        dialog.filesSelected.connect(lambda paths:selected(paths[0]) if paths else None)
        dialog.finished.connect(lambda result:self.release_picker(dialog))
        self.path_dialog=dialog
        dialog.open()
        return dialog
    def release_picker(self,dialog):
        if self.path_dialog is dialog:self.path_dialog=None
        dialog.deleteLater()
    def choose(self,field,kind):
        def chosen(path):
            if kind=='folder' and not Path(path).is_dir():
                self.settings_feedback.setText(self.t('path_invalid')); return
            field.setText(path); self.save_settings()
            self.settings_feedback.setText(self.t('folder_saved') if kind=='folder' else '')
        return self.pick_path(kind,field.text(),chosen)
    def check_dependencies(self):
        if self.deno.text() and Path(self.deno.text()).is_file():
            os.environ['PATH'] = str(Path(self.deno.text()).parent) + os.pathsep + os.environ['PATH']
        result = dependencies()
        self.dependency_summary.setText('  ·  '.join(f"{key}: {self.t('available' if value else 'missing')}" for key,value in result.items()))
        self.dependency_text.setPlainText('\n'.join(f'{key}: {value or "MISSING"}' for key,value in result.items()) + '\n\nhttps://github.com/yt-dlp/yt-dlp#dependencies\nhttps://ffmpeg.org/download.html\nhttps://deno.com/')
    def update_source_prompt(self):
        web = bool(self.source_mode.currentIndex())
        self.urls.setPlaceholderText(self.t('web_input' if web else 'input'))
        self.link_hint.setVisible(not web)

    def source_changed(self):
        self.update_source_prompt()
        self.invalidate()

    def selected_previews(self):
        return [info for info in self.previews if info.get('selected', True)]

    def invalidate(self):
        self.previews=[]; self.render_previews(); self.update_actions()
        if not self.analysis_active:self.analysis_tone=''; self.analysis_feedback.hide()
    def busy(self): return self.worker is not None and self.worker.isRunning()
    def launch(self,jobs,analyzing=False):
        if self.busy(): return
        self.check_dependencies(); self.save_settings()
        if analyzing:
            self.analysis_active=True; self.analysis_total=len(jobs); self.analysis_current=1
            self.analysis_failed=0; self.analysis_errors=[]; self.analysis_cancelled=False; self.analysis_started=time.monotonic()
            self.analysis_tone='running'; self.refresh_analysis_feedback(); self.analysis_clock.start()
            self.parse_button.setText(self.t('extracting'))
        self.worker = Worker(jobs,self.cookie.text().strip(),analyzing,profiles={task:self.job_options.get(task,{}) for task,*_ in jobs}, web=analyzing and bool(self.source_mode.currentIndex()))
        self.worker.event.connect(self.on_event); self.worker.parsed.connect(self.on_parsed); self.worker.success.connect(self.completed); self.worker.finished.connect(self.finished)
        for widget in (self.parse_button,self.start,self.retry,self.urls,self.source_mode,self.folder,self.cookie,self.deno,self.quality,self.audio_format,self.video_format): widget.setEnabled(False)
        self.paste_button.setEnabled(False); self.destination_button.setEnabled(False); self.folder_browse.setEnabled(False)
        self.cancel.setEnabled(True); self.worker.start()
        if not analyzing:QTimer.singleShot(0,lambda:self.download_scroll.ensureWidgetVisible(self.queue,0,20))
    def analyze(self):
        if self.busy():return
        self.invalidate(); urls=[]; seen=set()
        try:
            for line in self.urls.toPlainText().splitlines():
                if not line.strip(): continue
                if self.source_mode.currentIndex():
                    url = doda.page_url(line)
                else:
                    url = 'https://www.youtube.com/watch?v=' + video_id(line)
                if url not in seen:
                    urls.append(url)
                    seen.add(url)
        except ValueError:
            self.analysis_tone='invalid'; self.refresh_analysis_feedback(); return
        self.launch([(-index-1,url,'','') for index,url in enumerate(urls)],True) if urls else None
    def analysis_error_key(self,message):
        text=str(message).lower()
        if any(term in text for term in ('failed to resolve','getaddrinfo','name resolution','nodename nor servname')):return 'parse_dns'
        if 'timed out' in text or 'timeout' in text:return 'parse_timeout'
        if any(term in text for term in ('sign in','login','private video','members-only','authentication','confirm your age')):return 'parse_auth'
        if any(term in text for term in ('no module named','not installed','no such file','ffmpeg not found','cookie file does not exist')):return 'parse_dependency'
        if any(term in text for term in ('connection','network','proxy','http error 403','http error 429')):return 'parse_network'
        return 'parse_other'
    def refresh_analysis_feedback(self):
        tone=self.analysis_tone
        if not tone:self.analysis_feedback.hide(); return
        detail=''
        if self.analysis_active:
            seconds=max(0,int(time.monotonic()-self.analysis_started))
            text=self.t('parse_cancelling') if self.analysis_cancelled else self.t('parse_running').format(current=self.analysis_current,total=self.analysis_total,seconds=seconds)
            if self.analysis_errors:detail=self.t(self.analysis_errors[-1])
            elif seconds>=30:detail=self.t('parse_waiting')
            color='running'
        elif tone=='invalid':text=self.t('web_invalid' if self.source_mode.currentIndex() else 'parse_invalid'); color='error'
        elif tone=='cancelled':text=self.t('parse_cancelled'); color='warning'
        elif tone=='success':text=self.t('parse_success').format(count=len(self.previews)); color='success'
        elif tone=='warning':
            text=self.t('parse_partial').format(count=len(self.previews),failed=self.analysis_failed); color='warning'
            detail=self.t(self.analysis_errors[-1]) if self.analysis_errors else ''
        else:
            text=self.t('parse_failure'); color='error'
            detail=self.t(self.analysis_errors[-1]) if self.analysis_errors else self.t('parse_other')
        self.analysis_message.setText(text); self.analysis_detail.setText(detail); self.analysis_detail.setVisible(bool(detail))
        self.analysis_feedback.setProperty('tone',color)
        self.analysis_feedback.style().unpolish(self.analysis_feedback); self.analysis_feedback.style().polish(self.analysis_feedback)
        self.analysis_progress.setVisible(self.analysis_active)
        self.analysis_cancel.setVisible(self.analysis_active); self.analysis_cancel.setEnabled(not self.analysis_cancelled)
        self.analysis_retry.setVisible(not self.analysis_active and tone in ('error','warning','cancelled'))
        self.analysis_log.setVisible(tone in ('error','warning') or bool(self.analysis_errors))
        self.analysis_feedback.show()
    def on_parsed(self,info):
        self.previews.append(info); self.render_previews(); self.update_actions()
    def render_previews(self):
        while self.preview_layout.count()>1:
            item=self.preview_layout.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.preview_cards=[]
        self.preview_count.setText(str(len(self.previews)))
        self.preview_stack.setCurrentIndex(1 if self.previews else 0)
        for info in self.previews:
            card=QWidget(); row=QHBoxLayout(card); row.setContentsMargins(0,0,0,0); row.setSpacing(16)
            cover=QLabel('▶'); cover.setObjectName('thumbnail'); cover.setFixedSize(156,96); cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap=QPixmap()
            if info.get('thumbnail_bytes') and pixmap.loadFromData(info['thumbnail_bytes']): cover.setPixmap(pixmap.scaled(156,96,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            row.addWidget(cover,0,Qt.AlignmentFlag.AlignTop); details=QVBoxLayout(); details.setSpacing(8)
            if info.get('source') == 'doda':
                choice = QCheckBox(self.t('select_lesson'))
                choice.setAccessibleName(f"{self.t('select_lesson')} · {info['title']}")
                choice.setChecked(info['selected'])
                choice.toggled.connect(lambda checked, lesson=info: self.select_lesson(lesson, checked))
                details.addWidget(choice)
            title=QLabel(info.get('title') or self.t('unknown')); title.setObjectName('videoTitle'); title.setTextFormat(Qt.TextFormat.PlainText); title.setWordWrap(True); details.addWidget(title)
            author_row=QHBoxLayout(); author=QLabel(info.get('channel') or self.t('unknown')); author.setTextFormat(Qt.TextFormat.PlainText); author.setWordWrap(True); author_row.addWidget(author,1)
            identity=info.get('channel_id')
            if identity:
                followed=any(item[0]==identity for item in self.monitor.channels())
                follow=QPushButton(self.t('followed' if followed else 'follow_creator')); follow.setObjectName('quiet'); follow.setEnabled(not followed)
                follow.clicked.connect(lambda checked=False,info=info:self.follow_one(info)); author_row.addWidget(follow)
            details.addLayout(author_row)
            date=info.get('upload_date') or self.t('unknown')
            if len(date)==8 and date.isdigit():date=f'{date[:4]}-{date[4:6]}-{date[6:]}'
            duration=info.get('duration'); duration=f'{int(duration)//3600:02}:{int(duration)%3600//60:02}:{int(duration)%60:02}' if duration is not None else self.t('unknown')
            heights=', '.join(str(height)+'p' for height in info.get('heights',[])) or self.t('unknown')
            if info.get('source') != 'doda':
                meta=QLabel(f'{date}  ·  {duration}\n{heights}'); meta.setObjectName('muted'); meta.setWordWrap(True); details.addWidget(meta)
            details.addStretch()
            row.addLayout(details,1); self.preview_layout.insertWidget(self.preview_layout.count()-1,card)
            self.preview_cards.append(card)
    def select_lesson(self, info, checked):
        info['selected'] = checked
        self.update_actions()

    def follow_one(self,info):
        self.monitor.follow(info['channel_id'],info.get('channel') or info['channel_id'])
        self.refresh_following(); self.render_previews()
    def begin(self):
        if self.busy(): return
        selected = self.selected_previews()
        if not selected: QMessageBox.information(self,APP_NAME,self.t('not_ready')); return
        preset=('best','1080','720','audio')[self.quality.currentIndex()]
        if preset=='audio' and self.audio_format.currentIndex()==1:preset='audio_mp3'
        jobs=[]
        for info in selected:
            if self.history.contains(info['id']) and QMessageBox.question(self,APP_NAME,info['id']+'\n'+self.t('duplicate')) != QMessageBox.StandardButton.Yes: continue
            settings = {'video_format': self.video_format.currentText().lower()}
            if info.get('source') == 'doda':
                settings.update(source='doda', episode=info['episode'])
            task=self.history.create_task(info['id'],info['url'],self.folder.text(),preset,settings)
            self.add_task(task,info['id'],info['url'],self.folder.text(),preset,'waiting',''); jobs.append((task,info['url'],self.folder.text(),preset))
        if jobs: self.launch(jobs)
    def add_task(self,task,identity,url,folder,preset,state,detail):
        self.job_options[task]=self.history.task_options(task)
        row=self.queue.rowCount(); self.queue.insertRow(row); self.task_rows[task]=row; self.job_data[task]=(url,folder,preset)
        title=next((info.get('title') for info in self.previews if info['id']==identity),identity)
        item=QTableWidgetItem(title); item.setToolTip(identity); self.queue.setItem(row,0,item)
        self.queue.setItem(row,1,QTableWidgetItem(self.t(preset))); self.paint_task(task,state,detail)
        self.queue_stack.setCurrentIndex(1); self.queue_count.setText(str(self.queue.rowCount()))
        self.queue.setCurrentCell(row,0)
        QTimer.singleShot(0,self.queue.scrollToBottom)
    def paint_task(self,task,state,detail):
        self.task_states[task]=(state,detail); row=self.task_rows[task]
        preset=self.job_data[task][2];label=self.t(preset)
        if preset not in ('audio','audio_mp3','local_mp3') and self.job_options.get(task,{}).get('video_format'):label+=' · '+self.job_options[task]['video_format'].upper()
        self.queue.setItem(row,1,QTableWidgetItem(label))
        self.queue.setItem(row,2,QTableWidgetItem(self.t('audio_stage' if state=='audio' else state))); self.queue.setItem(row,3,QTableWidgetItem(detail))
    def on_event(self,task,event):
        state=event['state']; detail=event.get('detail','')
        if self.analysis_active and task<0:
            if state=='extracting':self.analysis_current=abs(task)
            elif state=='failed':
                self.analysis_failed+=1; self.analysis_errors.append(self.analysis_error_key(detail))
            elif state=='cancelled':self.analysis_cancelled=True
            self.refresh_analysis_feedback()
        if state=='failed':
            lower=detail.lower()
            key='cover_failure' if 'cover' in lower else 'container_failure' if 'selected ' in lower and ('mp4' in lower or 'mkv' in lower) else 'space_failure' if 'space' in lower else 'help'
            detail=self.t(key)+'\n'+detail
        if 'done' in event:
            now=time.monotonic()
            if now-self.last_progress.get(task,0)<0.3: return
            self.last_progress[task]=now
        if 'done' in event:
            detail=f"{event['done']/1024**2:.1f} MB"
            if event.get('total'): detail+=f" / {'≈' if event.get('estimated') else ''}{event['total']/1024**2:.1f} MB"
            if event.get('speed'): detail+=f" · {event['speed']/1024**2:.1f} MB/s"
        if task in self.task_rows and state not in ('notice','error'):
            self.paint_task(task,state,detail)
            self.history.update_task(task,state,detail)
        if 'done' not in event:
            line=f'{task} | {state} | {redact(detail)}'; self.log.insertPlainText(line+'\n')
            with (self.data/'diagnostic.log').open('a',encoding='utf-8') as handle: handle.write(line+'\n')
    def completed(self,task,result):
        if not result.get('id'):result['id']=self.queue.item(self.task_rows[task],0).toolTip()
        state='warning' if result['warnings'] else 'completed'
        self.history.save(result['id'],result['path'],state)
        self.history.save_details(result['id'],result['probe'])
        video=next((stream for stream in result['probe'].get('streams',[]) if stream.get('codec_type')=='video' and not stream.get('disposition',{}).get('attached_pic')),None)
        summary=Path(result['path']).suffix[1:].upper()
        if video:summary+=f" · {video.get('width')}×{video.get('height')}"
        if result.get('cover_verified',not result['warnings']):summary+=' · '+self.t('cover_verified')
        detail='\n'.join([summary,*result['warnings'],result['path']])
        self.on_event(task,{'state':state,'detail':detail}); self.refresh_history()
    def finished(self):
        if self.analysis_active:
            self.analysis_active=False; self.analysis_clock.stop()
            self.analysis_tone='cancelled' if self.analysis_cancelled else ('warning' if self.analysis_failed and self.previews else 'error' if self.analysis_failed else 'success')
            self.refresh_analysis_feedback(); self.parse_button.setText(self.t('parse'))
        for widget in (self.parse_button,self.start,self.retry,self.urls,self.source_mode,self.folder,self.cookie,self.deno,self.quality,self.audio_format,self.video_format): widget.setEnabled(True)
        self.save_settings()
        self.cancel.setEnabled(False); self.paste_button.setEnabled(True); self.destination_button.setEnabled(True); self.folder_browse.setEnabled(True); self.update_actions()
    def stop(self):
        if self.busy():
            self.worker.requestInterruption()
            if self.analysis_active:self.analysis_cancelled=True; self.refresh_analysis_feedback()
    def retry_task(self):
        row=self.queue.currentRow()
        for task,index in self.task_rows.items():
            if index==row and self.task_states[task][0] in ('failed','cancelled','interrupted','waiting'):
                url,folder,preset=self.job_data[task]; self.launch([(task,url,folder,preset)]); return
    def refresh_history(self):
        self.records.setRowCount(0)
        for record in self.history.rows():
            row=self.records.rowCount(); self.records.insertRow(row)
            for col,value in enumerate(record): self.records.setItem(row,col,QTableWidgetItem(str(value)))
        # DB order: identity, date, path, status; display status before path.
        for row in range(self.records.rowCount()):
            path=self.records.item(row,2).text(); status=self.records.item(row,3).text()
            self.records.setItem(row,2,QTableWidgetItem(self.t(status))); self.records.setItem(row,3,QTableWidgetItem(path))
    def export_selected_audio(self):
        if self.busy():return
        row=self.records.currentRow()
        if row<0:QMessageBox.information(self,APP_NAME,self.t('select_audio'));return
        identity=self.records.item(row,0).text();source=Path(self.records.item(row,3).text())
        if not source.is_file():QMessageBox.information(self,APP_NAME,self.t('moved'));return
        if source.suffix.lower() not in ('.webm','.opus','.m4a','.mp3','.ogg','.flac','.mka'):
            QMessageBox.information(self,APP_NAME,self.t('select_audio'));return
        def chosen(folder):
            if self.busy():return
            task=self.history.create_task(identity,str(source),folder,'local_mp3')
            self.add_task(task,identity,str(source),folder,'local_mp3','waiting','')
            self.navigate(0);self.launch([(task,str(source),folder,'local_mp3')])
        self.pick_path('folder',str(source.parent),chosen)
    def export_selected_video(self):
        if self.busy():return
        row=self.records.currentRow()
        if row<0:QMessageBox.information(self,APP_NAME,self.t('select_video'));return
        identity=self.records.item(row,0).text();source=Path(self.records.item(row,3).text())
        if not source.is_file():QMessageBox.information(self,APP_NAME,self.t('moved'));return
        if source.suffix.lower() not in ('.mp4','.mkv','.webm'):
            QMessageBox.information(self,APP_NAME,self.t('select_video'));return
        container,accepted=QInputDialog.getItem(self,self.t('export_video'),self.t('video_format'),['MP4','MKV'],0,False)
        if not accepted:return
        def chosen(folder):
            if self.busy():return
            task=self.history.create_task(identity,str(source),folder,'local_video',{'video_format':container.lower()})
            self.add_task(task,identity,str(source),folder,'local_video','waiting','')
            self.navigate(0);self.launch([(task,str(source),folder,'local_video')])
        self.pick_path('folder',str(source.parent),chosen)
    def import_history(self):
        self.pick_path('folder',self.folder.text(),self.confirm_import)
    def confirm_import(self,folder):
        candidates={key:path for key,path in import_candidates(folder).items() if not self.history.contains(key)}
        if not candidates: QMessageBox.information(self,APP_NAME,'0'); return
        if QMessageBox.question(self,APP_NAME,self.t('import_confirm')+'\n'+'\n'.join(candidates))==QMessageBox.StandardButton.Yes:
            for key,path in candidates.items(): self.history.save(key,path,'imported')
            self.refresh_history()
    def open_history(self,folder):
        row=self.records.currentRow()
        if row<0:return
        path=Path(self.records.item(row,3).text())
        if not path.exists(): QMessageBox.information(self,APP_NAME,self.t('moved')); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if folder else path)))
    def fill_table(self,table,rows):
        table.setRowCount(0)
        for values in rows:
            row=table.rowCount(); table.insertRow(row)
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value or '')); item.setToolTip(str(value or '')); table.setItem(row,col,item)
    def selected_creators(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.channels_list.selectedItems() if item.data(Qt.ItemDataRole.UserRole) is not None]
    def manage_groups(self):
        dialog=GroupManager(self.monitor,self.t,self)
        dialog.exec();self.refresh_following()
    def assign_groups(self):
        selected=self.selected_creators()
        if not selected:return
        if not self.monitor.groups():
            self.manage_groups()
            if not self.monitor.groups():return
        dialog=MembershipDialog(self.monitor,selected,self.t,self)
        dialog.exec();self.refresh_following()
    def refresh_following(self,*args):
        selected=set(self.selected_creators())
        group=self.group_filter.currentData()
        self.group_filter.blockSignals(True);self.group_filter.clear()
        self.group_filter.addItem(self.t('all_groups'),None);self.group_filter.addItem(self.t('ungrouped'),-1)
        for identity,name,count in self.monitor.groups():self.group_filter.addItem(f'{name} ({count})',identity)
        found=self.group_filter.findData(group)
        self.group_filter.setCurrentIndex(max(0,found));self.group_filter.setToolTip(self.group_filter.currentText());self.group_filter.blockSignals(False)
        records=self.monitor.filtered_channels(self.group_filter.currentData(),self.creator_search.text())
        self.filtered_creator_ids=[record[0] for record in records]
        self.channels_list.blockSignals(True);self.channels_list.clear()
        all_item=QListWidgetItem(self.t('all_creators'));all_item.setData(Qt.ItemDataRole.UserRole,None);self.channels_list.addItem(all_item)
        memberships=self.monitor.membership_map();names={row[0]:row[1] for row in self.monitor.groups()}
        for record in records:
            item=QListWidgetItem(record[1]);item.setData(Qt.ItemDataRole.UserRole,record[0]);self.channels_list.addItem(item)
            group_names=', '.join(names[group] for group in sorted(memberships.get(record[0],set()))) or self.t('ungrouped')
            item.setToolTip(record[0]+'\n'+group_names)
            if record[0] in selected:item.setSelected(True)
        if not self.channels_list.selectedItems():self.channels_list.setCurrentRow(0)
        self.channels_list.blockSignals(False)
        total=len(self.monitor.channels());count_text=str(total) if len(records)==total else f'{len(records)}/{total}'
        self.creator_count.setText(count_text);self.creator_count.setFixedWidth(max(38,self.creator_count.fontMetrics().horizontalAdvance(count_text)+22));self.creator_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.refresh_discoveries()
        self.fill_table(self.watch_table,[(r[0],self.t(r[1]),r[3],r[5]) for r in self.monitor.watched()])
    def refresh_discoveries(self,*args):
        selected=self.selected_creators()
        if selected:
            self.channels_list.blockSignals(True)
            for item in self.channels_list.selectedItems():
                if item.data(Qt.ItemDataRole.UserRole) is None:item.setSelected(False)
            self.channels_list.blockSignals(False)
        self.group_assign_button.setEnabled(bool(selected))
        identities=selected or getattr(self,'filtered_creator_ids',[])
        if len(selected)==1:
            record=next(record for record in self.monitor.channels() if record[0]==selected[0])
            self.creator_heading.setText(record[1])
            self.channel_status.setText(self.t('last_ok')+': '+(record[2] or self.t('not_checked'))+'\n'+(record[4] or ''))
        else:
            self.creator_heading.setText(self.t('all_creators'));self.channel_status.setText('' if identities else self.t('no_creators_match'))
        if identities:
            placeholders=','.join('?' for _ in identities)
            rows=self.history.db.execute('SELECT DISTINCT video,title,published,is_new FROM discoveries WHERE channel IN ('+placeholders+') ORDER BY published DESC',identities).fetchall()
        else:rows=[]
        self.fill_table(self.discovery_table,[(r[1],r[2][:10],self.t('new' if r[3] else 'baseline'),r[0]) for r in rows])
        self.discovery_stack.setCurrentIndex(1 if rows else 0);self.update_discovery_action()
    def update_discovery_action(self):
        self.discovery_button.setEnabled(self.discovery_table.currentRow()>=0 and not self.busy())
    def watch_selected(self):
        row=self.records.currentRow()
        if row>=0: self.monitor.watch(self.records.item(row,0).text()); self.refresh_following()
    def check_monitor(self):
        if self.monitor_worker and self.monitor_worker.isRunning(): return
        self.monitor_worker=MonitorWorker([r[0] for r in self.monitor.channels()],[r[0] for r in self.monitor.watched()],self.cookie.text().strip())
        self.monitor_worker.feed.connect(self.feed_result); self.monitor_worker.status.connect(self.status_result)
        self.monitor_worker.finished.connect(lambda:self.monitor_finished())
        self.check_follow.setEnabled(False); self.check_follow.setText(self.t('checking')); self.monitor_worker.start()
    def monitor_finished(self):
        self.check_follow.setEnabled(True); self.check_follow.setText(self.t('check_now'))
    def feed_result(self,identity,name,entries,error):
        self.monitor.apply_feed(identity,name,entries,error); self.refresh_following()
    def status_result(self,identity,ok,error,explicit):
        self.monitor.apply_status(identity,ok,error,explicit); self.refresh_following()
    def analyze_discovery(self):
        if self.busy(): return
        row=self.discovery_table.currentRow()
        if row>=0:
            identity=self.discovery_table.item(row,3).text(); self.source_mode.setCurrentIndex(0); self.urls.setPlainText('https://www.youtube.com/watch?v='+identity); self.navigate(0); self.analyze()
    def closeEvent(self,event):
        if self.monitor_worker and self.monitor_worker.isRunning(): self.monitor_worker.requestInterruption(); event.ignore(); return

        if self.busy(): self.stop(); event.ignore(); return
        self.save_settings(); QApplication.instance().removeTranslator(self.qt_translator); self.history.db.close(); event.accept()

def main():
    app=QApplication(sys.argv); window=Window(); window.show()
    sys.exit(app.exec())

if __name__=='__main__': main()
