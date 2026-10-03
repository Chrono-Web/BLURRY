"""A file and folder picker that remembers nothing.

The system dialogs record recent folders (macOS NSNavRecentPlaces and the
like), and Qt's own dialog saves the last visited folder and a history in the
"QtProject" preferences, whatever format is configured. Both would leave paths
on disk (R2). This picker is built on QFileSystemModel, starts from the home
folder every time and stores nothing.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, QStandardPaths, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileSystemModel,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeView,
    QVBoxLayout,
)

from blurry_opsec.i18n import t

_PLACES = (
    ("place_home", QStandardPaths.StandardLocation.HomeLocation),
    ("place_desktop", QStandardPaths.StandardLocation.DesktopLocation),
    ("place_downloads", QStandardPaths.StandardLocation.DownloadLocation),
    ("place_pictures", QStandardPaths.StandardLocation.PicturesLocation),
    ("place_movies", QStandardPaths.StandardLocation.MoviesLocation),
    ("place_documents", QStandardPaths.StandardLocation.DocumentsLocation),
)


def _volumes() -> list[Path]:
    roots = [Path("/Volumes"), Path("/media"), Path("/mnt")]
    out = []
    for root in roots:
        try:
            out += [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        except OSError:
            continue
    if not out:
        out = [Path(d.absolutePath()) for d in QDir.drives()]
    return out


class Picker(QDialog):
    def __init__(self, parent, title: str, folders_only: bool, extensions: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 520)
        self.folders_only = folders_only
        self.model = QFileSystemModel(self)
        self.model.setRootPath("")
        flags = QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot
        if not folders_only:
            flags |= QDir.Filter.Files
            self.model.setNameFilters(
                [f"*{e}" for e in extensions] + [f"*{e.upper()}" for e in extensions]
            )
            self.model.setNameFilterDisables(False)
        self.model.setFilter(flags)
        self.model.setReadOnly(True)

        self.places = QListWidget()
        self.places.setFixedWidth(170)
        for key, loc in _PLACES:
            path = QStandardPaths.writableLocation(loc)
            if path and Path(path).is_dir():
                item = QListWidgetItem(t(key))
                item.setData(Qt.ItemDataRole.UserRole, path)
                self.places.addItem(item)
        for vol in _volumes():
            item = QListWidgetItem(vol.name or str(vol))
            item.setData(Qt.ItemDataRole.UserRole, str(vol))
            self.places.addItem(item)
        self.places.itemClicked.connect(lambda it: self.go(Path(it.data(Qt.ItemDataRole.UserRole))))

        self.view = QTreeView()
        self.view.setModel(self.model)
        self.view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
            if folders_only
            else QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.view.setColumnHidden(2, True)  # type
        self.view.doubleClicked.connect(self._on_double)
        self.view.setRootIsDecorated(False)
        self.view.setItemsExpandable(False)

        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(36)
        self.up_btn.clicked.connect(lambda: self.go(self.current.parent))
        self.where = QLabel()
        self.where.setObjectName("muted")
        top = QHBoxLayout()
        top.addWidget(self.up_btn)
        top.addWidget(self.where, 1)

        self.ok_btn = QPushButton(t("picker_choose_folder") if folders_only else t("picker_add"))
        self.ok_btn.setObjectName("primary")
        self.ok_btn.clicked.connect(self.accept)
        cancel = QPushButton(t("cancel"))
        cancel.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(cancel)
        bottom.addWidget(self.ok_btn)

        body = QHBoxLayout()
        body.addWidget(self.places)
        right = QVBoxLayout()
        right.addLayout(top)
        right.addWidget(self.view, 1)
        body.addLayout(right, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addLayout(bottom)
        self.current = Path.home()
        self.go(Path.home())

    def go(self, path: Path) -> None:
        if not path.is_dir():
            return
        self.current = path
        self.view.setRootIndex(self.model.index(str(path)))
        self.where.setText(path.name or str(path))

    def _on_double(self, index: QModelIndex) -> None:
        path = Path(self.model.filePath(index))
        if path.is_dir():
            self.go(path)
        elif not self.folders_only:
            self.accept()

    def selected_paths(self) -> list[Path]:
        rows = {i.row(): i for i in self.view.selectionModel().selectedRows(0)}
        paths = [Path(self.model.filePath(i)) for i in rows.values()]
        if self.folders_only:
            dirs = [p for p in paths if p.is_dir()]
            return dirs[:1] or [self.current]
        return [p for p in paths if p.is_file() or p.is_dir()]


def choose_files(parent, extensions: list[str]) -> list[Path]:
    dlg = Picker(parent, t("choose_files"), False, extensions)
    return dlg.selected_paths() if dlg.exec() == QDialog.DialogCode.Accepted else []


def choose_folder(parent) -> Path | None:
    dlg = Picker(parent, t("dest_choose"), True, [])
    return dlg.selected_paths()[0] if dlg.exec() == QDialog.DialogCode.Accepted else None
