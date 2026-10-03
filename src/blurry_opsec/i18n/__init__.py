"""Interface strings in Italian and English. No i18n library: a plain table."""

from __future__ import annotations

LANGUAGES = {"it": "Italiano", "en": "English"}
_current = "en"

STRINGS: dict[str, dict[str, str]] = {
    # Header
    "tagline": {
        "it": "Copre i volti e cancella i metadati. Tutto sul tuo computer, senza rete.",
        "en": "Covers faces and strips metadata. All on your computer, with no network.",
    },
    "offline": {"it": "SENZA RETE", "en": "OFFLINE"},
    "updates": {"it": "Aggiornamenti", "en": "Updates"},
    "updates_tip": {
        "it": "Apre nel browser la pagina delle versioni. Blurry non si collega mai da solo.",
        "en": "Opens the releases page in your browser. Blurry never connects by itself.",
    },
    "language": {"it": "Lingua", "en": "Language"},
    # Drop zone and queue
    "drop_title": {"it": "Trascina qui foto e video", "en": "Drop photos and videos here"},
    "drop_formats": {
        "it": "JPEG · PNG · WebP · HEIC  —  MP4 · MOV · M4V · MKV · WebM · AVI",
        "en": "JPEG · PNG · WebP · HEIC  —  MP4 · MOV · M4V · MKV · WebM · AVI",
    },
    "choose_files": {"it": "Scegli file…", "en": "Choose files…"},
    "picker_add": {"it": "Aggiungi", "en": "Add"},
    "picker_choose_folder": {"it": "Usa questa cartella", "en": "Use this folder"},
    "place_home": {"it": "Inizio", "en": "Home"},
    "place_desktop": {"it": "Scrivania", "en": "Desktop"},
    "place_downloads": {"it": "Download", "en": "Downloads"},
    "place_pictures": {"it": "Immagini", "en": "Pictures"},
    "place_movies": {"it": "Filmati", "en": "Movies"},
    "place_documents": {"it": "Documenti", "en": "Documents"},
    "col_file": {"it": "File", "en": "File"},
    "col_faces": {"it": "Volti", "en": "Faces"},
    "col_status": {"it": "Stato", "en": "Status"},
    "queue_empty": {"it": "Nessun file in coda.", "en": "No files in the queue."},
    "review": {"it": "Rivedi", "en": "Review"},
    "remove": {"it": "Togli dalla coda", "en": "Remove"},
    "export_selected": {"it": "Esporta selezionati", "en": "Export selected"},
    "export_all": {"it": "Esporta tutti", "en": "Export all"},
    "cancel": {"it": "Annulla", "en": "Cancel"},
    # Status
    "st_waiting": {"it": "In attesa", "en": "Waiting"},
    "st_analyzing": {"it": "Analisi…", "en": "Analysing…"},
    "st_analyzing_pct": {"it": "Analisi {pct}%", "en": "Analysing {pct}%"},
    "st_ready": {"it": "Pronto da esportare", "en": "Ready to export"},
    "st_review": {"it": "Da rivedere", "en": "Please review"},
    "st_no_faces": {"it": "Nessun volto trovato", "en": "No face found"},
    "st_exporting": {"it": "Esportazione {pct}%", "en": "Exporting {pct}%"},
    "st_exported": {"it": "Esportato: {name}", "en": "Exported: {name}"},
    "st_error": {"it": "Errore: {msg}", "en": "Error: {msg}"},
    "st_cancelled": {"it": "Annullato", "en": "Cancelled"},
    "kind_image": {"it": "Foto", "en": "Photo"},
    "kind_video": {"it": "Video", "en": "Video"},
    # Settings
    "settings": {"it": "Impostazioni", "en": "Settings"},
    "level": {"it": "Sensibilità", "en": "Sensitivity"},
    "mode": {"it": "Copertura", "en": "Cover"},
    "mode_solid": {"it": "Rettangolo nero", "en": "Black box"},
    "mode_pixel": {"it": "Pixel", "en": "Pixels"},
    "padding": {"it": "Margine attorno al volto", "en": "Margin around the face"},
    "keep_audio": {"it": "Mantieni l'audio dei video", "en": "Keep video audio"},
    "audio_warning": {"it": "le voci possono identificare", "en": "voices can identify people"},
    "destination": {"it": "Dove salvare", "en": "Save to"},
    "dest_next": {"it": "Accanto", "en": "Same folder"},
    "dest_folder": {"it": "Altra cartella…", "en": "Other folder…"},
    "dest_next_tip": {
        "it": "Salva accanto all'originale, con «.blurry» nel nome.",
        "en": "Saves next to the original, with “.blurry” in the name.",
    },
    "dest_choose": {"it": "Scegli la cartella", "en": "Choose the folder"},
    "always_removed": {
        "it": "Sempre tolti: posizione GPS, dispositivo, date, miniature, profili colore, "
        "tag, capitoli, sottotitoli e tracce dati.",
        "en": "Always removed: GPS position, device, dates, thumbnails, colour profiles, "
        "tags, chapters, subtitles and data tracks.",
    },
    "reanalyze_title": {"it": "Cambiare sensibilità?", "en": "Change sensitivity?"},
    "reanalyze_text": {
        "it": "I file in coda verranno analizzati di nuovo e le correzioni fatte a mano "
        "andranno perse.",
        "en": "The files in the queue will be analysed again and manual corrections will be lost.",
    },
    # Editor
    "back": {"it": "← Coda", "en": "← Queue"},
    "done": {"it": "Fatto", "en": "Done"},
    "preview": {"it": "Anteprima del risultato", "en": "Preview result"},
    "legend_auto": {"it": "trovato", "en": "detected"},
    "legend_manual": {"it": "aggiunto a mano", "en": "added by hand"},
    "editor_help_image": {
        "it": "Trascina su un'area vuota per aggiungere un riquadro. Trascina un riquadro per "
        "spostarlo, i suoi angoli per ridimensionarlo; Canc per eliminarlo.",
        "en": "Drag on an empty area to add a box. Drag a box to move it, its corners to "
        "resize it; Delete to remove it.",
    },
    "editor_help_video": {
        "it": "Trascina sul fotogramma per coprire un'area per un intervallo di tempo. "
        "Spegni una traccia se non è un volto.",
        "en": "Drag on the frame to cover an area for a span of time. Turn a track off if "
        "it is not a face.",
    },
    "banner_no_faces": {
        "it": "Non ho trovato volti. Controlla bene: se ce ne sono, aggiungili a mano.",
        "en": "No face found. Look carefully: if there are any, add them by hand.",
    },
    "banner_flags": {
        "it": "Rilevamenti incerti: {n}. Controllali uno per uno.",
        "en": "Uncertain detections: {n}. Please check each of them.",
    },
    "tracks": {"it": "Volti nel video", "en": "Faces in the video"},
    "track_label": {"it": "Volto {n}", "en": "Face {n}"},
    "manual_ranges": {"it": "Riquadri a mano", "en": "Manual boxes"},
    "manual_label": {"it": "Riquadro {n}", "en": "Box {n}"},
    "from": {"it": "dal", "en": "from"},
    "to": {"it": "al", "en": "to"},
    "set_start": {"it": "Inizio qui", "en": "Start here"},
    "set_end": {"it": "Fine qui", "en": "End here"},
    "delete": {"it": "Elimina", "en": "Delete"},
    "flag_near_threshold": {"it": "incerto", "en": "uncertain"},
    "flag_small_face": {"it": "piccolo", "en": "small"},
    "flag_track_gap": {"it": "sparisce e ricompare", "en": "disappears and comes back"},
    "frame_of": {"it": "fotogramma {i} di {n}", "en": "frame {i} of {n}"},
    # Export confirmations
    "confirm_no_faces_title": {"it": "Nessun volto trovato", "en": "No face found"},
    "confirm_no_faces_text": {
        "it": "In {n} file non ho trovato nessun volto e non hai aggiunto riquadri.\n\n"
        "Se ci sono volti, resteranno scoperti. Esportare comunque?",
        "en": "In {n} file(s) I found no face and you added no boxes.\n\n"
        "Any faces in them will stay uncovered. Export anyway?",
    },
    "export_anyway": {"it": "Esporta comunque", "en": "Export anyway"},
    "skip_them": {"it": "Non esportarli", "en": "Skip them"},
    "quit_busy_title": {"it": "Lavoro in corso", "en": "Work in progress"},
    "quit_busy_text": {
        "it": "Un file è in elaborazione. Uscire e annullarlo?",
        "en": "A file is being processed. Quit and cancel it?",
    },
    "nothing_to_export": {
        "it": "Non c'è niente da esportare: aspetta che l'analisi finisca.",
        "en": "Nothing to export yet: wait for the analysis to finish.",
    },
    "worker_crashed": {
        "it": "Il processo di lavoro si è chiuso inaspettatamente",
        "en": "The worker process stopped unexpectedly",
    },
    "skipped_files": {
        "it": "{n} file ignorati: formato non supportato.",
        "en": "{n} file(s) ignored: unsupported format.",
    },
}


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else "en"


def language() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry["en"]
    return text.format(**kwargs) if kwargs else text
