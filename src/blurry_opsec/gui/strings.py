"""Interface strings in Italian and English: the same table as the Mac app's
macos/Sources/Blurry/Strings.swift, so that both apps say the same things.
Where the Mac says Mac, Finder or ⌘, this says computer, folder or Ctrl.
"""

from __future__ import annotations

from blurry_opsec import i18n, levels


def _italian() -> bool:
    return i18n.language() == "it"


def _t(it: str, en: str) -> str:
    return it if _italian() else en


# Drop window
def drop_title() -> str:
    return _t("Trascina qui foto e video", "Drop photos and videos here")


def choose_files() -> str:
    return _t("Scegli file…", "Choose Files…")


def engine_missing() -> str:
    return _t("Motore non trovato: reinstalla Blurry.", "Engine not found: reinstall Blurry.")


def skipped(n: int) -> str:
    return _t(
        f"{n} file ignorati: formato non supportato.", f"{n} files skipped: unsupported format."
    )


def worker_crashed() -> str:
    return _t(
        "Il motore si è fermato ed è stato riavviato.", "The engine stopped and was restarted."
    )


# Guide: steps
def step_title(step: str) -> str:
    return {
        "sensitivity": _t("SENSIBILITÀ", "SENSITIVITY"),
        "cover": _t("COPERTURA", "COVER"),
        "margin": _t("MARGINE", "MARGIN"),
        "audio": "AUDIO",
        "result": _t("RISULTATO", "RESULT"),
    }[step]


def step_question(step: str) -> str:
    return {
        "sensitivity": _t("Quanto deve cercare i volti?", "How hard should it look for faces?"),
        "cover": _t("Come coprirli?", "How should they be covered?"),
        "margin": _t("Quanto spazio attorno al volto?", "How much room around each face?"),
        "audio": _t("E l'audio del video?", "What about the video's sound?"),
        "result": _t("Ecco il risultato.", "Here is the result."),
    }[step]


def back() -> str:
    return _t("Indietro", "Back")


def next_step() -> str:
    return _t("Continua", "Continue")


def skip() -> str:
    return _t("Salta questo file", "Skip this file")


def same_settings() -> str:
    return _t("Stesse impostazioni del file precedente.", "Same settings as the previous file.")


def change() -> str:
    return _t("Cambia", "Change")


def no_audio() -> str:
    return _t(
        "Questo video non ha audio: non c'è niente da togliere.",
        "This video has no sound: nothing to remove.",
    )


def try_aggressive() -> str:
    return _t("Prova Aggressivo", "Try Aggressive")


def retry() -> str:
    return _t("Riprova", "Try Again")


def position(i: int, n: int) -> str:
    return _t(f"{i} DI {n}", f"{i} OF {n}")


def level_label(key: str) -> str:
    return levels.get(key).label[i18n.language()]


def level_description(key: str) -> str:
    return levels.get(key).description[i18n.language()]


def mode_solid() -> str:
    return _t("Nero", "Black")


def mode_solid_hint() -> str:
    return _t("Un rettangolo pieno. Il più sicuro.", "A solid box. The safest.")


def mode_pixel() -> str:
    return _t("Pixel", "Pixels")


def mode_pixel_hint() -> str:
    return _t("Blocchi grossi, meno invasivo.", "Large blocks, less stark.")


def margin_hint() -> str:
    return _t(
        "Allarga la copertura oltre il volto trovato: capelli, orecchie, profilo.",
        "Widens the cover beyond the detected face: hair, ears, profile.",
    )


def audio_remove() -> str:
    return _t("Togli l'audio", "Remove the sound")


def audio_remove_hint() -> str:
    return _t("Consigliato.", "Recommended.")


def audio_keep() -> str:
    return _t("Mantieni l'audio", "Keep the sound")


def audio_keep_hint() -> str:
    return _t("Le voci possono identificare.", "Voices can identify people.")


# Guide: picture
def analyzing(pct: int) -> str:
    return _t(f"Cerco i volti… {pct}%", f"Looking for faces… {pct}%")


def faces_found(n: int) -> str:
    if _italian():
        return "1 volto trovato" if n == 1 else f"{n} volti trovati"
    return "1 face found" if n == 1 else f"{n} faces found"


def no_face_found() -> str:
    return _t("Nessun volto trovato", "No face found")


def to_review() -> str:
    return _t(
        "Alcuni volti sono incerti: controlla bene.", "Some faces are uncertain: check carefully."
    )


