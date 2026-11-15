"""Group management and mixed-state batch membership editing."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QListWidget,QListWidgetItem,QMessageBox,QDialogButtonBox)

class GroupManager(QDialog):
    def __init__(self,monitor,tr,parent=None):
        super().__init__(parent);self.monitor=monitor;self.t=tr
        self.setWindowTitle(tr('manage_groups'));self.resize(480,480)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,22,22,22);layout.setSpacing(14)
        hint=QLabel(tr('group_manager_hint'));hint.setWordWrap(True);layout.addWidget(hint)
        self.list=QListWidget();layout.addWidget(self.list,1)
        self.name=QLineEdit();self.name.setPlaceholderText(tr('group_name'));layout.addWidget(self.name)
        row=QHBoxLayout()
        for key,handler in (('create_group',self.create),('rename_group',self.rename),('delete_group',self.delete)):
            button=QPushButton(tr(key));button.clicked.connect(handler);row.addWidget(button)
        layout.addLayout(row)
        self.feedback=QLabel();self.feedback.setWordWrap(True);self.feedback.setStyleSheet('color:#a44332');layout.addWidget(self.feedback)
        close=QPushButton(tr('done'));close.clicked.connect(self.accept);layout.addWidget(close)
        self.list.currentItemChanged.connect(self.selected);self.refresh()
    def refresh(self,selected=None):
        self.list.clear()
        for identity,name,count in self.monitor.groups():
            item=QListWidgetItem(f'{name}  ·  {count}');item.setData(Qt.ItemDataRole.UserRole,identity);item.setData(Qt.ItemDataRole.UserRole+1,name);self.list.addItem(item)
            if identity==selected:self.list.setCurrentItem(item)
    def selected(self,item,previous):
        if item:self.name.setText(item.data(Qt.ItemDataRole.UserRole+1))
    def create(self):
        try:identity=self.monitor.create_group(self.name.text())
        except ValueError as exc:self.feedback.setText(self.t(str(exc)));return
        self.feedback.clear();self.refresh(identity)
    def rename(self):
        item=self.list.currentItem()
        if not item:return
        identity=item.data(Qt.ItemDataRole.UserRole)
        try:self.monitor.rename_group(identity,self.name.text())
        except ValueError as exc:self.feedback.setText(self.t(str(exc)));return
        self.feedback.clear();self.refresh(identity)
    def delete(self):
        item=self.list.currentItem()
        if not item:return
        if QMessageBox.question(self,self.t('delete_group'),self.t('delete_group_confirm').format(name=item.data(Qt.ItemDataRole.UserRole+1)))!=QMessageBox.StandardButton.Yes:return
        self.monitor.delete_group(item.data(Qt.ItemDataRole.UserRole));self.name.clear();self.refresh()

class MembershipDialog(QDialog):
    def __init__(self,monitor,channels,tr,parent=None):
        super().__init__(parent);self.monitor=monitor;self.channels=list(channels);self.t=tr
        self.setWindowTitle(tr('assign_groups'));self.resize(470,470)
        layout=QVBoxLayout(self);layout.setContentsMargins(22,22,22,22);layout.setSpacing(14)
        label=QLabel(tr('membership_hint').format(count=len(self.channels)));label.setWordWrap(True);layout.addWidget(label)
        self.list=QListWidget();layout.addWidget(self.list,1)
        memberships=monitor.membership_map()
        for identity,name,count in monitor.groups():
            assigned=sum(identity in memberships.get(channel,set()) for channel in self.channels)
            state=Qt.CheckState.Checked if assigned==len(self.channels) else Qt.CheckState.PartiallyChecked if assigned else Qt.CheckState.Unchecked
            item=QListWidgetItem(name);item.setData(Qt.ItemDataRole.UserRole,identity);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(state);self.list.addItem(item)
        hint=QLabel(tr('membership_mixed'));hint.setWordWrap(True);layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.apply);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def apply(self):
        add=[];remove=[]
        for row in range(self.list.count()):
            item=self.list.item(row);identity=item.data(Qt.ItemDataRole.UserRole)
            if item.checkState()==Qt.CheckState.Checked:add.append(identity)
            elif item.checkState()==Qt.CheckState.Unchecked:remove.append(identity)
        self.monitor.change_memberships(self.channels,add,remove);self.accept()
