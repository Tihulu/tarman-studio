from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

from . import __app_name__, __version__
from .core import analyze_archive, install_archive, list_installed, uninstall
from .resources import (
    APP_ID,
    DESKTOP_FILE,
    checkbox_check_path,
    combo_arrow_path,
    icon_path,
    radio_dot_path,
)

try:  # pragma: no cover - depends on optional GUI extra
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListView,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSizePolicy,
        QSpacerItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except Exception as import_error:  # pragma: no cover - user-facing dependency path
    QApplication = None  # type: ignore[assignment]
    _IMPORT_ERROR = import_error
else:
    _IMPORT_ERROR = None


class GuiDependencyError(RuntimeError):
    pass


def require_gui_dependencies() -> None:
    if _IMPORT_ERROR is not None:
        raise GuiDependencyError(
            "PySide6 is missing. Install Tarman Studio with the pyenv installer, "
            "or run: python -m pip install '.[gui]'"
        ) from _IMPORT_ERROR


if QApplication is not None:

    class Section(QFrame):
        """A clean card with a title and content layout."""

        def __init__(self, title: str) -> None:
            super().__init__()
            self.setObjectName("sectionCard")
            self.outer = QVBoxLayout(self)
            self.outer.setContentsMargins(18, 14, 18, 18)
            self.outer.setSpacing(12)
            label = QLabel(title)
            label.setObjectName("sectionTitle")
            self.outer.addWidget(label)
            self.content = QVBoxLayout()
            self.content.setContentsMargins(0, 0, 0, 0)
            self.content.setSpacing(10)
            self.outer.addLayout(self.content)


    class PillLabel(QLabel):
        def __init__(self, text: str = "") -> None:
            super().__init__(text)
            self.setObjectName("pillLabel")
            self.setAlignment(Qt.AlignCenter)
            self.setMinimumHeight(34)
            self.setWordWrap(True)


    class HintLabel(QLabel):
        def __init__(self, text: str = "") -> None:
            super().__init__(text)
            self.setObjectName("hintLabel")
            self.setWordWrap(True)


    class DropBox(QFrame):
        def __init__(self, window: "TarmanWindow") -> None:
            super().__init__()
            self.window = window
            self.setAcceptDrops(True)
            self.setObjectName("dropBox")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(28, 28, 28, 28)
            layout.setSpacing(8)
            title = QLabel("Drop a portable Linux tarball here")
            title.setObjectName("dropTitle")
            title.setAlignment(Qt.AlignCenter)
            subtitle = QLabel("Supported: .tar, .tar.gz, .tgz, .tar.xz, .txz, .tar.bz2")
            subtitle.setObjectName("muted")
            subtitle.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)
            layout.addWidget(subtitle)

        def dragEnterEvent(self, event: QDragEnterEvent) -> None:
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()
            else:
                event.ignore()

        def dropEvent(self, event: QDropEvent) -> None:
            urls = event.mimeData().urls()
            if not urls:
                return
            path = Path(urls[0].toLocalFile())
            self.window.set_archive(path)
            event.acceptProposedAction()


    class TarmanWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setObjectName("mainWindow")
            self.setWindowTitle(f"{__app_name__} {__version__}")
            self.setMinimumSize(1080, 780)
            self.archive_path: Path | None = None
            self.analysis: Any | None = None
            self.installed_items: list[dict[str, Any]] = []
            if icon_path().exists():
                self.setWindowIcon(QIcon(str(icon_path())))

            root = QWidget()
            root.setObjectName("rootWidget")
            self.setCentralWidget(root)
            main = QVBoxLayout(root)
            main.setContentsMargins(28, 24, 28, 24)
            main.setSpacing(18)

            header = QHBoxLayout()
            header.setSpacing(16)
            if icon_path().exists():
                icon_label = QLabel()
                icon_label.setObjectName("headerIcon")
                pixmap = QPixmap(str(icon_path()))
                icon_label.setPixmap(pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                header.addWidget(icon_label)

            header_text = QVBoxLayout()
            header_text.setSpacing(4)
            title = QLabel("Tarman Studio")
            title.setObjectName("appTitle")
            subtitle = QLabel("A pyenv-isolated Qt GUI + CLI for portable tarball apps")
            subtitle.setObjectName("muted")
            header_text.addWidget(title)
            header_text.addWidget(subtitle)
            header.addLayout(header_text)
            header.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            about = QPushButton("About")
            about.setObjectName("secondaryButton")
            about.clicked.connect(self.show_about)
            header.addWidget(about)
            main.addLayout(header)

            body = QHBoxLayout()
            body.setSpacing(18)
            main.addLayout(body, 1)

            left_scroll = QScrollArea()
            left_scroll.setWidgetResizable(True)
            left_scroll.setFrameShape(QFrame.NoFrame)
            left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            left = QWidget()
            left_scroll.setWidget(left)
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(14)
            body.addWidget(left_scroll, 3)

            self.drop = DropBox(self)
            left_layout.addWidget(self.drop)

            picker = QHBoxLayout()
            picker.setSpacing(12)
            self.archive_edit = QLineEdit()
            self.archive_edit.setObjectName("pathInput")
            self.archive_edit.setPlaceholderText("Archive path")
            self.archive_edit.returnPressed.connect(self.analyze_current_archive)
            browse = QPushButton("Choose Archive")
            browse.clicked.connect(self.choose_archive)
            analyze = QPushButton("Analyze")
            analyze.setObjectName("primaryButton")
            analyze.clicked.connect(self.analyze_current_archive)
            picker.addWidget(self.archive_edit, 1)
            picker.addWidget(browse)
            picker.addWidget(analyze)
            left_layout.addLayout(picker)

            details = Section("Install options")
            form = QGridLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.setHorizontalSpacing(14)
            form.setVerticalSpacing(10)
            form.setColumnStretch(1, 1)
            self.name_edit = QLineEdit()
            self.name_edit.setPlaceholderText("Application name")
            self.executable_combo = QComboBox()
            self.executable_combo.setEditable(True)
            self.executable_combo.setInsertPolicy(QComboBox.NoInsert)
            self.executable_combo.setMaxVisibleItems(7)
            combo_view = QListView()
            combo_view.setObjectName("comboPopup")
            combo_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            combo_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            combo_view.setUniformItemSizes(True)
            combo_view.setSpacing(2)
            combo_view.setMinimumHeight(120)
            combo_view.setMaximumHeight(240)
            self.executable_combo.setMaxVisibleItems(7)
            self.executable_combo.setView(combo_view)
            if self.executable_combo.lineEdit() is not None:
                self.executable_combo.lineEdit().setPlaceholderText("Choose or type the main launcher")
                self.executable_combo.lineEdit().setClearButtonEnabled(True)
            self.scope_user = QRadioButton("User install")
            self.scope_user.setChecked(True)
            self.scope_system = QRadioButton("System install (/opt, uses pkexec)")
            self.overwrite_check = QCheckBox("Overwrite existing install")
            self.desktop_check = QCheckBox("Create app menu launcher")
            self.desktop_check.setChecked(True)
            self.terminal_check = QCheckBox("Run launcher in terminal")

            def field_label(text: str) -> QLabel:
                label = QLabel(text)
                label.setObjectName("fieldLabel")
                label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                return label

            self.executable_hint = HintLabel(
                "Pick the main launcher. The drop-down now clearly shows selectable items and you can still type your own path."
            )

            scope_row = QHBoxLayout()
            scope_row.setContentsMargins(0, 0, 0, 0)
            scope_row.setSpacing(18)
            scope_row.addWidget(self.scope_user)
            scope_row.addWidget(self.scope_system)
            scope_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            form.addWidget(field_label("Name"), 0, 0)
            form.addWidget(self.name_edit, 0, 1)
            form.addWidget(field_label("Executable"), 1, 0)
            form.addWidget(self.executable_combo, 1, 1)
            form.addWidget(self.executable_hint, 2, 1)
            form.addWidget(field_label("Scope"), 3, 0)
            form.addLayout(scope_row, 3, 1)
            form.addWidget(self.overwrite_check, 4, 1)
            form.addWidget(self.desktop_check, 5, 1)
            form.addWidget(self.terminal_check, 6, 1)
            details.content.addLayout(form)
            left_layout.addWidget(details)

            actions = QHBoxLayout()
            actions.setSpacing(12)
            install = QPushButton("Install")
            install.setObjectName("primaryButton")
            install.clicked.connect(self.install_current_archive)
            refresh = QPushButton("Refresh Installed")
            refresh.clicked.connect(self.refresh_installed)
            actions.addWidget(install)
            actions.addWidget(refresh)
            actions.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            left_layout.addLayout(actions)

            log_section = Section("Activity log")
            self.log = QTextEdit()
            self.log.setObjectName("logView")
            self.log.setReadOnly(True)
            self.log.setLineWrapMode(QTextEdit.WidgetWidth)
            self.log.setPlaceholderText("Analysis and install output will appear here.")
            log_section.content.addWidget(self.log)
            left_layout.addWidget(log_section, 1)

            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(14)
            body.addWidget(right, 2)

            stats = Section("Archive summary")
            stats_layout = QGridLayout()
            stats_layout.setContentsMargins(0, 0, 0, 0)
            stats_layout.setHorizontalSpacing(8)
            stats_layout.setVerticalSpacing(8)
            self.name_pill = PillLabel("No archive")
            self.entries_pill = PillLabel("0 entries")
            self.format_pill = PillLabel("Unknown format")
            self.exe_pill = PillLabel("No launcher")
            stats_layout.addWidget(self.name_pill, 0, 0)
            stats_layout.addWidget(self.entries_pill, 0, 1)
            stats_layout.addWidget(self.format_pill, 1, 0)
            stats_layout.addWidget(self.exe_pill, 1, 1)
            stats.content.addLayout(stats_layout)
            right_layout.addWidget(stats)

            found = Section("Detected launchers and assets")
            self.detected_list = QListWidget()
            self.detected_list.setObjectName("cleanList")
            self.detected_list.setWordWrap(True)
            self.detected_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            found.content.addWidget(self.detected_list)
            right_layout.addWidget(found, 1)

            installed_box = Section("Installed by Tarman")
            self.installed_list = QListWidget()
            self.installed_list.setObjectName("cleanList")
            self.installed_list.setWordWrap(True)
            self.installed_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            installed_box.content.addWidget(self.installed_list)
            uninstall_row = QHBoxLayout()
            uninstall_row.setContentsMargins(0, 0, 0, 0)
            uninstall_button = QPushButton("Uninstall Selected")
            uninstall_button.clicked.connect(self.uninstall_selected)
            uninstall_row.addWidget(uninstall_button)
            uninstall_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            installed_box.content.addLayout(uninstall_row)
            right_layout.addWidget(installed_box, 1)

            self.apply_style()
            self.refresh_installed()

        def apply_style(self) -> None:
            arrow = combo_arrow_path().as_posix() if combo_arrow_path().exists() else ""
            check = checkbox_check_path().as_posix() if checkbox_check_path().exists() else ""
            radio = radio_dot_path().as_posix() if radio_dot_path().exists() else ""
            self.setStyleSheet(
                f"""
                QWidget {{
                    font-size: 14px;
                }}
                QMainWindow, QWidget#rootWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
                    background: #0b1017;
                    color: #eef2f6;
                }}
                QLabel {{
                    background: transparent;
                    color: #eef2f6;
                }}
                #appTitle {{
                    font-size: 31px;
                    font-weight: 850;
                    letter-spacing: -0.5px;
                }}
                #muted {{
                    color: #98a6ba;
                }}
                #hintLabel {{
                    color: #8ea2bb;
                    font-size: 12px;
                    padding-top: 2px;
                }}
                #headerIcon {{
                    background: transparent;
                    border: none;
                }}
                #dropBox {{
                    border: 2px dashed #46617f;
                    border-radius: 20px;
                    background: #101822;
                }}
                #dropBox:hover {{
                    border-color: #60a5fa;
                    background: #111d2a;
                }}
                #dropTitle {{
                    font-size: 21px;
                    font-weight: 800;
                }}
                #sectionCard {{
                    background: #111822;
                    border: 1px solid #253247;
                    border-radius: 18px;
                }}
                #sectionTitle {{
                    color: #d9e5f2;
                    font-weight: 800;
                    font-size: 15px;
                    padding-bottom: 2px;
                }}
                #fieldLabel {{
                    color: #aab8ca;
                    font-weight: 700;
                    min-width: 84px;
                    padding-top: 10px;
                }}
                QLineEdit, QComboBox, QTextEdit, QListWidget {{
                    background: #0a0f16;
                    border: 1px solid #2c3a50;
                    border-radius: 12px;
                    padding: 9px 11px;
                    color: #eef2f6;
                    selection-background-color: #3b82f6;
                    selection-color: white;
                }}
                QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QListWidget:focus {{
                    border-color: #5b8def;
                }}
                #pathInput {{
                    background: #0f1620;
                }}
                QComboBox {{
                    padding-right: 40px;
                    min-height: 22px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 34px;
                    border: none;
                    border-left: 1px solid #24354c;
                    background: #121c29;
                    border-top-right-radius: 12px;
                    border-bottom-right-radius: 12px;
                }}
                QComboBox::down-arrow {{
                    image: url({arrow});
                    width: 14px;
                    height: 14px;
                }}
                QComboBox QAbstractItemView, QListView#comboPopup {{
                    background: #0f1620;
                    color: #eef2f6;
                    border: 1px solid #35507b;
                    border-radius: 12px;
                    padding: 6px;
                    outline: none;
                    selection-background-color: #3b82f6;
                    selection-color: white;
                }}
                QListView#comboPopup QScrollBar:vertical, QComboBox QAbstractItemView QScrollBar:vertical {{
                    background: #0b1118;
                    width: 12px;
                    margin: 6px 4px 6px 0;
                    border-radius: 6px;
                }}
                QListView#comboPopup QScrollBar::handle:vertical, QComboBox QAbstractItemView QScrollBar::handle:vertical {{
                    background: #42628d;
                    min-height: 28px;
                    border-radius: 6px;
                }}
                QListView#comboPopup QScrollBar::handle:vertical:hover, QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {{
                    background: #5c84bd;
                }}
                QListView#comboPopup QScrollBar::add-line:vertical, QListView#comboPopup QScrollBar::sub-line:vertical,
                QListView#comboPopup QScrollBar::add-page:vertical, QListView#comboPopup QScrollBar::sub-page:vertical,
                QComboBox QAbstractItemView QScrollBar::add-line:vertical, QComboBox QAbstractItemView QScrollBar::sub-line:vertical,
                QComboBox QAbstractItemView QScrollBar::add-page:vertical, QComboBox QAbstractItemView QScrollBar::sub-page:vertical {{
                    background: transparent;
                    border: none;
                    height: 0;
                }}
                QComboBox QAbstractItemView::item, QListView#comboPopup::item {{
                    min-height: 30px;
                    padding: 7px 10px;
                    margin: 1px 0;
                    border-radius: 8px;
                    background: transparent;
                    color: #eef2f6;
                }}
                QComboBox QAbstractItemView::item:selected, QListView#comboPopup::item:selected {{
                    background: #295aa7;
                    color: white;
                }}
                QComboBox QAbstractItemView::item:hover, QListView#comboPopup::item:hover {{
                    background: #1a2940;
                }}
                QTextEdit#logView {{
                    min-height: 145px;
                }}
                QListWidget#cleanList {{
                    padding: 6px;
                    outline: none;
                }}
                QListWidget#cleanList::item {{
                    padding: 8px;
                    border-radius: 9px;
                    margin: 2px 0;
                }}
                QListWidget#cleanList::item:selected {{
                    background: #244c8f;
                    color: white;
                }}
                QPushButton {{
                    background: #202b3b;
                    border: 1px solid #3a4a61;
                    border-radius: 12px;
                    padding: 9px 16px;
                    color: #eef2f6;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: #2a3749;
                    border-color: #53657d;
                }}
                QPushButton:pressed {{
                    background: #1a2330;
                }}
                #primaryButton {{
                    background: #3b82f6;
                    border-color: #60a5fa;
                    color: white;
                }}
                #primaryButton:hover {{
                    background: #2563eb;
                }}
                #secondaryButton {{
                    padding-left: 18px;
                    padding-right: 18px;
                }}
                #pillLabel {{
                    background: #1b2636;
                    border: 1px solid #32445e;
                    border-radius: 16px;
                    padding: 7px 10px;
                    font-weight: 800;
                }}
                QCheckBox, QRadioButton {{
                    background: transparent;
                    padding: 4px;
                    color: #eef2f6;
                    spacing: 10px;
                }}
                QCheckBox::indicator, QRadioButton::indicator {{
                    width: 18px;
                    height: 18px;
                    background: #0d131c;
                    border: 1px solid #486483;
                    margin-right: 6px;
                }}
                QCheckBox::indicator {{
                    border-radius: 6px;
                }}
                QRadioButton::indicator {{
                    border-radius: 9px;
                }}
                QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
                    border-color: #6e8fb9;
                }}
                QCheckBox::indicator:checked {{
                    background: #3b82f6;
                    border-color: #60a5fa;
                    image: url({check});
                }}
                QRadioButton::indicator:checked {{
                    background: #3b82f6;
                    border-color: #60a5fa;
                    image: url({radio});
                }}
                QScrollBar:vertical {{
                    background: transparent;
                    width: 10px;
                    margin: 2px;
                }}
                QScrollBar::handle:vertical {{
                    background: #34465f;
                    border-radius: 5px;
                    min-height: 28px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: #4a6385;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                    border: none;
                    height: 0;
                }}
                """
            )

        def set_archive(self, path: Path) -> None:
            self.archive_path = path.expanduser()
            self.archive_edit.setText(str(self.archive_path))
            self.analyze_current_archive()

        def choose_archive(self) -> None:
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Choose archive",
                str(Path.home()),
                "Tar archives (*.tar *.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2 *.tbz2);;All files (*)",
            )
            if file_name:
                self.set_archive(Path(file_name))

        def analyze_current_archive(self) -> None:
            text = self.archive_edit.text().strip()
            if not text:
                self.show_error("Choose an archive first.")
                return
            path = Path(text).expanduser()
            try:
                analysis = analyze_archive(path, app_name=self.name_edit.text().strip() or None)
            except Exception as exc:
                self.analysis = None
                self.show_error(str(exc))
                return
            self.archive_path = path
            self.analysis = analysis
            self.name_edit.setText(analysis.app_name)
            self.executable_combo.clear()
            self.executable_combo.addItems(analysis.executables)
            if analysis.recommended_executable:
                idx = self.executable_combo.findText(analysis.recommended_executable)
                if idx >= 0:
                    self.executable_combo.setCurrentIndex(idx)
            elif self.executable_combo.count() == 0 and self.executable_combo.lineEdit() is not None:
                self.executable_combo.lineEdit().clear()
            self.name_pill.setText(analysis.app_name)
            self.entries_pill.setText(f"{analysis.entries} entries")
            self.format_pill.setText(analysis.format or "tar")
            self.exe_pill.setText(analysis.recommended_executable or "No launcher")
            self.populate_detected_list(analysis)
            self.log.setPlainText(self.format_analysis(analysis))

        def populate_detected_list(self, analysis: Any) -> None:
            self.detected_list.clear()
            rows: list[tuple[str, str]] = []
            for value in analysis.executables[:12]:
                rows.append(("Launcher", value))
            if len(analysis.executables) > 12:
                rows.append(("Launcher", f"… {len(analysis.executables) - 12} more hidden"))
            for value in analysis.desktop_files[:6]:
                rows.append(("Desktop file", value))
            for value in analysis.icons[:8]:
                rows.append(("Icon", value))
            for value in analysis.install_scripts[:6]:
                rows.append(("Install script", value))
            for value in analysis.source_markers[:6]:
                rows.append(("Source marker", value))
            for value in analysis.warnings:
                rows.append(("Warning", value))
            if not rows:
                rows.append(("Status", "No launchers or app assets detected yet."))
            for kind, value in rows:
                item = QListWidgetItem(f"{kind}\n{value}")
                item.setToolTip(value)
                self.detected_list.addItem(item)

        def format_analysis(self, analysis: Any) -> str:
            lines = [
                f"Archive: {analysis.archive}",
                f"Name: {analysis.app_name}",
                f"Format: {analysis.format}",
                f"Entries: {analysis.entries}",
                f"Top level: {analysis.top_level or '(multiple)'}",
                f"Recommended executable: {analysis.recommended_executable or '(none)'}",
            ]
            if analysis.warnings:
                lines.append("\nWarnings:")
                lines.extend(f"- {warning}" for warning in analysis.warnings)
            if analysis.executables:
                lines.append("\nLaunchers:")
                lines.extend(f"- {item}" for item in analysis.executables[:40])
                if len(analysis.executables) > 40:
                    lines.append(f"- … {len(analysis.executables) - 40} more")
            if analysis.install_scripts:
                lines.append("\nInstall scripts found but not executed automatically:")
                lines.extend(f"- {item}" for item in analysis.install_scripts)
            return "\n".join(lines)

        def install_current_archive(self) -> None:
            if self.analysis is None:
                self.analyze_current_archive()
                if self.analysis is None:
                    return
            assert self.archive_path is not None
            executable = self.executable_combo.currentText().strip() or None
            scope = "system" if self.scope_system.isChecked() else "user"
            if scope == "system":
                auth_box = self.themed_message_box(
                    QMessageBox.Warning,
                    "Authorization required",
                    "<b>System install needs administrator permission.</b><br><br>"
                    "Tarman Studio will install this app under <code>/opt</code> and create a system launcher. "
                    "After you continue, your desktop will show the secure Polkit/pkexec password prompt.<br><br>"
                    "Tarman Studio does not read, store, or handle your password.",
                    buttons=QMessageBox.Ok | QMessageBox.Cancel,
                )
                ok_button = auth_box.button(QMessageBox.Ok)
                if ok_button is not None:
                    ok_button.setText("Continue")
                cancel_button = auth_box.button(QMessageBox.Cancel)
                if cancel_button is not None:
                    cancel_button.setText("Cancel")
                if auth_box.exec() != QMessageBox.Ok:
                    self.log.setPlainText("System install canceled before authorization.")
                    return
            try:
                result = install_archive(
                    self.archive_path,
                    app_name=self.name_edit.text().strip() or None,
                    executable=executable,
                    scope=scope,
                    create_desktop=self.desktop_check.isChecked(),
                    overwrite=self.overwrite_check.isChecked(),
                    terminal=self.terminal_check.isChecked(),
                )
            except Exception as exc:
                self.show_error(str(exc))
                return
            self.log.setPlainText(
                "Installed successfully.\n\n"
                f"Name: {result.app_name}\n"
                f"Files: {result.install_dir}\n"
                f"Launcher: {result.executable}\n"
                f"Desktop entry: {result.desktop_file or '(none)'}\n"
                f"Scope: {result.scope}\n"
                f"Privilege escalation: {'pkexec' if result.used_privilege_escalation else 'no'}"
            )
            self.themed_message_box(QMessageBox.Information, "Installed", f"<b>{result.app_name}</b> was installed.").exec()
            self.refresh_installed()

        def refresh_installed(self) -> None:
            self.installed_list.clear()
            self.installed_items = list_installed()
            if not self.installed_items:
                self.installed_list.addItem("No apps installed by Tarman Studio yet.")
                return
            for item in self.installed_items:
                name = item.get("app_name", "Unknown")
                location = item.get("install_dir", "")
                row = QListWidgetItem(f"{name}\n{location}")
                row.setToolTip(str(location))
                row.setData(Qt.UserRole, item)
                self.installed_list.addItem(row)

        def uninstall_selected(self) -> None:
            row = self.installed_list.currentItem()
            if row is None:
                self.show_error("Select an installed app first.")
                return
            item = row.data(Qt.UserRole)
            if not item:
                return
            name = item.get("app_name")
            if not name:
                return
            answer_box = self.themed_message_box(
                QMessageBox.Question,
                "Uninstall",
                f"Uninstall <b>{name}</b>?",
                buttons=QMessageBox.Yes | QMessageBox.No,
            )
            if answer_box.exec() != QMessageBox.Yes:
                return
            try:
                result = uninstall(name)
            except Exception as exc:
                self.show_error(str(exc))
                return
            self.log.setPlainText(
                f"Uninstalled {result.get('app_name')}\n\n" + "\n".join(result.get("removed", []))
            )
            self.refresh_installed()

        def themed_message_box(self, icon: QMessageBox.Icon, title: str, text: str, *, buttons: QMessageBox.StandardButtons = QMessageBox.Ok) -> QMessageBox:
            box = QMessageBox(self)
            box.setWindowTitle(title)
            box.setTextFormat(Qt.RichText)
            box.setText(text)
            box.setIcon(icon)
            box.setStandardButtons(buttons)
            if icon_path().exists():
                box.setIconPixmap(QPixmap(str(icon_path())).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            box.setStyleSheet(
                """
                QMessageBox {
                    background: #0f1620;
                }
                QMessageBox QLabel {
                    color: #eef2f6;
                    background: transparent;
                    min-width: 320px;
                }
                QMessageBox QPushButton {
                    background: #202b3b;
                    border: 1px solid #3a4a61;
                    border-radius: 12px;
                    padding: 8px 16px;
                    color: #eef2f6;
                    font-weight: 700;
                    min-width: 84px;
                }
                QMessageBox QPushButton:hover {
                    background: #2a3749;
                    border-color: #53657d;
                }
                """
            )
            return box

        def show_about(self) -> None:
            text = (
                f"<b>{__app_name__} {__version__}</b><br><br>"
                "Installs prebuilt portable Linux apps from tar archives.<br>"
                "This Qt build is designed for pyenv-isolated installs.<br><br>"
                "<span style='color:#9fb0c7'>License:</span> GPL-3.0-or-later"
            )
            self.themed_message_box(QMessageBox.Information, "About Tarman Studio", text).exec()

        def show_error(self, message: str) -> None:
            self.log.setPlainText(message)
            self.themed_message_box(QMessageBox.Critical, "Tarman Studio", message).exec()


def main(argv: list[str] | None = None) -> int:
    try:
        require_gui_dependencies()
    except GuiDependencyError as exc:
        print(str(exc), file=sys.stderr)
        if _IMPORT_ERROR is not None:
            print(f"Import error: {_IMPORT_ERROR}", file=sys.stderr)
        return 2
    try:
        app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
        app.setApplicationName(APP_ID)
        app.setApplicationDisplayName(__app_name__)
        if hasattr(app, "setDesktopFileName"):
            app.setDesktopFileName(DESKTOP_FILE)
        if icon_path().exists():
            app.setWindowIcon(QIcon(str(icon_path())))
        else:
            app.setWindowIcon(QIcon.fromTheme("package-x-generic"))
        window = TarmanWindow()
        window.show()
        return app.exec()
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