def play() -> str:
    return _t("Riproduci l'anteprima", "Play the preview")


def pause() -> str:
    return _t("Ferma", "Stop")


# Correcting boxes by hand
def correct() -> str:
    return _t("Correggi i riquadri", "Correct the boxes")


def check_boxes() -> str:
    return _t("Controlla i riquadri", "Check the boxes")


def edit_hint_image() -> str:
    return _t(
        "Trascina sull'immagine per coprire un'altra zona. Clicca un riquadro per spostarlo, "
        "ridimensionarlo o toglierlo.",
        "Drag on the picture to cover another area. Click a box to move, resize or remove it.",
    )


def edit_hint_video() -> str:
    return _t(
        "I riquadri trovati seguono il volto: se uno non è un volto, spegni la sua traccia. "
        "Quelli disegnati restano fermi nell'intervallo che scegli.",
        "Found boxes follow the face: if one is not a face, switch its track off. "
        "Drawn boxes stay still over the span you choose.",
    )


def remove_box() -> str:
    return _t("Togli il riquadro", "Remove Box")


def track_off() -> str:
    return _t("Spegni questa traccia", "Switch Track Off")


def track_on() -> str:
    return _t("Riaccendi la traccia", "Switch Track On")


def start_here() -> str:
    return _t("Inizia qui", "Start Here")


def end_here() -> str:
    return _t("Finisci qui", "End Here")


def span(a: str, b: str) -> str:
    return _t(f"Copre da {a} a {b}", f"Covers {a} to {b}")


def legend_found() -> str:
    return _t("trovato", "found")


def legend_uncertain() -> str:
    return _t("incerto", "uncertain")


def legend_drawn() -> str:
    return _t("a mano", "by hand")


def legend_off() -> str:
    return _t("spento", "off")


def done_editing() -> str:
    return _t("Fatto", "Done")


# Guide: result and export
def summary(level: str, mode: str, padding: int, audio: bool | None) -> str:
    parts = [
        level_label(level),
        mode_pixel() if mode == "pixel" else mode_solid(),
        _t(f"margine {padding}%", f"margin {padding}%"),
    ]
    if audio is not None:
        parts.append(_t("con audio", "with sound") if audio else _t("senza audio", "no sound"))
    return "  ·  ".join(parts)


def always_removed() -> str:
    return _t(
        "Tolti sempre: posizione GPS, dispositivo, date e gli altri metadati.",
        "Always removed: GPS position, device, dates and the other metadata.",
    )


def export() -> str:
    return _t("Esporta…", "Export…")


def exporting(pct: int) -> str:
    return _t(f"Esportazione {pct}%", f"Exporting {pct}%")


def cancel() -> str:
    return _t("Annulla", "Cancel")


def show_in_folder() -> str:
    return _t("Mostra nella cartella", "Show in Folder")


def next_file() -> str:
    return _t("Prossimo file", "Next file")


def done() -> str:
    return _t("Fine", "Done")


def no_faces_title() -> str:
    return _t("Nessun volto trovato", "No face found")


def no_faces_text() -> str:
    return _t(
        "Se nel file ci sono volti, resteranno scoperti. Prova una sensibilità più alta.",
        "If there are faces in the file, they will stay uncovered. Try a higher sensitivity.",
    )


def export_anyway() -> str:
    return _t("Esporta comunque", "Export anyway")


# Queue
def queue() -> str:
    return _t("Coda", "Queue")


def queue_empty() -> str:
    return _t("Nessun file.", "No files.")


def remove() -> str:
    return _t("Togli dalla coda", "Remove")


def open_in_guide() -> str:
    return _t("Apri", "Open")


def status(status: str, pct: int = 0) -> str:
    return {
        "waiting": _t("In attesa", "Waiting"),
        "analyzing": _t(f"Analisi {pct}%", f"Analysing {pct}%"),
        "ready": _t("Pronto", "Ready"),
        "review": _t("Da rivedere", "Review"),
        "no_faces": _t("Nessun volto", "No face"),
        "exporting": _t(f"Esportazione {pct}%", f"Exporting {pct}%"),
        "exported": _t("Esportato", "Exported"),
        "error": _t("Errore", "Error"),
        "cancelled": _t("Annullato", "Cancelled"),
    }[status]


