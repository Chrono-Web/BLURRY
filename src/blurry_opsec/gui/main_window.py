"""Main window: drop area, queue, settings, export."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import engine, i18n, image_io, levels, video_io
from blurry_opsec.files import InputError
from blurry_opsec.gui import lifecycle, native, picker
from blurry_opsec.gui import model as m
from blurry_opsec.gui.prefs import Prefs
from blurry_opsec.gui.review import ImageReview, VideoReview
from blurry_opsec.gui.widgets import (
    STATUS_ROLE,
    DragArea,
    GlassPanel,
    HudFrame,
    PillDelegate,
    Segmented,
    Switch,
    label,
)
from blurry_opsec.gui.worker_client import WorkerClient
from blurry_opsec.i18n import t
from blurry_opsec.plan import plan_from_dict, plan_to_dict

ACCEPTED = sorted(image_io.IMAGE_EXTENSIONS | video_io.VIDEO_EXTENSIONS)
WINDOW_TITLE = "Blurry"  # never a file name (R2)
IS_MAC = sys.platform == "darwin"


class MainWindow(QMainWindow):
    def __init__(self, prefs: Prefs, glass: bool = False) -> None:
        super().__init__()
        self.prefs = prefs
        self.glass = glass  # native window material underneath (macOS)
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
        self.resize(1200, 780)
        self.setMinimumSize(940, 620)
        if glass:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        root = QWidget()
        root.setObjectName("root")
        if glass:
            # The content runs under the transparent title bar; the header leaves
            # room for the traffic lights itself.
            for w in (self, root):
                w.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 4 if glass else 14, 18, 16)
        outer.setSpacing(14)
        outer.addWidget(self._build_header())
        self.stack = QStackedWidget()
        self.home = self._build_home()
        self.stack.addWidget(self.home)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.retranslate()
        self.refresh_queue()

    def show_guide(self, first: bool = False) -> None:
        self.guide_dialog = lifecycle.guide(self, first)

    def show_preferences(self) -> None:
        self.preferences_dialog = lifecycle.preferences(self)

    # -- layout ------------------------------------------------------------------
    def _build_header(self) -> QWidget:
        bar = DragArea()
        h = QHBoxLayout(bar)
        left = native.TRAFFIC_LIGHTS_WIDTH if self.glass else 0
        h.setContentsMargins(left, 0, 0, 0)
        if self.glass:
            bar.setFixedHeight(native.TITLEBAR_HEIGHT + 4)  # centred on the traffic lights
        h.setSpacing(12)
        h.addWidget(label("BLURRY", "wordmark"))
        self.chip = label("", "chip")
        h.addWidget(self.chip)
        self.tagline = label("", "muted")
        h.addSpacing(6)
        h.addWidget(self.tagline)
        h.addStretch(1)
        self.lang_seg = Segmented([(c, c.upper()) for c in i18n.LANGUAGES], i18n.language())
        self.lang_seg.setFixedWidth(84)
        self.lang_seg.changed.connect(self._on_language)
        h.addWidget(self.lang_seg)
        self.updates_btn = QPushButton()
        self.updates_btn.setObjectName("link")
        self.updates_btn.clicked.connect(self.show_preferences)
        self.guide_btn = QPushButton()
        self.guide_btn.setObjectName("link")
        self.guide_btn.clicked.connect(self.show_guide)
        h.addWidget(self.guide_btn)
        h.addWidget(self.updates_btn)
        return bar

    def _build_home(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(14)
        self.drop = HudFrame()
        self.drop.setObjectName("drop")
        dl = QVBoxLayout(self.drop)
        dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.setSpacing(6)
        self.drop_title = label("", "dropTitle")
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_formats = label("", "dropFormats")
        self.drop_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.choose_btn = QPushButton()
        self.choose_btn.clicked.connect(self.choose_files)
        dl.addWidget(self.drop_title)
        dl.addWidget(self.drop_formats)
        dl.addSpacing(8)
        dl.addWidget(self.choose_btn, 0, Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.drop)

        queue_panel = GlassPanel()
        ql = QVBoxLayout(queue_panel)
        ql.setContentsMargins(10, 8, 10, 10)
        self.queue = QTreeWidget()
        self.queue.setColumnCount(3)
        self.queue.setRootIsDecorated(False)
        self.queue.setIconSize(QSize(40, 30))
        self.queue.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.queue.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.queue.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.queue.header().resizeSection(1, 64)
        self.queue.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.queue.header().resizeSection(2, 250)
        self.queue.setItemDelegateForColumn(2, PillDelegate(self.queue))
        self.queue.itemDoubleClicked.connect(lambda *_: self.open_review())
        self.queue.itemSelectionChanged.connect(self._update_buttons)
        ql.addWidget(self.queue, 1)
        self.empty_hint = label("", "hint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ql.addWidget(self.empty_hint)
        left.addWidget(queue_panel, 1)

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
        for b in (self.review_btn, self.remove_btn, self.cancel_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.export_sel_btn)
        buttons.addWidget(self.export_all_btn)
        left.addLayout(buttons)
        h.addLayout(left, 1)

        panel = GlassPanel()
        panel.setFixedWidth(300)
        p = QVBoxLayout(panel)
        p.setContentsMargins(18, 18, 18, 18)
        p.setSpacing(8)
        self.settings_title = label()
        p.addWidget(self.settings_title)
        p.addSpacing(8)

        self.level_label = label()
        self.level_seg = Segmented([(k, k) for k in levels.LEVELS], self.prefs.level)
        self.level_seg.changed.connect(self._on_level)
        self.level_desc = label("", "hint")
        self.level_desc.setWordWrap(True)
        p.addWidget(self.level_label)
        p.addWidget(self.level_seg)
        p.addWidget(self.level_desc)
        p.addSpacing(10)

        self.mode_label = label()
        self.mode_seg = Segmented([("solid", "solid"), ("pixel", "pixel")], self.prefs.mode)
        self.mode_seg.changed.connect(self._on_mode)
        p.addWidget(self.mode_label)
        p.addWidget(self.mode_seg)
        p.addSpacing(10)

        pad_row = QHBoxLayout()
        self.padding_label = label()
        self.padding_value = label("", "value")
        pad_row.addWidget(self.padding_label)
        pad_row.addStretch(1)
        pad_row.addWidget(self.padding_value)
        self.padding_slider = QSlider(Qt.Orientation.Horizontal)
        self.padding_slider.setRange(0, 60)
        self.padding_slider.setValue(int(round(self.prefs.padding * 100)))
        self.padding_slider.valueChanged.connect(self._on_padding)
        p.addLayout(pad_row)
        p.addWidget(self.padding_slider)
        p.addSpacing(10)

        audio_row = QHBoxLayout()
        self.audio_label = label("", "muted")
        self.audio_label.setStyleSheet("color: white;")
        self.audio_box = Switch()  # not saved: off at every start
        audio_row.addWidget(self.audio_label)
        audio_row.addStretch(1)
        audio_row.addWidget(self.audio_box)
        self.audio_warning = label("", "warning")
        p.addLayout(audio_row)
        p.addWidget(self.audio_warning)
        p.addSpacing(10)

        self.dest_label = label()
        self.dest_seg = Segmented([("next", "next"), ("folder", "folder")], "next")
        self.dest_seg.changed.connect(self._on_dest)
        self.dest_path = label("", "hint")
        self.dest_path.setWordWrap(True)
        p.addWidget(self.dest_label)
        p.addWidget(self.dest_seg)
        p.addWidget(self.dest_path)
        p.addStretch(1)
        self.always_removed = label("", "hint")
        self.always_removed.setWordWrap(True)
        p.addWidget(self.always_removed)
        h.addWidget(panel)
        return page

    def retranslate(self) -> None:
        self.lang_seg.set_value(i18n.language())
        self.chip.setText("●  " + t("offline"))
        self.tagline.setText(t("tagline"))
        self.updates_btn.setText(t("settings"))
        self.guide_btn.setText(lifecycle.text("Guida", "Guide"))
        self.updates_btn.setToolTip(
            lifecycle.text("Impostazioni e aggiornamenti manuali", "Settings and manual updates")
        )
        self.drop_title.setText(t("drop_title"))
        self.drop_formats.setText(t("drop_formats").upper())
        self.choose_btn.setText(t("choose_files"))
        self.queue.setHeaderLabels([t("col_file").upper(), t("col_faces").upper(),
                                    t("col_status").upper()])  # fmt: skip
        self.empty_hint.setText(t("queue_empty"))
        self.review_btn.setText(t("review"))
        self.remove_btn.setText(t("remove"))
        self.cancel_btn.setText(t("cancel"))
        self.export_sel_btn.setText(t("export_selected"))
        self.export_all_btn.setText(t("export_all"))
        self.settings_title.setText(t("settings").upper())
        lang = i18n.language()
        self.level_label.setText(t("level").upper())
        self.level_seg.set_texts({k: v.label[lang].upper() for k, v in levels.LEVELS.items()})
        self.level_desc.setText(levels.get(self.level).description[lang])
        self.mode_label.setText(t("mode").upper())
        self.mode_seg.set_texts(
            {"solid": t("mode_solid").upper(), "pixel": t("mode_pixel").upper()}
        )
        self.padding_label.setText(t("padding").upper())
        self._update_padding_label()
        self.audio_label.setText(t("keep_audio"))
        self.audio_warning.setText(t("audio_warning"))
        self.dest_label.setText(t("destination").upper())
        self.dest_seg.set_texts(
            {"next": t("dest_next").upper(), "folder": t("dest_folder").upper()}
        )
        self.dest_seg.setToolTip(t("dest_next_tip"))
        self.always_removed.setText(t("always_removed"))
        if self.review is not None:
            self.review.retranslate()
        self.refresh_queue()

    # -- settings ------------------------------------------------------------------
    @property
    def level(self) -> str:
        return self.level_seg.value()

    @property
    def mode(self) -> str:
        return self.mode_seg.value()

    @property
    def padding(self) -> float:
        return self.padding_slider.value() / 100

    def settings(self) -> dict:
        return {"level": self.level, "mode": self.mode, "padding": self.padding,
                "keep_audio": self.audio_box.isChecked(), "faces": True}  # fmt: skip

    def _on_language(self, code: str) -> None:
        i18n.set_language(code)
        self.prefs.language = code
        self.retranslate()

    def _on_level(self, new: str) -> None:
        if new == self.prefs.level:
            return
        edited = any(it.edited for it in self.items if it.status != m.EXPORTED)
        if edited:
            answer = QMessageBox.question(self, t("reanalyze_title"), t("reanalyze_text"))
            if answer != QMessageBox.StandardButton.Yes:
                self.level_seg.set_value(self.prefs.level)
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
        self.padding_value.setText(f"{self.padding_slider.value()}%")

    def _on_dest(self, key: str) -> None:
        if key == "folder":
            self.choose_out_dir()
        else:
            self.out_dir = None
            self.dest_path.setText("")

    def choose_out_dir(self) -> None:
        folder = picker.choose_folder(self)
        if folder:
            self.out_dir = folder
            self.dest_path.setText("→ " + (folder.name or str(folder)))
        elif self.out_dir is None:
            self.dest_seg.set_value("next")

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self.glass and not getattr(self, "_glass_applied", False):
            self._glass_applied = True
            native.apply_macos_glass(self)

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
        for it in self.items:
            kind = t("kind_image") if it.kind == "image" else t("kind_video")
            w = QTreeWidgetItem([f"{it.name}", "" if it.faces is None else str(it.faces),
                                 self.status_text(it).upper()])  # fmt: skip
            w.setToolTip(0, kind)
            if it.thumb is not None:
                w.setIcon(0, it.thumb)
            w.setData(0, Qt.ItemDataRole.UserRole, id(it))
            w.setData(2, STATUS_ROLE, it.status)
            self.queue.addTopLevelItem(w)
            if id(it) in selected:
                w.setSelected(True)
        self.drop.setMinimumHeight(300 if not self.items else 140)
        self.drop.setMaximumHeight(16777215 if not self.items else 160)
        self.empty_hint.setVisible(not self.items)
        self._update_buttons()

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
                w.setText(2, self.status_text(it).upper())

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
