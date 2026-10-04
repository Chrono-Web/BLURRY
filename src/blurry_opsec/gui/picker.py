"""File pickers that remember nothing: opening files, and saving the export.

The system dialogs record recent folders (Windows' common dialogs in the
registry, GTK's in recently-used.xbel), and Qt's own dialog saves the last
visited folder and a history in the "QtProject" preferences, whatever format
is configured. All of them would leave paths on disk (R2). These pickers are
built on QFileSystemModel and store nothing: opening starts from the home
folder every time, saving from the original's folder, as on the Mac.
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTreeView,
    QVBoxLayout,
)

from blurry_opsec.gui import strings as L
from blurry_opsec.gui.widgets import button, label

_PLACES = (
    ("home", QStandardPaths.StandardLocation.HomeLocation),
    ("desktop", QStandardPaths.StandardLocation.DesktopLocation),
    ("downloads", QStandardPaths.StandardLocation.DownloadLocation),
    ("pictures", QStandardPaths.StandardLocation.PicturesLocation),
    ("movies", QStandardPaths.StandardLocation.MoviesLocation),
    ("documents", QStandardPaths.StandardLocation.DocumentsLocation),
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
    """folders_only: the files are shown but cannot be chosen (saving)."""

    def __init__(
        self,
        parent,
        title: str,
        folders_only: bool,
        extensions: list[str],
        start: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 520)
        self.folders_only = folders_only
        self.model = QFileSystemModel(self)
        self.model.setRootPath("")
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files)
        self.model.setNameFilters(
            [f"*{e}" for e in extensions] + [f"*{e.upper()}" for e in extensions]
        )
        self.model.setNameFilterDisables(folders_only)  # saving: other files greyed out
        self.model.setReadOnly(True)

        self.places = QListWidget()
        self.places.setFixedWidth(170)
        for key, loc in _PLACES:
            path = QStandardPaths.writableLocation(loc)
            if path and Path(path).is_dir():
                item = QListWidgetItem(L.place(key))
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
        self.where = label("", "secondary")
        top = QHBoxLayout()
        top.addWidget(self.up_btn)
        top.addWidget(self.where, 1)

        self.ok_btn = button(
            L.picker_export() if folders_only else L.picker_add(), "primary", self.accept
        )
        self.ok_btn.setDefault(True)
        self.bottom = QHBoxLayout()
        self.bottom.addStretch(1)
        self.bottom.addWidget(button(L.cancel(), "", self.reject))
        self.bottom.addWidget(self.ok_btn)

        body = QHBoxLayout()
        body.addWidget(self.places)
        right = QVBoxLayout()
        right.addLayout(top)
        right.addWidget(self.view, 1)
        body.addLayout(right, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addLayout(self.bottom)
        self.current = Path.home()
        self.go(start if start is not None and start.is_dir() else Path.home())

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
        return [p for p in paths if p.is_file() or p.is_dir()]


class SavePicker(Picker):
    """Where to save the export: a folder and a name."""

    def __init__(self, parent, start: Path, name: str, extension: str) -> None:
        super().__init__(parent, L.export().rstrip("…"), True, [extension], start)
        self.extension = extension
        self.name = QLineEdit(name)
        self.name.setMinimumWidth(320)
        stem = len(name) - len(extension)
        self.name.setSelection(0, max(0, stem))
        self.bottom.insertWidget(0, label(L.picker_name(), "secondary"))
        self.bottom.insertWidget(1, self.name, 1)
        self.view.clicked.connect(self._on_click)
        self.name.setFocus()

    def _on_click(self, index: QModelIndex) -> None:
        path = Path(self.model.filePath(index))
        if path.is_file():
            self.name.setText(path.name)

    def target(self) -> Path | None:
        name = Path(self.name.text().strip()).name
        if not name:
            return None
        if Path(name).suffix.lower() != self.extension:
            name += self.extension
        return self.current / name

    def accept(self) -> None:
        target = self.target()
        if target is None:
            return
        if target.exists():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(L.replace_title(target.name))
            box.setInformativeText(L.replace_text())
            replace = box.addButton(L.replace(), QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(L.cancel(), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not replace:
                return
        super().accept()


def choose_files(parent, extensions: list[str]) -> list[Path]:
    dlg = Picker(parent, L.choose_files().rstrip("…"), False, extensions)
    return dlg.selected_paths() if dlg.exec() == QDialog.DialogCode.Accepted else []


def choose_output(parent, original: Path, extension: str) -> Path | None:
    """The save picker, opened on the original's folder with <name>_blurry.<ext>."""
    ext = "." + extension.lstrip(".")
    dlg = SavePicker(parent, original.parent, f"{original.stem}_blurry{ext}", ext)
    return dlg.target() if dlg.exec() == QDialog.DialogCode.Accepted else None