def faces(n: int) -> str:
    if _italian():
        return "1 volto" if n == 1 else f"{n} volti"
    return "1 face" if n == 1 else f"{n} faces"


# First-run guide
def welcome_line() -> str:
    return _t(
        "Tutto resta su questo computer: niente rete, niente caricamenti.",
        "Everything stays on this computer: no network, no uploads.",
    )


def tip_steps() -> str:
    return _t(
        "Una scelta alla volta. L'immagine mostra subito il risultato: puoi tornare a ogni passo "
        "cliccandolo qui.",
        "One choice at a time. The picture shows the result right away: click a step here to go "
        "back to it.",
    )


def tip_correct() -> str:
    return _t(
        "Se manca un volto, aggiungilo qui. Se un riquadro non è un volto, toglilo.",
        "If a face is missing, add it here. If a box is not a face, remove it.",
    )


def tip_queue() -> str:
    return _t(
        "Ecco il tuo file: l'originale non viene mai toccato. Tutti i file di questa sessione "
        "sono nella Coda (Vista ▸ Coda, Ctrl+L).",
        "Here is your file: the original is never touched. Every file of this session is in "
        "the Queue (View ▸ Queue, Ctrl+L).",
    )


def tip_next() -> str:
    return _t("Avanti", "Next")


def tip_skip() -> str:
    return _t("Salta la guida", "Skip the guide")


def open_queue() -> str:
    return _t("Apri la coda", "Open the Queue")


def restart_guide() -> str:
    return _t("Rivedi la guida", "Show the Guide Again")


# Introduction
def welcome_title() -> str:
    return _t("Prima di cominciare", "Before you start")


def welcome_subtitle() -> str:
    return _t("Copri. Controlla. Condividi.", "Cover. Check. Share.")


def welcome_privacy() -> str:
    return _t(
        "Blurry lavora solo sul tuo computer. Copre i volti e rimuove i metadati, senza "
        "caricare nulla.",
        "Blurry works only on your computer. It covers faces and removes metadata, without "
        "uploading anything.",
    )


def welcome_safety_title() -> str:
    return _t("L'ultimo controllo è tuo", "The final check is yours")


def welcome_safety() -> str:
    return _t(
        "Il rilevatore può mancare dei volti. Guarda sempre il risultato e aggiungi a mano i "
        "riquadri che mancano prima di condividere.",
        "The detector can miss faces. Always check the result and add any missing boxes by "
        "hand before sharing.",
    )


def welcome_limits() -> str:
    return _t(
        "Corpi, tatuaggi, voci e luoghi possono ancora identificare una persona. L'audio viene "
        "tolto, salvo una tua scelta esplicita.",
        "Bodies, tattoos, voices and places can still identify a person. Sound is removed "
        "unless you explicitly choose to keep it.",
    )


def welcome_workflow_title() -> str:
    return _t("Un file, pochi passi", "One file, a few steps")


def welcome_drop() -> str:
    return _t("Trascina una foto o un video", "Drop a photo or video")


def welcome_review() -> str:
    return _t("Scegli la copertura e correggi i riquadri", "Choose the cover and correct the boxes")


def welcome_export() -> str:
    return _t("Controlla il risultato ed esporta", "Check the result and export")


def welcome_original() -> str:
    return _t(
        "Blurry crea un file nuovo. L'originale resta sul disco e negli eventuali servizi di "
        "sincronizzazione.",
        "Blurry creates a new file. The original stays on disk and in any sync services you use.",
    )


def start() -> str:
    return _t("Apri Blurry", "Start using Blurry")


# Settings
def preferences_title() -> str:
    return _t("Impostazioni", "Settings")


def processing() -> str:
    return _t("Elaborazione", "Processing")


def sensitivity() -> str:
    return _t("Sensibilità", "Sensitivity")


def cover() -> str:
    return _t("Copertura", "Cover")


def margin() -> str:
    return _t("Margine", "Margin")


def preferences_effect() -> str:
    return _t(
        "Le scelte vengono ricordate e si applicano anche al file aperto. Puoi cambiarle durante "
        "la revisione.",
        "These choices are remembered and also apply to the open file. You can change them "
        "during review.",
    )


def restore_defaults() -> str:
    return _t("Ripristina valori consigliati", "Restore recommended values")


def audio_default() -> str:
    return _t(
        "L'audio parte sempre spento. Puoi mantenerlo nella revisione di ogni video, ricordando "
        "che le voci possono identificare.",
        "Sound starts off every time. You can keep it when reviewing a video, remembering that "
        "voices can identify people.",
    )


