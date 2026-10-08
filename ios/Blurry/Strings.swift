import Foundation

/// Interface strings in Italian and English, following the system language.
/// No localisation framework: a plain table, as in the Mac app
/// (macos/Sources/Blurry/Strings.swift). Keep the two aligned: a text shared
/// by both apps changes in both.
enum L {
    static let italian = Locale.preferredLanguages.first?.hasPrefix("it") ?? false

    private static func t(_ it: String, _ en: String) -> String { italian ? it : en }

    // Home
    static var homeTitle: String { t("Scegli foto e video da coprire", "Choose the photos and videos to cover") }
    static var choosePhotos: String { t("Scegli dalle Foto", "Choose from Photos") }
    static var chooseFiles: String { t("Scegli dai File", "Choose from Files") }
    static var homeHint: String {
        t("Blurry riceve solo i file che scegli: non vede il resto della libreria.",
          "Blurry only gets the files you choose: it cannot see the rest of your library.")
    }
    static func skipped(_ n: Int) -> String {
        italian ? "\(n) file ignorati: formato non supportato." : "\(n) files skipped: unsupported format."
    }
    static var unreadable: String { t("Un file non si è potuto leggere.", "A file could not be read.") }
    static func photoName(_ n: Int) -> String { italian ? "Foto \(n)" : "Photo \(n)" }
    static func videoName(_ n: Int) -> String { "Video \(n)" }
    static var copying: String { t("Preparo i video…", "Preparing the videos…") }

