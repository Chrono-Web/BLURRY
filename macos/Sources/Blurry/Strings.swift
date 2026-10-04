import Foundation

/// Interface strings in Italian and English, following the system language.
/// No localisation framework: a plain table, as in the Python i18n module.
enum L {
    static let italian = Locale.preferredLanguages.first?.hasPrefix("it") ?? false

    private static func t(_ it: String, _ en: String) -> String { italian ? it : en }

    // Drop window
    static var dropTitle: String { t("Trascina qui foto e video", "Drop photos and videos here") }
    static var chooseFiles: String { t("Scegli file…", "Choose Files…") }
    static var engineMissing: String {
        t("Motore non trovato. Avvia l'app con scripts/dev.py.",
          "Engine not found. Start the app with scripts/dev.py.")
    }
    static func skipped(_ n: Int) -> String {
        italian ? "\(n) file ignorati: formato non supportato." : "\(n) files skipped: unsupported format."
    }
    static var workerCrashed: String {
        t("Il motore si è fermato ed è stato riavviato.", "The engine stopped and was restarted.")
    }

    // Guide: steps
    static func stepTitle(_ step: Step) -> String {
        switch step {
        case .sensitivity: t("SENSIBILITÀ", "SENSITIVITY")
        case .cover: t("COPERTURA", "COVER")
        case .margin: t("MARGINE", "MARGIN")
        case .audio: t("AUDIO", "AUDIO")
        case .result: t("RISULTATO", "RESULT")
        }
    }
    static func stepQuestion(_ step: Step) -> String {
        switch step {
        case .sensitivity: t("Quanto deve cercare i volti?", "How hard should it look for faces?")
        case .cover: t("Come coprirli?", "How should they be covered?")
        case .margin: t("Quanto spazio attorno al volto?", "How much room around each face?")
        case .audio: t("E l'audio del video?", "What about the video's sound?")
        case .result: t("Ecco il risultato.", "Here is the result.")
        }
    }
    static var back: String { t("Indietro", "Back") }
    static var next: String { t("Continua", "Continue") }
    static var skip: String { t("Salta questo file", "Skip this file") }
    static var sameSettings: String {
        t("Stesse impostazioni del file precedente.", "Same settings as the previous file.")
    }
    static var change: String { t("Cambia", "Change") }
    static var noAudio: String {
        t("Questo video non ha audio: non c'è niente da togliere.", "This video has no sound: nothing to remove.")
    }
    static var tryAggressive: String { t("Prova Aggressivo", "Try Aggressive") }
    static var retry: String { t("Riprova", "Try Again") }
    static func position(_ i: Int, _ n: Int) -> String { italian ? "\(i) DI \(n)" : "\(i) OF \(n)" }

    static func levelLabel(_ key: String) -> String {
        switch key {
        case "base": t("Leggero", "Light")
        case "medium": t("Standard", "Standard")
        default: t("Aggressivo", "Aggressive")
        }
    }
    static func levelDescription(_ key: String) -> String {
        switch key {
        case "base": t("Solo volti evidenti e frontali", "Only clear, frontal faces")
        case "medium": t("Bilanciato per la maggior parte dei casi", "Balanced for most cases")
        default: t("Anche volti piccoli o parzialmente nascosti", "Also small or partly hidden faces")
        }
    }
    static var modeSolid: String { t("Nero", "Black") }
    static var modeSolidHint: String { t("Un rettangolo pieno. Il più sicuro.", "A solid box. The safest.") }
    static var modePixel: String { t("Pixel", "Pixels") }
    static var modePixelHint: String { t("Blocchi grossi, meno invasivo.", "Large blocks, less stark.") }
    static var marginHint: String {
        t("Allarga la copertura oltre il volto trovato: capelli, orecchie, profilo.",
          "Widens the cover beyond the detected face: hair, ears, profile.")
    }
    static var audioRemove: String { t("Togli l'audio", "Remove the sound") }
    static var audioRemoveHint: String { t("Consigliato.", "Recommended.") }
    static var audioKeep: String { t("Mantieni l'audio", "Keep the sound") }
    static var audioKeepHint: String { t("Le voci possono identificare.", "Voices can identify people.") }

    // Guide: picture
    static func analyzing(_ pct: Int) -> String { t("Cerco i volti… \(pct)%", "Looking for faces… \(pct)%") }
    static func facesFound(_ n: Int) -> String {
        italian ? (n == 1 ? "1 volto trovato" : "\(n) volti trovati") : (n == 1 ? "1 face found" : "\(n) faces found")
    }
    static var noFaceFound: String { t("Nessun volto trovato", "No face found") }
    static var toReview: String { t("Alcuni volti sono incerti: controlla bene.", "Some faces are uncertain: check carefully.") }
    static var play: String { t("Riproduci l'anteprima", "Play the preview") }
    static var pause: String { t("Ferma", "Stop") }

