"""The main window, as on the Mac (BlurryApp.swift, Views.swift): only the drop
window at first; after the drop, the guide for one file at a time. The queue
and the settings are separate windows, reached from the menus."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QLocale, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import i18n, image_io, video_io
from blurry_opsec.gui import lifecycle, native, picker, translations
from blurry_opsec.gui import store as S
from blurry_opsec.gui import strings as L
from blurry_opsec.gui.guide import GuideView
from blurry_opsec.gui.onboarding import TipPopover, WelcomeDialog
from blurry_opsec.gui.preferences import PreferencesDialog
from blurry_opsec.gui.prefs import Prefs
from blurry_opsec.gui.queue import QueueWindow
from blurry_opsec.gui.widgets import DropFrame, PhotoGlyph, button, label

ACCEPTED = sorted(image_io.IMAGE_EXTENSIONS | video_io.VIDEO_EXTENSIONS)
WINDOW_TITLE = "Blurry"  # never a file name (R2)
LANDING_SIZE = (520, 440)
GUIDE_MIN = (720, 620)
GUIDE_SIZE = (820, 780)


class Landing(QWidget):
    """The drop window: corner ticks, green when a file arrives, Choose Files…"""

    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        top = native.TITLEBAR_HEIGHT + 6 if window.glass else 16
        outer.setContentsMargins(16, top, 16, 16)
        self.frame = DropFrame()
        outer.addWidget(self.frame)
        col = QVBoxLayout(self.frame)
        col.setSpacing(18)
        col.addStretch(1)
        self.glyph = PhotoGlyph()
        col.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = label("", "title3")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title)
        self.choose = button("", "large", window.choose_files)
        col.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignHCenter)
        self.welcome = label("", "calloutSecondary")
        self.welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.engine = label("", "captionOrange")
        self.engine.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice = label("", "caption")
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.welcome)
        col.addWidget(self.engine)
        col.addWidget(self.notice)
        col.addStretch(1)

    def set_targeted(self, on: bool) -> None:
        self.frame.set_active(on)
        self.glyph.active = on
        self.glyph.update()

    def sync(self, store: S.Store) -> None:
        self.title.setText(L.drop_title())
        self.choose.setText(L.choose_files())
        self.welcome.setText(L.welcome_line())
        self.welcome.setVisible(not store.onboarded)
        self.engine.setText(L.engine_missing())
        self.engine.setVisible(store.engine_missing)
        self.notice.setText(store.notice or "")
        self.notice.setVisible(bool(store.notice))


class _PressWatcher(QObject):
    """Every mouse press in the app, so that a tip can hide on a click outside it."""

    def __init__(self, tip: TipPopover) -> None:
        super().__init__(tip)
        self.tip = tip

    def eventFilter(self, _obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress and self.tip.isVisible():
            self.tip.outside_click(event.globalPosition())
        return False


class MainWindow(QMainWindow):
    def __init__(self, prefs: Prefs, glass: bool = False) -> None:
        super().__init__()
        self.prefs = prefs
        self.glass = glass  # native window material underneath (macOS)
        lang = prefs.language or ("it" if QLocale.system().name().startswith("it") else "en")
        i18n.set_language(lang)
        translations.set_language(lang)
        self.store = S.Store(prefs, self)
        self.queue_window: QueueWindow | None = None
        self.preferences_dialog: PreferencesDialog | None = None
        self.welcome: WelcomeDialog | None = None
        self._targeted = False
        self._tip_now: str | None = None
        self._tip_dismissed = False

        self.setWindowTitle(WINDOW_TITLE)
        self.setAcceptDrops(True)
        if glass:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.root = QWidget()
        self.root.setObjectName("root")
        if glass:
            for w in (self, self.root):
                w.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.landing = Landing(self)
        self.guide = GuideView(self.store)
        self.guide.export_requested.connect(self.choose_output)
        self.guide.reveal_requested.connect(lifecycle.reveal)
        if glass:
            self.guide.layout().setContentsMargins(0, native.TITLEBAR_HEIGHT - 12, 0, 0)
        self.stack.addWidget(self.landing)
        self.stack.addWidget(self.guide)
        self.setCentralWidget(self.root)
        self.drop_overlay = DropFrame(self.root)
        self.drop_overlay.set_active(True)
        self.drop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drop_overlay.hide()
        self.tip = TipPopover(self.root)
        self.tip.action.connect(self._tip_action)
        self.tip.skip.connect(self.store.finish_onboarding)
        self.tip.dismissed.connect(self._tip_hidden)
        QApplication.instance().installEventFilter(_PressWatcher(self.tip))
        self.notice_timer = QTimer(self, singleShot=True, interval=8000)
        self.notice_timer.timeout.connect(self._clear_notice)

        self._build_menus()
        self._build_shortcuts()
        self.store.changed.connect(self.sync)
        self.store.picture.connect(self.guide.on_picture)
        self.resize(*LANDING_SIZE)
        self.sync()

    # -- menus and keys ------------------------------------------------------------
    def _build_menus(self) -> None:
        bar = self.menuBar()
        self.file_menu = bar.addMenu("")
        self.choose_action = QAction(self, triggered=self.choose_files)
        self.choose_action.setShortcut(QKeySequence.StandardKey.Open)
        self.settings_action = QAction(self, triggered=self.open_preferences)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.quit_action = QAction(self, triggered=self.close)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        self.file_menu.addAction(self.choose_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.settings_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)
        self.view_menu = bar.addMenu("")
        self.queue_action = QAction(self, triggered=self.open_queue)
        self.queue_action.setShortcut(QKeySequence("Ctrl+L"))
        self.view_menu.addAction(self.queue_action)
        self.help_menu = bar.addMenu("")
        self.guide_action = QAction(self, triggered=self.restart_guide)
        self.updates_action = QAction(self, triggered=lifecycle.open_releases)
        self.help_menu.addAction(self.guide_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.updates_action)

    def _retranslate_menus(self) -> None:
        self.file_menu.setTitle(L.file_menu())
        self.choose_action.setText(L.choose_files())
        self.settings_action.setText(L.settings_menu())
        self.quit_action.setText(L.quit_app())
        self.view_menu.setTitle(L.view_menu())
        self.queue_action.setText(L.queue())
        self.help_menu.setTitle(L.help_menu())
        self.guide_action.setText(L.restart_guide())
        self.updates_action.setText(L.updates())

    def _build_shortcuts(self) -> None:
        def key(seq, slot) -> QShortcut:
            return QShortcut(QKeySequence(seq), self, slot)

        self.enter_keys = [key(Qt.Key.Key_Return, self._enter), key(Qt.Key.Key_Enter, self._enter)]
        self.back_keys = [
            key(QKeySequence.StandardKey.Back, lambda: self._back()),
            key("Ctrl+[", lambda: self._back()),
        ]
        self.space_key = key(Qt.Key.Key_Space, self.guide.player.toggle)
        self.correct_key = key("Ctrl+E", self.store.start_editing)
        self.escape_key = key(Qt.Key.Key_Escape, lambda: self.store.end_editing(False))
        self.delete_keys = [
            key(QKeySequence.StandardKey.Delete, self.guide.edit_panel.delete_selected),
            key(Qt.Key.Key_Backspace, self.guide.edit_panel.delete_selected),
        ]

    def _enter(self) -> None:
        if self.tip.isVisible():
            self._tip_action()
        elif self.stack.currentWidget() is self.guide:
            if self.store.editing:
                self.store.end_editing(True)
            elif self.guide.primary_btn.isVisible():
                self.guide.primary_action()

    def _back(self) -> None:
        if self.guide.back_btn.isVisible() and self.stack.currentWidget() is self.guide:
            self.store.move(-1)

    # -- state ------------------------------------------------------------------------
    def sync(self) -> None:
        store = self.store
        self._retranslate_menus()
        in_guide = store.current is not None
        if in_guide and self.stack.currentWidget() is not self.guide:
            self.stack.setCurrentWidget(self.guide)
            self.setMinimumSize(*GUIDE_MIN)
            screen = self.screen().availableGeometry() if self.screen() else None
            w, h = GUIDE_SIZE
            if screen is not None:
                w, h = min(w, screen.width()), min(h, screen.height() - 40)
            if self.width() < w or self.height() < h:
                self.resize(max(self.width(), w), max(self.height(), h))
        elif not in_guide and self.stack.currentWidget() is not self.landing:
            self.stack.setCurrentWidget(self.landing)
            self.setMinimumSize(440, 380)
        self.landing.sync(store)
        if in_guide:
            self.guide.sync()
        if store.notice:
            self.notice_timer.start()
        editing = in_guide and store.editing
        item = store.current
        self.space_key.setEnabled(
            in_guide
            and not editing
            and store.step == "result"
            and item is not None
            and item.kind == "video"
            and item.analysed
        )
        self.correct_key.setEnabled(in_guide and self.guide.picture.correct_btn.isVisible())
        self.escape_key.setEnabled(editing)
        for k in self.delete_keys:
            k.setEnabled(editing)
        if store.show_welcome:
            QTimer.singleShot(0, self._show_welcome)
        QTimer.singleShot(0, self._sync_tip)

    def _clear_notice(self) -> None:
        if self.store.notice:
            self.store.notice = None
            self.store.changed.emit()

    def _show_welcome(self) -> None:
        if not self.store.show_welcome or (self.welcome is not None and self.welcome.isVisible()):
            return
        self.welcome = WelcomeDialog(self.store, self)
        self.welcome.open()

    def _sync_tip(self) -> None:
        tip = self.store.tip if self.stack.currentWidget() is self.guide else None
        if tip != self._tip_now:
            self._tip_now = tip
            self._tip_dismissed = False
        anchor = self.guide.anchor(tip) if tip else None
        if tip is None or anchor is None or self._tip_dismissed or not self.isVisible():
            self.tip.hide()
            return
        text = {"steps": L.tip_steps(), "correct": L.tip_correct(), "queue": L.tip_queue()}[tip]
        action = L.open_queue() if tip == "queue" else L.tip_next()
        self.tip.show_at(anchor, text, action, prefer_below=tip != "correct")

    def _tip_action(self) -> None:
        if self._tip_now == "queue":
            self.open_queue()
            self.store.finish_onboarding()
        else:
            self.store.next_tip()

    def _tip_hidden(self) -> None:
        self._tip_dismissed = True

    # -- files ---------------------------------------------------------------------------
    def choose_files(self) -> None:
        self.store.add(picker.choose_files(self, ACCEPTED))

    def add_paths(self, paths: list[Path]) -> None:
        self.store.add(paths)

    def choose_output(self) -> None:
        item = self.store.current
        if item is None:
            return
        if item.status == S.NO_FACES:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(L.no_faces_title())
            box.setInformativeText(L.no_faces_text())
            anyway = box.addButton(L.export_anyway(), QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(L.cancel(), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not anyway:
                return
        self.store.stop_playing()
        output = picker.choose_output(self, item.path, item.out_ext)
        if output is not None:
            self.store.export(output)

    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_targeted(True)

    def dragLeaveEvent(self, _e) -> None:  # noqa: N802
        self._set_targeted(False)

    def dropEvent(self, e) -> None:  # noqa: N802
        self._set_targeted(False)
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        e.acceptProposedAction()
        self.store.add(paths)

    def _set_targeted(self, on: bool) -> None:
        self._targeted = on
        self.landing.set_targeted(on)
        in_guide = self.stack.currentWidget() is self.guide
        self.drop_overlay.setVisible(on and in_guide)
        if on and in_guide:
            self.drop_overlay.setGeometry(self.root.rect().adjusted(10, 10, -10, -10))
            self.drop_overlay.raise_()

    # -- other windows -----------------------------------------------------------------
    def open_queue(self) -> None:
        if self.queue_window is None:
            self.queue_window = QueueWindow(self.store, self)
            self.queue_window.open_item.connect(self._open_from_queue)
            self.queue_window.reveal.connect(lambda p: p and lifecycle.reveal(p))
            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.queue_window.move(
                screen.right() - self.queue_window.width() - 24, screen.top() + 24
            )
        self.queue_window.show()
        self.queue_window.raise_()
        self.queue_window.activateWindow()

    def _open_from_queue(self, item_id: int) -> None:
        self.store.open(item_id)
        self.show()
        self.raise_()
        self.activateWindow()

    def open_preferences(self) -> None:
        if self.preferences_dialog is None:
            self.preferences_dialog = PreferencesDialog(self, self.store)
        self.preferences_dialog.show()
        self.preferences_dialog.raise_()
        self.preferences_dialog.activateWindow()

    def restart_guide(self) -> None:
        self.show()
        self.raise_()
        self.store.restart_onboarding()

    def set_language(self, code: str) -> None:
        i18n.set_language(code)
        translations.set_language(code)
        self.prefs.language = code
        self.store.changed.emit()

    # -- window ------------------------------------------------------------------------
    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self.glass and not getattr(self, "_glass_applied", False):
            self._glass_applied = True
            native.apply_macos_glass(self)
        QTimer.singleShot(0, self._sync_tip)

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        QTimer.singleShot(0, self._sync_tip)

    def closeEvent(self, e) -> None:  # noqa: N802
        self.store.shutdown()
        self.prefs.sync()
        for w in (self.queue_window, self.preferences_dialog):
            if w is not None:
                w.close()
        e.accept()