    // Guide: steps
    static func stepTitle(_ step: Step) -> String {
        switch step {
        case .sensitivity: t("Sensibilità", "Sensitivity")
        case .cover: t("Copertura", "Cover")
        case .margin: t("Margine", "Margin")
        case .audio: t("Audio", "Sound")
        case .result: t("Risultato", "Result")
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
    static var skip: String { t("Salta", "Skip") }
    static var sameSettings: String {
        t("Stesse impostazioni del file precedente.", "Same settings as the previous file.")
    }
    static var change: String { t("Cambia", "Change") }
    static var tryAggressive: String { t("Prova Aggressivo", "Try Aggressive") }
    static var retry: String { t("Riprova", "Try Again") }
    static func stepCount(_ i: Int, _ n: Int) -> String { italian ? "Passo \(i) di \(n)" : "Step \(i) of \(n)" }
    static func fileCount(_ i: Int, _ n: Int) -> String { italian ? "File \(i) di \(n)" : "File \(i) of \(n)" }

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
    static var noAudio: String {
        t("Questo video non ha audio: non c'è niente da togliere.", "This video has no sound: nothing to remove.")
    }
    static var audioRemove: String { t("Togli l'audio", "Remove the sound") }
    static var audioRemoveHint: String { t("Consigliato.", "Recommended.") }
    static var audioKeep: String { t("Mantieni l'audio", "Keep the sound") }
    static var audioKeepHint: String { t("Le voci possono identificare.", "Voices can identify people.") }
    static var marginHint: String {
        t("Allarga la copertura oltre il volto trovato: capelli, orecchie, profilo.",
          "Widens the cover beyond the detected face: hair, ears, profile.")
    }

    // Guide: picture
    static var analyzing: String { t("Cerco i volti…", "Looking for faces…") }
    static func analyzing(_ pct: Int) -> String { t("Cerco i volti… \(pct)%", "Looking for faces… \(pct)%") }
    static var play: String { t("Riproduci l'anteprima", "Play the preview") }
    static var pause: String { t("Ferma", "Stop") }
    static var waiting: String { t("In attesa", "Waiting") }
    static func facesFound(_ n: Int) -> String {
        italian ? (n == 1 ? "1 volto trovato" : "\(n) volti trovati") : (n == 1 ? "1 face found" : "\(n) faces found")
    }
    static var noFaceFound: String { t("Nessun volto trovato", "No face found") }
    static var toReview: String { t("Alcuni volti sono incerti: controlla bene.", "Some faces are uncertain: check carefully.") }

    // Correcting boxes by hand
    static var correct: String { t("Correggi i riquadri", "Correct the boxes") }
    static var checkBoxes: String { t("Controlla i riquadri", "Check the boxes") }
    static var editHint: String {
        t("Trascina col dito sull'immagine per coprire un'altra zona. Tocca un riquadro per spostarlo, ridimensionarlo dagli angoli o toglierlo.",
          "Drag on the picture to cover another area. Tap a box to move it, resize it from its corners or remove it.")
    }
    static var editHintVideo: String {
        t("I riquadri trovati seguono il volto: se uno non è un volto, spegni la sua traccia. Quelli disegnati restano fermi nell'intervallo che scegli.",
          "Found boxes follow the face: if one is not a face, switch its track off. Drawn boxes stay still over the span you choose.")
    }
    static var removeBox: String { t("Togli il riquadro", "Remove Box") }
    static var selectHint: String {
        t("Tocca un riquadro per modificarlo.", "Tap a box to change it.")
    }
    static var selectHintVideo: String {
        t("Tocca un riquadro per spegnerne la traccia o cambiarne l'intervallo.",
          "Tap a box to switch its track off or change its span.")
    }
    static var trackOff: String { t("Spegni la traccia", "Switch Track Off") }
    static var trackOn: String { t("Riaccendi la traccia", "Switch Track On") }
    static var startHere: String { t("Inizia qui", "Start Here") }
    static var endHere: String { t("Finisci qui", "End Here") }
    static func span(_ a: String, _ b: String) -> String { italian ? "Copre da \(a) a \(b)" : "Covers \(a) to \(b)" }
    static var legendOff: String { t("spento", "off") }
    static var legendFound: String { t("trovato", "found") }
    static var legendUncertain: String { t("incerto", "uncertain") }
    static var legendDrawn: String { t("a mano", "by hand") }
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
    static var saveToFiles: String { t("Salva in File", "Save to Files") }
    static var share: String { t("Condividi…", "Share…") }
    static var exportQuestion: String { t("Dove va il file pulito?", "Where should the clean file go?") }
    static var exportNote: String {
        t("«Salva immagine» non c'è: salvare in Foto manderebbe il file anche in iCloud.",
          "“Save Image” is not offered: saving to Photos would send the file to iCloud too.")
    }
    static var preparing: String { t("Preparo il file…", "Preparing the file…") }
    static func exporting(_ pct: Int) -> String { t("Esportazione \(pct)%", "Exporting \(pct)%") }
    static var cancel: String { t("Annulla", "Cancel") }
    static var saved: String { t("Salvato", "Saved") }
    static var shared: String { t("Condiviso", "Shared") }
    static var nextFile: String { t("Prossimo file", "Next file") }
    static var done: String { t("Fine", "Done") }
    static var noFacesTitle: String { t("Nessun volto trovato", "No face found") }
    static var noFacesText: String {
        t("Se nel file ci sono volti, resteranno scoperti. Prova una sensibilità più alta.",
          "If there are faces in the file, they will stay uncovered. Try a higher sensitivity.")
    }
    static var exportAnyway: String { t("Esporta comunque", "Export anyway") }
    static var interrupted: String {
        t("Blurry è andato in secondo piano: il lavoro si è fermato e riparte da capo. Tienilo aperto finché finisce.",
          "Blurry went to the background: the work stopped and starts again. Keep it open until it is done.")
    }

    // Queue
    static var queue: String { t("Coda", "Queue") }
    static var queueEmpty: String { t("Nessun file.", "No files.") }
    static var remove: String { t("Togli dalla coda", "Remove") }
    static var clearQueue: String { t("Svuota la coda", "Clear the Queue") }
    static var stWaiting: String { t("In attesa", "Waiting") }
    static var stAnalyzing: String { t("Analisi", "Analysing") }
    static var stReady: String { t("Pronto", "Ready") }
    static var stReview: String { t("Da rivedere", "Review") }
    static var stNoFaces: String { t("Nessun volto", "No face") }
    static var stExporting: String { t("Esportazione", "Exporting") }
    static var stExported: String { t("Esportato", "Exported") }
    static var stError: String { t("Errore", "Error") }
    static func faces(_ n: Int) -> String {
        italian ? (n == 1 ? "1 volto" : "\(n) volti") : (n == 1 ? "1 face" : "\(n) faces")
    }

    // First-run guide
    static var welcomeLine: String {
        t("Tutto resta su questo dispositivo: niente rete, niente caricamenti.",
          "Everything stays on this device: no network, no uploads.")
    }
    static var tipSteps: String {
        t("Una scelta alla volta. L'immagine mostra subito il risultato: puoi tornare a ogni passo toccandolo qui.",
          "One choice at a time. The picture shows the result right away: tap a step here to go back to it.")
    }
    static var tipCorrect: String {
        t("Se manca un volto, aggiungilo qui. Se un riquadro non è un volto, toglilo.",
          "If a face is missing, add it here. If a box is not a face, remove it.")
    }
    static var tipQueue: String {
        t("Ecco il tuo file: l'originale non viene mai toccato. Tutti i file di questa sessione sono nella Coda.",
          "Here is your file: the original is never touched. Every file of this session is in the Queue.")
    }
    static var tipNext: String { t("Avanti", "Next") }
    static var tipSkip: String { t("Salta la guida", "Skip the guide") }
    static var restartGuide: String { t("Rivedi la guida", "Show the Guide Again") }

    // Introduction and settings
    static var welcomeTitle: String { t("Prima di cominciare", "Before you start") }
    static var welcomeSubtitle: String { t("Copri. Controlla. Condividi.", "Cover. Check. Share.") }
    static var welcomePrivacy: String {
        t("Blurry lavora solo sul tuo dispositivo. Copre i volti e rimuove i metadati, senza caricare nulla.",
          "Blurry works only on your device. It covers faces and removes metadata, without uploading anything.")
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
    static var welcomeChoose: String { t("Scegli una foto o un video", "Choose a photo or a video") }
    static var welcomeReview: String { t("Scegli la copertura e correggi i riquadri", "Choose the cover and correct the boxes") }
    static var welcomeExport: String { t("Controlla il risultato ed esporta", "Check the result and export") }
    static var welcomeOriginal: String {
        t("Blurry crea un file nuovo. L'originale resta nella libreria, e in iCloud se lo usi.",
          "Blurry creates a new file. The original stays in your library, and in iCloud if you use it.")
    }
    static var start: String { t("Apri Blurry", "Start using Blurry") }
    static var settingsTitle: String { t("Impostazioni", "Settings") }
    static var processing: String { t("Elaborazione", "Processing") }
    static var sensitivity: String { t("Sensibilità", "Sensitivity") }
    static var cover: String { t("Copertura", "Cover") }
    static var margin: String { t("Margine", "Margin") }
    static var settingsEffect: String {
        t("Le scelte vengono ricordate e si applicano anche al file aperto. Puoi cambiarle durante la revisione.",
          "These choices are remembered and also apply to the open file. You can change them during review.")
    }
    static var restoreDefaults: String { t("Ripristina valori consigliati", "Restore recommended values") }
    static var privacyTitle: String { t("Privacy", "Privacy") }
    static var settingsPrivacy: String {
        t("Nessuna rete, account o telemetria. Blurry ricorda solo le impostazioni e se hai visto la guida: mai file o foto recenti.",
          "No network, accounts or telemetry. Blurry remembers only preferences and whether you have seen the guide: never recent files or photos.")
    }
    static var guideTitle: String { t("Guida", "Guide") }
    static var aboutTitle: String { t("Informazioni", "About") }
    static var version: String { t("Versione", "Version") }
    static var updates: String { t("Aggiornamenti", "Updates") }
    static var updatesDescription: String {
        t("Apre le Release in Safari. Blurry non cerca aggiornamenti in automatico.",
          "Opens Releases in Safari. Blurry does not check for updates automatically.")
    }
    static var memoryTitle: String { t("Memoria", "Memory") }
    static var memoryPeak: String { t("Picco in questa sessione", "Peak in this session") }
    static var memoryDescription: String {
        t("Quanta memoria ha usato Blurry al massimo da quando è aperto: serve a capire fin dove arrivano le foto grandi su questo dispositivo.",
          "The most memory Blurry has used since it was opened: it shows how large a photo this device can handle.")
    }
    static var close: String { t("Chiudi", "Close") }
}