    // Correcting boxes by hand
    static var correct: String { t("Correggi i riquadri", "Correct the boxes") }
    static var checkBoxes: String { t("Controlla i riquadri", "Check the boxes") }
    static var editHintImage: String {
        t("Trascina sull'immagine per coprire un'altra zona. Clicca un riquadro per spostarlo, ridimensionarlo o toglierlo.",
          "Drag on the picture to cover another area. Click a box to move, resize or remove it.")
    }
    static var editHintVideo: String {
        t("I riquadri trovati seguono il volto: se uno non è un volto, spegni la sua traccia. Quelli disegnati restano fermi nell'intervallo che scegli.",
          "Found boxes follow the face: if one is not a face, switch its track off. Drawn boxes stay still over the span you choose.")
    }
    static var removeBox: String { t("Togli il riquadro", "Remove Box") }
    static var trackOff: String { t("Spegni questa traccia", "Switch Track Off") }
    static var trackOn: String { t("Riaccendi la traccia", "Switch Track On") }
    static var startHere: String { t("Inizia qui", "Start Here") }
    static var endHere: String { t("Finisci qui", "End Here") }
    static func span(_ a: String, _ b: String) -> String { italian ? "Copre da \(a) a \(b)" : "Covers \(a) to \(b)" }
    static var legendFound: String { t("trovato", "found") }
    static var legendUncertain: String { t("incerto", "uncertain") }
    static var legendDrawn: String { t("a mano", "by hand") }
    static var legendOff: String { t("spento", "off") }
    static var doneEditing: String { t("Fatto", "Done") }

    // Guide: result and export
    static func summary(level: String, mode: String, padding: Int, audio: Bool?) -> String {
        var parts = [levelLabel(level), mode == "pixel" ? modePixel : modeSolid,
                     italian ? "margine \(padding)%" : "margin \(padding)%"]
        if let audio { parts.append(audio ? t("con audio", "with sound") : t("senza audio", "no sound")) }
        return parts.joined(separator: "  ·  ")
    }
    static var alwaysRemoved: String {
        t("Tolti sempre: posizione GPS, dispositivo, date e gli altri metadati.",
          "Always removed: GPS position, device, dates and the other metadata.")
    }
    static var export: String { t("Esporta…", "Export…") }
    static func exporting(_ pct: Int) -> String { t("Esportazione \(pct)%", "Exporting \(pct)%") }
    static var cancel: String { t("Annulla", "Cancel") }
    static var saved: String { t("Salvato", "Saved") }
    static var showInFinder: String { t("Mostra nel Finder", "Show in Finder") }
    static var nextFile: String { t("Prossimo file", "Next file") }
    static var done: String { t("Fine", "Done") }
    static var noFacesTitle: String { t("Nessun volto trovato", "No face found") }
    static var noFacesText: String {
        t("Se nel file ci sono volti, resteranno scoperti. Prova una sensibilità più alta.",
          "If there are faces in the file, they will stay uncovered. Try a higher sensitivity.")
    }
    static var exportAnyway: String { t("Esporta comunque", "Export anyway") }

    // Queue
    static var queue: String { t("Coda", "Queue") }
    static var queueEmpty: String { t("Nessun file.", "No files.") }
    static var remove: String { t("Togli dalla coda", "Remove") }
    static var openInGuide: String { t("Apri", "Open") }
    static var stWaiting: String { t("In attesa", "Waiting") }
    static func stAnalyzing(_ pct: Int) -> String { t("Analisi \(pct)%", "Analysing \(pct)%") }
    static var stReady: String { t("Pronto", "Ready") }
    static var stReview: String { t("Da rivedere", "Review") }
    static var stNoFaces: String { t("Nessun volto", "No face") }
    static func stExporting(_ pct: Int) -> String { t("Esportazione \(pct)%", "Exporting \(pct)%") }
    static var stExported: String { t("Esportato", "Exported") }
    static var stError: String { t("Errore", "Error") }
    static var stCancelled: String { t("Annullato", "Cancelled") }
    static func faces(_ n: Int) -> String {
        italian ? (n == 1 ? "1 volto" : "\(n) volti") : (n == 1 ? "1 face" : "\(n) faces")
    }

    // First-run guide
    static var welcomeLine: String {
        t("Tutto resta su questo Mac: niente rete, niente caricamenti.",
          "Everything stays on this Mac: no network, no uploads.")
    }
    static var tipSteps: String {
        t("Una scelta alla volta. L'immagine mostra subito il risultato: puoi tornare a ogni passo cliccandolo qui.",
          "One choice at a time. The picture shows the result right away: click a step here to go back to it.")
    }
    static var tipCorrect: String {
        t("Se manca un volto, aggiungilo qui. Se un riquadro non è un volto, toglilo.",
          "If a face is missing, add it here. If a box is not a face, remove it.")
    }
    static var tipQueue: String {
        t("Ecco il tuo file: l'originale non viene mai toccato. Tutti i file di questa sessione sono nella Coda (Vista ▸ Coda, ⌘L).",
          "Here is your file: the original is never touched. Every file of this session is in the Queue (View ▸ Queue, ⌘L).")
    }
    static var tipNext: String { t("Avanti", "Next") }
    static var tipSkip: String { t("Salta la guida", "Skip the guide") }
    static var openQueue: String { t("Apri la coda", "Open the Queue") }
    static var restartGuide: String { t("Rivedi la guida", "Show the Guide Again") }

