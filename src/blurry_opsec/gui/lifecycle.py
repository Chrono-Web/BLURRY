"""First-run guide and local lifecycle controls. No network requests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from blurry_opsec import __version__, i18n, levels
from blurry_opsec.gui.widgets import label

RELEASES_URL = "https://github.com/Chrono-Web/BLURRY/releases"


def text(it: str, en: str) -> str:
    return it if i18n.language() == "it" else en


def guide(window, first: bool = False) -> QDialog:
    dlg = QDialog(window)
    dlg.setWindowTitle(text("Benvenuto in Blurry", "Welcome to Blurry"))
    dlg.setMinimumWidth(520)
    layout = QVBoxLayout(dlg)
    for it, en in [
        ("1. Scegli foto e video", "1. Choose photos and videos"),
        (
            "Tutto viene elaborato sul computer, senza rete e senza telemetria. "
            "Nessuna cronologia di file o cartelle viene salvata.",
            "Everything is processed on your computer, offline, without telemetry. "
            "No file or folder history is saved.",
        ),
        ("2. Rivedi e correggi i volti", "2. Review and correct faces"),
        (
            "Apri Rivedi prima di esportare. Aggiungi, sposta o elimina riquadri nelle foto; "
            "nei video controlla le tracce e aggiungi coperture manuali sugli intervalli. "
            "Il rilevatore può mancare volti; corpi, luoghi e voci possono identificare.",
            "Open Review before exporting. Add, move or remove photo boxes; "
            "in videos check tracks and add manual covers over time intervals. "
            "The detector can miss faces; bodies, places and voices can identify people.",
        ),
        ("3. Controlla l’anteprima ed esporta", "3. Check the preview and export"),
        (
            "Blurry crea nuovi file senza metadati e preserva gli originali. "
            "L’audio è disattivato a ogni avvio. Conserva solo sensibilità, copertura, "
            "margine, lingua e completamento della guida.",
            "Blurry creates new files without metadata and preserves originals. "
            "Audio is off at every launch. Only sensitivity, coverage, padding, "
            "language and guide completion are saved.",
        ),
    ]:
        item = label(text(it, en), "guideHeading" if it[:1].isdigit() else "body")
        item.setWordWrap(True)
        layout.addWidget(item)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(text("Inizia", "Start"))
    buttons.accepted.connect(dlg.accept)
    layout.addWidget(buttons)
    if first:
        dlg.accepted.connect(lambda: setattr(window.prefs, "onboarded", True))
    dlg.setModal(True)
    dlg.open()
    return dlg


def uninstall_command() -> list[str] | None:
    if not getattr(sys, "frozen", False):
        return None
    root = Path(sys.executable).resolve().parent
    if sys.platform == "win32" and (root / "unins000.exe").is_file():
        return [str(root / "unins000.exe")]
    expected = Path.home() / ".local/opt/blurry"
    if sys.platform == "linux" and root == expected and (root / "uninstall.sh").is_file():
        return ["/bin/sh", str(root / "uninstall.sh")]
    return None


def remove(window) -> None:
    if window.jobs.busy or window.frames.busy:
        QMessageBox.information(
            window,
            "Blurry",
            text(
                "Attendi la fine dell’elaborazione prima di disinstallare.",
                "Wait for processing to finish before uninstalling.",
            ),
        )
        return
    command = uninstall_command()
    if command is None:
        QMessageBox.information(
            window,
            "Blurry",
            text(
                "Questa copia non è installata dal pacchetto Blurry. Usa il gestore "
                "con cui l’hai installata. Ripristina le preferenze per riavviare la guida.",
                "This copy was not installed by a Blurry installer. Use your original "
                "package manager. Clear preferences to restart the guide.",
            ),
        )
        return
    answer = QMessageBox.question(
        window,
        text("Disinstalla Blurry", "Uninstall Blurry"),
        text(
            "Rimuovere Blurry e tutte le preferenze? Foto, video ed esportazioni rimangono. "
            "Reinstallando ripartirà la guida.",
            "Remove Blurry and all preferences? Photos, videos and exports remain. "
            "Reinstalling will restart the guide.",
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    try:
        env = os.environ.copy()
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env.pop("LD_LIBRARY_PATH_ORIG")
        else:
            env.pop("LD_LIBRARY_PATH", None)
        # The Linux helper waits for this process to exit before removing files.
        if sys.platform == "linux":
            command.append(str(os.getpid()))
        subprocess.Popen(command, env=env, start_new_session=True)  # noqa: S603
    except OSError:
        QMessageBox.warning(
            window,
            "Blurry",
            text("Impossibile avviare la disinstallazione.", "Could not start the uninstaller."),
        )
        return
    window.close()


def preferences(window) -> QDialog:
    dlg = QDialog(window)
    dlg.setWindowTitle(text("Impostazioni di Blurry", "Blurry settings"))
    dlg.setMinimumSize(560, 370)
    layout = QVBoxLayout(dlg)
    tabs = QTabWidget()
    layout.addWidget(tabs)

    def page(title, description):
        w = QWidget()
        w.setObjectName("lifecyclePage")
        box = QVBoxLayout(w)
        box.setContentsMargins(18, 18, 18, 18)
        box.setSpacing(10)
        item = label(description, "body")
        item.setWordWrap(True)
        box.addWidget(item)
        tabs.addTab(w, title)
        return box

    def button(box, title, callback):
        b = QPushButton(title)
        b.clicked.connect(callback)
        box.addWidget(b)
        return b

    box = page(
        text("Generali", "General"),
        text(
            "Sensibilità, copertura e margine si applicano anche alla finestra principale "
            "e si applicano alla revisione aperta. "
            "Audio e destinazione valgono solo per la sessione.",
            "Sensitivity, coverage and padding also apply to the main window and "
            "to the open review. Audio and destination are session-only.",
        ),
    )

    def combo(caption, choices, current, callback):
        box.addWidget(label(caption))
        control = QComboBox()
        for key, title in choices:
            control.addItem(title, key)
        control.setCurrentIndex(control.findData(current))
        control.activated.connect(lambda index: callback(control.itemData(index)))
        box.addWidget(control)
        return control

    def change_level(value):
        window.level_seg._buttons[value].click()
        sensitivity.setCurrentIndex(sensitivity.findData(window.prefs.level))

    lang = i18n.language()
    sensitivity = combo(
        text("Sensibilità", "Sensitivity"),
        [(k, v.label[lang]) for k, v in levels.LEVELS.items()],
        window.level,
        change_level,
    )

    def change_mode(value):
        window.mode_seg.set_value(value)
        window._on_mode()

    coverage = combo(
        text("Copertura", "Coverage"),
        [
            ("solid", text("Rettangolo nero", "Black rectangle")),
            ("pixel", text("Pixelazione", "Pixelation")),
        ],
        window.mode,
        change_mode,
    )
    margin_label = label()
    box.addWidget(margin_label)
    margin = QSlider(Qt.Orientation.Horizontal)
    margin.setRange(0, 60)
    margin.setValue(window.padding_slider.value())

    def change_margin(value):
        margin_label.setText(text("Margine", "Padding") + f": {value}%")
        window.padding_slider.setValue(value)

    margin.valueChanged.connect(change_margin)
    change_margin(margin.value())
    box.addWidget(margin)

    def change_language(value):
        window._on_language(value)
        dlg.close()
        window.show_preferences()

    combo(
        text("Lingua", "Language"), [("it", "Italiano"), ("en", "English")], lang, change_language
    )

    def reset():
        window.level_seg._buttons[levels.DEFAULT_LEVEL].click()
        if window.prefs.level != levels.DEFAULT_LEVEL:
            return
        window.mode_seg.set_value(levels.DEFAULT_MODE)
        window._on_mode()
        window.padding_slider.setValue(round(levels.DEFAULT_PADDING * 100))
        window.audio_box.setChecked(False)
        sensitivity.setCurrentIndex(sensitivity.findData(window.level))
        coverage.setCurrentIndex(coverage.findData(window.mode))
        margin.setValue(window.padding_slider.value())
        window.prefs.sync()

    button(box, text("Ripristina valori consigliati", "Restore recommended values"), reset)
    button(box, text("Rivedi la guida", "Show guide again"), lambda: guide(window))
    box.addStretch()
    box = page(
        text("Aggiornamenti", "Updates"),
        text(
            f"Versione installata: {__version__}. Nessun controllo automatico. "
            "Il pulsante apre le Release nel browser esterno, solo su tua richiesta. "
            "Scarica il pacchetto e controlla SHA256SUMS e le attestazioni; "
            "installa la nuova versione sopra quella attuale.",
            f"Installed version: {__version__}. No automatic checks. "
            "The button opens Releases in your external browser, only on request. "
            "Download the package and verify SHA256SUMS and attestations; "
            "install the new version over the current one.",
        ),
    )
    button(
        box,
        text("Apri le Release nel browser", "Open Releases in browser"),
        lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL)),
    )
    box.addStretch()
    box = page(
        text("Disinstallazione", "Uninstall"),
        text(
            "La disinstallazione completa rimuove applicazione e preferenze di questo utente. "
            "Gli originali e le esportazioni rimangono. La guida riparte dopo la reinstallazione.",
            "Complete uninstall removes the application and this user’s preferences. "
            "Originals and exports remain. The guide restarts after reinstalling.",
        ),
    )
    button(box, text("Disinstalla Blurry…", "Uninstall Blurry…"), lambda: remove(window))

    def clear():
        if (
            QMessageBox.question(
                dlg,
                "Blurry",
                text(
                    "Cancellare tutte le preferenze e chiudere Blurry?",
                    "Clear all preferences and close Blurry?",
                ),
            )
            == QMessageBox.StandardButton.Yes
        ):
            window.prefs.clear()
            dlg.close()
            window.close()

    button(box, text("Cancella preferenze e chiudi…", "Clear preferences and close…"), clear)
    box.addStretch()
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.button(QDialogButtonBox.StandardButton.Close).setText(text("Chiudi", "Close"))
    buttons.rejected.connect(dlg.close)
    layout.addWidget(buttons)
    dlg.open()
    return dlg
