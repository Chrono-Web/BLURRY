"""Main window: drop area, queue, settings, export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLocale, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import engine, i18n, image_io, levels, video_io
from blurry_opsec.files import InputError
from blurry_opsec.gui import model as m
from blurry_opsec.gui import picker, style
from blurry_opsec.gui.prefs import Prefs
from blurry_opsec.gui.review import ImageReview, VideoReview
from blurry_opsec.gui.worker_client import WorkerClient
from blurry_opsec.i18n import t
from blurry_opsec.plan import plan_from_dict, plan_to_dict

RELEASES_URL = "https://github.com/Chrono-Web/BLURRY/releases"
ACCEPTED = sorted(image_io.IMAGE_EXTENSIONS | video_io.VIDEO_EXTENSIONS)
WINDOW_TITLE = "Blurry"  # never a file name (R2)


class DropFrame(QFrame):
    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self, prefs: Prefs) -> None:
        super().__init__()
        self.prefs = prefs
        lang = prefs.language or ("it" if QLocale.system().name().startswith("it") else "en")
        i18n.set_language(lang)
        self.items: list[m.Item] = []
        self.export_queue: list[m.Item] = []
        self.current: m.Item | None = None  # item the jobs worker is processing
        self.out_dir: Path | None = None  # this session only, never saved
        self.review: ImageReview | VideoReview | None = None
        self._requeue: list[m.Item] = []

        self.jobs = WorkerClient(self)
        self.frames = WorkerClient(self)
        self.jobs.crashed.connect(self._on_worker_crashed)

        self.setWindowTitle(WINDOW_TITLE)
        self.setAcceptDrops(True)
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(12)
        outer.addLayout(self._build_header())
        self.stack = QStackedWidget()
        self.home = self._build_home()
        self.stack.addWidget(self.home)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.retranslate()
        self.refresh_queue()

    # -- layout ------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        h = QHBoxLayout()
        wordmark = QLabel("BLURRY")
        wordmark.setObjectName("wordmark")
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.tagline = QLabel()
        self.tagline.setObjectName("muted")
        self.lang_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        self.updates_btn = QPushButton()
        self.updates_btn.setObjectName("link")
        self.updates_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL)))
        h.addWidget(wordmark)
        h.addSpacing(10)
        h.addWidget(self.chip)
        h.addSpacing(14)
        h.addWidget(self.tagline)
        h.addStretch(1)
        h.addWidget(self.lang_combo)
        h.addWidget(self.updates_btn)
        return h

    def _build_home(self) -> QWidget:
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)

        left = QVBoxLayout()
        self.drop = DropFrame()
        self.drop.setObjectName("drop")
        self.drop.setMinimumHeight(150)
        dl = QVBoxLayout(self.drop)
        dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_title = QLabel()
        self.drop_title.setObjectName("dropTitle")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_formats = QLabel()
        self.drop_formats.setObjectName("hint")
        self.drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose_btn = QPushButton()
        self.choose_btn.clicked.connect(self.choose_files)
        dl.addWidget(self.drop_title)
        dl.addWidget(self.drop_formats)
        dl.addSpacing(6)
        dl.addWidget(self.choose_btn, 0, Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.drop)

        self.queue = QTreeWidget()
        self.queue.setColumnCount(3)
        self.queue.setRootIsDecorated(False)
        self.queue.setAlternatingRowColors(True)
        self.queue.setIconSize(QSize(36, 28))
        self.queue.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.queue.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.queue.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.queue.header().resizeSection(2, 230)
        self.queue.itemDoubleClicked.connect(lambda *_: self.open_review())
        self.queue.itemSelectionChanged.connect(self._update_buttons)
        left.addWidget(self.queue, 1)

        buttons = QHBoxLayout()
        self.review_btn = QPushButton()
        self.review_btn.clicked.connect(self.open_review)
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self.remove_selected)
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.cancel_work)
        self.export_sel_btn = QPushButton()
        self.export_sel_btn.clicked.connect(lambda: self.export(selected_only=True))
        self.export_all_btn = QPushButton()
        self.export_all_btn.setObjectName("primary")
        self.export_all_btn.clicked.connect(lambda: self.export(selected_only=False))
        buttons.addWidget(self.review_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.export_sel_btn)
        buttons.addWidget(self.export_all_btn)
        left.addLayout(buttons)
        h.addLayout(left, 1)

        panel = QWidget()
        panel.setObjectName("panel")
        panel.setFixedWidth(300)
        p = QVBoxLayout(panel)
        p.setContentsMargins(16, 16, 16, 16)
        p.setSpacing(8)
        self.settings_title = QLabel()
        self.settings_title.setObjectName("section")
        p.addWidget(self.settings_title)

        self.level_label = QLabel()
        self.level_combo = QComboBox()
        for name in levels.LEVELS:
            self.level_combo.addItem(name, name)
        self.level_combo.setCurrentIndex(list(levels.LEVELS).index(self.prefs.level))
        self.level_combo.currentIndexChanged.connect(self._on_level)
        self.level_desc = QLabel()
        self.level_desc.setObjectName("hint")
        self.level_desc.setWordWrap(True)
        p.addWidget(self.level_label)
        p.addWidget(self.level_combo)
        p.addWidget(self.level_desc)
        p.addSpacing(6)

        self.mode_label = QLabel()
        self.mode_solid = QRadioButton()
        self.mode_pixel = QRadioButton()
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_solid)
        self.mode_group.addButton(self.mode_pixel)
        (self.mode_solid if self.prefs.mode == "solid" else self.mode_pixel).setChecked(True)
        self.mode_group.buttonToggled.connect(self._on_mode)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_solid)
        mode_row.addWidget(self.mode_pixel)
        p.addWidget(self.mode_label)
        p.addLayout(mode_row)
        p.addSpacing(6)

        self.padding_label = QLabel()
        self.padding_slider = QSlider(Qt.Orientation.Horizontal)
        self.padding_slider.setRange(0, 60)
        self.padding_slider.setValue(int(round(self.prefs.padding * 100)))
        self.padding_slider.valueChanged.connect(self._on_padding)
        p.addWidget(self.padding_label)
        p.addWidget(self.padding_slider)
        p.addSpacing(6)

        self.audio_box = QCheckBox()  # not saved: off at every start
        self.audio_warning = QLabel()
        self.audio_warning.setObjectName("warning")
        p.addWidget(self.audio_box)
        p.addWidget(self.audio_warning)
        p.addSpacing(6)

        self.dest_label = QLabel()
        self.dest_next = QRadioButton()
        self.dest_folder = QRadioButton()
        self.dest_group = QButtonGroup(self)
        self.dest_group.addButton(self.dest_next)
        self.dest_group.addButton(self.dest_folder)
        self.dest_next.setChecked(True)
        self.dest_folder.clicked.connect(self.choose_out_dir)
        self.dest_next.clicked.connect(self._dest_next)
        self.dest_path = QLabel()
        self.dest_path.setObjectName("hint")
        self.dest_path.setWordWrap(True)
        p.addWidget(self.dest_label)
        p.addWidget(self.dest_next)
        p.addWidget(self.dest_folder)
        p.addWidget(self.dest_path)
        p.addStretch(1)
        self.always_removed = QLabel()
        self.always_removed.setObjectName("hint")
        self.always_removed.setWordWrap(True)
        p.addWidget(self.always_removed)
        h.addWidget(panel)
        return page

    def retranslate(self) -> None:
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(list(i18n.LANGUAGES).index(i18n.language()))
        self.lang_combo.blockSignals(False)
        self.chip.setText("●  " + t("offline"))
        self.tagline.setText(t("tagline"))
        self.updates_btn.setText(t("updates"))
        self.updates_btn.setToolTip(t("updates_tip"))
        self.drop_title.setText(t("drop_title"))
        self.drop_formats.setText(t("drop_formats"))
        self.choose_btn.setText(t("choose_files"))
        self.queue.setHeaderLabels([t("col_file"), t("col_faces"), t("col_status")])
        self.review_btn.setText(t("review"))
        self.remove_btn.setText(t("remove"))
        self.cancel_btn.setText(t("cancel"))
        self.export_sel_btn.setText(t("export_selected"))
        self.export_all_btn.setText(t("export_all"))
        self.settings_title.setText(t("settings").upper())
        self.level_label.setText(t("level"))
        lang = i18n.language()
        for i, lvl in enumerate(levels.LEVELS.values()):
            self.level_combo.setItemText(i, lvl.label[lang])
        self.level_desc.setText(levels.get(self.level).description[lang])
        self.mode_label.setText(t("mode"))
        self.mode_solid.setText(t("mode_solid"))
        self.mode_pixel.setText(t("mode_pixel"))
        self._update_padding_label()
        self.audio_box.setText(t("keep_audio"))
        self.audio_warning.setText("⚠ " + t("audio_warning"))
        self.dest_label.setText(t("destination"))
        self.dest_next.setText(t("dest_next"))
        self.dest_folder.setText(t("dest_folder"))
        self.always_removed.setText(t("always_removed"))
        if self.review is not None:
            self.review.retranslate()
        self.refresh_queue()

    # -- settings ------------------------------------------------------------------
    @property
    def level(self) -> str:
        return self.level_combo.currentData()

    @property
    def mode(self) -> str:
        return "solid" if self.mode_solid.isChecked() else "pixel"

    @property
    def padding(self) -> float:
        return self.padding_slider.value() / 100

    def settings(self) -> dict:
        return {"level": self.level, "mode": self.mode, "padding": self.padding,
                "keep_audio": self.audio_box.isChecked(), "faces": True}  # fmt: skip

    def _on_language(self) -> None:
        code = self.lang_combo.currentData()
        i18n.set_language(code)
        self.prefs.language = code
        self.retranslate()

    def _on_level(self) -> None:
        new = self.level
        edited = any(it.edited for it in self.items if it.status != m.EXPORTED)
        if edited:
            answer = QMessageBox.question(self, t("reanalyze_title"), t("reanalyze_text"))
            if answer != QMessageBox.StandardButton.Yes:
                self.level_combo.blockSignals(True)
                self.level_combo.setCurrentIndex(list(levels.LEVELS).index(self.prefs.level))
                self.level_combo.blockSignals(False)
                return
        self.prefs.level = new
        self.level_desc.setText(levels.get(new).description[i18n.language()])
        for it in self.items:
            if it.status in (m.EXPORTING,):
                continue
            if it is self.current and it.status == m.ANALYZING:
                self._requeue.append(it)
                self.jobs.cancel()  # analysed again when the cancellation arrives
                continue
            it.plan, it.edited, it.status, it.progress = None, False, m.WAITING, 0
        self.refresh_queue()
        self.pump()

    def _on_mode(self, *_args) -> None:
        self.prefs.mode = self.mode
        if self.review is not None:
            self.review.refresh_settings()

    def _on_padding(self) -> None:
        self.prefs.padding = self.padding
        self._update_padding_label()
        if self.review is not None:
            self.review.refresh_settings()

    def _update_padding_label(self) -> None:
        self.padding_label.setText(f"{t('padding')}: {self.padding_slider.value()}%")

    def choose_out_dir(self) -> None:
        folder = picker.choose_folder(self)
        if folder:
            self.out_dir = folder
            self.dest_path.setText(folder.name or str(folder))
        elif self.out_dir is None:
            self.dest_next.setChecked(True)

    def _dest_next(self) -> None:
        self.out_dir = None
        self.dest_path.setText("")

    # -- adding files --------------------------------------------------------------
    def dragEnterEvent(self, e) -> None:  # noqa: N802
        if e.mimeData().hasUrls() and self.stack.currentWidget() is self.home:
            e.acceptProposedAction()
            self.drop.set_active(True)

    def dragLeaveEvent(self, _e) -> None:  # noqa: N802
        self.drop.set_active(False)

    def dropEvent(self, e) -> None:  # noqa: N802
        self.drop.set_active(False)
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        self.add_paths(paths)
        e.acceptProposedAction()

    def choose_files(self) -> None:
        self.add_paths(picker.choose_files(self, ACCEPTED))

    def add_paths(self, paths: list[Path]) -> None:
        expanded: list[Path] = []
        for p in paths:
            if p.is_dir():
                expanded += sorted(c for c in p.iterdir() if c.is_file())
            else:
                expanded.append(p)
        known = {it.path for it in self.items}
        skipped = 0
        for p in expanded:
            if p in known or p.name.startswith("."):
                continue
            try:
                kind = engine.kind_of(p)
            except InputError:
                skipped += 1
                continue
            self.items.append(m.Item(p, kind))
            known.add(p)
        if skipped:
            self.statusBar().showMessage(t("skipped_files", n=skipped), 6000)
        self.refresh_queue()
        self.pump()

    # -- queue -----------------------------------------------------------------------
    def status_text(self, it: m.Item) -> str:
        s = it.status
        if s == m.ANALYZING:
            return (
                t("st_analyzing_pct", pct=it.progress) if it.kind == "video" else t("st_analyzing")
            )
        if s == m.EXPORTING:
            return t("st_exporting", pct=it.progress)
        if s == m.EXPORTED:
            return t("st_exported", name=it.output_name)
        if s == m.ERROR:
            return t("st_error", msg=it.error)
        return t({m.WAITING: "st_waiting", m.READY: "st_ready", m.REVIEW: "st_review",
                  m.NO_FACES_FOUND: "st_no_faces", m.CANCELLED: "st_cancelled"}[s])  # fmt: skip

    def refresh_queue(self) -> None:
        selected = {id(self._item_of(w)) for w in self.queue.selectedItems()}
        self.queue.clear()
        color = {m.NO_FACES_FOUND: style.DANGER, m.ERROR: style.DANGER, m.REVIEW: style.AUTO,
                 m.EXPORTED: style.OK}  # fmt: skip
        for it in self.items:
            kind = t("kind_image") if it.kind == "image" else t("kind_video")
            w = QTreeWidgetItem([f"{it.name}", "" if it.faces is None else str(it.faces),
                                 self.status_text(it)])  # fmt: skip
            w.setToolTip(0, kind)
            if it.thumb is not None:
                w.setIcon(0, it.thumb)
            if it.status in color:
                w.setForeground(2, self._brush(color[it.status]))
            w.setData(0, Qt.ItemDataRole.UserRole, id(it))
            self.queue.addTopLevelItem(w)
            if id(it) in selected:
                w.setSelected(True)
        self.drop.setMinimumHeight(260 if not self.items else 130)
        self._update_buttons()

    @staticmethod
    def _brush(color: str):
        from PySide6.QtGui import QBrush, QColor

        return QBrush(QColor(color))

    def _item_of(self, w: QTreeWidgetItem) -> m.Item | None:
        key = w.data(0, Qt.ItemDataRole.UserRole)
        return next((it for it in self.items if id(it) == key), None)

    def selected_items(self) -> list[m.Item]:
        return [it for w in self.queue.selectedItems() if (it := self._item_of(w))]

    def _update_buttons(self) -> None:
        sel = self.selected_items()
        self.review_btn.setEnabled(len(sel) == 1 and sel[0].status in m.ANALYSED)
        self.remove_btn.setEnabled(bool(sel))
        self.cancel_btn.setEnabled(self.jobs.busy or bool(self.export_queue))
        ready = [it for it in self.items if it.status in m.ANALYSED]
        self.export_all_btn.setEnabled(bool(ready))
        self.export_sel_btn.setEnabled(any(it.status in m.ANALYSED for it in sel))

    def remove_selected(self) -> None:
        for it in self.selected_items():
            if it is self.current:
                self.jobs.cancel()
            if it in self.export_queue:
                self.export_queue.remove(it)
            self.items.remove(it)
        self.refresh_queue()

    def cancel_work(self) -> None:
        for it in self.export_queue:
            it.settle()
        self.export_queue.clear()
        if self.jobs.busy:
            self.jobs.cancel()
        self.refresh_queue()

    # -- worker scheduling -----------------------------------------------------------
    def pump(self) -> None:
        if self.jobs.busy:
            return
        nxt = next((it for it in self.items if it.status == m.WAITING), None)
        if nxt is not None:
            self._analyze(nxt)
            return
        if self.export_queue:
            self._render(self.export_queue.pop(0))
        self._update_buttons()

    def _analyze(self, it: m.Item) -> None:
        self.current = it
        it.status, it.progress = m.ANALYZING, 0
        self.refresh_queue()

        def progress(_stage, done, total) -> None:
            pct = int(done * 100 / total) if total else 0
            if pct != it.progress:
                it.progress = min(99, pct)
                self._update_row(it)

        def result(msg: dict) -> None:
            it.plan = plan_from_dict(msg["plan"])
            it.metadata_found = msg.get("metadata_found", [])
            it.has_audio = msg.get("has_audio", False)
            if msg.get("preview"):
                it.preview = m.decode_preview(msg["preview"])
                it.preview_scale = msg["scale"]
                it.thumb = m.icon_from(it.preview)
            elif it.kind == "video":
                self.frames.request("frame", {"path": str(it.path), "index": 0, "max_side": 160},
                                    on_result=lambda r: self._set_thumb(it, r))  # fmt: skip
            it.settle()
            self._done()

        def error(msg: str) -> None:
            it.status, it.error = m.ERROR, self._error_text(msg)
            self._done()

        def cancelled() -> None:
            # Cancelled because the level changed: analyse again; otherwise stop.
            if it in self._requeue:
                self._requeue.remove(it)
                it.status = m.WAITING
            else:
                it.status = m.CANCELLED
            self._done()

        self.jobs.request("analyze", {"path": str(it.path), "settings": self.settings()},
                          result, progress, error, cancelled)  # fmt: skip

    def _render(self, it: m.Item) -> None:
        self.current = it
        it.status, it.progress = m.EXPORTING, 0
        self.refresh_queue()

        def progress(stage, done, total) -> None:
            pct = int(done * 100 / total) if total else 0
            if pct != it.progress:
                it.progress = min(99, pct)
                self._update_row(it)

        def result(msg: dict) -> None:
            it.status, it.output_name = m.EXPORTED, msg["output_name"]
            self._done()

        def error(msg: str) -> None:
            it.status, it.error = m.ERROR, self._error_text(msg)
            self._done()

        def cancelled() -> None:
            it.settle()
            self._done()

        payload = {"path": str(it.path), "plan": plan_to_dict(it.plan), "settings": self.settings(),
                   "out_dir": str(self.out_dir) if self.out_dir else None}  # fmt: skip
        self.jobs.request("render", payload, result, progress, error, cancelled)

    def _error_text(self, msg: str) -> str:
        return t("worker_crashed") if msg == "worker" else msg

    def _set_thumb(self, it: m.Item, msg: dict) -> None:
        it.thumb = m.icon_from(m.decode_preview(msg["preview"]))
        self.refresh_queue()

    def _done(self) -> None:
        self.current = None
        self.refresh_queue()
        self.pump()

    def _update_row(self, it: m.Item) -> None:
        for i in range(self.queue.topLevelItemCount()):
            w = self.queue.topLevelItem(i)
            if w.data(0, Qt.ItemDataRole.UserRole) == id(it):
                w.setText(2, self.status_text(it))

    def _on_worker_crashed(self) -> None:
        self.statusBar().showMessage(t("worker_crashed"), 6000)

    # -- export ------------------------------------------------------------------------
    def export(self, selected_only: bool) -> None:
        pool = self.selected_items() if selected_only else self.items
        todo = [it for it in pool if it.status in m.ANALYSED and it not in self.export_queue]
        if not todo:
            QMessageBox.information(self, WINDOW_TITLE, t("nothing_to_export"))
            return
        risky = [it for it in todo if it.uncovered_risk]
        if risky:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(t("confirm_no_faces_title"))
            box.setText(t("confirm_no_faces_text", n=len(risky)))
            anyway = box.addButton(t("export_anyway"), QMessageBox.ButtonRole.DestructiveRole)
            skip = box.addButton(t("skip_them"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(skip)
            box.exec()
            if box.clickedButton() is not anyway:
                todo = [it for it in todo if it not in risky]
        self.export_queue += todo
        self.refresh_queue()
        self.pump()

    # -- review --------------------------------------------------------------------------
    def open_review(self) -> None:
        sel = self.selected_items()
        if len(sel) != 1 or sel[0].status not in m.ANALYSED or sel[0].plan is None:
            return
        it = sel[0]
        if it.kind == "image":
            self.review = ImageReview(it, self.settings)
        else:
            self.review = VideoReview(it, self.settings, self.frames)
        self.review.finished.connect(self.close_review)
        self.review.changed.connect(self.refresh_queue)
        self.stack.addWidget(self.review)
        self.stack.setCurrentWidget(self.review)

    def close_review(self) -> None:
        if self.review is None:
            return
        self.stack.setCurrentWidget(self.home)
        self.stack.removeWidget(self.review)
        self.review.deleteLater()
        self.review = None
        self.refresh_queue()

    # -- closing ---------------------------------------------------------------------------
    def closeEvent(self, e) -> None:  # noqa: N802
        if self.jobs.busy and any(it.status == m.EXPORTING for it in self.items):
            answer = QMessageBox.question(self, t("quit_busy_title"), t("quit_busy_text"))
            if answer != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
        self.jobs.shutdown()
        self.frames.shutdown()
        self.prefs.sync()
        e.accept()