    // Introduction and preferences
    static var welcomeTitle: String { t("Prima di cominciare", "Before you start") }
    static var welcomeSubtitle: String { t("Copri. Controlla. Condividi.", "Cover. Check. Share.") }
    static var welcomePrivacy: String {
        t("Blurry lavora solo sul tuo computer. Copre i volti e rimuove i metadati, senza caricare nulla.",
          "Blurry works only on your computer. It covers faces and removes metadata, without uploading anything.")
    }
    static var welcomeSafetyTitle: String { t("L'ultimo controllo è tuo", "The final check is yours") }
    static var welcomeSafety: String {
        t("Il rilevatore può mancare dei volti. Guarda sempre il risultato e aggiungi a mano i riquadri che mancano prima di condividere.",
          "The detector can miss faces. Always check the result and add any missing boxes by hand before sharing.")
    }
    static var welcomeLimits: String {
        t("Corpi, tatuaggi, voci e luoghi possono ancora identificare una persona. L'audio viene tolto, salvo una tua scelta esplicita.",
          "Bodies, tattoos, voices and places can still identify a person. Sound is removed unless you explicitly choose to keep it.")
    }
    static var welcomeWorkflowTitle: String { t("Un file, pochi passi", "One file, a few steps") }
    static var welcomeDrop: String { t("Trascina una foto o un video", "Drop a photo or video") }
    static var welcomeReview: String { t("Scegli la copertura e correggi i riquadri", "Choose the cover and correct the boxes") }
    static var welcomeExport: String { t("Controlla il risultato ed esporta", "Check the result and export") }
    static var welcomeOriginal: String {
        t("Blurry crea un file nuovo. L'originale resta sul disco e negli eventuali servizi di sincronizzazione.",
          "Blurry creates a new file. The original stays on disk and in any sync services you use.")
    }
    static var start: String { t("Apri Blurry", "Start using Blurry") }
    static var preferencesTitle: String { t("Impostazioni", "Settings") }
    static var processing: String { t("Elaborazione", "Processing") }
    static var sensitivity: String { t("Sensibilità", "Sensitivity") }
    static var cover: String { t("Copertura", "Cover") }
    static var margin: String { t("Margine", "Margin") }
    static var preferencesEffect: String {
        t("Le scelte vengono ricordate e si applicano anche al file aperto. Puoi cambiarle durante la revisione.",
          "These choices are remembered and also apply to the open file. You can change them during review.")
    }
    static var restoreDefaults: String { t("Ripristina valori consigliati", "Restore recommended values") }
    static var audioDefault: String {
        t("L'audio parte sempre spento. Puoi mantenerlo nella revisione di ogni video, ricordando che le voci possono identificare.",
          "Sound starts off every time. You can keep it when reviewing a video, remembering that voices can identify people.")
    }
    static var privacyTitle: String { t("Privacy", "Privacy") }
    static var preferencesPrivacy: String {
        t("Nessuna rete, account o telemetria. Blurry ricorda solo le impostazioni e se hai visto la guida: mai file o cartelle recenti.",
          "No network, accounts or telemetry. Blurry remembers only preferences and whether you have seen the guide: never recent files or folders.")
    }
    static var guideTitle: String { t("Guida", "Guide") }
    static var guideDescription: String { t("Rivedi l'introduzione e i suggerimenti sul primo file.", "Replay the introduction and tips on your first file.") }
    static var aboutTitle: String { t("Informazioni", "About") }
    static var version: String { t("Versione", "Version") }
    static var updatesDescription: String {
        t("Apre le Release nel browser. Blurry non cerca aggiornamenti in automatico.",
          "Opens Releases in your browser. Blurry does not check for updates automatically.")
    }

    static var updatesTitle: String { t("Aggiornamenti", "Updates") }
    static var uninstallTitle: String { t("Disinstalla", "Uninstall") }
    static var uninstall: String { t("Disinstalla Blurry…", "Uninstall Blurry…") }
    static var uninstallQuestion: String { t("Disinstallare Blurry?", "Uninstall Blurry?") }
    static var uninstallDescription: String {
        t("Chiude Blurry, sposta l'app nel Cestino e cancella le impostazioni e lo stato della guida. Foto, video originali ed esportazioni restano dove sono. Reinstallando Blurry, la guida riparte dall'inizio.",
          "Quits Blurry, moves the app to the Trash and removes preferences and guide progress. Original photos, videos and exports stay where they are. Reinstalling Blurry starts the guide from the beginning.")
    }
    static var uninstallErrorTitle: String { t("Blurry non è stato disinstallato", "Blurry was not uninstalled") }
    static var uninstallError: String {
        t("Non riesco a spostare l'app nel Cestino. Se è aperta dal disco di installazione, installala prima in Applicazioni. Le impostazioni non sono state cancellate.",
          "The app could not be moved to the Trash. If it is open from the installation disk, install it in Applications first. Preferences have not been removed.")
    }

    // Menu
    static var updates: String { t("Aggiornamenti di Blurry", "Blurry Updates") }
}