def language_title() -> str:
    return _t("Lingua", "Language")


def language_description() -> str:
    return _t(
        "Di base Blurry usa la lingua del sistema.",
        "By default Blurry follows the system language.",
    )


def privacy_title() -> str:
    return "Privacy"


def preferences_privacy() -> str:
    return _t(
        "Nessuna rete, account o telemetria. Blurry ricorda solo le impostazioni e se hai visto "
        "la guida: mai file o cartelle recenti.",
        "No network, accounts or telemetry. Blurry remembers only preferences and whether you "
        "have seen the guide: never recent files or folders.",
    )


def guide_title() -> str:
    return _t("Guida", "Guide")


def guide_description() -> str:
    return _t(
        "Rivedi l'introduzione e i suggerimenti sul primo file.",
        "Replay the introduction and tips on your first file.",
    )


def version() -> str:
    return _t("Versione", "Version")


def updates_title() -> str:
    return _t("Aggiornamenti", "Updates")


def updates_description() -> str:
    return _t(
        "Apre le Release nel browser. Blurry non cerca aggiornamenti in automatico.",
        "Opens Releases in your browser. Blurry does not check for updates automatically.",
    )


def uninstall_title() -> str:
    return _t("Disinstalla", "Uninstall")


def uninstall() -> str:
    return _t("Disinstalla Blurry…", "Uninstall Blurry…")


def uninstall_question() -> str:
    return _t("Disinstallare Blurry?", "Uninstall Blurry?")


def uninstall_description() -> str:
    return _t(
        "Chiude Blurry, lo rimuove e cancella le impostazioni e lo stato della guida. Foto, "
        "video originali ed esportazioni restano dove sono. Reinstallando Blurry, la guida "
        "riparte dall'inizio.",
        "Quits Blurry, removes it and deletes preferences and guide progress. Original photos, "
        "videos and exports stay where they are. Reinstalling Blurry starts the guide from the "
        "beginning.",
    )


def uninstall_busy() -> str:
    return _t(
        "Attendi la fine dell'elaborazione prima di disinstallare.",
        "Wait for processing to finish before uninstalling.",
    )


def uninstall_not_packaged() -> str:
    return _t(
        "Questa copia non è installata dal pacchetto di Blurry: rimuovila con lo strumento con "
        "cui l'hai installata (per esempio pipx uninstall blurry-opsec).",
        "This copy was not installed by Blurry's installer: remove it with the tool you "
        "installed it with (for example pipx uninstall blurry-opsec).",
    )


def clear_and_quit() -> str:
    return _t("Cancella le impostazioni e chiudi", "Remove Preferences and Quit")


def uninstall_error() -> str:
    return _t("Impossibile avviare la disinstallazione.", "Could not start the uninstaller.")


# Menus
def file_menu() -> str:
    return _t("&File", "&File")


def view_menu() -> str:
    return _t("&Vista", "&View")


def help_menu() -> str:
    return _t("&Aiuto", "&Help")


def settings_menu() -> str:
    return _t("Impostazioni…", "Settings…")


def quit_app() -> str:
    return _t("Esci", "Quit")


def updates() -> str:
    return _t("Aggiornamenti di Blurry", "Blurry Updates")


# File picker (Qt's own dialogs would remember folders: see picker.py)
def picker_add() -> str:
    return _t("Aggiungi", "Add")


def picker_name() -> str:
    return _t("Nome:", "Name:")


def picker_export() -> str:
    return _t("Esporta", "Export")


def replace_title(name: str) -> str:
    return _t(f"«{name}» esiste già. Vuoi sostituirlo?", f"“{name}” already exists. Replace it?")


def replace_text() -> str:
    return _t(
        "Il file esistente verrà sovrascritto. L'originale non viene mai toccato.",
        "The existing file will be overwritten. The original is never touched.",
    )


def replace() -> str:
    return _t("Sostituisci", "Replace")


def place(key: str) -> str:
    return {
        "home": _t("Inizio", "Home"),
        "desktop": _t("Scrivania", "Desktop"),
        "downloads": _t("Download", "Downloads"),
        "pictures": _t("Immagini", "Pictures"),
        "movies": _t("Filmati", "Videos"),
        "documents": _t("Documenti", "Documents"),
    }[key]
