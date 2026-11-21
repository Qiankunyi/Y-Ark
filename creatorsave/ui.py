"""Desktop presentation: primary workspaces and secondary utilities."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QPen, QColor, QPixmap
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,
    QGridLayout,QStackedWidget,QScrollArea,QTextEdit,QLineEdit,QComboBox,QListWidget,
    QTabWidget,QCheckBox,QProgressBar,QSizePolicy,QAbstractItemView,QHeaderView)
from .i18n import LANGUAGES

STYLE = '''
QWidget { font-family: "Microsoft YaHei UI"; font-size: 13px; color: #27364b; }
QMainWindow, #workspace { background: #f4f6fa; }
QLabel { background: transparent; }
#navSidebar { background: #142b37; border: none; }
#navSidebar QLabel { color: #92aeb9; }
#navSidebar #brand { color: #f0fcf9; font-size: 22px; font-weight: 700; }
#navSidebar #brandSub { font-size: 11px; color: #8ba8b2; }
#navSidebar QPushButton { text-align: left; background: transparent; color: #abc1ca; border: 0; border-radius: 9px; padding: 10px 15px; }
#navSidebar QPushButton:hover { background: #203e4b; color: white; }
#navSidebar QPushButton:checked { background: #244a56; color: #e5fff6; border-left: 3px solid #63ddbd; }
#navSidebar QPushButton[primaryNav="true"] { font-size: 16px; font-weight: 600; min-height: 35px; }
#navSidebar #navFoot { color: #8faab4; font-size: 11px; }
#pageTitle { font-size: 28px; font-weight: 700; color: #172c3e; }
#pageSubtitle, #muted { color: #718094; font-size: 12px; }
#sectionTitle { font-size: 16px; font-weight: 600; color: #21364b; }
#card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; }
#card QLabel { background: transparent; }
QLabel#step { color: #237e70; background: #e7f5f0; border: none; border-radius: 7px; font-weight: 700; }
QLabel#thumbnail { background: #edf3f5; color: #72929c; border-radius: 8px; font-size: 24px; }
#videoTitle { font-size: 15px; font-weight: 600; }
#emptyTitle { font-size: 15px; font-weight: 600; color: #677c8d; }
#emptyMark { font-size: 27px; color: #86a6ad; }
QLabel#count { background: #e8f0f3; color: #527583; border-radius: 9px; padding: 3px 9px; font-size: 11px; }
#feedback { color: #21766a; font-size: 12px; }
QPushButton { background: #ffffff; border: 1px solid #d8e1ea; border-radius: 7px; padding: 8px 13px; font-weight: 500; }
QPushButton:hover { background: #f0f6f6; border-color: #9bbdb9; }
QPushButton:pressed { background: #e0eeeb; }
QPushButton:disabled { color: #a8b4bf; background: #eff3f6; border-color: #e3e9ef; }
QPushButton#primary { background: #177965; color: white; border: 1px solid #177965; font-weight: 600; }
QPushButton#primary:hover { background: #116653; }
QPushButton#primary:disabled { background: #b7d5cc; border-color: #b7d5cc; color: #eff8f5; }
QPushButton#quiet { color: #577183; background: transparent; border: 0; padding: 6px 3px; }
QPushButton#quiet:hover { color: #126e5c; }
QLineEdit, QTextEdit, QComboBox { background: #fbfcfe; border: 1px solid #dce4ed; border-radius: 7px; padding: 8px; selection-background-color: #d5eee6; selection-color: #163f35; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #369780; }
QComboBox { min-height: 18px; padding-right: 24px; }
QComboBox QAbstractItemView { background: white; color: #27364b; selection-background-color: #d5eee6; selection-color: #163f35; padding: 4px; }
QTableWidget { background: white; alternate-background-color: #fafcfd; border: none; gridline-color: #edf1f5; selection-background-color: #e4f2ed; selection-color: #1d4d40; outline: none; }
QHeaderView { background: #f7f9fc; }
QHeaderView::section { background: #f7f9fc; color: #7c8998; border: none; border-bottom: 1px solid #e8edf2; padding: 10px 8px; font-size: 11px; text-align: left; }
QTableWidget::item { border: none; padding: 8px; }
QListWidget { background: white; border: none; outline: none; }
QListWidget::item { padding: 16px 10px; border-bottom: 1px solid #eff3f7; }
QListWidget::item:selected { background: #e8f5ef; color: #176a56; border-left: 3px solid #26977a; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: #c6d4dc; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: none; background: white; }
QTabBar::tab { padding: 10px 16px; background: transparent; color: #7b8998; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #19795f; border-bottom: 2px solid #26977a; }
QCheckBox { spacing: 8px; color: #677c8d; }
QMenu { background: #ffffff; color: #27364b; border: 1px solid #d6e0e9; border-radius: 6px; padding: 5px; }
QMenu::item { background: transparent; color: #27364b; padding: 7px 30px 7px 12px; border-radius: 4px; }
QMenu::item:selected { background: #dcefe8; color: #165c49; }
QMenu::item:disabled { color: #8796a6; background: transparent; }
QMenu::separator { height: 1px; background: #e5ebf1; margin: 5px 7px; }
QToolTip { background: #ffffff; color: #27364b; border: 1px solid #d6e0e9; padding: 5px; }
QFrame#analysisFeedback { background: #edf5fa; border: 1px solid #d4e6ef; border-radius: 8px; }
QFrame#analysisFeedback[tone="error"] { background: #fff3f0; border-color: #e9c5bd; }
QFrame#analysisFeedback[tone="success"] { background: #ecf7f1; border-color: #c4e3d4; }
QFrame#analysisFeedback[tone="warning"] { background: #fff8eb; border-color: #ebd8b2; }
QProgressBar#analysisProgress { background: #d8e7e6; border: none; border-radius: 3px; max-height: 6px; }
QProgressBar#analysisProgress::chunk { background: #258671; border-radius: 3px; }
QFileDialog { background: #f4f6fa; }
QFileDialog QTreeView,QFileDialog QListView { background: white; color: #27364b; border: 1px solid #dce4ed; selection-background-color: #d5eee6; selection-color: #163f35; }
'''

class WrappingLabel(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWordWrap(True)
    def fit_height(self):
        height=self.heightForWidth(max(80,self.width()))
        if height>0 and height!=self.minimumHeight():self.setMinimumHeight(height)
    def setText(self,text):
        super().setText(text);self.fit_height()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.fit_height()

def icon(kind):
    pix=QPixmap(24,24); pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#a9c7cf'),1.7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    if kind=='download':
        p.drawLine(12,3,12,15); p.drawLine(7,10,12,15); p.drawLine(12,15,17,10); p.drawLine(4,16,4,21); p.drawLine(4,21,20,21); p.drawLine(20,21,20,16)
    elif kind=='creators':
        p.drawEllipse(7,3,9,9); p.drawArc(4,12,16,15,0,180*16)
    elif kind=='history':
        p.drawEllipse(3,3,18,18); p.drawLine(12,6,12,12); p.drawLine(12,12,16,14)
    elif kind=='logs':
        p.drawRoundedRect(5,2,14,20,2,2)
        for y in (7,12,17): p.drawLine(8,y,16,y)
    else:
        p.drawEllipse(4,4,16,16); p.drawEllipse(9,9,6,6)
        for a,b,c,d in ((12,1,12,4),(12,20,12,23),(1,12,4,12),(20,12,23,12)): p.drawLine(a,b,c,d)
    p.end(); return QIcon(pix)

def build(window):
    w=window; w.text_bindings=[]
    def label(key,name=None):
        item=QLabel(); item.setWordWrap(True); item.setTextFormat(Qt.TextFormat.PlainText)
        if name:item.setObjectName(name)
        w.text_bindings.append((item,key)); return item
    def button(key,style=None):
        item=QPushButton()
        if style:item.setObjectName(style)
        w.text_bindings.append((item,key)); return item
    def card():
        frame=QFrame(); frame.setObjectName('card'); layout=QVBoxLayout(frame); layout.setContentsMargins(20,18,20,18); layout.setSpacing(14); return frame,layout
    def section(key): return label(key,'sectionTitle')
    central=QWidget(); w.setCentralWidget(central); shell=QHBoxLayout(central); shell.setContentsMargins(0,0,0,0); shell.setSpacing(0)
    sidebar=QFrame(); sidebar.setObjectName('navSidebar'); sidebar.setFixedWidth(216); side=QVBoxLayout(sidebar); side.setContentsMargins(18,28,18,22); side.setSpacing(8)
    brand=QLabel('Y-Ark'); brand.setObjectName('brand'); side.addWidget(brand)
    side.addWidget(label('brand_sub','brandSub')); side.addSpacing(30); side.addWidget(label('workspace','muted')); side.addSpacing(5)
    w.nav_buttons={}
    for index,key,kind in ((0,'download_page','download'),(4,'creators_page','creators')):
        item=button(key); item.setProperty('primaryNav',True); item.setIcon(icon(kind)); item.setIconSize(QSize(21,21)); item.setCheckable(True)
        item.clicked.connect(lambda checked=False,index=index:w.navigate(index)); side.addWidget(item); w.nav_buttons[index]=item
    side.addStretch(); side.addWidget(label('tools','muted')); side.addSpacing(5)
    for index,key,kind in ((1,'history','history'),(3,'logs','logs'),(2,'settings','settings')):
        item=button(key); item.setIcon(icon(kind)); item.setCheckable(True); item.clicked.connect(lambda checked=False,index=index:w.navigate(index)); side.addWidget(item); w.nav_buttons[index]=item
    side.addSpacing(18); side.addWidget(label('local_only','navFoot')); shell.addWidget(sidebar)
    workspace=QWidget(); workspace.setObjectName('workspace'); main=QVBoxLayout(workspace); main.setContentsMargins(30,27,30,24); main.setSpacing(22)
    heading=QHBoxLayout(); heading_text=QVBoxLayout(); heading_text.setSpacing(6)
    w.page_title=QLabel(); w.page_title.setObjectName('pageTitle'); w.page_subtitle=QLabel(); w.page_subtitle.setObjectName('pageSubtitle'); w.page_subtitle.setWordWrap(True)
    heading_text.addWidget(w.page_title); heading_text.addWidget(w.page_subtitle); heading.addLayout(heading_text,1)
    w.language=QComboBox(); w.language.addItems(LANGUAGES); w.language.setCurrentIndex(w.config.get('language',0)); w.language.setMinimumWidth(116); heading.addWidget(w.language,0,Qt.AlignmentFlag.AlignTop); main.addLayout(heading)
    w.tabs=QStackedWidget(); main.addWidget(w.tabs,1); shell.addWidget(workspace,1)
    w.pages=[]
    for index in range(5):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(18)
        if index in (0,2):
            scroller=QScrollArea(); scroller.setWidgetResizable(True); scroller.setWidget(page); w.tabs.addWidget(scroller)
            if index==0:w.download_scroll=scroller
            if index==0:page.setMinimumHeight(720)
        else:w.tabs.addWidget(page)
        w.pages.append(layout)
    dl,hist,settings,logs,follow=w.pages
    # Download intake is the first action. Confirmation and options appear together below.
    intake,inside=card(); inside.setSpacing(10); top=QHBoxLayout(); step=QLabel('01'); step.setObjectName('step'); step.setFixedSize(30,28); step.setAlignment(Qt.AlignmentFlag.AlignCenter); top.addWidget(step); top.addWidget(section('add_video')); top.addStretch(); inside.addLayout(top)
    w.urls=QTextEdit(); w.urls.setFixedHeight(64); w.urls.setAcceptRichText(False); inside.addWidget(w.urls)
    row=QHBoxLayout(); w.link_hint=label('single_links','muted'); row.addWidget(w.link_hint,1)
    w.source_mode=QComboBox(); w.source_mode.addItems(['YouTube', '']); row.addWidget(w.source_mode)
    w.paste_button=button('paste','quiet'); w.parse_button=button('parse','primary'); row.addWidget(w.paste_button); row.addWidget(w.parse_button); inside.addLayout(row)
    w.analysis_feedback=QFrame(); w.analysis_feedback.setObjectName('analysisFeedback'); feedback=QVBoxLayout(w.analysis_feedback); feedback.setContentsMargins(12,10,12,10); feedback.setSpacing(6)
    status_row=QHBoxLayout(); w.analysis_message=QLabel(); w.analysis_message.setTextFormat(Qt.TextFormat.PlainText); w.analysis_message.setWordWrap(True); status_row.addWidget(w.analysis_message,1)
    w.analysis_progress=QProgressBar(); w.analysis_progress.setObjectName('analysisProgress'); w.analysis_progress.setRange(0,0); w.analysis_progress.setTextVisible(False); w.analysis_progress.setFixedWidth(84); status_row.addWidget(w.analysis_progress); feedback.addLayout(status_row)
    w.analysis_detail=QLabel(); w.analysis_detail.setTextFormat(Qt.TextFormat.PlainText); w.analysis_detail.setWordWrap(True); feedback.addWidget(w.analysis_detail)
    actions=QHBoxLayout(); w.analysis_cancel=button('parse_cancel','quiet'); w.analysis_retry=button('parse_retry','quiet'); w.analysis_log=button('view_log','quiet'); actions.addWidget(w.analysis_cancel); actions.addWidget(w.analysis_retry); actions.addWidget(w.analysis_log); actions.addStretch(); feedback.addLayout(actions)
    w.analysis_feedback.hide(); inside.addWidget(w.analysis_feedback); dl.addWidget(intake)
    middle=QHBoxLayout(); middle.setSpacing(18)
    preview,content=card(); head=QHBoxLayout(); head.addWidget(section('video_preview')); head.addStretch(); w.preview_count=QLabel(); w.preview_count.setObjectName('count'); head.addWidget(w.preview_count); content.addLayout(head)
    w.preview_stack=QStackedWidget(); empty=QWidget(); empty_layout=QVBoxLayout(empty); empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mark=QLabel('↓'); mark.setObjectName('emptyMark'); mark.setAlignment(Qt.AlignmentFlag.AlignCenter); empty_layout.addWidget(mark)
    title=label('preview_empty','emptyTitle'); title.setAlignment(Qt.AlignmentFlag.AlignCenter); empty_layout.addWidget(title)
    caption=label('preview_hint','muted'); caption.setAlignment(Qt.AlignmentFlag.AlignCenter); empty_layout.addWidget(caption)
    w.preview_stack.addWidget(empty); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumHeight(160)
    w.preview_content=QWidget(); w.preview_layout=QVBoxLayout(w.preview_content); w.preview_layout.setContentsMargins(0,0,0,0); w.preview_layout.setSpacing(16); w.preview_layout.addStretch(); scroll.setWidget(w.preview_content); w.preview_stack.addWidget(scroll); content.addWidget(w.preview_stack,1); middle.addWidget(preview,1)
    options,opts=card(); options.setFixedWidth(282); options.setMinimumHeight(278); opts.addWidget(section('save_options')); opts.addWidget(label('media_mode','muted')); w.quality=QComboBox(); opts.addWidget(w.quality)
    w.video_options=QWidget(); video_layout=QVBoxLayout(w.video_options); video_layout.setContentsMargins(0,0,0,0); video_layout.setSpacing(8)
    video_layout.addWidget(label('video_format','muted')); w.video_format=QComboBox(); w.video_format.addItems(['MP4','MKV']); video_layout.addWidget(w.video_format)
    w.video_format_hint=WrappingLabel(); w.video_format_hint.setObjectName('muted'); w.video_format_hint.setWordWrap(True); video_layout.addWidget(w.video_format_hint); opts.addWidget(w.video_options)
    w.audio_options=QWidget(); audio_layout=QVBoxLayout(w.audio_options); audio_layout.setContentsMargins(0,0,0,0); audio_layout.setSpacing(8)
    audio_layout.addWidget(label('audio_format','muted')); w.audio_format=QComboBox(); audio_layout.addWidget(w.audio_format)
    w.audio_format_hint=WrappingLabel(); w.audio_format_hint.setObjectName('muted'); w.audio_format_hint.setWordWrap(True); audio_layout.addWidget(w.audio_format_hint)
    opts.addWidget(w.audio_options); w.audio_options.hide()
    opts.addWidget(label('folder','muted')); w.destination=QLabel(); w.destination.setWordWrap(True); w.destination.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); opts.addWidget(w.destination)
    w.destination_button=button('change_folder','quiet'); opts.addWidget(w.destination_button,0,Qt.AlignmentFlag.AlignLeft); opts.addStretch()
    w.start=button('enqueue','primary'); w.start.setMinimumHeight(40); w.start.setEnabled(False); opts.addWidget(w.start); middle.addWidget(options); dl.addLayout(middle,3)
    queue_card,q=card(); row=QHBoxLayout(); row.addWidget(section('queue')); w.queue_count=QLabel('0'); w.queue_count.setObjectName('count'); row.addWidget(w.queue_count); row.addStretch(); w.retry=button('retry','quiet'); w.cancel=button('cancel','quiet'); w.cancel.setEnabled(False); row.addWidget(w.retry); row.addWidget(w.cancel); q.addLayout(row)
    w.queue_stack=QStackedWidget(); queue_empty=label('queue_empty','muted'); queue_empty.setAlignment(Qt.AlignmentFlag.AlignCenter); w.queue_stack.addWidget(queue_empty)
    w.queue=w.table(4); w.queue_stack.addWidget(w.queue); w.queue_stack.setMinimumHeight(96); q.addWidget(w.queue_stack); dl.addWidget(queue_card,2)
    # History and diagnostics are utility pages, reachable from the bottom of the sidebar.
    history_card,h=card(); row=QHBoxLayout(); row.addWidget(section('download_records')); row.addStretch(); w.import_button=button('import'); row.addWidget(w.import_button); h.addLayout(row)
    exports=QHBoxLayout(); w.export_mp3_button=button('export_mp3'); w.export_video_button=button('export_video'); exports.addWidget(w.export_mp3_button); exports.addWidget(w.export_video_button); exports.addStretch(); h.addLayout(exports)
    w.records=w.table(4); h.addWidget(w.records,1); row=QHBoxLayout(); w.open_button=button('open'); w.folder_button=button('open_folder'); w.watch_button=button('monitor_video')
    for item in (w.open_button,w.folder_button,w.watch_button):row.addWidget(item)
    row.addStretch(); h.addLayout(row); hist.addWidget(history_card,1)
    storage,body=card(); body.addWidget(section('storage')); body.addWidget(label('storage_hint','muted'))
    w.folder=QLineEdit(w.config.get('folder',str(Path.home()/'Downloads'))); w.folder.setMinimumWidth(200)
    w.folder_browse=button('choose_folder'); row=QHBoxLayout(); row.addWidget(w.folder,1); row.addWidget(w.folder_browse); body.addLayout(row)
    w.settings_feedback=QLabel(); w.settings_feedback.setObjectName('feedback'); w.settings_feedback.setWordWrap(True); body.addWidget(w.settings_feedback); settings.addWidget(storage)
    filenames,body=card(); body.addWidget(section('filename_date'))
    w.youtube_filename_date=QCheckBox(); w.youtube_filename_date.setChecked(w.config.get('youtube_filename_date', True))
    w.web_filename_date=QCheckBox(); w.web_filename_date.setChecked(w.config.get('web_filename_date', False))
    body.addWidget(w.youtube_filename_date); body.addWidget(w.web_filename_date); settings.addWidget(filenames)
    advanced,body=card(); w.advanced_toggle=button('advanced','quiet'); w.advanced_toggle.setCheckable(True); body.addWidget(w.advanced_toggle,0,Qt.AlignmentFlag.AlignLeft)
    w.advanced_panel=QWidget(); a=QVBoxLayout(w.advanced_panel); a.setContentsMargins(0,4,0,0); a.setSpacing(12); a.addWidget(label('advanced_hint','muted'))
    w.cookie=QLineEdit(w.config.get('cookie','')); w.cookie.setEchoMode(QLineEdit.EchoMode.Password); w.deno=QLineEdit(w.config.get('deno',''))
    w.file_browse_buttons={}
    for field,key in ((w.cookie,'cookie'),(w.deno,'deno')):
        a.addWidget(label(key,'muted')); row=QHBoxLayout(); row.addWidget(field,1); pick=button('choose_file'); row.addWidget(pick); a.addLayout(row); w.file_browse_buttons[key]=pick
    w.advanced_panel.hide(); w.advanced_toggle.toggled.connect(w.advanced_panel.setVisible); body.addWidget(w.advanced_panel); settings.addWidget(advanced)
    deps,body=card(); row=QHBoxLayout(); row.addWidget(section('environment')); row.addStretch(); w.check_button=button('check'); row.addWidget(w.check_button); body.addLayout(row)
    w.dependency_summary=QLabel(); w.dependency_summary.setWordWrap(True); body.addWidget(w.dependency_summary); w.dependency_text=QTextEdit(); w.dependency_text.setReadOnly(True); w.dependency_text.setMaximumHeight(150); w.dependency_text.hide(); w.dependency_toggle=button('environment_details','quiet'); w.dependency_toggle.setCheckable(True); w.dependency_toggle.toggled.connect(w.dependency_text.setVisible); body.addWidget(w.dependency_toggle,0,Qt.AlignmentFlag.AlignLeft); body.addWidget(w.dependency_text); settings.addWidget(deps); settings.addStretch()
    log_card,body=card(); row=QHBoxLayout(); row.addWidget(section('logs')); row.addStretch(); w.copy_button=button('copy'); row.addWidget(w.copy_button); body.addLayout(row); w.log=QTextEdit(); w.log.setReadOnly(True); body.addWidget(w.log); logs.addWidget(log_card)
    # Creator list on the left, discoveries and monitored status on the right.
    top=QHBoxLayout(); w.daily=QCheckBox(); w.daily.setChecked(w.config.get('daily',False)); top.addWidget(w.daily,1); w.check_follow=button('check_now','primary'); top.addWidget(w.check_follow); follow.addLayout(top)
    columns=QHBoxLayout(); columns.setSpacing(18); creators,left=card(); creators.setFixedWidth(290); row=QHBoxLayout(); row.addWidget(section('creator_list')); w.creator_count=QLabel('0'); w.creator_count.setObjectName('count'); row.addWidget(w.creator_count); left.addLayout(row)
    filters=QHBoxLayout(); w.group_filter=QComboBox(); filters.addWidget(w.group_filter,1); w.group_manager_button=button('manage_groups','quiet'); filters.addWidget(w.group_manager_button); left.addLayout(filters)
    w.creator_search=QLineEdit(); w.creator_search.setClearButtonEnabled(True); left.addWidget(w.creator_search)
    w.group_assign_button=button('assign_groups'); left.addWidget(w.group_assign_button)
    w.channels_list=QListWidget(); w.channels_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); w.channels_list.setUniformItemSizes(True); w.channels_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); w.channels_list.setTextElideMode(Qt.TextElideMode.ElideRight); left.addWidget(w.channels_list,1); left.addWidget(label('group_selection_hint','muted')); left.addWidget(label('follow_hint','muted')); columns.addWidget(creators)
    activity,right=card(); w.creator_heading=section('all_creators'); right.addWidget(w.creator_heading)
    w.channel_status=QLabel(); w.channel_status.setObjectName('muted'); w.channel_status.setWordWrap(True); right.addWidget(w.channel_status)
    w.activity_tabs=QTabWidget(); right.addWidget(w.activity_tabs,1)
    recent=QWidget(); recent_layout=QVBoxLayout(recent); recent_layout.setContentsMargins(0,12,0,0)
    w.discovery_stack=QStackedWidget(); w.discovery_empty=label('discovery_empty','muted'); w.discovery_empty.setAlignment(Qt.AlignmentFlag.AlignCenter); w.discovery_stack.addWidget(w.discovery_empty); w.discovery_table=w.table(4); w.discovery_stack.addWidget(w.discovery_table); recent_layout.addWidget(w.discovery_stack,1)
    w.discovery_button=button('queue_discovery'); recent_layout.addWidget(w.discovery_button,0,Qt.AlignmentFlag.AlignRight); w.activity_tabs.addTab(recent,'')
    watched=QWidget(); watch_layout=QVBoxLayout(watched); watch_layout.setContentsMargins(0,12,0,0); watch_layout.addWidget(label('watch_hint','muted')); w.watch_table=w.table(4); watch_layout.addWidget(w.watch_table); w.activity_tabs.addTab(watched,'')
    right.addWidget(label('feed_note','muted')); columns.addWidget(activity,1); follow.addLayout(columns,1)
    from PySide6.QtWidgets import QApplication
    QApplication.instance().setStyleSheet(STYLE)
